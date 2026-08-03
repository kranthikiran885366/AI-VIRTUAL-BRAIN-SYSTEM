"""
Production Emotion State Model for Phase 8

Implements a stateful emotion model with:
- State machine (pending → active → decaying → resolved)
- Context accumulation and correlation tracking
- Temporal metadata and lifecycle management
- Serialization for persistence
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Set
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmotionState(Enum):
    """Emotion lifecycle states."""
    PENDING = "pending"           # Just created, not yet activated
    ACTIVE = "active"             # Currently affecting the agent
    DECAYING = "decaying"         # Intensity is naturally diminishing
    RESOLVED = "resolved"         # Resolved with outcome data
    SUPPRESSED = "suppressed"     # Actively suppressed by intervention


class EmotionType(Enum):
    """Canonical emotion types."""
    HAPPINESS = "happiness"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    CONFIDENCE = "confidence"
    UNCERTAINTY = "uncertainty"
    FRUSTRATION = "frustration"
    CONTENTMENT = "contentment"
    ANXIETY = "anxiety"


@dataclass
class EmotionalContext:
    """Context accumulation for an emotion."""
    triggering_events: List[str] = field(default_factory=list)
    preceding_emotions: List[str] = field(default_factory=list)  # emotion IDs
    external_factors: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_event(self, event: str) -> None:
        """Add a triggering event."""
        if event and event not in self.triggering_events:
            self.triggering_events.append(event)
    
    def add_preceding_emotion(self, emotion_id: str) -> None:
        """Link to a preceding emotion."""
        if emotion_id and emotion_id not in self.preceding_emotions:
            self.preceding_emotions.append(emotion_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmotionalContext":
        """Deserialize from dictionary."""
        return cls(**data)


@dataclass
class TemporalMetadata:
    """Temporal tracking for an emotion."""
    created_at: datetime
    activated_at: Optional[datetime] = None
    decay_started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, str]:
        """Serialize to dictionary (ISO format strings)."""
        return {
            "created_at": self.created_at.isoformat(),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "decay_started_at": self.decay_started_at.isoformat() if self.decay_started_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "TemporalMetadata":
        """Deserialize from dictionary."""
        return cls(
            created_at=datetime.fromisoformat(data["created_at"]),
            activated_at=datetime.fromisoformat(data["activated_at"]) if data.get("activated_at") else None,
            decay_started_at=datetime.fromisoformat(data["decay_started_at"]) if data.get("decay_started_at") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            last_updated_at=datetime.fromisoformat(data["last_updated_at"]) if data.get("last_updated_at") else None,
        )


@dataclass
class EmotionRecord:
    """A complete emotion record with state, context, and lifecycle."""
    id: str
    agent_id: str
    emotion_type: EmotionType
    intensity: float  # 0.0 to 1.0
    state: EmotionState
    context: EmotionalContext
    temporal: TemporalMetadata
    correlation_id: str  # For tracing emotion chains
    parent_emotion_id: Optional[str] = None  # For emotion causation chains
    child_emotion_ids: List[str] = field(default_factory=list)
    resolution_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "emotion_type": self.emotion_type.value,
            "intensity": self.intensity,
            "state": self.state.value,
            "context": self.context.to_dict(),
            "temporal": self.temporal.to_dict(),
            "correlation_id": self.correlation_id,
            "parent_emotion_id": self.parent_emotion_id,
            "child_emotion_ids": self.child_emotion_ids,
            "resolution_data": self.resolution_data or {},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmotionRecord":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            agent_id=data["agent_id"],
            emotion_type=EmotionType(data["emotion_type"]),
            intensity=data["intensity"],
            state=EmotionState(data["state"]),
            context=EmotionalContext.from_dict(data["context"]),
            temporal=TemporalMetadata.from_dict(data["temporal"]),
            correlation_id=data["correlation_id"],
            parent_emotion_id=data.get("parent_emotion_id"),
            child_emotion_ids=data.get("child_emotion_ids", []),
            resolution_data=data.get("resolution_data"),
        )


class StateTransitionValidator:
    """Validates emotion state transitions."""
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        EmotionState.PENDING: {EmotionState.ACTIVE, EmotionState.SUPPRESSED},
        EmotionState.ACTIVE: {EmotionState.DECAYING, EmotionState.SUPPRESSED, EmotionState.RESOLVED},
        EmotionState.DECAYING: {EmotionState.RESOLVED, EmotionState.SUPPRESSED},
        EmotionState.RESOLVED: {EmotionState.SUPPRESSED},
        EmotionState.SUPPRESSED: {EmotionState.ACTIVE, EmotionState.PENDING},
    }
    
    @classmethod
    def can_transition(cls, from_state: EmotionState, to_state: EmotionState) -> bool:
        """Check if a state transition is valid."""
        return to_state in cls.VALID_TRANSITIONS.get(from_state, set())
    
    @classmethod
    def validate(cls, from_state: EmotionState, to_state: EmotionState) -> None:
        """Validate a state transition, raise ValueError if invalid."""
        if not cls.can_transition(from_state, to_state):
            raise ValueError(
                f"Invalid emotion state transition: {from_state.value} → {to_state.value}"
            )


class ProductionEmotionModel:
    """
    Production-grade emotion state machine with full lifecycle management.
    
    Implements:
    - State machine with validation
    - Context accumulation
    - Correlation tracking
    - Temporal metadata
    - Full serialization
    """
    
    def __init__(self):
        """Initialize the emotion model."""
        self._emotions: Dict[str, EmotionRecord] = {}
        self._emotion_index: Dict[str, List[str]] = {}  # agent_id -> [emotion_ids]
        self._correlation_chains: Dict[str, List[str]] = {}  # correlation_id -> [emotion_ids]
        self._lock = asyncio.Lock()
        self._validators = StateTransitionValidator()
    
    async def create_emotion(
        self,
        agent_id: str,
        emotion_type: EmotionType,
        intensity: float,
        context: Optional[EmotionalContext] = None,
        correlation_id: Optional[str] = None,
        parent_emotion_id: Optional[str] = None,
    ) -> EmotionRecord:
        """
        Create a new emotion record in PENDING state.
        
        Args:
            agent_id: ID of the agent experiencing the emotion
            emotion_type: Type of emotion
            intensity: Initial intensity (0.0-1.0)
            context: Optional emotional context
            correlation_id: Optional ID for tracking emotion chains
            parent_emotion_id: Optional parent emotion ID for causation chains
        
        Returns:
            Created EmotionRecord
        
        Raises:
            ValueError: If intensity is out of range
        """
        if not 0.0 <= intensity <= 1.0:
            raise ValueError(f"Intensity must be between 0.0 and 1.0, got {intensity}")
        
        async with self._lock:
            emotion_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            emotion = EmotionRecord(
                id=emotion_id,
                agent_id=agent_id,
                emotion_type=emotion_type,
                intensity=intensity,
                state=EmotionState.PENDING,
                context=context or EmotionalContext(),
                temporal=TemporalMetadata(created_at=now),
                correlation_id=correlation_id or str(uuid.uuid4()),
                parent_emotion_id=parent_emotion_id,
            )
            
            # Store emotion
            self._emotions[emotion_id] = emotion
            
            # Index by agent
            if agent_id not in self._emotion_index:
                self._emotion_index[agent_id] = []
            self._emotion_index[agent_id].append(emotion_id)
            
            # Index by correlation
            if emotion.correlation_id not in self._correlation_chains:
                self._correlation_chains[emotion.correlation_id] = []
            self._correlation_chains[emotion.correlation_id].append(emotion_id)
            
            # Link parent-child
            if parent_emotion_id and parent_emotion_id in self._emotions:
                self._emotions[parent_emotion_id].child_emotion_ids.append(emotion_id)
            
            logger.info(
                f"Created emotion {emotion_id}: {emotion_type.value} "
                f"(intensity={intensity}) for agent {agent_id}"
            )
            
            return emotion
    
    async def activate_emotion(self, emotion_id: str) -> EmotionRecord:
        """
        Transition emotion from PENDING to ACTIVE.
        
        Args:
            emotion_id: ID of emotion to activate
        
        Returns:
            Updated EmotionRecord
        
        Raises:
            ValueError: If emotion doesn't exist or invalid transition
        """
        async with self._lock:
            if emotion_id not in self._emotions:
                raise ValueError(f"Emotion {emotion_id} not found")
            
            emotion = self._emotions[emotion_id]
            self._validators.validate(emotion.state, EmotionState.ACTIVE)
            
            emotion.state = EmotionState.ACTIVE
            emotion.temporal.activated_at = datetime.utcnow()
            emotion.temporal.last_updated_at = emotion.temporal.activated_at
            
            logger.info(f"Activated emotion {emotion_id}")
            
            return emotion
    
    async def decay_emotion(
        self,
        emotion_id: str,
        decay_factor: float,
        reason: Optional[str] = None,
    ) -> EmotionRecord:
        """
        Begin decay of emotion, optionally reducing intensity.
        
        Args:
            emotion_id: ID of emotion to decay
            decay_factor: Amount to reduce intensity (0.0-1.0)
            reason: Optional reason for decay
        
        Returns:
            Updated EmotionRecord
        
        Raises:
            ValueError: If emotion doesn't exist or invalid transition
        """
        async with self._lock:
            if emotion_id not in self._emotions:
                raise ValueError(f"Emotion {emotion_id} not found")
            
            emotion = self._emotions[emotion_id]
            
            # If not already decaying, transition to DECAYING
            if emotion.state == EmotionState.ACTIVE:
                self._validators.validate(emotion.state, EmotionState.DECAYING)
                emotion.state = EmotionState.DECAYING
                emotion.temporal.decay_started_at = datetime.utcnow()
            
            # Reduce intensity
            emotion.intensity = max(0.0, emotion.intensity - decay_factor)
            emotion.temporal.last_updated_at = datetime.utcnow()
            
            if reason:
                if "decay_reasons" not in emotion.context.metadata:
                    emotion.context.metadata["decay_reasons"] = []
                emotion.context.metadata["decay_reasons"].append(reason)
            
            logger.info(f"Decayed emotion {emotion_id} by {decay_factor} (new intensity={emotion.intensity})")
            
            return emotion
    
    async def resolve_emotion(
        self,
        emotion_id: str,
        resolution_data: Optional[Dict[str, Any]] = None,
    ) -> EmotionRecord:
        """
        Resolve an emotion with optional outcome data.
        
        Args:
            emotion_id: ID of emotion to resolve
            resolution_data: Optional outcome data
        
        Returns:
            Updated EmotionRecord
        
        Raises:
            ValueError: If emotion doesn't exist or invalid transition
        """
        async with self._lock:
            if emotion_id not in self._emotions:
                raise ValueError(f"Emotion {emotion_id} not found")
            
            emotion = self._emotions[emotion_id]
            self._validators.validate(emotion.state, EmotionState.RESOLVED)
            
            emotion.state = EmotionState.RESOLVED
            emotion.intensity = 0.0
            emotion.resolution_data = resolution_data or {}
            emotion.temporal.resolved_at = datetime.utcnow()
            emotion.temporal.last_updated_at = emotion.temporal.resolved_at
            
            logger.info(f"Resolved emotion {emotion_id}")
            
            return emotion
    
    async def suppress_emotion(self, emotion_id: str) -> EmotionRecord:
        """
        Suppress an emotion (can be unsuppressed later).
        
        Args:
            emotion_id: ID of emotion to suppress
        
        Returns:
            Updated EmotionRecord
        
        Raises:
            ValueError: If emotion doesn't exist or invalid transition
        """
        async with self._lock:
            if emotion_id not in self._emotions:
                raise ValueError(f"Emotion {emotion_id} not found")
            
            emotion = self._emotions[emotion_id]
            self._validators.validate(emotion.state, EmotionState.SUPPRESSED)
            
            emotion.state = EmotionState.SUPPRESSED
            emotion.temporal.last_updated_at = datetime.utcnow()
            
            logger.info(f"Suppressed emotion {emotion_id}")
            
            return emotion
    
    async def get_emotion(self, emotion_id: str) -> Optional[EmotionRecord]:
        """Get an emotion by ID."""
        async with self._lock:
            return self._emotions.get(emotion_id)
    
    async def get_agent_emotions(
        self,
        agent_id: str,
        state: Optional[EmotionState] = None,
    ) -> List[EmotionRecord]:
        """
        Get all emotions for an agent, optionally filtered by state.
        
        Args:
            agent_id: ID of the agent
            state: Optional state filter
        
        Returns:
            List of EmotionRecords
        """
        async with self._lock:
            emotion_ids = self._emotion_index.get(agent_id, [])
            emotions = [self._emotions[eid] for eid in emotion_ids if eid in self._emotions]
            
            if state:
                emotions = [e for e in emotions if e.state == state]
            
            return emotions
    
    async def get_emotional_context(self, agent_id: str) -> Dict[str, Any]:
        """
        Get complete emotional context for an agent.
        
        Returns:
            Dictionary with:
            - active_emotions: List of active emotions
            - decaying_emotions: List of decaying emotions
            - resolved_emotions: List of recently resolved emotions
            - current_intensity: Dict of emotion type → average intensity
        """
        async with self._lock:
            emotions = await self.get_agent_emotions(agent_id)
            
            active = [e for e in emotions if e.state == EmotionState.ACTIVE]
            decaying = [e for e in emotions if e.state == EmotionState.DECAYING]
            resolved = [e for e in emotions if e.state == EmotionState.RESOLVED]
            
            # Calculate current intensities by type
            intensity_by_type = {}
            for emotion in active + decaying:
                emotion_type = emotion.emotion_type.value
                if emotion_type not in intensity_by_type:
                    intensity_by_type[emotion_type] = []
                intensity_by_type[emotion_type].append(emotion.intensity)
            
            # Average intensities
            current_intensity = {
                emotion_type: sum(values) / len(values)
                for emotion_type, values in intensity_by_type.items()
            }
            
            return {
                "active_emotions": [e.to_dict() for e in active],
                "decaying_emotions": [e.to_dict() for e in decaying],
                "resolved_emotions": [e.to_dict() for e in resolved[-10:]],  # Last 10
                "current_intensity": current_intensity,
            }
    
    async def get_correlation_chain(self, correlation_id: str) -> List[EmotionRecord]:
        """Get all emotions in a correlation chain."""
        async with self._lock:
            emotion_ids = self._correlation_chains.get(correlation_id, [])
            return [self._emotions[eid] for eid in emotion_ids if eid in self._emotions]
    
    async def to_dict(self) -> Dict[str, Any]:
        """Serialize entire model to dictionary."""
        async with self._lock:
            return {
                "emotions": {eid: emotion.to_dict() for eid, emotion in self._emotions.items()},
                "emotion_index": self._emotion_index.copy(),
                "correlation_chains": self._correlation_chains.copy(),
            }
    
    async def from_dict(self, data: Dict[str, Any]) -> None:
        """Deserialize model from dictionary."""
        async with self._lock:
            self._emotions = {
                eid: EmotionRecord.from_dict(emotion_data)
                for eid, emotion_data in data.get("emotions", {}).items()
            }
            self._emotion_index = data.get("emotion_index", {})
            self._correlation_chains = data.get("correlation_chains", {})
    
    async def clear(self) -> None:
        """Clear all emotions (for testing)."""
        async with self._lock:
            self._emotions.clear()
            self._emotion_index.clear()
            self._correlation_chains.clear()
