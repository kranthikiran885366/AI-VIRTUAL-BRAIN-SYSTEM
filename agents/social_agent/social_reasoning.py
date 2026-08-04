"""
Social Reasoning Engine — Phase 13

Implements:
- Social cue analysis (emotion, intent, formality, politeness)
- Rapport and trust estimation
- Communication strategy selection
- Empathy interface
- Ambiguity handling
- Context-aware response adaptation
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Lexical resources ──────────────────────────────────────────────────────────

_POSITIVE_WORDS = frozenset([
    "happy", "great", "wonderful", "amazing", "excited", "love", "excellent",
    "fantastic", "joy", "glad", "pleased", "delighted", "thrilled", "good",
])
_NEGATIVE_WORDS = frozenset([
    "sad", "angry", "upset", "terrible", "awful", "horrible", "frustrated",
    "worried", "anxious", "disappointed", "annoyed", "bad", "hate", "fear",
])
_FORMAL_WORDS = frozenset([
    "please", "kindly", "would you", "could you", "thank you", "regards",
    "sincerely", "respectfully", "appreciate", "request",
])
_INFORMAL_WORDS = frozenset([
    "hey", "yo", "sup", "gonna", "wanna", "lol", "omg", "btw", "tbh", "ngl",
])
_GREETING_PATTERNS = [
    r"\b(hi|hello|hey|greetings|good\s+(morning|afternoon|evening|day))\b",
    r"👋|🙋",
]
_FAREWELL_PATTERNS = [
    r"\b(bye|goodbye|see\s+you|farewell|take\s+care|later|ciao)\b",
    r"👋",
]
_QUESTION_PATTERNS = [
    r"\b(what|when|where|why|how|who|can|could|would|should|is|are|do|does|did)\b.*\?",
    r"\?",
]
_EMPATHY_TRIGGERS = frozenset([
    "sad", "upset", "worried", "anxious", "frustrated", "disappointed",
    "hurt", "scared", "lonely", "overwhelmed",
])
_POLITENESS_MARKERS = frozenset([
    "please", "thank you", "thanks", "sorry", "excuse me", "pardon",
    "appreciate", "grateful", "kindly",
])


def _lower(text: str) -> str:
    return text.lower()


def _match_any(text: str, patterns: List[str]) -> bool:
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


class SocialReasoning:
    """
    Stateless social reasoning engine.
    All methods are pure functions of their inputs.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyze(
        self,
        content: str,
        sender: str = "user",
        relationship_context: Optional[Dict[str, Any]] = None,
        session_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Full social analysis pipeline.
        Returns a structured analysis dict consumed by SocialAgent.
        """
        rel = relationship_context or {}
        lower = _lower(content)

        emotion_sentiment, detected_emotions = self._detect_emotions(lower)
        interaction_type = self._detect_interaction_type(content, lower)
        formality = self._analyze_formality(lower)
        intent = self._interpret_intent(content, lower, interaction_type)
        politeness = self._estimate_politeness(lower)
        empathy_needed = self._needs_empathy(lower, emotion_sentiment)
        ambiguous = self._is_ambiguous(content, interaction_type)
        rapport = self._estimate_rapport(rel)
        trust = float(rel.get("trust_score", 0.5))
        strategy = self._select_strategy(
            interaction_type, formality, emotion_sentiment, trust, rapport
        )

        return {
            "sender": sender,
            "content": content,
            "interaction_type": interaction_type,
            "emotions": detected_emotions,
            "emotion_sentiment": emotion_sentiment,
            "formality": formality,
            "intent": intent,
            "politeness_score": politeness,
            "empathy_needed": empathy_needed,
            "ambiguous": ambiguous,
            "rapport_score": rapport,
            "trust_score": trust,
            "communication_strategy": strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def build_response_prefix(
        self,
        analysis: Dict[str, Any],
        relationship_context: Dict[str, Any],
    ) -> str:
        """Build a contextual prefix for the response based on analysis."""
        parts: List[str] = []
        sentiment = analysis.get("emotion_sentiment", "neutral")
        status = relationship_context.get("status", "new")
        interaction_type = analysis.get("interaction_type", "statement")

        if analysis.get("empathy_needed"):
            parts.append("I understand this might be difficult. ")
        elif sentiment == "positive" and interaction_type not in ("greeting", "farewell"):
            parts.append("I'm glad to hear that! ")

        if interaction_type not in ("greeting", "farewell"):
            if status == "trusted":
                parts.append("Based on our ongoing conversations, ")
            elif status == "distrustful":
                parts.append("I want to be clear and transparent: ")

        return "".join(parts)

    def adapt_tone(
        self,
        base_response: str,
        analysis: Dict[str, Any],
        relationship_context: Dict[str, Any],
    ) -> str:
        """Append trust/rapport-based tone adaptation to a response."""
        trust = analysis.get("trust_score", 0.5)
        interaction_type = analysis.get("interaction_type", "statement")
        if interaction_type in ("greeting", "farewell"):
            return base_response
        if trust > 0.7:
            return base_response + " I'm here for you — feel free to share more."
        if trust < 0.3:
            return base_response + " Please let me know if you need clarification."
        return base_response

    # ── Private helpers ────────────────────────────────────────────────────────

    def _detect_emotions(self, lower: str) -> Tuple[str, List[str]]:
        pos = any(w in lower for w in _POSITIVE_WORDS)
        neg = any(w in lower for w in _NEGATIVE_WORDS)
        if pos and not neg:
            return "positive", ["positive"]
        if neg and not pos:
            return "negative", ["negative"]
        if pos and neg:
            return "mixed", ["positive", "negative"]
        return "neutral", ["neutral"]

    def _detect_interaction_type(self, content: str, lower: str) -> str:
        if _match_any(content, _GREETING_PATTERNS):
            return "greeting"
        if _match_any(content, _FAREWELL_PATTERNS):
            return "farewell"
        if _match_any(content, _QUESTION_PATTERNS):
            return "question"
        return "statement"

    def _analyze_formality(self, lower: str) -> str:
        formal_score = sum(1 for w in _FORMAL_WORDS if w in lower)
        informal_score = sum(1 for w in _INFORMAL_WORDS if w in lower)
        if formal_score > informal_score:
            return "formal"
        if informal_score > formal_score:
            return "informal"
        return "neutral"

    def _interpret_intent(self, content: str, lower: str, interaction_type: str) -> str:
        if interaction_type == "greeting":
            return "initiate_conversation"
        if interaction_type == "farewell":
            return "end_conversation"
        if interaction_type == "question":
            return "seek_information"
        if any(w in lower for w in ["help", "assist", "support", "need"]):
            return "request_assistance"
        if any(w in lower for w in ["think", "believe", "feel", "opinion"]):
            return "share_perspective"
        return "general_statement"

    def _estimate_politeness(self, lower: str) -> float:
        score = sum(0.2 for w in _POLITENESS_MARKERS if w in lower)
        return min(1.0, round(score, 2))

    def _needs_empathy(self, lower: str, sentiment: str) -> bool:
        if sentiment == "negative":
            return True
        return any(w in lower for w in _EMPATHY_TRIGGERS)

    def _is_ambiguous(self, content: str, interaction_type: str) -> bool:
        if len(content.strip()) < 5:
            return True
        if interaction_type == "statement" and "?" not in content and len(content.split()) < 3:
            return True
        return False

    def _estimate_rapport(self, rel: Dict[str, Any]) -> float:
        trust = float(rel.get("trust_score", 0.5))
        count = int(rel.get("interaction_count", 0))
        bonus = min(0.3, count * 0.01)
        return round(min(1.0, trust * 0.7 + bonus), 3)

    def _select_strategy(
        self,
        interaction_type: str,
        formality: str,
        sentiment: str,
        trust: float,
        rapport: float,
    ) -> str:
        if interaction_type in ("greeting", "farewell"):
            return "social_ritual"
        if sentiment == "negative":
            return "empathetic_support"
        if trust > 0.7 and rapport > 0.6:
            return "collaborative_dialogue"
        if formality == "formal":
            return "professional_response"
        if interaction_type == "question":
            return "informative_response"
        return "conversational_response"
