"""
VisionProvider — Abstract base class + Mock implementation for Phase 12.

Every concrete vision backend (OpenCV, ONNX, YOLO, MediaPipe, TensorRT) must
implement `VisionProvider`. No business logic in EyesAgent or PerceptionAgent
depends on any specific provider API.

Concrete providers delivered here:
  - MockVisionProvider  : zero-hardware, deterministic stubs for testing
"""
from __future__ import annotations

import uuid
import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..models import (
    VisionResult,
    DetectedObject,
    DetectedFace,
    BoundingBox,
)

logger = logging.getLogger(__name__)


class VisionProvider(ABC):
    """Abstract vision processing provider."""

    @abstractmethod
    def analyze_frame(
        self,
        frame_bytes: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> VisionResult:
        """Full frame analysis — objects, faces, scene, OCR, motion."""

    @abstractmethod
    def detect_objects(
        self,
        frame_bytes: bytes,
        confidence_threshold: float = 0.5,
    ) -> List[DetectedObject]:
        """Detect objects in frame."""

    @abstractmethod
    def detect_faces(
        self,
        frame_bytes: bytes,
        confidence_threshold: float = 0.5,
    ) -> List[DetectedFace]:
        """Detect and optionally recognise faces in frame."""

    @abstractmethod
    def run_ocr(self, frame_bytes: bytes) -> str:
        """Extract text from image frame."""

    @abstractmethod
    def classify_scene(self, frame_bytes: bytes) -> str:
        """Classify the overall scene."""

    def provider_name(self) -> str:
        return self.__class__.__name__

    def is_available(self) -> bool:
        """Return True if the provider is available in this environment."""
        return True


# ─── Mock Provider ─────────────────────────────────────────────────────────────

class MockVisionProvider(VisionProvider):
    """
    Deterministic, zero-hardware vision provider for unit testing and
    server environments without cameras or GPU.
    """

    def analyze_frame(
        self,
        frame_bytes: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> VisionResult:
        start = time.time()
        cfg = config or {}
        session_id = cfg.get("session_id", "")
        objects = self.detect_objects(frame_bytes)
        faces = self.detect_faces(frame_bytes)
        scene = self.classify_scene(frame_bytes)
        ocr = self.run_ocr(frame_bytes)
        ms = round((time.time() - start) * 1000, 2)
        return VisionResult(
            frame_id=str(uuid.uuid4()),
            session_id=session_id,
            provider=self.provider_name(),
            objects=objects,
            faces=faces,
            scene_label=scene,
            scene_confidence=0.88,
            ocr_text=ocr,
            motion_detected=False,
            motion_score=0.05,
            attention_zones=[{"zone": "center", "score": 0.9}],
            overall_confidence=0.85,
            processing_ms=ms,
        )

    def detect_objects(
        self,
        frame_bytes: bytes,
        confidence_threshold: float = 0.5,
    ) -> List[DetectedObject]:
        return [
            DetectedObject(
                label="person",
                confidence=0.92,
                bbox=BoundingBox(x1=100, y1=50, x2=300, y2=400),
            ),
            DetectedObject(
                label="chair",
                confidence=0.78,
                bbox=BoundingBox(x1=350, y1=200, x2=480, y2=380),
            ),
        ]

    def detect_faces(
        self,
        frame_bytes: bytes,
        confidence_threshold: float = 0.5,
    ) -> List[DetectedFace]:
        return [
            DetectedFace(
                identity="unknown",
                confidence=0.90,
                bbox=BoundingBox(x1=120, y1=60, x2=240, y2=180),
                emotion="neutral",
                landmarks={"left_eye": [145, 90], "right_eye": [195, 90]},
            )
        ]

    def run_ocr(self, frame_bytes: bytes) -> str:
        return "[MockOCR: no text detected]"

    def classify_scene(self, frame_bytes: bytes) -> str:
        return "office_environment"

    def provider_name(self) -> str:
        return "MockVisionProvider"
