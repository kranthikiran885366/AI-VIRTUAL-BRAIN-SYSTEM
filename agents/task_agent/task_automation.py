import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import uuid
import json

from structlog import get_logger

from ...config import settings

logger = get_logger()

class TaskAutomation:
    """Task automation component for the Task Agent."""
    
    def __init__(self):
        """Initialize the task automation component."""
        self.automation_rules: Dict[str, Dict] = {}
        self.rule_handlers: Dict[str, Callable] = {}
        self.execution_history: List[Dict] = []
        self.max_history = settings.TASK_AUTOMATION_HISTORY_SIZE
        self._initialized = False
        self._running = False
        self._task_queue = asyncio.Queue()
    
    async def initialize(self):
        """Initialize the task automation component."""
        if self._initialized:
            return
        
        logger.info("Initializing task automation")
        
        # Register default rule handlers
        self._register_default_handlers()
        
        # Load existing rules
        await self._load_rules()
        
        # Start automation loop
        self._running = True
        asyncio.create_task(self._automation_loop())
        
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the task automation component."""
        if not self._initialized:
            return
        
        logger.info("Shutting down task automation")
        
        # Stop automation loop
        self._running = False
        
        # Save rules
        await self._save_rules()
        
        self._initialized = False
    
    def _register_default_handlers(self):
        """Register default rule handlers."""
        self.rule_handlers = {
            "schedule": self._handle_schedule,
            "notify": self._handle_notify,
            "assign": self._handle_assign,
            "tag": self._handle_tag,
            "priority": self._handle_priority,
            "status": self._handle_status
        }
    
    async def _load_rules(self):
        """Load automation rules from storage."""
        try:
            with open(settings.TASK_AUTOMATION_RULES_PATH, "r") as f:
                self.automation_rules = json.load(f)
            logger.info(f"Loaded {len(self.automation_rules)} automation rules")
        except FileNotFoundError:
            logger.info("No existing automation rules found")
    
    async def _save_rules(self):
        """Save automation rules to storage."""
        try:
            with open(settings.TASK_AUTOMATION_RULES_PATH, "w") as f:
                json.dump(self.automation_rules, f, indent=2)
            logger.info(f"Saved {len(self.automation_rules)} automation rules")
        except Exception as e:
            logger.error(f"Failed to save automation rules: {e}")
    
    async def _automation_loop(self):
        """Main automation loop for processing tasks."""
        while self._running:
            try:
                # Get task from queue
                task = await self._task_queue.get()
                
                # Process task with matching rules
                await self._process_task(task)
                
                # Mark task as done
                self._task_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in automation loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_task(self, task: Dict):
        """Process a task with matching automation rules."""
        for rule_id, rule in self.automation_rules.items():
            if await self._matches_rule(task, rule):
                try:
                    # Execute rule actions
                    for action in rule["actions"]:
                        handler = self.rule_handlers.get(action["type"])
                        if handler:
                            await handler(task, action)
                    
                    # Record execution
                    self._record_execution(task, rule_id, True)
                    
                except Exception as e:
                    logger.error(f"Error executing rule {rule_id}: {e}")
                    self._record_execution(task, rule_id, False, str(e))
    
    async def _matches_rule(self, task: Dict, rule: Dict) -> bool:
        """Check if a task matches an automation rule."""
        # Check conditions
        for condition in rule["conditions"]:
            if not await self._evaluate_condition(task, condition):
                return False
        return True
    
    async def _evaluate_condition(self, task: Dict, condition: Dict) -> bool:
        """Evaluate a condition against a task."""
        field = condition["field"]
        operator = condition["operator"]
        value = condition["value"]
        
        task_value = task.get(field)
        if task_value is None:
            return False
        
        if operator == "equals":
            return task_value == value
        elif operator == "contains":
            return value in task_value
        elif operator == "greater_than":
            return task_value > value
        elif operator == "less_than":
            return task_value < value
        elif operator == "in":
            return task_value in value
        elif operator == "not_in":
            return task_value not in value
        
        return False
    
    async def _handle_schedule(self, task: Dict, action: Dict):
        """Handle schedule action."""
        # Schedule task for future execution
        schedule_time = datetime.fromisoformat(action["time"])
        delay = (schedule_time - datetime.utcnow()).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
            await self._task_queue.put(task)
    
    async def _handle_notify(self, task: Dict, action: Dict):
        """Handle notify action."""
        # Send notification about task
        notification = {
            "type": "task_notification",
            "task_id": task["id"],
            "title": task["title"],
            "message": action["message"],
            "priority": action.get("priority", "normal")
        }
        # TODO: Implement notification system
        logger.info(f"Notification: {notification}")
    
    async def _handle_assign(self, task: Dict, action: Dict):
        """Handle assign action."""
        # Assign task to user
        task["assigned_to"] = action["user"]
        # TODO: Implement user assignment system
        logger.info(f"Assigned task {task['id']} to {action['user']}")
    
    async def _handle_tag(self, task: Dict, action: Dict):
        """Handle tag action."""
        # Add tags to task
        if "tags" not in task:
            task["tags"] = []
        task["tags"].extend(action["tags"])
        # TODO: Implement tag update system
        logger.info(f"Added tags {action['tags']} to task {task['id']}")
    
    async def _handle_priority(self, task: Dict, action: Dict):
        """Handle priority action."""
        # Update task priority
        task["priority"] = action["priority"]
        # TODO: Implement priority update system
        logger.info(f"Updated priority of task {task['id']} to {action['priority']}")
    
    async def _handle_status(self, task: Dict, action: Dict):
        """Handle status action."""
        # Update task status
        task["status"] = action["status"]
        # TODO: Implement status update system
        logger.info(f"Updated status of task {task['id']} to {action['status']}")
    
    def _record_execution(self, task: Dict, rule_id: str, success: bool, error: Optional[str] = None):
        """Record rule execution in history."""
        execution = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": task["id"],
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
            raise RuntimeError("Task automation not initialized")
        
        rule_id = str(uuid.uuid4())
        self.automation_rules[rule_id] = rule
        
        # Save rules
        await self._save_rules()
        
        logger.info(f"Added automation rule: {rule_id}")
        return rule_id
    
    async def update_rule(self, rule_id: str, rule: Dict):
        """Update an existing automation rule."""
        if not self._initialized:
            raise RuntimeError("Task automation not initialized")
        
        if rule_id not in self.automation_rules:
            raise ValueError(f"Rule {rule_id} not found")
        
        self.automation_rules[rule_id] = rule
        
        # Save rules
        await self._save_rules()
        
        logger.info(f"Updated automation rule: {rule_id}")
    
    async def delete_rule(self, rule_id: str):
        """Delete an automation rule."""
        if not self._initialized:
            raise RuntimeError("Task automation not initialized")
        
        if rule_id not in self.automation_rules:
            raise ValueError(f"Rule {rule_id} not found")
        
        del self.automation_rules[rule_id]
        
        # Save rules
        await self._save_rules()
        
        logger.info(f"Deleted automation rule: {rule_id}")
    
    async def get_rule(self, rule_id: str) -> Dict:
        """Get an automation rule by ID."""
        if not self._initialized:
            raise RuntimeError("Task automation not initialized")
        
        if rule_id not in self.automation_rules:
            raise ValueError(f"Rule {rule_id} not found")
        
        return self.automation_rules[rule_id]
    
    async def get_rules(self) -> Dict[str, Dict]:
        """Get all automation rules."""
        if not self._initialized:
            raise RuntimeError("Task automation not initialized")
        
        return self.automation_rules
    
    async def get_execution_history(self) -> List[Dict]:
        """Get automation execution history."""
        if not self._initialized:
            raise RuntimeError("Task automation not initialized")
        
        return self.execution_history
    
    async def get_stats(self) -> Dict:
        """Get task automation statistics."""
        if not self._initialized:
            raise RuntimeError("Task automation not initialized")
        
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
            raise RuntimeError("Task automation not initialized")
        
        self.automation_rules.clear()
        await self._save_rules()
        logger.info("Cleared all automation rules")
    
    async def clear_history(self):
        """Clear execution history."""
        if not self._initialized:
            raise RuntimeError("Task automation not initialized")
        
        self.execution_history.clear()
        logger.info("Cleared execution history") 