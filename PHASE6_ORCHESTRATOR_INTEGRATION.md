# Phase 6 Orchestrator Integration Guide

**Purpose:** Complete integration of all Phase 6 Planning Engine components with existing orchestrator  
**Target:** Update PlanningAgent and create production-ready API surface  
**Status:** Integration specification ready for implementation  

---

## Integration Architecture

### Component Integration Map

```
BaseAgent (existing)
    ↓
PlanningAgent (enhanced)
    ├── GoalManager
    ├── TaskDecomposer  
    ├── PlanValidator
    ├── RiskAnalyzer
    ├── PlanningSessionManager
    ├── PlanCheckpointManager
    ├── PlanVersionManager
    ├── PlanAuditTrail
    ├── ResourceRegistry
    ├── ResourceAllocator
    ├── ResourcePlanner
    ├── DynamicReplanner
    └── ExecutionMonitor
        ↓
    Message Broker ← Coordination
        ↓
    [DecisionAgent, ReasoningAgent, MemoryAgent]
```

---

## PlanningAgent Enhancements

### Phase 1: Initialize Engines

```python
class PlanningAgent(BaseAgent):
    async def initialize(self):
        await super().initialize()
        
        # Load configuration
        config = self.config or self._load_planning_config()
        
        # Initialize all engines
        self.goal_manager = GoalManager(config.get("goals", {}))
        self.task_decomposer = TaskDecomposer(config.get("decomposer", {}))
        self.plan_validator = PlanValidator(config.get("validator", {}))
        self.risk_analyzer = RiskAnalyzer(config.get("risks", {}))
        
        self.session_manager = PlanningSessionManager(config.get("sessions", {}))
        self.checkpoint_manager = PlanCheckpointManager(config.get("checkpoints", {}))
        self.version_manager = PlanVersionManager(config.get("versions", {}))
        self.audit_trail = PlanAuditTrail(config.get("audit", {}))
        
        self.resource_registry = ResourceRegistry(config.get("resources", {}))
        self.resource_allocator = ResourceAllocator(
            self.resource_registry,
            config.get("allocation", {})
        )
        self.resource_planner = ResourcePlanner(config.get("planning", {}))
        
        self.dynamic_replanner = DynamicReplanner(config.get("replanning", {}))
        self.execution_monitor = ExecutionMonitor(config.get("monitoring", {}))
        
        logger.info("PlanningAgent initialized with all engines")
```

### Phase 2: Extend create_plan Method

```python
async def create_plan(
    self,
    goal: str,
    timeframe: str = None,
    constraints: List[str] = None,
    context: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Enhanced plan creation using all production engines.
    Maintains backward compatibility with existing interface.
    """
    # Parse inputs
    constraints = [self._parse_constraint(c) for c in (constraints or [])]
    context = context or {}
    metadata = metadata or {}
    
    # Create session
    session = await self.session_manager.create_session(
        plan_id=str(uuid.uuid4()),
        request_id=context.get("request_id"),
        correlation_id=context.get("correlation_id"),
        trace_id=context.get("trace_id"),
        planning_strategy="goal_decomposition",
    )
    
    # Create goal node
    goal_node = await self.goal_manager.create_goal(
        goal_title=goal,
        goal_description=context.get("goal_description", goal),
        category=self._infer_category(goal),
        priority=self._infer_priority(metadata),
        deadline=metadata.get("deadline"),
        owner=metadata.get("owner", "planning_agent"),
        success_criteria=self._extract_success_criteria(goal),
        constraints=constraints,
    )
    
    # Decompose goal into tasks
    htn, alternatives = await self.task_decomposer.decompose_goal(
        goal=goal,
        goal_description=context.get("goal_description", goal),
        constraints=constraints,
        timeframe=timeframe,
        include_alternatives=True,
    )
    
    # Select optimal plan if alternatives exist
    if alternatives:
        primary_htn = await self.task_decomposer.select_optimal_plan([htn] + alternatives)
    else:
        primary_htn = htn
    
    # Plan resources
    resource_profile = await self.resource_planner.estimate_resource_requirements(
        goal=goal,
        tasks=list(primary_htn.all_tasks.values()),
        constraints=[c.name for c in constraints],
    )
    
    # Validate plan
    validation = await self.plan_validator.validate_plan(
        plan_id=session.plan_id,
        htn=primary_htn,
        constraints=constraints,
        resources=resource_profile,
        goal=goal,
    )
    
    # Analyze risks
    risks = await self.risk_analyzer.analyze_risks(
        goal=goal,
        htn=primary_htn,
        constraints=constraints,
        resources=resource_profile,
    )
    
    # Create production plan
    plan = ProductionPlan(
        plan_id=session.plan_id,
        goal_id=goal_node.goal_id,
        goal=goal,
        goal_node=goal_node,
        timeframe=timeframe or "flexible",
        htn=primary_htn,
        all_tasks=primary_htn.all_tasks,
        resource_profile=resource_profile,
        constraints=constraints,
        validation_result=validation,
        risks=risks,
        plan_context=self._build_plan_context(context),
        plan_session=session,
    )
    
    # Store in active plans
    self.active_plans[plan.plan_id] = plan
    
    # Broadcast planning completion
    await self.broadcast_message("plan_created", {
        "plan_id": plan.plan_id,
        "goal": goal,
        "task_count": len(plan.all_tasks),
        "validation_status": validation.status.value,
    })
    
    # Return in legacy format for backward compatibility
    return plan.to_legacy_dict()
```

### Phase 3: New Planning Management Methods

```python
# Goal Management
async def create_goal(self, goal_title: str, parent_id: Optional[str] = None, **kwargs):
    return await self.goal_manager.create_goal(goal_title, parent_goal_id=parent_id, **kwargs)

async def add_goal_dependency(self, source_id: str, target_id: str):
    await self.goal_manager.add_goal_dependency(source_id, target_id)

# Resource Management  
async def allocate_resources(self, plan_id: str, task_id: str, requirements: List):
    plan = self.active_plans.get(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    
    task = plan.all_tasks.get(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    
    allocations = []
    for req in requirements:
        alloc = await self.resource_allocator.allocate_resource(
            task_id, req
        )
        if alloc:
            allocations.append(alloc)
    
    return allocations

# Dynamic Replanning
async def handle_goal_change(self, plan_id: str, new_goal: str):
    plan = self.active_plans.get(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    
    return await self.dynamic_replanner.handle_goal_change(
        plan, new_goal, reason="goal_change"
    )

async def handle_task_failure(self, plan_id: str, task_id: str, reason: str):
    plan = self.active_plans.get(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    
    return await self.dynamic_replanner.handle_task_failure(
        plan, task_id, reason
    )

# Execution Monitoring
async def update_task_status(self, plan_id: str, task_id: str, status: str):
    plan = self.active_plans.get(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    
    new_status = TaskStatus(status)
    await self.execution_monitor.update_task_status(plan, task_id, new_status)
    
    return plan.to_legacy_dict()

async def get_execution_report(self, plan_id: str):
    plan = self.active_plans.get(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    
    return await self.execution_monitor.generate_execution_report(plan)

# Plan Management
async def get_plan_details(self, plan_id: str):
    plan = self.active_plans.get(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    
    return plan.to_dict()

async def checkpoint_plan(self, plan_id: str, reason: str = "manual"):
    plan = self.active_plans.get(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    
    checkpoint = await self.checkpoint_manager.create_checkpoint(
        plan, reason=reason
    )
    return checkpoint

async def recover_plan(self, plan_id: str, checkpoint_id: Optional[str] = None):
    checkpoint = await self.checkpoint_manager.recover_from_checkpoint(
        plan_id, checkpoint_id
    )
    
    # Deserialize plan from snapshot
    plan_data = checkpoint["plan_snapshot"]
    # In production, deserialize into ProductionPlan object
    
    return plan_data
```

---

## Message Broker Integration

### Message Types

```python
# Planning messages
planning_messages = {
    "plan_created": {
        "plan_id": str,
        "goal": str,
        "task_count": int,
        "validation_status": str,
    },
    "plan_replanned": {
        "plan_id": str,
        "reason": str,
        "version": int,
    },
    "task_status_changed": {
        "plan_id": str,
        "task_id": str,
        "old_status": str,
        "new_status": str,
    },
    "goal_changed": {
        "plan_id": str,
        "old_goal": str,
        "new_goal": str,
    },
}
```

### Coordination with DecisionAgent

```python
async def request_decision_on_plan(
    self,
    plan_id: str,
    decision_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Request decision agent to score plan options."""
    plan = self.active_plans.get(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    
    # Send request through message broker
    await self._message_broker.send_message(
        sender_agent_id=self.agent_id,
        recipient_agent_id="decision_agent",
        message_type="decision_request",
        content={
            "plan_id": plan_id,
            "context": decision_context,
            "options": [
                {"option_id": "proceed", "confidence": 0.7},
                {"option_id": "replan", "confidence": 0.3},
            ],
        },
        correlation_id=plan.plan_context.correlation_id,
        priority="HIGH",
    )
    
    # Wait for response (with timeout)
    response = await asyncio.wait_for(
        self._wait_for_decision_response(plan_id),
        timeout=30.0
    )
    
    return response
```

### Coordination with ReasoningAgent

```python
async def request_reasoning_justification(
    self,
    plan_id: str,
    question: str,
) -> Dict[str, Any]:
    """Request reasoning for plan justification."""
    plan = self.active_plans.get(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    
    # Send request through message broker
    await self._message_broker.send_message(
        sender_agent_id=self.agent_id,
        recipient_agent_id="reasoning_agent",
        message_type="reasoning_request",
        content={
            "plan_id": plan_id,
            "question": question,
            "context": plan.plan_context.to_dict(),
        },
        correlation_id=plan.plan_context.correlation_id,
        priority="NORMAL",
    )
    
    # Wait for response
    response = await asyncio.wait_for(
        self._wait_for_reasoning_response(plan_id),
        timeout=30.0
    )
    
    return response
```

---

## Configuration File

### config/planning_config.yaml

```yaml
planning:
  version: "1.0.0"
  enabled: true

goals:
  max_goal_hierarchy_depth: 5
  enable_dependencies: true
  max_constraints_per_goal: 20

decomposer:
  max_decomposition_depth: 5
  max_tasks_per_plan: 50
  parallel_task_limit: 5
  effort_weights:
    low: 1
    medium: 2
    high: 4
    critical: 8

validator:
  enable_cycle_detection: true
  enable_resource_validation: true
  enable_deadline_validation: true
  confidence_threshold: 0.55

risks:
  enable_risk_analysis: true
  risk_threshold: 0.65
  max_identified_risks: 15

sessions:
  max_session_duration_hours: 24
  checkpoint_interval_minutes: 15
  enable_recovery: true
  recovery_retention_days: 30

resources:
  enable_future_providers: false
  max_concurrent_allocations: 10
  resource_utilization_target: 0.85

monitoring:
  blocked_task_threshold_minutes: 30
  enable_stall_detection: true
  report_interval_minutes: 15

replanning:
  enable_incremental_replanning: true
  max_replans_per_plan: 10
```

---

## API Endpoints (if HTTP-based)

```python
# GET /api/plans/{plan_id}
# Get plan details

# POST /api/plans
# Create new plan

# POST /api/plans/{plan_id}/tasks/{task_id}/status
# Update task status

# GET /api/plans/{plan_id}/execution-report
# Get execution report

# POST /api/plans/{plan_id}/checkpoint
# Create plan checkpoint

# POST /api/plans/{plan_id}/recover
# Recover from checkpoint

# POST /api/plans/{plan_id}/goals
# Add goal to plan

# POST /api/plans/{plan_id}/resources
# Allocate resources
```

---

## Testing Strategy

### Unit Tests for Each Integration Point

```python
# tests/test_planning_agent_integration.py

class TestPlanningAgentIntegration:
    @pytest.mark.asyncio
    async def test_create_plan_uses_all_engines(self):
        """Verify plan creation uses all new engines."""
        agent = PlanningAgent()
        await agent.initialize()
        
        plan = await agent.create_plan(
            goal="Build new feature",
            constraints=["timeline_constraint"],
        )
        
        assert "plan_id" in plan
        assert "validation" in plan
        assert "risks" in plan
        assert "htn" in plan
        assert "resources" in plan
    
    @pytest.mark.asyncio
    async def test_backward_compatibility(self):
        """Verify backward compatibility with legacy interface."""
        agent = PlanningAgent()
        await agent.initialize()
        
        # Old interface still works
        plan = await agent.create_plan(
            goal="Test goal",
            timeframe="1 week",
        )
        
        # Legacy fields present
        assert "milestones" in plan
        assert "tasks" in plan
        assert "status" in plan
        assert "progress" in plan
```

---

## Migration Path

### Step 1: Add New Methods (No Breaking Changes)
- All new methods are additive
- Existing methods unchanged
- Legacy interface preserved

### Step 2: Gradual Adoption
- New code uses new methods
- Old code continues using legacy methods
- Parallel execution safe

### Step 3: Complete Integration
- Orchestrator fully uses Phase 6 engines
- Comprehensive monitoring in place
- Full production deployment

---

## Success Criteria

✓ All 9 engines initialized and working  
✓ Backward compatibility verified  
✓ Message broker coordination functional  
✓ DecisionAgent integration working  
✓ ReasoningAgent integration working  
✓ MemoryAgent context passing  
✓ Execution monitoring active  
✓ Configuration-driven thresholds  
✓ Production logging throughout  
✓ Error handling comprehensive  

---

## Deployment Checklist

- [ ] All engines tested individually
- [ ] Integration tests passing
- [ ] Backward compatibility verified
- [ ] Message broker properly configured
- [ ] Agent coordination tested
- [ ] Monitoring and logging configured
- [ ] Performance benchmarks acceptable
- [ ] Error handling validated
- [ ] Documentation complete
- [ ] Production deployment ready

---

**Status:** Ready for implementation  
**Estimated Effort:** 4-6 hours  
**Risk Level:** Low (backward compatible)
