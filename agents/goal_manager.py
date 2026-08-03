"""
Goal Manager for Phase 6 Production Planning Engine

Manages:
- Goal creation and lifecycle
- Goal hierarchy (parent/child relationships)
- Goal dependencies
- Goal progress tracking
- Goal prioritization
- Goal archival

Production-grade goal management integrated with planning engine.
Supports multi-level goal hierarchies with dependency tracking.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from planning_models import (
    GoalNode,
    Goal,
    GoalStatus,
    GoalPriority,
    GoalCategory,
    GoalConstraint,
)

logger = logging.getLogger(__name__)


class GoalManager:
    """Production goal management system."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize goal manager."""
        self.config = config or {}
        self.goals: Dict[str, Goal] = {}  # goal_id -> Goal
        self.goal_nodes: Dict[str, GoalNode] = {}  # node_id -> GoalNode
        self.goal_hierarchy: Dict[str, List[str]] = {}  # parent_id -> [child_ids]
        self.goal_dependencies: Dict[str, List[str]] = {}  # goal_id -> [dependent_goal_ids]
        self.max_hierarchy_depth: int = self.config.get("max_goal_hierarchy_depth", 5)
        self.version = "1.0.0"
        logger.info("GoalManager initialized", extra={"version": self.version})

    async def create_goal(
        self,
        goal_title: str,
        goal_description: str = "",
        category: GoalCategory = GoalCategory.EXECUTION,
        priority: GoalPriority = GoalPriority.MEDIUM,
        parent_goal_id: Optional[str] = None,
        deadline: Optional[str] = None,
        owner: str = "system",
        success_criteria: Optional[List[str]] = None,
        constraints: Optional[List[GoalConstraint]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Goal:
        """
        Create a new goal, optionally as a child of another goal.

        Args:
            goal_title: Goal title
            goal_description: Goal description
            category: Goal category
            priority: Goal priority
            parent_goal_id: Parent goal ID (None for root goals)
            deadline: Goal deadline (ISO string)
            owner: Goal owner
            success_criteria: List of success criteria
            constraints: List of constraints
            metadata: Additional metadata

        Returns:
            Created Goal object

        Raises:
            ValueError: If parent goal not found or hierarchy too deep
        """
        goal_id = str(uuid.uuid4())
        success_criteria = success_criteria or []
        constraints = constraints or []
        metadata = metadata or {}

        # Validate parent hierarchy
        if parent_goal_id:
            parent_node = self.goal_nodes.get(parent_goal_id)
            if not parent_node:
                raise ValueError(f"Parent goal {parent_goal_id} not found")
            depth = self._calculate_node_depth(parent_goal_id) + 1
            if depth > self.max_hierarchy_depth:
                raise ValueError(f"Goal hierarchy exceeds maximum depth {self.max_hierarchy_depth}")

        # Create root node
        root_node = GoalNode(
            goal_id=goal_id,
            parent_goal_id=parent_goal_id,
            goal_title=goal_title,
            goal_description=goal_description,
            goal_category=category,
            priority=priority,
            deadline=deadline,
            owner=owner,
            success_criteria=success_criteria,
            constraints=constraints,
            metadata=metadata,
        )

        # Create Goal object
        goal = Goal(goal_id=goal_id, root_node=root_node)
        goal.all_nodes[goal_id] = root_node

        # Store in registry
        self.goal_nodes[goal_id] = root_node
        self.goals[goal_id] = goal
        self.goal_dependencies[goal_id] = []

        # Update hierarchy
        if parent_goal_id:
            if parent_goal_id not in self.goal_hierarchy:
                self.goal_hierarchy[parent_goal_id] = []
            self.goal_hierarchy[parent_goal_id].append(goal_id)
            parent_node.child_goal_ids.append(goal_id)

        logger.info(
            "Goal created",
            extra={
                "goal_id": goal_id,
                "title": goal_title,
                "parent_id": parent_goal_id,
                "priority": priority.value if priority else None,
            },
        )
        return goal

    async def add_child_goal(
        self,
        parent_goal_id: str,
        child_goal_title: str,
        child_goal_description: str = "",
        priority: GoalPriority = GoalPriority.MEDIUM,
        **kwargs,
    ) -> Goal:
        """
        Add a child goal to an existing goal.

        Args:
            parent_goal_id: Parent goal ID
            child_goal_title: Child goal title
            child_goal_description: Child goal description
            priority: Child goal priority
            **kwargs: Additional arguments to create_goal

        Returns:
            Created child Goal

        Raises:
            ValueError: If parent not found or depth exceeded
        """
        return await self.create_goal(
            goal_title=child_goal_title,
            goal_description=child_goal_description,
            priority=priority,
            parent_goal_id=parent_goal_id,
            **kwargs,
        )

    async def add_goal_dependency(
        self,
        source_goal_id: str,
        target_goal_id: str,
        dependency_type: str = "sequential",
    ) -> None:
        """
        Add a dependency between goals.

        Args:
            source_goal_id: Source goal (must complete first)
            target_goal_id: Target goal (depends on source)
            dependency_type: Type of dependency

        Raises:
            ValueError: If goals not found or cycle would be created
        """
        if source_goal_id not in self.goals:
            raise ValueError(f"Source goal {source_goal_id} not found")
        if target_goal_id not in self.goals:
            raise ValueError(f"Target goal {target_goal_id} not found")

        # Check for cycles
        if self._would_create_cycle(source_goal_id, target_goal_id):
            raise ValueError(f"Dependency would create cycle: {source_goal_id} -> {target_goal_id}")

        # Add dependency
        if target_goal_id not in self.goal_dependencies:
            self.goal_dependencies[target_goal_id] = []
        if source_goal_id not in self.goal_dependencies[target_goal_id]:
            self.goal_dependencies[target_goal_id].append(source_goal_id)

        # Add to goal node
        target_node = self.goal_nodes[target_goal_id]
        if source_goal_id not in target_node.dependencies:
            target_node.dependencies.append(source_goal_id)

        logger.info(
            "Goal dependency added",
            extra={
                "source_goal_id": source_goal_id,
                "target_goal_id": target_goal_id,
                "type": dependency_type,
            },
        )

    async def add_constraint(
        self,
        goal_id: str,
        constraint_name: str,
        constraint_description: str,
        constraint_type: str = "general",
        severity: str = "medium",
        value: Any = None,
    ) -> GoalConstraint:
        """
        Add a constraint to a goal.

        Args:
            goal_id: Goal ID
            constraint_name: Constraint name
            constraint_description: Constraint description
            constraint_type: Type of constraint
            severity: Severity level
            value: Constraint value

        Returns:
            Created constraint

        Raises:
            ValueError: If goal not found
        """
        if goal_id not in self.goal_nodes:
            raise ValueError(f"Goal {goal_id} not found")

        constraint = GoalConstraint(
            name=constraint_name,
            description=constraint_description,
            constraint_type=constraint_type,
            severity=severity,
            value=value,
        )

        goal_node = self.goal_nodes[goal_id]
        goal_node.constraints.append(constraint)

        logger.info(
            "Constraint added to goal",
            extra={
                "goal_id": goal_id,
                "constraint_name": constraint_name,
                "severity": severity,
            },
        )
        return constraint

    async def update_goal_status(
        self,
        goal_id: str,
        new_status: GoalStatus,
        progress: float = 0.0,
    ) -> GoalNode:
        """
        Update goal status and progress.

        Args:
            goal_id: Goal ID
            new_status: New status
            progress: Progress percentage (0-1)

        Returns:
            Updated goal node

        Raises:
            ValueError: If goal not found
        """
        if goal_id not in self.goal_nodes:
            raise ValueError(f"Goal {goal_id} not found")

        goal_node = self.goal_nodes[goal_id]
        old_status = goal_node.status
        goal_node.status = new_status
        goal_node.progress = max(0.0, min(1.0, progress))
        goal_node.updated_at = datetime.utcnow().isoformat()

        logger.info(
            "Goal status updated",
            extra={
                "goal_id": goal_id,
                "old_status": old_status.value,
                "new_status": new_status.value,
                "progress": goal_node.progress,
            },
        )
        return goal_node

    async def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Get goal by ID."""
        return self.goals.get(goal_id)

    async def get_goal_node(self, goal_id: str) -> Optional[GoalNode]:
        """Get goal node by ID."""
        return self.goal_nodes.get(goal_id)

    async def get_child_goals(self, goal_id: str) -> List[GoalNode]:
        """Get all child goals of a goal."""
        child_ids = self.goal_hierarchy.get(goal_id, [])
        return [self.goal_nodes[cid] for cid in child_ids if cid in self.goal_nodes]

    async def get_goal_dependencies(self, goal_id: str) -> List[GoalNode]:
        """Get all goals that this goal depends on."""
        dep_ids = self.goal_dependencies.get(goal_id, [])
        return [self.goal_nodes[did] for did in dep_ids if did in self.goal_nodes]

    async def get_goal_tree(self, root_goal_id: str, max_depth: int = 10) -> Dict[str, Any]:
        """
        Get full goal tree rooted at a goal.

        Args:
            root_goal_id: Root goal ID
            max_depth: Maximum depth to traverse

        Returns:
            Goal tree dictionary
        """
        if root_goal_id not in self.goal_nodes:
            return {}

        def build_tree(goal_id: str, depth: int) -> Dict[str, Any]:
            if depth > max_depth:
                return {}
            node = self.goal_nodes[goal_id]
            children = [build_tree(cid, depth + 1) for cid in node.child_goal_ids]
            return {
                "goal_id": goal_id,
                "title": node.goal_title,
                "status": node.status.value,
                "progress": node.progress,
                "children": children,
            }

        return build_tree(root_goal_id, 0)

    async def calculate_goal_tree_stats(self, root_goal_id: str) -> Dict[str, Any]:
        """
        Calculate statistics for goal tree.

        Args:
            root_goal_id: Root goal ID

        Returns:
            Stats dictionary with depth, width, total nodes
        """
        if root_goal_id not in self.goals:
            return {}

        def traverse(goal_id: str) -> Tuple[int, int, int]:  # (max_depth, width, count)
            node = self.goal_nodes[goal_id]
            if not node.child_goal_ids:
                return (0, 1, 1)
            child_depths = []
            for cid in node.child_goal_ids:
                d, w, c = traverse(cid)
                child_depths.append((d + 1, w, c))
            max_depth = max(d for d, w, c in child_depths) if child_depths else 0
            total_width = sum(w for d, w, c in child_depths)
            total_count = sum(c for d, w, c in child_depths) + 1
            return (max_depth, total_width, total_count)

        max_depth, width, total = traverse(root_goal_id)
        goal = self.goals[root_goal_id]
        goal.goal_tree_depth = max_depth
        goal.goal_tree_width = width
        goal.total_child_goals = total - 1

        return {
            "max_depth": max_depth,
            "width": width,
            "total_goals": total,
            "leaf_goals": sum(
                1 for node in self.goal_nodes.values() if not node.child_goal_ids
            ),
        }

    async def archive_goal(self, goal_id: str) -> GoalNode:
        """Archive a completed or cancelled goal."""
        if goal_id not in self.goal_nodes:
            raise ValueError(f"Goal {goal_id} not found")

        goal_node = self.goal_nodes[goal_id]
        goal_node.status = GoalStatus.ARCHIVED
        goal_node.updated_at = datetime.utcnow().isoformat()

        logger.info("Goal archived", extra={"goal_id": goal_id})
        return goal_node

    async def list_active_goals(self) -> List[GoalNode]:
        """Get all active goals."""
        return [n for n in self.goal_nodes.values() if n.status == GoalStatus.ACTIVE]

    async def get_goal_priority_order(self) -> List[GoalNode]:
        """Get goals sorted by priority."""
        nodes = [n for n in self.goal_nodes.values() if n.status != GoalStatus.ARCHIVED]
        return sorted(nodes, key=lambda n: (n.priority.value if n.priority else 999), reverse=True)

    def _calculate_node_depth(self, goal_id: str) -> int:
        """Calculate depth of node in hierarchy."""
        if goal_id not in self.goal_nodes:
            return 0
        node = self.goal_nodes[goal_id]
        if not node.parent_goal_id:
            return 0
        return 1 + self._calculate_node_depth(node.parent_goal_id)

    def _would_create_cycle(self, source_id: str, target_id: str) -> bool:
        """Check if adding dependency would create cycle."""
        if source_id == target_id:
            return True
        visited = set()
        to_visit = [target_id]
        while to_visit:
            current = to_visit.pop(0)
            if current == source_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            deps = self.goal_dependencies.get(current, [])
            to_visit.extend(deps)
        return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get goal manager statistics."""
        return {
            "total_goals": len(self.goals),
            "total_nodes": len(self.goal_nodes),
            "active_goals": sum(
                1 for n in self.goal_nodes.values() if n.status == GoalStatus.ACTIVE
            ),
            "completed_goals": sum(
                1 for n in self.goal_nodes.values() if n.status == GoalStatus.COMPLETED
            ),
            "archived_goals": sum(
                1 for n in self.goal_nodes.values() if n.status == GoalStatus.ARCHIVED
            ),
            "total_dependencies": sum(len(v) for v in self.goal_dependencies.values()),
            "max_hierarchy_depth": max(
                self._calculate_node_depth(gid) for gid in self.goal_nodes.keys()
            ) if self.goal_nodes else 0,
        }
