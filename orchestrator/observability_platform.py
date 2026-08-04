"""
Phase 15 — Enterprise Observability Platform.

Extends the existing RuntimeObservability (orchestrator/observability.py) with
enterprise-grade OpenTelemetry tracing hooks, Prometheus metrics export,
SLO/SLA tracking, and a unified ObservabilityPlatform facade.

The existing ``runtime_observability`` singleton is NOT modified.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "MetricType",
    "MetricEntry",
    "PrometheusExporter",
    "TraceSpan",
    "OpenTelemetryHook",
    "SLODefinition",
    "SLOTracker",
    "ObservabilityPlatform",
]


# ─── Metric Types ───────────────────────────────────────────────────────────


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


# ─── Metric Entry ───────────────────────────────────────────────────────────


@dataclass
class MetricEntry:
    name: str
    metric_type: MetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    help_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["metric_type"] = self.metric_type.value
        return d


# ─── Prometheus Exporter ────────────────────────────────────────────────────


class PrometheusExporter:
    """In-memory Prometheus-compatible metrics registry and text exporter."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._registry: Dict[str, Dict[str, Any]] = {}
        # name -> {"type": MetricType, "help": str, "entries": [MetricEntry]}

    def register_metric(
        self, name: str, metric_type: MetricType, help_text: str = ""
    ) -> None:
        with self._lock:
            if name not in self._registry:
                self._registry[name] = {
                    "type": metric_type,
                    "help": help_text,
                    "entries": [],
                }

    def record(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        with self._lock:
            if name not in self._registry:
                self._registry[name] = {
                    "type": MetricType.GAUGE,
                    "help": "",
                    "entries": [],
                }
            entry = MetricEntry(
                name=name,
                metric_type=self._registry[name]["type"],
                value=value,
                labels=labels or {},
            )
            self._registry[name]["entries"].append(entry)
            # Keep last 1000 entries per metric
            if len(self._registry[name]["entries"]) > 1000:
                self._registry[name]["entries"] = self._registry[name]["entries"][-500:]

    def increment(
        self, name: str, amount: float = 1.0, labels: Optional[Dict[str, str]] = None
    ) -> None:
        with self._lock:
            if name not in self._registry:
                self._registry[name] = {
                    "type": MetricType.COUNTER,
                    "help": "",
                    "entries": [],
                }
            entries = self._registry[name]["entries"]
            # Find matching labels entry and increment
            label_key = str(sorted((labels or {}).items()))
            current = 0.0
            for e in reversed(entries):
                if str(sorted(e.labels.items())) == label_key:
                    current = e.value
                    break
            entry = MetricEntry(
                name=name,
                metric_type=MetricType.COUNTER,
                value=current + amount,
                labels=labels or {},
            )
            entries.append(entry)

    def export_text(self) -> str:
        """Export all metrics in Prometheus text exposition format."""
        lines: List[str] = []
        with self._lock:
            for name, info in self._registry.items():
                if info["help"]:
                    lines.append(f"# HELP {name} {info['help']}")
                lines.append(f"# TYPE {name} {info['type'].value}")
                # Get latest entry per label combination
                latest: Dict[str, MetricEntry] = {}
                for entry in info["entries"]:
                    key = str(sorted(entry.labels.items()))
                    latest[key] = entry
                for entry in latest.values():
                    if entry.labels:
                        label_str = ",".join(
                            f'{k}="{v}"' for k, v in sorted(entry.labels.items())
                        )
                        lines.append(f"{name}{{{label_str}}} {entry.value}")
                    else:
                        lines.append(f"{name} {entry.value}")
        return "\n".join(lines) + "\n"

    def get_all_metrics(self) -> Dict[str, Any]:
        with self._lock:
            result = {}
            for name, info in self._registry.items():
                entries = info["entries"]
                latest = entries[-1].to_dict() if entries else None
                result[name] = {
                    "type": info["type"].value,
                    "help": info["help"],
                    "latest": latest,
                    "sample_count": len(entries),
                }
            return result

    def reset(self) -> None:
        with self._lock:
            for info in self._registry.values():
                info["entries"].clear()


# ─── Trace Span ─────────────────────────────────────────────────────────────


@dataclass
class TraceSpan:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: Optional[str] = None
    operation_name: str = ""
    service_name: str = "virtual-brain"
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    status: str = "ok"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is not None:
            return (self.end_time - self.start_time) * 1000
        return None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["duration_ms"] = self.duration_ms
        return d


# ─── OpenTelemetry Hook ─────────────────────────────────────────────────────


class OpenTelemetryHook:
    """In-memory OpenTelemetry-compatible trace collector."""

    def __init__(self, max_traces: int = 5000) -> None:
        self._lock = Lock()
        self._traces: List[TraceSpan] = []
        self._active: Dict[str, TraceSpan] = {}
        self._max_traces = max_traces

    def start_span(
        self,
        operation_name: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        span = TraceSpan(
            operation_name=operation_name,
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )
        with self._lock:
            self._active[span.span_id] = span
        return span

    def end_span(self, span: TraceSpan, status: str = "ok") -> None:
        span.end_time = time.monotonic()
        span.status = status
        with self._lock:
            self._active.pop(span.span_id, None)
            self._traces.append(span)
            if len(self._traces) > self._max_traces:
                self._traces = self._traces[-(self._max_traces // 2):]

    def add_event(self, span: TraceSpan, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        span.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def get_traces(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            traces = list(self._traces[-limit:])
        return [t.to_dict() for t in traces]

    def get_active_spans(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._active.values()]

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()
            self._active.clear()


# ─── SLO Tracker ────────────────────────────────────────────────────────────


@dataclass
class SLODefinition:
    name: str
    target_percentage: float
    metric_name: str
    description: str = ""
    total_outcomes: int = 0
    successful_outcomes: int = 0

    @property
    def current_percentage(self) -> float:
        if self.total_outcomes == 0:
            return 100.0
        return (self.successful_outcomes / self.total_outcomes) * 100.0

    @property
    def is_meeting_target(self) -> bool:
        return self.current_percentage >= self.target_percentage

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "target_percentage": self.target_percentage,
            "current_percentage": round(self.current_percentage, 4),
            "metric_name": self.metric_name,
            "description": self.description,
            "total_outcomes": self.total_outcomes,
            "successful_outcomes": self.successful_outcomes,
            "is_meeting_target": self.is_meeting_target,
        }


class SLOTracker:
    """Tracks SLO targets and actual performance compliance."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._slos: Dict[str, SLODefinition] = {}

    def define_slo(
        self,
        name: str,
        target_percentage: float,
        metric_name: str,
        description: str = "",
    ) -> SLODefinition:
        slo = SLODefinition(
            name=name,
            target_percentage=target_percentage,
            metric_name=metric_name,
            description=description,
        )
        with self._lock:
            self._slos[name] = slo
        logger.info("slo.defined name=%s target=%.2f%%", name, target_percentage)
        return slo

    def record_outcome(self, slo_name: str, success: bool) -> None:
        with self._lock:
            slo = self._slos.get(slo_name)
            if slo:
                slo.total_outcomes += 1
                if success:
                    slo.successful_outcomes += 1

    def get_slo_status(self, slo_name: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            if slo_name:
                slo = self._slos.get(slo_name)
                return slo.to_dict() if slo else {}
            return {name: slo.to_dict() for name, slo in self._slos.items()}

    def get_error_budget(self, slo_name: str) -> Dict[str, Any]:
        with self._lock:
            slo = self._slos.get(slo_name)
        if not slo:
            return {"error": "SLO not found"}
        allowed_failures = (
            (100.0 - slo.target_percentage) / 100.0
        ) * max(slo.total_outcomes, 1)
        actual_failures = slo.total_outcomes - slo.successful_outcomes
        remaining = max(0, allowed_failures - actual_failures)
        return {
            "slo_name": slo_name,
            "target_percentage": slo.target_percentage,
            "allowed_failures": round(allowed_failures, 2),
            "actual_failures": actual_failures,
            "remaining_budget": round(remaining, 2),
            "budget_consumed_pct": round(
                (actual_failures / max(allowed_failures, 0.001)) * 100, 2
            ),
        }


# ─── Observability Platform (Facade) ────────────────────────────────────────


class ObservabilityPlatform:
    """Unified enterprise observability facade composing metrics, tracing, and SLOs."""

    def __init__(self) -> None:
        self._metrics = PrometheusExporter()
        self._tracing = OpenTelemetryHook()
        self._slo_tracker = SLOTracker()

        # Register default brain metrics
        self._metrics.register_metric(
            "brain_requests_total", MetricType.COUNTER, "Total API requests"
        )
        self._metrics.register_metric(
            "brain_request_duration_ms", MetricType.HISTOGRAM, "Request latency in ms"
        )
        self._metrics.register_metric(
            "brain_active_agents", MetricType.GAUGE, "Currently active agents"
        )
        self._metrics.register_metric(
            "brain_errors_total", MetricType.COUNTER, "Total errors"
        )

        # Default SLOs
        self._slo_tracker.define_slo(
            "availability", 99.9, "brain_requests_total", "System availability SLO"
        )
        self._slo_tracker.define_slo(
            "latency_p99", 95.0, "brain_request_duration_ms", "P99 latency under 500ms"
        )

        logger.info("ObservabilityPlatform initialized")

    @property
    def metrics(self) -> PrometheusExporter:
        return self._metrics

    @property
    def tracing(self) -> OpenTelemetryHook:
        return self._tracing

    @property
    def slo_tracker(self) -> SLOTracker:
        return self._slo_tracker

    def get_full_status(self) -> Dict[str, Any]:
        return {
            "metrics_summary": self._metrics.get_all_metrics(),
            "active_spans": self._tracing.get_active_spans(),
            "recent_traces_count": len(self._tracing.get_traces(limit=100)),
            "slo_status": self._slo_tracker.get_slo_status(),
        }
