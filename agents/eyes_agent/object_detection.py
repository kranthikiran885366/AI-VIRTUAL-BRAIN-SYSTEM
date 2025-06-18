import cv2
import numpy as np
from typing import Dict, Any, List, Optional
import logging
import asyncio
from datetime import datetime
import json
from pathlib import Path

class ObjectDetector:
    def __init__(self, config: Dict[str, Any]):
        """Initialize object detector with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Load model
        self.model_path = config.get("model_path", "models/yolov4.weights")
        self.config_path = config.get("config_path", "models/yolov4.cfg")
        self.classes_path = config.get("classes_path", "models/coco.names")
        
        # Detection settings
        self.confidence_threshold = config.get("confidence_threshold", 0.5)
        self.nms_threshold = config.get("nms_threshold", 0.4)
        self.target_classes = config.get("target_classes", [])
        
        # Load model and classes
        self.net = None
        self.classes = []
        self._load_model()
        
        # Metrics
        self.metrics = {
            "total_detections": 0,
            "detections_by_class": {},
            "average_confidence": 0,
            "processing_times": [],
            "start_time": datetime.utcnow().isoformat()
        }
        
        self.logger.info("Object detector initialized")

    def _load_model(self):
        """Load YOLO model and classes."""
        try:
            # Load classes
            with open(self.classes_path, 'r') as f:
                self.classes = [line.strip() for line in f.readlines()]
            
            # Load model
            self.net = cv2.dnn.readNet(self.model_path, self.config_path)
            
            # Set backend and target
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
            
            self.logger.info("Model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load model: {str(e)}")
            raise

    async def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect objects in the frame."""
        if self.net is None:
            return []
            
        try:
            start_time = datetime.utcnow()
            
            # Prepare image
            height, width = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
            
            # Set input
            self.net.setInput(blob)
            
            # Get output layers
            layer_names = self.net.getLayerNames()
            output_layers = [layer_names[i - 1] for i in self.net.getUnconnectedOutLayers()]
            
            # Forward pass
            outputs = self.net.forward(output_layers)
            
            # Process detections
            detections = self._process_detections(outputs, width, height)
            
            # Update metrics
            self._update_metrics(detections, start_time)
            
            return detections
            
        except Exception as e:
            self.logger.error(f"Error in object detection: {str(e)}")
            return []

    def _process_detections(self, outputs: List[np.ndarray], width: int, height: int) -> List[Dict[str, Any]]:
        """Process detection outputs and apply NMS."""
        boxes = []
        confidences = []
        class_ids = []
        
        # Process each output layer
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                
                # Filter by confidence and target classes
                if confidence > self.confidence_threshold:
                    if not self.target_classes or self.classes[class_id] in self.target_classes:
                        # Get box coordinates
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)
                        
                        # Rectangle coordinates
                        x = int(center_x - w / 2)
                        y = int(center_y - h / 2)
                        
                        boxes.append([x, y, w, h])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)
        
        # Apply NMS
        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence_threshold, self.nms_threshold)
        
        # Format detections
        detections = []
        for i in indices:
            box = boxes[i]
            detection = {
                "class": self.classes[class_ids[i]],
                "confidence": confidences[i],
                "bbox": {
                    "x": box[0],
                    "y": box[1],
                    "width": box[2],
                    "height": box[3]
                }
            }
            detections.append(detection)
        
        return detections

    def _update_metrics(self, detections: List[Dict[str, Any]], start_time: datetime):
        """Update detection metrics."""
        # Update total detections
        self.metrics["total_detections"] += len(detections)
        
        # Update detections by class
        for detection in detections:
            class_name = detection["class"]
            if class_name not in self.metrics["detections_by_class"]:
                self.metrics["detections_by_class"][class_name] = 0
            self.metrics["detections_by_class"][class_name] += 1
        
        # Update average confidence
        if detections:
            confidences = [d["confidence"] for d in detections]
            current_avg = self.metrics["average_confidence"]
            new_avg = (current_avg * (self.metrics["total_detections"] - len(detections)) + 
                      sum(confidences)) / self.metrics["total_detections"]
            self.metrics["average_confidence"] = new_avg
        
        # Update processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        self.metrics["processing_times"].append(processing_time)
        
        # Keep only last 100 processing times
        if len(self.metrics["processing_times"]) > 100:
            self.metrics["processing_times"] = self.metrics["processing_times"][-100:]

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the object detector."""
        return {
            "model_loaded": self.net is not None,
            "confidence_threshold": self.confidence_threshold,
            "nms_threshold": self.nms_threshold,
            "target_classes": self.target_classes,
            "metrics": self.metrics
        }

    def update_config(self, new_config: Dict[str, Any]):
        """Update detector configuration."""
        try:
            # Update thresholds
            if "confidence_threshold" in new_config:
                self.confidence_threshold = new_config["confidence_threshold"]
            
            if "nms_threshold" in new_config:
                self.nms_threshold = new_config["nms_threshold"]
            
            # Update target classes
            if "target_classes" in new_config:
                self.target_classes = new_config["target_classes"]
            
            # Update model if changed
            if "model_path" in new_config and new_config["model_path"] != self.model_path:
                self.model_path = new_config["model_path"]
                self._load_model()
            
            # Update configuration
            self.config.update(new_config)
            
            self.logger.info("Object detector configuration updated successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to update object detector configuration: {str(e)}")
            raise 