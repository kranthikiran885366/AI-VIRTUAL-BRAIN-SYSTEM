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
from orchestrator.decision_engine import DecisionEngine, _PHASE4_AVAILABLE
from orchestrator.request_context import (
    build_request_context,
    clear_request_context,
    get_request_context,
    set_request_context,
)

# Phase 15 — Enterprise Infrastructure
from orchestrator.distributed.cluster_coordinator import ClusterCoordinator
from orchestrator.security.auth_governance import SecurityGovernanceEngine
from orchestrator.security.secrets_audit import SecretManager, AuditLogger
from orchestrator.resilience.circuit_breaker import CircuitBreaker, BulkheadIsolator
from orchestrator.resilience.dlq_disaster_recovery import DeadLetterQueue, DisasterRecoveryManager
from orchestrator.observability_platform import ObservabilityPlatform
from orchestrator.enterprise_ops import EnterpriseOpsManager

DEFAULT_AGENT_CONFIG = {}

# ─── Logging ──────────────────────────────────────────────────────────────────

os.makedirs("logs", exist_ok=True)
_stream_handler = logging.StreamHandler()
_stream_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/orchestrator.log", encoding="utf-8"),
        _stream_handler,
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

from orchestrator.autonomous_controller import AutonomousCognitiveController

# ─── Global State ─────────────────────────────────────────────────────────────

_agent_manager: Optional[AgentManager] = None
_task_scheduler: Optional[TaskScheduler] = None
_communication_controller: Optional[CommunicationController] = None
_database_manager: Optional[DatabaseManager] = None
_decision_engine: Optional[DecisionEngine] = None
_autonomous_controller: Optional[AutonomousCognitiveController] = None
_startup_time = datetime.utcnow()

# Phase 15 — Enterprise Infrastructure globals
_cluster_coordinator: Optional[ClusterCoordinator] = None
_security_engine: Optional[SecurityGovernanceEngine] = None
_secret_manager: Optional[SecretManager] = None
_audit_logger: Optional[AuditLogger] = None
_circuit_breaker: Optional[CircuitBreaker] = None
_bulkhead: Optional[BulkheadIsolator] = None
_dlq: Optional[DeadLetterQueue] = None
_disaster_recovery: Optional[DisasterRecoveryManager] = None
_observability_platform: Optional[ObservabilityPlatform] = None
_enterprise_ops: Optional[EnterpriseOpsManager] = None

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
    def autonomous_controller(self) -> Optional[AutonomousCognitiveController]:
        return _autonomous_controller

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
        cognitive_status = _autonomous_controller.get_status() if _autonomous_controller else {}
        return {
            "status": "running" if self.is_running else "stopped",
            "uptime_seconds": (datetime.utcnow() - _startup_time).total_seconds(),
            "agents": agents,
            "cognitive_controller": cognitive_status,
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
# Legacy keyword routing kept as a last-resort fallback only.
# Primary routing is handled by DecisionEngine (Phase 4 pipeline).

def _keyword_route_fallback(content: str) -> Dict[str, Any]:
    """Keyword-only fallback used when DecisionEngine is unavailable."""
    _KEYWORDS: Dict[str, List[str]] = {
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
    lower = content.lower()
    scores: Dict[str, int] = {
        agent: sum(1 for kw in kws if kw in lower)
        for agent, kws in _KEYWORDS.items()
    }
    scores = {k: v for k, v in scores.items() if v > 0}
    if not scores:
        return {
            "selectedAgent": "orchestrator_agent",
            "confidence": 0.5,
            "reasoning": "keyword fallback: no match",
            "alternativeAgents": [],
            "routing_strategy": "keyword",
            "is_fallback": True,
        }
    best = max(scores, key=lambda k: scores[k])
    alts = sorted([a for a in scores if a != best], key=lambda k: scores[k], reverse=True)[:2]
    return {
        "selectedAgent": best,
        "confidence": min(0.60, 0.35 + scores[best] * 0.08),
        "reasoning": f"keyword fallback: {scores[best]} match(es) for {best}",
        "alternativeAgents": alts,
        "routing_strategy": "keyword",
        "is_fallback": True,
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

        if not settings.DEBUG and not settings.SECURITY_ENABLED:
            logger.warning(
                "SECURITY WARNING: SECURITY_ENABLED=false in non-debug mode. "
                "Set SECURITY_ENABLED=true and configure JWT_SECRET_KEY for production."
            )

        _database_manager = DatabaseManager(DatabaseConfig(database_path=_resolve_database_path(settings.DATABASE_URL)))
        _database_manager.initialize()
        db_health = _database_manager.health_check()
        if settings.REQUIRE_DATABASE and not db_health.get("ok"):
            raise RuntimeError(f"Database health check failed: {db_health.get('error', 'unknown error')}")

        broker = get_message_broker()
        await asyncio.wait_for(broker.start(), timeout=float(settings.STARTUP_TIMEOUT))
        logger.info("[OK] Message broker started")

        lifecycle = get_lifecycle_manager()
        await asyncio.wait_for(lifecycle.start(), timeout=float(settings.STARTUP_TIMEOUT))
        logger.info("[OK] Lifecycle manager started")

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
        logger.info("[OK] Communication controller started")

        # Initialize agent manager and load concrete agent implementations
        default_agents = [
            "memory_agent", "emotion_agent", "decision_agent",
            "learning_agent", "reasoning_agent", "creativity_agent", "task_agent",
            "planning_agent", "perception_agent", "language_agent", "social_agent",
            "motivation_agent", "ethics_agent", "eyes_agent", "ear_agent", "mouth_agent",
        ]
        default_agent_config = {"agents": {name: {} for name in default_agents}}
        global _agent_manager
        _agent_manager = AgentManager(default_agent_config)
        await asyncio.wait_for(_agent_manager.initialize(), timeout=float(settings.STARTUP_TIMEOUT))
        await asyncio.wait_for(_agent_manager.start(), timeout=float(settings.STARTUP_TIMEOUT))
        logger.info(f"[OK] Agent manager started with {len(_agent_manager.agents)} agents")

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
        logger.info(f"[OK] Task scheduler started with {len(_task_scheduler.workers)} workers")

        # Register loaded agents with lifecycle manager
        for agent_id, agent_instance in _agent_manager.agents.items():
            await lifecycle.register_agent(agent_id, agent_id.replace("_agent", ""), agent_instance)
            lifecycle.agents[agent_id]["is_running"] = True
            lifecycle.agent_health[agent_id].status = "healthy"

        logger.info(f"[OK] {len(_agent_manager.agents)} agents registered")

        # ── Phase 4: Decision Engine ──────────────────────────────────────
        global _decision_engine
        _decision_engine = DecisionEngine.from_config_file("config/decision_config.yaml")
        await _decision_engine.initialize()
        await _decision_engine.start()
        # Sync agent capability registry into the decision engine
        _snapshot = _agent_manager.get_capability_snapshot()
        _decision_engine.update_agent_registry(
            available_agents=_snapshot["available_agents"],
            agent_capabilities=_snapshot["agent_capabilities"],
            agent_health=_snapshot["agent_health"],
            agent_load=_snapshot["agent_load"],
        )
        logger.info(f"[OK] Decision engine started (phase4={_PHASE4_AVAILABLE})")

        # ── Phase 14: Autonomous Cognitive Controller ──────────────────────
        global _autonomous_controller
        _autonomous_controller = AutonomousCognitiveController(settings.model_dump())
        _autonomous_controller.wire(
            agent_manager=_agent_manager,
            lifecycle_manager=lifecycle,
            task_scheduler=_task_scheduler,
            message_broker=broker,
            communication_controller=_communication_controller,
        )
        await _autonomous_controller.start()
        logger.info("[OK] Autonomous Cognitive Controller started (Phase 14)")

        # ── Phase 15: Enterprise Infrastructure ───────────────────────────
        global _cluster_coordinator, _security_engine, _secret_manager
        global _audit_logger, _circuit_breaker, _bulkhead
        global _dlq, _disaster_recovery, _observability_platform, _enterprise_ops

        # Distributed cluster coordinator
        _cluster_coordinator = ClusterCoordinator(config={
            "cluster": {
                "node_id": settings.CLUSTER_NODE_ID,
                "heartbeat_timeout_seconds": settings.CLUSTER_HEARTBEAT_INTERVAL,
                "renew_interval_seconds": max(1, settings.CLUSTER_HEARTBEAT_INTERVAL // 3),
                "lease_duration_seconds": settings.CLUSTER_LEADER_LEASE_TTL,
            }
        })
        await _cluster_coordinator.start()
        logger.info("[OK] Cluster Coordinator started (Phase 15)")

        # Security governance
        _security_engine = SecurityGovernanceEngine()
        _secret_manager = SecretManager()
        _audit_logger = _secret_manager.get_audit_logger()
        logger.info("[OK] Security Governance & Audit initialized (Phase 15)")

        # Resilience infrastructure
        _circuit_breaker = CircuitBreaker(
            name="orchestrator-main",
            failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            recovery_timeout=settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
        )
        _bulkhead = BulkheadIsolator(name="orchestrator-main", max_concurrent=20, max_queue=100)
        _dlq = DeadLetterQueue(max_size=settings.DLQ_MAX_SIZE)
        _disaster_recovery = DisasterRecoveryManager()
        logger.info("[OK] Circuit Breaker, Bulkhead, DLQ & DR initialized (Phase 15)")

        # Observability platform
        _observability_platform = ObservabilityPlatform()
        logger.info("[OK] Observability Platform initialized (Phase 15)")

        # Enterprise operations
        _enterprise_ops = EnterpriseOpsManager()
        # Register config reload source
        _enterprise_ops.config_reloader.register_source(
            "orchestrator_settings", lambda: settings.reload()
        )
        logger.info("[OK] Enterprise Operations Manager initialized (Phase 15)")

        logger.info(f"[OK] API server ready on http://0.0.0.0:{settings.PORT}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
        try:
            if _autonomous_controller:
                await _autonomous_controller.stop()
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
        # Phase 15 shutdown
        if _cluster_coordinator:
            await asyncio.wait_for(_cluster_coordinator.stop(), timeout=float(settings.SHUTDOWN_TIMEOUT))
        # Phase 14 shutdown
        if _autonomous_controller:
            await asyncio.wait_for(_autonomous_controller.stop(), timeout=float(settings.SHUTDOWN_TIMEOUT))
        if _decision_engine:
            await asyncio.wait_for(_decision_engine.stop(), timeout=float(settings.SHUTDOWN_TIMEOUT))
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
@app.get("/status")
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

@app.get("/metrics")
async def get_metrics_alias():
    return runtime_observability.snapshot().__dict__

# ─── Agent Endpoints ──────────────────────────────────────────────────────────

@app.get("/agents")
@app.get("/agents/status")
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

class RouteRequest(BaseModel):
    content: str
    agent_hint: Optional[str] = None
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    priority: str = "normal"


@app.post("/route")
async def route_request(body: RouteRequest):
    """Phase 4 production routing — intent analysis + capability-based agent selection."""
    _ctx = get_request_context()
    context = {
        "agent_hint": body.agent_hint,
        "user_id": body.user_id,
        "conversation_id": body.conversation_id,
        "priority": body.priority,
        "request_id": _ctx.request_id if _ctx else None,
        "correlation_id": _ctx.correlation_id if _ctx else None,
        "trace_id": _ctx.trace_id if _ctx else None,
    }

    if _decision_engine is not None:
        # Sync registry on every route call so health/load stay current
        if _agent_manager is not None:
            snapshot = _agent_manager.get_capability_snapshot()
            _decision_engine.update_agent_registry(
                available_agents=snapshot["available_agents"],
                agent_capabilities=snapshot["agent_capabilities"],
                agent_health=snapshot["agent_health"],
                agent_load=snapshot["agent_load"],
            )
        result = await _decision_engine.route_request(body.content, context)
        # Normalise to camelCase keys expected by frontend
        return {
            "selectedAgent": result.get("selected_agent"),
            "confidence": result.get("confidence"),
            "reasoning": result.get("reasoning"),
            "alternativeAgents": result.get("alternative_agents", []),
            "routingStrategy": result.get("routing_strategy"),
            "isFallback": result.get("is_fallback", False),
            "intent": result.get("intent"),
            "intentConfidence": result.get("intent_confidence"),
            "routingConfidence": result.get("routing_confidence"),
            "combinedConfidence": result.get("combined_confidence"),
            "explanation": result.get("explanation"),
            "decisionId": result.get("decision_id"),
            "correlationId": result.get("correlation_id"),
            "traceId": result.get("trace_id"),
            "latencyMs": result.get("latency_ms"),
            "timestamp": result.get("timestamp"),
            "selectedAgents": result.get("selected_agents", [result.get("selected_agent")]),
            "multiAgent": result.get("multi_agent", False),
        }

    # DecisionEngine not yet initialised — keyword fallback
    return _keyword_route_fallback(body.content)


@app.post("/route/feedback")
async def route_feedback(body: Dict[str, Any]):
    """
    Record execution outcome for a previous routing decision.
    Feeds back into the confidence engine for future routing calibration.
    """
    agent_name = body.get("agent_name", "")
    success = bool(body.get("success", True))
    if not agent_name:
        raise HTTPException(status_code=422, detail="agent_name is required")
    if _decision_engine is not None:
        _decision_engine.record_agent_outcome(agent_name, success)
    return {
        "status": "recorded",
        "agent_name": agent_name,
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/route/status")
async def route_status():
    """Return current Decision Engine status and metrics."""
    if _decision_engine is None:
        return {"status": "not_initialized"}
    return await _decision_engine.get_status()


# ─── Phase 14 Cognitive Controller Endpoints ─────────────────────────────────

@app.get("/api/v1/cognitive/state")
async def get_cognitive_state():
    """Return synchronized Global Cognitive State."""
    if _autonomous_controller is None:
        raise HTTPException(status_code=503, detail="Autonomous Cognitive Controller not running")
    return _autonomous_controller.get_global_state()


@app.get("/api/v1/cognitive/reports")
async def get_cognitive_reports(limit: int = 50):
    """Return monitoring reports history."""
    if _autonomous_controller is None:
        raise HTTPException(status_code=503, detail="Autonomous Cognitive Controller not running")
    return _autonomous_controller.monitoring_engine.get_report_history(limit=limit)


@app.post("/api/v1/cognitive/heal")
async def trigger_cognitive_healing(body: Dict[str, Any]):
    """Trigger a self-healing action on a target agent."""
    if _autonomous_controller is None:
        raise HTTPException(status_code=503, detail="Autonomous Cognitive Controller not running")
    target_agent = body.get("target_agent")
    reason = body.get("reason", "Manual trigger")
    if not target_agent:
        raise HTTPException(status_code=422, detail="target_agent is required")
    action = await _autonomous_controller.healing_engine.recover_agent(
        target_agent=target_agent,
        reason=reason,
        triggered_by="api_request",
    )
    return action.to_dict()


@app.post("/api/v1/cognitive/optimize")
async def trigger_cognitive_optimization():
    """Trigger an on-demand adaptive execution optimization cycle."""
    if _autonomous_controller is None:
        raise HTTPException(status_code=503, detail="Autonomous Cognitive Controller not running")
    session = await _autonomous_controller.adaptive_optimizer.run_optimization_cycle()
    return session.to_dict()


@app.get("/api/v1/cognitive/policies")
async def list_cognitive_policies():
    """List operational policies."""
    if _autonomous_controller is None:
        raise HTTPException(status_code=503, detail="Autonomous Cognitive Controller not running")
    return _autonomous_controller.policy_engine.list_policies()


@app.post("/api/v1/cognitive/policies")
async def create_cognitive_policy(body: Dict[str, Any]):
    """Register or update an operational policy."""
    if _autonomous_controller is None:
        raise HTTPException(status_code=503, detail="Autonomous Cognitive Controller not running")
    from orchestrator.cognitive_models import Policy
    try:
        policy = Policy.from_dict(body)
        success = _autonomous_controller.policy_engine.register_policy(policy)
        if not success:
            raise HTTPException(status_code=400, detail="Invalid policy configuration")
        return policy.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/cognitive/analytics")
async def get_cognitive_analytics():
    """Return execution analytics."""
    if _autonomous_controller is None:
        raise HTTPException(status_code=503, detail="Autonomous Cognitive Controller not running")
    hardware = _autonomous_controller.resource_governor.get_hardware_utilization()
    analytics = _autonomous_controller.execution_analytics.generate_analytics(
        cpu_utilization=hardware["cpu"],
        memory_utilization=hardware["memory"],
        gpu_utilization=hardware["gpu"],
    )
    return analytics.to_dict()

# ─── Phase 15: Enterprise API Endpoints ──────────────────────────────────────

@app.get("/api/v1/cluster/status")
async def get_cluster_status():
    """Return cluster coordinator status."""
    if _cluster_coordinator is None:
        raise HTTPException(status_code=503, detail="Cluster coordinator not running")
    return _cluster_coordinator.get_status()


@app.get("/api/v1/cluster/nodes")
async def list_cluster_nodes():
    """List registered cluster nodes."""
    if _cluster_coordinator is None:
        raise HTTPException(status_code=503, detail="Cluster coordinator not running")
    return _cluster_coordinator.node_registry.list_nodes()


@app.get("/api/v1/security/status")
async def get_security_status():
    """Return security governance status."""
    if _security_engine is None:
        raise HTTPException(status_code=503, detail="Security engine not initialized")
    return _security_engine.get_status()


@app.get("/api/v1/security/audit")
async def get_audit_log(limit: int = 100):
    """Return recent audit log entries."""
    if _audit_logger is None:
        raise HTTPException(status_code=503, detail="Audit logger not initialized")
    return _audit_logger.export_events()[-limit:]


@app.get("/api/v1/resilience/circuit-breaker")
async def get_circuit_breaker_status():
    """Return circuit breaker status."""
    if _circuit_breaker is None:
        raise HTTPException(status_code=503, detail="Circuit breaker not initialized")
    return _circuit_breaker.get_stats()


@app.post("/api/v1/resilience/circuit-breaker/reset")
async def reset_circuit_breaker():
    """Reset circuit breaker to CLOSED state."""
    if _circuit_breaker is None:
        raise HTTPException(status_code=503, detail="Circuit breaker not initialized")
    _circuit_breaker.reset()
    return {"status": "reset", "state": _circuit_breaker.state.value}


@app.get("/api/v1/resilience/dlq")
async def get_dlq_status():
    """Return dead-letter queue status."""
    if _dlq is None:
        raise HTTPException(status_code=503, detail="DLQ not initialized")
    return _dlq.get_stats()


@app.get("/api/v1/resilience/dlq/entries")
async def list_dlq_entries(status: Optional[str] = None, limit: int = 50):
    """List DLQ entries."""
    if _dlq is None:
        raise HTTPException(status_code=503, detail="DLQ not initialized")
    entries = _dlq.list_entries(status=status, limit=limit)
    return [e.to_dict() for e in entries]


@app.get("/api/v1/resilience/disaster-recovery")
async def get_dr_status():
    """Return disaster recovery readiness status."""
    if _disaster_recovery is None:
        raise HTTPException(status_code=503, detail="DR not initialized")
    return _disaster_recovery.get_recovery_status()


@app.post("/api/v1/resilience/disaster-recovery/backup")
async def create_backup(body: Dict[str, Any]):
    """Create a backup manifest."""
    if _disaster_recovery is None:
        raise HTTPException(status_code=503, detail="DR not initialized")
    components = body.get("components", ["orchestrator", "agents", "memory"])
    manifest = _disaster_recovery.create_backup(components=components, metadata=body.get("metadata"))
    return manifest.to_dict()


@app.post("/api/v1/resilience/disaster-recovery/failover-test")
async def simulate_failover():
    """Simulate failover for DR validation."""
    if _disaster_recovery is None:
        raise HTTPException(status_code=503, detail="DR not initialized")
    return _disaster_recovery.simulate_failover()


@app.get("/api/v1/observability/metrics")
async def get_observability_metrics():
    """Return Prometheus-format metrics."""
    if _observability_platform is None:
        raise HTTPException(status_code=503, detail="Observability platform not initialized")
    return Response(content=_observability_platform.metrics.export_text(), media_type="text/plain")


@app.get("/api/v1/observability/traces")
async def get_traces(limit: int = 50):
    """Return recent traces."""
    if _observability_platform is None:
        raise HTTPException(status_code=503, detail="Observability platform not initialized")
    return _observability_platform.tracing.get_traces(limit=limit)


@app.get("/api/v1/observability/slo")
async def get_slo_status():
    """Return SLO compliance status."""
    if _observability_platform is None:
        raise HTTPException(status_code=503, detail="Observability platform not initialized")
    return _observability_platform.slo_tracker.get_slo_status()


@app.get("/api/v1/observability/status")
async def get_observability_full_status():
    """Return full observability platform status."""
    if _observability_platform is None:
        raise HTTPException(status_code=503, detail="Observability platform not initialized")
    return _observability_platform.get_full_status()


@app.get("/api/v1/ops/status")
async def get_enterprise_ops_status():
    """Return enterprise operations status."""
    if _enterprise_ops is None:
        raise HTTPException(status_code=503, detail="Enterprise ops not initialized")
    return _enterprise_ops.get_full_status()


@app.get("/api/v1/ops/maintenance")
async def get_maintenance_status():
    """Return maintenance mode status."""
    if _enterprise_ops is None:
        raise HTTPException(status_code=503, detail="Enterprise ops not initialized")
    return _enterprise_ops.maintenance.get_status()


@app.post("/api/v1/ops/maintenance")
async def toggle_maintenance(body: Dict[str, Any]):
    """Enable or disable maintenance mode."""
    if _enterprise_ops is None:
        raise HTTPException(status_code=503, detail="Enterprise ops not initialized")
    if body.get("enabled", False):
        _enterprise_ops.maintenance.enable(
            reason=body.get("reason", "Manual activation"),
            scheduled_end=body.get("scheduled_end"),
        )
    else:
        _enterprise_ops.maintenance.disable()
    return _enterprise_ops.maintenance.get_status()


@app.get("/api/v1/ops/features")
async def list_feature_flags():
    """List all feature flags."""
    if _enterprise_ops is None:
        raise HTTPException(status_code=503, detail="Enterprise ops not initialized")
    return _enterprise_ops.features.list_flags()


@app.post("/api/v1/ops/features")
async def update_feature_flags(body: Dict[str, Any]):
    """Update feature flags."""
    if _enterprise_ops is None:
        raise HTTPException(status_code=503, detail="Enterprise ops not initialized")
    _enterprise_ops.features.bulk_update(body)
    return _enterprise_ops.features.list_flags()


@app.get("/api/v1/ops/diagnostics")
async def run_diagnostics():
    """Run cluster diagnostics."""
    if _enterprise_ops is None:
        raise HTTPException(status_code=503, detail="Enterprise ops not initialized")
    return _enterprise_ops.diagnostics.run_diagnostics()


@app.get("/api/v1/ops/dependencies")
async def check_dependencies():
    """Check optional dependency availability."""
    if _enterprise_ops is None:
        raise HTTPException(status_code=503, detail="Enterprise ops not initialized")
    return _enterprise_ops.diagnostics.check_dependencies()


@app.post("/api/v1/ops/reload")
async def reload_configuration(body: Dict[str, Any]):
    """Hot-reload configuration sources."""
    if _enterprise_ops is None:
        raise HTTPException(status_code=503, detail="Enterprise ops not initialized")
    source = body.get("source")
    return _enterprise_ops.config_reloader.reload(source_name=source)


@app.get("/api/v1/ops/upgrade-compatibility")
async def check_upgrade_compatibility():
    """Check cross-phase upgrade compatibility."""
    if _enterprise_ops is None:
        raise HTTPException(status_code=503, detail="Enterprise ops not initialized")
    return _enterprise_ops.upgrade_checker.check_compatibility()


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
