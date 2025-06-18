import asyncio
import logging
from typing import Dict, Any, Optional, List
import json
from datetime import datetime
import uuid
from dataclasses import dataclass, asdict

from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

@dataclass
class Event:
    """Event data class."""
    event_id: str
    event_type: str
    source: str
    data: Dict[str, Any]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class EventProducer:
    """Produces events to the message bus."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the event producer with configuration."""
        self.config = config
        self.is_running = False
        
        # Initialize Kafka producer
        self.producer = None
        
        # Initialize event queue
        self.event_queue = asyncio.Queue()
        
        # Initialize metrics
        self.metrics = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "average_latency": 0.0
        }
    
    async def start(self):
        """Start the event producer."""
        logger.info("Starting event producer...")
        
        try:
            # Initialize Kafka producer
            self.producer = KafkaProducer(
                bootstrap_servers=self.config["kafka"]["bootstrap_servers"],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks=self.config["kafka"].get("acks", "all"),
                retries=self.config["kafka"].get("retries", 3),
                max_in_flight_requests_per_connection=self.config["kafka"].get("max_in_flight", 5)
            )
            
            self.is_running = True
            
            # Start event processing loop
            asyncio.create_task(self._process_events())
            
            logger.info("Event producer started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start event producer: {e}")
            raise
    
    async def stop(self):
        """Stop the event producer."""
        logger.info("Stopping event producer...")
        self.is_running = False
        
        if self.producer:
            self.producer.close()
        
        logger.info("Event producer stopped successfully")
    
    async def publish_event(self, event_type: str, data: Dict[str, Any], 
                          source: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Publish an event to the message bus."""
        event_id = str(uuid.uuid4())
        
        event = Event(
            event_id=event_id,
            event_type=event_type,
            source=source,
            data=data,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        
        # Add to queue
        await self.event_queue.put(event)
        
        logger.info(f"Event {event_id} queued for publishing")
        return event_id
    
    async def _process_events(self):
        """Process events from the queue."""
        while self.is_running:
            try:
                # Get event from queue
                event = await self.event_queue.get()
                
                # Publish event
                success = await self._publish_to_kafka(event)
                
                # Update metrics
                self._update_metrics(success, event.timestamp)
                
                # Mark event as processed
                self.event_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                await asyncio.sleep(1)
    
    async def _publish_to_kafka(self, event: Event) -> bool:
        """Publish event to Kafka."""
        try:
            # Prepare message
            message = asdict(event)
            
            # Get topic
            topic = self._get_topic_for_event(event.event_type)
            
            # Send message
            future = self.producer.send(
                topic,
                value=message,
                key=event.event_id.encode('utf-8')
            )
            
            # Wait for send to complete
            await asyncio.get_event_loop().run_in_executor(
                None, future.get
            )
            
            logger.debug(f"Published event {event.event_id} to topic {topic}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            return False
    
    def _get_topic_for_event(self, event_type: str) -> str:
        """Get Kafka topic for event type."""
        # Map event types to topics
        topic_mapping = self.config.get("topic_mapping", {})
        return topic_mapping.get(event_type, "default_events")
    
    def _update_metrics(self, success: bool, start_time: datetime):
        """Update event metrics."""
        self.metrics["total_events"] += 1
        
        if success:
            self.metrics["successful_events"] += 1
        else:
            self.metrics["failed_events"] += 1
        
        # Update average latency
        latency = (datetime.utcnow() - start_time).total_seconds()
        self.metrics["average_latency"] = (
            (self.metrics["average_latency"] * (self.metrics["successful_events"] - 1) +
             latency) / self.metrics["successful_events"]
        )
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the event producer."""
        return {
            "status": "running" if self.is_running else "stopped",
            "metrics": self.metrics,
            "queue_size": self.event_queue.qsize(),
            "kafka_connected": self.producer is not None
        }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get event metrics."""
        return self.metrics
    
    async def clear_metrics(self):
        """Clear event metrics."""
        self.metrics = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "average_latency": 0.0
        }
        logger.info("Event metrics cleared") 