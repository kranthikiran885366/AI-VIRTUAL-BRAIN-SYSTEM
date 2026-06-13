"""
API Integration Module

Provides HTTP API endpoints that the Next.js frontend can call to:
- Execute agent operations
- Query agent status
- Send tasks to agents
- Retrieve memories and results
- Monitor system health
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel
import uvicorn

from .agent_manager import AgentManager
from .agent_communication import get_message_broker, MessageType, MessagePriority
from .agent_lifecycle import get_lifecycle_manager

logger = logging.getLogger(__name__)


class ExecuteAgentRequest(BaseModel):
    """Request to execute an agent."""
    agent_name: str
    action: str
    input_data: Dict[str, Any]
    priority: str = "normal"
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None


class SendMessageRequest(BaseModel):
    """Request to send a message between agents."""
    sender_agent_id: str
    recipient_agent_id: str
    message_type: str
    content: Dict[str, Any]
    priority: str = "normal"


class BroadcastMessageRequest(BaseModel):
    """Request to broadcast a message."""
    sender_agent_id: str
    message_type: str
    content: Dict[str, Any]
    priority: str = "normal"


class TaskRequest(BaseModel):
    """Request to create a task for an agent."""
    agent_name: str
    task_type: str
    description: str
    priority: str = "normal"
    user_id: Optional[str] = None
    context: Dict[str, Any] = {}


class APIIntegration:
    """
    API Integration service for frontend-backend communication.
    Provides REST endpoints and WebSocket support for real-time communication.
    """
    
    def __init__(self, agent_manager: AgentManager, port: int = 8001):
        """Initialize the API integration."""
        self.agent_manager = agent_manager
        self.message_broker = get_message_broker()
        self.lifecycle_manager = get_lifecycle_manager()
        self.port = port
        
        # Create FastAPI app
        self.app = FastAPI(
            title="Virtual Brain API Integration",
            description="Frontend integration API for the Virtual Brain System",
            version="1.0.0"
        )
        
        # Register routes
        self._register_routes()
    
    def _register_routes(self):
        """Register API routes."""
        
        @self.app.on_event("startup")
        async def startup():
            logger.info("API Integration starting...")
            await self.message_broker.start()
            await self.lifecycle_manager.start()
        
        @self.app.on_event("shutdown")
        async def shutdown():
            logger.info("API Integration shutting down...")
            await self.lifecycle_manager.stop()
            await self.message_broker.stop()
        
        # Health check endpoints
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            try:
                statuses = await self.lifecycle_manager.get_all_agent_statuses()
                healthy_agents = sum(1 for s in statuses.values() if s.get("is_running"))
                
                return {
                    "status": "operational" if healthy_agents > 0 else "degraded",
                    "timestamp": datetime.utcnow().isoformat(),
                    "agents": {
                        "total": len(statuses),
                        "healthy": healthy_agents,
                        "unhealthy": len(statuses) - healthy_agents
                    },
                    "broker": await self.message_broker.get_stats()
                }
            except Exception as e:
                logger.error(f"Health check error: {e}")
                return {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        # Agent management endpoints
        @self.app.get("/agents")
        async def list_agents():
            """List all agents."""
            try:
                statuses = await self.lifecycle_manager.get_all_agent_statuses()
                return {
                    "agents": statuses,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/agents/{agent_id}/status")
        async def get_agent_status(agent_id: str):
            """Get status of a specific agent."""
            try:
                status = await self.lifecycle_manager.get_agent_status(agent_id)
                if not status:
                    raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
                return status
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/agents/{agent_id}/start")
        async def start_agent(agent_id: str):
            """Start a specific agent."""
            try:
                success = await self.lifecycle_manager.start_agent(agent_id)
                if not success:
                    raise HTTPException(status_code=400, detail=f"Failed to start agent {agent_id}")
                return {"status": "started", "agent_id": agent_id}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/agents/{agent_id}/stop")
        async def stop_agent(agent_id: str):
            """Stop a specific agent."""
            try:
                success = await self.lifecycle_manager.stop_agent(agent_id)
                if not success:
                    raise HTTPException(status_code=400, detail=f"Failed to stop agent {agent_id}")
                return {"status": "stopped", "agent_id": agent_id}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # Execute agent endpoints
        @self.app.post("/execute")
        async def execute_agent(request: ExecuteAgentRequest):
            """Execute an agent with the given action."""
            try:
                agent = await self.agent_manager.get_agent(request.agent_name)
                if not agent:
                    raise HTTPException(status_code=404, detail=f"Agent {request.agent_name} not found")
                
                # Create task for agent
                task = {
                    "id": str(uuid.uuid4()),
                    "agent_name": request.agent_name,
                    "action": request.action,
                    "input_data": request.input_data,
                    "user_id": request.user_id,
                    "conversation_id": request.conversation_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "pending"
                }
                
                # Execute the agent
                result = await agent.execute_task(task) if hasattr(agent, "execute_task") else {
                    "status": "completed",
                    "message": f"Agent {request.agent_name} executed {request.action}",
                    "task_id": task["id"]
                }
                
                return {
                    "status": "success",
                    "task_id": task["id"],
                    "agent": request.agent_name,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Agent execution error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Message endpoints
        @self.app.post("/messages/send")
        async def send_message(request: SendMessageRequest):
            """Send a message from one agent to another."""
            try:
                message_id = await self.message_broker.send_message(
                    sender_agent_id=request.sender_agent_id,
                    recipient_agent_id=request.recipient_agent_id,
                    message_type=MessageType[request.message_type.upper()],
                    content=request.content,
                    priority=MessagePriority[request.priority.upper()]
                )
                
                return {
                    "status": "sent",
                    "message_id": message_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except KeyError as e:
                raise HTTPException(status_code=400, detail=f"Invalid enum value: {e}")
            except Exception as e:
                logger.error(f"Message send error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/messages/broadcast")
        async def broadcast_message(request: BroadcastMessageRequest):
            """Broadcast a message from one agent to all agents."""
            try:
                message_id = await self.message_broker.send_message(
                    sender_agent_id=request.sender_agent_id,
                    recipient_agent_id=None,
                    message_type=MessageType[request.message_type.upper()],
                    content=request.content,
                    priority=MessagePriority[request.priority.upper()]
                )
                
                return {
                    "status": "broadcasted",
                    "message_id": message_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except KeyError as e:
                raise HTTPException(status_code=400, detail=f"Invalid enum value: {e}")
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Message history and queue endpoints
        @self.app.get("/messages/history")
        async def get_message_history(
            agent_id: Optional[str] = None,
            message_type: Optional[str] = None,
            limit: int = 100
        ):
            """Get message history."""
            try:
                msg_type = None
                if message_type:
                    msg_type = MessageType[message_type.upper()]
                
                history = await self.message_broker.get_message_history(
                    agent_id=agent_id,
                    message_type=msg_type,
                    limit=limit
                )
                
                return {
                    "messages": history,
                    "count": len(history),
                    "timestamp": datetime.utcnow().isoformat()
                }
            except KeyError as e:
                raise HTTPException(status_code=400, detail=f"Invalid message type: {e}")
            except Exception as e:
                logger.error(f"Message history error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/messages/queue/{agent_id}")
        async def get_agent_queue(agent_id: str, limit: int = 50):
            """Get pending messages for an agent."""
            try:
                messages = await self.message_broker.get_agent_messages(
                    agent_id=agent_id,
                    limit=limit
                )
                
                return {
                    "agent_id": agent_id,
                    "messages": [m.to_dict() for m in messages],
                    "count": len(messages),
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Queue retrieval error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # System stats endpoints
        @self.app.get("/stats")
        async def get_system_stats():
            """Get overall system statistics."""
            try:
                statuses = await self.lifecycle_manager.get_all_agent_statuses()
                broker_stats = await self.message_broker.get_stats()
                
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "agents": statuses,
                    "broker": broker_stats,
                    "summary": {
                        "total_agents": len(statuses),
                        "running_agents": sum(1 for s in statuses.values() if s.get("is_running")),
                        "healthy_agents": sum(1 for s in statuses.values() if s.get("status") == "healthy"),
                        "pending_messages": broker_stats.get("queue_size", 0),
                        "subscribed_message_types": len(broker_stats.get("message_types", []))
                    }
                }
            except Exception as e:
                logger.error(f"Stats error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def run(self, host: str = "0.0.0.0"):
        """Run the API server."""
        logger.info(f"Starting API Integration on {host}:{self.port}")
        uvicorn.run(self.app, host=host, port=self.port, log_level="info")


# Import uuid for task creation
import uuid
