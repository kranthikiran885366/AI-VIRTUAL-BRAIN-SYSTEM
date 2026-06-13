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
        self._message_broker = None
        self._message_queue = None
        self._last_heartbeat = None
    
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
            
            # Initialize message broker connection
            try:
                from orchestrator.agent_communication import get_message_broker
                self._message_broker = get_message_broker()
                self._message_queue = await self._message_broker.register_agent(self.agent_id)
                logger.debug(f"Agent {self.agent_id} registered with message broker")
            except Exception as e:
                logger.warning(f"Failed to initialize message broker for {self.agent_id}: {e}")
            
            # Start processing task
            self._process_task = asyncio.create_task(self._process_loop())
            
            self._initialized = True
            self.state["status"] = "active"
            self._last_heartbeat = datetime.utcnow()
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
                
                # Send heartbeat
                await self._send_heartbeat()
                
                # Check for incoming messages
                await self._process_incoming_messages()
                
                # Process incoming messages (legacy)
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
    
    async def _send_heartbeat(self):
        """Send a heartbeat message to indicate agent is alive."""
        if self._message_broker:
            try:
                from orchestrator.agent_communication import MessageType, MessagePriority
                await self._message_broker.send_message(
                    sender_agent_id=self.agent_id,
                    recipient_agent_id=None,  # Broadcast
                    message_type=MessageType.HEARTBEAT,
                    content={"status": self.state.get("status", "unknown")},
                    priority=MessagePriority.LOW
                )
                self._last_heartbeat = datetime.utcnow()
            except Exception as e:
                logger.debug(f"Failed to send heartbeat for {self.agent_id}: {e}")
    
    async def _process_incoming_messages(self):
        """Process incoming messages from message broker."""
        if not self._message_queue:
            return
        
        try:
            from orchestrator.agent_communication import MessageType
            
            # Check for messages in queue
            while True:
                message = await asyncio.wait_for(self._message_queue.get(), timeout=0.1)
                if not message:
                    break
                
                # Route message to appropriate handler
                if message.message_type == MessageType.MEMORY_RECALL:
                    await self._handle_memory_recall(message)
                elif message.message_type == MessageType.EMOTION_UPDATE:
                    await self._handle_emotion_update(message)
                elif message.message_type == MessageType.TASK_CREATE:
                    await self._handle_task_create(message)
                elif message.message_type == MessageType.DECISION_REQUEST:
                    await self._handle_decision_request(message)
                else:
                    # Pass to subclass for handling
                    await self._handle_custom_message(message)
        
        except asyncio.TimeoutError:
            pass  # No messages in queue
        except Exception as e:
            logger.debug(f"Error processing messages for {self.agent_id}: {e}")
    
    async def _handle_memory_recall(self, message: Any):
        """Handle memory recall request."""
        pass
    
    async def _handle_emotion_update(self, message: Any):
        """Handle emotion update."""
        pass
    
    async def _handle_task_create(self, message: Any):
        """Handle task creation."""
        pass
    
    async def _handle_decision_request(self, message: Any):
        """Handle decision request."""
        pass
    
    async def _handle_custom_message(self, message: Any):
        """Handle custom message - to be implemented by subclasses."""
        pass
    
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
    
    async def send_message(
        self,
        recipient_agent_id: str,
        message_type: str,
        content: Dict[str, Any],
        priority: str = "normal"
    ) -> Optional[str]:
        """Send a message to another agent."""
        if not self._message_broker:
            logger.warning(f"Message broker not available for {self.agent_id}")
            return None
        
        try:
            from orchestrator.agent_communication import MessageType, MessagePriority
            
            # Map string priority to enum
            priority_map = {
                "low": MessagePriority.LOW,
                "normal": MessagePriority.NORMAL,
                "high": MessagePriority.HIGH,
                "critical": MessagePriority.CRITICAL,
            }
            
            # Map string message type to enum
            try:
                msg_type = MessageType[message_type.upper()]
            except KeyError:
                logger.warning(f"Unknown message type: {message_type}")
                return None
            
            message_id = await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=recipient_agent_id,
                message_type=msg_type,
                content=content,
                priority=priority_map.get(priority.lower(), MessagePriority.NORMAL)
            )
            
            logger.debug(f"Message {message_id} sent from {self.agent_id} to {recipient_agent_id}")
            return message_id
        
        except Exception as e:
            logger.error(f"Failed to send message from {self.agent_id}: {e}")
            return None
    
    async def broadcast_message(
        self,
        message_type: str,
        content: Dict[str, Any],
        priority: str = "normal"
    ) -> Optional[str]:
        """Broadcast a message to all agents."""
        if not self._message_broker:
            logger.warning(f"Message broker not available for {self.agent_id}")
            return None
        
        try:
            from orchestrator.agent_communication import MessageType, MessagePriority
            
            priority_map = {
                "low": MessagePriority.LOW,
                "normal": MessagePriority.NORMAL,
                "high": MessagePriority.HIGH,
                "critical": MessagePriority.CRITICAL,
            }
            
            try:
                msg_type = MessageType[message_type.upper()]
            except KeyError:
                logger.warning(f"Unknown message type: {message_type}")
                return None
            
            message_id = await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=None,  # Broadcast
                message_type=msg_type,
                content=content,
                priority=priority_map.get(priority.lower(), MessagePriority.NORMAL)
            )
            
            logger.debug(f"Broadcast message {message_id} from {self.agent_id}")
            return message_id
        
        except Exception as e:
            logger.error(f"Failed to broadcast message from {self.agent_id}: {e}")
            return None 
