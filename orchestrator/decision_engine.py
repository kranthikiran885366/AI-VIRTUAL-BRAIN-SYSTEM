import asyncio
import json
import logging
import os
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from orchestrator.semantic_intent import get_intent_router, IntentRouteResult
    _SEMANTIC_ROUTING = True
except ImportError:
    _SEMANTIC_ROUTING = False
    get_intent_router = None  # type: ignore
    IntentRouteResult = None  # type: ignore

class DecisionEngine:
    """Makes decisions about task allocation and system behavior."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the decision engine with configuration."""
        self.config = config
        self.is_running = False
        
        # Initialize decision models
        self.task_classifier = None
        self.priority_model = None
        self.resource_allocator = None
        
        # Initialize decision history
        self.decision_history = []
        self._intent_router = get_intent_router() if _SEMANTIC_ROUTING else None
        self._agent_performance: Dict[str, float] = {}
        
        # Initialize metrics
        self.metrics = {
            "total_decisions": 0,
            "successful_decisions": 0,
            "failed_decisions": 0,
            "average_decision_time": 0.0
        }
    
    async def start(self):
        """Start the decision engine."""
        logger.info("Starting decision engine...")
        self.is_running = True
        
        # Load models
        await self._load_models()
        
        logger.info("Decision engine started successfully")
    
    async def stop(self):
        """Stop the decision engine."""
        logger.info("Stopping decision engine...")
        self.is_running = False
        
        # Save decision history
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

    async def route_request(self, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Public semantic routing API with confidence and fallback metadata."""
        hint = (context or {}).get("agent_name") or (context or {}).get("agent_hint")

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
                    "timestamp": datetime.utcnow().isoformat(),
                }
                self.decision_history.append(decision)
                self.metrics["total_decisions"] += 1
                self.metrics["successful_decisions"] += 1
                return decision
            except Exception as exc:
                logger.warning(f"decision_engine.semantic_route_failed error={exc}")

        # Keyword fallback
        features = {"action": content, "agent_hint": hint or ""}
        agent = await self._classify_task(features)
        decision = {
            "selected_agent": agent,
            "confidence": 0.6,
            "uncertainty": 0.4,
            "reasoning": "keyword fallback routing",
            "alternative_agents": [],
            "scores": {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.decision_history.append(decision)
        self.metrics["total_decisions"] += 1
        self.metrics["successful_decisions"] += 1
        return decision

    def record_agent_outcome(self, agent_name: str, success: bool) -> None:
        """Weight future routing by historical agent outcomes."""
        current = self._agent_performance.get(agent_name, 1.0)
        delta = 0.05 if success else -0.08
        self._agent_performance[agent_name] = max(0.2, min(1.5, current + delta))

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
        try:
            os.makedirs("logs", exist_ok=True)
            def _default(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return str(obj)
            with open("logs/decision_history.json", "w") as f:
                json.dump(self.decision_history[-1000:], f, indent=2, default=_default)
        except Exception as e:
            logger.error(f"Failed to save decision history: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the decision engine."""
        return {
            "status": "running" if self.is_running else "stopped",
            "models": {
                "task_classifier": "loaded" if self.task_classifier else "not_loaded",
                "priority_model": "loaded" if self.priority_model else "not_loaded",
                "resource_allocator": "initialized" if self.resource_allocator else "not_initialized"
            },
            "metrics": self.metrics,
            "decision_history_size": len(self.decision_history)
        }
    
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
