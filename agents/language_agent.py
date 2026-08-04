"""
Production Language Agent — Phase 9
Wraps LanguageEngine. Backward compatible with all Phase 1–8 execute_task actions.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent  # type: ignore

try:
    from agents.language_agent.engine import LanguageEngine
except ImportError:
    try:
        from language_agent.engine import LanguageEngine  # type: ignore
    except ImportError:
        LanguageEngine = None  # type: ignore

logger = logging.getLogger(__name__)


class LanguageAgent(BaseAgent):
    """
    Production Language Agent — Phase 9.
    Preserves all Phase 1–8 execute_task actions.
    Adds full language intelligence via LanguageEngine.
    """

    def __init__(self, agent_id: str = "language_agent") -> None:
        super().__init__(agent_id, "language")
        # Phase 1–8 backward-compat state
        self.processing_history: List[Dict] = []
        # Phase 9: production engine
        self.engine: Optional[LanguageEngine] = (
            LanguageEngine() if LanguageEngine else None
        )

    async def initialize(self) -> None:
        await super().initialize()
        self.state.update({"texts_processed": 0})
        if self.engine:
            await self.engine.start()
        logger.info("language_agent.initialized agent_id=%s engine=%s",
                    self.agent_id, self.engine is not None)

    async def shutdown(self) -> None:
        if self.engine:
            await self.engine.stop()
        await super().shutdown()
        logger.info("language_agent.shutdown agent_id=%s", self.agent_id)

    async def _update_state(self) -> None:
        self.state.update({
            "texts_processed": len(self.processing_history),
            "last_active": datetime.utcnow().isoformat(),
        })

    # ── Phase 1–8 backward-compat helpers ────────────────────────────────────

    def _detect_language_task(self, text: str, action: str = "") -> str:
        """Preserved from Phase 1 for backward compatibility."""
        if self.engine:
            result = self.engine._understanding.detect_intent(text, action)
            return result["intent"]
        # Fallback keyword detection
        lower = (text + " " + action).lower()
        if any(w in lower for w in ["summarize", "summary", "tldr", "brief", "shorten"]):
            return "summarize"
        if any(w in lower for w in ["translate", "in spanish", "in french", "in german"]):
            return "translate"
        if any(w in lower for w in ["improve", "rewrite", "rephrase", "enhance"]):
            return "improve"
        if any(w in lower for w in ["grammar", "spelling", "correct", "proofread"]):
            return "proofread"
        if any(w in lower for w in ["formal", "professional", "business"]):
            return "formalize"
        if any(w in lower for w in ["casual", "informal", "simple", "simplify"]):
            return "simplify"
        if any(w in lower for w in ["expand", "elaborate", "longer"]):
            return "expand"
        return "analyze"

    async def process(
        self, text: str, task_type: str = "analyze", options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Phase 1–8 compatible process() method — now backed by LanguageEngine."""
        options = options or {}
        self.processing_history.append({
            "task_type": task_type,
            "word_count": len(text.split()),
            "timestamp": datetime.utcnow().isoformat(),
        })
        if len(self.processing_history) > 500:
            self.processing_history = self.processing_history[-500:]

        if not self.engine:
            return {"input": text[:200], "task_type": task_type,
                    "error": "engine_unavailable"}

        if task_type == "summarize":
            return await self.engine.summarize(text, options.get("length", "medium"))
        if task_type in ("improve", "rewrite"):
            return await self.engine.improve(text)
        if task_type == "proofread":
            return await self.engine.proofread(text)
        if task_type == "formalize":
            return await self.engine.formalize(text)
        if task_type == "simplify":
            return await self.engine.simplify(text)
        if task_type == "translate":
            return await self.engine.translate(text, options.get("target_language", "en"))
        if task_type == "document":
            return await self.engine.process_document(text)
        if task_type == "quality":
            return await self.engine.quality_report(text)
        # Default: analyze
        return await self.engine.analyze(text)

    # ── execute_task ──────────────────────────────────────────────────────────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {}) or {}
        text = data.get("content", data.get("text", ""))
        correlation_id = task.get("correlation_id")
        trace_id = task.get("trace_id")

        # ── Phase 9 explicit actions ──────────────────────────────────────────

        if action == "analyze" and self.engine:
            return await self.engine.analyze(text, correlation_id)

        if action == "summarize" and self.engine:
            return await self.engine.summarize(
                text, data.get("length", "medium"), correlation_id
            )

        if action == "improve" and self.engine:
            return await self.engine.improve(text, correlation_id)

        if action == "proofread" and self.engine:
            return await self.engine.proofread(text, correlation_id)

        if action == "formalize" and self.engine:
            return await self.engine.formalize(text, correlation_id)

        if action == "simplify" and self.engine:
            return await self.engine.simplify(text, correlation_id)

        if action == "expand" and self.engine:
            result = self.engine._improvement.expand(text)
            return {"status": "ok", "operation": "expand", **result}

        if action == "translate" and self.engine:
            return await self.engine.translate(
                text, data.get("target_language", "en"), correlation_id
            )

        if action == "process_document" and self.engine:
            return await self.engine.process_document(
                text, data.get("doc_type", "plain"), correlation_id
            )

        if action == "quality_report" and self.engine:
            return await self.engine.quality_report(text, correlation_id)

        if action == "detect_language" and self.engine:
            result = self.engine._understanding.detect_language(text)
            return {"status": "ok", "operation": "detect_language", **result}

        if action == "extract_entities" and self.engine:
            entities = self.engine._understanding.extract_entities(text)
            return {"status": "ok", "operation": "extract_entities",
                    "entities": entities, "count": len(entities)}

        if action == "extract_keywords" and self.engine:
            keywords = self.engine._understanding.extract_keywords(
                text, data.get("max_keywords", 15)
            )
            return {"status": "ok", "operation": "extract_keywords",
                    "keywords": keywords, "count": len(keywords)}

        if action == "semantic_analysis" and self.engine:
            lang = self.engine._understanding.detect_language(text)["language"]
            result = self.engine._semantic.analyze(text, lang)
            return {"status": "ok", "operation": "semantic_analysis",
                    **result.to_dict()}

        if action == "begin_session" and self.engine:
            session = self.engine.begin_session(
                request_id=data.get("request_id"),
                correlation_id=data.get("correlation_id", correlation_id),
                trace_id=data.get("trace_id", trace_id),
                user_id=data.get("user_id"),
                conversation_id=data.get("conversation_id"),
            )
            return {"status": "ok", "session": session.to_dict()}

        if action == "end_session" and self.engine:
            result = self.engine.end_session()
            return {"status": "ok", "session": result}

        if action == "get_metrics" and self.engine:
            return {"status": "ok", "metrics": self.engine.get_metrics()}

        if action == "get_analytics" and self.engine:
            return {"status": "ok", "analytics": self.engine.get_analytics()}

        if action == "get_audit_trail" and self.engine:
            limit = int(data.get("limit", 100))
            return {"status": "ok",
                    "audit_trail": self.engine.get_audit_trail(limit)}

        if action == "get_history" and self.engine:
            limit = int(data.get("limit", 50))
            return {"status": "ok", "history": self.engine.get_history(limit)}

        if action == "create_conversation" and self.engine:
            state = self.engine.create_conversation(
                data.get("user_id"), data.get("conversation_id")
            )
            return {"status": "ok", "conversation": state}

        if action == "add_turn" and self.engine:
            turn = self.engine.add_conversation_turn(
                data.get("session_id", ""),
                data.get("role", "user"),
                text,
                language=data.get("language", "en"),
                intent=data.get("intent", "analyze"),
                topics=data.get("topics", []),
                quality_score=float(data.get("quality_score", 0.0)),
            )
            return {"status": "ok", "turn": turn}

        if action == "get_conversation_history" and self.engine:
            history = self.engine.get_conversation_history(
                data.get("session_id", ""),
                data.get("limit"),
            )
            return {"status": "ok", "history": history, "count": len(history)}

        if action == "summarize_conversation" and self.engine:
            summary = self.engine.summarize_conversation(data.get("session_id", ""))
            return {"status": "ok", "summary": summary}

        # ── Phase 1–8 fallback (backward compat) ─────────────────────────────
        task_type = self._detect_language_task(text, action)
        options = {"length": data.get("length", "medium"),
                   "target_language": data.get("target_language", "en")}
        return await self.process(text, task_type, options)
