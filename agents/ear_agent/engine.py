"""
EarAgent — Production Audio Intelligence Engine (Phase 12).

Extends BaseAgent for full orchestrator lifecycle integration.
Implements:
  - Audio sessions with lifecycle management
  - Pluggable provider abstraction (Whisper / Wav2Vec2 / Energy fallback)
  - Full audio pipeline: VAD → transcription → speaker ID → emotion → intent → language
  - Streaming audio support with bounded buffers
  - Audio history, metrics, audit trail
  - Broker-based collaboration with Memory/Emotion/Language agents
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
    from agents.ear_agent.providers import (
        SpeechRecognitionProvider, SpeakerRecognitionProvider, AudioEmotionProvider,
        build_speech_provider, build_speaker_provider, build_audio_emotion_provider,
    )
    from agents.perception_agent.models import (
        AudioFrame, AudioResult, PerceptionSession, PerceptionMetrics,
        PerceptionAuditEntry, PerceptionContext,
    )
except ImportError:
    from .providers import (  # type: ignore
        SpeechRecognitionProvider, SpeakerRecognitionProvider, AudioEmotionProvider,
        build_speech_provider, build_speaker_provider, build_audio_emotion_provider,
    )
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from perception_agent.models import (  # type: ignore
        AudioFrame, AudioResult, PerceptionSession, PerceptionMetrics,
        PerceptionAuditEntry, PerceptionContext,
    )

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None  # type: ignore

_DEFAULT_CONFIG_PATH = "config/ear_agent_config.yaml"


def _load_config(path: str) -> Dict[str, Any]:
    try:
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        logging.getLogger(__name__).warning(f"EarAgentEngine: config load failed ({path}): {e}")
    return {}


class EarAgentEngine(BaseAgent):
    """
    Production audio intelligence engine.

    Lifecycle:
      initialize()      → load config, build providers, register with broker
      start_session()   → open a named audio session
      process_audio()   → run full audio pipeline on a raw audio chunk
      stop_session()    → close session, flush audit
      shutdown()        → stop all sessions, release resources
      execute_task()    → orchestrator dispatch
    """

    DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_PATH

    def __init__(
        self,
        agent_id: str = "ear_agent_engine",
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ):
        super().__init__(agent_id=agent_id, agent_type="perception")
        self.logger = logging.getLogger(f"EarAgentEngine.{agent_id}")

        if config is not None:
            self._cfg = config
        else:
            self._cfg = _load_config(config_path or self.DEFAULT_CONFIG_PATH)

        # Providers
        asr_cfg = self._cfg.get("speech_recognition", {})
        spk_cfg = self._cfg.get("speaker_identification", {})
        emo_cfg = self._cfg.get("emotion_detection", {})

        self._speech_provider: SpeechRecognitionProvider = build_speech_provider(
            asr_cfg.get("backend", asr_cfg.get("engine", "energy")), asr_cfg
        )
        self._speaker_provider: SpeakerRecognitionProvider = build_speaker_provider(
            spk_cfg.get("model", "mock"), spk_cfg
        )
        self._emotion_provider: AudioEmotionProvider = build_audio_emotion_provider(
            emo_cfg.get("model", "mock"), emo_cfg
        )

        # Sessions
        self._sessions: Dict[str, PerceptionSession] = {}
        self._active_session_id: Optional[str] = None

        # Audio history (bounded)
        max_history = int(self._cfg.get("audio_history_size", 200))
        self._audio_history: Deque[AudioResult] = deque(maxlen=max_history)

        # Streaming buffer
        stream_buf = int(self._cfg.get("stream_buffer_size", 50))
        self._stream_buffer: Deque[Dict[str, Any]] = deque(maxlen=stream_buf)

        # Metrics & audit
        self._metrics = PerceptionMetrics()
        self._audit_trail: Deque[PerceptionAuditEntry] = deque(maxlen=1000)

        # Config shortcuts
        audio_cfg = self._cfg.get("audio", {})
        self._sample_rate: int = int(audio_cfg.get("sample_rate", 16000))
        self._asr_conf_threshold: float = float(asr_cfg.get("confidence_threshold", 0.5))
        self._language: str = asr_cfg.get("language", "en")
        self._keywords: List[str] = self._cfg.get("keywords", [])
        self._noise_threshold: float = float(audio_cfg.get("silence_threshold", 0.01))

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self):
        try:
            await super().initialize()
        except Exception:
            pass
        self.state.update({
            "speech_provider": self._speech_provider.name,
            "speaker_provider": self._speaker_provider.name,
            "emotion_provider": self._emotion_provider.name,
            "sessions_opened": 0,
            "utterances_processed": 0,
            "errors": 0,
        })
        self.logger.info(
            f"EarAgentEngine initialized | "
            f"speech={self._speech_provider.name} "
            f"speaker={self._speaker_provider.name} "
            f"emotion={self._emotion_provider.name}"
        )

    async def shutdown(self):
        for sid in list(self._sessions.keys()):
            await self.stop_session(sid)
        await super().shutdown()
        self.logger.info("EarAgentEngine shut down")

    # ─── Session Management ───────────────────────────────────────────────────

    def start_session(
        self,
        context: Optional[PerceptionContext] = None,
        session_id: Optional[str] = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        session = PerceptionSession(
            session_id=sid,
            agent_type="ear",
            provider=self._speech_provider.name,
            request_id=context.request_id if context else None,
            correlation_id=context.correlation_id if context else None,
            trace_id=context.trace_id if context else None,
        )
        self._sessions[sid] = session
        self._active_session_id = sid
        self._metrics.audio_sessions += 1
        self.state["sessions_opened"] = self.state.get("sessions_opened", 0) + 1
        self.logger.info(f"EarAgentEngine: session started | session_id={sid}")
        return sid

    async def stop_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return None
        session.ended_at = datetime.utcnow().isoformat()
        if self._active_session_id == session_id:
            self._active_session_id = None
        self.logger.info(
            f"EarAgentEngine: session closed | session_id={session_id} "
            f"ops={session.operations_count}"
        )
        return session.to_dict()

    # ─── Audio Processing Pipeline ────────────────────────────────────────────

    def process_audio(
        self,
        audio,
        sample_rate: Optional[int] = None,
        session_id: Optional[str] = None,
        context: Optional[PerceptionContext] = None,
    ) -> AudioResult:
        """
        Full audio pipeline on a raw audio chunk (numpy int16 array or None).
        Returns AudioResult with transcription, speaker, emotion, intent, language.
        """
        t0 = time.perf_counter()
        sid = session_id or self._active_session_id or "default"
        frame_id = str(uuid.uuid4())
        sr = sample_rate or self._sample_rate

        # Validate input
        if audio is not None and _HAS_NUMPY:
            if not isinstance(audio, np.ndarray):
                try:
                    audio = np.frombuffer(bytes(audio), dtype=np.int16)
                except Exception:
                    audio = None

        try:
            asr_cfg = self._cfg.get("speech_recognition", {})
            asr_cfg["language"] = self._language

            # Voice activity detection (energy-based)
            voice_active = self._detect_voice_activity(audio)

            # Transcription
            asr_result = self._speech_provider.transcribe(audio, sr, asr_cfg)
            transcription = asr_result.get("text", "")
            asr_conf = float(asr_result.get("confidence", 0.0))
            language = asr_result.get("language", self._language)

            # Speaker identification
            spk_result = self._speaker_provider.identify(
                audio, sr, self._cfg.get("speaker_identification", {})
            )
            speaker_id = spk_result.get("speaker_id", "unknown")
            speaker_conf = float(spk_result.get("confidence", 0.0))

            # Emotion detection
            emo_result = self._emotion_provider.detect_emotion(
                audio, sr, self._cfg.get("emotion_detection", {})
            )
            emotion = emo_result.get("emotion", "neutral")
            emotion_scores = emo_result.get("scores", {})
            emo_conf = float(emo_result.get("confidence", 0.0))

            # Keyword spotting
            keywords_detected = self._spot_keywords(transcription)

            # Noise estimation
            noise_level = self._estimate_noise(audio)

            # Intent extraction (lightweight pattern-based)
            intent, intent_conf = self._extract_intent(transcription)

            # Language confidence (from ASR)
            lang_conf = float(asr_result.get("language_confidence", asr_conf))

            # Overall confidence
            confs = [c for c in [asr_conf, speaker_conf, emo_conf] if c > 0]
            overall_conf = round(sum(confs) / max(1, len(confs)), 4)

            processing_ms = round((time.perf_counter() - t0) * 1000, 2)

            result = AudioResult(
                frame_id=frame_id,
                session_id=sid,
                provider=self._speech_provider.name,
                transcription=transcription,
                transcription_confidence=asr_conf,
                language=language,
                language_confidence=lang_conf,
                speaker_id=speaker_id,
                speaker_confidence=speaker_conf,
                emotion=emotion,
                emotion_scores=emotion_scores,
                intent=intent,
                intent_confidence=intent_conf,
                keywords_detected=keywords_detected,
                noise_level=noise_level,
                voice_activity=voice_active,
                overall_confidence=overall_conf,
                processing_ms=processing_ms,
            )

            # Update metrics
            self._metrics.utterances_transcribed += 1
            self._metrics.total_processing_ms += processing_ms
            self.state["utterances_processed"] = self._metrics.utterances_transcribed

            # Update session
            if sid in self._sessions:
                self._sessions[sid].operations_count += 1

            # History
            self._audio_history.append(result)

            # Audit
            self._audit(sid, "process_audio", overall_conf, processing_ms, True,
                        f"text='{transcription[:40]}' speaker={speaker_id} emotion={emotion}")

            return result

        except Exception as e:
            self.logger.error(f"EarAgentEngine.process_audio: {e}")
            self._metrics.error_count += 1
            self.state["errors"] = self.state.get("errors", 0) + 1
            self._audit(sid, "process_audio", 0.0, 0.0, False, str(e))
            return AudioResult(frame_id=frame_id, session_id=sid, provider=self._speech_provider.name)

    # ─── Pipeline Helpers ─────────────────────────────────────────────────────

    def _detect_voice_activity(self, audio) -> bool:
        if audio is None:
            return False
        if _HAS_NUMPY and isinstance(audio, np.ndarray) and len(audio) > 0:
            rms = float(np.sqrt(np.mean(audio.astype(float) ** 2)))
            return rms > (self._noise_threshold * 32768.0)
        return False

    def _estimate_noise(self, audio) -> float:
        if audio is None or not _HAS_NUMPY:
            return 0.0
        if isinstance(audio, np.ndarray) and len(audio) > 0:
            rms = float(np.sqrt(np.mean(audio.astype(float) ** 2)))
            return round(min(1.0, rms / 32768.0), 4)
        return 0.0

    def _spot_keywords(self, text: str) -> List[str]:
        if not text or not self._keywords:
            return []
        lower = text.lower()
        return [kw for kw in self._keywords if kw.lower() in lower]

    _INTENT_PATTERNS = [
        (["hello", "hi", "hey", "good morning", "good evening"], "greeting"),
        (["bye", "goodbye", "see you", "farewell"], "farewell"),
        (["help", "assist", "support", "can you"], "help_request"),
        (["what", "who", "where", "when", "why", "how"], "question"),
        (["stop", "cancel", "abort", "quit", "exit"], "stop"),
        (["start", "begin", "go", "run", "execute"], "start"),
        (["remember", "save", "store", "note"], "memory_store"),
        (["recall", "remind", "what did", "do you remember"], "memory_recall"),
    ]

    def _extract_intent(self, text: str):
        if not text:
            return "unknown", 0.0
        lower = text.lower()
        for signals, intent in self._INTENT_PATTERNS:
            if any(s in lower for s in signals):
                return intent, 0.75
        return "statement", 0.5

    # ─── Streaming ────────────────────────────────────────────────────────────

    def push_stream_chunk(self, audio_chunk, timestamp: Optional[float] = None):
        """Push a streaming audio chunk into the bounded buffer."""
        self._stream_buffer.append({
            "audio": audio_chunk,
            "timestamp": timestamp or time.time(),
        })

    async def flush_stream(self, session_id: Optional[str] = None) -> List[AudioResult]:
        """Process all buffered stream chunks and return results."""
        results = []
        while self._stream_buffer:
            chunk = self._stream_buffer.popleft()
            result = self.process_audio(
                chunk["audio"],
                session_id=session_id or self._active_session_id,
            )
            results.append(result)
            await asyncio.sleep(0)  # yield to event loop
        return results

    # ─── History & Metrics ────────────────────────────────────────────────────

    def get_audio_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        history = list(self._audio_history)
        return [r.to_dict() for r in history[-limit:]]

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics.as_dict(),
            "avg_processing_ms": self._metrics.avg_processing_ms(),
            "speech_provider": self._speech_provider.name,
            "speaker_provider": self._speaker_provider.name,
            "emotion_provider": self._emotion_provider.name,
            "active_sessions": len(self._sessions),
            "stream_buffer_size": len(self._stream_buffer),
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
            agent_type="ear",
            operation=operation,
            provider=self._speech_provider.name,
            success=success,
            confidence=confidence,
            processing_ms=processing_ms,
            summary=summary,
        )
        self._audit_trail.append(entry)

    # ─── Broker Collaboration ─────────────────────────────────────────────────

    async def _broadcast_audio_result(self, result: AudioResult):
        if not self._message_broker:
            return
        try:
            from orchestrator.agent_communication import MessageType, MessagePriority
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=None,
                message_type=MessageType.PERCEPTION_INPUT,
                content={
                    "input_type": "audio",
                    "session_id": result.session_id,
                    "frame_id": result.frame_id,
                    "transcription": result.transcription,
                    "speaker_id": result.speaker_id,
                    "emotion": result.emotion,
                    "intent": result.intent,
                    "language": result.language,
                    "confidence": result.overall_confidence,
                    "timestamp": result.timestamp,
                },
                priority=MessagePriority.NORMAL,
            )
        except Exception as e:
            self.logger.debug(f"EarAgentEngine: broker publish failed: {e}")

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

        if action in ("process_audio", "transcribe", "recognize_speech"):
            audio = self._decode_audio(data)
            sr = int(data.get("sample_rate", self._sample_rate))
            sid = data.get("session_id", self._active_session_id)
            result = self.process_audio(audio, sample_rate=sr, session_id=sid)
            await self._broadcast_audio_result(result)
            return result.to_dict()

        if action == "push_stream":
            audio = self._decode_audio(data)
            self.push_stream_chunk(audio, data.get("timestamp"))
            return {"status": "buffered", "buffer_size": len(self._stream_buffer)}

        if action == "flush_stream":
            sid = data.get("session_id", self._active_session_id)
            results = await self.flush_stream(session_id=sid)
            return {"results": [r.to_dict() for r in results], "count": len(results)}

        if action == "enroll_speaker":
            samples = [self._decode_audio({"audio": s}) for s in data.get("samples", [])]
            samples = [s for s in samples if s is not None]
            success = self._speaker_provider.enroll(
                data.get("speaker_id", str(uuid.uuid4())),
                data.get("name", "unknown"),
                samples,
                self._cfg.get("speaker_identification", {}),
            )
            return {"success": success}

        if action == "get_history":
            return {"history": self.get_audio_history(data.get("limit", 50))}

        if action == "get_metrics":
            return self.get_metrics()

        if action == "get_audit":
            return {"audit": self.get_audit_trail(data.get("limit", 100))}

        if action == "get_status":
            return await self.get_status()

        if action == "get_health":
            return await self.get_health()

        if action == "switch_speech_provider":
            new_name = data.get("provider", "energy")
            self._speech_provider = build_speech_provider(new_name, self._cfg.get("speech_recognition", {}))
            self.state["speech_provider"] = self._speech_provider.name
            return {"provider": self._speech_provider.name, "available": self._speech_provider.available}

        return await super().execute_task(task)

    def _decode_audio(self, data: Dict[str, Any]):
        raw = data.get("audio")
        if raw is None:
            return None
        if _HAS_NUMPY and isinstance(raw, np.ndarray):
            return raw
        if _HAS_NUMPY:
            try:
                return np.frombuffer(bytes(raw), dtype=np.int16)
            except Exception as e:
                self.logger.warning(f"EarAgentEngine: audio decode failed: {e}")
        return None

    # ─── State Update ─────────────────────────────────────────────────────────

    async def _update_state(self):
        await super()._update_state()
        self.state["utterances_processed"] = self._metrics.utterances_transcribed
        self.state["active_sessions"] = len(self._sessions)
        self.state["speech_provider"] = self._speech_provider.name
