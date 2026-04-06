import asyncio
import logging
import psutil
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
from dataclasses import dataclass, asdict
from enum import Enum

from structlog import get_logger

from .config import settings

logger = get_logger()

@dataclass
class HealthMetrics:
    """Health metrics data class."""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    process_count: int
    uptime: float
    timestamp: datetime

class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class HealthMonitor:
    """Monitors system health and performance."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the health monitor with configuration."""
        self.config = config
        self.is_running = False
        
        # Initialize metrics storage
        self.metrics_history: List[HealthMetrics] = []
        self.max_history_size = config.get("max_history_size", 1000)
        
        # Initialize thresholds
        self.thresholds = {
            "cpu_usage": config.get("cpu_threshold", 80.0),
            "memory_usage": config.get("memory_threshold", 80.0),
            "disk_usage": config.get("disk_threshold", 90.0),
            "process_count": config.get("process_threshold", 1000)
        }
        
        # Initialize component status
        self.component_status: Dict[str, HealthStatus] = {}
        
        # Initialize alerts
        self.alerts: List[Dict[str, Any]] = []
        self.max_alerts = config.get("max_alerts", 100)
    
    async def start(self):
        """Start the health monitor."""
        logger.info("Starting health monitor...")
        self.is_running = True
        
        # Start monitoring loop
        asyncio.create_task(self._monitor_loop())
        
        logger.info("Health monitor started successfully")
    
    async def stop(self):
        """Stop the health monitor."""
        logger.info("Stopping health monitor...")
        self.is_running = False
        
        # Save metrics history
        await self._save_metrics_history()
        
        logger.info("Health monitor stopped successfully")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.is_running:
            try:
                # Collect metrics
                metrics = await self._collect_metrics()
                
                # Update metrics history
                self.metrics_history.append(metrics)
                if len(self.metrics_history) > self.max_history_size:
                    self.metrics_history.pop(0)
                
                # Check health status
                await self._check_health_status(metrics)
                
                # Wait for next collection
                await asyncio.sleep(self.config.get("collection_interval", 60))
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _collect_metrics(self) -> HealthMetrics:
        """Collect system metrics."""
        try:
            # CPU metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent
            
            # Network metrics
            net_io = psutil.net_io_counters()
            network_io = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            }
            
            # Process metrics
            process_count = len(psutil.pids())
            
            # System uptime
            uptime = time.time() - psutil.boot_time()
            
            return HealthMetrics(
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                network_io=network_io,
                process_count=process_count,
                uptime=uptime,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            raise
    
    async def _check_health_status(self, metrics: HealthMetrics):
        """Check system health status."""
        # Check CPU usage
        if metrics.cpu_usage > self.thresholds["cpu_usage"]:
            await self._create_alert("CPU usage", metrics.cpu_usage)
        
        # Check memory usage
        if metrics.memory_usage > self.thresholds["memory_usage"]:
            await self._create_alert("Memory usage", metrics.memory_usage)
        
        # Check disk usage
        if metrics.disk_usage > self.thresholds["disk_usage"]:
            await self._create_alert("Disk usage", metrics.disk_usage)
        
        # Check process count
        if metrics.process_count > self.thresholds["process_count"]:
            await self._create_alert("Process count", metrics.process_count)
    
    async def _create_alert(self, metric_name: str, value: float):
        """Create a health alert."""
        alert = {
            "metric": metric_name,
            "value": value,
            "threshold": self.thresholds[metric_name.lower().replace(" ", "_")],
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "critical" if value > self.thresholds[metric_name.lower().replace(" ", "_")] * 1.2 else "warning"
        }
        
        self.alerts.append(alert)
        
        # Trim alerts if needed
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]
        
        logger.warning(f"Health alert: {metric_name} = {value} (threshold: {alert['threshold']})")
    
    async def _save_metrics_history(self):
        """Save metrics history to file."""
        try:
            with open("logs/metrics_history.json", "w") as f:
                json.dump([asdict(m) for m in self.metrics_history], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metrics history: {e}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        if not self.metrics_history:
            return {
                "status": HealthStatus.UNKNOWN,
                "last_update": None,
                "metrics": None,
                "alerts": self.alerts
            }
        
        latest_metrics = self.metrics_history[-1]
        
        # Determine overall status
        status = HealthStatus.HEALTHY
        if any([
            latest_metrics.cpu_usage > self.thresholds["cpu_usage"],
            latest_metrics.memory_usage > self.thresholds["memory_usage"],
            latest_metrics.disk_usage > self.thresholds["disk_usage"],
            latest_metrics.process_count > self.thresholds["process_count"]
        ]):
            status = HealthStatus.DEGRADED
        
        if any([
            latest_metrics.cpu_usage > self.thresholds["cpu_usage"] * 1.2,
            latest_metrics.memory_usage > self.thresholds["memory_usage"] * 1.2,
            latest_metrics.disk_usage > self.thresholds["disk_usage"] * 1.2,
            latest_metrics.process_count > self.thresholds["process_count"] * 1.2
        ]):
            status = HealthStatus.CRITICAL
        
        return {
            "status": status,
            "last_update": latest_metrics.timestamp.isoformat(),
            "metrics": asdict(latest_metrics),
            "alerts": self.alerts
        }
    
    async def get_metrics_history(self, duration: Optional[timedelta] = None) -> List[Dict[str, Any]]:
        """Get metrics history for a specific duration."""
        if not duration:
            return [asdict(m) for m in self.metrics_history]
        
        cutoff_time = datetime.utcnow() - duration
        return [asdict(m) for m in self.metrics_history if m.timestamp >= cutoff_time]
    
    async def clear_alerts(self):
        """Clear all alerts."""
        self.alerts.clear()
        logger.info("Alerts cleared")
    
    async def update_thresholds(self, new_thresholds: Dict[str, float]):
        """Update health thresholds."""
        for metric, value in new_thresholds.items():
            if metric in self.thresholds:
                self.thresholds[metric] = value
                logger.info(f"Updated {metric} threshold to {value}")
    
    async def get_component_status(self, component_id: str) -> Optional[HealthStatus]:
        """Get health status of a specific component."""
        return self.component_status.get(component_id)
    
    async def update_component_status(self, component_id: str, status: HealthStatus):
        """Update health status of a specific component."""
        self.component_status[component_id] = status
        logger.info(f"Updated component {component_id} status to {status}")
    
    async def initialize(self):
        """Initialize the health monitor."""
        logger.info("Initializing health monitor...")
        # Initialize component status
        self.component_status = {}
        self.alerts = []
        logger.info("Health monitor initialized")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get health monitor status (alias for get_health_status)."""
        return await self.get_health_status()
    
    async def monitor_health(self):
        """Monitor health (wrapper for _monitor_loop)."""
        await self._monitor_loop()
    
    async def shutdown(self):
        """Shutdown the health monitor."""
        await self.stop() 
