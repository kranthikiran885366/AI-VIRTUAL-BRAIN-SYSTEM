import cv2
import numpy as np
import time
import threading
import queue
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import yaml

from .capture_manager import CaptureManager
from .perception import Perception
from .vision_attention import VisionAttention
from .focus_control import FocusControl
from .eye_memory_buffer import EyeMemoryBuffer
from .emotion_face import EmotionFace
from .eye_tracking import EyeTracking

@dataclass
class AutomationConfig:
    """Configuration for automation controller."""
    blink_interval: float = 4.0  # seconds
    look_around_interval: float = 2.0  # seconds
    memory_update_interval: float = 0.5  # seconds
    alert_threshold: float = 0.8  # confidence threshold for alerts
    max_focus_duration: float = 5.0  # seconds
    min_focus_duration: float = 0.5  # seconds
    crowd_threshold: int = 3  # number of people to trigger social mode

class AutomationController:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the automation controller."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.capture = CaptureManager()
        self.perception = Perception()
        self.attention = VisionAttention()
        self.focus = FocusControl()
        self.memory = EyeMemoryBuffer()
        self.emotion = EmotionFace()
        self.tracking = EyeTracking()
        
        # State management
        self.is_running = False
        self.current_focus = None
        self.last_blink_time = time.time()
        self.last_look_around_time = time.time()
        self.last_memory_update = time.time()
        self.focus_start_time = None
        
        # Threading
        self.processing_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.processing_thread = None
        
        # Connected agents
        self.connected_agents = {
            "memory": None,
            "emotion": None,
            "attention": None,
            "decision": None,
            "speech": None,
            "motor": None
        }
    
    def _load_config(self, config_path: str) -> AutomationConfig:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return AutomationConfig(**config_data.get("automation", {}))
    
    def connect_agent(self, agent_type: str, agent_instance: Any):
        """Connect to another agent in the system."""
        if agent_type in self.connected_agents:
            self.connected_agents[agent_type] = agent_instance
            self.logger.info(f"Connected to {agent_type} agent")
    
    def start(self):
        """Start the automation controller."""
        if self.is_running:
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop)
        self.processing_thread.start()
        self.logger.info("Automation controller started")
    
    def stop(self):
        """Stop the automation controller."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join()
        self.logger.info("Automation controller stopped")
    
    def _processing_loop(self):
        """Main processing loop."""
        while self.is_running:
            try:
                # Get frame from camera
                frame = self.capture.get_frame()
                if frame is None:
                    continue
                
                # Detect objects and faces
                detections = self.perception.detect(frame)
                
                # Update eye tracking
                gaze_data = self.tracking.update(frame)
                
                # Check for blinks
                self._check_blink()
                
                # Look around periodically
                self._check_look_around()
                
                # Update focus based on attention
                self._update_focus(detections, gaze_data)
                
                # Analyze emotions
                emotions = self.emotion.analyze(frame)
                
                # Update memory
                self._update_memory(detections, emotions, gaze_data)
                
                # Check for alerts
                self._check_alerts(detections, emotions)
                
                # Notify connected agents
                self._notify_agents(detections, emotions, gaze_data)
                
                # Small delay to prevent CPU overload
                time.sleep(0.01)
            
            except Exception as e:
                self.logger.error(f"Error in processing loop: {str(e)}")
    
    def _check_blink(self):
        """Check if it's time to blink."""
        current_time = time.time()
        if current_time - self.last_blink_time >= self.config.blink_interval:
            self.focus.blink()
            self.last_blink_time = current_time
    
    def _check_look_around(self):
        """Periodically look around the scene."""
        current_time = time.time()
        if current_time - self.last_look_around_time >= self.config.look_around_interval:
            self.focus.look_around()
            self.last_look_around_time = current_time
    
    def _update_focus(self, detections: Dict[str, Any], gaze_data: Dict[str, Any]):
        """Update focus based on attention and detections."""
        # Get attention target
        focus_target = self.attention.choose_focus(detections, gaze_data)
        
        # Check if we need to change focus
        if focus_target != self.current_focus:
            # Check if we've focused long enough
            if self.focus_start_time is not None:
                focus_duration = time.time() - self.focus_start_time
                if focus_duration < self.config.min_focus_duration:
                    return
            
            # Update focus
            self.focus.adjust_focus(focus_target)
            self.current_focus = focus_target
            self.focus_start_time = time.time()
        
        # Check if we've focused too long
        elif self.focus_start_time is not None:
            focus_duration = time.time() - self.focus_start_time
            if focus_duration > self.config.max_focus_duration:
                self.focus.look_around()
                self.current_focus = None
                self.focus_start_time = None
    
    def _update_memory(self, detections: Dict[str, Any],
                      emotions: Dict[str, Any],
                      gaze_data: Dict[str, Any]):
        """Update visual memory buffer."""
        current_time = time.time()
        if current_time - self.last_memory_update >= self.config.memory_update_interval:
            # Store current scene in memory
            self.memory.store({
                "timestamp": current_time,
                "detections": detections,
                "emotions": emotions,
                "gaze": gaze_data,
                "focus": self.current_focus
            })
            
            # Notify memory agent if connected
            if self.connected_agents["memory"]:
                self.connected_agents["memory"].update_visual_memory(
                    detections, emotions, gaze_data
                )
            
            self.last_memory_update = current_time
    
    def _check_alerts(self, detections: Dict[str, Any], emotions: Dict[str, Any]):
        """Check for unusual stimuli and trigger alerts."""
        # Check for crowd
        if len(detections.get("faces", [])) >= self.config.crowd_threshold:
            self._trigger_alert("crowd_detected", {
                "count": len(detections["faces"]),
                "confidence": 1.0
            })
        
        # Check for unusual emotions
        for emotion, intensity in emotions.items():
            if intensity > self.config.alert_threshold:
                self._trigger_alert("strong_emotion", {
                    "emotion": emotion,
                    "intensity": intensity
                })
        
        # Check for unusual objects
        for obj in detections.get("objects", []):
            if obj.get("confidence", 0) > self.config.alert_threshold:
                self._trigger_alert("unusual_object", {
                    "object": obj["class"],
                    "confidence": obj["confidence"]
                })
    
    def _trigger_alert(self, alert_type: str, data: Dict[str, Any]):
        """Trigger an alert to connected agents."""
        alert = {
            "type": alert_type,
            "timestamp": time.time(),
            "data": data
        }
        
        # Notify decision agent
        if self.connected_agents["decision"]:
            self.connected_agents["decision"].handle_alert(alert)
        
        # Notify emotion agent
        if self.connected_agents["emotion"]:
            self.connected_agents["emotion"].handle_alert(alert)
        
        self.logger.info(f"Alert triggered: {alert_type}")
    
    def _notify_agents(self, detections: Dict[str, Any],
                      emotions: Dict[str, Any],
                      gaze_data: Dict[str, Any]):
        """Notify all connected agents of current state."""
        state = {
            "timestamp": time.time(),
            "detections": detections,
            "emotions": emotions,
            "gaze": gaze_data,
            "focus": self.current_focus
        }
        
        # Notify attention agent
        if self.connected_agents["attention"]:
            self.connected_agents["attention"].update_visual_state(state)
        
        # Notify speech agent
        if self.connected_agents["speech"]:
            self.connected_agents["speech"].describe_scene(state)
        
        # Notify motor agent
        if self.connected_agents["motor"]:
            self.connected_agents["motor"].adjust_position(gaze_data)
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state of the automation controller."""
        return {
            "is_running": self.is_running,
            "current_focus": self.current_focus,
            "last_blink_time": self.last_blink_time,
            "last_look_around_time": self.last_look_around_time,
            "last_memory_update": self.last_memory_update,
            "focus_start_time": self.focus_start_time
        }
    
    def reset(self):
        """Reset the automation controller state."""
        self.stop()
        self.current_focus = None
        self.last_blink_time = time.time()
        self.last_look_around_time = time.time()
        self.last_memory_update = time.time()
        self.focus_start_time = None
        self.memory.clear()
        self.logger.info("Automation controller reset")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create and start automation controller
    controller = AutomationController()
    controller.start()
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        controller.stop() 