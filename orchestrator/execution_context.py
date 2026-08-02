"""Lightweight execution context helpers for orchestrator and broker components."""

from __future__ import annotations

import contextvars
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExecutionContext:
    """Execution-scoped metadata that can be bound to the current task."""

    request_id: str
    correlation_id: str
    trace_id: str
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    conversation_id: Optional[str] = None
    timeout: Optional[float] = None
    retry_count: int = 0
    priority: int = 2
    deadline: Optional[str] = None
    span_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def bind(self) -> contextvars.Token:
        return _execution_context_var.set(self)

    def unbind(self, token: contextvars.Token) -> None:
        _execution_context_var.reset(token)


_execution_context_var: contextvars.ContextVar[Optional[ExecutionContext]] = contextvars.ContextVar(
    "execution_context",
    default=None,
)


def build_execution_context(
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    task_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    timeout: Optional[float] = None,
    retry_count: int = 0,
    priority: int = 2,
    deadline: Optional[str] = None,
    span_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ExecutionContext:
    return ExecutionContext(
        request_id=request_id or f"req-{uuid.uuid4().hex}",
        correlation_id=correlation_id or f"corr-{uuid.uuid4().hex}",
        trace_id=trace_id or f"trace-{uuid.uuid4().hex}",
        task_id=task_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        timeout=timeout,
        retry_count=retry_count,
        priority=priority,
        deadline=deadline,
        span_id=span_id or f"span-{uuid.uuid4().hex[:8]}",
        metadata=metadata or {},
    )


def get_execution_context() -> Optional[ExecutionContext]:
    return _execution_context_var.get()


def clear_execution_context(token: Optional[contextvars.Token] = None) -> None:
    if token is not None:
        _execution_context_var.reset(token)
    else:
        _execution_context_var.set(None)
