import asyncio
from collections import defaultdict
import logging
import os
import sys
import signal
import uuid as _uuid_mod
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from orchestrator.config import settings
from orchestrator.agent_communication import get_message_broker, MessageType, MessagePriority
from orchestrator.agent_lifecycle import get_lifecycle_manager
from orchestrator.agent_manager import AgentManager
from orchestrator.communication_controller import CommunicationController
from orchestrator.database import DatabaseConfig, DatabaseManager
from orchestrator.observability import runtime_observability
from orchestrator.task_scheduler import TaskScheduler
from orchestrator.execution_pipeline import execute_via_pipeline
from orchestrator.request_context import (
    build_request_context,
    clear_request_context,
    get_request_context,
    set_request_context,
)

DEFAULT_AGENT_CONFIG = {}

# ─── Logging ──────────────────────────────────────────────────────────────────

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/orchestrator.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

_rate_limit_state: Dict[str, List[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW_SECONDS = 60.0
_RATE_LIMIT_MAX_REQUESTS = 120


def _resolve_database_path(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "", 1)
    if database_url.startswith("sqlite://"):
        return database_url.replace("sqlite://", "", 1)
    return "data/brain.db"

# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Virtual Brain Orchestrator",
    description="Orchestrator for the AI Virtual Brain System — 28+ specialized agents",
    version="1.0.0",
)

_allowed_origins = settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next) -> Response:
    """Attach request context, correlation metadata, and telemetry to every request."""
    correlation_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(_uuid_mod.uuid4())
    request_id = request.headers.get("X-Request-ID") or str(_uuid_mod.uuid4())
    trace_id = request.headers.get("X-Trace-ID") or str(_uuid_mod.uuid4())
    client_host = request.client.host if request.client else "unknown"
    user_id = request.headers.get("X-User-ID")
    agent_name = request.headers.get("X-Agent-Name")

    context = build_request_context(
        correlation_id=correlation_id,
        request_id=request_id,
        trace_id=trace_id,
        user_context={"user_id": user_id, "client_host": client_host},
        agent_context={"agent_name": agent_name, "path": request.url.path},
        execution_context={"method": request.method},
    )
    token = set_request_context(context)
    request.state.request_context = context
    request.state.correlation_id = correlation_id
    request.state.request_id = request_id
    request.state.trace_id = trace_id

    now = time.time()
    history = _rate_limit_state[client_host]
    history[:] = [ts for ts in history if now - ts <= _RATE_LIMIT_WINDOW_SECONDS]
    if len(history) >= _RATE_LIMIT_MAX_REQUESTS:
        clear_request_context(token)
        runtime_observability.record_error()
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "correlation_id": correlation_id},
            headers={"X-Correlation-ID": correlation_id, "X-Request-ID": request_id, "X-Trace-ID": trace_id},
        )
    history.append(now)

    timeline = runtime_observability.begin_request(
        name=f"{request.method} {request.url.path}",
        metadata={"client_host": client_host, "user_id": user_id, "agent_name": agent_name},
    )
    start = time.perf_counter()
    try:
        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - start) * 1000:.2f}"
        runtime_observability.end_request(timeline, "success", (time.perf_counter() - start) * 1000)
        return response
    except Exception as exc:
        runtime_observability.end_request(timeline, "error", (time.perf_counter() - start) * 1000, error=str(exc))
        runtime_observability.record_error()
        raise
    finally:
        clear_request_context(token)

# ─── Global State ─────────────────────────────────────────────────────────────

_agent_manager: Optional[AgentManager] = None
_task_scheduler: Optional[TaskScheduler] = None
_communication_controller: Optional[CommunicationController] = None
_database_manager: Optional[DatabaseManager] = None
_startup_time = datetime.utcnow()

# In-memory agent state (used when no DB)
_agent_states: Dict[str, Dict[str, Any]] = {}
_memory_store: Dict[str, List[Dict]] = {}  # user_id -> memories


# ─── Orchestrator Facade ──────────────────────────────────────────────────────

class Orchestrator:
    """
    Facade class providing access to the Virtual Brain Orchestrator components.
    All components are accessed through the module-level singletons.
    """

    @property
    def agent_manager(self) -> Optional[AgentManager]:
        return _agent_manager

    @property
    def message_broker(self):
        try:
            return get_message_broker()
        except Exception:
            return None

    @property
    def lifecycle_manager(self):
        try:
            return get_lifecycle_manager()
        except Exception:
            return None

    @property
    def is_running(self) -> bool:
        return _agent_manager is not None and _agent_manager.is_running

    async def get_status(self) -> Dict[str, Any]:
        agents = {}
        if _agent_manager:
            agents = await _agent_manager.get_status()
        return {
            "status": "running" if self.is_running else "stopped",
            "uptime_seconds": (datetime.utcnow() - _startup_time).total_seconds(),
            "agents": agents,
        }

    @property
    def communication_controller(self):
        try:
            from orchestrator.communication_controller import CommunicationController
            return CommunicationController
        except Exception:
            return None

    @property
    def task_scheduler(self):
        try:
            return _task_scheduler
        except Exception:
            return None

    @property
    def health_monitor(self):
        try:
            from orchestrator.health_monitor import HealthMonitor
            return HealthMonitor
        except Exception:
            return None

# ─── Request Models ───────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    agent_name: str
    action: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    priority: str = "normal"
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None

    @field_validator("agent_name")
    @classmethod
    def validate_agent_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 128:
            raise ValueError("agent_name must be 1-128 characters")
        # Allow only alphanumeric + underscore
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("agent_name must contain only letters, digits, and underscores")
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 128:
            raise ValueError("action must be 1-128 characters")
        return v

    @field_validator("input_data")
    @classmethod
    def validate_input_data(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        # Prevent excessively large payloads
        import json
        if len(json.dumps(v)) > 1_048_576:  # 1 MB
            raise ValueError("input_data exceeds maximum allowed size of 1MB")
        return v

class SendMessageRequest(BaseModel):
    sender_agent_id: str
    recipient_agent_id: str
    message_type: str
    content: Dict[str, Any]
    priority: str = "normal"

class BroadcastRequest(BaseModel):
    sender_agent_id: str
    message_type: str
    content: Dict[str, Any]
    priority: str = "normal"

class MemoryStoreRequest(BaseModel):
    user_id: str
    content: str
    memory_type: str = "general"
    importance: float = 0.5
    tags: List[str] = []
    conversation_id: Optional[str] = None

class MemoryRecallRequest(BaseModel):
    user_id: str
    query: str
    limit: int = 10

# ─── Agent Routing Logic ──────────────────────────────────────────────────────

AGENT_KEYWORDS: Dict[str, List[str]] = {
    "memory_agent": ["remember", "recall", "memory", "forget", "store", "save", "history"],
    "emotion_agent": ["feel", "emotion", "sad", "happy", "angry", "anxious", "stress", "mood"],
    "creativity_agent": ["create", "idea", "brainstorm", "creative", "imagine", "invent", "design", "story"],
    "task_agent": ["task", "todo", "schedule", "plan", "deadline", "reminder", "organize"],
    "reasoning_agent": ["analyze", "logic", "reason", "why", "argument", "proof", "deduce"],
    "learning_agent": ["learn", "study", "understand", "teach", "tutorial", "knowledge"],
    "planning_agent": ["plan", "goal", "strategy", "roadmap", "milestone", "timeline"],
    "social_agent": ["social", "relationship", "friend", "communicate", "interact", "people"],
    "language_agent": ["write", "code", "program", "translate", "grammar", "text", "essay"],
    "motivation_agent": ["motivate", "inspire", "encourage", "stuck", "give up", "tired"],
    "ethics_agent": ["ethics", "moral", "right", "wrong", "fair", "justice", "dilemma"],
    "decision_agent": ["decide", "choice", "option", "should i", "which", "best", "compare"],
    "perception_agent": ["see", "hear", "sense", "detect", "recognize", "identify", "perceive"],
}

def route_to_agent(content: str) -> Dict[str, Any]:
    lower = content.lower()
    scores: Dict[str, int] = {}
    for agent, keywords in AGENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[agent] = score

    if not scores:
        return {
            "selectedAgent": "orchestrator_agent",
            "confidence": 0.6,
            "reasoning": "No specific agent matched — using orchestrator",
            "alternativeAgents": ["reasoning_agent", "language_agent"],
        }

    best = max(scores, key=lambda k: scores[k])
    confidence = min(0.95, 0.5 + scores[best] * 0.1)
    alts = sorted([a for a in scores if a != best], key=lambda k: scores[k], reverse=True)[:2]

    return {
        "selectedAgent": best,
        "confidence": confidence,
        "reasoning": f"Matched {scores[best]} keyword(s) for {best}",
        "alternativeAgents": alts,
    }

# ─── Agent Execution Logic ────────────────────────────────────────────────────

async def execute_agent_action(agent_name: str, action: str, input_data: Dict, user_id: Optional[str]) -> Dict:
    """Execute an agent action through the shared orchestrator execution pipeline."""
    # FIXED: declare global so assignment inside this async function mutates the
    # module-level variable instead of raising UnboundLocalError.
    global _task_scheduler

    if _task_scheduler is None:
        _task_scheduler = TaskScheduler({
            "max_concurrent_tasks": settings.MAX_CONCURRENT_TASKS,
            "task_timeout": settings.TASK_TIMEOUT,
            "message_broker": get_message_broker(),
            "communication_controller": _communication_controller,
            "agent_manager": _agent_manager,
        })
        await _task_scheduler.initialize()
        await _task_scheduler.start()

    pipeline_result = await execute_via_pipeline(
        agent_name=agent_name,
        action=action,
        input_data=input_data,
        user_id=user_id,
        conversation_id=None,
        priority="normal",
        task_scheduler=_task_scheduler,
        agent_manager=_agent_manager,
        communication_controller=_communication_controller,
        message_broker=get_message_broker(),
        timeout=float(settings.AGENT_TIMEOUT),
    )

    # FIXED: removed unreachable dead-code block that appeared after the return.
    # The pipeline handles all agent dispatch; agent-specific in-line fallbacks
    # below the return statement could never execute and caused a SyntaxError
    # risk in some Python versions.
    if pipeline_result.get("status") == "error":
        return pipeline_result.get("result", pipeline_result)

    return pipeline_result.get("result", pipeline_result)

# ─── Startup / Shutdown ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    global _agent_manager
    global _task_scheduler
    global _database_manager
    logger.info("=" * 60)
    logger.info("AI Virtual Brain Orchestrator Starting...")
    logger.info("=" * 60)

    try:
        runtime_report = settings.validate_runtime()
        if runtime_report["warnings"]:
            logger.warning(f"Runtime warnings: {runtime_report['warnings']}")
        if not runtime_report["ok"]:
            raise RuntimeError("Invalid orchestrator runtime configuration: " + "; ".join(runtime_report["errors"]))

        _database_manager = DatabaseManager(DatabaseConfig(database_path=_resolve_database_path(settings.DATABASE_URL)))
        _database_manager.initialize()
        db_health = _database_manager.health_check()
        if settings.REQUIRE_DATABASE and not db_health.get("ok"):
            raise RuntimeError(f"Database health check failed: {db_health.get('error', 'unknown error')}")

        broker = get_message_broker()
        await asyncio.wait_for(broker.start(), timeout=float(settings.STARTUP_TIMEOUT))
        logger.info("✓ Message broker started")

        lifecycle = get_lifecycle_manager()
        await asyncio.wait_for(lifecycle.start(), timeout=float(settings.STARTUP_TIMEOUT))
        logger.info("✓ Lifecycle manager started")

        global _communication_controller
        _communication_controller = CommunicationController({
            "timeout": float(settings.AGENT_TIMEOUT) if settings.AGENT_TIMEOUT else 5.0,
            "queue_limits": {
                "message_queue_size": 1000,
                "event_queue_size": 1000,
            },
            "retry": {
                "max_retries": 3,
                "backoff_seconds": 0.25,
            },
            "kafka": {"enabled": False},
            "redis": {"enabled": False},
            "max_payload_bytes": 1_048_576,
        })
        await asyncio.wait_for(_communication_controller.initialize(), timeout=float(settings.STARTUP_TIMEOUT))
        logger.info("✓ Communication controller started")

        # Initialize agent manager and load concrete agent implementations
        default_agents = [
            "orchestrator_agent", "memory_agent", "emotion_agent", "decision_agent",
            "learning_agent", "reasoning_agent", "creativity_agent", "task_agent",
            "planning_agent", "perception_agent", "language_agent", "social_agent",
            "motivation_agent", "ethics_agent", "eyes_agent", "ear_agent", "mouth_agent",
        ]
        default_agent_config = {"agents": {name: {} for name in default_agents}}
        global _agent_manager
        _agent_manager = AgentManager(default_agent_config)
        await asyncio.wait_for(_agent_manager.initialize(), timeout=float(settings.STARTUP_TIMEOUT))
        await asyncio.wait_for(_agent_manager.start(), timeout=float(settings.STARTUP_TIMEOUT))
        logger.info(f"✓ Agent manager started with {len(_agent_manager.agents)} agents")

        _task_scheduler = TaskScheduler({
            "max_concurrent_tasks": settings.MAX_CONCURRENT_TASKS,
            "task_timeout": settings.TASK_TIMEOUT,
            "message_broker": broker,
            "communication_controller": _communication_controller,
            "agent_manager": _agent_manager,
        })

        await asyncio.wait_for(_task_scheduler.initialize(), timeout=float(settings.STARTUP_TIMEOUT))
        for agent_name, agent_instance in _agent_manager.agents.items():
            await _task_scheduler.register_worker(agent_name, agent_instance, pool="agents")
        await asyncio.wait_for(_task_scheduler.start(), timeout=float(settings.STARTUP_TIMEOUT))
        logger.info(f"✓ Task scheduler started with {len(_task_scheduler.workers)} workers")

        # Register loaded agents with lifecycle manager
        for agent_id, agent_instance in _agent_manager.agents.items():
            await lifecycle.register_agent(agent_id, agent_id.replace("_agent", ""), agent_instance)
            lifecycle.agents[agent_id]["is_running"] = True
            lifecycle.agent_health[agent_id].status = "healthy"

        logger.info(f"✓ {len(_agent_manager.agents)} agents registered")
        logger.info(f"✓ API server ready on http://0.0.0.0:{settings.PORT}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
        try:
            if _agent_manager:
                await _agent_manager.stop()
            if _database_manager:
                _database_manager.shutdown()
            lifecycle = get_lifecycle_manager()
            await lifecycle.stop()
            broker = get_message_broker()
            await broker.stop()
        except Exception:
            logger.exception("Startup cleanup failed")
        raise


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down orchestrator...")
    try:
        broker = get_message_broker()
        lifecycle = get_lifecycle_manager()
        if _agent_manager:
            await asyncio.wait_for(_agent_manager.stop(), timeout=float(settings.SHUTDOWN_TIMEOUT))
        if _task_scheduler:
            await asyncio.wait_for(_task_scheduler.shutdown(), timeout=float(settings.SHUTDOWN_TIMEOUT))
        if _communication_controller:
            await asyncio.wait_for(_communication_controller.stop(), timeout=float(settings.SHUTDOWN_TIMEOUT))
        await asyncio.wait_for(lifecycle.stop(), timeout=float(settings.SHUTDOWN_TIMEOUT))
        await asyncio.wait_for(broker.stop(), timeout=float(settings.SHUTDOWN_TIMEOUT))
        if _database_manager:
            _database_manager.shutdown()
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# ─── Health Endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    lifecycle = get_lifecycle_manager()
    statuses = await lifecycle.get_all_agent_statuses()
    healthy = sum(1 for s in statuses.values() if s.get("is_running"))
    uptime = (datetime.utcnow() - _startup_time).total_seconds()
    db_health = _database_manager.health_check() if _database_manager else {"ok": True, "status": "unknown"}
    controller_status = await _communication_controller.get_status() if _communication_controller else {"status": "stopped"}

    return {
        "status": "operational" if healthy > 0 else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": uptime,
        "database": db_health,
        "scheduler": await _task_scheduler.get_status() if _task_scheduler else {"status": "stopped"},
        "controller": controller_status,
        "agents": {
            "total": len(statuses),
            "healthy": healthy,
            "unhealthy": len(statuses) - healthy,
        },
    }

@app.get("/stats")
async def get_stats():
    lifecycle = get_lifecycle_manager()
    broker = get_message_broker()
    statuses = await lifecycle.get_all_agent_statuses()
    broker_stats = await broker.get_stats()
    uptime = (datetime.utcnow() - _startup_time).total_seconds()
    observability_snapshot = runtime_observability.snapshot()
    scheduler_stats = await _task_scheduler.get_status() if _task_scheduler else {"status": "stopped"}
    controller_stats = await _communication_controller.get_status() if _communication_controller else {"status": "stopped"}

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": uptime,
        "agents": statuses,
        "broker": broker_stats,
        "scheduler": scheduler_stats,
        "controller": controller_stats,
        "observability": observability_snapshot.__dict__,
        "summary": {
            "total_agents": len(statuses),
            "running_agents": sum(1 for s in statuses.values() if s.get("is_running")),
            "healthy_agents": sum(1 for s in statuses.values() if s.get("status") == "healthy"),
            "pending_messages": broker_stats.get("queue_size", 0),
            "pending_tasks": scheduler_stats.get("queue_size", 0) if isinstance(scheduler_stats, dict) else 0,
        },
        "memory_store": {
            "users_with_memories": len(_memory_store),
            "total_memories": sum(len(v) for v in _memory_store.values()),
        },
    }

# ─── Agent Endpoints ──────────────────────────────────────────────────────────

@app.get("/agents")
async def list_agents():
    lifecycle = get_lifecycle_manager()
    statuses = await lifecycle.get_all_agent_statuses()
    return {"agents": statuses, "timestamp": datetime.utcnow().isoformat()}

@app.get("/agents/{agent_id}/status")
async def get_agent_status(agent_id: str):
    lifecycle = get_lifecycle_manager()
    status = await lifecycle.get_agent_status(agent_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return status

@app.post("/agents/{agent_id}/start")
async def start_agent(agent_id: str):
    lifecycle = get_lifecycle_manager()
    if agent_id not in lifecycle.agents:
        await lifecycle.register_agent(agent_id, agent_id.replace("_agent", ""), None)
    success = await lifecycle.start_agent(agent_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to start {agent_id}")
    return {"status": "started", "agent_id": agent_id}

@app.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    lifecycle = get_lifecycle_manager()
    success = await lifecycle.stop_agent(agent_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to stop {agent_id}")
    return {"status": "stopped", "agent_id": agent_id}

# ─── Execute Endpoint ─────────────────────────────────────────────────────────

@app.post("/execute")
async def execute_agent(request: ExecuteRequest):
    try:
        result = await execute_agent_action(
            request.agent_name,
            request.action,
            request.input_data,
            request.user_id,
        )

        # Log activity
        lifecycle = get_lifecycle_manager()
        if request.agent_name in lifecycle.agents:
            await lifecycle.record_heartbeat(request.agent_name)

        _ctx = get_request_context()
        correlation_id = (_ctx.correlation_id if _ctx else None) or str(_uuid_mod.uuid4())
        trace_id = (_ctx.trace_id if _ctx else None) or str(_uuid_mod.uuid4())
        return {
            "status": "success",
            "agent": request.agent_name,
            "action": request.action,
            "result": result,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Execute error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Memory Endpoints ─────────────────────────────────────────────────────────

@app.post("/memory/store")
async def store_memory(request: MemoryStoreRequest):
    result = await execute_agent_action(
        "memory_agent", "store",
        {"content": request.content, "memory_type": request.memory_type,
         "importance": request.importance, "tags": request.tags},
        request.user_id,
    )
    return result

@app.post("/memory/recall")
async def recall_memory(request: MemoryRecallRequest):
    result = await execute_agent_action(
        "memory_agent", "recall",
        {"query": request.query, "limit": request.limit},
        request.user_id,
    )
    return result

@app.get("/memory/{user_id}")
async def get_memories(user_id: str, limit: int = 20):
    memories = _memory_store.get(user_id, [])
    return {"memories": memories[-limit:], "count": len(memories)}

# ─── Message Endpoints ────────────────────────────────────────────────────────

@app.post("/messages/send")
async def send_message(request: SendMessageRequest):
    broker = get_message_broker()
    try:
        msg_type = MessageType[request.message_type.upper()]
        priority = MessagePriority[request.priority.upper()]
    except KeyError:
        msg_type = MessageType.STATE_UPDATE
        priority = MessagePriority.NORMAL

    message_id = await broker.send_message(
        sender_agent_id=request.sender_agent_id,
        recipient_agent_id=request.recipient_agent_id,
        message_type=msg_type,
        content=request.content,
        priority=priority,
    )
    # FIXED: SendMessageRequest is a Pydantic model, it has no .state attribute.
    # Pull correlation/trace IDs from the contextvars-bound request context instead.
    _ctx = get_request_context()
    return {
        "status": "sent",
        "message_id": message_id,
        "correlation_id": _ctx.correlation_id if _ctx else None,
        "trace_id": _ctx.trace_id if _ctx else None,
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.post("/messages/broadcast")
async def broadcast_message(request: BroadcastRequest):
    broker = get_message_broker()
    try:
        msg_type = MessageType[request.message_type.upper()]
        priority = MessagePriority[request.priority.upper()]
    except KeyError:
        msg_type = MessageType.STATE_UPDATE
        priority = MessagePriority.NORMAL

    message_id = await broker.send_message(
        sender_agent_id=request.sender_agent_id,
        recipient_agent_id=None,
        message_type=msg_type,
        content=request.content,
        priority=priority,
    )
    # FIXED: BroadcastRequest is a Pydantic model, it has no .state attribute.
    _ctx = get_request_context()
    return {
        "status": "broadcasted",
        "message_id": message_id,
        "correlation_id": _ctx.correlation_id if _ctx else None,
        "trace_id": _ctx.trace_id if _ctx else None,
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.get("/messages/history")
async def get_message_history(agent_id: Optional[str] = None, limit: int = 100):
    broker = get_message_broker()
    history = await broker.get_message_history(agent_id=agent_id, limit=limit)
    return {"messages": history, "count": len(history), "timestamp": datetime.utcnow().isoformat()}

@app.get("/messages/queue/{agent_id}")
async def get_agent_queue(agent_id: str, limit: int = 50):
    broker = get_message_broker()
    messages = await broker.get_agent_messages(agent_id=agent_id, limit=limit)
    return {
        "agent_id": agent_id,
        "messages": [m.to_dict() for m in messages],
        "count": len(messages),
        "timestamp": datetime.utcnow().isoformat(),
    }

# ─── Route Endpoint ───────────────────────────────────────────────────────────

@app.post("/route")
async def route_request(body: Dict[str, Any]):
    content = body.get("content", "")
    return route_to_agent(content)

# ─── Entry Point ──────────────────────────────────────────────────────────────

def handle_signal(signum, frame):
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info(f"Starting AI Virtual Brain Orchestrator on port {settings.PORT}")
    uvicorn.run(
        "orchestrator.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
