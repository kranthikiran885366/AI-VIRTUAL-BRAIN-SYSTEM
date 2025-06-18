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
from .emotion_processor import EmotionProcessor
from .emotion_store import EmotionStore
from .emotion_analyzer import EmotionAnalyzer
from .emotion_automation import EmotionAutomation

logger = get_logger()

class EmotionData(BaseModel):
    """Emotion data model."""
    type: str
    intensity: float
    source: str
    context: Dict[str, Any] = {}
    tags: List[str] = []
    priority: int = 0
    metadata: Dict[str, Any] = {}

class EmotionQuery(BaseModel):
    """Emotion query model."""
    type: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[int] = None
    created_before: Optional[str] = None
    created_after: Optional[str] = None

class EmotionAgent(BaseAgent):
    """Emotion Agent for managing and processing emotions."""
    
    def __init__(self):
        """Initialize the Emotion Agent."""
        super().__init__(
            agent_id=str(uuid.uuid4()),
            agent_type="emotion",
            state={},
            memory=[],
            emotions={},
            connections=[]
        )
        
        # Initialize components
        self.processor = EmotionProcessor()
        self.store = EmotionStore()
        self.analyzer = EmotionAnalyzer()
        self.automation = EmotionAutomation()
        
        # Create FastAPI app
        self.app = FastAPI(title="Emotion Agent API")
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up API routes."""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "agent_id": self.agent_id}
        
        @self.app.get("/stats")
        async def get_stats():
            """Get emotion statistics."""
            return {
                "processor": await self.processor.get_stats(),
                "store": await self.store.get_stats(),
                "analyzer": await self.analyzer.get_stats(),
                "automation": await self.automation.get_stats()
            }
        
        @self.app.post("/emotions")
        async def create_emotion(emotion: EmotionData):
            """Create a new emotion."""
            try:
                # Process emotion
                processed_emotion = await self.processor.process_emotion(emotion.dict())
                
                # Store emotion
                emotion_id = await self.store.store_emotion(processed_emotion)
                
                # Analyze emotion
                analysis = await self.analyzer.analyze_emotion(processed_emotion)
                
                # Queue emotion for automation
                await self.automation._emotion_queue.put(processed_emotion)
                
                # Update agent state
                await self._update_state()
                
                return {
                    "emotion_id": emotion_id,
                    "analysis": analysis
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/emotions/{emotion_id}")
        async def get_emotion(emotion_id: str):
            """Get a specific emotion."""
            try:
                emotion = await self.store.get_emotion(emotion_id)
                if not emotion:
                    raise HTTPException(status_code=404, detail="Emotion not found")
                return emotion
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/emotions/search")
        async def search_emotions(query: EmotionQuery):
            """Search emotions."""
            try:
                return await self.store.search_emotions(query.dict(exclude_none=True))
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
        """Initialize the Emotion Agent."""
        await super().initialize()
        
        # Initialize components
        await self.processor.initialize()
        await self.store.initialize()
        await self.analyzer.initialize()
        await self.automation.initialize()
        
        # Connect to other agents
        await self._connect_to_agents()
        
        logger.info("Emotion Agent initialized")
    
    async def shutdown(self):
        """Shutdown the Emotion Agent."""
        await super().shutdown()
        
        # Shutdown components
        await self.processor.shutdown()
        await self.store.shutdown()
        await self.analyzer.shutdown()
        await self.automation.shutdown()
        
        logger.info("Emotion Agent shut down")
    
    async def _connect_to_agents(self):
        """Connect to other agents."""
        # Connect to Task Agent
        task_agent_url = settings.TASK_AGENT_URL
        await self._establish_connection("task_agent", task_agent_url)
        
        # Connect to Memory Agent
        memory_agent_url = settings.MEMORY_AGENT_URL
        await self._establish_connection("memory_agent", memory_agent_url)
    
    async def _process_messages(self):
        """Process incoming messages."""
        # Process messages from communication bus
        pass
    
    async def _update_state(self):
        """Update agent state."""
        # Update state with component statistics
        self.state.update({
            "emotion_count": await self.store.get_emotion_count(),
            "analysis": await self.analyzer.get_analysis(),
            "automation": await self.automation.get_stats(),
            "last_updated": datetime.utcnow().isoformat()
        })
    
    async def _process_emotions(self):
        """Process emotions based on incoming data."""
        # Process emotions and update state
        pass
    
    async def _maintain_connections(self):
        """Maintain connections with other agents."""
        # Maintain connections with other agents
        pass

# FastAPI application
app = FastAPI(
    title="Emotion Agent API",
    description="API for the Emotion Agent in the Virtual Brain System",
    version="1.0.0"
)

# Global agent instance
emotion_agent = None

@app.on_event("startup")
async def startup_event():
    """Initialize the emotion agent on startup."""
    global emotion_agent
    emotion_agent = EmotionAgent()
    await emotion_agent.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown the emotion agent on shutdown."""
    if emotion_agent:
        await emotion_agent.shutdown()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.EMOTION_AGENT_HOST,
        port=settings.EMOTION_AGENT_PORT,
        reload=settings.DEBUG
    ) 