import cv2
import numpy as np
from typing import Dict, Any, List, Tuple
import logging
from dataclasses import dataclass
import time
from collections import deque

@dataclass
class BlinkEvent:
    """Data class for blink event information."""
    timestamp: float
    duration: float
    confidence: float
    eye_state: str  # "open", "closed", "transitioning"

class BlinkAnalyzer:
    def __init__(self, config: Dict[str, Any]):
        """Initialize blink analyzer."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Blink detection
        self.eye_state = "open"
        self.last_state_change = time.time()
        self.blink_history: deque[BlinkEvent] = deque(maxlen=config.get("history_size", 100))
        
        # Blink statistics
        self.total_blinks = 0
        self.blink_durations: List[float] = []
        self.last_blink_time = time.time()
        
        # Fatigue detection
        self.fatigue_threshold = config.get("fatigue_threshold", 20)  # blinks per minute
        self.fatigue_window = config.get("fatigue_window", 60)  # seconds
        
        # Emotion simulation
        self.emotion_state = "neutral"
        self.emotion_intensity = 0.0
    
    def analyze(self, frame: np.ndarray) -> Dict[str, Any]:
        """Analyze frame for blink detection."""
        # Detect eye state
        eye_state = self._detect_eye_state(frame)
        
        # Update state
        if eye_state != self.eye_state:
            self._handle_state_change(eye_state)
        
        # Calculate blink statistics
        blink_rate = self._calculate_blink_rate()
        fatigue_level = self._calculate_fatigue_level()
        
        return {
            "blink_detected": self._is_blink_detected(),
            "current_state": self.eye_state,
            "blink_rate": blink_rate,
            "fatigue_level": fatigue_level,
            "last_blink_duration": self._get_last_blink_duration(),
            "emotion_state": self.emotion_state
        }
    
    def _detect_eye_state(self, frame: np.ndarray) -> str:
        """Detect current eye state from frame."""
        # Convert frame to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply eye region detection
        eye_regions = self._detect_eye_regions(gray)
        
        if not eye_regions:
            return "unknown"
        
        # Analyze each eye region
        eye_states = []
        for region in eye_regions:
            state = self._analyze_eye_region(region)
            eye_states.append(state)
        
        # Combine eye states
        if "closed" in eye_states:
            return "closed"
        elif "transitioning" in eye_states:
            return "transitioning"
        else:
            return "open"
    
    def _detect_eye_regions(self, gray_frame: np.ndarray) -> List[np.ndarray]:
        """Detect eye regions in the frame."""
        # Load eye cascade classifier
        eye_cascade = cv2.CascadeClassifier(self.config["eye_cascade_path"])
        
        # Detect eyes
        eyes = eye_cascade.detectMultiScale(
            gray_frame,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        # Extract eye regions
        eye_regions = []
        for (x, y, w, h) in eyes:
            eye_region = gray_frame[y:y+h, x:x+w]
            eye_regions.append(eye_region)
        
        return eye_regions
    
    def _analyze_eye_region(self, eye_region: np.ndarray) -> str:
        """Analyze a single eye region to determine its state."""
        # Apply threshold
        _, threshold = cv2.threshold(eye_region, 70, 255, cv2.THRESH_BINARY)
        
        # Calculate white pixel ratio
        white_ratio = np.sum(threshold == 255) / threshold.size
        
        # Determine state based on white pixel ratio
        if white_ratio < self.config.get("closed_threshold", 0.2):
            return "closed"
        elif white_ratio < self.config.get("open_threshold", 0.5):
            return "transitioning"
        else:
            return "open"
    
    def _handle_state_change(self, new_state: str):
        """Handle eye state change."""
        current_time = time.time()
        
        if new_state == "closed" and self.eye_state == "open":
            # Start of blink
            self.last_state_change = current_time
        elif new_state == "open" and self.eye_state == "closed":
            # End of blink
            blink_duration = current_time - self.last_state_change
            
            # Create blink event
            blink_event = BlinkEvent(
                timestamp=current_time,
                duration=blink_duration,
                confidence=1.0,  # Could be improved with confidence estimation
                eye_state=new_state
            )
            
            # Update history
            self.blink_history.append(blink_event)
            self.blink_durations.append(blink_duration)
            self.total_blinks += 1
            self.last_blink_time = current_time
        
        self.eye_state = new_state
    
    def _is_blink_detected(self) -> bool:
        """Check if a blink was just detected."""
        if not self.blink_history:
            return False
        
        last_event = self.blink_history[-1]
        return (time.time() - last_event.timestamp < 0.5 and
                last_event.eye_state == "open" and
                last_event.duration < self.config.get("max_blink_duration", 0.4))
    
    def _calculate_blink_rate(self) -> float:
        """Calculate current blink rate (blinks per minute)."""
        current_time = time.time()
        window_start = current_time - self.fatigue_window
        
        # Count blinks in window
        blinks_in_window = sum(1 for event in self.blink_history
                             if event.timestamp >= window_start)
        
        return (blinks_in_window / self.fatigue_window) * 60
    
    def _calculate_fatigue_level(self) -> float:
        """Calculate current fatigue level (0.0 to 1.0)."""
        blink_rate = self._calculate_blink_rate()
        
        if blink_rate < self.fatigue_threshold:
            return 0.0
        
        # Normalize to [0, 1] range
        max_rate = self.fatigue_threshold * 2
        return min(1.0, (blink_rate - self.fatigue_threshold) / (max_rate - self.fatigue_threshold))
    
    def _get_last_blink_duration(self) -> float:
        """Get the duration of the last blink."""
        if not self.blink_history:
            return 0.0
        return self.blink_history[-1].duration
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current blink statistics."""
        return {
            "total_blinks": self.total_blinks,
            "blink_rate": self._calculate_blink_rate(),
            "average_duration": np.mean(self.blink_durations) if self.blink_durations else 0.0,
            "fatigue_level": self._calculate_fatigue_level(),
            "last_blink_time": self.last_blink_time,
            "emotion_state": self.emotion_state
        }
    
    def simulate_emotion(self, emotion: str, intensity: float):
        """Simulate emotional response in blink behavior."""
        self.emotion_state = emotion
        self.emotion_intensity = intensity
        
        # Adjust blink parameters based on emotion
        if emotion == "stress":
            self.fatigue_threshold *= (1 + intensity)
        elif emotion == "calm":
            self.fatigue_threshold *= (1 - intensity)
        elif emotion == "surprise":
            # Simulate rapid blinking
            self._simulate_rapid_blinks(intensity)
    
    def _simulate_rapid_blinks(self, intensity: float):
        """Simulate rapid blinking for surprise emotion."""
        current_time = time.time()
        num_blinks = int(3 + intensity * 2)  # 3-5 blinks
        
        for i in range(num_blinks):
            # Create simulated blink event
            blink_event = BlinkEvent(
                timestamp=current_time + i * 0.1,
                duration=0.1,
                confidence=1.0,
                eye_state="open"
            )
            
            self.blink_history.append(blink_event)
            self.blink_durations.append(0.1)
            self.total_blinks += 1
        
        self.last_blink_time = current_time + (num_blinks - 1) * 0.1 