"""
Emotion Context — Phase 8
Structured context threading correlation IDs, session metadata, and
multi-agent state through all emotion and motivation operations.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class EmotionContext:
    """
    Reusable context object that flows through the entire emotion pipeline.
    Carries conversation state, memory context, decision context, and
    all observability identifiers needed for audit and replay.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # ── Conversation context ──────────────────────────────────────────────────
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    last_user_message: Optional[str] = None
    message_count: int = 0

    # ── Memory context ────────────────────────────────────────────────────────
    memory_context: Dict[str, Any] = field(default_factory=dict)
    recent_memories: List[Dict[str, Any]] = field(default_factory=list)

    # ── Decision context ──────────────────────────────────────────────────────
    decision_context: Dict[str, Any] = field(default_factory=dict)
    last_routing_confidence: float = 0.0
    last_selected_agent: Optional[str] = None

    # ── Reasoning context ─────────────────────────────────────────────────────
    reasoning_context: Dict[str, Any] = field(default_factory=dict)
    last_reasoning_confidence: float = 0.0
    last_reasoning_type: Optional[str] = None

    # ── Planning context ──────────────────────────────────────────────────────
    planning_context: Dict[str, Any] = field(default_factory=dict)
    active_plan_id: Optional[str] = None
    plan_progress: float = 0.0

    # ── Learning context ──────────────────────────────────────────────────────
    learning_context: Dict[str, Any] = field(default_factory=dict)
    learning_rate: float = 0.5

    # ── Execution context ─────────────────────────────────────────────────────
    execution_context: Dict[str, Any] = field(default_factory=dict)
    consecutive_failures: int = 0
    last_execution_success: bool = True
    last_execution_latency_ms: float = 0.0

    # ── System state ──────────────────────────────────────────────────────────
    system_state: Dict[str, Any] = field(default_factory=dict)
    system_health: str = "healthy"

    # ── User interaction history ──────────────────────────────────────────────
    interaction_count: int = 0
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "created_at": self.created_at,
            "message_count": self.message_count,
            "last_user_message": (self.last_user_message or "")[:200],
            "last_routing_confidence": self.last_routing_confidence,
            "last_selected_agent": self.last_selected_agent,
            "last_reasoning_confidence": self.last_reasoning_confidence,
            "last_reasoning_type": self.last_reasoning_type,
            "active_plan_id": self.active_plan_id,
            "plan_progress": self.plan_progress,
            "learning_rate": self.learning_rate,
            "consecutive_failures": self.consecutive_failures,
            "last_execution_success": self.last_execution_success,
            "last_execution_latency_ms": self.last_execution_latency_ms,
            "system_health": self.system_health,
            "interaction_count": self.interaction_count,
            "positive_feedback_count": self.positive_feedback_count,
            "negative_feedback_count": self.negative_feedback_count,
        }

    def record_execution(
        self,
        success: bool,
        latency_ms: float = 0.0,
        agent_name: Optional[str] = None,
    ) -> None:
        """Update execution tracking fields."""
        self.last_execution_success = success
        self.last_execution_latency_ms = latency_ms
        if agent_name:
            self.last_selected_agent = agent_name
        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

    def record_feedback(self, positive: bool) -> None:
        """Record user feedback."""
        self.interaction_count += 1
        if positive:
            self.positive_feedback_count += 1
        else:
            self.negative_feedback_count += 1

    def feedback_ratio(self) -> float:
        """Return positive feedback ratio [0, 1]."""
        total = self.positive_feedback_count + self.negative_feedback_count
        if total == 0:
            return 0.5
        return self.positive_feedback_count / total
