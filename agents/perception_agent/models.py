"""
Phase 12 — Shared Perception Models.

Data structures used across all four sensory agents:
  EyesAgent / EarAgent / MouthAgent / PerceptionAgent

All dataclasses are fully serializable via .to_dict() and importable
without any hardware driver dependency.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


# ─── Context ──────────────────────────────────────────────────────────────────

@dataclass
class PerceptionContext:
    """Multi-agent perception context aggregating inputs from all cognitive systems."""
    conversation_context: Dict[str, Any] = field(default_factory=dict)
    memory_context: Dict[str, Any] = field(default_factory=dict)
    decision_context: Dict[str, Any] = field(default_factory=dict)
    reasoning_context: Dict[str, Any] = field(default_factory=dict)
    planning_context: Dict[str, Any] = field(default_factory=dict)
    learning_context: Dict[str, Any] = field(default_factory=dict)
    emotion_context: Dict[str, Any] = field(default_factory=dict)
    language_context: Dict[str, Any] = field(default_factory=dict)
    creativity_context: Dict[str, Any] = field(default_factory=dict)
    ethics_context: Dict[str, Any] = field(default_factory=dict)
    system_state: Dict[str, Any] = field(default_factory=dict)
    sensor_metadata: Dict[str, Any] = field(default_factory=dict)
    # Trace IDs
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Vision Models ────────────────────────────────────────────────────────────

@dataclass
class BoundingBox:
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DetectedObject:
    label: str = ""
    confidence: float = 0.0
    bbox: BoundingBox = field(default_factory=BoundingBox)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DetectedFace:
    face_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    identity: str = "unknown"
    confidence: float = 0.0
    bbox: BoundingBox = field(default_factory=BoundingBox)
    emotion: str = "neutral"
    landmarks: Dict[str, Any] = field(default_factory=dict)
    age_estimate: Optional[float] = None
    gaze_direction: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VisionFrame:
    frame_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    source: str = "camera"          # camera / file / stream / synthetic
    width: int = 0
    height: int = 0
    channels: int = 3
    encoding: str = "BGR"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VisionResult:
    frame_id: str = ""
    session_id: str = ""
    provider: str = "mock"
    objects: List[DetectedObject] = field(default_factory=list)
    faces: List[DetectedFace] = field(default_factory=list)
    scene_label: str = "unknown"
    scene_confidence: float = 0.0
    ocr_text: str = ""
    motion_detected: bool = False
    motion_score: float = 0.0
    attention_zones: List[Dict[str, Any]] = field(default_factory=list)
    overall_confidence: float = 0.0
    processing_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Audio Models ─────────────────────────────────────────────────────────────

@dataclass
class AudioFrame:
    frame_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    sample_rate: int = 16000
    channels: int = 1
    encoding: str = "int16"
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AudioResult:
    frame_id: str = ""
    session_id: str = ""
    provider: str = "mock"
    transcription: str = ""
    transcription_confidence: float = 0.0
    language: str = "en"
    language_confidence: float = 0.0
    speaker_id: str = "unknown"
    speaker_confidence: float = 0.0
    emotion: str = "neutral"
    emotion_scores: Dict[str, float] = field(default_factory=dict)
    intent: str = "unknown"
    intent_confidence: float = 0.0
    keywords_detected: List[str] = field(default_factory=list)
    noise_level: float = 0.0
    voice_activity: bool = False
    overall_confidence: float = 0.0
    processing_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Speech / TTS Models ──────────────────────────────────────────────────────

@dataclass
class VoiceProfile:
    profile_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "default"
    language: str = "en-US"
    gender: str = "neutral"
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    provider: str = "mock"
    provider_voice_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProsodyConfig:
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    emphasis: str = "normal"    # normal / strong / reduced
    break_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SpeechRequest:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    text: str = ""
    emotion: str = "neutral"
    language: str = "en-US"
    voice_profile: Optional[VoiceProfile] = None
    prosody: Optional[ProsodyConfig] = None
    stream: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SpeechResult:
    request_id: str = ""
    session_id: str = ""
    provider: str = "mock"
    text_rendered: str = ""
    audio_bytes: bytes = field(default_factory=bytes)
    duration_ms: float = 0.0
    format: str = "wav"
    processing_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["audio_bytes"] = len(self.audio_bytes)  # Don't serialize binary blob
        return d


# ─── Fusion Models ────────────────────────────────────────────────────────────

@dataclass
class CrossModalCorrelation:
    modalities: List[str] = field(default_factory=list)       # e.g. ["vision", "audio"]
    correlation_score: float = 0.0
    temporal_offset_ms: float = 0.0
    aligned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FusionResult:
    fusion_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    provider: str = "default"
    visual_summary: Dict[str, Any] = field(default_factory=dict)
    audio_summary: Dict[str, Any] = field(default_factory=dict)
    cross_modal_correlations: List[CrossModalCorrelation] = field(default_factory=list)
    situation_label: str = "unknown"
    situation_confidence: float = 0.0
    attention_focus: str = ""
    detected_events: List[str] = field(default_factory=list)
    environment_understanding: str = ""
    aggregate_confidence: float = 0.0
    uncertainty: float = 0.0
    temporal_window_ms: float = 0.0
    processing_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Session & Metrics ────────────────────────────────────────────────────────

@dataclass
class PerceptionSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_type: str = ""        # eyes / ear / mouth / perception
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ended_at: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    provider: str = "mock"
    operations_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerceptionMetrics:
    # Vision
    vision_sessions: int = 0
    frames_processed: int = 0
    objects_detected: int = 0
    faces_detected: int = 0
    ocr_operations: int = 0
    # Audio
    audio_sessions: int = 0
    utterances_transcribed: int = 0
    speakers_identified: int = 0
    intents_detected: int = 0
    # Speech output
    speech_sessions: int = 0
    utterances_synthesized: int = 0
    # Fusion
    fusion_operations: int = 0
    # General
    error_count: int = 0
    total_processing_ms: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def avg_processing_ms(self) -> float:
        total_ops = (self.frames_processed + self.utterances_transcribed +
                     self.utterances_synthesized + self.fusion_operations)
        return round(self.total_processing_ms / max(1, total_ops), 2)


@dataclass
class PerceptionAuditEntry:
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    agent_type: str = ""
    operation: str = ""
    provider: str = "mock"
    success: bool = True
    confidence: float = 0.0
    processing_ms: float = 0.0
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
