import asyncio
import logging
import psutil
from typing import Dict, List, Optional
from datetime import datetime

from structlog import get_logger

from .config import settings

logger = get_logger()

class HealthMonitor:
    """Monitors the health of the communication bus and its components."""
    
    def __init__(self):
        """Initialize the health monitor."""
        self.metrics: Dict[str, Dict] = {}
        self.health_status: Dict[str, str] = {}
        self.alerts: List[Dict] = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the health monitor."""
        if self._initialized:
            return
        
        logger.info("Initializing health monitor...")
        
        try:
            # Start monitoring task
            self._monitor_task = asyncio.create_task(self.monitor_health())
            
            self._initialized = True
            logger.info("Health monitor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize health monitor: {str(e)}")
            raise
    
    async def shutdown(self):
        """Shutdown the health monitor."""
        logger.info("Shutting down health monitor...")
        
        # Cancel monitoring task
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        self._initialized = False
        logger.info("Health monitor shut down")
    
    async def monitor_health(self):
        """Continuously monitor system health."""
        while True:
            try:
                # Collect system metrics
                await self._collect_system_metrics()
                
                # Check system health
                await self._check_system_health()
                
                # Process alerts
                await self._process_alerts()
                
                await asyncio.sleep(settings.HEALTH_CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring: {str(e)}")
                await asyncio.sleep(1)
    
    async def _collect_system_metrics(self):
        """Collect system metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used = memory.used
            memory_total = memory.total
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_used = disk.used
            disk_total = disk.total
            
            # Network metrics
            net_io = psutil.net_io_counters()
            bytes_sent = net_io.bytes_sent
            bytes_recv = net_io.bytes_recv
            
            # Update metrics
            self.metrics = {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "memory": {
                    "percent": memory_percent,
                    "used": memory_used,
                    "total": memory_total,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "disk": {
                    "percent": disk_percent,
                    "used": disk_used,
                    "total": disk_total,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "network": {
                    "bytes_sent": bytes_sent,
                    "bytes_recv": bytes_recv,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            logger.debug("System metrics collected")
        except Exception as e:
            logger.error(f"Error collecting system metrics: {str(e)}")
    
    async def _check_system_health(self):
        """Check system health based on collected metrics."""
        try:
            # Check CPU usage
            if self.metrics["cpu"]["percent"] > settings.CPU_USAGE_THRESHOLD:
                await self._create_alert(
                    "high_cpu_usage",
                    f"CPU usage is {self.metrics['cpu']['percent']}%",
                    "warning"
                )
            
            # Check memory usage
            if self.metrics["memory"]["percent"] > settings.MEMORY_USAGE_THRESHOLD:
                await self._create_alert(
                    "high_memory_usage",
                    f"Memory usage is {self.metrics['memory']['percent']}%",
                    "warning"
                )
            
            # Check disk usage
            if self.metrics["disk"]["percent"] > settings.DISK_USAGE_THRESHOLD:
                await self._create_alert(
                    "high_disk_usage",
                    f"Disk usage is {self.metrics['disk']['percent']}%",
                    "warning"
                )
            
            # Update health status
            self.health_status = {
                "status": "healthy" if not self.alerts else "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": self.metrics
            }
            
            logger.debug("System health checked")
        except Exception as e:
            logger.error(f"Error checking system health: {str(e)}")
    
    async def _create_alert(self, alert_type: str, message: str, severity: str):
        """Create a new alert."""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        self.alerts.append(alert)
        logger.warning(f"Alert created: {message}")
    
    async def _process_alerts(self):
        """Process active alerts."""
        try:
            for alert in self.alerts:
                if alert["status"] == "active":
                    # Here you would typically implement alert processing logic
                    # For example, sending notifications, taking corrective actions, etc.
                    
                    # For now, we'll just log the alert
                    logger.warning(
                        f"Processing alert: {alert['type']} - {alert['message']}",
                        severity=alert["severity"]
                    )
            
            logger.debug("Alerts processed")
        except Exception as e:
            logger.error(f"Error processing alerts: {str(e)}")
    
    async def get_status(self) -> Dict:
        """Get health monitor status."""
        return {
            "initialized": self._initialized,
            "health_status": self.health_status,
            "active_alerts": len([a for a in self.alerts if a["status"] == "active"]),
            "metrics": self.metrics
        }
    
    async def get_alerts(self, status: Optional[str] = None) -> List[Dict]:
        """Get alerts, optionally filtered by status."""
        if status:
            return [a for a in self.alerts if a["status"] == status]
        return self.alerts
    
    async def clear_alerts(self):
        """Clear all alerts."""
        self.alerts = []
        logger.info("Alerts cleared") 