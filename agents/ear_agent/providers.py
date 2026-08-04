"""
EarAgent — Audio Provider Abstraction Layer (Phase 12).

All external audio/speech models are accessed through provider interfaces.
No business logic depends on provider-specific APIs.

Providers:
  MockAudioProvider        — always available, zero dependencies
  WhisperAudioProvider     — faster-whisper / openai-whisper
  Wav2Vec2AudioProvider    — HuggingFace transformers
  EnergyFallbackProvider   — energy + ZCR heuristic (no ML)
"""
from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None  # type: ignore


# ─── Provider Interfaces ──────────────────────────────────────────────────────

class SpeechRecognitionProvider(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    def transcribe(self, audio, sample_rate: int, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return {text, confidence, language, backend}."""


class SpeakerRecognitionProvider(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    def identify(self, audio, sample_rate: int, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return {speaker_id, name, confidence}."""

    @abc.abstractmethod
    def enroll(self, speaker_id: str, name: str, samples: List, config: Dict[str, Any]) -> bool:
        """Enroll a new speaker. Return True on success."""


class AudioEmotionProvider(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    def detect_emotion(self, audio, sample_rate: int, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return {emotion, confidence, scores:{emotion:float}}."""


# ─── Mock Providers ───────────────────────────────────────────────────────────

class MockSpeechProvider(SpeechRecognitionProvider):
    @property
    def name(self) -> str:
        return "mock"

    @property
    def available(self) -> bool:
        return True

    def transcribe(self, audio, sample_rate: int, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"text": "", "confidence": 0.0, "language": "en", "backend": "mock"}


class MockSpeakerProvider(SpeakerRecognitionProvider):
    def __init__(self):
        self._speakers: Dict[str, str] = {}

    @property
    def name(self) -> str:
        return "mock"

    @property
    def available(self) -> bool:
        return True

    def identify(self, audio, sample_rate: int, config: Dict[str, Any]) -> Dict[str, Any]:
        return {"speaker_id": "unknown", "name": "unknown", "confidence": 0.0}

    def enroll(self, speaker_id: str, name: str, samples: List, config: Dict[str, Any]) -> bool:
        self._speakers[speaker_id] = name
        return True


class MockAudioEmotionProvider(AudioEmotionProvider):
    @property
    def name(self) -> str:
        return "mock"

    @property
    def available(self) -> bool:
        return True

    def detect_emotion(self, audio, sample_rate: int, config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "emotion": "neutral",
            "confidence": 0.0,
            "scores": {"neutral": 1.0},
        }


# ─── Whisper Provider ─────────────────────────────────────────────────────────

class WhisperSpeechProvider(SpeechRecognitionProvider):
    def __init__(self, config: Dict[str, Any]):
        self._model = None
        self._available = False
        model_size = config.get("whisper_model_size", "tiny")
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(model_size, device="auto", compute_type="int8")
            self._available = True
            logger.info(f"WhisperSpeechProvider: loaded model '{model_size}'")
        except Exception as e:
            logger.warning(f"WhisperSpeechProvider: load failed: {e}")

    @property
    def name(self) -> str:
        return "whisper"

    @property
    def available(self) -> bool:
        return self._available

    def transcribe(self, audio, sample_rate: int, config: Dict[str, Any]) -> Dict[str, Any]:
        if not self._available or not _HAS_NUMPY:
            return {"text": "", "confidence": 0.0, "language": "en", "backend": "whisper"}
        try:
            audio_f32 = audio.astype(np.float32) / 32768.0
            language = config.get("language", None)
            segments, info = self._model.transcribe(
                audio_f32,
                language=language if language and language != "auto" else None,
                beam_size=int(config.get("beam_size", 5)),
                vad_filter=bool(config.get("vad_filter", True)),
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            return {
                "text": text,
                "confidence": 0.85,
                "language": info.language or "en",
                "backend": "whisper",
            }
        except Exception as e:
            logger.error(f"WhisperSpeechProvider.transcribe: {e}")
            return {"text": "", "confidence": 0.0, "language": "en", "backend": "whisper", "error": str(e)}


# ─── Energy Fallback Provider ─────────────────────────────────────────────────

class EnergyFallbackSpeechProvider(SpeechRecognitionProvider):
    """Pure-Python energy + ZCR heuristic — no ML required."""

    @property
    def name(self) -> str:
        return "energy_fallback"

    @property
    def available(self) -> bool:
        return True

    def transcribe(self, audio, sample_rate: int, config: Dict[str, Any]) -> Dict[str, Any]:
        if audio is None or (hasattr(audio, "__len__") and len(audio) == 0):
            return {"text": "[silence]", "confidence": 0.9, "language": "en", "backend": "energy_fallback"}

        silence_threshold = float(config.get("silence_threshold", 0.01))
        noise_threshold = float(config.get("noise_threshold", 0.05))

        if _HAS_NUMPY:
            audio_f32 = audio.astype(float) / 32768.0
            rms = float(np.sqrt(np.mean(audio_f32 ** 2)))
        else:
            vals = [float(x) / 32768.0 for x in audio]
            rms = (sum(x * x for x in vals) / max(1, len(vals))) ** 0.5

        if rms < silence_threshold:
            return {"text": "[silence]", "confidence": 0.92, "language": "en", "backend": "energy_fallback"}
        if rms < noise_threshold:
            return {"text": "[noise]", "confidence": 0.70, "language": "en", "backend": "energy_fallback"}
        return {
            "text": "[speech detected — install faster-whisper for transcription]",
            "confidence": 0.55,
            "language": "en",
            "backend": "energy_fallback",
        }


# ─── Registries & Factories ───────────────────────────────────────────────────

def build_speech_provider(name: str, config: Dict[str, Any]) -> SpeechRecognitionProvider:
    if name == "whisper":
        p = WhisperSpeechProvider(config)
        if p.available:
            return p
        logger.warning("WhisperSpeechProvider unavailable — using energy fallback")
    if name in ("energy", "energy_fallback", "mock"):
        return EnergyFallbackSpeechProvider()
    logger.warning(f"SpeechProvider '{name}' unknown — using energy fallback")
    return EnergyFallbackSpeechProvider()


def build_speaker_provider(name: str, config: Dict[str, Any]) -> SpeakerRecognitionProvider:
    # Resemblyzer / SpeechBrain can be added here as concrete providers
    return MockSpeakerProvider()


def build_audio_emotion_provider(name: str, config: Dict[str, Any]) -> AudioEmotionProvider:
    return MockAudioEmotionProvider()
