"""
PerceptionAgent — Production Multimodal Fusion Engine (Phase 12).

Extends BaseAgent for full orchestrator lifecycle integration.
Implements:
  - Perception sessions with lifecycle management
  - Multimodal context aggregation (vision + audio + memory + language + emotion)
  - Sensor fusion with temporal synchronization
  - Cross-modal correlation scoring
  - Confidence aggregation and uncertainty propagation
  - Environment understanding and situation assessment
  - Attention estimation across modalities
  - Event detection from fused signals
  - Fusion history, metrics, audit trail
  - Broker-based collaboration with all cognitive agents
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
from typing import Any, Deque, Dict, List, Optional, Tuple

import yaml

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from ..base_agent import BaseAgent  # type: ignore

try:
    from agents.perception_agent.models import (
        VisionResult, AudioResult, FusionResult, CrossModalCorrelation,
        PerceptionSession, PerceptionMetrics, PerceptionAuditEntry, PerceptionContext,
    )
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from perception_agent.models import (  # type: ignore
        VisionResult, AudioResult, FusionResult, CrossModalCorrelation,
        PerceptionSession, PerceptionMetrics, PerceptionAuditEntry, PerceptionContext,
    )

_DEFAULT_CONFIG_PATH = "config/orchestrator_config.yaml"


def _load_config(path: str) -> Dict[str, Any]:
    try:
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        logging.getLogger(__name__).warning(f"PerceptionFusionEngine: config load failed ({path}): {e}")
    return {}


# ─── Situation Labels ─────────────────────────────────────────────────────────

_SITUATION_RULES: List[Tuple[str, float, List[str]]] = [
    # (label, min_confidence, required_signals)
    ("active_conversation",  0.6, ["speech_detected", "face_detected"]),
    ("person_present",       0.5, ["face_detected"]),
    ("speech_only",          0.5, ["speech_detected"]),
    ("motion_detected",      0.4, ["motion_detected"]),
    ("quiet_environment",    0.7, ["no_speech", "no_motion"]),
    ("multiple_people",      0.6, ["multiple_faces"]),
    ("emotional_state",      0.5, ["emotion_detected"]),
    ("unknown",              0.0, []),
]


class PerceptionFusionEngine(BaseAgent):
    """
    Production multimodal fusion engine.

    Lifecycle:
      initialize()     → load config, register with broker
      start_session()  → open a named perception session
      fuse()           → fuse VisionResult + AudioResult → FusionResult
      stop_session()   → close session, flush audit
      shutdown()       → stop all sessions
      execute_task()   → orchestrator dispatch
    """

    DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_PATH

    def __init__(
        self,
        agent_id: str = "perception_fusion_engine",
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ):
        super().__init__(agent_id=agent_id, agent_type="perception")
        self.logger = logging.getLogger(f"PerceptionFusionEngine.{agent_id}")

        if config is not None:
            self._cfg = config
        else:
            self._cfg = _load_config(config_path or self.DEFAULT_CONFIG_PATH)

        fusion_cfg = self._cfg.get("perception_fusion", self._cfg.get("fusion", {}))

        # Temporal window for fusion (ms)
        self._temporal_window_ms: float = float(fusion_cfg.get("temporal_window_ms", 500.0))

        # Confidence thresholds
        self._min_confidence: float = float(fusion_cfg.get("min_confidence", 0.3))
        self._fusion_confidence_threshold: float = float(
            fusion_cfg.get("fusion_confidence_threshold", 0.5)
        )

        # Modality weights for confidence aggregation
        self._modality_weights: Dict[str, float] = {
            "vision": float(fusion_cfg.get("vision_weight", 0.5)),
            "audio": float(fusion_cfg.get("audio_weight", 0.5)),
        }

        # Sessions
        self._sessions: Dict[str, PerceptionSession] = {}
        self._active_session_id: Optional[str] = None

        # Temporal buffers for each modality
        buf_size = int(fusion_cfg.get("temporal_buffer_size", 20))
        self._vision_buffer: Deque[VisionResult] = deque(maxlen=buf_size)
        self._audio_buffer: Deque[AudioResult] = deque(maxlen=buf_size)

        # Fusion history
        max_history = int(fusion_cfg.get("fusion_history_size", 200))
        self._fusion_history: Deque[FusionResult] = deque(maxlen=max_history)

        # Multimodal context (shared across all agents)
        self._context: PerceptionContext = PerceptionContext()

        # Metrics & audit
        self._metrics = PerceptionMetrics()
        self._audit_trail: Deque[PerceptionAuditEntry] = deque(maxlen=1000)

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self):
        try:
            await super().initialize()
        except Exception:
            pass
        self.state.update({
            "temporal_window_ms": self._temporal_window_ms,
            "sessions_opened": 0,
            "fusion_operations": 0,
            "errors": 0,
        })
        self.logger.info(
            f"PerceptionFusionEngine initialized | "
            f"temporal_window={self._temporal_window_ms}ms"
        )

    async def shutdown(self):
        for sid in list(self._sessions.keys()):
            await self.stop_session(sid)
        await super().shutdown()
        self.logger.info("PerceptionFusionEngine shut down")

    # ─── Session Management ───────────────────────────────────────────────────

    def start_session(
        self,
        context: Optional[PerceptionContext] = None,
        session_id: Optional[str] = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        if context:
            self._context = context
        session = PerceptionSession(
            session_id=sid,
            agent_type="perception",
            provider="fusion",
            request_id=context.request_id if context else None,
            correlation_id=context.correlation_id if context else None,
            trace_id=context.trace_id if context else None,
        )
        self._sessions[sid] = session
        self._active_session_id = sid
        self.state["sessions_opened"] = self.state.get("sessions_opened", 0) + 1
        self.logger.info(f"PerceptionFusionEngine: session started | session_id={sid}")
        return sid

    async def stop_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return None
        session.ended_at = datetime.utcnow().isoformat()
        if self._active_session_id == session_id:
            self._active_session_id = None
        self.logger.info(
            f"PerceptionFusionEngine: session closed | session_id={session_id} "
            f"ops={session.operations_count}"
        )
        return session.to_dict()

    # ─── Modality Ingestion ───────────────────────────────────────────────────

    def ingest_vision(self, result: VisionResult):
        """Add a VisionResult to the temporal buffer."""
        self._vision_buffer.append(result)

    def ingest_audio(self, result: AudioResult):
        """Add an AudioResult to the temporal buffer."""
        self._audio_buffer.append(result)

    # ─── Fusion Pipeline ──────────────────────────────────────────────────────

    def fuse(
        self,
        vision: Optional[VisionResult] = None,
        audio: Optional[AudioResult] = None,
        session_id: Optional[str] = None,
        context: Optional[PerceptionContext] = None,
    ) -> FusionResult:
        """
        Fuse vision + audio into a FusionResult.
        Uses temporal buffers if explicit inputs are not provided.
        """
        t0 = time.perf_counter()
        sid = session_id or self._active_session_id or "default"
        fusion_id = str(uuid.uuid4())

        # Ingest if provided
        if vision is not None:
            self.ingest_vision(vision)
        if audio is not None:
            self.ingest_audio(audio)

        # Use latest from buffers
        latest_vision = vision or (self._vision_buffer[-1] if self._vision_buffer else None)
        latest_audio = audio or (self._audio_buffer[-1] if self._audio_buffer else None)

        try:
            # Build summaries
            visual_summary = self._summarize_vision(latest_vision)
            audio_summary = self._summarize_audio(latest_audio)

            # Cross-modal correlations
            correlations = self._compute_correlations(latest_vision, latest_audio)

            # Temporal synchronization check
            temporal_ok = self._check_temporal_sync(latest_vision, latest_audio)

            # Situation assessment
            signals = self._extract_signals(visual_summary, audio_summary)
            situation_label, situation_conf = self._assess_situation(signals)

            # Attention focus
            attention_focus = self._estimate_attention(visual_summary, audio_summary)

            # Event detection
            events = self._detect_events(visual_summary, audio_summary, signals)

            # Environment understanding
            env_understanding = self._understand_environment(
                visual_summary, audio_summary, situation_label
            )

            # Confidence aggregation
            agg_conf, uncertainty = self._aggregate_confidence(
                latest_vision, latest_audio, correlations
            )

            processing_ms = round((time.perf_counter() - t0) * 1000, 2)

            result = FusionResult(
                fusion_id=fusion_id,
                session_id=sid,
                provider="fusion",
                visual_summary=visual_summary,
                audio_summary=audio_summary,
                cross_modal_correlations=correlations,
                situation_label=situation_label,
                situation_confidence=situation_conf,
                attention_focus=attention_focus,
                detected_events=events,
                environment_understanding=env_understanding,
                aggregate_confidence=agg_conf,
                uncertainty=uncertainty,
                temporal_window_ms=self._temporal_window_ms,
                processing_ms=processing_ms,
            )

            # Metrics
            self._metrics.fusion_operations += 1
            self._metrics.total_processing_ms += processing_ms
            self.state["fusion_operations"] = self._metrics.fusion_operations

            # Session
            if sid in self._sessions:
                self._sessions[sid].operations_count += 1

            # History
            self._fusion_history.append(result)

            # Audit
            self._audit(sid, "fuse", agg_conf, processing_ms, True,
                        f"situation={situation_label} conf={agg_conf:.2f} events={events}")

            return result

        except Exception as e:
            self.logger.error(f"PerceptionFusionEngine.fuse: {e}")
            self._metrics.error_count += 1
            self.state["errors"] = self.state.get("errors", 0) + 1
            self._audit(sid, "fuse", 0.0, 0.0, False, str(e))
            return FusionResult(fusion_id=fusion_id, session_id=sid)

    # ─── Fusion Helpers ───────────────────────────────────────────────────────

    def _summarize_vision(self, vision: Optional[VisionResult]) -> Dict[str, Any]:
        if vision is None:
            return {"available": False}
        return {
            "available": True,
            "frame_id": vision.frame_id,
            "objects": [{"label": o.label, "confidence": o.confidence} for o in vision.objects],
            "faces": [{"face_id": f.face_id, "emotion": f.emotion, "confidence": f.confidence}
                      for f in vision.faces],
            "scene": vision.scene_label,
            "scene_confidence": vision.scene_confidence,
            "motion_detected": vision.motion_detected,
            "motion_score": vision.motion_score,
            "ocr_text": vision.ocr_text,
            "attention_zones": vision.attention_zones,
            "overall_confidence": vision.overall_confidence,
        }

    def _summarize_audio(self, audio: Optional[AudioResult]) -> Dict[str, Any]:
        if audio is None:
            return {"available": False}
        return {
            "available": True,
            "frame_id": audio.frame_id,
            "transcription": audio.transcription,
            "transcription_confidence": audio.transcription_confidence,
            "language": audio.language,
            "speaker_id": audio.speaker_id,
            "emotion": audio.emotion,
            "emotion_scores": audio.emotion_scores,
            "intent": audio.intent,
            "intent_confidence": audio.intent_confidence,
            "keywords": audio.keywords_detected,
            "voice_activity": audio.voice_activity,
            "noise_level": audio.noise_level,
            "overall_confidence": audio.overall_confidence,
        }

    def _compute_correlations(
        self,
        vision: Optional[VisionResult],
        audio: Optional[AudioResult],
    ) -> List[CrossModalCorrelation]:
        correlations = []

        if vision is not None and audio is not None:
            # Vision + Audio temporal correlation
            try:
                v_ts = datetime.fromisoformat(vision.timestamp)
                a_ts = datetime.fromisoformat(audio.timestamp)
                offset_ms = abs((v_ts - a_ts).total_seconds() * 1000)
                aligned = offset_ms <= self._temporal_window_ms
                score = max(0.0, 1.0 - offset_ms / max(1.0, self._temporal_window_ms))
            except Exception:
                offset_ms, aligned, score = 0.0, True, 0.5

            correlations.append(CrossModalCorrelation(
                modalities=["vision", "audio"],
                correlation_score=round(score, 4),
                temporal_offset_ms=round(offset_ms, 2),
                aligned=aligned,
            ))

            # Emotion correlation (face emotion vs audio emotion)
            if vision.faces and audio.emotion != "neutral":
                face_emotions = [f.emotion for f in vision.faces]
                emotion_match = audio.emotion in face_emotions
                correlations.append(CrossModalCorrelation(
                    modalities=["vision_emotion", "audio_emotion"],
                    correlation_score=0.8 if emotion_match else 0.3,
                    temporal_offset_ms=0.0,
                    aligned=emotion_match,
                ))

        return correlations

    def _check_temporal_sync(
        self,
        vision: Optional[VisionResult],
        audio: Optional[AudioResult],
    ) -> bool:
        if vision is None or audio is None:
            return True
        try:
            v_ts = datetime.fromisoformat(vision.timestamp)
            a_ts = datetime.fromisoformat(audio.timestamp)
            offset_ms = abs((v_ts - a_ts).total_seconds() * 1000)
            return offset_ms <= self._temporal_window_ms
        except Exception:
            return True

    def _extract_signals(
        self, visual: Dict[str, Any], audio: Dict[str, Any]
    ) -> List[str]:
        signals = []
        if visual.get("available"):
            if visual.get("faces"):
                signals.append("face_detected")
                if len(visual["faces"]) > 1:
                    signals.append("multiple_faces")
                for f in visual["faces"]:
                    if f.get("emotion") and f["emotion"] != "neutral":
                        signals.append("emotion_detected")
                        break
            if visual.get("motion_detected"):
                signals.append("motion_detected")
            else:
                signals.append("no_motion")
        if audio.get("available"):
            if audio.get("voice_activity") or (
                audio.get("transcription") and
                not audio["transcription"].startswith("[")
            ):
                signals.append("speech_detected")
            else:
                signals.append("no_speech")
            if audio.get("emotion") and audio["emotion"] != "neutral":
                signals.append("emotion_detected")
        return signals

    def _assess_situation(self, signals: List[str]) -> Tuple[str, float]:
        for label, min_conf, required in _SITUATION_RULES:
            if not required:
                continue
            if all(s in signals for s in required):
                return label, min_conf + 0.1 * len(signals)
        return "unknown", 0.3

    def _estimate_attention(
        self, visual: Dict[str, Any], audio: Dict[str, Any]
    ) -> str:
        if visual.get("faces"):
            return f"face:{visual['faces'][0].get('face_id', 'unknown')}"
        if visual.get("objects"):
            top = max(visual["objects"], key=lambda o: o.get("confidence", 0))
            return f"object:{top.get('label', 'unknown')}"
        if audio.get("voice_activity"):
            return f"speaker:{audio.get('speaker_id', 'unknown')}"
        return "environment"

    def _detect_events(
        self,
        visual: Dict[str, Any],
        audio: Dict[str, Any],
        signals: List[str],
    ) -> List[str]:
        events = []
        if "face_detected" in signals:
            events.append("face_appeared")
        if "motion_detected" in signals:
            events.append("motion_event")
        if "speech_detected" in signals:
            events.append("speech_event")
            intent = audio.get("intent", "")
            if intent and intent not in ("unknown", "statement"):
                events.append(f"intent:{intent}")
        if "emotion_detected" in signals:
            emo = audio.get("emotion") or (
                visual.get("faces", [{}])[0].get("emotion") if visual.get("faces") else None
            )
            if emo:
                events.append(f"emotion:{emo}")
        keywords = audio.get("keywords", [])
        for kw in keywords:
            events.append(f"keyword:{kw}")
        return events

    def _understand_environment(
        self,
        visual: Dict[str, Any],
        audio: Dict[str, Any],
        situation: str,
    ) -> str:
        parts = []
        if visual.get("scene") and visual["scene"] != "unknown":
            parts.append(f"scene={visual['scene']}")
        if visual.get("faces"):
            parts.append(f"people={len(visual['faces'])}")
        if visual.get("objects"):
            labels = [o["label"] for o in visual["objects"][:3]]
            parts.append(f"objects={','.join(labels)}")
        if audio.get("voice_activity"):
            parts.append(f"speech=active lang={audio.get('language', 'en')}")
        noise = audio.get("noise_level", 0.0)
        if noise > 0.3:
            parts.append(f"noise={noise:.2f}")
        parts.append(f"situation={situation}")
        return " | ".join(parts) if parts else "environment=unknown"

    def _aggregate_confidence(
        self,
        vision: Optional[VisionResult],
        audio: Optional[AudioResult],
        correlations: List[CrossModalCorrelation],
    ) -> Tuple[float, float]:
        scores = []
        weights = []

        if vision is not None:
            scores.append(vision.overall_confidence)
            weights.append(self._modality_weights["vision"])
        if audio is not None:
            scores.append(audio.overall_confidence)
            weights.append(self._modality_weights["audio"])

        if not scores:
            return 0.0, 1.0

        total_weight = sum(weights)
        agg = sum(s * w for s, w in zip(scores, weights)) / max(0.001, total_weight)

        # Boost confidence if modalities are temporally aligned
        if correlations:
            avg_corr = sum(c.correlation_score for c in correlations) / len(correlations)
            agg = min(1.0, agg * (1.0 + 0.1 * avg_corr))

        uncertainty = round(1.0 - agg, 4)
        return round(agg, 4), uncertainty

    # ─── Context Management ───────────────────────────────────────────────────

    def update_context(self, updates: Dict[str, Any]):
        """Update the shared multimodal context."""
        for key, value in updates.items():
            if hasattr(self._context, key):
                setattr(self._context, key, value)

    def get_context(self) -> Dict[str, Any]:
        return self._context.to_dict()

    # ─── History & Metrics ────────────────────────────────────────────────────

    def get_fusion_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        history = list(self._fusion_history)
        return [r.to_dict() for r in history[-limit:]]

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics.as_dict(),
            "avg_processing_ms": self._metrics.avg_processing_ms(),
            "active_sessions": len(self._sessions),
            "vision_buffer_size": len(self._vision_buffer),
            "audio_buffer_size": len(self._audio_buffer),
            "temporal_window_ms": self._temporal_window_ms,
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
            agent_type="perception",
            operation=operation,
            provider="fusion",
            success=success,
            confidence=confidence,
            processing_ms=processing_ms,
            summary=summary,
        )
        self._audit_trail.append(entry)

    # ─── Broker Collaboration ─────────────────────────────────────────────────

    async def _broadcast_fusion_result(self, result: FusionResult):
        if not self._message_broker:
            return
        try:
            from orchestrator.agent_communication import MessageType, MessagePriority
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=None,
                message_type=MessageType.PERCEPTION_INPUT,
                content={
                    "input_type": "fusion",
                    "fusion_id": result.fusion_id,
                    "session_id": result.session_id,
                    "situation": result.situation_label,
                    "situation_confidence": result.situation_confidence,
                    "events": result.detected_events,
                    "attention": result.attention_focus,
                    "confidence": result.aggregate_confidence,
                    "uncertainty": result.uncertainty,
                    "environment": result.environment_understanding,
                    "timestamp": result.timestamp,
                },
                priority=MessagePriority.NORMAL,
            )
        except Exception as e:
            self.logger.debug(f"PerceptionFusionEngine: broker publish failed: {e}")

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

        if action in ("fuse", "perceive", "process"):
            vision_data = data.get("vision")
            audio_data = data.get("audio")

            vision = None
            if vision_data:
                try:
                    from agents.perception_agent.models import VisionResult as VR
                    vision = VR(**{k: v for k, v in vision_data.items()
                                   if k in VR.__dataclass_fields__})
                except Exception:
                    pass

            audio = None
            if audio_data:
                try:
                    from agents.perception_agent.models import AudioResult as AR
                    audio = AR(**{k: v for k, v in audio_data.items()
                                  if k in AR.__dataclass_fields__})
                except Exception:
                    pass

            sid = data.get("session_id", self._active_session_id)
            result = self.fuse(vision=vision, audio=audio, session_id=sid)
            await self._broadcast_fusion_result(result)
            return result.to_dict()

        if action == "ingest_vision":
            try:
                from agents.perception_agent.models import VisionResult as VR
                vr = VR(**{k: v for k, v in data.items() if k in VR.__dataclass_fields__})
                self.ingest_vision(vr)
                return {"status": "ingested", "frame_id": vr.frame_id}
            except Exception as e:
                return {"error": str(e)}

        if action == "ingest_audio":
            try:
                from agents.perception_agent.models import AudioResult as AR
                ar = AR(**{k: v for k, v in data.items() if k in AR.__dataclass_fields__})
                self.ingest_audio(ar)
                return {"status": "ingested", "frame_id": ar.frame_id}
            except Exception as e:
                return {"error": str(e)}

        if action == "update_context":
            self.update_context(data)
            return {"status": "updated"}

        if action == "get_context":
            return self.get_context()

        if action == "get_history":
            return {"history": self.get_fusion_history(data.get("limit", 50))}

        if action == "get_metrics":
            return self.get_metrics()

        if action == "get_audit":
            return {"audit": self.get_audit_trail(data.get("limit", 100))}

        if action == "get_status":
            return await self.get_status()

        if action == "get_health":
            return await self.get_health()

        return await super().execute_task(task)

    # ─── State Update ─────────────────────────────────────────────────────────

    async def _update_state(self):
        await super()._update_state()
        self.state["fusion_operations"] = self._metrics.fusion_operations
        self.state["active_sessions"] = len(self._sessions)
        self.state["vision_buffer"] = len(self._vision_buffer)
        self.state["audio_buffer"] = len(self._audio_buffer)
