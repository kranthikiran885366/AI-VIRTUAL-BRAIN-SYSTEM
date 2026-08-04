"""
Semantic intent routing for agent selection.

Uses TF–IDF cosine similarity over agent capability profiles (no keyword-only routing).
Optional sentence-transformer embeddings when available for higher-quality matching.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9']+")

# Capability profiles: natural-language descriptions per agent (not keyword lists for routing).
AGENT_CAPABILITY_PROFILES: Dict[str, str] = {
    "memory_agent": (
        "store recall retrieve remember episodic semantic working memory history "
        "consolidate forget past experiences knowledge retention"
    ),
    "emotion_agent": (
        "emotion mood sentiment feeling anxiety stress happiness sadness anger "
        "affective state regulation empathy emotional analysis"
    ),
    "creativity_agent": (
        "creative brainstorm idea invent design story imagination innovation "
        "novel concepts artistic generation"
    ),
    "task_agent": (
        "task todo schedule deadline reminder organize checklist assignment "
        "productivity tracking completion"
    ),
    "reasoning_agent": (
        "analyze logic reason deductive inductive causal argument evidence "
        "inference proof contradiction analytical thinking"
    ),
    "learning_agent": (
        "learn study knowledge acquisition tutorial teaching adapt skill "
        "experience feedback improvement"
    ),
    "planning_agent": (
        "plan goal strategy roadmap milestone timeline decomposition "
        "hierarchical planning resources risks progress"
    ),
    "social_agent": (
        "social relationship communication interaction people dialogue "
        "collaboration community norms"
    ),
    "language_agent": (
        "write code program translate grammar text essay language generation "
        "syntax documentation"
    ),
    "motivation_agent": (
        "motivate inspire encourage persistence goal commitment energy "
        "overcome stuck burnout"
    ),
    "ethics_agent": (
        "ethics moral fairness justice dilemma right wrong values "
        "responsible decision harm prevention"
    ),
    "decision_agent": (
        "decide choice option compare recommend tradeoff utility "
        "multi-criteria decision uncertainty"
    ),
    "perception_agent": (
        "perceive sense detect recognize audio visual pattern classification "
        "environment awareness threat"
    ),
    "ear_agent": (
        "listen speech audio hearing transcription sound speaker intent "
        "acoustic perception"
    ),
    "orchestrator_agent": (
        "coordinate route dispatch multi-agent orchestration system control "
        "general assistance fallback"
    ),
}

_STOPWORDS = frozenset(
    "a an the and or but in on at to for of with by is are was were be been being "
    "this that it as from into about than then so if when what which who how".split()
)


def _tokenize(text: str) -> List[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _tf(tokens: List[str]) -> Dict[str, float]:
    counts = Counter(tokens)
    total = float(len(tokens)) or 1.0
    return {term: count / total for term, count in counts.items()}


def _idf(corpus: List[List[str]]) -> Dict[str, float]:
    n = len(corpus) or 1
    df: Counter = Counter()
    for doc in corpus:
        for term in set(doc):
            df[term] += 1
    return {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}


def _tfidf_vector(tokens: List[str], idf: Dict[str, float]) -> Dict[str, float]:
    tf = _tf(tokens)
    return {term: tf_val * idf.get(term, 1.0) for term, tf_val in tf.items()}


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in set(a) | set(b))
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class IntentRouteResult:
    selected_agent: str
    confidence: float
    reasoning: str
    alternative_agents: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    uncertainty: float = 0.0

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "selectedAgent": self.selected_agent,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "alternativeAgents": self.alternative_agents,
            "uncertainty": round(self.uncertainty, 4),
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
        }


class SemanticIntentRouter:
    """Configuration-driven semantic router with optional embedding backend."""

    def __init__(
        self,
        profiles: Optional[Dict[str, str]] = None,
        fallback_agent: str = "orchestrator_agent",
        min_confidence: float = 0.12,
    ) -> None:
        self.profiles = profiles or dict(AGENT_CAPABILITY_PROFILES)
        self.fallback_agent = fallback_agent
        self.min_confidence = min_confidence
        self._embedding_model = None
        self._embedding_available = False
        self._init_embeddings()
        self._build_tfidf_index()

    def _init_embeddings(self) -> None:
        import os
        if os.getenv("DISABLE_EMBEDDINGS", "").lower() in ("1", "true", "yes"):
            self._embedding_model = None
            self._embedding_available = False
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            self._embedding_available = True
        except Exception:
            self._embedding_model = None
            self._embedding_available = False

    def _build_tfidf_index(self) -> None:
        corpus_tokens = [_tokenize(text) for text in self.profiles.values()]
        self._idf = _idf(corpus_tokens)
        self._profile_vectors: Dict[str, Dict[str, float]] = {}
        for agent, text in self.profiles.items():
            self._profile_vectors[agent] = _tfidf_vector(_tokenize(text), self._idf)

    def _embedding_scores(self, content: str) -> Dict[str, float]:
        if not self._embedding_available or self._embedding_model is None:
            return {}
        try:
            import numpy as np

            query_vec = self._embedding_model.encode(content, normalize_embeddings=True)
            scores: Dict[str, float] = {}
            for agent, profile_text in self.profiles.items():
                profile_vec = self._embedding_model.encode(profile_text, normalize_embeddings=True)
                scores[agent] = float(np.dot(query_vec, profile_vec))
            return scores
        except Exception as exc:
            logger.debug("embedding_route_failed: %s", exc)
            return {}

    def route(
        self,
        content: str,
        agent_hint: Optional[str] = None,
        performance_weights: Optional[Dict[str, float]] = None,
    ) -> IntentRouteResult:
        text = (content or "").strip()
        if not text:
            return IntentRouteResult(
                selected_agent=self.fallback_agent,
                confidence=0.5,
                reasoning="Empty input — routing to orchestrator",
                uncertainty=1.0,
            )

        if agent_hint and agent_hint in self.profiles:
            return IntentRouteResult(
                selected_agent=agent_hint,
                confidence=0.98,
                reasoning=f"Explicit agent hint: {agent_hint}",
                uncertainty=0.02,
            )

        query_vec = _tfidf_vector(_tokenize(text), self._idf)
        tfidf_scores = {
            agent: _cosine(query_vec, profile_vec)
            for agent, profile_vec in self._profile_vectors.items()
        }

        embed_scores = self._embedding_scores(text)
        combined: Dict[str, float] = {}
        for agent in self.profiles:
            tfidf = tfidf_scores.get(agent, 0.0)
            embed = embed_scores.get(agent, tfidf)
            combined[agent] = 0.45 * tfidf + 0.55 * embed if embed_scores else tfidf

        if performance_weights:
            for agent, weight in performance_weights.items():
                if agent in combined:
                    combined[agent] *= max(0.1, float(weight))

        ranked: List[Tuple[str, float]] = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        best_agent, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0

        if best_score < self.min_confidence:
            return IntentRouteResult(
                selected_agent=self.fallback_agent,
                confidence=round(0.45 + best_score, 4),
                reasoning="Low semantic match — orchestrator fallback",
                alternative_agents=[a for a, _ in ranked[:3]],
                scores=combined,
                uncertainty=round(1.0 - best_score, 4),
            )

        margin = max(0.0, best_score - second_score)
        confidence = min(0.98, 0.35 + best_score * 0.55 + margin * 0.25)
        uncertainty = max(0.0, 1.0 - confidence)

        return IntentRouteResult(
            selected_agent=best_agent,
            confidence=round(confidence, 4),
            reasoning=(
                f"Semantic intent match (score={best_score:.3f}, margin={margin:.3f}) "
                f"→ {best_agent}"
            ),
            alternative_agents=[a for a, s in ranked[1:4] if s > self.min_confidence * 0.5],
            scores=combined,
            uncertainty=round(uncertainty, 4),
        )


_default_router: Optional[SemanticIntentRouter] = None


def get_intent_router() -> SemanticIntentRouter:
    global _default_router
    if _default_router is None:
        _default_router = SemanticIntentRouter()
    return _default_router
