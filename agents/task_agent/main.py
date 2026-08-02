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
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError:
    FastAPI = None
    HTTPException = Exception
    BaseModel = object

try:
    from agents.base_agent import BaseAgent
except ImportError:
    try:
        from ..base_agent import BaseAgent
    except ImportError:
        class BaseAgent:
            def __init__(self, **kwargs):
                self.agent_id = kwargs.get("agent_id", str(uuid.uuid4()))
                self.agent_type = kwargs.get("agent_type", "base")
                self.state = kwargs.get("state", {})
                self.memory = kwargs.get("memory", [])
                self.emotions = kwargs.get("emotions", {})
                self.connections = kwargs.get("connections", {})
            async def initialize(self): pass
            async def shutdown(self): pass
            async def _establish_connection(self, *a, **kw): pass

try:
    from agents.task_agent.task_processor import TaskProcessor
    from agents.task_agent.task_store import TaskStore
    from agents.task_agent.task_analyzer import TaskAnalyzer
    from agents.task_agent.task_automation import TaskAutomation
except ImportError:
    try:
        from .task_processor import TaskProcessor
        from .task_store import TaskStore
        from .task_analyzer import TaskAnalyzer
        from .task_automation import TaskAutomation
    except ImportError:
        TaskProcessor = TaskStore = TaskAnalyzer = TaskAutomation = None

logger = get_logger()

if BaseModel is not object:
    class TaskData(BaseModel):
        title: str
        description: str = ""
        priority: int = 1
        status: str = "pending"
        due_date: Optional[str] = None
        dependencies: List[str] = []
        tags: List[str] = []
        context: Dict[str, Any] = {}
        assigned_to: Optional[str] = None

    class TaskQuery(BaseModel):
        status: Optional[str] = None
        priority: Optional[int] = None
        tags: Optional[List[str]] = None
        assigned_to: Optional[str] = None
        due_before: Optional[str] = None
        due_after: Optional[str] = None
else:
    TaskData = dict
    TaskQuery = dict


class TaskAgent(BaseAgent):
    """Task Agent — creates, stores, analyzes, and automates tasks."""

    def __init__(self):
        super().__init__(
            agent_id="task_agent",
            agent_type="task",
        )
        # Build store first, inject into processor so tasks persist
        self.store = TaskStore() if TaskStore else None
        self.processor = TaskProcessor(store=self.store) if TaskProcessor else None
        self.analyzer = TaskAnalyzer() if TaskAnalyzer else None
        self.automation = TaskAutomation() if TaskAutomation else None

        if FastAPI:
            self.app = FastAPI(title="Task Agent API")
            self._setup_routes()

    def _setup_routes(self):
        app = self.app

        @app.get("/health")
        async def health_check():
            return {"status": "healthy", "agent_id": self.agent_id}

        @app.get("/stats")
        async def get_stats():
            stats = {}
            if self.processor:
                stats["processor"] = await self.processor.get_stats()
            if self.store:
                stats["store"] = await self.store.get_stats()
            if self.analyzer:
                stats["analyzer"] = await self.analyzer.get_stats()
            if self.automation:
                stats["automation"] = await self.automation.get_stats()
            return stats

        @app.post("/tasks")
        async def create_task(task: TaskData):
            try:
                data = task.dict() if hasattr(task, "dict") else task
                processed = await self.processor.process_task(data) if self.processor else data
                analysis = await self.analyzer.analyze_task(processed) if self.analyzer else {}
                automation_result = await self.automation.check_automation(processed) if self.automation else {}
                await self._update_state()
                return {
                    "task_id": processed.get("id"),
                    "task": processed,
                    "analysis": analysis,
                    "automation": automation_result,
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/tasks/{task_id}")
        async def get_task(task_id: str):
            if not self.store:
                raise HTTPException(status_code=503, detail="Store not available")
            task = await self.store.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return task

        @app.post("/tasks/search")
        async def search_tasks(query: TaskQuery):
            if not self.store:
                return []
            q = query.dict(exclude_none=True) if hasattr(query, "dict") else query
            return await self.store.search_tasks(q)

        @app.get("/tasks/current")
        async def get_current_tasks():
            if not self.processor:
                return {}
            return await self.processor.get_current_tasks()

    async def initialize(self):
        await super().initialize()
        if self.store:
            await self.store.initialize()
        if self.processor:
            await self.processor.initialize()
        if self.analyzer:
            await self.analyzer.initialize()
        if self.automation:
            await self.automation.initialize()
        logger.info("Task Agent initialized")

    async def shutdown(self):
        await super().shutdown()
        if self.processor:
            await self.processor.shutdown()
        if self.store:
            await self.store.shutdown()
        if self.analyzer:
            await self.analyzer.shutdown()
        if self.automation:
            await self.automation.shutdown()
        logger.info("Task Agent shut down")

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Called by orchestrator agent_manager."""
        action = task.get("action", "")
        input_data = task.get("input_data", {})
        user_id = task.get("user_id")

        if action in ("create", "add"):
            task_data = {
                "title": input_data.get("title", "New Task"),
                "description": input_data.get("description", ""),
                "priority": input_data.get("priority", 1),
                "status": "pending",
                "due_date": input_data.get("due_date"),
                "tags": input_data.get("tags", []),
                "assigned_to": user_id,
            }
            if self.processor:
                processed = await self.processor.process_task(task_data)
                return {"status": "created", "task_id": processed["id"], "task": processed}
            return {"status": "created", "task_id": str(uuid.uuid4()), "task": task_data}

        if action in ("list", "get_all"):
            if self.store:
                query = {}
                if input_data.get("status"):
                    query["status"] = input_data["status"]
                tasks = await self.store.search_tasks(query)
                return {"tasks": tasks, "count": len(tasks)}
            if self.processor:
                current = await self.processor.get_current_tasks()
                return {"tasks": list(current.values()), "count": len(current)}
            return {"tasks": [], "count": 0}

        if action in ("update", "complete"):
            task_id = input_data.get("task_id", "")
            status = input_data.get("status", "completed")
            if self.processor:
                success = await self.processor.update_task_status(task_id, status)
                return {"status": "updated" if success else "not_found", "task_id": task_id}
            return {"status": "updated", "task_id": task_id}

        if action == "search":
            query = input_data.get("query", {})
            if self.store:
                tasks = await self.store.search_tasks(query)
                return {"tasks": tasks, "count": len(tasks)}
            return {"tasks": [], "count": 0}

        # Default: return current task stats
        stats = await self.processor.get_stats() if self.processor else {}
        return {"status": "ok", "stats": stats}

    async def _update_state(self):
        task_count = 0
        if self.store:
            try:
                task_count = await self.store.get_task_count()
            except Exception:
                pass
        self.state.update({
            "task_count": task_count,
            "last_updated": datetime.utcnow().isoformat(),
        })


# ─── Standalone FastAPI app ───────────────────────────────────────────────────

if FastAPI:
    app = FastAPI(
        title="Task Agent API",
        description="Task management agent for the AI Virtual Brain System",
        version="1.0.0",
    )
    _task_agent: Optional[TaskAgent] = None

    @app.on_event("startup")
    async def startup_event():
        global _task_agent
        _task_agent = TaskAgent()
        await _task_agent.initialize()

    @app.on_event("shutdown")
    async def shutdown_event():
        if _task_agent:
            await _task_agent.shutdown()
