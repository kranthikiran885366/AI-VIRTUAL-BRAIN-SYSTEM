import numpy as np
import torch
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from transformers import CLIPProcessor, CLIPModel

@dataclass
class FusionConfig:
    """Configuration for multi-modal fusion."""
    device: str
    model_path: str
    confidence_threshold: float
    temporal_window: int
    feature_dim: int

class FusionModule:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the fusion module."""
        self.logger = logging.getLogger(__name__)
        self.config = FusionConfig(**config)
        
        # Initialize models
        self._init_models()
        
        # Temporal buffer
        self.temporal_buffer = []
        self.max_buffer_size = self.config.temporal_window
        
        # Performance metrics
        self.processing_times = []
    
    def _init_models(self):
        """Initialize fusion models."""
        # Initialize CLIP model for cross-modal alignment
        self.clip_processor = CLIPProcessor.from_pretrained(self.config.model_path)
        self.clip_model = CLIPModel.from_pretrained(self.config.model_path)
        
        # Move model to specified device
        if self.config.device == "cuda" and torch.cuda.is_available():
            self.clip_model = self.clip_model.to("cuda")
    
    def fuse(self, visual_data: Dict[str, Any], audio_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fuse visual and audio data."""
        start_time = time.time()
        
        try:
            # Update temporal buffer
            self._update_buffer(visual_data, audio_data)
            
            # Extract features
            visual_features = self._extract_visual_features(visual_data)
            audio_features = self._extract_audio_features(audio_data)
            
            # Perform cross-modal alignment
            alignment = self._align_modalities(visual_features, audio_features)
            
            # Perform temporal fusion
            temporal_fusion = self._fuse_temporal()
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            return {
                "visual_features": visual_features,
                "audio_features": audio_features,
                "alignment": alignment,
                "temporal_fusion": temporal_fusion,
                "processing_time": processing_time,
                "timestamp": time.time()
            }
        
        except Exception as e:
            self.logger.error(f"Error in fusion: {str(e)}")
            return {"error": str(e)}
    
    def _update_buffer(self, visual_data: Dict[str, Any], audio_data: Dict[str, Any]):
        """Update temporal buffer with new data."""
        # Add new data to buffer
        self.temporal_buffer.append({
            "visual": visual_data,
            "audio": audio_data,
            "timestamp": time.time()
        })
        
        # Remove old data if buffer is full
        if len(self.temporal_buffer) > self.max_buffer_size:
            self.temporal_buffer.pop(0)
    
    def _extract_visual_features(self, visual_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features from visual data."""
        features = {}
        
        try:
            # Extract object features
            if "objects" in visual_data:
                object_features = []
                for obj in visual_data["objects"]:
                    if obj["confidence"] >= self.config.confidence_threshold:
                        object_features.append({
                            "class": obj["class"],
                            "confidence": obj["confidence"],
                            "bbox": obj["bbox"]
                        })
                features["objects"] = object_features
            
            # Extract face features
            if "faces" in visual_data:
                face_features = []
                for face in visual_data["faces"]:
                    if face["confidence"] >= self.config.confidence_threshold:
                        face_features.append({
                            "landmarks": face["landmarks"],
                            "confidence": face["confidence"],
                            "bbox": face["bbox"]
                        })
                features["faces"] = face_features
            
            # Extract scene features
            if "scene_features" in visual_data:
                features["scene"] = visual_data["scene_features"]
        
        except Exception as e:
            self.logger.error(f"Error in visual feature extraction: {str(e)}")
        
        return features
    
    def _extract_audio_features(self, audio_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features from audio data."""
        features = {}
        
        try:
            # Extract speech features
            if "transcription" in audio_data:
                features["speech"] = {
                    "text": audio_data["transcription"]["text"],
                    "confidence": audio_data["transcription"]["confidence"]
                }
            
            # Extract audio characteristics
            if "characteristics" in audio_data:
                features["characteristics"] = audio_data["characteristics"]
            
            # Extract spectral features
            if "features" in audio_data:
                features["spectral"] = audio_data["features"]
        
        except Exception as e:
            self.logger.error(f"Error in audio feature extraction: {str(e)}")
        
        return features
    
    def _align_modalities(self, visual_features: Dict[str, Any],
                         audio_features: Dict[str, Any]) -> Dict[str, Any]:
        """Align visual and audio modalities."""
        alignment = {}
        
        try:
            # Prepare text input
            if "speech" in audio_features:
                text = audio_features["speech"]["text"]
            else:
                text = ""
            
            # Prepare image input (use scene features)
            if "scene" in visual_features:
                image = visual_features["scene"]
            else:
                image = None
            
            if text and image:
                # Process inputs with CLIP
                inputs = self.clip_processor(
                    text=[text],
                    images=[image],
                    return_tensors="pt",
                    padding=True
                )
                
                # Move inputs to device
                if self.config.device == "cuda" and torch.cuda.is_available():
                    inputs = {k: v.to("cuda") for k, v in inputs.items()}
                
                # Get embeddings
                outputs = self.clip_model(**inputs)
                
                # Calculate similarity
                similarity = torch.nn.functional.cosine_similarity(
                    outputs.text_embeds,
                    outputs.image_embeds
                ).item()
                
                alignment = {
                    "similarity": similarity,
                    "aligned": similarity >= self.config.confidence_threshold
                }
        
        except Exception as e:
            self.logger.error(f"Error in modality alignment: {str(e)}")
        
        return alignment
    
    def _fuse_temporal(self) -> Dict[str, Any]:
        """Fuse data across temporal window."""
        fusion = {}
        
        try:
            if not self.temporal_buffer:
                return fusion
            
            # Extract features across temporal window
            visual_features = []
            audio_features = []
            
            for frame in self.temporal_buffer:
                if "visual" in frame:
                    visual_features.append(self._extract_visual_features(frame["visual"]))
                if "audio" in frame:
                    audio_features.append(self._extract_audio_features(frame["audio"]))
            
            # Perform temporal fusion
            if visual_features:
                fusion["visual"] = self._aggregate_features(visual_features)
            if audio_features:
                fusion["audio"] = self._aggregate_features(audio_features)
        
        except Exception as e:
            self.logger.error(f"Error in temporal fusion: {str(e)}")
        
        return fusion
    
    def _aggregate_features(self, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate features across temporal window."""
        aggregated = {}
        
        try:
            # Aggregate object features
            if all("objects" in f for f in features):
                objects = {}
                for frame in features:
                    for obj in frame["objects"]:
                        if obj["class"] not in objects:
                            objects[obj["class"]] = []
                        objects[obj["class"]].append(obj["confidence"])
                
                aggregated["objects"] = {
                    cls: {
                        "mean": float(np.mean(confs)),
                        "std": float(np.std(confs)),
                        "count": len(confs)
                    }
                    for cls, confs in objects.items()
                }
            
            # Aggregate face features
            if all("faces" in f for f in features):
                faces = []
                for frame in features:
                    faces.extend(frame["faces"])
                aggregated["faces"] = faces
            
            # Aggregate scene features
            if all("scene" in f for f in features):
                scene_features = [f["scene"] for f in features]
                aggregated["scene"] = {
                    key: float(np.mean([f[key] for f in scene_features]))
                    for key in scene_features[0].keys()
                }
        
        except Exception as e:
            self.logger.error(f"Error in feature aggregation: {str(e)}")
        
        return aggregated
    
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
        """Reset the fusion module."""
        self.temporal_buffer = []
        self.processing_times = []
        self.logger.info("Fusion module reset") 