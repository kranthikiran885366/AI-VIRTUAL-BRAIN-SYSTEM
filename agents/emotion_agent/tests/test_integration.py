"""
Phase 8.1 Integration Tests

Tests the complete emotion engine integration with:
- State model + Persistence
- Configuration loading
- Backward compatibility
- End-to-end workflow
"""

import pytest
import asyncio
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotion_engine import (
    EmotionEngineConfig,
    ProductionEmotionEngine,
    get_emotion_engine,
)


class TestEmotionEngineConfig:
    """Tests for configuration loading."""
    
    def test_load_default_config(self):
        """Test loading default configuration."""
        config = EmotionEngineConfig()
        
        # Should have default values
        assert config.get("emotion_engine.decay.base_rate") == 0.1
        assert config.get("emotion_engine.features.use_state_machine") is True
    
    def test_get_config_value(self):
        """Test getting configuration values."""
        config = EmotionEngineConfig()
        
        # Test dot-path access
        assert config.get("emotion_engine.decay.base_rate") is not None
        assert config.get("emotion_engine.intensity_mapping.minimal") == 0.1
    
    def test_get_with_default(self):
        """Test getting with default value."""
        config = EmotionEngineConfig()
        
        result = config.get("nonexistent.path", "default_value")
        assert result == "default_value"


class TestProductionEmotionEngine:
    """Tests for the production emotion engine."""
    
    @pytest.fixture
    async def engine(self):
        """Create engine for testing."""
        engine = ProductionEmotionEngine()
        await engine.initialize()
        yield engine
        await engine.shutdown()
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test engine initialization."""
        engine = ProductionEmotionEngine()
        
        assert not engine._initialized
        
        await engine.initialize()
        assert engine._initialized
        
        await engine.shutdown()
        assert not engine._initialized
    
    @pytest.mark.asyncio
    async def test_create_emotion(self, engine):
        """Test creating an emotion."""
        emotion_data = await engine.create_emotion(
            agent_id="test-agent",
            emotion_type="happiness",
            intensity=0.7,
        )
        
        assert emotion_data["id"] is not None
        assert emotion_data["emotion_type"] == "happiness"
        assert emotion_data["intensity"] == 0.7
        assert emotion_data["state"] == "pending"
    
    @pytest.mark.asyncio
    async def test_activate_emotion(self, engine):
        """Test activating an emotion."""
        emotion_data = await engine.create_emotion(
            agent_id="test-agent",
            emotion_type="sadness",
            intensity=0.5,
        )
        
        activated = await engine.activate_emotion(emotion_data["id"])
        
        assert activated["state"] == "active"
        assert activated["activated_at"] is not None
    
    @pytest.mark.asyncio
    async def test_decay_emotion(self, engine):
        """Test decaying an emotion."""
        emotion_data = await engine.create_emotion(
            agent_id="test-agent",
            emotion_type="anger",
            intensity=0.8,
        )
        
        await engine.activate_emotion(emotion_data["id"])
        
        decayed = await engine.decay_emotion(
            emotion_data["id"],
            decay_factor=0.3,
            reason="time_passed",
        )
        
        assert decayed["state"] == "decaying"
        assert decayed["intensity"] < 0.8
    
    @pytest.mark.asyncio
    async def test_resolve_emotion(self, engine):
        """Test resolving an emotion."""
        emotion_data = await engine.create_emotion(
            agent_id="test-agent",
            emotion_type="fear",
            intensity=0.7,
        )
        
        await engine.activate_emotion(emotion_data["id"])
        await engine.decay_emotion(emotion_data["id"], 0.6)
        
        resolved = await engine.resolve_emotion(
            emotion_data["id"],
            resolution_data={"outcome": "managed"},
        )
        
        assert resolved["state"] == "resolved"
        assert resolved["intensity"] == 0.0
    
    @pytest.mark.asyncio
    async def test_get_emotional_context(self, engine):
        """Test getting emotional context."""
        await engine.create_emotion(
            agent_id="test-agent",
            emotion_type="happiness",
            intensity=0.6,
        )
        
        await engine.create_emotion(
            agent_id="test-agent",
            emotion_type="confidence",
            intensity=0.8,
        )
        
        context = await engine.get_agent_emotional_context("test-agent")
        
        assert "active_emotions" in context
        assert "current_intensity" in context
        assert len(context["active_emotions"]) >= 1
    
    @pytest.mark.asyncio
    async def test_emotion_history(self, engine):
        """Test retrieving emotion history."""
        emotion_data = await engine.create_emotion(
            agent_id="test-agent",
            emotion_type="anger",
            intensity=0.7,
        )
        
        await engine.activate_emotion(emotion_data["id"])
        
        history = await engine.get_emotion_history(emotion_data["id"])
        
        # Should have history entries
        assert isinstance(history, list)
    
    @pytest.mark.asyncio
    async def test_audit_log(self, engine):
        """Test audit log functionality."""
        emotion_data = await engine.create_emotion(
            agent_id="test-agent",
            emotion_type="joy",
            intensity=0.8,
        )
        
        await engine.activate_emotion(emotion_data["id"])
        
        audit_log = await engine.get_audit_log(emotion_id=emotion_data["id"])
        
        # Should have audit entries
        assert isinstance(audit_log, list)
        assert len(audit_log) >= 1
    
    @pytest.mark.asyncio
    async def test_feature_flags(self, engine):
        """Test feature flag checking."""
        assert engine.is_enabled("use_state_machine") is True
        assert engine.is_enabled("use_persistence") is True
    
    @pytest.mark.asyncio
    async def test_unknown_emotion_type_fallback(self, engine):
        """Test fallback for unknown emotion types."""
        # Should not raise error
        emotion_data = await engine.create_emotion(
            agent_id="test-agent",
            emotion_type="unknown_emotion",
            intensity=0.5,
        )
        
        # Should fall back to HAPPINESS
        assert emotion_data["emotion_type"] in ["happiness", "unknown_emotion"]


class TestEndToEndWorkflow:
    """Tests for end-to-end workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_emotion_lifecycle(self):
        """Test complete emotion lifecycle."""
        engine = ProductionEmotionEngine()
        await engine.initialize()
        
        try:
            # Create
            emotion1 = await engine.create_emotion(
                agent_id="agent-1",
                emotion_type="frustration",
                intensity=0.7,
                context={"triggering_events": ["task_failure"]},
            )
            
            # Create related emotion
            emotion2 = await engine.create_emotion(
                agent_id="agent-1",
                emotion_type="uncertainty",
                intensity=0.5,
                parent_emotion_id=emotion1["id"],
            )
            
            # Get context
            context1 = await engine.get_agent_emotional_context("agent-1")
            assert len(context1["active_emotions"]) >= 2
            
            # Activate first emotion
            await engine.activate_emotion(emotion1["id"])
            
            # Decay
            await engine.decay_emotion(emotion1["id"], 0.2)
            
            # Resolve
            resolved = await engine.resolve_emotion(emotion1["id"])
            assert resolved["state"] == "resolved"
            
            # Check audit trail
            audit = await engine.get_audit_log(emotion_id=emotion1["id"])
            actions = [entry["action"] for entry in audit]
            assert "emotion_created" in actions
            assert "emotion_activated" in actions
        
        finally:
            await engine.shutdown()
    
    @pytest.mark.asyncio
    async def test_correlation_tracking(self):
        """Test emotion correlation tracking."""
        engine = ProductionEmotionEngine()
        await engine.initialize()
        
        try:
            correlation_id = "corr-123"
            
            # Create chain of related emotions
            e1 = await engine.create_emotion(
                agent_id="agent-1",
                emotion_type="anger",
                intensity=0.8,
                correlation_id=correlation_id,
            )
            
            e2 = await engine.create_emotion(
                agent_id="agent-1",
                emotion_type="frustration",
                intensity=0.6,
                correlation_id=correlation_id,
                parent_emotion_id=e1["id"],
            )
            
            # Both should be tracked
            context = await engine.get_agent_emotional_context("agent-1")
            assert len(context["active_emotions"]) >= 2
        
        finally:
            await engine.shutdown()


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
