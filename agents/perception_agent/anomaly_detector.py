import numpy as np
import torch
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

@dataclass
class AnomalyConfig:
    """Configuration for anomaly detection."""
    contamination: float
    n_estimators: int
    max_samples: int
    confidence_threshold: float
    temporal_window: int
    feature_dim: int

class AnomalyDetector:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the anomaly detector."""
        self.logger = logging.getLogger(__name__)
        self.config = AnomalyConfig(**config)
        
        # Initialize models
        self._init_models()
        
        # Temporal buffer
        self.temporal_buffer = []
        self.max_buffer_size = self.config.temporal_window
        
        # Performance metrics
        self.processing_times = []
    
    def _init_models(self):
        """Initialize anomaly detection models."""
        # Initialize isolation forest
        self.isolation_forest = IsolationForest(
            contamination=self.config.contamination,
            n_estimators=self.config.n_estimators,
            max_samples=self.config.max_samples,
            random_state=42
        )
        
        # Initialize feature scaler
        self.scaler = StandardScaler()
        
        # Initialize model state
        self.is_fitted = False
    
    def detect(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect anomalies in the current context."""
        start_time = time.time()
        
        try:
            # Update temporal buffer
            self._update_buffer(context)
            
            # Extract features
            features = self._extract_features(context)
            
            # Detect anomalies
            anomalies = self._detect_anomalies(features)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            return anomalies
        
        except Exception as e:
            self.logger.error(f"Error in anomaly detection: {str(e)}")
            return []
    
    def _update_buffer(self, context: Dict[str, Any]):
        """Update temporal buffer with new context."""
        # Add new context to buffer
        self.temporal_buffer.append({
            "context": context,
            "timestamp": time.time()
        })
        
        # Remove old context if buffer is full
        if len(self.temporal_buffer) > self.max_buffer_size:
            self.temporal_buffer.pop(0)
    
    def _extract_features(self, context: Dict[str, Any]) -> np.ndarray:
        """Extract features for anomaly detection."""
        features = []
        
        try:
            # Extract visual features
            if "perception" in context and "visual_features" in context["perception"]:
                visual = context["perception"]["visual_features"]
                
                # Object features
                if "objects" in visual:
                    for obj in visual["objects"]:
                        features.extend([
                            obj["confidence"],
                            *obj["bbox"]
                        ])
                
                # Face features
                if "faces" in visual:
                    for face in visual["faces"]:
                        features.extend([
                            face["confidence"],
                            *face["bbox"]
                        ])
                
                # Scene features
                if "scene" in visual:
                    scene = visual["scene"]
                    features.extend([
                        scene["brightness"],
                        scene["contrast"],
                        scene["edge_density"]
                    ])
            
            # Extract audio features
            if "perception" in context and "audio_features" in context["perception"]:
                audio = context["perception"]["audio_features"]
                
                # Speech features
                if "speech" in audio:
                    speech = audio["speech"]
                    features.extend([
                        speech["confidence"]
                    ])
                
                # Audio characteristics
                if "characteristics" in audio:
                    chars = audio["characteristics"]
                    features.extend([
                        chars["rms"],
                        chars["zcr"],
                        chars["centroid"],
                        chars["bandwidth"]
                    ])
            
            # Extract emotion features
            if "emotions" in context:
                emotions = context["emotions"]
                features.extend([
                    emotions.get("valence", 0.0),
                    emotions.get("arousal", 0.0),
                    emotions.get("dominance", 0.0)
                ])
        
        except Exception as e:
            self.logger.error(f"Error in feature extraction: {str(e)}")
        
        # Pad or truncate to fixed size
        if len(features) < self.config.feature_dim:
            features.extend([0] * (self.config.feature_dim - len(features)))
        else:
            features = features[:self.config.feature_dim]
        
        return np.array(features)
    
    def _detect_anomalies(self, features: np.ndarray) -> List[Dict[str, Any]]:
        """Detect anomalies using isolation forest."""
        anomalies = []
        
        try:
            # Reshape features for sklearn
            features = features.reshape(1, -1)
            
            # Scale features
            if not self.is_fitted:
                self.scaler.fit(features)
                self.isolation_forest.fit(self.scaler.transform(features))
                self.is_fitted = True
            
            # Transform features
            features_scaled = self.scaler.transform(features)
            
            # Get anomaly scores
            scores = self.isolation_forest.score_samples(features_scaled)
            
            # Convert scores to probabilities
            probs = 1 - np.exp(scores)
            
            # Detect anomalies
            if probs[0] >= self.config.confidence_threshold:
                anomalies.append({
                    "type": "anomaly",
                    "confidence": float(probs[0]),
                    "features": features.tolist(),
                    "timestamp": time.time()
                })
        
        except Exception as e:
            self.logger.error(f"Error in anomaly detection: {str(e)}")
        
        return anomalies
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        if not self.processing_times:
            return {}
        
        return {
            "mean": np.mean(self.processing_times),
            "std": np.std(self.processing_times),
            "min": np.min(self.processing_times),
            "max": np.max(self.processing_times)
        }
    
    def reset(self):
        """Reset the anomaly detector."""
        self.temporal_buffer = []
        self.processing_times = []
        self.is_fitted = False
        self.logger.info("Anomaly detector reset") 