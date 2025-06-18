"""Memory type definitions for the memory agent."""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

class MemoryType(Enum):
    """Types of memory supported by the system."""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EMOTIONAL = "emotional"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"

class EmotionType(Enum):
    """Types of emotions that can be associated with memories."""
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    NEUTRAL = "neutral"

class MemorySource(Enum):
    """Sources of memory data."""
    EYES = "eyes"
    EARS = "ears"
    LANGUAGE = "language"
    EMOTION = "emotion"
    DECISION = "decision"
    PLANNER = "planner"
    ATTENTION = "attention"

@dataclass
class MemoryMetadata:
    """Metadata for a memory item."""
    source: MemorySource
    timestamp: datetime
    emotion: Optional[EmotionType] = None
    importance: float = 0.0
    confidence: float = 0.0
    location: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    tags: List[str] = None

@dataclass
class MemoryItem:
    """Base class for all memory items."""
    id: str
    type: MemoryType
    content: Dict[str, Any]
    metadata: MemoryMetadata
    embedding: Optional[List[float]] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    ttl: Optional[float] = None  # Time to live in seconds

@dataclass
class ShortTermMemory(MemoryItem):
    """Short-term memory item."""
    def __post_init__(self):
        self.type = MemoryType.SHORT_TERM
        if self.ttl is None:
            self.ttl = 300  # 5 minutes default TTL

@dataclass
class LongTermMemory(MemoryItem):
    """Long-term memory item."""
    def __post_init__(self):
        self.type = MemoryType.LONG_TERM
        self.ttl = None  # Long-term memories don't expire

@dataclass
class EmotionalMemory(MemoryItem):
    """Emotional memory item."""
    def __post_init__(self):
        self.type = MemoryType.EMOTIONAL
        if self.metadata.importance == 0.0:
            self.metadata.importance = 0.8  # Emotional memories are important by default

@dataclass
class SemanticMemory(MemoryItem):
    """Semantic memory item."""
    def __post_init__(self):
        self.type = MemoryType.SEMANTIC

@dataclass
class EpisodicMemory(MemoryItem):
    """Episodic memory item."""
    def __post_init__(self):
        self.type = MemoryType.EPISODIC

@dataclass
class ProceduralMemory(MemoryItem):
    """Procedural memory item."""
    def __post_init__(self):
        self.type = MemoryType.PROCEDURAL 