import os
from typing import Optional
from pydantic import BaseSettings, validator

class Settings(BaseSettings):
    """Settings for the communication bus."""
    
    # API settings
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = False
    WORKERS: int = 4
    LOG_LEVEL: str = "INFO"
    
    # Kafka settings
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_GROUP_ID: str = "communication-bus"
    KAFKA_TOPICS: list = [
        "agent-communication",
        "system-events",
        "health-metrics",
        "task-updates"
    ]
    
    # Message processing settings
    MESSAGE_PROCESSING_INTERVAL: int = 1  # seconds
    MESSAGE_BATCH_SIZE: int = 100
    MESSAGE_RETENTION_HOURS: int = 24
    
    # Topic management settings
    TOPIC_MANAGEMENT_INTERVAL: int = 300  # 5 minutes
    DEFAULT_PARTITIONS: int = 3
    DEFAULT_REPLICATION_FACTOR: int = 1
    
    # Health monitoring settings
    HEALTH_CHECK_INTERVAL: int = 60  # 1 minute
    CPU_USAGE_THRESHOLD: float = 80.0  # percentage
    MEMORY_USAGE_THRESHOLD: float = 80.0  # percentage
    DISK_USAGE_THRESHOLD: float = 80.0  # percentage
    
    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Monitoring settings
    PROMETHEUS_MULTIPROC_DIR: str = "/tmp"
    SENTRY_DSN: Optional[str] = None
    
    # Service URLs
    API_GATEWAY_URL: str = "http://localhost:8000"
    ORCHESTRATOR_URL: str = "http://localhost:8002"
    
    @validator("KAFKA_TOPICS", pre=True)
    def parse_kafka_topics(cls, v):
        """Parse Kafka topics from string if needed."""
        if isinstance(v, str):
            return [topic.strip() for topic in v.split(",")]
        return v
    
    @property
    def REDIS_URL(self) -> str:
        """Get Redis connection URL."""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings() 