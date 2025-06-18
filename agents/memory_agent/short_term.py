import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid

from structlog import get_logger

from ...config import settings

logger = get_logger()

class ShortTermMemory:
    """Short-term memory component for the Memory Agent."""
    
    def __init__(self):
        """Initialize the short-term memory."""
        self.memories: List[Dict] = []
        self.max_memories = settings.SHORT_TERM_MEMORY_MAX_SIZE
        self.retention_period = settings.SHORT_TERM_MEMORY_RETENTION_PERIOD
        self._initialized = False
    
    async def initialize(self):
        """Initialize the short-term memory component."""
        if self._initialized:
            return
        
        logger.info("Initializing short-term memory")
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the short-term memory component."""
        logger.info("Shutting down short-term memory")
        self._initialized = False
    
    async def add_memory(self, memory_data: Dict):
        """Add a new memory to short-term storage."""
        if not self._initialized:
            raise RuntimeError("Short-term memory not initialized")
        
        memory = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "type": memory_data.get("type", "general"),
            "content": memory_data.get("content", ""),
            "importance": memory_data.get("importance", 0.5),
            "emotions": memory_data.get("emotions", {}),
            "connections": memory_data.get("connections", []),
            "access_count": 0,
            "last_accessed": datetime.utcnow().isoformat()
        }
        
        # Add to memories
        self.memories.append(memory)
        
        # Check if we need to remove old memories
        await self._cleanup_old_memories()
        
        logger.debug(f"Added memory to short-term storage: {memory['id']}")
    
    async def _cleanup_old_memories(self):
        """Remove old memories based on retention period."""
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(seconds=self.retention_period)
        
        # Remove memories older than retention period
        self.memories = [
            m for m in self.memories
            if datetime.fromisoformat(m["timestamp"]) > cutoff_time
        ]
        
        # If still over max size, remove least important memories
        if len(self.memories) > self.max_memories:
            self.memories.sort(key=lambda x: x["importance"])
            self.memories = self.memories[-self.max_memories:]
    
    async def get_memory(self, memory_id: str) -> Optional[Dict]:
        """Get a specific memory by ID."""
        if not self._initialized:
            raise RuntimeError("Short-term memory not initialized")
        
        for memory in self.memories:
            if memory["id"] == memory_id:
                # Update access statistics
                memory["access_count"] += 1
                memory["last_accessed"] = datetime.utcnow().isoformat()
                return memory
        
        return None
    
    async def search_memory(self, query: Dict) -> List[Dict]:
        """Search memories based on criteria."""
        if not self._initialized:
            raise RuntimeError("Short-term memory not initialized")
        
        results = []
        
        for memory in self.memories:
            if self._matches_query(memory, query):
                results.append(memory)
                
                # Update access statistics
                memory["access_count"] += 1
                memory["last_accessed"] = datetime.utcnow().isoformat()
        
        return results
    
    def _matches_query(self, memory: Dict, query: Dict) -> bool:
        """Check if a memory matches the query criteria."""
        # Check type
        if "type" in query and memory["type"] != query["type"]:
            return False
        
        # Check content
        if "content" in query and query["content"].lower() not in memory["content"].lower():
            return False
        
        # Check time range
        if "start_time" in query:
            memory_time = datetime.fromisoformat(memory["timestamp"])
            start_time = datetime.fromisoformat(query["start_time"])
            if memory_time < start_time:
                return False
        
        if "end_time" in query:
            memory_time = datetime.fromisoformat(memory["timestamp"])
            end_time = datetime.fromisoformat(query["end_time"])
            if memory_time > end_time:
                return False
        
        return True
    
    async def get_recent_memories(self, count: int = 10) -> List[Dict]:
        """Get the most recent memories."""
        if not self._initialized:
            raise RuntimeError("Short-term memory not initialized")
        
        # Sort by timestamp and get most recent
        sorted_memories = sorted(
            self.memories,
            key=lambda x: x["timestamp"],
            reverse=True
        )
        
        return sorted_memories[:count]
    
    async def get_memory_count(self) -> int:
        """Get the number of memories in short-term storage."""
        if not self._initialized:
            raise RuntimeError("Short-term memory not initialized")
        
        return len(self.memories)
    
    async def get_stats(self) -> Dict:
        """Get short-term memory statistics."""
        if not self._initialized:
            raise RuntimeError("Short-term memory not initialized")
        
        return {
            "memory_count": len(self.memories),
            "max_memories": self.max_memories,
            "retention_period": self.retention_period,
            "oldest_memory": min(m["timestamp"] for m in self.memories) if self.memories else None,
            "newest_memory": max(m["timestamp"] for m in self.memories) if self.memories else None
        }
    
    async def clear_memories(self):
        """Clear all memories from short-term storage."""
        if not self._initialized:
            raise RuntimeError("Short-term memory not initialized")
        
        self.memories.clear()
        logger.info("Cleared all short-term memories") 