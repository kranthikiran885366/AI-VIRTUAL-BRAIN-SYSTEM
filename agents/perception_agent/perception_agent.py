import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .fusion_module import FusionModule
from .anomaly_detector import AnomalyDetector
from .threat_analyzer import ThreatAnalyzer
import numpy as np

@dataclass
class PerceptionConfig:
    """Configuration for the perception agent."""
    fusion_config: Dict[str, Any]
    anomaly_config: Dict[str, Any]
    threat_config: Dict[str, Any]
    temporal_window: int
    confidence_threshold: float

class PerceptionAgent:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the perception agent."""
        self.logger = logging.getLogger(__name__)
        self.config = PerceptionConfig(**config)
        
        # Initialize modules
        self._init_modules()
        
        # Performance metrics
        self.processing_times = []
    
    def _init_modules(self):
        """Initialize perception modules."""
        # Initialize fusion module
        self.fusion_module = FusionModule(self.config.fusion_config)
        
        # Initialize anomaly detector
        self.anomaly_detector = AnomalyDetector(self.config.anomaly_config)
        
        # Initialize threat analyzer
        self.threat_analyzer = ThreatAnalyzer(self.config.threat_config)
    
    def process(self, visual_data: Dict[str, Any], audio_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process visual and audio data."""
        start_time = time.time()
        
        try:
            # Fuse multi-modal data
            fused_data = self.fusion_module.fuse(visual_data, audio_data)
            
            # Create context for analysis
            context = {
                "perception": fused_data,
                "timestamp": time.time()
            }
            
            # Detect anomalies
            anomalies = self.anomaly_detector.detect(context)
            
            # Analyze threats
            threats = self.threat_analyzer.analyze(context)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            return {
                "fused_data": fused_data,
                "anomalies": anomalies,
                "threats": threats,
                "processing_time": processing_time,
                "timestamp": time.time()
            }
        
        except Exception as e:
            self.logger.error(f"Error in perception processing: {str(e)}")
            return {
                "error": str(e),
                "timestamp": time.time()
            }
    
    def get_performance_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics for all modules."""
        return {
            "fusion": self.fusion_module.get_performance_metrics(),
            "anomaly": self.anomaly_detector.get_performance_metrics(),
            "threat": self.threat_analyzer.get_performance_metrics(),
            "overall": {
                "mean": sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0,
                "std": np.std(self.processing_times) if self.processing_times else 0,
                "min": min(self.processing_times) if self.processing_times else 0,
                "max": max(self.processing_times) if self.processing_times else 0
            }
        }
    
    def reset(self):
        """Reset all modules."""
        self.fusion_module.reset()
        self.anomaly_detector.reset()
        self.threat_analyzer.reset()
        self.processing_times = []
        self.logger.info("Perception agent reset") 