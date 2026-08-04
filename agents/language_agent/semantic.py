"""
Semantic Analyzer — Phase 9
Topic detection, keyword extraction, concept extraction,
sentiment analysis. Provider-independent, embedding-ready.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional

from .models import SemanticResult


class SemanticAnalyzer:
    """
    Lightweight semantic analysis pipeline.
    Designed for provider-independent operation with future
    embedding-provider integration points.
    """

    _SENTIMENT_POS = [
        "good", "great", "excellent", "amazing", "wonderful", "fantastic",
        "happy", "love", "best", "perfect", "brilliant", "outstanding",
        "positive", "success", "helpful", "effective", "clear", "easy",
    ]
    _SENTIMENT_NEG = [
        "bad", "terrible", "awful", "horrible", "poor", "worst", "hate",
        "fail", "failure", "difficult", "hard", "confusing", "broken",
        "error", "problem", "issue", "wrong", "negative", "slow", "ugly",
    ]
    _STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "are", "was", "were",
        "be", "been", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "this", "that", "it", "its", "i",
        "you", "he", "she", "we", "they", "not", "no", "so", "if", "as",
        "up", "out", "what", "which", "who", "how", "when", "where", "why",
    }

    # Lightweight topic taxonomy
    _TOPIC_SEEDS: Dict[str, List[str]] = {
        "technology": ["software", "code", "program", "computer", "data", "system",
                       "api", "algorithm", "database", "network", "cloud", "ai"],
        "science":    ["research", "study", "experiment", "hypothesis", "theory",
                       "analysis", "result", "evidence", "scientific", "biology"],
        "business":   ["company", "market", "revenue", "profit", "strategy",
                       "customer", "product", "service", "management", "growth"],
        "health":     ["medical", "health", "disease", "treatment", "patient",
                       "doctor", "hospital", "medicine", "symptom", "therapy"],
        "education":  ["learn", "teach", "school", "student", "course", "knowledge",
                       "training", "skill", "education", "university"],
        "finance":    ["money", "investment", "bank", "financial", "budget",
                       "cost", "price", "economic", "fund", "capital"],
        "legal":      ["law", "legal", "court", "contract", "regulation",
                       "compliance", "policy", "rights", "agreement", "clause"],
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = (config or {}).get("semantic", {})
        self._topic_min = float(cfg.get("topic_min_score", 0.40))
        self._max_topics = int(cfg.get("max_topics", 10))
        self._max_concepts = int(cfg.get("max_concepts", 20))
        self._max_keywords = int(cfg.get("max_keywords", 15))
        self._concept_min_freq = int(cfg.get("concept_min_frequency", 2))

    def analyze(self, text: str, language: str = "en") -> SemanticResult:
        """Full semantic analysis of text."""
        keywords = self._extract_keywords(text)
        topics = self._detect_topics(text)
        concepts = self._extract_concepts(text)
        sentiment, sentiment_score = self._analyze_sentiment(text)
        confidence = self._estimate_confidence(text, keywords, topics)

        return SemanticResult(
            topics=topics,
            keywords=keywords,
            concepts=concepts,
            sentiment=sentiment,
            sentiment_score=round(sentiment_score, 3),
            confidence=round(confidence, 3),
            language=language,
            summary="",
        )

    def similarity(self, text_a: str, text_b: str) -> float:
        """Jaccard similarity between two texts (keyword overlap)."""
        kw_a = set(self._extract_keywords(text_a))
        kw_b = set(self._extract_keywords(text_b))
        if not kw_a and not kw_b:
            return 0.0
        intersection = kw_a & kw_b
        union = kw_a | kw_b
        return round(len(intersection) / len(union), 4)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        freq = Counter(w for w in words if w not in self._STOPWORDS)
        return [w for w, _ in freq.most_common(self._max_keywords)]

    def _detect_topics(self, text: str) -> List[str]:
        lower = text.lower()
        scores: Dict[str, float] = {}
        for topic, seeds in self._TOPIC_SEEDS.items():
            hits = sum(1 for s in seeds if s in lower)
            if hits:
                scores[topic] = min(1.0, hits / len(seeds))
        filtered = {t: s for t, s in scores.items() if s >= self._topic_min}
        sorted_topics = sorted(filtered, key=lambda t: filtered[t], reverse=True)
        return sorted_topics[: self._max_topics]

    def _extract_concepts(self, text: str) -> List[str]:
        """Extract multi-word noun phrases as concepts."""
        # Simple bigram/trigram extraction from capitalized or frequent phrases
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text)
        bigrams = [
            f"{words[i].lower()} {words[i+1].lower()}"
            for i in range(len(words) - 1)
            if words[i].lower() not in self._STOPWORDS
            and words[i+1].lower() not in self._STOPWORDS
        ]
        freq = Counter(bigrams)
        concepts = [
            bg for bg, count in freq.most_common(self._max_concepts)
            if count >= self._concept_min_freq
        ]
        return concepts

    def _analyze_sentiment(self, text: str) -> tuple:
        lower = text.lower()
        pos = sum(1 for w in self._SENTIMENT_POS if w in lower)
        neg = sum(1 for w in self._SENTIMENT_NEG if w in lower)
        total = pos + neg
        if total == 0:
            return "neutral", 0.0
        score = (pos - neg) / total
        if score > 0.1:
            return "positive", score
        if score < -0.1:
            return "negative", score
        return "neutral", score

    def _estimate_confidence(
        self, text: str, keywords: List[str], topics: List[str]
    ) -> float:
        base = 0.40
        if len(keywords) >= 5:
            base += 0.15
        if topics:
            base += 0.15
        if len(text.split()) >= 20:
            base += 0.10
        return min(0.95, base)
