import numpy as np
import torch
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch.nn as nn
import torch.nn.functional as F

@dataclass
class ModelConfig:
    """Configuration for perception model."""
    device: str
    model_path: str
    confidence_threshold: float
    num_classes: int
    hidden_size: int
    num_layers: int
    dropout: float

class PerceptionModel(nn.Module):
    def __init__(self, config: Dict[str, Any]):
        """Initialize the perception model."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.config = ModelConfig(**config)
        
        # Initialize models
        self._init_models()
        
        # Performance metrics
        self.processing_times = []
    
    def _init_models(self):
        """Initialize perception models."""
        # Initialize base model
        self.base_model = AutoModelForSequenceClassification.from_pretrained(
            self.config.model_path,
            num_labels=self.config.num_classes
        )
        
        # Initialize tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_path)
        
        # Initialize custom layers
        self.visual_encoder = nn.Sequential(
            nn.Linear(2048, self.config.hidden_size),
            nn.ReLU(),
            nn.Dropout(self.config.dropout)
        )
        
        self.audio_encoder = nn.Sequential(
            nn.Linear(1024, self.config.hidden_size),
            nn.ReLU(),
            nn.Dropout(self.config.dropout)
        )
        
        self.fusion_layer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=self.config.hidden_size,
                nhead=8,
                dim_feedforward=2048,
                dropout=self.config.dropout
            ),
            num_layers=self.config.num_layers
        )
        
        self.classifier = nn.Sequential(
            nn.Linear(self.config.hidden_size, self.config.hidden_size),
            nn.ReLU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(self.config.hidden_size, self.config.num_classes)
        )
        
        # Move models to specified device
        if self.config.device == "cuda" and torch.cuda.is_available():
            self.to("cuda")
    
    def forward(self, visual_features: torch.Tensor, audio_features: torch.Tensor,
                text_features: torch.Tensor) -> torch.Tensor:
        """Forward pass through the model."""
        # Encode visual features
        visual_encoded = self.visual_encoder(visual_features)
        
        # Encode audio features
        audio_encoded = self.audio_encoder(audio_features)
        
        # Combine features
        combined = torch.stack([visual_encoded, audio_encoded, text_features], dim=1)
        
        # Apply transformer fusion
        fused = self.fusion_layer(combined)
        
        # Pool features
        pooled = torch.mean(fused, dim=1)
        
        # Classify
        logits = self.classifier(pooled)
        
        return logits
    
    def interpret(self, fused_data: Dict[str, Any]) -> Dict[str, Any]:
        """Interpret fused sensory data."""
        start_time = time.time()
        
        try:
            # Extract features
            visual_features = self._extract_visual_features(fused_data)
            audio_features = self._extract_audio_features(fused_data)
            text_features = self._extract_text_features(fused_data)
            
            # Prepare inputs
            visual_tensor = torch.tensor(visual_features, dtype=torch.float32)
            audio_tensor = torch.tensor(audio_features, dtype=torch.float32)
            text_tensor = torch.tensor(text_features, dtype=torch.float32)
            
            # Move to device
            if self.config.device == "cuda" and torch.cuda.is_available():
                visual_tensor = visual_tensor.cuda()
                audio_tensor = audio_tensor.cuda()
                text_tensor = text_tensor.cuda()
            
            # Get predictions
            with torch.no_grad():
                logits = self(visual_tensor, audio_tensor, text_tensor)
                probs = F.softmax(logits, dim=-1)
            
            # Get top predictions
            top_probs, top_indices = torch.topk(probs, k=3)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            return {
                "predictions": [
                    {
                        "class": self.id2label[idx.item()],
                        "confidence": prob.item()
                    }
                    for prob, idx in zip(top_probs[0], top_indices[0])
                ],
                "processing_time": processing_time,
                "timestamp": time.time()
            }
        
        except Exception as e:
            self.logger.error(f"Error in interpretation: {str(e)}")
            return {"error": str(e)}
    
    def _extract_visual_features(self, fused_data: Dict[str, Any]) -> np.ndarray:
        """Extract visual features from fused data."""
        features = []
        
        try:
            # Extract object features
            if "visual_features" in fused_data and "objects" in fused_data["visual_features"]:
                for obj in fused_data["visual_features"]["objects"]:
                    features.extend([
                        obj["confidence"],
                        *obj["bbox"]
                    ])
            
            # Extract face features
            if "visual_features" in fused_data and "faces" in fused_data["visual_features"]:
                for face in fused_data["visual_features"]["faces"]:
                    features.extend([
                        face["confidence"],
                        *face["bbox"]
                    ])
            
            # Extract scene features
            if "visual_features" in fused_data and "scene" in fused_data["visual_features"]:
                scene = fused_data["visual_features"]["scene"]
                features.extend([
                    scene["brightness"],
                    scene["contrast"],
                    scene["edge_density"]
                ])
        
        except Exception as e:
            self.logger.error(f"Error in visual feature extraction: {str(e)}")
        
        # Pad or truncate to fixed size
        if len(features) < 2048:
            features.extend([0] * (2048 - len(features)))
        else:
            features = features[:2048]
        
        return np.array(features)
    
    def _extract_audio_features(self, fused_data: Dict[str, Any]) -> np.ndarray:
        """Extract audio features from fused data."""
        features = []
        
        try:
            # Extract speech features
            if "audio_features" in fused_data and "speech" in fused_data["audio_features"]:
                speech = fused_data["audio_features"]["speech"]
                features.extend([
                    speech["confidence"]
                ])
            
            # Extract audio characteristics
            if "audio_features" in fused_data and "characteristics" in fused_data["audio_features"]:
                chars = fused_data["audio_features"]["characteristics"]
                features.extend([
                    chars["rms"],
                    chars["zcr"],
                    chars["centroid"],
                    chars["bandwidth"]
                ])
            
            # Extract spectral features
            if "audio_features" in fused_data and "spectral" in fused_data["audio_features"]:
                spectral = fused_data["audio_features"]["spectral"]
                if "mfccs" in spectral:
                    features.extend(np.mean(spectral["mfccs"], axis=1))
        
        except Exception as e:
            self.logger.error(f"Error in audio feature extraction: {str(e)}")
        
        # Pad or truncate to fixed size
        if len(features) < 1024:
            features.extend([0] * (1024 - len(features)))
        else:
            features = features[:1024]
        
        return np.array(features)
    
    def _extract_text_features(self, fused_data: Dict[str, Any]) -> np.ndarray:
        """Extract text features from fused data."""
        features = []
        
        try:
            # Extract speech text
            if "audio_features" in fused_data and "speech" in fused_data["audio_features"]:
                text = fused_data["audio_features"]["speech"]["text"]
                
                # Tokenize text
                inputs = self.tokenizer(
                    text,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512
                )
                
                # Get embeddings
                with torch.no_grad():
                    outputs = self.base_model(**inputs, output_hidden_states=True)
                    features = outputs.hidden_states[-1].mean(dim=1).squeeze().numpy()
        
        except Exception as e:
            self.logger.error(f"Error in text feature extraction: {str(e)}")
        
        # Pad or truncate to fixed size
        if len(features) < self.config.hidden_size:
            features = np.pad(features, (0, self.config.hidden_size - len(features)))
        else:
            features = features[:self.config.hidden_size]
        
        return features
    
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
        """Reset the perception model."""
        self.processing_times = []
        self.logger.info("Perception model reset") 