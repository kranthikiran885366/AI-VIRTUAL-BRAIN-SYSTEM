"""
Production Emotion Engine — Phase 8
Structured affective state model with signal detection, regulation, history,
metrics, audit trail, and multi-agent influence via broker.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

_EMOTION_VERSION = "8.0.0"
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "emotion_config.yaml"


# ─── Config loader ────────────────────────────────────────────────────────────

def _load_emotion_config() -> Dict[str, Any]:
    if not _YAML_AVAILABLE or not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = _yaml.safe_load(f) or {}
        return raw.get("emotion", {})
    except Exception as exc:
        logger.warning("emotion_config.load_failed error=%s", exc)
        return {}


# ─── Emotional State Model ────────────────────────────────────────────────────

@dataclass
class EmotionalState:
    """Structured multi-dimensional emotional state."""
    state_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1

    # Core dimensions (all 0.0–1.0)
    confidence: float = 0.70
    uncertainty: float = 0.20
    curiosity: float = 0.50
    urgency: float = 0.20
    engagement: float = 0.60
    satisfaction: float = 0.50
    frustration: float = 0.00
    focus: float = 0.60
    cognitive_load: float = 0.30
    stress: float = 0.00
    recovery: float = 1.00

    # Derived indicators
    is_stressed: bool = False
    is_overloaded: bool = False
    is_low_confidence: bool = False
    is_highly_engaged: bool = False
    needs_recovery: bool = False

    # Transition metadata
    trigger: Optional[str] = None
    trigger_source: Optional[str] = None
    previous_state_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def get_dimension(self, name: str) -> float:
        return float(getattr(self, name, 0.0))

    def set_dimension(self, name: str, value: float) -> None:
        if hasattr(self, name) and isinstance(getattr(self, name), float):
            setattr(self, name, max(0.0, min(1.0, value)))

    def dimensions(self) -> Dict[str, float]:
        return {
            k: getattr(self, k)
            for k in ["confidence", "uncertainty", "curiosity", "urgency",
                      "engagement", "satisfaction", "frustration", "focus",
                      "cognitive_load", "stress", "recovery"]
        }

    def confidence_influence(self, cfg: Dict[str, Any]) -> float:
        """Compute net confidence adjustment to emit to other agents."""
        if not cfg.get("enabled", True):
            return 0.0
        delta = 0.0
        if self.confidence < cfg.get("low_confidence_threshold", 0.40):
            delta -= cfg.get("low_confidence_penalty", 0.10)
        if self.stress > cfg.get("stress_alert_threshold", 0.70):
            delta -= cfg.get("high_stress_penalty", 0.08)
        if self.engagement > cfg.get("high_engagement_threshold", 0.80):
            delta += cfg.get("high_engagement_bonus", 0.05)
        return max(
            cfg.get("min_influence", -0.20),
            min(cfg.get("max_influence", 0.10), delta)
        )


# ─── Signal ───────────────────────────────────────────────────────────────────

@dataclass
class EmotionSignal:
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "unknown"          # execution | reasoning | planning | learning | user | system
    signal_type: str = "unknown"     # failure | timeout | low_confidence | positive_feedback …
    intensity: float = 0.5           # 0.0–1.0
    context: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Emotion Session ──────────────────────────────────────────────────────────

@dataclass
class EmotionSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ended_at: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    signals_processed: int = 0
    transitions: int = 0
    recommendations_generated: int = 0
    initial_state: Optional[Dict] = None
    final_state: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Emotion Metrics ──────────────────────────────────────────────────────────

@dataclass
class EmotionMetrics:
    total_signals: int = 0
    total_transitions: int = 0
    total_recommendations: int = 0
    stress_alerts: int = 0
    overload_alerts: int = 0
    low_confidence_alerts: int = 0
    recovery_events: int = 0
    total_analysis_ms: float = 0.0
    sessions_created: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Production Emotion Engine ────────────────────────────────────────────────

class EmotionEngine:
    """
    Production affective state engine.
    Manages emotional state lifecycle, signal detection, regulation,
    history, metrics, audit trail, and confidence influence.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        file_cfg = _load_emotion_config()
        self._cfg = {**file_cfg, **(config or {})}

        # Dimension defaults from config
        dim_defaults = self._cfg.get("dimensions", {})
        self._neutral = self._cfg.get("decay", {}).get("neutral", {})
        self._decay_rates = self._cfg.get("decay", {}).get("rates", {})
        self._decay_interval = float(self._cfg.get("decay", {}).get("interval_seconds", 5.0))
        self._transition_cfg = self._cfg.get("transitions", {})
        self._signal_cfg = self._cfg.get("signals", {})
        self._confidence_influence_cfg = self._cfg.get("confidence_influence", {})
        self._history_cfg = self._cfg.get("history", {})
        self._smoothing = float(self._transition_cfg.get("smoothing_factor", 0.25))

        # Current state
        self._state = EmotionalState(
            confidence=float(dim_defaults.get("confidence", 0.70)),
            uncertainty=float(dim_defaults.get("uncertainty", 0.20)),
            curiosity=float(dim_defaults.get("curiosity", 0.50)),
            urgency=float(dim_defaults.get("urgency", 0.20)),
            engagement=float(dim_defaults.get("engagement", 0.60)),
            satisfaction=float(dim_defaults.get("satisfaction", 0.50)),
            frustration=float(dim_defaults.get("frustration", 0.00)),
            focus=float(dim_defaults.get("focus", 0.60)),
            cognitive_load=float(dim_defaults.get("cognitive_load", 0.30)),
            stress=float(dim_defaults.get("stress", 0.00)),
            recovery=float(dim_defaults.get("recovery", 1.00)),
        )

        # History (bounded)
        max_state = int(self._history_cfg.get("max_state_history", 2000))
        max_trans = int(self._history_cfg.get("max_transition_history", 1000))
        max_audit = int(self._history_cfg.get("max_audit_trail", 5000))
        max_sess = int(self._history_cfg.get("max_session_history", 500))

        self._state_history: Deque[Dict] = deque(maxlen=max_state)
        self._transition_history: Deque[Dict] = deque(maxlen=max_trans)
        self._audit_trail: Deque[Dict] = deque(maxlen=max_audit)
        self._session_history: Deque[Dict] = deque(maxlen=max_sess)
        self._signal_history: Deque[Dict] = deque(maxlen=max_state)

        self._metrics = EmotionMetrics()
        self._active_session: Optional[EmotionSession] = None
        self._decay_task: Optional[asyncio.Task] = None
        self._running = False
        self._version = _EMOTION_VERSION

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._decay_task = asyncio.create_task(
            self._decay_loop(), name="emotion_engine.decay"
        )
        logger.info("emotion_engine.started version=%s", self._version)

    async def stop(self) -> None:
        self._running = False
        if self._decay_task and not self._decay_task.done():
            self._decay_task.cancel()
            try:
                await self._decay_task
            except asyncio.CancelledError:
                pass
        logger.info("emotion_engine.stopped")

    # ─── Session Management ───────────────────────────────────────────────────

    def begin_session(
        self,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> EmotionSession:
        session = EmotionSession(
            request_id=request_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            initial_state=self._state.to_dict(),
        )
        self._active_session = session
        self._metrics.sessions_created += 1
        self._audit("session_started", {"session_id": session.session_id,
                                         "correlation_id": correlation_id})
        return session

    def end_session(self, session: Optional[EmotionSession] = None) -> Optional[Dict]:
        s = session or self._active_session
        if not s:
            return None
        s.ended_at = datetime.utcnow().isoformat()
        s.final_state = self._state.to_dict()
        self._session_history.append(s.to_dict())
        if self._active_session and self._active_session.session_id == s.session_id:
            self._active_session = None
        self._audit("session_ended", {"session_id": s.session_id})
        return s.to_dict()

    # ─── Signal Processing ────────────────────────────────────────────────────

    async def process_signal(self, signal: EmotionSignal) -> Dict[str, Any]:
        """Process an emotion signal and update state accordingly."""
        start = time.perf_counter()
        self._metrics.total_signals += 1
        self._signal_history.append(signal.to_dict())

        if self._active_session:
            self._active_session.signals_processed += 1

        # Compute state deltas from signal
        deltas = self._compute_signal_deltas(signal)

        # Apply deltas with smoothing
        prev_state_id = self._state.state_id
        old_dims = self._state.dimensions()
        self._apply_deltas(deltas, signal)

        # Detect transitions
        new_dims = self._state.dimensions()
        transitions = self._detect_transitions(old_dims, new_dims)
        if transitions:
            self._metrics.total_transitions += len(transitions)
            if self._active_session:
                self._active_session.transitions += len(transitions)
            for t in transitions:
                self._transition_history.append(t)

        # Update derived indicators
        self._update_indicators()

        # Snapshot state
        self._state_history.append(self._state.to_dict())

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_analysis_ms += duration_ms

        self._audit("signal_processed", {
            "signal_id": signal.signal_id,
            "signal_type": signal.signal_type,
            "source": signal.source,
            "intensity": signal.intensity,
            "transitions": len(transitions),
            "duration_ms": duration_ms,
            "correlation_id": signal.correlation_id,
        })

        return {
            "signal_id": signal.signal_id,
            "state": self._state.to_dict(),
            "transitions": transitions,
            "confidence_influence": self._state.confidence_influence(
                {**self._confidence_influence_cfg, **self._transition_cfg}
            ),
            "duration_ms": duration_ms,
        }

    def _compute_signal_deltas(self, signal: EmotionSignal) -> Dict[str, float]:
        """Map signal type to dimension deltas."""
        w = self._signal_cfg
        intensity = max(0.0, min(1.0, signal.intensity))
        deltas: Dict[str, float] = {}

        stype = signal.signal_type

        if stype == "execution_failure":
            w_val = float(w.get("execution_failure_weight", 0.15))
            deltas["frustration"] = intensity * w_val * 2.0
            deltas["confidence"] = -intensity * w_val
            deltas["stress"] = intensity * w_val * 1.5
            deltas["satisfaction"] = -intensity * w_val * 0.5

        elif stype == "timeout":
            w_val = float(w.get("timeout_weight", 0.12))
            deltas["urgency"] = intensity * w_val * 2.0
            deltas["stress"] = intensity * w_val * 1.5
            deltas["frustration"] = intensity * w_val

        elif stype == "reasoning_low_confidence":
            w_val = float(w.get("reasoning_low_confidence_weight", 0.10))
            deltas["uncertainty"] = intensity * w_val * 2.0
            deltas["confidence"] = -intensity * w_val
            deltas["cognitive_load"] = intensity * w_val

        elif stype == "planning_risk":
            w_val = float(w.get("planning_risk_weight", 0.08))
            deltas["urgency"] = intensity * w_val
            deltas["stress"] = intensity * w_val
            deltas["focus"] = intensity * w_val * 0.5

        elif stype == "learning_failure":
            w_val = float(w.get("learning_failure_weight", 0.10))
            deltas["frustration"] = intensity * w_val
            deltas["confidence"] = -intensity * w_val * 0.5
            deltas["curiosity"] = intensity * w_val * 0.3

        elif stype == "user_feedback_positive":
            w_val = float(w.get("user_feedback_positive_weight", 0.12))
            deltas["satisfaction"] = intensity * w_val * 2.0
            deltas["confidence"] = intensity * w_val
            deltas["engagement"] = intensity * w_val
            deltas["frustration"] = -intensity * w_val * 0.5

        elif stype == "user_feedback_negative":
            w_val = float(w.get("user_feedback_negative_weight", 0.15))
            deltas["frustration"] = intensity * w_val * 1.5
            deltas["confidence"] = -intensity * w_val
            deltas["satisfaction"] = -intensity * w_val

        elif stype == "system_health_degraded":
            w_val = float(w.get("system_health_degraded_weight", 0.10))
            deltas["stress"] = intensity * w_val * 2.0
            deltas["urgency"] = intensity * w_val
            deltas["cognitive_load"] = intensity * w_val

        elif stype == "task_completed":
            deltas["satisfaction"] = intensity * 0.10
            deltas["confidence"] = intensity * 0.05
            deltas["frustration"] = -intensity * 0.05
            deltas["stress"] = -intensity * 0.05

        elif stype == "high_load":
            deltas["cognitive_load"] = intensity * 0.15
            deltas["stress"] = intensity * 0.10
            deltas["focus"] = -intensity * 0.05

        elif stype == "recovery":
            deltas["stress"] = -intensity * 0.20
            deltas["frustration"] = -intensity * 0.15
            deltas["recovery"] = intensity * 0.20
            deltas["confidence"] = intensity * 0.05

        # Cap max impact per signal
        max_impact = float(w.get("max_signal_impact", 0.40))
        return {k: max(-max_impact, min(max_impact, v)) for k, v in deltas.items()}

    def _apply_deltas(self, deltas: Dict[str, float], signal: EmotionSignal) -> None:
        """Apply deltas to current state with smoothing."""
        new_state = EmotionalState(
            **{k: v for k, v in self._state.to_dict().items()
               if k in EmotionalState.__dataclass_fields__}
        )
        new_state.state_id = str(uuid.uuid4())
        new_state.timestamp = datetime.utcnow().isoformat()
        new_state.version = self._state.version + 1
        new_state.previous_state_id = self._state.state_id
        new_state.trigger = signal.signal_type
        new_state.trigger_source = signal.source

        for dim, delta in deltas.items():
            current = new_state.get_dimension(dim)
            # Smoothed update: new = current + (1 - smoothing) * delta
            updated = current + (1.0 - self._smoothing) * delta
            new_state.set_dimension(dim, updated)

        self._state = new_state

    def _detect_transitions(
        self, old: Dict[str, float], new: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Detect significant state transitions."""
        transitions = []
        threshold = 0.05  # minimum change to record as transition

        for dim in old:
            old_val = old.get(dim, 0.0)
            new_val = new.get(dim, 0.0)
            change = new_val - old_val
            if abs(change) >= threshold:
                transitions.append({
                    "dimension": dim,
                    "from": round(old_val, 4),
                    "to": round(new_val, 4),
                    "change": round(change, 4),
                    "direction": "increase" if change > 0 else "decrease",
                    "timestamp": datetime.utcnow().isoformat(),
                })

        return transitions

    def _update_indicators(self) -> None:
        """Update derived boolean indicators from thresholds."""
        t = self._transition_cfg
        self._state.is_stressed = self._state.stress > float(t.get("stress_alert_threshold", 0.70))
        self._state.is_overloaded = self._state.cognitive_load > float(t.get("cognitive_overload_threshold", 0.80))
        self._state.is_low_confidence = self._state.confidence < float(t.get("low_confidence_threshold", 0.40))
        self._state.is_highly_engaged = self._state.engagement > float(t.get("high_engagement_threshold", 0.80))
        self._state.needs_recovery = self._state.recovery < float(t.get("recovery_threshold", 0.30))

        if self._state.is_stressed:
            self._metrics.stress_alerts += 1
        if self._state.is_overloaded:
            self._metrics.overload_alerts += 1
        if self._state.is_low_confidence:
            self._metrics.low_confidence_alerts += 1
        if self._state.needs_recovery:
            self._metrics.recovery_events += 1

    # ─── Decay Loop ───────────────────────────────────────────────────────────

    async def _decay_loop(self) -> None:
        """Background decay: gradually return dimensions toward neutral."""
        while self._running:
            try:
                await asyncio.sleep(self._decay_interval)
                self._apply_decay()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("emotion_engine.decay_error error=%s", exc)

    def _apply_decay(self) -> None:
        """Apply per-dimension decay toward neutral values."""
        for dim, rate in self._decay_rates.items():
            current = self._state.get_dimension(dim)
            neutral = float(self._neutral.get(dim, 0.5))
            # Move toward neutral by decay rate
            if abs(current - neutral) > 0.001:
                direction = 1.0 if neutral > current else -1.0
                new_val = current + direction * float(rate)
                # Don't overshoot neutral
                if direction > 0:
                    new_val = min(new_val, neutral)
                else:
                    new_val = max(new_val, neutral)
                self._state.set_dimension(dim, new_val)

        self._update_indicators()

    # ─── Text Analysis ────────────────────────────────────────────────────────

    def analyze_text(self, text: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Keyword-weighted emotion scoring from text input."""
        lower = text.lower()
        emotion_keywords = {
            "joy":          ["happy", "great", "wonderful", "excited", "love", "amazing", "fantastic", "glad", "delighted", "thrilled"],
            "sadness":      ["sad", "unhappy", "depressed", "cry", "miss", "lonely", "grief", "sorrow", "heartbroken", "miserable"],
            "anger":        ["angry", "frustrated", "annoyed", "hate", "mad", "furious", "rage", "irritated", "outraged", "livid"],
            "fear":         ["scared", "afraid", "anxious", "worried", "nervous", "terrified", "panic", "dread", "apprehensive"],
            "surprise":     ["surprised", "shocked", "unexpected", "astonished", "amazed", "stunned", "wow", "unbelievable"],
            "disgust":      ["disgusting", "gross", "awful", "horrible", "revolting", "nasty", "repulsive"],
            "anticipation": ["excited", "looking forward", "can't wait", "eager", "hopeful", "expect", "anticipate"],
            "trust":        ["trust", "believe", "confident", "reliable", "honest", "faithful", "secure", "safe"],
        }
        scores: Dict[str, float] = {}
        for emotion, keywords in emotion_keywords.items():
            count = sum(1 for kw in keywords if kw in lower)
            scores[emotion] = round(min(1.0, count * 0.25), 3)

        if all(v == 0 for v in scores.values()):
            scores["neutral"] = 0.5
            primary = "neutral"
            sentiment = "neutral"
        else:
            primary = max(scores, key=lambda k: scores[k])
            pos = scores.get("joy", 0) + scores.get("trust", 0) + scores.get("anticipation", 0)
            neg = scores.get("sadness", 0) + scores.get("anger", 0) + scores.get("fear", 0) + scores.get("disgust", 0)
            sentiment = "positive" if pos > neg else "negative" if neg > pos else "neutral"

        confidence = min(0.95, 0.4 + max(scores.values()) * 0.6)

        # Map detected emotion to signal type
        signal_type = self._map_emotion_to_signal(primary, sentiment)

        return {
            "primary_emotion": primary,
            "emotions": scores,
            "sentiment": sentiment,
            "confidence": round(confidence, 3),
            "signal_type": signal_type,
            "text_length": len(text),
            "current_state": self._state.dimensions(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _map_emotion_to_signal(self, primary: str, sentiment: str) -> str:
        mapping = {
            "anger": "user_feedback_negative",
            "sadness": "user_feedback_negative",
            "fear": "user_feedback_negative",
            "disgust": "user_feedback_negative",
            "joy": "user_feedback_positive",
            "trust": "user_feedback_positive",
            "anticipation": "user_feedback_positive",
        }
        return mapping.get(primary, "user_feedback_positive" if sentiment == "positive" else "user_feedback_negative")

    # ─── State Access ─────────────────────────────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        return self._state.to_dict()

    def get_dimensions(self) -> Dict[str, float]:
        return self._state.dimensions()

    def get_confidence_influence(self) -> float:
        return self._state.confidence_influence(
            {**self._confidence_influence_cfg, **self._transition_cfg}
        )

    def get_state_history(self, limit: int = 50) -> List[Dict]:
        return list(self._state_history)[-limit:]

    def get_transition_history(self, limit: int = 50) -> List[Dict]:
        return list(self._transition_history)[-limit:]

    def get_audit_trail(self, limit: int = 100) -> List[Dict]:
        return list(self._audit_trail)[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        m = self._metrics.as_dict()
        m["version"] = self._version
        m["state_history_size"] = len(self._state_history)
        m["transition_history_size"] = len(self._transition_history)
        m["signal_history_size"] = len(self._signal_history)
        m["avg_analysis_ms"] = round(
            self._metrics.total_analysis_ms / max(1, self._metrics.total_signals), 2
        )
        return m

    def get_analytics(self) -> Dict[str, Any]:
        """Compute trend analytics from state history."""
        history = list(self._state_history)
        if not history:
            return {"error": "no_history"}

        dims = ["confidence", "stress", "frustration", "engagement", "satisfaction"]
        trends: Dict[str, Any] = {}
        for dim in dims:
            values = [h.get(dim, 0.0) for h in history[-20:]]
            if len(values) >= 2:
                trend = "increasing" if values[-1] > values[0] else "decreasing" if values[-1] < values[0] else "stable"
                trends[dim] = {
                    "current": round(values[-1], 4),
                    "average": round(sum(values) / len(values), 4),
                    "min": round(min(values), 4),
                    "max": round(max(values), 4),
                    "trend": trend,
                }

        return {
            "state_snapshots": len(history),
            "dimension_trends": trends,
            "current_indicators": {
                "is_stressed": self._state.is_stressed,
                "is_overloaded": self._state.is_overloaded,
                "is_low_confidence": self._state.is_low_confidence,
                "is_highly_engaged": self._state.is_highly_engaged,
                "needs_recovery": self._state.needs_recovery,
            },
            "metrics": self.get_metrics(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ─── Validation ───────────────────────────────────────────────────────────

    def validate_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        if not isinstance(signal_data.get("signal_type"), str):
            errors.append("signal_type must be a string")
        intensity = signal_data.get("intensity", 0.5)
        if not isinstance(intensity, (int, float)) or not (0.0 <= float(intensity) <= 1.0):
            errors.append("intensity must be a float in [0.0, 1.0]")
        if not isinstance(signal_data.get("source", ""), str):
            errors.append("source must be a string")
        return {"valid": len(errors) == 0, "errors": errors}

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _audit(self, event: str, data: Dict[str, Any]) -> None:
        self._audit_trail.append({
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            **data,
        })
