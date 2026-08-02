import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

try:
    from structlog import get_logger
    logger = get_logger()
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore

try:
    from .config import settings
except ImportError:
    class _S:  # type: ignore
        MESSAGE_PROCESSING_INTERVAL = 1
    settings = _S()


class MessageProcessor:
    """Validates, transforms, and processes messages per topic."""

    def __init__(self) -> None:
        self.processors: Dict[str, List[Callable]] = {}
        self.transformers: Dict[str, List[Callable]] = {}
        self.validators: Dict[str, List[Callable]] = {}
        self._process_task: Optional[asyncio.Task] = None
        self._initialized = False
        self.is_running = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        logger.info("message_processor.initializing")
        self._register_default_processors()
        self.is_running = True
        # Store task reference — prevents GC on Python 3.11+
        self._process_task = asyncio.create_task(
            self._housekeeping_loop(), name="message_processor.housekeeping"
        )
        self._initialized = True
        logger.info("message_processor.initialized")

    async def shutdown(self) -> None:
        logger.info("message_processor.shutting_down")
        self.is_running = False
        if self._process_task and not self._process_task.done():
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        self._initialized = False
        logger.info("message_processor.stopped")

    async def process_messages(self) -> None:
        """Public alias called as a background task from main.py."""
        await self._housekeeping_loop()

    async def _housekeeping_loop(self) -> None:
        """Periodic housekeeping — exits cleanly when is_running is False."""
        while self.is_running:
            try:
                await asyncio.sleep(settings.MESSAGE_PROCESSING_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("message_processor.housekeeping_error", error=str(exc))
                await asyncio.sleep(1)

    def _register_default_processors(self) -> None:
        for topic in ("agent-communication", "system-events", "health-metrics", "task-updates"):
            self.register_validator(topic, self._validate_has_timestamp)
            self.register_transformer(topic, self._stamp_processed_at)

    def register_processor(self, topic: str, processor: Callable) -> None:
        self.processors.setdefault(topic, []).append(processor)

    def register_transformer(self, topic: str, transformer: Callable) -> None:
        self.transformers.setdefault(topic, []).append(transformer)

    def register_validator(self, topic: str, validator: Callable) -> None:
        self.validators.setdefault(topic, []).append(validator)

    async def process_message(self, topic: str, message: Dict) -> Optional[Dict]:
        if not self._initialized:
            raise RuntimeError("MessageProcessor not initialized")
        try:
            if not await self._validate_message(topic, message):
                logger.warning("message_processor.validation_failed", topic=topic)
                return None
            transformed = await self._transform_message(topic, message)
            if transformed is None:
                return None
            return await self._apply_processors(topic, transformed)
        except Exception as exc:
            logger.error("message_processor.process_error", topic=topic, error=str(exc))
            return None

    async def _validate_message(self, topic: str, message: Dict) -> bool:
        for validator in self.validators.get(topic, []):
            try:
                result = validator(message)
                if asyncio.iscoroutine(result):
                    result = await result
                if not result:
                    return False
            except Exception as exc:
                logger.error("message_processor.validator_error", topic=topic, error=str(exc))
                return False
        return True

    async def _transform_message(self, topic: str, message: Dict) -> Optional[Dict]:
        transformed = dict(message)
        for transformer in self.transformers.get(topic, []):
            try:
                result = transformer(transformed)
                if asyncio.iscoroutine(result):
                    result = await result
                if result is None:
                    return None
                transformed = result
            except Exception as exc:
                logger.error("message_processor.transformer_error", topic=topic, error=str(exc))
                return None
        return transformed

    async def _apply_processors(self, topic: str, message: Dict) -> Optional[Dict]:
        processed = dict(message)
        for processor in self.processors.get(topic, []):
            try:
                result = processor(processed)
                if asyncio.iscoroutine(result):
                    result = await result
                if result is None:
                    return None
                processed = result
            except Exception as exc:
                logger.error("message_processor.processor_error", topic=topic, error=str(exc))
                return None
        return processed

    # Default validator — only requires a timestamp field
    def _validate_has_timestamp(self, message: Dict) -> bool:
        return "timestamp" in message

    # Default transformer — stamps processed_at
    def _stamp_processed_at(self, message: Dict) -> Dict:
        out = dict(message)
        out["processed_at"] = datetime.utcnow().isoformat()
        return out

    async def get_status(self) -> Dict:
        return {
            "initialized": self._initialized,
            "topics_with_processors": len(self.processors),
            "topics_with_transformers": len(self.transformers),
            "topics_with_validators": len(self.validators),
        }


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