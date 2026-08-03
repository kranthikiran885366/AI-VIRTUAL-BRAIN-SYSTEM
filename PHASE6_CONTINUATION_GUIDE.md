# Phase 6 Planning Engine - Continuation Guide

**Current Status:** Foundation Complete (36% - Tasks 1-5)  
**Last Update:** August 3, 2026  
**Next Focus:** Task 6 - Plan Context & Lifecycle Management  

---

## What Has Been Completed

### ✓ Task 1: Architecture Analysis (COMPLETE)
**Document:** `PHASE6_PLANNING_ENGINE_ANALYSIS.md`
- Analyzed existing PlanningAgent (450 lines)
- Identified 10 production gaps
- Documented 8 design decisions for Phase 6
- Created backward compatibility checklist
- Established success criteria

### ✓ Task 2: Production Models (COMPLETE)
**File:** `agents/planning_models.py` (655 lines)
- 6 enumerations for status tracking
- 15 production-grade dataclasses
- Full JSON serialization support
- Backward compatibility layer via `to_legacy_dict()`
- Comprehensive docstrings

**Key Models:** Goal, GoalNode, DecomposedTask, HierarchicalTaskNetwork, Risk, PlanValidationResult, ProductionPlan

### ✓ Task 3: Goal Manager (COMPLETE)
**File:** `agents/goal_manager.py` (459 lines)
- Multi-level goal hierarchies with depth limits
- Goal dependency tracking with cycle detection
- Constraint management per goal
- Status lifecycle tracking
- Goal tree traversal and statistics

**Key Methods:** create_goal(), add_goal_dependency(), get_goal_tree(), archive_goal()

### ✓ Task 4: HTN Decomposition (COMPLETE)
**File:** `agents/task_decomposer.py` (564 lines)
- 5 decomposition strategies (goal, phase, constraint, resource, timeline)
- Automatic strategy selection based on goal/constraints
- Alternative plan generation
- Optimal plan scoring and selection
- Cycle detection in HTN

**Key Methods:** decompose_goal(), generate_alternative_plans(), select_optimal_plan()

### ✓ Task 5: Validation & Risk (COMPLETE)
**File:** `agents/plan_validator.py` (697 lines)

**PlanValidator (7 checks):**
- Dependency cycle detection
- Missing resources
- Invalid goals
- Duplicate tasks
- Conflicting constraints
- Deadline conflicts
- Execution feasibility

**RiskAnalyzer:**
- Goal-based, task-based, constraint-based, resource-based risk identification
- Probability × Impact scoring
- Severity classification
- Mitigation strategy generation

---

## Architecture Overview

```
Planning Engine Components:
┌─────────────────────────────────────────────────────────────┐
│                    PlanningAgent (v2)                       │
│  (Integrates all components with orchestrator)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
    ┌────────────┐  ┌─────────────┐ ┌──────────────┐
    │Goal        │  │Task         │ │Execution     │
    │Manager     │  │Decomposer   │ │Monitor       │
    │            │  │             │ │(Task 8)      │
    │- hierarchy │  │- HTN        │ │- track tasks │
    │- deps      │  │- strategies │ │- metrics     │
    │- validate  │  │- alternatives│             │
    └────────────┘  └─────────────┘ └──────────────┘
        ↓              ↓
    ┌─────────────────────────────────────────────┐
    │         Core Models (planning_models.py)    │
    │  Goal, Task, HTN, Risk, Validation, Plan   │
    └─────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────┐
    │           Validation & Risk Analysis        │
    │  Validator (7 checks), Analyzer (5 types)   │
    └─────────────────────────────────────────────┘
```

---

## Immediate Next Steps

### Priority 1: Task 6 - Plan Context & Lifecycle
**Estimated:** 300-400 lines, 1-2 hours

**Create:** `agents/planning_session.py`

**Key Classes:**
```python
class PlanningSession:
    """Session management for planning operations."""
    - session_id
    - plan_id
    - correlation_id, trace_id
    - planning_strategy
    - created_at, duration_seconds
    
class PlanStateMachine:
    """Plan lifecycle state machine."""
    - current_state (DRAFT → ACTIVE → COMPLETED)
    - valid_transitions()
    - on_enter_state()
    - on_exit_state()
    
class PlanRecovery:
    """Plan failure recovery."""
    - save_checkpoint()
    - recover_from_checkpoint()
    - rollback_to_version()
```

**Integration Points:**
- PlanContext already in models (use as-is)
- PlanSession already in models (use as-is)
- PlanVersion already in models (use as-is)
- AuditRecord already in models (use as-is)

### Priority 2: Task 7 - Resource Management
**Estimated:** 400-500 lines, 2-3 hours

**Create:** `agents/resource_manager.py`

**Key Classes:**
```python
class ResourceRegistry:
    """Central resource registry."""
    - register_resource()
    - allocate_resource()
    - check_conflicts()
    - get_available()
    
class ResourceOptimizer:
    """Resource allocation optimization."""
    - optimize_allocation()
    - find_alternatives()
    - compute_utilization()
    
class FutureResourceProvider:
    """Integration point for external resources."""
    - async fetch_resources()
    - validate_availability()
```

**Models Already Exist:**
- ResourceRequirement
- ResourceAllocation
- ResourceProfile

### Priority 3: Task 8 - Execution Monitoring
**Estimated:** 350-400 lines, 2-3 hours

**Create:** `agents/execution_monitor.py`

**Key Classes:**
```python
class ExecutionMonitor:
    """Monitor task execution and progress."""
    - track_task_state()
    - update_progress()
    - detect_blocked_tasks()
    - handle_failures()
    
class ProgressCalculator:
    """Calculate plan progress metrics."""
    - compute_overall_progress()
    - estimate_completion_time()
    - calculate_task_status_distribution()
```

**Models Already Exist:**
- ExecutionProgress
- TaskStatus

---

## Implementation Guidelines

### Code Style Consistency

All new components should follow patterns established in completed components:

```python
# 1. Import organization
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum

from planning_models import (
    # List all imports from models
)

logger = logging.getLogger(__name__)

# 2. Class structure
class MyComponent:
    """Docstring with purpose."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize with config dict."""
        self.config = config or {}
        self.version = "1.0.0"
        logger.info("Component initialized", extra={"version": self.version})
    
    async def public_method(self) -> ReturnType:
        """Main public method with docstring."""
        pass
    
    def _private_method(self) -> None:
        """Private helper methods start with underscore."""
        pass

# 3. Error handling
try:
    result = await operation()
except ValueError as e:
    logger.error("Operation failed", extra={"error": str(e)})
    raise ValueError(f"Clear error message: {e}") from e

# 4. Logging
logger.info(
    "Event happened",
    extra={
        "id": some_id,
        "status": status.value,
        "count": len(items),
    },
)

# 5. Configuration
self.max_retries = self.config.get("max_retries", 3)
self.timeout = self.config.get("timeout", 30.0)
```

### Testing Patterns

For each new component, create corresponding test file:

```python
# tests/test_planning_session.py
import pytest
from agents.planning_session import PlanningSession

@pytest.fixture
def session():
    return PlanningSession(config={})

@pytest.mark.asyncio
async def test_create_session(session):
    """Test session creation."""
    result = await session.create_session(plan_id="123")
    assert result.session_id is not None
    assert result.plan_id == "123"

@pytest.mark.asyncio
async def test_state_transitions(session):
    """Test state machine transitions."""
    session.transition_to("ACTIVE")
    assert session.current_state == "ACTIVE"
    
    with pytest.raises(ValueError):
        session.transition_to("DRAFT")  # Invalid backward transition
```

### Configuration Pattern

Add section to planned `config/planning_config.yaml`:

```yaml
planning_session:
  max_session_duration_hours: 24
  checkpoint_interval_minutes: 15
  enable_recovery: true
  recovery_retention_days: 30

resource_management:
  max_concurrent_allocations: 10
  resource_utilization_target: 0.85
  enable_future_providers: false

execution_monitoring:
  progress_update_interval_seconds: 5
  blocked_task_threshold_minutes: 30
  failure_threshold_count: 3
```

---

## Integration with PlanningAgent

When integrating all components into `planning_agent.py`:

### Current PlanningAgent Methods (PRESERVE)
```python
async def initialize(self)
async def create_plan(goal, timeframe, constraints, context, metadata)
async def update_milestone(plan_id, milestone_id, status)
async def replan(plan_id, goal, timeframe, constraints, context)
async def execute_task(task)
```

### New Methods to Add
```python
# From GoalManager
async def create_goal(goal_title, category, priority, parent_id, deadline, owner)
async def add_goal_dependency(source_id, target_id)
async def add_goal_constraint(goal_id, constraint_name, constraint_type)

# From TaskDecomposer
async def decompose_goal_with_alternatives(goal, strategy)
async def select_optimal_plan(plans)

# From PlanValidator
async def validate_plan(plan, constraints, resources)

# From RiskAnalyzer
async def analyze_plan_risks(goal, htn, constraints)

# From remaining components
async def manage_plan_session(plan_id, session_id)
async def allocate_resources(task_id, resources)
async def monitor_execution(plan_id)
```

### Initialization in PlanningAgent
```python
async def initialize(self):
    await super().initialize()
    
    # Initialize all engines
    self.goal_manager = GoalManager(config)
    self.task_decomposer = TaskDecomposer(config)
    self.plan_validator = PlanValidator(config)
    self.risk_analyzer = RiskAnalyzer(config)
    self.planning_session = PlanningSession(config)  # When created
    self.resource_manager = ResourceManager(config)  # When created
    self.execution_monitor = ExecutionMonitor(config)  # When created
    
    logger.info("Planning Agent initialized with production engines")
```

---

## Common Patterns to Follow

### Pattern 1: Async Operations with Error Handling
```python
async def critical_operation(self, param: str) -> Dict[str, Any]:
    """Perform critical operation with comprehensive error handling."""
    try:
        logger.info("Operation starting", extra={"param": param})
        result = await self._do_work(param)
        logger.info("Operation completed", extra={"result_id": result.get("id")})
        return result
    except ValueError as e:
        logger.error("Invalid parameter", extra={"error": str(e)})
        raise ValueError(f"Invalid parameter: {e}") from e
    except Exception as e:
        logger.error("Unexpected error", extra={"error": str(e)})
        raise RuntimeError(f"Operation failed: {e}") from e
```

### Pattern 2: Configuration with Defaults
```python
class MyComponent:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.param1 = self.config.get("param1", "default_value")
        self.param2 = int(self.config.get("param2", 10))
        self.param3 = float(self.config.get("param3", 0.5))
        
        # Validate bounds
        if self.param2 < 0 or self.param2 > 100:
            raise ValueError(f"param2 must be 0-100, got {self.param2}")
```

### Pattern 3: Metrics Collection
```python
async def get_stats(self) -> Dict[str, Any]:
    """Get component statistics for monitoring."""
    return {
        "version": self.version,
        "total_operations": len(self.history),
        "success_rate": self._calculate_success_rate(),
        "average_duration_ms": self._calculate_avg_duration(),
        "last_error": self.last_error,
    }
```

---

## File Organization

```
/vercel/share/v0-project/agents/

# Phase 6 Files (COMPLETED)
planning_models.py          ← All data structures
goal_manager.py             ← Goal management
task_decomposer.py          ← HTN & decomposition
plan_validator.py           ← Validation & risk

# Phase 6 Files (IN PROGRESS)
planning_session.py         ← Next: Session management
resource_manager.py         ← Next: Resource management
execution_monitor.py        ← Next: Execution tracking

# Phase 6 Files (TO CREATE)
planning_agent.py           ← Update: Integrate all components

# Tests (TO CREATE)
tests/test_planning_engine.py       ← Comprehensive tests
tests/test_goal_manager.py
tests/test_task_decomposer.py
tests/test_plan_validator.py
tests/test_planning_session.py
tests/test_resource_manager.py

# Configuration (TO CREATE)
config/planning_config.yaml         ← All thresholds & settings
```

---

## Dependency Graph

Recommended implementation order based on dependencies:

```
1. ✓ planning_models.py       (no dependencies)
   ↓
2. ✓ goal_manager.py          (uses models)
   ↓
3. ✓ task_decomposer.py       (uses models)
   ↓
4. ✓ plan_validator.py        (uses models + decomposer)
   ↓
5. → planning_session.py       (uses models + validator)
   ↓
6. → resource_manager.py       (uses models + session)
   ↓
7. → execution_monitor.py      (uses models + session)
   ↓
8. planning_agent.py           (integrates all + base agent)
   ↓
9. tests/*                     (test all components)
   ↓
10. config/planning_config.yaml (configuration)
```

---

## Verification Checklist for Each Component

Before moving to next task, verify:

- [ ] All docstrings present
- [ ] Type hints 95%+ complete
- [ ] Configuration-driven (no hardcoded values)
- [ ] Comprehensive error handling
- [ ] Structured logging throughout
- [ ] No breaking changes to BaseAgent
- [ ] Models can serialize to JSON
- [ ] Test fixtures created
- [ ] 85%+ test coverage target
- [ ] Performance within spec

---

## Common Pitfalls to Avoid

1. **Hardcoded Values**
   - ❌ `if count > 50:` 
   - ✓ `if count > self.config.get("max_items", 50):`

2. **Missing Error Handling**
   - ❌ `result = await operation()`
   - ✓ `try: result = await operation() except: handle_error()`

3. **Blocking Operations**
   - ❌ `time.sleep(1)`
   - ✓ `await asyncio.sleep(1)`

4. **Unlogged Critical Operations**
   - ❌ `return self._calculate()` 
   - ✓ `result = self._calculate(); logger.info(...); return result`

5. **Type Hints Missing**
   - ❌ `def process(data):`
   - ✓ `def process(self, data: Dict[str, Any]) -> List[str]:`

---

## Performance Targets

- Goal creation: <50ms
- HTN decomposition: <100ms
- Plan validation: <50ms
- Risk analysis: <200ms
- Resource allocation: <100ms
- Session checkpoint: <20ms

---

## Success Indicators

When implementation is on track:
- [ ] All 11 tasks completed
- [ ] 2,500+ lines of production code
- [ ] 85%+ test coverage
- [ ] Zero breaking changes
- [ ] All performance targets met
- [ ] Full documentation
- [ ] Backward compatibility verified
- [ ] Integration tests passing

---

## Questions & Clarifications

If you need clarification on:
- **Architecture:** Refer to `PHASE6_PLANNING_ENGINE_ANALYSIS.md`
- **Models:** Reference `PHASE6_COMPONENT_SUMMARY.md`
- **Implementation:** Check completed components for patterns
- **Integration:** Review `BaseAgent` contract in `base_agent.py`
- **Configuration:** Look at `config/orchestrator_config.yaml`

---

## Final Notes

This Phase 6 implementation maintains 100% backward compatibility while adding comprehensive production-grade planning capabilities. The foundation is solid—focus on implementation consistency and thorough testing for the remaining components.

Good luck with the continuation! 🚀

---

**Document:** Phase 6 Continuation Guide v1.0  
**Created:** August 3, 2026  
**Status:** Ready for next implementation phase
