import os
from pathlib import Path
from typing import List, Optional, Any, Dict
from typing import List, Optional, Any

try:
    from pydantic import Field
except ImportError:
    Field = None  # type: ignore

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    try:
        from pydantic import BaseSettings
        SettingsConfigDict = dict
    except ImportError:
        class BaseSettings:
            def __init__(self, **values):
                for key, value in values.items():
                    setattr(self, key, value)

            def __init_subclass__(cls, **kwargs):
                return super().__init_subclass__(**kwargs)

        SettingsConfigDict = dict

class Settings(BaseSettings):
    """Orchestrator settings with optional external dependencies."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # API Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = True
    WORKERS: int = 1
    LOG_LEVEL: str = "INFO"
    APP_VERSION: str = "1.0.0"
    CONFIG_VERSION: str = "1.0.0"
    STARTUP_TIMEOUT: int = 120
    SHUTDOWN_TIMEOUT: int = 30
    ENABLE_TRACING: bool = False

    # Agent Settings
    AGENT_HEALTH_CHECK_INTERVAL: int = 30
    AGENT_TIMEOUT: int = 60
    MAX_CONCURRENT_AGENTS: int = 50
    AGENT_PROCESSING_INTERVAL: float = 1.0

    # Task Settings
    TASK_TIMEOUT: int = 300
    MAX_CONCURRENT_TASKS: int = 20

    # Kafka (optional — system works without it)
    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_GROUP_ID: str = "brain-orchestrator"
    KAFKA_TOPICS: List[str] = Field(default_factory=lambda: ["agent-communication", "system-events", "health-metrics"]) if Field else ["agent-communication", "system-events", "health-metrics"]

    # Database (optional — falls back to SQLite)
    DATABASE_URL: str = "sqlite:///./data/brain.db"
    POSTGRES_SERVER: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_PORT: str = "5432"

    # Redis (optional)
    REDIS_ENABLED: bool = False
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REQUIRE_DATABASE: bool = False
    REQUIRE_BROKER: bool = False

    # Health Monitoring
    HEALTH_CHECK_INTERVAL: int = 30
    CPU_USAGE_THRESHOLD: float = 85.0
    MEMORY_USAGE_THRESHOLD: float = 85.0
    DISK_USAGE_THRESHOLD: float = 90.0

    # CORS
    ALLOWED_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]) if Field else ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Monitoring
    PROMETHEUS_ENABLED: bool = False
    SENTRY_DSN: Optional[str] = None

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.POSTGRES_SERVER and self.POSTGRES_USER and self.POSTGRES_PASSWORD and self.POSTGRES_DB:
            return (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self.DATABASE_URL

    def ensure_directories(self) -> None:
        """Create runtime directories used by the orchestrator if they are missing."""
        for path_value in ("logs", "data", "config"):
            Path(path_value).mkdir(parents=True, exist_ok=True)

    def validate_runtime(self) -> Dict[str, Any]:
        """Validate runtime configuration and return a structured report."""
        errors: List[str] = []
        warnings: List[str] = []

        if not isinstance(self.PORT, int) or self.PORT <= 0 or self.PORT > 65535:
            errors.append("PORT must be an integer between 1 and 65535")
        if self.AGENT_TIMEOUT <= 0:
            errors.append("AGENT_TIMEOUT must be greater than 0")
        if self.STARTUP_TIMEOUT <= 0:
            errors.append("STARTUP_TIMEOUT must be greater than 0")
        if self.SHUTDOWN_TIMEOUT <= 0:
            errors.append("SHUTDOWN_TIMEOUT must be greater than 0")
        if self.MAX_CONCURRENT_AGENTS <= 0:
            errors.append("MAX_CONCURRENT_AGENTS must be greater than 0")
        if self.MAX_CONCURRENT_TASKS <= 0:
            errors.append("MAX_CONCURRENT_TASKS must be greater than 0")
        if self.HEALTH_CHECK_INTERVAL <= 0:
            errors.append("HEALTH_CHECK_INTERVAL must be greater than 0")

        if isinstance(self.ALLOWED_ORIGINS, str):
            self.ALLOWED_ORIGINS = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
        if not self.ALLOWED_ORIGINS:
            warnings.append("ALLOWED_ORIGINS is empty; browser clients will be rejected by CORS")

        if isinstance(self.KAFKA_TOPICS, str):
            self.KAFKA_TOPICS = [topic.strip() for topic in self.KAFKA_TOPICS.split(",") if topic.strip()]
        if self.KAFKA_ENABLED and not self.KAFKA_BOOTSTRAP_SERVERS.strip():
            errors.append("KAFKA_ENABLED is true but KAFKA_BOOTSTRAP_SERVERS is empty")
        if self.REQUIRE_BROKER and not self.KAFKA_ENABLED:
            warnings.append("REQUIRE_BROKER is enabled but KAFKA_ENABLED is false; broker checks will be skipped")

        if self.REQUIRE_DATABASE and not self.DATABASE_URL.strip():
            errors.append("REQUIRE_DATABASE is true but DATABASE_URL is empty")

        self.ensure_directories()

        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "version": self.CONFIG_VERSION,
            "app_version": self.APP_VERSION,
        }

    def reload(self) -> "Settings":
        """Reload settings from environment variables and return the refreshed instance."""
        fresh = self.__class__()
        try:
            items = fresh.model_dump().items()  # pydantic v2
        except AttributeError:
            items = fresh.dict().items()  # pydantic v1 fallback
        for key, value in items:
            setattr(self, key, value)
        return self

    def to_runtime_config(self) -> Dict[str, Any]:
        """Return a serializable snapshot of runtime configuration."""
        try:
            return self.model_dump()  # pydantic v2
        except AttributeError:
            return self.dict()  # pydantic v1 fallback


# Singleton
settings = Settings()
