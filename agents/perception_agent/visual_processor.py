import cv2
import numpy as np
import torch
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from ultralytics import YOLO
import mediapipe as mp

@dataclass
class VisualConfig:
    """Configuration for visual processing."""
    model_path: str
    confidence_threshold: float
    device: str
    max_faces: int
    min_detection_confidence: float
    min_tracking_confidence: float

class VisualProcessor:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the visual processor."""
        self.logger = logging.getLogger(__name__)
        self.config = VisualConfig(**config)
        
        # Initialize models
        self._init_models()
        
        # Performance metrics
        self.processing_times = []
    
    def _init_models(self):
        """Initialize visual processing models."""
        # Initialize YOLO for object detection
        self.object_detector = YOLO(self.config.model_path)
        
        # Initialize MediaPipe for face detection
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=self.config.max_faces,
            min_detection_confidence=self.config.min_detection_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence
        )
        
        # Move models to specified device
        if self.config.device == "cuda" and torch.cuda.is_available():
            self.object_detector.to("cuda")
    
    def process(self, frame: Optional[np.ndarray]) -> Dict[str, Any]:
        """Process a single frame."""
        if frame is None:
            return {"error": "No frame provided"}
        
        start_time = time.time()
        
        try:
            # Convert frame to RGB for MediaPipe
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Detect objects
            objects = self._detect_objects(frame)
            
            # Detect faces
            faces = self._detect_faces(frame_rgb)
            
            # Extract scene features
            scene_features = self._extract_scene_features(frame)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            return {
                "objects": objects,
                "faces": faces,
                "scene_features": scene_features,
                "processing_time": processing_time,
                "timestamp": time.time()
            }
        
        except Exception as e:
            self.logger.error(f"Error in visual processing: {str(e)}")
            return {"error": str(e)}
    
    def _detect_objects(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect objects in the frame using YOLO."""
        objects = []
        
        try:
            # Run object detection
            results = self.object_detector(frame)
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Get class and confidence
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    
                    if conf >= self.config.confidence_threshold:
                        # Get bounding box
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        
                        objects.append({
                            "class": result.names[cls],
                            "confidence": conf,
                            "bbox": [x1, y1, x2, y2]
                        })
        
        except Exception as e:
            self.logger.error(f"Error in object detection: {str(e)}")
        
        return objects
    
    def _detect_faces(self, frame_rgb: np.ndarray) -> List[Dict[str, Any]]:
        """Detect faces in the frame using MediaPipe."""
        faces = []
        
        try:
            # Detect faces
            results = self.face_mesh.process(frame_rgb)
            
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # Get face bounding box
                    h, w = frame_rgb.shape[:2]
                    x_min = w
                    y_min = h
                    x_max = 0
                    y_max = 0
                    
                    for landmark in face_landmarks.landmark:
                        x, y = int(landmark.x * w), int(landmark.y * h)
                        x_min = min(x_min, x)
                        y_min = min(y_min, y)
                        x_max = max(x_max, x)
                        y_max = max(y_max, y)
                    
                    faces.append({
                        "bbox": [x_min, y_min, x_max, y_max],
                        "landmarks": [[lm.x, lm.y, lm.z] for lm in face_landmarks.landmark],
                        "confidence": 1.0
                    })
        
        except Exception as e:
            self.logger.error(f"Error in face detection: {str(e)}")
        
        return faces
    
    def _extract_scene_features(self, frame: np.ndarray) -> Dict[str, Any]:
        """Extract scene-level features from the frame."""
        features = {}
        
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate brightness
            brightness = np.mean(gray)
            
            # Calculate contrast
            contrast = np.std(gray)
            
            # Detect edges
            edges = cv2.Canny(gray, 100, 200)
            edge_density = np.mean(edges > 0)
            
            features = {
                "brightness": float(brightness),
                "contrast": float(contrast),
                "edge_density": float(edge_density)
            }
        
        except Exception as e:
            self.logger.error(f"Error in scene feature extraction: {str(e)}")
        
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
        """Reset the visual processor."""
        self.processing_times = []
        self.logger.info("Visual processor reset") 