import asyncio
import json
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

logger = logging.getLogger(__name__)

try:
    from orchestrator.semantic_intent import get_intent_router, IntentRouteResult
    _SEMANTIC_ROUTING = True
except ImportError:
    _SEMANTIC_ROUTING = False
    get_intent_router = None  # type: ignore
    IntentRouteResult = None  # type: ignore

try:
    from orchestrator.decision_context import (
        DecisionContext, DecisionRecord, DecisionStatus,
        ExecutionFeedback, RoutingDecision, RoutingStrategy,
    )
    from orchestrator.confidence_engine import ConfidenceEngine
    from orchestrator.intent_pipeline import IntentPipeline
    from orchestrator.routing_engine import RoutingEngine
    _PHASE4_AVAILABLE = True
except ImportError:
    _PHASE4_AVAILABLE = False
    DecisionContext = None  # type: ignore
    DecisionRecord = None  # type: ignore
    DecisionStatus = None  # type: ignore
    ExecutionFeedback = None  # type: ignore
    RoutingDecision = None  # type: ignore
    RoutingStrategy = None  # type: ignore
    ConfidenceEngine = None  # type: ignore
    IntentPipeline = None  # type: ignore
    RoutingEngine = None  # type: ignore


class DecisionEngine:
    """Production Decision Intelligence Engine — Phase 4."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_running = False

        # Legacy models (kept for backward compat)
        self.task_classifier = None
        self.priority_model = None
        self.resource_allocator = None

        # Semantic router (Phase 3 component — preserved)
        self._intent_router = get_intent_router() if _SEMANTIC_ROUTING else None
        self._agent_performance: Dict[str, float] = {}

        # Phase 4 components
        _decision_cfg = config.get("decision", {})
        _conf_cfg = config.get("confidence", {})
        _routing_cfg = config.get("routing", {})
        _intent_cfg = config.get("intent", {})

        if _PHASE4_AVAILABLE:
            self._confidence_engine = ConfidenceEngine(_conf_cfg)
            self._intent_pipeline = IntentPipeline(
                confidence_engine=self._confidence_engine,
                config=_intent_cfg,
            )
            self._routing_engine = RoutingEngine(
                confidence_engine=self._confidence_engine,
                config=_routing_cfg,
            )
        else:
            self._confidence_engine = None
            self._intent_pipeline = None
            self._routing_engine = None

        # Decision history — bounded ring buffer
        _max_history = int(_decision_cfg.get("max_history", 2000))
        self.decision_history: Deque[Dict[str, Any]] = deque(maxlen=_max_history)
        self._audit_log_path: str = _decision_cfg.get("audit_log_path", "logs/decision_audit.jsonl")
        self._history_path: str = _decision_cfg.get("history_path", "logs/decision_history.json")
        self._persist_history: bool = bool(_decision_cfg.get("persist_history", True))

        # Agent capability registry snapshot (populated by AgentManager)
        self._agent_capabilities: Dict[str, List[str]] = {}
        self._agent_health: Dict[str, str] = {}
        self._agent_load: Dict[str, int] = {}
        self._available_agents: List[str] = []

        self._repository: Optional[Any] = None  # DecisionRepository (optional)

        self.metrics = {
            "total_decisions": 0,
            "successful_decisions": 0,
            "failed_decisions": 0,
            "fallback_decisions": 0,
            "average_decision_time": 0.0,
            "average_confidence": 0.0,
        }
    
    async def start(self):
        """Start the decision engine."""
        logger.info("Starting decision engine...")
        self.is_running = True
        await self._load_models()
        logger.info("Decision engine started successfully")

    async def stop(self):
        """Stop the decision engine."""
        logger.info("Stopping decision engine...")
        self.is_running = False
        await self._save_decision_history()
        logger.info("Decision engine stopped successfully")
    
    async def _load_models(self):
        """Initialize decision models and allocators."""
        try:
            self.task_classifier = None
            self.priority_model = None
            resource_config = self.config.get("resources", {
                "initial_resources": {
                    "cpu": 4,
                    "memory": 8192,
                    "gpu": 0
                }
            })
            if "initial_resources" not in resource_config:
                resource_config = {"initial_resources": resource_config}
            # ResourceAllocator is defined later in this module
            self.resource_allocator = ResourceAllocator(resource_config)
            logger.info("Decision engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize decision engine: {e}")
            # Non-fatal: create a minimal allocator so the engine stays functional
            self.resource_allocator = ResourceAllocator(
                {"initial_resources": {"cpu": 4, "memory": 8192, "gpu": 0}}
            )
    
    async def make_decision(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Make a decision about a task."""
        start_time = datetime.utcnow()
        
        try:
            # Extract task features
            features = self._extract_features(task)
            
            # Classify task
            task_type = await self._classify_task(features)
            
            # Determine priority
            priority = await self._determine_priority(features)
            
            # Allocate resources
            resources = await self._allocate_resources(task_type, priority)
            
            # Make final decision
            decision = {
                "task_type": task_type,
                "priority": priority,
                "resources": resources,
                "agent_name": self._select_agent(task_type, priority),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Update metrics
            self._update_metrics(True, start_time)
            
            # Store decision
            self.decision_history.append(decision)
            
            return decision
            
        except Exception as e:
            logger.error(f"Error making decision: {e}")
            self._update_metrics(False, start_time)
            raise
    
    def _extract_features(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features from a task."""
        return {
            "description_length": len(str(task.get("description", ""))),
            "has_due_date": bool(task.get("due_date")),
            "priority_label": str(task.get("priority", "medium")).lower(),
            "agent_hint": str(task.get("agent_name", "")).lower(),
            "topic": str(task.get("topic", "")).lower(),
            "action": str(task.get("action", "")).lower(),
        }

    async def _classify_task(self, features: Dict[str, Any]) -> str:
        """Classify task intent using semantic routing when available, keyword fallback otherwise."""
        if features.get("agent_hint"):
            return features["agent_hint"]

        text_parts = [
            features.get("action", ""),
            features.get("topic", ""),
        ]
        content = " ".join(p for p in text_parts if p).strip()
        if not content:
            return "orchestrator_agent"

        if self._intent_router is not None:
            try:
                route = self._intent_router.route(
                    content,
                    performance_weights=self._agent_performance or None,
                )
                return route.selected_agent
            except Exception:
                pass

        # Keyword fallback
        lower = content.lower()
        if any(k in lower for k in ["remember", "recall", "memory"]):
            return "memory_agent"
        if any(k in lower for k in ["feel", "emotion", "mood", "sentiment"]):
            return "emotion_agent"
        if any(k in lower for k in ["plan", "schedule", "goal", "roadmap"]):
            return "planning_agent"
        if any(k in lower for k in ["task", "todo", "deadline", "reminder"]):
            return "task_agent"
        if any(k in lower for k in ["create", "design", "story", "idea"]):
            return "creativity_agent"
        if any(k in lower for k in ["decide", "choose", "compare", "recommend"]):
            return "decision_agent"
        if any(k in lower for k in ["write", "code", "translate", "text"]):
            return "language_agent"
        return "orchestrator_agent"

    async def route_request(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Production routing API — Phase 4.
        Runs full intent analysis + capability-based routing pipeline.
        Falls back to semantic router, then keyword routing.
        Returns structured decision with audit metadata.
        """
        start = time.perf_counter()
        ctx_data = context or {}
        hint = ctx_data.get("agent_name") or ctx_data.get("agent_hint")
        request_id = ctx_data.get("request_id")
        correlation_id = ctx_data.get("correlation_id")
        trace_id = ctx_data.get("trace_id")

        # ── Phase 4 full pipeline ──────────────────────────────────────────
        if _PHASE4_AVAILABLE and self._intent_pipeline and self._routing_engine:
            try:
                return await self._route_via_pipeline(
                    content=content,
                    hint=hint,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    ctx_data=ctx_data,
                    start=start,
                )
            except Exception as exc:
                logger.warning(f"decision_engine.pipeline_failed error={exc}")

        # ── Legacy semantic router (Phase 3 fallback) ──────────────────────
        if self._intent_router is not None:
            try:
                route = self._intent_router.route(
                    content,
                    agent_hint=hint,
                    performance_weights=self._agent_performance,
                )
                decision = {
                    "selected_agent": route.selected_agent,
                    "confidence": route.confidence,
                    "uncertainty": getattr(route, "uncertainty", 0.0),
                    "reasoning": getattr(route, "reasoning", ""),
                    "alternative_agents": getattr(route, "alternative_agents", []),
                    "scores": getattr(route, "scores", {}),
                    "routing_strategy": "semantic",
                    "timestamp": datetime.utcnow().isoformat(),
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                }
                self._record_decision(decision)
                return decision
            except Exception as exc:
                logger.warning(f"decision_engine.semantic_route_failed error={exc}")

        # ── Keyword fallback ───────────────────────────────────────────────
        features = {"action": content, "agent_hint": hint or ""}
        agent = await self._classify_task(features)
        decision = {
            "selected_agent": agent,
            "confidence": 0.50,
            "uncertainty": 0.50,
            "reasoning": "keyword fallback routing",
            "alternative_agents": [],
            "scores": {},
            "routing_strategy": "keyword",
            "is_fallback": True,
            "timestamp": datetime.utcnow().isoformat(),
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        }
        self._record_decision(decision)
        return decision

    async def _route_via_pipeline(
        self,
        content: str,
        hint: Optional[str],
        request_id: Optional[str],
        correlation_id: Optional[str],
        trace_id: Optional[str],
        ctx_data: Dict[str, Any],
        start: float,
    ) -> Dict[str, Any]:
        """Full Phase 4 decision pipeline: intent → routing → confidence → audit."""
        # Build decision context
        dec_ctx = DecisionContext(
            content=content,
            agent_hint=hint,
            user_id=ctx_data.get("user_id"),
            conversation_id=ctx_data.get("conversation_id"),
            priority=ctx_data.get("priority", "normal"),
            timeout=float(ctx_data.get("timeout", 60.0) or 60.0),
            available_agents=list(self._available_agents),
            agent_health=dict(self._agent_health),
            agent_load=dict(self._agent_load),
            agent_capabilities=dict(self._agent_capabilities),
            config=dict(self.config),
        )
        if request_id:
            dec_ctx.request_id = request_id
        if correlation_id:
            dec_ctx.correlation_id = correlation_id
        if trace_id:
            dec_ctx.trace_id = trace_id

        # Populate record identity
        dec_ctx.record.request_id = dec_ctx.request_id
        dec_ctx.record.correlation_id = dec_ctx.correlation_id
        dec_ctx.record.trace_id = dec_ctx.trace_id
        dec_ctx.record.content = content
        dec_ctx.record.agent_hint = hint
        dec_ctx.record.user_id = dec_ctx.user_id
        dec_ctx.record.conversation_id = dec_ctx.conversation_id
        dec_ctx.record.status = DecisionStatus.ANALYZING

        # Step 1: Intent analysis
        normalized = self._intent_pipeline.normalize(content)
        primary_intent, all_intents = self._intent_pipeline.analyze(normalized)
        dec_ctx.record.primary_intent = primary_intent
        dec_ctx.record.intents = all_intents
        dec_ctx.record.intent_confidence = primary_intent.confidence if primary_intent else 0.0
        dec_ctx.record.status = DecisionStatus.ROUTING

        # Step 2: Routing
        routing = self._routing_engine.route(dec_ctx, self._intent_router)
        dec_ctx.record.routing = routing
        dec_ctx.record.selected_agents = [routing.selected_agent]
        dec_ctx.record.routing_confidence = routing.confidence
        dec_ctx.record.fallback_used = routing.is_fallback

        multi_agents = []
        if len(all_intents) > 1 and self._routing_engine:
            multi_agents = self._routing_engine.route_multi_agent(dec_ctx, self._intent_router)
            if multi_agents:
                dec_ctx.record.multi_agent = True
                dec_ctx.record.selected_agents = [item.selected_agent for item in multi_agents]

        # Step 3: Combined confidence
        combined = self._confidence_engine.combined_confidence(
            dec_ctx.record.intent_confidence,
            dec_ctx.record.routing_confidence,
        )
        dec_ctx.record.combined_confidence = combined

        # Step 4: Rich explanation
        rich_explanation = self._routing_engine.explain_routing(routing, dec_ctx)
        explanation = rich_explanation + " || " + self._confidence_engine.explain(
            dec_ctx.record.intent_confidence,
            dec_ctx.record.routing_confidence,
            combined,
        )
        dec_ctx.record.explanation = explanation

        # Finalize
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        dec_ctx.record.latency_ms = latency_ms
        dec_ctx.record.status = DecisionStatus.COMPLETED
        dec_ctx.record.completed_at = datetime.utcnow().isoformat()

        result = {
            "decision_id": dec_ctx.record.decision_id,
            "selected_agent": routing.selected_agent,
            "selected_agents": list(dec_ctx.record.selected_agents) or [routing.selected_agent],
            "multi_agent": bool(dec_ctx.record.multi_agent),
            "confidence": routing.confidence,
            "uncertainty": routing.uncertainty,
            "reasoning": routing.reasoning,
            "alternative_agents": routing.alternative_agents,
            "scores": routing.scores,
            "routing_strategy": routing.strategy.value,
            "is_fallback": routing.is_fallback,
            "intent": primary_intent.to_dict() if primary_intent else None,
            "all_intents": [i.to_dict() for i in all_intents],
            "intent_confidence": dec_ctx.record.intent_confidence,
            "routing_confidence": dec_ctx.record.routing_confidence,
            "combined_confidence": combined,
            "explanation": explanation,
            "request_id": dec_ctx.request_id,
            "correlation_id": dec_ctx.correlation_id,
            "trace_id": dec_ctx.trace_id,
            "timestamp": datetime.utcnow().isoformat(),
            "latency_ms": latency_ms,
        }

        self._record_decision(result)
        self._append_audit(dec_ctx.record)

        if routing.is_fallback:
            self.metrics["fallback_decisions"] += 1

        return result

    async def replay_decision(self, decision_id: str) -> Dict[str, Any]:
        """
        Replay a previous decision using its stored context.
        Requires DecisionRepository wired via set_repository().
        """
        if self._repository is None:
            return {"error": "repository_not_configured", "decision_id": decision_id}
        ctx_data = self._repository.get_replay_context(decision_id)
        if not ctx_data:
            return {"error": "decision_not_found", "decision_id": decision_id}
        content = ctx_data.get("content", "")
        replay_ctx = {
            "user_id": ctx_data.get("user_id"),
            "conversation_id": ctx_data.get("conversation_id"),
            "agent_hint": ctx_data.get("agent_hint"),
            "priority": ctx_data.get("priority", "normal"),
            "replay": True,
            "original_decision_id": decision_id,
        }
        result = await self.route_request(content, replay_ctx)
        result["replayed_from"] = decision_id
        result["is_replay"] = True
        return result

    def set_repository(self, repository: Any) -> None:
        """Wire a DecisionRepository for persistence and replay."""
        self._repository = repository

    def record_agent_outcome(self, agent_name: str, success: bool) -> None:
        """Record execution outcome — updates both legacy weights and Phase 4 confidence engine."""
        current = self._agent_performance.get(agent_name, 1.0)
        delta = 0.05 if success else -0.08
        self._agent_performance[agent_name] = max(0.2, min(1.5, current + delta))
        if self._confidence_engine:
            self._confidence_engine.record_outcome(agent_name, success)

    def update_agent_registry(
        self,
        available_agents: List[str],
        agent_capabilities: Dict[str, List[str]],
        agent_health: Optional[Dict[str, str]] = None,
        agent_load: Optional[Dict[str, int]] = None,
    ) -> None:
        """Sync agent registry snapshot used by routing engine."""
        self._available_agents = list(available_agents)
        self._agent_capabilities = dict(agent_capabilities)
        self._agent_health = dict(agent_health or {})
        self._agent_load = dict(agent_load or {})
        if self._routing_engine:
            for agent, caps in agent_capabilities.items():
                self._routing_engine.update_capability_cache(agent, caps)

    def _record_decision(self, decision: Dict[str, Any]) -> None:
        """Append to bounded decision history and update metrics."""
        self.decision_history.append(decision)
        self.metrics["total_decisions"] += 1
        self.metrics["successful_decisions"] += 1
        # Rolling average confidence
        conf = decision.get("confidence", 0.0)
        n = self.metrics["total_decisions"]
        prev_avg = self.metrics["average_confidence"]
        self.metrics["average_confidence"] = round(
            (prev_avg * (n - 1) + conf) / n, 4
        )

    def _append_audit(self, record: Any) -> None:
        """Append decision record to JSONL audit log (non-blocking best-effort)."""
        try:
            os.makedirs("logs", exist_ok=True)
            with open(self._audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), default=str) + "\n")
        except Exception as exc:
            logger.debug(f"decision_engine.audit_write_failed error={exc}")

    async def _determine_priority(self, features: Dict[str, Any]) -> int:
        """Determine task priority from task metadata."""
        label = features.get("priority_label", "medium")
        if label == "critical":
            return 1
        if label == "high":
            return 2
        if label == "medium":
            return 3
        return 4
    
    async def _allocate_resources(self, task_type: str, priority: int) -> Dict[str, Any]:
        """Allocate resources for a task based on type and priority."""
        cpu = 1
        memory = 512
        if priority == 1:
            cpu = 2
            memory = 1024
        elif priority == 2:
            cpu = 1
            memory = 768

        if task_type == "language_agent":
            memory = max(memory, 1024)
        if task_type == "memory_agent":
            memory = max(memory, 1024)
        if task_type == "decision_agent":
            cpu = max(cpu, 1)

        return {
            "cpu": min(self.resource_allocator.available_resources.get("cpu", 4), cpu),
            "memory": min(self.resource_allocator.available_resources.get("memory", 8192), memory),
            "gpu": 0,
        }
    
    def _select_agent(self, task_type: str, priority: int) -> str:
        """Select an agent to handle the task."""
        known_agents = {
            "memory_agent",
            "task_agent",
            "emotion_agent",
            "learning_agent",
            "reasoning_agent",
            "creativity_agent",
            "planning_agent",
            "perception_agent",
            "language_agent",
            "social_agent",
            "motivation_agent",
            "ethics_agent",
            "decision_agent",
            "orchestrator_agent",
        }
        if task_type in known_agents:
            return task_type
        return "orchestrator_agent"
    
    def _update_metrics(self, success: bool, start_time: datetime):
        """Update decision metrics."""
        self.metrics["total_decisions"] += 1
        if success:
            self.metrics["successful_decisions"] += 1
        else:
            self.metrics["failed_decisions"] += 1
        
        # Update average decision time
        decision_time = (datetime.utcnow() - start_time).total_seconds()
        self.metrics["average_decision_time"] = (
            (self.metrics["average_decision_time"] * (self.metrics["total_decisions"] - 1) +
             decision_time) / self.metrics["total_decisions"]
        )
    
    async def _save_decision_history(self):
        """Save decision history to file with safe serialization."""
        if not self._persist_history:
            return
        try:
            os.makedirs("logs", exist_ok=True)
            def _default(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return str(obj)
            with open(self._history_path, "w") as f:
                json.dump(list(self.decision_history), f, indent=2, default=_default)
        except Exception as e:
            logger.error(f"Failed to save decision history: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the decision engine."""
        return {
            "status": "running" if self.is_running else "stopped",
            "phase4_enabled": _PHASE4_AVAILABLE,
            "models": {
                "task_classifier": "loaded" if self.task_classifier else "not_loaded",
                "priority_model": "loaded" if self.priority_model else "not_loaded",
                "resource_allocator": "initialized" if self.resource_allocator else "not_initialized",
                "semantic_router": "loaded" if self._intent_router else "not_loaded",
                "intent_pipeline": "loaded" if self._intent_pipeline else "not_loaded",
                "routing_engine": "loaded" if self._routing_engine else "not_loaded",
                "confidence_engine": "loaded" if self._confidence_engine else "not_loaded",
            },
            "metrics": self.metrics,
            "decision_history_size": len(self.decision_history),
            "available_agents": len(self._available_agents),
            "agent_performance": dict(self._agent_performance),
        }
    
    @classmethod
    def from_config_file(
        cls,
        config_path: str = "config/decision_config.yaml",
    ) -> "DecisionEngine":
        """
        Factory: load decision_config.yaml and return a configured DecisionEngine.
        Falls back to empty config if file is missing or yaml is unavailable.
        """
        cfg: Dict[str, Any] = {}
        path = Path(config_path)
        if _YAML_AVAILABLE and path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                logger.info(f"decision_engine.config_loaded path={config_path}")
            except Exception as exc:
                logger.warning(f"decision_engine.config_load_failed path={config_path} error={exc}")
        else:
            logger.info(f"decision_engine.config_not_found path={config_path} using_defaults=true")
        return cls(cfg)

    async def initialize(self):
        """Initialize the decision engine."""
        logger.info("Initializing decision engine...")
        await self._load_models()
        logger.info("Decision engine initialized")
    
    async def process_decisions(self):
        """Process pending decisions in a loop."""
        logger.info("Starting decision processing loop...")
        while self.is_running:
            try:
                # Process any pending decisions
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in decision processing: {e}")
                await asyncio.sleep(5)
    
    async def shutdown(self):
        """Shutdown the decision engine."""
        await self.stop()

class ResourceAllocator:
    """Manages resource allocation for tasks."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # Keep a permanent copy of the initial pool so we can always restore it
        self._initial_resources: Dict[str, Any] = dict(
            config.get("initial_resources", {"cpu": 4, "memory": 8192, "gpu": 0})
        )
        self.available_resources: Dict[str, Any] = dict(self._initial_resources)
        self.allocated_resources: Dict[str, Dict[str, Any]] = {}

    def allocate(self, task_id: str, resources: Dict[str, Any]) -> bool:
        """Allocate resources for a task. Returns False if insufficient."""
        if not self._check_availability(resources):
            return False
        self.allocated_resources[task_id] = resources
        for resource, amount in resources.items():
            self.available_resources[resource] = self.available_resources.get(resource, 0) - amount
        return True

    def deallocate(self, task_id: str) -> bool:
        """Release resources held by a task."""
        if task_id not in self.allocated_resources:
            return False
        resources = self.allocated_resources.pop(task_id)
        for resource, amount in resources.items():
            # Never exceed the original pool ceiling
            restored = self.available_resources.get(resource, 0) + amount
            self.available_resources[resource] = min(restored, self._initial_resources.get(resource, restored))
        return True

    def reset(self) -> None:
        """Release all allocations and restore the full resource pool."""
        self.allocated_resources.clear()
        self.available_resources = dict(self._initial_resources)

    def _check_availability(self, resources: Dict[str, Any]) -> bool:
        for resource, amount in resources.items():
            if self.available_resources.get(resource, 0) < amount:
                return False
        return True

    def get_utilization(self) -> Dict[str, Any]:
        """Return current utilization as a fraction of the initial pool."""
        result = {}
        for resource, total in self._initial_resources.items():
            available = self.available_resources.get(resource, 0)
            used = total - available
            result[resource] = {
                "total": total,
                "used": used,
                "available": available,
                "utilization": round(used / total, 3) if total else 0.0,
            }
        return result
