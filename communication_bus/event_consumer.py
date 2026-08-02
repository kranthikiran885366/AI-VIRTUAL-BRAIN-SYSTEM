import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

try:
    import aiokafka
    _AIOKAFKA_AVAILABLE = True
except ImportError:
    aiokafka = None  # type: ignore
    _AIOKAFKA_AVAILABLE = False

logger = logging.getLogger(__name__)


class EventConsumer:
    """Async event consumer. Uses aiokafka when available; falls back to no-op."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.is_running = False
        self.consumer: Optional[Any] = None
        self.event_handlers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}
        self._process_task: Optional[asyncio.Task] = None
        self.metrics = {
            "total_events": 0,
            "processed_events": 0,
            "failed_events": 0,
            "average_processing_time": 0.0,
        }

    async def start(self) -> None:
        if self.is_running:
            return
        logger.info("event_consumer.starting")
        kafka_cfg = self.config.get("kafka", {})
        if kafka_cfg.get("enabled", False) and _AIOKAFKA_AVAILABLE:
            servers = kafka_cfg.get("bootstrap_servers", ["localhost:9092"])
            topics = kafka_cfg.get("topics", [])
            try:
                self.consumer = aiokafka.AIOKafkaConsumer(
                    *topics,
                    bootstrap_servers=servers,
                    group_id=kafka_cfg.get("group_id", "event-consumer"),
                    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                    auto_offset_reset=kafka_cfg.get("auto_offset_reset", "latest"),
                    enable_auto_commit=kafka_cfg.get("enable_auto_commit", True),
                    auto_commit_interval_ms=kafka_cfg.get("auto_commit_interval_ms", 5000),
                )
                await self.consumer.start()
                logger.info("event_consumer.kafka_connected", topics=topics)
            except Exception as exc:
                logger.warning("event_consumer.kafka_init_failed", error=str(exc))
                self.consumer = None

        self.is_running = True
        # Store task reference — prevents GC on Python 3.11+
        self._process_task = asyncio.create_task(
            self._process_events(), name="event_consumer.process"
        )
        logger.info("event_consumer.started")

    async def stop(self) -> None:
        if not self.is_running:
            return
        logger.info("event_consumer.stopping")
        self.is_running = False
        if self._process_task and not self._process_task.done():
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        if self.consumer:
            try:
                await self.consumer.stop()
            except Exception:
                pass
        logger.info("event_consumer.stopped")

    def register_handler(
        self, event_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.info("event_consumer.handler_registered", event_type=event_type)

    def unregister_handler(
        self, event_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
            except ValueError:
                pass

    async def _process_events(self) -> None:
        """Consume from Kafka when available; otherwise idle until stopped."""
        if not self.consumer:
            # No Kafka — just wait until stopped
            while self.is_running:
                await asyncio.sleep(0.1)
            return

        while self.is_running:
            try:
                msg = await asyncio.wait_for(self.consumer.getone(), timeout=0.5)
                event_data = msg.value
                if isinstance(event_data, dict):
                    await self._handle_event(event_data)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("event_consumer.process_error", error=str(exc))
                await asyncio.sleep(1)

    async def _handle_event(self, event_data: Dict[str, Any]) -> None:
        start = datetime.utcnow()
        event_type = event_data.get("event_type", "")
        handlers = self.event_handlers.get(event_type, [])
        if not handlers:
            logger.debug("event_consumer.no_handlers", event_type=event_type)
            return
        self.metrics["total_events"] += 1
        try:
            for handler in handlers:
                try:
                    await handler(event_data)
                except Exception as exc:
                    logger.error("event_consumer.handler_error", event_type=event_type, error=str(exc))
            n = self.metrics["processed_events"] + 1
            self.metrics["processed_events"] = n
            elapsed = (datetime.utcnow() - start).total_seconds()
            self.metrics["average_processing_time"] = (
                (self.metrics["average_processing_time"] * (n - 1) + elapsed) / n
            )
        except Exception as exc:
            logger.error("event_consumer.handle_error", error=str(exc))
            self.metrics["failed_events"] += 1

    async def get_status(self) -> Dict[str, Any]:
        return {
            "status": "running" if self.is_running else "stopped",
            "metrics": self.metrics,
            "registered_handlers": {
                et: len(hs) for et, hs in self.event_handlers.items()
            },
            "kafka_connected": self.consumer is not None,
        }

    async def get_metrics(self) -> Dict[str, Any]:
        return dict(self.metrics)

    async def clear_metrics(self) -> None:
        self.metrics = {
            "total_events": 0,
            "processed_events": 0,
            "failed_events": 0,
            "average_processing_time": 0.0,
        }


@dataclass
class Event:
    """Event data class."""
    event_id: str
    event_type: str
    source: str
    data: Dict[str, Any]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class EventConsumer:
    """Consumes events from the message bus."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the event consumer with configuration."""
        self.config = config
        self.is_running = False
        
        # Initialize Kafka consumer
        self.consumer = None
        
        # Initialize event handlers
        self.event_handlers: Dict[str, List[Callable[[Event], Awaitable[None]]]] = {}
        
        # Initialize metrics
        self.metrics = {
            "total_events": 0,
            "processed_events": 0,
            "failed_events": 0,
            "average_processing_time": 0.0
        }
    
    async def start(self):
        """Start the event consumer."""
        logger.info("Starting event consumer...")
        
        try:
            # Initialize Kafka consumer
            self.consumer = KafkaConsumer(
                *self.config["kafka"]["topics"],
                bootstrap_servers=self.config["kafka"]["bootstrap_servers"],
                group_id=self.config["kafka"]["group_id"],
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                auto_offset_reset=self.config["kafka"].get("auto_offset_reset", "latest"),
                enable_auto_commit=self.config["kafka"].get("enable_auto_commit", True),
                auto_commit_interval_ms=self.config["kafka"].get("auto_commit_interval_ms", 5000)
            )
            
            self.is_running = True
            
            # Start event processing loop
            asyncio.create_task(self._process_events())
            
            logger.info("Event consumer started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start event consumer: {e}")
            raise
    
    async def stop(self):
        """Stop the event consumer."""
        logger.info("Stopping event consumer...")
        self.is_running = False
        
        if self.consumer:
            self.consumer.close()
        
        logger.info("Event consumer stopped successfully")
    
    def register_handler(self, event_type: str, handler: Callable[[Event], Awaitable[None]]):
        """Register an event handler."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered handler for event type: {event_type}")
    
    def unregister_handler(self, event_type: str, handler: Callable[[Event], Awaitable[None]]):
        """Unregister an event handler."""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].remove(handler)
            logger.info(f"Unregistered handler for event type: {event_type}")
    
    async def _process_events(self):
        """Process events from Kafka."""
        while self.is_running:
            try:
                # Get messages from Kafka
                messages = self.consumer.poll(
                    timeout_ms=self.config["kafka"].get("poll_timeout_ms", 1000),
                    max_records=self.config["kafka"].get("max_records", 100)
                )
                
                for topic_partition, msgs in messages.items():
                    for msg in msgs:
                        try:
                            # Parse event
                            event_data = msg.value
                            event = Event(
                                event_id=event_data["event_id"],
                                event_type=event_data["event_type"],
                                source=event_data["source"],
                                data=event_data["data"],
                                timestamp=datetime.fromisoformat(event_data["timestamp"]),
                                metadata=event_data.get("metadata")
                            )
                            
                            # Process event
                            await self._handle_event(event)
                            
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            self.metrics["failed_events"] += 1
                
            except KafkaError as e:
                logger.error(f"Kafka error: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in event processing loop: {e}")
                await asyncio.sleep(1)
    
    async def _handle_event(self, event: Event):
        """Handle an event by calling registered handlers."""
        start_time = datetime.utcnow()
        
        try:
            # Get handlers for event type
            handlers = self.event_handlers.get(event.event_type, [])
            
            if not handlers:
                logger.warning(f"No handlers registered for event type: {event.event_type}")
                return
            
            # Call handlers
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")
            
            # Update metrics
            self.metrics["processed_events"] += 1
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.metrics["average_processing_time"] = (
                (self.metrics["average_processing_time"] * (self.metrics["processed_events"] - 1) +
                 processing_time) / self.metrics["processed_events"]
            )
            
        except Exception as e:
            logger.error(f"Error handling event {event.event_id}: {e}")
            self.metrics["failed_events"] += 1
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the event consumer."""
        return {
            "status": "running" if self.is_running else "stopped",
            "metrics": self.metrics,
            "registered_handlers": {
                event_type: len(handlers)
                for event_type, handlers in self.event_handlers.items()
            },
            "kafka_connected": self.consumer is not None
        }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get event metrics."""
        return self.metrics
    
    async def clear_metrics(self):
        """Clear event metrics."""
        self.metrics = {
            "total_events": 0,
            "processed_events": 0,
            "failed_events": 0,
            "average_processing_time": 0.0
        }
        logger.info("Event metrics cleared") 