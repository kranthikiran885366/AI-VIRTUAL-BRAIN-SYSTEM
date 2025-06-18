import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from .emotion_processor import EmotionProcessor
from .emotion_store import EmotionStore
from .emotion_analyzer import EmotionAnalyzer
from .main import EmotionAgent, EmotionData, EmotionQuery

@pytest.fixture
async def emotion_processor():
    """Create an emotion processor instance."""
    processor = EmotionProcessor()
    await processor.initialize()
    yield processor
    await processor.shutdown()

@pytest.fixture
async def emotion_store():
    """Create an emotion store instance."""
    store = EmotionStore()
    await store.initialize()
    yield store
    await store.shutdown()

@pytest.fixture
async def emotion_analyzer():
    """Create an emotion analyzer instance."""
    analyzer = EmotionAnalyzer()
    await analyzer.initialize()
    yield analyzer
    await analyzer.shutdown()

@pytest.fixture
async def emotion_agent():
    """Create an emotion agent instance."""
    agent = EmotionAgent()
    await agent.initialize()
    yield agent
    await agent.shutdown()

@pytest.mark.asyncio
async def test_emotion_processor(emotion_processor):
    """Test emotion processor functionality."""
    # Test processing new emotion
    emotion_data = {
        "type": "joy",
        "intensity": 0.8,
        "source": "test",
        "context": {"test": "context"}
    }
    emotion = await emotion_processor.process_emotion(emotion_data)
    assert emotion["type"] == "joy"
    assert emotion["intensity"] == 0.8
    
    # Test emotion decay
    await asyncio.sleep(1)
    current_emotions = await emotion_processor.get_current_emotions()
    assert current_emotions["joy"]["intensity"] < 0.8
    
    # Test emotion history
    history = await emotion_processor.get_emotion_history()
    assert len(history) > 0
    assert history[0]["type"] == "joy"

@pytest.mark.asyncio
async def test_emotion_store(emotion_store):
    """Test emotion store functionality."""
    # Test storing emotion
    emotion_data = {
        "type": "sadness",
        "intensity": 0.6,
        "source": "test",
        "context": {"test": "context"}
    }
    emotion_id = await emotion_store.store_emotion(emotion_data)
    assert emotion_id is not None
    
    # Test retrieving emotion
    emotion = await emotion_store.get_emotion(emotion_id)
    assert emotion["type"] == "sadness"
    assert emotion["intensity"] == 0.6
    
    # Test searching emotions
    results = await emotion_store.search_emotions({"type": "sadness"})
    assert len(results) > 0
    assert results[0]["type"] == "sadness"

@pytest.mark.asyncio
async def test_emotion_analyzer(emotion_analyzer):
    """Test emotion analyzer functionality."""
    # Test analyzing emotion
    emotion_data = {
        "type": "anger",
        "intensity": 0.9,
        "source": "test",
        "context": {"test": "context"}
    }
    analysis = await emotion_analyzer.analyze_emotion(emotion_data)
    assert analysis["emotion_type"] == "anger"
    assert "patterns" in analysis
    assert "impact" in analysis
    assert "recommendations" in analysis
    
    # Test getting analysis history
    history = await emotion_analyzer.get_analysis()
    assert len(history) > 0
    assert history[0]["emotion_type"] == "anger"

@pytest.mark.asyncio
async def test_emotion_agent(emotion_agent):
    """Test emotion agent functionality."""
    # Test adding emotion
    emotion_data = EmotionData(
        type="fear",
        intensity=0.7,
        source="test",
        context={"test": "context"}
    )
    response = await emotion_agent.add_emotion(emotion_data)
    assert response["status"] == "success"
    assert "emotion_id" in response
    
    # Test getting emotion
    emotion = await emotion_agent.get_emotion(response["emotion_id"])
    assert emotion["type"] == "fear"
    assert emotion["intensity"] == 0.7
    
    # Test searching emotions
    query = EmotionQuery(type="fear")
    results = await emotion_agent.search_emotions(query)
    assert len(results) > 0
    assert results[0]["type"] == "fear"
    
    # Test getting current emotions
    current = await emotion_agent.get_current_emotions()
    assert "fear" in current
    assert current["fear"]["intensity"] == 0.7

@pytest.mark.asyncio
async def test_emotion_agent_integration(emotion_agent):
    """Test emotion agent integration with other components."""
    # Test emotion processing and analysis
    emotion_data = EmotionData(
        type="joy",
        intensity=0.9,
        source="test",
        context={"test": "context"}
    )
    response = await emotion_agent.add_emotion(emotion_data)
    assert response["status"] == "success"
    
    # Test emotion decay
    await asyncio.sleep(1)
    current = await emotion_agent.get_current_emotions()
    assert current["joy"]["intensity"] < 0.9
    
    # Test emotion history
    history = await emotion_agent.get_emotion_history()
    assert len(history) > 0
    assert history[0]["type"] == "joy"
    
    # Test emotion analysis
    analysis = await emotion_agent.get_emotion_analysis(response["emotion_id"])
    assert analysis["emotion_type"] == "joy"
    assert "patterns" in analysis
    assert "impact" in analysis
    assert "recommendations" in analysis

@pytest.mark.asyncio
async def test_emotion_agent_error_handling(emotion_agent):
    """Test emotion agent error handling."""
    # Test invalid emotion data
    with pytest.raises(ValueError):
        await emotion_agent.add_emotion(EmotionData(
            type="invalid",
            intensity=1.5,  # Invalid intensity
            source="test",
            context={}
        ))
    
    # Test non-existent emotion
    with pytest.raises(ValueError):
        await emotion_agent.get_emotion("non-existent-id")
    
    # Test invalid search query
    with pytest.raises(ValueError):
        await emotion_agent.search_emotions(EmotionQuery(invalid_field="test")) 