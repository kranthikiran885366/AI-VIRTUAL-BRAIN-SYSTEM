import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from structlog import get_logger

from ..config import settings

logger = get_logger()

class BaseAgent:
    """Base class for all virtual brain agents."""
    
    def __init__(self, agent_id: str, agent_type: str):
        """Initialize the base agent."""
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.state: Dict[str, Any] = {}
        self.memory: List[Dict] = []
        self.emotions: Dict[str, float] = {}
        self.connections: Dict[str, List[str]] = {}
        self._process_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the agent."""
        if self._initialized:
            return
        
        logger.info(f"Initializing agent {self.agent_id} of type {self.agent_type}")
        
        try:
            # Initialize agent state
            self.state = {
                "status": "initializing",
                "created_at": datetime.utcnow().isoformat(),
                "last_active": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }
            
            # Initialize emotions
            self.emotions = {
                "happiness": 0.5,
                "sadness": 0.0,
                "anger": 0.0,
                "fear": 0.0,
                "surprise": 0.0
            }
            
            # Start processing task
            self._process_task = asyncio.create_task(self._process_loop())
            
            self._initialized = True
            self.state["status"] = "active"
            logger.info(f"Agent {self.agent_id} initialized")
        except Exception as e:
            logger.error(f"Failed to initialize agent {self.agent_id}: {str(e)}")
            raise
    
    async def shutdown(self):
        """Shutdown the agent."""
        logger.info(f"Shutting down agent {self.agent_id}")
        
        # Cancel processing task
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        
        self.state["status"] = "shutdown"
        self._initialized = False
        logger.info(f"Agent {self.agent_id} shut down")
    
    async def _process_loop(self):
        """Main processing loop for the agent."""
        while True:
            try:
                # Update last active timestamp
                self.state["last_active"] = datetime.utcnow().isoformat()
                
                # Process incoming messages
                await self._process_messages()
                
                # Update agent state
                await self._update_state()
                
                # Process emotions
                await self._process_emotions()
                
                # Maintain connections
                await self._maintain_connections()
                
                await asyncio.sleep(settings.AGENT_PROCESSING_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in agent {self.agent_id} processing loop: {str(e)}")
                await asyncio.sleep(1)
    
    async def _process_messages(self):
        """Process incoming messages."""
        # To be implemented by specific agent types
        pass
    
    async def _update_state(self):
        """Update agent state."""
        # To be implemented by specific agent types
        pass
    
    async def _process_emotions(self):
        """Process and update emotions."""
        # To be implemented by specific agent types
        pass
    
    async def _maintain_connections(self):
        """Maintain connections with other agents."""
        # To be implemented by specific agent types
        pass
    
    async def add_memory(self, memory_data: Dict):
        """Add a memory to the agent's memory store."""
        memory = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "type": memory_data.get("type", "general"),
            "content": memory_data.get("content", ""),
            "importance": memory_data.get("importance", 0.5),
            "emotions": memory_data.get("emotions", {}),
            "connections": memory_data.get("connections", [])
        }
        
        self.memory.append(memory)
        logger.debug(f"Added memory to agent {self.agent_id}")
    
    async def update_emotion(self, emotion: str, value: float):
        """Update an emotion value."""
        if emotion in self.emotions:
            self.emotions[emotion] = max(0.0, min(1.0, value))
            logger.debug(f"Updated emotion {emotion} for agent {self.agent_id}")
    
    async def add_connection(self, agent_id: str, connection_type: str):
        """Add a connection to another agent."""
        if connection_type not in self.connections:
            self.connections[connection_type] = []
        
        if agent_id not in self.connections[connection_type]:
            self.connections[connection_type].append(agent_id)
            logger.debug(f"Added connection to agent {agent_id} for agent {self.agent_id}")
    
    async def remove_connection(self, agent_id: str, connection_type: str):
        """Remove a connection to another agent."""
        if connection_type in self.connections and agent_id in self.connections[connection_type]:
            self.connections[connection_type].remove(agent_id)
            logger.debug(f"Removed connection to agent {agent_id} for agent {self.agent_id}")
    
    async def get_status(self) -> Dict:
        """Get agent status."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "initialized": self._initialized,
            "state": self.state,
            "emotions": self.emotions,
            "connections": self.connections,
            "memory_count": len(self.memory)
        }
    
    async def get_memory(self, memory_id: str) -> Optional[Dict]:
        """Get a specific memory."""
        for memory in self.memory:
            if memory["id"] == memory_id:
                return memory
        return None
    
    async def search_memory(self, query: Dict) -> List[Dict]:
        """Search memories based on criteria."""
        # To be implemented by specific agent types
        return []
    
    async def clear_memory(self):
        """Clear all memories."""
        self.memory.clear()
        logger.info(f"Cleared memories for agent {self.agent_id}") 