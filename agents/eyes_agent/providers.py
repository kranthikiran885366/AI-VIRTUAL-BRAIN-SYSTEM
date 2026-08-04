"""
EyesAgent — Vision Provider Abstraction Layer (Phase 12).

All external vision models are accessed through VisionProvider.
No business logic depends on provider-specific APIs.

Providers:
  MockVisionProvider   — always available, zero dependencies
  OpenCVVisionProvider — OpenCV-based face/object detection
  ONNXVisionProvider   — ONNX Runtime inference
  MediaPipeProvider    — MediaPipe face mesh + hands
"""
from __future__ import annotations

import abc
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Optional imports ─────────────────────────────────────────────────────────
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None  # type: ignore

try:
    import cv2
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False
    cv2 = None  # type: ignore

try:
    import onnxruntime as ort
    _HAS_ONNX = True
except ImportError:
    _HAS_ONNX = False
    ort = None  # type: ignore

try:
    import mediapipe as mp
    _HAS_MEDIAPIPE = True
except ImportError:
    _HAS_MEDIAPIPE = False
    mp = None  # type: ignore


# ─── Provider Interface ───────────────────────────────────────────────────────

class VisionProvider(abc.ABC):
    """Abstract vision provider — all concrete providers implement this."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    def detect_objects(self, frame, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return list of {label, confidence, bbox:{x1,y1,x2,y2}}."""

    @abc.abstractmethod
    def detect_faces(self, frame, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return list of {face_id, confidence, bbox, emotion, landmarks}."""

    @abc.abstractmethod
    def classify_scene(self, frame, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return {label, confidence}."""

    @abc.abstractmethod
    def extract_ocr(self, frame, config: Dict[str, Any]) -> str:
        """Return extracted text string."""

    @abc.abstractmethod
    def detect_motion(self, frame, prev_frame, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return {detected: bool, score: float}."""


# ─── Mock Provider ────────────────────────────────────────────────────────────

class MockVisionProvider(VisionProvider):
    """Zero-dependency mock — always available for testing and fallback."""

    @property
    def name(self) -> str:
        return "mock"

    @property
    def available(self) -> bool:
        return True

    def detect_objects(self, frame, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def detect_faces(self, frame, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def classify_scene(self, frame, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"label": "unknown", "confidence": 0.0}

    def extract_ocr(self, frame, config: Dict[str, Any]) -> str:
        return ""

    def detect_motion(self, frame, prev_frame, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"detected": False, "score": 0.0}


# ─── OpenCV Provider ──────────────────────────────────────────────────────────

class OpenCVVisionProvider(VisionProvider):
    """OpenCV-based face detection using Haar cascades or DNN."""

    def __init__(self, config: Dict[str, Any]):
        self._available = _HAS_CV2 and _HAS_NUMPY
        self._face_cascade = None
        if self._available:
            try:
                cascade_path = config.get("face_cascade_path", "")
                if cascade_path:
                    self._face_cascade = cv2.CascadeClassifier(cascade_path)
                else:
                    # Use built-in cascade
                    self._face_cascade = cv2.CascadeClassifier(
                        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                    )
            except Exception as e:
                logger.warning(f"OpenCVVisionProvider: cascade load failed: {e}")
                self._available = False

    @property
    def name(self) -> str:
        return "opencv"

    @property
    def available(self) -> bool:
        return self._available

    def detect_objects(self, frame, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []  # Haar cascades don't do general object detection

    def detect_faces(self, frame, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self._available or self._face_cascade is None or frame is None:
            return []
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            min_size = config.get("min_face_size", [30, 30])
            detections = self._face_cascade.detectMultiScale(
                gray,
                scaleFactor=config.get("scale_factor", 1.1),
                minNeighbors=config.get("min_neighbors", 5),
                minSize=tuple(min_size),
            )
            faces = []
            for (x, y, w, h) in (detections if len(detections) > 0 else []):
                faces.append({
                    "face_id": str(uuid.uuid4()),
                    "confidence": 0.75,
                    "bbox": {"x1": float(x), "y1": float(y), "x2": float(x + w), "y2": float(y + h)},
                    "emotion": "neutral",
                    "landmarks": {},
                    "identity": "unknown",
                })
            return faces
        except Exception as e:
            logger.error(f"OpenCVVisionProvider.detect_faces: {e}")
            return []

    def classify_scene(self, frame, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"label": "unknown", "confidence": 0.0}

    def extract_ocr(self, frame, config: Dict[str, Any]) -> str:
        return ""

    def detect_motion(self, frame, prev_frame, config: Dict[str, Any]) -> Dict[str, Any]:
        if not self._available or frame is None or prev_frame is None:
            return {"detected": False, "score": 0.0}
        try:
            gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(gray1, gray2)
            score = float(np.mean(diff)) / 255.0
            threshold = config.get("motion_threshold", 0.02)
            return {"detected": score > threshold, "score": round(score, 4)}
        except Exception as e:
            logger.error(f"OpenCVVisionProvider.detect_motion: {e}")
            return {"detected": False, "score": 0.0}


# ─── MediaPipe Provider ───────────────────────────────────────────────────────

class MediaPipeVisionProvider(VisionProvider):
    """MediaPipe face mesh provider."""

    def __init__(self, config: Dict[str, Any]):
        self._available = _HAS_MEDIAPIPE and _HAS_CV2 and _HAS_NUMPY
        self._face_detection = None
        if self._available:
            try:
                self._face_detection = mp.solutions.face_detection.FaceDetection(
                    model_selection=config.get("model_selection", 0),
                    min_detection_confidence=config.get("min_detection_confidence", 0.5),
                )
            except Exception as e:
                logger.warning(f"MediaPipeVisionProvider: init failed: {e}")
                self._available = False

    @property
    def name(self) -> str:
        return "mediapipe"

    @property
    def available(self) -> bool:
        return self._available

    def detect_objects(self, frame, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def detect_faces(self, frame, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self._available or self._face_detection is None or frame is None:
            return []
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._face_detection.process(rgb)
            faces = []
            if results.detections:
                h, w = frame.shape[:2]
                for det in results.detections:
                    bb = det.location_data.relative_bounding_box
                    x1 = max(0.0, bb.xmin * w)
                    y1 = max(0.0, bb.ymin * h)
                    x2 = min(float(w), (bb.xmin + bb.width) * w)
                    y2 = min(float(h), (bb.ymin + bb.height) * h)
                    faces.append({
                        "face_id": str(uuid.uuid4()),
                        "confidence": round(det.score[0] if det.score else 0.8, 4),
                        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                        "emotion": "neutral",
                        "landmarks": {},
                        "identity": "unknown",
                    })
            return faces
        except Exception as e:
            logger.error(f"MediaPipeVisionProvider.detect_faces: {e}")
            return []

    def classify_scene(self, frame, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"label": "unknown", "confidence": 0.0}

    def extract_ocr(self, frame, config: Dict[str, Any]) -> str:
        return ""

    def detect_motion(self, frame, prev_frame, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"detected": False, "score": 0.0}


# ─── ONNX Provider ────────────────────────────────────────────────────────────

class ONNXVisionProvider(VisionProvider):
    """ONNX Runtime inference provider — loads any ONNX model."""

    def __init__(self, config: Dict[str, Any]):
        self._available = _HAS_ONNX and _HAS_NUMPY
        self._session = None
        if self._available:
            model_path = config.get("model_path", "")
            if model_path:
                try:
                    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
                    self._session = ort.InferenceSession(model_path, providers=providers)
                    logger.info(f"ONNXVisionProvider: loaded model {model_path}")
                except Exception as e:
                    logger.warning(f"ONNXVisionProvider: model load failed: {e}")
                    self._available = False
            else:
                self._available = False  # No model path — not usable

    @property
    def name(self) -> str:
        return "onnx"

    @property
    def available(self) -> bool:
        return self._available

    def detect_objects(self, frame, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []  # Generic ONNX — subclass for specific model output parsing

    def detect_faces(self, frame, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def classify_scene(self, frame, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"label": "unknown", "confidence": 0.0}

    def extract_ocr(self, frame, config: Dict[str, Any]) -> str:
        return ""

    def detect_motion(self, frame, prev_frame, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"detected": False, "score": 0.0}


# ─── Registry ─────────────────────────────────────────────────────────────────

_PROVIDER_REGISTRY: Dict[str, type] = {
    "mock": MockVisionProvider,
    "opencv": OpenCVVisionProvider,
    "mediapipe": MediaPipeVisionProvider,
    "onnx": ONNXVisionProvider,
}


def build_vision_provider(name: str, config: Dict[str, Any]) -> VisionProvider:
    """
    Instantiate a vision provider by name.
    Falls back to MockVisionProvider if the requested provider is unavailable.
    """
    cls = _PROVIDER_REGISTRY.get(name.lower())
    if cls is None:
        logger.warning(f"VisionProvider '{name}' unknown — using mock")
        return MockVisionProvider()
    try:
        provider = cls(config)
        if not provider.available:
            logger.warning(f"VisionProvider '{name}' unavailable — using mock")
            return MockVisionProvider()
        logger.info(f"VisionProvider '{name}' ready")
        return provider
    except Exception as e:
        logger.warning(f"VisionProvider '{name}' init error ({e}) — using mock")
        return MockVisionProvider()
