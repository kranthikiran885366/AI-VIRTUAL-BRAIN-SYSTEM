"""
Agent Communication Bus and Message Broker

Handles all inter-agent communication and message routing in the virtual brain system.
Implements pub/sub pattern for agent-to-agent communication and event propagation.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from structlog import get_logger

logger = get_logger()


class MessageType(str, Enum):
    """Types of messages that can be exchanged between agents."""
    MEMORY_STORE = "memory_store"
    MEMORY_RECALL = "memory_recall"
    EMOTION_UPDATE = "emotion_update"
    TASK_CREATE = "task_create"
    TASK_UPDATE = "task_update"
    DECISION_REQUEST = "decision_request"
    DECISION_RESULT = "decision_result"
    LEARNING_UPDATE = "learning_update"
    PERCEPTION_INPUT = "perception_input"
    SOCIAL_INTERACTION = "social_interaction"
    PLANNING_REQUEST = "planning_request"
    CREATIVITY_IDEA = "creativity_idea"
    REASONING_REQUEST = "reasoning_request"
    LANGUAGE_PROCESS = "language_process"
    MOTIVATION_REQUEST = "motivation_request"
    ETHICS_QUERY = "ethics_query"
    HEALTH_CHECK = "health_check"
    STATE_UPDATE = "state_update"
    CONNECTION_REQUEST = "connection_request"
    HEARTBEAT = "heartbeat"


class MessagePriority(int, Enum):
    """Priority levels for messages."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


@dataclass
class Message:
    """Message structure for agent communication."""
    id: str
    sender_agent_id: str
    recipient_agent_id: Optional[str]  # None for broadcast
    message_type: MessageType
    content: Dict[str, Any]
    priority: MessagePriority
    timestamp: str
    reply_to: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        data = asdict(self)
        data['message_type'] = self.message_type.value
        data['priority'] = self.priority.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        data = data.copy()
        data['message_type'] = MessageType(data['message_type'])
        data['priority'] = MessagePriority(data['priority'])
        return cls(**data)


class MessageQueue:
    """
    Priority queue for messages.
    Messages are processed by priority, with critical messages processed first.
    """
    
    def __init__(self, max_size: int = 10000):
        """Initialize the message queue."""
        self.max_size = max_size
        self.queue: List[Message] = []
        self.lock = asyncio.Lock()
    
    async def put(self, message: Message) -> bool:
        """Add a message to the queue."""
        async with self.lock:
            if len(self.queue) >= self.max_size:
                logger.warning(f"Message queue full, dropping message: {message.id}")
                return False
            
            # Insert message maintaining priority order
            insert_pos = 0
            for i, msg in enumerate(self.queue):
                if message.priority.value < msg.priority.value:
                    insert_pos = i
                    break
                insert_pos = i + 1
            
            self.queue.insert(insert_pos, message)
            return True
    
    async def get(self) -> Optional[Message]:
        """Get the next message from the queue."""
        async with self.lock:
            if self.queue:
                return self.queue.pop(0)
            return None
    
    async def peek(self) -> Optional[Message]:
        """Peek at the next message without removing it."""
        async with self.lock:
            if self.queue:
                return self.queue[0]
            return None
    
    async def size(self) -> int:
        """Get the current queue size."""
        async with self.lock:
            return len(self.queue)


class MessageBroker:
    """
    Central message broker for agent communication.
    Implements publish-subscribe pattern for inter-agent communication.
    """
    
    def __init__(self):
        """Initialize the message broker."""
        self.message_queue = MessageQueue()
        self.subscribers: Dict[MessageType, List[Callable]] = {}
        self.agent_queues: Dict[str, MessageQueue] = {}
        self.message_history: List[Message] = []
        self.max_history = 10000
        self.is_running = False
        self._process_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the message broker."""
        logger.info("Starting message broker...")
        self.is_running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("Message broker started")
    
    async def stop(self):
        """Stop the message broker."""
        logger.info("Stopping message broker...")
        self.is_running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("Message broker stopped")
    
    async def _process_loop(self):
        """Main processing loop for messages."""
        while self.is_running:
            try:
                # Get next message from queue
                message = await self.message_queue.get()
                
                if message:
                    # Store in history
                    self._store_in_history(message)
                    
                    # Route message
                    await self._route_message(message)
                else:
                    # No messages, wait a bit before checking again
                    await asyncio.sleep(0.1)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message broker loop: {e}")
                await asyncio.sleep(1)
    
    async def publish(self, message: Message) -> bool:
        """Publish a message to the broker."""
        return await self.message_queue.put(message)
    
    async def send_message(
        self,
        sender_agent_id: str,
        recipient_agent_id: Optional[str],
        message_type: MessageType,
        content: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        reply_to: Optional[str] = None,
    ) -> str:
        """Send a message through the broker."""
        message = Message(
            id=str(uuid.uuid4()),
            sender_agent_id=sender_agent_id,
            recipient_agent_id=recipient_agent_id,
            message_type=message_type,
            content=content,
            priority=priority,
            timestamp=datetime.utcnow().isoformat(),
            reply_to=reply_to,
            metadata={
                "sent_at": datetime.utcnow().isoformat(),
                "status": "pending"
            }
        )
        
        await self.publish(message)
        logger.debug(f"Message published: {message.id} from {sender_agent_id}")
        
        return message.id
    
    async def _route_message(self, message: Message):
        """Route a message to appropriate subscribers."""
        # Get subscribers for this message type
        subscribers = self.subscribers.get(message.message_type, [])
        
        # Route to specific agent if specified
        if message.recipient_agent_id:
            queue = self.agent_queues.get(message.recipient_agent_id)
            if queue:
                await queue.put(message)
                logger.debug(f"Message {message.id} routed to {message.recipient_agent_id}")
            else:
                logger.warning(f"Agent {message.recipient_agent_id} not found")
        
        # Notify all subscribers
        for subscriber_callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber_callback):
                    await subscriber_callback(message)
                else:
                    subscriber_callback(message)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")
    
    def subscribe(
        self,
        message_type: MessageType,
        callback: Callable[[Message], Any]
    ) -> str:
        """Subscribe to messages of a specific type."""
        if message_type not in self.subscribers:
            self.subscribers[message_type] = []
        
        self.subscribers[message_type].append(callback)
        subscription_id = str(uuid.uuid4())
        
        logger.debug(f"Subscription created for {message_type.value}")
        return subscription_id
    
    async def register_agent(self, agent_id: str) -> MessageQueue:
        """Register an agent with the broker."""
        queue = MessageQueue()
        self.agent_queues[agent_id] = queue
        logger.info(f"Agent {agent_id} registered with broker")
        return queue
    
    async def unregister_agent(self, agent_id: str):
        """Unregister an agent from the broker."""
        if agent_id in self.agent_queues:
            del self.agent_queues[agent_id]
            logger.info(f"Agent {agent_id} unregistered from broker")
    
    async def get_agent_messages(
        self,
        agent_id: str,
        message_type: Optional[MessageType] = None,
        limit: int = 100
    ) -> List[Message]:
        """Get messages for a specific agent."""
        queue = self.agent_queues.get(agent_id)
        if not queue:
            return []
        
        messages = queue.queue[:limit]
        
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]
        
        return messages
    
    def _store_in_history(self, message: Message):
        """Store message in history."""
        self.message_history.append(message)
        
        # Trim history if too large
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history:]
    
    async def get_message_history(
        self,
        agent_id: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get message history."""
        history = self.message_history[-limit:]
        
        if agent_id:
            history = [m for m in history if m.sender_agent_id == agent_id or m.recipient_agent_id == agent_id]
        
        if message_type:
            history = [m for m in history if m.message_type == message_type]
        
        return [m.to_dict() for m in history]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get broker statistics."""
        return {
            "queue_size": await self.message_queue.size(),
            "agents_registered": len(self.agent_queues),
            "subscribers_count": sum(len(subs) for subs in self.subscribers.values()),
            "message_types": list(MessageType),
            "history_size": len(self.message_history),
            "is_running": self.is_running
        }


# Global message broker instance
message_broker: Optional[MessageBroker] = None


def get_message_broker() -> MessageBroker:
    """Get or create the global message broker."""
    global message_broker
    if message_broker is None:
        message_broker = MessageBroker()
    return message_broker


async def initialize_message_broker():
    """Initialize and start the message broker."""
    broker = get_message_broker()
    await broker.start()
    return broker


async def shutdown_message_broker():
    """Shutdown the message broker."""
    broker = get_message_broker()
    await broker.stop()
