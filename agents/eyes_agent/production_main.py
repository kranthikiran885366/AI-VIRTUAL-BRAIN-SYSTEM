"""
Production EyesAgent — Phase 12.

Full lifecycle integration with BaseAgent orchestrator.
Provider-abstracted vision pipeline: no hard dependency on cv2/mediapipe/torch.
All vision operations go through VisionProvider interface.

Task dispatch actions:
  analyze_frame    — full analysis of an image frame
  detect_objects   — object detection only
  detect_faces     — face detection only
  run_ocr          — optical character recognition
  classify_scene   — scene classification
  get_history      — recent vision results
  get_metrics      — operational metrics
  get_status       — agent status
  get_health       — health check
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
        VisionResult, VisionFrame, PerceptionSession,
        PerceptionMetrics, PerceptionAuditEntry,
    )
    from agents.perception_agent.providers.vision_provider import (
        VisionProvider, MockVisionProvider,
    )
except ImportError:
    from ..perception_agent.models import (  # type: ignore
        VisionResult, VisionFrame, PerceptionSession,
        PerceptionMetrics, PerceptionAuditEntry,
    )
    from ..perception_agent.providers.vision_provider import (  # type: ignore
        VisionProvider, MockVisionProvider,
    )


class EyesAgent(BaseAgent):
    """
    Production Vision Agent.

    Wraps VisionProvider for hardware-agnostic frame analysis.
    Falls back to MockVisionProvider when no real provider is available.
    """

    DEFAULT_MAX_HISTORY = 200
    DEFAULT_MAX_AUDIT   = 500

    def __init__(
        self,
        agent_id: str = "eyes_agent",
        config: Optional[Dict[str, Any]] = None,
        vision_provider: Optional[VisionProvider] = None,
    ):
        super().__init__(agent_id=agent_id, agent_type="perception")
        self.config = config or {}
        self._vision_provider: VisionProvider = vision_provider or MockVisionProvider()

        # Session registry
        self._active_sessions: Dict[str, PerceptionSession] = {}
        self._vision_history: Deque[Dict[str, Any]] = deque(
            maxlen=self.config.get("max_history", self.DEFAULT_MAX_HISTORY)
        )
        self._audit_log: Deque[PerceptionAuditEntry] = deque(
            maxlen=self.config.get("max_audit", self.DEFAULT_MAX_AUDIT)
        )
        self.metrics = PerceptionMetrics()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialize(self):
        try:
            await super().initialize()
        except Exception:
            pass
        if not hasattr(self, "logger") or self.logger is None:
            self.logger = logging.getLogger(f"EyesAgent.{self.agent_id}")

        self.state.update({
            "provider": self._vision_provider.provider_name(),
            "frames_processed": 0,
            "sessions_active": 0,
            "last_active": None,
        })
        self.logger.info(
            f"EyesAgent '{self.agent_id}' initialized — "
            f"provider: {self._vision_provider.provider_name()}"
        )

    async def _update_state(self):
        try:
            await super()._update_state()
        except Exception:
            pass
        self.state["frames_processed"] = self.metrics.frames_processed
        self.state["sessions_active"]  = len(self._active_sessions)

    async def shutdown(self):
        self._active_sessions.clear()
        self.logger.info(f"EyesAgent '{self.agent_id}' shut down.")

    # ── Provider Swap ─────────────────────────────────────────────────────────

    def set_provider(self, provider: VisionProvider) -> None:
        """Hot-swap the vision provider at runtime."""
        self._vision_provider = provider
        self.logger.info(f"EyesAgent: vision provider set to {provider.provider_name()}")

    # ── Session Management ────────────────────────────────────────────────────

    def start_vision_session(
        self,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> PerceptionSession:
        session = PerceptionSession(
            agent_type="eyes",
            request_id=request_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            provider=self._vision_provider.provider_name(),
        )
        self._active_sessions[session.session_id] = session
        self.metrics.vision_sessions += 1
        return session

    def end_vision_session(self, session_id: str) -> None:
        if session_id in self._active_sessions:
            self._active_sessions[session_id].ended_at = datetime.utcnow().isoformat()

    # ── Core Vision Operations ────────────────────────────────────────────────

    def analyze_frame(
        self,
        frame_bytes: bytes,
        session_id: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> VisionResult:
        """Run full frame analysis through the vision provider."""
        start = time.time()
        cfg = {**(config or {}), "session_id": session_id}
        try:
            result = self._vision_provider.analyze_frame(frame_bytes, cfg)
            result.session_id = session_id
        except Exception as exc:
            self.logger.error(f"EyesAgent.analyze_frame error: {exc}")
            self.metrics.error_count += 1
            result = VisionResult(session_id=session_id, provider="error", metadata={"error": str(exc)})

        ms = round((time.time() - start) * 1000, 2)
        self._record_frame(result, ms, session_id)
        return result

    def detect_objects(self, frame_bytes: bytes, session_id: str = "") -> List[Dict[str, Any]]:
        try:
            objs = self._vision_provider.detect_objects(frame_bytes)
            self.metrics.objects_detected += len(objs)
            return [o.to_dict() for o in objs]
        except Exception as exc:
            self.logger.error(f"EyesAgent.detect_objects error: {exc}")
            self.metrics.error_count += 1
            return []

    def detect_faces(self, frame_bytes: bytes, session_id: str = "") -> List[Dict[str, Any]]:
        try:
            faces = self._vision_provider.detect_faces(frame_bytes)
            self.metrics.faces_detected += len(faces)
            return [f.to_dict() for f in faces]
        except Exception as exc:
            self.logger.error(f"EyesAgent.detect_faces error: {exc}")
            self.metrics.error_count += 1
            return []

    def run_ocr(self, frame_bytes: bytes, session_id: str = "") -> str:
        try:
            text = self._vision_provider.run_ocr(frame_bytes)
            self.metrics.ocr_operations += 1
            return text
        except Exception as exc:
            self.logger.error(f"EyesAgent.run_ocr error: {exc}")
            self.metrics.error_count += 1
            return ""

    def classify_scene(self, frame_bytes: bytes, session_id: str = "") -> str:
        try:
            return self._vision_provider.classify_scene(frame_bytes)
        except Exception as exc:
            self.logger.error(f"EyesAgent.classify_scene error: {exc}")
            self.metrics.error_count += 1
            return "unknown"

    # ── History & Audit ───────────────────────────────────────────────────────

    def _record_frame(self, result: VisionResult, ms: float, session_id: str) -> None:
        self.metrics.frames_processed += 1
        self.metrics.total_processing_ms += ms
        self.state["last_active"] = datetime.utcnow().isoformat()
        self._vision_history.append({
            "frame_id": result.frame_id,
            "session_id": session_id,
            "scene": result.scene_label,
            "objects": len(result.objects),
            "faces": len(result.faces),
            "confidence": result.overall_confidence,
            "timestamp": result.timestamp,
        })
        self._audit_log.append(PerceptionAuditEntry(
            session_id=session_id,
            agent_type="eyes",
            operation="analyze_frame",
            provider=self._vision_provider.provider_name(),
            success=True,
            confidence=result.overall_confidence,
            processing_ms=ms,
            summary=f"scene={result.scene_label}, objects={len(result.objects)}, faces={len(result.faces)}",
        ))

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        history = list(self._vision_history)
        return history[-limit:]

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in list(self._audit_log)[-limit:]]

    # ── execute_task (Orchestrator Contract) ──────────────────────────────────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action     = (task.get("action", "") or "").lower()
        data       = task.get("input_data", {}) or {}
        req_id     = task.get("request_id") or data.get("request_id")
        corr_id    = task.get("correlation_id") or data.get("correlation_id")
        tr_id      = task.get("trace_id") or data.get("trace_id")

        # Frame bytes: accept raw bytes or base64-encoded string
        frame_bytes: bytes = b""
        raw = data.get("frame") or data.get("image") or data.get("frame_bytes") or b""
        if isinstance(raw, str):
            import base64
            try:
                frame_bytes = base64.b64decode(raw)
            except Exception:
                frame_bytes = raw.encode("utf-8")
        elif isinstance(raw, (bytes, bytearray)):
            frame_bytes = bytes(raw)

        session = self.start_vision_session(req_id, corr_id, tr_id)
        sid = session.session_id

        try:
            if action in ("analyze_frame", "analyze", "process_frame"):
                result = self.analyze_frame(frame_bytes, sid)
                return {**result.to_dict(), "session_id": sid}

            if action == "detect_objects":
                return {"objects": self.detect_objects(frame_bytes, sid), "session_id": sid}

            if action == "detect_faces":
                return {"faces": self.detect_faces(frame_bytes, sid), "session_id": sid}

            if action == "run_ocr":
                return {"text": self.run_ocr(frame_bytes, sid), "session_id": sid}

            if action == "classify_scene":
                return {"scene": self.classify_scene(frame_bytes, sid), "session_id": sid}

            if action == "get_history":
                limit = data.get("limit", 20)
                return {"history": self.get_history(limit), "total": self.metrics.frames_processed}

            if action == "get_metrics":
                return {"metrics": self.metrics.as_dict()}

            if action == "get_status":
                return await self.get_status()

            if action == "get_health":
                return await self.get_health()

            # Default: full analysis
            result = self.analyze_frame(frame_bytes, sid)
            return {**result.to_dict(), "session_id": sid}

        finally:
            self.end_vision_session(sid)

    # ── Health ────────────────────────────────────────────────────────────────

    async def get_health(self) -> Dict[str, Any]:
        return {
            "healthy": True,
            "agent_id": self.agent_id,
            "provider": self._vision_provider.provider_name(),
            "provider_available": self._vision_provider.is_available(),
            "frames_processed": self.metrics.frames_processed,
            "error_count": self.metrics.error_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
