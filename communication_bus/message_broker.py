import asyncio
import json
import logging
from typing import Dict, List, Optional, Set, Any, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass, asdict

import aiokafka
from structlog import get_logger
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import redis

from .config import settings

logger = get_logger()

@dataclass
class Message:
    """Message data class."""
    message_id: str
    topic: str
    sender: str
    recipient: Optional[str]
    content: Dict[str, Any]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class MessageBroker:
    """Handles message routing and delivery."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the message broker with configuration."""
        self.config = config
        self.is_running = False
        
        # Initialize Kafka producer and consumer
        self.producer = None
        self.consumer = None
        
        # Initialize Redis client
        self.redis_client = None
        
        # Initialize message handlers
        self.message_handlers: Dict[str, List[Callable[[Message], Awaitable[None]]]] = {}
        
        # Initialize message queue
        self.message_queue = asyncio.Queue()
        
        # Initialize metrics
        self.metrics = {
            "total_messages": 0,
            "delivered_messages": 0,
            "failed_messages": 0,
            "average_delivery_time": 0.0
        }
    
    async def start(self):
        """Start the message broker."""
        logger.info("Starting message broker...")
        
        try:
            # Initialize Kafka producer
            self.producer = KafkaProducer(
                bootstrap_servers=self.config["kafka"]["bootstrap_servers"],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
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
            
            # Initialize Redis client
            self.redis_client = redis.Redis(
                host=self.config["redis"]["host"],
                port=self.config["redis"]["port"],
                db=self.config["redis"].get("db", 0),
                decode_responses=True
            )
            
            self.is_running = True
            
            # Start message processing loop
            asyncio.create_task(self._process_messages())
            
            logger.info("Message broker started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start message broker: {e}")
            raise
    
    async def stop(self):
        """Stop the message broker."""
        logger.info("Stopping message broker...")
        self.is_running = False
        
        if self.producer:
            self.producer.close()
        
        if self.consumer:
            self.consumer.close()
        
        if self.redis_client:
            self.redis_client.close()
        
        logger.info("Message broker stopped successfully")
    
    def register_handler(self, topic: str, handler: Callable[[Message], Awaitable[None]]):
        """Register a message handler."""
        if topic not in self.message_handlers:
            self.message_handlers[topic] = []
        
        self.message_handlers[topic].append(handler)
        logger.info(f"Registered handler for topic: {topic}")
    
    def unregister_handler(self, topic: str, handler: Callable[[Message], Awaitable[None]]):
        """Unregister a message handler."""
        if topic in self.message_handlers:
            self.message_handlers[topic].remove(handler)
            logger.info(f"Unregistered handler for topic: {topic}")
    
    async def send_message(self, message: Message):
        """Send a message to a topic."""
        try:
            # Add message to queue
            await self.message_queue.put(message)
            
            # Update metrics
            self.metrics["total_messages"] += 1
            
            logger.info(f"Message {message.message_id} queued for delivery")
            
        except Exception as e:
            logger.error(f"Error queuing message {message.message_id}: {e}")
            self.metrics["failed_messages"] += 1
            raise
    
    async def _process_messages(self):
        """Process messages from the queue."""
        while self.is_running:
            try:
                # Get message from queue
                message = await self.message_queue.get()
                
                try:
                    # Send message to Kafka
                    future = self.producer.send(
                        message.topic,
                        value=asdict(message)
                    )
                    future.get(timeout=self.config["kafka"].get("send_timeout", 10))
                    
                    # Store message in Redis for persistence
                    self.redis_client.setex(
                        f"message:{message.message_id}",
                        self.config["redis"].get("message_ttl", 86400),
                        json.dumps(asdict(message))
                    )
                    
                    # Update metrics
                    self.metrics["delivered_messages"] += 1
                    
                    logger.info(f"Message {message.message_id} delivered successfully")
                    
                except Exception as e:
                    logger.error(f"Error delivering message {message.message_id}: {e}")
                    self.metrics["failed_messages"] += 1
                
                finally:
                    self.message_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in message processing loop: {e}")
                await asyncio.sleep(1)
    
    async def _handle_message(self, message: Message):
        """Handle a message by calling registered handlers."""
        start_time = datetime.utcnow()
        
        try:
            # Get handlers for topic
            handlers = self.message_handlers.get(message.topic, [])
            
            if not handlers:
                logger.warning(f"No handlers registered for topic: {message.topic}")
                return
            
            # Call handlers
            for handler in handlers:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Error in message handler: {e}")
            
            # Update metrics
            delivery_time = (datetime.utcnow() - start_time).total_seconds()
            self.metrics["average_delivery_time"] = (
                (self.metrics["average_delivery_time"] * (self.metrics["delivered_messages"] - 1) +
                 delivery_time) / self.metrics["delivered_messages"]
            )
            
        except Exception as e:
            logger.error(f"Error handling message {message.message_id}: {e}")
            self.metrics["failed_messages"] += 1
    
    async def get_message(self, message_id: str) -> Optional[Message]:
        """Get a message from Redis."""
        try:
            message_data = self.redis_client.get(f"message:{message_id}")
            if message_data:
                data = json.loads(message_data)
                return Message(
                    message_id=data["message_id"],
                    topic=data["topic"],
                    sender=data["sender"],
                    recipient=data["recipient"],
                    content=data["content"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    metadata=data.get("metadata")
                )
            return None
            
        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            return None
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the message broker."""
        return {
            "status": "running" if self.is_running else "stopped",
            "metrics": self.metrics,
            "registered_handlers": {
                topic: len(handlers)
                for topic, handlers in self.message_handlers.items()
            },
            "kafka_connected": self.producer is not None and self.consumer is not None,
            "redis_connected": self.redis_client is not None,
            "queue_size": self.message_queue.qsize()
        }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get message metrics."""
        return self.metrics
    
    async def clear_metrics(self):
        """Clear message metrics."""
        self.metrics = {
            "total_messages": 0,
            "delivered_messages": 0,
            "failed_messages": 0,
            "average_delivery_time": 0.0
        }
        logger.info("Message metrics cleared")

    async def initialize(self):
        """Initialize the message broker."""
        if self._initialized:
            return
        
        logger.info("Initializing message broker...")
        
        try:
            # Initialize Kafka producer
            self.producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                compression_type='gzip',
                max_batch_size=16384,
                linger_ms=5,
                retries=3
            )
            await self.producer.start()
            
            # Initialize consumers for each topic
            for topic in settings.KAFKA_TOPICS:
                await self._create_consumer(topic)
            
            self._initialized = True
            logger.info("Message broker initialized")
        except Exception as e:
            logger.error(f"Failed to initialize message broker: {str(e)}")
            raise
    
    async def shutdown(self):
        """Shutdown the message broker."""
        logger.info("Shutting down message broker...")
        
        # Cancel processing task
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        
        # Close Kafka connections
        if self.producer:
            await self.producer.stop()
        
        for consumer in self.consumers.values():
            await consumer.stop()
        
        self._initialized = False
        logger.info("Message broker shut down")
    
    async def _create_consumer(self, topic: str):
        """Create a consumer for a topic."""
        try:
            consumer = aiokafka.AIOKafkaConsumer(
                topic,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                group_id=settings.KAFKA_GROUP_ID,
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                auto_commit_interval_ms=5000
            )
            await consumer.start()
            self.consumers[topic] = consumer
            self.active_topics.add(topic)
            logger.info(f"Created consumer for topic {topic}")
        except Exception as e:
            logger.error(f"Failed to create consumer for topic {topic}: {str(e)}")
            raise
    
    async def publish_message(self, topic: str, message: Dict) -> bool:
        """Publish a message to a topic."""
        if not self._initialized:
            raise RuntimeError("Message broker not initialized")
        
        try:
            # Add metadata to message
            message_with_metadata = {
                **message,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "communication_bus"
            }
            
            # Send message
            await self.producer.send_and_wait(topic, message_with_metadata)
            logger.debug(f"Published message to topic {topic}: {message_with_metadata}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message to topic {topic}: {str(e)}")
            return False
    
    async def get_messages(self, topic: str, limit: int = 100) -> List[Dict]:
        """Get messages from a topic."""
        if not self._initialized:
            raise RuntimeError("Message broker not initialized")
        
        if topic not in self.consumers:
            raise ValueError(f"No consumer for topic {topic}")
        
        messages = []
        try:
            # Get messages from consumer
            async for message in self.consumers[topic]:
                messages.append(message.value)
                if len(messages) >= limit:
                    break
        except Exception as e:
            logger.error(f"Error getting messages from topic {topic}: {str(e)}")
        
        return messages
    
    async def subscribe_to_topic(self, topic: str, handler: callable):
        """Subscribe to a topic with a message handler."""
        if topic not in self.message_handlers:
            self.message_handlers[topic] = []
        self.message_handlers[topic].append(handler)
        logger.info(f"Subscribed to topic {topic}")
    
    async def unsubscribe_from_topic(self, topic: str, handler: callable):
        """Unsubscribe from a topic."""
        if topic in self.message_handlers:
            self.message_handlers[topic].remove(handler)
            if not self.message_handlers[topic]:
                del self.message_handlers[topic]
            logger.info(f"Unsubscribed from topic {topic}")
    
    async def process_messages(self):
        """Process incoming messages."""
        if not self._initialized:
            raise RuntimeError("Message broker not initialized")
        
        while True:
            try:
                # Process messages from each consumer
                for topic, consumer in self.consumers.items():
                    try:
                        # Get message from consumer
                        message = await consumer.getone()
                        
                        # Process message
                        value = message.value
                        
                        # Call handlers for this topic
                        if topic in self.message_handlers:
                            for handler in self.message_handlers[topic]:
                                try:
                                    await handler(value)
                                except Exception as e:
                                    logger.error(f"Error in message handler for topic {topic}: {str(e)}")
                        
                        logger.debug(f"Processed message from topic {topic}: {value}")
                    except Exception as e:
                        logger.error(f"Error processing message from topic {topic}: {str(e)}")
                        continue
                
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message processing loop: {str(e)}")
                await asyncio.sleep(1)
    
    async def broadcast_message(self, message: Dict):
        """Broadcast a message to all active topics."""
        for topic in self.active_topics:
            await self.publish_message(topic, message)
    
    async def route_message(self, message: Dict, target_topic: str):
        """Route a message to a specific topic."""
        await self.publish_message(target_topic, message) 