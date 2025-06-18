import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

from structlog import get_logger

from .config import settings

logger = get_logger()

class MessageProcessor:
    """Processes and transforms messages in the communication bus."""
    
    def __init__(self):
        """Initialize the message processor."""
        self.processors: Dict[str, List[Callable]] = {}
        self.transformers: Dict[str, List[Callable]] = {}
        self.validators: Dict[str, List[Callable]] = {}
        self._process_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the message processor."""
        if self._initialized:
            return
        
        logger.info("Initializing message processor...")
        
        try:
            # Register default processors
            self._register_default_processors()
            
            # Start processing task
            self._process_task = asyncio.create_task(self._process_messages())
            
            self._initialized = True
            logger.info("Message processor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize message processor: {str(e)}")
            raise
    
    async def shutdown(self):
        """Shutdown the message processor."""
        logger.info("Shutting down message processor...")
        
        # Cancel processing task
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        
        self._initialized = False
        logger.info("Message processor shut down")
    
    def _register_default_processors(self):
        """Register default message processors."""
        # Register message validation
        self.register_validator("agent-communication", self._validate_agent_message)
        self.register_validator("system-events", self._validate_system_event)
        self.register_validator("health-metrics", self._validate_health_metric)
        self.register_validator("task-updates", self._validate_task_update)
        
        # Register message transformation
        self.register_transformer("agent-communication", self._transform_agent_message)
        self.register_transformer("system-events", self._transform_system_event)
        self.register_transformer("health-metrics", self._transform_health_metric)
        self.register_transformer("task-updates", self._transform_task_update)
        
        # Register message processing
        self.register_processor("agent-communication", self._process_agent_message)
        self.register_processor("system-events", self._process_system_event)
        self.register_processor("health-metrics", self._process_health_metric)
        self.register_processor("task-updates", self._process_task_update)
    
    def register_processor(self, topic: str, processor: Callable):
        """Register a message processor for a topic."""
        if topic not in self.processors:
            self.processors[topic] = []
        self.processors[topic].append(processor)
    
    def register_transformer(self, topic: str, transformer: Callable):
        """Register a message transformer for a topic."""
        if topic not in self.transformers:
            self.transformers[topic] = []
        self.transformers[topic].append(transformer)
    
    def register_validator(self, topic: str, validator: Callable):
        """Register a message validator for a topic."""
        if topic not in self.validators:
            self.validators[topic] = []
        self.validators[topic].append(validator)
    
    async def process_message(self, topic: str, message: Dict) -> Optional[Dict]:
        """Process a message for a specific topic."""
        if not self._initialized:
            raise RuntimeError("Message processor not initialized")
        
        try:
            # Validate message
            if not await self._validate_message(topic, message):
                logger.warning(f"Message validation failed for topic {topic}")
                return None
            
            # Transform message
            transformed_message = await self._transform_message(topic, message)
            if not transformed_message:
                logger.warning(f"Message transformation failed for topic {topic}")
                return None
            
            # Process message
            processed_message = await self._apply_processors(topic, transformed_message)
            if not processed_message:
                logger.warning(f"Message processing failed for topic {topic}")
                return None
            
            return processed_message
        except Exception as e:
            logger.error(f"Error processing message for topic {topic}: {str(e)}")
            return None
    
    async def _validate_message(self, topic: str, message: Dict) -> bool:
        """Validate a message using registered validators."""
        if topic not in self.validators:
            return True
        
        for validator in self.validators[topic]:
            try:
                if not await validator(message):
                    return False
            except Exception as e:
                logger.error(f"Validator error for topic {topic}: {str(e)}")
                return False
        
        return True
    
    async def _transform_message(self, topic: str, message: Dict) -> Optional[Dict]:
        """Transform a message using registered transformers."""
        if topic not in self.transformers:
            return message
        
        transformed = message.copy()
        for transformer in self.transformers[topic]:
            try:
                transformed = await transformer(transformed)
                if not transformed:
                    return None
            except Exception as e:
                logger.error(f"Transformer error for topic {topic}: {str(e)}")
                return None
        
        return transformed
    
    async def _apply_processors(self, topic: str, message: Dict) -> Optional[Dict]:
        """Apply registered processors to a message."""
        if topic not in self.processors:
            return message
        
        processed = message.copy()
        for processor in self.processors[topic]:
            try:
                processed = await processor(processed)
                if not processed:
                    return None
            except Exception as e:
                logger.error(f"Processor error for topic {topic}: {str(e)}")
                return None
        
        return processed
    
    async def _process_messages(self):
        """Background task for processing messages."""
        while True:
            try:
                # Here you would typically implement message processing tasks
                # For example, batch processing, cleanup, etc.
                
                await asyncio.sleep(settings.MESSAGE_PROCESSING_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message processing: {str(e)}")
                await asyncio.sleep(1)
    
    # Default validators
    async def _validate_agent_message(self, message: Dict) -> bool:
        """Validate an agent communication message."""
        required_fields = ["sender", "receiver", "content", "timestamp"]
        return all(field in message for field in required_fields)
    
    async def _validate_system_event(self, message: Dict) -> bool:
        """Validate a system event message."""
        required_fields = ["event_type", "source", "timestamp", "data"]
        return all(field in message for field in required_fields)
    
    async def _validate_health_metric(self, message: Dict) -> bool:
        """Validate a health metric message."""
        required_fields = ["metric_name", "value", "timestamp", "source"]
        return all(field in message for field in required_fields)
    
    async def _validate_task_update(self, message: Dict) -> bool:
        """Validate a task update message."""
        required_fields = ["task_id", "status", "timestamp", "details"]
        return all(field in message for field in required_fields)
    
    # Default transformers
    async def _transform_agent_message(self, message: Dict) -> Dict:
        """Transform an agent communication message."""
        transformed = message.copy()
        transformed["processed_at"] = datetime.utcnow().isoformat()
        return transformed
    
    async def _transform_system_event(self, message: Dict) -> Dict:
        """Transform a system event message."""
        transformed = message.copy()
        transformed["processed_at"] = datetime.utcnow().isoformat()
        return transformed
    
    async def _transform_health_metric(self, message: Dict) -> Dict:
        """Transform a health metric message."""
        transformed = message.copy()
        transformed["processed_at"] = datetime.utcnow().isoformat()
        return transformed
    
    async def _transform_task_update(self, message: Dict) -> Dict:
        """Transform a task update message."""
        transformed = message.copy()
        transformed["processed_at"] = datetime.utcnow().isoformat()
        return transformed
    
    # Default processors
    async def _process_agent_message(self, message: Dict) -> Dict:
        """Process an agent communication message."""
        processed = message.copy()
        # Add any agent-specific processing logic here
        return processed
    
    async def _process_system_event(self, message: Dict) -> Dict:
        """Process a system event message."""
        processed = message.copy()
        # Add any system event-specific processing logic here
        return processed
    
    async def _process_health_metric(self, message: Dict) -> Dict:
        """Process a health metric message."""
        processed = message.copy()
        # Add any health metric-specific processing logic here
        return processed
    
    async def _process_task_update(self, message: Dict) -> Dict:
        """Process a task update message."""
        processed = message.copy()
        # Add any task update-specific processing logic here
        return processed
    
    async def get_status(self) -> Dict:
        """Get message processor status."""
        return {
            "initialized": self._initialized,
            "topics_with_processors": len(self.processors),
            "topics_with_transformers": len(self.transformers),
            "topics_with_validators": len(self.validators)
        } 