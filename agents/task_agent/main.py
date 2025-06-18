import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid

from structlog import get_logger
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ...config import settings
from ..base_agent import BaseAgent
from .task_processor import TaskProcessor
from .task_store import TaskStore
from .task_analyzer import TaskAnalyzer
from .task_automation import TaskAutomation

logger = get_logger()

class TaskData(BaseModel):
    """Task data model."""
    title: str
    description: str
    priority: int
    status: str = "pending"
    due_date: Optional[str] = None
    dependencies: List[str] = []
    tags: List[str] = []
    context: Dict[str, Any] = {}
    assigned_to: Optional[str] = None

class TaskQuery(BaseModel):
    """Task query model."""
    status: Optional[str] = None
    priority: Optional[int] = None
    tags: Optional[List[str]] = None
    assigned_to: Optional[str] = None
    due_before: Optional[str] = None
    due_after: Optional[str] = None

class TaskAgent(BaseAgent):
    """Task Agent for managing and automating tasks."""
    
    def __init__(self):
        """Initialize the Task Agent."""
        super().__init__(
            agent_id=str(uuid.uuid4()),
            agent_type="task",
            state={},
            memory=[],
            emotions={},
            connections=[]
        )
        
        # Initialize components
        self.processor = TaskProcessor()
        self.store = TaskStore()
        self.analyzer = TaskAnalyzer()
        self.automation = TaskAutomation()
        
        # Create FastAPI app
        self.app = FastAPI(title="Task Agent API")
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up API routes."""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "agent_id": self.agent_id}
        
        @self.app.get("/stats")
        async def get_stats():
            """Get task statistics."""
            return {
                "processor": await self.processor.get_stats(),
                "store": await self.store.get_stats(),
                "analyzer": await self.analyzer.get_stats(),
                "automation": await self.automation.get_stats()
            }
        
        @self.app.post("/tasks")
        async def create_task(task: TaskData):
            """Create a new task."""
            try:
                # Process task
                processed_task = await self.processor.process_task(task.dict())
                
                # Store task
                task_id = await self.store.store_task(processed_task)
                
                # Analyze task
                analysis = await self.analyzer.analyze_task(processed_task)
                
                # Check for automation opportunities
                automation_result = await self.automation.check_automation(processed_task)
                
                # Update agent state
                await self._update_state()
                
                return {
                    "task_id": task_id,
                    "analysis": analysis,
                    "automation": automation_result
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/tasks/{task_id}")
        async def get_task(task_id: str):
            """Get a specific task."""
            try:
                task = await self.store.get_task(task_id)
                if not task:
                    raise HTTPException(status_code=404, detail="Task not found")
                return task
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/tasks/search")
        async def search_tasks(query: TaskQuery):
            """Search tasks."""
            try:
                return await self.store.search_tasks(query.dict(exclude_none=True))
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/tasks/current")
        async def get_current_tasks():
            """Get current tasks."""
            try:
                return await self.processor.get_current_tasks()
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/automation/rules")
        async def get_automation_rules():
            """Get automation rules."""
            try:
                return await self.automation.get_rules()
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/automation/rules")
        async def add_automation_rule(rule: Dict):
            """Add automation rule."""
            try:
                return await self.automation.add_rule(rule)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    async def initialize(self):
        """Initialize the Task Agent."""
        await super().initialize()
        
        # Initialize components
        await self.processor.initialize()
        await self.store.initialize()
        await self.analyzer.initialize()
        await self.automation.initialize()
        
        # Connect to other agents
        await self._connect_to_agents()
        
        logger.info("Task Agent initialized")
    
    async def shutdown(self):
        """Shutdown the Task Agent."""
        await super().shutdown()
        
        # Shutdown components
        await self.processor.shutdown()
        await self.store.shutdown()
        await self.analyzer.shutdown()
        await self.automation.shutdown()
        
        logger.info("Task Agent shut down")
    
    async def _connect_to_agents(self):
        """Connect to other agents."""
        # Connect to Memory Agent
        memory_agent_url = settings.MEMORY_AGENT_URL
        await self._establish_connection("memory_agent", memory_agent_url)
        
        # Connect to Emotion Agent
        emotion_agent_url = settings.EMOTION_AGENT_URL
        await self._establish_connection("emotion_agent", emotion_agent_url)
    
    async def _process_messages(self):
        """Process incoming messages."""
        # Process messages from communication bus
        pass
    
    async def _update_state(self):
        """Update agent state."""
        # Update state with component statistics
        self.state.update({
            "current_tasks": await self.processor.get_current_tasks(),
            "task_count": await self.store.get_task_count(),
            "analysis": await self.analyzer.get_analysis(),
            "automation": await self.automation.get_stats(),
            "last_updated": datetime.utcnow().isoformat()
        })
    
    async def _process_tasks(self):
        """Process tasks based on incoming data."""
        # Process tasks and update state
        pass
    
    async def _maintain_connections(self):
        """Maintain connections with other agents."""
        # Maintain connections with other agents
        pass

# FastAPI application
app = FastAPI(
    title="Task Agent API",
    description="API for the Task Agent in the Virtual Brain System",
    version="1.0.0"
)

# Global agent instance
task_agent = None

@app.on_event("startup")
async def startup_event():
    """Initialize the task agent on startup."""
    global task_agent
    task_agent = TaskAgent()
    await task_agent.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown the task agent on shutdown."""
    if task_agent:
        await task_agent.shutdown()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.TASK_AGENT_HOST,
        port=settings.TASK_AGENT_PORT,
        reload=settings.DEBUG
    ) 