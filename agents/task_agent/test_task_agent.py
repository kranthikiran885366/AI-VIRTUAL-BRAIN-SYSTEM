import pytest
import asyncio
from datetime import datetime, timedelta
import uuid
from typing import Dict, List

from .main import TaskAgent
from .task_processor import TaskProcessor
from .task_store import TaskStore
from .task_analyzer import TaskAnalyzer
from .task_automation import TaskAutomation
from .config import settings

@pytest.fixture
async def task_processor():
    """Create a TaskProcessor instance for testing."""
    processor = TaskProcessor()
    await processor.initialize()
    yield processor
    await processor.shutdown()

@pytest.fixture
async def task_store():
    """Create a TaskStore instance for testing."""
    store = TaskStore()
    await store.initialize()
    yield store
    await store.shutdown()

@pytest.fixture
async def task_analyzer():
    """Create a TaskAnalyzer instance for testing."""
    analyzer = TaskAnalyzer()
    await analyzer.initialize()
    yield analyzer
    await analyzer.shutdown()

@pytest.fixture
async def task_automation():
    """Create a TaskAutomation instance for testing."""
    automation = TaskAutomation()
    await automation.initialize()
    yield automation
    await automation.shutdown()

@pytest.fixture
async def task_agent():
    """Create a TaskAgent instance for testing."""
    agent = TaskAgent()
    await agent.initialize()
    yield agent
    await agent.shutdown()

@pytest.mark.asyncio
async def test_task_processor(task_processor):
    """Test task processor functionality."""
    # Create test task
    task = {
        "id": str(uuid.uuid4()),
        "title": "Test Task",
        "description": "Test task description",
        "priority": 1,
        "status": "pending",
        "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "tags": ["test", "automation"],
        "dependencies": []
    }
    
    # Process task
    processed_task = await task_processor.process_task(task)
    assert processed_task["id"] == task["id"]
    assert processed_task["status"] == "processing"
    
    # Get current tasks
    current_tasks = await task_processor.get_current_tasks()
    assert len(current_tasks) > 0
    assert any(t["id"] == task["id"] for t in current_tasks)
    
    # Search tasks
    search_results = await task_processor.search_tasks({"status": "processing"})
    assert len(search_results) > 0
    assert any(t["id"] == task["id"] for t in search_results)

@pytest.mark.asyncio
async def test_task_store(task_store):
    """Test task store functionality."""
    # Create test task
    task = {
        "id": str(uuid.uuid4()),
        "title": "Test Task",
        "description": "Test task description",
        "priority": 1,
        "status": "pending",
        "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "tags": ["test", "storage"],
        "dependencies": []
    }
    
    # Store task
    stored_task = await task_store.store_task(task)
    assert stored_task["id"] == task["id"]
    
    # Get task
    retrieved_task = await task_store.get_task(task["id"])
    assert retrieved_task["id"] == task["id"]
    assert retrieved_task["title"] == task["title"]
    
    # Search tasks
    search_results = await task_store.search_tasks({"tags": ["test"]})
    assert len(search_results) > 0
    assert any(t["id"] == task["id"] for t in search_results)
    
    # Update task
    updated_task = await task_store.update_task(task["id"], {"status": "completed"})
    assert updated_task["status"] == "completed"
    
    # Delete task
    await task_store.delete_task(task["id"])
    with pytest.raises(ValueError):
        await task_store.get_task(task["id"])

@pytest.mark.asyncio
async def test_task_analyzer(task_analyzer):
    """Test task analyzer functionality."""
    # Create test task
    task = {
        "id": str(uuid.uuid4()),
        "title": "Test Task",
        "description": "Test task description",
        "priority": 1,
        "status": "pending",
        "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "tags": ["test", "analysis"],
        "dependencies": []
    }
    
    # Analyze task
    analysis = await task_analyzer.analyze_task(task)
    assert analysis["task_id"] == task["id"]
    assert "patterns" in analysis
    assert "metrics" in analysis
    assert "recommendations" in analysis
    
    # Get analysis
    current_analysis = await task_analyzer.get_analysis()
    assert current_analysis["history_size"] > 0
    assert "patterns" in current_analysis
    assert "metrics" in current_analysis
    
    # Get stats
    stats = await task_analyzer.get_stats()
    assert stats["analysis_count"] > 0
    assert stats["pattern_count"] >= 0
    assert stats["metric_count"] >= 0

@pytest.mark.asyncio
async def test_task_automation(task_automation):
    """Test task automation functionality."""
    # Create test rule
    rule = {
        "conditions": [
            {
                "field": "tags",
                "operator": "contains",
                "value": "automation"
            }
        ],
        "actions": [
            {
                "type": "notify",
                "message": "Automated task detected",
                "priority": "high"
            }
        ]
    }
    
    # Add rule
    rule_id = await task_automation.add_rule(rule)
    assert rule_id in await task_automation.get_rules()
    
    # Create test task
    task = {
        "id": str(uuid.uuid4()),
        "title": "Test Task",
        "description": "Test task description",
        "priority": 1,
        "status": "pending",
        "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "tags": ["test", "automation"],
        "dependencies": []
    }
    
    # Process task with automation
    await task_automation._process_task(task)
    
    # Check execution history
    history = await task_automation.get_execution_history()
    assert len(history) > 0
    assert any(e["task_id"] == task["id"] for e in history)
    
    # Update rule
    updated_rule = {
        "conditions": [
            {
                "field": "tags",
                "operator": "contains",
                "value": "automation"
            }
        ],
        "actions": [
            {
                "type": "notify",
                "message": "Updated automated task detected",
                "priority": "high"
            }
        ]
    }
    await task_automation.update_rule(rule_id, updated_rule)
    
    # Delete rule
    await task_automation.delete_rule(rule_id)
    with pytest.raises(ValueError):
        await task_automation.get_rule(rule_id)

@pytest.mark.asyncio
async def test_task_agent(task_agent):
    """Test task agent functionality."""
    # Create test task
    task = {
        "title": "Test Task",
        "description": "Test task description",
        "priority": 1,
        "status": "pending",
        "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "tags": ["test", "agent"],
        "dependencies": []
    }
    
    # Add task
    added_task = await task_agent.add_task(task)
    assert "id" in added_task
    assert added_task["title"] == task["title"]
    
    # Get task
    retrieved_task = await task_agent.get_task(added_task["id"])
    assert retrieved_task["id"] == added_task["id"]
    
    # Search tasks
    search_results = await task_agent.search_tasks({"tags": ["test"]})
    assert len(search_results) > 0
    assert any(t["id"] == added_task["id"] for t in search_results)
    
    # Get current tasks
    current_tasks = await task_agent.get_current_tasks()
    assert len(current_tasks) > 0
    assert any(t["id"] == added_task["id"] for t in current_tasks)

@pytest.mark.asyncio
async def test_task_agent_integration(task_agent):
    """Test task agent integration with other components."""
    # Create test task
    task = {
        "title": "Test Task",
        "description": "Test task description",
        "priority": 1,
        "status": "pending",
        "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "tags": ["test", "integration"],
        "dependencies": []
    }
    
    # Add task
    added_task = await task_agent.add_task(task)
    
    # Wait for processing
    await asyncio.sleep(1)
    
    # Check task was processed
    processed_task = await task_agent.get_task(added_task["id"])
    assert processed_task["status"] in ["processing", "completed"]
    
    # Check analysis was performed
    analysis = await task_agent.task_analyzer.get_analysis()
    assert analysis["history_size"] > 0
    
    # Check automation was triggered
    automation_history = await task_agent.task_automation.get_execution_history()
    assert len(automation_history) > 0

@pytest.mark.asyncio
async def test_task_agent_error_handling(task_agent):
    """Test task agent error handling."""
    # Test invalid task data
    with pytest.raises(ValueError):
        await task_agent.add_task({})
    
    # Test non-existent task
    with pytest.raises(ValueError):
        await task_agent.get_task("non_existent_id")
    
    # Test invalid search query
    with pytest.raises(ValueError):
        await task_agent.search_tasks({"invalid_field": "value"})
    
    # Test invalid automation rule
    with pytest.raises(ValueError):
        await task_agent.task_automation.add_rule({})