import numpy as np
import torch
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from transformers import AutoTokenizer, AutoModelForSequenceClassification

@dataclass
class ThreatConfig:
    """Configuration for threat analysis."""
    model_path: str
    device: str
    confidence_threshold: float
    temporal_window: int
    threat_categories: List[str]

class ThreatAnalyzer:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the threat analyzer."""
        self.logger = logging.getLogger(__name__)
        self.config = ThreatConfig(**config)
        
        # Initialize models
        self._init_models()
        
        # Temporal buffer
        self.temporal_buffer = []
        self.max_buffer_size = self.config.temporal_window
        
        # Performance metrics
        self.processing_times = []
    
    def _init_models(self):
        """Initialize threat analysis models."""
        # Initialize text classification model
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.config.model_path,
            num_labels=len(self.config.threat_categories)
        )
        
        # Move model to specified device
        if self.config.device == "cuda" and torch.cuda.is_available():
            self.model = self.model.to("cuda")
    
    def analyze(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze context for potential threats."""
        start_time = time.time()
        
        try:
            # Update temporal buffer
            self._update_buffer(context)
            
            # Extract features
            features = self._extract_features(context)
            
            # Analyze threats
            threats = self._analyze_threats(features)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            return threats
        
        except Exception as e:
            self.logger.error(f"Error in threat analysis: {str(e)}")
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
    
    def _extract_features(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features for threat analysis."""
        features = {}
        
        try:
            # Extract visual features
            if "perception" in context and "visual_features" in context["perception"]:
                visual = context["perception"]["visual_features"]
                
                # Object features
                if "objects" in visual:
                    features["objects"] = [
                        {
                            "class": obj["class"],
                            "confidence": obj["confidence"],
                            "bbox": obj["bbox"]
                        }
                        for obj in visual["objects"]
                        if obj["confidence"] >= self.config.confidence_threshold
                    ]
                
                # Face features
                if "faces" in visual:
                    features["faces"] = [
                        {
                            "landmarks": face["landmarks"],
                            "confidence": face["confidence"],
                            "bbox": face["bbox"]
                        }
                        for face in visual["faces"]
                        if face["confidence"] >= self.config.confidence_threshold
                    ]
            
            # Extract audio features
            if "perception" in context and "audio_features" in context["perception"]:
                audio = context["perception"]["audio_features"]
                
                # Speech features
                if "speech" in audio:
                    features["speech"] = {
                        "text": audio["speech"]["text"],
                        "confidence": audio["speech"]["confidence"]
                    }
                
                # Audio characteristics
                if "characteristics" in audio:
                    features["audio"] = audio["characteristics"]
            
            # Extract emotion features
            if "emotions" in context:
                features["emotions"] = context["emotions"]
        
        except Exception as e:
            self.logger.error(f"Error in feature extraction: {str(e)}")
        
        return features
    
    def _analyze_threats(self, features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze features for potential threats."""
        threats = []
        
        try:
            # Analyze text threats
            if "speech" in features:
                text = features["speech"]["text"]
                if text:
                    # Tokenize text
                    inputs = self.tokenizer(
                        text,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=512
                    )
                    
                    # Move inputs to device
                    if self.config.device == "cuda" and torch.cuda.is_available():
                        inputs = {k: v.to("cuda") for k, v in inputs.items()}
                    
                    # Get predictions
                    with torch.no_grad():
                        outputs = self.model(**inputs)
                        probs = torch.softmax(outputs.logits, dim=1)
                    
                    # Check for threats
                    for i, prob in enumerate(probs[0]):
                        if prob >= self.config.confidence_threshold:
                            threats.append({
                                "type": "text",
                                "category": self.config.threat_categories[i],
                                "confidence": float(prob),
                                "text": text,
                                "timestamp": time.time()
                            })
            
            # Analyze visual threats
            if "objects" in features:
                for obj in features["objects"]:
                    if obj["class"] in self.config.threat_categories:
                        threats.append({
                            "type": "visual",
                            "category": obj["class"],
                            "confidence": obj["confidence"],
                            "bbox": obj["bbox"],
                            "timestamp": time.time()
                        })
            
            # Analyze audio threats
            if "audio" in features:
                audio = features["audio"]
                if audio["rms"] > 0.8:  # High volume
                    threats.append({
                        "type": "audio",
                        "category": "loud_noise",
                        "confidence": float(audio["rms"]),
                        "characteristics": audio,
                        "timestamp": time.time()
                    })
            
            # Analyze emotional threats
            if "emotions" in features:
                emotions = features["emotions"]
                if emotions.get("arousal", 0) > 0.8:  # High arousal
                    threats.append({
                        "type": "emotional",
                        "category": "high_arousal",
                        "confidence": float(emotions["arousal"]),
                        "emotions": emotions,
                        "timestamp": time.time()
                    })
        
        except Exception as e:
            self.logger.error(f"Error in threat analysis: {str(e)}")
        
        return threats
    
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
        """Reset the threat analyzer."""
        self.temporal_buffer = []
        self.processing_times = []
        self.logger.info("Threat analyzer reset") 