import os
import cv2
import time
import logging
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import json
from datetime import datetime

def setup_logging(level: str = "INFO", output_dir: str = "logs", max_files: int = 10):
    """Setup logging configuration."""
    # Create logs directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Configure logging
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=getattr(logging, level),
        format=log_format,
        handlers=[
            logging.FileHandler(os.path.join(output_dir, f"eyes_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")),
            logging.StreamHandler()
        ]
    )
    
    # Clean up old log files
    log_files = sorted(Path(output_dir).glob("eyes_agent_*.log"))
    if len(log_files) > max_files:
        for old_file in log_files[:-max_files]:
            old_file.unlink()

def calculate_fps(frame_count: int, start_time: float) -> float:
    """Calculate frames per second."""
    elapsed_time = time.time() - start_time
    if elapsed_time > 0:
        return frame_count / elapsed_time
    return 0.0

def draw_detections(
    frame: np.ndarray,
    object_detections: List[Dict[str, Any]],
    face_detections: List[Dict[str, Any]],
    display_config: Dict[str, Any]
) -> np.ndarray:
    """Draw detection boxes and labels on the frame."""
    # Get display settings
    show_boxes = display_config["show_boxes"]
    show_labels = display_config["show_labels"]
    show_confidence = display_config["show_confidence"]
    box_color = tuple(display_config["box_color"])
    text_color = tuple(display_config["text_color"])
    font_scale = display_config["font_scale"]
    thickness = display_config["thickness"]
    
    # Draw object detections
    for detection in object_detections:
        bbox = detection["bbox"]
        x1, y1, x2, y2 = map(int, bbox)
        
        if show_boxes:
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, thickness)
        
        if show_labels or show_confidence:
            label = []
            if show_labels:
                label.append(detection["class_name"])
            if show_confidence:
                label.append(f"{detection['score']:.2f}")
            
            text = " ".join(label)
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
            cv2.rectangle(frame, (x1, y1 - text_size[1] - 5), (x1 + text_size[0], y1), box_color, -1)
            cv2.putText(frame, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, thickness)
    
    # Draw face detections
    for face in face_detections:
        bbox = face["bbox"]
        x1, y1, x2, y2 = map(int, bbox)
        
        if show_boxes:
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, thickness)
        
        if show_labels or show_confidence:
            label = []
            if show_labels:
                label.append("Face")
            if show_confidence:
                label.append(f"{face['confidence']:.2f}")
            
            text = " ".join(label)
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
            cv2.rectangle(frame, (x1, y1 - text_size[1] - 5), (x1 + text_size[0], y1), box_color, -1)
            cv2.putText(frame, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, thickness)
        
        # Draw landmarks if available
        if "landmarks" in face:
            for landmark in face["landmarks"]:
                x, y = map(int, landmark)
                cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)
    
    return frame

def draw_fps(frame: np.ndarray, fps: float, position: Tuple[int, int] = (10, 30)) -> np.ndarray:
    """Draw FPS counter on the frame."""
    text = f"FPS: {fps:.1f}"
    cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    return frame

def save_detection_results(
    detections: List[Dict[str, Any]],
    output_dir: str,
    filename: str = None
):
    """Save detection results to a JSON file."""
    if filename is None:
        filename = f"detections_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    output_path = os.path.join(output_dir, filename)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save results
    with open(output_path, 'w') as f:
        json.dump(detections, f, indent=2)
    
    logging.info(f"Detection results saved to {output_path}")

def create_video_writer(
    output_path: str,
    width: int,
    height: int,
    fps: float
) -> cv2.VideoWriter:
    """Create a video writer object."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    return cv2.VideoWriter(output_path, fourcc, fps, (width, height))

def calculate_iou(box1: List[int], box2: List[int]) -> float:
    """Calculate Intersection over Union between two bounding boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = box1_area + box2_area - intersection
    
    return intersection / union if union > 0 else 0

def non_max_suppression(
    detections: List[Dict[str, Any]],
    iou_threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """Apply non-maximum suppression to remove overlapping detections."""
    if not detections:
        return []
    
    # Sort detections by confidence
    detections = sorted(detections, key=lambda x: x["score"], reverse=True)
    
    # Initialize list of kept detections
    kept = []
    
    while detections:
        # Get detection with highest confidence
        current = detections.pop(0)
        kept.append(current)
        
        # Remove overlapping detections
        detections = [
            detection for detection in detections
            if calculate_iou(current["bbox"], detection["bbox"]) < iou_threshold
        ]
    
    return kept

def draw_tracking_path(
    frame: np.ndarray,
    track_history: List[Tuple[int, int, int, int]],
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2
) -> np.ndarray:
    """Draw tracking path on the frame."""
    if not track_history:
        return frame
    
    # Get center points
    points = []
    for bbox in track_history:
        x, y, w, h = bbox
        center_x = x + w // 2
        center_y = y + h // 2
        points.append((center_x, center_y))
    
    # Draw lines between points
    for i in range(1, len(points)):
        cv2.line(frame, points[i-1], points[i], color, thickness)
    
    return frame

def create_timestamp() -> str:
    """Create a timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def ensure_directory(directory: str):
    """Ensure a directory exists, create if it doesn't."""
    os.makedirs(directory, exist_ok=True)

def get_file_extension(filename: str) -> str:
    """Get the extension of a file."""
    return os.path.splitext(filename)[1].lower()

def is_valid_image_file(filename: str) -> bool:
    """Check if a file is a valid image file."""
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    return get_file_extension(filename) in valid_extensions

def is_valid_video_file(filename: str) -> bool:
    """Check if a file is a valid video file."""
    valid_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv'}
    return get_file_extension(filename) in valid_extensions 