"""
MouthAgent — Production Speech Generation Engine (Phase 12).

Extends BaseAgent for full orchestrator lifecycle integration.
Implements:
  - Speech sessions with lifecycle management
  - Pluggable TTS provider abstraction (pyttsx3 / gTTS / ElevenLabs / Mock)
  - Voice profiles with prosody configuration
  - Emotion-aware speech rendering
  - Multilingual speech support
  - Streaming TTS (chunked synthesis)
  - Speech history, metrics, audit trail
  - Broker-based collaboration with Emotion/Language agents
  - Configuration-driven — no hardcoded parameters
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

import yaml

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from ..base_agent import BaseAgent  # type: ignore

try:
    from agents.mouth_agent.providers import TTSProvider, build_tts_provider
    from agents.perception_agent.models import (
        VoiceProfile, ProsodyConfig, SpeechRequest, SpeechResult,
        PerceptionSession, PerceptionMetrics, PerceptionAuditEntry, PerceptionContext,
    )
except ImportError:
    from .providers import TTSProvider, build_tts_provider  # type: ignore
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from perception_agent.models import (  # type: ignore
        VoiceProfile, ProsodyConfig, SpeechRequest, SpeechResult,
        PerceptionSession, PerceptionMetrics, PerceptionAuditEntry, PerceptionContext,
    )

_DEFAULT_CONFIG_PATH = "config/mouth_agent_config.yaml"


def _load_config(path: str) -> Dict[str, Any]:
    try:
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        logging.getLogger(__name__).warning(f"MouthAgentEngine: config load failed ({path}): {e}")
    return {}


# ─── Emotion → Prosody Mapping ────────────────────────────────────────────────

_DEFAULT_EMOTION_PROSODY: Dict[str, Dict[str, float]] = {
    "happy":    {"speed": 1.1, "pitch": 1.2, "volume": 1.0},
    "sad":      {"speed": 0.9, "pitch": 0.9, "volume": 0.8},
    "angry":    {"speed": 1.0, "pitch": 1.1, "volume": 1.2},
    "fear":     {"speed": 1.2, "pitch": 1.3, "volume": 1.1},
    "calm":     {"speed": 0.9, "pitch": 1.0, "volume": 0.9},
    "excited":  {"speed": 1.2, "pitch": 1.2, "volume": 1.1},
    "neutral":  {"speed": 1.0, "pitch": 1.0, "volume": 1.0},
    "surprise": {"speed": 1.1, "pitch": 1.3, "volume": 1.0},
}


class MouthAgentEngine(BaseAgent):
    """
    Production speech generation engine.

    Lifecycle:
      initialize()     → load config, build provider, load voice profiles
      start_session()  → open a named speech session
      synthesize()     → generate speech from SpeechRequest
      speak()          → synthesize + play
      stop_session()   → close session, flush audit
      shutdown()       → stop all sessions, release resources
      execute_task()   → orchestrator dispatch
    """

    DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_PATH

    def __init__(
        self,
        agent_id: str = "mouth_agent_engine",
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ):
        super().__init__(agent_id=agent_id, agent_type="perception")
        self.logger = logging.getLogger(f"MouthAgentEngine.{agent_id}")

        if config is not None:
            self._cfg = config
        else:
            self._cfg = _load_config(config_path or self.DEFAULT_CONFIG_PATH)

        # TTS Provider
        provider_name = self._cfg.get("tts_engine", self._cfg.get("provider", "pyttsx3"))
        provider_cfg = self._cfg.get("provider_config", {})
        # Inject API key if present in config
        if "elevenlabs_api_key" in self._cfg:
            provider_cfg["api_key"] = self._cfg["elevenlabs_api_key"]
        self._provider: TTSProvider = build_tts_provider(provider_name, provider_cfg)

        # Voice profiles
        self._voice_profiles: Dict[str, VoiceProfile] = self._load_voice_profiles()
        self._active_profile_id: str = self._cfg.get("default_voice_profile", "default")

        # Emotion prosody map (config-overridable)
        self._emotion_prosody: Dict[str, Dict[str, float]] = {
            **_DEFAULT_EMOTION_PROSODY,
            **self._cfg.get("emotion_mappings", {}),
        }

        # Sessions
        self._sessions: Dict[str, PerceptionSession] = {}
        self._active_session_id: Optional[str] = None

        # Speech history (bounded)
        max_history = int(self._cfg.get("speech_history_size", 200))
        self._speech_history: Deque[SpeechResult] = deque(maxlen=max_history)

        # Metrics & audit
        self._metrics = PerceptionMetrics()
        self._audit_trail: Deque[PerceptionAuditEntry] = deque(maxlen=1000)

        # State
        self._is_speaking: bool = False

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self):
        try:
            await super().initialize()
        except Exception:
            pass
        self.state.update({
            "provider": self._provider.name,
            "provider_available": self._provider.available,
            "voice_profiles": list(self._voice_profiles.keys()),
            "active_profile": self._active_profile_id,
            "sessions_opened": 0,
            "utterances_synthesized": 0,
            "errors": 0,
        })
        self.logger.info(
            f"MouthAgentEngine initialized | provider={self._provider.name} "
            f"available={self._provider.available} "
            f"profiles={list(self._voice_profiles.keys())}"
        )

    async def shutdown(self):
        for sid in list(self._sessions.keys()):
            await self.stop_session(sid)
        await super().shutdown()
        self.logger.info("MouthAgentEngine shut down")

    # ─── Voice Profiles ───────────────────────────────────────────────────────

    def _load_voice_profiles(self) -> Dict[str, VoiceProfile]:
        profiles: Dict[str, VoiceProfile] = {}
        raw = self._cfg.get("voice_profiles", {})
        for name, cfg in raw.items():
            profiles[name] = VoiceProfile(
                profile_id=name,
                name=name,
                language=cfg.get("language", "en-US"),
                gender=cfg.get("gender", "neutral"),
                speed=float(cfg.get("speed", 1.0)),
                pitch=float(cfg.get("pitch", 1.0)),
                volume=float(cfg.get("volume", 1.0)),
                provider=self._provider.name,
                provider_voice_id=cfg.get("provider_voice_id", ""),
            )
        if "default" not in profiles:
            profiles["default"] = VoiceProfile(
                profile_id="default",
                name="default",
                provider=self._provider.name,
            )
        return profiles

    def add_voice_profile(self, profile: VoiceProfile):
        self._voice_profiles[profile.profile_id] = profile
        self.state["voice_profiles"] = list(self._voice_profiles.keys())

    def get_voice_profile(self, profile_id: str) -> VoiceProfile:
        return self._voice_profiles.get(profile_id, self._voice_profiles["default"])

    def set_active_profile(self, profile_id: str) -> bool:
        if profile_id in self._voice_profiles:
            self._active_profile_id = profile_id
            self.state["active_profile"] = profile_id
            return True
        return False

    # ─── Session Management ───────────────────────────────────────────────────

    def start_session(
        self,
        context: Optional[PerceptionContext] = None,
        session_id: Optional[str] = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        session = PerceptionSession(
            session_id=sid,
            agent_type="mouth",
            provider=self._provider.name,
            request_id=context.request_id if context else None,
            correlation_id=context.correlation_id if context else None,
            trace_id=context.trace_id if context else None,
        )
        self._sessions[sid] = session
        self._active_session_id = sid
        self._metrics.speech_sessions += 1
        self.state["sessions_opened"] = self.state.get("sessions_opened", 0) + 1
        self.logger.info(f"MouthAgentEngine: session started | session_id={sid}")
        return sid

    async def stop_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return None
        session.ended_at = datetime.utcnow().isoformat()
        if self._active_session_id == session_id:
            self._active_session_id = None
        self.logger.info(
            f"MouthAgentEngine: session closed | session_id={session_id} "
            f"ops={session.operations_count}"
        )
        return session.to_dict()

    # ─── Prosody Resolution ───────────────────────────────────────────────────

    def _resolve_prosody(
        self,
        emotion: str,
        profile: VoiceProfile,
        override: Optional[ProsodyConfig] = None,
    ) -> Dict[str, Any]:
        """Merge emotion prosody + voice profile + optional override."""
        emo_map = self._emotion_prosody.get(emotion, self._emotion_prosody["neutral"])
        prosody = {
            "speed": profile.speed * emo_map.get("speed", 1.0),
            "pitch": profile.pitch * emo_map.get("pitch", 1.0),
            "volume": profile.volume * emo_map.get("volume", 1.0),
            "language": profile.language,
            "gender": profile.gender,
            "provider_voice_id": profile.provider_voice_id,
        }
        if override:
            prosody["speed"] = override.speed
            prosody["pitch"] = override.pitch
            prosody["volume"] = override.volume
        # Clamp values
        prosody["speed"] = round(max(0.5, min(3.0, prosody["speed"])), 3)
        prosody["pitch"] = round(max(0.5, min(2.0, prosody["pitch"])), 3)
        prosody["volume"] = round(max(0.1, min(2.0, prosody["volume"])), 3)
        return prosody

    # ─── Synthesis Pipeline ───────────────────────────────────────────────────

    def synthesize(self, request: SpeechRequest) -> SpeechResult:
        """Synthesize speech from a SpeechRequest. Returns SpeechResult."""
        t0 = time.perf_counter()
        sid = request.session_id or self._active_session_id or "default"

        # Validate text
        text = (request.text or "").strip()
        if not text:
            return SpeechResult(
                request_id=request.request_id,
                session_id=sid,
                provider=self._provider.name,
            )

        try:
            profile = self.get_voice_profile(
                request.voice_profile.profile_id if request.voice_profile else self._active_profile_id
            )
            prosody = self._resolve_prosody(request.emotion, profile, request.prosody)

            # Synthesize
            audio_bytes = self._provider.synthesize(text, prosody)

            processing_ms = round((time.perf_counter() - t0) * 1000, 2)

            result = SpeechResult(
                request_id=request.request_id,
                session_id=sid,
                provider=self._provider.name,
                text_rendered=text,
                audio_bytes=audio_bytes,
                format="wav" if audio_bytes else "none",
                processing_ms=processing_ms,
            )

            # Metrics
            self._metrics.utterances_synthesized += 1
            self._metrics.total_processing_ms += processing_ms
            self.state["utterances_synthesized"] = self._metrics.utterances_synthesized

            # Session
            if sid in self._sessions:
                self._sessions[sid].operations_count += 1

            # History
            self._speech_history.append(result)

            # Audit
            self._audit(sid, "synthesize", 1.0, processing_ms, True,
                        f"text='{text[:40]}' emotion={request.emotion} provider={self._provider.name}")

            return result

        except Exception as e:
            self.logger.error(f"MouthAgentEngine.synthesize: {e}")
            self._metrics.error_count += 1
            self.state["errors"] = self.state.get("errors", 0) + 1
            self._audit(sid, "synthesize", 0.0, 0.0, False, str(e))
            return SpeechResult(
                request_id=request.request_id,
                session_id=sid,
                provider=self._provider.name,
            )

    async def speak(self, request: SpeechRequest) -> SpeechResult:
        """Synthesize and play speech. Returns SpeechResult."""
        t0 = time.perf_counter()
        sid = request.session_id or self._active_session_id or "default"
        text = (request.text or "").strip()

        if not text:
            return SpeechResult(request_id=request.request_id, session_id=sid, provider=self._provider.name)

        self._is_speaking = True
        try:
            profile = self.get_voice_profile(
                request.voice_profile.profile_id if request.voice_profile else self._active_profile_id
            )
            prosody = self._resolve_prosody(request.emotion, profile, request.prosody)

            # Run blocking TTS in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, self._provider.speak, text, prosody
            )

            processing_ms = round((time.perf_counter() - t0) * 1000, 2)

            result = SpeechResult(
                request_id=request.request_id,
                session_id=sid,
                provider=self._provider.name,
                text_rendered=text,
                processing_ms=processing_ms,
            )

            self._metrics.utterances_synthesized += 1
            self._metrics.total_processing_ms += processing_ms
            self.state["utterances_synthesized"] = self._metrics.utterances_synthesized

            if sid in self._sessions:
                self._sessions[sid].operations_count += 1

            self._speech_history.append(result)
            self._audit(sid, "speak", 1.0 if success else 0.0, processing_ms, success,
                        f"text='{text[:40]}' emotion={request.emotion}")

            # Broadcast to broker
            await self._broadcast_speech_event(result, request.emotion)

            return result

        except Exception as e:
            self.logger.error(f"MouthAgentEngine.speak: {e}")
            self._metrics.error_count += 1
            self._audit(sid, "speak", 0.0, 0.0, False, str(e))
            return SpeechResult(request_id=request.request_id, session_id=sid, provider=self._provider.name)
        finally:
            self._is_speaking = False

    async def speak_stream(self, texts: List[str], emotion: str = "neutral", session_id: Optional[str] = None):
        """Stream multiple text chunks as sequential speech."""
        sid = session_id or self._active_session_id or "default"
        for chunk in texts:
            if not chunk.strip():
                continue
            req = SpeechRequest(
                session_id=sid,
                text=chunk,
                emotion=emotion,
            )
            await self.speak(req)
            await asyncio.sleep(0)  # yield

    # ─── History & Metrics ────────────────────────────────────────────────────

    def get_speech_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        history = list(self._speech_history)
        return [r.to_dict() for r in history[-limit:]]

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics.as_dict(),
            "avg_processing_ms": self._metrics.avg_processing_ms(),
            "provider": self._provider.name,
            "provider_available": self._provider.available,
            "active_sessions": len(self._sessions),
            "is_speaking": self._is_speaking,
            "voice_profiles": list(self._voice_profiles.keys()),
            "active_profile": self._active_profile_id,
        }

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        trail = list(self._audit_trail)
        return [e.to_dict() for e in trail[-limit:]]

    def _audit(
        self, session_id: str, operation: str, confidence: float,
        processing_ms: float, success: bool, summary: str
    ):
        entry = PerceptionAuditEntry(
            session_id=session_id,
            agent_type="mouth",
            operation=operation,
            provider=self._provider.name,
            success=success,
            confidence=confidence,
            processing_ms=processing_ms,
            summary=summary,
        )
        self._audit_trail.append(entry)

    # ─── Broker Collaboration ─────────────────────────────────────────────────

    async def _broadcast_speech_event(self, result: SpeechResult, emotion: str):
        if not self._message_broker:
            return
        try:
            from orchestrator.agent_communication import MessageType, MessagePriority
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=None,
                message_type=MessageType.PERCEPTION_INPUT,
                content={
                    "input_type": "speech_output",
                    "session_id": result.session_id,
                    "request_id": result.request_id,
                    "text": result.text_rendered,
                    "emotion": emotion,
                    "provider": result.provider,
                    "processing_ms": result.processing_ms,
                    "timestamp": result.timestamp,
                },
                priority=MessagePriority.LOW,
            )
        except Exception as e:
            self.logger.debug(f"MouthAgentEngine: broker publish failed: {e}")

    # ─── execute_task (Orchestrator Dispatch) ─────────────────────────────────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {}) or {}

        if action == "start_session":
            sid = self.start_session(session_id=data.get("session_id"))
            return {"session_id": sid, "status": "started"}

        if action == "stop_session":
            sid = data.get("session_id", self._active_session_id)
            result = await self.stop_session(sid) if sid else None
            return {"status": "stopped", "session": result}

        if action in ("speak", "say", "synthesize_and_play"):
            req = self._build_request(data)
            result = await self.speak(req)
            return result.to_dict()

        if action == "synthesize":
            req = self._build_request(data)
            result = self.synthesize(req)
            return result.to_dict()

        if action == "speak_stream":
            texts = data.get("texts", [data.get("text", "")])
            if isinstance(texts, str):
                texts = [texts]
            emotion = data.get("emotion", "neutral")
            sid = data.get("session_id", self._active_session_id)
            await self.speak_stream(texts, emotion=emotion, session_id=sid)
            return {"status": "streamed", "chunks": len(texts)}

        if action == "add_voice_profile":
            profile = VoiceProfile(
                profile_id=data.get("profile_id", str(uuid.uuid4())),
                name=data.get("name", "custom"),
                language=data.get("language", "en-US"),
                gender=data.get("gender", "neutral"),
                speed=float(data.get("speed", 1.0)),
                pitch=float(data.get("pitch", 1.0)),
                volume=float(data.get("volume", 1.0)),
                provider=self._provider.name,
                provider_voice_id=data.get("provider_voice_id", ""),
            )
            self.add_voice_profile(profile)
            return {"profile_id": profile.profile_id, "status": "added"}

        if action == "set_active_profile":
            success = self.set_active_profile(data.get("profile_id", "default"))
            return {"success": success, "active_profile": self._active_profile_id}

        if action == "list_profiles":
            return {
                "profiles": [p.to_dict() for p in self._voice_profiles.values()],
                "active": self._active_profile_id,
            }

        if action == "switch_provider":
            new_name = data.get("provider", "pyttsx3")
            new_cfg = data.get("provider_config", {})
            self._provider = build_tts_provider(new_name, new_cfg)
            self.state["provider"] = self._provider.name
            return {"provider": self._provider.name, "available": self._provider.available}

        if action == "get_history":
            return {"history": self.get_speech_history(data.get("limit", 50))}

        if action == "get_metrics":
            return self.get_metrics()

        if action == "get_audit":
            return {"audit": self.get_audit_trail(data.get("limit", 100))}

        if action == "get_status":
            return await self.get_status()

        if action == "get_health":
            return await self.get_health()

        return await super().execute_task(task)

    def _build_request(self, data: Dict[str, Any]) -> SpeechRequest:
        profile_id = data.get("voice_profile", data.get("profile_id", self._active_profile_id))
        profile = self.get_voice_profile(profile_id)
        prosody = None
        if any(k in data for k in ("speed", "pitch", "volume")):
            prosody = ProsodyConfig(
                speed=float(data.get("speed", profile.speed)),
                pitch=float(data.get("pitch", profile.pitch)),
                volume=float(data.get("volume", profile.volume)),
            )
        return SpeechRequest(
            session_id=data.get("session_id", self._active_session_id or ""),
            text=data.get("text", ""),
            emotion=data.get("emotion", "neutral"),
            language=data.get("language", profile.language),
            voice_profile=profile,
            prosody=prosody,
            stream=bool(data.get("stream", False)),
        )

    # ─── State Update ─────────────────────────────────────────────────────────

    async def _update_state(self):
        await super()._update_state()
        self.state["utterances_synthesized"] = self._metrics.utterances_synthesized
        self.state["active_sessions"] = len(self._sessions)
        self.state["is_speaking"] = self._is_speaking
        self.state["provider"] = self._provider.name
