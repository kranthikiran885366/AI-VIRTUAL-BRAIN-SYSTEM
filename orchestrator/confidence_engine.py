"""
Confidence Engine — Phase 4.1

Multi-dimensional agent performance scoring.
Tracks: success rate, latency, timeout frequency, retry frequency,
partial success, and resource cost.
All thresholds and weights are configuration-driven.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: Dict[str, Any] = {
    "min_routing_confidence": 0.35,
    "min_intent_confidence": 0.30,
    "high_confidence_threshold": 0.75,
    "history_weight": 0.15,
    # Multi-dimensional weights (must sum to 1.0)
    "perf_weight_success": 0.45,
    "perf_weight_latency": 0.20,
    "perf_weight_timeout": 0.15,
    "perf_weight_retry": 0.10,
    "perf_weight_partial": 0.10,
    # Latency target in ms — above this, latency score degrades
    "latency_target_ms": 500.0,
    # Max history entries per agent
    "max_history_per_agent": 200,
}


@dataclass
class AgentExecutionSample:
    """Single execution observation for multi-dimensional scoring."""
    success: bool
    latency_ms: float
    timed_out: bool = False
    retry_count: int = 0
    partial_success: bool = False
    resource_cost: float = 0.0  # normalised [0, 1]; reserved for future use


@dataclass
class AgentPerformanceProfile:
    """Rolling multi-dimensional performance profile for one agent."""
    samples: Deque[AgentExecutionSample] = field(default_factory=lambda: deque(maxlen=200))

    # Derived metrics (recomputed on each record_sample call)
    success_rate: float = 1.0
    avg_latency_ms: float = 0.0
    timeout_rate: float = 0.0
    retry_rate: float = 0.0
    partial_success_rate: float = 0.0
    composite_score: float = 1.0

    def record(self, sample: AgentExecutionSample, weights: Dict[str, float]) -> None:
        self.samples.append(sample)
        self._recompute(weights)

    def _recompute(self, weights: Dict[str, float]) -> None:
        n = len(self.samples)
        if n == 0:
            return
        successes = sum(1 for s in self.samples if s.success)
        timeouts = sum(1 for s in self.samples if s.timed_out)
        retries = sum(s.retry_count for s in self.samples)
        partials = sum(1 for s in self.samples if s.partial_success)
        latencies = [s.latency_ms for s in self.samples if s.latency_ms > 0]

        self.success_rate = round(successes / n, 4)
        self.timeout_rate = round(timeouts / n, 4)
        self.retry_rate = round(min(1.0, retries / n), 4)
        self.partial_success_rate = round(partials / n, 4)
        self.avg_latency_ms = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_count": len(self.samples),
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "timeout_rate": self.timeout_rate,
            "retry_rate": self.retry_rate,
            "partial_success_rate": self.partial_success_rate,
            "composite_score": self.composite_score,
        }


class ConfidenceEngine:
    """
    Multi-dimensional confidence estimation and agent performance tracking.
    All thresholds and dimension weights are configuration-driven.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = config or {}
        self._min_routing = float(cfg.get("min_routing_confidence", _DEFAULT_CONFIG["min_routing_confidence"]))
        self._min_intent = float(cfg.get("min_intent_confidence", _DEFAULT_CONFIG["min_intent_confidence"]))
        self._high_threshold = float(cfg.get("high_confidence_threshold", _DEFAULT_CONFIG["high_confidence_threshold"]))
        self._history_weight = float(cfg.get("history_weight", _DEFAULT_CONFIG["history_weight"]))
        self._latency_target = float(cfg.get("latency_target_ms", _DEFAULT_CONFIG["latency_target_ms"]))
        self._max_history = int(cfg.get("max_history_per_agent", _DEFAULT_CONFIG["max_history_per_agent"]))

        # Dimension weights
        self._w_success = float(cfg.get("perf_weight_success", _DEFAULT_CONFIG["perf_weight_success"]))
        self._w_latency = float(cfg.get("perf_weight_latency", _DEFAULT_CONFIG["perf_weight_latency"]))
        self._w_timeout = float(cfg.get("perf_weight_timeout", _DEFAULT_CONFIG["perf_weight_timeout"]))
        self._w_retry = float(cfg.get("perf_weight_retry", _DEFAULT_CONFIG["perf_weight_retry"]))
        self._w_partial = float(cfg.get("perf_weight_partial", _DEFAULT_CONFIG["perf_weight_partial"]))

        self._weights = {
            "success": self._w_success,
            "latency": self._w_latency,
            "timeout": self._w_timeout,
            "retry": self._w_retry,
            "partial": self._w_partial,
        }

        # Per-agent profiles
        self._profiles: Dict[str, AgentPerformanceProfile] = {}

        # Legacy boolean history (kept for get_performance_weights backward compat)
        self._agent_history: Dict[str, List[bool]] = {}

    # ─── Confidence Calibration ───────────────────────────────────────────────

    def intent_confidence(self, raw_score: float, margin: float = 0.0) -> float:
        calibrated = min(0.98, 0.30 + raw_score * 0.55 + margin * 0.20)
        return round(max(0.0, calibrated), 4)

    def routing_confidence(
        self,
        semantic_score: float,
        margin: float = 0.0,
        capability_match: bool = False,
        agent_name: Optional[str] = None,
    ) -> float:
        base = min(0.98, 0.35 + semantic_score * 0.55 + margin * 0.25)
        if capability_match:
            base = min(0.98, base + 0.05)
        if agent_name:
            hist = self._composite_score(agent_name)
            base = base * (1.0 - self._history_weight) + hist * self._history_weight
        return round(max(0.0, base), 4)

    def combined_confidence(self, intent_conf: float, routing_conf: float) -> float:
        return round(min(0.98, (intent_conf * routing_conf) ** 0.5), 4)

    def is_high_confidence(self, confidence: float) -> bool:
        return confidence >= self._high_threshold

    def is_above_routing_threshold(self, confidence: float) -> bool:
        return confidence >= self._min_routing

    def is_above_intent_threshold(self, confidence: float) -> bool:
        return confidence >= self._min_intent

    def explain(self, intent_conf: float, routing_conf: float, combined: float) -> str:
        parts = [
            f"intent={intent_conf:.3f}",
            f"routing={routing_conf:.3f}",
            f"combined={combined:.3f}",
        ]
        if combined >= self._high_threshold:
            parts.append("HIGH_CONFIDENCE")
        elif combined >= self._min_routing:
            parts.append("ACCEPTABLE")
        else:
            parts.append("LOW_CONFIDENCE→FALLBACK")
        return " | ".join(parts)

    # ─── Multi-dimensional Recording ─────────────────────────────────────────

    def record_sample(self, agent_name: str, sample: AgentExecutionSample) -> None:
        """Record a full execution sample for multi-dimensional scoring."""
        profile = self._profiles.setdefault(agent_name, AgentPerformanceProfile(
            samples=deque(maxlen=self._max_history)
        ))
        profile.record(sample, self._weights)
        profile.composite_score = self._compute_composite(profile)
        # Keep legacy boolean history in sync
        self._agent_history.setdefault(agent_name, []).append(sample.success)
        if len(self._agent_history[agent_name]) > self._max_history:
            self._agent_history[agent_name] = self._agent_history[agent_name][-self._max_history:]

    def record_outcome(self, agent_name: str, success: bool) -> None:
        """Backward-compatible single-bool recording."""
        self.record_sample(agent_name, AgentExecutionSample(
            success=success, latency_ms=0.0
        ))

    def record_execution(
        self,
        agent_name: str,
        success: bool,
        latency_ms: float,
        timed_out: bool = False,
        retry_count: int = 0,
        partial_success: bool = False,
        resource_cost: float = 0.0,
    ) -> None:
        """Convenience wrapper for full execution recording."""
        self.record_sample(agent_name, AgentExecutionSample(
            success=success,
            latency_ms=latency_ms,
            timed_out=timed_out,
            retry_count=retry_count,
            partial_success=partial_success,
            resource_cost=resource_cost,
        ))

    # ─── Performance Queries ──────────────────────────────────────────────────

    def get_agent_success_rate(self, agent_name: str) -> float:
        profile = self._profiles.get(agent_name)
        if profile is None or not profile.samples:
            return 1.0
        return profile.success_rate

    def get_agent_profile(self, agent_name: str) -> Dict[str, Any]:
        profile = self._profiles.get(agent_name)
        if profile is None:
            return {"sample_count": 0, "composite_score": 1.0}
        return profile.to_dict()

    def get_performance_weights(self) -> Dict[str, float]:
        """Return per-agent routing weights based on composite score."""
        weights: Dict[str, float] = {}
        for agent, profile in self._profiles.items():
            if not profile.samples:
                continue
            score = profile.composite_score
            weights[agent] = round(0.2 + score * 1.3, 4)
        return weights

    def rank_agents(self, agent_names: List[str]) -> List[str]:
        """Return agents sorted by composite score descending."""
        def _score(name: str) -> float:
            p = self._profiles.get(name)
            return p.composite_score if p else 1.0
        return sorted(agent_names, key=_score, reverse=True)

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _composite_score(self, agent_name: str) -> float:
        profile = self._profiles.get(agent_name)
        if profile is None or not profile.samples:
            return 1.0
        return profile.composite_score

    def _compute_composite(self, profile: AgentPerformanceProfile) -> float:
        """
        Weighted composite: higher is better.
        - success_rate: higher = better
        - latency_score: 1.0 at target, degrades above
        - timeout_rate: lower = better (inverted)
        - retry_rate: lower = better (inverted)
        - partial_success_rate: partial credit
        """
        latency_score = min(1.0, self._latency_target / max(1.0, profile.avg_latency_ms))
        composite = (
            self._w_success * profile.success_rate
            + self._w_latency * latency_score
            + self._w_timeout * (1.0 - profile.timeout_rate)
            + self._w_retry * (1.0 - min(1.0, profile.retry_rate))
            + self._w_partial * (profile.success_rate + profile.partial_success_rate * 0.5)
        )
        return round(min(1.0, max(0.0, composite)), 4)
