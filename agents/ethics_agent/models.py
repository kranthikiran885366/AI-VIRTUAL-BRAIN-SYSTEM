"""
Ethics Engine Models — Phase 11 Production Dataclasses.

Defines data structures for:
  - Multi-agent EthicsContext (9-agent contexts + correlation/trace IDs)
  - Ethical reasoning results (framework scores & dimensions)
  - Governance policies & policy evaluation results
  - Compliance reports & regulatory audit findings
  - Multi-dimensional Risk reports & risk matrix
  - Operational Safety reports & advisory rollback recommendations
  - Stakeholder impact matrices & trade-off analysis
  - Ethics audit trails, session snapshots & replay results
  - Aggregated operational EthicsMetrics
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class EthicsContext:
    """Multi-agent ethics context aggregating inputs across the cognitive system."""
    conversation_context: Dict[str, Any] = field(default_factory=dict)
    memory_context: Dict[str, Any] = field(default_factory=dict)
    decision_context: Dict[str, Any] = field(default_factory=dict)
    reasoning_context: Dict[str, Any] = field(default_factory=dict)
    planning_context: Dict[str, Any] = field(default_factory=dict)
    learning_context: Dict[str, Any] = field(default_factory=dict)
    emotion_context: Dict[str, Any] = field(default_factory=dict)
    language_context: Dict[str, Any] = field(default_factory=dict)
    creativity_context: Dict[str, Any] = field(default_factory=dict)
    domain: str = "general"
    situation: str = ""
    proposed_action: str = ""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FrameworkEvaluation:
    """Evaluation result for a single ethical framework."""
    framework_name: str = ""
    score: float = 0.0          # 0.0 (unethical/harmful) to 1.0 (highly ethical)
    guidance: str = ""
    key_findings: List[str] = field(default_factory=list)
    confidence: float = 0.8

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EthicalAnalysisResult:
    """Combined ethical analysis output across modular frameworks."""
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ethical_dimensions: List[str] = field(default_factory=list)
    stakeholders_affected: List[str] = field(default_factory=list)
    risk_level: str = "low"     # low / medium / high / critical
    framework_analyses: Dict[str, str] = field(default_factory=dict)
    framework_scores: Dict[str, float] = field(default_factory=dict)
    key_considerations: List[str] = field(default_factory=list)
    recommendation: str = ""
    questions_to_consider: List[str] = field(default_factory=list)
    overall_ethical_score: float = 0.8
    confidence: float = 0.8
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GovernancePolicy:
    """Definition of an organizational or operational governance policy."""
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: str = "operational"  # organizational / operational / business_rule / approval / workflow
    description: str = ""
    rules: List[Dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"
    is_active: bool = True
    priority: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GovernanceResult:
    """Evaluation output for governance policies."""
    evaluation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    compliant: bool = True
    policies_checked: int = 0
    violations: List[Dict[str, Any]] = field(default_factory=list)
    approvals_required: List[str] = field(default_factory=list)
    governance_score: float = 1.0
    recommendation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComplianceReport:
    """Domain-agnostic compliance evaluation report."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_compliant: bool = True
    compliance_score: float = 1.0
    validations: List[Dict[str, Any]] = field(default_factory=list)
    data_handling_issues: List[str] = field(default_factory=list)
    audit_checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    regulatory_notes: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskReport:
    """Structured multi-dimensional risk evaluation report."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    overall_risk_level: str = "low"  # low / medium / high / critical
    risk_score: float = 0.2
    risk_matrix: Dict[str, float] = field(default_factory=dict)  # operational, decision, planning, execution, etc.
    identified_risks: List[Dict[str, Any]] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)
    stability_impact: str = "stable"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SafetyReport:
    """Operational safety assessment report."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_safe: bool = True
    safety_score: float = 0.95
    detected_hazards: List[Dict[str, Any]] = field(default_factory=list)
    execution_safeguards: List[str] = field(default_factory=list)
    resource_exhaustion_risk: bool = False
    dependency_integrity_pass: bool = True
    estimated_failure_impact: str = "minimal"
    rollback_recommendation: Optional[str] = None
    advisory_summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StakeholderImpact:
    """Stakeholder identification and trade-off analysis matrix."""
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stakeholders: List[str] = field(default_factory=list)
    impact_matrix: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    benefit_analysis: List[str] = field(default_factory=list)
    trade_off_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    priority_balancing: Dict[str, float] = field(default_factory=dict)
    recommendation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EthicsAuditTrail:
    """Audit log entry for ethics decisions."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    action: str = ""
    input_summary: Dict[str, Any] = field(default_factory=dict)
    frameworks_used: List[str] = field(default_factory=list)
    reasoning_summary: str = ""
    risk_level: str = "low"
    recommendation_rationale: str = ""
    confidence: float = 0.8
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EthicsAuditSnapshot:
    """Full snapshot of an ethics session state for replay."""
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    context: Dict[str, Any] = field(default_factory=dict)
    analysis_results: Dict[str, Any] = field(default_factory=dict)
    audit_entries: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReplayResult:
    """Result of replaying an ethics session."""
    session_id: str = ""
    replayed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    match_rate: float = 1.0
    original_analysis: Dict[str, Any] = field(default_factory=dict)
    replayed_analysis: Dict[str, Any] = field(default_factory=dict)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EthicsSession:
    """Tracks an active operational ethics evaluation session."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ended_at: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    domain: str = ""
    analyses_count: int = 0
    audit_entries: List[EthicsAuditTrail] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EthicsMetrics:
    """Aggregated operational metrics for the Ethics, Governance & Safety Engine."""
    total_sessions: int = 0
    total_analyses: int = 0
    governance_checks: int = 0
    compliance_evaluations: int = 0
    risk_assessments: int = 0
    safety_evaluations: int = 0
    stakeholder_analyses: int = 0
    replay_count: int = 0
    error_count: int = 0
    total_processing_ms: float = 0.0
    # BaseAgent-required fields
    heartbeat_count: int = 0
    messages_processed: int = 0
    messages_sent: int = 0
    execution_failures: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def avg_processing_ms(self) -> float:
        total_ops = (self.total_analyses + self.governance_checks + self.compliance_evaluations +
                     self.risk_assessments + self.safety_evaluations + self.stakeholder_analyses + self.replay_count)
        return round(self.total_processing_ms / max(1, total_ops), 2)
