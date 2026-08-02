"""Memory type definitions for the memory agent."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum


class MemoryType(str, Enum):
    """Types of memory supported by the system."""
    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EMOTIONAL = "emotional"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"


class RelationshipType(str, Enum):
    """Relationship types between memory items."""
    CAUSE_EFFECT = "cause_effect"
    DERIVED_FROM = "derived_from"
    TASK_OUTCOME = "task_outcome"
    PARENT_CONCEPT = "parent_concept"
    RELATED_EXPERIENCE = "related_experience"
    ASSOCIATED = "associated"


class EmotionType(str, Enum):
    """Types of emotions that can be associated with memories."""
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    NEUTRAL = "neutral"


class MemorySource(str, Enum):
    """Sources of memory data."""
    EYES = "eyes"
    EARS = "ears"
    LANGUAGE = "language"
    EMOTION = "emotion"
    DECISION = "decision"
    PLANNER = "planner"
    ATTENTION = "attention"
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


@dataclass
class MemoryMetadata:
    """Metadata for a memory item."""
    source: MemorySource = MemorySource.SYSTEM
    timestamp: datetime = field(default_factory=datetime.utcnow)
    emotion: Optional[EmotionType] = None
    importance: float = 0.5
    confidence: float = 1.0
    location: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)
    category: Optional[str] = None
    priority: int = 5  # 1 (highest) – 10 (lowest)
    source_attribution: Optional[str] = None


@dataclass
class RetentionPolicy:
    """Per-memory-type retention configuration."""
    memory_type: MemoryType = MemoryType.SHORT_TERM
    ttl_seconds: Optional[float] = None          # None = no expiry
    max_capacity: int = 10_000
    importance_floor: float = 0.0                # archive below this
    consolidation_threshold: float = 0.65        # promote above this
    archival_after_days: Optional[int] = None    # archive after N days


@dataclass
class ConsolidationRecord:
    """Audit trail entry for a memory promotion/merge/archive event."""
    id: str
    memory_id: str
    from_type: str
    to_type: str
    reason: str                                  # promoted | merged | archived
    importance_at_consolidation: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryItem:
    """Base class for all memory items."""
    id: str
    type: MemoryType
    content: Any
    metadata: MemoryMetadata
    user_id: str = "default"
    agent_id: Optional[str] = None
    conversation_id: Optional[str] = None
    embedding: Optional[List[float]] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_archived: bool = False
    is_deleted: bool = False
    version: int = 1
    ttl: Optional[float] = None                  # seconds; None = no expiry
    retrieval_history: List[str] = field(default_factory=list)  # ISO timestamps
    consolidation_count: int = 0


@dataclass
class WorkingMemory(MemoryItem):
    """Working memory item for short-lived reasoning context."""
    def __post_init__(self):
        self.type = MemoryType.WORKING
        if self.ttl is None:
            self.ttl = 60.0  # 1 minute default TTL


@dataclass
class ShortTermMemory(MemoryItem):
    """Short-term memory item."""
    def __post_init__(self):
        self.type = MemoryType.SHORT_TERM
        if self.ttl is None:
            self.ttl = 300.0  # 5 minutes default TTL


@dataclass
class LongTermMemory(MemoryItem):
    """Long-term memory item."""
    def __post_init__(self):
        self.type = MemoryType.LONG_TERM
        self.ttl = None  # Long-term memories don't expire automatically


@dataclass
class EmotionalMemory(MemoryItem):
    """Emotional memory item."""
    def __post_init__(self):
        self.type = MemoryType.EMOTIONAL
        if self.metadata and self.metadata.importance == 0.0:
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


@dataclass
class MemoryRelationship:
    """Edge representing a relationship between two memory items."""
    id: str
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MemorySearchFilter:
    """Filter criteria for memory retrieval queries."""
    query: str = ""
    user_id: str = "default"
    agent_id: Optional[str] = None
    conversation_id: Optional[str] = None
    memory_type: Optional[Union[MemoryType, str]] = None
    memory_types: Optional[List[Union[MemoryType, str]]] = None
    min_importance: float = 0.0
    min_confidence: float = 0.0
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    priority_min: Optional[int] = None
    source_attribution: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    include_archived: bool = False
    include_deleted: bool = False
    limit: int = 10
    offset: int = 0
    page: int = 0                                # alternative to offset
    traverse_relationships: bool = False
    traversal_depth: int = 1


@dataclass
class RetrievalResult:
    """Scored memory retrieval result with explanation."""
    memory: MemoryItem
    relevance_score: float
    keyword_score: float = 0.0
    semantic_score: float = 0.0
    importance_score: float = 0.0
    recency_score: float = 0.0
    frequency_score: float = 0.0
    context_score: float = 0.0
    tier_score: float = 0.0
    explanation: str = ""
    linked_memories: List[MemoryItem] = field(default_factory=list)