import asyncio
import cv2
import numpy as np
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import json
from pathlib import Path
import yaml
from .camera_interface import CameraInterface
from .object_detection import ObjectDetector
from .face_tracking import FaceTracker
from .image_processing import ImageProcessor
from .utils import setup_logging, load_config

class EyesAgent:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the eyes agent with configuration."""
        self.config = load_config(config_path)
        self.logger = setup_logging("eyes_agent", self.config["logging"])
        
        # Initialize components
        self.camera = CameraInterface(self.config["camera"])
        self.object_detector = ObjectDetector(self.config["object_detection"])
        self.face_tracker = FaceTracker(self.config["face_tracking"])
        self.image_processor = ImageProcessor(self.config["image_processing"])
        
        # State variables
        self.is_running = False
        self.current_frame = None
        self.detected_objects = []
        self.tracked_faces = []
        self.processing_stats = {
            "fps": 0,
            "frame_count": 0,
            "processing_time": 0
        }
        
        # Initialize metrics
        self.metrics = {
            "total_frames_processed": 0,
            "total_objects_detected": 0,
            "total_faces_tracked": 0,
            "average_processing_time": 0,
            "start_time": datetime.utcnow().isoformat()
        }
        
        self.logger.info("Eyes agent initialized")

    async def start(self):
        """Start the eyes agent."""
        try:
            self.is_running = True
            await self.camera.start()
            self.logger.info("Eyes agent started")
            
            # Start processing loop
            asyncio.create_task(self._processing_loop())
            
        except Exception as e:
            self.logger.error(f"Failed to start eyes agent: {str(e)}")
            raise

    async def stop(self):
        """Stop the eyes agent."""
        try:
            self.is_running = False
            await self.camera.stop()
            self.logger.info("Eyes agent stopped")
            
            # Save final metrics
            self._save_metrics()
            
        except Exception as e:
            self.logger.error(f"Error stopping eyes agent: {str(e)}")
            raise

    async def _processing_loop(self):
        """Main processing loop for real-time vision."""
        while self.is_running:
            try:
                # Get frame from camera
                frame = await self.camera.get_frame()
                if frame is None:
                    continue
                
                # Process frame
                start_time = datetime.utcnow()
                
                # Detect objects
                objects = await self.object_detector.detect(frame)
                self.detected_objects = objects
                
                # Track faces
                faces = await self.face_tracker.track(frame)
                self.tracked_faces = faces
                
                # Process image
                processed_frame = await self.image_processor.process(frame)
                self.current_frame = processed_frame
                
                # Update metrics
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                self._update_metrics(len(objects), len(faces), processing_time)
                
                # Update processing stats
                self._update_processing_stats(processing_time)
                
            except Exception as e:
                self.logger.error(f"Error in processing loop: {str(e)}")
                await asyncio.sleep(1)  # Prevent tight loop on error

    def _update_metrics(self, num_objects: int, num_faces: int, processing_time: float):
        """Update agent metrics."""
        self.metrics["total_frames_processed"] += 1
        self.metrics["total_objects_detected"] += num_objects
        self.metrics["total_faces_tracked"] += num_faces
        
        # Update average processing time
        current_avg = self.metrics["average_processing_time"]
        new_avg = (current_avg * (self.metrics["total_frames_processed"] - 1) + 
                  processing_time) / self.metrics["total_frames_processed"]
        self.metrics["average_processing_time"] = new_avg

    def _update_processing_stats(self, processing_time: float):
        """Update real-time processing statistics."""
        self.processing_stats["frame_count"] += 1
        self.processing_stats["processing_time"] = processing_time
        
        # Calculate FPS
        if processing_time > 0:
            self.processing_stats["fps"] = 1 / processing_time

    def _save_metrics(self):
        """Save metrics to file."""
        try:
            metrics_file = Path(self.config["metrics"]["file"])
            metrics_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(metrics_file, "w") as f:
                json.dump(self.metrics, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save metrics: {str(e)}")

    async def get_status(self) -> Dict[str, Any]:
        """Get current status of the eyes agent."""
        return {
            "status": "running" if self.is_running else "stopped",
            "components": {
                "camera": await self.camera.get_status(),
                "object_detector": self.object_detector.get_status(),
                "face_tracker": self.face_tracker.get_status(),
                "image_processor": self.image_processor.get_status()
            },
            "processing_stats": self.processing_stats,
            "metrics": self.metrics
        }

    async def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the current processed frame."""
        return self.current_frame

    async def get_detected_objects(self) -> List[Dict[str, Any]]:
        """Get currently detected objects."""
        return self.detected_objects

    async def get_tracked_faces(self) -> List[Dict[str, Any]]:
        """Get currently tracked faces."""
        return self.tracked_faces

    async def update_config(self, new_config: Dict[str, Any]):
        """Update agent configuration."""
        try:
            # Update component configurations
            self.camera.update_config(new_config.get("camera", {}))
            self.object_detector.update_config(new_config.get("object_detection", {}))
            self.face_tracker.update_config(new_config.get("face_tracking", {}))
            self.image_processor.update_config(new_config.get("image_processing", {}))
            
            # Update main configuration
            self.config.update(new_config)
            
            self.logger.info("Configuration updated successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to update configuration: {str(e)}")
            raise

def main():
    """Main entry point for the eyes agent system."""
    try:
        agent = EyesAgent()
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        logging.error(f"Error in main: {e}")
    finally:
        if 'agent' in locals():
            asyncio.run(agent.stop())

if __name__ == "__main__":
    main() 