import os
from typing import Optional, List

try:
    from pydantic import Field
except ImportError:
    Field = None  # type: ignore

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    try:
        from pydantic import BaseSettings  # type: ignore
        SettingsConfigDict = dict  # type: ignore
    except ImportError:
        class BaseSettings:  # type: ignore
            def __init__(self, **values):
                for k, v in values.items():
                    setattr(self, k, v)
        SettingsConfigDict = dict  # type: ignore


class Settings(BaseSettings):
    """Settings for the communication bus."""

    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = False
    WORKERS: int = 4
    LOG_LEVEL: str = "INFO"

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_GROUP_ID: str = "communication-bus"
    KAFKA_TOPICS: List[str] = Field(default_factory=lambda: [
        "agent-communication",
        "system-events",
        "health-metrics",
        "task-updates",
    ]) if Field else [
        "agent-communication",
        "system-events",
        "health-metrics",
        "task-updates",
    ]

    MESSAGE_PROCESSING_INTERVAL: int = 1
    MESSAGE_BATCH_SIZE: int = 100
    MESSAGE_RETENTION_HOURS: int = 24
    MESSAGE_MAX_SIZE_BYTES: int = 1_048_576
    MESSAGE_RETRY_ATTEMPTS: int = 3
    MESSAGE_RETRY_BACKOFF_MS: int = 200
    MESSAGE_DEAD_LETTER_LIMIT: int = 10_000
    MESSAGE_COMPRESSION_ENABLED: bool = True
    MESSAGE_BACKPRESSURE_LIMIT: int = 10_000
    MESSAGE_PERSISTENCE_ENABLED: bool = True

    TOPIC_MANAGEMENT_INTERVAL: int = 300
    DEFAULT_PARTITIONS: int = 3
    DEFAULT_REPLICATION_FACTOR: int = 1

    HEALTH_CHECK_INTERVAL: int = 60
    CPU_USAGE_THRESHOLD: float = 80.0
    MEMORY_USAGE_THRESHOLD: float = 80.0
    DISK_USAGE_THRESHOLD: float = 80.0

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_ENABLED: bool = False

    PROMETHEUS_MULTIPROC_DIR: str = "/tmp"
    SENTRY_DSN: Optional[str] = None

    API_GATEWAY_URL: str = "http://localhost:8000"
    ORCHESTRATOR_URL: str = "http://localhost:8002"

    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    def validate_runtime(self) -> dict:
        errors = []
        warnings = []

        if self.MESSAGE_MAX_SIZE_BYTES <= 0:
            errors.append("MESSAGE_MAX_SIZE_BYTES must be greater than 0")
        if self.MESSAGE_RETRY_ATTEMPTS < 0:
            errors.append("MESSAGE_RETRY_ATTEMPTS cannot be negative")
        if self.MESSAGE_BACKPRESSURE_LIMIT <= 0:
            errors.append("MESSAGE_BACKPRESSURE_LIMIT must be greater than 0")
        if not self.KAFKA_TOPICS:
            warnings.append("KAFKA_TOPICS is empty; default topics will be used")
        if self.MESSAGE_PERSISTENCE_ENABLED and not self.REDIS_PASSWORD and self.REDIS_ENABLED:
            warnings.append("Redis persistence is enabled without a password")

        return {"ok": not errors, "errors": errors, "warnings": warnings}

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


try:
    settings = Settings()
except Exception:
    # Minimal fallback when pydantic is unavailable
    class _FallbackSettings:  # type: ignore
        HOST = "0.0.0.0"
        PORT = 8001
        DEBUG = False
        WORKERS = 4
        LOG_LEVEL = "INFO"
        KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
        KAFKA_GROUP_ID = "communication-bus"
        KAFKA_TOPICS = ["agent-communication", "system-events", "health-metrics", "task-updates"]
        MESSAGE_PROCESSING_INTERVAL = 1
        MESSAGE_BATCH_SIZE = 100
        MESSAGE_RETENTION_HOURS = 24
        MESSAGE_MAX_SIZE_BYTES = 1_048_576
        MESSAGE_RETRY_ATTEMPTS = 3
        MESSAGE_RETRY_BACKOFF_MS = 200
        MESSAGE_DEAD_LETTER_LIMIT = 10_000
        MESSAGE_COMPRESSION_ENABLED = True
        MESSAGE_BACKPRESSURE_LIMIT = 10_000
        MESSAGE_PERSISTENCE_ENABLED = True
        TOPIC_MANAGEMENT_INTERVAL = 300
        DEFAULT_PARTITIONS = 3
        DEFAULT_REPLICATION_FACTOR = 1
        HEALTH_CHECK_INTERVAL = 60
        CPU_USAGE_THRESHOLD = 80.0
        MEMORY_USAGE_THRESHOLD = 80.0
        DISK_USAGE_THRESHOLD = 80.0
        REDIS_HOST = "localhost"
        REDIS_PORT = 6379
        REDIS_DB = 0
        REDIS_PASSWORD = None
        PROMETHEUS_MULTIPROC_DIR = "/tmp"
        SENTRY_DSN = None
        API_GATEWAY_URL = "http://localhost:8000"
        ORCHESTRATOR_URL = "http://localhost:8002"

        @property
        def REDIS_URL(self) -> str:
            return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    settings = _FallbackSettings()  # type: ignore
