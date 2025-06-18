import asyncio
import logging
from typing import Dict, Any, List, Optional
import importlib
from pathlib import Path

logger = logging.getLogger(__name__)

class AgentManager:
    """Manages the lifecycle and execution of all agents in the system."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the agent manager with configuration."""
        self.config = config
        self.agents: Dict[str, Any] = {}
        self.agent_status: Dict[str, str] = {}
        self.is_running = False
    
    async def start(self):
        """Start the agent manager."""
        logger.info("Starting agent manager...")
        self.is_running = True
        
        # Load and initialize all agents
        for agent_name, agent_config in self.config["agents"].items():
            try:
                await self.load_agent(agent_name, agent_config)
            except Exception as e:
                logger.error(f"Failed to load agent {agent_name}: {e}")
        
        logger.info("Agent manager started successfully")
    
    async def stop(self):
        """Stop the agent manager and all agents."""
        logger.info("Stopping agent manager...")
        self.is_running = False
        
        # Stop all agents
        for agent_name, agent in self.agents.items():
            try:
                await agent.stop()
                self.agent_status[agent_name] = "stopped"
            except Exception as e:
                logger.error(f"Error stopping agent {agent_name}: {e}")
        
        logger.info("Agent manager stopped successfully")
    
    async def load_agent(self, agent_name: str, agent_config: Dict[str, Any]) -> None:
        """Load and initialize an agent."""
        try:
            # Import agent module
            module_path = f"agents.{agent_name}.main"
            agent_module = importlib.import_module(module_path)
            
            # Create agent instance
            agent_class = getattr(agent_module, f"{agent_name.title()}Agent")
            agent = agent_class(agent_config)
            
            # Initialize agent
            await agent.initialize()
            
            # Store agent
            self.agents[agent_name] = agent
            self.agent_status[agent_name] = "initialized"
            
            logger.info(f"Agent {agent_name} loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load agent {agent_name}: {e}")
            raise
    
    async def get_agent(self, agent_name: str) -> Optional[Any]:
        """Get an agent by name."""
        return self.agents.get(agent_name)
    
    async def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents and their status."""
        return [
            {
                "name": name,
                "status": self.agent_status.get(name, "unknown"),
                "config": self.config["agents"].get(name, {})
            }
            for name in self.agents.keys()
        ]
    
    async def start_agent(self, agent_name: str) -> bool:
        """Start a specific agent."""
        agent = self.agents.get(agent_name)
        if not agent:
            logger.error(f"Agent {agent_name} not found")
            return False
        
        try:
            await agent.start()
            self.agent_status[agent_name] = "running"
            return True
        except Exception as e:
            logger.error(f"Failed to start agent {agent_name}: {e}")
            return False
    
    async def stop_agent(self, agent_name: str) -> bool:
        """Stop a specific agent."""
        agent = self.agents.get(agent_name)
        if not agent:
            logger.error(f"Agent {agent_name} not found")
            return False
        
        try:
            await agent.stop()
            self.agent_status[agent_name] = "stopped"
            return True
        except Exception as e:
            logger.error(f"Failed to stop agent {agent_name}: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the agent manager."""
        return {
            "status": "running" if self.is_running else "stopped",
            "agents": {
                name: {
                    "status": status,
                    "config": self.config["agents"].get(name, {})
                }
                for name, status in self.agent_status.items()
            }
        }
    
    async def monitor_agents(self):
        """Monitor the health and status of all agents."""
        while self.is_running:
            for agent_name, agent in self.agents.items():
                try:
                    # Check agent health
                    health = await agent.get_health()
                    if health["status"] != "healthy":
                        logger.warning(f"Agent {agent_name} health check failed: {health}")
                        # Attempt to restart unhealthy agent
                        await self.restart_agent(agent_name)
                except Exception as e:
                    logger.error(f"Error monitoring agent {agent_name}: {e}")
            
            await asyncio.sleep(self.config.get("monitor_interval", 30))
    
    async def restart_agent(self, agent_name: str) -> bool:
        """Restart a specific agent."""
        logger.info(f"Restarting agent {agent_name}")
        
        # Stop agent
        if not await self.stop_agent(agent_name):
            return False
        
        # Wait for agent to stop
        await asyncio.sleep(1)
        
        # Start agent
        return await self.start_agent(agent_name) 