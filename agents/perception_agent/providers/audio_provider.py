"""
AudioProvider — Abstract base class + Mock implementation for Phase 12.

Every concrete speech recognition backend (Whisper, Vosk, SpeechBrain,
DeepSpeech, Azure Speech) must implement `SpeechRecognitionProvider`.

Concrete providers delivered here:
  - MockSpeechRecognitionProvider : zero-hardware, deterministic stubs
"""
from __future__ import annotations

import uuid
import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..models import AudioResult

logger = logging.getLogger(__name__)


class SpeechRecognitionProvider(ABC):
    """Abstract audio / speech recognition provider."""

    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> AudioResult:
        """Transcribe audio bytes into text."""

    @abstractmethod
    def detect_language(self, audio_bytes: bytes) -> str:
        """Detect spoken language in audio."""

    @abstractmethod
    def detect_emotion(self, audio_bytes: bytes) -> Dict[str, float]:
        """Detect emotional tone in audio. Returns {emotion: score}."""

    @abstractmethod
    def identify_speaker(
        self,
        audio_bytes: bytes,
        known_profiles: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Identify speaker from audio. Returns speaker_id."""

    def provider_name(self) -> str:
        return self.__class__.__name__

    def is_available(self) -> bool:
        return True


class MockSpeechRecognitionProvider(SpeechRecognitionProvider):
    """
    Deterministic, zero-hardware speech recognition provider.
    Returns structured stubs suitable for all unit tests.
    """

    def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> AudioResult:
        start = time.time()
        ms = round((time.time() - start) * 1000 + 2.5, 2)
        return AudioResult(
            frame_id=str(uuid.uuid4()),
            provider=self.provider_name(),
            transcription="Hello, this is a mock transcription.",
            transcription_confidence=0.92,
            language=language or "en",
            language_confidence=0.95,
            speaker_id="speaker_0",
            speaker_confidence=0.80,
            emotion="neutral",
            emotion_scores={"neutral": 0.75, "calm": 0.20, "happy": 0.05},
            intent="greeting",
            intent_confidence=0.85,
            keywords_detected=["hello", "mock"],
            noise_level=0.12,
            voice_activity=True,
            overall_confidence=0.88,
            processing_ms=ms,
        )

    def detect_language(self, audio_bytes: bytes) -> str:
        return "en"

    def detect_emotion(self, audio_bytes: bytes) -> Dict[str, float]:
        return {"neutral": 0.75, "calm": 0.20, "happy": 0.05}

    def identify_speaker(
        self,
        audio_bytes: bytes,
        known_profiles: Optional[Dict[str, Any]] = None,
    ) -> str:
        return "speaker_0"

    def provider_name(self) -> str:
        return "MockSpeechRecognitionProvider"
