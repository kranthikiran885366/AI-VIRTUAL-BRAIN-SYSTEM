import os
from functools import lru_cache
from typing import Any, List, Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover
    from pydantic import BaseSettings
    SettingsConfigDict = dict

from pydantic import field_validator


class Settings(BaseSettings):
    """API Gateway settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # API Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    WORKERS: int = 4
    LOG_LEVEL: str = "INFO"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    ALLOWED_ORIGINS: List[str] = ["*"]
    ALLOWED_HOSTS: List[str] = ["*"]

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "virtual_brain"
    POSTGRES_PORT: str = "5432"
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: Any) -> Any:
        if isinstance(v, str):
            return v
        values = info.data
        password = values.get("POSTGRES_PASSWORD") or ""
        credentials = f"{values.get('POSTGRES_USER')}:{password}@" if values.get("POSTGRES_USER") else ""
        host = values.get("POSTGRES_SERVER") or "localhost"
        port = values.get("POSTGRES_PORT") or "5432"
        db = values.get("POSTGRES_DB") or "virtual_brain"
        return f"postgresql://{credentials}{host}:{port}/{db}"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URI: Optional[str] = None

    @field_validator("REDIS_URI", mode="before")
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], info: Any) -> Any:
        if isinstance(v, str):
            return v
        values = info.data
        password = values.get("REDIS_PASSWORD") or ""
        credentials = f":{password}@" if password else ""
        host = values.get("REDIS_HOST") or "localhost"
        port = values.get("REDIS_PORT") or "6379"
        return f"redis://{credentials}{host}:{port}"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: List[str] = ["localhost:9092"]
    KAFKA_GROUP_ID: str = "api-gateway-group"

    # Service URLs
    ORCHESTRATOR_URL: str = "http://localhost:8001"
    COMMUNICATION_BUS_URL: str = "http://localhost:8002"

    # Monitoring
    PROMETHEUS_MULTIPROC_DIR: str = "/tmp"
    SENTRY_DSN: Optional[str] = None

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # Agent settings
    MAX_CONCURRENT_TASKS: int = 10
    DEFAULT_TASK_TIMEOUT: int = 300  # 5 minutes
    DEFAULT_RETRY_COUNT: int = 3
    DEFAULT_RETRY_DELAY: int = 5

    # Orchestrator settings
    ORCHESTRATOR_TIMEOUT: int = 30

    # Communication bus settings
    COMMUNICATION_BUS_TIMEOUT: int = 30

    # Monitoring settings
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090

    # Logging settings
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "api_gateway.log"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()