"""
DecisionAgent — Phase 4 Production Implementation

Integrates with the Phase 4 Decision Intelligence pipeline:
- Full decision lifecycle (context, metadata, history, versioning)
- Intent-aware decision making
- Confidence-calibrated option scoring
- Decision audit trail
- Execution feedback loop
- Backward compatible with BaseAgent and AgentManager
"""

import asyncio
import logging
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

try:
    from orchestrator.decision_context import (
        DecisionRecord, DecisionStatus, ExecutionFeedback,
    )
    from orchestrator.confidence_engine import ConfidenceEngine
    _PHASE4 = True
except ImportError:
    _PHASE4 = False
    DecisionRecord = None  # type: ignore
    DecisionStatus = None  # type: ignore
    ExecutionFeedback = None  # type: ignore
    ConfidenceEngine = None  # type: ignore

logger = logging.getLogger(__name__)

_VERSION = "4.0.0"
_MAX_HISTORY = 2000


class DecisionAgent(BaseAgent):
    """
    Production Decision Agent.
    Handles decision requests, option scoring, outcome recording,
    and integrates with the Phase 4 confidence engine.
    """

    def __init__(self, agent_id: str = "decision_agent"):
        super().__init__(agent_id, "decision", version=_VERSION)
        self.capabilities = [
            "decision_making", "option_scoring", "confidence_estimation",
            "outcome_recording", "decision_history",
        ]
        # Bounded decision history
        self._decision_history: Deque[Dict[str, Any]] = deque(maxlen=_MAX_HISTORY)
        # Per-option outcome tracking for historical scoring
        self._option_outcomes: Dict[str, List[bool]] = {}
        # Confidence engine (Phase 4)
        self._confidence_engine = ConfidenceEngine() if _PHASE4 else None
        # Exploration rate for option selection
        self._exploration_rate: float = 0.05

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self):
        await super().initialize()
        self.state.update({
            "decision_count": 0,
            "success_rate": 0.0,
            "last_decision": None,
            "version": _VERSION,
        })
        logger.info(f"decision_agent.initialized agent_id={self.agent_id}")

    async def _update_state(self):
        total = len(self._decision_history)
        successes = sum(1 for d in self._decision_history if d.get("success") is True)
        self.state.update({
            "decision_count": total,
            "success_rate": round(successes / total, 3) if total else 0.0,
            "last_active": datetime.utcnow().isoformat(),
        })

    async def _process_emotions(self):
        recent = list(self._decision_history)[-10:]
        if not recent:
            return
        rate = sum(1 for d in recent if d.get("success") is True) / len(recent)
        if rate > 0.7:
            await self.update_emotion("confidence", min(1.0, self.emotions.get("confidence", 0.7) + 0.05))
            await self.update_emotion("uncertainty", max(0.0, self.emotions.get("uncertainty", 0.1) - 0.03))
        elif rate < 0.3:
            await self.update_emotion("uncertainty", min(1.0, self.emotions.get("uncertainty", 0.1) + 0.05))
            await self.update_emotion("confidence", max(0.0, self.emotions.get("confidence", 0.7) - 0.03))

    # ─── Core Decision Making ─────────────────────────────────────────────────

    async def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a decision given a context dict.
        Returns a structured decision record with confidence, explanation,
        and audit metadata.
        """
        decision_id = str(uuid.uuid4())
        goal = context.get("goal", "")
        options = context.get("options") or self._infer_options(goal)
        constraints = context.get("constraints", [])
        request_id = context.get("request_id")
        correlation_id = context.get("correlation_id")
        trace_id = context.get("trace_id")

        # Score all options
        scored = [
            {"option": opt, "score": self._score_option(opt, goal, constraints)}
            for opt in options
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)

        # Exploration vs exploitation
        import random
        if random.random() < self._exploration_rate and len(scored) > 1:
            chosen = random.choice(scored[1:])
            method = "exploration"
        else:
            chosen = scored[0] if scored else {"option": "proceed", "score": 0.5}
            method = "exploitation"

        # Confidence calibration
        raw_score = chosen["score"]
        margin = raw_score - (scored[1]["score"] if len(scored) > 1 else 0.0)
        if self._confidence_engine:
            confidence = self._confidence_engine.intent_confidence(raw_score, margin)
        else:
            confidence = round(min(0.95, 0.40 + raw_score * 0.55), 3)

        record = None
        if DecisionRecord is not None:
            record = DecisionRecord(
                decision_id=decision_id,
                request_id=request_id,
                correlation_id=correlation_id,
                trace_id=trace_id,
                version=_VERSION,
                content=goal,
                agent_hint=context.get("agent_hint"),
                status=DecisionStatus.COMPLETED,
                intent_confidence=confidence,
                routing_confidence=confidence,
                combined_confidence=confidence,
                explanation=(
                    f"Selected '{chosen['option']}' via {method} "
                    f"(score={raw_score:.3f}, confidence={confidence:.3f})"
                ),
                metrics={
                    "goal": goal,
                    "options": [opt["option"] for opt in scored],
                    "constraints": constraints,
                    "decision_method": method,
                },
            )

        decision: Dict[str, Any] = {
            "id": decision_id,
            "version": _VERSION,
            "timestamp": datetime.utcnow().isoformat(),
            "goal": goal,
            "chosen_option": chosen["option"],
            "confidence": confidence,
            "method": method,
            "all_options": scored,
            "constraints_applied": constraints,
            "success": None,
            "request_id": request_id,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "decision_context": context,
            "decision_record": record.to_dict() if record is not None else None,
            "explanation": (
                f"Selected '{chosen['option']}' via {method} "
                f"(score={raw_score:.3f}, confidence={confidence:.3f})"
            ),
        }

        self._decision_history.append(decision)
        self.state["decision_count"] = len(self._decision_history)
        self.state["last_decision"] = decision["timestamp"]

        await self.broadcast_message("decision_result", {
            "decision_id": decision_id,
            "chosen": chosen["option"],
            "confidence": confidence,
            "goal": goal,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
        })

        return decision

    async def record_outcome(self, decision_id: str, success: bool) -> bool:
        """Record execution outcome for a previous decision."""
        for d in self._decision_history:
            if d["id"] == decision_id:
                d["success"] = success
                option = d["chosen_option"]
                outcomes = self._option_outcomes.setdefault(option, [])
                outcomes.append(success)
                if len(outcomes) > 200:
                    self._option_outcomes[option] = outcomes[-200:]
                if self._confidence_engine:
                    self._confidence_engine.record_outcome(option, success)
                return True
        return False

    # ─── execute_task (AgentManager contract) ────────────────────────────────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        input_data = task.get("input_data", {}) or {}

        if action in ("decide", "make_decision", "choose"):
            return await self.make_decision(input_data)

        if action == "record_outcome":
            ok = await self.record_outcome(
                input_data.get("decision_id", ""),
                bool(input_data.get("success", True)),
            )
            return {"status": "recorded" if ok else "not_found"}

        if action == "get_stats":
            return {
                "decision_count": len(self._decision_history),
                "success_rate": self.state.get("success_rate", 0.0),
                "exploration_rate": self._exploration_rate,
                "tracked_options": len(self._option_outcomes),
                "version": _VERSION,
            }

        if action == "get_history":
            limit = int(input_data.get("limit", 50))
            return {
                "history": list(self._decision_history)[-limit:],
                "total": len(self._decision_history),
            }

        if action in ("get_status", "status"):
            return await self.get_status()

        # Default: treat content as a goal
        return await self.make_decision({
            "goal": input_data.get("content", action),
            "options": input_data.get("options", []),
            "request_id": task.get("execution_context", {}).get("request_id"),
            "correlation_id": task.get("execution_context", {}).get("correlation_id"),
            "trace_id": task.get("execution_context", {}).get("trace_id"),
        })

    # ─── Option Scoring ───────────────────────────────────────────────────────

    def _infer_options(self, goal: str) -> List[str]:
        lower = goal.lower()
        if any(w in lower for w in ["plan", "schedule", "organize"]):
            return ["create_detailed_plan", "create_quick_outline", "delegate_planning"]
        if any(w in lower for w in ["decide", "choose", "pick", "select"]):
            return ["gather_more_info", "decide_now", "defer_decision"]
        if any(w in lower for w in ["problem", "issue", "fix", "solve"]):
            return ["analyze_root_cause", "apply_quick_fix", "escalate"]
        return ["proceed", "pause_and_reflect", "seek_input"]

    def _score_option(self, option: str, goal: str, constraints: List[str]) -> float:
        base = 0.5
        goal_words = set(goal.lower().split())
        option_words = set(option.lower().replace("_", " ").split())
        overlap = len(goal_words & option_words)
        base += overlap * 0.10

        past = self._option_outcomes.get(option, [])
        if past:
            base += (sum(past) / len(past)) * 0.30

        for constraint in constraints:
            if constraint.lower() in option.lower():
                base -= 0.15

        return round(min(1.0, max(0.0, base)), 3)
