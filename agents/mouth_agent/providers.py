"""
MouthAgent — TTS Provider Abstraction Layer (Phase 12).

All external TTS engines are accessed through TTSProvider.
No business logic depends on provider-specific APIs.

Providers:
  MockTTSProvider     — always available, zero dependencies
  Pyttsx3TTSProvider  — offline TTS via pyttsx3
  ElevenLabsProvider  — cloud TTS via ElevenLabs API
  GTTSProvider        — Google TTS (gTTS)
"""
from __future__ import annotations

import abc
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import pyttsx3 as _pyttsx3
    _HAS_PYTTSX3 = True
except ImportError:
    _HAS_PYTTSX3 = False
    _pyttsx3 = None  # type: ignore

try:
    from gtts import gTTS as _gTTS
    _HAS_GTTS = True
except ImportError:
    _HAS_GTTS = False
    _gTTS = None  # type: ignore


# ─── Provider Interface ───────────────────────────────────────────────────────

class TTSProvider(abc.ABC):
    """Abstract TTS provider — all concrete providers implement this."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    def synthesize(self, text: str, config: Dict[str, Any]) -> bytes:
        """
        Synthesize text to audio bytes (WAV/MP3).
        Returns empty bytes if synthesis is not possible.
        """

    @abc.abstractmethod
    def speak(self, text: str, config: Dict[str, Any]) -> bool:
        """
        Synthesize and play audio directly.
        Returns True on success.
        """


# ─── Mock Provider ────────────────────────────────────────────────────────────

class MockTTSProvider(TTSProvider):
    """Zero-dependency mock — always available."""

    @property
    def name(self) -> str:
        return "mock"

    @property
    def available(self) -> bool:
        return True

    def synthesize(self, text: str, config: Dict[str, Any]) -> bytes:
        return b""

    def speak(self, text: str, config: Dict[str, Any]) -> bool:
        logger.debug(f"MockTTSProvider.speak: '{text[:60]}'")
        return True


# ─── pyttsx3 Provider ─────────────────────────────────────────────────────────

class Pyttsx3TTSProvider(TTSProvider):
    """Offline TTS using pyttsx3."""

    def __init__(self, config: Dict[str, Any]):
        self._engine = None
        self._available = False
        if _HAS_PYTTSX3:
            try:
                self._engine = _pyttsx3.init()
                self._available = True
                logger.info("Pyttsx3TTSProvider: initialized")
            except Exception as e:
                logger.warning(f"Pyttsx3TTSProvider: init failed: {e}")

    @property
    def name(self) -> str:
        return "pyttsx3"

    @property
    def available(self) -> bool:
        return self._available

    def synthesize(self, text: str, config: Dict[str, Any]) -> bytes:
        # pyttsx3 doesn't easily return bytes — use speak() instead
        return b""

    def speak(self, text: str, config: Dict[str, Any]) -> bool:
        if not self._available or self._engine is None:
            return False
        try:
            rate = int(200 * float(config.get("speed", 1.0)))
            volume = float(config.get("volume", 1.0))
            self._engine.setProperty("rate", rate)
            self._engine.setProperty("volume", volume)

            # Voice gender selection
            gender = config.get("gender", "")
            if gender:
                voices = self._engine.getProperty("voices")
                for v in voices:
                    if gender.lower() in v.name.lower():
                        self._engine.setProperty("voice", v.id)
                        break

            self._engine.say(text)
            self._engine.runAndWait()
            return True
        except Exception as e:
            logger.error(f"Pyttsx3TTSProvider.speak: {e}")
            return False


# ─── gTTS Provider ────────────────────────────────────────────────────────────

class GTTSProvider(TTSProvider):
    """Google TTS via gTTS — requires internet."""

    def __init__(self, config: Dict[str, Any]):
        self._available = _HAS_GTTS
        if not self._available:
            logger.warning("GTTSProvider: gTTS not installed")

    @property
    def name(self) -> str:
        return "gtts"

    @property
    def available(self) -> bool:
        return self._available

    def synthesize(self, text: str, config: Dict[str, Any]) -> bytes:
        if not self._available:
            return b""
        try:
            import io
            lang = config.get("language", "en").split("-")[0]
            tts = _gTTS(text=text, lang=lang, slow=False)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            return buf.getvalue()
        except Exception as e:
            logger.error(f"GTTSProvider.synthesize: {e}")
            return b""

    def speak(self, text: str, config: Dict[str, Any]) -> bool:
        audio_bytes = self.synthesize(text, config)
        if not audio_bytes:
            return False
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                tmp = f.name
            if os.name == "nt":
                os.system(f'start /wait "" "{tmp}"')
            else:
                os.system(f"mpg123 -q '{tmp}' 2>/dev/null || afplay '{tmp}' 2>/dev/null")
            os.unlink(tmp)
            return True
        except Exception as e:
            logger.error(f"GTTSProvider.speak: {e}")
            return False


# ─── ElevenLabs Provider ──────────────────────────────────────────────────────

class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs cloud TTS — requires API key."""

    def __init__(self, config: Dict[str, Any]):
        self._available = False
        self._api_key = config.get("api_key", "")
        self._voice_id = config.get("voice_id", "Josh")
        self._model = config.get("model", "eleven_monolingual_v1")
        if self._api_key:
            try:
                import elevenlabs  # noqa: F401
                self._available = True
                logger.info("ElevenLabsTTSProvider: ready")
            except ImportError:
                logger.warning("ElevenLabsTTSProvider: elevenlabs package not installed")
        else:
            logger.warning("ElevenLabsTTSProvider: no API key configured")

    @property
    def name(self) -> str:
        return "elevenlabs"

    @property
    def available(self) -> bool:
        return self._available

    def synthesize(self, text: str, config: Dict[str, Any]) -> bytes:
        if not self._available:
            return b""
        try:
            from elevenlabs import generate, set_api_key
            set_api_key(self._api_key)
            audio = generate(
                text=text,
                voice=config.get("voice_id", self._voice_id),
                model=config.get("model", self._model),
            )
            return bytes(audio)
        except Exception as e:
            logger.error(f"ElevenLabsTTSProvider.synthesize: {e}")
            return b""

    def speak(self, text: str, config: Dict[str, Any]) -> bool:
        audio_bytes = self.synthesize(text, config)
        if not audio_bytes:
            return False
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                tmp = f.name
            if os.name == "nt":
                os.system(f'start /wait "" "{tmp}"')
            else:
                os.system(f"mpg123 -q '{tmp}' 2>/dev/null || afplay '{tmp}' 2>/dev/null")
            os.unlink(tmp)
            return True
        except Exception as e:
            logger.error(f"ElevenLabsTTSProvider.speak: {e}")
            return False


# ─── Registry & Factory ───────────────────────────────────────────────────────

_TTS_REGISTRY: Dict[str, type] = {
    "mock": MockTTSProvider,
    "pyttsx3": Pyttsx3TTSProvider,
    "gtts": GTTSProvider,
    "elevenlabs": ElevenLabsTTSProvider,
}


def build_tts_provider(name: str, config: Dict[str, Any]) -> TTSProvider:
    """
    Instantiate a TTS provider by name.
    Falls back through pyttsx3 → mock if the requested provider is unavailable.
    """
    cls = _TTS_REGISTRY.get(name.lower())
    if cls is None:
        logger.warning(f"TTSProvider '{name}' unknown — trying pyttsx3")
        name = "pyttsx3"
        cls = Pyttsx3TTSProvider

    try:
        provider = cls(config)
        if provider.available:
            logger.info(f"TTSProvider '{provider.name}' ready")
            return provider
    except Exception as e:
        logger.warning(f"TTSProvider '{name}' init error: {e}")

    # Fallback chain: pyttsx3 → mock
    if name != "pyttsx3":
        try:
            p = Pyttsx3TTSProvider(config)
            if p.available:
                logger.info("TTSProvider: fell back to pyttsx3")
                return p
        except Exception:
            pass

    logger.warning("TTSProvider: using mock (no TTS engine available)")
    return MockTTSProvider()
