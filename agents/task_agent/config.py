from typing import Dict, List, Optional
from pydantic import BaseSettings, validator
import os

class TaskAgentSettings(BaseSettings):
    """Settings for the Task Agent."""
    
    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8002
    API_PREFIX: str = "/api/v1/tasks"
    
    # Task Processing Settings
    TASK_PROCESSING_INTERVAL: float = 1.0  # seconds
    TASK_HISTORY_MAX_SIZE: int = 1000
    TASK_ANALYSIS_HISTORY_SIZE: int = 1000
    TASK_AUTOMATION_HISTORY_SIZE: int = 1000
    
    # Task Store Settings
    TASK_STORE_PATH: str = "data/tasks"
    TASK_STORE_BACKUP_INTERVAL: int = 3600  # seconds
    TASK_STORE_MAX_BACKUPS: int = 24
    
    # Task Automation Settings
    TASK_AUTOMATION_RULES_PATH: str = "data/tasks/automation_rules.json"
    TASK_AUTOMATION_CHECK_INTERVAL: float = 1.0  # seconds
    
    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Kafka Settings
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPICS: Dict[str, str] = {
        "task_created": "task_created",
        "task_updated": "task_updated",
        "task_deleted": "task_deleted",
        "task_completed": "task_completed"
    }
    KAFKA_CONSUMER_GROUP: str = "task_agent"
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Monitoring Settings
    PROMETHEUS_PORT: int = 9092
    SENTRY_DSN: Optional[str] = None
    
    # Health Check Settings
    HEALTH_CHECK_INTERVAL: float = 30.0  # seconds
    HEALTH_CHECK_TIMEOUT: float = 5.0  # seconds
    
    # Service URLs
    MEMORY_AGENT_URL: str = "http://localhost:8000"
    EMOTION_AGENT_URL: str = "http://localhost:8001"
    
    @validator("TASK_STORE_PATH")
    def validate_task_store_path(cls, v):
        """Ensure task store path exists."""
        os.makedirs(v, exist_ok=True)
        return v
    
    @validator("KAFKA_TOPICS")
    def validate_kafka_topics(cls, v):
        """Ensure all Kafka topics are strings."""
        return {k: str(v) for k, v in v.items()}
    
    class Config:
        env_prefix = "TASK_AGENT_"
        case_sensitive = True

# Create settings instance
settings = TaskAgentSettings() 