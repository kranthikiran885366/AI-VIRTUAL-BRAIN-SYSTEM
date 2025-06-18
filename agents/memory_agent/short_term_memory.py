"""Short-term memory module for handling temporary memory storage."""

import time
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import deque
from .memory_types import (
    ShortTermMemory,
    MemoryMetadata,
    MemorySource,
    EmotionType
)
from .memory_storage import MemoryStorage

class ShortTermMemoryManager:
    def __init__(self, config: Dict[str, Any], storage: MemoryStorage):
        """Initialize short-term memory manager."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.storage = storage
        
        # Initialize memory buffer
        self.max_size = config.get("max_size", 1000)
        self.memory_buffer = deque(maxlen=self.max_size)
        
        # Performance metrics
        self.processing_times = []
    
    def store(self, data: Dict[str, Any], source: MemorySource,
              emotion: Optional[EmotionType] = None) -> Optional[str]:
        """Store new data in short-term memory."""
        start_time = time.time()
        
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
            
            # Create short-term memory item
            memory = ShortTermMemory(
                id=str(uuid.uuid4()),
                content=data,
                metadata=metadata
            )
            
            # Store in buffer
            self.memory_buffer.append(memory)
            
            # Store in persistent storage
            self.storage.store(memory)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            return memory.id
        
        except Exception as e:
            self.logger.error(f"Error storing short-term memory: {str(e)}")
            return None
    
    def retrieve(self, memory_id: str) -> Optional[ShortTermMemory]:
        """Retrieve a memory by ID."""
        try:
            # Check buffer first
            for memory in self.memory_buffer:
                if memory.id == memory_id:
                    return memory
            
            # Check storage
            memory = self.storage.retrieve(memory_id)
            if memory and isinstance(memory, ShortTermMemory):
                return memory
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error retrieving short-term memory: {str(e)}")
            return None
    
    def search(self, query: str, limit: int = 10) -> List[ShortTermMemory]:
        """Search short-term memories by semantic similarity."""
        try:
            # Search in storage
            memories = self.storage.search(query, limit)
            
            # Filter for short-term memories
            return [m for m in memories if isinstance(m, ShortTermMemory)]
        
        except Exception as e:
            self.logger.error(f"Error searching short-term memories: {str(e)}")
            return []
    
    def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a short-term memory."""
        try:
            # Update in storage
            success = self.storage.update(memory_id, updates)
            
            if success:
                # Update in buffer
                for memory in self.memory_buffer:
                    if memory.id == memory_id:
                        for key, value in updates.items():
                            if hasattr(memory, key):
                                setattr(memory, key, value)
                        break
            
            return success
        
        except Exception as e:
            self.logger.error(f"Error updating short-term memory: {str(e)}")
            return False
    
    def delete(self, memory_id: str) -> bool:
        """Delete a short-term memory."""
        try:
            # Delete from storage
            success = self.storage.delete(memory_id)
            
            if success:
                # Delete from buffer
                self.memory_buffer = deque(
                    [m for m in self.memory_buffer if m.id != memory_id],
                    maxlen=self.max_size
                )
            
            return success
        
        except Exception as e:
            self.logger.error(f"Error deleting short-term memory: {str(e)}")
            return False
    
    def cleanup(self):
        """Clean up expired memories."""
        try:
            # Clean up storage
            self.storage.cleanup()
            
            # Clean up buffer
            now = datetime.now()
            self.memory_buffer = deque(
                [
                    m for m in self.memory_buffer
                    if m.ttl is None or
                    (m.last_accessed and
                     (now - m.last_accessed).total_seconds() < m.ttl)
                ],
                maxlen=self.max_size
            )
        
        except Exception as e:
            self.logger.error(f"Error cleaning up short-term memories: {str(e)}")
    
    def _calculate_importance(self, data: Dict[str, Any],
                            emotion: Optional[EmotionType]) -> float:
        """Calculate importance score for memory."""
        importance = 0.0
        
        # Base importance from confidence
        importance += data.get("confidence", 0.0) * 0.3
        
        # Importance from emotion
        if emotion:
            if emotion in [EmotionType.FEAR, EmotionType.JOY]:
                importance += 0.4
            elif emotion in [EmotionType.ANGER, EmotionType.SURPRISE]:
                importance += 0.3
            elif emotion in [EmotionType.SADNESS, EmotionType.DISGUST]:
                importance += 0.2
        
        # Importance from source
        if data.get("source") in [MemorySource.EYES, MemorySource.EARS]:
            importance += 0.2
        
        # Importance from context
        if data.get("context", {}).get("is_important", False):
            importance += 0.3
        
        return min(importance, 1.0)
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        if not self.processing_times:
            return {}
        
        return {
            "mean": sum(self.processing_times) / len(self.processing_times),
            "std": (sum((x - sum(self.processing_times) / len(self.processing_times)) ** 2
                      for x in self.processing_times) / len(self.processing_times)) ** 0.5,
            "min": min(self.processing_times),
            "max": max(self.processing_times)
        }
    
    def reset(self):
        """Reset the short-term memory manager."""
        self.memory_buffer.clear()
        self.processing_times = []
        self.logger.info("Short-term memory manager reset") 