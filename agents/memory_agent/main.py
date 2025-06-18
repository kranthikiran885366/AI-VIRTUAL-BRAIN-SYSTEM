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
from .memory_processor import MemoryProcessor
from .memory_store import MemoryStore
from .memory_analyzer import MemoryAnalyzer
from .memory_automation import MemoryAutomation

logger = get_logger()

class MemoryData(BaseModel):
    """Memory data model."""
    content: str
    type: str
    source: str
    context: Dict[str, Any] = {}
    tags: List[str] = []
    priority: int = 0
    metadata: Dict[str, Any] = {}

class MemoryQuery(BaseModel):
    """Memory query model."""
    type: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[int] = None
    created_before: Optional[str] = None
    created_after: Optional[str] = None

class MemoryAgent(BaseAgent):
    """Memory Agent for managing and processing memories."""
    
    def __init__(self):
        """Initialize the Memory Agent."""
        super().__init__(
            agent_id=str(uuid.uuid4()),
            agent_type="memory",
            state={},
            memory=[],
            emotions={},
            connections=[]
        )
        
        # Initialize components
        self.processor = MemoryProcessor()
        self.store = MemoryStore()
        self.analyzer = MemoryAnalyzer()
        self.automation = MemoryAutomation()
        
        # Create FastAPI app
        self.app = FastAPI(title="Memory Agent API")
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up API routes."""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "agent_id": self.agent_id}
        
        @self.app.get("/stats")
        async def get_stats():
            """Get memory statistics."""
            return {
                "processor": await self.processor.get_stats(),
                "store": await self.store.get_stats(),
                "analyzer": await self.analyzer.get_stats(),
                "automation": await self.automation.get_stats()
            }
        
        @self.app.post("/memories")
        async def create_memory(memory: MemoryData):
            """Create a new memory."""
            try:
                # Process memory
                processed_memory = await self.processor.process_memory(memory.dict())
                
                # Store memory
                memory_id = await self.store.store_memory(processed_memory)
                
                # Analyze memory
                analysis = await self.analyzer.analyze_memory(processed_memory)
                
                # Queue memory for automation
                await self.automation._memory_queue.put(processed_memory)
                
                # Update agent state
                await self._update_state()
                
                return {
                    "memory_id": memory_id,
                    "analysis": analysis
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/memories/{memory_id}")
        async def get_memory(memory_id: str):
            """Get a specific memory."""
            try:
                memory = await self.store.get_memory(memory_id)
                if not memory:
                    raise HTTPException(status_code=404, detail="Memory not found")
                return memory
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/memories/search")
        async def search_memories(query: MemoryQuery):
            """Search memories."""
            try:
                return await self.store.search_memories(query.dict(exclude_none=True))
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
        
        @self.app.get("/automation/rules/{rule_id}")
        async def get_automation_rule(rule_id: str):
            """Get specific automation rule."""
            try:
                return await self.automation.get_rule(rule_id)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/automation/rules/{rule_id}")
        async def update_automation_rule(rule_id: str, rule: Dict):
            """Update automation rule."""
            try:
                await self.automation.update_rule(rule_id, rule)
                return {"status": "success"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/automation/rules/{rule_id}")
        async def delete_automation_rule(rule_id: str):
            """Delete automation rule."""
            try:
                await self.automation.delete_rule(rule_id)
                return {"status": "success"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/automation/history")
        async def get_automation_history():
            """Get automation execution history."""
            try:
                return await self.automation.get_execution_history()
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    async def initialize(self):
        """Initialize the Memory Agent."""
        await super().initialize()
        
        # Initialize components
        await self.processor.initialize()
        await self.store.initialize()
        await self.analyzer.initialize()
        await self.automation.initialize()
        
        # Connect to other agents
        await self._connect_to_agents()
        
        logger.info("Memory Agent initialized")
    
    async def shutdown(self):
        """Shutdown the Memory Agent."""
        await super().shutdown()
        
        # Shutdown components
        await self.processor.shutdown()
        await self.store.shutdown()
        await self.analyzer.shutdown()
        await self.automation.shutdown()
        
        logger.info("Memory Agent shut down")
    
    async def _connect_to_agents(self):
        """Connect to other agents."""
        # Connect to Task Agent
        task_agent_url = settings.TASK_AGENT_URL
        await self._establish_connection("task_agent", task_agent_url)
        
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
            "memory_count": await self.store.get_memory_count(),
            "analysis": await self.analyzer.get_analysis(),
            "automation": await self.automation.get_stats(),
            "last_updated": datetime.utcnow().isoformat()
        })
    
    async def _process_memories(self):
        """Process memories based on incoming data."""
        # Process memories and update state
        pass
    
    async def _maintain_connections(self):
        """Maintain connections with other agents."""
        # Maintain connections with other agents
        pass

# FastAPI application
app = FastAPI(
    title="Memory Agent API",
    description="API for the Memory Agent in the Virtual Brain System",
    version="1.0.0"
)

# Global agent instance
memory_agent = None

@app.on_event("startup")
async def startup_event():
    """Initialize the memory agent on startup."""
    global memory_agent
    memory_agent = MemoryAgent()
    await memory_agent.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown the memory agent on shutdown."""
    if memory_agent:
        await memory_agent.shutdown()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.MEMORY_AGENT_HOST,
        port=settings.MEMORY_AGENT_PORT,
        reload=settings.DEBUG
    ) 