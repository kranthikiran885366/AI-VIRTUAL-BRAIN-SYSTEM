import asyncio
import logging
import os
import signal
import sys
from typing import Dict, List, Optional, Any
import yaml
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from prometheus_client import make_asgi_app
from structlog import get_logger

from .agent_manager import AgentManager
from .communication_controller import CommunicationController
from .decision_engine import DecisionEngine
from .task_scheduler import TaskScheduler
from .health_monitor import HealthMonitor
from .config import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load settings
settings = Settings()

# Create FastAPI app
app = FastAPI(
    title="Virtual Brain Orchestrator",
    description="Orchestrator for the Virtual Brain System",
    version="1.0.0",
)

# Add Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

class Orchestrator:
    """Main orchestrator class for managing the virtual brain system."""
    
    def __init__(self, config_path: str = "config/orchestrator_config.yaml"):
        """Initialize the orchestrator with configuration."""
        self.config = self._load_config(config_path)
        self.agent_manager = AgentManager(self.config["agents"])
        self.communication_controller = CommunicationController(self.config["communication"])
        self.decision_engine = DecisionEngine(self.config["decision"])
        self.task_scheduler = TaskScheduler(self.config["scheduler"])
        self.health_monitor = HealthMonitor(self.config["health"])
        
        self.is_running = False
        self.tasks = {}
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    async def start(self):
        """Start the orchestrator and all its components."""
        logger.info("Starting orchestrator...")
        self.is_running = True
        
        # Start components
        await self.agent_manager.start()
        await self.communication_controller.start()
        await self.decision_engine.start()
        await self.task_scheduler.start()
        await self.health_monitor.start()
        
        logger.info("Orchestrator started successfully")
    
    async def stop(self):
        """Stop the orchestrator and all its components."""
        logger.info("Stopping orchestrator...")
        self.is_running = False
        
        # Stop components
        await self.agent_manager.stop()
        await self.communication_controller.stop()
        await self.decision_engine.stop()
        await self.task_scheduler.stop()
        await self.health_monitor.stop()
        
        logger.info("Orchestrator stopped successfully")
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a new task."""
        try:
            # Schedule the task
            task_id = await self.task_scheduler.schedule_task(task)
            
            # Get decision from decision engine
            decision = await self.decision_engine.make_decision(task)
            
            # Assign task to appropriate agent
            agent = await self.agent_manager.get_agent(decision["agent_name"])
            result = await agent.execute_task(task)
            
            # Update task status
            await self.task_scheduler.update_task_status(task_id, "completed", result)
            
            return {
                "status": "success",
                "task_id": task_id,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error processing task: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get the current status of all system components."""
        return {
            "status": "operational" if self.is_running else "stopped",
            "components": {
                "agent_manager": await self.agent_manager.get_status(),
                "communication_controller": await self.communication_controller.get_status(),
                "decision_engine": await self.decision_engine.get_status(),
                "task_scheduler": await self.task_scheduler.get_status(),
                "health_monitor": await self.health_monitor.get_status()
            }
        }

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting up Orchestrator...")
    
    orchestrator = Orchestrator()
    
    # Initialize components
    await orchestrator.agent_manager.initialize()
    await orchestrator.communication_controller.initialize()
    await orchestrator.decision_engine.initialize()
    await orchestrator.task_scheduler.initialize()
    await orchestrator.health_monitor.initialize()
    
    # Start background tasks
    asyncio.create_task(orchestrator.agent_manager.monitor_agents())
    asyncio.create_task(orchestrator.communication_controller.process_messages())
    asyncio.create_task(orchestrator.decision_engine.process_decisions())
    asyncio.create_task(orchestrator.task_scheduler.process_tasks())
    asyncio.create_task(orchestrator.health_monitor.monitor_health())

    try:
        await orchestrator.start()
        
        # Keep the orchestrator running
        while orchestrator.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        await orchestrator.stop()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Orchestrator...")
    
    # Stop background tasks
    await orchestrator.agent_manager.shutdown()
    await orchestrator.communication_controller.shutdown()
    await orchestrator.decision_engine.shutdown()
    await orchestrator.task_scheduler.shutdown()
    await orchestrator.health_monitor.shutdown()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    orchestrator = Orchestrator()
    return await orchestrator.get_system_status()

@app.get("/agents")
async def list_agents():
    """List all agents."""
    orchestrator = Orchestrator()
    return await orchestrator.agent_manager.list_agents()

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent by ID."""
    orchestrator = Orchestrator()
    agent = await orchestrator.agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.post("/agents/{agent_id}/start")
async def start_agent(agent_id: str):
    """Start an agent."""
    orchestrator = Orchestrator()
    success = await orchestrator.agent_manager.start_agent(agent_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to start agent")
    return {"status": "started"}

@app.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    """Stop an agent."""
    orchestrator = Orchestrator()
    success = await orchestrator.agent_manager.stop_agent(agent_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to stop agent")
    return {"status": "stopped"}

@app.get("/tasks")
async def list_tasks():
    """List all tasks."""
    orchestrator = Orchestrator()
    return await orchestrator.task_scheduler.list_tasks()

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task by ID."""
    orchestrator = Orchestrator()
    task = await orchestrator.task_scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/tasks")
async def create_task(task: dict):
    """Create a new task."""
    orchestrator = Orchestrator()
    task_id = await orchestrator.task_scheduler.create_task(task)
    return {"task_id": task_id}

def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    sys.exit(0)

def start():
    """Start the Orchestrator server."""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Start the server
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )

if __name__ == "__main__":
    start() 