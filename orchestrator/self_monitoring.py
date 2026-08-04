"""
Phase 14 — Self-Monitoring Engine.

Continuously monitors:
  - Agent health (via AgentManager + AgentLifecycleManager)
  - System resources (CPU, memory — via psutil when available)
  - Queue depths (TaskScheduler + MessageBroker)
  - Execution latency and throughput (RuntimeObservability)
  - Error and timeout rates
  - Confidence trends

Produces structured MonitoringReport objects.
Does NOT modify any existing component — read-only observation.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False
    psutil = None  # type: ignore

from orchestrator.cognitive_models import (
    MonitoringReport, SystemHealthLevel, Phase14Metrics,
)

logger = logging.getLogger(__name__)


class SelfMonitoringEngine:
    """
    Read-only system observer.

    Wires into existing components via constructor injection.
    Never modifies agent state — only reads and reports.
    """

    def __init__(self, config: Dict[str, Any]):
        self._cfg = config
        mon_cfg = config.get("monitoring", {})

        self._interval: float = float(mon_cfg.get("interval_seconds", 30.0))
        self._history_limit: int = int(mon_cfg.get("history_limit", 200))
        self._cpu_warn: float = float(mon_cfg.get("cpu_warn_threshold", 80.0))
        self._mem_warn: float = float(mon_cfg.get("mem_warn_threshold", 80.0))
        self._error_rate_warn: float = float(mon_cfg.get("error_rate_warn", 0.10))
        self._latency_warn_ms: float = float(mon_cfg.get("latency_warn_ms", 2000.0))
        self._queue_warn: int = int(mon_cfg.get("queue_depth_warn", 500))

        # Injected dependencies (all optional — degrade gracefully)
        self._agent_manager: Optional[Any] = None
        self._lifecycle_manager: Optional[Any] = None
        self._task_scheduler: Optional[Any] = None
        self._message_broker: Optional[Any] = None
        self._observability: Optional[Any] = None

        # State
        self._running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._session_id: str = ""
        self._report_history: Deque[MonitoringReport] = deque(maxlen=self._history_limit)
        self._metrics = Phase14Metrics()

        # Rolling counters for rate calculation
        self._prev_completed: int = 0
        self._prev_failed: int = 0
        self._prev_ts: float = time.monotonic()

    # ─── Dependency Injection ─────────────────────────────────────────────────

    def wire(
        self,
        agent_manager=None,
        lifecycle_manager=None,
        task_scheduler=None,
        message_broker=None,
        observability=None,
    ):
        self._agent_manager = agent_manager
        self._lifecycle_manager = lifecycle_manager
        self._task_scheduler = task_scheduler
        self._message_broker = message_broker
        self._observability = observability

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self, session_id: str = ""):
        if self._running:
            return
        self._running = True
        self._session_id = session_id
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(), name="phase14.monitoring"
        )
        logger.info("SelfMonitoringEngine started session_id=%s", session_id)

    async def stop(self):
        self._running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("SelfMonitoringEngine stopped")

    # ─── Monitoring Loop ──────────────────────────────────────────────────────

    async def _monitor_loop(self):
        while self._running:
            try:
                report = await self.collect()
                self._report_history.append(report)
                self._metrics.monitoring_cycles += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("SelfMonitoringEngine._monitor_loop error=%s", e)
                self._metrics.errors += 1
            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break

    # ─── Collection ───────────────────────────────────────────────────────────

    async def collect(self) -> MonitoringReport:
        """Collect a full monitoring snapshot. Safe to call externally."""
        t0 = time.perf_counter()

        cpu, memory = self._collect_resources()
        agent_health = await self._collect_agent_health()
        queue_depth = await self._collect_queue_depth()
        throughput, error_rate, timeout_rate, avg_latency = self._collect_execution_stats()

        alerts = self._evaluate_alerts(cpu, memory, queue_depth, error_rate, avg_latency)
        recommendations = self._generate_recommendations(
            cpu, memory, queue_depth, error_rate, avg_latency, agent_health
        )

        health_level = self._compute_health_level(cpu, memory, error_rate, agent_health)

        report = MonitoringReport(
            session_id=self._session_id,
            health_level=health_level,
            cpu_usage=cpu,
            memory_usage=memory,
            queue_depth=queue_depth,
            throughput=throughput,
            error_rate=error_rate,
            timeout_rate=timeout_rate,
            avg_latency_ms=avg_latency,
            agent_health=agent_health,
            alerts=alerts,
            recommendations=recommendations,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._metrics.total_latency_ms += elapsed_ms
        return report

    # ─── Resource Collection ──────────────────────────────────────────────────

    def _collect_resources(self):
        if not _HAS_PSUTIL:
            return 0.0, 0.0
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            return float(cpu), float(mem)
        except Exception:
            return 0.0, 0.0

    # ─── Agent Health ─────────────────────────────────────────────────────────

    async def _collect_agent_health(self) -> Dict[str, str]:
        health: Dict[str, str] = {}

        # From AgentManager
        if self._agent_manager:
            try:
                snapshot = self._agent_manager.get_capability_snapshot()
                for agent_id, status in snapshot.get("agent_health", {}).items():
                    health[agent_id] = str(status)
            except Exception as e:
                logger.debug("SelfMonitoringEngine: agent_manager health error=%s", e)

        # From LifecycleManager (fills gaps)
        if self._lifecycle_manager:
            try:
                statuses = await self._lifecycle_manager.get_all_agent_statuses()
                for agent_id, info in statuses.items():
                    if agent_id not in health:
                        health[agent_id] = info.get("status", "unknown")
            except Exception as e:
                logger.debug("SelfMonitoringEngine: lifecycle health error=%s", e)

        return health

    # ─── Queue Depth ─────────────────────────────────────────────────────────

    async def _collect_queue_depth(self) -> int:
        total = 0
        if self._task_scheduler:
            try:
                status = await self._task_scheduler.get_status()
                total += int(status.get("queue_size", 0))
                total += int(status.get("running_tasks", 0))
            except Exception:
                pass
        if self._message_broker:
            try:
                stats = await self._message_broker.get_stats()
                total += int(stats.get("queue_size", 0))
            except Exception:
                pass
        return total

    # ─── Execution Stats ──────────────────────────────────────────────────────

    def _collect_execution_stats(self):
        """Compute throughput, error_rate, timeout_rate, avg_latency from observability."""
        if self._observability:
            try:
                snap = self._observability.snapshot()
                total = max(1, snap.request_count)
                error_rate = round(snap.error_count / total, 4)
                avg_latency = round(snap.latency_ms, 2)

                now = time.monotonic()
                elapsed = max(0.001, now - self._prev_ts)
                completed = snap.request_count - self._prev_completed
                throughput = round(completed / elapsed, 2)
                self._prev_completed = snap.request_count
                self._prev_ts = now

                return throughput, error_rate, 0.0, avg_latency
            except Exception:
                pass

        if self._task_scheduler:
            try:
                # Synchronous metrics dict access
                m = self._task_scheduler.metrics
                total = max(1, m.get("total_tasks", 1))
                error_rate = round(m.get("failed_tasks", 0) / total, 4)
                timeout_rate = round(m.get("cancelled_tasks", 0) / total, 4)
                avg_latency = round(m.get("average_completion_time", 0.0) * 1000, 2)

                now = time.monotonic()
                elapsed = max(0.001, now - self._prev_ts)
                completed = m.get("completed_tasks", 0) - self._prev_completed
                throughput = round(max(0, completed) / elapsed, 2)
                self._prev_completed = m.get("completed_tasks", 0)
                self._prev_ts = now

                return throughput, error_rate, timeout_rate, avg_latency
            except Exception:
                pass

        return 0.0, 0.0, 0.0, 0.0

    # ─── Alert Evaluation ─────────────────────────────────────────────────────

    def _evaluate_alerts(
        self, cpu: float, memory: float, queue: int,
        error_rate: float, latency_ms: float
    ) -> List[str]:
        alerts = []
        if cpu > self._cpu_warn:
            alerts.append(f"HIGH_CPU: {cpu:.1f}% > {self._cpu_warn}%")
        if memory > self._mem_warn:
            alerts.append(f"HIGH_MEMORY: {memory:.1f}% > {self._mem_warn}%")
        if queue > self._queue_warn:
            alerts.append(f"QUEUE_DEPTH: {queue} > {self._queue_warn}")
        if error_rate > self._error_rate_warn:
            alerts.append(f"HIGH_ERROR_RATE: {error_rate:.2%} > {self._error_rate_warn:.2%}")
        if latency_ms > self._latency_warn_ms:
            alerts.append(f"HIGH_LATENCY: {latency_ms:.0f}ms > {self._latency_warn_ms:.0f}ms")
        return alerts

    # ─── Recommendations ─────────────────────────────────────────────────────

    def _generate_recommendations(
        self, cpu: float, memory: float, queue: int,
        error_rate: float, latency_ms: float,
        agent_health: Dict[str, str],
    ) -> List[str]:
        recs = []
        if cpu > self._cpu_warn:
            recs.append("Consider reducing parallel task concurrency to lower CPU pressure.")
        if memory > self._mem_warn:
            recs.append("Consider clearing agent memory caches or reducing history limits.")
        if queue > self._queue_warn:
            recs.append("Queue depth is high — consider increasing max_concurrent_tasks.")
        if error_rate > self._error_rate_warn:
            recs.append("Error rate elevated — review failing agents and retry policies.")
        if latency_ms > self._latency_warn_ms:
            recs.append("High latency detected — consider timeout adjustment or load balancing.")
        unhealthy = [a for a, s in agent_health.items() if s in ("unhealthy", "error", "critical")]
        if unhealthy:
            recs.append(f"Unhealthy agents detected: {', '.join(unhealthy[:5])} — trigger recovery.")
        return recs

    # ─── Health Level ─────────────────────────────────────────────────────────

    def _compute_health_level(
        self, cpu: float, memory: float,
        error_rate: float, agent_health: Dict[str, str]
    ) -> SystemHealthLevel:
        unhealthy_count = sum(
            1 for s in agent_health.values()
            if s in ("unhealthy", "error", "critical")
        )
        total_agents = max(1, len(agent_health))
        unhealthy_ratio = unhealthy_count / total_agents

        if (cpu > 95 or memory > 95 or error_rate > 0.5 or unhealthy_ratio > 0.5):
            return SystemHealthLevel.CRITICAL
        if (cpu > self._cpu_warn or memory > self._mem_warn or
                error_rate > self._error_rate_warn or unhealthy_ratio > 0.2):
            return SystemHealthLevel.DEGRADED
        return SystemHealthLevel.HEALTHY

    # ─── Public API ───────────────────────────────────────────────────────────

    def get_latest_report(self) -> Optional[MonitoringReport]:
        return self._report_history[-1] if self._report_history else None

    def get_report_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        history = list(self._report_history)
        return [r.to_dict() for r in history[-limit:]]

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics.as_dict(),
            "avg_cycle_ms": self._metrics.avg_cycle_ms(),
            "history_size": len(self._report_history),
            "running": self._running,
        }
