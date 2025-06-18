import cv2
import numpy as np
import mediapipe as mp
from typing import Dict, Any, Tuple, List, Optional
import logging
from dataclasses import dataclass
import time
import yaml

@dataclass
class EyeTrackingConfig:
    """Configuration for eye tracking module."""
    model: str
    pupil_detection: Dict[str, Any]
    head_pose: Dict[str, Any]
    blink_detection: Dict[str, Any]

class EyeTracker:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the eye tracking module."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize MediaPipe Face Mesh
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Eye tracking state
        self.gaze_direction = (0, 0)  # (x, y) in normalized coordinates
        self.head_pose = (0, 0, 0)  # (pitch, yaw, roll) in degrees
        self.is_blinking = False
        self.blink_start_time = None
        self.last_update_time = time.time()
        
        # Performance metrics
        self.tracking_time = 0
        self.blink_count = 0
    
    def _load_config(self, config_path: str) -> EyeTrackingConfig:
        """Load eye tracking configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return EyeTrackingConfig(**config_data.get("tracking", {}))
    
    def track(self, frame: np.ndarray) -> Dict[str, Any]:
        """Track eyes and head pose in the frame."""
        start_time = time.time()
        
        # Convert to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process frame with MediaPipe
        results = self.face_mesh.process(frame_rgb)
        
        if results.multi_face_landmarks:
            # Get first face
            face_landmarks = results.multi_face_landmarks[0]
            
            # Track eyes
            self._track_eyes(face_landmarks, frame.shape)
            
            # Track head pose
            self._track_head_pose(face_landmarks, frame.shape)
            
            # Detect blinks
            self._detect_blinks(face_landmarks)
        
        # Update metrics
        self.tracking_time = time.time() - start_time
        self.last_update_time = time.time()
        
        return {
            "gaze_direction": self.gaze_direction,
            "head_pose": self.head_pose,
            "is_blinking": self.is_blinking,
            "timestamp": time.time()
        }
    
    def _track_eyes(self, face_landmarks, frame_shape):
        """Track eye movements and gaze direction."""
        # Get eye landmarks
        left_eye = [face_landmarks.landmark[33], face_landmarks.landmark[160],
                   face_landmarks.landmark[158], face_landmarks.landmark[133],
                   face_landmarks.landmark[153], face_landmarks.landmark[144]]
        
        right_eye = [face_landmarks.landmark[362], face_landmarks.landmark[385],
                    face_landmarks.landmark[387], face_landmarks.landmark[263],
                    face_landmarks.landmark[373], face_landmarks.landmark[380]]
        
        # Calculate eye aspect ratios
        left_ear = self._calculate_ear(left_eye)
        right_ear = self._calculate_ear(right_eye)
        
        # Calculate gaze direction
        left_iris = face_landmarks.landmark[468]  # Left iris center
        right_iris = face_landmarks.landmark[473]  # Right iris center
        
        # Convert to normalized coordinates
        self.gaze_direction = (
            (left_iris.x + right_iris.x) / 2,
            (left_iris.y + right_iris.y) / 2
        )
    
    def _track_head_pose(self, face_landmarks, frame_shape):
        """Track head pose using facial landmarks."""
        # Get key points for head pose estimation
        nose_tip = face_landmarks.landmark[1]
        left_eye = face_landmarks.landmark[33]
        right_eye = face_landmarks.landmark[263]
        left_mouth = face_landmarks.landmark[61]
        right_mouth = face_landmarks.landmark[291]
        
        # Calculate head pose angles
        # This is a simplified calculation - in reality, you would use
        # a more sophisticated method like PnP algorithm
        pitch = (left_eye.y + right_eye.y) / 2 - nose_tip.y
        yaw = (left_eye.x + right_eye.x) / 2 - nose_tip.x
        roll = np.arctan2(right_eye.y - left_eye.y,
                         right_eye.x - left_eye.x)
        
        # Convert to degrees
        self.head_pose = (
            np.degrees(pitch),
            np.degrees(yaw),
            np.degrees(roll)
        )
    
    def _detect_blinks(self, face_landmarks):
        """Detect eye blinks."""
        # Get eye landmarks
        left_eye = [face_landmarks.landmark[33], face_landmarks.landmark[160],
                   face_landmarks.landmark[158], face_landmarks.landmark[133],
                   face_landmarks.landmark[153], face_landmarks.landmark[144]]
        
        right_eye = [face_landmarks.landmark[362], face_landmarks.landmark[385],
                    face_landmarks.landmark[387], face_landmarks.landmark[263],
                    face_landmarks.landmark[373], face_landmarks.landmark[380]]
        
        # Calculate eye aspect ratios
        left_ear = self._calculate_ear(left_eye)
        right_ear = self._calculate_ear(right_eye)
        
        # Average EAR
        ear = (left_ear + right_ear) / 2
        
        # Detect blink
        if ear < self.config.blink_detection["threshold"]:
            if not self.is_blinking:
                self.is_blinking = True
                self.blink_start_time = time.time()
                self.blink_count += 1
        else:
            if self.is_blinking:
                # Check blink duration
                blink_duration = time.time() - self.blink_start_time
                if (blink_duration < self.config.blink_detection["min_duration"] or
                    blink_duration > self.config.blink_detection["max_duration"]):
                    # Invalid blink duration
                    self.is_blinking = False
                    self.blink_start_time = None
    
    def _calculate_ear(self, eye_landmarks):
        """Calculate Eye Aspect Ratio (EAR)."""
        # Calculate vertical distances
        v1 = np.linalg.norm(np.array([eye_landmarks[1].x - eye_landmarks[5].x,
                                     eye_landmarks[1].y - eye_landmarks[5].y]))
        v2 = np.linalg.norm(np.array([eye_landmarks[2].x - eye_landmarks[4].x,
                                     eye_landmarks[2].y - eye_landmarks[4].y]))
        
        # Calculate horizontal distance
        h = np.linalg.norm(np.array([eye_landmarks[0].x - eye_landmarks[3].x,
                                    eye_landmarks[0].y - eye_landmarks[3].y]))
        
        # Calculate EAR
        ear = (v1 + v2) / (2.0 * h)
        
        return ear
    
    def get_tracking_visualization(self, frame: np.ndarray) -> np.ndarray:
        """Create visualization of eye tracking results."""
        vis = frame.copy()
        
        # Draw gaze direction
        h, w = frame.shape[:2]
        gaze_x = int(self.gaze_direction[0] * w)
        gaze_y = int(self.gaze_direction[1] * h)
        cv2.circle(vis, (gaze_x, gaze_y), 5, (0, 255, 0), -1)
        
        # Draw head pose
        pitch, yaw, roll = self.head_pose
        cv2.putText(vis, f"Pitch: {pitch:.1f}°", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(vis, f"Yaw: {yaw:.1f}°", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(vis, f"Roll: {roll:.1f}°", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw blink status
        blink_status = "Blinking" if self.is_blinking else "Eyes Open"
        cv2.putText(vis, blink_status, (10, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return vis
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        return {
            "tracking_time": self.tracking_time,
            "blink_count": self.blink_count,
            "time_since_update": time.time() - self.last_update_time
        }
    
    def reset(self):
        """Reset the eye tracking module."""
        self.gaze_direction = (0, 0)
        self.head_pose = (0, 0, 0)
        self.is_blinking = False
        self.blink_start_time = None
        self.last_update_time = time.time()
        self.tracking_time = 0
        self.blink_count = 0
        self.logger.info("Eye tracking module reset")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create eye tracker
    eye_tracker = EyeTracker()
    
    # Test with webcam
    cap = cv2.VideoCapture(0)
    
    try:
        while True:
            # Read frame
            ret, frame = cap.read()
            if not ret:
                break
            
            # Track eyes
            tracking = eye_tracker.track(frame)
            
            # Get visualization
            vis = eye_tracker.get_tracking_visualization(frame)
            
            # Display frame
            cv2.imshow("Eye Tracking Test", vis)
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Print performance metrics
            metrics = eye_tracker.get_performance_metrics()
            print(f"Tracking time: {metrics['tracking_time']*1000:.1f}ms")
            print(f"Blink count: {metrics['blink_count']}")
            print("---")
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cap.release()
        cv2.destroyAllWindows() 