import cv2
import numpy as np
from typing import Dict, Any, Tuple, List, Optional
import logging
from dataclasses import dataclass
import time
from collections import deque
import yaml

@dataclass
class FocusRegion:
    """Data class for focus region information."""
    bbox: Tuple[int, int, int, int]
    attention_level: float
    timestamp: float
    object_id: Optional[int] = None

@dataclass
class FocusConfig:
    """Configuration for focus control module."""
    saccade_speed: float
    pursuit_speed: float
    smooth_factor: float
    max_angle: float
    min_angle: float

class FocusController:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the focus control module."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Focus tracking
        self.current_focus: Optional[FocusRegion] = None
        self.focus_history: deque[FocusRegion] = deque(maxlen=self.config.get("history_size", 100))
        
        # Attention parameters
        self.attention_threshold = self.config.get("attention_threshold", 0.5)
        self.attention_decay = self.config.get("attention_decay", 0.95)
        self.focus_radius = self.config.get("focus_radius", 100)
        
        # Target tracking
        self.target_position: Optional[Tuple[float, float]] = None
        self.target_velocity: Tuple[float, float] = (0.0, 0.0)
        
        # Integration with other agents
        self.attention_agent = None
        self.perception_agent = None
        
        # Focus state
        self.current_position = (0, 0)  # (x, y) in degrees
        self.is_saccading = False
        self.saccade_start_time = None
        self.last_update_time = time.time()
        
        # Performance metrics
        self.update_time = 0
        self.saccade_count = 0
        self.pursuit_time = 0
    
    def _load_config(self, config_path: str) -> FocusConfig:
        """Load focus control configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return FocusConfig(**config_data.get("focus", {}))
    
    def update(self, target_position: Tuple[float, float]) -> Dict[str, Any]:
        """Update focus control based on target position."""
        start_time = time.time()
        
        # Convert target position from image coordinates to degrees
        target_x, target_y = self._image_to_degrees(target_position)
        
        # Clamp target position to valid range
        target_x = np.clip(target_x, self.config.min_angle, self.config.max_angle)
        target_y = np.clip(target_y, self.config.min_angle, self.config.max_angle)
        
        # Update target position
        self.target_position = (target_x, target_y)
        
        # Calculate distance to target
        distance = np.sqrt(
            (self.current_position[0] - target_x)**2 +
            (self.current_position[1] - target_y)**2
        )
        
        # Determine if we should saccade
        if distance > 5.0 and not self.is_saccading:  # 5 degrees threshold
            self.is_saccading = True
            self.saccade_start_time = time.time()
            self.saccade_count += 1
        
        # Update current position
        if self.is_saccading:
            # Perform saccade
            self._update_saccade()
        else:
            # Perform smooth pursuit
            self._update_pursuit()
        
        # Update metrics
        self.update_time = time.time() - start_time
        self.last_update_time = time.time()
        
        return {
            "current_position": self.current_position,
            "target_position": self.target_position,
            "is_saccading": self.is_saccading,
            "timestamp": time.time()
        }
    
    def _image_to_degrees(self, position: Tuple[int, int]) -> Tuple[float, float]:
        """Convert image coordinates to degrees."""
        # This is a simplified conversion - in reality, this would depend on
        # the camera's field of view and the distance to the target
        x, y = position
        h, w = 480, 640  # Assuming standard webcam resolution
        
        # Convert to degrees (assuming 60-degree horizontal FOV)
        x_deg = (x - w/2) * (60.0/w)
        y_deg = (y - h/2) * (60.0/h)
        
        return (x_deg, y_deg)
    
    def _degrees_to_image(self, position: Tuple[float, float]) -> Tuple[int, int]:
        """Convert degrees to image coordinates."""
        x_deg, y_deg = position
        h, w = 480, 640  # Assuming standard webcam resolution
        
        # Convert to image coordinates
        x = int(x_deg * (w/60.0) + w/2)
        y = int(y_deg * (h/60.0) + h/2)
        
        return (x, y)
    
    def _update_saccade(self):
        """Update position during saccade movement."""
        if not self.saccade_start_time:
            return
        
        # Calculate saccade progress
        elapsed_time = time.time() - self.saccade_start_time
        progress = min(1.0, elapsed_time / self.config.saccade_speed)
        
        # Use smooth acceleration/deceleration
        progress = self._smooth_step(progress)
        
        # Update position
        self.current_position = (
            self.current_position[0] + (self.target_position[0] - self.current_position[0]) * progress,
            self.current_position[1] + (self.target_position[1] - self.current_position[1]) * progress
        )
        
        # Check if saccade is complete
        if progress >= 1.0:
            self.is_saccading = False
            self.saccade_start_time = None
    
    def _update_pursuit(self):
        """Update position during smooth pursuit."""
        # Calculate pursuit movement
        dx = self.target_position[0] - self.current_position[0]
        dy = self.target_position[1] - self.current_position[1]
        
        # Apply smooth pursuit
        self.current_position = (
            self.current_position[0] + dx * self.config.smooth_factor,
            self.current_position[1] + dy * self.config.smooth_factor
        )
        
        # Update pursuit time
        self.pursuit_time += self.update_time
    
    def _smooth_step(self, x: float) -> float:
        """Apply smooth step function for acceleration/deceleration."""
        return x * x * (3 - 2 * x)
    
    def get_focus_visualization(self, frame: np.ndarray) -> np.ndarray:
        """Create visualization of focus control."""
        vis = frame.copy()
        
        # Convert current position to image coordinates
        current_pos = self._degrees_to_image(self.current_position)
        target_pos = self._degrees_to_image(self.target_position)
        
        # Draw current focus point
        cv2.circle(vis, current_pos, 5, (0, 255, 0), -1)
        
        # Draw target point
        cv2.circle(vis, target_pos, 5, (0, 0, 255), -1)
        
        # Draw movement line
        cv2.line(vis, current_pos, target_pos, (255, 0, 0), 2)
        
        # Add status text
        status = "Saccading" if self.is_saccading else "Pursuing"
        cv2.putText(vis, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                   (0, 255, 0), 2)
        
        return vis
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        return {
            "update_time": self.update_time,
            "saccade_count": self.saccade_count,
            "pursuit_time": self.pursuit_time,
            "time_since_update": time.time() - self.last_update_time
        }
    
    def reset(self):
        """Reset the focus control module."""
        self.current_position = (0, 0)
        self.target_position = (0, 0)
        self.is_saccading = False
        self.saccade_start_time = None
        self.last_update_time = time.time()
        self.update_time = 0
        self.saccade_count = 0
        self.pursuit_time = 0
        self.logger.info("Focus control module reset")

    def _find_focus_region(self, frame: np.ndarray,
                          gaze_point: Tuple[float, float]) -> Optional[FocusRegion]:
        """Find the region of focus based on gaze point."""
        # If target is set, focus on target
        if self.target_position:
            return self._create_focus_region(self.target_position)
        
        # Otherwise, find region around gaze point
        x, y = int(gaze_point[0]), int(gaze_point[1])
        
        # Create focus region
        bbox = (
            max(0, x - self.focus_radius),
            max(0, y - self.focus_radius),
            min(frame.shape[1], x + self.focus_radius),
            min(frame.shape[0], y + self.focus_radius)
        )
        
        return FocusRegion(
            bbox=bbox,
            attention_level=1.0,
            timestamp=time.time()
        )
    
    def _create_focus_region(self, point: Tuple[float, float]) -> FocusRegion:
        """Create a focus region around a point."""
        x, y = int(point[0]), int(point[1])
        
        bbox = (
            max(0, x - self.focus_radius),
            max(0, y - self.focus_radius),
            min(self.config.get("frame_width", 640), x + self.focus_radius),
            min(self.config.get("frame_height", 480), y + self.focus_radius)
        )
        
        return FocusRegion(
            bbox=bbox,
            attention_level=1.0,
            timestamp=time.time()
        )
    
    def _update_focus_history(self, focus_region: FocusRegion):
        """Update focus history with new focus region."""
        self.focus_history.append(focus_region)
        self.current_focus = focus_region
    
    def _calculate_attention_level(self, focus_region: Optional[FocusRegion]) -> float:
        """Calculate current attention level."""
        if not focus_region:
            return 0.0
        
        # Base attention level from focus region
        attention_level = focus_region.attention_level
        
        # Apply attention decay
        if self.current_focus:
            time_diff = time.time() - self.current_focus.timestamp
            attention_level *= self.attention_decay ** time_diff
        
        # Get additional attention from attention agent if available
        if self.attention_agent:
            attention_level *= self.attention_agent.get_attention_multiplier()
        
        return min(1.0, attention_level)
    
    def _update_target_position(self):
        """Update target position based on velocity."""
        if not self.target_position:
            return
        
        current_time = time.time()
        time_diff = current_time - self.last_update
        
        # Update position
        new_x = self.target_position[0] + self.target_velocity[0] * time_diff
        new_y = self.target_position[1] + self.target_velocity[1] * time_diff
        
        # Keep within bounds
        new_x = max(0, min(self.config.get("frame_width", 640), new_x))
        new_y = max(0, min(self.config.get("frame_height", 480), new_y))
        
        self.target_position = (new_x, new_y)
        self.last_update = current_time
    
    def set_target(self, target: Tuple[float, float], velocity: Tuple[float, float] = (0.0, 0.0)):
        """Set a focus target with optional velocity."""
        self.target_position = target
        self.target_velocity = velocity
        self.last_update = time.time()
    
    def clear_target(self):
        """Clear the current focus target."""
        self.target_position = None
        self.target_velocity = (0.0, 0.0)
    
    def get_focus_region(self) -> Tuple[int, int, int, int]:
        """Get the current focus region coordinates."""
        if not self.current_focus:
            return (0, 0, 0, 0)
        return self.current_focus.bbox
    
    def get_attention_level(self) -> float:
        """Get the current attention level."""
        if not self.current_focus:
            return 0.0
        return self._calculate_attention_level(self.current_focus)
    
    def connect_attention_agent(self, agent):
        """Connect to attention agent."""
        self.attention_agent = agent
    
    def connect_perception_agent(self, agent):
        """Connect to perception agent."""
        self.perception_agent = agent
    
    def get_focus_history(self) -> List[FocusRegion]:
        """Get the focus history."""
        return list(self.focus_history)
    
    def is_focused(self) -> bool:
        """Check if currently focused."""
        return self.get_attention_level() > self.attention_threshold
    
    def get_focus_duration(self) -> float:
        """Calculate current focus duration."""
        if not self.current_focus:
            return 0.0
        
        current_time = time.time()
        focus_start = current_time
        
        for region in reversed(self.focus_history):
            if region.attention_level < self.attention_threshold:
                break
            focus_start = region.timestamp
        
        return current_time - focus_start

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create focus control module
    focus_control = FocusController()
    
    # Test with webcam
    cap = cv2.VideoCapture(0)
    
    try:
        while True:
            # Read frame
            ret, frame = cap.read()
            if not ret:
                break
            
            # Get mouse position for testing
            mouse_pos = cv2.getWindowImageRect("Focus Control Test")
            if mouse_pos:
                x, y = mouse_pos[0], mouse_pos[1]
                
                # Update focus control
                focus_control.update((x, y))
            
            # Get visualization
            vis = focus_control.get_focus_visualization(frame)
            
            # Display frame
            cv2.imshow("Focus Control Test", vis)
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Print performance metrics
            metrics = focus_control.get_performance_metrics()
            print(f"Update time: {metrics['update_time']*1000:.1f}ms")
            print(f"Saccade count: {metrics['saccade_count']}")
            print(f"Pursuit time: {metrics['pursuit_time']:.1f}s")
            print("---")
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cap.release()
        cv2.destroyAllWindows()