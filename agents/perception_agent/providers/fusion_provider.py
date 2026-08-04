"""
FusionProvider — Abstract base class + DefaultFusionProvider for Phase 12.

Performs multimodal sensor fusion across vision, audio, language, and emotion.
No CLIP or GPU required by the default implementation.

Concrete providers:
  - DefaultFusionProvider : statistical feature fusion (CPU-safe, always available)
  - CLIPFusionProvider    : future — gated behind optional transformers install
"""
from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..models import (
    VisionResult,
    AudioResult,
    FusionResult,
    CrossModalCorrelation,
)

logger = logging.getLogger(__name__)


class FusionProvider(ABC):
    """Abstract multimodal fusion provider."""

    @abstractmethod
    def fuse(
        self,
        vision: Optional[VisionResult],
        audio: Optional[AudioResult],
        context: Optional[Dict[str, Any]] = None,
    ) -> FusionResult:
        """Fuse visual and audio modalities into a unified FusionResult."""

    @abstractmethod
    def assess_situation(self, fusion: FusionResult) -> Dict[str, Any]:
        """Produce a structured situation assessment from a FusionResult."""

    def provider_name(self) -> str:
        return self.__class__.__name__

    def is_available(self) -> bool:
        return True


class DefaultFusionProvider(FusionProvider):
    """
    Statistical multimodal fusion provider.
    CPU-safe, no torch or transformers required.
    Uses confidence-weighted feature aggregation and rule-based situation assessment.
    """

    # Situation labels derived from combined modality signals
    _SITUATION_RULES: List[Dict[str, Any]] = [
        {"label": "active_conversation", "requires": {"voice_activity": True, "face_present": True}},
        {"label": "speaker_only",        "requires": {"voice_activity": True, "face_present": False}},
        {"label": "silent_presence",     "requires": {"voice_activity": False, "face_present": True}},
        {"label": "environmental_noise", "requires": {"voice_activity": False, "face_present": False, "noise_high": True}},
        {"label": "idle",                "requires": {"voice_activity": False, "face_present": False, "noise_high": False}},
    ]

    def fuse(
        self,
        vision: Optional[VisionResult],
        audio: Optional[AudioResult],
        context: Optional[Dict[str, Any]] = None,
    ) -> FusionResult:
        start = time.time()
        ctx = context or {}
        session_id = ctx.get("session_id", "")

        visual_summary = self._summarize_vision(vision) if vision else {}
        audio_summary  = self._summarize_audio(audio) if audio else {}

        correlations = self._compute_correlations(vision, audio)
        situation    = self._determine_situation(visual_summary, audio_summary)
        events       = self._detect_events(visual_summary, audio_summary)
        env_desc     = self._describe_environment(visual_summary, audio_summary)

        v_conf = vision.overall_confidence if vision else 0.0
        a_conf = audio.overall_confidence  if audio  else 0.0
        agg_conf = (v_conf + a_conf) / max(1, sum(1 for c in [v_conf, a_conf] if c > 0))
        uncertainty = round(1.0 - agg_conf, 3)

        ms = round((time.time() - start) * 1000, 2)

        return FusionResult(
            session_id=session_id,
            provider=self.provider_name(),
            visual_summary=visual_summary,
            audio_summary=audio_summary,
            cross_modal_correlations=correlations,
            situation_label=situation["label"],
            situation_confidence=situation["confidence"],
            attention_focus=self._estimate_attention(visual_summary, audio_summary),
            detected_events=events,
            environment_understanding=env_desc,
            aggregate_confidence=round(agg_conf, 3),
            uncertainty=uncertainty,
            temporal_window_ms=ctx.get("temporal_window_ms", 1000.0),
            processing_ms=ms,
        )

    def assess_situation(self, fusion: FusionResult) -> Dict[str, Any]:
        return {
            "situation": fusion.situation_label,
            "confidence": fusion.situation_confidence,
            "attention_focus": fusion.attention_focus,
            "events": fusion.detected_events,
            "environment": fusion.environment_understanding,
            "aggregate_confidence": fusion.aggregate_confidence,
            "uncertainty": fusion.uncertainty,
        }

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _summarize_vision(self, vision: VisionResult) -> Dict[str, Any]:
        return {
            "object_count": len(vision.objects),
            "face_count": len(vision.faces),
            "face_present": len(vision.faces) > 0,
            "dominant_objects": [o.label for o in vision.objects[:3]],
            "scene": vision.scene_label,
            "scene_confidence": vision.scene_confidence,
            "motion_detected": vision.motion_detected,
            "ocr_text": vision.ocr_text,
            "confidence": vision.overall_confidence,
        }

    def _summarize_audio(self, audio: AudioResult) -> Dict[str, Any]:
        return {
            "voice_activity": audio.voice_activity,
            "transcription": audio.transcription,
            "language": audio.language,
            "speaker_id": audio.speaker_id,
            "emotion": audio.emotion,
            "intent": audio.intent,
            "keywords": audio.keywords_detected,
            "noise_level": audio.noise_level,
            "noise_high": audio.noise_level > 0.5,
            "confidence": audio.overall_confidence,
        }

    def _compute_correlations(
        self,
        vision: Optional[VisionResult],
        audio: Optional[AudioResult],
    ) -> List[CrossModalCorrelation]:
        correlations = []

        if vision and audio:
            # Vision-Audio correlation: both active → moderate alignment
            va_score = 0.0
            if vision.faces and audio.voice_activity:
                va_score = round((vision.overall_confidence + audio.overall_confidence) / 2, 3)
            correlations.append(CrossModalCorrelation(
                modalities=["vision", "audio"],
                correlation_score=va_score,
                temporal_offset_ms=0.0,
                aligned=va_score > 0.5,
            ))

            # Emotion correlation: visual emotion vs audio emotion
            v_emotions = {f.emotion for f in vision.faces}
            a_emotion = audio.emotion
            emotion_match = a_emotion in v_emotions or (not v_emotions and a_emotion == "neutral")
            correlations.append(CrossModalCorrelation(
                modalities=["vision_emotion", "audio_emotion"],
                correlation_score=0.85 if emotion_match else 0.40,
                temporal_offset_ms=50.0,
                aligned=emotion_match,
            ))

        return correlations

    def _determine_situation(
        self,
        visual: Dict[str, Any],
        audio: Dict[str, Any],
    ) -> Dict[str, Any]:
        signals = {
            "voice_activity": audio.get("voice_activity", False),
            "face_present":   visual.get("face_present", False),
            "noise_high":     audio.get("noise_high", False),
        }

        for rule in self._SITUATION_RULES:
            reqs = rule["requires"]
            if all(signals.get(k) == v for k, v in reqs.items()):
                v_conf = visual.get("confidence", 0.5)
                a_conf = audio.get("confidence", 0.5)
                return {"label": rule["label"], "confidence": round((v_conf + a_conf) / 2, 3)}

        return {"label": "unknown", "confidence": 0.4}

    def _detect_events(
        self,
        visual: Dict[str, Any],
        audio: Dict[str, Any],
    ) -> List[str]:
        events = []
        if visual.get("motion_detected"):
            events.append("motion_detected")
        if visual.get("face_present") and audio.get("voice_activity"):
            events.append("person_speaking")
        if audio.get("noise_high"):
            events.append("high_ambient_noise")
        if audio.get("keywords"):
            events.append(f"keywords_detected:{','.join(audio['keywords'][:3])}")
        return events

    def _estimate_attention(
        self,
        visual: Dict[str, Any],
        audio: Dict[str, Any],
    ) -> str:
        if visual.get("face_present") and audio.get("voice_activity"):
            return "person_speaking"
        if visual.get("face_present"):
            return "face"
        if audio.get("voice_activity"):
            return "audio_source"
        if visual.get("dominant_objects"):
            return visual["dominant_objects"][0]
        return "ambient"

    def _describe_environment(
        self,
        visual: Dict[str, Any],
        audio: Dict[str, Any],
    ) -> str:
        scene = visual.get("scene", "unknown")
        faces = visual.get("face_count", 0)
        noise = "noisy" if audio.get("noise_high") else "quiet"
        speech = "speech detected" if audio.get("voice_activity") else "no speech"
        return f"{scene} environment; {faces} person(s) visible; {noise}; {speech}."

    def provider_name(self) -> str:
        return "DefaultFusionProvider"
