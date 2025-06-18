"""Long-term memory module for handling persistent memory storage."""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from .memory_types import (
    LongTermMemory,
    MemoryMetadata,
    MemorySource,
    EmotionType,
    MemoryType
)
from .memory_storage import MemoryStorage

class LongTermMemoryManager:
    def __init__(self, config: Dict[str, Any], storage: MemoryStorage):
        """Initialize long-term memory manager."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.storage = storage
        
        # Initialize memory consolidation settings
        self.consolidation_threshold = config.get("consolidation_threshold", 0.7)
        self.consolidation_interval = config.get("consolidation_interval", 3600)  # 1 hour
        self.last_consolidation = datetime.now()
    
    def store(self, data: Dict[str, Any], source: MemorySource,
              emotion: Optional[EmotionType] = None) -> Optional[str]:
        """Store new data in long-term memory."""
        try:
            # Create memory metadata
            metadata = MemoryMetadata(
                source=source,
                timestamp=datetime.now(),
                emotion=emotion,
                importance=self._calculate_importance(data, emotion),
                confidence=data.get("confidence", 0.0),
                context=data.get("context", {}),
                tags=data.get("tags", [])
            )
            
            # Create long-term memory item
            memory = LongTermMemory(
                id=str(uuid.uuid4()),
                content=data,
                metadata=metadata
            )
            
            # Store in persistent storage
            self.storage.store(memory)
            
            return memory.id
        
        except Exception as e:
            self.logger.error(f"Error storing long-term memory: {str(e)}")
            return None
    
    def retrieve(self, memory_id: str) -> Optional[LongTermMemory]:
        """Retrieve a memory by ID."""
        try:
            memory = self.storage.retrieve(memory_id)
            if memory and isinstance(memory, LongTermMemory):
                return memory
            return None
        
        except Exception as e:
            self.logger.error(f"Error retrieving long-term memory: {str(e)}")
            return None
    
    def search(self, query: str, limit: int = 10) -> List[LongTermMemory]:
        """Search long-term memories by semantic similarity."""
        try:
            # Search in storage
            memories = self.storage.search(query, limit)
            
            # Filter for long-term memories
            return [m for m in memories if isinstance(m, LongTermMemory)]
        
        except Exception as e:
            self.logger.error(f"Error searching long-term memories: {str(e)}")
            return []
    
    def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a long-term memory."""
        try:
            return self.storage.update(memory_id, updates)
        
        except Exception as e:
            self.logger.error(f"Error updating long-term memory: {str(e)}")
            return False
    
    def delete(self, memory_id: str) -> bool:
        """Delete a long-term memory."""
        try:
            return self.storage.delete(memory_id)
        
        except Exception as e:
            self.logger.error(f"Error deleting long-term memory: {str(e)}")
            return False
    
    def consolidate_memories(self, short_term_memories: List[Any]) -> List[str]:
        """Consolidate important short-term memories into long-term storage."""
        try:
            consolidated_ids = []
            now = datetime.now()
            
            # Check if it's time for consolidation
            if (now - self.last_consolidation).total_seconds() < self.consolidation_interval:
                return consolidated_ids
            
            # Process each short-term memory
            for memory in short_term_memories:
                if self._should_consolidate(memory):
                    # Create long-term memory
                    long_term_memory = LongTermMemory(
                        id=str(uuid.uuid4()),
                        content=memory.content,
                        metadata=memory.metadata
                    )
                    
                    # Store in long-term storage
                    if self.storage.store(long_term_memory):
                        consolidated_ids.append(long_term_memory.id)
            
            # Update last consolidation time
            self.last_consolidation = now
            
            return consolidated_ids
        
        except Exception as e:
            self.logger.error(f"Error consolidating memories: {str(e)}")
            return []
    
    def _should_consolidate(self, memory: Any) -> bool:
        """Determine if a memory should be consolidated into long-term storage."""
        # Check memory type
        if not isinstance(memory, (LongTermMemory, MemoryType.SHORT_TERM)):
            return False
        
        # Check importance threshold
        if memory.metadata.importance < self.consolidation_threshold:
            return False
        
        # Check access count
        if memory.access_count < 3:  # Memory must be accessed multiple times
            return False
        
        # Check emotion
        if memory.metadata.emotion in [EmotionType.JOY, EmotionType.FEAR]:
            return True
        
        # Check source
        if memory.metadata.source in [MemorySource.EYES, MemorySource.EARS]:
            return True
        
        return False
    
    def _calculate_importance(self, data: Dict[str, Any],
                            emotion: Optional[EmotionType]) -> float:
        """Calculate importance score for memory."""
        importance = 0.0
        
        # Base importance from confidence
        importance += data.get("confidence", 0.0) * 0.4
        
        # Importance from emotion
        if emotion:
            if emotion in [EmotionType.FEAR, EmotionType.JOY]:
                importance += 0.5
            elif emotion in [EmotionType.ANGER, EmotionType.SURPRISE]:
                importance += 0.4
            elif emotion in [EmotionType.SADNESS, EmotionType.DISGUST]:
                importance += 0.3
        
        # Importance from source
        if data.get("source") in [MemorySource.EYES, MemorySource.EARS]:
            importance += 0.3
        
        # Importance from context
        if data.get("context", {}).get("is_important", False):
            importance += 0.4
        
        return min(importance, 1.0)
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about stored memories."""
        try:
            # Get all memories
            memories = self.storage.search("", limit=1000)
            long_term_memories = [m for m in memories if isinstance(m, LongTermMemory)]
            
            if not long_term_memories:
                return {}
            
            # Calculate statistics
            total_memories = len(long_term_memories)
            total_importance = sum(m.metadata.importance for m in long_term_memories)
            total_confidence = sum(m.metadata.confidence for m in long_term_memories)
            
            # Count memories by emotion
            emotion_counts = {}
            for memory in long_term_memories:
                if memory.metadata.emotion:
                    emotion_counts[memory.metadata.emotion.value] = \
                        emotion_counts.get(memory.metadata.emotion.value, 0) + 1
            
            # Count memories by source
            source_counts = {}
            for memory in long_term_memories:
                source_counts[memory.metadata.source.value] = \
                    source_counts.get(memory.metadata.source.value, 0) + 1
            
            return {
                "total_memories": total_memories,
                "average_importance": total_importance / total_memories,
                "average_confidence": total_confidence / total_memories,
                "emotion_distribution": emotion_counts,
                "source_distribution": source_counts
            }
        
        except Exception as e:
            self.logger.error(f"Error getting memory stats: {str(e)}")
            return {} 