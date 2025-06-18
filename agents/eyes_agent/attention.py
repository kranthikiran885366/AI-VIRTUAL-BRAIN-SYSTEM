import numpy as np
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import yaml
import cv2

@dataclass
class AttentionConfig:
    """Configuration for attention module."""
    fovea_radius: int
    peripheral_blur: float
    focus_weights: Dict[str, float]
    min_focus_duration: float
    max_focus_duration: float

class Attention:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the attention module."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Attention state
        self.current_focus = None
        self.focus_start_time = None
        self.focus_duration = 0
        self.attention_map = None
        self.last_update_time = time.time()
        
        # Performance metrics
        self.update_time = 0
        self.focus_changes = 0
    
    def _load_config(self, config_path: str) -> AttentionConfig:
        """Load attention configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return AttentionConfig(**config_data.get("attention", {}))
    
    def update(self, frame: np.ndarray, detections: Dict[str, Any]) -> Dict[str, Any]:
        """Update attention based on current frame and detections."""
        start_time = time.time()
        
        # Initialize attention map
        h, w = frame.shape[:2]
        self.attention_map = np.zeros((h, w), dtype=np.float32)
        
        # Update attention based on different factors
        self._update_attention_from_faces(detections["faces"])
        self._update_attention_from_objects(detections["objects"])
        self._update_attention_from_scene(detections["scene"])
        
        # Normalize attention map
        if np.max(self.attention_map) > 0:
            self.attention_map /= np.max(self.attention_map)
        
        # Update focus
        self._update_focus()
        
        # Update metrics
        self.update_time = time.time() - start_time
        self.last_update_time = time.time()
        
        return {
            "attention_map": self.attention_map,
            "current_focus": self.current_focus,
            "focus_duration": self.focus_duration,
            "timestamp": time.time()
        }
    
    def _update_attention_from_faces(self, faces: List[Dict[str, Any]]):
        """Update attention map based on detected faces."""
        if not faces:
            return
        
        for face in faces:
            x1, y1, x2, y2 = face["bbox"]
            confidence = face["confidence"]
            
            # Create face attention region
            face_region = np.zeros_like(self.attention_map)
            cv2.rectangle(face_region, (x1, y1), (x2, y2), 1.0, -1)
            
            # Apply Gaussian blur to create smooth attention falloff
            face_region = cv2.GaussianBlur(face_region, (0, 0), self.config.fovea_radius)
            
            # Add to attention map with face weight
            self.attention_map += face_region * confidence * self.config.focus_weights["emotion"]
    
    def _update_attention_from_objects(self, objects: List[Dict[str, Any]]):
        """Update attention map based on detected objects."""
        if not objects:
            return
        
        for obj in objects:
            x1, y1, x2, y2 = obj["bbox"]
            confidence = obj["confidence"]
            
            # Create object attention region
            obj_region = np.zeros_like(self.attention_map)
            cv2.rectangle(obj_region, (x1, y1), (x2, y2), 1.0, -1)
            
            # Apply Gaussian blur
            obj_region = cv2.GaussianBlur(obj_region, (0, 0), self.config.fovea_radius)
            
            # Add to attention map with object weight
            self.attention_map += obj_region * confidence * self.config.focus_weights["task"]
    
    def _update_attention_from_scene(self, scene: Optional[Dict[str, Any]]):
        """Update attention map based on scene classification."""
        if not scene:
            return
        
        # Create scene attention region (full frame)
        scene_region = np.ones_like(self.attention_map)
        
        # Apply Gaussian blur for peripheral vision
        scene_region = cv2.GaussianBlur(scene_region, (0, 0),
                                      int(self.config.fovea_radius * 2))
        
        # Add to attention map with scene weight
        self.attention_map += scene_region * scene["confidence"] * self.config.focus_weights["movement"]
    
    def _update_focus(self):
        """Update current focus point based on attention map."""
        if self.attention_map is None or np.max(self.attention_map) == 0:
            return
        
        # Find point of maximum attention
        h, w = self.attention_map.shape
        max_val = np.max(self.attention_map)
        max_pos = np.unravel_index(np.argmax(self.attention_map), self.attention_map.shape)
        
        # Check if we should change focus
        should_change = False
        
        if self.current_focus is None:
            should_change = True
        else:
            # Calculate distance to current focus
            current_y, current_x = self.current_focus
            new_y, new_x = max_pos
            distance = np.sqrt((current_x - new_x)**2 + (current_y - new_y)**2)
            
            # Change focus if new point is significantly more interesting
            if max_val > 1.5 * self.attention_map[current_y, current_x]:
                should_change = True
            
            # Change focus if current focus duration exceeds maximum
            if self.focus_duration > self.config.max_focus_duration:
                should_change = True
        
        if should_change:
            self.current_focus = max_pos
            self.focus_start_time = time.time()
            self.focus_duration = 0
            self.focus_changes += 1
        else:
            # Update focus duration
            self.focus_duration = time.time() - self.focus_start_time
    
    def get_attention_visualization(self, frame: np.ndarray) -> np.ndarray:
        """Create visualization of attention map."""
        if self.attention_map is None:
            return frame
        
        # Create visualization
        vis = frame.copy()
        
        # Convert attention map to heatmap
        attention_vis = cv2.applyColorMap(
            (self.attention_map * 255).astype(np.uint8),
            cv2.COLORMAP_JET
        )
        
        # Blend with original frame
        alpha = 0.5
        vis = cv2.addWeighted(vis, 1 - alpha, attention_vis, alpha, 0)
        
        # Draw current focus point
        if self.current_focus is not None:
            y, x = self.current_focus
            cv2.circle(vis, (x, y), self.config.fovea_radius, (0, 255, 0), 2)
            cv2.circle(vis, (x, y), 2, (0, 255, 0), -1)
        
        return vis
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        return {
            "update_time": self.update_time,
            "focus_changes": self.focus_changes,
            "focus_duration": self.focus_duration,
            "time_since_update": time.time() - self.last_update_time
        }
    
    def reset(self):
        """Reset the attention module."""
        self.current_focus = None
        self.focus_start_time = None
        self.focus_duration = 0
        self.attention_map = None
        self.last_update_time = time.time()
        self.update_time = 0
        self.focus_changes = 0
        self.logger.info("Attention module reset")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create attention module
    attention = Attention()
    
    # Test with webcam
    cap = cv2.VideoCapture(0)
    
    try:
        while True:
            # Read frame
            ret, frame = cap.read()
            if not ret:
                break
            
            # Create dummy detections for testing
            detections = {
                "faces": [{
                    "bbox": [100, 100, 200, 200],
                    "confidence": 0.9
                }],
                "objects": [{
                    "bbox": [300, 300, 400, 400],
                    "confidence": 0.8
                }],
                "scene": {
                    "class": "indoor",
                    "confidence": 0.7
                }
            }
            
            # Update attention
            attention.update(frame, detections)
            
            # Get visualization
            vis = attention.get_attention_visualization(frame)
            
            # Display frame
            cv2.imshow("Attention Test", vis)
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Print performance metrics
            metrics = attention.get_performance_metrics()
            print(f"Update time: {metrics['update_time']*1000:.1f}ms")
            print(f"Focus changes: {metrics['focus_changes']}")
            print(f"Focus duration: {metrics['focus_duration']:.1f}s")
            print("---")
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cap.release()
        cv2.destroyAllWindows() 