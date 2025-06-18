import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import psutil
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

class ModelMonitor:
    """Monitors model performance and system health."""
    
    def __init__(self, metrics_dir: str):
        """Initialize the model monitor.
        
        Args:
            metrics_dir: Directory to store metrics
        """
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics = {
            "inference": {},
            "system": {},
            "model": {}
        }
        
        self.window_size = timedelta(hours=1)
        self.monitoring_task = None
    
    async def start_monitoring(self, interval: int = 60):
        """Start the monitoring process.
        
        Args:
            interval: Monitoring interval in seconds
        """
        if self.monitoring_task is not None:
            logger.warning("Monitoring already running")
            return
        
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval)
        )
        logger.info(f"Started monitoring with {interval}s interval")
    
    async def stop_monitoring(self):
        """Stop the monitoring process."""
        if self.monitoring_task is None:
            logger.warning("Monitoring not running")
            return
        
        self.monitoring_task.cancel()
        try:
            await self.monitoring_task
        except asyncio.CancelledError:
            pass
        
        self.monitoring_task = None
        logger.info("Stopped monitoring")
    
    async def _monitoring_loop(self, interval: int):
        """Main monitoring loop.
        
        Args:
            interval: Monitoring interval in seconds
        """
        while True:
            try:
                # Collect metrics
                await self._collect_system_metrics()
                await self._collect_model_metrics()
                
                # Save metrics
                await self._save_metrics()
                
                # Clean old metrics
                self._clean_old_metrics()
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_system_metrics(self):
        """Collect system-level metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_used = memory.used / memory.total
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_used = disk.used / disk.total
            
            # Network metrics
            net_io = psutil.net_io_counters()
            
            timestamp = datetime.now().isoformat()
            self.metrics["system"][timestamp] = {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count
                },
                "memory": {
                    "used_percent": memory_used * 100,
                    "total": memory.total,
                    "used": memory.used
                },
                "disk": {
                    "used_percent": disk_used * 100,
                    "total": disk.total,
                    "used": disk.used
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    async def _collect_model_metrics(self):
        """Collect model-specific metrics."""
        # This would be implemented based on specific model monitoring needs
        pass
    
    def record_inference_metrics(
        self,
        model_type: str,
        metrics: Dict[str, Any]
    ):
        """Record inference metrics for a model.
        
        Args:
            model_type: Type of model
            metrics: Inference metrics to record
        """
        timestamp = datetime.now().isoformat()
        
        if model_type not in self.metrics["inference"]:
            self.metrics["inference"][model_type] = {}
        
        self.metrics["inference"][model_type][timestamp] = metrics
    
    async def _save_metrics(self):
        """Save collected metrics to disk."""
        try:
            # Save each metric type separately
            for metric_type, data in self.metrics.items():
                file_path = self.metrics_dir / f"{metric_type}_metrics.json"
                
                # Load existing data
                if file_path.exists():
                    with open(file_path, "r") as f:
                        existing_data = json.load(f)
                else:
                    existing_data = {}
                
                # Update with new data
                existing_data.update(data)
                
                # Save back to file
                with open(file_path, "w") as f:
                    json.dump(existing_data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    def _clean_old_metrics(self):
        """Remove metrics older than the window size."""
        cutoff_time = datetime.now() - self.window_size
        
        for metric_type in self.metrics:
            for key in list(self.metrics[metric_type].keys()):
                try:
                    metric_time = datetime.fromisoformat(key)
                    if metric_time < cutoff_time:
                        del self.metrics[metric_type][key]
                except (ValueError, TypeError):
                    continue
    
    def get_metrics(
        self,
        metric_type: str,
        model_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """Get metrics for analysis.
        
        Args:
            metric_type: Type of metrics to retrieve
            model_type: Optional specific model type
            start_time: Optional start time for filtering
            end_time: Optional end time for filtering
            
        Returns:
            Filtered metrics data
        """
        if metric_type not in self.metrics:
            raise ValueError(f"Unknown metric type: {metric_type}")
        
        metrics = self.metrics[metric_type]
        
        # Filter by model type
        if model_type and metric_type == "inference":
            metrics = metrics.get(model_type, {})
        
        # Filter by time range
        if start_time or end_time:
            filtered_metrics = {}
            for timestamp, data in metrics.items():
                try:
                    metric_time = datetime.fromisoformat(timestamp)
                    if start_time and metric_time < start_time:
                        continue
                    if end_time and metric_time > end_time:
                        continue
                    filtered_metrics[timestamp] = data
                except (ValueError, TypeError):
                    continue
            metrics = filtered_metrics
        
        return metrics
    
    def get_metric_summary(
        self,
        metric_type: str,
        model_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for metrics.
        
        Args:
            metric_type: Type of metrics to summarize
            model_type: Optional specific model type
            
        Returns:
            Summary statistics
        """
        metrics = self.get_metrics(metric_type, model_type)
        
        if not metrics:
            return {}
        
        summary = {}
        
        # Calculate statistics for each metric
        for timestamp, data in metrics.items():
            for metric_name, value in data.items():
                if isinstance(value, (int, float)):
                    if metric_name not in summary:
                        summary[metric_name] = []
                    summary[metric_name].append(value)
        
        # Calculate statistics
        for metric_name, values in summary.items():
            values = np.array(values)
            summary[metric_name] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "count": len(values)
            }
        
        return summary 