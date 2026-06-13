"""
Agent Lifecycle Manager

Manages the complete lifecycle of agents:
- Initialization and dependency injection
- Health monitoring and recovery
- State persistence
- Graceful shutdown
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from structlog import get_logger

from .agent_communication import (
    get_message_broker,
    Message,
    MessageType,
    MessagePriority,
)

logger = get_logger()


@dataclass
class AgentHealthStatus:
    """Health status of an agent."""
    agent_id: str
    is_healthy: bool
    last_heartbeat: str
    error_count: int
    message_queue_size: int
    memory_usage: float
    uptime_seconds: float
    status: str  # "healthy", "degraded", "unhealthy", "recovering"


class AgentLifecycleManager:
    """
    Manages agent lifecycle events and health monitoring.
    Ensures all agents are properly initialized, monitored, and shutdown.
    """
    
    def __init__(self):
        """Initialize the lifecycle manager."""
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.agent_health: Dict[str, AgentHealthStatus] = {}
        self.message_broker = get_message_broker()
        self.is_running = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._recovery_task: Optional[asyncio.Task] = None
        self.health_check_interval = 30  # seconds
        self.heartbeat_timeout = 60  # seconds
        self.max_errors = 10
    
    async def start(self):
        """Start the lifecycle manager."""
        logger.info("Starting agent lifecycle manager...")
        self.is_running = True
        
        # Start health monitoring
        self._health_check_task = asyncio.create_task(self._health_monitor())
        
        # Start recovery mechanism
        self._recovery_task = asyncio.create_task(self._recovery_loop())
        
        logger.info("Agent lifecycle manager started")
    
    async def stop(self):
        """Stop the lifecycle manager."""
        logger.info("Stopping agent lifecycle manager...")
        self.is_running = False
        
        # Cancel tasks
        if self._health_check_task:
            self._health_check_task.cancel()
        if self._recovery_task:
            self._recovery_task.cancel()
        
        # Wait for cancellation
        try:
            if self._health_check_task:
                await self._health_check_task
            if self._recovery_task:
                await self._recovery_task
        except asyncio.CancelledError:
            pass
        
        logger.info("Agent lifecycle manager stopped")
    
    async def register_agent(
        self,
        agent_id: str,
        agent_type: str,
        agent_instance: Any,
        dependencies: Optional[Dict[str, str]] = None
    ):
        """Register an agent with the lifecycle manager."""
        self.agents[agent_id] = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "instance": agent_instance,
            "dependencies": dependencies or {},
            "created_at": datetime.utcnow().isoformat(),
            "last_heartbeat": datetime.utcnow().isoformat(),
            "error_count": 0,
            "is_running": False,
        }
        
        # Initialize health status
        self.agent_health[agent_id] = AgentHealthStatus(
            agent_id=agent_id,
            is_healthy=True,
            last_heartbeat=datetime.utcnow().isoformat(),
            error_count=0,
            message_queue_size=0,
            memory_usage=0.0,
            uptime_seconds=0.0,
            status="initialized"
        )
        
        logger.info(f"Agent {agent_id} registered: {agent_type}")
    
    async def initialize_agent(self, agent_id: str) -> bool:
        """Initialize an agent."""
        agent_info = self.agents.get(agent_id)
        if not agent_info:
            logger.error(f"Agent {agent_id} not found")
            return False
        
        try:
            # Check dependencies
            for dep_id, dep_type in agent_info["dependencies"].items():
                dep_agent = self.agents.get(dep_id)
                if not dep_agent or not dep_agent["is_running"]:
                    logger.warning(f"Dependency {dep_id} not ready for {agent_id}")
                    # Could queue for retry or handle gracefully
            
            # Initialize the agent
            agent = agent_info["instance"]
            if hasattr(agent, "initialize"):
                await agent.initialize()
            
            # Register with message broker
            await self.message_broker.register_agent(agent_id)
            
            # Mark as running
            agent_info["is_running"] = True
            self.agent_health[agent_id].status = "healthy"
            
            logger.info(f"Agent {agent_id} initialized successfully")
            return True
        
        except Exception as e:
            logger.error(f"Failed to initialize agent {agent_id}: {e}")
            self.agents[agent_id]["error_count"] += 1
            self.agent_health[agent_id].status = "unhealthy"
            return False
    
    async def start_agent(self, agent_id: str) -> bool:
        """Start an agent."""
        agent_info = self.agents.get(agent_id)
        if not agent_info:
            logger.error(f"Agent {agent_id} not found")
            return False
        
        if agent_info["is_running"]:
            logger.warning(f"Agent {agent_id} already running")
            return True
        
        try:
            agent = agent_info["instance"]
            if hasattr(agent, "start"):
                await agent.start()
            
            agent_info["is_running"] = True
            self.agent_health[agent_id].status = "healthy"
            self.agent_health[agent_id].last_heartbeat = datetime.utcnow().isoformat()
            
            logger.info(f"Agent {agent_id} started")
            return True
        
        except Exception as e:
            logger.error(f"Failed to start agent {agent_id}: {e}")
            agent_info["error_count"] += 1
            self.agent_health[agent_id].status = "unhealthy"
            return False
    
    async def stop_agent(self, agent_id: str) -> bool:
        """Stop an agent."""
        agent_info = self.agents.get(agent_id)
        if not agent_info:
            logger.error(f"Agent {agent_id} not found")
            return False
        
        try:
            agent = agent_info["instance"]
            if hasattr(agent, "stop"):
                await agent.stop()
            
            # Unregister from message broker
            await self.message_broker.unregister_agent(agent_id)
            
            agent_info["is_running"] = False
            self.agent_health[agent_id].status = "stopped"
            
            logger.info(f"Agent {agent_id} stopped")
            return True
        
        except Exception as e:
            logger.error(f"Failed to stop agent {agent_id}: {e}")
            return False
    
    async def record_heartbeat(self, agent_id: str):
        """Record a heartbeat from an agent."""
        if agent_id in self.agent_health:
            self.agent_health[agent_id].last_heartbeat = datetime.utcnow().isoformat()
            self.agents[agent_id]["last_heartbeat"] = datetime.utcnow().isoformat()
    
    async def record_error(self, agent_id: str, error: str):
        """Record an error for an agent."""
        if agent_id not in self.agents:
            return
        
        self.agents[agent_id]["error_count"] += 1
        self.agent_health[agent_id].error_count += 1
        
        # Degrade health if too many errors
        if self.agents[agent_id]["error_count"] >= self.max_errors:
            self.agent_health[agent_id].status = "unhealthy"
            logger.warning(f"Agent {agent_id} marked unhealthy due to error count")
        elif self.agents[agent_id]["error_count"] >= self.max_errors // 2:
            self.agent_health[agent_id].status = "degraded"
    
    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of an agent."""
        if agent_id not in self.agents:
            return None
        
        agent_info = self.agents[agent_id]
        health = self.agent_health.get(agent_id)
        
        created_at = datetime.fromisoformat(agent_info["created_at"])
        uptime = (datetime.utcnow() - created_at).total_seconds()
        
        return {
            "agent_id": agent_id,
            "agent_type": agent_info["agent_type"],
            "is_running": agent_info["is_running"],
            "status": health.status if health else "unknown",
            "error_count": agent_info["error_count"],
            "last_heartbeat": agent_info["last_heartbeat"],
            "uptime_seconds": uptime,
            "health": {
                "is_healthy": health.is_healthy if health else False,
                "status": health.status if health else "unknown",
                "error_count": health.error_count if health else 0,
                "message_queue_size": health.message_queue_size if health else 0,
                "memory_usage": health.memory_usage if health else 0.0,
            } if health else None
        }
    
    async def get_all_agent_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all agents."""
        statuses = {}
        for agent_id in self.agents.keys():
            status = await self.get_agent_status(agent_id)
            if status:
                statuses[agent_id] = status
        return statuses
    
    async def _health_monitor(self):
        """Monitor health of all agents."""
        while self.is_running:
            try:
                current_time = datetime.utcnow()
                
                for agent_id, agent_info in self.agents.items():
                    if not agent_info["is_running"]:
                        continue
                    
                    health = self.agent_health.get(agent_id)
                    if not health:
                        continue
                    
                    # Check heartbeat timeout
                    last_heartbeat = datetime.fromisoformat(health.last_heartbeat)
                    time_since_heartbeat = (current_time - last_heartbeat).total_seconds()
                    
                    if time_since_heartbeat > self.heartbeat_timeout:
                        logger.warning(f"Agent {agent_id} missed heartbeat (no activity for {time_since_heartbeat:.1f}s)")
                        health.is_healthy = False
                        health.status = "unhealthy"
                    else:
                        health.is_healthy = True
                        if health.status == "unhealthy" or health.status == "recovering":
                            health.status = "healthy"
                
                await asyncio.sleep(self.health_check_interval)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(5)
    
    async def _recovery_loop(self):
        """Recovery mechanism for unhealthy agents."""
        while self.is_running:
            try:
                unhealthy_agents = [
                    agent_id for agent_id, health in self.agent_health.items()
                    if health.status == "unhealthy" and self.agents[agent_id]["is_running"]
                ]
                
                for agent_id in unhealthy_agents:
                    logger.info(f"Attempting recovery for agent {agent_id}")
                    self.agent_health[agent_id].status = "recovering"
                    
                    # Attempt restart
                    success = await self.restart_agent(agent_id)
                    if success:
                        logger.info(f"Successfully recovered agent {agent_id}")
                        self.agent_health[agent_id].status = "healthy"
                        self.agents[agent_id]["error_count"] = 0
                    else:
                        logger.warning(f"Recovery failed for agent {agent_id}")
                
                await asyncio.sleep(60)  # Check recovery every minute
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in recovery loop: {e}")
                await asyncio.sleep(5)
    
    async def restart_agent(self, agent_id: str) -> bool:
        """Restart an agent."""
        logger.info(f"Restarting agent {agent_id}")
        
        # Stop the agent
        await self.stop_agent(agent_id)
        
        # Reinitialize
        await asyncio.sleep(2)  # Wait before restart
        
        # Start again
        return await self.start_agent(agent_id)


# Global lifecycle manager instance
_lifecycle_manager: Optional[AgentLifecycleManager] = None


def get_lifecycle_manager() -> AgentLifecycleManager:
    """Get or create the global lifecycle manager."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = AgentLifecycleManager()
    return _lifecycle_manager


async def initialize_lifecycle_manager():
    """Initialize and start the lifecycle manager."""
    manager = get_lifecycle_manager()
    await manager.start()
    return manager


async def shutdown_lifecycle_manager():
    """Shutdown the lifecycle manager."""
    manager = get_lifecycle_manager()
    await manager.stop()
