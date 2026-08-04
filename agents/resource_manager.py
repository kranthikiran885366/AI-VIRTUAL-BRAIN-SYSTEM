"""
Resource Manager for Phase 6 Planning Engine

Implements:
- Resource registry and inventory
- Resource allocation and tracking
- Conflict detection
- Resource utilization optimization
- Future provider integration support
- Constraint-aware allocation

Production-grade resource management integrated with planning system.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set

try:
    from agents.planning_models import (
        ResourceRequirement,
        ResourceAllocation,
        ResourceProfile,
        DecomposedTask,
    )
except ImportError:
    from planning_models import (  # type: ignore[no-redef]
        ResourceRequirement,
        ResourceAllocation,
        ResourceProfile,
        DecomposedTask,
    )

logger = logging.getLogger(__name__)


class ResourceRegistry:
    """Central registry of available resources."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize resource registry."""
        self.config = config or {}
        self.version = "1.0.0"
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.resource_categories: Dict[str, List[str]] = {}
        self.enable_future_providers = self.config.get("enable_future_providers", False)
        logger.info("ResourceRegistry initialized", extra={"version": self.version})

    async def register_resource(
        self,
        resource_name: str,
        resource_type: str = "skill",
        available_amount: float = 1.0,
        unit: str = "units",
        renewable: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Register a resource in the registry.

        Args:
            resource_name: Resource name
            resource_type: Type (skill, tool, time, budget, etc.)
            available_amount: Available quantity
            unit: Unit of measurement
            renewable: Whether resource is renewable
            metadata: Additional metadata

        Returns:
            Registered resource record
        """
        resource_id = str(uuid.uuid4())
        metadata = metadata or {}

        resource = {
            "resource_id": resource_id,
            "resource_name": resource_name,
            "resource_type": resource_type,
            "available_amount": available_amount,
            "allocated_amount": 0.0,
            "unit": unit,
            "renewable": renewable,
            "registered_at": datetime.utcnow().isoformat(),
            "metadata": metadata,
        }

        self.resources[resource_id] = resource

        # Organize by category
        if resource_type not in self.resource_categories:
            self.resource_categories[resource_type] = []
        self.resource_categories[resource_type].append(resource_id)

        logger.info(
            "Resource registered",
            extra={
                "resource_id": resource_id,
                "name": resource_name,
                "type": resource_type,
                "available": available_amount,
            },
        )
        return resource

    async def get_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """Get resource by ID."""
        return self.resources.get(resource_id)

    async def get_resources_by_type(self, resource_type: str) -> List[Dict[str, Any]]:
        """Get all resources of a specific type."""
        resource_ids = self.resource_categories.get(resource_type, [])
        return [self.resources[rid] for rid in resource_ids if rid in self.resources]

    async def get_available_resources(self) -> List[Dict[str, Any]]:
        """Get all resources with available capacity."""
        available = []
        for resource in self.resources.values():
            free = resource["available_amount"] - resource["allocated_amount"]
            if free > 0:
                available.append({**resource, "free_amount": free})
        return available

    async def update_resource_availability(
        self,
        resource_id: str,
        available_amount: float,
    ) -> Dict[str, Any]:
        """
        Update resource availability.

        Args:
            resource_id: Resource ID
            available_amount: New available amount

        Returns:
            Updated resource

        Raises:
            ValueError: If resource not found
        """
        if resource_id not in self.resources:
            raise ValueError(f"Resource {resource_id} not found")

        resource = self.resources[resource_id]
        old_amount = resource["available_amount"]
        resource["available_amount"] = available_amount

        logger.info(
            "Resource availability updated",
            extra={
                "resource_id": resource_id,
                "old_amount": old_amount,
                "new_amount": available_amount,
            },
        )
        return resource

    async def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_resources = len(self.resources)
        total_available = sum(r["available_amount"] for r in self.resources.values())
        total_allocated = sum(r["allocated_amount"] for r in self.resources.values())

        return {
            "total_resources": total_resources,
            "total_available": total_available,
            "total_allocated": total_allocated,
            "utilization_rate": (
                total_allocated / total_available if total_available > 0 else 0.0
            ),
            "resource_types": list(self.resource_categories.keys()),
        }


class ResourceAllocator:
    """Allocate resources to tasks."""

    def __init__(self, registry: ResourceRegistry, config: Optional[Dict[str, Any]] = None):
        """Initialize resource allocator."""
        self.config = config or {}
        self.registry = registry
        self.version = "1.0.0"
        self.allocations: Dict[str, List[ResourceAllocation]] = {}
        self.allocation_history: List[Dict[str, Any]] = []
        self.max_allocation_attempts = self.config.get("max_allocation_attempts", 3)
        self.greedy_allocation = self.config.get("greedy_allocation", True)
        logger.info("ResourceAllocator initialized", extra={"version": self.version})

    async def allocate_resource(
        self,
        task_id: str,
        resource_requirement: ResourceRequirement,
        preferred_resource_id: Optional[str] = None,
    ) -> Optional[ResourceAllocation]:
        """
        Allocate a resource to a task.

        Args:
            task_id: Task ID
            resource_requirement: Resource requirement
            preferred_resource_id: Preferred resource (if any)

        Returns:
            Allocation record or None if allocation failed
        """
        # Try preferred resource first
        if preferred_resource_id:
            resource = await self.registry.get_resource(preferred_resource_id)
            if resource:
                allocation = await self._try_allocate(task_id, resource, resource_requirement)
                if allocation:
                    return allocation

        # Find available resource of required type
        available = await self.registry.get_resources_by_type(resource_requirement.resource_type)
        for resource in available:
            allocation = await self._try_allocate(task_id, resource, resource_requirement)
            if allocation:
                return allocation

        # Allocation failed
        logger.warning(
            "Resource allocation failed",
            extra={
                "task_id": task_id,
                "resource_type": resource_requirement.resource_type,
                "required_amount": resource_requirement.required_amount,
            },
        )
        return None

    async def _try_allocate(
        self,
        task_id: str,
        resource: Dict[str, Any],
        requirement: ResourceRequirement,
    ) -> Optional[ResourceAllocation]:
        """Try to allocate specific resource."""
        available = (
            resource["available_amount"] - resource["allocated_amount"]
        )

        if available >= requirement.required_amount:
            # Perform allocation
            resource["allocated_amount"] += requirement.required_amount

            allocation = ResourceAllocation(
                task_id=task_id,
                resource_name=resource["resource_name"],
                allocated_amount=requirement.required_amount,
                allocation_start=datetime.utcnow().isoformat(),
                is_active=True,
            )

            if task_id not in self.allocations:
                self.allocations[task_id] = []
            self.allocations[task_id].append(allocation)

            logger.info(
                "Resource allocated",
                extra={
                    "task_id": task_id,
                    "resource_name": resource["resource_name"],
                    "amount": requirement.required_amount,
                },
            )
            return allocation

        return None

    async def deallocate_resource(
        self,
        allocation_id: str,
    ) -> bool:
        """
        Deallocate a resource.

        Args:
            allocation_id: Allocation ID

        Returns:
            Whether deallocation succeeded
        """
        for task_allocations in self.allocations.values():
            for allocation in task_allocations:
                if allocation.allocation_id == allocation_id:
                    allocation.is_active = False
                    allocation.allocation_end = datetime.utcnow().isoformat()

                    logger.info(
                        "Resource deallocated",
                        extra={
                            "allocation_id": allocation_id,
                            "resource": allocation.resource_name,
                        },
                    )
                    return True

        return False

    async def get_task_allocations(self, task_id: str) -> List[ResourceAllocation]:
        """Get all allocations for a task."""
        return self.allocations.get(task_id, [])

    async def check_allocation_conflicts(
        self,
        allocations: List[ResourceAllocation],
    ) -> List[Dict[str, Any]]:
        """
        Check for resource conflicts in allocations.

        Args:
            allocations: List of allocations to check

        Returns:
            List of conflicts found
        """
        conflicts = []

        # Group by resource
        resource_allocs: Dict[str, List[ResourceAllocation]] = {}
        for alloc in allocations:
            if alloc.resource_name not in resource_allocs:
                resource_allocs[alloc.resource_name] = []
            resource_allocs[alloc.resource_name].append(alloc)

        # Check for overallocation
        for resource_name, allocs in resource_allocs.items():
            total_allocated = sum(a.allocated_amount for a in allocs if a.is_active)
            resource_records = await self.registry.get_resources_by_type("skill")
            matching = [r for r in resource_records if r["resource_name"] == resource_name]

            if matching:
                resource = matching[0]
                if total_allocated > resource["available_amount"]:
                    conflicts.append({
                        "type": "overallocation",
                        "resource_name": resource_name,
                        "requested": total_allocated,
                        "available": resource["available_amount"],
                    })

        return conflicts

    async def optimize_allocation(
        self,
        tasks: List[DecomposedTask],
        requirements: List[ResourceRequirement],
    ) -> Dict[str, List[ResourceAllocation]]:
        """
        Optimize resource allocation across multiple tasks.

        Args:
            tasks: Tasks to allocate resources to
            requirements: Resource requirements

        Returns:
            Optimized allocations by task
        """
        allocations = {}

        # Simple greedy allocation: prioritize by task priority
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)

        for task in sorted_tasks:
            task_reqs = [r for r in requirements if task.task_id in [task.task_id]]
            allocations[task.task_id] = []

            for req in task_reqs:
                allocation = await self.allocate_resource(task.task_id, req)
                if allocation:
                    allocations[task.task_id].append(allocation)

        logger.info(
            "Allocation optimization complete",
            extra={
                "total_tasks": len(tasks),
                "total_requirements": len(requirements),
            },
        )
        return allocations

    async def get_stats(self) -> Dict[str, Any]:
        """Get allocator statistics."""
        total_allocs = sum(len(allocs) for allocs in self.allocations.values())
        active_allocs = sum(
            1 for allocs in self.allocations.values()
            for alloc in allocs if alloc.is_active
        )

        return {
            "version": self.version,
            "total_allocations": total_allocs,
            "active_allocations": active_allocs,
            "tasks_with_allocations": len(self.allocations),
        }


class ResourcePlanner:
    """Plan resource requirements for plans."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize resource planner."""
        self.config = config or {}
        self.version = "1.0.0"
        self.default_skills = self.config.get(
            "default_skills",
            ["project_management", "communication", "problem_solving"]
        )
        self.skill_effort_mapping = self.config.get(
            "skill_effort_mapping",
            {
                "low": ["communication", "planning"],
                "medium": ["implementation", "testing", "documentation"],
                "high": ["architecture", "optimization", "leadership"],
            }
        )
        logger.info("ResourcePlanner initialized", extra={"version": self.version})

    async def estimate_resource_requirements(
        self,
        goal: str,
        tasks: List[DecomposedTask],
        constraints: Optional[List[str]] = None,
    ) -> ResourceProfile:
        """
        Estimate resource requirements for a plan.

        Args:
            goal: Goal description
            tasks: Tasks in the plan
            constraints: Constraints on execution

        Returns:
            Resource profile with estimates
        """
        constraints = constraints or []

        # Calculate effort
        total_effort = sum(
            self._effort_to_hours(t.estimated_effort) for t in tasks
        )

        # Estimate team size
        team_size = max(1, int(total_effort / 160))  # ~160 hours/person/month

        # Identify required skills
        required_skills = await self._extract_required_skills(goal, tasks)

        # Create resource profile
        profile = ResourceProfile(
            profile_name="estimated",
            estimated_total_effort=f"{total_effort} hours",
            recommended_team_size=team_size,
            key_skills_needed=required_skills,
            resource_confidence=0.7,
        )

        # Add resource requirements
        for skill in required_skills:
            req = ResourceRequirement(
                resource_name=skill,
                resource_type="skill",
                required_amount=1.0,
                priority=2,
            )
            profile.required_resources.append(req)

        logger.info(
            "Resource requirements estimated",
            extra={
                "total_effort_hours": total_effort,
                "team_size": team_size,
                "required_skills": len(required_skills),
            },
        )
        return profile

    async def _extract_required_skills(
        self,
        goal: str,
        tasks: List[DecomposedTask],
    ) -> List[str]:
        """Extract required skills from goal and tasks."""
        skills = set(self.default_skills)
        goal_lower = goal.lower()

        # Analyze goal for skill hints
        if any(w in goal_lower for w in ["code", "develop", "build", "implement"]):
            skills.update(["software_development", "testing", "debugging"])
        if any(w in goal_lower for w in ["design", "architecture"]):
            skills.update(["system_design", "architecture"])
        if any(w in goal_lower for w in ["manage", "organize", "lead"]):
            skills.update(["project_management", "leadership"])
        if any(w in goal_lower for w in ["learn", "research"]):
            skills.update(["research", "learning"])
        if any(w in goal_lower for w in ["optimize", "improve"]):
            skills.update(["analysis", "optimization"])

        # Analyze task titles
        for task in tasks:
            title_lower = task.task_title.lower()
            for effort, effort_skills in self.skill_effort_mapping.items():
                if task.estimated_effort == effort:
                    skills.update(effort_skills)

        return sorted(list(skills))

    def _effort_to_hours(self, effort: str) -> float:
        """Convert effort level to estimated hours."""
        mapping = {
            "low": 8,
            "medium": 16,
            "high": 40,
            "critical": 80,
        }
        return mapping.get(effort, 16)

    async def validate_resource_availability(
        self,
        profile: ResourceProfile,
        registry: ResourceRegistry,
    ) -> Tuple[bool, List[str]]:
        """
        Validate that required resources are available.

        Args:
            profile: Resource profile
            registry: Resource registry

        Returns:
            (Is valid, List of missing resources)
        """
        missing = []

        for req in profile.required_resources:
            available = await registry.get_resources_by_type(req.resource_type)
            found = any(r["resource_name"] == req.resource_name for r in available)
            if not found:
                missing.append(req.resource_name)

        is_valid = len(missing) == 0
        logger.info(
            "Resource availability validated",
            extra={
                "valid": is_valid,
                "missing_count": len(missing),
            },
        )
        return is_valid, missing

    async def get_stats(self) -> Dict[str, Any]:
        """Get planner statistics."""
        return {
            "version": self.version,
            "default_skills": len(self.default_skills),
            "effort_levels": list(self.skill_effort_mapping.keys()),
        }


# ── Sync-compatible ResourceManager facade (test API) ────────────────────

class ResourceManager:
    """Sync-compatible resource manager for tests."""

    def __init__(self, config=None):
        self._registry = ResourceRegistry(config)
        self._resources: Dict[str, Dict[str, Any]] = {}

    def register_resource(self, name: str, resource_type: str = "skill",
                          capacity: float = 40.0) -> None:
        self._resources[name] = {"name": name, "type": resource_type,
                                  "capacity": capacity, "allocated": 0.0}

    def get_available_resources(self) -> List[Dict[str, Any]]:
        return list(self._resources.values())

    def check_availability(self, name: str, hours: float) -> bool:
        r = self._resources.get(name)
        if r is None:
            return False
        return (r["capacity"] - r["allocated"]) >= hours
