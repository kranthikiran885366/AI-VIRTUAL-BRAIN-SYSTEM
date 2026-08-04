"""
Production MouthAgent — Phase 12.

Full lifecycle integration with BaseAgent orchestrator.
Provider-abstracted TTS pipeline: no hard dependency on pyttsx3/espeak/coqui.
All synthesis goes through TTSProvider interface.

Task dispatch actions:
  speak               — synthesize and store speech result
  synthesize          — synthesize text without speaking (returns bytes)
  say_thought         — convert thought dict to speech
  respond             — generate contextual speech response
  list_voices         — list available voice profiles
  set_voice           — select voice profile by name
  set_language        — set default language
  get_supported_languages — list supported languages
  get_history         — recent speech outputs
  get_metrics         — operational metrics
  get_status          — agent status
  get_health          — health check
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from ..base_agent import BaseAgent  # type: ignore

try:
    from agents.perception_agent.models import (
        SpeechRequest, SpeechResult, VoiceProfile, ProsodyConfig,
        PerceptionSession, PerceptionMetrics, PerceptionAuditEntry,
    )
    from agents.perception_agent.providers.tts_provider import (
        TTSProvider, MockTTSProvider,
    )
except ImportError:
    from ..perception_agent.models import (  # type: ignore
        SpeechRequest, SpeechResult, VoiceProfile, ProsodyConfig,
        PerceptionSession, PerceptionMetrics, PerceptionAuditEntry,
    )
    from ..perception_agent.providers.tts_provider import (  # type: ignore
        TTSProvider, MockTTSProvider,
    )


# Default emotion → prosody mapping (configuration-driven in production)
_EMOTION_PROSODY: Dict[str, Dict[str, float]] = {
    "happy":    {"pitch": 1.15, "speed": 1.10, "volume": 1.05},
    "sad":      {"pitch": 0.88, "speed": 0.88, "volume": 0.90},
    "angry":    {"pitch": 1.10, "speed": 1.20, "volume": 1.15},
    "fearful":  {"pitch": 1.05, "speed": 1.15, "volume": 0.95},
    "calm":     {"pitch": 0.95, "speed": 0.92, "volume": 0.95},
    "excited":  {"pitch": 1.20, "speed": 1.25, "volume": 1.10},
    "neutral":  {"pitch": 1.00, "speed": 1.00, "volume": 1.00},
}


class MouthAgent(BaseAgent):
    """
    Production Speech Generation Agent.

    Wraps TTSProvider for hardware-agnostic speech synthesis.
    Falls back to MockTTSProvider when no real provider is configured.
    """

    DEFAULT_MAX_HISTORY = 200
    DEFAULT_LANGUAGE    = "en-US"

    def __init__(
        self,
        agent_id: str = "mouth_agent",
        config: Optional[Dict[str, Any]] = None,
        tts_provider: Optional[TTSProvider] = None,
    ):
        super().__init__(agent_id=agent_id, agent_type="speech")
        self.config = config or {}
        self._tts_provider: TTSProvider = tts_provider or MockTTSProvider()

        self._current_language: str = self.config.get("default_language", self.DEFAULT_LANGUAGE)
        self._current_voice_name: str = self.config.get("default_voice", "default_en")
        self._current_emotion: str = "neutral"
        self._is_speaking: bool = False

        self._speech_history: Deque[Dict[str, Any]] = deque(
            maxlen=self.config.get("max_history", self.DEFAULT_MAX_HISTORY)
        )
        self._audit_log: Deque[PerceptionAuditEntry] = deque(maxlen=500)
        self.metrics = PerceptionMetrics()
        self._active_sessions: Dict[str, PerceptionSession] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialize(self):
        try:
            await super().initialize()
        except Exception:
            pass
        if not hasattr(self, "logger") or self.logger is None:
            self.logger = logging.getLogger(f"MouthAgent.{self.agent_id}")

        self.state.update({
            "provider": self._tts_provider.provider_name(),
            "current_language": self._current_language,
            "current_voice": self._current_voice_name,
            "utterances_synthesized": 0,
            "is_speaking": False,
        })
        self.logger.info(
            f"MouthAgent '{self.agent_id}' initialized — "
            f"provider: {self._tts_provider.provider_name()}"
        )

    async def _update_state(self):
        try:
            await super()._update_state()
        except Exception:
            pass
        self.state["utterances_synthesized"] = self.metrics.utterances_synthesized
        self.state["is_speaking"] = self._is_speaking

    async def shutdown(self):
        self._active_sessions.clear()
        self.logger.info(f"MouthAgent '{self.agent_id}' shut down.")

    # ── Provider ──────────────────────────────────────────────────────────────

    def set_provider(self, provider: TTSProvider) -> None:
        """Hot-swap the TTS provider at runtime."""
        self._tts_provider = provider
        self.logger.info(f"MouthAgent: TTS provider set to {provider.provider_name()}")

    # ── Session Management ────────────────────────────────────────────────────

    def _start_session(self, req_id=None, corr_id=None, tr_id=None) -> PerceptionSession:
        session = PerceptionSession(
            agent_type="mouth",
            request_id=req_id,
            correlation_id=corr_id,
            trace_id=tr_id,
            provider=self._tts_provider.provider_name(),
        )
        self._active_sessions[session.session_id] = session
        self.metrics.speech_sessions += 1
        return session

    # ── Prosody Helpers ───────────────────────────────────────────────────────

    def _emotion_to_prosody(self, emotion: str) -> ProsodyConfig:
        e_map = _EMOTION_PROSODY.get(emotion, _EMOTION_PROSODY["neutral"])
        return ProsodyConfig(
            speed=e_map.get("speed", 1.0),
            pitch=e_map.get("pitch", 1.0),
            volume=e_map.get("volume", 1.0),
        )

    def _resolve_voice_profile(self, language: str) -> VoiceProfile:
        available = self._tts_provider.list_voices()
        for v in available:
            if v.language == language:
                return v
        return available[0] if available else VoiceProfile(language=language)

    # ── Core Synthesis ────────────────────────────────────────────────────────

    def synthesize(
        self,
        text: str,
        emotion: str = "neutral",
        language: Optional[str] = None,
        session_id: str = "",
        stream: bool = False,
    ) -> SpeechResult:
        """Synthesize speech and record to history."""
        start = time.time()
        lang = language or self._current_language
        voice = self._resolve_voice_profile(lang)
        prosody = self._emotion_to_prosody(emotion)

        request = SpeechRequest(
            session_id=session_id,
            text=text,
            emotion=emotion,
            language=lang,
            voice_profile=voice,
            prosody=prosody,
            stream=stream,
        )

        try:
            self._is_speaking = True
            result = self._tts_provider.synthesize(request)
            result.session_id = session_id
        except Exception as exc:
            self.logger.error(f"MouthAgent.synthesize error: {exc}")
            self.metrics.error_count += 1
            result = SpeechResult(
                session_id=session_id,
                provider="error",
                text_rendered=text,
            )
        finally:
            self._is_speaking = False

        ms = round((time.time() - start) * 1000, 2)
        self.metrics.utterances_synthesized += 1
        self.metrics.total_processing_ms += ms
        self._current_emotion = emotion

        self._speech_history.append({
            "session_id": session_id,
            "text": text[:120],
            "emotion": emotion,
            "language": lang,
            "voice": voice.name,
            "duration_ms": result.duration_ms,
            "processing_ms": ms,
            "timestamp": result.timestamp,
        })
        self._audit_log.append(PerceptionAuditEntry(
            session_id=session_id,
            agent_type="mouth",
            operation="synthesize",
            provider=self._tts_provider.provider_name(),
            success=True,
            processing_ms=ms,
            summary=f"text_len={len(text)}, emotion={emotion}, lang={lang}",
        ))
        return result

    async def speak(
        self,
        text: str,
        emotion: Optional[str] = None,
        language: Optional[str] = None,
    ) -> SpeechResult:
        """Async speak — maintains backward compatibility with original MouthAgent.speak() signature."""
        emo = emotion or self._current_emotion or "neutral"
        session = self._start_session()
        return self.synthesize(text, emo, language, session.session_id)

    # ── execute_task (Orchestrator Contract) ──────────────────────────────────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action  = (task.get("action", "") or "").lower()
        data    = task.get("input_data", {}) or {}
        req_id  = task.get("request_id") or data.get("request_id")
        corr_id = task.get("correlation_id") or data.get("correlation_id")
        tr_id   = task.get("trace_id") or data.get("trace_id")

        session = self._start_session(req_id, corr_id, tr_id)
        sid = session.session_id

        text     = data.get("text", data.get("content", ""))
        emotion  = data.get("emotion", "neutral")
        language = data.get("language", self._current_language)

        if action in ("speak", "say", "synthesize", "generate_speech"):
            result = self.synthesize(text, emotion, language, sid)
            return {**result.to_dict(), "session_id": sid}

        if action == "say_thought":
            thought = data.get("thought", {})
            text    = thought.get("content", thought.get("text", str(thought)))
            emotion = thought.get("emotion", "neutral")
            result  = self.synthesize(text, emotion, language, sid)
            return {**result.to_dict(), "session_id": sid}

        if action == "respond":
            ctx_text = data.get("response", data.get("text", "I understand."))
            result   = self.synthesize(ctx_text, emotion, language, sid)
            return {**result.to_dict(), "session_id": sid}

        if action == "list_voices":
            voices = self._tts_provider.list_voices()
            return {"voices": [v.to_dict() for v in voices]}

        if action == "set_voice":
            self._current_voice_name = data.get("voice_name", self._current_voice_name)
            return {"status": "ok", "voice": self._current_voice_name}

        if action == "set_language":
            lang_code = data.get("language", data.get("language_code", "en-US"))
            self._current_language = lang_code
            return {"status": "ok", "language": self._current_language}

        if action == "get_supported_languages":
            voices = self._tts_provider.list_voices()
            langs = list({v.language for v in voices})
            return {"languages": langs}

        if action == "get_history":
            limit = data.get("limit", 20)
            history = list(self._speech_history)[-limit:]
            return {"history": history, "total": self.metrics.utterances_synthesized}

        if action == "get_metrics":
            return {"metrics": self.metrics.as_dict()}

        if action == "get_status":
            return await self.get_status()

        if action == "get_health":
            return await self.get_health()

        # Default: speak
        if text:
            result = self.synthesize(text, emotion, language, sid)
            return {**result.to_dict(), "session_id": sid}

        return {"error": "No action or text provided"}

    # ── Health ────────────────────────────────────────────────────────────────

    async def get_health(self) -> Dict[str, Any]:
        return {
            "healthy": True,
            "agent_id": self.agent_id,
            "provider": self._tts_provider.provider_name(),
            "provider_available": self._tts_provider.is_available(),
            "utterances_synthesized": self.metrics.utterances_synthesized,
            "error_count": self.metrics.error_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
