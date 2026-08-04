"""
Conversation Manager — Phase 9
Session state, history, topic tracking, summarization,
multi-turn consistency. Config-driven.
"""
from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional


@dataclass
class ConversationTurn:
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    role: str = "user"          # user | assistant | system
    text: str = ""
    language: str = "en"
    intent: str = "analyze"
    topics: List[str] = field(default_factory=list)
    quality_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationState:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    turn_count: int = 0
    current_topics: List[str] = field(default_factory=list)
    dominant_language: str = "en"
    topic_switches: int = 0
    quality_trend: str = "stable"   # improving | stable | degrading

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConversationManager:
    """
    Manages conversation sessions, history, topic continuity,
    and multi-turn consistency.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = (config or {}).get("conversation", {})
        self._max_history = int(cfg.get("max_history_per_session", 200))
        self._max_sessions = int(cfg.get("max_active_sessions", 500))
        self._context_window = int(cfg.get("context_window", 10))
        self._topic_switch_threshold = float(cfg.get("topic_switch_threshold", 0.40))
        self._summary_trigger = int(cfg.get("summary_trigger_length", 50))

        # session_id → ConversationState
        self._states: Dict[str, ConversationState] = {}
        # session_id → deque of ConversationTurn
        self._histories: Dict[str, Deque[ConversationTurn]] = {}

    # ── Session lifecycle ─────────────────────────────────────────────────────

    def create_session(
        self,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> ConversationState:
        if len(self._states) >= self._max_sessions:
            # Evict oldest session
            oldest = min(self._states, key=lambda s: self._states[s].started_at)
            self._states.pop(oldest, None)
            self._histories.pop(oldest, None)

        state = ConversationState(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        self._states[state.session_id] = state
        self._histories[state.session_id] = deque(maxlen=self._max_history)
        return state

    def get_session(self, session_id: str) -> Optional[ConversationState]:
        return self._states.get(session_id)

    def end_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        state = self._states.pop(session_id, None)
        self._histories.pop(session_id, None)
        return state.to_dict() if state else None

    # ── Turn management ───────────────────────────────────────────────────────

    def add_turn(
        self,
        session_id: str,
        role: str,
        text: str,
        language: str = "en",
        intent: str = "analyze",
        topics: Optional[List[str]] = None,
        quality_score: float = 0.0,
    ) -> Optional[ConversationTurn]:
        state = self._states.get(session_id)
        if not state:
            return None

        turn = ConversationTurn(
            role=role,
            text=text,
            language=language,
            intent=intent,
            topics=topics or [],
            quality_score=quality_score,
        )
        self._histories[session_id].append(turn)
        state.turn_count += 1
        state.updated_at = datetime.utcnow().isoformat()
        state.dominant_language = language

        # Topic continuity tracking
        if topics:
            prev_topics = set(state.current_topics)
            new_topics = set(topics)
            overlap = len(prev_topics & new_topics) / max(1, len(prev_topics | new_topics))
            if prev_topics and overlap < self._topic_switch_threshold:
                state.topic_switches += 1
            state.current_topics = topics

        # Quality trend
        history = list(self._histories[session_id])
        if len(history) >= 3:
            recent = [t.quality_score for t in history[-3:]]
            if recent[-1] > recent[0] + 0.05:
                state.quality_trend = "improving"
            elif recent[-1] < recent[0] - 0.05:
                state.quality_trend = "degrading"
            else:
                state.quality_trend = "stable"

        return turn

    def get_history(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        history = list(self._histories.get(session_id, []))
        if limit:
            history = history[-limit:]
        return [t.to_dict() for t in history]

    def get_context_window(self, session_id: str) -> List[Dict[str, Any]]:
        """Return the last N turns for context propagation."""
        return self.get_history(session_id, limit=self._context_window)

    def summarize_session(self, session_id: str) -> Dict[str, Any]:
        """Generate a lightweight session summary."""
        state = self._states.get(session_id)
        history = list(self._histories.get(session_id, []))
        if not state or not history:
            return {"error": "session_not_found"}

        user_turns = [t for t in history if t.role == "user"]
        all_topics: List[str] = []
        for t in history:
            all_topics.extend(t.topics)

        from collections import Counter
        top_topics = [t for t, _ in Counter(all_topics).most_common(5)]

        return {
            "session_id": session_id,
            "turn_count": state.turn_count,
            "user_turns": len(user_turns),
            "dominant_language": state.dominant_language,
            "top_topics": top_topics,
            "topic_switches": state.topic_switches,
            "quality_trend": state.quality_trend,
            "started_at": state.started_at,
            "updated_at": state.updated_at,
        }

    def active_session_count(self) -> int:
        return len(self._states)
