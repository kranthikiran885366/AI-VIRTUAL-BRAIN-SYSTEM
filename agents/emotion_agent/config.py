from typing import Optional
from pydantic import BaseSettings, validator
import os

class EmotionAgentSettings(BaseSettings):
    """Settings for the Emotion Agent."""
    
    # Emotion processor settings
    EMOTION_HISTORY_MAX_SIZE: int = 1000
    EMOTION_DECAY_RATE: float = 0.1  # 10% decay per second
    EMOTION_MIN_INTENSITY: float = 0.1
    
    # Emotion analyzer settings
    EMOTION_ANALYSIS_HISTORY_SIZE: int = 100
    EMOTION_PATTERN_CONFIDENCE_THRESHOLD: float = 0.7
    EMOTION_IMPACT_THRESHOLD: float = 0.8
    
    # Emotion store settings
    EMOTION_STORE_PATH: str = "databases/emotion_db/store"
    
    # API settings
    API_HOST: str = "localhost"
    API_PORT: int = 8001
    API_DEBUG: bool = False
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 1
    REDIS_PASSWORD: Optional[str] = None
    
    # Kafka settings
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_GROUP_ID: str = "emotion_agent"
    KAFKA_TOPICS: list = ["emotion_events", "emotion_commands"]
    
    # Processing settings
    PROCESSING_INTERVAL: float = 1.0  # seconds
    BATCH_SIZE: int = 100
    
    # Health check settings
    HEALTH_CHECK_INTERVAL: float = 30.0  # seconds
    MAX_MEMORY_USAGE: float = 0.8  # 80% of available memory
    
    # Monitoring settings
    ENABLE_PROMETHEUS: bool = True
    PROMETHEUS_PORT: int = 9091
    ENABLE_SENTRY: bool = False
    SENTRY_DSN: Optional[str] = None
    
    # Service URLs
    API_GATEWAY_URL: str = "http://localhost:8000"
    ORCHESTRATOR_URL: str = "http://localhost:8001"
    MEMORY_AGENT_URL: str = "http://localhost:8002"
    
    @validator("EMOTION_STORE_PATH")
    def validate_storage_path(cls, v):
        """Validate storage path."""
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
        env_prefix = "EMOTION_AGENT_"
        case_sensitive = True

# Create settings instance
settings = EmotionAgentSettings() 