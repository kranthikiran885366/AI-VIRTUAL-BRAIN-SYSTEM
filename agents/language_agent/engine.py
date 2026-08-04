"""
Language Engine — Phase 9
Production language intelligence orchestrator.
Manages lifecycle, sessions, history, metrics, audit trail.
All thresholds are config-driven.
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

try:
    import yaml as _yaml
    _YAML = True
except ImportError:
    _YAML = False

from .models import LanguageSession, LanguageMetrics
from .understanding import LanguageUnderstanding
from .semantic import SemanticAnalyzer
from .quality import QualityEngine
from .conversation import ConversationManager
from .document import DocumentProcessor
from .improvement import ImprovementPipeline

logger = logging.getLogger(__name__)

_VERSION = "9.0.0"
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "language_config.yaml"


def _load_config() -> Dict[str, Any]:
    if not _YAML or not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = _yaml.safe_load(f) or {}
        return raw.get("language", {})
    except Exception as exc:
        logger.warning("language_engine.config_load_failed error=%s", exc)
        return {}


class LanguageEngine:
    """
    Production Language Intelligence Engine.
    Orchestrates all language subsystems with full lifecycle,
    session management, history, metrics, and audit trail.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        file_cfg = _load_config()
        self._cfg = {**file_cfg, **(config or {})}

        hist_cfg = self._cfg.get("history", {})
        self._max_history = int(hist_cfg.get("max_processing_history", 2000))
        self._max_audit = int(hist_cfg.get("max_audit_trail", 5000))
        self._max_sessions = int(hist_cfg.get("max_session_history", 500))

        self._understanding = LanguageUnderstanding(self._cfg)
        self._semantic = SemanticAnalyzer(self._cfg)
        self._quality = QualityEngine(self._cfg)
        self._conversation = ConversationManager(self._cfg)
        self._document = DocumentProcessor(self._cfg)
        self._improvement = ImprovementPipeline(self._cfg)

        self._history: Deque[Dict] = deque(maxlen=self._max_history)
        self._audit: Deque[Dict] = deque(maxlen=self._max_audit)
        self._session_history: Deque[Dict] = deque(maxlen=self._max_sessions)
        self._metrics = LanguageMetrics()
        self._active_session: Optional[LanguageSession] = None
        self._version = _VERSION
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("language_engine.started version=%s", self._version)

    async def stop(self) -> None:
        self._running = False
        logger.info("language_engine.stopped")

    # ── Session management ────────────────────────────────────────────────────

    def begin_session(
        self,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> LanguageSession:
        session = LanguageSession(
            request_id=request_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        self._active_session = session
        self._metrics.total_sessions += 1
        self._record_audit("session_started", {"session_id": session.session_id})
        return session

    def end_session(self, session: Optional[LanguageSession] = None) -> Optional[Dict]:
        s = session or self._active_session
        if not s:
            return None
        s.ended_at = datetime.utcnow().isoformat()
        self._session_history.append(s.to_dict())
        if self._active_session and self._active_session.session_id == s.session_id:
            self._active_session = None
        self._record_audit("session_ended", {"session_id": s.session_id})
        return s.to_dict()

    # ── Core operations ───────────────────────────────────────────────────────

    async def analyze(
        self, text: str, correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        v = self._understanding.validate_input(text, self._cfg.get("understanding", {}).get("max_text_length", 50000))
        if not v["valid"]:
            return {"status": "error", "errors": v["errors"]}

        lang_result = self._understanding.detect_language(text)
        intent_result = self._understanding.detect_intent(text)
        entities = self._understanding.extract_entities(text)
        keywords = self._understanding.extract_keywords(text)
        ambiguity = self._understanding.detect_ambiguity(text)
        quality = self._quality.evaluate(text)
        semantic = self._semantic.analyze(text, lang_result["language"])
        tokens = self._understanding.estimate_tokens(text)

        self._track_operation("analyze", text, quality.overall_score)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_processing_ms += duration_ms

        result = {
            "status": "ok",
            "operation": "analyze",
            "language": lang_result,
            "intent": intent_result,
            "entities": entities,
            "keywords": keywords,
            "ambiguity": ambiguity,
            "quality": quality.to_dict(),
            "semantic": semantic.to_dict(),
            "tokens_estimated": tokens,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id,
        }
        self._record_audit("analyze", {"tokens": tokens, "duration_ms": duration_ms,
                                        "language": lang_result["language"]})
        return result

    async def summarize(
        self, text: str, length: str = "medium", correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        v = self._understanding.validate_input(text)
        if not v["valid"]:
            return {"status": "error", "errors": v["errors"]}

        summary = self._document.extract_summary(
            text,
            max_sentences={"short": 2, "medium": 4, "long": 7}.get(length, 4),
        )
        original_wc = len(text.split())
        summary_wc = len(summary.split())
        compression = round(summary_wc / max(1, original_wc), 3)

        self._track_operation("summarize", text, 0.0)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_processing_ms += duration_ms

        result = {
            "status": "ok",
            "operation": "summarize",
            "summary": summary,
            "original_word_count": original_wc,
            "summary_word_count": summary_wc,
            "compression_ratio": compression,
            "length": length,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id,
        }
        self._record_audit("summarize", {"length": length, "compression": compression})
        return result

    async def improve(
        self, text: str, correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        v = self._understanding.validate_input(text)
        if not v["valid"]:
            return {"status": "error", "errors": v["errors"]}

        result_data = self._improvement.improve(text)
        quality_before = self._quality.evaluate(text)
        quality_after = self._quality.evaluate(result_data["improved"])

        self._track_operation("improve", text, quality_after.overall_score)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_processing_ms += duration_ms

        return {
            "status": "ok",
            "operation": "improve",
            **result_data,
            "quality_before": quality_before.overall_score,
            "quality_after": quality_after.overall_score,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id,
        }

    async def proofread(
        self, text: str, correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        v = self._understanding.validate_input(text)
        if not v["valid"]:
            return {"status": "error", "errors": v["errors"]}

        quality = self._quality.evaluate(text)
        self._track_operation("proofread", text, quality.overall_score)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_processing_ms += duration_ms

        return {
            "status": "ok",
            "operation": "proofread",
            "quality": quality.to_dict(),
            "issues": quality.suggestions,
            "overall_quality": quality.label,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id,
        }

    async def formalize(
        self, text: str, correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        v = self._understanding.validate_input(text)
        if not v["valid"]:
            return {"status": "error", "errors": v["errors"]}

        result_data = self._improvement.formalize(text)
        self._track_operation("improve", text, 0.0)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_processing_ms += duration_ms

        return {
            "status": "ok",
            "operation": "formalize",
            **result_data,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id,
        }

    async def simplify(
        self, text: str, correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        v = self._understanding.validate_input(text)
        if not v["valid"]:
            return {"status": "error", "errors": v["errors"]}

        result_data = self._improvement.simplify(text)
        self._track_operation("improve", text, 0.0)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_processing_ms += duration_ms

        return {
            "status": "ok",
            "operation": "simplify",
            **result_data,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id,
        }

    async def translate(
        self, text: str, target_language: str = "en",
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        v = self._understanding.validate_input(text)
        if not v["valid"]:
            return {"status": "error", "errors": v["errors"]}

        detected = self._understanding.detect_language(text)
        self._track_operation("translate", text, 0.0)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_processing_ms += duration_ms

        # Provider-independent: return detection + routing info
        return {
            "status": "ok",
            "operation": "translate",
            "source_language": detected["language"],
            "target_language": target_language,
            "detection_confidence": detected["confidence"],
            "text": text,
            "note": "Translation provider not configured. Source language detected.",
            "duration_ms": duration_ms,
            "correlation_id": correlation_id,
        }

    async def process_document(
        self, text: str, doc_type: str = "plain",
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        result = self._document.process(text, doc_type)
        self._track_operation("document", text, result.get("quality_score", 0.0))
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_processing_ms += duration_ms
        result["duration_ms"] = duration_ms
        result["correlation_id"] = correlation_id
        result["status"] = "ok" if result.get("valid") else "error"
        return result

    async def quality_report(
        self, text: str, correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        v = self._understanding.validate_input(text)
        if not v["valid"]:
            return {"status": "error", "errors": v["errors"]}

        quality = self._quality.evaluate(text)
        semantic = self._semantic.analyze(text)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_processing_ms += duration_ms

        return {
            "status": "ok",
            "operation": "quality_report",
            "quality": quality.to_dict(),
            "semantic": semantic.to_dict(),
            "duration_ms": duration_ms,
            "correlation_id": correlation_id,
        }

    # ── Conversation passthrough ───────────────────────────────────────────────

    def create_conversation(
        self, user_id: Optional[str] = None, conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        state = self._conversation.create_session(user_id, conversation_id)
        return state.to_dict()

    def add_conversation_turn(
        self, session_id: str, role: str, text: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        turn = self._conversation.add_turn(session_id, role, text, **kwargs)
        return turn.to_dict() if turn else None

    def get_conversation_history(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        return self._conversation.get_history(session_id, limit)

    def summarize_conversation(self, session_id: str) -> Dict[str, Any]:
        return self._conversation.summarize_session(session_id)

    # ── Observability ─────────────────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        m = self._metrics.as_dict()
        m["version"] = self._version
        m["history_size"] = len(self._history)
        m["audit_size"] = len(self._audit)
        m["avg_processing_ms"] = self._metrics.avg_processing_ms()
        m["active_conversations"] = self._conversation.active_session_count()
        return m

    def get_history(self, limit: int = 50) -> List[Dict]:
        return list(self._history)[-limit:]

    def get_audit_trail(self, limit: int = 100) -> List[Dict]:
        return list(self._audit)[-limit:]

    def get_analytics(self) -> Dict[str, Any]:
        history = list(self._history)
        if not history:
            return {"error": "no_history"}
        ops = [h["operation"] for h in history]
        from collections import Counter
        op_counts = dict(Counter(ops))
        quality_scores = [h["quality_score"] for h in history if h.get("quality_score", 0) > 0]
        return {
            "total_operations": len(history),
            "operations_by_type": op_counts,
            "avg_quality_score": round(sum(quality_scores) / max(1, len(quality_scores)), 4),
            "metrics": self.get_metrics(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _track_operation(self, operation: str, text: str, quality_score: float) -> None:
        tokens = self._understanding.estimate_tokens(text)
        self._metrics.total_operations += 1
        self._metrics.total_tokens += tokens
        counter_map = {
            "analyze": "analyze_count", "summarize": "summarize_count",
            "improve": "improve_count", "translate": "translate_count",
            "proofread": "proofread_count", "document": "document_count",
        }
        attr = counter_map.get(operation)
        if attr:
            setattr(self._metrics, attr, getattr(self._metrics, attr) + 1)

        if self._active_session:
            self._active_session.operations += 1
            self._active_session.tokens_processed += tokens
            if quality_score > 0:
                self._active_session.quality_scores.append(quality_score)

        self._history.append({
            "operation": operation,
            "tokens": tokens,
            "quality_score": quality_score,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def _record_audit(self, event: str, data: Dict[str, Any]) -> None:
        self._audit.append({
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            **data,
        })
