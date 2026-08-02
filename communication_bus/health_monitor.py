import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore
    _PSUTIL_AVAILABLE = False

try:
    from structlog import get_logger
    logger = get_logger()
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore

try:
    from .config import settings
except ImportError:
    class _S:  # type: ignore
        HEALTH_CHECK_INTERVAL = 60
        CPU_USAGE_THRESHOLD = 80.0
        MEMORY_USAGE_THRESHOLD = 80.0
        DISK_USAGE_THRESHOLD = 80.0
    settings = _S()

_MAX_ALERTS = 500  # bounded alert list — prevents unbounded memory growth


class HealthMonitor:
    """Monitors system health for the communication bus."""

    def __init__(self) -> None:
        self.metrics: Dict[str, Dict] = {}
        self.health_status: Dict = {}
        self.alerts: List[Dict] = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._initialized = False
        self.is_running = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        logger.info("health_monitor.initializing")
        self.is_running = True
        # Store task reference — prevents GC on Python 3.11+
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(), name="health_monitor.loop"
        )
        self._initialized = True
        logger.info("health_monitor.initialized")

    async def shutdown(self) -> None:
        logger.info("health_monitor.shutting_down")
        self.is_running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self._initialized = False
        logger.info("health_monitor.stopped")

    async def monitor_health(self) -> None:
        """Public alias — called externally as a background task from main.py."""
        await self._monitor_loop()

    async def _monitor_loop(self) -> None:
        """Internal loop guarded by is_running — exits cleanly on shutdown."""
        while self.is_running:
            try:
                await self._collect_system_metrics()
                if self.metrics:  # only check health once metrics are populated
                    await self._check_system_health()
                    await self._process_alerts()
                await asyncio.sleep(settings.HEALTH_CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("health_monitor.loop_error", error=str(exc))
                await asyncio.sleep(1)

    async def _collect_system_metrics(self) -> None:
        if not _PSUTIL_AVAILABLE:
            return
        try:
            # Run blocking psutil calls in executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            cpu_pct = await loop.run_in_executor(None, lambda: psutil.cpu_percent(interval=None))
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            net = psutil.net_io_counters()
            now = datetime.utcnow().isoformat()
            self.metrics = {
                "cpu": {"percent": cpu_pct, "count": psutil.cpu_count(), "timestamp": now},
                "memory": {"percent": mem.percent, "used": mem.used, "total": mem.total, "timestamp": now},
                "disk": {"percent": disk.percent, "used": disk.used, "total": disk.total, "timestamp": now},
                "network": {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "timestamp": now},
            }
        except Exception as exc:
            logger.error("health_monitor.collect_error", error=str(exc))

    async def _check_system_health(self) -> None:
        try:
            cpu = self.metrics.get("cpu", {})
            mem = self.metrics.get("memory", {})
            disk = self.metrics.get("disk", {})
            if cpu.get("percent", 0) > settings.CPU_USAGE_THRESHOLD:
                await self._create_alert("high_cpu_usage", f"CPU {cpu['percent']}%", "warning")
            if mem.get("percent", 0) > settings.MEMORY_USAGE_THRESHOLD:
                await self._create_alert("high_memory_usage", f"Memory {mem['percent']}%", "warning")
            if disk.get("percent", 0) > settings.DISK_USAGE_THRESHOLD:
                await self._create_alert("high_disk_usage", f"Disk {disk['percent']}%", "warning")
            active = [a for a in self.alerts if a["status"] == "active"]
            self.health_status = {
                "status": "healthy" if not active else "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": self.metrics,
            }
        except Exception as exc:
            logger.error("health_monitor.check_error", error=str(exc))

    async def _create_alert(self, alert_type: str, message: str, severity: str) -> None:
        # Bounded — evict oldest when at capacity
        if len(self.alerts) >= _MAX_ALERTS:
            self.alerts.pop(0)
        self.alerts.append({
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "active",
        })
        logger.warning("health_monitor.alert", alert_type=alert_type, message=message)

    async def _process_alerts(self) -> None:
        for alert in self.alerts:
            if alert["status"] == "active":
                logger.warning("health_monitor.active_alert", type=alert["type"], severity=alert["severity"])

    async def get_status(self) -> Dict:
        return {
            "initialized": self._initialized,
            "health_status": self.health_status,
            "active_alerts": len([a for a in self.alerts if a["status"] == "active"]),
            "metrics": self.metrics,
        }

    async def get_alerts(self, status: Optional[str] = None) -> List[Dict]:
        if status:
            return [a for a in self.alerts if a["status"] == status]
        return list(self.alerts)

    async def clear_alerts(self) -> None:
        self.alerts = []
        logger.info("health_monitor.alerts_cleared")
