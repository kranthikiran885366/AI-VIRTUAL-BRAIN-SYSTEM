"""Memory agent configuration — plain class, no pydantic dependency."""
from typing import Optional
import os


class MemoryAgentSettings:
    """Settings for the Memory Agent — loaded from env with safe defaults."""

    # Short-term memory
    SHORT_TERM_MEMORY_MAX_SIZE: int = int(os.environ.get("MEMORY_AGENT_SHORT_TERM_MEMORY_MAX_SIZE", 1000))
    SHORT_TERM_MEMORY_RETENTION_PERIOD: int = int(os.environ.get("MEMORY_AGENT_SHORT_TERM_MEMORY_RETENTION_PERIOD", 3600))

    # Long-term memory
    LONG_TERM_MEMORY_STORAGE_PATH: str = os.environ.get("MEMORY_AGENT_LONG_TERM_MEMORY_STORAGE_PATH", "databases/memory_db/long_term")
    MEMORY_IMPORTANCE_THRESHOLD: float = float(os.environ.get("MEMORY_AGENT_MEMORY_IMPORTANCE_THRESHOLD", 0.7))

    # Context
    CONTEXT_HISTORY_MAX_SIZE: int = int(os.environ.get("MEMORY_AGENT_CONTEXT_HISTORY_MAX_SIZE", 100))
    CONTEXT_WINDOW_SIZE: int = int(os.environ.get("MEMORY_AGENT_CONTEXT_WINDOW_SIZE", 10))

    # Store
    MEMORY_STORE_PATH: str = os.environ.get("MEMORY_AGENT_MEMORY_STORE_PATH", "databases/memory_db/store")

    # API
    API_HOST: str = os.environ.get("MEMORY_AGENT_API_HOST", "localhost")
    API_PORT: int = int(os.environ.get("MEMORY_AGENT_API_PORT", 8000))
    API_DEBUG: bool = os.environ.get("MEMORY_AGENT_API_DEBUG", "false").lower() == "true"

    # Logging
    LOG_LEVEL: str = os.environ.get("MEMORY_AGENT_LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Redis
    REDIS_HOST: str = os.environ.get("MEMORY_AGENT_REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.environ.get("MEMORY_AGENT_REDIS_PORT", 6379))
    REDIS_DB: int = int(os.environ.get("MEMORY_AGENT_REDIS_DB", 0))
    REDIS_PASSWORD: Optional[str] = os.environ.get("MEMORY_AGENT_REDIS_PASSWORD")

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = os.environ.get("MEMORY_AGENT_KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_GROUP_ID: str = os.environ.get("MEMORY_AGENT_KAFKA_GROUP_ID", "memory_agent")
    KAFKA_TOPICS: list = ["memory_events", "memory_commands"]

    # Processing
    PROCESSING_INTERVAL: float = float(os.environ.get("MEMORY_AGENT_PROCESSING_INTERVAL", 1.0))
    BATCH_SIZE: int = int(os.environ.get("MEMORY_AGENT_BATCH_SIZE", 100))

    # Health
    HEALTH_CHECK_INTERVAL: float = float(os.environ.get("MEMORY_AGENT_HEALTH_CHECK_INTERVAL", 30.0))
    MAX_MEMORY_USAGE: float = float(os.environ.get("MEMORY_AGENT_MAX_MEMORY_USAGE", 0.8))

    # Monitoring
    ENABLE_PROMETHEUS: bool = os.environ.get("MEMORY_AGENT_ENABLE_PROMETHEUS", "true").lower() == "true"
    PROMETHEUS_PORT: int = int(os.environ.get("MEMORY_AGENT_PROMETHEUS_PORT", 9090))
    ENABLE_SENTRY: bool = os.environ.get("MEMORY_AGENT_ENABLE_SENTRY", "false").lower() == "true"
    SENTRY_DSN: Optional[str] = os.environ.get("MEMORY_AGENT_SENTRY_DSN")

    # Service URLs
    API_GATEWAY_URL: str = os.environ.get("MEMORY_AGENT_API_GATEWAY_URL", "http://localhost:8000")
    ORCHESTRATOR_URL: str = os.environ.get("MEMORY_AGENT_ORCHESTRATOR_URL", "http://localhost:8001")
    TASK_AGENT_URL: str = os.environ.get("TASK_AGENT_URL", "http://localhost:8001")
    EMOTION_AGENT_URL: str = os.environ.get("EMOTION_AGENT_URL", "http://localhost:8001")
    MEMORY_AGENT_HOST: str = os.environ.get("MEMORY_AGENT_HOST", "0.0.0.0")
    MEMORY_AGENT_PORT: int = int(os.environ.get("MEMORY_AGENT_PORT", 8002))
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"

    def __init__(self):
        os.makedirs(self.LONG_TERM_MEMORY_STORAGE_PATH, exist_ok=True)
        os.makedirs(self.MEMORY_STORE_PATH, exist_ok=True)


# Singleton
settings = MemoryAgentSettings()