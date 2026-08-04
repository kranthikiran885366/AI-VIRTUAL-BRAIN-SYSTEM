"""
Plan Validator and Risk Analyzer for Phase 6 Planning Engine
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set

try:
    from agents.planning_models import (
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
except ImportError:
    from planning_models import (  # type: ignore[no-redef]
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


class _AsyncPlanValidator:
    """Production async plan validator."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
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

    async def validate_plan(self, plan_id, htn, constraints, resources, goal):
        result = PlanValidationResult(
            plan_id=plan_id,
            status=ValidationStatus.PASSED,
            timestamp=datetime.utcnow().isoformat(),
        )
        for check in self.validation_checks:
            result.issues.extend(await check(htn, constraints, resources, goal))
        if result.issues:
            error_count = sum(1 for i in result.issues if i.severity == "error")
            result.status = ValidationStatus.FAILED if error_count > 0 else ValidationStatus.WARNING
            result.failed_checks = [i.issue_type for i in result.issues]
        else:
            result.passed_checks = [c.__name__ for c in self.validation_checks]
        result.execution_feasibility = self._determine_feasibility(result)
        result.confidence_score = self._calculate_validation_confidence(result)
        return result

    async def _check_dependency_cycles(self, htn, constraints, resources, goal):
        issues = []
        if self._has_dependency_cycle(htn):
            issues.append(ValidationIssue(
                issue_type="dependency_cycle", severity="error",
                description="Circular dependency detected",
                affected_elements=self._find_cycle_tasks(htn),
                remediation="Remove circular references",
            ))
        return issues

    async def _check_missing_resources(self, htn, constraints, resources, goal):
        issues = []
        if not resources.key_skills_needed:
            issues.append(ValidationIssue(
                issue_type="missing_resources", severity="warning",
                description="No key skills identified",
                remediation="Review goal and identify required competencies",
            ))
        for task in htn.all_tasks.values():
            for req in task.required_resources:
                if not any(r.resource_name == req for r in resources.required_resources):
                    issues.append(ValidationIssue(
                        issue_type="missing_resources", severity="warning",
                        description=f"Required resource '{req}' not in profile",
                        affected_elements=[task.task_id],
                    ))
        return issues

    async def _check_invalid_goals(self, htn, constraints, resources, goal):
        issues = []
        if not goal or not goal.strip():
            issues.append(ValidationIssue(issue_type="invalid_goal", severity="error",
                                           description="Goal is empty"))
        elif len(goal) < 5:
            issues.append(ValidationIssue(issue_type="invalid_goal", severity="warning",
                                           description="Goal description is very brief"))
        return issues

    async def _check_duplicate_tasks(self, htn, constraints, resources, goal):
        issues = []
        titles = [t.task_title for t in htn.all_tasks.values()]
        for dup in set(t for t in titles if titles.count(t) > 1):
            ids = [t.task_id for t in htn.all_tasks.values() if t.task_title == dup]
            issues.append(ValidationIssue(issue_type="duplicate_task", severity="warning",
                                           description=f"Duplicate task: '{dup}'",
                                           affected_elements=ids))
        return issues

    async def _check_conflicting_constraints(self, htn, constraints, resources, goal):
        issues = []
        if len(constraints) > 5:
            issues.append(ValidationIssue(issue_type="conflicting_constraints", severity="warning",
                                           description="Many constraints may conflict"))
        return issues

    async def _check_deadline_conflicts(self, htn, constraints, resources, goal):
        issues = []
        total = sum(t.estimated_duration_hours for t in htn.all_tasks.values())
        if total > 1000:
            issues.append(ValidationIssue(issue_type="deadline_conflict", severity="warning",
                                           description=f"Total effort ({total}h) is very high"))
        return issues

    async def _check_execution_feasibility(self, htn, constraints, resources, goal):
        issues = []
        if htn.total_tasks > 50:
            issues.append(ValidationIssue(issue_type="execution_feasibility", severity="warning",
                                           description=f"Plan has {htn.total_tasks} tasks"))
        if htn.max_depth > 5:
            issues.append(ValidationIssue(issue_type="execution_feasibility", severity="warning",
                                           description=f"Depth {htn.max_depth} may be too deep"))
        orphaned = [t for t in htn.all_tasks.values()
                    if t.task_id != htn.root_task_id and not t.dependencies and t.parent_task_id is None]
        if orphaned:
            issues.append(ValidationIssue(issue_type="execution_feasibility", severity="warning",
                                           description=f"{len(orphaned)} orphaned tasks",
                                           affected_elements=[t.task_id for t in orphaned]))
        return issues

    def _has_dependency_cycle(self, htn):
        visited, rec_stack = set(), set()
        def visit(tid):
            visited.add(tid); rec_stack.add(tid)
            task = htn.all_tasks.get(tid)
            if task:
                for dep in task.dependencies:
                    if dep not in visited:
                        if visit(dep): return True
                    elif dep in rec_stack: return True
            rec_stack.discard(tid); return False
        return any(visit(tid) for tid in htn.all_tasks if tid not in visited)

    def _find_cycle_tasks(self, htn):
        cycle_tasks, visited = [], {}
        def dfs(tid, path):
            visited[tid] = "visiting"
            task = htn.all_tasks.get(tid)
            if task:
                for dep in task.dependencies:
                    if dep not in visited: dfs(dep, path + [tid])
                    elif visited[dep] == "visiting":
                        start = path.index(dep) if dep in path else 0
                        cycle_tasks.extend(path[start:] + [tid, dep])
            visited[tid] = "visited"
        for tid in htn.all_tasks:
            if tid not in visited: dfs(tid, [])
        return list(set(cycle_tasks))

    def _determine_feasibility(self, result):
        if result.status == ValidationStatus.FAILED: return "not_feasible"
        errors = sum(1 for i in result.issues if i.severity == "error")
        warnings = sum(1 for i in result.issues if i.severity == "warning")
        return "needs_review" if errors > 2 or warnings > 5 else "feasible"

    def _calculate_validation_confidence(self, result):
        c = 1.0 - 0.05 * len(result.issues)
        c -= 0.1 * sum(1 for i in result.issues if i.severity == "error")
        c -= 0.02 * sum(1 for i in result.issues if i.severity == "warning")
        return max(0.0, min(1.0, c))


class RiskAnalyzer:
    """Production risk analysis."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.version = "1.0.0"

    async def analyze_risks(self, goal, htn, constraints, resources):
        risks = []
        risks.extend(await self._identify_goal_risks(goal))
        risks.extend(await self._identify_task_risks(htn))
        risks.extend(await self._identify_constraint_risks(constraints))
        risks.extend(await self._identify_resource_risks(resources))
        for r in risks:
            await self._score_risk(r)
        risks.sort(key=lambda r: r.overall_risk_score, reverse=True)
        return risks

    async def _identify_goal_risks(self, goal):
        risks = []
        r = Risk(risk_id=str(uuid.uuid4()), risk_description="Timeline slippage",
                 risk_type="timeline", probability="medium", impact="medium",
                 severity=RiskSeverity.MEDIUM, likelihood_score=0.6, impact_score=0.6)
        r.mitigations.append(RiskMitigation(strategy_description="Build 20% buffer",
                                             estimated_effectiveness=0.7))
        risks.append(r)
        if len(goal) < 20 or "and" not in goal.lower():
            r2 = Risk(risk_id=str(uuid.uuid4()), risk_description="Scope creep",
                      risk_type="execution", probability="medium", impact="high",
                      severity=RiskSeverity.HIGH, likelihood_score=0.5, impact_score=0.8)
            risks.append(r2)
        return risks

    async def _identify_task_risks(self, htn):
        risks = []
        high = [t for t in htn.all_tasks.values() if t.estimated_effort in ("high", "critical")]
        if high:
            r = Risk(risk_id=str(uuid.uuid4()), risk_description="Technical challenges",
                     risk_type="technical", probability="medium", impact="medium",
                     severity=RiskSeverity.MEDIUM, likelihood_score=0.6, impact_score=0.6,
                     affected_tasks=[t.task_id for t in high])
            risks.append(r)
        total_deps = sum(len(t.dependencies) for t in htn.all_tasks.values())
        if total_deps > htn.total_tasks:
            risks.append(Risk(risk_id=str(uuid.uuid4()),
                              risk_description="Complex interdependencies",
                              risk_type="execution", probability="low", impact="high",
                              severity=RiskSeverity.HIGH, likelihood_score=0.3, impact_score=0.8))
        return risks

    async def _identify_constraint_risks(self, constraints):
        risks = []
        if len(constraints) > 3:
            risks.append(Risk(risk_id=str(uuid.uuid4()),
                              risk_description="Constraint pressure",
                              risk_type="execution", probability="medium", impact="medium",
                              severity=RiskSeverity.MEDIUM, likelihood_score=0.5, impact_score=0.6))
        return risks

    async def _identify_resource_risks(self, resources):
        risks = []
        if not resources.key_skills_needed:
            risks.append(Risk(risk_id=str(uuid.uuid4()),
                              risk_description="Missing resource specification",
                              risk_type="resource", probability="high", impact="medium",
                              severity=RiskSeverity.MEDIUM, likelihood_score=0.8, impact_score=0.6))
        return risks

    async def _score_risk(self, risk):
        m = {"low": 0.3, "medium": 0.6, "high": 0.9, "critical": 1.0}
        risk.likelihood_score = m.get(risk.probability, 0.5)
        risk.impact_score = m.get(risk.impact, 0.5)
        risk.overall_risk_score = risk.likelihood_score * risk.impact_score
        if risk.overall_risk_score > 0.7: risk.severity = RiskSeverity.HIGH
        elif risk.overall_risk_score > 0.4: risk.severity = RiskSeverity.MEDIUM
        else: risk.severity = RiskSeverity.LOW


# ── Sync-compatible PlanValidator facade (test API) ────────────────────────

class PlanValidator:
    """Sync-compatible plan validator for tests."""

    def __init__(self, config=None):
        self._validator = _AsyncPlanValidator(config)
        self._risk_analyzer = RiskAnalyzer(config)

    def validate_plan(self, plan) -> dict:
        import asyncio
        htn = HierarchicalTaskNetwork()
        for t in getattr(plan, 'tasks', []):
            dt = DecomposedTask(
                task_id=getattr(t, 'id', str(uuid.uuid4())),
                task_title=getattr(t, 'title', ''),
                estimated_duration_hours=getattr(t, 'estimated_effort_hours', 0.0),
                assigned_to=getattr(t, 'assigned_to', None),
            )
            htn.all_tasks[dt.task_id] = dt
        htn.total_tasks = len(htn.all_tasks)
        result = asyncio.get_event_loop().run_until_complete(
            self._validator.validate_plan(
                plan_id=getattr(plan, 'id', 'plan'),
                htn=htn, constraints=[], resources=ResourceProfile(),
                goal=getattr(plan, 'title', ''),
            )
        )
        return {"is_valid": result.status.value != "failed", "issues": len(result.issues),
                "status": result.status.value, "confidence": result.confidence_score}

    def identify_risks(self, plan) -> list:
        import asyncio
        htn = HierarchicalTaskNetwork()
        for t in getattr(plan, 'tasks', []):
            dt = DecomposedTask(
                task_id=getattr(t, 'id', str(uuid.uuid4())),
                task_title=getattr(t, 'title', ''),
                estimated_duration_hours=getattr(t, 'estimated_effort_hours', 0.0),
            )
            htn.all_tasks[dt.task_id] = dt
        htn.total_tasks = len(htn.all_tasks)
        return asyncio.get_event_loop().run_until_complete(
            self._risk_analyzer.analyze_risks(
                goal=getattr(plan, 'title', ''), htn=htn,
                constraints=[], resources=ResourceProfile(),
            )
        )

    def check_resource_conflicts(self, plan) -> list:
        conflicts, by_person = [], {}
        for t in getattr(plan, 'tasks', []):
            person = getattr(t, 'assigned_to', None)
            if not person: continue
            start, end = getattr(t, 'start_time', None), getattr(t, 'end_time', None)
            by_person.setdefault(person, [])
            for ps, pe in by_person[person]:
                if start and end and ps and pe and start < pe and end > ps:
                    conflicts.append({"person": person, "task": getattr(t, 'id', '')})
            if start and end:
                by_person[person].append((start, end))
        return conflicts
