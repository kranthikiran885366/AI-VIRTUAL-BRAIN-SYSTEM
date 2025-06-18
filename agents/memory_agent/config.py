from typing import Optional
from pydantic import BaseSettings, validator
import os

class MemoryAgentSettings(BaseSettings):
    """Settings for the Memory Agent."""
    
    # Short-term memory settings
    SHORT_TERM_MEMORY_MAX_SIZE: int = 1000
    SHORT_TERM_MEMORY_RETENTION_PERIOD: int = 3600  # 1 hour in seconds
    
    # Long-term memory settings
    LONG_TERM_MEMORY_STORAGE_PATH: str = "databases/memory_db/long_term"
    MEMORY_IMPORTANCE_THRESHOLD: float = 0.7
    
    # Context settings
    CONTEXT_HISTORY_MAX_SIZE: int = 100
    CONTEXT_WINDOW_SIZE: int = 10
    
    # Memory store settings
    MEMORY_STORE_PATH: str = "databases/memory_db/store"
    
    # API settings
    API_HOST: str = "localhost"
    API_PORT: int = 8000
    API_DEBUG: bool = False
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Kafka settings
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_GROUP_ID: str = "memory_agent"
    KAFKA_TOPICS: list = ["memory_events", "memory_commands"]
    
    # Processing settings
    PROCESSING_INTERVAL: float = 1.0  # seconds
    BATCH_SIZE: int = 100
    
    # Health check settings
    HEALTH_CHECK_INTERVAL: float = 30.0  # seconds
    MAX_MEMORY_USAGE: float = 0.8  # 80% of available memory
    
    # Monitoring settings
    ENABLE_PROMETHEUS: bool = True
    PROMETHEUS_PORT: int = 9090
    ENABLE_SENTRY: bool = False
    SENTRY_DSN: Optional[str] = None
    
    # Service URLs
    API_GATEWAY_URL: str = "http://localhost:8000"
    ORCHESTRATOR_URL: str = "http://localhost:8001"
    
    @validator("LONG_TERM_MEMORY_STORAGE_PATH", "MEMORY_STORE_PATH")
    def validate_storage_paths(cls, v):
        """Validate storage paths."""
        # Create directory if it doesn't exist
        os.makedirs(v, exist_ok=True)
        return v
    
    @validator("KAFKA_TOPICS")
    def validate_kafka_topics(cls, v):
        """Validate Kafka topics."""
        if not isinstance(v, list):
            raise ValueError("KAFKA_TOPICS must be a list")
        return v
    
    class Config:
        """Pydantic config."""
        env_prefix = "MEMORY_AGENT_"
        case_sensitive = True

# Create settings instance
settings = MemoryAgentSettings() 