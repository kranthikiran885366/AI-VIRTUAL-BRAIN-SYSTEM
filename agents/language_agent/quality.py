"""
Quality Engine — Phase 9
Grammar, clarity, coherence, fluency, readability scoring.
All thresholds are config-driven.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .models import LanguageQuality


class QualityEngine:
    """
    Evaluates text quality across multiple dimensions.
    Returns structured LanguageQuality reports.
    """

    _FILLER_WORDS = [
        "very", "really", "quite", "just", "basically", "literally",
        "actually", "honestly", "totally", "absolutely", "definitely",
    ]
    _PASSIVE_PATTERN = re.compile(
        r"\b(is|are|was|were|been|being)\s+\w+ed\b", re.IGNORECASE
    )
    _CONTRACTION_PATTERN = re.compile(
        r"\b(can't|won't|don't|isn't|aren't|wasn't|weren't|"
        r"I'm|I've|I'll|it's|they're|we're|you're|he's|she's)\b",
        re.IGNORECASE,
    )

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = (config or {}).get("quality", {})
        self._good = float(cfg.get("good_threshold", 0.75))
        self._acceptable = float(cfg.get("acceptable_threshold", 0.50))
        self._max_passive = int(cfg.get("max_passive_voice", 2))
        self._max_filler = int(cfg.get("max_filler_words", 3))
        self._max_sent_len = float(cfg.get("max_avg_sentence_length", 30))
        self._min_sent_len = float(cfg.get("min_avg_sentence_length", 8))
        self._readability_target = float(cfg.get("readability_target", 0.70))

    def evaluate(self, text: str) -> LanguageQuality:
        """Full quality evaluation of text."""
        words = text.split()
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        word_count = len(words)
        sentence_count = max(1, len(sentences))
        avg_word_len = sum(len(w) for w in words) / max(1, word_count)
        avg_sent_len = word_count / sentence_count

        passive_count = len(self._PASSIVE_PATTERN.findall(text))
        filler_count = sum(text.lower().count(w) for w in self._FILLER_WORDS)
        contraction_count = len(self._CONTRACTION_PATTERN.findall(text))

        # Complexity
        if avg_sent_len > 25 or avg_word_len > 6:
            complexity, reading_level = "complex", "advanced"
        elif avg_sent_len > 15 or avg_word_len > 5:
            complexity, reading_level = "moderate", "intermediate"
        else:
            complexity, reading_level = "simple", "basic"

        # Dimension scores
        grammar_score = max(0.0, 1.0 - passive_count * 0.08 - contraction_count * 0.03)
        clarity_score = max(0.0, 1.0 - filler_count * 0.06 - passive_count * 0.05)
        fluency_score = self._fluency(avg_sent_len)
        readability_score = self._readability(avg_sent_len, avg_word_len)
        coherence_score = self._coherence(sentences)

        overall = round(
            grammar_score * 0.25
            + clarity_score * 0.25
            + fluency_score * 0.20
            + readability_score * 0.15
            + coherence_score * 0.15,
            4,
        )

        suggestions = self._suggestions(passive_count, filler_count, avg_sent_len)
        label = (
            "good" if overall >= self._good
            else "acceptable" if overall >= self._acceptable
            else "poor"
        )

        return LanguageQuality(
            overall_score=overall,
            grammar_score=round(grammar_score, 4),
            clarity_score=round(clarity_score, 4),
            coherence_score=round(coherence_score, 4),
            fluency_score=round(fluency_score, 4),
            readability_score=round(readability_score, 4),
            complexity=complexity,
            reading_level=reading_level,
            word_count=word_count,
            sentence_count=sentence_count,
            avg_sentence_length=round(avg_sent_len, 1),
            avg_word_length=round(avg_word_len, 1),
            passive_voice_count=passive_count,
            filler_word_count=filler_count,
            suggestions=suggestions,
            label=label,
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fluency(self, avg_sent_len: float) -> float:
        if self._min_sent_len <= avg_sent_len <= self._max_sent_len:
            return 1.0
        if avg_sent_len < self._min_sent_len:
            return max(0.3, avg_sent_len / self._min_sent_len)
        return max(0.3, self._max_sent_len / avg_sent_len)

    def _readability(self, avg_sent_len: float, avg_word_len: float) -> float:
        # Simplified Flesch-like score (normalized 0–1)
        raw = 206.835 - 1.015 * avg_sent_len - 84.6 * (avg_word_len / 5.0)
        return round(max(0.0, min(1.0, raw / 100.0)), 4)

    def _coherence(self, sentences: List[str]) -> float:
        if len(sentences) <= 1:
            return 1.0
        # Proxy: ratio of sentences with transition words
        transitions = [
            "however", "therefore", "furthermore", "moreover", "additionally",
            "consequently", "thus", "hence", "meanwhile", "nevertheless",
            "although", "because", "since", "while", "whereas",
        ]
        count = sum(
            1 for s in sentences
            if any(t in s.lower() for t in transitions)
        )
        base = 0.60
        bonus = min(0.40, count / max(1, len(sentences)) * 0.80)
        return round(base + bonus, 4)

    def _suggestions(
        self, passive: int, filler: int, avg_sent_len: float
    ) -> List[str]:
        out = []
        if passive > self._max_passive:
            out.append(
                f"Found {passive} passive voice constructions. "
                "Convert to active voice for stronger writing."
            )
        if filler > self._max_filler:
            out.append(
                f"Found {filler} filler words. "
                "Remove them for more direct writing."
            )
        if avg_sent_len > self._max_sent_len:
            out.append(
                "Sentences are long. Break complex sentences for better readability."
            )
        if avg_sent_len < self._min_sent_len:
            out.append(
                "Sentences are very short. Combine some for better flow."
            )
        if not out:
            out.append("Writing quality looks good. No major issues detected.")
        return out
