"""
TTSProvider — Abstract base class + Mock implementation for Phase 12.

Every concrete TTS backend (pyttsx3, Coqui TTS, ElevenLabs, Azure TTS,
Google TTS) must implement `TTSProvider`.

Concrete providers delivered here:
  - MockTTSProvider : zero-hardware, deterministic stubs
"""
from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Optional

from ..models import SpeechRequest, SpeechResult, VoiceProfile

logger = logging.getLogger(__name__)


class TTSProvider(ABC):
    """Abstract Text-to-Speech provider."""

    @abstractmethod
    def synthesize(self, request: SpeechRequest) -> SpeechResult:
        """Synthesize speech from a SpeechRequest. Returns audio bytes."""

    @abstractmethod
    def list_voices(self) -> List[VoiceProfile]:
        """List available voice profiles for this provider."""

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Return True if the provider supports streaming synthesis."""

    async def synthesize_stream(
        self,
        request: SpeechRequest,
        chunk_size_ms: int = 200,
    ) -> AsyncGenerator[bytes, None]:
        """
        Async generator for streaming TTS output.
        Default fallback: synthesize fully then yield as single chunk.
        Override in providers that support true streaming.
        """
        result = self.synthesize(request)
        yield result.audio_bytes

    def provider_name(self) -> str:
        return self.__class__.__name__

    def is_available(self) -> bool:
        return True


class MockTTSProvider(TTSProvider):
    """
    Deterministic, zero-hardware TTS provider.
    Returns empty audio bytes and structured metadata — suitable for all tests.
    """

    _VOICES = [
        VoiceProfile(name="default_en", language="en-US", gender="neutral"),
        VoiceProfile(name="default_hi", language="hi-IN", gender="neutral"),
        VoiceProfile(name="default_es", language="es-ES", gender="neutral"),
    ]

    def synthesize(self, request: SpeechRequest) -> SpeechResult:
        start = time.time()
        # Simulate ~10ms per 100 chars
        sim_ms = max(5.0, len(request.text) * 0.1)
        ms = round((time.time() - start) * 1000 + sim_ms, 2)
        return SpeechResult(
            request_id=request.request_id,
            session_id=request.session_id,
            provider=self.provider_name(),
            text_rendered=request.text,
            audio_bytes=b"",          # No actual audio in mock
            duration_ms=sim_ms * 2,   # ~20ms audio per 100 chars
            format="wav",
            processing_ms=ms,
        )

    def list_voices(self) -> List[VoiceProfile]:
        return list(self._VOICES)

    def supports_streaming(self) -> bool:
        return True

    async def synthesize_stream(
        self,
        request: SpeechRequest,
        chunk_size_ms: int = 200,
    ) -> AsyncGenerator[bytes, None]:
        yield b""   # Empty audio chunk

    def provider_name(self) -> str:
        return "MockTTSProvider"
