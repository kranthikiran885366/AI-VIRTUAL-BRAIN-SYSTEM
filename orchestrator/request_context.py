"""Shared request and execution context for runtime infrastructure.

This module keeps request-scoped identifiers and execution metadata in
contextvars so FastAPI middleware, background tasks, and downstream services
can share correlation data without passing it manually everywhere.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterator, Optional


@dataclass
class RequestContext:
    correlation_id: str
    request_id: str
    trace_id: str
    user_context: Dict[str, Any] = field(default_factory=dict)
    agent_context: Dict[str, Any] = field(default_factory=dict)
    execution_context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "user_context": dict(self.user_context),
            "agent_context": dict(self.agent_context),
            "execution_context": dict(self.execution_context),
            "created_at": self.created_at,
            "cancelled": self.cancel_event.is_set(),
        }


_request_context_var: contextvars.ContextVar[Optional[RequestContext]] = contextvars.ContextVar(
    "request_context",
    default=None,
)


def _generate_identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def build_request_context(
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    user_context: Optional[Dict[str, Any]] = None,
    agent_context: Optional[Dict[str, Any]] = None,
    execution_context: Optional[Dict[str, Any]] = None,
) -> RequestContext:
    return RequestContext(
        correlation_id=correlation_id or _generate_identifier("corr"),
        request_id=request_id or _generate_identifier("req"),
        trace_id=trace_id or _generate_identifier("trace"),
        user_context=user_context or {},
        agent_context=agent_context or {},
        execution_context=execution_context or {},
    )


def set_request_context(context: RequestContext) -> contextvars.Token:
    return _request_context_var.set(context)


def get_request_context() -> Optional[RequestContext]:
    return _request_context_var.get()


def clear_request_context(token: Optional[contextvars.Token] = None) -> None:
    if token is not None:
        _request_context_var.reset(token)
    else:
        _request_context_var.set(None)


def get_correlation_id(default: Optional[str] = None) -> str:
    context = get_request_context()
    if context:
        return context.correlation_id
    return default or _generate_identifier("corr")


def get_request_id(default: Optional[str] = None) -> str:
    context = get_request_context()
    if context:
        return context.request_id
    return default or _generate_identifier("req")


def get_trace_id(default: Optional[str] = None) -> str:
    context = get_request_context()
    if context:
        return context.trace_id
    return default or _generate_identifier("trace")


def request_is_cancelled() -> bool:
    context = get_request_context()
    return bool(context and context.cancel_event.is_set())


def cancel_current_request() -> None:
    context = get_request_context()
    if context:
        context.cancel_event.set()


@contextlib.contextmanager
def bind_request_context(context: RequestContext) -> Iterator[RequestContext]:
    token = set_request_context(context)
    try:
        yield context
    finally:
        clear_request_context(token)
