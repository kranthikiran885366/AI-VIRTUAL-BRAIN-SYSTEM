import numpy as np
from typing import Dict, Any, Tuple, List
import logging
from dataclasses import dataclass
import time
from collections import deque

@dataclass
class Microsaccade:
    """Data class for microsaccade information."""
    direction: Tuple[float, float]
    amplitude: float
    duration: float
    timestamp: float

class MicrosaccadeSimulator:
    def __init__(self, config: Dict[str, Any]):
        """Initialize microsaccade simulator."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Microsaccade parameters
        self.enabled = config.get("enabled", True)
        self.frequency = config.get("frequency", 1.0)  # Hz
        self.max_amplitude = config.get("max_amplitude", 0.1)  # degrees
        self.min_amplitude = config.get("min_amplitude", 0.02)  # degrees
        self.duration = config.get("duration", 0.02)  # seconds
        
        # State tracking
        self.last_saccade_time = time.time()
        self.current_direction: Tuple[float, float] = (0.0, 0.0)
        self.current_amplitude: float = 0.0
        self.is_active = False
        
        # History
        self.saccade_history: deque[Microsaccade] = deque(maxlen=config.get("history_size", 100))
        
        # Random number generator
        self.rng = np.random.RandomState(config.get("random_seed", 42))
    
    def update(self, eye_state: Any):
        """Update microsaccade simulation based on current eye state."""
        if not self.enabled:
            return
        
        current_time = time.time()
        time_since_last = current_time - self.last_saccade_time
        
        # Check if it's time for a new microsaccade
        if time_since_last >= 1.0 / self.frequency:
            self._generate_microsaccade()
            self.last_saccade_time = current_time
        
        # Update active microsaccade
        if self.is_active:
            self._update_active_saccade(current_time)
    
    def _generate_microsaccade(self):
        """Generate a new microsaccade."""
        # Random direction
        angle = self.rng.uniform(0, 2 * np.pi)
        self.current_direction = (np.cos(angle), np.sin(angle))
        
        # Random amplitude
        self.current_amplitude = self.rng.uniform(
            self.min_amplitude,
            self.max_amplitude
        )
        
        # Create saccade record
        saccade = Microsaccade(
            direction=self.current_direction,
            amplitude=self.current_amplitude,
            duration=self.duration,
            timestamp=time.time()
        )
        
        self.saccade_history.append(saccade)
        self.is_active = True
    
    def _update_active_saccade(self, current_time: float):
        """Update the currently active microsaccade."""
        if not self.saccade_history:
            return
        
        last_saccade = self.saccade_history[-1]
        time_since_start = current_time - last_saccade.timestamp
        
        if time_since_start >= self.duration:
            self.is_active = False
            self.current_direction = (0.0, 0.0)
            self.current_amplitude = 0.0
    
    def get_current_movement(self) -> Tuple[float, float]:
        """Get current microsaccade movement."""
        if not self.is_active:
            return (0.0, 0.0)
        
        # Calculate movement based on current direction and amplitude
        return (
            self.current_direction[0] * self.current_amplitude,
            self.current_direction[1] * self.current_amplitude
        )
    
    def enable(self, enable: bool):
        """Enable or disable microsaccade simulation."""
        self.enabled = enable
        if not enable:
            self.is_active = False
            self.current_direction = (0.0, 0.0)
            self.current_amplitude = 0.0
    
    def set_frequency(self, frequency: float):
        """Set microsaccade frequency."""
        self.frequency = max(0.1, min(5.0, frequency))
    
    def set_amplitude_range(self, min_amplitude: float, max_amplitude: float):
        """Set microsaccade amplitude range."""
        self.min_amplitude = max(0.01, min_amplitude)
        self.max_amplitude = min(0.5, max_amplitude)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get microsaccade statistics."""
        if not self.saccade_history:
            return {
                "frequency": self.frequency,
                "average_amplitude": 0.0,
                "is_active": self.is_active,
                "total_saccades": 0
            }
        
        amplitudes = [s.accade.amplitude for s.accade in self.saccade_history]
        
        return {
            "frequency": self.frequency,
            "average_amplitude": np.mean(amplitudes),
            "is_active": self.is_active,
            "total_saccades": len(self.saccade_history)
        }
    
    def get_history(self) -> List[Microsaccade]:
        """Get microsaccade history."""
        return list(self.saccade_history)
    
    def reset(self):
        """Reset microsaccade simulation."""
        self.is_active = False
        self.current_direction = (0.0, 0.0)
        self.current_amplitude = 0.0
        self.last_saccade_time = time.time()
        self.saccade_history.clear() 