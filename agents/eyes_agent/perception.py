import cv2
import numpy as np
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import yaml
import mediapipe as mp
from ultralytics import YOLO

@dataclass
class PerceptionConfig:
    """Configuration for perception module."""
    face_detection: Dict[str, Any]
    object_detection: Dict[str, Any]
    scene_classification: Dict[str, Any]

class Perception:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the perception module."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize face detection
        self._init_face_detection()
        
        # Initialize object detection
        self._init_object_detection()
        
        # Initialize scene classification
        self._init_scene_classification()
        
        # Performance metrics
        self.face_detection_time = 0
        self.object_detection_time = 0
        self.scene_classification_time = 0
    
    def _load_config(self, config_path: str) -> PerceptionConfig:
        """Load perception configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return PerceptionConfig(**config_data.get("perception", {}))
    
    def _init_face_detection(self):
        """Initialize face detection model."""
        model_type = self.config.face_detection["model"]
        
        if model_type == "mediapipe":
            self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=self.config.face_detection["max_faces"],
                min_detection_confidence=self.config.face_detection["min_confidence"],
                min_tracking_confidence=0.5
            )
        elif model_type == "dlib":
            import dlib
            self.face_detector = dlib.get_frontal_face_detector()
            self.face_predictor = dlib.shape_predictor("models/dlib/shape_predictor_68_face_landmarks.dat")
        elif model_type == "mtcnn":
            from mtcnn import MTCNN
            self.face_detector = MTCNN()
        else:
            raise ValueError(f"Unsupported face detection model: {model_type}")
    
    def _init_object_detection(self):
        """Initialize object detection model."""
        model_type = self.config.object_detection["model"]
        
        if model_type.startswith("yolov8"):
            self.object_detector = YOLO(f"models/yolo/{model_type}.pt")
        else:
            raise ValueError(f"Unsupported object detection model: {model_type}")
    
    def _init_scene_classification(self):
        """Initialize scene classification model."""
        model_type = self.config.scene_classification["model"]
        
        if model_type == "resnet50":
            import tensorflow as tf
            self.scene_classifier = tf.keras.applications.ResNet50(
                weights="imagenet",
                include_top=True
            )
        else:
            raise ValueError(f"Unsupported scene classification model: {model_type}")
    
    def detect(self, frame: np.ndarray) -> Dict[str, Any]:
        """Detect objects, faces, and classify scene in the frame."""
        results = {
            "faces": [],
            "objects": [],
            "scene": None,
            "timestamp": time.time()
        }
        
        # Detect faces
        start_time = time.time()
        results["faces"] = self._detect_faces(frame)
        self.face_detection_time = time.time() - start_time
        
        # Detect objects
        start_time = time.time()
        results["objects"] = self._detect_objects(frame)
        self.object_detection_time = time.time() - start_time
        
        # Classify scene
        start_time = time.time()
        results["scene"] = self._classify_scene(frame)
        self.scene_classification_time = time.time() - start_time
        
        return results
    
    def _detect_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect faces in the frame."""
        faces = []
        model_type = self.config.face_detection["model"]
        
        try:
            if model_type == "mediapipe":
                # Convert to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Detect faces
                results = self.face_mesh.process(frame_rgb)
                
                if results.multi_face_landmarks:
                    for face_landmarks in results.multi_face_landmarks:
                        # Get face bounding box
                        h, w = frame.shape[:2]
                        x_min = w
                        y_min = h
                        x_max = 0
                        y_max = 0
                        
                        for landmark in face_landmarks.landmark:
                            x, y = int(landmark.x * w), int(landmark.y * h)
                            x_min = min(x_min, x)
                            y_min = min(y_min, y)
                            x_max = max(x_max, x)
                            y_max = max(y_max, y)
                        
                        faces.append({
                            "bbox": [x_min, y_min, x_max, y_max],
                            "landmarks": [[lm.x, lm.y, lm.z] for lm in face_landmarks.landmark],
                            "confidence": 1.0
                        })
            
            elif model_type == "dlib":
                # Convert to grayscale
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Detect faces
                detections = self.face_detector(gray)
                
                for detection in detections:
                    # Get face landmarks
                    shape = self.face_predictor(gray, detection)
                    landmarks = [[p.x, p.y] for p in shape.parts()]
                    
                    faces.append({
                        "bbox": [detection.left(), detection.top(),
                                detection.right(), detection.bottom()],
                        "landmarks": landmarks,
                        "confidence": detection.confidence
                    })
            
            elif model_type == "mtcnn":
                # Detect faces
                detections = self.face_detector.detect_faces(frame)
                
                for detection in detections:
                    x, y, w, h = detection["box"]
                    faces.append({
                        "bbox": [x, y, x + w, y + h],
                        "landmarks": detection["keypoints"],
                        "confidence": detection["confidence"]
                    })
        
        except Exception as e:
            self.logger.error(f"Error in face detection: {str(e)}")
        
        return faces
    
    def _detect_objects(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect objects in the frame."""
        objects = []
        
        try:
            # Run object detection
            results = self.object_detector(frame)
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Get class and confidence
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    
                    # Check if class is in allowed classes
                    class_name = result.names[cls]
                    if class_name in self.config.object_detection["classes"]:
                        # Get bounding box
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        
                        objects.append({
                            "class": class_name,
                            "bbox": [x1, y1, x2, y2],
                            "confidence": conf
                        })
        
        except Exception as e:
            self.logger.error(f"Error in object detection: {str(e)}")
        
        return objects
    
    def _classify_scene(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """Classify the scene in the frame."""
        try:
            # Resize frame to match model input
            input_size = (224, 224)
            frame_resized = cv2.resize(frame, input_size)
            
            # Preprocess frame
            frame_array = np.expand_dims(frame_resized, axis=0)
            frame_array = frame_array.astype(np.float32) / 255.0
            
            # Get predictions
            predictions = self.scene_classifier.predict(frame_array)
            
            # Get top prediction
            top_idx = np.argmax(predictions[0])
            confidence = float(predictions[0][top_idx])
            
            if confidence >= self.config.scene_classification["confidence_threshold"]:
                return {
                    "class": self.scene_classifier.layers[-1].get_config()["classes"][top_idx],
                    "confidence": confidence
                }
        
        except Exception as e:
            self.logger.error(f"Error in scene classification: {str(e)}")
        
        return None
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        return {
            "face_detection_time": self.face_detection_time,
            "object_detection_time": self.object_detection_time,
            "scene_classification_time": self.scene_classification_time,
            "total_time": (self.face_detection_time +
                         self.object_detection_time +
                         self.scene_classification_time)
        }
    
    def reset(self):
        """Reset the perception module."""
        self.face_detection_time = 0
        self.object_detection_time = 0
        self.scene_classification_time = 0
        self.logger.info("Perception module reset")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create perception module
    perception = Perception()
    
    # Test with webcam
    cap = cv2.VideoCapture(0)
    
    try:
        while True:
            # Read frame
            ret, frame = cap.read()
            if not ret:
                break
            
            # Detect objects and faces
            results = perception.detect(frame)
            
            # Draw results
            for face in results["faces"]:
                x1, y1, x2, y2 = face["bbox"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            for obj in results["objects"]:
                x1, y1, x2, y2 = obj["bbox"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(frame, f"{obj['class']}: {obj['confidence']:.2f}",
                          (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                          (255, 0, 0), 2)
            
            if results["scene"]:
                cv2.putText(frame, f"Scene: {results['scene']['class']}",
                          (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                          (0, 0, 255), 2)
            
            # Display frame
            cv2.imshow("Perception Test", frame)
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Print performance metrics
            metrics = perception.get_performance_metrics()
            print(f"Face detection: {metrics['face_detection_time']*1000:.1f}ms")
            print(f"Object detection: {metrics['object_detection_time']*1000:.1f}ms")
            print(f"Scene classification: {metrics['scene_classification_time']*1000:.1f}ms")
            print(f"Total time: {metrics['total_time']*1000:.1f}ms")
            print("---")
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cap.release()
        cv2.destroyAllWindows() 