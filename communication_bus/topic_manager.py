import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime

import aiokafka
from structlog import get_logger

from .config import settings

logger = get_logger()

class TopicManager:
    """Manages Kafka topics and their configurations."""
    
    def __init__(self):
        """Initialize the topic manager."""
        self.admin_client: Optional[aiokafka.AIOKafkaAdminClient] = None
        self.topics: Dict[str, Dict] = {}
        self.topic_configs: Dict[str, Dict] = {}
        self._manage_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the topic manager."""
        if self._initialized:
            return
        
        logger.info("Initializing topic manager...")
        
        try:
            # Initialize Kafka admin client
            self.admin_client = aiokafka.AIOKafkaAdminClient(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS
            )
            
            # Load existing topics
            await self._load_topics()
            
            # Create default topics if they don't exist
            await self._create_default_topics()
            
            self._initialized = True
            logger.info("Topic manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize topic manager: {str(e)}")
            raise
    
    async def shutdown(self):
        """Shutdown the topic manager."""
        logger.info("Shutting down topic manager...")
        
        # Cancel management task
        if self._manage_task:
            self._manage_task.cancel()
            try:
                await self._manage_task
            except asyncio.CancelledError:
                pass
        
        # Close admin client
        if self.admin_client:
            await self.admin_client.close()
        
        self._initialized = False
        logger.info("Topic manager shut down")
    
    async def _load_topics(self):
        """Load existing topics."""
        try:
            # Get list of topics
            topics = await self.admin_client.list_topics()
            
            # Get topic configurations
            for topic in topics:
                config = await self.admin_client.describe_configs(
                    [aiokafka.admin.ConfigResource(aiokafka.admin.ConfigResourceType.TOPIC, topic)]
                )
                self.topics[topic] = {
                    "name": topic,
                    "config": config[topic].configs,
                    "created_at": datetime.utcnow().isoformat()
                }
            
            logger.info(f"Loaded {len(self.topics)} topics")
        except Exception as e:
            logger.error(f"Failed to load topics: {str(e)}")
            raise
    
    async def _create_default_topics(self):
        """Create default topics if they don't exist."""
        default_topics = {
            "agent-communication": {
                "num_partitions": 3,
                "replication_factor": 1,
                "retention_hours": 24
            },
            "system-events": {
                "num_partitions": 3,
                "replication_factor": 1,
                "retention_hours": 168  # 7 days
            },
            "health-metrics": {
                "num_partitions": 3,
                "replication_factor": 1,
                "retention_hours": 24
            },
            "task-updates": {
                "num_partitions": 3,
                "replication_factor": 1,
                "retention_hours": 24
            }
        }
        
        for topic, config in default_topics.items():
            if topic not in self.topics:
                await self.create_topic(topic, config)
    
    async def create_topic(self, topic_name: str, config: Dict) -> bool:
        """Create a new topic."""
        if not self._initialized:
            raise RuntimeError("Topic manager not initialized")
        
        try:
            # Create topic
            await self.admin_client.create_topics([
                aiokafka.admin.NewTopic(
                    name=topic_name,
                    num_partitions=config.get("num_partitions", 3),
                    replication_factor=config.get("replication_factor", 1),
                    topic_configs={
                        "retention.ms": str(config.get("retention_hours", 24) * 3600 * 1000)
                    }
                )
            ])
            
            # Store topic configuration
            self.topics[topic_name] = {
                "name": topic_name,
                "config": config,
                "created_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Created topic {topic_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create topic {topic_name}: {str(e)}")
            return False
    
    async def delete_topic(self, topic_name: str) -> bool:
        """Delete a topic."""
        if not self._initialized:
            raise RuntimeError("Topic manager not initialized")
        
        try:
            # Delete topic
            await self.admin_client.delete_topics([topic_name])
            
            # Remove from local storage
            if topic_name in self.topics:
                del self.topics[topic_name]
            
            logger.info(f"Deleted topic {topic_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete topic {topic_name}: {str(e)}")
            return False
    
    async def get_topic(self, topic_name: str) -> Optional[Dict]:
        """Get topic information."""
        return self.topics.get(topic_name)
    
    async def list_topics(self) -> List[Dict]:
        """List all topics."""
        return list(self.topics.values())
    
    async def update_topic_config(self, topic_name: str, config: Dict) -> bool:
        """Update topic configuration."""
        if not self._initialized:
            raise RuntimeError("Topic manager not initialized")
        
        try:
            # Update topic configuration
            await self.admin_client.alter_configs([
                aiokafka.admin.ConfigResource(
                    aiokafka.admin.ConfigResourceType.TOPIC,
                    topic_name,
                    config
                )
            ])
            
            # Update local storage
            if topic_name in self.topics:
                self.topics[topic_name]["config"].update(config)
                self.topics[topic_name]["updated_at"] = datetime.utcnow().isoformat()
            
            logger.info(f"Updated configuration for topic {topic_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to update configuration for topic {topic_name}: {str(e)}")
            return False
    
    async def manage_topics(self):
        """Manage topics (cleanup, monitoring, etc.)."""
        if not self._initialized:
            raise RuntimeError("Topic manager not initialized")
        
        while True:
            try:
                # Here you would typically implement topic management tasks
                # For example, cleanup old topics, monitor topic health, etc.
                
                await asyncio.sleep(settings.TOPIC_MANAGEMENT_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in topic management: {str(e)}")
                await asyncio.sleep(1)
    
    async def get_status(self) -> Dict:
        """Get topic manager status."""
        return {
            "initialized": self._initialized,
            "total_topics": len(self.topics),
            "topics": list(self.topics.keys())
        } 