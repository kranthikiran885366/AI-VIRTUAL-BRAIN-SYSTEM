"""
Phase 8: Emotion & Motivation Engine — Integration Tests
"""
import pytest
from agents.emotion_agent.emotion_engine import EmotionEngine, EmotionSignal
from agents.emotion_agent.motivation_engine import MotivationEngine
from agents.emotion_agent.recommendation_engine import RecommendationEngine
from agents.emotion_agent.emotion_context import EmotionContext
from agents.emotion_agent.main import EmotionAgent
from agents.motivation_agent import MotivationAgent


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def engine():
    e = EmotionEngine()
    await e.start()
    yield e
    await e.stop()


@pytest.fixture
async def motivation(tmp_path):
    m = MotivationEngine(config={
        "persistence": {
            "enabled": True,
            "path": str(tmp_path / "motivation_engine.json"),
        }
    })
    await m.start()
    yield m
    await m.stop()


@pytest.fixture
async def emotion_agent():
    a = EmotionAgent()
    await a.initialize()
    yield a
    await a.shutdown()


@pytest.fixture
async def motivation_agent(tmp_path):
    a = MotivationAgent(config={
        "engine": {
            "persistence": {
                "enabled": True,
                "path": str(tmp_path / "motivation_state.json"),
            }
        }
    })
    await a.initialize()
    yield a
    await a.shutdown()


# ── EmotionEngine lifecycle ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_engine_starts(engine):
    assert engine._running is True


@pytest.mark.asyncio
async def test_engine_initial_state_in_range(engine):
    dims = engine.get_dimensions()
    for v in dims.values():
        assert 0.0 <= v <= 1.0


@pytest.mark.asyncio
async def test_engine_stop_cleans_up(engine):
    await engine.stop()
    assert engine._running is False


# ── Signal processing ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signal_execution_failure_raises_frustration(engine):
    before = engine.get_dimensions()["frustration"]
    await engine.process_signal(EmotionSignal(
        source="execution", signal_type="execution_failure", intensity=0.9
    ))
    assert engine.get_dimensions()["frustration"] > before


@pytest.mark.asyncio
async def test_signal_positive_feedback_raises_satisfaction(engine):
    before = engine.get_dimensions()["satisfaction"]
    await engine.process_signal(EmotionSignal(
        source="user", signal_type="user_feedback_positive", intensity=0.9
    ))
    assert engine.get_dimensions()["satisfaction"] > before


@pytest.mark.asyncio
async def test_signal_recovery_lowers_stress(engine):
    await engine.process_signal(EmotionSignal(
        source="execution", signal_type="execution_failure", intensity=1.0
    ))
    stress_before = engine.get_dimensions()["stress"]
    await engine.process_signal(EmotionSignal(
        source="system", signal_type="recovery", intensity=1.0
    ))
    assert engine.get_dimensions()["stress"] <= stress_before


@pytest.mark.asyncio
async def test_signal_result_has_required_keys(engine):
    result = await engine.process_signal(EmotionSignal(
        source="test", signal_type="timeout", intensity=0.5
    ))
    assert "signal_id" in result
    assert "state" in result
    assert "transitions" in result
    assert "confidence_influence" in result
    assert "duration_ms" in result


@pytest.mark.asyncio
async def test_signal_dimensions_stay_bounded(engine):
    for _ in range(10):
        await engine.process_signal(EmotionSignal(
            source="execution", signal_type="execution_failure", intensity=1.0
        ))
    for v in engine.get_dimensions().values():
        assert 0.0 <= v <= 1.0


# ── Session management ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_begin_returns_session(engine):
    s = engine.begin_session(request_id="r1", correlation_id="c1", trace_id="t1")
    assert s.session_id is not None
    assert s.request_id == "r1"


@pytest.mark.asyncio
async def test_session_end_records_final_state(engine):
    s = engine.begin_session()
    await engine.process_signal(EmotionSignal(source="test", signal_type="task_completed", intensity=0.5))
    result = engine.end_session(s)
    assert result["final_state"] is not None
    assert result["ended_at"] is not None


@pytest.mark.asyncio
async def test_session_tracks_signals(engine):
    s = engine.begin_session()
    await engine.process_signal(EmotionSignal(source="test", signal_type="timeout", intensity=0.4))
    await engine.process_signal(EmotionSignal(source="test", signal_type="timeout", intensity=0.4))
    assert s.signals_processed == 2


# ── History & audit ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_state_history_grows(engine):
    await engine.process_signal(EmotionSignal(source="test", signal_type="high_load", intensity=0.6))
    assert len(engine.get_state_history()) >= 1


@pytest.mark.asyncio
async def test_audit_trail_has_events(engine):
    await engine.process_signal(EmotionSignal(source="test", signal_type="timeout", intensity=0.5))
    audit = engine.get_audit_trail()
    events = [e["event"] for e in audit]
    assert "signal_processed" in events


@pytest.mark.asyncio
async def test_metrics_count_signals(engine):
    await engine.process_signal(EmotionSignal(source="test", signal_type="task_completed", intensity=0.5))
    await engine.process_signal(EmotionSignal(source="test", signal_type="task_completed", intensity=0.5))
    assert engine.get_metrics()["total_signals"] == 2


# ── Analytics ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_returns_trends(engine):
    for _ in range(5):
        await engine.process_signal(EmotionSignal(source="test", signal_type="execution_failure", intensity=0.5))
    a = engine.get_analytics()
    assert "dimension_trends" in a
    assert "current_indicators" in a


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_signal_valid(engine):
    r = engine.validate_signal({"signal_type": "timeout", "intensity": 0.5, "source": "test"})
    assert r["valid"] is True


@pytest.mark.asyncio
async def test_validate_signal_bad_intensity(engine):
    r = engine.validate_signal({"signal_type": "timeout", "intensity": 2.0, "source": "test"})
    assert r["valid"] is False


# ── Decay ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_decay_does_not_break_bounds(engine):
    await engine.process_signal(EmotionSignal(source="test", signal_type="execution_failure", intensity=1.0))
    engine._apply_decay()
    for v in engine.get_dimensions().values():
        assert 0.0 <= v <= 1.0


# ── MotivationEngine lifecycle ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_motivation_starts(motivation):
    assert motivation._running is True


@pytest.mark.asyncio
async def test_motivation_create_goal(motivation):
    g = motivation.create_goal("u1", "Learn Python", difficulty=0.6, priority=2)
    assert g.goal_id is not None
    assert g.status == "active"


@pytest.mark.asyncio
async def test_motivation_progress_updates_streak(motivation):
    g = motivation.create_goal("u1", "Exercise")
    motivation.update_goal_progress("u1", g.goal_id, 0.5, success=True)
    assert g.streak_days == 1


@pytest.mark.asyncio
async def test_motivation_progress_to_completion(motivation):
    g = motivation.create_goal("u1", "Read book")
    motivation.update_goal_progress("u1", g.goal_id, 1.0, success=True)
    assert g.status == "completed"


@pytest.mark.asyncio
async def test_motivation_abandon_goal(motivation):
    g = motivation.create_goal("u1", "Guitar")
    ok = motivation.abandon_goal("u1", g.goal_id, reason="no time")
    assert ok is True
    assert any(g2.goal_id == g.goal_id for g2 in motivation.get_goals("u1", status="abandoned"))


@pytest.mark.asyncio
async def test_motivation_score_in_range(motivation):
    motivation.create_goal("u1", "Goal A")
    score = motivation.compute_score("u1")
    assert 0.0 <= score.overall <= 1.0


@pytest.mark.asyncio
async def test_motivation_score_confidence_influence(motivation):
    motivation.create_goal("u1", "Goal B")
    score_base = motivation.compute_score("u1", confidence_influence=0.0)
    score_boosted = motivation.compute_score("u1", confidence_influence=0.15)
    assert score_boosted.task_motivation >= score_base.task_motivation


@pytest.mark.asyncio
async def test_motivation_audit_trail(motivation):
    motivation.create_goal("u1", "Audit goal")
    audit = motivation.get_audit_trail()
    assert any(e["event"] == "goal_created" for e in audit)


@pytest.mark.asyncio
async def test_motivation_metrics(motivation):
    motivation.create_goal("u1", "Metrics goal")
    m = motivation.get_metrics()
    assert m["total_goals_created"] >= 1


@pytest.mark.asyncio
async def test_motivation_validate_valid(motivation):
    r = motivation.validate_goal_data({"title": "Valid", "difficulty": 0.5, "priority": 2})
    assert r["valid"] is True


@pytest.mark.asyncio
async def test_motivation_validate_invalid(motivation):
    r = motivation.validate_goal_data({"title": "", "difficulty": 2.0, "priority": 9})
    assert r["valid"] is False


# ── RecommendationEngine ──────────────────────────────────────────────────────

def test_rec_stress_triggers_recovery():
    rec = RecommendationEngine()
    state = {"stress": 0.85, "confidence": 0.7, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec.generate(state, motivation_score=0.6)
    assert any(r.category == "recovery" for r in recs)


def test_rec_low_confidence_triggers_confidence_rec():
    rec = RecommendationEngine()
    state = {"stress": 0.1, "confidence": 0.25, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec.generate(state, motivation_score=0.6)
    assert any(r.category == "confidence" for r in recs)


def test_rec_low_motivation_triggers_planning_rec():
    rec = RecommendationEngine()
    state = {"stress": 0.1, "confidence": 0.7, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec.generate(state, motivation_score=0.20)
    assert any(r.category == "planning" for r in recs)


def test_rec_explainability_fields_present():
    rec = RecommendationEngine()
    state = {"stress": 0.85, "confidence": 0.25, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec.generate(state, motivation_score=0.6)
    for r in recs:
        assert r.reason
        assert r.expected_impact
        assert isinstance(r.supporting_evidence, list)
        assert isinstance(r.limitations, list)
        assert isinstance(r.affected_subsystems, list)


def test_rec_capped_at_max_per_session():
    rec = RecommendationEngine()
    state = {"stress": 0.9, "confidence": 0.2, "frustration": 0.8,
             "cognitive_load": 0.9, "engagement": 0.6, "recovery": 0.1}
    recs = rec.generate(state, motivation_score=0.2, context={"consecutive_failures": 5})
    assert len(recs) <= rec._max_per_session


def test_rec_record_outcome():
    rec = RecommendationEngine()
    state = {"stress": 0.85, "confidence": 0.7, "frustration": 0.1,
             "cognitive_load": 0.3, "engagement": 0.6, "recovery": 1.0}
    recs = rec.generate(state, motivation_score=0.6)
    if recs:
        ok = rec.record_outcome(recs[0].recommendation_id, True, "improved", 0.8)
        assert ok is True


# ── EmotionContext ────────────────────────────────────────────────────────────

def test_context_fields():
    ctx = EmotionContext(request_id="r1", correlation_id="c1", trace_id="t1")
    assert ctx.request_id == "r1"
    assert ctx.context_id is not None


def test_context_execution_tracking():
    ctx = EmotionContext()
    ctx.record_execution(success=False)
    ctx.record_execution(success=False)
    assert ctx.consecutive_failures == 2
    ctx.record_execution(success=True)
    assert ctx.consecutive_failures == 0


def test_context_feedback_ratio():
    ctx = EmotionContext()
    ctx.record_feedback(positive=True)
    ctx.record_feedback(positive=False)
    assert ctx.feedback_ratio() == 0.5


def test_context_to_dict_keys():
    ctx = EmotionContext(user_id="u1")
    d = ctx.to_dict()
    for key in ("context_id", "user_id", "consecutive_failures", "system_health"):
        assert key in d


# ── EmotionAgent.execute_task ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_analyze(emotion_agent):
    r = await emotion_agent.execute_task({
        "action": "analyze",
        "input_data": {"content": "I love this!"},
    })
    assert r["status"] == "analyzed"
    assert "primary_emotion" in r


@pytest.mark.asyncio
async def test_agent_get_state(emotion_agent):
    r = await emotion_agent.execute_task({"action": "get_state", "input_data": {}})
    assert r["status"] == "ok"
    assert "dimensions" in r


@pytest.mark.asyncio
async def test_agent_process_signal(emotion_agent):
    r = await emotion_agent.execute_task({
        "action": "process_signal",
        "input_data": {"signal": {
            "signal_type": "execution_failure", "intensity": 0.7, "source": "test"
        }},
    })
    assert r["status"] == "ok"


@pytest.mark.asyncio
async def test_agent_process_signal_invalid_rejected(emotion_agent):
    r = await emotion_agent.execute_task({
        "action": "process_signal",
        "input_data": {"signal": {
            "signal_type": "execution_failure", "intensity": 5.0, "source": "test"
        }},
    })
    assert r["status"] == "error"


@pytest.mark.asyncio
async def test_agent_get_recommendations(emotion_agent):
    r = await emotion_agent.execute_task({
        "action": "get_recommendations",
        "input_data": {"motivation_score": 0.2},
    })
    assert r["status"] == "ok"
    assert isinstance(r["recommendations"], list)


@pytest.mark.asyncio
async def test_agent_session_lifecycle(emotion_agent):
    begin = await emotion_agent.execute_task({
        "action": "begin_session",
        "input_data": {"request_id": "r1"},
    })
    assert begin["status"] == "ok"
    end = await emotion_agent.execute_task({"action": "end_session", "input_data": {}})
    assert end["status"] == "ok"


@pytest.mark.asyncio
async def test_agent_engine_metrics(emotion_agent):
    r = await emotion_agent.execute_task({"action": "get_engine_metrics", "input_data": {}})
    assert r["status"] == "ok"
    assert "total_signals" in r["metrics"]


@pytest.mark.asyncio
async def test_agent_audit_trail(emotion_agent):
    await emotion_agent.execute_task({
        "action": "process_signal",
        "input_data": {"signal": {"signal_type": "timeout", "intensity": 0.5, "source": "test"}},
    })
    r = await emotion_agent.execute_task({"action": "get_audit_trail", "input_data": {}})
    assert r["status"] == "ok"
    assert len(r["audit_trail"]) >= 1


@pytest.mark.asyncio
async def test_agent_confidence_influence(emotion_agent):
    r = await emotion_agent.execute_task({"action": "get_confidence_influence", "input_data": {}})
    assert r["status"] == "ok"
    assert isinstance(r["confidence_influence"], float)


# ── MotivationAgent.execute_task ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_motivation_agent_motivate(motivation_agent):
    r = await motivation_agent.execute_task({
        "action": "motivate",
        "input_data": {"content": "I feel like giving up."},
    })
    assert "message" in r
    assert "struggle_detected" in r


@pytest.mark.asyncio
async def test_motivation_agent_celebrate(motivation_agent):
    r = await motivation_agent.execute_task({
        "action": "celebrate",
        "input_data": {"achievement": "Finished the project"},
    })
    assert r["type"] == "celebration"
    assert "message" in r


@pytest.mark.asyncio
async def test_motivation_agent_track_goal(motivation_agent):
    r = await motivation_agent.execute_task({
        "action": "track_goal",
        "input_data": {"goal": "Run 5km daily"},
        "user_id": "u1",
    })
    assert r["tracked"] is True


@pytest.mark.asyncio
async def test_motivation_agent_create_goal(motivation_agent):
    r = await motivation_agent.execute_task({
        "action": "create_goal",
        "input_data": {"title": "Learn Rust", "difficulty": 0.7, "priority": 2},
        "user_id": "u1",
    })
    assert r["status"] == "created"
    assert "goal" in r


@pytest.mark.asyncio
async def test_motivation_agent_update_progress(motivation_agent):
    create = await motivation_agent.execute_task({
        "action": "create_goal",
        "input_data": {"title": "Write tests", "difficulty": 0.5, "priority": 2},
        "user_id": "u1",
    })
    goal_id = create["goal"]["goal_id"]
    r = await motivation_agent.execute_task({
        "action": "update_progress",
        "input_data": {"goal_id": goal_id, "progress": 0.6, "success": True},
        "user_id": "u1",
    })
    assert r["status"] == "updated"
    assert r["goal"]["progress"] == 0.6


@pytest.mark.asyncio
async def test_motivation_agent_get_score(motivation_agent):
    await motivation_agent.execute_task({
        "action": "create_goal",
        "input_data": {"title": "Score goal", "difficulty": 0.5, "priority": 2},
        "user_id": "u1",
    })
    r = await motivation_agent.execute_task({
        "action": "get_motivation_score",
        "input_data": {},
        "user_id": "u1",
    })
    assert r["status"] == "ok"
    assert 0.0 <= r["score"]["overall"] <= 1.0


@pytest.mark.asyncio
async def test_motivation_agent_get_analytics(motivation_agent):
    await motivation_agent.execute_task({
        "action": "create_goal",
        "input_data": {"title": "Analytics goal", "difficulty": 0.5, "priority": 2},
        "user_id": "u1",
    })
    await motivation_agent.execute_task({
        "action": "get_motivation_score", "input_data": {}, "user_id": "u1"
    })
    r = await motivation_agent.execute_task({
        "action": "get_analytics", "input_data": {}, "user_id": "u1"
    })
    assert r["status"] == "ok"
    assert "current_score" in r["analytics"]


@pytest.mark.asyncio
async def test_motivation_agent_abandon_goal(motivation_agent):
    create = await motivation_agent.execute_task({
        "action": "create_goal",
        "input_data": {"title": "Abandon me", "difficulty": 0.5, "priority": 3},
        "user_id": "u1",
    })
    goal_id = create["goal"]["goal_id"]
    r = await motivation_agent.execute_task({
        "action": "abandon_goal",
        "input_data": {"goal_id": goal_id, "reason": "changed priorities"},
        "user_id": "u1",
    })
    assert r["status"] == "abandoned"


@pytest.mark.asyncio
async def test_motivation_agent_get_metrics(motivation_agent):
    r = await motivation_agent.execute_task({
        "action": "get_metrics", "input_data": {}, "user_id": "u1"
    })
    assert r["status"] == "ok"
    assert "total_goals_created" in r["metrics"]


# ── Emotion → Motivation integration ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_emotion_confidence_influence_affects_motivation(engine, motivation):
    # Drive confidence down via signals
    for _ in range(5):
        await engine.process_signal(EmotionSignal(
            source="execution", signal_type="execution_failure", intensity=0.9
        ))
    influence = engine.get_confidence_influence()
    motivation.create_goal("u1", "Integration goal")
    score_with = motivation.compute_score("u1", confidence_influence=influence)
    score_without = motivation.compute_score("u1", confidence_influence=0.0)
    # Negative influence should lower task_motivation
    if influence < 0:
        assert score_with.task_motivation <= score_without.task_motivation


@pytest.mark.asyncio
async def test_recommendations_use_engine_state(engine):
    rec = RecommendationEngine()
    await engine.process_signal(EmotionSignal(
        source="execution", signal_type="execution_failure", intensity=1.0
    ))
    state = engine.get_dimensions()
    recs = rec.generate(state, motivation_score=0.6)
    assert isinstance(recs, list)


@pytest.mark.asyncio
async def test_emotion_context_threads_through_pipeline(engine):
    ctx = EmotionContext(request_id="r1", correlation_id="c1", trace_id="t1")
    signal = EmotionSignal(
        source="execution",
        signal_type="execution_failure",
        intensity=0.7,
        correlation_id=ctx.correlation_id,
        trace_id=ctx.trace_id,
    )
    result = await engine.process_signal(signal)
    assert result["signal_id"] is not None
    ctx.record_execution(success=False, latency_ms=120.0)
    assert ctx.consecutive_failures == 1
