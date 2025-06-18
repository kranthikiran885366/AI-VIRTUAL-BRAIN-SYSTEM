import cv2
import numpy as np
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import yaml
from collections import deque

@dataclass
class MemoryConfig:
    """Configuration for memory buffer module."""
    buffer_size: int
    retention_time: float
    importance_threshold: float
    compression_quality: float
    capacity: int
    frame_buffer: Dict[str, Any]
    feature_buffer: Dict[str, Any]
    temporal_buffer: Dict[str, Any]
    persistence: Dict[str, Any]

class MemoryBuffer:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the memory buffer module."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize buffers
        self.frame_buffer = deque(maxlen=self.config.frame_buffer["size"])
        self.feature_buffer = deque(maxlen=self.config.feature_buffer["size"])
        self.temporal_buffer = deque(maxlen=self.config.temporal_buffer["size"])
        
        # Memory state
        self.last_update_time = time.time()
        self.memory_count = 0
        self.important_memories = []
        
        # Performance metrics
        self.update_time = 0
        self.compression_time = 0
    
    def _load_config(self, config_path: str) -> MemoryConfig:
        """Load memory buffer configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return MemoryConfig(**config_data.get("memory", {}))
    
    def update(self, frame: np.ndarray, detections: Dict[str, Any],
              attention: Dict[str, Any]) -> Dict[str, Any]:
        """Update memory buffers with new information."""
        start_time = time.time()
        
        # Compress frame
        compressed_frame = self._compress_frame(frame)
        
        # Create memory entry
        memory = {
            "timestamp": time.time(),
            "frame": compressed_frame,
            "detections": detections,
            "attention": attention,
            "importance": self._calculate_importance(detections, attention)
        }
        
        # Update buffers
        self.frame_buffer.append(memory)
        self.feature_buffer.append(self._extract_features(memory))
        self.temporal_buffer.append(memory)
        
        # Update important memories
        if memory["importance"] > self.config.importance_threshold:
            self.important_memories.append(memory)
            self._cleanup_old_memories()
        
        # Update metrics
        self.update_time = time.time() - start_time
        self.memory_count += 1
        self.last_update_time = time.time()
        
        return memory
    
    def _compress_frame(self, frame: np.ndarray) -> np.ndarray:
        """Compress frame for storage."""
        start_time = time.time()
        
        # Resize frame
        h, w = frame.shape[:2]
        target_size = tuple(self.config.frame_buffer["resolution"])
        frame_resized = cv2.resize(frame, target_size)
        
        # Compress with specified quality
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY),
                       int(self.config.compression_quality * 100)]
        _, compressed = cv2.imencode('.jpg', frame_resized, encode_param)
        
        self.compression_time = time.time() - start_time
        
        return compressed
    
    def _cleanup_old_memories(self):
        """Remove old memories based on retention time."""
        current_time = time.time()
        self.important_memories = [
            mem for mem in self.important_memories
            if current_time - mem["timestamp"] <= self.config.retention_time
        ]
    
    def get_memory(self, index: int = -1) -> Optional[Dict[str, Any]]:
        """Get a specific memory entry."""
        if not self.frame_buffer:
            return None
        
        try:
            memory = self.frame_buffer[index]
            return memory
        except IndexError:
            return None
    
    def get_memories_in_range(self, start_time: float,
                            end_time: float) -> List[Dict[str, Any]]:
        """Get memories within a time range."""
        memories = []
        for memory in self.frame_buffer:
            if start_time <= memory["timestamp"] <= end_time:
                memories.append(memory)
        return memories
    
    def get_important_memories(self) -> List[Dict[str, Any]]:
        """Get memories marked as important."""
        return self.important_memories
    
    def get_memory_visualization(self, memory: Dict[str, Any]) -> np.ndarray:
        """Create visualization of a memory entry."""
        # Decode compressed frame
        frame = cv2.imdecode(memory["frame"], cv2.IMREAD_COLOR)
        
        # Create visualization
        vis = frame.copy()
        
        # Add detections
        for face in memory["detections"].get("faces", []):
            x1, y1, x2, y2 = face["bbox"]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        for obj in memory["detections"].get("objects", []):
            x1, y1, x2, y2 = obj["bbox"]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(vis, f"{obj['class']}: {obj['confidence']:.2f}",
                      (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                      (255, 0, 0), 2)
        
        # Add attention visualization
        if memory["attention"].get("attention_map") is not None:
            attention_map = memory["attention"]["attention_map"]
            attention_vis = cv2.applyColorMap(
                (attention_map * 255).astype(np.uint8),
                cv2.COLORMAP_JET
            )
            vis = cv2.addWeighted(vis, 0.7, attention_vis, 0.3, 0)
        
        # Add timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S",
                                time.localtime(memory["timestamp"]))
        cv2.putText(vis, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                   (0, 255, 0), 2)
        
        return vis
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        return {
            "update_time": self.update_time,
            "compression_time": self.compression_time,
            "memory_count": self.memory_count,
            "time_since_update": time.time() - self.last_update_time
        }
    
    def reset(self):
        """Reset the memory buffer module."""
        self.frame_buffer.clear()
        self.feature_buffer.clear()
        self.temporal_buffer.clear()
        self.important_memories.clear()
        self.last_update_time = time.time()
        self.memory_count = 0
        self.update_time = 0
        self.compression_time = 0
        self.logger.info("Memory buffer module reset")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create memory buffer
    memory_buffer = MemoryBuffer()
    
    # Test with webcam
    cap = cv2.VideoCapture(0)
    
    try:
        while True:
            # Read frame
            ret, frame = cap.read()
            if not ret:
                break
            
            # Create dummy detections and attention for testing
            detections = {
                "faces": [{
                    "bbox": [100, 100, 200, 200],
                    "confidence": 0.9
                }],
                "objects": [{
                    "bbox": [300, 300, 400, 400],
                    "confidence": 0.8
                }]
            }
            
            attention = {
                "attention_map": np.random.rand(480, 640),
                "current_focus": (320, 240)
            }
            
            # Update memory
            memory = memory_buffer.update(frame, detections, attention)
            
            # Get visualization
            vis = memory_buffer.get_memory_visualization(memory)
            
            # Display frame
            cv2.imshow("Memory Buffer Test", vis)
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Print performance metrics
            metrics = memory_buffer.get_performance_metrics()
            print(f"Update time: {metrics['update_time']*1000:.1f}ms")
            print(f"Compression time: {metrics['compression_time']*1000:.1f}ms")
            print(f"Memory count: {metrics['memory_count']}")
            print("---")
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cap.release()
        cv2.destroyAllWindows() 