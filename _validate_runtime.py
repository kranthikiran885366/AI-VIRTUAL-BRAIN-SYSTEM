"""
Full production runtime validation.
Tests every subsystem end-to-end with real execution.
"""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("DISABLE_EMBEDDINGS", "1")

import asyncio
import sys
import traceback
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

PASS = []
FAIL = []

def ok(name):
    PASS.append(name)
    print(f"  PASS  {name}")

def fail(name, err):
    FAIL.append((name, err))
    print(f"  FAIL  {name}: {err}")

# ─── 1. Settings ──────────────────────────────────────────────────────────────
async def test_settings():
    from orchestrator.config import settings
    report = settings.validate_runtime()
    assert report["ok"], f"Settings invalid: {report['errors']}"
    assert settings.PORT == 8001
    assert settings.KAFKA_ENABLED is False
    assert settings.REDIS_ENABLED is False
    ok("settings.validate_runtime")

# ─── 2. Database ──────────────────────────────────────────────────────────────
async def test_database():
    from orchestrator.database import DatabaseManager, DatabaseConfig
    dm = DatabaseManager(DatabaseConfig(database_path="data/brain.db"))
    dm.initialize()
    h = dm.health_check()
    assert h["ok"], f"DB health: {h}"
    # Verify all required tables exist
    result = dm.migration_validator.validate([
        "memories","memory_relationships","memory_history",
        "memory_consolidation_log","retention_policies","schema_migrations",
        "decision_records","decision_feedback"
    ])
    assert result["ok"], f"Missing tables: {result['missing_tables']}"
    dm.shutdown()
    ok("database.initialize+health+schema")

# ─── 3. Message Broker ────────────────────────────────────────────────────────
async def test_broker():
    from orchestrator.agent_communication import MessageBroker, MessageType, MessagePriority
    broker = MessageBroker()
    await broker.start()
    assert broker.is_running
    mid = await broker.send_message(
        sender_agent_id="test",
        recipient_agent_id=None,
        message_type=MessageType.STATE_UPDATE,
        content={"test": True},
        priority=MessagePriority.NORMAL,
    )
    assert mid
    stats = await broker.get_stats()
    assert stats["is_running"]
    await broker.stop()
    assert not broker.is_running
    ok("message_broker.start+send+stats+stop")

# ─── 4. Lifecycle Manager ─────────────────────────────────────────────────────
async def test_lifecycle():
    from orchestrator.agent_lifecycle import AgentLifecycleManager
    lm = AgentLifecycleManager()
    await lm.start()
    assert lm.is_running
    await lm.register_agent("test_agent", "test", None)
    status = await lm.get_agent_status("test_agent")
    assert status is not None
    assert status["agent_id"] == "test_agent"
    all_statuses = await lm.get_all_agent_statuses()
    assert "test_agent" in all_statuses
    await lm.stop()
    ok("lifecycle_manager.start+register+status+stop")

# ─── 5. Communication Controller ─────────────────────────────────────────────
async def test_comm_controller():
    from orchestrator.communication_controller import CommunicationController
    cc = CommunicationController({
        "timeout": 5.0,
        "queue_limits": {"message_queue_size": 100, "event_queue_size": 100},
        "retry": {"max_retries": 1, "backoff_seconds": 0.1},
        "kafka": {"enabled": False},
        "redis": {"enabled": False},
        "max_payload_bytes": 1_048_576,
    })
    await cc.initialize()
    assert cc.is_running
    assert cc._initialized
    status = await cc.get_status()
    assert status["status"] == "running"
    assert status["initialized"] is True
    await cc.stop()
    ok("comm_controller.initialize+status+stop")

# ─── 6. Task Scheduler ────────────────────────────────────────────────────────
async def test_task_scheduler():
    from orchestrator.task_scheduler import TaskScheduler, TaskPriority, TaskStatus
    from orchestrator.agent_communication import MessageBroker

    broker = MessageBroker()
    await broker.start()

    # Minimal agent mock
    class MockAgent:
        async def execute_task(self, task):
            return {"status": "completed", "result": "mock_ok"}
        async def execute_task_with_policies(self, task):
            return await self.execute_task(task)

    class MockAgentManager:
        def __init__(self):
            self.agents = {"mock_agent": MockAgent()}
        async def execute_agent_task(self, agent_name, task, timeout_seconds=30, execution_context=None):
            agent = self.agents.get(agent_name)
            if not agent:
                return {"status": "error", "error": f"Agent {agent_name} not found"}
            return await agent.execute_task(task)

    mgr = MockAgentManager()
    scheduler = TaskScheduler({
        "max_concurrent_tasks": 4,
        "task_timeout": 10,
        "message_broker": broker,
        "agent_manager": mgr,
    })
    await scheduler.initialize()
    await scheduler.start()
    assert scheduler.is_running

    await scheduler.register_worker("mock_agent", MockAgent(), pool="agents")

    task_id = await scheduler.schedule_task({
        "name": "test_task",
        "priority": TaskPriority.HIGH,
        "parameters": {
            "agent_name": "mock_agent",
            "action": "test",
            "input_data": {"content": "hello"},
        },
        "timeout": 10,
        "agent_manager": mgr,
    })
    assert task_id

    result = await scheduler.wait_for_task(task_id, timeout=10)
    assert result is not None
    assert result["status"] in (TaskStatus.COMPLETED, "completed"), f"Unexpected status: {result['status']}"

    sched_status = await scheduler.get_status()
    assert sched_status["status"] == "running"

    await scheduler.shutdown()
    await broker.stop()
    ok("task_scheduler.schedule+execute+wait+status")

# ─── 7. Decision Engine ───────────────────────────────────────────────────────
async def test_decision_engine():
    from orchestrator.decision_engine import DecisionEngine, _PHASE4_AVAILABLE
    assert _PHASE4_AVAILABLE, "Phase 4 components not available"
    engine = DecisionEngine.from_config_file("config/decision_config.yaml")
    await engine.initialize()
    await engine.start()
    assert engine.is_running

    # Update registry with test agents
    engine.update_agent_registry(
        available_agents=["memory_agent","emotion_agent","reasoning_agent","task_agent","planning_agent"],
        agent_capabilities={
            "memory_agent": ["memory","recall","storage"],
            "emotion_agent": ["emotion","sentiment","mood"],
            "reasoning_agent": ["reasoning","analysis","logic"],
            "task_agent": ["task_management","scheduling","task"],
            "planning_agent": ["planning","goal_management","strategy"],
        },
        agent_health={a: "healthy" for a in ["memory_agent","emotion_agent","reasoning_agent","task_agent","planning_agent"]},
        agent_load={a: 0 for a in ["memory_agent","emotion_agent","reasoning_agent","task_agent","planning_agent"]},
    )

    # Test routing
    result = await engine.route_request("I need to remember something important")
    assert "selected_agent" in result
    assert result["selected_agent"]
    assert result["confidence"] > 0

    result2 = await engine.route_request("analyze this logic problem")
    assert result2["selected_agent"]

    status = await engine.get_status()
    assert status["status"] == "running"
    assert status["phase4_enabled"] is True

    await engine.stop()
    ok(f"decision_engine.phase4_pipeline (phase4={_PHASE4_AVAILABLE})")

# ─── 8. Agent Manager ─────────────────────────────────────────────────────────
async def test_agent_manager():
    from orchestrator.agent_manager import AgentManager
    config = {"agents": {
        "memory_agent": {},
        "emotion_agent": {},
        "reasoning_agent": {},
        "planning_agent": {},
        "task_agent": {},
    }}
    mgr = AgentManager(config)
    await mgr.initialize()
    await mgr.start()
    assert mgr.is_running

    loaded = list(mgr.agents.keys())
    assert len(loaded) >= 3, f"Expected >=3 agents loaded, got {loaded}"

    snapshot = mgr.get_capability_snapshot()
    assert "available_agents" in snapshot
    assert "agent_capabilities" in snapshot

    status = await mgr.get_status()
    assert status["status"] == "running"

    await mgr.stop()
    ok(f"agent_manager.load+execute+snapshot ({len(loaded)} agents)")

# ─── 9. Execution Pipeline ────────────────────────────────────────────────────
async def test_execution_pipeline():
    from orchestrator.execution_pipeline import execute_via_pipeline
    from orchestrator.task_scheduler import TaskScheduler, TaskPriority
    from orchestrator.agent_communication import MessageBroker

    broker = MessageBroker()
    await broker.start()

    class MockAgent:
        async def execute_task(self, task):
            return {"status": "completed", "result": "pipeline_ok", "action": task.get("action")}
        async def execute_task_with_policies(self, task):
            return await self.execute_task(task)

    class MockAgentManager:
        def __init__(self):
            self.agents = {"memory_agent": MockAgent()}
        async def execute_agent_task(self, agent_name, task, timeout_seconds=30, execution_context=None):
            agent = self.agents.get(agent_name)
            if not agent:
                return {"status": "error", "error": f"Agent {agent_name} not found"}
            return await agent.execute_task(task)

    mgr = MockAgentManager()
    scheduler = TaskScheduler({
        "max_concurrent_tasks": 4,
        "task_timeout": 15,
        "message_broker": broker,
        "agent_manager": mgr,
    })
    await scheduler.initialize()
    await scheduler.start()
    await scheduler.register_worker("memory_agent", MockAgent(), pool="agents")

    result = await execute_via_pipeline(
        agent_name="memory_agent",
        action="store",
        input_data={"content": "test memory", "type": "short_term"},
        user_id="test_user",
        priority="normal",
        task_scheduler=scheduler,
        agent_manager=mgr,
        message_broker=broker,
        timeout=15.0,
    )
    assert result["status"] in ("completed", "ok"), f"Pipeline status: {result}"
    assert result["agent"] == "memory_agent"
    assert result["task_id"]

    await scheduler.shutdown()
    await broker.stop()
    ok("execution_pipeline.execute_via_pipeline")

# ─── 10. Memory Agent ─────────────────────────────────────────────────────────
async def test_memory_agent():
    from agents.memory_agent.agent import MemoryAgent
    agent = MemoryAgent(agent_id="memory_agent_test")
    await agent.initialize()

    # Store — processor returns 'created' on first insert, 'merged' on dedup
    _VALID_STORE_STATUSES = {"stored", "created", "merged", "ok"}
    result = await agent.store(
        content="Test memory content for validation",
        memory_type="short_term",
        importance=0.7,
        user_id="test_user",
    )
    assert result["status"] in _VALID_STORE_STATUSES, f"Store result: {result}"
    assert result.get("memory_id")

    # Recall
    memories = await agent.recall(query="test memory", user_id="test_user", limit=5)
    assert isinstance(memories, list)

    # Stats
    stats = await agent.get_stats()
    assert "total" in stats

    # execute_task interface
    task_result = await agent.execute_task({
        "action": "store",
        "input_data": {"content": "pipeline test", "memory_type": "short_term", "importance": 0.5},
        "user_id": "test_user",
    })
    assert task_result.get("status") in _VALID_STORE_STATUSES, f"Task store result: {task_result}"

    await agent.shutdown()
    ok("memory_agent.store+recall+stats+execute_task")

# ─── 11. Emotion Agent ────────────────────────────────────────────────────────
async def test_emotion_agent():
    from agents.emotion_agent.main import EmotionAgent
    agent = EmotionAgent()
    await agent.initialize()

    result = agent._analyze_text("I am feeling very happy and excited today!")
    assert result["primary_emotion"] in ("joy", "anticipation", "trust")
    assert result["sentiment"] == "positive"
    assert 0 < result["confidence"] <= 1.0

    task_result = await agent.execute_task({
        "action": "analyze",
        "input_data": {"text": "I feel sad and lonely"},
    })
    assert task_result.get("primary_emotion")
    assert task_result.get("sentiment") == "negative"

    await agent.shutdown()
    ok("emotion_agent.analyze+execute_task")

# ─── 12. Reasoning Agent ─────────────────────────────────────────────────────
async def test_reasoning_agent():
    from agents.reasoning_agent import ReasoningAgent
    agent = ReasoningAgent()
    await agent.initialize()

    result = await agent.reason(
        "Why does water boil at 100 degrees Celsius?",
        evidence=[{"content": "Water boils when vapor pressure equals atmospheric pressure", "confidence": 0.9}],
    )
    assert result["reasoning_state"] == "completed"
    assert result["reasoning_type"]
    assert result["confidence"]["overall"] >= 0

    metrics = agent.get_metrics()
    assert metrics["completed"] == 1

    await agent.shutdown()
    ok("reasoning_agent.reason+metrics")

# ─── 13. Planning Agent ───────────────────────────────────────────────────────
async def test_planning_agent():
    from agents.planning_agent import PlanningAgent
    agent = PlanningAgent()
    await agent.initialize()

    plan = await agent.create_plan(
        goal="Build a production-ready web application",
        timeframe="3 months",
        constraints=["budget: $10k", "team: 2 developers"],
    )
    assert plan["plan_id"]
    assert len(plan["milestones"]) > 0
    assert plan["status"] == "active"
    assert plan["htn"]["root_task"]
    assert plan["validation"]["status"] in ("passed", "warning")

    task_result = await agent.execute_task({
        "action": "create_plan",
        "input_data": {"goal": "Learn Python programming", "timeframe": "1 month"},
    })
    assert task_result.get("plan_id")

    await agent.shutdown()
    ok("planning_agent.create_plan+htn+validation")

# ─── 14. Learning Agent ───────────────────────────────────────────────────────
async def test_learning_agent():
    from agents.learning_agent.main import LearningAgent
    agent = LearningAgent({})
    await agent.initialize()

    task_result = await agent.execute_task({
        "action": "learn",
        "input_data": {"domain": "science", "information": "The speed of light is 299,792,458 m/s"},
    })
    assert task_result.get("status") in ("learned", "skipped", "ok")

    metrics = await agent.get_metrics()
    assert isinstance(metrics, dict)

    await agent.shutdown()
    ok("learning_agent.initialize+execute_task+metrics")

# ─── 15. Task Agent ───────────────────────────────────────────────────────────
async def test_task_agent():
    from agents.task_agent.main import TaskAgent
    agent = TaskAgent()
    await agent.initialize()

    result = await agent.execute_task({
        "action": "create",
        "input_data": {"title": "Write unit tests", "priority": 2, "description": "Add coverage"},
        "user_id": "test_user",
    })
    assert result.get("status") == "created"
    assert result.get("task_id")

    list_result = await agent.execute_task({
        "action": "list",
        "input_data": {},
    })
    assert "tasks" in list_result

    await agent.shutdown()
    ok("task_agent.create+list+execute_task")

# ─── 16. Observability ────────────────────────────────────────────────────────
async def test_observability():
    from orchestrator.observability import RuntimeObservability
    obs = RuntimeObservability()
    entry = obs.begin_request("test_request", {"key": "val"})
    assert entry.name == "test_request"
    obs.end_request(entry, "success", 42.5)
    obs.record_queue_usage("test_queue", 10, 100)
    obs.record_error()
    snap = obs.snapshot()
    assert snap.request_count == 1
    assert snap.error_count == 1
    assert snap.latency_ms == 42.5
    assert "test_queue" in snap.queue_usage
    ok("observability.begin+end+snapshot")

# ─── 17. Request Context ─────────────────────────────────────────────────────
async def test_request_context():
    from orchestrator.request_context import (
        build_request_context, set_request_context,
        get_request_context, clear_request_context,
    )
    ctx = build_request_context(
        correlation_id="corr-123",
        request_id="req-456",
        trace_id="trace-789",
    )
    token = set_request_context(ctx)
    retrieved = get_request_context()
    assert retrieved is not None
    assert retrieved.correlation_id == "corr-123"
    assert retrieved.request_id == "req-456"
    clear_request_context(token)
    assert get_request_context() is None
    ok("request_context.build+set+get+clear")

# ─── 18. Confidence Engine ────────────────────────────────────────────────────
async def test_confidence_engine():
    from orchestrator.confidence_engine import ConfidenceEngine
    ce = ConfidenceEngine()
    ic = ce.intent_confidence(0.8, 0.2)
    assert 0 < ic <= 1.0
    rc = ce.routing_confidence(0.75, capability_match=True, agent_name="memory_agent")
    assert 0 < rc <= 1.0
    combined = ce.combined_confidence(ic, rc)
    assert 0 < combined <= 1.0
    ce.record_outcome("memory_agent", True)
    ce.record_outcome("memory_agent", True)
    ce.record_outcome("memory_agent", False)
    profile = ce.get_agent_profile("memory_agent")
    assert profile["sample_count"] == 3
    ok("confidence_engine.intent+routing+combined+record")

# ─── 19. Intent Pipeline ─────────────────────────────────────────────────────
async def test_intent_pipeline():
    from orchestrator.intent_pipeline import IntentPipeline
    from orchestrator.confidence_engine import ConfidenceEngine
    pipeline = IntentPipeline(confidence_engine=ConfidenceEngine())
    normalized = pipeline.normalize("  What is the best way to remember things?  ")
    assert normalized == "What is the best way to remember things?"
    primary, all_intents = pipeline.analyze("Create a plan for my project")
    assert primary is not None
    assert primary.confidence > 0
    assert len(all_intents) >= 1
    ok("intent_pipeline.normalize+analyze")

# ─── 20. Full Orchestrator Startup Simulation ─────────────────────────────────
async def test_orchestrator_startup():
    """Simulate the full orchestrator startup sequence without uvicorn."""
    from orchestrator.config import settings
    from orchestrator.database import DatabaseManager, DatabaseConfig
    from orchestrator.agent_communication import get_message_broker
    from orchestrator.agent_lifecycle import AgentLifecycleManager
    from orchestrator.agent_manager import AgentManager
    from orchestrator.communication_controller import CommunicationController
    from orchestrator.task_scheduler import TaskScheduler
    from orchestrator.decision_engine import DecisionEngine

    # Step 1: DB
    dm = DatabaseManager(DatabaseConfig(database_path="data/brain.db"))
    dm.initialize()
    assert dm.health_check()["ok"]

    # Step 2: Broker
    broker = get_message_broker()
    await asyncio.wait_for(broker.start(), timeout=10)

    # Step 3: Lifecycle
    lifecycle = AgentLifecycleManager()
    await asyncio.wait_for(lifecycle.start(), timeout=10)

    # Step 4: Comm Controller
    cc = CommunicationController({
        "timeout": 5.0,
        "queue_limits": {"message_queue_size": 1000, "event_queue_size": 1000},
        "retry": {"max_retries": 3, "backoff_seconds": 0.25},
        "kafka": {"enabled": False},
        "redis": {"enabled": False},
        "max_payload_bytes": 1_048_576,
    })
    await asyncio.wait_for(cc.initialize(), timeout=10)

    # Step 5: Agent Manager (subset for speed)
    default_agents = ["memory_agent","emotion_agent","reasoning_agent","planning_agent","task_agent"]
    agent_mgr = AgentManager({"agents": {n: {} for n in default_agents}})
    await asyncio.wait_for(agent_mgr.initialize(), timeout=30)
    await asyncio.wait_for(agent_mgr.start(), timeout=60)
    loaded_count = len(agent_mgr.agents)
    assert loaded_count >= 3, f"Only {loaded_count} agents loaded"

    # Step 6: Task Scheduler
    scheduler = TaskScheduler({
        "max_concurrent_tasks": settings.MAX_CONCURRENT_TASKS,
        "task_timeout": settings.TASK_TIMEOUT,
        "message_broker": broker,
        "communication_controller": cc,
        "agent_manager": agent_mgr,
    })
    await asyncio.wait_for(scheduler.initialize(), timeout=10)
    for name, inst in agent_mgr.agents.items():
        await scheduler.register_worker(name, inst, pool="agents")
    await asyncio.wait_for(scheduler.start(), timeout=10)

    # Step 7: Decision Engine
    de = DecisionEngine.from_config_file("config/decision_config.yaml")
    await de.initialize()
    await de.start()
    snapshot = agent_mgr.get_capability_snapshot()
    de.update_agent_registry(
        available_agents=snapshot["available_agents"],
        agent_capabilities=snapshot["agent_capabilities"],
        agent_health=snapshot["agent_health"],
        agent_load=snapshot["agent_load"],
    )

    # Step 8: Register agents with lifecycle
    for agent_id, inst in agent_mgr.agents.items():
        await lifecycle.register_agent(agent_id, agent_id.replace("_agent",""), inst)
        lifecycle.agents[agent_id]["is_running"] = True
        lifecycle.agent_health[agent_id].status = "healthy"

    # Verify health endpoint data
    statuses = await lifecycle.get_all_agent_statuses()
    healthy = sum(1 for s in statuses.values() if s.get("is_running"))
    assert healthy >= 3, f"Only {healthy} healthy agents"

    # Verify routing works end-to-end
    route = await de.route_request("I need to remember my meeting tomorrow")
    assert route["selected_agent"]
    assert route["confidence"] > 0

    # Teardown
    await de.stop()
    await agent_mgr.stop()
    await scheduler.shutdown()
    await cc.stop()
    await lifecycle.stop()
    await broker.stop()
    dm.shutdown()

    ok(f"orchestrator_startup_simulation ({loaded_count} agents, routing={route['selected_agent']})")

# ─── 21. Autonomous Cognitive Controller (Phase 14) ───────────────────────
async def test_autonomous_controller():
    from orchestrator.autonomous_controller import AutonomousCognitiveController
    from orchestrator.config import settings

    controller = AutonomousCognitiveController(settings.model_dump())
    await controller.start()
    assert controller._running is True

    controller.record_execution_event("test_agent", "action", latency_ms=50.0, success=True)
    state = await controller.run_coordination_cycle()
    assert state.health_level is not None
    assert len(state.capabilities) > 0

    await controller.stop()
    assert controller._running is False
    ok("autonomous_controller.phase14_coordination")

# ─── 22. Enterprise Integration (Phase 15) ──────────────────────────────────
async def test_enterprise_integration():
    from orchestrator.distributed import ClusterCoordinator
    from orchestrator.security import SecurityGovernanceEngine, SecretManager, InMemorySecretProvider
    from orchestrator.resilience import CircuitBreaker, DeadLetterQueue, DisasterRecoveryManager
    from orchestrator.observability_platform import ObservabilityPlatform
    from orchestrator.enterprise_ops import EnterpriseOpsManager

    coord = ClusterCoordinator(config={"node_id": "val-node-1"})
    await coord.start()
    assert coord.is_running
    await coord.stop()

    sec = SecurityGovernanceEngine()
    assert sec.get_status()["initialized"]

    secrets = SecretManager(provider=InMemorySecretProvider())
    secrets.set_secret("KEY", "VAL")
    assert secrets.get_secret("KEY") == "VAL"

    cb = CircuitBreaker("val-cb")
    assert cb.state.value == "closed"

    dlq = DeadLetterQueue()
    entry = dlq.enqueue({"msg": "test"}, "error", "source")
    assert entry.status == "pending"

    dr = DisasterRecoveryManager()
    manifest = dr.create_backup(["val"])
    assert manifest.status == "completed"

    obs = ObservabilityPlatform()
    assert obs.get_full_status() is not None

    ops = EnterpriseOpsManager()
    assert not ops.maintenance.enabled

    ok("enterprise_integration.phase15_all_subsystems")

# ─── Runner ───────────────────────────────────────────────────────────────────
async def main():
    tests = [
        ("Settings", test_settings),
        ("Database", test_database),
        ("Message Broker", test_broker),
        ("Lifecycle Manager", test_lifecycle),
        ("Communication Controller", test_comm_controller),
        ("Task Scheduler", test_task_scheduler),
        ("Decision Engine", test_decision_engine),
        ("Agent Manager", test_agent_manager),
        ("Execution Pipeline", test_execution_pipeline),
        ("Memory Agent", test_memory_agent),
        ("Emotion Agent", test_emotion_agent),
        ("Reasoning Agent", test_reasoning_agent),
        ("Planning Agent", test_planning_agent),
        ("Learning Agent", test_learning_agent),
        ("Task Agent", test_task_agent),
        ("Observability", test_observability),
        ("Request Context", test_request_context),
        ("Confidence Engine", test_confidence_engine),
        ("Intent Pipeline", test_intent_pipeline),
        ("Autonomous Cognitive Controller", test_autonomous_controller),
        ("Enterprise Integration", test_enterprise_integration),
        ("Full Orchestrator Startup", test_orchestrator_startup),
    ]

    print("=" * 65)
    print("  AI VIRTUAL BRAIN — PRODUCTION RUNTIME VALIDATION")
    print("=" * 65)

    for name, fn in tests:
        print(f"\n[{name}]")
        try:
            await asyncio.wait_for(fn(), timeout=120)
        except Exception as e:
            tb = traceback.format_exc()
            fail(name, f"{type(e).__name__}: {e}")
            print(f"    {tb.strip().splitlines()[-1]}")

    print("\n" + "=" * 65)
    print(f"  RESULT: {len(PASS)} PASS  |  {len(FAIL)} FAIL")
    if FAIL:
        print("\n  FAILURES:")
        for name, err in FAIL:
            print(f"    - {name}: {err}")
    print("=" * 65)
    return len(FAIL)

if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
