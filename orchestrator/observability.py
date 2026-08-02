"""Runtime observability helpers.

The goal here is to provide lightweight request and execution telemetry that can
be consumed by middleware, background workers, and infrastructure services.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from threading import Lock
from typing import Any, Deque, Dict, Optional


@dataclass
class ExecutionTimelineEntry:
    name: str
    started_at: str
    finished_at: Optional[str] = None
    latency_ms: Optional[float] = None
    status: str = "running"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeSnapshot:
    request_count: int = 0
    error_count: int = 0
    active_requests: int = 0
    queue_usage: Dict[str, Any] = field(default_factory=dict)
    agent_usage: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    traces_recorded: int = 0


class RuntimeObservability:
    """In-memory runtime observability collector."""

    def __init__(self, max_timeline_entries: int = 1000) -> None:
        self._lock = Lock()
        self._request_count = 0
        self._error_count = 0
        self._active_requests = 0
        self._traces_recorded = 0
        self._latency_total = 0.0
        self._queue_usage: Dict[str, Any] = {}
        self._agent_usage: Dict[str, Any] = defaultdict(int)
        self._timelines: Deque[ExecutionTimelineEntry] = deque(maxlen=max_timeline_entries)

    def begin_request(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> ExecutionTimelineEntry:
        entry = ExecutionTimelineEntry(name=name, started_at=datetime.utcnow().isoformat(), metadata=metadata or {})
        with self._lock:
            self._request_count += 1
            self._active_requests += 1
            self._traces_recorded += 1
            self._timelines.append(entry)
        return entry

    def end_request(self, entry: ExecutionTimelineEntry, status: str, latency_ms: float, error: Optional[str] = None) -> None:
        entry.finished_at = datetime.utcnow().isoformat()
        entry.latency_ms = latency_ms
        entry.status = status
        if error:
            entry.metadata["error"] = error
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            self._latency_total += latency_ms
            if status != "success":
                self._error_count += 1

    def record_queue_usage(self, queue_name: str, size: int, max_size: Optional[int] = None) -> None:
        with self._lock:
            self._queue_usage[queue_name] = {
                "size": size,
                "max_size": max_size,
                "updated_at": datetime.utcnow().isoformat(),
            }

    def record_agent_usage(self, agent_name: str, usage: Dict[str, Any]) -> None:
        with self._lock:
            self._agent_usage[agent_name] = dict(usage)

    def record_error(self) -> None:
        with self._lock:
            self._error_count += 1

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            average_latency = self._latency_total / self._request_count if self._request_count else 0.0
            return RuntimeSnapshot(
                request_count=self._request_count,
                error_count=self._error_count,
                active_requests=self._active_requests,
                queue_usage=dict(self._queue_usage),
                agent_usage=dict(self._agent_usage),
                latency_ms=average_latency,
                traces_recorded=self._traces_recorded,
            )

    def recent_timeline(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "entries": [asdict(entry) for entry in list(self._timelines)],
                "count": len(self._timelines),
            }


runtime_observability = RuntimeObservability()
