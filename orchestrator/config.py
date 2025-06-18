import os
from typing import List, Optional
from pydantic import BaseSettings, PostgresDsn, RedisDsn, validator

class Settings(BaseSettings):
    """Orchestrator settings."""
    
    # API Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = False
    WORKERS: int = 4
    LOG_LEVEL: str = "INFO"
    
    # Agent Settings
    AGENT_HEALTH_CHECK_INTERVAL: int = 10
    AGENT_TIMEOUT: int = 60
    MAX_CONCURRENT_AGENTS: int = 100
    
    # Task Settings
    TASK_TIMEOUT: int = 300
    MAX_CONCURRENT_TASKS: int = 50
    TASK_PRIORITY_LEVELS: List[str] = ["critical", "high", "medium", "low"]
    
    # Communication Settings
    KAFKA_BOOTSTRAP_SERVERS: List[str]
    KAFKA_GROUP_ID: str = "orchestrator-group"
    KAFKA_TOPICS: List[str] = [
        "agent-communication",
        "system-events",
        "health-metrics",
        "task-updates"
    ]
    
    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None
    
    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=values.get("POSTGRES_PORT"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )
    
    # Redis
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URI: Optional[RedisDsn] = None
    
    @validator("REDIS_URI", pre=True)
    def assemble_redis_connection(cls, v: Optional[str], values: dict) -> Any:
        if isinstance(v, str):
            return v
        return RedisDsn.build(
            scheme="redis",
            host=values.get("REDIS_HOST"),
            port=str(values.get("REDIS_PORT")),
            password=values.get("REDIS_PASSWORD"),
        )
    
    # Health Monitoring
    HEALTH_CHECK_INTERVAL: int = 10
    CPU_USAGE_THRESHOLD: float = 80.0
    MEMORY_USAGE_THRESHOLD: float = 80.0
    DISK_USAGE_THRESHOLD: float = 80.0
    
    # Service URLs
    API_GATEWAY_URL: str
    COMMUNICATION_BUS_URL: str
    
    # Monitoring
    PROMETHEUS_MULTIPROC_DIR: str = "/tmp"
    SENTRY_DSN: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings() 