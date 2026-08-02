"""
Communication Controller

Manages request/event/command routing between system components.

Production changes (Phase 2):
- _initialized set to True at end of start()
- Redis uses redis.asyncio (async) — all Redis ops are awaited
- send_message has retry logic with configurable backoff
- get_message_history() implemented with in-memory ring buffer
- register_handler / handler dispatch wired up for route_message
- correlation/trace ID propagated on all outbound messages
- _event_history ring buffer for observability
- Structured logging throughout
"""

import asyncio
import json
import logging
import math
import random
import uuid
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Set
from datetime import datetime

try:
    import aiokafka
except ImportError:
    aiokafka = None  # type: ignore

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore

# Use async Redis exclusively — never the sync client
try:
    import redis.asyncio as _aioredis
    _AIOREDIS_AVAILABLE = True
except ImportError:
    try:
        import aioredis as _aioredis  # type: ignore
        _AIOREDIS_AVAILABLE = True
    except ImportError:
        _aioredis = None  # type: ignore
        _AIOREDIS_AVAILABLE = False

try:
    from structlog import get_logger
except ImportError:
    def get_logger():  # type: ignore
        return logging.getLogger(__name__)

logger = get_logger()

try:
    from orchestrator.request_context import get_request_context
except Exception:
    def get_request_context():  # type: ignore
        return None

try:
    from orchestrator.observability import runtime_observability
except Exception:
    runtime_observability = None  # type: ignore


class CommunicationController:
    """Manages communication between system components."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the communication controller with configuration."""
        self.config = config if isinstance(config, dict) else {}
        self.is_running: bool = False

        # Initialize bounded message queues
        queue_limits = self.config.get("queue_limits", {}) if isinstance(self.config, dict) else {}
        self.message_queue: asyncio.Queue = asyncio.Queue(
            maxsize=int(queue_limits.get("message_queue_size", 1000))
        )
        self.event_queue: asyncio.Queue = asyncio.Queue(
            maxsize=int(queue_limits.get("event_queue_size", 1000))
        )

        # External integrations (optional)
        self.kafka_producer = None
        self.kafka_consumer = None
        self.redis_client: Optional[Any] = None
        self.http_session: Optional[Any] = None

        # Internal aliases (keep for backward compat)
        self.producer: Optional[Any] = None
        self.consumer: Optional[Any] = None

        self.active_topics: Set[str] = set()

        # Handler registry: topic/event_type → list of async callables
        self.message_handlers: Dict[str, List[Callable]] = {}

        # In-memory event history ring buffer for observability
        self._max_event_history: int = int(
            self.config.get("max_event_history", 1000)
        )
        self._event_history: Deque[Dict[str, Any]] = deque(maxlen=self._max_event_history)

        # Background tasks
        self._process_task: Optional[asyncio.Task] = None
        self._dispatch_task: Optional[asyncio.Task] = None

        self._controller_lock = asyncio.Lock()
        self._initialized: bool = False

        # Retry config
        _retry_cfg = self.config.get("retry", {}) if isinstance(self.config, dict) else {}
        self._max_retries: int = int(_retry_cfg.get("max_retries", 3))
        self._retry_backoff_base: float = float(_retry_cfg.get("backoff_seconds", 0.25))
        self._retry_backoff_max: float = float(_retry_cfg.get("backoff_max_seconds", 10.0))

        self.metrics: Dict[str, Any] = {
            "sent": 0,
            "received": 0,
            "errors": 0,
            "timeouts": 0,
            "routed": 0,
            "recovered": 0,
            "retried": 0,
        }

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize the communication controller."""
        await self.start()

    async def start(self) -> None:
        """Start the communication controller."""
        logger.info("comm_controller.starting")
        self.is_running = True

        await self._init_kafka()
        await self._init_redis()

        if aiohttp is not None:
            self.http_session = aiohttp.ClientSession()
        else:
            self.http_session = None

        if not self._process_task or self._process_task.done():
            self._process_task = asyncio.create_task(
                self.process_messages(), name="comm_controller.process_messages"
            )

        # ← FIXED: was never set to True — get_status() always reported initialized=False
        self._initialized = True
        logger.info("comm_controller.started", kafka=self.producer is not None, redis=self.redis_client is not None)

    async def stop(self) -> None:
        """Stop the communication controller."""
        logger.info("comm_controller.stopping")
        self.is_running = False

        for task in [self._process_task, self._dispatch_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self.producer:
            try:
                await self.producer.stop()
            except Exception:
                pass
        if self.consumer:
            try:
                await self.consumer.stop()
            except Exception:
                pass

        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception:
                pass

        if self.http_session:
            try:
                await self.http_session.close()
            except Exception:
                pass

        self._initialized = False
        logger.info("comm_controller.stopped")

    # ─── External Connection Init ─────────────────────────────────────────────

    async def _init_kafka(self) -> None:
        """Initialize Kafka connections (optional)."""
        if not self.config.get("kafka", {}).get("enabled", False):
            logger.info("comm_controller.kafka_disabled")
            return
        if aiokafka is None:
            logger.info("comm_controller.kafka_unavailable")
            return

        kafka_config = self.config.get("kafka", {})
        try:
            self.producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=kafka_config.get("bootstrap_servers", ["localhost:9092"]),
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )
            await self.producer.start()

            self.consumer = aiokafka.AIOKafkaConsumer(
                *kafka_config.get("topics", []),
                bootstrap_servers=kafka_config.get("bootstrap_servers", ["localhost:9092"]),
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                group_id=kafka_config.get("consumer_group", "orchestrator-group"),
            )
            await self.consumer.start()
            await self.consumer.subscribe(kafka_config.get("topics", []))

            self.active_topics.update(kafka_config.get("topics", []))
            logger.info("comm_controller.kafka_initialized", topics=sorted(self.active_topics))

        except Exception as e:
            logger.error("comm_controller.kafka_init_failed", error=str(e))
            self.producer = None
            self.consumer = None

    async def _init_redis(self) -> None:
        """Initialize async Redis connection."""
        if not self.config.get("redis", {}).get("enabled", False):
            logger.info("comm_controller.redis_disabled")
            return
        if not _AIOREDIS_AVAILABLE:
            logger.info("comm_controller.redis_unavailable")
            return

        try:
            redis_cfg = self.config.get("redis", {})
            # ← FIXED: was using synchronous redis.Redis — now uses redis.asyncio
            self.redis_client = await _aioredis.from_url(
                f"redis://{redis_cfg.get('host', 'localhost')}:{redis_cfg.get('port', 6379)}/{redis_cfg.get('db', 0)}",
                password=redis_cfg.get("password"),
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await self.redis_client.ping()
            logger.info("comm_controller.redis_initialized")
        except Exception as e:
            logger.error("comm_controller.redis_init_failed", error=str(e))
            self.redis_client = None

    # ─── Validation ───────────────────────────────────────────────────────────

    def _validate_payload(self, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        try:
            size = len(json.dumps(payload, default=str))
        except Exception:
            return False
        if size > int(self.config.get("max_payload_bytes", 1_048_576)):
            return False
        return True

    # ─── Message Send with Retry ──────────────────────────────────────────────

    async def send_message(self, topic: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to Kafka and/or persist to Redis.
        Retries up to self._max_retries with exponential backoff.
        """
        context = get_request_context()
        message = dict(message)
        if not self._validate_payload(message):
            self.metrics["errors"] += 1
            logger.warning(
                "comm_controller.invalid_payload",
                topic=topic,
                size=len(json.dumps(message, default=str)) if isinstance(message, dict) else 0,
            )
            return False

        message.setdefault("timestamp", datetime.utcnow().isoformat())
        message.setdefault(
            "correlation_id",
            (context.correlation_id if context else None) or str(uuid.uuid4()),
        )
        message.setdefault(
            "trace_id",
            (context.trace_id if context else None) or str(uuid.uuid4()),
        )

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                timeout = float(self.config.get("timeout", 5))
                if self.producer:
                    await asyncio.wait_for(
                        self.producer.send_and_wait(topic, message), timeout=timeout
                    )

                # ← FIXED: Redis ops are now awaited (async client)
                if self.redis_client:
                    msg_id = message.get("id", str(uuid.uuid4()))
                    await self.redis_client.set(
                        f"message:{msg_id}",
                        json.dumps(message, default=str),
                    )

                self.metrics["sent"] += 1
                if runtime_observability:
                    runtime_observability.record_queue_usage(
                        "comm_controller.message_queue",
                        self.message_queue.qsize(),
                        self.message_queue.maxsize if hasattr(self.message_queue, "maxsize") else None,
                    )
                return True

            except asyncio.TimeoutError:
                self.metrics["timeouts"] += 1
                last_exc = asyncio.TimeoutError(f"send_message timed out on attempt {attempt + 1}")
                logger.warning(
                    "comm_controller.send_timeout",
                    topic=topic,
                    attempt=attempt + 1,
                    max_retries=self._max_retries,
                )
            except Exception as e:
                last_exc = e
                logger.warning(
                    "comm_controller.send_error",
                    topic=topic,
                    attempt=attempt + 1,
                    error=str(e),
                )

            if attempt < self._max_retries:
                backoff = min(
                    self._retry_backoff_max,
                    self._retry_backoff_base * math.pow(2.0, attempt),
                ) * (0.8 + 0.4 * random.random())
                self.metrics["retried"] += 1
                await asyncio.sleep(backoff)

        self.metrics["errors"] += 1
        logger.error(
            "comm_controller.send_failed",
            topic=topic,
            max_retries=self._max_retries,
            error=str(last_exc),
        )
        return False

    async def receive_message(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Receive a message from Kafka."""
        if not self.consumer:
            return None
        try:
            msg = await asyncio.wait_for(
                self.consumer.getone(),
                timeout=timeout or float(self.config.get("timeout", 5)),
            )
            if msg:
                self.metrics["received"] += 1
                return msg.value
            return None
        except asyncio.TimeoutError:
            return None
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("comm_controller.receive_error", error=str(e))
            return None

    # ─── Event Broadcast ──────────────────────────────────────────────────────

    async def broadcast_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Broadcast an event to all registered handlers and Kafka."""
        context = get_request_context()
        if not isinstance(event_data, dict):
            return False
        event = {
            "type": event_type,
            "data": event_data,
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": (context.correlation_id if context else None) or str(uuid.uuid4()),
            "trace_id": (context.trace_id if context else None) or str(uuid.uuid4()),
        }
        if not self._validate_payload(event):
            self.metrics["errors"] += 1
            return False

        try:
            await asyncio.wait_for(
                self.event_queue.put(event),
                timeout=float(self.config.get("timeout", 5)),
            )
        except (asyncio.TimeoutError, asyncio.QueueFull):
            logger.warning("comm_controller.event_queue_full", event_type=event_type)

        # Record in history ring buffer
        self._event_history.append(event)

        # Dispatch to registered handlers
        for handler in list(self.message_handlers.get(event_type, [])):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as exc:
                logger.error(
                    "comm_controller.event_handler_error",
                    event_type=event_type,
                    error=str(exc),
                )

        # Kafka broadcast
        await self.send_message("events", event)
        self.metrics["routed"] += 1

        if runtime_observability:
            runtime_observability.record_queue_usage(
                "comm_controller.event_queue",
                self.event_queue.qsize(),
                self.event_queue.maxsize if hasattr(self.event_queue, "maxsize") else None,
            )
        return True

    # ─── Message Processing Loop ──────────────────────────────────────────────

    async def process_messages(self) -> None:
        """Process incoming messages from the internal queue."""
        while self.is_running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=float(self.config.get("timeout", 5)),
                )
                await self._handle_message(message)
                self.message_queue.task_done()
            except asyncio.CancelledError:
                break
            except asyncio.TimeoutError:
                await asyncio.sleep(0)
            except Exception as e:
                self.metrics["errors"] += 1
                logger.error("comm_controller.process_error", error=str(e))

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Dispatch an incoming message by type."""
        if not self._validate_payload(message):
            self.metrics["errors"] += 1
            return

        message_type = message.get("type")
        if runtime_observability:
            runtime_observability.record_queue_usage(
                "comm_controller.event_queue",
                self.event_queue.qsize(),
                self.event_queue.maxsize if hasattr(self.event_queue, "maxsize") else None,
            )

        if message_type == "task":
            await self._handle_task_message(message)
        elif message_type == "event":
            await self._handle_event_message(message)
        elif message_type == "status":
            await self._handle_status_message(message)
        else:
            logger.debug("comm_controller.unknown_message_type", message_type=message_type)

    async def _handle_task_message(self, message: Dict[str, Any]) -> None:
        """Handle a task message — persists to Redis if available."""
        task_id = message.get("content", {}).get("id") or message.get("id")
        logger.debug(
            "comm_controller.task_message",
            task_id=task_id,
            correlation_id=message.get("correlation_id"),
        )
        if self.redis_client and task_id:
            try:
                # ← FIXED: was using synchronous .hset() — now awaited
                await self.redis_client.hset(f"task:{task_id}", mapping={
                    "status": message.get("content", {}).get("status", "pending"),
                    "updated_at": datetime.utcnow().isoformat(),
                    "source": message.get("sender_agent_id", "unknown"),
                })
            except Exception as e:
                logger.debug("comm_controller.redis_task_store_failed", task_id=task_id, error=str(e))

    async def _handle_event_message(self, message: Dict[str, Any]) -> None:
        """Handle an event message — persists to Redis if available."""
        event_id = message.get("id", str(uuid.uuid4()))
        logger.debug(
            "comm_controller.event_message",
            event_id=event_id,
            correlation_id=message.get("correlation_id"),
        )
        if self.redis_client:
            try:
                # ← FIXED: was using synchronous .hset() — now awaited
                await self.redis_client.hset(f"event:{event_id}", mapping={
                    "type": message.get("type", "event"),
                    "payload": json.dumps(message.get("content", {}), default=str),
                    "created_at": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.debug("comm_controller.redis_event_store_failed", event_id=event_id, error=str(e))

    async def _handle_status_message(self, message: Dict[str, Any]) -> None:
        """Handle a status message — persists to Redis if available."""
        agent_id = message.get("sender_agent_id", "unknown")
        logger.debug(
            "comm_controller.status_message",
            agent_id=agent_id,
            correlation_id=message.get("correlation_id"),
        )
        if self.redis_client:
            try:
                # ← FIXED: was using synchronous .hset() — now awaited
                await self.redis_client.hset(f"status:{agent_id}", mapping={
                    "status": message.get("content", {}).get("status", "unknown"),
                    "updated_at": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.debug("comm_controller.redis_status_store_failed", agent_id=agent_id, error=str(e))

    # ─── Handler Registry ─────────────────────────────────────────────────────

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register an async or sync handler for an event type."""
        if event_type not in self.message_handlers:
            self.message_handlers[event_type] = []
        if handler not in self.message_handlers[event_type]:
            self.message_handlers[event_type].append(handler)
        logger.info("comm_controller.handler_registered", event_type=event_type)

    def unregister_handler(self, event_type: str, handler: Callable) -> None:
        """Remove a handler for an event type."""
        if event_type in self.message_handlers:
            try:
                self.message_handlers[event_type].remove(handler)
            except ValueError:
                pass

    # ─── Routing ──────────────────────────────────────────────────────────────

    async def broadcast_message(self, message: Dict) -> None:
        """Broadcast a message to all active topics."""
        for topic in sorted(self.active_topics):
            await self.send_message(topic, message)

    async def route_message(self, message: Dict, target_agent: str) -> bool:
        """
        Route a message to a specific agent topic.
        Also dispatches to any registered handlers for that agent topic.
        """
        topic = f"agent.{target_agent}"
        self.active_topics.add(topic)

        # Dispatch to registered handlers for this target
        for handler in list(self.message_handlers.get(topic, [])):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
                self.metrics["routed"] += 1
            except Exception as exc:
                logger.error(
                    "comm_controller.route_handler_error",
                    target_agent=target_agent,
                    error=str(exc),
                )

        return await self.send_message(topic, message)

    # ─── History & Status ─────────────────────────────────────────────────────

    async def get_message_history(self, topic: str, limit: int = 100) -> List[Dict]:
        """
        Get recent event history from the in-memory ring buffer.
        FIXED: was always returning empty list.
        """
        history = [
            e for e in self._event_history
            if e.get("type") == topic or e.get("data", {}).get("topic") == topic
        ]
        return list(history)[-limit:]

    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the communication controller."""
        return {
            "status": "running" if self.is_running else "stopped",
            "initialized": self._initialized,   # ← FIXED: now correctly True after start()
            "kafka": {
                "producer": "connected" if self.producer else "disconnected",
                "consumer": "connected" if self.consumer else "disconnected",
            },
            "redis": "connected" if self.redis_client else "disconnected",
            "http": "connected" if self.http_session else "disconnected",
            "queues": {
                "message_queue_size": self.message_queue.qsize(),
                "event_queue_size": self.event_queue.qsize(),
                "message_queue_maxsize": self.message_queue.maxsize,
                "event_queue_maxsize": self.event_queue.maxsize,
            },
            "processing": {
                "process_task_running": self._process_task is not None and not self._process_task.done(),
                "dispatch_task_running": self._dispatch_task is not None and not self._dispatch_task.done(),
            },
            "recovery": {
                "ready": self.is_running,
                "active_topics": sorted(self.active_topics),
            },
            "event_history_size": len(self._event_history),
            "registered_handlers": {k: len(v) for k, v in self.message_handlers.items()},
            "metrics": dict(self.metrics),
        }