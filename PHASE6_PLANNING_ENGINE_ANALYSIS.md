# Phase 6 Planning Engine - Architecture Analysis

**Date:** August 3, 2026  
**Status:** Architecture Assessment Complete  
**Target:** Production-Grade Planning Engine Transformation

---

## 1. EXISTING PLANNING ARCHITECTURE

### 1.1 Current PlanningAgent Implementation

**Location:** `/agents/planning_agent.py`  
**Lines:** ~450  
**Version:** Base implementation (pre-Phase 6)

#### Current Capabilities:
- ✓ Basic goal input processing
- ✓ Goal decomposition into phases (template-driven)
- ✓ HTN (Hierarchical Task Network) structure generation
- ✓ Milestone creation and tracking
- ✓ Basic resource estimation
- ✓ Risk identification
- ✓ Plan validation (basic)
- ✓ Milestone status updates
- ✓ Plan history tracking
- ✓ Replan support
- ✓ Task execution interface

#### Inheritance:
```
BaseAgent (agents/base_agent.py)
    ↓
PlanningAgent (agents/planning_agent.py)
```

### 1.2 BaseAgent Infrastructure

**Location:** `/agents/base_agent.py`  
**Lines:** ~706

#### Provided:
- Agent lifecycle (initialize, shutdown, pause, resume, restart)
- Message queue processing & handlers
- Metrics collection (AgentMetrics dataclass)
- Emotion state management
- Memory integration hooks
- Configuration validation
- Task management

#### Message Types Supported:
- `memory_recall`, `memory_store`
- `emotion_update`, `task_create`
- `decision_request`, `learning_update`
- `perception_input`, `planning_request`
- `creativity_idea`, `health_check`

#### Limitations:
- No planning-specific instrumentation
- Generic message handlers only
- No plan-level metrics collection
- No integration with Decision/Reasoning context

### 1.3 Orchestrator Infrastructure

**Location:** `/orchestrator/`  
**Key Files:**
- `agent_manager.py` — Agent lifecycle & task execution
- `task_scheduler.py` — Task queueing, dispatch, execution
- `agent_communication.py` — Message broker, pub/sub
- `communication_controller.py` — Request/response coordination
- `decision_engine.py` — Decision intelligence (Phase 4)
- `confidence_engine.py` — Confidence scoring (Phase 4)

#### Integration Points:
1. **Message Broker** — Async message queue, routing
2. **Task Scheduler** — Task execution, concurrency management
3. **Agent Manager** — Agent loading, lifecycle, capability registry
4. **Decision Engine** — Option scoring, decision context
5. **Confidence Engine** — Confidence scoring, thresholds

#### Existing Patterns:
- Configuration-driven via YAML (e.g., `agents_config.yaml`)
- Async/await throughout
- Context tracing (request_id, correlation_id, trace_id)
- Execution history tracking
- Metrics collection

### 1.4 Configuration System

**Location:** `/config/`

#### Config Files:
- `agents_config.yaml` — Agent definitions & initialization
- `orchestrator_config.yaml` — Orchestrator settings
- `decision_config.yaml` — Decision engine thresholds
- `reasoning_config.yaml` — Reasoning engine config
- `communication_config.yaml` — Message broker config

#### Pattern:
```yaml
agents:
  planning_agent:
    enabled: true
    type: planning
    config:
      max_planning_depth: 3
      max_task_count: 12
      parallel_task_limit: 3
      confidence_threshold: 0.55
      risk_threshold: 0.65
```

---

## 2. PRODUCTION GAPS IDENTIFIED

### 2.1 Missing Planning Lifecycle Features

**Gap:** No structured plan session/context management

- [ ] Plan session IDs not tracked through execution
- [ ] Plan context not reusable across operations
- [ ] No plan-level correlation tracing
- [ ] Limited audit trail (only basic history)
- [ ] No plan state machine (status transitions not validated)
- [ ] No plan versioning with change tracking
- [ ] No plan recovery on failure

**Gap:** No structured goal management

- [ ] Goals treated as strings, not entities
- [ ] No goal hierarchy (parent/child relationships)
- [ ] No goal dependencies
- [ ] No goal priority/deadline management
- [ ] No goal ownership tracking
- [ ] No goal completion criteria validation
- [ ] No goal archival/lifecycle

### 2.2 Missing Plan Generation Features

**Gap:** Simplistic, template-driven decomposition

- [ ] Hardcoded phases for known patterns
- [ ] No structured goal analysis
- [ ] No constraint-aware decomposition
- [ ] No objective extraction
- [ ] No alternative plan generation
- [ ] No optimal plan selection logic
- [ ] No plan explanation/reasoning attached

**Gap:** Weak validation

- [ ] No dependency cycle detection (only basic check)
- [ ] No duplicate task detection
- [ ] No constraint conflict resolution
- [ ] No deadline conflict analysis
- [ ] No resource feasibility check

### 2.3 Missing Resource Management

**Gap:** Basic resource estimation only

- [ ] No resource catalog or registry
- [ ] No resource conflict detection
- [ ] No future resource provider integration
- [ ] No resource optimization
- [ ] No resource allocation tracking
- [ ] No resource limit enforcement

### 2.4 Missing Risk Analysis

**Gap:** Hardcoded risk patterns

- [ ] Only generic risks returned
- [ ] No probability/impact scoring
- [ ] No risk mitigation planning
- [ ] No fallback plan generation
- [ ] No risk threshold enforcement

### 2.5 Missing Dynamic Replanning

**Gap:** No incremental replanning

- [ ] Must regenerate full plan on changes
- [ ] No partial completion handling
- [ ] No mid-execution goal changes
- [ ] No task failure replanning
- [ ] No deadline adjustment logic

### 2.6 Missing Execution Monitoring

**Gap:** No real-time task tracking

- [ ] No blocked/waiting task detection
- [ ] No execution progress metrics
- [ ] No estimated completion tracking
- [ ] No execution history per plan
- [ ] No failure root cause tracking

### 2.7 Missing Multi-Agent Coordination

**Gap:** No structured coordination with other agents

- [ ] No DecisionAgent integration
- [ ] No ReasoningAgent integration
- [ ] No MemoryAgent context passing
- [ ] No async request/response pairs
- [ ] Direct agent-to-agent calls (violates broker pattern)

### 2.8 Missing Observability

**Gap:** Limited instrumentation

- [ ] No structured planning logs
- [ ] No planning metrics (decomposition time, etc.)
- [ ] No planning confidence tracking
- [ ] No planning ID propagation
- [ ] No plan-level traces

### 2.9 Missing Persistence

**Gap:** In-memory only, no durability

- [ ] No database persistence
- [ ] No recovery on restart
- [ ] No historical plan queries
- [ ] No audit trail queries

### 2.10 Missing Configuration

**Gap:** Hardcoded thresholds & limits

- [ ] max_planning_depth, max_task_count hardcoded in code
- [ ] confidence_threshold, risk_threshold hardcoded
- [ ] No dynamic configuration updates
- [ ] No feature flags

---

## 3. DESIGN DECISIONS FOR PHASE 6

### 3.1 Architecture Principles

1. **Backward Compatibility First**
   - All existing PlanningAgent methods remain unchanged
   - New functionality is additive only
   - BaseAgent contract respected
   - Existing message handlers work as-is

2. **Configuration-Driven**
   - All thresholds externalized to YAML
   - Feature flags for new subsystems
   - Runtime configuration updates supported

3. **Message Broker Pattern**
   - All coordination through message broker
   - No direct agent-to-agent calls
   - Request/response via correlation IDs

4. **Context Propagation**
   - request_id, correlation_id, trace_id throughout
   - Plan context passed through broker
   - Execution context carries all metadata

5. **Observability by Default**
   - Structured logging at every step
   - Metrics collection for all operations
   - Planning IDs in all logs
   - Trace IDs for correlation

### 3.2 New Components Required

#### Data Models (`planning_models.py`)
- `Goal` — Goal entity with hierarchy
- `GoalNode` — Goal tree node
- `Plan` — Typed plan structure
- `PlanVersion` — Version with change tracking
- `PlanSession` — Session context
- `PlanAuditRecord` — Audit trail
- `TaskDecomposition` — Decomposition result
- `ResourceRequirement` — Resource needs
- `RiskAssessment` — Risk with scoring
- `ConstraintViolation` — Constraint check result
- `PlanValidationResult` — Validation report

#### Planning Engine (`planning_engine.py`)
- `GoalAnalyzer` — Extract objectives, constraints
- `TaskDecomposer` — HTN-based decomposition
- `PlanValidator` — Comprehensive validation
- `RiskAnalyzer` — Risk assessment & scoring
- `ResourcePlanner` — Resource estimation & allocation
- `ReplanningEngine` — Incremental replanning
- `ExecutionMonitor` — Task tracking & progress
- `PlanningSession` — Session lifecycle

#### PlanningAgent Extensions (`planning_agent.py` v2)
- New methods built on planning engine
- Backward-compatible interface
- Enhanced error handling
- Configuration-driven thresholds
- Multi-agent coordination
- Comprehensive metrics
- Plan persistence hooks

#### Configuration (`planning_config.yaml`)
- Planning depth/breadth limits
- Confidence/risk thresholds
- Resource profiles
- Validation policies
- Feature flags

---

## 4. IMPLEMENTATION STRATEGY

### Phase 6.1: Data Models & Schemas (TASK 2)
- Create `planning_models.py` with all data structures
- Add type hints for IDE support
- Create serialization/deserialization
- No logic changes to existing code

### Phase 6.2: Goal Management (TASK 3)
- Create `goal_manager.py` with goal CRUD
- Implement goal hierarchy (parent/child)
- Add goal dependencies
- Integrate with PlanningAgent via new methods

### Phase 6.3: HTN & Decomposition (TASK 4)
- Create `task_decomposer.py` with production decomposition
- Implement constraint-aware decomposition
- Support alternative plan generation
- Add optimal plan selection

### Phase 6.4: Validation & Risk (TASK 5)
- Create `plan_validator.py` with comprehensive checks
- Create `risk_analyzer.py` with scoring
- Integrate into plan creation flow
- Generate structured validation results

### Phase 6.5: Context & Lifecycle (TASK 6)
- Create `planning_session.py` for session management
- Implement plan state machine
- Add version history tracking
- Enable plan recovery

### Phase 6.6: Resource Management (TASK 7)
- Create `resource_manager.py`
- Implement resource registry
- Add allocation tracking
- Support future providers

### Phase 6.7: Dynamic Replanning (TASK 8)
- Extend `task_decomposer.py` with incremental mode
- Handle partial completion
- Support goal/constraint changes
- No full regeneration if possible

### Phase 6.8: Execution Monitoring (TASK 9)
- Create `execution_monitor.py`
- Track task states (running, blocked, waiting)
- Compute progress metrics
- Handle failure scenarios

### Phase 6.9: Orchestrator Integration (TASK 10)
- Extend PlanningAgent to use all engines
- Implement message-based coordination
- Add DecisionAgent/ReasoningAgent calls
- Maintain backward compatibility

### Phase 6.10: Testing & Validation (TASK 11)
- Create comprehensive test suite
- Unit tests for each component
- Integration tests with orchestrator
- Backward compatibility verification

---

## 5. BACKWARD COMPATIBILITY CHECKLIST

### Must Preserve:
- [ ] `PlanningAgent.__init__(agent_id)` signature
- [ ] `await initialize()` behavior
- [ ] `async def create_plan(goal, timeframe, constraints, context, metadata)` signature
- [ ] `async def update_milestone(plan_id, milestone_id, status)` signature
- [ ] `async def replan(plan_id, goal, timeframe, constraints, context)` signature
- [ ] `async def execute_task(task)` behavior
- [ ] All message handlers in BaseAgent
- [ ] AgentMetrics collection
- [ ] State updates in _update_state()
- [ ] Plan JSON structure (for API compatibility)

### Safe to Extend:
- [ ] Add new methods to PlanningAgent
- [ ] Add new fields to plan dict (backward compatible)
- [ ] Add new message types
- [ ] Add new metrics
- [ ] Add new state fields

---

## 6. NEXT STEPS

1. ✓ Architecture Analysis Complete
2. → Create production data models
3. → Implement goal management
4. → Build task decomposition engine
5. → Add validation & risk analysis
6. → Implement context & lifecycle
7. → Add resource management
8. → Implement dynamic replanning
9. → Build execution monitor
10. → Integrate with orchestrator
11. → Comprehensive testing

---

## 7. RISK MITIGATION

### Risk: Breaking existing API
**Mitigation:** All changes are additive; existing methods unchanged

### Risk: Performance degradation
**Mitigation:** Async/await throughout; bounded history; efficient algorithms

### Risk: Configuration complexity
**Mitigation:** Sensible defaults; clear documentation; feature flags

### Risk: Orchestrator integration issues
**Mitigation:** Message broker pattern ensures loose coupling; gradual integration

---

## 8. SUCCESS CRITERIA

Phase 6 complete when:
- ✓ All 11 tasks completed
- ✓ Backward compatibility verified (100%)
- ✓ 85%+ test coverage
- ✓ All production gaps addressed
- ✓ Configuration-driven throughout
- ✓ Zero breaking changes
- ✓ Comprehensive observability
- ✓ Ready for integration tests with other agents
