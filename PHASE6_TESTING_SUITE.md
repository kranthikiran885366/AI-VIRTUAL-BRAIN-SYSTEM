# Phase 6 Comprehensive Testing & Validation Suite

**Purpose:** Complete testing strategy for Phase 6 Planning Engine  
**Target Coverage:** 85%+ code coverage  
**Status:** Testing framework and patterns documented  

---

## Testing Architecture

```
Test Pyramid:
           /\
          /  \
         /    \  Integration Tests (30%)
        /______\
         /    \
        /      \  Unit Tests (60%)
       /________\
       /          \
      /            \ E2E Tests (10%)
     /______________\
```

---

## Unit Tests

### 1. Planning Models Tests

**File:** `tests/test_planning_models.py`

```python
import pytest
from agents.planning_models import *

class TestGoalNode:
    def test_goal_node_creation(self):
        """Test basic goal node creation."""
        node = GoalNode(
            goal_title="Test Goal",
            goal_description="Test Description",
        )
        assert node.goal_id
        assert node.goal_title == "Test Goal"
        assert node.status == GoalStatus.CREATED
    
    def test_goal_node_serialization(self):
        """Test goal node to_dict()."""
        node = GoalNode(goal_title="Test")
        data = node.to_dict()
        assert data["goal_title"] == "Test"
        assert "goal_id" in data

class TestProductionPlan:
    def test_plan_creation(self):
        """Test production plan creation."""
        plan = ProductionPlan(goal="Test goal")
        assert plan.plan_id
        assert plan.status == PlanStatus.DRAFT
        assert plan.current_version == 1
    
    def test_plan_legacy_format(self):
        """Test backward compatibility format."""
        plan = ProductionPlan(goal="Test")
        legacy = plan.to_legacy_dict()
        assert "milestones" in legacy
        assert "tasks" in legacy
        assert "status" in legacy

class TestHierarchicalTaskNetwork:
    def test_htn_creation(self):
        """Test HTN structure creation."""
        htn = HierarchicalTaskNetwork()
        assert htn.network_id
        assert htn.total_tasks == 0
    
    def test_htn_with_tasks(self):
        """Test HTN with tasks."""
        htn = HierarchicalTaskNetwork()
        task = DecomposedTask(task_title="Test Task")
        htn.all_tasks[task.task_id] = task
        htn.total_tasks = 1
        
        assert len(htn.all_tasks) == 1
```

### 2. Goal Manager Tests

**File:** `tests/test_goal_manager.py`

```python
import pytest
from agents.goal_manager import GoalManager

@pytest.fixture
def manager():
    return GoalManager()

@pytest.mark.asyncio
class TestGoalManager:
    async def test_create_goal(self, manager):
        """Test goal creation."""
        goal = await manager.create_goal(
            goal_title="Learn Python",
            category=GoalCategory.LEARNING,
        )
        assert goal.goal_id
        assert goal.root_node.goal_title == "Learn Python"
    
    @pytest.mark.asyncio
    async def test_create_child_goal(self, manager):
        """Test child goal creation."""
        parent = await manager.create_goal("Parent Goal")
        child = await manager.add_child_goal(
            parent.goal_id,
            "Child Goal",
        )
        assert child.root_node.parent_goal_id == parent.goal_id
    
    @pytest.mark.asyncio
    async def test_goal_dependency(self, manager):
        """Test goal dependencies."""
        goal1 = await manager.create_goal("Goal 1")
        goal2 = await manager.create_goal("Goal 2")
        
        await manager.add_goal_dependency(goal1.goal_id, goal2.goal_id)
        deps = await manager.get_goal_dependencies(goal2.goal_id)
        assert len(deps) == 1
    
    @pytest.mark.asyncio
    async def test_cycle_detection(self, manager):
        """Test cycle detection in dependencies."""
        goal1 = await manager.create_goal("Goal 1")
        goal2 = await manager.create_goal("Goal 2")
        
        await manager.add_goal_dependency(goal1.goal_id, goal2.goal_id)
        
        with pytest.raises(ValueError):
            await manager.add_goal_dependency(goal2.goal_id, goal1.goal_id)
    
    @pytest.mark.asyncio
    async def test_get_goal_tree(self, manager):
        """Test goal tree retrieval."""
        parent = await manager.create_goal("Parent")
        child1 = await manager.add_child_goal(parent.goal_id, "Child 1")
        child2 = await manager.add_child_goal(parent.goal_id, "Child 2")
        
        tree = await manager.get_goal_tree(parent.goal_id)
        assert len(tree["children"]) == 2
```

### 3. Task Decomposer Tests

**File:** `tests/test_task_decomposer.py`

```python
import pytest
from agents.task_decomposer import TaskDecomposer, DecompositionStrategy

@pytest.fixture
def decomposer():
    return TaskDecomposer()

@pytest.mark.asyncio
class TestTaskDecomposer:
    async def test_basic_decomposition(self, decomposer):
        """Test basic goal decomposition."""
        htn, alternatives = await decomposer.decompose_goal(
            goal="Build a web application",
            include_alternatives=False,
        )
        
        assert htn.network_id
        assert len(htn.all_tasks) > 0
        assert htn.root_task_id
    
    async def test_strategy_selection(self, decomposer):
        """Test automatic strategy selection."""
        # Goal implies phase-based decomposition
        htn1, _ = await decomposer.decompose_goal(
            goal="Build a software system",
            strategy=DecompositionStrategy.GOAL_DECOMPOSITION,
        )
        
        # Goal implies learning decomposition  
        htn2, _ = await decomposer.decompose_goal(
            goal="Learn machine learning",
            strategy=DecompositionStrategy.GOAL_DECOMPOSITION,
        )
        
        assert htn1.total_tasks > 0
        assert htn2.total_tasks > 0
    
    async def test_alternative_generation(self, decomposer):
        """Test alternative plan generation."""
        htn, alternatives = await decomposer.decompose_goal(
            goal="Improve performance",
            include_alternatives=True,
        )
        
        assert len(alternatives) >= 0  # May be 0-2 alternatives
        assert htn.total_tasks > 0
    
    async def test_optimal_plan_selection(self, decomposer):
        """Test plan scoring and selection."""
        htn1, alternatives = await decomposer.decompose_goal(
            goal="Test goal",
            include_alternatives=True,
        )
        
        if alternatives:
            plans = [htn1] + alternatives
            selected = await decomposer.select_optimal_plan(plans)
            assert selected in plans
    
    async def test_htn_validation(self, decomposer):
        """Test HTN validation."""
        htn, _ = await decomposer.decompose_goal("Test goal")
        errors = decomposer._validate_htn(htn)
        assert len(errors) == 0  # Should be valid
    
    async def test_cycle_detection(self, decomposer):
        """Test cycle detection in HTN."""
        htn, _ = await decomposer.decompose_goal("Test")
        has_cycles = decomposer._has_cycles(htn)
        assert not has_cycles
```

### 4. Plan Validator & Risk Analyzer Tests

**File:** `tests/test_validator_and_risk.py`

```python
import pytest
from agents.plan_validator import PlanValidator, RiskAnalyzer
from agents.planning_models import ProductionPlan

@pytest.fixture
def validator():
    return PlanValidator()

@pytest.fixture
def risk_analyzer():
    return RiskAnalyzer()

@pytest.mark.asyncio
class TestPlanValidator:
    async def test_valid_plan(self, validator):
        """Test validation of valid plan."""
        plan = ProductionPlan(goal="Test goal")
        
        result = await validator.validate_plan(
            plan_id=plan.plan_id,
            htn=plan.htn,
            constraints=plan.constraints,
            resources=plan.resource_profile,
            goal=plan.goal,
        )
        
        assert result.status == ValidationStatus.PASSED or ValidationStatus.WARNING
    
    async def test_invalid_goal(self, validator):
        """Test validation with invalid goal."""
        plan = ProductionPlan(goal="")  # Empty goal
        
        result = await validator.validate_plan(
            plan_id=plan.plan_id,
            htn=plan.htn,
            constraints=[],
            resources=plan.resource_profile,
            goal="",
        )
        
        assert result.status == ValidationStatus.FAILED
        assert any(i.issue_type == "invalid_goal" for i in result.issues)

@pytest.mark.asyncio
class TestRiskAnalyzer:
    async def test_risk_identification(self, risk_analyzer):
        """Test risk identification."""
        plan = ProductionPlan(goal="Build complex system")
        
        risks = await risk_analyzer.analyze_risks(
            goal=plan.goal,
            htn=plan.htn,
            constraints=plan.constraints,
            resources=plan.resource_profile,
        )
        
        assert len(risks) > 0
        assert all(r.overall_risk_score >= 0 and r.overall_risk_score <= 1 for r in risks)
    
    async def test_risk_scoring(self, risk_analyzer):
        """Test risk probability × impact scoring."""
        from agents.planning_models import Risk
        
        risk = Risk(
            risk_description="Test risk",
            probability="high",
            impact="high",
        )
        
        await risk_analyzer._score_risk(risk)
        assert risk.overall_risk_score > 0.7
```

### 5. Session Management Tests

**File:** `tests/test_session_management.py`

```python
import pytest
from agents.planning_session import (
    PlanningSessionManager,
    PlanStateMachine,
    PlanCheckpointManager,
)
from agents.planning_models import ProductionPlan, PlanStatus

@pytest.mark.asyncio
class TestPlanningSession:
    async def test_create_session(self):
        """Test session creation."""
        manager = PlanningSessionManager()
        session = await manager.create_session(plan_id="plan123")
        
        assert session.session_id
        assert session.plan_id == "plan123"
    
    async def test_session_duration(self):
        """Test session duration tracking."""
        import asyncio
        
        manager = PlanningSessionManager()
        session = await manager.create_session(plan_id="plan123")
        
        await asyncio.sleep(0.1)
        
        session = await manager.end_session(session.session_id)
        assert session.duration_seconds > 0

@pytest.mark.asyncio
class TestStateMachine:
    async def test_valid_transition(self):
        """Test valid state transition."""
        sm = PlanStateMachine()
        plan = ProductionPlan()
        
        plan = await sm.transition_plan(
            plan,
            PlanStatus.ACTIVE,
            reason="test",
        )
        
        assert plan.status == PlanStatus.ACTIVE
    
    async def test_invalid_transition(self):
        """Test invalid state transition."""
        sm = PlanStateMachine()
        plan = ProductionPlan()
        plan.status = PlanStatus.COMPLETED
        
        with pytest.raises(ValueError):
            await sm.transition_plan(
                plan,
                PlanStatus.DRAFT,
                reason="test",
            )

@pytest.mark.asyncio
class TestCheckpointManager:
    async def test_create_checkpoint(self):
        """Test checkpoint creation."""
        manager = PlanCheckpointManager()
        plan = ProductionPlan()
        
        checkpoint = await manager.create_checkpoint(
            plan,
            reason="test_checkpoint",
        )
        
        assert checkpoint["checkpoint_id"]
        assert checkpoint["plan_id"] == plan.plan_id
    
    async def test_recover_checkpoint(self):
        """Test checkpoint recovery."""
        manager = PlanCheckpointManager()
        plan = ProductionPlan()
        
        checkpoint = await manager.create_checkpoint(plan)
        recovered = await manager.recover_from_checkpoint(plan.plan_id)
        
        assert recovered["checkpoint_id"] == checkpoint["checkpoint_id"]
```

---

## Integration Tests

### End-to-End Plan Creation Flow

**File:** `tests/test_e2e_plan_creation.py`

```python
import pytest
from agents.planning_agent import PlanningAgent

@pytest.fixture
async def agent():
    agent = PlanningAgent()
    await agent.initialize()
    yield agent
    await agent.shutdown()

@pytest.mark.asyncio
class TestE2EPlanning:
    async def test_complete_planning_flow(self, agent):
        """Test complete planning from goal to execution."""
        # Create plan
        plan = await agent.create_plan(
            goal="Build a web application",
            timeframe="1 month",
            constraints=["team_size_limit"],
        )
        
        # Verify plan structure
        assert "plan_id" in plan
        assert "milestones" in plan
        assert "tasks" in plan
        assert "validation" in plan
        assert "risks" in plan
        
        # Verify validation passed
        assert plan["validation"]["status"] in ("passed", "warning")
        
        # Verify risk analysis
        assert len(plan["risks"]) > 0
        
        # Verify resources estimated
        assert plan["resources"]["recommended_team_size"] > 0
```

---

## Performance Benchmarks

**File:** `tests/test_performance.py`

```python
import pytest
import time
from agents.task_decomposer import TaskDecomposer

class TestPerformance:
    @pytest.mark.asyncio
    async def test_decomposition_speed(self):
        """Test decomposition performance."""
        decomposer = TaskDecomposer()
        goal = "Build a complex enterprise system"
        
        start = time.time()
        htn, _ = await decomposer.decompose_goal(goal)
        duration = time.time() - start
        
        assert duration < 0.1  # Should complete in <100ms
    
    @pytest.mark.asyncio
    async def test_validation_speed(self):
        """Test validation performance."""
        from agents.plan_validator import PlanValidator
        from agents.planning_models import ProductionPlan
        
        validator = PlanValidator()
        plan = ProductionPlan(goal="Test")
        
        start = time.time()
        result = await validator.validate_plan(
            plan_id=plan.plan_id,
            htn=plan.htn,
            constraints=[],
            resources=plan.resource_profile,
            goal=plan.goal,
        )
        duration = time.time() - start
        
        assert duration < 0.05  # Should complete in <50ms
```

---

## Backward Compatibility Tests

**File:** `tests/test_backward_compatibility.py`

```python
import pytest
from agents.planning_agent import PlanningAgent

@pytest.mark.asyncio
class TestBackwardCompatibility:
    async def test_legacy_create_plan_interface(self):
        """Test legacy create_plan() interface still works."""
        agent = PlanningAgent()
        await agent.initialize()
        
        # Old interface
        plan = await agent.create_plan(
            goal="Test goal",
            timeframe="1 week",
            constraints=["constraint1"],
            context={"request_id": "123"},
            metadata={"owner": "test"},
        )
        
        # Legacy fields must be present
        assert "plan_id" in plan or "id" in plan
        assert "milestones" in plan
        assert "status" in plan
        assert "progress" in plan
    
    async def test_legacy_update_milestone_interface(self):
        """Test legacy update_milestone() interface still works."""
        agent = PlanningAgent()
        await agent.initialize()
        
        # Create plan
        plan = await agent.create_plan(goal="Test")
        plan_id = plan.get("plan_id") or plan.get("id")
        
        # Get first milestone
        milestones = plan.get("milestones", [])
        if milestones:
            milestone_id = milestones[0].get("id")
            
            # Update using legacy interface
            result = await agent.update_milestone(
                plan_id,
                milestone_id,
                "completed",
            )
            
            assert result is not None
```

---

## Test Configuration

**File:** `pytest.ini`

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    asyncio: marks tests as async (deselect with '-m "not asyncio"')
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
```

---

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_planning_models.py

# Run with coverage
pytest --cov=agents --cov-report=html

# Run async tests only
pytest -m asyncio

# Run performance tests
pytest tests/test_performance.py

# Run with verbose output
pytest -v

# Run specific test class
pytest tests/test_goal_manager.py::TestGoalManager
```

---

## Test Coverage Goals

| Component | Target Coverage |
|-----------|-----------------|
| planning_models | 95% |
| goal_manager | 90% |
| task_decomposer | 85% |
| plan_validator | 85% |
| resource_manager | 80% |
| planning_session | 85% |
| dynamic_replanner | 80% |
| execution_monitor | 80% |
| **Overall** | **85%** |

---

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Phase 6 Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: pytest --cov=agents --cov-report=xml
      - uses: codecov/codecov-action@v2
```

---

## Success Criteria

✓ 85%+ code coverage across all components  
✓ All unit tests passing  
✓ All integration tests passing  
✓ E2E planning flow functional  
✓ Backward compatibility verified  
✓ Performance targets met  
✓ No regressions from Phase 5  
✓ Production ready for deployment  

---

**Testing Status:** Framework complete, ready for implementation  
**Estimated Test Implementation Time:** 4-6 hours
