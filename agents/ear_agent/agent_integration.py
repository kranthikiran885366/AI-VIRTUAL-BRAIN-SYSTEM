import logging
import json
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional, Tuple
import yaml
from pathlib import Path

class AgentIntegration:
    def __init__(self, config_path: str = "config/ear_agent_config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.integration_config = self.config.get("agent_integration", {})
        
        # Initialize integration parameters
        self.brain_endpoint = self.integration_config.get("brain_endpoint", "http://localhost:5000")
        self.emotion_endpoint = self.integration_config.get("emotion_endpoint", "http://localhost:5001")
        self.memory_endpoint = self.integration_config.get("memory_endpoint", "http://localhost:5002")
        self.personality_endpoint = self.integration_config.get("personality_endpoint", "http://localhost:5003")
        
        # Initialize state
        self.session = None
        self.is_connected = False
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return yaml.safe_load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}
    
    async def initialize(self):
        """Initialize integration with other agents"""
        try:
            # Create aiohttp session
            self.session = aiohttp.ClientSession()
            self.is_connected = True
            self.logger.info("Initialized agent integration")
        
        except Exception as e:
            self.logger.error(f"Error initializing agent integration: {e}")
            await self.cleanup()
            raise
    
    async def notify_brain(self, event_type: str, data: Dict[str, Any]):
        """Notify Brain Agent of an event"""
        try:
            if not self.is_connected:
                raise RuntimeError("Not connected to agents")
            
            # Prepare event data
            event = {
                "type": event_type,
                "data": data,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Send event to Brain Agent
            async with self.session.post(
                f"{self.brain_endpoint}/events",
                json=event
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Brain Agent error: {await response.text()}")
                
                return await response.json()
        
        except Exception as e:
            self.logger.error(f"Error notifying Brain Agent: {e}")
            return None
    
    async def get_emotion_context(self) -> Optional[Dict[str, Any]]:
        """Get current emotional context from Emotion Agent"""
        try:
            if not self.is_connected:
                raise RuntimeError("Not connected to agents")
            
            # Get emotional context
            async with self.session.get(
                f"{self.emotion_endpoint}/context"
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Emotion Agent error: {await response.text()}")
                
                return await response.json()
        
        except Exception as e:
            self.logger.error(f"Error getting emotional context: {e}")
            return None
    
    async def get_memory_context(self, query: str) -> Optional[Dict[str, Any]]:
        """Get relevant memory context from Memory Agent"""
        try:
            if not self.is_connected:
                raise RuntimeError("Not connected to agents")
            
            # Get memory context
            async with self.session.post(
                f"{self.memory_endpoint}/query",
                json={"query": query}
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Memory Agent error: {await response.text()}")
                
                return await response.json()
        
        except Exception as e:
            self.logger.error(f"Error getting memory context: {e}")
            return None
    
    async def get_personality_traits(self) -> Optional[Dict[str, Any]]:
        """Get personality traits from Personality Agent"""
        try:
            if not self.is_connected:
                raise RuntimeError("Not connected to agents")
            
            # Get personality traits
            async with self.session.get(
                f"{self.personality_endpoint}/traits"
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Personality Agent error: {await response.text()}")
                
                return await response.json()
        
        except Exception as e:
            self.logger.error(f"Error getting personality traits: {e}")
            return None
    
    async def update_agent_status(self, status: Dict[str, Any]):
        """Update status with other agents"""
        try:
            if not self.is_connected:
                raise RuntimeError("Not connected to agents")
            
            # Update status with Brain Agent
            async with self.session.post(
                f"{self.brain_endpoint}/status",
                json=status
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Brain Agent error: {await response.text()}")
                
                return await response.json()
        
        except Exception as e:
            self.logger.error(f"Error updating agent status: {e}")
            return None
    
    async def get_agent_health(self) -> Dict[str, Any]:
        """Get health status of all agents"""
        try:
            if not self.is_connected:
                raise RuntimeError("Not connected to agents")
            
            # Check health of all agents
            health = {}
            
            # Check Brain Agent
            async with self.session.get(f"{self.brain_endpoint}/health") as response:
                health["brain"] = response.status == 200
            
            # Check Emotion Agent
            async with self.session.get(f"{self.emotion_endpoint}/health") as response:
                health["emotion"] = response.status == 200
            
            # Check Memory Agent
            async with self.session.get(f"{self.memory_endpoint}/health") as response:
                health["memory"] = response.status == 200
            
            # Check Personality Agent
            async with self.session.get(f"{self.personality_endpoint}/health") as response:
                health["personality"] = response.status == 200
            
            return health
        
        except Exception as e:
            self.logger.error(f"Error getting agent health: {e}")
            return {}
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.session:
                await self.session.close()
            
            self.is_connected = False
            self.logger.info("Cleaned up agent integration")
        
        except Exception as e:
            self.logger.error(f"Error cleaning up agent integration: {e}")
            raise

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test agent integration
    async def test_integration():
        integration = AgentIntegration()
        try:
            # Initialize integration
            await integration.initialize()
            
            # Test notifying Brain Agent
            result = await integration.notify_brain("test", {"message": "Hello"})
            print("\nBrain Agent notification result:")
            print(json.dumps(result, indent=2))
            
            # Test getting emotional context
            context = await integration.get_emotion_context()
            print("\nEmotional context:")
            print(json.dumps(context, indent=2))
            
            # Test getting memory context
            memory = await integration.get_memory_context("test query")
            print("\nMemory context:")
            print(json.dumps(memory, indent=2))
            
            # Test getting personality traits
            traits = await integration.get_personality_traits()
            print("\nPersonality traits:")
            print(json.dumps(traits, indent=2))
            
            # Test updating agent status
            status = await integration.update_agent_status({"status": "running"})
            print("\nAgent status update result:")
            print(json.dumps(status, indent=2))
            
            # Test getting agent health
            health = await integration.get_agent_health()
            print("\nAgent health:")
            print(json.dumps(health, indent=2))
        
        finally:
            await integration.cleanup()
    
    asyncio.run(test_integration()) 