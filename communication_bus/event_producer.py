import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional

try:
    import aiokafka
    _AIOKAFKA_AVAILABLE = True
except ImportError:
    aiokafka = None  # type: ignore
    _AIOKAFKA_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class Event:
    event_id: str
    event_type: str
    source: str
    data: Dict[str, Any]
    timestamp: str  # ISO string — safe for JSON serialization
    metadata: Optional[Dict[str, Any]] = None


class EventProducer:
    """Async event producer. Uses aiokafka when available; falls back to no-op."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.is_running = False
        self.producer: Optional[Any] = None
        # Bounded queue — prevents unbounded memory growth under backpressure
        maxsize = int(self.config.get("queue_maxsize", 10_000))
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._process_task: Optional[asyncio.Task] = None
        self.metrics = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "average_latency": 0.0,
        }

    async def start(self) -> None:
        if self.is_running:
            return
        logger.info("event_producer.starting")
        kafka_cfg = self.config.get("kafka", {})
        if kafka_cfg.get("enabled", False) and _AIOKAFKA_AVAILABLE:
            servers = kafka_cfg.get("bootstrap_servers", ["localhost:9092"])
            try:
                self.producer = aiokafka.AIOKafkaProducer(
                    bootstrap_servers=servers,
                    value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                    acks=kafka_cfg.get("acks", "all"),
                    request_timeout_ms=10_000,
                )
                await self.producer.start()
                logger.info("event_producer.kafka_connected")
            except Exception as exc:
                logger.warning("event_producer.kafka_init_failed", error=str(exc))
                self.producer = None

        self.is_running = True
        # Store task reference — prevents GC on Python 3.11+
        self._process_task = asyncio.create_task(
            self._process_events(), name="event_producer.process"
        )
        logger.info("event_producer.started")

    async def stop(self) -> None:
        if not self.is_running:
            return
        logger.info("event_producer.stopping")
        self.is_running = False
        if self._process_task and not self._process_task.done():
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        if self.producer:
            try:
                await self.producer.stop()
            except Exception:
                pass
        logger.info("event_producer.stopped")

    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        event = Event(
            event_id=event_id,
            event_type=event_type,
            source=source,
            data=data,
            timestamp=datetime.utcnow().isoformat(),
            metadata=metadata,
        )
        try:
            self.event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("event_producer.queue_full", event_type=event_type)
            self.metrics["failed_events"] += 1
        return event_id

    async def _process_events(self) -> None:
        while self.is_running:
            try:
                event = await asyncio.wait_for(self.event_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                success = await self._publish_to_kafka(event)
                self._update_metrics(success, event.timestamp)
            except Exception as exc:
                logger.error("event_producer.process_error", error=str(exc))
                self.metrics["failed_events"] += 1
            finally:
                self.event_queue.task_done()

    async def _publish_to_kafka(self, event: Event) -> bool:
        if not self.producer:
            return True  # no-op when Kafka is not configured
        try:
            topic = self.config.get("topic_mapping", {}).get(event.event_type, "default_events")
            await self.producer.send_and_wait(
                topic,
                value=asdict(event),
                key=event.event_id.encode("utf-8"),
            )
            return True
        except Exception as exc:
            logger.error("event_producer.kafka_send_failed", event_id=event.event_id, error=str(exc))
            return False

    def _update_metrics(self, success: bool, start_iso: str) -> None:
        self.metrics["total_events"] += 1
        if success:
            n = self.metrics["successful_events"] + 1
            self.metrics["successful_events"] = n
            try:
                start_dt = datetime.fromisoformat(start_iso)
                latency = (datetime.utcnow() - start_dt).total_seconds()
                # Running average — no division by zero
                self.metrics["average_latency"] = (
                    (self.metrics["average_latency"] * (n - 1) + latency) / n
                )
            except Exception:
                pass
        else:
            self.metrics["failed_events"] += 1

    async def get_status(self) -> Dict[str, Any]:
        return {
            "status": "running" if self.is_running else "stopped",
            "metrics": self.metrics,
            "queue_size": self.event_queue.qsize(),
            "kafka_connected": self.producer is not None,
        }

    async def get_metrics(self) -> Dict[str, Any]:
        return dict(self.metrics)

    async def clear_metrics(self) -> None:
        self.metrics = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "average_latency": 0.0,
        }
