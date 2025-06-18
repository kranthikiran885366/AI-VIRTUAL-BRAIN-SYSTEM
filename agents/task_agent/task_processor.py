import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid

from structlog import get_logger

from ...config import settings

logger = get_logger()

class TaskProcessor:
    """Task processor component for the Task Agent."""
    
    def __init__(self):
        """Initialize the task processor."""
        self.current_tasks: Dict[str, Dict] = {}
        self.task_history: List[Dict] = []
        self.max_history = settings.TASK_HISTORY_MAX_SIZE
        self.scheduled_tasks: Dict[str, asyncio.Task] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize the task processor component."""
        if self._initialized:
            return
        
        logger.info("Initializing task processor")
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the task processor component."""
        logger.info("Shutting down task processor")
        
        # Cancel all scheduled tasks
        for task in self.scheduled_tasks.values():
            task.cancel()
        
        self._initialized = False
    
    async def process_task(self, task_data: Dict) -> Dict:
        """Process a new task."""
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        
        # Create task entry
        task = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "title": task_data["title"],
            "description": task_data["description"],
            "priority": task_data["priority"],
            "status": task_data["status"],
            "due_date": task_data.get("due_date"),
            "dependencies": task_data.get("dependencies", []),
            "tags": task_data.get("tags", []),
            "context": task_data.get("context", {}),
            "assigned_to": task_data.get("assigned_to"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Update current tasks
        self.current_tasks[task["id"]] = task
        
        # Add to history
        self.task_history.append(task)
        
        # Trim history if needed
        if len(self.task_history) > self.max_history:
            self.task_history = self.task_history[-self.max_history:]
        
        # Schedule task if due date is set
        if task["due_date"]:
            await self._schedule_task(task)
        
        logger.debug(f"Processed task: {task['id']}")
        return task
    
    async def _schedule_task(self, task: Dict):
        """Schedule a task for execution."""
        if task["id"] in self.scheduled_tasks:
            self.scheduled_tasks[task["id"]].cancel()
        
        due_date = datetime.fromisoformat(task["due_date"])
        delay = (due_date - datetime.utcnow()).total_seconds()
        
        if delay > 0:
            self.scheduled_tasks[task["id"]] = asyncio.create_task(
                self._execute_task(task, delay)
            )
    
    async def _execute_task(self, task: Dict, delay: float):
        """Execute a scheduled task."""
        try:
            await asyncio.sleep(delay)
            
            # Check if task is still current
            if task["id"] not in self.current_tasks:
                return
            
            # Update task status
            task["status"] = "due"
            task["updated_at"] = datetime.utcnow().isoformat()
            
            # Notify about due task
            await self._notify_due_task(task)
            
        except asyncio.CancelledError:
            logger.debug(f"Task {task['id']} execution cancelled")
        except Exception as e:
            logger.error(f"Error executing task {task['id']}: {str(e)}")
    
    async def _notify_due_task(self, task: Dict):
        """Notify about a due task."""
        # TODO: Implement notification system
        logger.info(f"Task due: {task['title']}")
    
    async def update_task_status(self, task_id: str, status: str) -> bool:
        """Update task status."""
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        
        if task_id not in self.current_tasks:
            return False
        
        task = self.current_tasks[task_id]
        task["status"] = status
        task["updated_at"] = datetime.utcnow().isoformat()
        
        # Cancel scheduled execution if task is completed
        if status in ["completed", "cancelled"]:
            if task_id in self.scheduled_tasks:
                self.scheduled_tasks[task_id].cancel()
                del self.scheduled_tasks[task_id]
        
        logger.debug(f"Updated task status: {task_id} -> {status}")
        return True
    
    async def get_current_tasks(self) -> Dict[str, Dict]:
        """Get current tasks."""
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        
        return self.current_tasks
    
    async def get_task_history(self) -> List[Dict]:
        """Get task history."""
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        
        return self.task_history
    
    async def search_tasks(self, query: Dict) -> List[Dict]:
        """Search tasks based on criteria."""
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        
        results = []
        
        for task in self.task_history:
            if self._matches_query(task, query):
                results.append(task)
        
        return results
    
    def _matches_query(self, task: Dict, query: Dict) -> bool:
        """Check if a task matches the query criteria."""
        # Check status
        if "status" in query and task["status"] != query["status"]:
            return False
        
        # Check priority
        if "priority" in query and task["priority"] != query["priority"]:
            return False
        
        # Check tags
        if "tags" in query:
            if not all(tag in task["tags"] for tag in query["tags"]):
                return False
        
        # Check assigned_to
        if "assigned_to" in query and task["assigned_to"] != query["assigned_to"]:
            return False
        
        # Check due date range
        if "due_before" in query:
            task_due = datetime.fromisoformat(task["due_date"])
            due_before = datetime.fromisoformat(query["due_before"])
            if task_due > due_before:
                return False
        
        if "due_after" in query:
            task_due = datetime.fromisoformat(task["due_date"])
            due_after = datetime.fromisoformat(query["due_after"])
            if task_due < due_after:
                return False
        
        return True
    
    async def get_stats(self) -> Dict:
        """Get task processor statistics."""
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        
        return {
            "current_tasks": len(self.current_tasks),
            "history_size": len(self.task_history),
            "max_history": self.max_history,
            "scheduled_tasks": len(self.scheduled_tasks),
            "oldest_task": min(t["created_at"] for t in self.task_history) if self.task_history else None,
            "newest_task": max(t["created_at"] for t in self.task_history) if self.task_history else None
        }
    
    async def clear_tasks(self):
        """Clear all tasks."""
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        
        # Cancel all scheduled tasks
        for task in self.scheduled_tasks.values():
            task.cancel()
        
        self.current_tasks.clear()
        self.task_history.clear()
        self.scheduled_tasks.clear()
        
        logger.info("Cleared all tasks") 