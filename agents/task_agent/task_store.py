import logging
from typing import Dict, List, Any

from structlog import get_logger

logger = get_logger()

class TaskStore:
    """Simple in-memory task store for Task Agent."""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        logger.info("Initializing task store")
        self.tasks = {}
        self._initialized = True

    async def shutdown(self):
        logger.info("Shutting down task store")
        self.tasks.clear()
        self._initialized = False

    async def store_task(self, task: Dict[str, Any]) -> str:
        if not self._initialized:
            raise RuntimeError("Task store not initialized")
        task_id = task["id"]
        self.tasks[task_id] = task
        logger.debug(f"Stored task {task_id}")
        return task_id

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Task store not initialized")
        return self.tasks.get(task_id)

    async def search_tasks(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self._initialized:
            raise RuntimeError("Task store not initialized")
        results = []
        for task in self.tasks.values():
            match = True
            if "status" in query and task.get("status") != query["status"]:
                match = False
            if "priority" in query and task.get("priority") != query["priority"]:
                match = False
            if "assigned_to" in query and task.get("assigned_to") != query["assigned_to"]:
                match = False
            if "tags" in query and not all(tag in task.get("tags", []) for tag in query["tags"]):
                match = False
            if match:
                results.append(task)
        return results

    async def get_task_count(self) -> int:
        if not self._initialized:
            raise RuntimeError("Task store not initialized")
        return len(self.tasks)

    async def get_stats(self) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Task store not initialized")
        return {
            "task_count": len(self.tasks),
            "oldest_task": min((t["created_at"] for t in self.tasks.values()), default=None),
            "newest_task": max((t["created_at"] for t in self.tasks.values()), default=None),
        }

    async def clear_tasks(self):
        if not self._initialized:
            raise RuntimeError("Task store not initialized")
        self.tasks.clear()
