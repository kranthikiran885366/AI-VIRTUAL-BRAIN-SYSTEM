"""
Agent Communication Bus and Message Broker

Handles all inter-agent communication and message routing in the virtual brain system.
Implements pub/sub pattern for agent-to-agent communication and event propagation.

Production changes (Phase 2):
- Initialized message_history and max_history in __init__
- Exponential backoff with jitter in _retry_loop
- get_stats() serializes MessageType values
- replay_dead_letters clears replayed messages from DLQ
"""

import asyncio
import heapq
import json
import logging
import math
import random
import time
import zlib
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

try:
    from structlog import get_logger
    logger = get_logger()
except ImportError:
    import logging as _logging
    logger = _logging.getLogger(__name__)  # type: ignore

try:
    from orchestrator.request_context import get_request_context
except Exception:
    def get_request_context():  # type: ignore
        return None


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
    PERCEPTION_EVENT = "perception_event"
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
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    ordering_key: Optional[str] = None
    dedup_key: Optional[str] = None
    expires_at: Optional[str] = None
    acked: bool = False
    nacked: bool = False
    attempts: int = 0
    max_attempts: int = 3
    compressed: bool = False
    schema_version: str = "1.0.0"
    delivery_status: str = "pending"
    error: Optional[str] = None

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

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            return datetime.fromisoformat(self.expires_at) <= datetime.utcnow()
        except Exception:
            return False


class MessageQueue:
    """
    Priority queue for messages backed by heapq.
    O(log n) push/pop — replaces the previous O(n) list-insert implementation.
    Critical messages (priority=0) are processed first.
    """

    def __init__(self, max_size: int = 10_000) -> None:
        self.max_size = max_size
        # heap entries: (priority_value, sequence, Message)
        self._heap: List[tuple] = []
        self._sequence: int = 0
        self.lock = asyncio.Lock()
        self._not_empty = asyncio.Event()

    async def put(self, message: Message) -> bool:
        """Add a message to the priority queue. Returns False if full."""
        async with self.lock:
            if len(self._heap) >= self.max_size:
                logger.warning(
                    "agent_comm.queue_full",
                    message_id=message.id,
                    queue_size=len(self._heap),
                )
                return False
            self._sequence += 1
            # Lower priority.value = higher urgency (CRITICAL=0 processed first)
            heapq.heappush(self._heap, (message.priority.value, self._sequence, message))
            self._not_empty.set()
            return True

    async def get(self) -> Optional[Message]:
        """Pop the highest-priority message. Returns None if empty."""
        async with self.lock:
            if not self._heap:
                self._not_empty.clear()
                return None
            _, _, message = heapq.heappop(self._heap)
            if not self._heap:
                self._not_empty.clear()
            return message

    async def peek(self) -> Optional[Message]:
        """Peek at the highest-priority message without removing it."""
        async with self.lock:
            if self._heap:
                return self._heap[0][2]
            return None

    async def size(self) -> int:
        """Return current queue depth."""
        async with self.lock:
            return len(self._heap)

    @property
    def queue(self) -> List[Message]:
        """Read-only view of queued messages (for compatibility with get_agent_messages)."""
        return [entry[2] for entry in self._heap]


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
        self.message_history: List[Message] = []          # ← FIXED: was missing in original
        self.dead_letter_queue: List[Message] = []
        self.retry_queue: List[Message] = []
        self._message_index: Dict[str, Message] = {}
        self._dedup_index: Dict[str, str] = {}
        self.max_history: int = 10_000                    # ← FIXED: was missing in original
        self.max_dead_letters: int = 10_000
        self.max_retry_queue: int = 10_000
        self.message_ttl_seconds: int = 3600
        self.backpressure_threshold: int = 9_000
        self.is_running: bool = False
        self._process_task: Optional[asyncio.Task] = None
        self._retry_task: Optional[asyncio.Task] = None
        self._history_lock = asyncio.Lock()
        self._subscribers_lock = asyncio.Lock()
        self._delivery_timeout: float = 5.0
        self._compression_enabled: bool = True
        # Exponential backoff config
        self._retry_backoff_base: float = 0.5
        self._retry_backoff_max: float = 30.0
        self._retry_backoff_jitter: float = 0.3
        self._queue_metrics: Dict[str, Any] = {
            "enqueued": 0,
            "delivered": 0,
            "acked": 0,
            "nacked": 0,
            "failed": 0,
            "retried": 0,
            "dead_lettered": 0,
            "expired": 0,
            "persisted": 0,
            "duplicates": 0,
        }

    async def start(self):
        """Start the message broker."""
        logger.info("agent_comm.broker.starting")
        self.is_running = True
        self._process_task = asyncio.create_task(
            self._process_loop(), name="agent_comm.process_loop"
        )
        self._retry_task = asyncio.create_task(
            self._retry_loop(), name="agent_comm.retry_loop"
        )
        logger.info("agent_comm.broker.started")

    async def stop(self):
        """Stop the message broker."""
        logger.info("agent_comm.broker.stopping")
        self.is_running = False
        for task in [self._process_task, self._retry_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("agent_comm.broker.stopped")

    async def _process_loop(self):
        """Main processing loop for messages."""
        while self.is_running:
            try:
                # Wait up to 50ms for a message before looping — prevents tight spin
                try:
                    await asyncio.wait_for(self.message_queue._not_empty.wait(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue
                message = await self.message_queue.get()
                if message:
                    self._store_in_history(message)
                    await self._route_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("agent_comm.process_loop_error", error=str(e))
                await asyncio.sleep(1)

    async def publish(self, message: Message) -> bool:
        """Publish a message to the broker."""
        if not self._validate_message(message):
            await self._send_to_dead_letter(message, "validation_failed")
            return False
        if message.dedup_key and message.dedup_key in self._dedup_index:
            self._queue_metrics["duplicates"] += 1
            return False
        if self.backpressure_threshold and await self.message_queue.size() >= self.backpressure_threshold:
            await self._enqueue_retry(message)
            return False
        message.delivery_status = "queued"
        if message.dedup_key:
            self._dedup_index[message.dedup_key] = message.id
        self._message_index[message.id] = message
        self._queue_metrics["enqueued"] += 1
        return await self.message_queue.put(message)

    async def send_message(
        self,
        sender_agent_id: str,
        recipient_agent_id: Optional[str],
        message_type: MessageType,
        content: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        reply_to: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        ordering_key: Optional[str] = None,
        dedup_key: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        max_attempts: int = 3,
    ) -> str:
        """Send a message through the broker."""
        if isinstance(message_type, str):
            try:
                message_type = MessageType(message_type.lower())
            except ValueError:
                try:
                    message_type = MessageType[message_type.upper()]
                except KeyError:
                    message_type = MessageType.STATE_UPDATE

        if not isinstance(priority, MessagePriority):
            if isinstance(priority, str):
                try:
                    priority = MessagePriority[priority.upper()]
                except KeyError:
                    priority = MessagePriority.NORMAL
            elif isinstance(priority, int):
                try:
                    priority = MessagePriority(priority)
                except ValueError:
                    priority = MessagePriority.NORMAL
            else:
                priority = MessagePriority.NORMAL

        request_context = get_request_context()
        correlation_id = (
            correlation_id
            or (request_context.correlation_id if request_context else None)
            or str(uuid.uuid4())
        )
        trace_id = (
            trace_id
            or (request_context.trace_id if request_context else None)
            or str(uuid.uuid4())
        )
        ordering_key = ordering_key or recipient_agent_id or sender_agent_id
        expires_at = None
        if ttl_seconds and ttl_seconds > 0:
            expires_at = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat()
        message = Message(
            id=str(uuid.uuid4()),
            sender_agent_id=sender_agent_id,
            recipient_agent_id=recipient_agent_id,
            message_type=message_type,
            content=content,
            priority=priority,
            timestamp=datetime.utcnow().isoformat(),

            reply_to=reply_to,
            metadata={"sent_at": datetime.utcnow().isoformat(), "status": "pending"},
            correlation_id=correlation_id,
            trace_id=trace_id,
            ordering_key=ordering_key,
            dedup_key=dedup_key,
            expires_at=expires_at,
            attempts=0,
            max_attempts=max_attempts,
            compressed=False,
        )

        await self.publish(message)
        logger.debug(
            "agent_comm.message_published",
            message_id=message.id,
            sender=sender_agent_id,
            recipient=recipient_agent_id,
            message_type=message_type.value,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        return message.id

    async def _route_message(self, message: Message):
        """Route a message to appropriate subscribers."""
        if message.is_expired():
            self._queue_metrics["expired"] += 1
            await self._send_to_dead_letter(message, "expired")
            return

        subscribers = list(self.subscribers.get(message.message_type, []))

        if message.recipient_agent_id:
            queue = self.agent_queues.get(message.recipient_agent_id)
            if queue:
                await queue.put(message)
                logger.debug(
                    "agent_comm.message_routed",
                    message_id=message.id,
                    recipient=message.recipient_agent_id,
                    correlation_id=message.correlation_id,
                )
            else:
                logger.warning(
                    "agent_comm.recipient_not_found",
                    recipient=message.recipient_agent_id,
                    message_id=message.id,
                )
                await self._handle_delivery_failure(message, "recipient_not_found")

        for subscriber_callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber_callback):
                    await asyncio.wait_for(
                        subscriber_callback(message), timeout=self._delivery_timeout
                    )
                else:
                    subscriber_callback(message)
                self._queue_metrics["delivered"] += 1
                await self.ack_message(message.id)
            except asyncio.TimeoutError:
                logger.warning(
                    "agent_comm.subscriber_timeout",
                    message_id=message.id,
                    timeout=self._delivery_timeout,
                )
                self._queue_metrics["failed"] += 1
                await self.nack_message(message.id, reason="subscriber_timeout")
            except Exception as e:
                logger.error(
                    "agent_comm.subscriber_error",
                    message_id=message.id,
                    error=str(e),
                    correlation_id=message.correlation_id,
                )
                self._queue_metrics["failed"] += 1
                await self.nack_message(message.id, reason=str(e))

    async def ack_message(self, message_id: str) -> bool:
        message = self._message_index.get(message_id)
        if not message:
            return False
        message.acked = True
        message.nacked = False
        message.delivery_status = "acked"
        self._queue_metrics["acked"] += 1
        return True

    async def nack_message(self, message_id: str, reason: str = "subscriber_error") -> bool:
        message = self._message_index.get(message_id)
        if not message:
            return False
        message.nacked = True
        message.delivery_status = "nacked"
        message.error = reason
        self._queue_metrics["nacked"] += 1
        await self._handle_delivery_failure(message, reason)
        return True

    async def _handle_delivery_failure(self, message: Message, reason: str) -> None:
        message.error = reason
        message.attempts += 1
        if message.attempts >= message.max_attempts:
            await self._send_to_dead_letter(message, reason)
            return
        await self._enqueue_retry(message)

    def _validate_message(self, message: Message) -> bool:
        if not message.id or not message.sender_agent_id or not message.message_type:
            return False
        if not isinstance(message.content, dict):
            return False
        if message.is_expired():
            return False
        return True

    def _record_history(self, message: Message) -> None:
        self.message_history.append(message)
        if message.dedup_key:
            self._dedup_index[message.dedup_key] = message.id
        if self._compression_enabled:
            try:
                payload = json.dumps(message.to_dict(), default=str).encode("utf-8")
                compressed = zlib.compress(payload)
                message.compressed = len(compressed) < len(payload)
            except Exception:
                message.compressed = False
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history:]
        self._message_index[message.id] = message

    async def _enqueue_retry(self, message: Message) -> None:
        if len(self.retry_queue) >= self.max_retry_queue:
            await self._send_to_dead_letter(message, "retry_queue_full")
            return
        message.delivery_status = "retrying"
        self.retry_queue.append(message)
        self._queue_metrics["retried"] += 1

    async def _send_to_dead_letter(self, message: Message, reason: str) -> None:
        message.delivery_status = "dead_letter"
        message.error = reason
        message.metadata = dict(message.metadata or {})
        message.metadata["dead_letter_reason"] = reason
        message.metadata["dead_lettered_at"] = datetime.utcnow().isoformat()
        if len(self.dead_letter_queue) >= self.max_dead_letters:
            self.dead_letter_queue.pop(0)
        self.dead_letter_queue.append(message)
        self._queue_metrics["dead_lettered"] += 1
        logger.warning(
            "agent_comm.dead_lettered",
            message_id=message.id,
            reason=reason,
            attempts=message.attempts,
            correlation_id=message.correlation_id,
        )

    def _compute_backoff(self, attempt: int) -> float:
        """Exponential backoff with full jitter: min(max, base * 2^(attempt-1)) * U(1±jitter)."""
        delay = min(self._retry_backoff_max, self._retry_backoff_base * math.pow(2.0, max(0, attempt - 1)))
        jitter_factor = 1.0 + self._retry_backoff_jitter * (random.random() * 2 - 1)
        return max(0.0, delay * jitter_factor)

    async def _retry_loop(self):
        """Retry loop with exponential backoff per message attempt."""
        while self.is_running:
            try:
                if not self.retry_queue:
                    await asyncio.sleep(0.1)
                    continue
                message = self.retry_queue.pop(0)
                if message.is_expired():
                    await self._send_to_dead_letter(message, "expired")
                    continue
                backoff = self._compute_backoff(message.attempts)
                logger.info(
                    "agent_comm.retry_backoff",
                    message_id=message.id,
                    attempt=message.attempts,
                    backoff_seconds=round(backoff, 3),
                    correlation_id=message.correlation_id,
                )
                await asyncio.sleep(backoff)
                await self.publish(message)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("agent_comm.retry_loop_error", error=str(exc))
                await asyncio.sleep(0.5)

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
        logger.debug("agent_comm.subscription_created", message_type=message_type.value)
        return subscription_id

    async def register_agent(self, agent_id: str) -> MessageQueue:
        """Register an agent with the broker."""
        queue = MessageQueue()
        self.agent_queues[agent_id] = queue
        logger.info("agent_comm.agent_registered", agent_id=agent_id)
        return queue

    async def unregister_agent(self, agent_id: str):
        """Unregister an agent from the broker."""
        if agent_id in self.agent_queues:
            del self.agent_queues[agent_id]
            logger.info("agent_comm.agent_unregistered", agent_id=agent_id)

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
        self._record_history(message)

    async def get_message_history(
        self,
        agent_id: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get message history."""
        history = self.message_history[-limit:]
        if agent_id:
            history = [
                m for m in history
                if m.sender_agent_id == agent_id or m.recipient_agent_id == agent_id
            ]
        if message_type:
            history = [m for m in history if m.message_type == message_type]
        return [m.to_dict() for m in history]

    async def get_stats(self) -> Dict[str, Any]:
        """Get broker statistics. MessageType values are serialized as strings."""
        return {
            "queue_size": await self.message_queue.size(),
            "agents_registered": len(self.agent_queues),
            "subscribers_count": sum(len(subs) for subs in self.subscribers.values()),
            # ← FIXED: was returning List[MessageType] enum objects, now plain strings
            "message_types": [mt.value for mt in MessageType],
            "history_size": len(self.message_history),
            "retry_queue_size": len(self.retry_queue),
            "dead_letter_size": len(self.dead_letter_queue),
            "is_running": self.is_running,
        }

    async def get_queue_status(self) -> Dict[str, Any]:
        return {
            "queue_size": await self.message_queue.size(),
            "retry_queue_size": len(self.retry_queue),
            "dead_letter_size": len(self.dead_letter_queue),
            "history_size": len(self.message_history),
            "metrics": dict(self._queue_metrics),
            "is_running": self.is_running,
        }

    async def replay_dead_letters(self, limit: Optional[int] = None) -> int:
        """
        Re-enqueue dead letter messages for retry.
        FIXED: clears replayed messages from the DLQ after successful enqueue.
        """
        replayed = 0
        to_replay = list(self.dead_letter_queue if limit is None else self.dead_letter_queue[:limit])
        successfully_replayed: List[Message] = []
        for message in to_replay:
            message.nacked = False
            message.error = None
            message.delivery_status = "retrying"
            message.attempts = 0
            await self._enqueue_retry(message)
            successfully_replayed.append(message)
            replayed += 1
        # Remove replayed messages from DLQ
        for msg in successfully_replayed:
            try:
                self.dead_letter_queue.remove(msg)
            except ValueError:
                pass
        logger.info("agent_comm.dead_letters_replayed", count=replayed)
        return replayed

    async def recover_queue(self) -> int:
        recovered = 0
        while self.retry_queue:
            message = self.retry_queue.pop(0)
            if not message.is_expired():
                await self.message_queue.put(message)
                recovered += 1
        return recovered

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self._queue_metrics)


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
