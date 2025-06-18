import cv2
import torch
import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import asyncio
from datetime import datetime
import json

class FaceTracker:
    def __init__(self, config: Dict[str, Any]):
        """Initialize face tracker with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Load face detection model
        self.face_cascade_path = config.get("face_cascade_path", "models/haarcascade_frontalface_default.xml")
        self.eye_cascade_path = config.get("eye_cascade_path", "models/haarcascade_eye.xml")
        
        # Tracking settings
        self.min_face_size = config.get("min_face_size", (30, 30))
        self.tracking_history = config.get("tracking_history", 30)
        self.confidence_threshold = config.get("confidence_threshold", 0.5)
        
        # Load cascades
        self.face_cascade = None
        self.eye_cascade = None
        self._load_cascades()
        
        # Tracking state
        self.trackers = {}
        self.track_history = {}
        self.next_track_id = 0
        
        # Metrics
        self.metrics = {
            "total_faces_detected": 0,
            "total_faces_tracked": 0,
            "average_confidence": 0,
            "processing_times": [],
            "start_time": datetime.utcnow().isoformat()
        }
        
        self.logger.info("Face tracker initialized")

    def _load_cascades(self):
        """Load face and eye detection cascades."""
        try:
            self.face_cascade = cv2.CascadeClassifier(self.face_cascade_path)
            self.eye_cascade = cv2.CascadeClassifier(self.eye_cascade_path)
            
            if self.face_cascade.empty() or self.eye_cascade.empty():
                raise RuntimeError("Failed to load cascade classifiers")
            
            self.logger.info("Cascade classifiers loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load cascade classifiers: {str(e)}")
            raise

    async def track(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Track faces in the frame."""
        if self.face_cascade is None or self.eye_cascade is None:
            return []
            
        try:
            start_time = datetime.utcnow()
            
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=self.min_face_size
            )
            
            # Update trackers
            tracked_faces = self._update_trackers(frame, faces)
            
            # Update metrics
            self._update_metrics(tracked_faces, start_time)
            
            return tracked_faces
            
        except Exception as e:
            self.logger.error(f"Error in face tracking: {str(e)}")
            return []

    def _update_trackers(self, frame: np.ndarray, faces: List[tuple]) -> List[Dict[str, Any]]:
        """Update face trackers with new detections."""
        tracked_faces = []
        
        # Get current trackers
        current_trackers = list(self.trackers.keys())
        
        # Update existing trackers
        for track_id in current_trackers:
            success, bbox = self.trackers[track_id].update(frame)
            if success:
                # Update track history
                self.track_history[track_id].append(bbox)
                if len(self.track_history[track_id]) > self.tracking_history:
                    self.track_history[track_id].pop(0)
                
                # Add to tracked faces
                x, y, w, h = [int(v) for v in bbox]
                tracked_faces.append({
                    "track_id": track_id,
                    "bbox": {
                        "x": x,
                        "y": y,
                        "width": w,
                        "height": h
                    },
                    "confidence": 1.0,  # Tracker doesn't provide confidence
                    "history": self.track_history[track_id]
                })
            else:
                # Remove failed tracker
                del self.trackers[track_id]
                del self.track_history[track_id]
        
        # Create new trackers for unmatched faces
        for face in faces:
            x, y, w, h = face
            
            # Check if face overlaps with existing trackers
            overlap = False
            for track_id in current_trackers:
                if track_id in self.trackers:
                    success, bbox = self.trackers[track_id].update(frame)
                    if success:
                        tx, ty, tw, th = [int(v) for v in bbox]
                        if self._calculate_iou((x, y, w, h), (tx, ty, tw, th)) > 0.5:
                            overlap = True
                            break
            
            if not overlap:
                # Create new tracker
                tracker = cv2.TrackerCSRT_create()
                tracker.init(frame, (x, y, w, h))
                
                # Assign new track ID
                track_id = self.next_track_id
                self.next_track_id += 1
                
                self.trackers[track_id] = tracker
                self.track_history[track_id] = [(x, y, w, h)]
                
                # Add to tracked faces
                tracked_faces.append({
                    "track_id": track_id,
                    "bbox": {
                        "x": x,
                        "y": y,
                        "width": w,
                        "height": h
                    },
                    "confidence": 1.0,
                    "history": self.track_history[track_id]
                })
        
        return tracked_faces

    def _calculate_iou(self, box1: tuple, box2: tuple) -> float:
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

    def _update_metrics(self, tracked_faces: List[Dict[str, Any]], start_time: datetime):
        """Update tracking metrics."""
        # Update total faces
        self.metrics["total_faces_detected"] += len(tracked_faces)
        self.metrics["total_faces_tracked"] += len(self.trackers)
        
        # Update processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        self.metrics["processing_times"].append(processing_time)
        
        # Keep only last 100 processing times
        if len(self.metrics["processing_times"]) > 100:
            self.metrics["processing_times"] = self.metrics["processing_times"][-100:]

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the face tracker."""
        return {
            "cascades_loaded": self.face_cascade is not None and self.eye_cascade is not None,
            "min_face_size": self.min_face_size,
            "tracking_history": self.tracking_history,
            "confidence_threshold": self.confidence_threshold,
            "active_trackers": len(self.trackers),
            "metrics": self.metrics
        }

    def update_config(self, new_config: Dict[str, Any]):
        """Update tracker configuration."""
        try:
            # Update settings
            if "min_face_size" in new_config:
                self.min_face_size = new_config["min_face_size"]
            
            if "tracking_history" in new_config:
                self.tracking_history = new_config["tracking_history"]
            
            if "confidence_threshold" in new_config:
                self.confidence_threshold = new_config["confidence_threshold"]
            
            # Update cascades if changed
            if "face_cascade_path" in new_config and new_config["face_cascade_path"] != self.face_cascade_path:
                self.face_cascade_path = new_config["face_cascade_path"]
                self._load_cascades()
            
            if "eye_cascade_path" in new_config and new_config["eye_cascade_path"] != self.eye_cascade_path:
                self.eye_cascade_path = new_config["eye_cascade_path"]
                self._load_cascades()
            
            # Update configuration
            self.config.update(new_config)
            
            self.logger.info("Face tracker configuration updated successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to update face tracker configuration: {str(e)}")
            raise

    def _load_landmarks_model(self):
        """Load face landmarks detection model."""
        # Implementation depends on the specific model you're using
        # This is a placeholder
        return None

    def _load_pose_model(self):
        """Load 3D pose estimation model."""
        # Implementation depends on the specific model you're using
        # This is a placeholder
        return None

    def preprocess(self, frame: np.ndarray) -> torch.Tensor:
        """Preprocess frame for face detection."""
        # Convert to RGB
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        elif frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        elif frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Normalize
        frame = frame.astype(np.float32) / 255.0
        
        # Convert to tensor
        tensor = torch.from_numpy(frame).permute(2, 0, 1).unsqueeze(0)
        
        if torch.cuda.is_available():
            tensor = tensor.cuda()
        
        return tensor

    def detect_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect faces in the frame."""
        try:
            # Preprocess frame
            input_tensor = self.preprocess(frame)
            
            # Run inference
            with torch.no_grad():
                detections = self.model(input_tensor)
            
            # Process detections
            faces = []
            for detection in detections[0]:
                confidence = detection[4].item()
                if confidence < self.confidence_threshold:
                    continue
                
                # Get bounding box
                x1, y1, x2, y2 = detection[:4].tolist()
                x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
                
                # Check face size
                face_size = max(x2 - x1, y2 - y1)
                if face_size < self.min_face_size[0] or face_size > self.min_face_size[1]:
                    continue
                
                face = {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": confidence
                }
                
                # Detect landmarks if enabled
                if self.enable_landmarks:
                    landmarks = self._detect_landmarks(frame, face)
                    face["landmarks"] = landmarks
                
                # Estimate 3D pose if enabled
                if self.enable_3d_pose:
                    pose = self._estimate_pose(frame, face)
                    face["pose"] = pose
                
                faces.append(face)
            
            return faces
            
        except Exception as e:
            self.logger.error(f"Error in face detection: {e}")
            return []

    def _detect_landmarks(self, frame: np.ndarray, face: Dict[str, Any]) -> List[Tuple[int, int]]:
        """Detect facial landmarks for a face."""
        if not self.enable_landmarks or self.landmarks_model is None:
            return []
        
        # Extract face region
        x1, y1, x2, y2 = face["bbox"]
        face_region = frame[y1:y2, x1:x2]
        
        # Detect landmarks
        # Implementation depends on the specific model you're using
        # This is a placeholder
        landmarks = []
        
        return landmarks

    def _estimate_pose(self, frame: np.ndarray, face: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate 3D pose for a face."""
        if not self.enable_3d_pose or self.pose_model is None:
            return {}
        
        # Extract face region
        x1, y1, x2, y2 = face["bbox"]
        face_region = frame[y1:y2, x1:x2]
        
        # Estimate pose
        # Implementation depends on the specific model you're using
        # This is a placeholder
        pose = {
            "rotation": [0, 0, 0],  # [pitch, yaw, roll]
            "translation": [0, 0, 0]  # [x, y, z]
        }
        
        return pose

    def get_track_history(self, track_id: int) -> Optional[List[Tuple[int, int, int, int]]]:
        """Get tracking history for a specific track ID."""
        return self.track_history.get(track_id)

    def draw_track_history(self, frame: np.ndarray, track_id: int, color: Tuple[int, int, int] = (0, 255, 0)):
        """Draw tracking history for a specific track ID."""
        history = self.get_track_history(track_id)
        if history is None:
            return frame
        
        # Draw tracking path
        points = []
        for bbox in history:
            x, y, w, h = bbox
            center_x = x + w // 2
            center_y = y + h // 2
            points.append((center_x, center_y))
        
        # Draw lines between points
        for i in range(1, len(points)):
            cv2.line(frame, points[i-1], points[i], color, 2)
        
        return frame

    def reset_tracking(self):
        """Reset all trackers and tracking history."""
        self.trackers.clear()
        self.track_history.clear()
        self.next_track_id = 0
        self.logger.info("Face tracking reset") 