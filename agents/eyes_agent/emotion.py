import cv2
import numpy as np
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import yaml
import tensorflow as tf

@dataclass
class EmotionConfig:
    """Configuration for emotion detection module."""
    model: str
    emotions: List[str]
    min_confidence: float
    update_interval: float
    temporal_smoothing: Dict[str, Any]
    visualization: Dict[str, Any]

class EmotionDetector:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the emotion detection module."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize emotion model
        self._init_model()
        
        # Emotion state
        self.current_emotions = {}
        self.emotion_history = []
        self.last_update_time = time.time()
        
        # Performance metrics
        self.detection_time = 0
        self.processing_time = 0
    
    def _load_config(self, config_path: str) -> EmotionConfig:
        """Load emotion detection configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return EmotionConfig(**config_data.get("emotion", {}))
    
    def _init_model(self):
        """Initialize emotion detection model."""
        if self.config.model == "emotion_ferplus":
            # Load FER+ model
            self.model = tf.keras.models.load_model("models/emotion/ferplus_model.h5")
        else:
            raise ValueError(f"Unsupported emotion model: {self.config.model}")
    
    def detect(self, frame: np.ndarray, faces: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect emotions in detected faces."""
        start_time = time.time()
        
        emotions = {
            "faces": [],
            "timestamp": time.time()
        }
        
        for face in faces:
            # Extract face region
            x1, y1, x2, y2 = face["bbox"]
            face_region = frame[y1:y2, x1:x2]
            
            if face_region.size == 0:
                continue
            
            # Preprocess face
            face_processed = self._preprocess_face(face_region)
            
            # Detect emotion
            emotion_probs = self.model.predict(face_processed)
            
            # Get top emotion
            top_idx = np.argmax(emotion_probs[0])
            emotion = self.config.emotions[top_idx]
            confidence = float(emotion_probs[0][top_idx])
            
            if confidence >= self.config.min_confidence:
                emotions["faces"].append({
                    "bbox": face["bbox"],
                    "emotion": emotion,
                    "confidence": confidence,
                    "probabilities": {
                        emo: float(prob)
                        for emo, prob in zip(self.config.emotions, emotion_probs[0])
                    }
                })
        
        # Apply temporal smoothing
        if self.config.temporal_smoothing["enabled"]:
            emotions = self._apply_temporal_smoothing(emotions)
        
        # Update state
        self.current_emotions = emotions
        self.emotion_history.append(emotions)
        
        # Update metrics
        self.detection_time = time.time() - start_time
        self.last_update_time = time.time()
        
        return emotions
    
    def _preprocess_face(self, face: np.ndarray) -> np.ndarray:
        """Preprocess face for emotion detection."""
        # Resize to model input size
        face_resized = cv2.resize(face, (48, 48))
        
        # Convert to grayscale
        face_gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
        
        # Normalize
        face_normalized = face_gray.astype(np.float32) / 255.0
        
        # Add batch and channel dimensions
        face_batch = np.expand_dims(face_normalized, axis=[0, -1])
        
        return face_batch
    
    def _apply_temporal_smoothing(self, emotions: Dict[str, Any]) -> Dict[str, Any]:
        """Apply temporal smoothing to emotion detections."""
        if not self.emotion_history:
            return emotions
        
        # Get recent history
        window_size = self.config.temporal_smoothing["window_size"]
        recent_history = self.emotion_history[-window_size:]
        
        # Smooth face emotions
        smoothed_faces = []
        for face in emotions["faces"]:
            # Find matching face in history
            face_history = []
            for hist in recent_history:
                for hist_face in hist["faces"]:
                    if self._is_same_face(face["bbox"], hist_face["bbox"]):
                        face_history.append(hist_face)
                        break
            
            if face_history:
                # Calculate smoothed probabilities
                smoothed_probs = {}
                for emotion in self.config.emotions:
                    probs = [f["probabilities"][emotion] for f in face_history]
                    smoothed_probs[emotion] = np.mean(probs)
                
                # Get top emotion
                top_emotion = max(smoothed_probs.items(), key=lambda x: x[1])
                
                smoothed_faces.append({
                    "bbox": face["bbox"],
                    "emotion": top_emotion[0],
                    "confidence": top_emotion[1],
                    "probabilities": smoothed_probs
                })
        
        return {
            "faces": smoothed_faces,
            "timestamp": emotions["timestamp"]
        }
    
    def _is_same_face(self, bbox1: List[int], bbox2: List[int]) -> bool:
        """Check if two bounding boxes represent the same face."""
        # Calculate IoU
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        union = area1 + area2 - intersection
        
        return intersection / union > 0.5
    
    def get_emotion_summary(self) -> Dict[str, Any]:
        """Get summary of current emotions."""
        if not self.current_emotions["faces"]:
            return {
                "dominant_emotion": None,
                "emotion_counts": {},
                "average_confidence": 0.0,
                "timestamp": time.time()
            }
        
        # Count emotions
        emotion_counts = {}
        total_confidence = 0.0
        
        for face in self.current_emotions["faces"]:
            emotion = face["emotion"]
            confidence = face["confidence"]
            
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
            total_confidence += confidence
        
        # Find dominant emotion
        dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])
        
        return {
            "dominant_emotion": dominant_emotion[0],
            "emotion_counts": emotion_counts,
            "average_confidence": total_confidence / len(self.current_emotions["faces"]),
            "timestamp": time.time()
        }
    
    def get_emotion_visualization(self, frame: np.ndarray,
                                emotions: Dict[str, Any]) -> np.ndarray:
        """Create visualization of emotion detections."""
        vis = frame.copy()
        
        for face in emotions["faces"]:
            x1, y1, x2, y2 = face["bbox"]
            emotion = face["emotion"]
            confidence = face["confidence"]
            
            # Draw face box
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw emotion label
            label = f"{emotion}: {confidence:.2f}"
            cv2.putText(vis, label, (x1, y1 - 10),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Draw emotion probabilities
            y_offset = y1 - 30
            for emo, prob in face["probabilities"].items():
                label = f"{emo}: {prob:.2f}"
                cv2.putText(vis, label, (x1, y_offset),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                y_offset -= 15
        
        return vis
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        return {
            "detection_time": self.detection_time,
            "processing_time": self.processing_time,
            "time_since_update": time.time() - self.last_update_time
        }
    
    def reset(self):
        """Reset the emotion detection module."""
        self.current_emotions = {}
        self.emotion_history.clear()
        self.last_update_time = time.time()
        self.detection_time = 0
        self.processing_time = 0
        self.logger.info("Emotion detection module reset")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create emotion detector
    emotion_detector = EmotionDetector()
    
    # Test with webcam
    cap = cv2.VideoCapture(0)
    
    try:
        while True:
            # Read frame
            ret, frame = cap.read()
            if not ret:
                break
            
            # Create dummy face detections for testing
            faces = [{
                "bbox": [100, 100, 200, 200],
                "confidence": 0.9
            }]
            
            # Detect emotions
            emotions = emotion_detector.detect(frame, faces)
            
            # Get visualization
            vis = emotion_detector.get_emotion_visualization(frame, emotions)
            
            # Display frame
            cv2.imshow("Emotion Detection Test", vis)
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Print performance metrics
            metrics = emotion_detector.get_performance_metrics()
            print(f"Detection time: {metrics['detection_time']*1000:.1f}ms")
            print(f"Processing time: {metrics['processing_time']*1000:.1f}ms")
            print("---")
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cap.release()
        cv2.destroyAllWindows() 