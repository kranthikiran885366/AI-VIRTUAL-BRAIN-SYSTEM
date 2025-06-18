import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid
from enum import Enum

from structlog import get_logger

from .config import settings

logger = get_logger()

class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(int, Enum):
    """Task priority enumeration."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class TaskScheduler:
    """Manages task scheduling and execution."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the task scheduler with configuration."""
        self.config = config
        self.is_running = False
        
        # Initialize task storage
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_queue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # Initialize metrics
        self.metrics = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "average_completion_time": 0.0
        }
    
    async def start(self):
        """Start the task scheduler."""
        logger.info("Starting task scheduler...")
        self.is_running = True
        
        # Start task processing loop
        asyncio.create_task(self._process_tasks())
        
        logger.info("Task scheduler started successfully")
    
    async def stop(self):
        """Stop the task scheduler."""
        logger.info("Stopping task scheduler...")
        self.is_running = False
        
        # Cancel all running tasks
        for task_id, task in self.running_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        logger.info("Task scheduler stopped successfully")
    
    async def schedule_task(self, task: Dict[str, Any]) -> str:
        """Schedule a new task."""
        task_id = str(uuid.uuid4())
        
        # Create task record
        task_record = {
            "id": task_id,
            "name": task.get("name", "unnamed_task"),
            "description": task.get("description", ""),
            "priority": task.get("priority", TaskPriority.MEDIUM),
            "status": TaskStatus.PENDING,
            "created_at": datetime.utcnow(),
            "scheduled_for": task.get("scheduled_for", datetime.utcnow()),
            "timeout": task.get("timeout", 300),  # Default 5 minutes
            "dependencies": task.get("dependencies", []),
            "parameters": task.get("parameters", {}),
            "result": None,
            "error": None
        }
        
        # Store task
        self.tasks[task_id] = task_record
        
        # Add to queue
        await self.task_queue.put((
            -task_record["priority"],  # Negative for higher priority first
            task_record["scheduled_for"],
            task_id
        ))
        
        logger.info(f"Task {task_id} scheduled successfully")
        return task_id
    
    async def _process_tasks(self):
        """Process tasks from the queue."""
        while self.is_running:
            try:
                # Get next task from queue
                priority, scheduled_time, task_id = await self.task_queue.get()
                
                # Check if task should be executed now
                if datetime.utcnow() < scheduled_time:
                    # Put back in queue
                    await self.task_queue.put((priority, scheduled_time, task_id))
                    await asyncio.sleep(1)
                    continue
                
                # Get task record
                task = self.tasks[task_id]
                
                # Check dependencies
                if not await self._check_dependencies(task):
                    # Put back in queue
                    await self.task_queue.put((priority, scheduled_time, task_id))
                    await asyncio.sleep(1)
                    continue
                
                # Execute task
                await self._execute_task(task)
                
                # Mark task as done
                self.task_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing task: {e}")
                await asyncio.sleep(1)
    
    async def _check_dependencies(self, task: Dict[str, Any]) -> bool:
        """Check if all task dependencies are satisfied."""
        for dep_id in task["dependencies"]:
            dep_task = self.tasks.get(dep_id)
            if not dep_task or dep_task["status"] != TaskStatus.COMPLETED:
                return False
        return True
    
    async def _execute_task(self, task: Dict[str, Any]):
        """Execute a task."""
        try:
            # Update task status
            task["status"] = TaskStatus.RUNNING
            task["started_at"] = datetime.utcnow()
            
            # Create execution task
            execution_task = asyncio.create_task(
                self._run_task(task),
                name=f"task_{task['id']}"
            )
            
            # Store running task
            self.running_tasks[task["id"]] = execution_task
            
            # Wait for completion with timeout
            try:
                await asyncio.wait_for(execution_task, timeout=task["timeout"])
                task["status"] = TaskStatus.COMPLETED
                self.metrics["completed_tasks"] += 1
            except asyncio.TimeoutError:
                task["status"] = TaskStatus.FAILED
                task["error"] = "Task execution timed out"
                self.metrics["failed_tasks"] += 1
            except Exception as e:
                task["status"] = TaskStatus.FAILED
                task["error"] = str(e)
                self.metrics["failed_tasks"] += 1
            
            # Update completion time
            task["completed_at"] = datetime.utcnow()
            
            # Update metrics
            self._update_metrics(task)
            
        except Exception as e:
            logger.error(f"Error executing task {task['id']}: {e}")
            task["status"] = TaskStatus.FAILED
            task["error"] = str(e)
            self.metrics["failed_tasks"] += 1
    
    async def _run_task(self, task: Dict[str, Any]):
        """Run the actual task logic."""
        # This is a placeholder - implement actual task execution
        await asyncio.sleep(1)
        return {"result": "Task completed successfully"}
    
    def _update_metrics(self, task: Dict[str, Any]):
        """Update task metrics."""
        self.metrics["total_tasks"] += 1
        
        if task["status"] == TaskStatus.COMPLETED:
            completion_time = (task["completed_at"] - task["started_at"]).total_seconds()
            self.metrics["average_completion_time"] = (
                (self.metrics["average_completion_time"] * (self.metrics["completed_tasks"] - 1) +
                 completion_time) / self.metrics["completed_tasks"]
            )
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    async def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks."""
        return list(self.tasks.values())
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task["status"] in [TaskStatus.PENDING, TaskStatus.SCHEDULED]:
            task["status"] = TaskStatus.CANCELLED
            return True
        
        if task["status"] == TaskStatus.RUNNING:
            running_task = self.running_tasks.get(task_id)
            if running_task:
                running_task.cancel()
                try:
                    await running_task
                except asyncio.CancelledError:
                    pass
                task["status"] = TaskStatus.CANCELLED
                return True
        
        return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the task scheduler."""
        return {
            "status": "running" if self.is_running else "stopped",
            "metrics": self.metrics,
            "queue_size": self.task_queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "total_tasks": len(self.tasks)
        } 