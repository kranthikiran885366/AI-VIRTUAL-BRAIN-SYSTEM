import cv2
import numpy as np
import mediapipe as mp
from pathlib import Path
import logging
from typing import Dict, Any, List, Tuple, Optional
import time
from dataclasses import dataclass
import threading
import queue
import yaml

# Import custom modules
from .eye_tracking import EyeTracker
from .gaze_detection import GazeDetector
from .blink_analysis import BlinkAnalyzer
from .pupil_dilation import PupilDilationAnalyzer
from .focus_control import FocusController
from .microsaccades import MicrosaccadeSimulator
from .capture_manager import CaptureManager
from .perception import Perception
from .attention import Attention
from .memory_buffer import MemoryBuffer
from .emotion import EmotionDetector

@dataclass
class EyeState:
    """Current state of the eyes."""
    pupil_position: Tuple[float, float]
    gaze_direction: Tuple[float, float]
    blink_count: int
    last_blink_time: float
    pupil_size: float
    focus_point: Tuple[float, float]
    attention_level: float
    is_focused: bool
    microsaccade_active: bool

@dataclass
class EyesAgentConfig:
    """Configuration for eyes agent."""
    camera: Dict[str, Any]
    perception: Dict[str, Any]
    attention: Dict[str, Any]
    focus: Dict[str, Any]
    memory: Dict[str, Any]
    emotion: Dict[str, Any]
    tracking: Dict[str, Any]
    automation: Dict[str, Any]
    agent_integration: Dict[str, Any]
    logging: Dict[str, Any]
    monitoring: Dict[str, Any]
    hardware: Dict[str, Any]
    features: Dict[str, Any]

class EyesAgent:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the eyes agent."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize modules
        self.capture_manager = CaptureManager(config_path)
        self.perception = Perception(config_path)
        self.attention = Attention(config_path)
        self.focus_control = FocusController(config_path)
        self.memory_buffer = MemoryBuffer(config_path)
        self.emotion_detector = EmotionDetector(config_path)
        self.eye_tracker = EyeTracker(config_path)
        
        # Agent state
        self.is_running = False
        self.processing_thread = None
        self.frame_queue = queue.Queue(maxsize=10)
        self.last_update_time = time.time()
        
        # Performance metrics
        self.processing_time = 0
        self.frame_count = 0
        self.start_time = time.time()
        
        # State management
        self.current_state = EyeState(
            pupil_position=(0.0, 0.0),
            gaze_direction=(0.0, 0.0),
            blink_count=0,
            last_blink_time=time.time(),
            pupil_size=1.0,
            focus_point=(0.0, 0.0),
            attention_level=0.0,
            is_focused=False,
            microsaccade_active=False
        )
        
        # Agent integration
        self.connected_agents = {
            "perception": None,
            "emotion": None,
            "attention": None,
            "memory": None,
            "task": None,
            "social": None
        }
    
    def _load_config(self, config_path: str) -> EyesAgentConfig:
        """Load eyes agent configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return EyesAgentConfig(**config_data)
    
    def connect_agent(self, agent_type: str, agent_instance: Any):
        """Connect to another agent in the system."""
        if agent_type in self.connected_agents:
            self.connected_agents[agent_type] = agent_instance
            self.logger.info(f"Connected to {agent_type} agent")
    
    def start(self):
        """Start the eyes agent."""
        if self.is_running:
            return
        
        # Start capture manager
        self.capture_manager.start()
        
        # Start processing thread
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop)
        self.processing_thread.start()
        
        self.logger.info("Eyes agent started")
    
    def stop(self):
        """Stop the eyes agent."""
        if not self.is_running:
            return
        
        # Stop capture manager
        self.capture_manager.stop()
        
        # Stop processing thread
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join()
        
        self.logger.info("Eyes agent stopped")
    
    def _processing_loop(self):
        """Main processing loop."""
        while self.is_running:
            try:
                # Get frame from capture manager
                frame = self.capture_manager.get_frame()
                if frame is None:
                    continue
                
                # Process frame
                start_time = time.time()
                
                # Detect objects and faces
                detections = self.perception.detect(frame)
                
                # Update attention
                attention = self.attention.update(frame, detections)
                
                # Update focus control
                if attention["current_focus"]:
                    focus = self.focus_control.update(attention["current_focus"])
                
                # Update memory buffer
                memory = self.memory_buffer.update(frame, detections, attention)
                
                # Detect emotions
                emotions = self.emotion_detector.detect(frame, detections["faces"])
                
                # Track eyes
                tracking = self.eye_tracker.track(frame)
                
                # Update metrics
                self.processing_time = time.time() - start_time
                self.frame_count += 1
                self.last_update_time = time.time()
                
                # Small delay to prevent CPU overload
                time.sleep(0.001)
            
            except Exception as e:
                self.logger.error(f"Error in processing loop: {str(e)}")
    
    def get_visualization(self) -> Optional[np.ndarray]:
        """Get visualization of current state."""
        # Get latest frame
        frame = self.capture_manager.get_frame()
        if frame is None:
            return None
        
        # Create visualization
        vis = frame.copy()
        
        # Add perception visualization
        for face in self.perception.get_performance_metrics()["faces"]:
            x1, y1, x2, y2 = face["bbox"]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        for obj in self.perception.get_performance_metrics()["objects"]:
            x1, y1, x2, y2 = obj["bbox"]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(vis, f"{obj['class']}: {obj['confidence']:.2f}",
                      (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                      (255, 0, 0), 2)
        
        # Add attention visualization
        attention_vis = self.attention.get_attention_visualization(frame)
        vis = cv2.addWeighted(vis, 0.7, attention_vis, 0.3, 0)
        
        # Add focus control visualization
        focus_vis = self.focus_control.get_focus_visualization(frame)
        vis = cv2.addWeighted(vis, 0.7, focus_vis, 0.3, 0)
        
        # Add emotion visualization
        emotion_vis = self.emotion_detector.get_emotion_visualization(
            frame, self.emotion_detector.current_emotions)
        vis = cv2.addWeighted(vis, 0.7, emotion_vis, 0.3, 0)
        
        # Add eye tracking visualization
        tracking_vis = self.eye_tracker.get_tracking_visualization(frame)
        vis = cv2.addWeighted(vis, 0.7, tracking_vis, 0.3, 0)
        
        # Add performance metrics
        metrics = self.get_performance_metrics()
        cv2.putText(vis, f"FPS: {metrics['fps']:.1f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(vis, f"Processing: {metrics['processing_time']*1000:.1f}ms",
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return vis
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        elapsed_time = time.time() - self.start_time
        fps = self.frame_count / elapsed_time if elapsed_time > 0 else 0
        
        return {
            "fps": fps,
            "processing_time": self.processing_time,
            "frame_count": self.frame_count,
            "time_since_update": time.time() - self.last_update_time,
            "perception_metrics": self.perception.get_performance_metrics(),
            "attention_metrics": self.attention.get_performance_metrics(),
            "focus_metrics": self.focus_control.get_performance_metrics(),
            "memory_metrics": self.memory_buffer.get_performance_metrics(),
            "emotion_metrics": self.emotion_detector.get_performance_metrics(),
            "tracking_metrics": self.eye_tracker.get_performance_metrics()
        }
    
    def reset(self):
        """Reset the eyes agent."""
        self.stop()
        
        # Reset modules
        self.capture_manager.reset()
        self.perception.reset()
        self.attention.reset()
        self.focus_control.reset()
        self.memory_buffer.reset()
        self.emotion_detector.reset()
        self.eye_tracker.reset()
        
        # Reset state
        self.is_running = False
        self.processing_thread = None
        self.last_update_time = time.time()
        self.processing_time = 0
        self.frame_count = 0
        self.start_time = time.time()
        
        self.logger.info("Eyes agent reset")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create eyes agent
    agent = EyesAgent()
    
    try:
        # Start agent
        agent.start()
        
        while True:
            # Get visualization
            vis = agent.get_visualization()
            if vis is not None:
                # Display frame
                cv2.imshow("Eyes Agent", vis)
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Print performance metrics
            metrics = agent.get_performance_metrics()
            print(f"FPS: {metrics['fps']:.1f}")
            print(f"Processing time: {metrics['processing_time']*1000:.1f}ms")
            print("---")
    
    except KeyboardInterrupt:
        pass
    
    finally:
        # Stop agent
        agent.stop()
        cv2.destroyAllWindows() 