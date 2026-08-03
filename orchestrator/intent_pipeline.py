"""
Intent Analysis Pipeline — Phase 4.1

Pluggable classifier architecture.
The pipeline depends only on the IntentDetector interface.

Hierarchy:
    IntentDetector (ABC)
        ├── RuleIntentDetector      — compiled regex, zero deps, always available
        ├── EmbeddingIntentDetector — sentence-transformers cosine similarity
        ├── MLIntentDetector        — stub for future sklearn/torch classifiers
        └── HybridIntentDetector   — weighted ensemble of any detectors
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from .decision_context import DetectedIntent, IntentType
from .confidence_engine import ConfidenceEngine

logger = logging.getLogger(__name__)

# ─── Intent signal patterns (Rule detector only) ──────────────────────────────

_INTENT_SIGNALS: Dict[IntentType, List[str]] = {
    IntentType.COMMAND: [
        r"\b(do|run|execute|start|stop|create|delete|update|set|enable|disable|launch|open|close)\b",
    ],
    IntentType.QUESTION: [
        r"\b(what|who|where|when|why|how|which|is|are|was|were|can|could|would|should|does|did)\b",
        r"\?$",
    ],
    IntentType.TASK: [
        r"\b(task|todo|remind|schedule|deadline|organize|checklist|assign|track|complete)\b",
    ],
    IntentType.PLANNING_REQUEST: [
        r"\b(plan|goal|strategy|roadmap|milestone|timeline|objective|target|step)\b",
    ],
    IntentType.ANALYSIS_REQUEST: [
        r"\b(analyze|analyse|compare|evaluate|assess|review|examine|investigate|study|measure)\b",
    ],
    IntentType.CREATIVE_REQUEST: [
        r"\b(create|design|write|generate|imagine|invent|brainstorm|compose|draft|story|poem)\b",
    ],
    IntentType.INFORMATION_REQUEST: [
        r"\b(tell|explain|describe|define|show|list|summarize|what is|what are|how does)\b",
    ],
    IntentType.WORKFLOW: [
        r"\b(workflow|process|pipeline|sequence|chain|automate|batch|series of|step by step)\b",
    ],
    IntentType.CONVERSATION: [
        r"\b(hello|hi|hey|thanks|thank you|bye|goodbye|how are you|nice to meet|good morning|good evening)\b",
    ],
}

_COMPILED: Dict[IntentType, List[re.Pattern]] = {
    t: [re.compile(p, re.IGNORECASE) for p in patterns]
    for t, patterns in _INTENT_SIGNALS.items()
}

# Natural-language profiles for embedding-based detection (mirrors semantic_intent.py style)
_INTENT_PROFILES: Dict[IntentType, str] = {
    IntentType.COMMAND: "execute run start stop create delete update enable disable launch",
    IntentType.QUESTION: "what who where when why how which is are can could would should",
    IntentType.TASK: "task todo remind schedule deadline organize checklist assign track complete",
    IntentType.PLANNING_REQUEST: "plan goal strategy roadmap milestone timeline objective target step",
    IntentType.ANALYSIS_REQUEST: "analyze compare evaluate assess review examine investigate study measure",
    IntentType.CREATIVE_REQUEST: "create design write generate imagine invent brainstorm compose draft story",
    IntentType.INFORMATION_REQUEST: "tell explain describe define show list summarize information knowledge",
    IntentType.WORKFLOW: "workflow process pipeline sequence chain automate batch series step by step",
    IntentType.CONVERSATION: "hello hi hey thanks thank you bye goodbye how are you nice to meet",
}


# ─── Interface ────────────────────────────────────────────────────────────────

class IntentDetector(ABC):
    """
    Abstract base for all intent classifiers.
    The pipeline depends only on this interface — swap implementations freely.
    """

    @abstractmethod
    def detect(self, text: str) -> Dict[IntentType, float]:
        """
        Return a score dict mapping each IntentType to a raw [0, 1] score.
        Higher = stronger signal for that intent type.
        """

    @property
    def name(self) -> str:
        return self.__class__.__name__


# ─── Rule-based detector ──────────────────────────────────────────────────────

class RuleIntentDetector(IntentDetector):
    """
    Compiled regex pattern matching.
    Zero external dependencies — always available as fallback.
    Extensible: pass custom_signals to override or extend _INTENT_SIGNALS.
    """

    def __init__(self, custom_signals: Optional[Dict[IntentType, List[str]]] = None) -> None:
        signals = dict(_INTENT_SIGNALS)
        if custom_signals:
            for intent_type, patterns in custom_signals.items():
                signals[intent_type] = patterns
        self._compiled: Dict[IntentType, List[re.Pattern]] = {
            t: [re.compile(p, re.IGNORECASE) for p in pats]
            for t, pats in signals.items()
        }

    def detect(self, text: str) -> Dict[IntentType, float]:
        scores: Dict[IntentType, float] = {}
        for intent_type, patterns in self._compiled.items():
            if not patterns:
                scores[intent_type] = 0.0
                continue
            matches = sum(1 for p in patterns if p.search(text))
            scores[intent_type] = round(min(1.0, matches / len(patterns)), 4)
        return scores


# ─── Embedding-based detector ─────────────────────────────────────────────────

class EmbeddingIntentDetector(IntentDetector):
    """
    Sentence-transformer cosine similarity against intent profiles.
    Falls back to zero scores if sentence-transformers is unavailable.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model = None
        self._profile_vecs: Dict[IntentType, Any] = {}
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
            for intent_type, profile in _INTENT_PROFILES.items():
                self._profile_vecs[intent_type] = self._model.encode(
                    profile, normalize_embeddings=True
                )
            logger.info("EmbeddingIntentDetector loaded model=%s", model_name)
        except Exception as exc:
            logger.debug("EmbeddingIntentDetector unavailable: %s", exc)

    def detect(self, text: str) -> Dict[IntentType, float]:
        if self._model is None:
            return {t: 0.0 for t in IntentType if t != IntentType.UNKNOWN}
        try:
            import numpy as np
            query_vec = self._model.encode(text, normalize_embeddings=True)
            return {
                intent_type: round(float(np.dot(query_vec, profile_vec)), 4)
                for intent_type, profile_vec in self._profile_vecs.items()
            }
        except Exception as exc:
            logger.debug("EmbeddingIntentDetector.detect failed: %s", exc)
            return {t: 0.0 for t in IntentType if t != IntentType.UNKNOWN}

    @property
    def available(self) -> bool:
        return self._model is not None


# ─── ML detector stub ─────────────────────────────────────────────────────────

class MLIntentDetector(IntentDetector):
    """
    Stub for future sklearn / torch classifiers.
    Returns zero scores until a model is loaded via load_model().
    """

    def __init__(self) -> None:
        self._model: Optional[Any] = None

    def load_model(self, model: Any) -> None:
        """Inject a trained classifier that exposes predict_proba(texts)."""
        self._model = model

    def detect(self, text: str) -> Dict[IntentType, float]:
        if self._model is None:
            return {t: 0.0 for t in IntentType if t != IntentType.UNKNOWN}
        try:
            proba = self._model.predict_proba([text])[0]
            classes = getattr(self._model, "classes_", [])
            return {
                IntentType(cls): round(float(p), 4)
                for cls, p in zip(classes, proba)
                if cls in IntentType._value2member_map_
            }
        except Exception as exc:
            logger.debug("MLIntentDetector.detect failed: %s", exc)
            return {t: 0.0 for t in IntentType if t != IntentType.UNKNOWN}


# ─── Hybrid ensemble detector ─────────────────────────────────────────────────

class HybridIntentDetector(IntentDetector):
    """
    Weighted ensemble of any IntentDetector implementations.
    Weights are normalised so they always sum to 1.0.
    """

    def __init__(self, detectors: List[Tuple[IntentDetector, float]]) -> None:
        """
        detectors: list of (detector, weight) pairs.
        Weights need not sum to 1 — they are normalised internally.
        """
        if not detectors:
            raise ValueError("HybridIntentDetector requires at least one detector")
        total = sum(w for _, w in detectors)
        self._detectors: List[Tuple[IntentDetector, float]] = [
            (d, w / total) for d, w in detectors
        ]

    def detect(self, text: str) -> Dict[IntentType, float]:
        combined: Dict[IntentType, float] = {}
        for detector, weight in self._detectors:
            scores = detector.detect(text)
            for intent_type, score in scores.items():
                combined[intent_type] = combined.get(intent_type, 0.0) + score * weight
        return {t: round(v, 4) for t, v in combined.items()}

    @property
    def name(self) -> str:
        names = "+".join(d.name for d, _ in self._detectors)
        return f"Hybrid({names})"


# ─── Pipeline ─────────────────────────────────────────────────────────────────

class IntentPipeline:
    """
    Modular intent analysis pipeline.
    Depends only on IntentDetector — swap classifiers without changing the pipeline.

    Default detector: HybridIntentDetector(RuleIntentDetector + EmbeddingIntentDetector)
    when sentence-transformers is available, otherwise RuleIntentDetector alone.
    """

    def __init__(
        self,
        confidence_engine: Optional[ConfidenceEngine] = None,
        config: Optional[Dict[str, Any]] = None,
        detector: Optional[IntentDetector] = None,
    ) -> None:
        self._confidence = confidence_engine or ConfidenceEngine()
        cfg = config or {}
        self._multi_intent_enabled: bool = bool(cfg.get("multi_intent_enabled", True))
        self._max_intents: int = int(cfg.get("max_intents", 3))
        self._secondary_threshold: float = float(cfg.get("secondary_intent_threshold", 0.20))

        if detector is not None:
            self._detector = detector
        else:
            self._detector = self._build_default_detector(cfg)

        logger.debug("IntentPipeline using detector=%s", self._detector.name)

    # ─── Public API ───────────────────────────────────────────────────────────

    def set_detector(self, detector: IntentDetector) -> None:
        """Hot-swap the classifier without restarting the pipeline."""
        self._detector = detector
        logger.info("IntentPipeline.detector_swapped new=%s", detector.name)

    def analyze(self, content: str) -> Tuple[Optional[DetectedIntent], List[DetectedIntent]]:
        """
        Analyze content and return (primary_intent, all_intents).
        Delegates scoring entirely to the injected IntentDetector.
        """
        text = (content or "").strip()
        if not text:
            unknown = DetectedIntent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                reasoning="Empty input",
            )
            return unknown, [unknown]

        raw_scores = self._detector.detect(text)

        ranked: List[Tuple[IntentType, float]] = sorted(
            ((t, s) for t, s in raw_scores.items() if t != IntentType.UNKNOWN),
            key=lambda x: x[1],
            reverse=True,
        )

        if not ranked:
            unknown = DetectedIntent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                reasoning="No intent scores returned",
            )
            return unknown, [unknown]

        best_type, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = max(0.0, best_score - second_score)

        if best_score == 0.0:
            best_type = IntentType.CONVERSATION
            best_score = 0.40
            margin = 0.0

        primary_confidence = self._confidence.intent_confidence(best_score, margin)
        primary = DetectedIntent(
            intent_type=best_type,
            confidence=primary_confidence,
            reasoning=(
                f"{self._detector.name}: score={best_score:.3f}, margin={margin:.3f}"
            ),
            metadata={
                "raw_score": best_score,
                "margin": margin,
                "detector": self._detector.name,
            },
        )

        all_intents: List[DetectedIntent] = [primary]

        if self._multi_intent_enabled:
            for intent_type, score in ranked[1:self._max_intents]:
                if score < self._secondary_threshold:
                    break
                sec_conf = self._confidence.intent_confidence(score, 0.0)
                all_intents.append(DetectedIntent(
                    intent_type=intent_type,
                    confidence=sec_conf,
                    reasoning=f"{self._detector.name}: secondary score={score:.3f}",
                    metadata={"raw_score": score, "detector": self._detector.name},
                ))

        return primary, all_intents

    def is_ambiguous(self, intents: List[DetectedIntent]) -> bool:
        if len(intents) < 2:
            return False
        return abs(intents[0].confidence - intents[1].confidence) < 0.10

    def normalize(self, content: str) -> str:
        return re.sub(r"\s+", " ", content.strip()).strip() if content.strip() else ""

    # ─── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    def _build_default_detector(cfg: Dict[str, Any]) -> IntentDetector:
        rule = RuleIntentDetector()
        embed = EmbeddingIntentDetector(
            model_name=cfg.get("embedding_model", "all-MiniLM-L6-v2")
        )
        if embed.available:
            embed_weight = float(cfg.get("embedding_weight", 0.55))
            rule_weight = 1.0 - embed_weight
            return HybridIntentDetector([(rule, rule_weight), (embed, embed_weight)])
        return rule
