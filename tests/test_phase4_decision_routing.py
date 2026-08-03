import asyncio

from orchestrator.agent_manager import AgentManager
from orchestrator.decision_context import DecisionContext, DecisionRecord, DetectedIntent, IntentType
from orchestrator.routing_engine import RoutingEngine


class DummyAgent:
    def __init__(self):
        self.agent_id = "decision_agent"
        self.agent_type = "decision"
        self.version = "4.0.0"
        self.capabilities = ["decision_making", "routing", "analysis"]
        self.state = {"status": "active"}
        self.metrics = type("Metrics", (), {"executions": 1})()
    async def initialize(self):
        return None
    async def get_health(self):
        return {"healthy": True, "is_healthy": True}


def test_agent_manager_snapshot_exposes_rich_registry_metadata():
    mgr = AgentManager({"agents": {"decision_agent": {}}})
    mgr.agent_status["decision_agent"] = "initialized"
    mgr.capability_registry["decision_agent"] = {"decision_making", "routing", "analysis"}
    mgr.version_registry["decision_agent"] = "4.0.0"
    mgr.execution_stats["decision_agent"] = {"executions": 1, "successes": 1, "failures": 0}
    mgr.failure_history["decision_agent"] = []

    snapshot = mgr.get_capability_snapshot()

    assert "agent_metadata" in snapshot
    assert snapshot["agent_metadata"]["decision_agent"]["health"] == "initialized"
    assert snapshot["agent_metadata"]["decision_agent"]["version"] == "4.0.0"
    assert snapshot["agent_metadata"]["decision_agent"]["capabilities"] == ["analysis", "decision_making", "routing"]


def test_routing_engine_supports_agent_fallback_chain_from_context():
    ctx = DecisionContext(
        content="plan a schedule and write a summary",
        available_agents=["planning_agent", "language_agent", "orchestrator_agent"],
        agent_health={"planning_agent": "healthy", "language_agent": "healthy", "orchestrator_agent": "healthy"},
        agent_load={"planning_agent": 2, "language_agent": 4, "orchestrator_agent": 1},
        agent_capabilities={
            "planning_agent": ["planning", "goal_management"],
            "language_agent": ["language", "generation"],
            "orchestrator_agent": ["routing", "fallback"],
        },
    )
    ctx.record = DecisionRecord()
    ctx.record.intents = [
        DetectedIntent(IntentType.PLANNING_REQUEST, 0.78, "planning"),
        DetectedIntent(IntentType.CREATIVE_REQUEST, 0.61, "creative"),
    ]
    ctx.record.primary_intent = ctx.record.intents[0]

    engine = RoutingEngine(config={"fallback_agent": "orchestrator_agent", "fallback_chain": ["orchestrator_agent"]})
    engine.update_capability_cache("planning_agent", ["planning", "goal_management"])
    engine.update_capability_cache("language_agent", ["language", "generation"])
    engine.update_capability_cache("orchestrator_agent", ["routing", "fallback"])

    decision = engine.route(ctx)

    assert decision.selected_agent in {"planning_agent", "orchestrator_agent"}
    assert decision.reasoning
