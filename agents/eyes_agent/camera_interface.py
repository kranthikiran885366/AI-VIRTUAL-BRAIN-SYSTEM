import cv2
import time
import logging
from typing import Optional, Tuple, Dict, Any
import numpy as np
import asyncio
from datetime import datetime
import json
from pathlib import Path

class CameraInterface:
    def __init__(self, config: Dict[str, Any]):
        """Initialize camera interface with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Camera settings
        self.camera_id = config.get("camera_id", 0)
        self.resolution = config.get("resolution", (640, 480))
        self.fps = config.get("fps", 30)
        self.rotation = config.get("rotation", 0)
        
        # Camera state
        self.camera = None
        self.is_running = False
        self.current_frame = None
        self.frame_count = 0
        self.start_time = None
        
        # Metrics
        self.metrics = {
            "total_frames_captured": 0,
            "average_fps": 0,
            "start_time": None,
            "errors": 0
        }
        
        self.logger.info("Camera interface initialized")

    async def start(self):
        """Start the camera capture."""
        try:
            self.camera = cv2.VideoCapture(self.camera_id)
            
            # Set camera properties
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            if not self.camera.isOpened():
                raise RuntimeError("Failed to open camera")
            
            self.is_running = True
            self.start_time = datetime.utcnow()
            self.metrics["start_time"] = self.start_time.isoformat()
            
            self.logger.info("Camera started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start camera: {str(e)}")
            raise

    async def stop(self):
        """Stop the camera capture."""
        try:
            self.is_running = False
            if self.camera is not None:
                self.camera.release()
            self.camera = None
            
            # Save final metrics
            self._save_metrics()
            
            self.logger.info("Camera stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping camera: {str(e)}")
            raise

    async def get_frame(self) -> Optional[np.ndarray]:
        """Get the current frame from the camera."""
        if not self.is_running or self.camera is None:
            return None
            
        try:
            ret, frame = self.camera.read()
            if not ret:
                self.metrics["errors"] += 1
                self.logger.warning("Failed to capture frame")
                return None
            
            # Rotate frame if needed
            if self.rotation != 0:
                frame = self._rotate_frame(frame)
            
            # Update metrics
            self.frame_count += 1
            self.metrics["total_frames_captured"] += 1
            self._update_fps()
            
            self.current_frame = frame
            return frame
            
        except Exception as e:
            self.metrics["errors"] += 1
            self.logger.error(f"Error capturing frame: {str(e)}")
            return None

    def _rotate_frame(self, frame: np.ndarray) -> np.ndarray:
        """Rotate frame by specified angle."""
        if self.rotation == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotation == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return frame

    def _update_fps(self):
        """Update FPS metrics."""
        if self.start_time is None:
            return
            
        elapsed_time = (datetime.utcnow() - self.start_time).total_seconds()
        if elapsed_time > 0:
            self.metrics["average_fps"] = self.frame_count / elapsed_time

    def _save_metrics(self):
        """Save camera metrics to file."""
        try:
            metrics_file = Path(self.config.get("metrics_file", "data/camera_metrics.json"))
            metrics_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(metrics_file, "w") as f:
                json.dump(self.metrics, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save camera metrics: {str(e)}")

    async def get_status(self) -> Dict[str, Any]:
        """Get current status of the camera."""
        return {
            "status": "running" if self.is_running else "stopped",
            "camera_id": self.camera_id,
            "resolution": self.resolution,
            "fps": self.fps,
            "rotation": self.rotation,
            "metrics": self.metrics
        }

    def update_config(self, new_config: Dict[str, Any]):
        """Update camera configuration."""
        try:
            # Update camera properties if changed
            if "camera_id" in new_config and new_config["camera_id"] != self.camera_id:
                self.camera_id = new_config["camera_id"]
                if self.is_running:
                    self.stop()
                    self.start()
            
            if "resolution" in new_config and new_config["resolution"] != self.resolution:
                self.resolution = new_config["resolution"]
                if self.camera is not None:
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            
            if "fps" in new_config and new_config["fps"] != self.fps:
                self.fps = new_config["fps"]
                if self.camera is not None:
                    self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            if "rotation" in new_config:
                self.rotation = new_config["rotation"]
            
            # Update configuration
            self.config.update(new_config)
            
            self.logger.info("Camera configuration updated successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to update camera configuration: {str(e)}")
            raise

    def show_frame(self, frame: np.ndarray):
        """Display the frame in a window."""
        if frame is None:
            return

        cv2.imshow("Eyes Agent", frame)

    def wait_key(self, delay: int = 1) -> int:
        """Wait for a key press."""
        return cv2.waitKey(delay)

    def save_frame(self, frame: np.ndarray, filename: str):
        """Save the current frame to a file."""
        if frame is None:
            return

        try:
            cv2.imwrite(filename, frame)
            self.logger.info(f"Frame saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save frame: {e}")

    def start_recording(self, filename: str = None):
        """Start recording video."""
        if not self.is_running or self.recording:
            return

        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.mp4"

        try:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(
                filename,
                fourcc,
                self.fps,
                (self.width, self.height)
            )
            self.recording = True
            self.logger.info(f"Started recording to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to start recording: {e}")

    def stop_recording(self):
        """Stop recording video."""
        if not self.recording:
            return

        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

        self.recording = False
        self.logger.info("Recording stopped")

    def write_frame(self, frame: np.ndarray):
        """Write frame to video file if recording."""
        if not self.recording or self.video_writer is None:
            return

        self.video_writer.write(frame)

    def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information and status."""
        return {
            "device_id": self.device_id,
            "resolution": f"{self.width}x{self.height}",
            "fps": self.fps,
            "is_running": self.is_running,
            "is_recording": self.recording,
            "last_frame_time": self.last_frame_time
        }

    def set_camera_properties(self, width: int = None, height: int = None, fps: int = None):
        """Update camera properties."""
        if not self.is_running:
            return

        if width is not None:
            self.width = width
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)

        if height is not None:
            self.height = height
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if fps is not None:
            self.fps = fps
            self.cap.set(cv2.CAP_PROP_FPS, fps)

        self.logger.info(f"Camera properties updated: {self.get_camera_info()}") 