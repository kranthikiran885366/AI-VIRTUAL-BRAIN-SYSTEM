import cv2
import numpy as np
from typing import Dict, Any, Tuple, List, Optional
import logging
from dataclasses import dataclass
import time
from collections import deque

@dataclass
class GazePoint:
    """Data class for gaze point information."""
    position: Tuple[float, float]
    confidence: float
    timestamp: float
    object_id: Optional[int] = None

class GazeDetector:
    def __init__(self, config: Dict[str, Any]):
        """Initialize gaze detector."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Initialize YOLO for object detection
        self.net = cv2.dnn.readNetFromDarknet(
            self.config["yolo_config"],
            self.config["yolo_weights"]
        )
        self.classes = self._load_classes(self.config["yolo_classes"])
        
        # Gaze tracking
        self.gaze_history: deque[GazePoint] = deque(maxlen=config.get("history_size", 100))
        self.attention_heatmap = np.zeros((config.get("heatmap_height", 480),
                                         config.get("heatmap_width", 640)))
        
        # Object tracking
        self.tracked_objects: Dict[int, Dict[str, Any]] = {}
        self.next_object_id = 0
        
        # Gaze calibration
        self.calibration_points: List[Tuple[float, float]] = []
        self.calibration_data: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        self.is_calibrated = False
    
    def _load_classes(self, classes_path: str) -> List[str]:
        """Load YOLO class names."""
        with open(classes_path, 'r') as f:
            return [line.strip() for line in f.readlines()]
    
    def detect(self, frame: np.ndarray, pupil_position: Tuple[float, float]) -> Tuple[float, float]:
        """Detect gaze direction and focused object."""
        # Detect objects in frame
        objects = self._detect_objects(frame)
        
        # Update object tracking
        self._update_object_tracking(objects)
        
        # Calculate gaze direction
        gaze_direction = self._calculate_gaze_direction(pupil_position)
        
        # Find focused object
        focused_object = self._find_focused_object(gaze_direction)
        
        # Update gaze history
        self._update_gaze_history(pupil_position, focused_object)
        
        # Update attention heatmap
        self._update_attention_heatmap(pupil_position)
        
        return gaze_direction
    
    def _detect_objects(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect objects in frame using YOLO."""
        height, width = frame.shape[:2]
        
        # Prepare input blob
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
        self.net.setInput(blob)
        
        # Get output layers
        layer_names = self.net.getLayerNames()
        output_layers = [layer_names[i - 1] for i in self.net.getUnconnectedOutLayers()]
        
        # Forward pass
        outputs = self.net.forward(output_layers)
        
        # Process outputs
        objects = []
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                
                if confidence > self.config.get("confidence_threshold", 0.5):
                    # Get bounding box
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    
                    # Calculate box coordinates
                    x = int(center_x - w/2)
                    y = int(center_y - h/2)
                    
                    objects.append({
                        "class_id": class_id,
                        "class_name": self.classes[class_id],
                        "confidence": float(confidence),
                        "bbox": (x, y, w, h)
                    })
        
        return objects
    
    def _update_object_tracking(self, objects: List[Dict[str, Any]]):
        """Update tracked objects."""
        # Match objects with existing tracks
        matched_objects = set()
        for obj in objects:
            best_match = None
            best_iou = 0.0
            
            for obj_id, track in self.tracked_objects.items():
                if obj_id in matched_objects:
                    continue
                
                iou = self._calculate_iou(obj["bbox"], track["bbox"])
                if iou > best_iou and iou > self.config.get("tracking_iou_threshold", 0.3):
                    best_iou = iou
                    best_match = obj_id
            
            if best_match is not None:
                # Update existing track
                self.tracked_objects[best_match].update({
                    "bbox": obj["bbox"],
                    "class_id": obj["class_id"],
                    "class_name": obj["class_name"],
                    "confidence": obj["confidence"],
                    "last_seen": time.time()
                })
                matched_objects.add(best_match)
            else:
                # Create new track
                self.tracked_objects[self.next_object_id] = {
                    "bbox": obj["bbox"],
                    "class_id": obj["class_id"],
                    "class_name": obj["class_name"],
                    "confidence": obj["confidence"],
                    "first_seen": time.time(),
                    "last_seen": time.time()
                }
                self.next_object_id += 1
        
        # Remove old tracks
        current_time = time.time()
        self.tracked_objects = {
            obj_id: track for obj_id, track in self.tracked_objects.items()
            if current_time - track["last_seen"] < self.config.get("tracking_timeout", 5.0)
        }
    
    def _calculate_gaze_direction(self, pupil_position: Tuple[float, float]) -> Tuple[float, float]:
        """Calculate gaze direction from pupil position."""
        if not self.is_calibrated:
            return (0.0, 0.0)
        
        # Use calibration data to map pupil position to gaze direction
        # This is a simple linear mapping - could be improved with more sophisticated methods
        gaze_x = (pupil_position[0] - 0.5) * 2  # Map from [0,1] to [-1,1]
        gaze_y = (pupil_position[1] - 0.5) * 2
        
        return (gaze_x, gaze_y)
    
    def _find_focused_object(self, gaze_direction: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """Find the object that the gaze is focused on."""
        if not self.tracked_objects:
            return None
        
        # Convert gaze direction to screen coordinates
        screen_x = (gaze_direction[0] + 1) * self.attention_heatmap.shape[1] / 2
        screen_y = (gaze_direction[1] + 1) * self.attention_heatmap.shape[0] / 2
        
        # Find closest object
        closest_object = None
        min_distance = float('inf')
        
        for obj_id, track in self.tracked_objects.items():
            x, y, w, h = track["bbox"]
            center_x = x + w/2
            center_y = y + h/2
            
            distance = np.sqrt((screen_x - center_x)**2 + (screen_y - center_y)**2)
            if distance < min_distance:
                min_distance = distance
                closest_object = track
        
        # Check if closest object is within focus threshold
        if min_distance < self.config.get("focus_threshold", 50):
            return closest_object
        
        return None
    
    def _update_gaze_history(self, pupil_position: Tuple[float, float],
                           focused_object: Optional[Dict[str, Any]]):
        """Update gaze history with new gaze point."""
        gaze_point = GazePoint(
            position=pupil_position,
            confidence=1.0,  # Could be improved with confidence estimation
            timestamp=time.time(),
            object_id=focused_object["class_id"] if focused_object else None
        )
        
        self.gaze_history.append(gaze_point)
    
    def _update_attention_heatmap(self, pupil_position: Tuple[float, float]):
        """Update attention heatmap with new gaze point."""
        # Convert pupil position to heatmap coordinates
        x = int(pupil_position[0] * self.attention_heatmap.shape[1])
        y = int(pupil_position[1] * self.attention_heatmap.shape[0])
        
        # Add Gaussian blob to heatmap
        cv2.circle(self.attention_heatmap, (x, y), 20, 1.0, -1)
        
        # Decay heatmap
        self.attention_heatmap *= self.config.get("heatmap_decay", 0.95)
    
    def _calculate_iou(self, box1: Tuple[int, int, int, int],
                      box2: Tuple[int, int, int, int]) -> float:
        """Calculate Intersection over Union between two bounding boxes."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[0] + box1[2], box2[0] + box2[2])
        y2 = min(box1[1] + box1[3], box2[1] + box2[3])
        
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        box1_area = box1[2] * box1[3]
        box2_area = box2[2] * box2[3]
        union = box1_area + box2_area - intersection
        
        return intersection / union if union > 0 else 0
    
    def get_attention_heatmap(self) -> np.ndarray:
        """Get the current attention heatmap."""
        return self.attention_heatmap.copy()
    
    def get_gaze_history(self) -> List[GazePoint]:
        """Get the gaze history."""
        return list(self.gaze_history)
    
    def get_tracked_objects(self) -> Dict[int, Dict[str, Any]]:
        """Get currently tracked objects."""
        return self.tracked_objects.copy()
    
    def calibrate(self, calibration_points: List[Tuple[float, float]]):
        """Calibrate gaze detection with known points."""
        self.calibration_points = calibration_points
        self.calibration_data = []
        self.is_calibrated = False
    
    def add_calibration_point(self, pupil_position: Tuple[float, float],
                            target_position: Tuple[float, float]):
        """Add a calibration point."""
        self.calibration_data.append((pupil_position, target_position))
        
        if len(self.calibration_data) >= len(self.calibration_points):
            self._complete_calibration()
    
    def _complete_calibration(self):
        """Complete calibration process."""
        # Calculate calibration parameters
        # This is a simple linear mapping - could be improved with more sophisticated methods
        self.is_calibrated = True 