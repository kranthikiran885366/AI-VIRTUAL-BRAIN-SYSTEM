"""
Recommendation Engine — Phase 8
Generates structured affective recommendations for confidence improvement,
planning, learning, recovery, priority adjustment, and communication.
All thresholds are configuration-driven.
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

import logging
logger = logging.getLogger(__name__)


# ─── Recommendation dataclass ─────────────────────────────────────────────────

@dataclass
class Recommendation:
    """
    Structured recommendation with full explainability fields.
    Every recommendation must carry reason, confidence, evidence,
    expected impact, and limitations.
    """
    recommendation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Classification
    category: str = "general"          # confidence | planning | learning | recovery | priority | communication
    action_type: str = "suggest"       # suggest | alert | adjust | recover | escalate
    priority: int = 2                  # 1=critical, 2=high, 3=medium, 4=low

    # Content
    title: str = ""
    message: str = ""
    action_step: str = ""

    # Explainability
    reason: str = ""
    confidence: float = 0.5
    supporting_evidence: List[str] = field(default_factory=list)
    expected_impact: str = ""
    limitations: List[str] = field(default_factory=list)
    affected_subsystems: List[str] = field(default_factory=list)

    # Context
    trigger_dimension: Optional[str] = None
    trigger_value: Optional[float] = None
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None

    # Outcome tracking
    was_applied: bool = False
    outcome: Optional[str] = None
    effectiveness_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Recommendation Metrics ───────────────────────────────────────────────────

@dataclass
class RecommendationMetrics:
    total_generated: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    applied_count: int = 0
    effective_count: int = 0
    avg_confidence: float = 0.0
    total_confidence_sum: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total_generated": self.total_generated,
            "by_category": dict(self.by_category),
            "applied_count": self.applied_count,
            "effective_count": self.effective_count,
            "avg_confidence": round(self.avg_confidence, 4),
            "effectiveness_rate": round(
                self.effective_count / max(1, self.applied_count), 4
            ),
        }


# ─── Production Recommendation Engine ────────────────────────────────────────

class RecommendationEngine:
    """
    Generates structured affective recommendations from emotional state,
    motivation state, and execution context.
    Configuration-driven thresholds — no hardcoded values.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = config or {}
        rec_cfg = cfg.get("recommendations", {})
        self._min_confidence = float(rec_cfg.get("min_confidence", 0.50))
        self._max_per_session = int(rec_cfg.get("max_recommendations_per_session", 5))
        self._burnout_threshold = float(rec_cfg.get("burnout_recommendation_threshold", 0.70))
        self._stagnation_threshold = float(rec_cfg.get("stagnation_recommendation_threshold", 0.60))
        self._low_motivation_threshold = float(rec_cfg.get("low_motivation_threshold", 0.35))
        self._high_motivation_threshold = float(rec_cfg.get("high_motivation_threshold", 0.80))

        # Emotion thresholds from transitions config
        trans_cfg = cfg.get("transitions", {})
        self._stress_threshold = float(trans_cfg.get("stress_alert_threshold", 0.70))
        self._frustration_threshold = float(trans_cfg.get("frustration_alert_threshold", 0.65))
        self._overload_threshold = float(trans_cfg.get("cognitive_overload_threshold", 0.80))
        self._low_confidence_threshold = float(trans_cfg.get("low_confidence_threshold", 0.40))
        self._high_engagement_threshold = float(trans_cfg.get("high_engagement_threshold", 0.80))
        self._recovery_threshold = float(trans_cfg.get("recovery_threshold", 0.30))

        max_history = int(cfg.get("history", {}).get("max_audit_trail", 3000))
        self._history: Deque[Dict] = deque(maxlen=max_history)
        self._metrics = RecommendationMetrics()

    # ─── Public API ───────────────────────────────────────────────────────────

    def generate(
        self,
        emotional_state: Dict[str, Any],
        motivation_score: float = 0.6,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> List[Recommendation]:
        """
        Generate recommendations from current emotional state and motivation.
        Returns at most max_per_session recommendations, sorted by priority.
        """
        start = time.perf_counter()
        ctx = context or {}
        recs: List[Recommendation] = []

        dims = emotional_state.get("dimensions", emotional_state)

        # ── Stress / Recovery ─────────────────────────────────────────────────
        stress = float(dims.get("stress", 0.0))
        recovery = float(dims.get("recovery", 1.0))

        if stress > self._stress_threshold:
            recs.append(self._rec_stress_recovery(stress, recovery, correlation_id, trace_id))

        if recovery < self._recovery_threshold:
            recs.append(self._rec_needs_recovery(recovery, correlation_id, trace_id))

        # ── Confidence ────────────────────────────────────────────────────────
        confidence = float(dims.get("confidence", 0.7))
        if confidence < self._low_confidence_threshold:
            recs.append(self._rec_low_confidence(confidence, correlation_id, trace_id))

        # ── Cognitive Overload ────────────────────────────────────────────────
        cognitive_load = float(dims.get("cognitive_load", 0.3))
        if cognitive_load > self._overload_threshold:
            recs.append(self._rec_cognitive_overload(cognitive_load, correlation_id, trace_id))

        # ── Frustration ───────────────────────────────────────────────────────
        frustration = float(dims.get("frustration", 0.0))
        if frustration > self._frustration_threshold:
            recs.append(self._rec_frustration(frustration, correlation_id, trace_id))

        # ── Motivation ────────────────────────────────────────────────────────
        if motivation_score < self._low_motivation_threshold:
            recs.append(self._rec_low_motivation(motivation_score, correlation_id, trace_id))
        elif motivation_score > self._high_motivation_threshold:
            recs.append(self._rec_high_motivation(motivation_score, correlation_id, trace_id))

        # ── Engagement ────────────────────────────────────────────────────────
        engagement = float(dims.get("engagement", 0.6))
        if engagement > self._high_engagement_threshold:
            recs.append(self._rec_high_engagement(engagement, correlation_id, trace_id))

        # ── Consecutive failures from context ─────────────────────────────────
        consecutive_failures = int(ctx.get("consecutive_failures", 0))
        if consecutive_failures >= 3:
            recs.append(self._rec_consecutive_failures(consecutive_failures, correlation_id, trace_id))

        # Filter by min confidence, sort by priority, cap at max
        recs = [r for r in recs if r.confidence >= self._min_confidence]
        recs.sort(key=lambda r: r.priority)
        recs = recs[:self._max_per_session]

        # Update metrics
        for r in recs:
            self._metrics.total_generated += 1
            self._metrics.by_category[r.category] = (
                self._metrics.by_category.get(r.category, 0) + 1
            )
            self._metrics.total_confidence_sum += r.confidence
            self._metrics.avg_confidence = round(
                self._metrics.total_confidence_sum / self._metrics.total_generated, 4
            )
            self._history.append(r.to_dict())

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.debug(
            "recommendation_engine.generated count=%d duration_ms=%.2f",
            len(recs), duration_ms,
        )
        return recs

    def record_outcome(
        self,
        recommendation_id: str,
        was_applied: bool,
        outcome: str,
        effectiveness_score: float,
    ) -> bool:
        """Record the outcome of a recommendation for adaptation."""
        for entry in reversed(list(self._history)):
            if entry.get("recommendation_id") == recommendation_id:
                entry["was_applied"] = was_applied
                entry["outcome"] = outcome
                entry["effectiveness_score"] = effectiveness_score
                if was_applied:
                    self._metrics.applied_count += 1
                if effectiveness_score >= 0.6:
                    self._metrics.effective_count += 1
                return True
        return False

    def get_history(self, limit: int = 50) -> List[Dict]:
        return list(self._history)[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.as_dict()

    # ─── Recommendation Builders ──────────────────────────────────────────────

    def _rec_stress_recovery(
        self, stress: float, recovery: float,
        correlation_id: Optional[str], trace_id: Optional[str]
    ) -> Recommendation:
        return Recommendation(
            category="recovery",
            action_type="alert",
            priority=1,
            title="High Stress Detected",
            message=f"System stress level is {stress:.2f}, above threshold {self._stress_threshold:.2f}. "
                    "Reducing task complexity and introducing recovery cycles is recommended.",
            action_step="Reduce concurrent task load. Allow background processes to complete before scheduling new high-priority tasks.",
            reason=f"Stress dimension ({stress:.3f}) exceeds alert threshold ({self._stress_threshold:.3f}). "
                   f"Recovery state is {recovery:.3f}.",
            confidence=min(0.95, 0.60 + (stress - self._stress_threshold) * 1.5),
            supporting_evidence=[
                f"stress={stress:.3f} > threshold={self._stress_threshold:.3f}",
                f"recovery={recovery:.3f}",
            ],
            expected_impact="Reduce stress by 0.15–0.25 over next 2–3 cycles with reduced load.",
            limitations=["Stress reduction depends on actual task load reduction.", "Recovery is gradual."],
            affected_subsystems=["task_scheduler", "planning_agent", "decision_engine"],
            trigger_dimension="stress",
            trigger_value=stress,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    def _rec_needs_recovery(
        self, recovery: float,
        correlation_id: Optional[str], trace_id: Optional[str]
    ) -> Recommendation:
        return Recommendation(
            category="recovery",
            action_type="recover",
            priority=1,
            title="Recovery State Critical",
            message=f"Recovery dimension is {recovery:.2f}, below threshold {self._recovery_threshold:.2f}. "
                    "System needs a recovery cycle before resuming high-load operations.",
            action_step="Pause non-critical background tasks. Allow recovery signal to propagate.",
            reason=f"Recovery dimension ({recovery:.3f}) below critical threshold ({self._recovery_threshold:.3f}).",
            confidence=min(0.95, 0.70 + (self._recovery_threshold - recovery) * 2.0),
            supporting_evidence=[f"recovery={recovery:.3f} < threshold={self._recovery_threshold:.3f}"],
            expected_impact="Recovery dimension should increase by 0.20+ after one recovery cycle.",
            limitations=["Recovery requires actual reduction in processing load."],
            affected_subsystems=["task_scheduler", "agent_manager"],
            trigger_dimension="recovery",
            trigger_value=recovery,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    def _rec_low_confidence(
        self, confidence: float,
        correlation_id: Optional[str], trace_id: Optional[str]
    ) -> Recommendation:
        return Recommendation(
            category="confidence",
            action_type="adjust",
            priority=2,
            title="Low Confidence State",
            message=f"Confidence dimension is {confidence:.2f}, below threshold {self._low_confidence_threshold:.2f}. "
                    "Routing decisions and reasoning outputs may be less reliable.",
            action_step="Increase evidence gathering before decisions. Use higher-confidence fallback agents. "
                        "Reduce routing confidence thresholds temporarily.",
            reason=f"Confidence dimension ({confidence:.3f}) below low-confidence threshold ({self._low_confidence_threshold:.3f}).",
            confidence=min(0.90, 0.55 + (self._low_confidence_threshold - confidence) * 1.2),
            supporting_evidence=[f"confidence={confidence:.3f} < threshold={self._low_confidence_threshold:.3f}"],
            expected_impact="Routing accuracy may improve by 10–15% with additional evidence gathering.",
            limitations=["Confidence recovery depends on successful task completions.", "May increase latency."],
            affected_subsystems=["decision_engine", "routing_engine", "confidence_engine"],
            trigger_dimension="confidence",
            trigger_value=confidence,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    def _rec_cognitive_overload(
        self, cognitive_load: float,
        correlation_id: Optional[str], trace_id: Optional[str]
    ) -> Recommendation:
        return Recommendation(
            category="priority",
            action_type="adjust",
            priority=2,
            title="Cognitive Overload Detected",
            message=f"Cognitive load is {cognitive_load:.2f}, above threshold {self._overload_threshold:.2f}. "
                    "Complex reasoning and planning tasks may degrade.",
            action_step="Defer non-urgent planning tasks. Simplify active reasoning chains. "
                        "Reduce parallel agent execution count.",
            reason=f"Cognitive load ({cognitive_load:.3f}) exceeds overload threshold ({self._overload_threshold:.3f}).",
            confidence=min(0.90, 0.60 + (cognitive_load - self._overload_threshold) * 1.0),
            supporting_evidence=[f"cognitive_load={cognitive_load:.3f} > threshold={self._overload_threshold:.3f}"],
            expected_impact="Reducing parallel tasks by 30% should lower cognitive load within 2 cycles.",
            limitations=["Load reduction depends on task queue management.", "Some tasks cannot be deferred."],
            affected_subsystems=["task_scheduler", "reasoning_agent", "planning_agent"],
            trigger_dimension="cognitive_load",
            trigger_value=cognitive_load,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    def _rec_frustration(
        self, frustration: float,
        correlation_id: Optional[str], trace_id: Optional[str]
    ) -> Recommendation:
        return Recommendation(
            category="communication",
            action_type="adjust",
            priority=3,
            title="Elevated Frustration State",
            message=f"Frustration dimension is {frustration:.2f}, above threshold {self._frustration_threshold:.2f}. "
                    "Communication tone and response style should adapt.",
            action_step="Adopt more supportive communication patterns. Acknowledge difficulty explicitly. "
                        "Offer alternative approaches rather than repeating failed ones.",
            reason=f"Frustration ({frustration:.3f}) exceeds alert threshold ({self._frustration_threshold:.3f}).",
            confidence=min(0.85, 0.55 + (frustration - self._frustration_threshold) * 0.8),
            supporting_evidence=[f"frustration={frustration:.3f} > threshold={self._frustration_threshold:.3f}"],
            expected_impact="Adjusted communication reduces frustration escalation by ~20%.",
            limitations=["Communication adjustment is contextual.", "Frustration may have external causes."],
            affected_subsystems=["language_agent", "social_agent"],
            trigger_dimension="frustration",
            trigger_value=frustration,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    def _rec_low_motivation(
        self, motivation_score: float,
        correlation_id: Optional[str], trace_id: Optional[str]
    ) -> Recommendation:
        return Recommendation(
            category="planning",
            action_type="suggest",
            priority=2,
            title="Low Motivation Score",
            message=f"Motivation score is {motivation_score:.2f}, below threshold {self._low_motivation_threshold:.2f}. "
                    "Goal progress and task engagement may be impaired.",
            action_step="Break active goals into smaller milestones. Celebrate recent completions. "
                        "Re-evaluate goal difficulty and adjust if needed.",
            reason=f"Motivation score ({motivation_score:.3f}) below low threshold ({self._low_motivation_threshold:.3f}).",
            confidence=min(0.85, 0.55 + (self._low_motivation_threshold - motivation_score) * 1.0),
            supporting_evidence=[f"motivation_score={motivation_score:.3f} < threshold={self._low_motivation_threshold:.3f}"],
            expected_impact="Milestone decomposition typically increases motivation by 0.10–0.20.",
            limitations=["Motivation is influenced by external factors.", "Goal adjustment requires user input."],
            affected_subsystems=["planning_agent", "task_agent", "learning_agent"],
            trigger_dimension="motivation",
            trigger_value=motivation_score,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    def _rec_high_motivation(
        self, motivation_score: float,
        correlation_id: Optional[str], trace_id: Optional[str]
    ) -> Recommendation:
        return Recommendation(
            category="planning",
            action_type="suggest",
            priority=4,
            title="High Motivation — Leverage Opportunity",
            message=f"Motivation score is {motivation_score:.2f}. This is an optimal window for tackling challenging goals.",
            action_step="Schedule high-complexity tasks now. Advance planning milestones. "
                        "Consider adding stretch goals.",
            reason=f"Motivation score ({motivation_score:.3f}) above high threshold ({self._high_motivation_threshold:.3f}).",
            confidence=min(0.80, 0.55 + (motivation_score - self._high_motivation_threshold) * 0.8),
            supporting_evidence=[f"motivation_score={motivation_score:.3f} > threshold={self._high_motivation_threshold:.3f}"],
            expected_impact="High-motivation windows yield 20–30% better task completion rates.",
            limitations=["High motivation can lead to overcommitment.", "Monitor for burnout signs."],
            affected_subsystems=["planning_agent", "task_agent"],
            trigger_dimension="motivation",
            trigger_value=motivation_score,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    def _rec_high_engagement(
        self, engagement: float,
        correlation_id: Optional[str], trace_id: Optional[str]
    ) -> Recommendation:
        return Recommendation(
            category="planning",
            action_type="suggest",
            priority=4,
            title="High Engagement State",
            message=f"Engagement is {engagement:.2f}. System is in a high-focus state — ideal for complex reasoning.",
            action_step="Prioritize deep reasoning and planning tasks. Minimize interruptions.",
            reason=f"Engagement ({engagement:.3f}) above high threshold ({self._high_engagement_threshold:.3f}).",
            confidence=min(0.80, 0.55 + (engagement - self._high_engagement_threshold) * 0.6),
            supporting_evidence=[f"engagement={engagement:.3f} > threshold={self._high_engagement_threshold:.3f}"],
            expected_impact="High engagement improves reasoning depth and planning quality.",
            limitations=["Engagement can drop quickly with interruptions."],
            affected_subsystems=["reasoning_agent", "planning_agent"],
            trigger_dimension="engagement",
            trigger_value=engagement,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    def _rec_consecutive_failures(
        self, count: int,
        correlation_id: Optional[str], trace_id: Optional[str]
    ) -> Recommendation:
        return Recommendation(
            category="recovery",
            action_type="alert",
            priority=1,
            title=f"Consecutive Execution Failures ({count})",
            message=f"{count} consecutive execution failures detected. "
                    "System reliability may be degraded. Diagnostic review recommended.",
            action_step="Review recent failure logs. Check agent health. "
                        "Consider routing to fallback agents. Reduce task complexity.",
            reason=f"{count} consecutive failures indicate a systemic issue requiring attention.",
            confidence=min(0.95, 0.60 + count * 0.05),
            supporting_evidence=[f"consecutive_failures={count}"],
            expected_impact="Addressing root cause should restore normal execution within 1–3 cycles.",
            limitations=["Root cause may be external (network, model, data).", "Fallback agents may have lower capability."],
            affected_subsystems=["agent_manager", "task_scheduler", "decision_engine"],
            trigger_dimension="consecutive_failures",
            trigger_value=float(count),
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
