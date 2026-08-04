"""
Phase 14 — Execution Analytics Engine.

Calculates real-time, windowed performance analytics across the cognitive system:
  - Throughput (tasks/sec)
  - Latency percentiles (p50, p95, p99)
  - Success, failure, and timeout rates
  - CPU, memory, GPU utilization
  - Per-agent workload and task distribution
  - Automated bottleneck detection
  - System capacity estimation
"""
from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Tuple

from orchestrator.cognitive_models import ExecutionAnalytics

logger = logging.getLogger(__name__)


class ExecutionAnalyticsEngine:
    """
    Computes windowed execution analytics for the AI Virtual Brain System.
    Thread-safe and non-blocking.
    """

    def __init__(self, window_seconds: int = 300, max_samples: int = 10000):
        self._window_seconds: int = window_seconds
        self._max_samples: int = max_samples
        self._latency_samples: Deque[Tuple[float, float]] = deque(maxlen=max_samples)  # (timestamp, latency_ms)
        self._execution_records: Deque[Dict[str, Any]] = deque(maxlen=max_samples)  # record dicts
        self._agent_task_counts: Dict[str, int] = {}
        self._task_type_counts: Dict[str, int] = {}
        self._total_requests: int = 0
        self._total_successes: int = 0
        self._total_failures: int = 0
        self._total_timeouts: int = 0

    def record_execution(
        self,
        agent_name: str,
        action: str,
        latency_ms: float,
        success: bool = True,
        timed_out: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """Record an execution event for real-time analytics tracking."""
        now = time.time()
        self._total_requests += 1

        if timed_out:
            self._total_timeouts += 1
        elif success:
            self._total_successes += 1
        else:
            self._total_failures += 1

        self._latency_samples.append((now, float(latency_ms)))
        self._agent_task_counts[agent_name] = self._agent_task_counts.get(agent_name, 0) + 1
        self._task_type_counts[action] = self._task_type_counts.get(action, 0) + 1

        record = {
            "timestamp": now,
            "agent": agent_name,
            "action": action,
            "latency_ms": latency_ms,
            "success": success,
            "timed_out": timed_out,
            "error": error,
        }
        self._execution_records.append(record)

    def generate_analytics(
        self,
        cpu_utilization: float = 0.0,
        memory_utilization: float = 0.0,
        gpu_utilization: float = 0.0,
    ) -> ExecutionAnalytics:
        """Compute windowed metrics and percentiles over the defined time window."""
        now = time.time()
        cutoff = now - self._window_seconds

        # Filter windowed latency samples
        window_latencies = [lat for ts, lat in self._latency_samples if ts >= cutoff]
        window_records = [r for r in self._execution_records if r["timestamp"] >= cutoff]

        total_window = len(window_records)
        if total_window == 0:
            return ExecutionAnalytics(
                window_seconds=self._window_seconds,
                timestamp=datetime.utcnow().isoformat(),
                cpu_utilization=cpu_utilization,
                memory_utilization=memory_utilization,
                gpu_utilization=gpu_utilization,
            )

        # Percentiles
        sorted_lat = sorted(window_latencies)
        avg_lat = sum(sorted_lat) / len(sorted_lat)
        p50 = sorted_lat[int(len(sorted_lat) * 0.50)]
        p95 = sorted_lat[min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)]
        p99 = sorted_lat[min(int(len(sorted_lat) * 0.99), len(sorted_lat) - 1)]

        # Rates
        successes = sum(1 for r in window_records if r["success"] and not r["timed_out"])
        failures = sum(1 for r in window_records if not r["success"] and not r["timed_out"])
        timeouts = sum(1 for r in window_records if r["timed_out"])

        success_rate = round(successes / total_window, 4)
        failure_rate = round(failures / total_window, 4)
        timeout_rate = round(timeouts / total_window, 4)
        throughput = round(total_window / self._window_seconds, 2)

        # Agent utilization ratios
        agent_counts: Dict[str, int] = {}
        for r in window_records:
            agent_counts[r["agent"]] = agent_counts.get(r["agent"], 0) + 1

        agent_utilization = {
            agent: round(count / total_window, 4) for agent, count in agent_counts.items()
        }

        # Task distribution
        task_dist: Dict[str, int] = {}
        for r in window_records:
            task_dist[r["action"]] = task_dist.get(r["action"], 0) + 1

        # Bottlenecks & capacity
        bottlenecks: List[str] = []
        if p95 > 2000.0:
            bottlenecks.append(f"HIGH_P95_LATENCY: {p95:.1f}ms")
        if timeout_rate > 0.05:
            bottlenecks.append(f"HIGH_TIMEOUT_RATE: {timeout_rate:.2%}")
        if failure_rate > 0.10:
            bottlenecks.append(f"HIGH_FAILURE_RATE: {failure_rate:.2%}")
        if cpu_utilization > 85.0:
            bottlenecks.append(f"CPU_SATURATION: {cpu_utilization:.1f}%")

        # Capacity estimate (scale 0.0 - 1.0 based on bottleneck factors)
        headroom = max(0.1, 1.0 - (cpu_utilization / 100.0 * 0.5 + failure_rate * 0.5))
        capacity_est = round(headroom, 2)

        return ExecutionAnalytics(
            window_seconds=self._window_seconds,
            timestamp=datetime.utcnow().isoformat(),
            throughput_per_sec=throughput,
            avg_latency_ms=round(avg_lat, 2),
            p50_latency_ms=round(p50, 2),
            p95_latency_ms=round(p95, 2),
            p99_latency_ms=round(p99, 2),
            success_rate=success_rate,
            failure_rate=failure_rate,
            timeout_rate=timeout_rate,
            cpu_utilization=cpu_utilization,
            memory_utilization=memory_utilization,
            gpu_utilization=gpu_utilization,
            agent_utilization=agent_utilization,
            task_distribution=task_dist,
            bottlenecks=bottlenecks,
            capacity_estimate=capacity_est,
        )

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_requests": self._total_requests,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "total_timeouts": self._total_timeouts,
            "agent_task_counts": dict(self._agent_task_counts),
            "task_type_counts": dict(self._task_type_counts),
        }
