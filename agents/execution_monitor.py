"""
Execution Monitor for Phase 6 Planning Engine

Implements:
- Real-time task state tracking
- Progress metrics calculation
- Blocked/waiting task detection
- Execution history management
- Failure analysis and reporting
- Performance metrics collection

Production-grade execution monitoring for active plans.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from planning_models import (
    ProductionPlan,
    DecomposedTask,
    TaskStatus,
    ExecutionProgress,
)

logger = logging.getLogger(__name__)


class TaskExecutionTracker:
    """Track individual task execution."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize task tracker."""
        self.config = config or {}
        self.version = "1.0.0"
        self.task_states: Dict[str, Dict[str, Any]] = {}
        self.task_history: Dict[str, List[Dict[str, Any]]] = {}
        self.blocked_threshold_minutes = self.config.get("blocked_task_threshold_minutes", 30)
        logger.info("TaskExecutionTracker initialized", extra={"version": self.version})

    async def track_task_start(
        self,
        task_id: str,
        plan_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track task start."""
        metadata = metadata or {}

        self.task_states[task_id] = {
            "plan_id": plan_id,
            "status": TaskStatus.RUNNING.value,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "duration_seconds": None,
            "metadata": metadata,
        }

        if task_id not in self.task_history:
            self.task_history[task_id] = []

        self.task_history[task_id].append({
            "event": "started",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata,
        })

        logger.info(
            "Task execution started",
            extra={"task_id": task_id, "plan_id": plan_id},
        )

    async def track_task_completion(
        self,
        task_id: str,
        success: bool = True,
        result: Optional[str] = None,
    ) -> None:
        """Track task completion."""
        if task_id not in self.task_states:
            logger.warning(
                "Completion tracked for unstarted task",
                extra={"task_id": task_id},
            )
            return

        state = self.task_states[task_id]
        state["completed_at"] = datetime.utcnow().isoformat()
        state["success"] = success
        state["result"] = result

        # Calculate duration
        start = datetime.fromisoformat(state["started_at"])
        end = datetime.fromisoformat(state["completed_at"])
        state["duration_seconds"] = (end - start).total_seconds()

        # Update status
        state["status"] = TaskStatus.COMPLETED.value if success else TaskStatus.FAILED.value

        self.task_history[task_id].append({
            "event": "completed" if success else "failed",
            "timestamp": state["completed_at"],
            "duration_seconds": state["duration_seconds"],
            "result": result,
        })

        logger.info(
            "Task execution completed",
            extra={
                "task_id": task_id,
                "success": success,
                "duration_seconds": state["duration_seconds"],
            },
        )

    async def track_task_blocked(
        self,
        task_id: str,
        reason: str = "unknown",
    ) -> None:
        """Track task becoming blocked."""
        if task_id not in self.task_states:
            self.task_states[task_id] = {
                "status": TaskStatus.BLOCKED.value,
                "blocked_at": datetime.utcnow().isoformat(),
            }
        else:
            self.task_states[task_id]["status"] = TaskStatus.BLOCKED.value
            self.task_states[task_id]["blocked_at"] = datetime.utcnow().isoformat()
            self.task_states[task_id]["block_reason"] = reason

        if task_id not in self.task_history:
            self.task_history[task_id] = []

        self.task_history[task_id].append({
            "event": "blocked",
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason,
        })

        logger.info(
            "Task marked as blocked",
            extra={"task_id": task_id, "reason": reason},
        )

    async def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current task state."""
        return self.task_states.get(task_id)

    async def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
        """Get task execution history."""
        return self.task_history.get(task_id, [])

    async def detect_stalled_tasks(self) -> List[Tuple[str, int]]:
        """
        Detect tasks that have been in progress longer than threshold.

        Returns:
            List of (task_id, stalled_minutes)
        """
        stalled = []
        now = datetime.utcnow()

        for task_id, state in self.task_states.items():
            if state["status"] == TaskStatus.RUNNING.value:
                started = datetime.fromisoformat(state["started_at"])
                elapsed_minutes = (now - started).total_seconds() / 60

                if elapsed_minutes > self.blocked_threshold_minutes:
                    stalled.append((task_id, int(elapsed_minutes)))

        return stalled


class ProgressCalculator:
    """Calculate plan progress metrics."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize progress calculator."""
        self.config = config or {}
        self.version = "1.0.0"
        logger.info("ProgressCalculator initialized", extra={"version": self.version})

    async def calculate_plan_progress(
        self,
        plan: ProductionPlan,
    ) -> ExecutionProgress:
        """
        Calculate comprehensive progress metrics for a plan.

        Args:
            plan: Plan to analyze

        Returns:
            Progress metrics
        """
        tasks = plan.all_tasks.values()
        total = len(tasks)

        if total == 0:
            return ExecutionProgress()

        # Count task statuses
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        cancelled = sum(1 for t in tasks if t.status == TaskStatus.CANCELLED)
        blocked = sum(1 for t in tasks if t.status == TaskStatus.BLOCKED)
        waiting = sum(1 for t in tasks if t.status == TaskStatus.WAITING)
        running = sum(1 for t in tasks if t.status == TaskStatus.RUNNING)

        # Calculate progress percentage
        progress = completed / total

        # Estimate completion time
        completion_time = await self._estimate_completion_time(plan)

        # Create progress object
        progress_obj = ExecutionProgress(
            total_tasks=total,
            completed_tasks=completed,
            failed_tasks=failed,
            cancelled_tasks=cancelled,
            blocked_tasks=blocked,
            waiting_tasks=waiting,
            running_tasks=running,
            progress_percentage=round(progress, 3),
            estimated_completion_time=completion_time,
            last_updated=datetime.utcnow().isoformat(),
        )

        return progress_obj

    async def _estimate_completion_time(
        self,
        plan: ProductionPlan,
    ) -> Optional[str]:
        """Estimate when plan will complete."""
        remaining_tasks = [
            t for t in plan.all_tasks.values()
            if t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED)
        ]

        if not remaining_tasks:
            return None

        # Calculate total remaining duration
        total_remaining_hours = sum(
            t.estimated_duration_hours for t in remaining_tasks
        )

        # Estimate completion (simple linear assumption)
        estimated_completion = datetime.utcnow() + timedelta(hours=total_remaining_hours)
        return estimated_completion.isoformat()

    async def calculate_task_completion_rate(
        self,
        plan: ProductionPlan,
        time_window_minutes: int = 60,
    ) -> float:
        """
        Calculate task completion rate in given time window.

        Args:
            plan: Plan to analyze
            time_window_minutes: Time window to analyze

        Returns:
            Tasks completed per minute
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        recently_completed = [
            t for t in plan.all_tasks.values()
            if t.status == TaskStatus.COMPLETED and t.completed_at
            and datetime.fromisoformat(t.completed_at) > cutoff_time
        ]

        return len(recently_completed) / time_window_minutes if time_window_minutes > 0 else 0.0

    async def calculate_critical_path(
        self,
        plan: ProductionPlan,
    ) -> Tuple[List[str], float]:
        """
        Calculate critical path and duration.

        Args:
            plan: Plan to analyze

        Returns:
            (Task IDs in critical path, total duration in hours)
        """
        # Find longest dependency chain
        critical_path = []
        max_duration = 0.0

        for task in plan.all_tasks.values():
            path_duration = await self._calculate_path_duration(plan, task.task_id)
            if path_duration > max_duration:
                max_duration = path_duration
                critical_path = await self._get_task_path(plan, task.task_id)

        return critical_path, max_duration

    async def _calculate_path_duration(
        self,
        plan: ProductionPlan,
        task_id: str,
    ) -> float:
        """Calculate total duration of path to task."""
        task = plan.all_tasks.get(task_id)
        if not task or not task.dependencies:
            return task.estimated_duration_hours if task else 0.0

        max_dep_duration = 0.0
        for dep_id in task.dependencies:
            dep_duration = await self._calculate_path_duration(plan, dep_id)
            max_dep_duration = max(max_dep_duration, dep_duration)

        return task.estimated_duration_hours + max_dep_duration

    async def _get_task_path(
        self,
        plan: ProductionPlan,
        task_id: str,
    ) -> List[str]:
        """Get path of dependencies leading to task."""
        task = plan.all_tasks.get(task_id)
        if not task or not task.dependencies:
            return [task_id] if task else []

        # Get longest dependency path
        max_path = []
        for dep_id in task.dependencies:
            dep_path = await self._get_task_path(plan, dep_id)
            if len(dep_path) > len(max_path):
                max_path = dep_path

        return max_path + [task_id]


class ExecutionMonitor:
    """Main execution monitoring component."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize execution monitor."""
        self.config = config or {}
        self.version = "1.0.0"
        self.tracker = TaskExecutionTracker(config)
        self.calculator = ProgressCalculator(config)
        self.monitoring_active: Dict[str, bool] = {}
        logger.info("ExecutionMonitor initialized", extra={"version": self.version})

    async def start_monitoring(
        self,
        plan: ProductionPlan,
    ) -> None:
        """Start monitoring a plan."""
        self.monitoring_active[plan.plan_id] = True
        logger.info("Monitoring started", extra={"plan_id": plan.plan_id})

    async def stop_monitoring(
        self,
        plan_id: str,
    ) -> None:
        """Stop monitoring a plan."""
        self.monitoring_active[plan_id] = False
        logger.info("Monitoring stopped", extra={"plan_id": plan_id})

    async def update_task_status(
        self,
        plan: ProductionPlan,
        task_id: str,
        new_status: TaskStatus,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update task status and track."""
        metadata = metadata or {}

        task = plan.all_tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        old_status = task.status
        task.status = new_status

        # Track state change
        if new_status == TaskStatus.RUNNING:
            await self.tracker.track_task_start(task_id, plan.plan_id, metadata)
        elif new_status == TaskStatus.COMPLETED:
            await self.tracker.track_task_completion(task_id, success=True)
        elif new_status == TaskStatus.FAILED:
            await self.tracker.track_task_completion(
                task_id,
                success=False,
                result=metadata.get("reason", "unknown"),
            )
        elif new_status == TaskStatus.BLOCKED:
            await self.tracker.track_task_blocked(
                task_id,
                reason=metadata.get("reason", "blocked"),
            )

        # Update plan progress
        plan.execution_progress = await self.calculator.calculate_plan_progress(plan)

        logger.info(
            "Task status updated",
            extra={
                "plan_id": plan.plan_id,
                "task_id": task_id,
                "old_status": old_status.value,
                "new_status": new_status.value,
            },
        )

    async def detect_issues(
        self,
        plan: ProductionPlan,
    ) -> Dict[str, Any]:
        """
        Detect execution issues.

        Args:
            plan: Plan to analyze

        Returns:
            Issues found
        """
        issues = {
            "stalled_tasks": [],
            "blocked_tasks": [],
            "failed_tasks": [],
            "warnings": [],
        }

        # Detect stalled tasks
        stalled = await self.tracker.detect_stalled_tasks()
        issues["stalled_tasks"] = [
            {"task_id": tid, "stalled_minutes": minutes}
            for tid, minutes in stalled
        ]

        # Find blocked tasks
        blocked = [
            t for t in plan.all_tasks.values()
            if t.status == TaskStatus.BLOCKED
        ]
        issues["blocked_tasks"] = [{"task_id": t.task_id, "title": t.task_title} for t in blocked]

        # Find failed tasks
        failed = [
            t for t in plan.all_tasks.values()
            if t.status == TaskStatus.FAILED
        ]
        issues["failed_tasks"] = [{"task_id": t.task_id, "title": t.task_title} for t in failed]

        # Generate warnings
        if len(failed) > 0:
            issues["warnings"].append(f"{len(failed)} tasks have failed")
        if len(blocked) > 5:
            issues["warnings"].append(f"{len(blocked)} tasks are blocked")
        if len(stalled) > 0:
            issues["warnings"].append(f"{len(stalled)} tasks appear stalled")

        return issues

    async def generate_execution_report(
        self,
        plan: ProductionPlan,
    ) -> Dict[str, Any]:
        """Generate comprehensive execution report."""
        progress = await self.calculator.calculate_plan_progress(plan)
        critical_path, critical_duration = await self.calculator.calculate_critical_path(plan)
        issues = await self.detect_issues(plan)
        completion_rate = await self.calculator.calculate_task_completion_rate(plan)

        return {
            "plan_id": plan.plan_id,
            "generated_at": datetime.utcnow().isoformat(),
            "progress": {
                "completed_tasks": progress.completed_tasks,
                "total_tasks": progress.total_tasks,
                "progress_percentage": progress.progress_percentage,
                "estimated_completion": progress.estimated_completion_time,
            },
            "critical_path": {
                "task_count": len(critical_path),
                "estimated_duration_hours": critical_duration,
                "task_ids": critical_path,
            },
            "execution_rate": {
                "tasks_per_minute": round(completion_rate, 4),
            },
            "issues": issues,
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Get monitor statistics."""
        return {
            "version": self.version,
            "plans_being_monitored": len([p for p in self.monitoring_active.values() if p]),
            "total_tracked_tasks": len(self.tracker.task_states),
        }
