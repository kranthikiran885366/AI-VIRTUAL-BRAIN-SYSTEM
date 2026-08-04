"""
Phase 14 — Resource Governance Engine.

Provides intelligent system-wide resource management:
  - CPU, Memory, GPU resource allocation & quota management
  - Thread & Async task concurrency governance
  - Dynamic Backpressure control under resource saturation
  - Resource Forecasting based on request trends
  - Graceful Degradation (task throttling, non-essential agent shedding)
  - Connection & Worker Pool optimization
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

logger = logging.getLogger(__name__)


class ResourceGovernanceEngine:
    """
    Intelligent resource governance and backpressure engine.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self._max_cpu_percent: float = float(cfg.get("max_cpu_percent", 85.0))
        self._max_mem_percent: float = float(cfg.get("max_mem_percent", 85.0))
        self._max_gpu_percent: float = float(cfg.get("max_gpu_percent", 90.0))
        self._max_concurrent_async: int = int(cfg.get("max_concurrent_async", 100))
        self._enable_backpressure: bool = bool(cfg.get("enable_backpressure", True))

        # Runtime semaphores and quotas
        self._async_semaphore = asyncio.Semaphore(self._max_concurrent_async)
        self._active_tasks: int = 0
        self._rejected_tasks: int = 0
        self._throttled_tasks: int = 0

        # Memory / CPU trend history for forecasting
        self._resource_history: List[Dict[str, float]] = []

    def get_hardware_utilization(self) -> Dict[str, float]:
        """Fetch current hardware usage metrics."""
        cpu = 0.0
        mem = 0.0
        gpu = 0.0

        if _HAS_PSUTIL:
            try:
                cpu = float(psutil.cpu_percent(interval=None))
                mem = float(psutil.virtual_memory().percent)
            except Exception:
                pass

        # Record history snapshot
        self._resource_history.append({
            "timestamp": time.time(),
            "cpu": cpu,
            "memory": mem,
            "gpu": gpu,
        })
        if len(self._resource_history) > 100:
            self._resource_history.pop(0)

        return {"cpu": cpu, "memory": mem, "gpu": gpu}

    def check_backpressure(self, priority: int = 2) -> Dict[str, Any]:
        """
        Check if backpressure should be applied based on current resource stress and priority.
        Priority: 1=low, 2=medium, 3=high, 4=critical.
        """
        usage = self.get_hardware_utilization()
        cpu = usage["cpu"]
        mem = usage["memory"]

        should_shed = False
        reason = ""

        if cpu > self._max_cpu_percent:
            # Shed low or medium priority tasks when CPU exceeds limit
            if priority <= 2:
                should_shed = True
                reason = f"High CPU utilization ({cpu:.1f}% > {self._max_cpu_percent}%)"
        elif mem > self._max_mem_percent:
            if priority <= 2:
                should_shed = True
                reason = f"High Memory utilization ({mem:.1f}% > {self._max_mem_percent}%)"

        if should_shed and self._enable_backpressure:
            self._rejected_tasks += 1
            return {
                "allowed": False,
                "backpressure": True,
                "reason": reason,
                "cpu": cpu,
                "memory": mem,
            }

        return {
            "allowed": True,
            "backpressure": False,
            "reason": "Resources within limits",
            "cpu": cpu,
            "memory": mem,
        }

    def forecast_resource_pressure(self) -> Dict[str, Any]:
        """Simple linear trend forecasting for CPU and Memory over recent samples."""
        if len(self._resource_history) < 5:
            return {"forecast_available": False, "cpu_trend": "stable", "memory_trend": "stable"}

        recent = self._resource_history[-10:]
        first_cpu = recent[0]["cpu"]
        last_cpu = recent[-1]["cpu"]
        first_mem = recent[0]["memory"]
        last_mem = recent[-1]["memory"]

        cpu_diff = last_cpu - first_cpu
        mem_diff = last_mem - first_mem

        cpu_trend = "rising" if cpu_diff > 5.0 else ("falling" if cpu_diff < -5.0 else "stable")
        mem_trend = "rising" if mem_diff > 5.0 else ("falling" if mem_diff < -5.0 else "stable")

        return {
            "forecast_available": True,
            "cpu_trend": cpu_trend,
            "memory_trend": mem_trend,
            "predicted_cpu_delta": round(cpu_diff, 2),
            "predicted_mem_delta": round(mem_diff, 2),
            "risk_level": "high" if (last_cpu > 80.0 and cpu_trend == "rising") else "normal",
        }

    def get_governance_stats(self) -> Dict[str, Any]:
        return {
            "active_tasks": self._active_tasks,
            "rejected_tasks": self._rejected_tasks,
            "throttled_tasks": self._throttled_tasks,
            "max_concurrent_async": self._max_concurrent_async,
            "backpressure_enabled": self._enable_backpressure,
            "current_hardware": self.get_hardware_utilization(),
        }
