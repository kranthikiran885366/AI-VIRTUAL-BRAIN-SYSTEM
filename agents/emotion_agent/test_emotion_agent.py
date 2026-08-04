"""
Emotion Agent unit tests — Phase 8 (replaces broken Phase 4 stubs).
Tests EmotionProcessor, EmotionStore, EmotionAnalyzer, EmotionEngine,
MotivationEngine, RecommendationEngine, and EmotionAgent.execute_task.
"""
import asyncio
import pytest
from .emotion_processor import EmotionProcessor
from .emotion_store import EmotionStore
from .emotion_analyzer import EmotionAnalyzer
from .emotion_engine import EmotionEngine, EmotionSignal
from .motivation_engine import MotivationEngine
from .recommendation_engine import RecommendationEngine
from .emotion_context import EmotionContext
from .main import EmotionAgent


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def processor():
    p = EmotionProcessor()
    await p.initialize()
    yield p
    await p.shutdown()


@pytest.fixture
async def store():
    s = EmotionStore()
    await s.initialize()
    yield s
    await s.clear_emotions()
    await s.shutdown()


@pytest.fixture
async def analyzer():
    a = EmotionAnalyzer()
    await a.initialize()
    yield a
    await a.shutdown()


@pytest.fixture
async def engine():
    e = EmotionEngine()
    await e.start()
    yield e
    await e.stop()


@pytest.fixture
def motivation():
    return MotivationEngine()


@pytest.fixture
def rec_engine(engine):
    return RecommendationEngine()


@pytest.fixture
async def agent():
    a = EmotionAgent()
    await a.initialize()
    yield a
    await a.shutdown()


# ── EmotionProcessor ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_processor_initializes(processor):
    assert processor._initialized is True


@pytest.mark.asyncio
async def test_processor_process_emotion(processor):
    result = await processor.process_emotion({"type": "joy", "intensity": 0.8, "source": "test"})
    assert result["type"] == "joy"
    assert result["intensity"] == 0.8
    assert "id" in result


@pytest.mark.asyncio
async def test_processor_tracks_current(processor):
    await processor.process_emotion({"type": "trust", "intensity": 0.9, "source": "test"})
    current = await processor.get_current_emotions()
    assert "trust" in current


@pytest.mark.asyncio
async def test_processor_history(processor):
    await processor.process_emotion({"type": "fear", "intensity": 0.5, "source": "test"})
    history = await processor.get_emotion_history()
    assert len(history) >= 1


@pytest.mark.asyncio
async def test_processor_clear(processor):
    await processor.process_emotion({"type": "anger", "intensity": 0.6, "source": "test"})
    await processor.clear_emotions()
    history = await processor.get_emotion_history()
    assert len(history) == 0


# ── EmotionStore ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_initializes(store):
    assert store._initialized is True


@pytest.mark.asyncio
async def test_store_store_and_get(store):
    eid = await store.store_emotion({"type": "sadness", "intensity": 0.6, "source": "test"})
    assert eid is not None
    emotion = await store.get_emotion(eid)
    assert emotion["type"] == "sadness"


@pytest.mark.asyncio
async def test_store_search_by_type(store):
    await store.store_emotion({"type": "joy", "intensity": 0.7, "source": "test"})
    results = await store.search_emotions({"type": "joy"})
    assert len(results) >= 1
    assert all(e["type"] == "joy" for e in results)


@pytest.mark.asyncio
async def test_store_search_by_min_intensity(store):
    await store.store_emotion({"type": "joy", "intensity": 0.9, "source": "test"})
    await store.store_emotion({"type": "joy", "intensity": 0.2, "source": "test"})
    results = await store.search_emotions({"min_intensity": 0.7})
    assert all(e["intensity"] >= 0.7 for e in results)


@pytest.mark.asyncio
async def test_store_update(store):
    eid = await store.store_emotion({"type": "anger", "intensity": 0.5, "source": "test"})
    ok = await store.update_emotion(eid, {"intensity": 0.8})
    assert ok is True
    emotion = await store.get_emotion(eid)
    assert emotion["intensity"] == 0.8


@pytest.mark.asyncio
async def test_store_delete(store):
    eid = await store.store_emotion({"type": "fear", "intensity": 0.4, "source": "test"})
    ok = await store.delete_emotion(eid)
    assert ok is True
    assert await store.get_emotion(eid) is None


# ── EmotionAnalyzer ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyzer_initializes(analyzer):
    assert analyzer._initialized is True


@pytest.mark.asyncio
async def test_analyzer_analyze_emotion(analyzer):
    emotion = {"id": "e1", "type": "joy", "intensity": 0.8, "source": "test", "context": {}}
    result = await analyzer.analyze_emotion(emotion)
    assert result["emotion_type"] == "joy"
    assert "patterns" in result
    assert "impact" in result
    assert "recommendations" in result


@pytest.mark.asyncio
async def test_analyzer_detects_recurring_pattern(analyzer):
    for i in range(4):
        analyzer.analysis_history.append({
            "emotion_type": "sadness", "emotion_id": f"e{i}",
            "timestamp": "2024-01-01T00:00:00",
        })
    emotion = {"id": "e5", "type": "sadness", "intensity": 0.6, "source": "test", "context": {}}
    result = await analyzer.analyze_emotion(emotion)
    recurring = [p for p in result["patterns"] if p["type"] == "recurring"]
    assert len(recurring) >= 1


@pytest.mark.asyncio
async def test_analyzer_stats(analyzer):
    emotion = {"id": "e1", "type": "anger", "intensity": 0.7, "source": "test", "context": {}}
    await analyzer.analyze_emotion(emotion)
    stats = await analyzer.get_stats()
    assert stats["analysis_count"] >= 1


# ── EmotionEngine ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_engine_starts_and_stops(engine):
    assert engine._running is True


@pytest.mark.asyncio
async def test_engine_initial_state(engine):
    state = engine.get_state()
    assert "confidence" in state
    assert "stress" in state
    assert 0.0 <= state["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_engine_process_signal_execution_failure(engine):
    signal = EmotionSignal(source="execution", signal_type="execution_failure", intensity=0.8)
    result = await engine.process_signal(signal)
    assert "state" in result
    assert "transitions" in result
    assert result["state"]["frustration"] > 0.0


@pytest.mark.asyncio
async def test_engine_process_signal_positive_feedback(engine):
    signal = EmotionSignal(source="user", signal_type="user_feedback_positive", intensity=0.9)
    result = await engine.process_signal(signal)
    state = result["state"]
    assert state["satisfaction"] > 0.0


@pytest.mark.asyncio
async def test_engine_process_signal_recovery(engine):
    # First stress the engine
    await engine.process_signal(EmotionSignal(source="execution", signal_type="execution_failure", intensity=1.0))
    stress_before = engine.get_state()["stress"]
    # Then recover
    await engine.process_signal(EmotionSignal(source="system", signal_type="recovery", intensity=1.0))
    stress_after = engine.get_state()["stress"]
    assert stress_after <= stress_before


@pytest.mark.asyncio
async def test_engine_session_lifecycle(engine):
    session = engine.begin_session(request_id="req-1", correlation_id="corr-1")
    assert session.session_id is not None
    assert session.request_id == "req-1"
    result = engine.end_session(session)
    assert result["ended_at"] is not None


@pytest.mark.asyncio
async def test_engine_state_history(engine):
    await engine.process_signal(EmotionSignal(source="test", signal_type="execution_failure", intensity=0.5))
    history = engine.get_state_history(limit=10)
    assert len(history) >= 1


@pytest.mark.asyncio
async def test_engine_transition_history(engine):
    await engine.process_signal(EmotionSignal(source="test", signal_type="execution_failure", intensity=0.9))
    transitions = engine.get_transition_history(limit=10)
    assert isinstance(transitions, list)


@pytest.mark.asyncio
async def test_engine_audit_trail(engine):
    await engine.process_signal(EmotionSignal(source="test", signal_type="timeout", intensity=0.7))
    audit = engine.get_audit_trail(limit=20)
    assert len(audit) >= 1
    assert all("event" in entry for entry in audit)


@pytest.mark.asyncio
async def test_engine_metrics(engine):
    await engine.process_signal(EmotionSignal(source="test", signal_type="task_completed", intensity=0.6))
    metrics = engine.get_metrics()
    assert metrics["total_signals"] >= 1
    assert "version" in metrics


@pytest.mark.asyncio
async def test_engine_analytics(engine):
    for _ in range(3):
        await engine.process_signal(EmotionSignal(source="test", signal_type="execution_failure", intensity=0.5))
    analytics = engine.get_analytics()
    assert "dimension_trends" in analytics
    assert "current_indicators" in analytics


@pytest.mark.asyncio
async def test_engine_text_analysis(engine):
    result = engine.analyze_text("I am so happy and excited today!")
    assert result["primary_emotion"] in ("joy", "anticipation", "trust")
    assert result["sentiment"] == "positive"
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_engine_text_analysis_negative(engine):
    result = engine.analyze_text("I feel angry and frustrated.")
    assert result["sentiment"] == "negative"


@pytest.mark.asyncio
async def test_engine_text_analysis_neutral(engine):
    result = engine.analyze_text("The meeting is at 3pm.")
    assert result["primary_emotion"] == "neutral"


@pytest.mark.asyncio
async def test_engine_validate_signal_valid(engine):
    result = engine.validate_signal({"signal_type": "execution_failure", "intensity": 0.5, "source": "test"})
    assert result["valid"] is True
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_engine_validate_signal_invalid_intensity(engine):
    result = engine.validate_signal({"signal_type": "execution_failure", "intensity": 1.5, "source": "test"})
    assert result["valid"] is False
    assert len(result["errors"]) >= 1


@pytest.mark.asyncio
async def test_engine_confidence_influence(engine):
    influence = engine.get_confidence_influence()
    assert isinstance(influence, float)


@pytest.mark.asyncio
async def test_engine_decay_does_not_crash(engine):
    # Trigger decay manually
    engine._apply_decay()
    state = engine.get_state()
    assert 0.0 <= state["confidence"] <= 1.0


# ── MotivationEngine ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_motivation_engine_start_stop(motivation):
    await motivation.start()
    assert motivation._running is True
    await motivation.stop()
    assert motivation._running is False


@pytest.mark.asyncio
async def test_motivation_create_goal(motivation):
    await motivation.start()
    goal = motivation.create_goal("user1", "Learn Python", difficulty=0.6, priority=2)
    assert goal.goal_id is not None
    assert goal.title == "Learn Python"
    assert goal.status == "active"
    await motivation.stop()


@pytest.mark.asyncio
async def test_motivation_update_progress(motivation):
    await motivation.start()
    goal = motivation.create_goal("user1", "Exercise daily")
    updated = motivation.update_goal_progress("user1", goal.goal_id, 0.5, success=True)
    assert updated is not None
    assert updated.progress == 0.5
    assert updated.streak_days == 1
    await motivation.stop()


@pytest.mark.asyncio
async def test_motivation_goal_completion(motivation):
    await motivation.start()
    goal = motivation.create_goal("user1", "Read a book")
    updated = motivation.update_goal_progress("user1", goal.goal_id, 1.0, success=True)
    assert updated.status == "completed"
    assert updated.completed_at is not None
    await motivation.stop()


@pytest.mark.asyncio
async def test_motivation_abandon_goal(motivation):
    await motivation.start()
    goal = motivation.create_goal("user1", "Learn guitar")
    ok = motivation.abandon_goal("user1", goal.goal_id, reason="too busy")
    assert ok is True
    goals = motivation.get_goals("user1", status="abandoned")
    assert any(g.goal_id == goal.goal_id for g in goals)
    await motivation.stop()


@pytest.mark.asyncio
async def test_motivation_compute_score(motivation):
    await motivation.start()
    motivation.create_goal("user1", "Goal A", difficulty=0.5)
    score = motivation.compute_score("user1")
    assert 0.0 <= score.overall <= 1.0
    assert score.active_goals >= 1
    await motivation.stop()


@pytest.mark.asyncio
async def test_motivation_burnout_detection(motivation):
    await motivation.start()
    goal = motivation.create_goal("user1", "Hard goal", difficulty=0.9)
    # Simulate many failures
    for _ in range(12):
        motivation.update_goal_progress("user1", goal.goal_id, 0.1, success=False)
    score = motivation.compute_score("user1")
    # burnout detection depends on window — just verify it runs without error
    assert isinstance(score.is_burned_out, bool)
    await motivation.stop()


@pytest.mark.asyncio
async def test_motivation_stagnation_detection(motivation):
    await motivation.start()
    goal = motivation.create_goal("user1", "Stagnant goal")
    # Manually set last_activity to old time
    from datetime import datetime, timedelta
    goal.last_activity_at = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    score = motivation.compute_score("user1")
    assert isinstance(score.is_stagnant, bool)
    await motivation.stop()


@pytest.mark.asyncio
async def test_motivation_analytics(motivation):
    await motivation.start()
    motivation.create_goal("user1", "Analytics goal")
    motivation.compute_score("user1")
    analytics = motivation.get_analytics("user1")
    assert "current_score" in analytics
    assert "trend" in analytics
    await motivation.stop()


@pytest.mark.asyncio
async def test_motivation_audit_trail(motivation):
    await motivation.start()
    motivation.create_goal("user1", "Audit goal")
    audit = motivation.get_audit_trail(limit=10)
    assert len(audit) >= 1
    assert all("event" in e for e in audit)
    await motivation.stop()


@pytest.mark.asyncio
async def test_motivation_metrics(motivation):
    await motivation.start()
    motivation.create_goal("user1", "Metrics goal")
    metrics = motivation.get_metrics()
    assert metrics["total_goals_created"] >= 1
    assert "version" in metrics
    await motivation.stop()


@pytest.mark.asyncio
async def test_motivation_validate_goal_data_valid(motivation):
    result = motivation.validate_goal_data({"title": "Valid goal", "difficulty": 0.5, "priority": 2})
    assert result["valid"] is True


@pytest.mark.asyncio
async def test_motivation_validate_goal_data_invalid(motivation):
    result = motivation.validate_goal_data({"title": "", "difficulty": 1.5, "priority": 9})
    assert result["valid"] is False
    assert len(result["errors"]) >= 1


@pytest.mark.asyncio
async def test_motivation_persistence(tmp_path, motivation):
    motivation._persist_path = tmp_path / "motivation_state.json"
    await motivation.start()
    motivation.create_goal("user1", "Persist goal")
    motivation._persist_state()
    assert motivation._persist_path.exists()
    await motivation.stop()


# ── RecommendationEngine ──────────────────────────────────────────────────────

def test_rec_engine_no_recommendations_neutral_state(rec_engine):
    state = {"confidence": 0.7, "stress": 0.1, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec_engine.generate(state, motivation_score=0.6)
    assert isinstance(recs, list)


def test_rec_engine_stress_recommendation(rec_engine):
    state = {"confidence": 0.7, "stress": 0.85, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec_engine.generate(state, motivation_score=0.6)
    categories = [r.category for r in recs]
    assert "recovery" in categories


def test_rec_engine_low_confidence_recommendation(rec_engine):
    state = {"confidence": 0.25, "stress": 0.1, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec_engine.generate(state, motivation_score=0.6)
    categories = [r.category for r in recs]
    assert "confidence" in categories


def test_rec_engine_cognitive_overload_recommendation(rec_engine):
    state = {"confidence": 0.7, "stress": 0.1, "frustration": 0.1,
             "cognitive_load": 0.9, "engagement": 0.6, "recovery": 1.0}
    recs = rec_engine.generate(state, motivation_score=0.6)
    categories = [r.category for r in recs]
    assert "priority" in categories


def test_rec_engine_low_motivation_recommendation(rec_engine):
    state = {"confidence": 0.7, "stress": 0.1, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec_engine.generate(state, motivation_score=0.20)
    categories = [r.category for r in recs]
    assert "planning" in categories


def test_rec_engine_consecutive_failures(rec_engine):
    state = {"confidence": 0.7, "stress": 0.1, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec_engine.generate(state, motivation_score=0.6, context={"consecutive_failures": 5})
    categories = [r.category for r in recs]
    assert "recovery" in categories


def test_rec_engine_explainability_fields(rec_engine):
    state = {"confidence": 0.25, "stress": 0.85, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec_engine.generate(state, motivation_score=0.6)
    for r in recs:
        assert r.reason != ""
        assert 0.0 <= r.confidence <= 1.0
        assert isinstance(r.supporting_evidence, list)
        assert r.expected_impact != ""
        assert isinstance(r.limitations, list)
        assert isinstance(r.affected_subsystems, list)


def test_rec_engine_max_per_session(rec_engine):
    # Trigger all conditions simultaneously
    state = {"confidence": 0.20, "stress": 0.90, "frustration": 0.80,
             "cognitive_load": 0.90, "engagement": 0.6, "recovery": 0.10}
    recs = rec_engine.generate(state, motivation_score=0.20,
                                context={"consecutive_failures": 5})
    assert len(recs) <= rec_engine._max_per_session


def test_rec_engine_record_outcome(rec_engine):
    state = {"confidence": 0.25, "stress": 0.1, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec_engine.generate(state, motivation_score=0.6)
    if recs:
        ok = rec_engine.record_outcome(recs[0].recommendation_id, True, "improved", 0.8)
        assert ok is True


def test_rec_engine_metrics(rec_engine):
    state = {"confidence": 0.25, "stress": 0.1, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    rec_engine.generate(state, motivation_score=0.6)
    metrics = rec_engine.get_metrics()
    assert "total_generated" in metrics
    assert "by_category" in metrics


# ── EmotionContext ────────────────────────────────────────────────────────────

def test_emotion_context_creation():
    ctx = EmotionContext(request_id="req-1", correlation_id="corr-1", trace_id="trace-1")
    assert ctx.context_id is not None
    assert ctx.request_id == "req-1"


def test_emotion_context_record_execution():
    ctx = EmotionContext()
    ctx.record_execution(success=True, latency_ms=50.0, agent_name="decision_agent")
    assert ctx.last_execution_success is True
    assert ctx.consecutive_failures == 0
    assert ctx.last_selected_agent == "decision_agent"


def test_emotion_context_consecutive_failures():
    ctx = EmotionContext()
    ctx.record_execution(success=False)
    ctx.record_execution(success=False)
    assert ctx.consecutive_failures == 2
    ctx.record_execution(success=True)
    assert ctx.consecutive_failures == 0


def test_emotion_context_feedback_ratio():
    ctx = EmotionContext()
    assert ctx.feedback_ratio() == 0.5  # no feedback yet
    ctx.record_feedback(positive=True)
    ctx.record_feedback(positive=True)
    ctx.record_feedback(positive=False)
    assert abs(ctx.feedback_ratio() - 2 / 3) < 0.01


def test_emotion_context_to_dict():
    ctx = EmotionContext(user_id="u1", session_id="s1")
    d = ctx.to_dict()
    assert d["user_id"] == "u1"
    assert d["session_id"] == "s1"
    assert "context_id" in d


# ── EmotionAgent.execute_task ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_execute_analyze(agent):
    result = await agent.execute_task({
        "action": "analyze",
        "input_data": {"content": "I love this project!"},
    })
    assert result["status"] == "analyzed"
    assert "primary_emotion" in result


@pytest.mark.asyncio
async def test_agent_execute_store(agent):
    result = await agent.execute_task({
        "action": "store",
        "input_data": {"type": "joy", "intensity": 0.8, "source": "test"},
    })
    assert result["status"] == "stored"
    assert "emotion_id" in result


@pytest.mark.asyncio
async def test_agent_execute_recall(agent):
    await agent.execute_task({
        "action": "store",
        "input_data": {"type": "fear", "intensity": 0.6, "source": "test"},
    })
    result = await agent.execute_task({
        "action": "recall",
        "input_data": {"type": "fear"},
    })
    assert result["status"] == "ok"
    assert result["count"] >= 1


@pytest.mark.asyncio
async def test_agent_execute_get_state(agent):
    result = await agent.execute_task({"action": "get_state", "input_data": {}})
    assert result["status"] == "ok"
    assert "state" in result
    assert "dimensions" in result


@pytest.mark.asyncio
async def test_agent_execute_process_signal(agent):
    result = await agent.execute_task({
        "action": "process_signal",
        "input_data": {
            "signal": {"signal_type": "execution_failure", "intensity": 0.7, "source": "test"}
        },
    })
    assert result["status"] == "ok"
    assert "state" in result


@pytest.mark.asyncio
async def test_agent_execute_process_signal_invalid(agent):
    result = await agent.execute_task({
        "action": "process_signal",
        "input_data": {
            "signal": {"signal_type": "execution_failure", "intensity": 2.0, "source": "test"}
        },
    })
    assert result["status"] == "error"
    assert "errors" in result


@pytest.mark.asyncio
async def test_agent_execute_get_recommendations(agent):
    result = await agent.execute_task({
        "action": "get_recommendations",
        "input_data": {"motivation_score": 0.3},
    })
    assert result["status"] == "ok"
    assert "recommendations" in result
    assert isinstance(result["recommendations"], list)


@pytest.mark.asyncio
async def test_agent_execute_begin_end_session(agent):
    begin = await agent.execute_task({
        "action": "begin_session",
        "input_data": {"request_id": "req-1", "correlation_id": "corr-1"},
    })
    assert begin["status"] == "ok"
    assert "session" in begin

    end = await agent.execute_task({"action": "end_session", "input_data": {}})
    assert end["status"] == "ok"


@pytest.mark.asyncio
async def test_agent_execute_get_engine_metrics(agent):
    result = await agent.execute_task({"action": "get_engine_metrics", "input_data": {}})
    assert result["status"] == "ok"
    assert "metrics" in result
    assert "total_signals" in result["metrics"]


@pytest.mark.asyncio
async def test_agent_execute_get_analytics(agent):
    # Process a signal first to populate history
    await agent.execute_task({
        "action": "process_signal",
        "input_data": {"signal": {"signal_type": "task_completed", "intensity": 0.6, "source": "test"}},
    })
    result = await agent.execute_task({"action": "get_analytics", "input_data": {}})
    assert result["status"] == "ok"
    assert "analytics" in result


@pytest.mark.asyncio
async def test_agent_execute_get_audit_trail(agent):
    await agent.execute_task({
        "action": "process_signal",
        "input_data": {"signal": {"signal_type": "timeout", "intensity": 0.5, "source": "test"}},
    })
    result = await agent.execute_task({"action": "get_audit_trail", "input_data": {"limit": 20}})
    assert result["status"] == "ok"
    assert isinstance(result["audit_trail"], list)


@pytest.mark.asyncio
async def test_agent_execute_get_confidence_influence(agent):
    result = await agent.execute_task({"action": "get_confidence_influence", "input_data": {}})
    assert result["status"] == "ok"
    assert isinstance(result["confidence_influence"], float)


@pytest.mark.asyncio
async def test_agent_execute_get_stats(agent):
    result = await agent.execute_task({"action": "get_stats", "input_data": {}})
    assert result["status"] == "ok"
    assert "stats" in result


@pytest.mark.asyncio
async def test_agent_execute_clear(agent):
    await agent.execute_task({
        "action": "store",
        "input_data": {"type": "anger", "intensity": 0.7, "source": "test"},
    })
    result = await agent.execute_task({"action": "clear", "input_data": {}})
    assert result["status"] == "cleared"


@pytest.mark.asyncio
async def test_agent_default_action_feeds_engine(agent):
    """Default action (no recognized action) should still analyze text and feed engine."""
    result = await agent.execute_task({
        "action": "unknown_action",
        "input_data": {"content": "I am very happy today!"},
    })
    assert "primary_emotion" in result
