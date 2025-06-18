import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid
import json
import os

from structlog import get_logger

from ...config import settings

logger = get_logger()

class MemoryStore:
    """Memory store component for the Memory Agent."""
    
    def __init__(self):
        """Initialize the memory store."""
        self.memories: Dict[str, Dict] = {}
        self.memory_index: Dict[str, List[str]] = {}
        self.storage_path = settings.MEMORY_STORE_PATH
        self._initialized = False
    
    async def initialize(self):
        """Initialize the memory store component."""
        if self._initialized:
            return
        
        logger.info("Initializing memory store")
        
        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_path, exist_ok=True)
        
        # Load existing memories
        await self._load_memories()
        
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the memory store component."""
        logger.info("Shutting down memory store")
        
        # Save memories before shutting down
        await self._save_memories()
        
        self._initialized = False
    
    async def _load_memories(self):
        """Load memories from storage."""
        try:
            memory_file = os.path.join(self.storage_path, "memories.json")
            if os.path.exists(memory_file):
                with open(memory_file, "r") as f:
                    self.memories = json.load(f)
            
            index_file = os.path.join(self.storage_path, "memory_index.json")
            if os.path.exists(index_file):
                with open(index_file, "r") as f:
                    self.memory_index = json.load(f)
            
            logger.info(f"Loaded {len(self.memories)} memories from storage")
        except Exception as e:
            logger.error(f"Error loading memories: {str(e)}")
            self.memories = {}
            self.memory_index = {}
    
    async def _save_memories(self):
        """Save memories to storage."""
        try:
            # Save memories
            memory_file = os.path.join(self.storage_path, "memories.json")
            with open(memory_file, "w") as f:
                json.dump(self.memories, f)
            
            # Save index
            index_file = os.path.join(self.storage_path, "memory_index.json")
            with open(index_file, "w") as f:
                json.dump(self.memory_index, f)
            
            logger.info(f"Saved {len(self.memories)} memories to storage")
        except Exception as e:
            logger.error(f"Error saving memories: {str(e)}")
    
    async def store_memory(self, memory_data: Dict) -> str:
        """Store a new memory."""
        if not self._initialized:
            raise RuntimeError("Memory store not initialized")
        
        memory_id = str(uuid.uuid4())
        
        memory = {
            "id": memory_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": memory_data.get("type", "general"),
            "content": memory_data.get("content", ""),
            "importance": memory_data.get("importance", 0.5),
            "emotions": memory_data.get("emotions", {}),
            "connections": memory_data.get("connections", []),
            "access_count": 0,
            "last_accessed": datetime.utcnow().isoformat()
        }
        
        # Store memory
        self.memories[memory_id] = memory
        
        # Update index
        await self._update_index(memory)
        
        # Save to storage
        await self._save_memories()
        
        logger.debug(f"Stored memory: {memory_id}")
        return memory_id
    
    async def _update_index(self, memory: Dict):
        """Update the memory index with a new memory."""
        # Index by type
        if memory["type"] not in self.memory_index:
            self.memory_index[memory["type"]] = []
        self.memory_index[memory["type"]].append(memory["id"])
        
        # Index by content keywords
        keywords = self._extract_keywords(memory["content"])
        for keyword in keywords:
            if keyword not in self.memory_index:
                self.memory_index[keyword] = []
            self.memory_index[keyword].append(memory["id"])
    
    def _extract_keywords(self, content: str) -> List[str]:
        """Extract keywords from content."""
        # Simple keyword extraction - split by spaces and remove common words
        words = content.lower().split()
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        return [word for word in words if word not in stop_words and len(word) > 2]
    
    async def get_memory(self, memory_id: str) -> Optional[Dict]:
        """Get a specific memory by ID."""
        if not self._initialized:
            raise RuntimeError("Memory store not initialized")
        
        memory = self.memories.get(memory_id)
        if memory:
            # Update access statistics
            memory["access_count"] += 1
            memory["last_accessed"] = datetime.utcnow().isoformat()
            return memory
        
        return None
    
    async def search_memories(self, query: Dict) -> List[Dict]:
        """Search memories based on criteria."""
        if not self._initialized:
            raise RuntimeError("Memory store not initialized")
        
        results = []
        
        # If type is specified, use index
        if "type" in query:
            memory_ids = self.memory_index.get(query["type"], [])
            memories = [self.memories[m_id] for m_id in memory_ids if m_id in self.memories]
        else:
            memories = list(self.memories.values())
        
        # Filter memories
        for memory in memories:
            if self._matches_query(memory, query):
                results.append(memory)
                
                # Update access statistics
                memory["access_count"] += 1
                memory["last_accessed"] = datetime.utcnow().isoformat()
        
        return results
    
    def _matches_query(self, memory: Dict, query: Dict) -> bool:
        """Check if a memory matches the query criteria."""
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
    
    async def update_memory(self, memory_id: str, updates: Dict) -> bool:
        """Update an existing memory."""
        if not self._initialized:
            raise RuntimeError("Memory store not initialized")
        
        if memory_id not in self.memories:
            return False
        
        memory = self.memories[memory_id]
        
        # Update fields
        for key, value in updates.items():
            if key in memory:
                memory[key] = value
        
        # Update timestamp
        memory["last_modified"] = datetime.utcnow().isoformat()
        
        # Update index if type or content changed
        if "type" in updates or "content" in updates:
            await self._update_index(memory)
        
        # Save to storage
        await self._save_memories()
        
        logger.debug(f"Updated memory: {memory_id}")
        return True
    
    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory."""
        if not self._initialized:
            raise RuntimeError("Memory store not initialized")
        
        if memory_id not in self.memories:
            return False
        
        # Remove from memories
        del self.memories[memory_id]
        
        # Remove from index
        for index_list in self.memory_index.values():
            if memory_id in index_list:
                index_list.remove(memory_id)
        
        # Save to storage
        await self._save_memories()
        
        logger.debug(f"Deleted memory: {memory_id}")
        return True
    
    async def get_memory_count(self) -> int:
        """Get the number of memories in storage."""
        if not self._initialized:
            raise RuntimeError("Memory store not initialized")
        
        return len(self.memories)
    
    async def get_stats(self) -> Dict:
        """Get memory store statistics."""
        if not self._initialized:
            raise RuntimeError("Memory store not initialized")
        
        return {
            "memory_count": len(self.memories),
            "index_size": len(self.memory_index),
            "oldest_memory": min(m["timestamp"] for m in self.memories.values()) if self.memories else None,
            "newest_memory": max(m["timestamp"] for m in self.memories.values()) if self.memories else None,
            "storage_path": self.storage_path
        }
    
    async def clear_memories(self):
        """Clear all memories from storage."""
        if not self._initialized:
            raise RuntimeError("Memory store not initialized")
        
        self.memories.clear()
        self.memory_index.clear()
        
        # Remove storage files
        try:
            memory_file = os.path.join(self.storage_path, "memories.json")
            if os.path.exists(memory_file):
                os.remove(memory_file)
            
            index_file = os.path.join(self.storage_path, "memory_index.json")
            if os.path.exists(index_file):
                os.remove(index_file)
        except Exception as e:
            logger.error(f"Error removing storage files: {str(e)}")
        
        logger.info("Cleared all memories from storage") 