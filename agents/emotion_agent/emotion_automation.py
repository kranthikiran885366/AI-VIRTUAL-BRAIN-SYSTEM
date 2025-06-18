import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import uuid
import json

from structlog import get_logger

from ...config import settings

logger = get_logger()

class EmotionAutomation:
    """Emotion automation component for the Emotion Agent."""
    
    def __init__(self):
        """Initialize the emotion automation component."""
        self.automation_rules: Dict[str, Dict] = {}
        self.rule_handlers: Dict[str, Callable] = {}
        self.execution_history: List[Dict] = []
        self.max_history = settings.EMOTION_AUTOMATION_HISTORY_SIZE
        self._initialized = False
        self._running = False
        self._emotion_queue = asyncio.Queue()
    
    async def initialize(self):
        """Initialize the emotion automation component."""
        if self._initialized:
            return
        
        logger.info("Initializing emotion automation")
        
        # Register default rule handlers
        self._register_default_handlers()
        
        # Load existing rules
        await self._load_rules()
        
        # Start automation loop
        self._running = True
        asyncio.create_task(self._automation_loop())
        
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the emotion automation component."""
        if not self._initialized:
            return
        
        logger.info("Shutting down emotion automation")
        
        # Stop automation loop
        self._running = False
        
        # Save rules
        await self._save_rules()
        
        self._initialized = False
    
    def _register_default_handlers(self):
        """Register default rule handlers."""
        self.rule_handlers = {
            "categorize": self._handle_categorize,
            "tag": self._handle_tag,
            "link": self._handle_link,
            "archive": self._handle_archive,
            "prioritize": self._handle_prioritize,
            "summarize": self._handle_summarize
        }
    
    async def _load_rules(self):
        """Load automation rules from storage."""
        try:
            with open(settings.EMOTION_AUTOMATION_RULES_PATH, "r") as f:
                self.automation_rules = json.load(f)
            logger.info(f"Loaded {len(self.automation_rules)} automation rules")
        except FileNotFoundError:
            logger.info("No existing automation rules found")
    
    async def _save_rules(self):
        """Save automation rules to storage."""
        try:
            with open(settings.EMOTION_AUTOMATION_RULES_PATH, "w") as f:
                json.dump(self.automation_rules, f, indent=2)
            logger.info(f"Saved {len(self.automation_rules)} automation rules")
        except Exception as e:
            logger.error(f"Failed to save automation rules: {e}")
    
    async def _automation_loop(self):
        """Main automation loop for processing emotions."""
        while self._running:
            try:
                # Get emotion from queue
                emotion = await self._emotion_queue.get()
                
                # Process emotion with matching rules
                await self._process_emotion(emotion)
                
                # Mark emotion as done
                self._emotion_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in automation loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_emotion(self, emotion: Dict):
        """Process an emotion with matching automation rules."""
        for rule_id, rule in self.automation_rules.items():
            if await self._matches_rule(emotion, rule):
                try:
                    # Execute rule actions
                    for action in rule["actions"]:
                        handler = self.rule_handlers.get(action["type"])
                        if handler:
                            await handler(emotion, action)
                    
                    # Record execution
                    self._record_execution(emotion, rule_id, True)
                    
                except Exception as e:
                    logger.error(f"Error executing rule {rule_id}: {e}")
                    self._record_execution(emotion, rule_id, False, str(e))
    
    async def _matches_rule(self, emotion: Dict, rule: Dict) -> bool:
        """Check if an emotion matches an automation rule."""
        # Check conditions
        for condition in rule["conditions"]:
            if not await self._evaluate_condition(emotion, condition):
                return False
        return True
    
    async def _evaluate_condition(self, emotion: Dict, condition: Dict) -> bool:
        """Evaluate a condition against an emotion."""
        field = condition["field"]
        operator = condition["operator"]
        value = condition["value"]
        
        emotion_value = emotion.get(field)
        if emotion_value is None:
            return False
        
        if operator == "equals":
            return emotion_value == value
        elif operator == "contains":
            return value in emotion_value
        elif operator == "greater_than":
            return emotion_value > value
        elif operator == "less_than":
            return emotion_value < value
        elif operator == "in":
            return emotion_value in value
        elif operator == "not_in":
            return emotion_value not in value
        
        return False
    
    async def _handle_categorize(self, emotion: Dict, action: Dict):
        """Handle categorize action."""
        # Categorize emotion
        emotion["category"] = action["category"]
        # TODO: Implement category update system
        logger.info(f"Categorized emotion {emotion['id']} as {action['category']}")
    
    async def _handle_tag(self, emotion: Dict, action: Dict):
        """Handle tag action."""
        # Add tags to emotion
        if "tags" not in emotion:
            emotion["tags"] = []
        emotion["tags"].extend(action["tags"])
        # TODO: Implement tag update system
        logger.info(f"Added tags {action['tags']} to emotion {emotion['id']}")
    
    async def _handle_link(self, emotion: Dict, action: Dict):
        """Handle link action."""
        # Link emotion to other emotions
        if "links" not in emotion:
            emotion["links"] = []
        emotion["links"].extend(action["emotion_ids"])
        # TODO: Implement link update system
        logger.info(f"Linked emotion {emotion['id']} to {action['emotion_ids']}")
    
    async def _handle_archive(self, emotion: Dict, action: Dict):
        """Handle archive action."""
        # Archive emotion
        emotion["archived"] = True
        emotion["archived_at"] = datetime.utcnow().isoformat()
        # TODO: Implement archive system
        logger.info(f"Archived emotion {emotion['id']}")
    
    async def _handle_prioritize(self, emotion: Dict, action: Dict):
        """Handle prioritize action."""
        # Update emotion priority
        emotion["priority"] = action["priority"]
        # TODO: Implement priority update system
        logger.info(f"Updated priority of emotion {emotion['id']} to {action['priority']}")
    
    async def _handle_summarize(self, emotion: Dict, action: Dict):
        """Handle summarize action."""
        # Generate emotion summary
        # TODO: Implement summarization system
        logger.info(f"Generated summary for emotion {emotion['id']}")
    
    def _record_execution(self, emotion: Dict, rule_id: str, success: bool, error: Optional[str] = None):
        """Record rule execution in history."""
        execution = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "emotion_id": emotion["id"],
            "rule_id": rule_id,
            "success": success,
            "error": error
        }
        
        self.execution_history.append(execution)
        
        # Trim history if needed
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
    
    async def add_rule(self, rule: Dict) -> str:
        """Add a new automation rule."""
        if not self._initialized:
            raise RuntimeError("Emotion automation not initialized")
        
        rule_id = str(uuid.uuid4())
        self.automation_rules[rule_id] = rule
        
        # Save rules
        await self._save_rules()
        
        logger.info(f"Added automation rule: {rule_id}")
        return rule_id
    
    async def update_rule(self, rule_id: str, rule: Dict):
        """Update an existing automation rule."""
        if not self._initialized:
            raise RuntimeError("Emotion automation not initialized")
        
        if rule_id not in self.automation_rules:
            raise ValueError(f"Rule {rule_id} not found")
        
        self.automation_rules[rule_id] = rule
        
        # Save rules
        await self._save_rules()
        
        logger.info(f"Updated automation rule: {rule_id}")
    
    async def delete_rule(self, rule_id: str):
        """Delete an automation rule."""
        if not self._initialized:
            raise RuntimeError("Emotion automation not initialized")
        
        if rule_id not in self.automation_rules:
            raise ValueError(f"Rule {rule_id} not found")
        
        del self.automation_rules[rule_id]
        
        # Save rules
        await self._save_rules()
        
        logger.info(f"Deleted automation rule: {rule_id}")
    
    async def get_rule(self, rule_id: str) -> Dict:
        """Get an automation rule by ID."""
        if not self._initialized:
            raise RuntimeError("Emotion automation not initialized")
        
        if rule_id not in self.automation_rules:
            raise ValueError(f"Rule {rule_id} not found")
        
        return self.automation_rules[rule_id]
    
    async def get_rules(self) -> Dict[str, Dict]:
        """Get all automation rules."""
        if not self._initialized:
            raise RuntimeError("Emotion automation not initialized")
        
        return self.automation_rules
    
    async def get_execution_history(self) -> List[Dict]:
        """Get automation execution history."""
        if not self._initialized:
            raise RuntimeError("Emotion automation not initialized")
        
        return self.execution_history
    
    async def get_stats(self) -> Dict:
        """Get emotion automation statistics."""
        if not self._initialized:
            raise RuntimeError("Emotion automation not initialized")
        
        return {
            "rule_count": len(self.automation_rules),
            "execution_count": len(self.execution_history),
            "success_count": sum(1 for e in self.execution_history if e["success"]),
            "error_count": sum(1 for e in self.execution_history if not e["success"]),
            "max_history": self.max_history,
            "oldest_execution": min(e["timestamp"] for e in self.execution_history) if self.execution_history else None,
            "newest_execution": max(e["timestamp"] for e in self.execution_history) if self.execution_history else None
        }
    
    async def clear_rules(self):
        """Clear all automation rules."""
        if not self._initialized:
            raise RuntimeError("Emotion automation not initialized")
        
        self.automation_rules.clear()
        await self._save_rules()
        logger.info("Cleared all automation rules")
    
    async def clear_history(self):
        """Clear execution history."""
        if not self._initialized:
            raise RuntimeError("Emotion automation not initialized")
        
        self.execution_history.clear()
        logger.info("Cleared execution history") 