"""
Task Decomposer & HTN Planning Engine for Phase 6

Implements:
- Hierarchical Task Network (HTN) construction
- Goal-to-task decomposition with multiple strategies
- Constraint-aware decomposition
- Alternative plan generation
- Optimal plan selection
- Parallel vs sequential task scheduling

Production-grade task decomposition engine integrated with planning system.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum

from planning_models import (
    DecomposedTask,
    TaskDependency,
    HierarchicalTaskNetwork,
    TaskType,
    TaskStatus,
    DependencyType,
    GoalConstraint,
)

logger = logging.getLogger(__name__)


class DecompositionStrategy(str, Enum):
    """Task decomposition strategy."""
    GOAL_DECOMPOSITION = "goal_decomposition"
    PHASE_BASED = "phase_based"
    CONSTRAINT_DRIVEN = "constraint_driven"
    RESOURCE_AWARE = "resource_aware"
    TIMELINE_DRIVEN = "timeline_driven"


class TaskDecomposer:
    """Production task decomposition and HTN planning engine."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize task decomposer."""
        self.config = config or {}
        self.version = "1.0.0"
        self.max_decomposition_depth = self.config.get("max_decomposition_depth", 5)
        self.max_tasks_per_plan = self.config.get("max_tasks_per_plan", 50)
        self.parallel_task_limit = self.config.get("parallel_task_limit", 5)
        self.effort_weights = self.config.get(
            "effort_weights",
            {"low": 1, "medium": 2, "high": 4, "critical": 8}
        )
        self.strategy_templates = self._initialize_strategy_templates()
        logger.info("TaskDecomposer initialized", extra={"version": self.version})

    def _initialize_strategy_templates(self) -> Dict[str, List[str]]:
        """Initialize decomposition strategy templates."""
        return {
            DecompositionStrategy.PHASE_BASED: [
                "Research & Requirements",
                "Design & Architecture",
                "Implementation",
                "Testing & Validation",
                "Launch & Monitor",
            ],
            DecompositionStrategy.GOAL_DECOMPOSITION: [
                "Define Objectives",
                "Break into Subtasks",
                "Prioritize",
                "Execute",
                "Review",
            ],
            DecompositionStrategy.CONSTRAINT_DRIVEN: [
                "Analyze Constraints",
                "Identify Bottlenecks",
                "Design Solutions",
                "Implement",
                "Validate",
            ],
        }

    async def decompose_goal(
        self,
        goal: str,
        goal_description: str = "",
        constraints: Optional[List[GoalConstraint]] = None,
        timeframe: Optional[str] = None,
        strategy: DecompositionStrategy = DecompositionStrategy.GOAL_DECOMPOSITION,
        include_alternatives: bool = True,
    ) -> Tuple[HierarchicalTaskNetwork, List[HierarchicalTaskNetwork]]:
        """
        Decompose a goal into structured tasks using HTN planning.

        Args:
            goal: Goal to decompose
            goal_description: Goal description
            constraints: Constraints on decomposition
            timeframe: Expected timeframe
            strategy: Decomposition strategy
            include_alternatives: Whether to generate alternative plans

        Returns:
            Tuple of (primary HTN, alternative HTNs)
        """
        constraints = constraints or []
        logger.info(
            "Decomposing goal",
            extra={
                "goal": goal,
                "strategy": strategy.value,
                "constraint_count": len(constraints),
            },
        )

        # Analyze goal to select/refine strategy
        selected_strategy = await self._select_strategy(goal, strategy, constraints)

        # Generate primary decomposition
        primary_htn = await self._decompose_with_strategy(
            goal=goal,
            goal_description=goal_description,
            constraints=constraints,
            timeframe=timeframe,
            strategy=selected_strategy,
        )

        # Generate alternative decompositions
        alternatives = []
        if include_alternatives:
            alt_strategies = [
                s for s in DecompositionStrategy
                if s != selected_strategy and s in self.strategy_templates
            ]
            for alt_strategy in alt_strategies[:2]:  # Limit to 2 alternatives
                try:
                    alt_htn = await self._decompose_with_strategy(
                        goal=goal,
                        goal_description=goal_description,
                        constraints=constraints,
                        timeframe=timeframe,
                        strategy=alt_strategy,
                    )
                    alternatives.append(alt_htn)
                except Exception as e:
                    logger.debug(
                        "Alternative decomposition failed",
                        extra={"strategy": alt_strategy.value, "error": str(e)},
                    )

        logger.info(
            "Goal decomposed",
            extra={
                "primary_tasks": primary_htn.total_tasks,
                "alternatives": len(alternatives),
            },
        )
        return primary_htn, alternatives

    async def _select_strategy(
        self,
        goal: str,
        requested_strategy: DecompositionStrategy,
        constraints: List[GoalConstraint],
    ) -> DecompositionStrategy:
        """Select decomposition strategy based on goal and constraints."""
        goal_lower = goal.lower()

        # Check for constraint-driven decomposition
        if any(c.constraint_type == "technical" for c in constraints):
            return DecompositionStrategy.CONSTRAINT_DRIVEN
        if any(c.constraint_type == "resource" for c in constraints):
            return DecompositionStrategy.RESOURCE_AWARE

        # Check goal type for strategy hints
        if any(w in goal_lower for w in ["build", "create", "develop", "code"]):
            return DecompositionStrategy.PHASE_BASED
        if any(w in goal_lower for w in ["learn", "understand", "master"]):
            return DecompositionStrategy.GOAL_DECOMPOSITION
        if any(w in goal_lower for w in ["improve", "optimize", "fix"]):
            return DecompositionStrategy.CONSTRAINT_DRIVEN

        return requested_strategy

    async def _decompose_with_strategy(
        self,
        goal: str,
        goal_description: str,
        constraints: List[GoalConstraint],
        timeframe: Optional[str],
        strategy: DecompositionStrategy,
    ) -> HierarchicalTaskNetwork:
        """Decompose goal using specific strategy."""
        htn = HierarchicalTaskNetwork()

        # Generate task phases/milestones
        if strategy in self.strategy_templates:
            phases = self.strategy_templates[strategy]
        else:
            phases = self._generate_phases(goal)

        # Create root task
        root_task = DecomposedTask(
            task_id=f"task-root-{uuid.uuid4().hex[:8]}",
            task_title=goal,
            task_description=goal_description,
            task_type=TaskType.COMPOUND,
            status=TaskStatus.PENDING,
            order_in_plan=0,
            estimated_effort="high",
        )
        htn.root_task_id = root_task.task_id
        htn.all_tasks[root_task.task_id] = root_task

        # Create subtasks for each phase
        previous_task_id = None
        effort_idx = 0
        for order, phase in enumerate(phases, start=1):
            task_id = f"task-{uuid.uuid4().hex[:8]}"

            # Determine effort based on phase type
            effort_levels = ["low", "medium", "high"]
            effort = effort_levels[min(effort_idx, len(effort_levels) - 1)]
            if "implement" in phase.lower() or "execute" in phase.lower():
                effort = "high"
            elif "design" in phase.lower() or "test" in phase.lower():
                effort = "medium"

            task = DecomposedTask(
                task_id=task_id,
                parent_task_id=root_task.task_id,
                task_title=phase,
                task_description=f"Complete '{phase}' for: {goal}",
                task_type=TaskType.ATOMIC,
                status=TaskStatus.PENDING,
                priority=2,
                order_in_plan=order,
                estimated_effort=effort,
                estimated_duration_hours=self.effort_weights.get(effort, 2) * 4,
                success_criteria=[f"{phase} completed and validated"],
            )

            # Add to HTN
            htn.all_tasks[task_id] = task
            root_task.subtask_ids.append(task_id)

            # Create dependency on previous task
            if previous_task_id:
                dependency = TaskDependency(
                    source_task_id=previous_task_id,
                    target_task_id=task_id,
                    dependency_type=DependencyType.SEQUENTIAL,
                )
                htn.task_dependencies.append(dependency)
                task.dependencies.append(previous_task_id)
                htn.sequential_task_order.append(task_id)

            previous_task_id = task_id
            effort_idx += 1

        # Update HTN metadata
        htn.total_tasks = len(htn.all_tasks)
        htn.atomic_tasks_count = sum(
            1 for t in htn.all_tasks.values() if t.task_type == TaskType.ATOMIC
        )
        htn.compound_tasks_count = sum(
            1 for t in htn.all_tasks.values() if t.task_type == TaskType.COMPOUND
        )
        htn.max_depth = self._calculate_htn_depth(htn)
        htn.decomposition_strategy = strategy.value

        # Validate HTN
        validation_errors = self._validate_htn(htn)
        if validation_errors:
            logger.warning(
                "HTN validation issues",
                extra={"strategy": strategy.value, "issues": validation_errors},
            )

        return htn

    def _generate_phases(self, goal: str) -> List[str]:
        """Generate decomposition phases based on goal."""
        goal_lower = goal.lower()

        if any(w in goal_lower for w in ["build", "create", "develop", "make"]):
            return [
                "Research & Requirements",
                "Design & Architecture",
                "Implementation",
                "Testing & Validation",
                "Launch & Monitor",
            ]
        elif any(w in goal_lower for w in ["learn", "study", "understand", "master"]):
            return [
                "Assess Current Knowledge",
                "Gather Learning Resources",
                "Structured Study",
                "Practice & Apply",
                "Review & Consolidate",
            ]
        elif any(w in goal_lower for w in ["improve", "optimize", "enhance", "fix"]):
            return [
                "Diagnose Current State",
                "Identify Improvement Areas",
                "Design Solutions",
                "Implement Changes",
                "Measure Results",
            ]
        elif any(w in goal_lower for w in ["plan", "organize", "schedule", "manage"]):
            return [
                "Define Scope & Objectives",
                "Break Down into Tasks",
                "Prioritize & Schedule",
                "Execute",
                "Review & Adjust",
            ]
        else:
            return [
                "Define Clear Objectives",
                "Research & Gather Information",
                "Develop Strategy",
                "Execute Plan",
                "Evaluate Outcomes",
            ]

    async def generate_alternative_plans(
        self,
        goal: str,
        goal_description: str,
        constraints: List[GoalConstraint],
        max_alternatives: int = 3,
    ) -> List[HierarchicalTaskNetwork]:
        """Generate multiple alternative decomposition plans."""
        alternatives = []
        strategies = [s for s in DecompositionStrategy if s in self.strategy_templates]

        for strategy in strategies[:max_alternatives]:
            try:
                htn = await self._decompose_with_strategy(
                    goal=goal,
                    goal_description=goal_description,
                    constraints=constraints,
                    timeframe=None,
                    strategy=strategy,
                )
                alternatives.append(htn)
            except Exception as e:
                logger.debug(
                    "Alternative plan generation failed",
                    extra={"strategy": strategy.value, "error": str(e)},
                )

        return alternatives

    async def select_optimal_plan(
        self,
        plans: List[HierarchicalTaskNetwork],
        criteria: Optional[Dict[str, Any]] = None,
    ) -> HierarchicalTaskNetwork:
        """
        Select optimal plan from alternatives using scoring.

        Args:
            plans: List of alternative plans
            criteria: Selection criteria with weights

        Returns:
            Selected optimal plan
        """
        if not plans:
            raise ValueError("No plans to select from")
        if len(plans) == 1:
            return plans[0]

        criteria = criteria or {
            "task_count": 0.3,      # Prefer fewer tasks
            "total_effort": 0.3,    # Prefer less effort
            "parallelizability": 0.2,
            "simplicity": 0.2,
        }

        scores = []
        for plan in plans:
            score = self._score_plan(plan, criteria)
            scores.append((score, plan))

        scores.sort(key=lambda x: x[0], reverse=True)
        selected = scores[0][1]

        logger.info(
            "Optimal plan selected",
            extra={
                "selected_score": round(scores[0][0], 3),
                "total_plans": len(plans),
            },
        )
        return selected

    def _score_plan(
        self,
        plan: HierarchicalTaskNetwork,
        criteria: Dict[str, float],
    ) -> float:
        """Score a plan based on criteria."""
        score = 0.0

        # Task count score (fewer is better)
        if "task_count" in criteria:
            task_ratio = max(0.0, 1.0 - (plan.total_tasks / 20.0))
            score += criteria["task_count"] * task_ratio

        # Total effort score (less is better)
        if "total_effort" in criteria:
            total_effort = sum(
                self.effort_weights.get(t.estimated_effort, 2)
                for t in plan.all_tasks.values()
            )
            effort_ratio = max(0.0, 1.0 - (total_effort / 50.0))
            score += criteria["total_effort"] * effort_ratio

        # Parallelizability score (more is better)
        if "parallelizability" in criteria:
            parallel_ratio = len(plan.parallel_task_groups) / max(1, plan.total_tasks)
            score += criteria["parallelizability"] * parallel_ratio

        # Simplicity score (based on depth and branch factor)
        if "simplicity" in criteria:
            depth_penalty = max(0.0, 1.0 - (plan.max_depth / 5.0))
            score += criteria["simplicity"] * depth_penalty

        return score

    async def refine_decomposition(
        self,
        htn: HierarchicalTaskNetwork,
        focus_task_id: str,
        further_decomposition: int = 1,
    ) -> HierarchicalTaskNetwork:
        """
        Further decompose a specific task in the HTN.

        Args:
            htn: Current HTN
            focus_task_id: Task to further decompose
            further_decomposition: Decomposition levels

        Returns:
            Updated HTN with refined decomposition
        """
        if focus_task_id not in htn.all_tasks:
            raise ValueError(f"Task {focus_task_id} not found in HTN")

        focus_task = htn.all_tasks[focus_task_id]

        # Convert atomic task to compound if needed
        if focus_task.task_type == TaskType.ATOMIC and further_decomposition > 0:
            focus_task.task_type = TaskType.COMPOUND

            # Create subtasks
            base_effort = self.effort_weights.get(focus_task.estimated_effort, 2)
            subtasks_needed = max(2, base_effort // 2)

            for i in range(subtasks_needed):
                sub_task_id = f"task-{uuid.uuid4().hex[:8]}"
                sub_task = DecomposedTask(
                    task_id=sub_task_id,
                    parent_task_id=focus_task_id,
                    task_title=f"{focus_task.task_title} - Part {i+1}",
                    task_description=f"Subtask {i+1} of {focus_task.task_title}",
                    task_type=TaskType.ATOMIC,
                    status=TaskStatus.PENDING,
                    order_in_plan=focus_task.order_in_plan + (i * 0.1),
                    estimated_effort="medium" if base_effort > 1 else "low",
                )
                htn.all_tasks[sub_task_id] = sub_task
                focus_task.subtask_ids.append(sub_task_id)

                # Add dependency from previous subtask
                if i > 0:
                    prev_sub_id = f"task-{htn.all_tasks[focus_task.subtask_ids[-2]].task_id}"
                    dep = TaskDependency(
                        source_task_id=prev_sub_id,
                        target_task_id=sub_task_id,
                        dependency_type=DependencyType.SEQUENTIAL,
                    )
                    htn.task_dependencies.append(dep)

        htn.total_tasks = len(htn.all_tasks)
        htn.max_depth = self._calculate_htn_depth(htn)
        return htn

    def _calculate_htn_depth(self, htn: HierarchicalTaskNetwork) -> int:
        """Calculate maximum depth of HTN."""
        def calc_depth(task_id: str) -> int:
            task = htn.all_tasks.get(task_id)
            if not task or not task.subtask_ids:
                return 0
            return 1 + max((calc_depth(sub_id) for sub_id in task.subtask_ids), default=0)

        return calc_depth(htn.root_task_id)

    def _validate_htn(self, htn: HierarchicalTaskNetwork) -> List[str]:
        """Validate HTN structure."""
        errors = []

        # Check for cycles
        if self._has_cycles(htn):
            errors.append("Dependency cycle detected")

        # Check root task exists
        if htn.root_task_id not in htn.all_tasks:
            errors.append("Root task not found")

        # Check all dependencies are valid
        for dep in htn.task_dependencies:
            if dep.source_task_id not in htn.all_tasks:
                errors.append(f"Invalid dependency source: {dep.source_task_id}")
            if dep.target_task_id not in htn.all_tasks:
                errors.append(f"Invalid dependency target: {dep.target_task_id}")

        return errors

    def _has_cycles(self, htn: HierarchicalTaskNetwork) -> bool:
        """Check if HTN has dependency cycles."""
        visited = set()
        rec_stack = set()

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

    async def get_stats(self) -> Dict[str, Any]:
        """Get decomposer statistics."""
        return {
            "version": self.version,
            "max_decomposition_depth": self.max_decomposition_depth,
            "max_tasks_per_plan": self.max_tasks_per_plan,
            "parallel_task_limit": self.parallel_task_limit,
            "strategies": [s.value for s in DecompositionStrategy],
        }
