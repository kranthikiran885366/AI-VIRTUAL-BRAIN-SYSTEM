import cv2
import numpy as np
from typing import Dict, Any, Tuple, List
import logging
from dataclasses import dataclass
import time
from collections import deque

@dataclass
class PupilState:
    """Data class for pupil state information."""
    size: float
    timestamp: float
    emotion: str
    cognitive_load: float

class PupilDilationAnalyzer:
    def __init__(self, config: Dict[str, Any]):
        """Initialize pupil dilation analyzer."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Pupil tracking
        self.base_size = config.get("base_pupil_size", 1.0)
        self.current_size = self.base_size
        self.pupil_history: deque[PupilState] = deque(maxlen=config.get("history_size", 100))
        
        # Emotion simulation
        self.emotion_state = "neutral"
        self.emotion_intensity = 0.0
        self.emotion_effects = {
            "surprise": 1.5,  # Dilate
            "fear": 1.3,      # Dilate
            "anger": 0.8,     # Constrict
            "disgust": 0.9,   # Slight constriction
            "happiness": 1.1,  # Slight dilation
            "sadness": 0.95,  # Slight constriction
            "calm": 1.0,      # Neutral
            "stress": 1.2,    # Dilate
            "focus": 1.15,    # Dilate
            "fatigue": 0.85   # Constrict
        }
        
        # Cognitive load simulation
        self.cognitive_load = 0.0
        self.max_cognitive_load = config.get("max_cognitive_load", 1.0)
        
        # Time-based effects
        self.last_update = time.time()
        self.recovery_rate = config.get("recovery_rate", 0.1)  # Size change per second
    
    def analyze(self, frame: np.ndarray) -> float:
        """Analyze frame for pupil size and return current size."""
        # Detect pupil size from frame
        detected_size = self._detect_pupil_size(frame)
        
        # Update current size based on detection and simulation
        self._update_pupil_size(detected_size)
        
        # Record state
        self._record_state()
        
        return self.current_size
    
    def _detect_pupil_size(self, frame: np.ndarray) -> float:
        """Detect pupil size from frame."""
        # Convert frame to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold
        _, threshold = cv2.threshold(gray, 70, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return self.current_size
        
        # Find largest contour (assumed to be pupil)
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Calculate pupil size
        area = cv2.contourArea(largest_contour)
        size = np.sqrt(area / np.pi)  # Approximate radius
        
        # Normalize size
        normalized_size = size / self.config.get("max_pupil_size", 100.0)
        
        return normalized_size
    
    def _update_pupil_size(self, detected_size: float):
        """Update pupil size based on detection and simulation."""
        current_time = time.time()
        time_diff = current_time - self.last_update
        
        # Calculate target size based on emotion and cognitive load
        emotion_factor = self.emotion_effects.get(self.emotion_state, 1.0)
        cognitive_factor = 1.0 + (self.cognitive_load * 0.3)  # Up to 30% increase
        
        target_size = self.base_size * emotion_factor * cognitive_factor
        
        # Apply recovery rate
        if self.current_size > target_size:
            self.current_size = max(target_size, self.current_size - self.recovery_rate * time_diff)
        elif self.current_size < target_size:
            self.current_size = min(target_size, self.current_size + self.recovery_rate * time_diff)
        
        # Blend with detected size
        if detected_size > 0:
            self.current_size = 0.7 * self.current_size + 0.3 * detected_size
        
        # Ensure size is within bounds
        self.current_size = max(0.5, min(2.0, self.current_size))
        
        self.last_update = current_time
    
    def _record_state(self):
        """Record current pupil state."""
        state = PupilState(
            size=self.current_size,
            timestamp=time.time(),
            emotion=self.emotion_state,
            cognitive_load=self.cognitive_load
        )
        
        self.pupil_history.append(state)
    
    def simulate_emotion(self, emotion: str, intensity: float):
        """Simulate emotional response in pupil size."""
        self.emotion_state = emotion
        self.emotion_intensity = intensity
        
        # Adjust emotion effects based on intensity
        for emotion, effect in self.emotion_effects.items():
            if emotion == self.emotion_state:
                # Amplify effect based on intensity
                self.emotion_effects[emotion] = 1.0 + (effect - 1.0) * intensity
    
    def set_cognitive_load(self, load: float):
        """Set cognitive load level (0.0 to 1.0)."""
        self.cognitive_load = max(0.0, min(self.max_cognitive_load, load))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current pupil statistics."""
        if not self.pupil_history:
            return {
                "current_size": self.current_size,
                "emotion_state": self.emotion_state,
                "cognitive_load": self.cognitive_load,
                "average_size": self.base_size,
                "size_trend": "stable"
            }
        
        # Calculate size trend
        recent_sizes = [state.size for state in list(self.pupil_history)[-10:]]
        size_trend = "increasing" if recent_sizes[-1] > recent_sizes[0] else "decreasing"
        
        return {
            "current_size": self.current_size,
            "emotion_state": self.emotion_state,
            "cognitive_load": self.cognitive_load,
            "average_size": np.mean(recent_sizes),
            "size_trend": size_trend
        }
    
    def get_size_history(self) -> List[Tuple[float, float]]:
        """Get pupil size history as (timestamp, size) pairs."""
        return [(state.timestamp, state.size) for state in self.pupil_history]
    
    def reset(self):
        """Reset pupil state to baseline."""
        self.current_size = self.base_size
        self.emotion_state = "neutral"
        self.emotion_intensity = 0.0
        self.cognitive_load = 0.0
        self.pupil_history.clear()
        
        # Reset emotion effects to default
        self.emotion_effects = {
            "surprise": 1.5,
            "fear": 1.3,
            "anger": 0.8,
            "disgust": 0.9,
            "happiness": 1.1,
            "sadness": 0.95,
            "calm": 1.0,
            "stress": 1.2,
            "focus": 1.15,
            "fatigue": 0.85
        } 