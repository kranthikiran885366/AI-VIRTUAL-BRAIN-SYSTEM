"""
Phase 15 — Secrets Management & Audit Logging.

Provides pluggable secret providers (environment, in-memory) and a structured,
tamper-evident audit logging system with query, export, and statistics support.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "AuditSeverity",
    "AuditEvent",
    "AuditLogger",
    "SecretProvider",
    "InMemorySecretProvider",
    "EnvironmentSecretProvider",
    "SecretManager",
]


# ─── Audit Severity ──────────────────────────────────────────────────────────


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"


# ─── Audit Event ─────────────────────────────────────────────────────────────


@dataclass
class AuditEvent:
    """Structured audit log entry with tamper-detection support."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    severity: AuditSeverity = AuditSeverity.INFO
    category: str = ""
    action: str = ""
    actor: str = "system"
    target: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    checksum: str = ""

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        raw = f"{self.event_id}|{self.timestamp}|{self.severity.value}|{self.category}|{self.action}|{self.actor}|{self.target}|{self.success}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        data = dict(data)
        if "severity" in data and isinstance(data["severity"], str):
            data["severity"] = AuditSeverity(data["severity"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ─── Audit Logger ────────────────────────────────────────────────────────────


class AuditLogger:
    """Thread-safe, in-memory structured audit logger with query and export."""

    def __init__(self, max_entries: int = 10_000) -> None:
        self._lock = Lock()
        self._events: List[AuditEvent] = []
        self._max_entries = max_entries

    def log(self, event: AuditEvent) -> None:
        with self._lock:
            if len(self._events) >= self._max_entries:
                self._events = self._events[-(self._max_entries // 2):]
            self._events.append(event)
        logger.debug("audit.event_logged event_id=%s action=%s", event.event_id, event.action)

    def log_action(
        self,
        action: str,
        category: str = "general",
        actor: str = "system",
        target: str = "",
        severity: AuditSeverity = AuditSeverity.INFO,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            severity=severity,
            category=category,
            action=action,
            actor=actor,
            target=target,
            details=details or {},
            success=success,
        )
        self.log(event)
        return event

    def query(
        self,
        severity: Optional[AuditSeverity] = None,
        category: Optional[str] = None,
        actor: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        with self._lock:
            results = list(self._events)
        if severity is not None:
            results = [e for e in results if e.severity == severity]
        if category is not None:
            results = [e for e in results if e.category == category]
        if actor is not None:
            results = [e for e in results if e.actor == actor]
        return results[-limit:]

    def export_events(
        self, start_time: Optional[str] = None, end_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._events)
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        return [e.to_dict() for e in events]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            events = list(self._events)
        by_severity: Dict[str, int] = defaultdict(int)
        by_category: Dict[str, int] = defaultdict(int)
        for e in events:
            by_severity[e.severity.value] += 1
            by_category[e.category] += 1
        return {
            "total_events": len(events),
            "by_severity": dict(by_severity),
            "by_category": dict(by_category),
        }

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


# ─── Secret Providers ────────────────────────────────────────────────────────


class SecretProvider(ABC):
    """Abstract interface for secret storage backends."""

    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        ...

    @abstractmethod
    def set_secret(self, key: str, value: str) -> None:
        ...

    @abstractmethod
    def delete_secret(self, key: str) -> bool:
        ...

    @abstractmethod
    def list_keys(self) -> List[str]:
        ...


class InMemorySecretProvider(SecretProvider):
    """In-memory secret provider for local development and testing."""

    def __init__(self) -> None:
        self._secrets: Dict[str, str] = {}
        self._lock = Lock()

    def get_secret(self, key: str) -> Optional[str]:
        with self._lock:
            return self._secrets.get(key)

    def set_secret(self, key: str, value: str) -> None:
        with self._lock:
            self._secrets[key] = value

    def delete_secret(self, key: str) -> bool:
        with self._lock:
            return self._secrets.pop(key, None) is not None

    def list_keys(self) -> List[str]:
        with self._lock:
            return list(self._secrets.keys())


class EnvironmentSecretProvider(SecretProvider):
    """Secret provider that reads from OS environment variables."""

    def __init__(self, prefix: str = "VBRAIN_SECRET_") -> None:
        self._prefix = prefix

    def get_secret(self, key: str) -> Optional[str]:
        return os.environ.get(f"{self._prefix}{key}")

    def set_secret(self, key: str, value: str) -> None:
        os.environ[f"{self._prefix}{key}"] = value

    def delete_secret(self, key: str) -> bool:
        env_key = f"{self._prefix}{key}"
        if env_key in os.environ:
            del os.environ[env_key]
            return True
        return False

    def list_keys(self) -> List[str]:
        return [
            k[len(self._prefix):]
            for k in os.environ
            if k.startswith(self._prefix)
        ]


# ─── Secret Manager ─────────────────────────────────────────────────────────


class SecretManager:
    """Manages secrets with pluggable backends and full audit logging."""

    def __init__(self, provider: Optional[SecretProvider] = None) -> None:
        self._provider = provider or EnvironmentSecretProvider()
        self._audit = AuditLogger(max_entries=5000)
        logger.info("SecretManager initialized provider=%s", type(self._provider).__name__)

    def get_secret(self, key: str) -> Optional[str]:
        value = self._provider.get_secret(key)
        self._audit.log_action(
            action="get_secret",
            category="secrets",
            target=key,
            success=value is not None,
            details={"found": value is not None},
        )
        return value

    def set_secret(self, key: str, value: str) -> None:
        self._provider.set_secret(key, value)
        self._audit.log_action(
            action="set_secret",
            category="secrets",
            target=key,
            severity=AuditSeverity.SECURITY,
        )

    def delete_secret(self, key: str) -> bool:
        result = self._provider.delete_secret(key)
        self._audit.log_action(
            action="delete_secret",
            category="secrets",
            target=key,
            severity=AuditSeverity.SECURITY,
            success=result,
        )
        return result

    def list_keys(self) -> List[str]:
        keys = self._provider.list_keys()
        self._audit.log_action(
            action="list_keys",
            category="secrets",
            details={"count": len(keys)},
        )
        return keys

    def rotate_secret(self, key: str, new_value: str) -> bool:
        old = self._provider.get_secret(key)
        self._provider.set_secret(key, new_value)
        self._audit.log_action(
            action="rotate_secret",
            category="secrets",
            target=key,
            severity=AuditSeverity.SECURITY,
            details={"had_previous": old is not None},
        )
        logger.info("secret.rotated key=%s", key)
        return True

    def get_audit_logger(self) -> AuditLogger:
        return self._audit
