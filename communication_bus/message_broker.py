"""
Communication Bus — Message Broker

Production-grade async message broker with:
- Graceful degradation when Kafka/Redis are unavailable
- In-memory fallback queue (heapq-based priority ordering)
- Full __init__ attribute declaration (no AttributeError at runtime)
- Structured logging with correlation IDs
- Exponential backoff with jitter in retry loop
- Cursor-based Redis SCAN (O(1) per page, not O(n) KEYS)
- TTL dedup index eviction
- Message TTL enforcement in in-memory processing path
- Clean shutdown with task cancellation
"""

import asyncio
import heapq
import json
import logging
import math
import random
import zlib
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

try:
    from orchestrator.execution_context import get_execution_context
except Exception:
    def get_execution_context():  # type: ignore
        return None

try:
    import aiokafka
    _AIOKAFKA_AVAILABLE = True
except ImportError:
    aiokafka = None  # type: ignore
    _AIOKAFKA_AVAILABLE = False

try:
    import aioredis
    _AIOREDIS_AVAILABLE = True
except ImportError:
    try:
        import redis.asyncio as aioredis  # type: ignore
        _AIOREDIS_AVAILABLE = True
    except ImportError:
        aioredis = None  # type: ignore
        _AIOREDIS_AVAILABLE = False

try:
    from structlog import get_logger
    logger = get_logger()
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore

try:
    from .config import settings as _bus_settings
except ImportError:
    _bus_settings = None  # type: ignore

try:
    from orchestrator.request_context import get_request_context
except Exception:
    def get_request_context():  # type: ignore
        return None


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass(order=True)
class _PrioritizedMessage:
    """Heap-compatible wrapper: lower priority value = higher urgency."""
    priority: int
    sequence: int  # tie-breaker to maintain FIFO within same priority
    message_id: str = field(compare=False)
    topic: str = field(compare=False)
    sender: str = field(compare=False)
    recipient: Optional[str] = field(compare=False, default=None)
    content: Dict[str, Any] = field(compare=False, default_factory=dict)
    timestamp: str = field(compare=False, default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: Optional[str] = field(compare=False, default=None)
    metadata: Optional[Dict[str, Any]] = field(compare=False, default=None)
    correlation_id: Optional[str] = field(compare=False, default=None)
    trace_id: Optional[str] = field(compare=False, default=None)
    ordering_key: Optional[str] = field(compare=False, default=None)
    attempts: int = field(compare=False, default=0)
    max_attempts: int = field(compare=False, default=3)
    compressed: bool = field(compare=False, default=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
            "priority": self.priority,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "attempts": self.attempts,
        }

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            return datetime.fromisoformat(self.expires_at) <= datetime.utcnow()
        except Exception:
            return False


# ─── In-Memory Priority Queue ─────────────────────────────────────────────────

class _InMemoryPriorityQueue:
    """
    Thread-safe async priority queue backed by heapq.
    O(log n) push/pop. Used as fallback when Kafka is unavailable.
    """

    def __init__(self, maxsize: int = 10_000) -> None:
        self._heap: List[_PrioritizedMessage] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()
        self._maxsize = maxsize
        self._sequence = 0

    async def put(
        self,
        topic: str,
        sender: str,
        content: Dict[str, Any],
        recipient: Optional[str] = None,
        priority: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        async with self._lock:
            if len(self._heap) >= self._maxsize:
                # Evict lowest-priority (highest int value) item
                self._heap.sort()
                self._heap.pop()
            msg_id = str(uuid.uuid4())
            self._sequence += 1
            item = _PrioritizedMessage(
                priority=priority,
                sequence=self._sequence,
                message_id=msg_id,
                topic=topic,
                sender=sender,
                recipient=recipient,
                content=content,
                metadata=metadata,
                expires_at=expires_at,
                correlation_id=correlation_id,
                trace_id=trace_id,
            )
            heapq.heappush(self._heap, item)
            self._not_empty.set()
            return msg_id

    async def get(self, timeout: float = 0.1) -> Optional[_PrioritizedMessage]:
        try:
            await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        async with self._lock:
            if not self._heap:
                self._not_empty.clear()
                return None
            item = heapq.heappop(self._heap)
            if not self._heap:
                self._not_empty.clear()
            return item

    def qsize(self) -> int:
        return len(self._heap)


# ─── Message Broker ───────────────────────────────────────────────────────────

class MessageBroker:
    """
    Central message broker for the communication bus.

    Supports:
    - Kafka (when available and configured)
    - In-memory priority queue fallback (always available)
    - Redis persistence (when available)
    - Topic-based pub/sub with async handlers
    - Graceful start/stop with task cancellation
    - Exponential backoff with jitter in retry loop
    - Cursor-based Redis SCAN for message retrieval
    - TTL dedup index eviction
    - Message TTL enforcement in processing path
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = config or {}

        # ── State flags ──────────────────────────────────────────────────────
        self._initialized: bool = False
        self.is_running: bool = False

        # ── Kafka ────────────────────────────────────────────────────────────
        self.producer: Optional[Any] = None
        self.consumers: Dict[str, Any] = {}
        self.active_topics: Set[str] = set()

        # ── Redis ────────────────────────────────────────────────────────────
        self.redis_client: Optional[Any] = None

        # ── In-memory fallback ───────────────────────────────────────────────
        self._queue = _InMemoryPriorityQueue(
            maxsize=self.config.get("queue_maxsize", 10_000)
        )
        self.dead_letter_queue: List[_PrioritizedMessage] = []
        self.retry_queue: List[_PrioritizedMessage] = []
        self.message_history: List[_PrioritizedMessage] = []  # ← FIXED: was missing
        self.max_history: int = int(self.config.get("max_history", 10_000))  # ← FIXED: was missing
        self.max_dead_letters: int = int(self.config.get("dead_letter_maxsize", 10_000))
        self.max_retry_queue: int = int(self.config.get("retry_queue_maxsize", 10_000))
        self.backpressure_threshold: int = int(self.config.get("backpressure_threshold", 9_000))
        self._persistence_store: Dict[str, bytes] = {}
        self._deduplication_index: Dict[str, str] = {}
        self._dedup_timestamps: Dict[str, float] = {}  # key → insertion epoch for eviction
        self._dedup_ttl_seconds: float = float(self.config.get("dedup_ttl_seconds", 300.0))
        self._queue_metrics: Dict[str, Any] = {
            "enqueued": 0,
            "delivered": 0,
            "failed": 0,
            "retried": 0,
            "dead_lettered": 0,
            "persisted": 0,
            "deduplicated": 0,
            "expired": 0,
        }

        # ── Retry backoff config ─────────────────────────────────────────────
        self._retry_backoff_base: float = float(self.config.get("retry_backoff_base_seconds", 0.5))
        self._retry_backoff_max: float = float(self.config.get("retry_backoff_max_seconds", 30.0))
        self._retry_backoff_jitter: float = float(self.config.get("retry_backoff_jitter", 0.3))

        # ── Handlers ─────────────────────────────────────────────────────────
        self.message_handlers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}

        # ── Background tasks ─────────────────────────────────────────────────
        self._process_task: Optional[asyncio.Task] = None
        self._kafka_consume_task: Optional[asyncio.Task] = None
        self._retry_task: Optional[asyncio.Task] = None
        self._dedup_evict_task: Optional[asyncio.Task] = None

        # ── Metrics ──────────────────────────────────────────────────────────
        self.metrics: Dict[str, Any] = {
            "total_messages": 0,
            "delivered_messages": 0,
            "failed_messages": 0,
            "kafka_messages": 0,
            "memory_messages": 0,
            "average_delivery_time_ms": 0.0,
        }

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize broker — idempotent."""
        if self._initialized:
            return
        await self.start()

    async def start(self) -> None:
        """Start the message broker and all background workers."""
        if self.is_running:
            return

        logger.info("communication_bus.message_broker.starting")
        self.is_running = True

        # Try Kafka
        kafka_cfg = self.config.get("kafka", {})
        if kafka_cfg.get("enabled", False) and _AIOKAFKA_AVAILABLE:
            await self._init_kafka(kafka_cfg)

        # Try Redis
        redis_cfg = self.config.get("redis", {})
        if redis_cfg.get("enabled", False) and _AIOREDIS_AVAILABLE:
            await self._init_redis(redis_cfg)

        # Always start in-memory processing loop
        self._process_task = asyncio.create_task(
            self._process_loop(), name="comm_bus.process_loop"
        )
        self._retry_task = asyncio.create_task(
            self._retry_loop(), name="comm_bus.retry_loop"
        )
        self._dedup_evict_task = asyncio.create_task(
            self._dedup_eviction_loop(), name="comm_bus.dedup_evict"
        )

        self._initialized = True
        logger.info(
            "communication_bus.message_broker.started",
            kafka=self.producer is not None,
            redis=self.redis_client is not None,
        )

    async def stop(self) -> None:
        """Graceful shutdown — cancel tasks, close connections."""
        if not self.is_running:
            return

        logger.info("communication_bus.message_broker.stopping")
        self.is_running = False

        for task in [self._process_task, self._kafka_consume_task, self._retry_task, self._dedup_evict_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self.producer:
            try:
                await self.producer.stop()
            except Exception as exc:
                logger.warning("comm_bus.kafka_producer_stop_error", error=str(exc))

        for topic, consumer in self.consumers.items():
            try:
                await consumer.stop()
            except Exception as exc:
                logger.warning("comm_bus.kafka_consumer_stop_error", topic=topic, error=str(exc))

        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception:
                pass

        self._initialized = False
        logger.info("communication_bus.message_broker.stopped")

    async def shutdown(self) -> None:
        """Alias for stop()."""
        await self.stop()

    # ─── Kafka Init ───────────────────────────────────────────────────────────

    async def _init_kafka(self, kafka_cfg: Dict[str, Any]) -> None:
        servers = kafka_cfg.get("bootstrap_servers", ["localhost:9092"])
        if isinstance(servers, str):
            servers = [servers]
        try:
            self.producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                compression_type="gzip",
                max_batch_size=16_384,
                linger_ms=5,
                request_timeout_ms=10_000,
                retry_backoff_ms=200,
            )
            await self.producer.start()

            for topic in kafka_cfg.get("topics", []):
                await self._create_kafka_consumer(topic, servers, kafka_cfg)

            self._kafka_consume_task = asyncio.create_task(
                self._kafka_consume_loop(), name="comm_bus.kafka_consume"
            )
            logger.info("comm_bus.kafka_initialized", topics=list(self.active_topics))
        except Exception as exc:
            logger.warning("comm_bus.kafka_init_failed", error=str(exc))
            self.producer = None

    async def _create_kafka_consumer(
        self, topic: str, servers: List[str], kafka_cfg: Dict[str, Any]
    ) -> None:
        try:
            consumer = aiokafka.AIOKafkaConsumer(
                topic,
                bootstrap_servers=servers,
                group_id=kafka_cfg.get("group_id", "communication-bus"),
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="latest",
                enable_auto_commit=True,
                auto_commit_interval_ms=5_000,
                session_timeout_ms=30_000,
                heartbeat_interval_ms=10_000,
            )
            await consumer.start()
            self.consumers[topic] = consumer
            self.active_topics.add(topic)
        except Exception as exc:
            logger.warning("comm_bus.kafka_consumer_create_failed", topic=topic, error=str(exc))

    # ─── Redis Init ───────────────────────────────────────────────────────────

    async def _init_redis(self, redis_cfg: Dict[str, Any]) -> None:
        try:
            self.redis_client = await aioredis.from_url(
                f"redis://{redis_cfg.get('host', 'localhost')}:{redis_cfg.get('port', 6379)}/{redis_cfg.get('db', 0)}",
                password=redis_cfg.get("password"),
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await self.redis_client.ping()
            logger.info("comm_bus.redis_initialized")
        except Exception as exc:
            logger.warning("comm_bus.redis_init_failed", error=str(exc))
            self.redis_client = None

    # ─── Processing Loops ─────────────────────────────────────────────────────

    async def _process_loop(self) -> None:
        """Drain the in-memory queue and dispatch to registered handlers."""
        while self.is_running:
            try:
                item = await self._queue.get(timeout=0.05)
                if item is None:
                    continue

                # Enforce TTL: drop expired messages before dispatch
                if item.is_expired():
                    self._queue_metrics["expired"] += 1
                    logger.debug(
                        "comm_bus.message_expired_dropped",
                        message_id=item.message_id,
                        topic=item.topic,
                        correlation_id=item.correlation_id,
                    )
                    continue

                self._record_history(item)
                start = asyncio.get_event_loop().time()
                await self._dispatch(item.topic, item.to_dict())
                elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000
                self._update_delivery_metrics(elapsed_ms, success=True)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("comm_bus.process_loop_error", error=str(exc))
                self.metrics["failed_messages"] += 1
                await asyncio.sleep(0.5)

    async def _kafka_consume_loop(self) -> None:
        """Consume messages from all Kafka topics and dispatch to handlers."""
        while self.is_running:
            for topic, consumer in list(self.consumers.items()):
                try:
                    msg = await asyncio.wait_for(consumer.getone(), timeout=0.1)
                    await self._dispatch(topic, msg.value)
                    self.metrics["kafka_messages"] += 1
                except asyncio.TimeoutError:
                    pass
                except asyncio.CancelledError:
                    return
                except Exception as exc:
                    logger.error("comm_bus.kafka_consume_error", topic=topic, error=str(exc))
            await asyncio.sleep(0.01)

    async def _dispatch(self, topic: str, message: Dict[str, Any]) -> None:
        """Call all registered handlers for a topic."""
        handlers = self.message_handlers.get(topic, [])
        if not handlers:
            return
        for handler in handlers:
            try:
                await handler(message)
                self.metrics["delivered_messages"] += 1
                self._queue_metrics["delivered"] += 1
            except Exception as exc:
                logger.error(
                    "comm_bus.handler_error",
                    topic=topic,
                    handler=str(handler),
                    error=str(exc),
                    correlation_id=message.get("correlation_id"),
                    trace_id=message.get("trace_id"),
                )
                self.metrics["failed_messages"] += 1
                self._queue_metrics["failed"] += 1
                prioritized = _PrioritizedMessage(
                    priority=message.get("priority", 5),
                    sequence=len(self.message_history) + len(self.retry_queue) + 1,
                    message_id=message.get("message_id", str(uuid.uuid4())),
                    topic=topic,
                    sender=message.get("sender", "system"),
                    recipient=message.get("recipient"),
                    content=message,
                    metadata={"error": str(exc)},
                    correlation_id=message.get("correlation_id"),
                    trace_id=message.get("trace_id"),
                    ordering_key=message.get("ordering_key"),
                    expires_at=message.get("expires_at"),
                )
                await self._handle_failed_message(prioritized, str(exc))

    def _record_history(self, item: _PrioritizedMessage) -> None:
        self.message_history.append(item)
        try:
            payload = json.dumps(item.to_dict(), default=str).encode("utf-8")
            self._persistence_store[item.message_id] = zlib.compress(payload)
            self._queue_metrics["persisted"] += 1
        except Exception:
            pass
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history:]

    async def _handle_failed_message(self, message: _PrioritizedMessage, reason: str) -> None:
        if message.attempts + 1 >= message.max_attempts:
            await self._send_to_dead_letter(message, reason)
            return
        await self._enqueue_retry(message)

    # ─── Dedup Eviction Loop ──────────────────────────────────────────────────

    async def _dedup_eviction_loop(self) -> None:
        """Periodically evict expired deduplication index entries."""
        eviction_interval = max(30.0, self._dedup_ttl_seconds / 4)
        while self.is_running:
            try:
                await asyncio.sleep(eviction_interval)
                now = asyncio.get_event_loop().time()
                expired_keys = [
                    k for k, ts in list(self._dedup_timestamps.items())
                    if now - ts > self._dedup_ttl_seconds
                ]
                for k in expired_keys:
                    self._deduplication_index.pop(k, None)
                    self._dedup_timestamps.pop(k, None)
                if expired_keys:
                    logger.debug(
                        "comm_bus.dedup_evicted",
                        evicted_count=len(expired_keys),
                        remaining=len(self._deduplication_index),
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("comm_bus.dedup_eviction_error", error=str(exc))

    # ─── Public API ───────────────────────────────────────────────────────────

    async def publish_message(
        self,
        topic: str,
        message: Dict[str, Any],
        sender: str = "system",
        recipient: Optional[str] = None,
        priority: int = 5,
        dedup_key: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """
        Publish a message. Routes to Kafka if available, always enqueues
        in-memory for local handler dispatch.
        """
        if not self._initialized:
            raise RuntimeError("MessageBroker not initialized — call start() first")

        exec_context = get_execution_context()
        request_context = get_request_context()
        correlation_id = message.get("correlation_id") if isinstance(message, dict) else None
        trace_id = message.get("trace_id") if isinstance(message, dict) else None
        if request_context:
            correlation_id = correlation_id or request_context.correlation_id
            trace_id = trace_id or request_context.trace_id
        if exec_context:
            correlation_id = correlation_id or exec_context.correlation_id
            trace_id = trace_id or exec_context.trace_id

        dedup_key = dedup_key or (message.get("dedup_key") if isinstance(message, dict) else None)
        if dedup_key and dedup_key in self._deduplication_index:
            self._queue_metrics["deduplicated"] = self._queue_metrics.get("deduplicated", 0) + 1
            self.metrics["total_messages"] += 1
            logger.debug(
                "comm_bus.message_deduplicated",
                dedup_key=dedup_key,
                original_id=self._deduplication_index[dedup_key],
            )
            return self._deduplication_index[dedup_key]

        msg_id = str(uuid.uuid4())
        if dedup_key:
            self._deduplication_index[dedup_key] = msg_id
            self._dedup_timestamps[dedup_key] = asyncio.get_event_loop().time()

        # Compute TTL expiry
        # Respect explicit 0 TTL (meaning immediate expiration) — don't coerce with `or`.
        if ttl_seconds is not None:
            effective_ttl = ttl_seconds
        else:
            effective_ttl = (message.get("ttl_seconds") if isinstance(message, dict) else None)
        expires_at: Optional[str] = None
        if effective_ttl and int(effective_ttl) > 0:
            expires_at = (datetime.utcnow() + timedelta(seconds=int(effective_ttl))).isoformat()

        enriched = {
            **message,
            "message_id": msg_id,
            "topic": topic,
            "sender": sender,
            "recipient": recipient,
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": correlation_id or msg_id,
            "trace_id": trace_id or msg_id,
        }
        if expires_at:
            enriched["expires_at"] = expires_at

        self.metrics["total_messages"] += 1
        self._queue_metrics["enqueued"] += 1

        max_bytes = self.config.get("message_max_size_bytes", 1_048_576)
        try:
            encoded_size = len(json.dumps(enriched, default=str))
        except Exception:
            encoded_size = 0

        if encoded_size > max_bytes:
            await self._send_to_dead_letter(
                _PrioritizedMessage(
                    priority=priority,
                    sequence=0,
                    message_id=msg_id,
                    topic=topic,
                    sender=sender,
                    recipient=recipient,
                    content=enriched,
                    metadata={"reason": "payload_too_large", "size_bytes": encoded_size},
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    expires_at=expires_at,
                ),
                reason="payload_too_large",
            )
            logger.warning(
                "comm_bus.message_too_large",
                topic=topic,
                size_bytes=encoded_size,
                max_bytes=max_bytes,
                message_id=msg_id,
            )
            return msg_id

        # Backpressure check
        if self._queue.qsize() >= self.backpressure_threshold:
            logger.warning(
                "comm_bus.backpressure",
                queue_size=self._queue.qsize(),
                threshold=self.backpressure_threshold,
                topic=topic,
            )

        # Kafka publish (best-effort)
        if self.producer:
            try:
                await self.producer.send_and_wait(topic, enriched)
            except Exception as exc:
                logger.warning("comm_bus.kafka_publish_failed", topic=topic, error=str(exc))

        # Redis persistence (best-effort, async)
        if self.redis_client:
            try:
                redis_ttl = self.config.get("redis", {}).get("message_ttl", 86_400)
                payload = json.dumps(enriched, default=str).encode("utf-8")
                if self.config.get("message_compression_enabled", True):
                    payload = zlib.compress(payload)
                await self.redis_client.setex(f"msg:{msg_id}", redis_ttl, payload)
                self._queue_metrics["persisted"] += 1
            except Exception as exc:
                logger.debug("comm_bus.redis_persist_failed", message_id=msg_id, error=str(exc))

        # If TTL explicitly set to 0 treat as immediately expired and send to DLQ
        try:
            _effective_ttl_val = int(effective_ttl) if effective_ttl is not None else None
        except Exception:
            _effective_ttl_val = None
        if _effective_ttl_val == 0:
            prioritized = _PrioritizedMessage(
                priority=priority,
                sequence=len(self.message_history) + len(self.retry_queue) + 1,
                message_id=msg_id,
                topic=topic,
                sender=sender,
                recipient=recipient,
                content=enriched,
                metadata={"reason": "ttl_zero_expired"},
                correlation_id=enriched.get("correlation_id"),
                trace_id=enriched.get("trace_id"),
                expires_at=expires_at,
            )
            await self._send_to_dead_letter(prioritized, "ttl_zero_expired")
            self._queue_metrics["expired"] += 1
            logger.debug(
                "comm_bus.message_expired_at_publish",
                message_id=msg_id,
                topic=topic,
                correlation_id=enriched.get("correlation_id"),
            )
            return msg_id

        # Always enqueue in-memory for local dispatch
        await self._queue.put(
            topic=topic,
            sender=sender,
            content=enriched,
            recipient=recipient,
            priority=priority,
            metadata={
                "correlation_id": enriched["correlation_id"],
                "trace_id": enriched["trace_id"],
            },
            expires_at=expires_at,
            correlation_id=enriched["correlation_id"],
            trace_id=enriched["trace_id"],
        )
        self.metrics["memory_messages"] += 1

        logger.debug(
            "comm_bus.message_published",
            topic=topic,
            message_id=msg_id,
            priority=priority,
            correlation_id=enriched["correlation_id"],
            trace_id=enriched["trace_id"],
        )
        return msg_id

    async def send_message(
        self,
        topic: str,
        message: Dict[str, Any],
        sender: str = "system",
        recipient: Optional[str] = None,
        priority: int = 5,
    ) -> str:
        """Alias for publish_message — backward compatibility."""
        return await self.publish_message(topic, message, sender, recipient, priority)

    async def broadcast_message(self, message: Dict[str, Any], sender: str = "system") -> None:
        """Broadcast to all active topics."""
        for topic in list(self.active_topics) or ["system-events"]:
            await self.publish_message(topic, message, sender=sender)

    async def route_message(
        self, message: Dict[str, Any], target_topic: str, sender: str = "system"
    ) -> str:
        """Route a message to a specific topic."""
        return await self.publish_message(target_topic, message, sender=sender)

    def register_handler(
        self, topic: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Register an async handler for a topic."""
        if topic not in self.message_handlers:
            self.message_handlers[topic] = []
        if handler not in self.message_handlers[topic]:
            self.message_handlers[topic].append(handler)
        if topic not in self.active_topics:
            self.active_topics.add(topic)
        logger.info("comm_bus.handler_registered", topic=topic)

    def unregister_handler(
        self, topic: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Unregister a handler for a topic."""
        if topic in self.message_handlers:
            try:
                self.message_handlers[topic].remove(handler)
            except ValueError:
                pass

    async def subscribe_to_topic(
        self, topic: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Async alias for register_handler."""
        self.register_handler(topic, handler)

    async def unsubscribe_from_topic(
        self, topic: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Async alias for unregister_handler."""
        self.unregister_handler(topic, handler)

    async def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a persisted message from Redis by ID."""
        if not self.redis_client:
            # Fall back to in-memory persistence store
            raw = self._persistence_store.get(message_id)
            if raw:
                try:
                    return json.loads(zlib.decompress(raw))
                except Exception:
                    pass
            return None
        try:
            raw = await self.redis_client.get(f"msg:{message_id}")
            if raw:
                try:
                    decompressed = zlib.decompress(raw.encode("latin-1") if isinstance(raw, str) else raw)
                    return json.loads(decompressed)
                except Exception:
                    return json.loads(raw) if raw else None
            return None
        except Exception:
            return None

    async def get_messages(self, topic: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent messages for a topic.
        Uses cursor-based SCAN instead of O(n) KEYS when Redis is available.
        Falls back to in-memory history when Redis is unavailable.
        """
        if not self.redis_client:
            # In-memory fallback: scan message_history
            results = []
            for item in reversed(self.message_history):
                if item.topic == topic:
                    results.append(item.to_dict())
                    if len(results) >= limit:
                        break
            return results

        messages: List[Dict[str, Any]] = []
        cursor = 0
        scanned = 0
        max_scan = limit * 10  # scan up to 10× limit keys to find enough matches

        try:
            while True:
                cursor, keys = await self.redis_client.scan(cursor, match="msg:*", count=100)
                for key in keys:
                    if len(messages) >= limit or scanned >= max_scan:
                        break
                    scanned += 1
                    try:
                        raw = await self.redis_client.get(key)
                        if not raw:
                            continue
                        try:
                            data = json.loads(zlib.decompress(
                                raw.encode("latin-1") if isinstance(raw, str) else raw
                            ))
                        except Exception:
                            data = json.loads(raw)
                        if data.get("topic") == topic:
                            messages.append(data)
                    except Exception:
                        continue

                if cursor == 0 or len(messages) >= limit or scanned >= max_scan:
                    break
        except Exception as exc:
            logger.error("comm_bus.get_messages_scan_error", topic=topic, error=str(exc))

        return messages[:limit]

    async def process_messages(self) -> None:
        """Public alias so external callers (e.g. communication_bus/main.py) can reference
        the broker's processing loop without starting a duplicate internal task.
        This is a no-op when the broker is already running — the internal _process_loop
        is managed by start()."""
        if not self.is_running:
            await self.start()

    async def get_status(self) -> Dict[str, Any]:
        """Return current broker status and metrics."""
        return {
            "status": "running" if self.is_running else "stopped",
            "initialized": self._initialized,
            "kafka_connected": self.producer is not None,
            "redis_connected": self.redis_client is not None,
            "active_topics": sorted(self.active_topics),
            "queue_size": self._queue.qsize(),
            "queue_maxsize": self._queue._maxsize,
            "backpressure_threshold": self.backpressure_threshold,
            "registered_handlers": {
                topic: len(handlers)
                for topic, handlers in self.message_handlers.items()
            },
            "recovery": {
                "retry_queue_size": len(self.retry_queue),
                "dead_letter_size": len(self.dead_letter_queue),
                "history_size": len(self.message_history),
                "dedup_index_size": len(self._deduplication_index),
                "ready": self.is_running,
            },
            "metrics": self.metrics,
            "queue_metrics": self._queue_metrics,
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Alias for get_status() — backward compatibility with orchestrator/main.py."""
        return await self.get_status()

    async def get_metrics(self) -> Dict[str, Any]:
        """Return metrics dict."""
        return {**self.metrics, **self._queue_metrics}

    async def clear_metrics(self) -> None:
        """Reset all metrics counters."""
        self.metrics = {
            "total_messages": 0,
            "delivered_messages": 0,
            "failed_messages": 0,
            "kafka_messages": 0,
            "memory_messages": 0,
            "average_delivery_time_ms": 0.0,
        }
        self._queue_metrics = {
            "enqueued": 0,
            "delivered": 0,
            "failed": 0,
            "retried": 0,
            "dead_lettered": 0,
            "persisted": 0,
            "deduplicated": 0,
            "expired": 0,
        }
        self._deduplication_index = {}
        self._dedup_timestamps = {}

    async def get_dead_letter_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [message.to_dict() for message in self.dead_letter_queue[-limit:]]

    async def replay_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [message.to_dict() for message in self.message_history[-limit:]]

    async def cleanup_queues(self) -> Dict[str, int]:
        self.message_history = self.message_history[-self.max_history:]
        self.dead_letter_queue = self.dead_letter_queue[-self.max_dead_letters:]
        self.retry_queue = self.retry_queue[-self.max_retry_queue:]
        return {
            "history_size": len(self.message_history),
            "dead_letter_size": len(self.dead_letter_queue),
            "retry_queue_size": len(self.retry_queue),
        }

    async def _send_to_dead_letter(self, message: _PrioritizedMessage, reason: str) -> None:
        message.metadata = dict(message.metadata or {})
        message.metadata["dead_letter_reason"] = reason
        message.metadata["dead_lettered_at"] = datetime.utcnow().isoformat()
        if len(self.dead_letter_queue) >= self.max_dead_letters:
            self.dead_letter_queue.pop(0)
        self.dead_letter_queue.append(message)
        self._queue_metrics["dead_lettered"] += 1
        logger.warning(
            "comm_bus.message_dead_lettered",
            message_id=message.message_id,
            topic=message.topic,
            reason=reason,
            attempts=message.attempts,
            correlation_id=message.correlation_id,
            trace_id=message.trace_id,
        )

    async def _enqueue_retry(self, message: _PrioritizedMessage) -> None:
        if len(self.retry_queue) >= self.max_retry_queue:
            await self._send_to_dead_letter(message, "retry_queue_full")
            return
        message.attempts += 1
        self.retry_queue.append(message)
        self._queue_metrics["retried"] += 1

    def _compute_backoff(self, attempt: int) -> float:
        """
        Exponential backoff with full jitter.
        delay = min(max, base * 2^(attempt-1)) * U(0,1)
        where U(0,1) is uniform random in [1-jitter, 1+jitter].
        """
        base = self._retry_backoff_base
        cap = self._retry_backoff_max
        jitter = self._retry_backoff_jitter
        delay = min(cap, base * math.pow(2.0, max(0, attempt - 1)))
        jitter_factor = 1.0 + jitter * (random.random() * 2 - 1)
        return max(0.0, delay * jitter_factor)

    async def _retry_loop(self) -> None:
        """Process the retry queue with exponential backoff per message attempt."""
        while self.is_running:
            try:
                if not self.retry_queue:
                    await asyncio.sleep(0.1)
                    continue

                message = self.retry_queue.pop(0)

                if message.is_expired():
                    await self._send_to_dead_letter(message, "expired_during_retry")
                    continue

                if message.attempts >= message.max_attempts:
                    await self._send_to_dead_letter(message, "max_attempts_exceeded")
                    continue

                # Exponential backoff with jitter before re-enqueue
                backoff_seconds = self._compute_backoff(message.attempts)
                logger.info(
                    "comm_bus.retry_backoff",
                    message_id=message.message_id,
                    topic=message.topic,
                    attempt=message.attempts,
                    backoff_seconds=round(backoff_seconds, 3),
                    correlation_id=message.correlation_id,
                    trace_id=message.trace_id,
                )
                await asyncio.sleep(backoff_seconds)

                await self._queue.put(
                    topic=message.topic,
                    sender=message.sender,
                    content=message.content,
                    recipient=message.recipient,
                    priority=message.priority,
                    metadata=message.metadata,
                    expires_at=message.expires_at,
                    correlation_id=message.correlation_id,
                    trace_id=message.trace_id,
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("comm_bus.retry_loop_error", error=str(exc))
                await asyncio.sleep(0.5)

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _update_delivery_metrics(self, elapsed_ms: float, success: bool) -> None:
        if success:
            n = self.metrics["delivered_messages"]
            prev_avg = self.metrics["average_delivery_time_ms"]
            self.metrics["average_delivery_time_ms"] = (
                (prev_avg * n + elapsed_ms) / (n + 1) if n >= 0 else elapsed_ms
            )
