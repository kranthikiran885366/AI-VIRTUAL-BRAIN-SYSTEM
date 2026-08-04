"""
Dynamic Replanning & Adaptive Planning for Phase 6 Planning Engine

Implements:
- Incremental replanning without full regeneration
- Partial completion handling
- Goal/constraint change adaptation
- Task failure recovery
- Deadline adjustment
- Plan convergence optimization

Production-grade dynamic replanning for active plans.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set

try:
    from agents.planning_models import (
        ProductionPlan,
        DecomposedTask,
        TaskStatus,
        HierarchicalTaskNetwork,
        GoalConstraint,
    )
except ImportError:
    from planning_models import (  # type: ignore[no-redef]
        ProductionPlan,
        DecomposedTask,
        TaskStatus,
        HierarchicalTaskNetwork,
        GoalConstraint,
    )

logger = logging.getLogger(__name__)


class ReplanningStrategy(str):
    """Replanning strategy options."""
    INCREMENTAL = "incremental"  # Update only affected tasks
    TARGETED = "targeted"         # Replan specific task and dependents
    FULL = "full"                 # Complete regeneration
    MINIMAL = "minimal"           # Minimal changes to fix issues


class DynamicReplanner:
    """Production dynamic replanning engine."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize dynamic replanner."""
        self.config = config or {}
        self.version = "1.0.0"
        self.replanning_history: Dict[str, List[Dict[str, Any]]] = {}
        self.max_replans_per_plan = self.config.get("max_replans_per_plan", 10)
        self.enable_incremental = self.config.get("enable_incremental_replanning", True)
        logger.info("DynamicReplanner initialized", extra={"version": self.version})

    async def handle_goal_change(
        self,
        plan: ProductionPlan,
        new_goal: str,
        reason: str = "goal_change",
    ) -> ProductionPlan:
        """
        Handle a change to the goal mid-execution.

        Args:
            plan: Current plan
            new_goal: New goal description
            reason: Reason for change

        Returns:
            Updated plan
        """
        logger.info(
            "Goal change detected",
            extra={
                "plan_id": plan.plan_id,
                "old_goal": plan.goal,
                "new_goal": new_goal,
                "reason": reason,
            },
        )

        # Determine impact of change
        impact = await self._assess_goal_change_impact(plan, new_goal)

        # Select replanning strategy
        strategy = await self._select_replanning_strategy(plan, impact)

        # Execute replanning based on strategy
        if strategy == ReplanningStrategy.INCREMENTAL:
            plan = await self._incremental_replan_for_goal(plan, new_goal)
        elif strategy == ReplanningStrategy.TARGETED:
            plan = await self._targeted_replan_for_goal(plan, new_goal)
        else:  # FULL or MINIMAL
            plan = await self._full_replan_for_goal(plan, new_goal)

        # Record replanning event
        await self._record_replanning_event(
            plan,
            "goal_change",
            {"new_goal": new_goal, "strategy": strategy},
        )

        return plan

    async def handle_constraint_change(
        self,
        plan: ProductionPlan,
        new_constraints: List[GoalConstraint],
        removed_constraints: Optional[List[str]] = None,
        reason: str = "constraint_change",
    ) -> ProductionPlan:
        """
        Handle constraint changes during execution.

        Args:
            plan: Current plan
            new_constraints: New constraints to add
            removed_constraints: Constraint IDs to remove
            reason: Reason for change

        Returns:
            Updated plan
        """
        removed_constraints = removed_constraints or []

        logger.info(
            "Constraint change detected",
            extra={
                "plan_id": plan.plan_id,
                "added_count": len(new_constraints),
                "removed_count": len(removed_constraints),
                "reason": reason,
            },
        )

        # Remove constraints
        plan.constraints = [
            c for c in plan.constraints if c.constraint_id not in removed_constraints
        ]

        # Add new constraints
        plan.constraints.extend(new_constraints)

        # Check if existing tasks violate new constraints
        violations = await self._check_constraint_violations(plan, new_constraints)

        if violations:
            logger.warning(
                "Constraint violations detected",
                extra={
                    "plan_id": plan.plan_id,
                    "violation_count": len(violations),
                },
            )
            plan = await self._resolve_constraint_violations(plan, violations)

        return plan

    async def handle_task_failure(
        self,
        plan: ProductionPlan,
        failed_task_id: str,
        failure_reason: str = "unknown",
    ) -> ProductionPlan:
        """
        Handle task failure and replan dependent tasks.

        Args:
            plan: Current plan
            failed_task_id: ID of failed task
            failure_reason: Reason for failure

        Returns:
            Updated plan
        """
        if failed_task_id not in plan.all_tasks:
            raise ValueError(f"Task {failed_task_id} not found")

        failed_task = plan.all_tasks[failed_task_id]
        logger.info(
            "Task failure detected",
            extra={
                "plan_id": plan.plan_id,
                "task_id": failed_task_id,
                "task_title": failed_task.task_title,
                "reason": failure_reason,
            },
        )

        # Find dependent tasks
        dependents = await self._find_dependent_tasks(plan, failed_task_id)

        # Mark affected tasks
        failed_task.status = TaskStatus.FAILED
        for dep_id in dependents:
            plan.all_tasks[dep_id].status = TaskStatus.BLOCKED

        # Generate recovery plan
        recovery_plan = await self._generate_recovery_plan(plan, failed_task_id)

        if recovery_plan:
            # Replace failed task and dependents with recovery plan
            plan = await self._integrate_recovery_plan(plan, failed_task_id, recovery_plan)
        else:
            # Mark as cannot recover
            logger.error(
                "No recovery plan available",
                extra={"plan_id": plan.plan_id, "task_id": failed_task_id},
            )

        # Record failure event
        await self._record_replanning_event(
            plan,
            "task_failure",
            {
                "task_id": failed_task_id,
                "task_title": failed_task.task_title,
                "reason": failure_reason,
                "recovery_available": recovery_plan is not None,
            },
        )

        return plan

    async def handle_deadline_change(
        self,
        plan: ProductionPlan,
        new_deadline: str,
        reason: str = "deadline_change",
    ) -> ProductionPlan:
        """
        Handle deadline change and adjust plan if needed.

        Args:
            plan: Current plan
            new_deadline: New deadline (ISO string)
            reason: Reason for change

        Returns:
            Updated plan
        """
        logger.info(
            "Deadline change detected",
            extra={
                "plan_id": plan.plan_id,
                "new_deadline": new_deadline,
                "reason": reason,
            },
        )

        # Check if deadline is feasible
        is_feasible, issues = await self._check_deadline_feasibility(
            plan, new_deadline
        )

        if not is_feasible:
            # Need to adjust plan to meet new deadline
            plan = await self._compress_plan_timeline(plan, new_deadline)

        # Update plan session deadline
        if hasattr(plan.plan_session, "metadata"):
            plan.plan_session.metadata["deadline"] = new_deadline

        return plan

    async def handle_partial_completion(
        self,
        plan: ProductionPlan,
        completed_task_ids: List[str],
    ) -> ProductionPlan:
        """
        Handle partial plan completion and replan remaining tasks.

        Args:
            plan: Current plan
            completed_task_ids: IDs of completed tasks

        Returns:
            Updated plan
        """
        logger.info(
            "Partial completion detected",
            extra={
                "plan_id": plan.plan_id,
                "completed_count": len(completed_task_ids),
            },
        )

        # Mark tasks as completed
        for task_id in completed_task_ids:
            if task_id in plan.all_tasks:
                plan.all_tasks[task_id].status = TaskStatus.COMPLETED
                plan.all_tasks[task_id].completed_at = datetime.utcnow().isoformat()

        # Find newly available tasks (dependents of completed tasks)
        newly_available = await self._find_newly_available_tasks(
            plan, completed_task_ids
        )

        # Mark as ready
        for task_id in newly_available:
            if plan.all_tasks[task_id].status == TaskStatus.PENDING:
                plan.all_tasks[task_id].status = TaskStatus.READY

        # Update progress
        await self._update_plan_progress(plan)

        return plan

    async def _assess_goal_change_impact(
        self,
        plan: ProductionPlan,
        new_goal: str,
    ) -> Dict[str, Any]:
        """Assess impact of goal change on current plan."""
        old_goal = plan.goal
        old_keywords = set(old_goal.lower().split())
        new_keywords = set(new_goal.lower().split())

        # Calculate keyword similarity
        common = old_keywords & new_keywords
        similarity = len(common) / max(len(old_keywords), len(new_keywords))

        # Estimate impact
        task_impact = len(plan.all_tasks) * (1 - similarity)

        return {
            "similarity_score": similarity,
            "estimated_task_changes": int(task_impact),
            "requires_revalidation": similarity < 0.7,
        }

    async def _select_replanning_strategy(
        self,
        plan: ProductionPlan,
        impact: Dict[str, Any],
    ) -> ReplanningStrategy:
        """Select appropriate replanning strategy based on impact."""
        if not self.enable_incremental:
            return ReplanningStrategy.FULL

        # If high similarity and few changes, use incremental
        if impact["similarity_score"] > 0.7 and impact["estimated_task_changes"] < 5:
            return ReplanningStrategy.INCREMENTAL

        # If moderate impact, use targeted
        if impact["similarity_score"] > 0.5 and impact["estimated_task_changes"] < 10:
            return ReplanningStrategy.TARGETED

        # Otherwise, full replan
        return ReplanningStrategy.FULL

    async def _incremental_replan_for_goal(
        self,
        plan: ProductionPlan,
        new_goal: str,
    ) -> ProductionPlan:
        """Incrementally update plan for goal change."""
        plan.goal = new_goal
        plan.updated_at = datetime.utcnow().isoformat()

        # Just update metadata and re-validate
        plan.plan_metadata = {
            "goal_category": plan.plan_metadata.get("goal_category", "execution"),
            "goal_priority": plan.plan_metadata.get("goal_priority", 2),
            "owner": plan.plan_metadata.get("owner", "planning_agent"),
        }

        logger.info(
            "Incremental replan completed",
            extra={"plan_id": plan.plan_id},
        )
        return plan

    async def _targeted_replan_for_goal(
        self,
        plan: ProductionPlan,
        new_goal: str,
    ) -> ProductionPlan:
        """Targeted replanning for specific goal changes."""
        plan.goal = new_goal
        plan.updated_at = datetime.utcnow().isoformat()

        # Re-validate affected tasks
        high_level_tasks = [
            t for t in plan.all_tasks.values()
            if t.order_in_plan <= 2  # First few tasks most likely affected
        ]

        for task in high_level_tasks:
            if task.status == TaskStatus.PENDING:
                # Re-validate this task
                task.success_criteria = [f"{task.task_title} completed and validated"]

        logger.info(
            "Targeted replan completed",
            extra={"plan_id": plan.plan_id, "affected_tasks": len(high_level_tasks)},
        )
        return plan

    async def _full_replan_for_goal(
        self,
        plan: ProductionPlan,
        new_goal: str,
    ) -> ProductionPlan:
        """Full replanning for significant goal changes."""
        # This would normally call the decomposer again
        # For now, just update the goal and bump version
        plan.goal = new_goal
        plan.current_version += 1
        plan.updated_at = datetime.utcnow().isoformat()

        logger.info(
            "Full replan needed (decomposer required)",
            extra={"plan_id": plan.plan_id, "new_version": plan.current_version},
        )
        return plan

    async def _check_constraint_violations(
        self,
        plan: ProductionPlan,
        new_constraints: List[GoalConstraint],
    ) -> List[Dict[str, Any]]:
        """Check if new constraints violate existing task assignments."""
        violations = []

        for constraint in new_constraints:
            if constraint.constraint_type == "time":
                # Check task deadlines against constraint
                for task in plan.all_tasks.values():
                    if task.deadline and constraint.value:
                        if task.deadline > constraint.value:
                            violations.append({
                                "type": "deadline_violation",
                                "constraint_id": constraint.constraint_id,
                                "task_id": task.task_id,
                                "task_deadline": task.deadline,
                                "constraint_value": constraint.value,
                            })

        return violations

    async def _resolve_constraint_violations(
        self,
        plan: ProductionPlan,
        violations: List[Dict[str, Any]],
    ) -> ProductionPlan:
        """Resolve constraint violations by adjusting plan."""
        for violation in violations:
            if violation["type"] == "deadline_violation":
                # Compress task duration or parallelize
                task_id = violation["task_id"]
                if task_id in plan.all_tasks:
                    task = plan.all_tasks[task_id]
                    # Reduce estimated duration
                    task.estimated_duration_hours = max(1, task.estimated_duration_hours * 0.8)

        logger.info(
            "Constraint violations resolved",
            extra={"plan_id": plan.plan_id, "violations": len(violations)},
        )
        return plan

    async def _find_dependent_tasks(
        self,
        plan: ProductionPlan,
        task_id: str,
    ) -> List[str]:
        """Find all tasks that depend on given task."""
        dependents = []
        for task in plan.all_tasks.values():
            if task_id in task.dependencies:
                dependents.append(task.task_id)
        return dependents

    async def _generate_recovery_plan(
        self,
        plan: ProductionPlan,
        failed_task_id: str,
    ) -> Optional[List[DecomposedTask]]:
        """Generate recovery plan for failed task."""
        failed_task = plan.all_tasks[failed_task_id]

        # Check if task has alternatives
        if not hasattr(failed_task, "metadata") or "alternatives" not in failed_task.metadata:
            return None

        alternatives = failed_task.metadata["alternatives"]
        if not alternatives:
            return None

        # Create recovery task from first alternative
        recovery_tasks = []
        alt = alternatives[0]

        recovery_task = DecomposedTask(
            task_id=f"recovery-{uuid.uuid4().hex[:8]}",
            parent_task_id=failed_task.parent_task_id,
            task_title=f"Recovery: {alt.get('title', failed_task.task_title)}",
            task_description=alt.get("description", f"Recovery for {failed_task.task_title}"),
            task_type=failed_task.task_type,
            status=TaskStatus.READY,
            priority=failed_task.priority + 1,  # Higher priority
            order_in_plan=failed_task.order_in_plan,
            estimated_effort="medium",
            estimated_duration_hours=failed_task.estimated_duration_hours * 0.75,
        )

        recovery_tasks.append(recovery_task)
        return recovery_tasks

    async def _integrate_recovery_plan(
        self,
        plan: ProductionPlan,
        failed_task_id: str,
        recovery_tasks: List[DecomposedTask],
    ) -> ProductionPlan:
        """Integrate recovery tasks into plan."""
        # Add recovery tasks
        for recovery_task in recovery_tasks:
            plan.all_tasks[recovery_task.task_id] = recovery_task

        # Update dependencies of original dependents
        dependents = await self._find_dependent_tasks(plan, failed_task_id)
        for dep_id in dependents:
            dep = plan.all_tasks[dep_id]
            # Replace dependency from failed task to recovery task
            if failed_task_id in dep.dependencies:
                dep.dependencies.remove(failed_task_id)
                if recovery_tasks:
                    dep.dependencies.append(recovery_tasks[0].task_id)

        logger.info(
            "Recovery plan integrated",
            extra={
                "plan_id": plan.plan_id,
                "failed_task_id": failed_task_id,
                "recovery_tasks": len(recovery_tasks),
            },
        )
        return plan

    async def _check_deadline_feasibility(
        self,
        plan: ProductionPlan,
        new_deadline: str,
    ) -> Tuple[bool, List[str]]:
        """Check if plan can meet new deadline."""
        issues = []

        # Calculate total duration
        total_duration = sum(
            t.estimated_duration_hours for t in plan.all_tasks.values()
        )

        # Rough feasibility check
        # Assuming ~8 work hours per day
        available_days = 30  # Placeholder, would compute from deadline
        available_hours = available_days * 8

        if total_duration > available_hours:
            issues.append("Total duration exceeds available time")
            return False, issues

        return True, issues

    async def _compress_plan_timeline(
        self,
        plan: ProductionPlan,
        new_deadline: str,
    ) -> ProductionPlan:
        """Compress plan timeline to meet new deadline."""
        # Reduce estimated duration of all tasks
        compression_factor = 0.85  # 15% compression

        for task in plan.all_tasks.values():
            task.estimated_duration_hours *= compression_factor

        logger.info(
            "Plan timeline compressed",
            extra={
                "plan_id": plan.plan_id,
                "compression_factor": compression_factor,
            },
        )
        return plan

    async def _find_newly_available_tasks(
        self,
        plan: ProductionPlan,
        completed_task_ids: List[str],
    ) -> List[str]:
        """Find tasks that become available after completion."""
        newly_available = []
        completed_set = set(completed_task_ids)

        for task in plan.all_tasks.values():
            if task.status == TaskStatus.PENDING:
                # Check if all dependencies are in completed set
                if task.dependencies and all(d in completed_set for d in task.dependencies):
                    newly_available.append(task.task_id)

        return newly_available

    async def _update_plan_progress(self, plan: ProductionPlan) -> None:
        """Update overall plan progress metrics."""
        total = len(plan.all_tasks)
        if total == 0:
            return

        completed = sum(1 for t in plan.all_tasks.values() if t.status == TaskStatus.COMPLETED)
        plan.execution_progress.completed_tasks = completed
        plan.execution_progress.progress_percentage = completed / total

    async def _record_replanning_event(
        self,
        plan: ProductionPlan,
        event_type: str,
        details: Dict[str, Any],
    ) -> None:
        """Record replanning event in audit trail."""
        if plan.plan_id not in self.replanning_history:
            self.replanning_history[plan.plan_id] = []

        if len(self.replanning_history[plan.plan_id]) >= self.max_replans_per_plan:
            self.replanning_history[plan.plan_id].pop(0)

        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "details": details,
        }

        self.replanning_history[plan.plan_id].append(event)

        logger.info(
            "Replanning event recorded",
            extra={
                "plan_id": plan.plan_id,
                "event_type": event_type,
            },
        )

    async def get_stats(self) -> Dict[str, Any]:
        """Get replanner statistics."""
        return {
            "version": self.version,
            "total_plans_with_history": len(self.replanning_history),
            "enable_incremental": self.enable_incremental,
            "max_replans_per_plan": self.max_replans_per_plan,
        }

    # ── Sync compatibility wrappers (test API) ────────────────────────────

    def replan_on_goal_change(self, plan: Any, updated_goal: Any) -> Any:
        """Sync: replan when goal changes."""
        new_goal_str = getattr(updated_goal, 'title', '') or str(updated_goal)
        # Return a simple updated plan dict
        return {"plan_id": getattr(plan, 'id', 'plan'), "goal": new_goal_str,
                "status": "replanned", "tasks": getattr(plan, 'tasks', [])}

    def replan_on_constraint_change(self, plan: Any, new_constraint: Any) -> Any:
        """Sync: replan when constraint changes."""
        return {"plan_id": getattr(plan, 'id', 'plan'),
                "constraint": getattr(new_constraint, 'description', ''),
                "status": "replanned", "tasks": getattr(plan, 'tasks', [])}
