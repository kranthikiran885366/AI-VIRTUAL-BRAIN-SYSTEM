"""
Phase 14 — Global Cognitive State & Shared Models.

Data structures used by the Autonomous Cognitive Controller,
Self-Monitoring Engine, Self-Healing Engine, Policy Engine,
Adaptive Execution Optimizer, Continuous Self-Improvement Engine,
Resource Governance Engine, and Execution Analytics Engine.

All dataclasses are fully serializable via .to_dict() / asdict() and constructible via .from_dict().
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ─── Enumerations ─────────────────────────────────────────────────────────────

class SystemHealthLevel(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    CRITICAL  = "critical"
    UNKNOWN   = "unknown"


class OptimizationAction(str, Enum):
    SCALE_UP        = "scale_up"
    SCALE_DOWN      = "scale_down"
    RESTART_AGENT   = "restart_agent"
    THROTTLE        = "throttle"
    REBALANCE       = "rebalance"
    FLUSH_QUEUE     = "flush_queue"
    ADJUST_TIMEOUT  = "adjust_timeout"
    ADJUST_PRIORITY = "adjust_priority"
    NO_OP           = "no_op"


class RecoveryStrategy(str, Enum):
    RESTART           = "restart"
    FAILOVER          = "failover"
    REPLAY_MESSAGES   = "replay_messages"
    QUEUE_RECOVERY    = "queue_recovery"
    STATE_RECONSTRUCT = "state_reconstruct"
    GRACEFUL_DEGRADE  = "graceful_degrade"
    ESCALATE          = "escalate"


class PolicyType(str, Enum):
    EXECUTION    = "execution"
    RESOURCE     = "resource"
    RETRY        = "retry"
    TIMEOUT      = "timeout"
    PRIORITY     = "priority"
    OPTIMIZATION = "optimization"
    MAINTENANCE  = "maintenance"
    DEGRADATION  = "degradation"


# ─── Agent Snapshot ────────────────────────────────────────────────────────────

@dataclass
class AgentSnapshot:
    agent_id: str
    agent_type: str = "agent"
    status: str = "unknown"
    health_score: float = 1.0
    error_count: int = 0
    task_count: int = 0
    avg_latency_ms: float = 0.0
    queue_depth: int = 0
    last_heartbeat: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentSnapshot:
        return cls(
            agent_id=data.get("agent_id", "unknown"),
            agent_type=data.get("agent_type", "agent"),
            status=data.get("status", "unknown"),
            health_score=float(data.get("health_score", 1.0)),
            error_count=int(data.get("error_count", 0)),
            task_count=int(data.get("task_count", 0)),
            avg_latency_ms=float(data.get("avg_latency_ms", 0.0)),
            queue_depth=int(data.get("queue_depth", 0)),
            last_heartbeat=data.get("last_heartbeat"),
            capabilities=list(data.get("capabilities", [])),
        )


# ─── Global Cognitive State ───────────────────────────────────────────────────

@dataclass
class GlobalCognitiveState:
    """Synchronized global state across all cognitive agents and subsystems."""
    state_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    system_version: str = "1.0.0"

    # System Health & Workload
    health_level: SystemHealthLevel = SystemHealthLevel.UNKNOWN
    global_health_score: float = 1.0
    global_confidence: float = 0.70
    global_workload: float = 0.0

    # Agent registry snapshot
    agents: Dict[str, AgentSnapshot] = field(default_factory=dict)
    active_agent_count: int = 0
    degraded_agent_count: int = 0

    # Cognitive Activity Tracking
    active_goals: List[str] = field(default_factory=list)
    active_reasoning: List[str] = field(default_factory=list)
    active_planning: List[str] = field(default_factory=list)
    active_learning: List[str] = field(default_factory=list)
    active_memory: List[str] = field(default_factory=list)
    active_perception: List[str] = field(default_factory=list)
    active_conversations: List[str] = field(default_factory=list)
    active_collaborations: List[str] = field(default_factory=list)

    # System Resource Utilization & Metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    gpu_usage: float = 0.0
    queue_depth_total: int = 0
    throughput_per_sec: float = 0.0
    failure_rate: float = 0.0
    timeout_rate: float = 0.0

    # Subsystems & Capabilities
    active_subsystems: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    runtime_capabilities: List[str] = field(default_factory=list)
    global_metrics: Dict[str, Any] = field(default_factory=dict)

    def update_agent(self, snapshot: AgentSnapshot) -> None:
        self.agents[snapshot.agent_id] = snapshot
        self.active_agent_count = sum(1 for a in self.agents.values() if a.status in ("running", "healthy", "initialized"))
        self.degraded_agent_count = sum(1 for a in self.agents.values() if a.status in ("degraded", "unhealthy", "recovering"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["health_level"] = self.health_level.value if isinstance(self.health_level, SystemHealthLevel) else str(self.health_level)
        d["agents"] = {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in self.agents.items()}
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GlobalCognitiveState:
        hl_raw = data.get("health_level", "unknown")
        try:
            hl = SystemHealthLevel(hl_raw)
        except ValueError:
            hl = SystemHealthLevel.UNKNOWN

        raw_agents = data.get("agents", {})
        agents = {}
        for k, v in raw_agents.items():
            if isinstance(v, dict):
                agents[k] = AgentSnapshot.from_dict(v)
            elif isinstance(v, AgentSnapshot):
                agents[k] = v

        return cls(
            state_id=data.get("state_id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            system_version=data.get("system_version", "1.0.0"),
            health_level=hl,
            global_health_score=float(data.get("global_health_score", 1.0)),
            global_confidence=float(data.get("global_confidence", 0.70)),
            global_workload=float(data.get("global_workload", 0.0)),
            agents=agents,
            active_agent_count=int(data.get("active_agent_count", 0)),
            degraded_agent_count=int(data.get("degraded_agent_count", 0)),
            active_goals=list(data.get("active_goals", [])),
            active_reasoning=list(data.get("active_reasoning", [])),
            active_planning=list(data.get("active_planning", [])),
            active_learning=list(data.get("active_learning", [])),
            active_memory=list(data.get("active_memory", [])),
            active_perception=list(data.get("active_perception", [])),
            active_conversations=list(data.get("active_conversations", [])),
            active_collaborations=list(data.get("active_collaborations", [])),
            cpu_usage=float(data.get("cpu_usage", 0.0)),
            memory_usage=float(data.get("memory_usage", 0.0)),
            gpu_usage=float(data.get("gpu_usage", 0.0)),
            queue_depth_total=int(data.get("queue_depth_total", 0)),
            throughput_per_sec=float(data.get("throughput_per_sec", 0.0)),
            failure_rate=float(data.get("failure_rate", 0.0)),
            timeout_rate=float(data.get("timeout_rate", 0.0)),
            active_subsystems=list(data.get("active_subsystems", [])),
            capabilities=list(data.get("capabilities", [])),
            runtime_capabilities=list(data.get("runtime_capabilities", [])),
            global_metrics=dict(data.get("global_metrics", {})),
        )


# ─── Monitoring Data Models ───────────────────────────────────────────────────

@dataclass
class MonitoringReport:
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    health_level: SystemHealthLevel = SystemHealthLevel.UNKNOWN
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    gpu_usage: float = 0.0
    queue_depth: int = 0
    throughput: float = 0.0
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    avg_latency_ms: float = 0.0
    confidence_trend: float = 0.70
    agent_health: Dict[str, str] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["health_level"] = self.health_level.value if isinstance(self.health_level, SystemHealthLevel) else str(self.health_level)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MonitoringReport:
        hl_raw = data.get("health_level", "unknown")
        try:
            hl = SystemHealthLevel(hl_raw)
        except ValueError:
            hl = SystemHealthLevel.UNKNOWN

        return cls(
            report_id=data.get("report_id", str(uuid.uuid4())),
            session_id=data.get("session_id", ""),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            health_level=hl,
            cpu_usage=float(data.get("cpu_usage", 0.0)),
            memory_usage=float(data.get("memory_usage", 0.0)),
            gpu_usage=float(data.get("gpu_usage", 0.0)),
            queue_depth=int(data.get("queue_depth", 0)),
            throughput=float(data.get("throughput", 0.0)),
            error_rate=float(data.get("error_rate", 0.0)),
            timeout_rate=float(data.get("timeout_rate", 0.0)),
            avg_latency_ms=float(data.get("avg_latency_ms", 0.0)),
            confidence_trend=float(data.get("confidence_trend", 0.70)),
            agent_health=dict(data.get("agent_health", {})),
            alerts=list(data.get("alerts", [])),
            recommendations=list(data.get("recommendations", [])),
        )


# ─── Self-Healing Models ──────────────────────────────────────────────────────

@dataclass
class RecoveryAction:
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target_agent: str = ""
    strategy: RecoveryStrategy = RecoveryStrategy.RESTART
    triggered_by: str = ""
    reason: str = ""
    success: bool = False
    attempts: int = 0
    max_attempts: int = 3
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["strategy"] = self.strategy.value if isinstance(self.strategy, RecoveryStrategy) else str(self.strategy)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecoveryAction:
        st_raw = data.get("strategy", "restart")
        try:
            st = RecoveryStrategy(st_raw)
        except ValueError:
            st = RecoveryStrategy.RESTART

        return cls(
            action_id=data.get("action_id", str(uuid.uuid4())),
            target_agent=data.get("target_agent", ""),
            strategy=st,
            triggered_by=data.get("triggered_by", ""),
            reason=data.get("reason", ""),
            success=bool(data.get("success", False)),
            attempts=int(data.get("attempts", 0)),
            max_attempts=int(data.get("max_attempts", 3)),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
        )


# ─── Optimization Models ──────────────────────────────────────────────────────

@dataclass
class OptimizationRecommendation:
    rec_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    action: OptimizationAction = OptimizationAction.NO_OP
    target: str = ""
    reason: str = ""
    expected_improvement: str = ""
    confidence: float = 0.50
    priority: int = 2          # 1=low, 2=medium, 3=high, 4=critical
    applied: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["action"] = self.action.value if isinstance(self.action, OptimizationAction) else str(self.action)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OptimizationRecommendation:
        act_raw = data.get("action", "no_op")
        try:
            act = OptimizationAction(act_raw)
        except ValueError:
            act = OptimizationAction.NO_OP

        return cls(
            rec_id=data.get("rec_id", str(uuid.uuid4())),
            session_id=data.get("session_id", ""),
            action=act,
            target=data.get("target", ""),
            reason=data.get("reason", ""),
            expected_improvement=data.get("expected_improvement", ""),
            confidence=float(data.get("confidence", 0.50)),
            priority=int(data.get("priority", 2)),
            applied=bool(data.get("applied", False)),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
        )


@dataclass
class OptimizationSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    recommendations: List[OptimizationRecommendation] = field(default_factory=list)
    actions_applied: int = 0
    improvement_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["recommendations"] = [r.to_dict() if hasattr(r, "to_dict") else r for r in self.recommendations]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OptimizationSession:
        recs = [OptimizationRecommendation.from_dict(r) if isinstance(r, dict) else r for r in data.get("recommendations", [])]
        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            correlation_id=data.get("correlation_id"),
            trace_id=data.get("trace_id"),
            started_at=data.get("started_at", datetime.utcnow().isoformat()),
            completed_at=data.get("completed_at"),
            recommendations=recs,
            actions_applied=int(data.get("actions_applied", 0)),
            improvement_score=float(data.get("improvement_score", 0.0)),
        )


# ─── Policy Models ────────────────────────────────────────────────────────────

@dataclass
class Policy:
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    policy_type: PolicyType = PolicyType.EXECUTION
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["policy_type"] = self.policy_type.value if isinstance(self.policy_type, PolicyType) else str(self.policy_type)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Policy:
        pt_raw = data.get("policy_type", "execution")
        try:
            pt = PolicyType(pt_raw)
        except ValueError:
            pt = PolicyType.EXECUTION

        return cls(
            policy_id=data.get("policy_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            policy_type=pt,
            enabled=bool(data.get("enabled", True)),
            parameters=dict(data.get("parameters", {})),
            description=data.get("description", ""),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at"),
        )


# ─── Analytics Models ─────────────────────────────────────────────────────────

@dataclass
class ExecutionAnalytics:
    analytics_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    window_seconds: int = 300
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    throughput_per_sec: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    success_rate: float = 1.0
    failure_rate: float = 0.0
    timeout_rate: float = 0.0
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    gpu_utilization: float = 0.0
    agent_utilization: Dict[str, float] = field(default_factory=dict)
    task_distribution: Dict[str, int] = field(default_factory=dict)
    bottlenecks: List[str] = field(default_factory=list)
    capacity_estimate: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionAnalytics:
        return cls(
            analytics_id=data.get("analytics_id", str(uuid.uuid4())),
            window_seconds=int(data.get("window_seconds", 300)),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            throughput_per_sec=float(data.get("throughput_per_sec", 0.0)),
            avg_latency_ms=float(data.get("avg_latency_ms", 0.0)),
            p50_latency_ms=float(data.get("p50_latency_ms", 0.0)),
            p95_latency_ms=float(data.get("p95_latency_ms", 0.0)),
            p99_latency_ms=float(data.get("p99_latency_ms", 0.0)),
            success_rate=float(data.get("success_rate", 1.0)),
            failure_rate=float(data.get("failure_rate", 0.0)),
            timeout_rate=float(data.get("timeout_rate", 0.0)),
            cpu_utilization=float(data.get("cpu_utilization", 0.0)),
            memory_utilization=float(data.get("memory_utilization", 0.0)),
            gpu_utilization=float(data.get("gpu_utilization", 0.0)),
            agent_utilization=dict(data.get("agent_utilization", {})),
            task_distribution=dict(data.get("task_distribution", {})),
            bottlenecks=list(data.get("bottlenecks", [])),
            capacity_estimate=float(data.get("capacity_estimate", 1.0)),
        )


# ─── Phase 14 Metrics ─────────────────────────────────────────────────────────

@dataclass
class Phase14Metrics:
    optimization_cycles: int = 0
    monitoring_cycles: int = 0
    recovery_actions: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0
    recommendations_generated: int = 0
    recommendations_applied: int = 0
    policy_evaluations: int = 0
    total_latency_ms: float = 0.0
    errors: int = 0

    def avg_cycle_ms(self) -> float:
        total = self.optimization_cycles + self.monitoring_cycles
        return round(self.total_latency_ms / max(1, total), 2)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)
