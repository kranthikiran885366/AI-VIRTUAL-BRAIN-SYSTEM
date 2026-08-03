"""Comprehensive tests for Phase 7 - Production Learning Engine."""

import asyncio
import pytest
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from agents.learning_agent import (
    LearningAgent,
    LearningContext,
    LearningSessionStatus,
    ExperienceClassification,
    ExperienceRecord,
)


@pytest.fixture
def learning_agent():
    """Create a learning agent instance for testing."""
    config = {
        "max_experiences": 1000,
        "max_patterns": 500,
        "max_learning_sessions": 50,
        "quality_threshold": 0.7,
        "confidence_threshold": 0.6,
        "failure_pattern_threshold": 3,
    }
    agent = LearningAgent(agent_id="test_learning", config=config)
    return agent


@pytest.fixture
async def initialized_agent(learning_agent):
    """Initialize learning agent."""
    await learning_agent.initialize()
    yield learning_agent


# Test Suite 1: Learning Lifecycle
@pytest.mark.asyncio
async def test_create_learning_session(initialized_agent):
    """Test learning session creation."""
    context = LearningContext(
        request_id="req-001",
        correlation_id="corr-001",
        trace_id="trace-001",
        session_id="sess-001",
    )
    
    session = await initialized_agent.create_learning_session(context)
    
    assert session["session_id"] == "sess-001"
    assert session["status"] == LearningSessionStatus.INITIATED.value
    assert "context" in session
    assert "created_at" in session


@pytest.mark.asyncio
async def test_learning_session_workflow(initialized_agent):
    """Test complete learning session workflow."""
    context = LearningContext(
        request_id="req-002",
        correlation_id="corr-002",
        trace_id="trace-002",
        session_id="sess-002",
    )
    
    # Create
    session = await initialized_agent.create_learning_session(context)
    assert session["status"] == LearningSessionStatus.INITIATED.value
    
    # Start
    session = await initialized_agent.start_learning_session(session["session_id"])
    assert session["status"] == LearningSessionStatus.ACTIVE.value
    assert session["started_at"] is not None
    
    # End
    session = await initialized_agent.end_learning_session(session["session_id"], "completed")
    assert session["status"] == "completed"
    assert session["ended_at"] is not None


# Test Suite 2: Experience Recording
@pytest.mark.asyncio
async def test_record_success_experience(initialized_agent):
    """Test recording a successful experience."""
    context = LearningContext(
        request_id="req-003",
        correlation_id="corr-003",
        trace_id="trace-003",
        session_id="sess-003",
    )
    session = await initialized_agent.create_learning_session(context)
    
    experience = {
        "description": "Successful query resolution",
        "context": {"agent_type": "decision_agent"},
        "metrics": {"latency_ms": 150, "success": True},
        "confidence": 0.95,
    }
    
    record = await initialized_agent.record_experience(session["session_id"], experience)
    
    assert record.classification == ExperienceClassification.SUCCESS.value
    assert record.confidence == 0.95
    assert record.session_id == session["session_id"]


@pytest.mark.asyncio
async def test_record_failure_experience(initialized_agent):
    """Test recording a failure experience."""
    context = LearningContext(
        request_id="req-004",
        correlation_id="corr-004",
        trace_id="trace-004",
        session_id="sess-004",
    )
    session = await initialized_agent.create_learning_session(context)
    
    experience = {
        "description": "Query resolution failed",
        "context": {"agent_type": "decision_agent"},
        "error": RuntimeError("Connection timeout"),
        "metrics": {"latency_ms": 5000, "success": False},
        "confidence": 0.3,
    }
    
    record = await initialized_agent.record_experience(session["session_id"], experience)
    
    assert record.classification == ExperienceClassification.FAILURE.value
    assert record.error_info is not None
    assert record.root_cause is not None


@pytest.mark.asyncio
async def test_record_anomaly_experience(initialized_agent):
    """Test recording an anomaly experience."""
    context = LearningContext(
        request_id="req-005",
        correlation_id="corr-005",
        trace_id="trace-005",
        session_id="sess-005",
    )
    session = await initialized_agent.create_learning_session(context)
    
    experience = {
        "description": "Unexpected behavior detected",
        "context": {"agent_type": "memory_agent"},
        "anomaly": True,
        "metrics": {"latency_ms": 500},
    }
    
    record = await initialized_agent.record_experience(session["session_id"], experience)
    
    assert record.classification == ExperienceClassification.ANOMALY.value


# Test Suite 3: Knowledge Management
@pytest.mark.asyncio
async def test_knowledge_update(initialized_agent):
    """Test knowledge update process."""
    update = {
        "type": "new_knowledge",
        "domain": "planning",
        "content": "New planning heuristic discovered",
        "confidence": 0.85,
        "source": "experiment",
    }
    
    result = await initialized_agent.update_knowledge(update)
    
    assert result["validation_status"] in ["applied", "valid"]
    assert "planning" in initialized_agent.knowledge_base
    assert len(initialized_agent.knowledge_base["planning"]["entries"]) > 0


@pytest.mark.asyncio
async def test_knowledge_validation(initialized_agent):
    """Test knowledge validation."""
    # Invalid update (missing confidence bounds)
    update = {
        "type": "refinement",
        "domain": "reasoning",
        "content": "Refinement",
        "confidence": 1.5,  # Invalid: >1.0
    }
    
    result = await initialized_agent.update_knowledge(update)
    
    assert result["validation_status"] == "invalid"
    assert len(result.get("errors", [])) > 0


# Test Suite 4: Adaptation Engine
@pytest.mark.asyncio
async def test_increase_confidence_adaptation(initialized_agent):
    """Test confidence increase adaptation."""
    initial_threshold = initialized_agent.confidence_threshold
    
    result = await initialized_agent.apply_adaptation(
        "increase_confidence",
        {"delta": 0.05}
    )
    
    assert result["status"] == "applied"
    assert result["success"] is True
    assert initialized_agent.confidence_threshold > initial_threshold


@pytest.mark.asyncio
async def test_multiple_adaptations(initialized_agent):
    """Test applying multiple adaptation strategies."""
    strategies = ["increase_confidence", "increase_timeout", "optimize_memory"]
    
    for strategy in strategies:
        result = await initialized_agent.apply_adaptation(strategy, {})
        assert result["status"] == "applied"
    
    assert len(initialized_agent.adaptation_log) >= 3


# Test Suite 5: Performance Analysis
@pytest.mark.asyncio
async def test_performance_analysis(initialized_agent):
    """Test performance analysis."""
    # Add sample performance data
    for i in range(20):
        initialized_agent.performance_history.append({
            "latency_ms": 100 + (i * 10),
            "success": i % 3 != 0,  # 66% success rate
            "confidence": 0.7,
        })
    
    analysis = await initialized_agent.analyze_performance()
    
    assert "latency_metrics" in analysis
    assert "success_rate" in analysis
    assert "quality_score" in analysis
    assert "health_status" in analysis


@pytest.mark.asyncio
async def test_performance_trend_detection(initialized_agent):
    """Test performance trend detection."""
    # Add improving performance
    for i in range(10):
        initialized_agent.performance_history.append({
            "latency_ms": 100,
            "success": False,
            "confidence": 0.5,
        })
    
    for i in range(10):
        initialized_agent.performance_history.append({
            "latency_ms": 100,
            "success": True,
            "confidence": 0.8,
        })
    
    analysis = await initialized_agent.analyze_performance()
    
    assert analysis["trend"] == "improving"


# Test Suite 6: Self-Evaluation
@pytest.mark.asyncio
async def test_comprehensive_evaluation(initialized_agent):
    """Test comprehensive self-evaluation."""
    # Setup some data
    await initialized_agent.analyze_performance()
    
    evaluation = await initialized_agent.evaluate_performance()
    
    assert "learning_cycles" in evaluation
    assert "experiences_processed" in evaluation


@pytest.mark.asyncio
async def test_evaluation_by_focus_area(initialized_agent):
    """Test evaluation with specific focus areas."""
    focus_areas = ["performance", "errors", "knowledge", "adaptations", "recommendations"]
    
    for focus in focus_areas:
        evaluation = await initialized_agent.evaluate_performance(focus)
        assert "evaluation_timestamp" in evaluation


# Test Suite 7: Experience Replay
@pytest.mark.asyncio
async def test_experience_replay(initialized_agent):
    """Test experience replay functionality."""
    # Create and record experiences
    context = LearningContext(
        request_id="req-006",
        correlation_id="corr-006",
        trace_id="trace-006",
        session_id="sess-006",
    )
    session = await initialized_agent.create_learning_session(context)
    
    for i in range(5):
        experience = {
            "description": f"Experience {i}",
            "context": {},
            "metrics": {"latency_ms": 100},
            "success": i % 2 == 0,
        }
        await initialized_agent.record_experience(session["session_id"], experience)
    
    # Replay
    replayed = await initialized_agent.replay_experiences(limit=3)
    
    assert len(replayed) > 0


@pytest.mark.asyncio
async def test_replay_with_filters(initialized_agent):
    """Test experience replay with filters."""
    context = LearningContext(
        request_id="req-007",
        correlation_id="corr-007",
        trace_id="trace-007",
        session_id="sess-007",
    )
    session = await initialized_agent.create_learning_session(context)
    
    # Record failures
    for i in range(3):
        experience = {
            "description": "Failed experience",
            "error": RuntimeError("Test error"),
            "context": {},
        }
        await initialized_agent.record_experience(session["session_id"], experience)
    
    # Replay failures only
    replayed = await initialized_agent.replay_experiences(
        filter_criteria={"classification": "failure"},
        limit=10
    )
    
    assert all(r["classification"] == "failure" for r in replayed)


# Test Suite 8: Error Analysis
@pytest.mark.asyncio
async def test_error_pattern_detection(initialized_agent):
    """Test error pattern detection."""
    context = LearningContext(
        request_id="req-008",
        correlation_id="corr-008",
        trace_id="trace-008",
        session_id="sess-008",
    )
    session = await initialized_agent.create_learning_session(context)
    
    # Record same error multiple times
    error = RuntimeError("Database connection failed")
    for i in range(5):
        experience = {
            "description": f"Database error {i}",
            "error": error,
            "error_hash": "db_connection_error",
            "context": {},
        }
        await initialized_agent.record_experience(session["session_id"], experience)
    
    # Check pattern detection
    assert len(initialized_agent.error_patterns) > 0


# Test Suite 9: Learning Analytics
@pytest.mark.asyncio
async def test_learning_analytics(initialized_agent):
    """Test learning analytics aggregation."""
    context = LearningContext(
        request_id="req-009",
        correlation_id="corr-009",
        trace_id="trace-009",
        session_id="sess-009",
    )
    
    session = await initialized_agent.create_learning_session(context)
    
    task = {
        "action": "get_learning_analytics",
        "input_data": {},
    }
    
    result = await initialized_agent.execute_task(task)
    
    assert "total_sessions" in result
    assert "total_experiences" in result
    assert "learning_cycles" in result


# Test Suite 10: Backward Compatibility
@pytest.mark.asyncio
async def test_legacy_learn_from_interaction(initialized_agent):
    """Test backward compatibility with legacy learning."""
    result = await initialized_agent.learn_from_interaction({
        "user_message": "Tell me about planning",
        "agent_used": "planning_agent",
        "user_id": "test_user",
    })
    
    assert "learned" in result
    assert "topic" in result


# Test Suite 11: Concurrent Operations
@pytest.mark.asyncio
async def test_concurrent_session_creation(initialized_agent):
    """Test concurrent session creation."""
    async def create_session(i):
        context = LearningContext(
            request_id=f"req-{i}",
            correlation_id=f"corr-{i}",
            trace_id=f"trace-{i}",
            session_id=f"sess-{i}",
        )
        return await initialized_agent.create_learning_session(context)
    
    sessions = await asyncio.gather(*[create_session(i) for i in range(10)])
    
    assert len(sessions) == 10
    assert len(initialized_agent.learning_sessions) == 10


# Test Suite 12: Data Persistence
@pytest.mark.asyncio
async def test_state_persistence(initialized_agent):
    """Test learning agent state persistence."""
    await initialized_agent._update_state()
    
    state = initialized_agent.state
    
    assert "knowledge_entries" in state
    assert "experience_count" in state
    assert "active_sessions" in state
    assert "learning_cycles" in state


# Main test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
