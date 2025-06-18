from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import logging

from .auth import get_current_user
from .schemas import (
    User,
    AgentRequest,
    AgentResponse,
    SystemStatus,
    TaskRequest,
    TaskResponse,
    AgentStatus,
    AgentConfig
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Agent registry
AGENT_REGISTRY = {
    "memory_agent": {"status": "operational", "type": "core"},
    "emotion_agent": {"status": "operational", "type": "core"},
    "task_agent": {"status": "operational", "type": "core"},
    "learning_agent": {"status": "operational", "type": "core"},
    "social_agent": {"status": "operational", "type": "core"},
    "perception_agent": {"status": "operational", "type": "core"},
    "creativity_agent": {"status": "operational", "type": "core"},
    "self_reflection_agent": {"status": "operational", "type": "core"},
    "attention_agent": {"status": "operational", "type": "core"},
    "motor_control_agent": {"status": "operational", "type": "core"},
    "language_agent": {"status": "operational", "type": "core"},
    "planning_agent": {"status": "operational", "type": "core"},
    "motivation_agent": {"status": "operational", "type": "core"},
    "intuition_agent": {"status": "operational", "type": "core"},
    "sleep_rest_agent": {"status": "operational", "type": "core"},
    "pain_discomfort_agent": {"status": "operational", "type": "core"},
    "ethics_morality_agent": {"status": "operational", "type": "core"},
    "humor_agent": {"status": "operational", "type": "core"},
    "spatial_agent": {"status": "operational", "type": "core"},
    "sensory_integration_agent": {"status": "operational", "type": "core"},
    "language_production_agent": {"status": "operational", "type": "core"},
    "executive_function_agent": {"status": "operational", "type": "core"},
    "stress_anxiety_agent": {"status": "operational", "type": "core"},
    "trust_relationship_agent": {"status": "operational", "type": "core"},
    "creativity_control_agent": {"status": "operational", "type": "core"},
    "sensory_memory_agent": {"status": "operational", "type": "core"},
    "body_awareness_agent": {"status": "operational", "type": "core"},
    "eyes_agent": {"status": "operational", "type": "core"}
}

async def execute_agent_task(agent_name: str, request: AgentRequest) -> Dict[str, Any]:
    """Execute an agent task asynchronously."""
    try:
        # Simulate agent execution
        await asyncio.sleep(1)  # Simulate processing time
        return {
            "status": "success",
            "agent_name": agent_name,
            "result": {"message": f"Agent {agent_name} executed successfully"},
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error executing agent {agent_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents/{agent_name}/execute", response_model=AgentResponse)
async def execute_agent(
    agent_name: str,
    request: AgentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
) -> AgentResponse:
    """Execute an agent with the given parameters."""
    if agent_name not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    
    try:
        # Add task to background tasks
        background_tasks.add_task(execute_agent_task, agent_name, request)
        
        return AgentResponse(
            status="processing",
            agent_name=agent_name,
            result={"message": f"Agent {agent_name} execution started"},
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error starting agent {agent_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system/status", response_model=SystemStatus)
async def get_system_status(
    current_user: User = Depends(get_current_user)
) -> SystemStatus:
    """Get the current status of all system components."""
    try:
        return SystemStatus(
            status="operational",
            components={
                "orchestrator": "operational",
                "communication_bus": "operational",
                "agents": {name: info["status"] for name, info in AGENT_REGISTRY.items()}
            },
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks", response_model=TaskResponse)
async def create_task(
    task: TaskRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
) -> TaskResponse:
    """Create a new task in the system."""
    try:
        # Generate unique task ID
        task_id = f"task_{datetime.utcnow().timestamp()}"
        
        # Add task to background tasks
        background_tasks.add_task(execute_agent_task, task.agent_name, task.request)
        
        return TaskResponse(
            task_id=task_id,
            status="created",
            message="Task created successfully",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> TaskResponse:
    """Get the status of a specific task."""
    try:
        # This is a placeholder - implement actual task status checking
        return TaskResponse(
            task_id=task_id,
            status="in_progress",
            message="Task is being processed",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        raise HTTPException(status_code=404, detail="Task not found")

@router.get("/agents", response_model=List[str])
async def list_agents(
    current_user: User = Depends(get_current_user)
) -> List[str]:
    """List all available agents in the system."""
    return list(AGENT_REGISTRY.keys())

@router.get("/agents/{agent_name}/status", response_model=AgentStatus)
async def get_agent_status(
    agent_name: str,
    current_user: User = Depends(get_current_user)
) -> AgentStatus:
    """Get the status of a specific agent."""
    if agent_name not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    
    return AgentStatus(
        name=agent_name,
        status=AGENT_REGISTRY[agent_name]["status"],
        type=AGENT_REGISTRY[agent_name]["type"],
        timestamp=datetime.utcnow().isoformat()
    )

@router.put("/agents/{agent_name}/config", response_model=AgentConfig)
async def update_agent_config(
    agent_name: str,
    config: AgentConfig,
    current_user: User = Depends(get_current_user)
) -> AgentConfig:
    """Update the configuration of a specific agent."""
    if agent_name not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    
    try:
        # Update agent configuration
        # This is a placeholder - implement actual config update
        return config
    except Exception as e:
        logger.error(f"Error updating agent config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 