# Phase 6 Planning Engine - Quick Start Guide

**Quick Reference for Using Phase 6 Production Planning Engine**

---

## Installation & Setup

```bash
# 1. All Phase 6 components are in agents/ directory
cd /vercel/share/v0-project

# 2. Import components
from agents.planning_models import Goal, Task, Plan, Constraint
from agents.goal_manager import GoalManager
from agents.task_decomposer import TaskDecomposer, DecompositionStrategy
from agents.plan_validator import PlanValidator
from agents.planning_session import PlanningSession
from agents.resource_manager import ResourceManager
from agents.dynamic_replanner import DynamicReplanner
from agents.execution_monitor import ExecutionMonitor

# 3. Run tests
pytest tests/test_planning_engine_phase6.py -v
```

---

## Basic Usage

### 1. Create Goals

```python
from agents.planning_models import Goal, GoalStatus
from agents.goal_manager import GoalManager
from datetime import datetime, timedelta

# Initialize goal manager
goal_mgr = GoalManager()

# Create goals
goal = Goal(
    id="goal_1",
    title="Complete Q3 Project",
    description="Deliver quarterly milestone",
    priority=9,  # 1-10 scale
    status=GoalStatus.ACTIVE,
    target_date=datetime.now() + timedelta(days=90)
)

# Add goal
goal_mgr.add_goal(goal)
```

### 2. Decompose into Tasks

```python
from agents.task_decomposer import TaskDecomposer, DecompositionStrategy

decomposer = TaskDecomposer()

# Decompose goal into tasks using different strategies
tasks = decomposer.decompose_goal(
    goal,
    strategy=DecompositionStrategy.PHASE_BASED  # or GOAL_BASED, CONSTRAINT_BASED, etc.
)

# Generate alternative plans
alternatives = decomposer.generate_alternative_plans(goal, num_alternatives=3)

# Score and select best plan
best_plan = max(alternatives, key=lambda p: decomposer.score_plan(p))
```

### 3. Create & Validate Plan

```python
from agents.planning_models import Plan, PlanStatus
from agents.plan_validator import PlanValidator

# Create plan
plan = Plan(
    id="plan_1",
    title="Q3 Execution Plan",
    goals=[goal.id],
    status=PlanStatus.DRAFT,
    tasks=tasks
)

# Validate plan
validator = PlanValidator()
validation = validator.validate_plan(plan)

# Analyze risks
risks = validator.identify_risks(plan)
for risk in risks:
    print(f"Risk: {risk.title}")
    print(f"Severity: {risk.get_severity()}")
    print(f"Mitigation: {risk.mitigation_strategy}")
```

### 4. Manage Resources

```python
from agents.resource_manager import ResourceManager

resource_mgr = ResourceManager()

# Register team members
resource_mgr.register_resource("alice", "developer", hours_available=40)
resource_mgr.register_resource("bob", "qa", hours_available=40)

# Check availability
available = resource_mgr.check_availability("alice", hours_required=16)

# Allocate to tasks
allocation = resource_mgr.allocate_resource("alice", "task_1", 16)
```

### 5. Start Planning Session

```python
from agents.planning_session import PlanningSession

session_mgr = PlanningSession()

# Create session
session = session_mgr.create_session(user_id="user_123", project_name="Q3Project")

# Get session
current_session = session_mgr.get_session(session["session_id"])

# Create checkpoint for recovery
checkpoint = session_mgr.create_checkpoint(
    session["session_id"],
    checkpoint_name="After_Risk_Analysis"
)
```

### 6. Monitor Execution

```python
from agents.execution_monitor import ExecutionMonitor

monitor = ExecutionMonitor()

# Calculate progress
progress = monitor.calculate_progress(plan)
print(f"Completion: {progress['completion_percentage']}%")

# Identify critical path
critical_path = monitor.identify_critical_path(plan)
print(f"Critical path: {[t.title for t in critical_path]}")

# Get stalled tasks
stalled = monitor.get_stalled_tasks(plan, threshold_hours=24)
```

### 7. Dynamic Replanning

```python
from agents.dynamic_replanner import DynamicReplanner
from agents.planning_models import Goal

replanner = DynamicReplanner()

# Handle goal changes
updated_goal = Goal(id="goal_1", title="Updated Goal", priority=10)
new_plan = replanner.replan_on_goal_change(plan, updated_goal)

# Handle deadline changes
new_constraint = Constraint(
    id="c1",
    type=ConstraintType.TIME,
    goal_id="goal_1",
    deadline=datetime.now() + timedelta(days=60)  # Accelerated
)
new_plan = replanner.replan_on_constraint_change(plan, new_constraint)
```

---

## Advanced Features

### Goal Hierarchies

```python
# Create parent goal
parent = Goal(id="parent", title="Parent Goal", priority=10)
goal_mgr.add_goal(parent)

# Create child goal
child = Goal(
    id="child",
    title="Child Goal",
    priority=8,
    parent_goal_id="parent"
)
goal_mgr.add_goal(child)

# Get hierarchy
hierarchy = goal_mgr.get_goal_hierarchy("parent")
```

### Goal Dependencies

```python
# Add dependency: goal_2 depends on goal_1
goal_mgr.add_dependency("goal_2", "goal_1")

# System prevents circular dependencies
goal_mgr.add_dependency("goal_1", "goal_2")  # Returns False
```

### Constraints Management

```python
from agents.planning_models import Constraint, ConstraintType

# Add time constraint
constraint = Constraint(
    id="c1",
    type=ConstraintType.TIME,
    goal_id="goal_1",
    deadline=datetime.now() + timedelta(days=90)
)
goal_mgr.add_constraint("goal_1", constraint)

# Add resource constraint
resource_constraint = Constraint(
    id="c2",
    type=ConstraintType.RESOURCE,
    goal_id="goal_1",
    description="Max 2 team members"
)
```

### Decomposition Strategies

```python
from agents.task_decomposer import DecompositionStrategy

# 1. GOAL_BASED - Break by responsibility areas
tasks_goal = decomposer.decompose_goal(
    goal, 
    strategy=DecompositionStrategy.GOAL_BASED
)

# 2. PHASE_BASED - Sequential phases
tasks_phase = decomposer.decompose_goal(
    goal,
    strategy=DecompositionStrategy.PHASE_BASED
)

# 3. CONSTRAINT_BASED - Constraint-driven
tasks_constraint = decomposer.decompose_goal(
    goal,
    strategy=DecompositionStrategy.CONSTRAINT_BASED
)

# 4. RESOURCE_BASED - Resource-efficient
tasks_resource = decomposer.decompose_goal(
    goal,
    strategy=DecompositionStrategy.RESOURCE_BASED
)

# 5. TIMELINE_BASED - Schedule-driven
tasks_timeline = decomposer.decompose_goal(
    goal,
    strategy=DecompositionStrategy.TIMELINE_BASED
)
```

### Risk Analysis & Mitigation

```python
# Identify all risks
risks = validator.identify_risks(plan)

# Check resource conflicts
conflicts = validator.check_resource_conflicts(plan)

# Validate dependencies
dep_issues = validator.check_dependency_chain(plan)

# Get severity distribution
for risk in risks:
    severity = risk.get_severity()  # Returns RiskSeverity enum
    print(f"{risk.title}: {severity.name}")
```

### Plan Versioning & Recovery

```python
# Get plan history
versions = session_mgr.get_plan_versions(session_id, plan_id)

# Get specific version
old_plan = session_mgr.get_plan_version(
    session_id, 
    plan_id, 
    version_number=2
)

# Rollback to previous version
session_mgr.rollback_plan(session_id, plan_id, version_number=2)

# Query audit trail
audit = session_mgr.query_audit_trail(
    session_id,
    start_time=datetime.now() - timedelta(hours=24)
)
```

---

## Configuration

All thresholds are configurable in component initialization:

```python
# Custom configuration
config = {
    "max_goal_depth": 5,
    "max_alternatives": 3,
    "risk_probability_threshold": 0.3,
    "critical_path_margin": 0.1,
    "resource_utilization_target": 0.85,
}

goal_mgr = GoalManager(config=config)
decomposer = TaskDecomposer(config=config)
validator = PlanValidator(config=config)
```

---

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Goal creation | <50ms | Single goal |
| HTN decomposition | <100ms | ~20 tasks |
| Plan validation | <50ms | ~20 tasks |
| Risk analysis | <200ms | Full analysis |
| Resource allocation | <100ms | Single task |
| Session checkpoint | <20ms | State save |
| Progress calculation | <30ms | Real-time |

---

## Testing

```bash
# Run all Phase 6 tests
pytest tests/test_planning_engine_phase6.py -v

# Run specific test class
pytest tests/test_planning_engine_phase6.py::TestGoalManager -v

# Run with coverage
pytest tests/test_planning_engine_phase6.py --cov=agents

# Run performance tests
pytest tests/test_planning_engine_phase6.py::TestPerformance -v
```

---

## Common Patterns

### Complete Planning Workflow

```python
# 1. Define goals
goals = [create_goal(...), create_goal(...), ...]
for goal in goals:
    goal_mgr.add_goal(goal)

# 2. Decompose goals
all_tasks = []
for goal in goals:
    tasks = decomposer.decompose_goal(goal)
    all_tasks.extend(tasks)

# 3. Create plan
plan = Plan(
    id=generate_id(),
    title="My Plan",
    goals=[g.id for g in goals],
    tasks=all_tasks,
    status=PlanStatus.DRAFT
)

# 4. Validate
validation = validator.validate_plan(plan)
if not validation["is_valid"]:
    raise ValueError(f"Plan invalid: {validation['errors']}")

# 5. Allocate resources
for task in plan.tasks:
    resource = find_available_resource(task.required_skills)
    resource_mgr.allocate_resource(resource.id, task.id, task.estimated_effort_hours)

# 6. Start session and execute
session = session_mgr.create_session(user_id, project_name)
session_mgr.save_plan(session["session_id"], plan)

# 7. Monitor
progress = monitor.calculate_progress(plan)
critical_path = monitor.identify_critical_path(plan)
```

### Adaptive Replanning

```python
# Monitor and detect issue
anomalies = detector.detect_anomalies(plan)

if anomalies:
    # Trigger replanning
    new_plan = replanner.replan(plan, anomalies)
    
    # Validate new plan
    validation = validator.validate_plan(new_plan)
    
    # Update session
    session_mgr.update_plan(session_id, new_plan)
    
    # Alert stakeholders
    notify_stakeholders(f"Plan updated: {new_plan.adaptations}")
```

---

## Troubleshooting

### Common Issues

**Issue:** "Circular dependency detected"
- **Solution:** Check goal dependencies - ensure no cycles exist

**Issue:** "Resource conflict detected"
- **Solution:** Use resource_mgr to check availability before allocation

**Issue:** "Plan validation failed"
- **Solution:** Check validation result for specific errors

**Issue:** "No valid decomposition found"
- **Solution:** Try different DecompositionStrategy or adjust constraints

---

## API Reference

### GoalManager
- `add_goal(goal: Goal) -> bool`
- `get_goal(goal_id: str) -> Goal | None`
- `add_dependency(dependent: str, dependency: str) -> bool`
- `add_constraint(goal_id: str, constraint: Constraint) -> bool`
- `get_goal_hierarchy(goal_id: str) -> Dict`

### TaskDecomposer
- `decompose_goal(goal: Goal, strategy: DecompositionStrategy) -> List[Task]`
- `generate_alternative_plans(goal: Goal, num_alternatives: int) -> List[Plan]`
- `score_plan(plan: Plan) -> float`

### PlanValidator
- `validate_plan(plan: Plan) -> Dict`
- `identify_risks(plan: Plan) -> List[Risk]`
- `check_resource_conflicts(plan: Plan) -> List[Conflict]`

### ResourceManager
- `register_resource(resource_id: str, role: str, hours_available: int)`
- `check_availability(resource_id: str, hours_required: int) -> bool`
- `allocate_resource(resource_id: str, task_id: str, hours: int) -> bool`

### ExecutionMonitor
- `calculate_progress(plan: Plan) -> Dict`
- `identify_critical_path(plan: Plan) -> List[Task]`
- `get_stalled_tasks(plan: Plan, threshold_hours: int) -> List[Task]`

### DynamicReplanner
- `replan_on_goal_change(plan: Plan, goal: Goal) -> Plan`
- `replan_on_constraint_change(plan: Plan, constraint: Constraint) -> Plan`

---

## Next Steps

1. **Review** Phase 6 implementation
2. **Run** test suite: `pytest tests/test_planning_engine_phase6.py`
3. **Integrate** with your orchestrator
4. **Monitor** plan quality metrics
5. **Plan** Phase 7 Execution Intelligence implementation

---

**Documentation Version:** 1.0  
**Phase:** 6 - Production Planning Engine  
**Last Updated:** August 3, 2026
