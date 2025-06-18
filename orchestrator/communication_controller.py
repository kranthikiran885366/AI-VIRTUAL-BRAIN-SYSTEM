import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime

import aiokafka
from structlog import get_logger
import aiohttp
import redis

from .config import settings

logger = get_logger()

class CommunicationController:
    """Manages communication between system components."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the communication controller with configuration."""
        self.config = config
        self.is_running = False
        
        # Initialize message queues
        self.message_queue = asyncio.Queue()
        self.event_queue = asyncio.Queue()
        
        # Initialize Kafka producer and consumer
        self.kafka_producer = None
        self.kafka_consumer = None
        
        # Initialize Redis client
        self.redis_client = None
        
        # Initialize HTTP session
        self.http_session = None
        
        self.producer: Optional[aiokafka.AIOKafkaProducer] = None
        self.consumer: Optional[aiokafka.AIOKafkaConsumer] = None
        self.active_topics: Set[str] = set()
        self.message_handlers: Dict[str, List[callable]] = {}
        self._process_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def start(self):
        """Start the communication controller."""
        logger.info("Starting communication controller...")
        self.is_running = True
        
        # Initialize Kafka
        await self._init_kafka()
        
        # Initialize Redis
        await self._init_redis()
        
        # Initialize HTTP session
        self.http_session = aiohttp.ClientSession()
        
        logger.info("Communication controller started successfully")
    
    async def stop(self):
        """Stop the communication controller."""
        logger.info("Stopping communication controller...")
        self.is_running = False
        
        # Close Kafka connections
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        # Close HTTP session
        if self.http_session:
            await self.http_session.close()
        
        logger.info("Communication controller stopped successfully")
    
    async def _init_kafka(self):
        """Initialize Kafka connections."""
        try:
            # Initialize producer
            self.producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=self.config["kafka"]["bootstrap_servers"],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await self.producer.start()
            
            # Initialize consumer
            self.consumer = aiokafka.AIOKafkaConsumer(
                bootstrap_servers=self.config["kafka"]["bootstrap_servers"],
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                group_id=self.config["kafka"]["consumer_group"]
            )
            await self.consumer.start()
            
            # Subscribe to topics
            for topic in self.config["kafka"]["topics"]:
                self.active_topics.add(topic)
            
            logger.info("Kafka connections initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kafka: {e}")
            raise
    
    async def _init_redis(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.Redis(
                host=self.config["redis"]["host"],
                port=self.config["redis"]["port"],
                db=self.config["redis"]["db"]
            )
            logger.info("Redis connection initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise
    
    async def send_message(self, topic: str, message: Dict[str, Any]) -> bool:
        """Send a message to a Kafka topic."""
        try:
            # Add timestamp
            message["timestamp"] = datetime.utcnow().isoformat()
            
            # Send to Kafka
            await self.producer.send_and_wait(topic, message)
            
            # Store in Redis for persistence
            await self.redis_client.set(
                f"message:{message.get('id', 'unknown')}",
                json.dumps(message)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    async def receive_message(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Receive a message from Kafka."""
        try:
            # Get message from Kafka
            message = await self.consumer.getone()
            if message:
                return message.value
            return None
            
        except Exception as e:
            logger.error(f"Failed to receive message: {e}")
            return None
    
    async def broadcast_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Broadcast an event to all components."""
        try:
            event = {
                "type": event_type,
                "data": event_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send to event queue
            await self.event_queue.put(event)
            
            # Broadcast to Kafka
            await self.send_message("events", event)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to broadcast event: {e}")
            return False
    
    async def process_messages(self):
        """Process incoming messages."""
        while self.is_running:
            try:
                # Get message from queue
                message = await self.message_queue.get()
                
                # Process message
                await self._handle_message(message)
                
                # Mark task as done
                self.message_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle an incoming message."""
        try:
            message_type = message.get("type")
            
            if message_type == "task":
                # Handle task message
                await self._handle_task_message(message)
            elif message_type == "event":
                # Handle event message
                await self._handle_event_message(message)
            elif message_type == "status":
                # Handle status message
                await self._handle_status_message(message)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_task_message(self, message: Dict[str, Any]):
        """Handle a task message."""
        # This is a placeholder - implement actual task handling
        logger.info(f"Handling task message: {message}")
    
    async def _handle_event_message(self, message: Dict[str, Any]):
        """Handle an event message."""
        # This is a placeholder - implement actual event handling
        logger.info(f"Handling event message: {message}")
    
    async def _handle_status_message(self, message: Dict[str, Any]):
        """Handle a status message."""
        # This is a placeholder - implement actual status handling
        logger.info(f"Handling status message: {message}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the communication controller."""
        return {
            "status": "running" if self.is_running else "stopped",
            "kafka": {
                "producer": "connected" if self.producer else "disconnected",
                "consumer": "connected" if self.consumer else "disconnected"
            },
            "redis": "connected" if self.redis_client else "disconnected",
            "http": "connected" if self.http_session else "disconnected",
            "queues": {
                "message_queue_size": self.message_queue.qsize(),
                "event_queue_size": self.event_queue.qsize()
            }
        }
    
    async def broadcast_message(self, message: Dict):
        """Broadcast a message to all active topics."""
        for topic in self.active_topics:
            await self.send_message(topic, message)
    
    async def route_message(self, message: Dict, target_agent: str):
        """Route a message to a specific agent."""
        topic = f"agent.{target_agent}"
        await self.send_message(topic, message)
    
    async def get_message_history(self, topic: str, limit: int = 100) -> List[Dict]:
        """Get message history for a topic."""
        # Here you would typically implement message history retrieval
        # For now, we'll return an empty list
        return [] 