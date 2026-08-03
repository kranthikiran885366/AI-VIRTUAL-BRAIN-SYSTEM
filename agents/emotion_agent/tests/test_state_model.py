"""
Comprehensive tests for Production Emotion State Model

Tests:
- State machine transitions
- Emotion lifecycle
- Context accumulation
- Correlation tracking
- Serialization
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List

# Import state model components
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from state_model import (
    EmotionState, EmotionType, EmotionRecord,
    EmotionalContext, TemporalMetadata,
    StateTransitionValidator, ProductionEmotionModel,
)


class TestStateTransitionValidator:
    """Tests for state transition validation."""
    
    def test_valid_transitions(self):
        """Test valid state transitions."""
        # PENDING -> ACTIVE
        assert StateTransitionValidator.can_transition(
            EmotionState.PENDING, EmotionState.ACTIVE
        )
        
        # ACTIVE -> DECAYING
        assert StateTransitionValidator.can_transition(
            EmotionState.ACTIVE, EmotionState.DECAYING
        )
        
        # DECAYING -> RESOLVED
        assert StateTransitionValidator.can_transition(
            EmotionState.DECAYING, EmotionState.RESOLVED
        )
    
    def test_invalid_transitions(self):
        """Test invalid state transitions."""
        # PENDING -> RESOLVED (invalid - must go through ACTIVE/DECAYING)
        assert not StateTransitionValidator.can_transition(
            EmotionState.PENDING, EmotionState.RESOLVED
        )
        
        # RESOLVED -> ACTIVE (invalid - end state)
        assert not StateTransitionValidator.can_transition(
            EmotionState.RESOLVED, EmotionState.ACTIVE
        )
    
    def test_suppression_transitions(self):
        """Test suppression transitions."""
        # Any state can be suppressed
        assert StateTransitionValidator.can_transition(
            EmotionState.PENDING, EmotionState.SUPPRESSED
        )
        assert StateTransitionValidator.can_transition(
            EmotionState.ACTIVE, EmotionState.SUPPRESSED
        )
        
        # Suppressed can return to ACTIVE/PENDING
        assert StateTransitionValidator.can_transition(
            EmotionState.SUPPRESSED, EmotionState.ACTIVE
        )
    
    def test_validate_raises_on_invalid(self):
        """Test that validate() raises on invalid transitions."""
        with pytest.raises(ValueError):
            StateTransitionValidator.validate(
                EmotionState.PENDING, EmotionState.RESOLVED
            )


class TestEmotionalContext:
    """Tests for emotional context."""
    
    def test_add_event(self):
        """Test adding triggering events."""
        context = EmotionalContext()
        context.add_event("user_feedback")
        assert "user_feedback" in context.triggering_events
        
        # Duplicate events not added
        context.add_event("user_feedback")
        assert len(context.triggering_events) == 1
    
    def test_add_preceding_emotion(self):
        """Test adding preceding emotions."""
        context = EmotionalContext()
        context.add_preceding_emotion("emotion-123")
        assert "emotion-123" in context.preceding_emotions
    
    def test_serialization(self):
        """Test context serialization."""
        context = EmotionalContext()
        context.add_event("test_event")
        context.metadata["custom"] = "value"
        
        data = context.to_dict()
        restored = EmotionalContext.from_dict(data)
        
        assert restored.triggering_events == context.triggering_events
        assert restored.metadata == context.metadata


class TestTemporalMetadata:
    """Tests for temporal metadata."""
    
    def test_serialization(self):
        """Test temporal metadata serialization."""
        now = datetime.utcnow()
        temporal = TemporalMetadata(
            created_at=now,
            activated_at=now + timedelta(seconds=1),
        )
        
        data = temporal.to_dict()
        restored = TemporalMetadata.from_dict(data)
        
        assert restored.created_at == temporal.created_at
        assert restored.activated_at == temporal.activated_at
    
    def test_none_values(self):
        """Test handling of None values."""
        temporal = TemporalMetadata(created_at=datetime.utcnow())
        data = temporal.to_dict()
        
        assert data["activated_at"] is None
        assert data["resolved_at"] is None
        
        restored = TemporalMetadata.from_dict(data)
        assert restored.activated_at is None


class TestEmotionRecord:
    """Tests for emotion records."""
    
    def test_creation(self):
        """Test creating an emotion record."""
        emotion = EmotionRecord(
            id="emotion-1",
            agent_id="agent-1",
            emotion_type=EmotionType.HAPPINESS,
            intensity=0.7,
            state=EmotionState.PENDING,
            context=EmotionalContext(),
            temporal=TemporalMetadata(created_at=datetime.utcnow()),
            correlation_id="corr-1",
        )
        
        assert emotion.id == "emotion-1"
        assert emotion.emotion_type == EmotionType.HAPPINESS
        assert emotion.intensity == 0.7
    
    def test_serialization(self):
        """Test emotion record serialization."""
        context = EmotionalContext()
        context.add_event("test")
        
        emotion = EmotionRecord(
            id="emotion-1",
            agent_id="agent-1",
            emotion_type=EmotionType.ANGER,
            intensity=0.5,
            state=EmotionState.ACTIVE,
            context=context,
            temporal=TemporalMetadata(created_at=datetime.utcnow()),
            correlation_id="corr-1",
        )
        
        data = emotion.to_dict()
        restored = EmotionRecord.from_dict(data)
        
        assert restored.id == emotion.id
        assert restored.emotion_type == emotion.emotion_type
        assert restored.intensity == emotion.intensity


class TestProductionEmotionModel:
    """Tests for the production emotion model."""
    
    @pytest.fixture
    async def model(self):
        """Create a fresh model for each test."""
        model = ProductionEmotionModel()
        yield model
        await model.clear()
    
    @pytest.mark.asyncio
    async def test_create_emotion(self, model):
        """Test creating an emotion."""
        emotion = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.HAPPINESS,
            intensity=0.7,
        )
        
        assert emotion.id is not None
        assert emotion.state == EmotionState.PENDING
        assert emotion.intensity == 0.7
    
    @pytest.mark.asyncio
    async def test_create_emotion_invalid_intensity(self, model):
        """Test that invalid intensity raises error."""
        with pytest.raises(ValueError):
            await model.create_emotion(
                agent_id="agent-1",
                emotion_type=EmotionType.HAPPINESS,
                intensity=1.5,  # Invalid
            )
    
    @pytest.mark.asyncio
    async def test_activate_emotion(self, model):
        """Test activating an emotion."""
        emotion = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.HAPPINESS,
            intensity=0.7,
        )
        
        activated = await model.activate_emotion(emotion.id)
        assert activated.state == EmotionState.ACTIVE
        assert activated.temporal.activated_at is not None
    
    @pytest.mark.asyncio
    async def test_decay_emotion(self, model):
        """Test decaying an emotion."""
        emotion = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.ANGER,
            intensity=0.8,
        )
        
        # Activate first
        await model.activate_emotion(emotion.id)
        
        # Decay
        decayed = await model.decay_emotion(emotion.id, decay_factor=0.3)
        
        assert decayed.state == EmotionState.DECAYING
        assert decayed.intensity == pytest.approx(0.5)
    
    @pytest.mark.asyncio
    async def test_resolve_emotion(self, model):
        """Test resolving an emotion."""
        emotion = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.FEAR,
            intensity=0.6,
        )
        
        await model.activate_emotion(emotion.id)
        await model.decay_emotion(emotion.id, decay_factor=0.5)
        
        resolved = await model.resolve_emotion(
            emotion.id,
            resolution_data={"outcome": "positive"}
        )
        
        assert resolved.state == EmotionState.RESOLVED
        assert resolved.intensity == 0.0
        assert resolved.resolution_data["outcome"] == "positive"
    
    @pytest.mark.asyncio
    async def test_suppress_emotion(self, model):
        """Test suppressing an emotion."""
        emotion = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.ANXIETY,
            intensity=0.7,
        )
        
        suppressed = await model.suppress_emotion(emotion.id)
        assert suppressed.state == EmotionState.SUPPRESSED
    
    @pytest.mark.asyncio
    async def test_get_agent_emotions(self, model):
        """Test retrieving agent emotions."""
        # Create multiple emotions
        e1 = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.HAPPINESS,
            intensity=0.7,
        )
        
        e2 = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.SADNESS,
            intensity=0.3,
        )
        
        # Get all
        emotions = await model.get_agent_emotions("agent-1")
        assert len(emotions) == 2
        
        # Get by state
        await model.activate_emotion(e1.id)
        active = await model.get_agent_emotions(
            "agent-1",
            state=EmotionState.ACTIVE
        )
        assert len(active) == 1
        assert active[0].emotion_type == EmotionType.HAPPINESS
    
    @pytest.mark.asyncio
    async def test_get_emotional_context(self, model):
        """Test getting emotional context for an agent."""
        await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.HAPPINESS,
            intensity=0.6,
        )
        
        await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.CONFIDENCE,
            intensity=0.8,
        )
        
        context = await model.get_emotional_context("agent-1")
        
        assert "active_emotions" in context
        assert "current_intensity" in context
        assert len(context["active_emotions"]) == 2
    
    @pytest.mark.asyncio
    async def test_correlation_chains(self, model):
        """Test emotion correlation chains."""
        correlation_id = "corr-123"
        
        e1 = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.HAPPINESS,
            intensity=0.5,
            correlation_id=correlation_id,
        )
        
        e2 = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.CONTENTMENT,
            intensity=0.6,
            correlation_id=correlation_id,
            parent_emotion_id=e1.id,
        )
        
        chain = await model.get_correlation_chain(correlation_id)
        assert len(chain) == 2
        assert chain[0].id == e1.id
        assert chain[1].id == e2.id
    
    @pytest.mark.asyncio
    async def test_parent_child_relationships(self, model):
        """Test parent-child emotion relationships."""
        parent = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.ANGER,
            intensity=0.7,
        )
        
        child = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.FRUSTRATION,
            intensity=0.5,
            parent_emotion_id=parent.id,
        )
        
        # Check parent has child reference
        updated_parent = await model.get_emotion(parent.id)
        assert child.id in updated_parent.child_emotion_ids
    
    @pytest.mark.asyncio
    async def test_serialization(self, model):
        """Test model serialization."""
        await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.HAPPINESS,
            intensity=0.7,
        )
        
        data = await model.to_dict()
        
        assert "emotions" in data
        assert "emotion_index" in data
        assert len(data["emotions"]) > 0
        
        # Clear and restore
        await model.clear()
        assert len(await model.get_agent_emotions("agent-1")) == 0
        
        await model.from_dict(data)
        emotions = await model.get_agent_emotions("agent-1")
        assert len(emotions) == 1
    
    @pytest.mark.asyncio
    async def test_invalid_emotion_id(self, model):
        """Test operations on non-existent emotion."""
        with pytest.raises(ValueError):
            await model.activate_emotion("nonexistent-id")
    
    @pytest.mark.asyncio
    async def test_intensity_clipping(self, model):
        """Test that intensity is clipped to [0, 1]."""
        emotion = await model.create_emotion(
            agent_id="agent-1",
            emotion_type=EmotionType.HAPPINESS,
            intensity=0.5,
        )
        
        # Decay beyond zero should clip
        await model.activate_emotion(emotion.id)
        decayed = await model.decay_emotion(emotion.id, decay_factor=0.8)
        
        assert decayed.intensity == 0.0


class TestEmotionModelConcurrency:
    """Tests for concurrent operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_creates(self):
        """Test creating emotions concurrently."""
        model = ProductionEmotionModel()
        
        async def create_emotion(i):
            return await model.create_emotion(
                agent_id=f"agent-{i % 3}",
                emotion_type=EmotionType.HAPPINESS,
                intensity=0.5,
            )
        
        tasks = [create_emotion(i) for i in range(10)]
        emotions = await asyncio.gather(*tasks)
        
        assert len(emotions) == 10
        assert len(set(e.id for e in emotions)) == 10  # All unique IDs
        
        await model.clear()


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
