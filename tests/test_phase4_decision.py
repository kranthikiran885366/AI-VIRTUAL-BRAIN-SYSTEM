"""
Phase 4 Decision Intelligence Tests

Covers:
- Intent detection accuracy
- Single-agent routing
- Multi-agent routing
- Fallback routing
- Confidence calculation
- Capability-based routing
- Health-aware routing
- Load-aware routing
- Keyword fallback
- DecisionEngine pipeline
- DecisionAgent execute_task
- AgentManager capability snapshot
- Backward compatibility
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from orchestrator.decision_context import (
    DecisionContext, DecisionRecord, DecisionStatus,
    DetectedIntent, IntentType, RoutingDecision, RoutingStrategy,
)
from orchestrator.confidence_engine import ConfidenceEngine
from orchestrator.intent_pipeline import IntentPipeline
from orchestrator.routing_engine import RoutingEngine
from orchestrator.decision_engine import DecisionEngine


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def confidence_engine():
    return ConfidenceEngine({
        "min_routing_confidence": 0.35,
        "min_intent_confidence": 0.30,
        "high_confidence_threshold": 0.75,
        "history_weight": 0.15,
    })


@pytest.fixture
def intent_pipeline(confidence_engine):
    return IntentPipeline(
        confidence_engine=confidence_engine,
        config={"multi_intent_enabled": True, "max_intents": 3, "secondary_intent_threshold": 0.20},
    )


@pytest.fixture
def routing_engine(confidence_engine):
    return RoutingEngine(
        confidence_engine=confidence_engine,
        config={
            "fallback_agent": "orchestrator_agent",
            "max_alternatives": 3,
            "capability_routing_enabled": True,
            "health_aware_routing": True,
            "load_aware_routing": False,
            "strategy_order": ["semantic", "capability", "keyword"],
        },
    )


@pytest.fixture
def decision_engine():
    return DecisionEngine({
        "confidence": {"min_routing_confidence": 0.35, "min_intent_confidence": 0.30},
        "routing": {"fallback_agent": "orchestrator_agent"},
        "intent": {"multi_intent_enabled": True},
        "decision": {"max_history": 100, "persist_history": False},
    })


def _make_ctx(
    content: str,
    available_agents=None,
    agent_health=None,
    agent_capabilities=None,
    agent_hint=None,
) -> DecisionContext:
    ctx = DecisionContext(
        content=content,
        agent_hint=agent_hint,
        available_agents=available_agents or [
            "memory_agent", "emotion_agent", "task_agent", "planning_agent",
            "creativity_agent", "reasoning_agent", "language_agent",
            "decision_agent", "orchestrator_agent",
        ],
        agent_health=agent_health or {},
        agent_capabilities=agent_capabilities or {
            "memory_agent": ["memory", "recall", "store"],
            "emotion_agent": ["emotion", "sentiment", "mood"],
            "task_agent": ["task_management", "scheduling", "task"],
            "planning_agent": ["planning", "goal_management", "strategy"],
            "creativity_agent": ["creativity", "generation", "creative"],
            "reasoning_agent": ["reasoning", "analysis", "logic"],
            "language_agent": ["language", "knowledge", "information"],
            "decision_agent": ["decision_making", "option_scoring"],
            "orchestrator_agent": [],
        },
    )
    ctx.record.primary_intent = None
    ctx.record.intents = []
    return ctx


# ─── Confidence Engine Tests ───────────────────────────────────────────────────

class TestConfidenceEngine:
    def test_intent_confidence_calibration(self, confidence_engine):
        conf = confidence_engine.intent_confidence(0.8, 0.3)
        assert 0.0 <= conf <= 1.0
        assert conf > confidence_engine.intent_confidence(0.3, 0.0)

    def test_routing_confidence_capability_bonus(self, confidence_engine):
        without = confidence_engine.routing_confidence(0.6, capability_match=False)
        with_cap = confidence_engine.routing_confidence(0.6, capability_match=True)
        assert with_cap >= without

    def test_combined_confidence_geometric_mean(self, confidence_engine):
        combined = confidence_engine.combined_confidence(0.8, 0.8)
        assert abs(combined - 0.8) < 0.05

    def test_high_confidence_threshold(self, confidence_engine):
        assert confidence_engine.is_high_confidence(0.80)
        assert not confidence_engine.is_high_confidence(0.50)

    def test_routing_threshold(self, confidence_engine):
        assert confidence_engine.is_above_routing_threshold(0.40)
        assert not confidence_engine.is_above_routing_threshold(0.20)

    def test_historical_confidence_optimistic_prior(self, confidence_engine):
        assert confidence_engine.get_agent_success_rate("unknown_agent") == 1.0

    def test_record_outcome_updates_rate(self, confidence_engine):
        for _ in range(8):
            confidence_engine.record_outcome("test_agent", True)
        for _ in range(2):
            confidence_engine.record_outcome("test_agent", False)
        rate = confidence_engine.get_agent_success_rate("test_agent")
        assert abs(rate - 0.8) < 0.01

    def test_performance_weights_populated(self, confidence_engine):
        confidence_engine.record_outcome("agent_a", True)
        weights = confidence_engine.get_performance_weights()
        assert "agent_a" in weights
        assert 0.2 <= weights["agent_a"] <= 1.5

    def test_explain_output(self, confidence_engine):
        explanation = confidence_engine.explain(0.8, 0.75, 0.77)
        assert "intent=" in explanation
        assert "routing=" in explanation
        assert "combined=" in explanation


# ─── Intent Pipeline Tests ─────────────────────────────────────────────────────

class TestIntentPipeline:
    def test_empty_input_returns_unknown(self, intent_pipeline):
        primary, all_intents = intent_pipeline.analyze("")
        assert primary.intent_type == IntentType.UNKNOWN
        assert len(all_intents) == 1

    def test_task_intent_detected(self, intent_pipeline):
        primary, _ = intent_pipeline.analyze("remind me to schedule a meeting deadline")
        assert primary.intent_type == IntentType.TASK
        assert primary.confidence > 0.0

    def test_question_intent_detected(self, intent_pipeline):
        primary, _ = intent_pipeline.analyze("What is the best way to learn Python?")
        assert primary.intent_type in (IntentType.QUESTION, IntentType.INFORMATION_REQUEST)

    def test_command_intent_detected(self, intent_pipeline):
        primary, _ = intent_pipeline.analyze("create a new task and start the process")
        assert primary.intent_type in (IntentType.COMMAND, IntentType.TASK, IntentType.CREATIVE_REQUEST)

    def test_multi_intent_detection(self, intent_pipeline):
        _, all_intents = intent_pipeline.analyze(
            "analyze my schedule and create a plan for the deadline"
        )
        assert len(all_intents) >= 1

    def test_ambiguity_detection(self, intent_pipeline):
        # Two equally matched intents
        _, intents = intent_pipeline.analyze("plan and analyze")
        # ambiguous only when margin < 0.10 — just verify it doesn't crash
        result = intent_pipeline.is_ambiguous(intents)
        assert isinstance(result, bool)

    def test_normalize_collapses_whitespace(self, intent_pipeline):
        normalized = intent_pipeline.normalize("  hello   world  ")
        assert normalized == "hello world"

    def test_conversation_intent_for_greeting(self, intent_pipeline):
        primary, _ = intent_pipeline.analyze("Hello, how are you?")
        assert primary.intent_type in (IntentType.CONVERSATION, IntentType.QUESTION)

    def test_planning_intent(self, intent_pipeline):
        primary, _ = intent_pipeline.analyze("I need a roadmap and strategy for my goal")
        assert primary.intent_type == IntentType.PLANNING_REQUEST

    def test_creative_intent(self, intent_pipeline):
        primary, _ = intent_pipeline.analyze("write a story and design a character")
        assert primary.intent_type == IntentType.CREATIVE_REQUEST


# ─── Routing Engine Tests ──────────────────────────────────────────────────────

class TestRoutingEngine:
    def test_keyword_route_memory(self, routing_engine):
        ctx = _make_ctx("remember this for later")
        ctx.record.primary_intent = DetectedIntent(
            intent_type=IntentType.INFORMATION_REQUEST, confidence=0.5, reasoning="test"
        )
        ctx.record.intents = [ctx.record.primary_intent]
        decision = routing_engine.route(ctx, semantic_router=None)
        # keyword fallback routes to memory_agent; semantic router may prefer language_agent
        assert decision.selected_agent in ("memory_agent", "language_agent", "orchestrator_agent")
        assert decision.confidence > 0.0

    def test_keyword_route_task(self, routing_engine):
        ctx = _make_ctx("add a todo and set a deadline reminder")
        ctx.record.primary_intent = DetectedIntent(
            intent_type=IntentType.TASK, confidence=0.6, reasoning="test"
        )
        ctx.record.intents = [ctx.record.primary_intent]
        decision = routing_engine.route(ctx, semantic_router=None)
        assert decision.selected_agent in ("task_agent", "orchestrator_agent")

    def test_fallback_when_no_match(self, routing_engine):
        ctx = _make_ctx("xyzzy frobnicator quux")
        ctx.record.primary_intent = DetectedIntent(
            intent_type=IntentType.UNKNOWN, confidence=0.0, reasoning="test"
        )
        ctx.record.intents = [ctx.record.primary_intent]
        decision = routing_engine.route(ctx, semantic_router=None)
        assert decision.selected_agent == "orchestrator_agent"
        assert decision.is_fallback

    def test_health_aware_reroute(self, routing_engine):
        ctx = _make_ctx(
            "remember this",
            agent_health={"memory_agent": "error", "orchestrator_agent": "healthy"},
        )
        ctx.record.primary_intent = DetectedIntent(
            intent_type=IntentType.INFORMATION_REQUEST, confidence=0.5, reasoning="test"
        )
        ctx.record.intents = [ctx.record.primary_intent]
        decision = routing_engine.route(ctx, semantic_router=None)
        # memory_agent is unhealthy — should reroute
        assert decision.selected_agent != "memory_agent" or decision.is_fallback

    def test_capability_route_planning(self, routing_engine):
        ctx = _make_ctx("I need a strategy and roadmap for my goal")
        ctx.record.primary_intent = DetectedIntent(
            intent_type=IntentType.PLANNING_REQUEST, confidence=0.7, reasoning="test"
        )
        ctx.record.intents = [ctx.record.primary_intent]
        decision = routing_engine.route(ctx, semantic_router=None)
        assert decision.selected_agent in ("planning_agent", "orchestrator_agent")

    def test_multi_agent_routing_returns_list(self, routing_engine):
        ctx = _make_ctx("analyze my tasks and create a plan")
        ctx.record.primary_intent = DetectedIntent(
            intent_type=IntentType.ANALYSIS_REQUEST, confidence=0.6, reasoning="test"
        )
        secondary = DetectedIntent(
            intent_type=IntentType.PLANNING_REQUEST, confidence=0.4, reasoning="secondary"
        )
        ctx.record.intents = [ctx.record.primary_intent, secondary]
        decisions = routing_engine.route_multi_agent(ctx, semantic_router=None)
        assert isinstance(decisions, list)
        assert len(decisions) >= 1

    def test_routing_decision_to_dict(self, routing_engine):
        ctx = _make_ctx("remember this")
        ctx.record.primary_intent = DetectedIntent(
            intent_type=IntentType.INFORMATION_REQUEST, confidence=0.5, reasoning="test"
        )
        ctx.record.intents = [ctx.record.primary_intent]
        decision = routing_engine.route(ctx, semantic_router=None)
        d = decision.to_dict()
        assert "selected_agent" in d
        assert "confidence" in d
        assert "strategy" in d


# ─── DecisionEngine Integration Tests ─────────────────────────────────────────

class TestDecisionEngine:
    def test_from_config_file_returns_instance(self):
        engine = DecisionEngine.from_config_file("config/decision_config.yaml")
        assert isinstance(engine, DecisionEngine)

    def test_from_config_file_missing_uses_defaults(self):
        engine = DecisionEngine.from_config_file("config/nonexistent_config.yaml")
        assert isinstance(engine, DecisionEngine)

    @pytest.mark.asyncio
    async def test_route_request_returns_selected_agent(self, decision_engine):
        result = await decision_engine.route_request("I need to remember something important")
        assert "selected_agent" in result
        assert result["selected_agent"]

    @pytest.mark.asyncio
    async def test_route_request_has_confidence(self, decision_engine):
        result = await decision_engine.route_request("schedule a task for tomorrow")
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_route_request_has_intent(self, decision_engine):
        result = await decision_engine.route_request("what is machine learning?")
        assert "intent" in result or "routing_strategy" in result

    @pytest.mark.asyncio
    async def test_route_request_with_hint(self, decision_engine):
        result = await decision_engine.route_request(
            "do something", context={"agent_hint": "memory_agent"}
        )
        assert result["selected_agent"] == "memory_agent"

    @pytest.mark.asyncio
    async def test_route_request_fallback_on_empty(self, decision_engine):
        result = await decision_engine.route_request("")
        assert result["selected_agent"] == "orchestrator_agent"

    @pytest.mark.asyncio
    async def test_decision_history_grows(self, decision_engine):
        for i in range(5):
            await decision_engine.route_request(f"test query {i}")
        assert len(decision_engine.decision_history) == 5

    def test_record_agent_outcome_updates_performance(self, decision_engine):
        decision_engine.record_agent_outcome("memory_agent", True)
        assert "memory_agent" in decision_engine._agent_performance

    def test_update_agent_registry(self, decision_engine):
        decision_engine.update_agent_registry(
            available_agents=["memory_agent", "task_agent"],
            agent_capabilities={"memory_agent": ["memory"], "task_agent": ["task"]},
            agent_health={"memory_agent": "healthy"},
            agent_load={"memory_agent": 5},
        )
        assert "memory_agent" in decision_engine._available_agents
        assert decision_engine._agent_capabilities["task_agent"] == ["task"]

    @pytest.mark.asyncio
    async def test_get_status_structure(self, decision_engine):
        status = await decision_engine.get_status()
        assert "status" in status
        assert "metrics" in status
        assert "phase4_enabled" in status

    @pytest.mark.asyncio
    async def test_metrics_increment(self, decision_engine):
        before = decision_engine.metrics["total_decisions"]
        await decision_engine.route_request("analyze this data")
        assert decision_engine.metrics["total_decisions"] == before + 1


# ─── DecisionAgent Tests ───────────────────────────────────────────────────────

class TestDecisionAgent:
    @pytest.mark.asyncio
    async def test_initialize(self):
        from agents.decision_agent import DecisionAgent
        agent = DecisionAgent("test_decision_agent")
        await agent.initialize()
        assert agent._initialized
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_make_decision_returns_structure(self):
        from agents.decision_agent import DecisionAgent
        agent = DecisionAgent("test_decision_agent")
        await agent.initialize()
        result = await agent.make_decision({"goal": "solve a problem", "options": ["fix", "escalate"]})
        assert "id" in result
        assert "chosen_option" in result
        assert "confidence" in result
        assert result["chosen_option"] in ("fix", "escalate")
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_record_outcome(self):
        from agents.decision_agent import DecisionAgent
        agent = DecisionAgent("test_decision_agent")
        await agent.initialize()
        decision = await agent.make_decision({"goal": "test"})
        ok = await agent.record_outcome(decision["id"], True)
        assert ok
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_execute_task_decide(self):
        from agents.decision_agent import DecisionAgent
        agent = DecisionAgent("test_decision_agent")
        await agent.initialize()
        result = await agent.execute_task({
            "action": "decide",
            "input_data": {"goal": "choose a path", "options": ["left", "right"]},
        })
        assert "chosen_option" in result
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_execute_task_get_stats(self):
        from agents.decision_agent import DecisionAgent
        agent = DecisionAgent("test_decision_agent")
        await agent.initialize()
        result = await agent.execute_task({"action": "get_stats", "input_data": {}})
        assert "decision_count" in result
        assert "version" in result
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_execute_task_get_history(self):
        from agents.decision_agent import DecisionAgent
        agent = DecisionAgent("test_decision_agent")
        await agent.initialize()
        await agent.make_decision({"goal": "test"})
        result = await agent.execute_task({"action": "get_history", "input_data": {"limit": 10}})
        assert "history" in result
        assert "total" in result
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_capabilities_exposed(self):
        from agents.decision_agent import DecisionAgent
        agent = DecisionAgent()
        assert "decision_making" in agent.capabilities
        assert "confidence_estimation" in agent.capabilities


# ─── AgentManager Capability Snapshot Tests ───────────────────────────────────

class TestAgentManagerSnapshot:
    @pytest.mark.asyncio
    async def test_get_capability_snapshot_structure(self):
        from orchestrator.agent_manager import AgentManager
        mgr = AgentManager({"agents": {}})
        snapshot = mgr.get_capability_snapshot()
        assert "available_agents" in snapshot
        assert "agent_capabilities" in snapshot
        assert "agent_health" in snapshot
        assert "agent_load" in snapshot

    @pytest.mark.asyncio
    async def test_snapshot_reflects_status(self):
        from orchestrator.agent_manager import AgentManager
        mgr = AgentManager({"agents": {}})
        mgr.agent_status["fake_agent"] = "running"
        mgr.agents["fake_agent"] = object()
        mgr.capability_registry["fake_agent"] = {"memory", "recall"}
        mgr.execution_stats["fake_agent"] = {"executions": 3}
        snapshot = mgr.get_capability_snapshot()
        assert "fake_agent" in snapshot["available_agents"]
        assert "memory" in snapshot["agent_capabilities"]["fake_agent"]
        assert snapshot["agent_load"]["fake_agent"] == 3


# ─── Backward Compatibility Tests ─────────────────────────────────────────────

class TestBackwardCompatibility:
    @pytest.mark.asyncio
    async def test_decision_engine_make_decision_still_works(self, decision_engine):
        """Legacy make_decision method must still return a valid dict."""
        await decision_engine.initialize()  # ensures resource_allocator is set
        result = await decision_engine.make_decision({"description": "test task", "priority": "high"})
        assert "agent_name" in result or "task_type" in result

    @pytest.mark.asyncio
    async def test_decision_engine_route_request_legacy_keys(self, decision_engine):
        """route_request must always return selected_agent key."""
        result = await decision_engine.route_request("remember my notes")
        assert "selected_agent" in result

    def test_keyword_fallback_function(self):
        """_keyword_route_fallback must return selectedAgent key."""
        import importlib
        main_mod = importlib.import_module("orchestrator.main")
        result = main_mod._keyword_route_fallback("remember this")
        assert "selectedAgent" in result
        assert result["selectedAgent"]

    @pytest.mark.asyncio
    async def test_decision_agent_base_agent_contract(self):
        """DecisionAgent must satisfy BaseAgent contract."""
        from agents.decision_agent import DecisionAgent
        agent = DecisionAgent()
        await agent.initialize()
        status = await agent.get_status()
        assert "agent_id" in status
        assert "initialized" in status
        health = await agent.get_health()
        assert "healthy" in health
        await agent.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
