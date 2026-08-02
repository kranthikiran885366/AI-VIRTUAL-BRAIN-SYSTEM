"""
Production exception hierarchy for the AI Virtual Brain System.

Usage:
    from orchestrator.exceptions import AgentNotFoundError, TaskTimeoutError
"""

from __future__ import annotations
from typing import Any, Dict, Optional


class VirtualBrainError(Exception):
    """Root exception for all Virtual Brain System errors."""
    recoverable: bool = True

    def __init__(self, message: str, *, context: Optional[Dict[str, Any]] = None,
                 cause: Optional[BaseException] = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: Dict[str, Any] = context or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        return {"error": type(self).__name__, "message": self.message,
                "recoverable": self.recoverable, "context": self.context}


# ─── Configuration ────────────────────────────────────────────────────────────

class ConfigurationError(VirtualBrainError):
    recoverable = False

class MissingConfigurationError(ConfigurationError):
    def __init__(self, key: str, **kw: Any) -> None:
        super().__init__(f"Required configuration key '{key}' is missing", **kw)
        self.key = key

class InvalidConfigurationError(ConfigurationError):
    def __init__(self, key: str, value: Any, reason: str, **kw: Any) -> None:
        super().__init__(f"Config key '{key}' invalid value {value!r}: {reason}", **kw)
        self.key = key; self.value = value; self.reason = reason


# ─── Agent ────────────────────────────────────────────────────────────────────

class AgentError(VirtualBrainError):
    def __init__(self, message: str, *, agent_id: Optional[str] = None, **kw: Any) -> None:
        super().__init__(message, **kw)
        self.agent_id = agent_id
        if agent_id:
            self.context["agent_id"] = agent_id

class AgentNotFoundError(AgentError):
    recoverable = False
    def __init__(self, agent_id: str, **kw: Any) -> None:
        super().__init__(f"Agent '{agent_id}' not found", agent_id=agent_id, **kw)

class AgentInitializationError(AgentError):
    recoverable = True
    def __init__(self, agent_id: str, reason: str, **kw: Any) -> None:
        super().__init__(f"Agent '{agent_id}' failed to initialize: {reason}",
                         agent_id=agent_id, **kw)
        self.reason = reason

class AgentShutdownError(AgentError):
    recoverable = True

class AgentExecutionError(AgentError):
    recoverable = True
    def __init__(self, agent_id: str, action: str, reason: str, **kw: Any) -> None:
        super().__init__(f"Agent '{agent_id}' failed action '{action}': {reason}",
                         agent_id=agent_id, **kw)
        self.action = action; self.reason = reason
        self.context["action"] = action

class AgentTimeoutError(AgentError):
    recoverable = True
    def __init__(self, agent_id: str, timeout_seconds: float, **kw: Any) -> None:
        super().__init__(f"Agent '{agent_id}' timed out after {timeout_seconds}s",
                         agent_id=agent_id, **kw)
        self.timeout_seconds = timeout_seconds
        self.context["timeout_seconds"] = timeout_seconds

class AgentAlreadyRunningError(AgentError):
    recoverable = False

class AgentNotRunningError(AgentError):
    recoverable = True


# ─── Task ─────────────────────────────────────────────────────────────────────

class TaskError(VirtualBrainError):
    def __init__(self, message: str, *, task_id: Optional[str] = None, **kw: Any) -> None:
        super().__init__(message, **kw)
        self.task_id = task_id
        if task_id:
            self.context["task_id"] = task_id

class TaskNotFoundError(TaskError):
    recoverable = False
    def __init__(self, task_id: str, **kw: Any) -> None:
        super().__init__(f"Task '{task_id}' not found", task_id=task_id, **kw)

class TaskTimeoutError(TaskError):
    recoverable = True
    def __init__(self, task_id: str, timeout_seconds: float, **kw: Any) -> None:
        super().__init__(f"Task '{task_id}' timed out after {timeout_seconds}s",
                         task_id=task_id, **kw)
        self.timeout_seconds = timeout_seconds

class TaskCancelledError(TaskError):
    recoverable = True

class TaskDependencyError(TaskError):
    recoverable = True
    def __init__(self, task_id: str, missing_deps: list, **kw: Any) -> None:
        super().__init__(f"Task '{task_id}' has unsatisfied dependencies: {missing_deps}",
                         task_id=task_id, **kw)
        self.missing_deps = missing_deps


# ─── Broker ───────────────────────────────────────────────────────────────────

class BrokerError(VirtualBrainError):
    pass

class BrokerNotInitializedError(BrokerError):
    recoverable = False
    def __init__(self, **kw: Any) -> None:
        super().__init__("Message broker not initialized — call start() first", **kw)

class BrokerPublishError(BrokerError):
    recoverable = True
    def __init__(self, topic: str, reason: str, **kw: Any) -> None:
        super().__init__(f"Failed to publish to topic '{topic}': {reason}", **kw)
        self.topic = topic

class BrokerQueueFullError(BrokerError):
    recoverable = True
    def __init__(self, queue_size: int, **kw: Any) -> None:
        super().__init__(f"Message queue full (size={queue_size})", **kw)
        self.queue_size = queue_size


# ─── Database ─────────────────────────────────────────────────────────────────

class DatabaseError(VirtualBrainError):
    pass

class DatabaseConnectionError(DatabaseError):
    recoverable = True

class DatabaseQueryError(DatabaseError):
    recoverable = True
    def __init__(self, sql: str, reason: str, **kw: Any) -> None:
        super().__init__(f"Database query failed: {reason}", **kw)
        self.sql = sql; self.reason = reason


# ─── Validation ───────────────────────────────────────────────────────────────

class ValidationError(VirtualBrainError):
    recoverable = False
    def __init__(self, field: str, value: Any, reason: str, **kw: Any) -> None:
        super().__init__(f"Validation failed for '{field}': {reason} (got {value!r})", **kw)
        self.field = field; self.value = value; self.reason = reason

class PayloadTooLargeError(ValidationError):
    def __init__(self, size_bytes: int, max_bytes: int, **kw: Any) -> None:
        super().__init__("input_data", size_bytes,
                         f"size {size_bytes}B exceeds max {max_bytes}B", **kw)
        self.size_bytes = size_bytes; self.max_bytes = max_bytes


# ─── Lifecycle ────────────────────────────────────────────────────────────────

class LifecycleError(VirtualBrainError):
    pass

class StartupError(LifecycleError):
    recoverable = False

class ShutdownError(LifecycleError):
    recoverable = True


# ─── Resource ─────────────────────────────────────────────────────────────────

class ResourceError(VirtualBrainError):
    pass

class InsufficientResourcesError(ResourceError):
    recoverable = True
    def __init__(self, resource: str, requested: Any, available: Any, **kw: Any) -> None:
        super().__init__(
            f"Insufficient {resource}: requested {requested}, available {available}", **kw)
        self.resource = resource; self.requested = requested; self.available = available
