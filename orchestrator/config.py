import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _coerce_bool(v: Any) -> bool:
    """Coerce any value to bool — handles OS env strings like 'release', 'yes', '0'."""
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on", "enabled")
    return bool(v)


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
    KAFKA_TOPICS: List[str] = Field(
        default_factory=lambda: ["agent-communication", "system-events", "health-metrics"]
    )

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
    ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # Monitoring
    PROMETHEUS_ENABLED: bool = False
    SENTRY_DSN: Optional[str] = None

    # Phase 14 Autonomous Cognitive Coordination & Self-Improvement Settings
    AUTONOMOUS_CONTROLLER_ENABLED: bool = True
    COGNITIVE_CYCLE_INTERVAL: float = 10.0
    SELF_HEALING_ENABLED: bool = True
    MAX_RESTART_ATTEMPTS: int = 3
    ADAPTIVE_OPTIMIZATION_ENABLED: bool = True
    SELF_IMPROVEMENT_ENABLED: bool = True

    # Phase 15 Distributed Brain Infrastructure & Enterprise Settings
    # ── Distributed Execution ──
    DISTRIBUTED_MODE: bool = False
    CLUSTER_NODE_ID: str = "node-primary"
    CLUSTER_DISCOVERY_URL: Optional[str] = None
    CLUSTER_HEARTBEAT_INTERVAL: int = 15
    CLUSTER_LEADER_LEASE_TTL: int = 30
    CLUSTER_MAX_NODES: int = 10

    # ── Enterprise Security ──
    SECURITY_ENABLED: bool = False
    JWT_SECRET_KEY: Optional[str] = None
    API_KEY_HEADER: str = "X-API-Key"
    RBAC_DEFAULT_ROLE: str = "viewer"
    AUDIT_LOG_ENABLED: bool = True
    AUDIT_MAX_ENTRIES: int = 10000

    # ── Resilience ──
    CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: float = 30.0
    DLQ_ENABLED: bool = True
    DLQ_MAX_SIZE: int = 10000

    # ── Observability ──
    OTEL_ENABLED: bool = False
    OTEL_ENDPOINT: Optional[str] = None
    GRAFANA_DASHBOARD_ENABLED: bool = False
    SLO_AVAILABILITY_TARGET: float = 99.9
    SLO_LATENCY_TARGET: float = 95.0

    # ── Enterprise Operations ──
    MAINTENANCE_MODE_ENABLED: bool = False
    FEATURE_FLAGS_ENABLED: bool = True
    HOT_RELOAD_ENABLED: bool = True
    CAPACITY_PLANNING_ENABLED: bool = True

    # ── Bool validators ────────────────────────────────────────────────────────
    # Coerce non-standard OS env values (e.g. DEBUG=release set by Node tooling)
    # to proper booleans before pydantic strict-bool parsing runs.

    @field_validator(
        "DEBUG", "ENABLE_TRACING", "KAFKA_ENABLED", "REDIS_ENABLED",
        "PROMETHEUS_ENABLED", "REQUIRE_DATABASE", "REQUIRE_BROKER",
        "AUTONOMOUS_CONTROLLER_ENABLED", "SELF_HEALING_ENABLED",
        "ADAPTIVE_OPTIMIZATION_ENABLED", "SELF_IMPROVEMENT_ENABLED",
        "DISTRIBUTED_MODE", "SECURITY_ENABLED", "AUDIT_LOG_ENABLED",
        "CIRCUIT_BREAKER_ENABLED", "DLQ_ENABLED", "OTEL_ENABLED",
        "GRAFANA_DASHBOARD_ENABLED", "MAINTENANCE_MODE_ENABLED",
        "FEATURE_FLAGS_ENABLED", "HOT_RELOAD_ENABLED",
        "CAPACITY_PLANNING_ENABLED",
        mode="before",
    )
    @classmethod
    def _coerce_bool_fields(cls, v: Any) -> bool:
        return _coerce_bool(v)

    # ── Properties ─────────────────────────────────────────────────────────────

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.POSTGRES_SERVER and self.POSTGRES_USER and self.POSTGRES_PASSWORD and self.POSTGRES_DB:
            return (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self.DATABASE_URL

    # ── Helpers ────────────────────────────────────────────────────────────────

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
            self.ALLOWED_ORIGINS = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        if not self.ALLOWED_ORIGINS:
            warnings.append("ALLOWED_ORIGINS is empty; browser clients will be rejected by CORS")

        if isinstance(self.KAFKA_TOPICS, str):
            self.KAFKA_TOPICS = [t.strip() for t in self.KAFKA_TOPICS.split(",") if t.strip()]
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
        for key, value in fresh.model_dump().items():
            setattr(self, key, value)
        return self

    def to_runtime_config(self) -> Dict[str, Any]:
        """Return a serializable snapshot of runtime configuration."""
        return self.model_dump()


# Singleton
settings = Settings()
