import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

try:
    from structlog import get_logger
except ImportError:
    def get_logger(): return logging.getLogger(__name__)

try:
    from agents.task_agent.config import settings
except ImportError:
    try:
        from .config import settings
    except ImportError:
        class _S:
            TASK_HISTORY_MAX_SIZE = 1000
        settings = _S()

logger = get_logger()


class TaskProcessor:
    """Task processor — creates, schedules, and tracks tasks. Persists via injected store."""

    def __init__(self, store=None):
        self.store = store  # Optional TaskStore injected at init
        self.current_tasks: Dict[str, Dict] = {}
        self.task_history: List[Dict] = []
        self.max_history = settings.TASK_HISTORY_MAX_SIZE
        self.scheduled_tasks: Dict[str, asyncio.Task] = {}
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        logger.info("Initializing task processor")
        self._initialized = True

    async def shutdown(self):
        logger.info("Shutting down task processor")
        for task in self.scheduled_tasks.values():
            task.cancel()
        self._initialized = False

    async def process_task(self, task_data: Dict) -> Dict:
        """Create, store, and schedule a task."""
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")

        task = {
            "id": task_data.get("id", str(uuid.uuid4())),
            "timestamp": datetime.utcnow().isoformat(),
            "title": task_data.get("title", "Untitled"),
            "description": task_data.get("description", ""),
            "priority": task_data.get("priority", 1),
            "status": task_data.get("status", "pending"),
            "due_date": task_data.get("due_date"),
            "dependencies": task_data.get("dependencies", []),
            "tags": task_data.get("tags", []),
            "context": task_data.get("context", {}),
            "assigned_to": task_data.get("assigned_to"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        self.current_tasks[task["id"]] = task

        self.task_history.append(task)
        if len(self.task_history) > self.max_history:
            self.task_history = self.task_history[-self.max_history:]

        # Persist to store if available
        if self.store and self.store._initialized:
            try:
                await self.store.store_task(task)
            except Exception as e:
                logger.warning(f"Could not persist task to store: {e}")

        if task["due_date"]:
            await self._schedule_task(task)

        logger.debug(f"Processed task: {task['id']}")
        return task

    async def _schedule_task(self, task: Dict):
        if task["id"] in self.scheduled_tasks:
            self.scheduled_tasks[task["id"]].cancel()
        try:
            due_date = datetime.fromisoformat(task["due_date"])
            delay = (due_date - datetime.utcnow()).total_seconds()
            if delay > 0:
                self.scheduled_tasks[task["id"]] = asyncio.create_task(
                    self._execute_task(task, delay)
                )
        except Exception as e:
            logger.warning(f"Could not schedule task {task['id']}: {e}")

    async def _execute_task(self, task: Dict, delay: float):
        try:
            await asyncio.sleep(delay)
            if task["id"] not in self.current_tasks:
                return
            task["status"] = "due"
            task["updated_at"] = datetime.utcnow().isoformat()
            if self.store and self.store._initialized:
                await self.store.store_task(task)
            logger.info(f"Task due: {task['title']}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error executing task {task['id']}: {e}")

    async def update_task_status(self, task_id: str, status: str) -> bool:
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        if task_id not in self.current_tasks:
            return False
        task = self.current_tasks[task_id]
        task["status"] = status
        task["updated_at"] = datetime.utcnow().isoformat()
        if status in ["completed", "cancelled"]:
            if task_id in self.scheduled_tasks:
                self.scheduled_tasks[task_id].cancel()
                del self.scheduled_tasks[task_id]
        if self.store and self.store._initialized:
            try:
                await self.store.store_task(task)
            except Exception as e:
                logger.warning(f"Could not update task in store: {e}")
        return True

    async def get_current_tasks(self) -> Dict[str, Dict]:
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        return self.current_tasks

    async def get_task_history(self) -> List[Dict]:
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        return self.task_history

    async def search_tasks(self, query: Dict) -> List[Dict]:
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        results = []
        for task in self.task_history:
            if self._matches_query(task, query):
                results.append(task)
        return results

    def _matches_query(self, task: Dict, query: Dict) -> bool:
        if "status" in query and task.get("status") != query["status"]:
            return False
        if "priority" in query and task.get("priority") != query["priority"]:
            return False
        if "tags" in query:
            if not all(tag in task.get("tags", []) for tag in query["tags"]):
                return False
        if "assigned_to" in query and task.get("assigned_to") != query["assigned_to"]:
            return False
        if "due_before" in query and task.get("due_date"):
            try:
                if datetime.fromisoformat(task["due_date"]) > datetime.fromisoformat(query["due_before"]):
                    return False
            except Exception:
                pass
        if "due_after" in query and task.get("due_date"):
            try:
                if datetime.fromisoformat(task["due_date"]) < datetime.fromisoformat(query["due_after"]):
                    return False
            except Exception:
                pass
        return True

    async def get_stats(self) -> Dict:
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        return {
            "current_tasks": len(self.current_tasks),
            "history_size": len(self.task_history),
            "max_history": self.max_history,
            "scheduled_tasks": len(self.scheduled_tasks),
            "oldest_task": min((t["created_at"] for t in self.task_history), default=None),
            "newest_task": max((t["created_at"] for t in self.task_history), default=None),
        }

    async def clear_tasks(self):
        if not self._initialized:
            raise RuntimeError("Task processor not initialized")
        for task in self.scheduled_tasks.values():
            task.cancel()
        self.current_tasks.clear()
        self.task_history.clear()
        self.scheduled_tasks.clear()
        logger.info("Cleared all tasks")
