"""
Phase 4: Production Emotion Intelligence System Tests
Covers: emotion processing, storage, analysis, automation, pipeline integration.
"""
import asyncio
import pytest
from agents.emotion_agent.main import EmotionAgent
from orchestrator.execution_pipeline import execute_via_pipeline


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def agent():
    a = EmotionAgent()
    await a.initialize()
    # Ensure sub-components are initialized
    if a.processor:
        await a.processor.initialize()
    if a.store:
        await a.store.initialize()
    if a.analyzer:
        await a.analyzer.initialize()
    yield a
    # Cleanup
    if a.processor:
        await a.processor.clear_emotions()
    if a.store:
        await a.store.clear_emotions()
    if a.analyzer:
        await a.analyzer.clear_analysis()


# ── 1. Agent initializes all sub-components ───────────────────────────────────

@pytest.mark.asyncio
async def test_emotion_agent_initializes():
    a = EmotionAgent()
    await a.initialize()
    assert a.processor is not None
    assert a.store is not None
    assert a.analyzer is not None
    assert a.automation is not None
    await a.shutdown()


# ── 2. Text analysis returns structured result ────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_text_positive(agent):
    result = agent._analyze_text("I am so happy and excited today!")
    assert result["primary_emotion"] in ("joy", "anticipation", "trust")
    assert result["sentiment"] == "positive"
    assert 0.0 <= result["confidence"] <= 1.0
    assert "emotions" in result


@pytest.mark.asyncio
async def test_analyze_text_negative(agent):
    result = agent._analyze_text("I feel sad and angry about this.")
    assert result["sentiment"] == "negative"
    assert result["primary_emotion"] in ("sadness", "anger", "fear", "disgust")


@pytest.mark.asyncio
async def test_analyze_text_neutral(agent):
    result = agent._analyze_text("The meeting is at 3pm.")
    assert result["primary_emotion"] == "neutral"
    assert result["sentiment"] == "neutral"


# ── 3. execute_task analyze action ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_task_analyze(agent):
    result = await agent.execute_task({
        "action": "analyze",
        "input_data": {"content": "I love this project!"},
    })
    assert result["status"] == "analyzed"
    assert "primary_emotion" in result
    assert "emotions" in result


# ── 4. execute_task store action ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_task_store(agent):
    result = await agent.execute_task({
        "action": "store",
        "input_data": {
            "type": "joy",
            "intensity": 0.8,
            "source": "user_input",
            "context": {"topic": "work"},
        },
    })
    assert result["status"] == "stored"
    assert "emotion_id" in result
    assert result["emotion"]["type"] == "joy"


# ── 5. execute_task recall action ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_task_recall(agent):
    # Store first
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
    assert all(e["type"] == "fear" for e in result["emotions"])


# ── 6. execute_task get_stats action ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_task_get_stats(agent):
    result = await agent.execute_task({"action": "get_stats", "input_data": {}})
    assert result["status"] == "ok"
    assert "stats" in result
    assert "processor" in result["stats"]
    assert "store" in result["stats"]


# ── 7. execute_task get_history action ────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_task_get_history(agent):
    # Process an emotion first
    await agent.processor.process_emotion({"type": "surprise", "intensity": 0.5, "source": "test"})
    result = await agent.execute_task({"action": "get_history", "input_data": {}})
    assert result["status"] == "ok"
    assert result["count"] >= 1
    assert isinstance(result["history"], list)


# ── 8. execute_task clear action ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_task_clear(agent):
    await agent.execute_task({
        "action": "store",
        "input_data": {"type": "anger", "intensity": 0.7, "source": "test"},
    })
    result = await agent.execute_task({"action": "clear", "input_data": {}})
    assert result["status"] == "cleared"
    # Verify cleared
    stats = await agent.execute_task({"action": "get_stats", "input_data": {}})
    assert stats["stats"]["store"]["emotion_count"] == 0


# ── 9. Emotion processor decay tracking ───────────────────────────────────────

@pytest.mark.asyncio
async def test_processor_tracks_current_emotions(agent):
    await agent.processor.process_emotion({"type": "trust", "intensity": 0.9, "source": "test"})
    current = await agent.processor.get_current_emotions()
    assert "trust" in current
    assert current["trust"]["intensity"] == 0.9


# ── 10. Emotion store search by intensity ─────────────────────────────────────

@pytest.mark.asyncio
async def test_store_search_by_min_intensity(agent):
    await agent.store.store_emotion({"type": "joy", "intensity": 0.9, "source": "test"})
    await agent.store.store_emotion({"type": "joy", "intensity": 0.2, "source": "test"})
    results = await agent.store.search_emotions({"min_intensity": 0.7})
    assert all(e["intensity"] >= 0.7 for e in results)
    assert len(results) >= 1


# ── 11. Emotion analyzer detects recurring patterns ───────────────────────────

@pytest.mark.asyncio
async def test_analyzer_detects_recurring_pattern(agent):
    base_emotion = {"id": "e1", "type": "sadness", "intensity": 0.6, "source": "test", "context": {}}
    # Seed history with recurring sadness
    for i in range(4):
        e = {**base_emotion, "id": f"e{i}"}
        agent.analyzer.analysis_history.append({
            "emotion_type": "sadness",
            "emotion_id": e["id"],
            "timestamp": "2024-01-01T00:00:00",
        })
    analysis = await agent.analyzer.analyze_emotion(base_emotion)
    recurring = [p for p in analysis["patterns"] if p["type"] == "recurring"]
    assert len(recurring) >= 1
    assert recurring[0]["emotion_type"] == "sadness"


# ── 12. Emotion automation initializes without crashing ───────────────────────

@pytest.mark.asyncio
async def test_automation_initializes(agent):
    assert agent.automation._initialized is True
    stats = await agent.automation.get_stats()
    assert "rule_count" in stats
    assert "execution_count" in stats


# ── 13. Multiple emotion types stored and recalled independently ───────────────

@pytest.mark.asyncio
async def test_store_multiple_emotion_types(agent):
    for etype in ("joy", "sadness", "anger"):
        await agent.store.store_emotion({"type": etype, "intensity": 0.5, "source": "test"})
    for etype in ("joy", "sadness", "anger"):
        results = await agent.store.search_emotions({"type": etype})
        assert len(results) == 1
        assert results[0]["type"] == etype


# ── 14. Pipeline integration ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execution_pipeline_integration():
    emotion_agent = EmotionAgent()
    await emotion_agent.initialize()
    if emotion_agent.processor:
        await emotion_agent.processor.initialize()
    if emotion_agent.store:
        await emotion_agent.store.initialize()
    if emotion_agent.analyzer:
        await emotion_agent.analyzer.initialize()

    class DummyAgentManager:
        def __init__(self, agent):
            self._agent = agent

        async def execute_agent_task(self, agent_name, task, timeout_seconds=None, execution_context=None):
            return await self._agent.execute_task(task)

    class DummyScheduler:
        def __init__(self, agent_manager):
            self._am = agent_manager
            self._task = None

        async def schedule_task(self, task):
            self._task = task
            return task["id"]

        async def wait_for_task(self, task_id, timeout=None):
            result = await self._am.execute_agent_task(
                self._task["parameters"]["agent_name"],
                {
                    "action": self._task["parameters"]["action"],
                    "input_data": self._task["parameters"].get("input_data", {}),
                },
            )
            return {"id": task_id, "status": "completed", "result": result}

    am = DummyAgentManager(emotion_agent)
    scheduler = DummyScheduler(am)

    result = await execute_via_pipeline(
        agent_name="emotion_agent",
        action="analyze",
        input_data={"content": "I feel wonderful today!"},
        user_id="u1",
        conversation_id="c1",
        priority="high",
        task_scheduler=scheduler,
        agent_manager=am,
        communication_controller=None,
        message_broker=None,
    )

    assert result["status"] == "completed"
    inner = result.get("result", result)
    assert inner.get("status") == "analyzed"
    assert "primary_emotion" in inner

    await emotion_agent.shutdown()
