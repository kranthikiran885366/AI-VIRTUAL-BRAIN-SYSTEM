"""
EyesAgent — Production Vision Engine (Phase 12).

Extends BaseAgent for full orchestrator lifecycle integration.
Implements:
  - Vision sessions with lifecycle management
  - Pluggable provider abstraction (OpenCV / MediaPipe / ONNX / Mock)
  - Frame processing pipeline: objects → faces → scene → OCR → motion → attention
  - Vision history and replay
  - Structured metrics and audit trail
  - Broker-based collaboration with Memory/Emotion/Perception agents
  - GPU/CPU fallback
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
    from agents.eyes_agent.providers import VisionProvider, build_vision_provider
    from agents.perception_agent.models import (
        VisionFrame, VisionResult, DetectedObject, DetectedFace,
        BoundingBox, PerceptionSession, PerceptionMetrics, PerceptionAuditEntry,
        PerceptionContext,
    )
except ImportError:
    from .providers import VisionProvider, build_vision_provider  # type: ignore
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from perception_agent.models import (  # type: ignore
        VisionFrame, VisionResult, DetectedObject, DetectedFace,
        BoundingBox, PerceptionSession, PerceptionMetrics, PerceptionAuditEntry,
        PerceptionContext,
    )

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None  # type: ignore


_DEFAULT_CONFIG_PATH = "config/eyes_config.yaml"


def _load_config(path: str) -> Dict[str, Any]:
    try:
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        logging.getLogger(__name__).warning(f"EyesAgent: config load failed ({path}): {e}")
    return {}


class EyesAgentEngine(BaseAgent):
    """
    Production vision engine.

    Lifecycle:
      initialize()     → load config, build provider, register with broker
      start_session()  → open a named vision session
      process_frame()  → run full vision pipeline on a raw frame
      stop_session()   → close session, flush audit
      shutdown()       → stop all sessions, release resources
      execute_task()   → orchestrator dispatch
    """

    DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_PATH

    def __init__(
        self,
        agent_id: str = "eyes_agent",
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ):
        super().__init__(agent_id=agent_id, agent_type="perception")
        self.logger = logging.getLogger(f"EyesAgent.{agent_id}")

        # Config: explicit dict > yaml file > empty dict
        if config is not None:
            self._cfg = config
        else:
            self._cfg = _load_config(config_path or self.DEFAULT_CONFIG_PATH)

        # Provider
        provider_name = self._cfg.get("provider", "mock")
        provider_cfg = self._cfg.get("provider_config", {})
        self._provider: VisionProvider = build_vision_provider(provider_name, provider_cfg)

        # Sessions
        self._sessions: Dict[str, PerceptionSession] = {}
        self._active_session_id: Optional[str] = None

        # Frame history (bounded ring buffer)
        max_history = int(self._cfg.get("vision_history_size", 200))
        self._frame_history: Deque[VisionResult] = deque(maxlen=max_history)

        # Previous frame for motion detection
        self._prev_frame = None

        # Metrics & audit
        self._metrics = PerceptionMetrics()
        self._audit_trail: Deque[PerceptionAuditEntry] = deque(maxlen=1000)

        # Config shortcuts
        self._obj_conf = float(self._cfg.get("object_detection", {}).get("confidence_threshold", 0.5))
        self._face_conf = float(self._cfg.get("face_tracking", {}).get("confidence_threshold", 0.5))
        self._scene_conf = float(self._cfg.get("perception", {}).get("confidence_threshold", 0.5))
        self._motion_threshold = float(self._cfg.get("motion_threshold", 0.02))
        self._max_objects = int(self._cfg.get("object_detection", {}).get("max_objects", 20))
        self._max_faces = int(self._cfg.get("face_tracking", {}).get("max_faces", 10))

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self):
        try:
            await super().initialize()
        except Exception:
            pass
        self.state.update({
            "provider": self._provider.name,
            "provider_available": self._provider.available,
            "sessions_opened": 0,
            "frames_processed": 0,
            "errors": 0,
        })
        self.logger.info(
            f"EyesAgent initialized | provider={self._provider.name} "
            f"available={self._provider.available}"
        )

    async def shutdown(self):
        for sid in list(self._sessions.keys()):
            await self.stop_session(sid)
        await super().shutdown()
        self.logger.info("EyesAgent shut down")

    # ─── Session Management ───────────────────────────────────────────────────

    def start_session(
        self,
        context: Optional[PerceptionContext] = None,
        session_id: Optional[str] = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        session = PerceptionSession(
            session_id=sid,
            agent_type="eyes",
            provider=self._provider.name,
            request_id=context.request_id if context else None,
            correlation_id=context.correlation_id if context else None,
            trace_id=context.trace_id if context else None,
        )
        self._sessions[sid] = session
        self._active_session_id = sid
        self._metrics.vision_sessions += 1
        self.state["sessions_opened"] = self.state.get("sessions_opened", 0) + 1
        self.logger.info(f"EyesAgent: session started | session_id={sid}")
        return sid

    async def stop_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return None
        session.ended_at = datetime.utcnow().isoformat()
        if self._active_session_id == session_id:
            self._active_session_id = None
        self.logger.info(
            f"EyesAgent: session closed | session_id={session_id} "
            f"ops={session.operations_count}"
        )
        return session.to_dict()

    # ─── Frame Processing Pipeline ────────────────────────────────────────────

    def process_frame(
        self,
        frame,
        session_id: Optional[str] = None,
        context: Optional[PerceptionContext] = None,
    ) -> VisionResult:
        """
        Full vision pipeline on a raw frame (numpy array or None for mock).
        Returns VisionResult with all detections.
        """
        t0 = time.perf_counter()
        sid = session_id or self._active_session_id or "default"
        frame_id = str(uuid.uuid4())

        # Validate input
        if frame is not None and _HAS_NUMPY:
            if not isinstance(frame, np.ndarray):
                self.logger.warning("EyesAgent: invalid frame type — skipping")
                frame = None

        try:
            # Object detection
            raw_objects = self._provider.detect_objects(
                frame, {"confidence_threshold": self._obj_conf}
            )
            objects = [
                DetectedObject(
                    label=o.get("label", o.get("class", "unknown")),
                    confidence=float(o.get("confidence", 0.0)),
                    bbox=BoundingBox(**o["bbox"]) if "bbox" in o else BoundingBox(),
                    attributes=o.get("attributes", {}),
                )
                for o in raw_objects[: self._max_objects]
                if float(o.get("confidence", 0.0)) >= self._obj_conf
            ]

            # Face detection
            raw_faces = self._provider.detect_faces(
                frame, {"confidence_threshold": self._face_conf}
            )
            faces = [
                DetectedFace(
                    face_id=f.get("face_id", str(uuid.uuid4())),
                    identity=f.get("identity", "unknown"),
                    confidence=float(f.get("confidence", 0.0)),
                    bbox=BoundingBox(**f["bbox"]) if "bbox" in f else BoundingBox(),
                    emotion=f.get("emotion", "neutral"),
                    landmarks=f.get("landmarks", {}),
                )
                for f in raw_faces[: self._max_faces]
                if float(f.get("confidence", 0.0)) >= self._face_conf
            ]

            # Scene classification
            scene = self._provider.classify_scene(frame, {})
            scene_label = scene.get("label", "unknown")
            scene_conf = float(scene.get("confidence", 0.0))

            # OCR
            ocr_text = self._provider.extract_ocr(frame, {})

            # Motion detection
            motion = self._provider.detect_motion(frame, self._prev_frame, {
                "motion_threshold": self._motion_threshold
            })
            self._prev_frame = frame

            # Attention zones (top-confidence objects + faces)
            attention_zones = self._compute_attention_zones(objects, faces)

            # Overall confidence
            confidences = (
                [o.confidence for o in objects] +
                [f.confidence for f in faces] +
                ([scene_conf] if scene_conf > 0 else [])
            )
            overall_conf = round(sum(confidences) / max(1, len(confidences)), 4)

            processing_ms = round((time.perf_counter() - t0) * 1000, 2)

            result = VisionResult(
                frame_id=frame_id,
                session_id=sid,
                provider=self._provider.name,
                objects=objects,
                faces=faces,
                scene_label=scene_label,
                scene_confidence=scene_conf,
                ocr_text=ocr_text,
                motion_detected=motion.get("detected", False),
                motion_score=float(motion.get("score", 0.0)),
                attention_zones=attention_zones,
                overall_confidence=overall_conf,
                processing_ms=processing_ms,
            )

            # Update metrics
            self._metrics.frames_processed += 1
            self._metrics.objects_detected += len(objects)
            self._metrics.faces_detected += len(faces)
            self._metrics.total_processing_ms += processing_ms
            self.state["frames_processed"] = self._metrics.frames_processed

            # Update session
            if sid in self._sessions:
                self._sessions[sid].operations_count += 1

            # Audit
            self._audit(sid, "process_frame", overall_conf, processing_ms, True,
                        f"objects={len(objects)} faces={len(faces)} scene={scene_label}")

            return result

        except Exception as e:
            self.logger.error(f"EyesAgent.process_frame: {e}")
            self._metrics.error_count += 1
            self.state["errors"] = self.state.get("errors", 0) + 1
            self._audit(sid, "process_frame", 0.0, 0.0, False, str(e))
            return VisionResult(frame_id=frame_id, session_id=sid, provider=self._provider.name)

    def _compute_attention_zones(
        self, objects: List[DetectedObject], faces: List[DetectedFace]
    ) -> List[Dict[str, Any]]:
        zones = []
        for f in faces:
            zones.append({
                "type": "face",
                "bbox": f.bbox.to_dict(),
                "confidence": f.confidence,
                "priority": "high",
            })
        for o in sorted(objects, key=lambda x: x.confidence, reverse=True)[:3]:
            zones.append({
                "type": "object",
                "label": o.label,
                "bbox": o.bbox.to_dict(),
                "confidence": o.confidence,
                "priority": "medium",
            })
        return zones

    # ─── Vision History & Replay ──────────────────────────────────────────────

    def get_vision_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        history = list(self._frame_history)
        return [r.to_dict() for r in history[-limit:]]

    def replay_session(self, session_id: str) -> List[Dict[str, Any]]:
        return [
            r.to_dict()
            for r in self._frame_history
            if r.session_id == session_id
        ]

    # ─── Metrics & Audit ─────────────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics.as_dict(),
            "avg_processing_ms": self._metrics.avg_processing_ms(),
            "provider": self._provider.name,
            "provider_available": self._provider.available,
            "active_sessions": len(self._sessions),
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
            agent_type="eyes",
            operation=operation,
            provider=self._provider.name,
            success=success,
            confidence=confidence,
            processing_ms=processing_ms,
            summary=summary,
        )
        self._audit_trail.append(entry)

    # ─── Broker Collaboration ─────────────────────────────────────────────────

    async def _broadcast_vision_result(self, result: VisionResult):
        """Publish vision result to broker for downstream agents."""
        if not self._message_broker:
            return
        try:
            from orchestrator.agent_communication import MessageType, MessagePriority
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=None,
                message_type=MessageType.PERCEPTION_INPUT,
                content={
                    "input_type": "vision",
                    "session_id": result.session_id,
                    "frame_id": result.frame_id,
                    "objects": len(result.objects),
                    "faces": len(result.faces),
                    "scene": result.scene_label,
                    "motion": result.motion_detected,
                    "confidence": result.overall_confidence,
                    "timestamp": result.timestamp,
                },
                priority=MessagePriority.NORMAL,
            )
        except Exception as e:
            self.logger.debug(f"EyesAgent: broker publish failed: {e}")

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

        if action in ("process_frame", "analyze_frame", "detect"):
            # Accept base64 or raw bytes — decode to numpy if possible
            frame = self._decode_frame(data)
            sid = data.get("session_id", self._active_session_id)
            result = self.process_frame(frame, session_id=sid)
            self._frame_history.append(result)
            await self._broadcast_vision_result(result)
            return result.to_dict()

        if action == "get_history":
            return {"history": self.get_vision_history(data.get("limit", 50))}

        if action == "replay_session":
            return {"frames": self.replay_session(data.get("session_id", ""))}

        if action == "get_metrics":
            return self.get_metrics()

        if action == "get_audit":
            return {"audit": self.get_audit_trail(data.get("limit", 100))}

        if action == "get_status":
            return await self.get_status()

        if action == "get_health":
            return await self.get_health()

        if action == "switch_provider":
            new_name = data.get("provider", "mock")
            new_cfg = data.get("provider_config", {})
            self._provider = build_vision_provider(new_name, new_cfg)
            self.state["provider"] = self._provider.name
            return {"provider": self._provider.name, "available": self._provider.available}

        return await super().execute_task(task)

    def _decode_frame(self, data: Dict[str, Any]):
        """Decode frame from task data — supports base64, bytes, or None."""
        if not _HAS_NUMPY:
            return None
        raw = data.get("frame") or data.get("image")
        if raw is None:
            return None
        try:
            import base64
            if isinstance(raw, str):
                raw = base64.b64decode(raw)
            arr = np.frombuffer(raw, dtype=np.uint8)
            try:
                import cv2
                return cv2.imdecode(arr, cv2.IMREAD_COLOR)
            except Exception:
                return arr
        except Exception as e:
            self.logger.warning(f"EyesAgent: frame decode failed: {e}")
            return None

    # ─── State Update ─────────────────────────────────────────────────────────

    async def _update_state(self):
        await super()._update_state()
        self.state["frames_processed"] = self._metrics.frames_processed
        self.state["active_sessions"] = len(self._sessions)
        self.state["provider"] = self._provider.name
