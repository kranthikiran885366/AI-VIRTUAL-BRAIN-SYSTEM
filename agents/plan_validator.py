"""
Plan Validator and Risk Analyzer for Phase 6 Planning Engine

Implements:
- Comprehensive plan validation
- Dependency cycle detection
- Constraint checking
- Resource feasibility analysis
- Risk assessment and scoring
- Mitigation planning

Production-grade validation integrated with planning engine.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
import uuid

from planning_models import (
    PlanValidationResult,
    ValidationIssue,
    ValidationStatus,
    Risk,
    RiskMitigation,
    RiskSeverity,
    HierarchicalTaskNetwork,
    DecomposedTask,
    GoalConstraint,
    ResourceProfile,
)

logger = logging.getLogger(__name__)


class PlanValidator:
    """Production plan validator."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize validator."""
        self.config = config or {}
        self.version = "1.0.0"
        self.validation_checks = [
            self._check_dependency_cycles,
            self._check_missing_resources,
            self._check_invalid_goals,
            self._check_duplicate_tasks,
            self._check_conflicting_constraints,
            self._check_deadline_conflicts,
            self._check_execution_feasibility,
        ]
        logger.info("PlanValidator initialized", extra={"version": self.version})

    async def validate_plan(
        self,
        plan_id: str,
        htn: HierarchicalTaskNetwork,
        constraints: List[GoalConstraint],
        resources: ResourceProfile,
        goal: str,
    ) -> PlanValidationResult:
        """
        Validate a complete plan.

        Args:
            plan_id: Plan ID
            htn: Hierarchical task network
            constraints: Goal constraints
            resources: Resource profile
            goal: Goal description

        Returns:
            Validation result with issues and status
        """
        result = PlanValidationResult(
            plan_id=plan_id,
            status=ValidationStatus.PASSED,
            timestamp=datetime.utcnow().isoformat(),
        )

        # Run all validation checks
        for check in self.validation_checks:
            check_issues = await check(htn, constraints, resources, goal)
            result.issues.extend(check_issues)

        # Update result status
        if result.issues:
            error_count = sum(1 for i in result.issues if i.severity == "error")
            result.status = ValidationStatus.FAILED if error_count > 0 else ValidationStatus.WARNING
            result.failed_checks = [i.issue_type for i in result.issues]
        else:
            result.passed_checks = [c.__name__ for c in self.validation_checks]

        # Determine feasibility
        result.execution_feasibility = self._determine_feasibility(result)

        # Calculate confidence based on validation
        result.confidence_score = self._calculate_validation_confidence(result)

        logger.info(
            "Plan validation completed",
            extra={
                "plan_id": plan_id,
                "status": result.status.value,
                "issue_count": len(result.issues),
                "confidence": round(result.confidence_score, 3),
            },
        )

        return result

    async def _check_dependency_cycles(
        self,
        htn: HierarchicalTaskNetwork,
        constraints: List[GoalConstraint],
        resources: ResourceProfile,
        goal: str,
    ) -> List[ValidationIssue]:
        """Check for dependency cycles."""
        issues = []

        if self._has_dependency_cycle(htn):
            issue = ValidationIssue(
                issue_type="dependency_cycle",
                severity="error",
                description="Circular dependency detected in task network",
                affected_elements=self._find_cycle_tasks(htn),
                remediation="Review task dependencies and remove circular references",
            )
            issues.append(issue)

        return issues

    async def _check_missing_resources(
        self,
        htn: HierarchicalTaskNetwork,
        constraints: List[GoalConstraint],
        resources: ResourceProfile,
        goal: str,
    ) -> List[ValidationIssue]:
        """Check for missing required resources."""
        issues = []

        if not resources.key_skills_needed:
            issue = ValidationIssue(
                issue_type="missing_resources",
                severity="warning",
                description="No key skills identified for plan execution",
                remediation="Review goal and identify required competencies",
            )
            issues.append(issue)

        for task in htn.all_tasks.values():
            for required_resource in task.required_resources:
                found = any(
                    r.resource_name == required_resource
                    for r in resources.required_resources
                )
                if not found:
                    issue = ValidationIssue(
                        issue_type="missing_resources",
                        severity="warning",
                        description=f"Required resource '{required_resource}' not in resource profile",
                        affected_elements=[task.task_id],
                        remediation=f"Add '{required_resource}' to resource profile",
                    )
                    issues.append(issue)

        return issues

    async def _check_invalid_goals(
        self,
        htn: HierarchicalTaskNetwork,
        constraints: List[GoalConstraint],
        resources: ResourceProfile,
        goal: str,
    ) -> List[ValidationIssue]:
        """Check for invalid goal specifications."""
        issues = []

        if not goal or not goal.strip():
            issue = ValidationIssue(
                issue_type="invalid_goal",
                severity="error",
                description="Goal is empty or invalid",
                remediation="Provide a clear, specific goal",
            )
            issues.append(issue)

        if len(goal) < 5:
            issue = ValidationIssue(
                issue_type="invalid_goal",
                severity="warning",
                description="Goal description is very brief",
                remediation="Provide more detail about the goal",
            )
            issues.append(issue)

        return issues

    async def _check_duplicate_tasks(
        self,
        htn: HierarchicalTaskNetwork,
        constraints: List[GoalConstraint],
        resources: ResourceProfile,
        goal: str,
    ) -> List[ValidationIssue]:
        """Check for duplicate tasks."""
        issues = []
        task_titles = [t.task_title for t in htn.all_tasks.values()]
        duplicates = [t for t in set(task_titles) if task_titles.count(t) > 1]

        for dup_title in duplicates:
            dup_task_ids = [
                t.task_id for t in htn.all_tasks.values() if t.task_title == dup_title
            ]
            issue = ValidationIssue(
                issue_type="duplicate_task",
                severity="warning",
                description=f"Duplicate task title: '{dup_title}'",
                affected_elements=dup_task_ids,
                remediation="Consolidate or rename duplicate tasks",
            )
            issues.append(issue)

        return issues

    async def _check_conflicting_constraints(
        self,
        htn: HierarchicalTaskNetwork,
        constraints: List[GoalConstraint],
        resources: ResourceProfile,
        goal: str,
    ) -> List[ValidationIssue]:
        """Check for conflicting constraints."""
        issues = []

        # Check for mutually exclusive constraints
        constraint_types: Dict[str, List[str]] = {}
        for constraint in constraints:
            if constraint.constraint_type not in constraint_types:
                constraint_types[constraint.constraint_type] = []
            constraint_types[constraint.constraint_type].append(constraint.name)

        # Identify potential conflicts (simplified logic)
        if len(constraints) > 5:
            issue = ValidationIssue(
                issue_type="conflicting_constraints",
                severity="warning",
                description="Many constraints may cause conflicts or overconstraint",
                affected_elements=[c.constraint_id for c in constraints],
                remediation="Review constraints for redundancy or conflicts",
            )
            issues.append(issue)

        return issues

    async def _check_deadline_conflicts(
        self,
        htn: HierarchicalTaskNetwork,
        constraints: List[GoalConstraint],
        resources: ResourceProfile,
        goal: str,
    ) -> List[ValidationIssue]:
        """Check for deadline conflicts."""
        issues = []

        # Calculate total estimated duration
        total_duration = sum(
            t.estimated_duration_hours for t in htn.all_tasks.values()
        )

        # Check for unrealistic timelines (simplified)
        if total_duration > 1000:  # More than ~125 working days
            issue = ValidationIssue(
                issue_type="deadline_conflict",
                severity="warning",
                description=f"Total estimated effort ({total_duration}h) is very high",
                remediation="Consider breaking goal into smaller pieces or increasing resources",
            )
            issues.append(issue)

        return issues

    async def _check_execution_feasibility(
        self,
        htn: HierarchicalTaskNetwork,
        constraints: List[GoalConstraint],
        resources: ResourceProfile,
        goal: str,
    ) -> List[ValidationIssue]:
        """Check overall execution feasibility."""
        issues = []

        # Check task count
        if htn.total_tasks > 50:
            issue = ValidationIssue(
                issue_type="execution_feasibility",
                severity="warning",
                description=f"Plan has {htn.total_tasks} tasks, which may be difficult to manage",
                remediation="Consider further decomposition or consolidation",
            )
            issues.append(issue)

        # Check depth
        if htn.max_depth > 5:
            issue = ValidationIssue(
                issue_type="execution_feasibility",
                severity="warning",
                description=f"Task decomposition depth ({htn.max_depth}) may be too deep",
                remediation="Simplify task hierarchy",
            )
            issues.append(issue)

        # Check for orphaned tasks
        orphaned = [
            t for t in htn.all_tasks.values()
            if t.task_id != htn.root_task_id
            and not t.dependencies
            and t.parent_task_id is None
        ]
        if orphaned:
            issue = ValidationIssue(
                issue_type="execution_feasibility",
                severity="warning",
                description=f"Found {len(orphaned)} tasks with no dependencies or parent",
                affected_elements=[t.task_id for t in orphaned],
                remediation="Link orphaned tasks to task hierarchy",
            )
            issues.append(issue)

        return issues

    def _has_dependency_cycle(self, htn: HierarchicalTaskNetwork) -> bool:
        """Detect if HTN has cycles using DFS."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def visit(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            task = htn.all_tasks.get(task_id)
            if task:
                for dep_id in task.dependencies:
                    if dep_id not in visited:
                        if visit(dep_id):
                            return True
                    elif dep_id in rec_stack:
                        return True

            rec_stack.discard(task_id)
            return False

        for task_id in htn.all_tasks:
            if task_id not in visited:
                if visit(task_id):
                    return True

        return False

    def _find_cycle_tasks(self, htn: HierarchicalTaskNetwork) -> List[str]:
        """Find tasks involved in cycles."""
        cycle_tasks = []
        visited: Dict[str, str] = {}  # task_id -> status (visiting, visited)

        def dfs(task_id: str, path: List[str]) -> None:
            visited[task_id] = "visiting"
            task = htn.all_tasks.get(task_id)

            if task:
                for dep_id in task.dependencies:
                    if dep_id not in visited:
                        dfs(dep_id, path + [task_id])
                    elif visited[dep_id] == "visiting":
                        # Found cycle
                        cycle_start = path.index(dep_id) if dep_id in path else 0
                        cycle_tasks.extend(path[cycle_start:] + [task_id, dep_id])

            visited[task_id] = "visited"

        for task_id in htn.all_tasks:
            if task_id not in visited:
                dfs(task_id, [])

        return list(set(cycle_tasks))

    def _determine_feasibility(self, result: PlanValidationResult) -> str:
        """Determine overall execution feasibility."""
        if result.status == ValidationStatus.FAILED:
            return "not_feasible"
        error_count = sum(1 for i in result.issues if i.severity == "error")
        warning_count = sum(1 for i in result.issues if i.severity == "warning")

        if error_count > 2 or warning_count > 5:
            return "needs_review"
        return "feasible"

    def _calculate_validation_confidence(self, result: PlanValidationResult) -> float:
        """Calculate confidence score based on validation results."""
        base_confidence = 1.0
        issue_penalty = 0.05 * len(result.issues)
        error_penalty = 0.1 * sum(1 for i in result.issues if i.severity == "error")
        warning_penalty = 0.02 * sum(1 for i in result.issues if i.severity == "warning")

        confidence = base_confidence - issue_penalty - error_penalty - warning_penalty
        return max(0.0, min(1.0, confidence))


class RiskAnalyzer:
    """Production risk analysis."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize risk analyzer."""
        self.config = config or {}
        self.version = "1.0.0"
        self.risk_patterns = self._initialize_risk_patterns()
        logger.info("RiskAnalyzer initialized", extra={"version": self.version})

    def _initialize_risk_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize risk pattern templates."""
        return {
            "timeline_slippage": {
                "description": "Timeline slippage",
                "risk_type": "timeline",
                "base_probability": "medium",
                "base_impact": "medium",
                "mitigation": "Build 20% buffer into each milestone",
            },
            "scope_creep": {
                "description": "Scope creep",
                "risk_type": "execution",
                "base_probability": "medium",
                "base_impact": "high",
                "mitigation": "Define clear requirements upfront",
            },
            "resource_shortage": {
                "description": "Resource shortage",
                "risk_type": "resource",
                "base_probability": "low",
                "base_impact": "high",
                "mitigation": "Identify backup resources early",
            },
            "technical_challenges": {
                "description": "Technical implementation challenges",
                "risk_type": "technical",
                "base_probability": "medium",
                "base_impact": "medium",
                "mitigation": "Prototype and validate early",
            },
            "dependency_failure": {
                "description": "External dependency failure",
                "risk_type": "technical",
                "base_probability": "low",
                "base_impact": "high",
                "mitigation": "Identify alternatives and fallback plans",
            },
        }

    async def analyze_risks(
        self,
        goal: str,
        htn: HierarchicalTaskNetwork,
        constraints: List[GoalConstraint],
        resources: ResourceProfile,
    ) -> List[Risk]:
        """
        Analyze risks in a plan.

        Args:
            goal: Goal description
            htn: Task network
            constraints: Goal constraints
            resources: Resource profile

        Returns:
            List of identified risks
        """
        risks = []

        # Identify goal-based risks
        goal_risks = await self._identify_goal_risks(goal)
        risks.extend(goal_risks)

        # Identify task-based risks
        task_risks = await self._identify_task_risks(htn)
        risks.extend(task_risks)

        # Identify constraint-based risks
        constraint_risks = await self._identify_constraint_risks(constraints)
        risks.extend(constraint_risks)

        # Identify resource-based risks
        resource_risks = await self._identify_resource_risks(resources)
        risks.extend(resource_risks)

        # Score risks
        for risk in risks:
            await self._score_risk(risk)

        # Sort by overall risk score
        risks.sort(key=lambda r: r.overall_risk_score, reverse=True)

        logger.info(
            "Risk analysis completed",
            extra={"total_risks": len(risks)},
        )
        return risks

    async def _identify_goal_risks(self, goal: str) -> List[Risk]:
        """Identify risks based on goal characteristics."""
        risks = []

        # Timeline slippage is common
        risk = Risk(
            risk_id=str(uuid.uuid4()),
            risk_description="Timeline slippage",
            risk_type="timeline",
            probability="medium",
            impact="medium",
            severity=RiskSeverity.MEDIUM,
            likelihood_score=0.6,
            impact_score=0.6,
        )
        risk.mitigations.append(
            RiskMitigation(
                strategy_description="Build 20% buffer into each milestone",
                estimated_effectiveness=0.7,
            )
        )
        risks.append(risk)

        # Scope creep if goal is vague
        if len(goal) < 20 or "and" not in goal.lower():
            risk = Risk(
                risk_id=str(uuid.uuid4()),
                risk_description="Scope creep due to unclear requirements",
                risk_type="execution",
                probability="medium",
                impact="high",
                severity=RiskSeverity.HIGH,
                likelihood_score=0.5,
                impact_score=0.8,
            )
            risk.mitigations.append(
                RiskMitigation(
                    strategy_description="Clarify and document requirements early",
                    estimated_effectiveness=0.8,
                )
            )
            risks.append(risk)

        return risks

    async def _identify_task_risks(self, htn: HierarchicalTaskNetwork) -> List[Risk]:
        """Identify risks based on task network."""
        risks = []

        # High-complexity tasks have higher risk
        high_effort_tasks = [
            t for t in htn.all_tasks.values()
            if t.estimated_effort in ("high", "critical")
        ]

        if high_effort_tasks:
            risk = Risk(
                risk_id=str(uuid.uuid4()),
                risk_description="Technical implementation challenges",
                risk_type="technical",
                probability="medium",
                impact="medium",
                severity=RiskSeverity.MEDIUM,
                likelihood_score=0.6,
                impact_score=0.6,
                affected_tasks=[t.task_id for t in high_effort_tasks],
            )
            risk.mitigations.append(
                RiskMitigation(
                    strategy_description="Prototype and validate technical approach early",
                    estimated_effectiveness=0.7,
                )
            )
            risks.append(risk)

        # Many dependencies increase risk
        total_deps = sum(len(t.dependencies) for t in htn.all_tasks.values())
        if total_deps > htn.total_tasks:
            risk = Risk(
                risk_id=str(uuid.uuid4()),
                risk_description="Complex task interdependencies",
                risk_type="execution",
                probability="low",
                impact="high",
                severity=RiskSeverity.HIGH,
                likelihood_score=0.3,
                impact_score=0.8,
            )
            risks.append(risk)

        return risks

    async def _identify_constraint_risks(
        self,
        constraints: List[GoalConstraint],
    ) -> List[Risk]:
        """Identify risks based on constraints."""
        risks = []

        if len(constraints) > 3:
            risk = Risk(
                risk_id=str(uuid.uuid4()),
                risk_description="Constraint pressure may limit options",
                risk_type="execution",
                probability="medium",
                impact="medium",
                severity=RiskSeverity.MEDIUM,
                likelihood_score=0.5,
                impact_score=0.6,
            )
            risks.append(risk)

        # High-severity constraints are risky
        critical_constraints = [c for c in constraints if c.severity == "high"]
        if critical_constraints:
            risk = Risk(
                risk_id=str(uuid.uuid4()),
                risk_description="Critical constraints may block execution",
                risk_type="execution",
                probability="low",
                impact="high",
                severity=RiskSeverity.HIGH,
                likelihood_score=0.4,
                impact_score=0.9,
            )
            risks.append(risk)

        return risks

    async def _identify_resource_risks(
        self,
        resources: ResourceProfile,
    ) -> List[Risk]:
        """Identify risks based on resource constraints."""
        risks = []

        if not resources.key_skills_needed:
            risk = Risk(
                risk_id=str(uuid.uuid4()),
                risk_description="Missing resource specification",
                risk_type="resource",
                probability="high",
                impact="medium",
                severity=RiskSeverity.MEDIUM,
                likelihood_score=0.8,
                impact_score=0.6,
            )
            risks.append(risk)

        if resources.recommended_team_size == 0:
            risk = Risk(
                risk_id=str(uuid.uuid4()),
                risk_description="No team size specified",
                risk_type="resource",
                probability="high",
                impact="high",
                severity=RiskSeverity.HIGH,
                likelihood_score=0.9,
                impact_score=0.7,
            )
            risks.append(risk)

        return risks

    async def _score_risk(self, risk: Risk) -> None:
        """Score a risk based on probability and impact."""
        # Convert probability/impact strings to scores
        severity_map = {"low": 0.3, "medium": 0.6, "high": 0.9, "critical": 1.0}

        risk.likelihood_score = severity_map.get(risk.probability, 0.5)
        risk.impact_score = severity_map.get(risk.impact, 0.5)
        risk.overall_risk_score = risk.likelihood_score * risk.impact_score

        # Determine severity based on score
        if risk.overall_risk_score > 0.7:
            risk.severity = RiskSeverity.HIGH
        elif risk.overall_risk_score > 0.4:
            risk.severity = RiskSeverity.MEDIUM
        else:
            risk.severity = RiskSeverity.LOW

    async def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        return {
            "version": self.version,
            "risk_patterns": list(self.risk_patterns.keys()),
        }
