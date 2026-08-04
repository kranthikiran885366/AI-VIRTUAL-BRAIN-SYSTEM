"""
Language Understanding — Phase 9
Intent refinement, entity extraction, keyword extraction,
language detection, ambiguity detection. Provider-independent.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple


class LanguageUnderstanding:
    """
    Modular NLU pipeline. All thresholds are config-driven.
    Provider-independent — no external NLP library required.
    """

    # Language detection patterns (ISO 639-1)
    _LANG_PATTERNS: Dict[str, List[str]] = {
        "es": ["el ", "la ", "los ", "las ", "que ", "de ", "en ", "es ", "con ", "por "],
        "fr": ["le ", "la ", "les ", "de ", "du ", "des ", "et ", "en ", "je ", "vous "],
        "de": ["der ", "die ", "das ", "und ", "ist ", "ich ", "sie ", "ein ", "mit ", "auf "],
        "hi": ["है", "का", "की", "के", "में", "और", "को", "से", "पर", "यह"],
        "ar": ["في", "من", "على", "إلى", "هذا", "هذه", "كان", "مع", "عن", "أن"],
        "zh": ["的", "了", "在", "是", "我", "有", "和", "就", "不", "人"],
        "pt": ["de ", "que ", "em ", "do ", "da ", "os ", "as ", "um ", "uma ", "para "],
        "ru": ["и ", "в ", "не ", "на ", "я ", "что ", "он ", "с ", "как ", "это "],
        "ja": ["の", "に", "は", "を", "た", "が", "で", "て", "と", "し"],
    }

    # Intent keyword map
    _INTENT_PATTERNS: Dict[str, List[str]] = {
        "summarize":  ["summarize", "summary", "tldr", "brief", "shorten", "condense", "overview"],
        "translate":  ["translate", "in spanish", "in french", "in german", "in hindi", "in arabic",
                       "in chinese", "in portuguese", "in russian", "in japanese"],
        "improve":    ["improve", "rewrite", "rephrase", "better", "enhance", "polish", "refine"],
        "proofread":  ["grammar", "spelling", "correct", "fix", "proofread", "check", "errors"],
        "formalize":  ["formal", "professional", "business", "official", "academic"],
        "simplify":   ["casual", "informal", "friendly", "conversational", "simple", "simplify"],
        "expand":     ["expand", "elaborate", "more detail", "longer", "extend", "explain more"],
        "tone_adjust":["tone", "style", "voice", "adapt", "adjust tone"],
        "document":   ["document", "parse", "extract sections", "key points", "structure"],
        "quality":    ["quality", "score", "evaluate", "assess", "rate"],
    }

    # Filler words for detection
    _FILLER_WORDS = [
        "very", "really", "quite", "just", "basically", "literally",
        "actually", "honestly", "totally", "absolutely", "definitely",
    ]

    # Named entity patterns (lightweight regex-based)
    _ENTITY_PATTERNS: List[Tuple[str, str]] = [
        (r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", "PERSON"),
        (r"\b[A-Z]{2,}\b", "ACRONYM"),
        (r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "DATE"),
        (r"\b\d{4}-\d{2}-\d{2}\b", "DATE"),
        (r"\b\$[\d,]+(?:\.\d{2})?\b", "MONEY"),
        (r"\b\d+(?:\.\d+)?%\b", "PERCENT"),
        (r"\bhttps?://\S+\b", "URL"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "EMAIL"),
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = (config or {}).get("understanding", {})
        self._min_confidence = float(cfg.get("min_confidence", 0.30))
        self._high_confidence = float(cfg.get("high_confidence", 0.75))
        self._intent_threshold = float(cfg.get("intent_confidence_threshold", 0.50))
        self._ambiguity_threshold = float(cfg.get("ambiguity_threshold", 0.45))
        self._detect_min_patterns = int(
            (config or {}).get("translation", {}).get("detect_min_patterns", 3)
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def detect_language(self, text: str) -> Dict[str, Any]:
        """Detect language from text. Returns ISO 639-1 code + confidence."""
        normalized = unicodedata.normalize("NFC", text.lower())
        scores: Dict[str, int] = {}
        for lang, patterns in self._LANG_PATTERNS.items():
            scores[lang] = sum(1 for p in patterns if p in normalized)

        best_lang = max(scores, key=lambda k: scores[k]) if scores else "en"
        best_score = scores.get(best_lang, 0)

        if best_score < self._detect_min_patterns:
            best_lang = "en"
            confidence = 0.60
        else:
            confidence = min(0.95, 0.50 + best_score * 0.05)

        return {
            "language": best_lang,
            "confidence": round(confidence, 3),
            "scores": {k: v for k, v in scores.items() if v > 0},
        }

    def detect_intent(self, text: str, action: str = "") -> Dict[str, Any]:
        """Detect primary intent from text + action hint."""
        combined = (text + " " + action).lower()
        matched: Dict[str, int] = {}
        for intent, patterns in self._INTENT_PATTERNS.items():
            count = sum(1 for p in patterns if p in combined)
            if count:
                matched[intent] = count

        if not matched:
            return {"intent": "analyze", "confidence": self._min_confidence,
                    "alternatives": [], "ambiguous": False}

        sorted_intents = sorted(matched.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_intents[0][0]
        primary_count = sorted_intents[0][1]
        confidence = min(0.95, self._intent_threshold + primary_count * 0.10)

        alternatives = [i for i, _ in sorted_intents[1:3]]
        ambiguous = (
            len(sorted_intents) > 1
            and sorted_intents[1][1] >= primary_count * self._ambiguity_threshold
        )

        return {
            "intent": primary,
            "confidence": round(confidence, 3),
            "alternatives": alternatives,
            "ambiguous": ambiguous,
        }

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract named entities using lightweight regex patterns."""
        entities = []
        seen: set = set()
        for pattern, etype in self._ENTITY_PATTERNS:
            for match in re.finditer(pattern, text):
                value = match.group()
                key = (value, etype)
                if key not in seen:
                    seen.add(key)
                    entities.append({
                        "text": value,
                        "type": etype,
                        "start": match.start(),
                        "end": match.end(),
                    })
        return entities

    def extract_keywords(self, text: str, max_keywords: int = 15) -> List[str]:
        """Extract keywords by frequency, excluding stopwords."""
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "shall",
            "this", "that", "these", "those", "it", "its", "i", "you", "he",
            "she", "we", "they", "what", "which", "who", "how", "when",
            "where", "why", "not", "no", "so", "if", "as", "up", "out",
        }
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        freq: Dict[str, int] = {}
        for w in words:
            if w not in stopwords:
                freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:max_keywords]]

    def segment_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        raw = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s.strip() for s in raw if s.strip()]

    def tokenize(self, text: str) -> List[str]:
        """Simple whitespace + punctuation tokenizer."""
        return re.findall(r"\b\w+\b", text)

    def estimate_tokens(self, text: str) -> int:
        """Rough token count estimate (words / 0.75)."""
        return max(1, int(len(text.split()) / 0.75))

    def detect_ambiguity(self, text: str) -> Dict[str, Any]:
        """Detect linguistic ambiguity indicators."""
        lower = text.lower()
        ambiguity_markers = [
            "maybe", "perhaps", "possibly", "might", "could be",
            "not sure", "unclear", "ambiguous", "either", "or maybe",
            "i think", "i believe", "seems like", "appears to",
        ]
        found = [m for m in ambiguity_markers if m in lower]
        score = min(1.0, len(found) * 0.15)
        return {
            "is_ambiguous": score >= self._ambiguity_threshold,
            "ambiguity_score": round(score, 3),
            "markers_found": found,
        }

    def normalize_unicode(self, text: str) -> str:
        """Normalize Unicode to NFC form."""
        return unicodedata.normalize("NFC", text)

    def validate_input(self, text: str, max_length: int = 50000) -> Dict[str, Any]:
        """Validate text input before processing."""
        errors = []
        if not isinstance(text, str):
            errors.append("text must be a string")
        elif len(text) == 0:
            errors.append("text must not be empty")
        elif len(text) > max_length:
            errors.append(f"text exceeds max length {max_length}")
        return {"valid": len(errors) == 0, "errors": errors}
