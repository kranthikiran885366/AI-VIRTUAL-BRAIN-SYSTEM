import logging
from typing import Dict, Any, Optional, List
import aiohttp
import asyncio
from datetime import datetime

class AgentIntegration:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = None
        self.agent_endpoints = {
            "brain": "http://localhost:8001",  # Brain Agent endpoint
            "emotion": "http://localhost:8002",  # Emotion Agent endpoint
            "memory": "http://localhost:8003",  # Memory Agent endpoint
            "personality": "http://localhost:8004"  # Personality Agent endpoint
        }
        self.last_interaction = {}
        
    async def initialize(self):
        """Initialize HTTP session for agent communication"""
        try:
            self.session = aiohttp.ClientSession()
            self.logger.info("Agent integration initialized")
        except Exception as e:
            self.logger.error(f"Error initializing agent integration: {e}")
            raise

    async def get_emotion_context(self) -> Dict[str, Any]:
        """Get current emotional context from Emotion Agent"""
        try:
            if not self.session:
                await self.initialize()
                
            async with self.session.get(f"{self.agent_endpoints['emotion']}/current_emotion") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.error(f"Error getting emotion context: {response.status}")
                    return {"emotion": "neutral", "intensity": 0.5}
        except Exception as e:
            self.logger.error(f"Error in get_emotion_context: {e}")
            return {"emotion": "neutral", "intensity": 0.5}

    async def get_personality_traits(self) -> Dict[str, Any]:
        """Get personality traits from Personality Agent"""
        try:
            if not self.session:
                await self.initialize()
                
            async with self.session.get(f"{self.agent_endpoints['personality']}/traits") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.error(f"Error getting personality traits: {response.status}")
                    return {"traits": {}}
        except Exception as e:
            self.logger.error(f"Error in get_personality_traits: {e}")
            return {"traits": {}}

    async def get_memory_context(self, query: str) -> Dict[str, Any]:
        """Get relevant memory context from Memory Agent"""
        try:
            if not self.session:
                await self.initialize()
                
            async with self.session.post(
                f"{self.agent_endpoints['memory']}/query",
                json={"query": query}
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.error(f"Error getting memory context: {response.status}")
                    return {"context": {}}
        except Exception as e:
            self.logger.error(f"Error in get_memory_context: {e}")
            return {"context": {}}

    async def notify_brain(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify Brain Agent of speech events"""
        try:
            if not self.session:
                await self.initialize()
                
            event_data = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            
            async with self.session.post(
                f"{self.agent_endpoints['brain']}/events",
                json=event_data
            ) as response:
                if response.status != 200:
                    self.logger.error(f"Error notifying brain: {response.status}")
        except Exception as e:
            self.logger.error(f"Error in notify_brain: {e}")

    async def get_conversation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history from Memory Agent"""
        try:
            if not self.session:
                await self.initialize()
                
            async with self.session.get(
                f"{self.agent_endpoints['memory']}/conversation_history",
                params={"limit": limit}
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.error(f"Error getting conversation history: {response.status}")
                    return []
        except Exception as e:
            self.logger.error(f"Error in get_conversation_history: {e}")
            return []

    async def update_agent_status(self, status: Dict[str, Any]) -> None:
        """Update status with all connected agents"""
        try:
            if not self.session:
                await self.initialize()
                
            for agent, endpoint in self.agent_endpoints.items():
                try:
                    async with self.session.post(
                        f"{endpoint}/status_update",
                        json=status
                    ) as response:
                        if response.status != 200:
                            self.logger.error(f"Error updating {agent} status: {response.status}")
                except Exception as e:
                    self.logger.error(f"Error updating {agent} status: {e}")
        except Exception as e:
            self.logger.error(f"Error in update_agent_status: {e}")

    async def get_agent_health(self) -> Dict[str, bool]:
        """Check health status of all connected agents"""
        try:
            if not self.session:
                await self.initialize()
                
            health_status = {}
            for agent, endpoint in self.agent_endpoints.items():
                try:
                    async with self.session.get(f"{endpoint}/health") as response:
                        health_status[agent] = response.status == 200
                except Exception:
                    health_status[agent] = False
                    
            return health_status
        except Exception as e:
            self.logger.error(f"Error in get_agent_health: {e}")
            return {agent: False for agent in self.agent_endpoints}

    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.session:
                await self.session.close()
                self.session = None
        except Exception as e:
            self.logger.error(f"Error cleaning up agent integration: {e}") 