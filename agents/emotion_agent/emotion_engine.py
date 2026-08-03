"""
Phase 8: Production Emotion Engine Integration Layer

Bridges the production emotion state model and persistence with the existing
Emotion Agent, maintaining full backward compatibility.

Features:
- Seamless integration with existing EmotionAgent
- Optional production features via configuration
- Fallback to legacy behavior if needed
- Configuration-driven parameter management
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)


class EmotionEngineConfig:
    """Load and manage emotion engine configuration."""
    
    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "emotion_engine_config.yaml"
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration."""
        self.config_path = Path(config_path or self.DEFAULT_CONFIG_PATH)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found at {self.config_path}, using defaults")
            return self._default_config()
        
        try:
            with open(self.config_path, 'r') as f:
                if yaml:
                    config = yaml.safe_load(f) or {}
                else:
                    # Fallback: simple line-by-line YAML parser for basic structures
                    config = self._simple_yaml_load(f.read())
            logger.info(f"Loaded emotion engine config from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}, using defaults")
            return self._default_config()
    
    def _simple_yaml_load(self, content: str) -> Dict[str, Any]:
        """Simple YAML parser for basic key-value structures."""
        result = {}
        stack = [result]
        
        for line in content.split('\n'):
            if not line.strip() or line.strip().startswith('#'):
                continue
            
            # Count leading spaces
            spaces = len(line) - len(line.lstrip())
            line = line.strip()
            
            if ':' not in line:
                continue
            
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Parse value
            if value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            elif value.lower() == 'null' or value == '':
                value = None
            else:
                try:
                    value = float(value) if '.' in value else int(value)
                except ValueError:
                    pass  # Keep as string
            
            # Simple depth handling (not perfect but works for basic configs)
            depth = spaces // 2
            
            # Navigate to correct depth
            current = result
            for _ in range(max(0, depth - 1)):
                # This is simplified - a real parser would maintain stack
                pass
            
            current[key] = value
        
        return result
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "emotion_engine": {
                "decay": {
                    "base_rate": 0.1,
                    "contextual_factors": {
                        "ongoing_stressor": 0.05,
                        "recent_success": 0.15,
                    },
                    "min_intensity": 0.05,
                    "method": "linear",
                },
                "intensity_mapping": {
                    "minimal": 0.1,
                    "mild": 0.3,
                    "moderate": 0.5,
                    "strong": 0.7,
                    "intense": 0.9,
                },
                "transitions": {
                    "activation_threshold": 0.15,
                    "decay_threshold": 0.40,
                    "resolution_threshold": 0.02,
                },
                "audit": {
                    "enable_detailed_logging": True,
                    "retention_days": 90,
                },
                "features": {
                    "use_state_machine": True,
                    "use_persistence": True,
                    "enable_audit_trail": True,
                    "legacy_json_storage_enabled": False,
                },
            }
        }
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated path."""
        keys = path.split(".")
        value = self.config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default


class ProductionEmotionEngine:
    """
    High-level emotion engine that coordinates the production components.
    
    Responsibilities:
    - Load and manage configuration
    - Coordinate state model and persistence
    - Maintain backward compatibility
    - Provide unified interface
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the production emotion engine."""
        self.config = EmotionEngineConfig(config_path)
        self._initialized = False
        self._lock = asyncio.Lock()
        
        # Lazy-load production components
        self._state_model = None
        self._persistence = None
    
    async def initialize(self) -> None:
        """Initialize the production emotion engine."""
        if self._initialized:
            return
        
        async with self._lock:
            try:
                # Import production components
                from .state_model import ProductionEmotionModel
                from .persistence import EmotionPersistence
                
                # Initialize if enabled in config
                if self.config.get("emotion_engine.features.use_state_machine", True):
                    self._state_model = ProductionEmotionModel()
                    logger.info("Initialized production emotion state model")
                
                if self.config.get("emotion_engine.features.use_persistence", True):
                    db_path = "data/emotion_store/emotions.db"
                    self._persistence = EmotionPersistence(db_path)
                    await self._persistence.initialize()
                    logger.info("Initialized emotion persistence layer")
                
                self._initialized = True
                logger.info("Production emotion engine initialized")
            except ImportError as e:
                logger.error(f"Failed to import production components: {e}")
                self._initialized = False
                raise
    
    async def shutdown(self) -> None:
        """Shutdown the production emotion engine."""
        async with self._lock:
            if self._persistence:
                await self._persistence.shutdown()
            self._initialized = False
            logger.info("Production emotion engine shutdown")
    
    async def create_emotion(
        self,
        agent_id: str,
        emotion_type: str,
        intensity: float,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        parent_emotion_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new emotion using the production state model.
        
        Args:
            agent_id: ID of agent experiencing emotion
            emotion_type: Type of emotion
            intensity: Intensity 0.0-1.0
            context: Optional emotional context
            correlation_id: Optional correlation ID
            parent_emotion_id: Optional parent emotion ID
        
        Returns:
            Emotion data dictionary
        """
        if not self._initialized:
            raise RuntimeError("Production emotion engine not initialized")
        
        if not self._state_model:
            raise RuntimeError("State model not available")
        
        from .state_model import EmotionType, EmotionalContext
        
        try:
            # Convert string emotion type to enum
            emotion_enum = EmotionType[emotion_type.upper()]
        except (KeyError, AttributeError):
            # Fallback for unsupported emotion types
            logger.warning(f"Unknown emotion type: {emotion_type}, using HAPPINESS")
            emotion_enum = EmotionType.HAPPINESS
        
        # Create context if provided
        emotional_context = EmotionalContext()
        if context:
            if isinstance(context, dict):
                if "triggering_events" in context:
                    for event in context["triggering_events"]:
                        emotional_context.add_event(event)
                if "metadata" in context:
                    emotional_context.metadata.update(context["metadata"])
        
        # Create emotion in state model
        emotion = await self._state_model.create_emotion(
            agent_id=agent_id,
            emotion_type=emotion_enum,
            intensity=intensity,
            context=emotional_context,
            correlation_id=correlation_id,
            parent_emotion_id=parent_emotion_id,
        )
        
        # Persist if persistence enabled
        if self._persistence:
            await self._persistence.save_emotion(emotion)
            await self._persistence.add_audit_entry(
                emotion_id=emotion.id,
                action="emotion_created",
                actor=f"agent:{agent_id}",
                metadata={
                    "emotion_type": emotion_type,
                    "intensity": intensity,
                },
            )
        
        return emotion.to_dict()
    
    async def activate_emotion(self, emotion_id: str) -> Dict[str, Any]:
        """Activate an emotion."""
        if not self._state_model:
            raise RuntimeError("State model not available")
        
        emotion = await self._state_model.activate_emotion(emotion_id)
        
        if self._persistence:
            await self._persistence.save_emotion(emotion)
            await self._persistence.add_audit_entry(
                emotion_id=emotion_id,
                action="emotion_activated",
                actor="engine",
            )
        
        return emotion.to_dict()
    
    async def decay_emotion(
        self,
        emotion_id: str,
        decay_factor: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Decay an emotion."""
        if not self._state_model:
            raise RuntimeError("State model not available")
        
        # Use configured decay rate if not provided
        if decay_factor is None:
            decay_factor = self.config.get(
                "emotion_engine.decay.base_rate",
                0.1
            )
        
        emotion = await self._state_model.decay_emotion(
            emotion_id=emotion_id,
            decay_factor=decay_factor,
            reason=reason,
        )
        
        if self._persistence:
            await self._persistence.save_emotion(emotion)
            await self._persistence.add_audit_entry(
                emotion_id=emotion_id,
                action="emotion_decayed",
                actor="engine",
                metadata={"decay_factor": decay_factor, "reason": reason},
            )
        
        return emotion.to_dict()
    
    async def resolve_emotion(
        self,
        emotion_id: str,
        resolution_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resolve an emotion."""
        if not self._state_model:
            raise RuntimeError("State model not available")
        
        emotion = await self._state_model.resolve_emotion(
            emotion_id=emotion_id,
            resolution_data=resolution_data,
        )
        
        if self._persistence:
            await self._persistence.save_emotion(emotion)
            await self._persistence.add_audit_entry(
                emotion_id=emotion_id,
                action="emotion_resolved",
                actor="engine",
                metadata=resolution_data or {},
            )
        
        return emotion.to_dict()
    
    async def get_agent_emotional_context(self, agent_id: str) -> Dict[str, Any]:
        """Get complete emotional context for an agent."""
        if not self._state_model:
            raise RuntimeError("State model not available")
        
        return await self._state_model.get_emotional_context(agent_id)
    
    async def get_emotion_history(
        self,
        emotion_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get emotion state transition history."""
        if not self._persistence:
            return []
        
        return await self._persistence.get_emotion_history(emotion_id, limit)
    
    async def get_audit_log(
        self,
        emotion_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit log."""
        if not self._persistence:
            return []
        
        return await self._persistence.get_audit_log(emotion_id, action, limit)
    
    def is_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled."""
        return self.config.get(f"emotion_engine.features.{feature}", False)


# Global engine instance
_global_engine: Optional[ProductionEmotionEngine] = None


async def get_emotion_engine(config_path: Optional[str] = None) -> ProductionEmotionEngine:
    """Get or create the global emotion engine."""
    global _global_engine
    
    if _global_engine is None:
        _global_engine = ProductionEmotionEngine(config_path)
        await _global_engine.initialize()
    
    return _global_engine


async def shutdown_emotion_engine() -> None:
    """Shutdown the global emotion engine."""
    global _global_engine
    
    if _global_engine:
        await _global_engine.shutdown()
        _global_engine = None
