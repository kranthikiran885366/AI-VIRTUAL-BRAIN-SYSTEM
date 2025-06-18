import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List

from agents.memory_agent.main import MemoryAgent, MemoryData, MemoryQuery
from agents.memory_agent.config import settings

@pytest.fixture
async def memory_agent():
    """Create a Memory Agent instance for testing."""
    agent = MemoryAgent()
    await agent.initialize()
    yield agent
    await agent.shutdown()

@pytest.mark.asyncio
async def test_memory_agent_initialization(memory_agent):
    """Test Memory Agent initialization."""
    assert memory_agent.agent_type == "memory"
    assert memory_agent.state == {}
    assert memory_agent.memory == []
    assert memory_agent.emotions == {}
    assert memory_agent.connections == []

@pytest.mark.asyncio
async def test_add_memory(memory_agent):
    """Test adding a memory."""
    memory_data = MemoryData(
        type="test",
        content="Test memory content",
        importance=0.8,
        emotions={"happiness": 0.5},
        connections=["agent1", "agent2"]
    )
    
    response = await memory_agent.app.post("/memories", json=memory_data.dict())
    assert response.status_code == 200
    assert "memory_id" in response.json()
    
    # Verify memory was added to short-term memory
    short_term_count = await memory_agent.short_term.get_memory_count()
    assert short_term_count == 1
    
    # Verify memory was added to long-term memory (importance >= threshold)
    long_term_count = await memory_agent.long_term.get_memory_count()
    assert long_term_count == 1
    
    # Verify memory was stored
    store_count = await memory_agent.store.get_memory_count()
    assert store_count == 1

@pytest.mark.asyncio
async def test_get_memory(memory_agent):
    """Test getting a memory."""
    # Add a memory first
    memory_data = MemoryData(
        type="test",
        content="Test memory content",
        importance=0.8
    )
    
    response = await memory_agent.app.post("/memories", json=memory_data.dict())
    memory_id = response.json()["memory_id"]
    
    # Get the memory
    response = await memory_agent.app.get(f"/memories/{memory_id}")
    assert response.status_code == 200
    
    memory = response.json()
    assert memory["id"] == memory_id
    assert memory["type"] == "test"
    assert memory["content"] == "Test memory content"
    assert memory["importance"] == 0.8

@pytest.mark.asyncio
async def test_search_memories(memory_agent):
    """Test searching memories."""
    # Add multiple memories
    memories = [
        MemoryData(type="test1", content="First test memory", importance=0.8),
        MemoryData(type="test2", content="Second test memory", importance=0.6),
        MemoryData(type="test1", content="Third test memory", importance=0.9)
    ]
    
    for memory in memories:
        await memory_agent.app.post("/memories", json=memory.dict())
    
    # Search by type
    query = MemoryQuery(type="test1")
    response = await memory_agent.app.post("/memories/search", json=query.dict())
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert all(r["type"] == "test1" for r in results)
    
    # Search by content
    query = MemoryQuery(content="Second")
    response = await memory_agent.app.post("/memories/search", json=query.dict())
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["content"] == "Second test memory"

@pytest.mark.asyncio
async def test_context_management(memory_agent):
    """Test context management."""
    # Add a memory to update context
    memory_data = MemoryData(
        type="test",
        content="Test memory content",
        importance=0.8
    )
    
    await memory_agent.app.post("/memories", json=memory_data.dict())
    
    # Get current context
    response = await memory_agent.app.get("/context")
    assert response.status_code == 200
    context = response.json()
    assert context["type"] == "memory_added"
    assert "memory_id" in context["data"]
    
    # Get context history
    response = await memory_agent.app.get("/context/history")
    assert response.status_code == 200
    history = response.json()
    assert len(history) > 0
    assert all("timestamp" in c for c in history)

@pytest.mark.asyncio
async def test_memory_consolidation(memory_agent):
    """Test memory consolidation."""
    # Add memories with different importance levels
    memories = [
        MemoryData(type="test", content=f"Memory {i}", importance=imp)
        for i, imp in enumerate([0.3, 0.5, 0.7, 0.9])
    ]
    
    for memory in memories:
        await memory_agent.app.post("/memories", json=memory.dict())
    
    # Wait for consolidation
    await asyncio.sleep(settings.PROCESSING_INTERVAL * 2)
    
    # Check short-term memory (should have all memories)
    short_term_count = await memory_agent.short_term.get_memory_count()
    assert short_term_count == 4
    
    # Check long-term memory (should have memories with importance >= threshold)
    long_term_count = await memory_agent.long_term.get_memory_count()
    assert long_term_count == 2  # Only memories with importance >= 0.7

@pytest.mark.asyncio
async def test_memory_cleanup(memory_agent):
    """Test memory cleanup."""
    # Add memories
    for i in range(settings.SHORT_TERM_MEMORY_MAX_SIZE + 10):
        memory_data = MemoryData(
            type="test",
            content=f"Memory {i}",
            importance=0.5
        )
        await memory_agent.app.post("/memories", json=memory_data.dict())
    
    # Wait for cleanup
    await asyncio.sleep(settings.PROCESSING_INTERVAL * 2)
    
    # Check short-term memory count (should be at max size)
    short_term_count = await memory_agent.short_term.get_memory_count()
    assert short_term_count <= settings.SHORT_TERM_MEMORY_MAX_SIZE

@pytest.mark.asyncio
async def test_memory_stats(memory_agent):
    """Test memory statistics."""
    # Add some memories
    for i in range(5):
        memory_data = MemoryData(
            type="test",
            content=f"Memory {i}",
            importance=0.8
        )
        await memory_agent.app.post("/memories", json=memory_data.dict())
    
    # Get stats
    response = await memory_agent.app.get("/stats")
    assert response.status_code == 200
    stats = response.json()
    
    assert "short_term" in stats
    assert "long_term" in stats
    assert "context" in stats
    assert "store" in stats
    
    assert stats["short_term"]["memory_count"] == 5
    assert stats["long_term"]["memory_count"] == 5
    assert stats["store"]["memory_count"] == 5 