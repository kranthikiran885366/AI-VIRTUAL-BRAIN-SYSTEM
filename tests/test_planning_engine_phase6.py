"""
Phase 6 Production Planning Engine - Comprehensive Test Suite
Tests for planning models, goal management, task decomposition, validation, and integration
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.planning_models import (
    Goal, Task, Plan, PlanContext, Constraint, Risk,
    GoalStatus, TaskStatus, PlanStatus, RiskSeverity, ConstraintType
)
from agents.goal_manager import GoalManager
from agents.task_decomposer import TaskDecomposer, DecompositionStrategy
from agents.plan_validator import PlanValidator
from agents.planning_session import PlanningSession
from agents.resource_manager import ResourceManager
from agents.dynamic_replanner import DynamicReplanner
from agents.execution_monitor import ExecutionMonitor


# ============================================================================
# FIXTURE SETUP
# ============================================================================

@pytest.fixture
def goal_manager():
    """Create a goal manager instance for testing"""
    return GoalManager()


@pytest.fixture
def task_decomposer():
    """Create a task decomposer instance for testing"""
    return TaskDecomposer()


@pytest.fixture
def plan_validator():
    """Create a plan validator instance for testing"""
    return PlanValidator()


@pytest.fixture
def planning_session():
    """Create a planning session instance for testing"""
    return PlanningSession()


@pytest.fixture
def resource_manager():
    """Create a resource manager instance for testing"""
    return ResourceManager()


@pytest.fixture
def dynamic_replanner():
    """Create a dynamic replanner instance for testing"""
    return DynamicReplanner()


@pytest.fixture
def execution_monitor():
    """Create an execution monitor instance for testing"""
    return ExecutionMonitor()


@pytest.fixture
def sample_goals():
    """Create sample goals for testing"""
    return [
        Goal(
            id="goal_1",
            title="Complete Q3 Project",
            description="Deliver Q3 milestone project",
            priority=9,
            status=GoalStatus.ACTIVE,
            target_date=datetime.now() + timedelta(days=90)
        ),
        Goal(
            id="goal_2",
            title="Improve Code Quality",
            description="Refactor legacy code",
            priority=7,
            status=GoalStatus.ACTIVE,
            target_date=datetime.now() + timedelta(days=60)
        ),
        Goal(
            id="goal_3",
            title="Team Training",
            description="Complete training program",
            priority=6,
            status=GoalStatus.PENDING,
            target_date=datetime.now() + timedelta(days=45)
        ),
    ]


@pytest.fixture
def sample_plan():
    """Create a sample plan for testing"""
    return Plan(
        id="plan_1",
        title="Q3 Execution Plan",
        description="Complete quarterly execution strategy",
        goals=["goal_1"],
        status=PlanStatus.DRAFT,
        created_at=datetime.now(),
        tasks=[]
    )


# ============================================================================
# UNIT TESTS - PLANNING MODELS
# ============================================================================

class TestPlanningModels:
    """Test planning data models and serialization"""

    def test_goal_creation(self):
        """Test basic goal creation"""
        goal = Goal(
            id="test_goal",
            title="Test Goal",
            description="This is a test goal",
            priority=8,
            status=GoalStatus.ACTIVE
        )
        assert goal.id == "test_goal"
        assert goal.title == "Test Goal"
        assert goal.priority == 8
        assert goal.status == GoalStatus.ACTIVE

    def test_goal_serialization(self):
        """Test goal JSON serialization"""
        goal = Goal(
            id="test_goal",
            title="Test Goal",
            description="Test description",
            priority=8,
            status=GoalStatus.ACTIVE
        )
        serialized = goal.to_dict()
        assert isinstance(serialized, dict)
        assert serialized["id"] == "test_goal"
        assert serialized["priority"] == 8

    def test_task_creation(self):
        """Test task creation"""
        task = Task(
            id="task_1",
            title="Implement Feature",
            description="Implement new feature",
            goal_id="goal_1",
            estimated_effort_hours=16,
            status=TaskStatus.PENDING
        )
        assert task.id == "task_1"
        assert task.estimated_effort_hours == 16
        assert task.status == TaskStatus.PENDING

    def test_plan_creation(self, sample_goals):
        """Test plan creation"""
        plan = Plan(
            id="plan_1",
            title="Quarterly Plan",
            description="Q3 execution plan",
            goals=[goal.id for goal in sample_goals],
            status=PlanStatus.DRAFT
        )
        assert plan.id == "plan_1"
        assert len(plan.goals) == 3
        assert plan.status == PlanStatus.DRAFT

    def test_constraint_creation(self):
        """Test constraint creation and validation"""
        constraint = Constraint(
            id="constraint_1",
            type=ConstraintType.TIME,
            goal_id="goal_1",
            description="Must complete by end of Q3",
            deadline=datetime.now() + timedelta(days=90)
        )
        assert constraint.id == "constraint_1"
        assert constraint.type == ConstraintType.TIME

    def test_risk_creation(self):
        """Test risk creation"""
        risk = Risk(
            id="risk_1",
            title="Resource Shortage",
            description="Insufficient staff available",
            probability=0.6,
            impact=0.8,
            mitigation_strategy="Hire contractors"
        )
        severity = risk.get_severity()
        assert severity == RiskSeverity.MEDIUM  # 0.6 * 0.8 = 0.48


# ============================================================================
# UNIT TESTS - GOAL MANAGER
# ============================================================================

class TestGoalManager:
    """Test goal management functionality"""

    def test_add_goal(self, goal_manager, sample_goals):
        """Test adding goals"""
        for goal in sample_goals:
            result = goal_manager.add_goal(goal)
            assert result is True

    def test_get_goal(self, goal_manager, sample_goals):
        """Test retrieving goals"""
        for goal in sample_goals:
            goal_manager.add_goal(goal)

        retrieved = goal_manager.get_goal("goal_1")
        assert retrieved is not None
        assert retrieved.title == "Complete Q3 Project"

    def test_goal_hierarchy(self, goal_manager):
        """Test goal hierarchy creation"""
        parent_goal = Goal(
            id="parent",
            title="Parent Goal",
            priority=10,
            status=GoalStatus.ACTIVE
        )
        child_goal = Goal(
            id="child",
            title="Child Goal",
            priority=8,
            status=GoalStatus.PENDING,
            parent_goal_id="parent"
        )
        goal_manager.add_goal(parent_goal)
        goal_manager.add_goal(child_goal)

        hierarchy = goal_manager.get_goal_hierarchy("parent")
        assert hierarchy is not None
        assert len(hierarchy.get("children", [])) == 1

    def test_goal_dependencies(self, goal_manager):
        """Test goal dependencies"""
        goal1 = Goal(id="g1", title="Goal 1", priority=10, status=GoalStatus.ACTIVE)
        goal2 = Goal(id="g2", title="Goal 2", priority=8, status=GoalStatus.PENDING)

        goal_manager.add_goal(goal1)
        goal_manager.add_goal(goal2)

        # Add dependency
        added = goal_manager.add_dependency("g2", "g1")
        assert added is True

        # Check if cycle detection works
        cycle = goal_manager.add_dependency("g1", "g2")
        assert cycle is False  # Should prevent circular dependency

    def test_goal_constraints(self, goal_manager):
        """Test adding constraints to goals"""
        goal = Goal(id="g1", title="Goal 1", priority=10, status=GoalStatus.ACTIVE)
        goal_manager.add_goal(goal)

        constraint = Constraint(
            id="c1",
            type=ConstraintType.TIME,
            goal_id="g1",
            description="Q3 deadline",
            deadline=datetime.now() + timedelta(days=90)
        )
        result = goal_manager.add_constraint("g1", constraint)
        assert result is True


# ============================================================================
# UNIT TESTS - TASK DECOMPOSER
# ============================================================================

class TestTaskDecomposer:
    """Test task decomposition engine"""

    def test_goal_based_decomposition(self, task_decomposer):
        """Test goal-based task decomposition"""
        goal = Goal(
            id="goal_1",
            title="Build API",
            description="Build REST API",
            priority=10,
            status=GoalStatus.ACTIVE
        )

        tasks = task_decomposer.decompose_goal(
            goal,
            strategy=DecompositionStrategy.GOAL_BASED
        )
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_phase_based_decomposition(self, task_decomposer):
        """Test phase-based decomposition"""
        goal = Goal(
            id="goal_1",
            title="Release Product",
            description="Complete product release",
            priority=10,
            status=GoalStatus.ACTIVE
        )

        tasks = task_decomposer.decompose_goal(
            goal,
            strategy=DecompositionStrategy.PHASE_BASED
        )
        # Should generate phases: planning, development, testing, deployment
        assert len(tasks) >= 4

    def test_alternative_plans(self, task_decomposer):
        """Test generating alternative decomposition plans"""
        goal = Goal(
            id="goal_1",
            title="Test Goal",
            priority=10,
            status=GoalStatus.ACTIVE
        )

        alternatives = task_decomposer.generate_alternative_plans(goal, num_alternatives=3)
        assert isinstance(alternatives, list)
        assert len(alternatives) == 3

    def test_plan_scoring(self, task_decomposer):
        """Test plan scoring for optimization"""
        plan = Plan(
            id="plan_1",
            title="Test Plan",
            goals=["goal_1"],
            status=PlanStatus.DRAFT,
            tasks=[
                Task(id="t1", title="Task 1", goal_id="goal_1"),
                Task(id="t2", title="Task 2", goal_id="goal_1"),
            ]
        )

        score = task_decomposer.score_plan(plan)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


# ============================================================================
# UNIT TESTS - PLAN VALIDATOR
# ============================================================================

class TestPlanValidator:
    """Test plan validation and risk analysis"""

    def test_plan_validation(self, plan_validator):
        """Test basic plan validation"""
        plan = Plan(
            id="plan_1",
            title="Test Plan",
            goals=["goal_1"],
            status=PlanStatus.DRAFT,
            tasks=[
                Task(id="t1", title="Task 1", goal_id="goal_1", estimated_effort_hours=8),
                Task(id="t2", title="Task 2", goal_id="goal_1", estimated_effort_hours=16),
            ]
        )

        validation = plan_validator.validate_plan(plan)
        assert validation is not None
        assert "is_valid" in validation

    def test_risk_analysis(self, plan_validator):
        """Test risk identification and analysis"""
        plan = Plan(
            id="plan_1",
            title="Test Plan",
            goals=["goal_1"],
            status=PlanStatus.DRAFT,
            tasks=[
                Task(id="t1", title="Task 1", goal_id="goal_1", estimated_effort_hours=40),
            ]
        )

        risks = plan_validator.identify_risks(plan)
        assert isinstance(risks, list)
        # Should identify risks like scope creep, timeline, resource constraints

    def test_resource_conflict_detection(self, plan_validator):
        """Test resource conflict detection"""
        plan = Plan(
            id="plan_1",
            title="Test Plan",
            goals=["goal_1"],
            status=PlanStatus.DRAFT,
            tasks=[
                Task(id="t1", title="Task 1", goal_id="goal_1", assigned_to="alice"),
                Task(id="t2", title="Task 2", goal_id="goal_1", assigned_to="alice", 
                     start_time=datetime.now(), end_time=datetime.now() + timedelta(days=5)),
                Task(id="t3", title="Task 3", goal_id="goal_1", assigned_to="alice",
                     start_time=datetime.now() + timedelta(days=3), 
                     end_time=datetime.now() + timedelta(days=8)),
            ]
        )

        conflicts = plan_validator.check_resource_conflicts(plan)
        assert isinstance(conflicts, list)


# ============================================================================
# INTEGRATION TESTS - PLANNING WORKFLOW
# ============================================================================

class TestPlanningWorkflow:
    """Test complete planning workflow"""

    def test_complete_planning_workflow(
        self,
        goal_manager,
        task_decomposer,
        plan_validator,
        planning_session
    ):
        """Test end-to-end planning workflow"""
        # 1. Create goals
        goal = Goal(
            id="goal_1",
            title="Project Alpha",
            description="Complete project alpha",
            priority=10,
            status=GoalStatus.ACTIVE,
            target_date=datetime.now() + timedelta(days=90)
        )
        goal_manager.add_goal(goal)

        # 2. Start planning session
        session = planning_session.create_session("test_user", "project_alpha")
        assert session["status"] == "active"

        # 3. Decompose goal into tasks
        tasks = task_decomposer.decompose_goal(goal)
        assert len(tasks) > 0

        # 4. Create plan
        plan = Plan(
            id="plan_1",
            title="Project Alpha Plan",
            goals=[goal.id],
            status=PlanStatus.DRAFT,
            tasks=tasks
        )

        # 5. Validate plan
        validation = plan_validator.validate_plan(plan)
        assert validation is not None

        # 6. Identify risks
        risks = plan_validator.identify_risks(plan)
        assert isinstance(risks, list)

    def test_multi_goal_planning(
        self,
        goal_manager,
        task_decomposer,
        plan_validator,
        sample_goals
    ):
        """Test planning with multiple goals"""
        # Add all goals
        for goal in sample_goals:
            goal_manager.add_goal(goal)

        # Create dependencies
        goal_manager.add_dependency("goal_2", "goal_1")  # goal_2 depends on goal_1

        # Create plan with multiple goals
        all_tasks = []
        for goal in sample_goals:
            tasks = task_decomposer.decompose_goal(goal)
            all_tasks.extend(tasks)

        plan = Plan(
            id="multi_goal_plan",
            title="Multi-Goal Plan",
            goals=[g.id for g in sample_goals],
            status=PlanStatus.DRAFT,
            tasks=all_tasks
        )

        # Validate
        validation = plan_validator.validate_plan(plan)
        assert validation is not None


# ============================================================================
# INTEGRATION TESTS - RESOURCE MANAGEMENT
# ============================================================================

class TestResourceManagement:
    """Test resource management integration"""

    def test_resource_allocation(self, resource_manager):
        """Test resource allocation"""
        # Register resources
        resource_manager.register_resource("alice", "developer", 40)
        resource_manager.register_resource("bob", "qa", 40)

        # Check resources
        resources = resource_manager.get_available_resources()
        assert len(resources) >= 2

    def test_resource_availability(self, resource_manager):
        """Test resource availability checking"""
        resource_manager.register_resource("alice", "developer", 40)

        available = resource_manager.check_availability("alice", 16)
        assert available is True

        available = resource_manager.check_availability("alice", 50)
        assert available is False


# ============================================================================
# INTEGRATION TESTS - DYNAMIC REPLANNING
# ============================================================================

class TestDynamicReplanning:
    """Test dynamic replanning capabilities"""

    def test_replanning_on_goal_change(self, dynamic_replanner):
        """Test replanning when goals change"""
        original_plan = Plan(
            id="plan_1",
            title="Original Plan",
            goals=["goal_1"],
            status=PlanStatus.ACTIVE,
            tasks=[
                Task(id="t1", title="Task 1", goal_id="goal_1", status=TaskStatus.IN_PROGRESS),
            ]
        )

        updated_goal = Goal(
            id="goal_1",
            title="Updated Goal",
            priority=10,
            status=GoalStatus.ACTIVE
        )

        new_plan = dynamic_replanner.replan_on_goal_change(
            original_plan,
            updated_goal
        )
        assert new_plan is not None

    def test_replanning_on_constraint_change(self, dynamic_replanner):
        """Test replanning when constraints change"""
        original_plan = Plan(
            id="plan_1",
            title="Original Plan",
            goals=["goal_1"],
            status=PlanStatus.ACTIVE,
            tasks=[
                Task(id="t1", title="Task 1", goal_id="goal_1", 
                     estimated_effort_hours=20, status=TaskStatus.IN_PROGRESS),
            ]
        )

        new_constraint = Constraint(
            id="c1",
            type=ConstraintType.TIME,
            goal_id="goal_1",
            description="Accelerated deadline",
            deadline=datetime.now() + timedelta(days=30)
        )

        new_plan = dynamic_replanner.replan_on_constraint_change(
            original_plan,
            new_constraint
        )
        assert new_plan is not None


# ============================================================================
# INTEGRATION TESTS - EXECUTION MONITORING
# ============================================================================

class TestExecutionMonitoring:
    """Test execution monitoring"""

    def test_task_completion_tracking(self, execution_monitor):
        """Test tracking task completion"""
        plan = Plan(
            id="plan_1",
            title="Test Plan",
            goals=["goal_1"],
            status=PlanStatus.ACTIVE,
            tasks=[
                Task(id="t1", title="Task 1", status=TaskStatus.COMPLETED),
                Task(id="t2", title="Task 2", status=TaskStatus.IN_PROGRESS),
                Task(id="t3", title="Task 3", status=TaskStatus.PENDING),
            ]
        )

        progress = execution_monitor.calculate_progress(plan)
        assert isinstance(progress, dict)
        assert "completion_percentage" in progress

    def test_critical_path_analysis(self, execution_monitor):
        """Test critical path identification"""
        plan = Plan(
            id="plan_1",
            title="Test Plan",
            goals=["goal_1"],
            status=PlanStatus.ACTIVE,
            tasks=[
                Task(id="t1", title="Task 1", estimated_effort_hours=10),
                Task(id="t2", title="Task 2", estimated_effort_hours=20, depends_on=["t1"]),
                Task(id="t3", title="Task 3", estimated_effort_hours=15, depends_on=["t2"]),
            ]
        )

        critical_path = execution_monitor.identify_critical_path(plan)
        assert isinstance(critical_path, list)


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Test performance characteristics"""

    def test_goal_manager_performance(self, goal_manager):
        """Test goal manager performance with many goals"""
        import time
        goals = [
            Goal(id=f"goal_{i}", title=f"Goal {i}", priority=i % 10, status=GoalStatus.ACTIVE)
            for i in range(100)
        ]

        start = time.time()
        for goal in goals:
            goal_manager.add_goal(goal)
        elapsed = time.time() - start

        assert elapsed < 5.0  # Should complete in less than 5 seconds

    def test_plan_validation_performance(self, plan_validator):
        """Test plan validation performance"""
        import time

        large_plan = Plan(
            id="large_plan",
            title="Large Plan",
            goals=["goal_1"],
            status=PlanStatus.DRAFT,
            tasks=[
                Task(id=f"task_{i}", title=f"Task {i}", goal_id="goal_1")
                for i in range(50)
            ]
        )

        start = time.time()
        validation = plan_validator.validate_plan(large_plan)
        elapsed = time.time() - start

        assert elapsed < 2.0  # Should complete in less than 2 seconds


# ============================================================================
# BACKWARDS COMPATIBILITY TESTS
# ============================================================================

class TestBackwardsCompatibility:
    """Test backwards compatibility with existing PlanningAgent"""

    def test_planning_models_serialization(self, sample_plan):
        """Test that plans can be serialized for existing systems"""
        serialized = sample_plan.to_dict()
        assert isinstance(serialized, dict)
        assert "id" in serialized
        assert "title" in serialized
        assert "goals" in serialized

    def test_task_serialization(self):
        """Test task serialization for compatibility"""
        task = Task(
            id="t1",
            title="Test Task",
            goal_id="g1",
            estimated_effort_hours=8
        )
        serialized = task.to_dict()
        assert isinstance(serialized, dict)


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_invalid_goal_id(self, goal_manager):
        """Test handling of invalid goal IDs"""
        result = goal_manager.get_goal("nonexistent_goal")
        assert result is None

    def test_circular_dependency_prevention(self, goal_manager):
        """Test prevention of circular dependencies"""
        g1 = Goal(id="g1", title="G1", priority=10, status=GoalStatus.ACTIVE)
        g2 = Goal(id="g2", title="G2", priority=10, status=GoalStatus.ACTIVE)

        goal_manager.add_goal(g1)
        goal_manager.add_goal(g2)

        goal_manager.add_dependency("g2", "g1")
        result = goal_manager.add_dependency("g1", "g2")  # Should fail

        assert result is False

    def test_constraint_validation(self):
        """Test constraint validation"""
        with pytest.raises((ValueError, TypeError)):
            Constraint(
                id="c1",
                type=ConstraintType.TIME,
                goal_id="g1",
                description="Invalid constraint",
                # Missing deadline for TIME constraint
            )


# ============================================================================
# SUITE EXECUTION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
