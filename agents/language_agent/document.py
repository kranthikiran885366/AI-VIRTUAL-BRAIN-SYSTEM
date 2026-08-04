"""
Document Processor — Phase 9
Parsing, section detection, key-point extraction,
metadata extraction, quality scoring. Provider-independent.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class DocumentProcessor:
    """
    Processes plain-text documents into structured representations.
    Future-ready for PDF/DOCX/HTML/Markdown via provider plugins.
    """

    _SECTION_MARKERS = re.compile(
        r"^(#{1,6}\s+.+|[A-Z][A-Z\s]{3,}:|(?:\d+\.)+\s+.+)$",
        re.MULTILINE,
    )

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = (config or {}).get("document", {})
        self._max_length = int(cfg.get("max_document_length", 200000))
        self._max_sections = int(cfg.get("max_sections", 50))
        self._min_section_len = int(cfg.get("min_section_length", 100))
        self._title_max = int(cfg.get("title_max_length", 200))

    def process(self, text: str, doc_type: str = "plain") -> Dict[str, Any]:
        """Full document processing pipeline."""
        validation = self.validate(text)
        if not validation["valid"]:
            return {"error": validation["errors"], "valid": False}

        title = self._extract_title(text)
        sections = self._detect_sections(text)
        key_points = self._extract_key_points(text)
        metadata = self._extract_metadata(text)
        quality = self._score_quality(text, sections)

        return {
            "title": title,
            "sections": sections,
            "section_count": len(sections),
            "key_points": key_points,
            "metadata": metadata,
            "quality_score": quality,
            "word_count": len(text.split()),
            "char_count": len(text),
            "doc_type": doc_type,
            "valid": True,
        }

    def validate(self, text: str) -> Dict[str, Any]:
        errors = []
        if not isinstance(text, str):
            errors.append("document must be a string")
        elif len(text) == 0:
            errors.append("document must not be empty")
        elif len(text) > self._max_length:
            errors.append(f"document exceeds max length {self._max_length}")
        return {"valid": len(errors) == 0, "errors": errors}

    def extract_summary(self, text: str, max_sentences: int = 5) -> str:
        """Extract a summary from the document."""
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 20]
        if not sentences:
            return text[:500]

        scored = []
        important = ["important", "key", "main", "primary", "critical",
                     "essential", "significant", "therefore", "conclusion", "result"]
        for i, s in enumerate(sentences):
            score = 0
            if i == 0: score += 3
            if i == len(sentences) - 1: score += 2
            score += sum(2 for w in important if w in s.lower())
            score += len(s.split()) * 0.05
            scored.append((score, i, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = sorted(scored[:max_sentences], key=lambda x: x[1])
        return ". ".join(s for _, _, s in top) + "."

    # ── Internal ──────────────────────────────────────────────────────────────

    def _extract_title(self, text: str) -> str:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return ""
        # First non-empty line, capped at title_max
        candidate = lines[0]
        if candidate.startswith("#"):
            candidate = candidate.lstrip("#").strip()
        return candidate[: self._title_max]

    def _detect_sections(self, text: str) -> List[Dict[str, Any]]:
        sections = []
        matches = list(self._SECTION_MARKERS.finditer(text))

        for i, match in enumerate(matches[: self._max_sections]):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            if len(content) >= self._min_section_len:
                sections.append({
                    "title": match.group().strip(),
                    "content_length": len(content),
                    "word_count": len(content.split()),
                    "start_char": match.start(),
                })

        return sections

    def _extract_key_points(self, text: str, max_points: int = 8) -> List[str]:
        """Extract bullet points and numbered list items."""
        bullet_pattern = re.compile(
            r"^[\s]*[-*•]\s+(.+)$|^[\s]*\d+[.)]\s+(.+)$", re.MULTILINE
        )
        points = []
        for m in bullet_pattern.finditer(text):
            point = (m.group(1) or m.group(2) or "").strip()
            if point and len(point) > 10:
                points.append(point)
            if len(points) >= max_points:
                break

        # Fallback: first sentences if no bullets found
        if not points:
            sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 30]
            points = sentences[:max_points]

        return points

    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        # Date patterns
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b", text)
        if date_match:
            metadata["date"] = date_match.group()
        # Author pattern
        author_match = re.search(r"\b(?:by|author|written by)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)", text, re.IGNORECASE)
        if author_match:
            metadata["author"] = author_match.group(1)
        # Version pattern
        version_match = re.search(r"\bv(?:ersion)?\s*(\d+\.\d+(?:\.\d+)?)\b", text, re.IGNORECASE)
        if version_match:
            metadata["version"] = version_match.group(1)
        return metadata

    def _score_quality(self, text: str, sections: List[Dict]) -> float:
        score = 0.50
        words = text.split()
        if len(words) >= 100:
            score += 0.10
        if sections:
            score += min(0.20, len(sections) * 0.04)
        if len(words) > 50:
            score += 0.10
        # Penalize very short documents
        if len(words) < 20:
            score -= 0.20
        return round(max(0.0, min(1.0, score)), 3)
