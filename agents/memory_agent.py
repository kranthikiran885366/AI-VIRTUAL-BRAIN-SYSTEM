import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from structlog import get_logger

from .base_agent import BaseAgent
from ..config import settings

logger = get_logger()

class MemoryAgent(BaseAgent):
    """Agent responsible for memory management and consolidation."""
    
    def __init__(self, agent_id: str):
        """Initialize the memory agent."""
        super().__init__(agent_id, "memory")
        self.short_term_memory: List[Dict] = []
        self.long_term_memory: List[Dict] = []
        self.memory_index: Dict[str, List[str]] = {}
        self.consolidation_threshold = 0.7
        self.max_short_term_memory = 1000
        self.max_long_term_memory = 10000
    
    async def initialize(self):
        """Initialize the memory agent."""
        await super().initialize()
        
        # Initialize memory-specific state
        self.state.update({
            "short_term_memory_count": 0,
            "long_term_memory_count": 0,
            "last_consolidation": datetime.utcnow().isoformat(),
            "consolidation_count": 0
        })
        
        logger.info(f"Memory agent {self.agent_id} initialized")
    
    async def _process_messages(self):
        """Process incoming messages."""
        # Process memory-related messages
        # This would typically involve receiving messages from the communication bus
        pass
    
    async def _update_state(self):
        """Update agent state."""
        self.state.update({
            "short_term_memory_count": len(self.short_term_memory),
            "long_term_memory_count": len(self.long_term_memory),
            "last_active": datetime.utcnow().isoformat()
        })
    
    async def _process_emotions(self):
        """Process and update emotions based on memory content."""
        # Analyze memory content to influence emotions
        recent_memories = self.short_term_memory[-10:]  # Last 10 memories
        
        # Calculate emotional impact
        emotional_impact = {
            "happiness": 0.0,
            "sadness": 0.0,
            "anger": 0.0,
            "fear": 0.0,
            "surprise": 0.0
        }
        
        for memory in recent_memories:
            if "emotions" in memory:
                for emotion, value in memory["emotions"].items():
                    if emotion in emotional_impact:
                        emotional_impact[emotion] += value
        
        # Update emotions with weighted average
        for emotion, impact in emotional_impact.items():
            current_value = self.emotions[emotion]
            new_value = (current_value * 0.7) + (impact * 0.3)  # 70% current, 30% new
            await self.update_emotion(emotion, new_value)
    
    async def _maintain_connections(self):
        """Maintain connections with other agents."""
        # Check for memory-related connections
        # This would typically involve communicating with other agents
        pass
    
    async def add_memory(self, memory_data: Dict):
        """Add a memory to short-term memory."""
        memory = {
            "id": memory_data.get("id", str(uuid.uuid4())),
            "timestamp": datetime.utcnow().isoformat(),
            "type": memory_data.get("type", "general"),
            "content": memory_data.get("content", ""),
            "importance": memory_data.get("importance", 0.5),
            "emotions": memory_data.get("emotions", {}),
            "connections": memory_data.get("connections", []),
            "access_count": 0,
            "last_accessed": datetime.utcnow().isoformat()
        }
        
        # Add to short-term memory
        self.short_term_memory.append(memory)
        
        # Update index
        self._update_memory_index(memory)
        
        # Check if consolidation is needed
        if len(self.short_term_memory) >= self.max_short_term_memory:
            await self._consolidate_memories()
        
        logger.debug(f"Added memory to short-term memory: {memory['id']}")
    
    async def _consolidate_memories(self):
        """Consolidate memories from short-term to long-term storage."""
        logger.info("Starting memory consolidation")
        
        # Sort memories by importance and recency
        sorted_memories = sorted(
            self.short_term_memory,
            key=lambda x: (x["importance"], x["timestamp"]),
            reverse=True
        )
        
        # Move important memories to long-term storage
        for memory in sorted_memories:
            if memory["importance"] >= self.consolidation_threshold:
                # Add to long-term memory
                self.long_term_memory.append(memory)
                
                # Remove from short-term memory
                self.short_term_memory.remove(memory)
                
                # Update state
                self.state["consolidation_count"] += 1
        
        # Update last consolidation timestamp
        self.state["last_consolidation"] = datetime.utcnow().isoformat()
        
        logger.info(f"Memory consolidation completed: {self.state['consolidation_count']} memories consolidated")
    
    def _update_memory_index(self, memory: Dict):
        """Update the memory index for efficient searching."""
        # Index by type
        if memory["type"] not in self.memory_index:
            self.memory_index[memory["type"]] = []
        self.memory_index[memory["type"]].append(memory["id"])
        
        # Index by content keywords (simple implementation)
        keywords = set(memory["content"].lower().split())
        for keyword in keywords:
            if keyword not in self.memory_index:
                self.memory_index[keyword] = []
            self.memory_index[keyword].append(memory["id"])
    
    async def search_memory(self, query: Dict) -> List[Dict]:
        """Search memories based on criteria."""
        results = []
        
        # Search in both short-term and long-term memory
        all_memories = self.short_term_memory + self.long_term_memory
        
        for memory in all_memories:
            # Check if memory matches query criteria
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
    
    async def get_memory_stats(self) -> Dict:
        """Get memory statistics."""
        return {
            "short_term_memory_count": len(self.short_term_memory),
            "long_term_memory_count": len(self.long_term_memory),
            "total_memory_count": len(self.short_term_memory) + len(self.long_term_memory),
            "index_size": len(self.memory_index),
            "consolidation_count": self.state["consolidation_count"],
            "last_consolidation": self.state["last_consolidation"]
        }
    
    async def clear_memory(self):
        """Clear all memories."""
        self.short_term_memory.clear()
        self.long_term_memory.clear()
        self.memory_index.clear()
        self.state.update({
            "short_term_memory_count": 0,
            "long_term_memory_count": 0,
            "consolidation_count": 0
        })
        logger.info(f"Cleared all memories for agent {self.agent_id}") 