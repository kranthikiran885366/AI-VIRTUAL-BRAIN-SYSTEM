import cv2
import numpy as np
import time
import threading
import queue
import logging
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
import yaml

@dataclass
class CameraConfig:
    """Configuration for camera capture."""
    device_id: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    buffer_size: int = 10

class CaptureManager:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the capture manager."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Camera state
        self.camera = None
        self.is_running = False
        self.frame_buffer = queue.Queue(maxsize=self.config.buffer_size)
        self.last_frame = None
        self.last_frame_time = 0
        
        # Threading
        self.capture_thread = None
        self.processing_thread = None
        
        # Performance metrics
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
    
    def _load_config(self, config_path: str) -> CameraConfig:
        """Load camera configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return CameraConfig(**config_data.get("camera", {}))
    
    def start(self):
        """Start the camera capture."""
        if self.is_running:
            return
        
        # Initialize camera
        self.camera = cv2.VideoCapture(self.config.device_id)
        if not self.camera.isOpened():
            raise RuntimeError(f"Failed to open camera {self.config.device_id}")
        
        # Set camera properties
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self.camera.set(cv2.CAP_PROP_FPS, self.config.fps)
        
        # Start capture thread
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.start()
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._processing_loop)
        self.processing_thread.start()
        
        self.logger.info("Camera capture started")
    
    def stop(self):
        """Stop the camera capture."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.capture_thread:
            self.capture_thread.join()
        
        if self.processing_thread:
            self.processing_thread.join()
        
        if self.camera:
            self.camera.release()
        
        self.logger.info("Camera capture stopped")
    
    def _capture_loop(self):
        """Main capture loop."""
        while self.is_running:
            try:
                # Read frame from camera
                ret, frame = self.camera.read()
                if not ret:
                    self.logger.warning("Failed to read frame from camera")
                    continue
                
                # Add frame to buffer
                if not self.frame_buffer.full():
                    self.frame_buffer.put(frame)
                
                # Update performance metrics
                self.frame_count += 1
                current_time = time.time()
                elapsed_time = current_time - self.start_time
                if elapsed_time >= 1.0:
                    self.fps = self.frame_count / elapsed_time
                    self.frame_count = 0
                    self.start_time = current_time
                
                # Small delay to maintain target FPS
                time.sleep(1.0 / self.config.fps)
            
            except Exception as e:
                self.logger.error(f"Error in capture loop: {str(e)}")
    
    def _processing_loop(self):
        """Process frames from buffer."""
        while self.is_running:
            try:
                # Get frame from buffer
                if not self.frame_buffer.empty():
                    frame = self.frame_buffer.get()
                    
                    # Process frame
                    processed_frame = self._process_frame(frame)
                    
                    # Update last frame
                    self.last_frame = processed_frame
                    self.last_frame_time = time.time()
                
                # Small delay to prevent CPU overload
                time.sleep(0.001)
            
            except Exception as e:
                self.logger.error(f"Error in processing loop: {str(e)}")
    
    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process a single frame."""
        # Convert to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Apply basic preprocessing
        frame_rgb = cv2.GaussianBlur(frame_rgb, (5, 5), 0)
        
        return frame_rgb
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame."""
        return self.last_frame
    
    def get_frame_with_timestamp(self) -> Tuple[Optional[np.ndarray], float]:
        """Get the latest frame with its timestamp."""
        return self.last_frame, self.last_frame_time
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get camera performance metrics."""
        return {
            "fps": self.fps,
            "buffer_size": self.frame_buffer.qsize(),
            "is_running": self.is_running,
            "frame_count": self.frame_count,
            "elapsed_time": time.time() - self.start_time
        }
    
    def reset(self):
        """Reset the capture manager."""
        self.stop()
        self.frame_buffer.queue.clear()
        self.last_frame = None
        self.last_frame_time = 0
        self.frame_count = 0
        self.start_time = time.time()
        self.logger.info("Capture manager reset")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create and start capture manager
    manager = CaptureManager()
    manager.start()
    
    try:
        # Keep main thread alive
        while True:
            frame = manager.get_frame()
            if frame is not None:
                # Display frame
                cv2.imshow("Camera Feed", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Print performance metrics
            metrics = manager.get_performance_metrics()
            print(f"FPS: {metrics['fps']:.1f}")
            
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        pass
    
    finally:
        manager.stop()
        cv2.destroyAllWindows() 