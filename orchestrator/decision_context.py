"""
Decision Context — Phase 4

Reusable dataclasses for decision lifecycle, metadata, audit trail,
and execution context that flow through the entire decision pipeline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class DecisionStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    ROUTING = "routing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    FALLBACK = "fallback"
    TIMEOUT = "timeout"


class IntentType(str, Enum):
    CONVERSATION = "conversation"
    TASK = "task"
    QUESTION = "question"
    COMMAND = "command"
    WORKFLOW = "workflow"
    INFORMATION_REQUEST = "information_request"
    ANALYSIS_REQUEST = "analysis_request"
    CREATIVE_REQUEST = "creative_request"
    PLANNING_REQUEST = "planning_request"
    UNKNOWN = "unknown"


class RoutingStrategy(str, Enum):
    SEMANTIC = "semantic"
    CAPABILITY = "capability"
    KEYWORD = "keyword"
    HINT = "hint"
    FALLBACK = "fallback"


@dataclass
class DetectedIntent:
    intent_type: IntentType
    confidence: float
    reasoning: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }


@dataclass
class RoutingDecision:
    selected_agent: str
    confidence: float
    strategy: RoutingStrategy
    reasoning: str
    alternative_agents: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    uncertainty: float = 0.0
    is_fallback: bool = False
    capability_match: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_agent": self.selected_agent,
            "confidence": round(self.confidence, 4),
            "strategy": self.strategy.value,
            "reasoning": self.reasoning,
            "alternative_agents": self.alternative_agents,
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "uncertainty": round(self.uncertainty, 4),
            "is_fallback": self.is_fallback,
            "capability_match": self.capability_match,
        }


@dataclass
class ExecutionFeedback:
    agent_name: str
    success: bool
    latency_ms: float
    retry_count: int = 0
    quality_score: float = 1.0
    error: Optional[str] = None
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "success": self.success,
            "latency_ms": round(self.latency_ms, 2),
            "retry_count": self.retry_count,
            "quality_score": round(self.quality_score, 4),
            "error": self.error,
            "resource_usage": self.resource_usage,
            "timestamp": self.timestamp,
        }


@dataclass
class DecisionRecord:
    """Full lifecycle record for a single decision — persisted to audit log."""

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    version: str = "4.0.0"

    # Input
    content: str = ""
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    agent_hint: Optional[str] = None

    # Analysis
    intents: List[DetectedIntent] = field(default_factory=list)
    primary_intent: Optional[DetectedIntent] = None

    # Routing
    routing: Optional[RoutingDecision] = None
    multi_agent: bool = False
    selected_agents: List[str] = field(default_factory=list)

    # Confidence
    intent_confidence: float = 0.0
    routing_confidence: float = 0.0
    combined_confidence: float = 0.0

    # Execution
    feedback: List[ExecutionFeedback] = field(default_factory=list)
    fallback_used: bool = False
    retry_count: int = 0

    # Lifecycle
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    latency_ms: float = 0.0

    # Observability
    explanation: str = ""
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "version": self.version,
            "content": self.content[:500],  # truncate for storage
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "agent_hint": self.agent_hint,
            "intents": [i.to_dict() for i in self.intents],
            "primary_intent": self.primary_intent.to_dict() if self.primary_intent else None,
            "routing": self.routing.to_dict() if self.routing else None,
            "multi_agent": self.multi_agent,
            "selected_agents": self.selected_agents,
            "intent_confidence": round(self.intent_confidence, 4),
            "routing_confidence": round(self.routing_confidence, 4),
            "combined_confidence": round(self.combined_confidence, 4),
            "feedback": [f.to_dict() for f in self.feedback],
            "fallback_used": self.fallback_used,
            "retry_count": self.retry_count,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "latency_ms": round(self.latency_ms, 2),
            "explanation": self.explanation,
            "error": self.error,
            "metrics": self.metrics,
        }


@dataclass
class DecisionContext:
    """
    Full context flowing through the decision pipeline.
    Carries conversation state, memory context, system state,
    and all metadata needed for routing and execution.
    """

    # Identity
    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    correlation_id: str = field(default_factory=lambda: f"corr-{uuid.uuid4().hex[:12]}")
    trace_id: str = field(default_factory=lambda: f"trace-{uuid.uuid4().hex[:12]}")

    # Request
    content: str = ""
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    agent_hint: Optional[str] = None
    priority: str = "normal"
    timeout: float = 60.0
    deadline: Optional[str] = None
    requested_agents: List[str] = field(default_factory=list)

    # Conversation context
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    memory_context: Dict[str, Any] = field(default_factory=dict)
    execution_metadata: Dict[str, Any] = field(default_factory=dict)

    # System state
    available_agents: List[str] = field(default_factory=list)
    agent_health: Dict[str, str] = field(default_factory=dict)
    agent_load: Dict[str, int] = field(default_factory=dict)
    agent_capabilities: Dict[str, List[str]] = field(default_factory=dict)
    system_state: Dict[str, Any] = field(default_factory=dict)
    resource_limits: Dict[str, Any] = field(default_factory=dict)

    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)

    # Decision record (populated during pipeline execution)
    record: DecisionRecord = field(default_factory=DecisionRecord)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "content": self.content[:200],
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "agent_hint": self.agent_hint,
            "priority": self.priority,
            "timeout": self.timeout,
            "deadline": self.deadline,
            "requested_agents": self.requested_agents,
            "available_agents": self.available_agents,
            "agent_health": self.agent_health,
            "agent_load": self.agent_load,
            "agent_capabilities": self.agent_capabilities,
            "system_state": self.system_state,
            "resource_limits": self.resource_limits,
            "execution_metadata": self.execution_metadata,
        }
