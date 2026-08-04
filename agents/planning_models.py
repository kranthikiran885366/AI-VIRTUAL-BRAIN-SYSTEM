"""
Planning Models for Phase 6 Production Planning Engine

Production-grade data structures for:
- Goal management and hierarchy
- Plan lifecycle and versioning
- Task decomposition and HTN
- Resource management
- Risk assessment
- Plan validation
- Execution monitoring
- Audit trails

All models support JSON serialization for persistence.
Backward compatible with existing plan dictionaries.
"""

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple
from abc import ABC, abstractmethod


# ─── Enumerations ────────────────────────────────────────────────────────────

class GoalStatus(str, Enum):
    """Goal lifecycle status."""
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class GoalPriority(int, Enum):
    """Goal priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class GoalCategory(str, Enum):
    """Goal categories for planning strategy selection."""
    DEVELOPMENT = "development"
    LEARNING = "learning"
    IMPROVEMENT = "improvement"
    EXECUTION = "execution"
    PLANNING = "planning"


class PlanStatus(str, Enum):
    """Plan lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Task type in task network."""
    ATOMIC = "atomic"           # No further decomposition
    COMPOUND = "compound"       # Decomposes into subtasks
    SEQUENTIAL = "sequential"   # Must run in order
    PARALLEL = "parallel"       # Can run concurrently


class DependencyType(str, Enum):
    """Dependency relationship types."""
    SEQUENTIAL = "sequential"         # Must complete before
    PARALLEL = "parallel"             # Can run concurrently
    CONDITIONAL = "conditional"       # Depends on outcome
    RESOURCE_CONSTRAINED = "resource_constrained"  # Requires resource from other


class RiskSeverity(str, Enum):
    """Risk severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ValidationStatus(str, Enum):
    """Plan validation status."""
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


# ─── Goal Models ─────────────────────────────────────────────────────────────

@dataclass
class GoalConstraint:
    """Constraint on goal execution."""
    constraint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    constraint_type: str = "general"  # time, resource, technical, business
    severity: str = "medium"  # low, medium, high
    value: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GoalNode:
    """Goal hierarchy node."""
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_goal_id: Optional[str] = None
    goal_title: str = ""
    goal_description: str = ""
    goal_category: GoalCategory = GoalCategory.EXECUTION
    priority: GoalPriority = GoalPriority.MEDIUM
    status: GoalStatus = GoalStatus.CREATED
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    owner: str = "system"
    success_criteria: List[str] = field(default_factory=list)
    constraints: List[GoalConstraint] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # goal_ids
    child_goal_ids: List[str] = field(default_factory=list)
    progress: float = 0.0
    estimated_effort: str = "medium"  # low, medium, high
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['goal_category'] = self.goal_category.value if self.goal_category else None
        data['priority'] = self.priority.value if self.priority else None
        data['status'] = self.status.value if self.status else None
        data['constraints'] = [c.to_dict() for c in self.constraints]
        return data


@dataclass
class Goal:
    """Top-level goal with hierarchy support."""
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    root_node: GoalNode = field(default_factory=GoalNode)
    all_nodes: Dict[str, GoalNode] = field(default_factory=dict)
    goal_tree_depth: int = 0
    goal_tree_width: int = 0
    total_child_goals: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "root_node": self.root_node.to_dict(),
            "all_nodes": {gid: node.to_dict() for gid, node in self.all_nodes.items()},
            "goal_tree_depth": self.goal_tree_depth,
            "goal_tree_width": self.goal_tree_width,
            "total_child_goals": self.total_child_goals,
        }


# ─── Task Decomposition Models ────────────────────────────────────────────────

@dataclass
class TaskDependency:
    """Dependency between tasks."""
    source_task_id: str = ""
    target_task_id: str = ""
    dependency_type: DependencyType = DependencyType.SEQUENTIAL
    condition: Optional[str] = None  # For conditional dependencies
    weight: float = 1.0  # For weighted dependencies
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['dependency_type'] = self.dependency_type.value
        return data


@dataclass
class DecomposedTask:
    """A task resulting from goal decomposition."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_task_id: Optional[str] = None
    task_title: str = ""
    task_description: str = ""
    task_type: TaskType = TaskType.ATOMIC
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 2
    order_in_plan: int = 0
    estimated_effort: str = "medium"  # low, medium, high
    estimated_duration_hours: float = 0.0
    success_criteria: List[str] = field(default_factory=list)
    required_resources: List[str] = field(default_factory=list)
    assigned_to: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)  # task_ids
    subtask_ids: List[str] = field(default_factory=list)
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['task_type'] = self.task_type.value
        data['status'] = self.status.value
        return data


@dataclass
class HierarchicalTaskNetwork:
    """Hierarchical Task Network (HTN) structure."""
    network_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    root_task_id: str = ""
    all_tasks: Dict[str, DecomposedTask] = field(default_factory=dict)
    task_dependencies: List[TaskDependency] = field(default_factory=list)
    parallel_task_groups: List[List[str]] = field(default_factory=list)
    sequential_task_order: List[str] = field(default_factory=list)
    decomposition_strategy: str = "goal_decomposition"
    max_depth: int = 0
    total_tasks: int = 0
    atomic_tasks_count: int = 0
    compound_tasks_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "network_id": self.network_id,
            "root_task_id": self.root_task_id,
            "all_tasks": {tid: task.to_dict() for tid, task in self.all_tasks.items()},
            "task_dependencies": [dep.to_dict() for dep in self.task_dependencies],
            "parallel_task_groups": self.parallel_task_groups,
            "sequential_task_order": self.sequential_task_order,
            "decomposition_strategy": self.decomposition_strategy,
            "max_depth": self.max_depth,
            "total_tasks": self.total_tasks,
            "atomic_tasks_count": self.atomic_tasks_count,
            "compound_tasks_count": self.compound_tasks_count,
        }


# ─── Resource Models ─────────────────────────────────────────────────────────

@dataclass
class ResourceRequirement:
    """Resource requirement for a task or plan."""
    resource_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_name: str = ""
    resource_type: str = "skill"  # skill, tool, time, budget, etc.
    required_amount: float = 1.0
    unit: str = "units"
    priority: int = 2
    is_critical: bool = False
    alternative_resources: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResourceAllocation:
    """Resource allocation to a task."""
    allocation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    resource_name: str = ""
    allocated_amount: float = 1.0
    allocation_start: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    allocation_end: Optional[str] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResourceProfile:
    """Resource profile for a plan."""
    profile_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    profile_name: str = "standard"
    estimated_total_effort: str = "0"
    recommended_team_size: int = 1
    key_skills_needed: List[str] = field(default_factory=list)
    required_resources: List[ResourceRequirement] = field(default_factory=list)
    resource_confidence: float = 0.7
    available_resources: Dict[str, float] = field(default_factory=dict)
    resource_constraints: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['required_resources'] = [r.to_dict() for r in self.required_resources]
        return data


# ─── Risk Models ────────────────────────────────────────────────────────────

@dataclass
class RiskMitigation:
    """Mitigation strategy for a risk."""
    mitigation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_description: str = ""
    owner: Optional[str] = None
    estimated_effectiveness: float = 0.5
    cost: str = "medium"
    timeline: str = "immediate"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Risk:
    """Risk in a plan."""
    risk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    risk_description: str = ""
    risk_type: str = "generic"  # technical, resource, timeline, external
    probability: str = "medium"  # low, medium, high
    impact: str = "medium"  # low, medium, high
    severity: RiskSeverity = RiskSeverity.MEDIUM
    affected_tasks: List[str] = field(default_factory=list)
    likelihood_score: float = 0.5
    impact_score: float = 0.5
    overall_risk_score: float = 0.0
    mitigations: List[RiskMitigation] = field(default_factory=list)
    fallback_plan: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['severity'] = self.severity.value
        data['mitigations'] = [m.to_dict() for m in self.mitigations]
        return data


# ─── Validation Models ────────────────────────────────────────────────────────

@dataclass
class ValidationIssue:
    """A single validation issue found in a plan."""
    issue_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issue_type: str = "generic"  # dependency_cycle, missing_resource, invalid_goal, etc.
    severity: str = "warning"  # error, warning, info
    description: str = ""
    affected_elements: List[str] = field(default_factory=list)  # IDs of affected tasks/goals
    remediation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanValidationResult:
    """Result of plan validation."""
    validation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    status: ValidationStatus = ValidationStatus.PASSED
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    issues: List[ValidationIssue] = field(default_factory=list)
    dependency_cycle_count: int = 0
    missing_resources_count: int = 0
    duplicate_task_count: int = 0
    conflicting_constraint_count: int = 0
    deadline_conflict_count: int = 0
    execution_feasibility: str = "feasible"  # feasible, needs_review, not_feasible
    confidence_score: float = 1.0
    passed_checks: List[str] = field(default_factory=list)
    failed_checks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value
        data['issues'] = [issue.to_dict() for issue in self.issues]
        return data


# ─── Plan Context Models ─────────────────────────────────────────────────────

@dataclass
class PlanContext:
    """Context for plan execution."""
    goal: str = ""
    conversation_context: Dict[str, Any] = field(default_factory=dict)
    memory_context: Dict[str, Any] = field(default_factory=dict)
    decision_context: Dict[str, Any] = field(default_factory=dict)
    reasoning_context: Dict[str, Any] = field(default_factory=dict)
    execution_context: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    resources: Dict[str, Any] = field(default_factory=dict)
    deadlines: Dict[str, str] = field(default_factory=dict)
    system_state: Dict[str, Any] = field(default_factory=dict)
    priority: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanSession:
    """Planning session context."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    planning_strategy: str = "goal_decomposition"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Plan State & History Models ─────────────────────────────────────────────

@dataclass
class ExecutionProgress:
    """Current execution progress of a plan."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    blocked_tasks: int = 0
    waiting_tasks: int = 0
    running_tasks: int = 0
    progress_percentage: float = 0.0
    estimated_completion_time: Optional[str] = None
    actual_completion_time: Optional[str] = None
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanVersion:
    """Version record for a plan."""
    version_number: int = 1
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    change_reason: str = "initial"
    changed_by: str = "system"
    changes_summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditRecord:
    """Audit trail record for plan operations."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    goal_id: str = ""
    event_type: str = ""  # plan_created, task_started, milestone_completed, etc.
    event_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    actor: str = "system"
    details: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanExplanation:
    """Explanation of plan generation and reasoning."""
    goal_summary: str = ""
    planning_strategy: str = "goal_decomposition"
    reasoning_summary: str = ""
    dependency_explanation: str = ""
    resource_explanation: str = ""
    risk_explanation: str = ""
    execution_order: List[str] = field(default_factory=list)
    confidence: float = 0.7
    limitations: List[str] = field(default_factory=list)
    alternative_plans_considered: List[str] = field(default_factory=list)
    optimization_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Compatibility Aliases (test-facing API) ────────────────────────────────

class ConstraintType(str, Enum):
    """Constraint type aliases for test compatibility."""
    TIME = "time"
    RESOURCE = "resource"
    TECHNICAL = "technical"
    BUSINESS = "business"


@dataclass
class Task:
    """Simplified task for test compatibility."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    goal_id: str = ""
    estimated_effort_hours: float = 0.0
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    start_time: Optional[Any] = None
    end_time: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "title": self.title, "goal_id": self.goal_id,
                "estimated_effort_hours": self.estimated_effort_hours,
                "status": self.status.value if hasattr(self.status, 'value') else self.status}


@dataclass
class Plan:
    """Simplified plan for test compatibility."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    goals: List[str] = field(default_factory=list)
    status: PlanStatus = PlanStatus.DRAFT
    tasks: List[Task] = field(default_factory=list)
    created_at: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "title": self.title, "goals": self.goals,
                "status": self.status.value if hasattr(self.status, 'value') else self.status,
                "tasks": [t.to_dict() for t in self.tasks]}


@dataclass
class Constraint:
    """Simplified constraint for test compatibility."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: ConstraintType = ConstraintType.TIME
    goal_id: str = ""
    description: str = ""
    deadline: Optional[Any] = None

    def __post_init__(self):
        if self.type == ConstraintType.TIME and self.deadline is None:
            raise ValueError("TIME constraint requires a deadline")


# ─── Top-Level Plan Model ────────────────────────────────────────────────────

@dataclass
class ProductionPlan:
    """Production-grade plan with full lifecycle support."""
    # Identifiers
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Goal & Strategy
    goal: str = ""
    goal_node: Optional[GoalNode] = None
    timeframe: str = "flexible"
    planning_strategy: str = "goal_decomposition"

    # Plan State
    status: PlanStatus = PlanStatus.DRAFT
    current_version: int = 1
    execution_progress: ExecutionProgress = field(default_factory=ExecutionProgress)

    # Lifecycle Tracking
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Context & Session
    plan_context: PlanContext = field(default_factory=PlanContext)
    plan_session: PlanSession = field(default_factory=PlanSession)

    # Tasks & Decomposition
    htn: HierarchicalTaskNetwork = field(default_factory=HierarchicalTaskNetwork)
    all_tasks: Dict[str, DecomposedTask] = field(default_factory=dict)

    # Resources & Constraints
    resource_profile: ResourceProfile = field(default_factory=ResourceProfile)
    constraints: List[GoalConstraint] = field(default_factory=list)

    # Quality Assurance
    validation_result: PlanValidationResult = field(default_factory=PlanValidationResult)
    risks: List[Risk] = field(default_factory=list)
    explanation: PlanExplanation = field(default_factory=PlanExplanation)

    # History & Versioning
    version_history: List[PlanVersion] = field(default_factory=list)
    audit_trail: List[AuditRecord] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    owner: str = "planning_agent"
    priority: int = 2

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "plan_id": self.plan_id,
            "goal_id": self.goal_id,
            "goal": self.goal,
            "goal_node": self.goal_node.to_dict() if self.goal_node else None,
            "timeframe": self.timeframe,
            "planning_strategy": self.planning_strategy,
            "status": self.status.value,
            "current_version": self.current_version,
            "execution_progress": self.execution_progress.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "plan_context": self.plan_context.to_dict(),
            "plan_session": self.plan_session.to_dict(),
            "htn": self.htn.to_dict(),
            "all_tasks": {tid: task.to_dict() for tid, task in self.all_tasks.items()},
            "resource_profile": self.resource_profile.to_dict(),
            "constraints": [c.to_dict() for c in self.constraints],
            "validation_result": self.validation_result.to_dict(),
            "risks": [r.to_dict() for r in self.risks],
            "explanation": self.explanation.to_dict(),
            "version_history": [v.to_dict() for v in self.version_history],
            "audit_trail": [a.to_dict() for a in self.audit_trail],
            "metadata": self.metadata,
            "owner": self.owner,
            "priority": self.priority,
        }

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Convert to legacy format for backward compatibility."""
        # Flatten for API compatibility with existing code
        milestones = list(self.all_tasks.values())
        return {
            "plan_id": self.plan_id,
            "id": self.plan_id,
            "goal_id": self.goal_id,
            "goal": self.goal,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "timeframe": self.timeframe,
            "constraints": [c.to_dict() for c in self.constraints],
            "milestones": [t.to_dict() for t in milestones],
            "tasks": [t.to_dict() for t in milestones],
            "plan_context": self.plan_context.to_dict(),
            "plan_metadata": {
                "goal_category": self.goal_node.goal_category.value if self.goal_node else "execution",
                "goal_priority": self.priority,
                "owner": self.owner,
                "deadline": self.plan_session.completed_at,
                "constraints": [c.to_dict() for c in self.constraints],
                "resource_profile": self.resource_profile.profile_name,
                "planning_strategy": self.planning_strategy,
            },
            "plan_session": self.plan_session.to_dict(),
            "plan_state": {
                "status": self.status.value,
                "progress": self.execution_progress.progress_percentage,
                "running_tasks": self.execution_progress.running_tasks,
                "completed_tasks": self.execution_progress.completed_tasks,
                "failed_tasks": self.execution_progress.failed_tasks,
                "cancelled_tasks": self.execution_progress.cancelled_tasks,
                "blocked_tasks": self.execution_progress.blocked_tasks,
                "waiting_tasks": self.execution_progress.waiting_tasks,
            },
            "plan_history": [a.to_dict() for a in self.audit_trail],
            "history": [
                {
                    "version": v.version_number,
                    "event": "version_change",
                    "timestamp": v.created_at,
                    "summary": v.changes_summary,
                }
                for v in self.version_history
            ],
            "plan_audit": [a.to_dict() for a in self.audit_trail],
            "version": self.current_version,
            "version_history": [v.to_dict() for v in self.version_history],
            "htn": self.htn.to_dict(),
            "validation": self.validation_result.to_dict(),
            "risks": [r.to_dict() for r in self.risks],
            "resources": self.resource_profile.to_dict(),
            "status": self.status.value,
            "progress": self.execution_progress.progress_percentage,
            "explanation": self.explanation.to_dict(),
        }
