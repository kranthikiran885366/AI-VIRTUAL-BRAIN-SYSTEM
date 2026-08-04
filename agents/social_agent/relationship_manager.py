"""
Relationship Manager — Phase 13

Production-grade relationship modeling:
- User profiles with interaction history
- Trust evolution (decay, positive/negative deltas)
- Rapport scoring
- Communication style preferences
- Relationship confidence scoring
- Context continuity
- Persistent storage with safe load/save
"""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class RelationshipManager:
    """Manages all user relationships with trust, rapport, and history."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config
        self._trust_cfg = config.get("trust", {})
        self._rapport_cfg = config.get("rapport", {})
        self._confidence_cfg = config.get("social_confidence", {})
        self._max_history = int(config.get("max_interaction_history", 200))
        self._storage_path = Path(config.get("storage_path", "data/relationships.json"))

        # In-memory stores
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._trust: Dict[str, float] = {}
        self._rapport: Dict[str, float] = {}
        self._history: Dict[str, Deque[Dict[str, Any]]] = {}

        self._load()

    # ── Public API ─────────────────────────────────────────────────────────────

    def update_state(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update relationship state from a social analysis result.
        Returns the current relationship context.
        """
        sender = analysis.get("sender", "unknown")
        if sender not in self._profiles:
            self._init_profile(sender)

        self._record_interaction(sender, analysis)
        self._update_trust(sender, analysis)
        self._update_rapport(sender, analysis)
        self._update_status(sender)
        self._apply_decay(sender)
        self._save()
        return self.get_context(sender)

    def get_context(self, sender: str) -> Dict[str, Any]:
        if sender not in self._profiles:
            return {
                "status": "new",
                "trust_score": self._trust_cfg.get("initial_value", 0.5),
                "rapport_score": self._rapport_cfg.get("initial_value", 0.5),
                "interaction_count": 0,
                "preferred_formality": "neutral",
                "last_interaction": None,
                "confidence": self._confidence_cfg.get("base", 0.5),
            }
        profile = self._profiles[sender]
        trust = self._trust.get(sender, 0.5)
        rapport = self._rapport.get(sender, 0.5)
        count = profile.get("interaction_count", 0)
        confidence = self._compute_confidence(trust, count)
        return {
            "status": profile.get("status", "new"),
            "trust_score": round(trust, 4),
            "rapport_score": round(rapport, 4),
            "interaction_count": count,
            "preferred_formality": profile.get("preferred_formality", "neutral"),
            "last_interaction": profile.get("last_interaction"),
            "first_interaction": profile.get("first_interaction"),
            "confidence": round(confidence, 4),
            "communication_style": profile.get("communication_style", "neutral"),
        }

    def get_all_relationships(self) -> Dict[str, Dict[str, Any]]:
        return {sender: self.get_context(sender) for sender in self._profiles}

    def get_interaction_history(self, sender: str, limit: int = 20) -> List[Dict[str, Any]]:
        hist = self._history.get(sender)
        if not hist:
            return []
        return list(hist)[-limit:]

    # ── Private helpers ────────────────────────────────────────────────────────

    def _init_profile(self, sender: str) -> None:
        initial_trust = float(self._trust_cfg.get("initial_value", 0.5))
        initial_rapport = float(self._rapport_cfg.get("initial_value", 0.5))
        self._profiles[sender] = {
            "status": "new",
            "first_interaction": _utcnow(),
            "last_interaction": None,
            "interaction_count": 0,
            "preferred_formality": "neutral",
            "communication_style": "neutral",
            "emotional_trend": [],
        }
        self._trust[sender] = initial_trust
        self._rapport[sender] = initial_rapport
        self._history[sender] = deque(maxlen=self._max_history)

    def _record_interaction(self, sender: str, analysis: Dict[str, Any]) -> None:
        profile = self._profiles[sender]
        profile["interaction_count"] = profile.get("interaction_count", 0) + 1
        profile["last_interaction"] = _utcnow()

        # Update preferred formality via exponential moving average
        formality = analysis.get("formality", "neutral")
        formality_map = {"formal": 1.0, "neutral": 0.5, "informal": 0.0}
        current_map = {"formal": 1.0, "neutral": 0.5, "informal": 0.0}
        alpha = 0.2
        current_val = current_map.get(profile.get("preferred_formality", "neutral"), 0.5)
        new_val = formality_map.get(formality, 0.5)
        blended = (1 - alpha) * current_val + alpha * new_val
        if blended > 0.66:
            profile["preferred_formality"] = "formal"
        elif blended < 0.33:
            profile["preferred_formality"] = "informal"
        else:
            profile["preferred_formality"] = "neutral"

        # Communication style from strategy
        strategy = analysis.get("communication_strategy", "conversational_response")
        profile["communication_style"] = strategy

        # Emotional trend (keep last 10)
        trend: List[str] = profile.get("emotional_trend", [])
        trend.append(analysis.get("emotion_sentiment", "neutral"))
        profile["emotional_trend"] = trend[-10:]

        # History entry
        self._history[sender].append({
            "timestamp": _utcnow(),
            "interaction_type": analysis.get("interaction_type", "statement"),
            "emotion_sentiment": analysis.get("emotion_sentiment", "neutral"),
            "formality": formality,
            "intent": analysis.get("intent", "general_statement"),
        })

    def _update_trust(self, sender: str, analysis: Dict[str, Any]) -> None:
        current = self._trust.get(sender, 0.5)
        sentiment = analysis.get("emotion_sentiment", "neutral")
        formality = analysis.get("formality", "neutral")

        delta = 0.0
        if sentiment == "positive":
            delta += float(self._trust_cfg.get("positive_delta", 0.08))
        elif sentiment == "negative":
            delta -= float(self._trust_cfg.get("negative_delta", 0.10))

        if formality == "formal":
            delta += float(self._trust_cfg.get("formal_delta", 0.04))
        elif formality == "informal":
            delta -= float(self._trust_cfg.get("informal_delta", 0.03))

        min_v = float(self._trust_cfg.get("min_value", 0.0))
        max_v = float(self._trust_cfg.get("max_value", 1.0))
        self._trust[sender] = max(min_v, min(max_v, current + delta))

    def _update_rapport(self, sender: str, analysis: Dict[str, Any]) -> None:
        current = self._rapport.get(sender, 0.5)
        sentiment = analysis.get("emotion_sentiment", "neutral")
        delta = 0.0
        if sentiment == "positive":
            delta += float(self._rapport_cfg.get("positive_delta", 0.06))
        elif sentiment == "negative":
            delta -= float(self._rapport_cfg.get("negative_delta", 0.08))
        self._rapport[sender] = max(0.0, min(1.0, current + delta))

    def _update_status(self, sender: str) -> None:
        profile = self._profiles[sender]
        count = profile.get("interaction_count", 0)
        trust = self._trust.get(sender, 0.5)
        trusted_t = float(self._trust_cfg.get("trusted_threshold", 0.70))
        distrust_t = float(self._trust_cfg.get("distrustful_threshold", 0.30))
        new_t = int(self._trust_cfg.get("new_interaction_count", 3))

        if count < new_t:
            profile["status"] = "new"
        elif trust >= trusted_t:
            profile["status"] = "trusted"
        elif trust <= distrust_t:
            profile["status"] = "distrustful"
        else:
            profile["status"] = "developing"

    def _apply_decay(self, sender: str) -> None:
        """Apply time-based trust/rapport decay for inactivity."""
        profile = self._profiles.get(sender, {})
        last_str = profile.get("last_interaction")
        if not last_str:
            return
        try:
            last = datetime.fromisoformat(last_str)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days_inactive = max(0.0, (datetime.now(timezone.utc) - last).total_seconds() / 86400 - 1)
            if days_inactive <= 0:
                return
            trust_decay = float(self._trust_cfg.get("decay_rate_per_day", 0.01)) * days_inactive
            rapport_decay = float(self._rapport_cfg.get("decay_rate_per_day", 0.005)) * days_inactive
            self._trust[sender] = max(0.0, self._trust.get(sender, 0.5) - trust_decay)
            self._rapport[sender] = max(0.0, self._rapport.get(sender, 0.5) - rapport_decay)
        except Exception:
            pass

    def _compute_confidence(self, trust: float, count: int) -> float:
        base = float(self._confidence_cfg.get("base", 0.5))
        tw = float(self._confidence_cfg.get("trust_weight", 0.4))
        iw = float(self._confidence_cfg.get("interaction_weight", 0.01))
        max_bonus = float(self._confidence_cfg.get("max_interaction_bonus", 0.3))
        return min(1.0, base + trust * tw + min(max_bonus, count * iw))

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if self._storage_path.exists():
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._profiles = data.get("profiles", {})
                self._trust = data.get("trust", {})
                self._rapport = data.get("rapport", {})
                raw_history = data.get("history", {})
                for sender, entries in raw_history.items():
                    self._history[sender] = deque(entries, maxlen=self._max_history)
        except Exception as exc:
            logger.warning("relationship_manager.load_failed error=%s", exc)

    def _save(self) -> None:
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "profiles": self._profiles,
                "trust": self._trust,
                "rapport": self._rapport,
                "history": {s: list(h) for s, h in self._history.items()},
            }
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, default=str)
        except Exception as exc:
            logger.warning("relationship_manager.save_failed error=%s", exc)

    # ── Legacy compatibility ───────────────────────────────────────────────────

    def _get_relationship_context(self, sender: str) -> Dict[str, Any]:
        """Backward-compatible alias."""
        return self.get_context(sender)
