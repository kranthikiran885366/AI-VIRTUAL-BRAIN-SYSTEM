"""
Phase 15 — Enterprise Operations Platform.

Provides runtime operational controls: maintenance mode, feature flags,
configuration hot-reload, cluster diagnostics, capacity planning,
and upgrade compatibility checking.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "MaintenanceMode",
    "FeatureFlags",
    "ConfigurationReloader",
    "ClusterDiagnostics",
    "CapacityPlanner",
    "UpgradeCompatibilityChecker",
    "EnterpriseOpsManager",
]

_PROCESS_START_TIME = time.monotonic()


# ─── Maintenance Mode ──────────────────────────────────────────────────────


class MaintenanceMode:
    """Controls system-wide maintenance mode."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._enabled = False
        self._reason = ""
        self._started_at: Optional[str] = None
        self._scheduled_end: Optional[str] = None

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def enable(self, reason: str, scheduled_end: Optional[str] = None) -> None:
        with self._lock:
            self._enabled = True
            self._reason = reason
            self._started_at = datetime.now(timezone.utc).isoformat()
            self._scheduled_end = scheduled_end
        logger.warning("maintenance.enabled reason=%s", reason)

    def disable(self) -> None:
        with self._lock:
            self._enabled = False
            self._reason = ""
            self._started_at = None
            self._scheduled_end = None
        logger.info("maintenance.disabled")

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._enabled,
                "reason": self._reason,
                "started_at": self._started_at,
                "scheduled_end": self._scheduled_end,
            }


# ─── Feature Flags ──────────────────────────────────────────────────────────


class FeatureFlags:
    """Runtime feature flag registry."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._flags: Dict[str, Dict[str, Any]] = {}

    def register(
        self, flag_name: str, default: bool = False, description: str = ""
    ) -> None:
        with self._lock:
            if flag_name not in self._flags:
                self._flags[flag_name] = {
                    "enabled": default,
                    "description": description,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }

    def is_enabled(self, flag_name: str) -> bool:
        with self._lock:
            flag = self._flags.get(flag_name)
            return flag["enabled"] if flag else False

    def enable(self, flag_name: str) -> None:
        with self._lock:
            if flag_name in self._flags:
                self._flags[flag_name]["enabled"] = True
                self._flags[flag_name]["updated_at"] = datetime.now(timezone.utc).isoformat()
                logger.info("feature_flag.enabled flag=%s", flag_name)

    def disable(self, flag_name: str) -> None:
        with self._lock:
            if flag_name in self._flags:
                self._flags[flag_name]["enabled"] = False
                self._flags[flag_name]["updated_at"] = datetime.now(timezone.utc).isoformat()
                logger.info("feature_flag.disabled flag=%s", flag_name)

    def list_flags(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {"name": name, **info} for name, info in self._flags.items()
            ]

    def bulk_update(self, updates: Dict[str, bool]) -> None:
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            for name, value in updates.items():
                if name in self._flags:
                    self._flags[name]["enabled"] = value
                    self._flags[name]["updated_at"] = now
        logger.info("feature_flag.bulk_update count=%d", len(updates))


# ─── Configuration Reloader ─────────────────────────────────────────────────


class ConfigurationReloader:
    """Manages dynamic configuration hot-reload for registered sources."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sources: Dict[str, Callable] = {}
        self._history: List[Dict[str, Any]] = []

    def register_source(self, name: str, reload_fn: Callable) -> None:
        with self._lock:
            self._sources[name] = reload_fn
        logger.info("config_reloader.source_registered name=%s", name)

    def reload(self, source_name: Optional[str] = None) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        with self._lock:
            targets = (
                {source_name: self._sources[source_name]}
                if source_name and source_name in self._sources
                else dict(self._sources)
            )

        for name, fn in targets.items():
            try:
                fn()
                results[name] = {"status": "ok"}
                logger.info("config_reloader.reloaded source=%s", name)
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
                logger.error("config_reloader.failed source=%s error=%s", name, e)

        event = {
            "reload_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": list(results.keys()),
            "results": results,
        }
        with self._lock:
            self._history.append(event)
            if len(self._history) > 200:
                self._history = self._history[-100:]
        return event

    def get_reload_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history[-limit:])


# ─── Cluster Diagnostics ───────────────────────────────────────────────────


class ClusterDiagnostics:
    """System and cluster diagnostics for enterprise operations."""

    def run_diagnostics(self) -> Dict[str, Any]:
        diag: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "uptime_seconds": round(time.monotonic() - _PROCESS_START_TIME, 2),
        }
        # CPU and memory via psutil (optional)
        try:
            import psutil
            diag["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            diag["memory_total_gb"] = round(mem.total / (1024**3), 2)
            diag["memory_used_gb"] = round(mem.used / (1024**3), 2)
            diag["memory_percent"] = mem.percent
            disk = psutil.disk_usage("/")
            diag["disk_total_gb"] = round(disk.total / (1024**3), 2)
            diag["disk_used_percent"] = disk.percent
        except ImportError:
            diag["psutil_available"] = False
        return diag

    def check_dependencies(self) -> Dict[str, Any]:
        deps: Dict[str, bool] = {}
        optional_packages = [
            "psutil", "redis", "kafka", "aiohttp", "uvicorn",
            "fastapi", "pydantic", "structlog", "torch",
        ]
        for pkg in optional_packages:
            try:
                __import__(pkg)
                deps[pkg] = True
            except ImportError:
                deps[pkg] = False
        return {
            "dependencies": deps,
            "available_count": sum(1 for v in deps.values() if v),
            "total_checked": len(deps),
        }

    def get_system_info(self) -> Dict[str, Any]:
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "architecture": platform.architecture(),
            "machine": platform.machine(),
            "node": platform.node(),
        }


# ─── Capacity Planner ──────────────────────────────────────────────────────


class CapacityPlanner:
    """Tracks load metrics and provides simple linear-trend capacity forecasting."""

    def __init__(self, max_history: int = 1000) -> None:
        self._lock = Lock()
        self._history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._max_history = max_history

    def record_load(self, metric_name: str, value: float) -> None:
        with self._lock:
            self._history[metric_name].append({
                "value": value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ts": time.monotonic(),
            })
            if len(self._history[metric_name]) > self._max_history:
                self._history[metric_name] = self._history[metric_name][-500:]

    def forecast(self, metric_name: str, periods: int = 10) -> Dict[str, Any]:
        with self._lock:
            points = list(self._history.get(metric_name, []))
        if len(points) < 2:
            return {
                "metric": metric_name,
                "forecast": [],
                "trend": "insufficient_data",
            }
        # Simple linear regression
        values = [p["value"] for p in points]
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean

        forecast_values = [
            round(slope * (n + i) + intercept, 4) for i in range(periods)
        ]
        trend = "increasing" if slope > 0.01 else ("decreasing" if slope < -0.01 else "stable")
        return {
            "metric": metric_name,
            "data_points": n,
            "slope": round(slope, 6),
            "trend": trend,
            "forecast": forecast_values,
        }

    def get_recommendations(self) -> List[str]:
        recommendations: List[str] = []
        with self._lock:
            metrics = dict(self._history)
        for name, points in metrics.items():
            if not points:
                continue
            latest = points[-1]["value"]
            if "cpu" in name.lower() and latest > 80:
                recommendations.append(
                    f"CPU utilization ({latest:.1f}%) is high — consider scaling horizontally."
                )
            if "memory" in name.lower() and latest > 85:
                recommendations.append(
                    f"Memory utilization ({latest:.1f}%) is elevated — investigate memory leaks or increase RAM."
                )
            if "queue" in name.lower() and latest > 1000:
                recommendations.append(
                    f"Queue depth for '{name}' ({latest:.0f}) is high — add more consumers."
                )
        if not recommendations:
            recommendations.append("All monitored metrics are within normal thresholds.")
        return recommendations

    def get_utilization_report(self) -> Dict[str, Any]:
        with self._lock:
            report: Dict[str, Any] = {}
            for name, points in self._history.items():
                if points:
                    values = [p["value"] for p in points]
                    report[name] = {
                        "latest": values[-1],
                        "min": min(values),
                        "max": max(values),
                        "avg": round(sum(values) / len(values), 4),
                        "samples": len(values),
                    }
            return report


# ─── Upgrade Compatibility Checker ─────────────────────────────────────────


class UpgradeCompatibilityChecker:
    """Validates cross-phase compatibility and provides upgrade path guidance."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._phases: Dict[int, Dict[str, Any]] = {}

    def register_phase(
        self, phase: int, version: str, required_components: List[str]
    ) -> None:
        with self._lock:
            self._phases[phase] = {
                "phase": phase,
                "version": version,
                "required_components": required_components,
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }

    def check_compatibility(self) -> Dict[str, Any]:
        with self._lock:
            phases = dict(self._phases)
        issues: List[str] = []
        if not phases:
            return {"compatible": True, "phases_registered": 0, "issues": []}
        # Verify sequential phase ordering
        registered = sorted(phases.keys())
        for i in range(1, len(registered)):
            if registered[i] != registered[i - 1] + 1:
                issues.append(
                    f"Gap between phase {registered[i-1]} and {registered[i]}"
                )
        return {
            "compatible": len(issues) == 0,
            "phases_registered": len(phases),
            "phase_range": f"{min(registered)}-{max(registered)}" if registered else "none",
            "issues": issues,
        }

    def get_upgrade_path(self) -> List[Dict[str, Any]]:
        with self._lock:
            phases = dict(self._phases)
        return [
            phases[p] for p in sorted(phases.keys())
        ]


# ─── Enterprise Ops Manager (Facade) ───────────────────────────────────────


class EnterpriseOpsManager:
    """Unified enterprise operations management facade."""

    def __init__(self) -> None:
        self._maintenance = MaintenanceMode()
        self._features = FeatureFlags()
        self._config_reloader = ConfigurationReloader()
        self._diagnostics = ClusterDiagnostics()
        self._capacity_planner = CapacityPlanner()
        self._upgrade_checker = UpgradeCompatibilityChecker()

        # Register default feature flags
        self._features.register("distributed_mode", False, "Enable distributed multi-node operation")
        self._features.register("advanced_security", True, "Enable enterprise security governance")
        self._features.register("circuit_breakers", True, "Enable circuit breaker protection")
        self._features.register("observability_export", False, "Enable external observability export")

        # Register known phases
        for phase in range(1, 16):
            self._upgrade_checker.register_phase(
                phase, f"1.{phase}.0", [f"phase{phase}_core"]
            )

        logger.info("EnterpriseOpsManager initialized")

    @property
    def maintenance(self) -> MaintenanceMode:
        return self._maintenance

    @property
    def features(self) -> FeatureFlags:
        return self._features

    @property
    def config_reloader(self) -> ConfigurationReloader:
        return self._config_reloader

    @property
    def diagnostics(self) -> ClusterDiagnostics:
        return self._diagnostics

    @property
    def capacity_planner(self) -> CapacityPlanner:
        return self._capacity_planner

    @property
    def upgrade_checker(self) -> UpgradeCompatibilityChecker:
        return self._upgrade_checker

    def get_full_status(self) -> Dict[str, Any]:
        return {
            "maintenance": self._maintenance.get_status(),
            "feature_flags": self._features.list_flags(),
            "diagnostics": self._diagnostics.get_system_info(),
            "capacity": self._capacity_planner.get_utilization_report(),
            "upgrade_compatibility": self._upgrade_checker.check_compatibility(),
        }
