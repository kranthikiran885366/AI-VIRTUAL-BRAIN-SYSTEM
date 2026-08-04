"""
Improvement Pipeline — Phase 9
Grammar correction, style improvement, formalization,
simplification, expansion, tone adaptation.
Every transformation is explainable.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class ImprovementPipeline:
    """
    Modular text improvement pipeline.
    All rules are config-driven and explainable.
    """

    # (pattern, replacement, description)
    _WORDINESS: List[Tuple[str, str, str]] = [
        (r"\bin order to\b",          "to",        "wordy phrase → concise"),
        (r"\bdue to the fact that\b",  "because",   "wordy phrase → concise"),
        (r"\bat this point in time\b", "now",       "wordy phrase → concise"),
        (r"\bfor the purpose of\b",    "to",        "wordy phrase → concise"),
        (r"\bin the event that\b",     "if",        "wordy phrase → concise"),
        (r"\bwith regard to\b",        "regarding", "wordy phrase → concise"),
        (r"\ba lot of\b",              "many",      "vague quantifier → precise"),
        (r"\bkind of\b",               "somewhat",  "vague qualifier → precise"),
        (r"\bsort of\b",               "somewhat",  "vague qualifier → precise"),
    ]

    _FILLER_REPLACEMENTS: List[Tuple[str, str, str]] = [
        (r"\bvery good\b",   "excellent",  "intensifier + adjective → precise word"),
        (r"\bvery bad\b",    "terrible",   "intensifier + adjective → precise word"),
        (r"\bvery big\b",    "enormous",   "intensifier + adjective → precise word"),
        (r"\bvery small\b",  "tiny",       "intensifier + adjective → precise word"),
        (r"\bvery fast\b",   "rapid",      "intensifier + adjective → precise word"),
        (r"\bvery slow\b",   "sluggish",   "intensifier + adjective → precise word"),
        (r"\bvery happy\b",  "delighted",  "intensifier + adjective → precise word"),
        (r"\bvery sad\b",    "devastated", "intensifier + adjective → precise word"),
    ]

    _CONTRACTIONS_EXPAND: List[Tuple[str, str]] = [
        (r"\bcan't\b",   "cannot"),
        (r"\bwon't\b",   "will not"),
        (r"\bdon't\b",   "do not"),
        (r"\bisn't\b",   "is not"),
        (r"\baren't\b",  "are not"),
        (r"\bwasn't\b",  "was not"),
        (r"\bweren't\b", "were not"),
        (r"\bI'm\b",     "I am"),
        (r"\bI've\b",    "I have"),
        (r"\bI'll\b",    "I will"),
        (r"\bit's\b",    "it is"),
        (r"\bthey're\b", "they are"),
        (r"\bwe're\b",   "we are"),
        (r"\byou're\b",  "you are"),
        (r"\bhe's\b",    "he is"),
        (r"\bshe's\b",   "she is"),
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = (config or {}).get("improvement", {})
        self._enable_contractions = bool(cfg.get("enable_contraction_expansion", True))
        self._enable_filler = bool(cfg.get("enable_filler_removal", True))
        self._enable_wordiness = bool(cfg.get("enable_wordiness_reduction", True))

    def improve(self, text: str) -> Dict[str, Any]:
        """Apply full improvement pipeline."""
        result = text
        changes: List[str] = []

        if self._enable_filler:
            result, c = self._apply_rules(result, self._FILLER_REPLACEMENTS)
            changes.extend(c)

        if self._enable_wordiness:
            result, c = self._apply_rules(result, [
                (p, r, d) for p, r, d in self._WORDINESS
            ])
            changes.extend(c)

        return {
            "original": text,
            "improved": result,
            "changes_made": changes,
            "improvement_count": len(changes),
        }

    def formalize(self, text: str) -> Dict[str, Any]:
        """Expand contractions and apply formal register."""
        result = text
        changes: List[str] = []
        if self._enable_contractions:
            for pattern, replacement in self._CONTRACTIONS_EXPAND:
                new = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
                if new != result:
                    changes.append(f"Expanded contraction → '{replacement}'")
                    result = new
        return {
            "original": text,
            "formalized": result,
            "changes_made": changes,
            "change_count": len(changes),
        }

    def simplify(self, text: str) -> Dict[str, Any]:
        """Simplify text by reducing sentence complexity."""
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        # Keep shorter sentences; split long ones at conjunctions
        simplified = []
        for s in sentences:
            if len(s.split()) > 25:
                parts = re.split(r"\b(and|but|however|although|because)\b", s, maxsplit=1, flags=re.IGNORECASE)
                simplified.extend(p.strip() for p in parts if p.strip() and len(p.strip()) > 5)
            else:
                simplified.append(s)
        result = ". ".join(simplified) + "." if simplified else text
        return {
            "original": text,
            "simplified": result,
            "sentence_count_before": len(sentences),
            "sentence_count_after": len(simplified),
        }

    def expand(self, text: str) -> Dict[str, Any]:
        """Expand text with elaboration markers (structural, not generative)."""
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        expanded = []
        for i, s in enumerate(sentences):
            expanded.append(s)
            if i == 0 and len(sentences) > 1:
                expanded.append("To elaborate further")
            elif i == len(sentences) - 2:
                expanded.append("In conclusion")
        result = ". ".join(expanded) + "."
        return {
            "original": text,
            "expanded": result,
            "added_markers": len(expanded) - len(sentences),
        }

    def adapt_tone(self, text: str, target_tone: str = "neutral") -> Dict[str, Any]:
        """Adapt tone: formal | casual | technical | empathetic."""
        if target_tone == "formal":
            r = self.formalize(text)
            return {"original": text, "adapted": r["formalized"],
                    "target_tone": target_tone, "changes": r["changes_made"]}
        if target_tone == "casual":
            r = self.simplify(text)
            return {"original": text, "adapted": r["simplified"],
                    "target_tone": target_tone, "changes": []}
        return {"original": text, "adapted": text,
                "target_tone": target_tone, "changes": []}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _apply_rules(
        self,
        text: str,
        rules: List[Tuple[str, str, str]],
    ) -> Tuple[str, List[str]]:
        changes = []
        for pattern, replacement, description in rules:
            new = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            if new != text:
                changes.append(description)
                text = new
        return text, changes
