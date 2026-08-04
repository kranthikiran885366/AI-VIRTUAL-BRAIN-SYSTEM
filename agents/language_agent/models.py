"""
Language Intelligence Models — Phase 9
All dataclasses used across the language subsystem.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class LanguageSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ended_at: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    operations: int = 0
    tokens_processed: int = 0
    detected_language: str = "en"
    quality_scores: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def avg_quality(self) -> float:
        if not self.quality_scores:
            return 0.0
        return round(sum(self.quality_scores) / len(self.quality_scores), 4)


@dataclass
class LanguageQuality:
    overall_score: float = 0.0
    grammar_score: float = 0.0
    clarity_score: float = 0.0
    coherence_score: float = 0.0
    fluency_score: float = 0.0
    readability_score: float = 0.0
    complexity: str = "moderate"
    reading_level: str = "intermediate"
    word_count: int = 0
    sentence_count: int = 0
    avg_sentence_length: float = 0.0
    avg_word_length: float = 0.0
    passive_voice_count: int = 0
    filler_word_count: int = 0
    suggestions: List[str] = field(default_factory=list)
    label: str = "acceptable"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticResult:
    topics: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    confidence: float = 0.0
    language: str = "en"
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LanguageMetrics:
    total_operations: int = 0
    total_tokens: int = 0
    total_sessions: int = 0
    analyze_count: int = 0
    summarize_count: int = 0
    improve_count: int = 0
    translate_count: int = 0
    proofread_count: int = 0
    document_count: int = 0
    quality_alerts: int = 0
    total_processing_ms: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def avg_processing_ms(self) -> float:
        return round(self.total_processing_ms / max(1, self.total_operations), 2)
