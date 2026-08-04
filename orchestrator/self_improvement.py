"""
Phase 14 — Continuous Self-Improvement Engine.

Performs runtime performance analysis, profiling, bottleneck detection,
confidence calibration, heuristic refinement, and recommendation generation.

Strict Constraint: Generates recommendations and tunes dynamic runtime parameters
without modifying codebase source files automatically.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from orchestrator.cognitive_models import OptimizationRecommendation, OptimizationAction

logger = logging.getLogger(__name__)


class ContinuousSelfImprovementEngine:
    """
    Continuous Self-Improvement engine. Safe, non-mutating to source code.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        imp_cfg = cfg.get("self_improvement", {})

        self._enabled: bool = bool(imp_cfg.get("enabled", True))
        self._min_confidence_threshold: float = float(imp_cfg.get("min_confidence_threshold", 0.60))
        self._calibration_factor: float = 1.0

        self._historical_recommendations: List[OptimizationRecommendation] = []
        self._improvement_logs: List[Dict[str, Any]] = []

    def analyze_performance_trends(
        self,
        analytics_history: List[Dict[str, Any]],
        monitoring_reports: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze trends over historical analytics and monitoring reports."""
        if not analytics_history:
            return {
                "trend_status": "insufficient_data",
                "confidence_calibration": self._calibration_factor,
                "recommendations": [],
            }

        recent = analytics_history[-10:]
        latencies = [a.get("avg_latency_ms", 0.0) for a in recent if "avg_latency_ms" in a]
        error_rates = [a.get("failure_rate", 0.0) for a in recent if "failure_rate" in a]

        avg_lat = sum(latencies) / max(1, len(latencies))
        avg_err = sum(error_rates) / max(1, len(error_rates))

        # Calibrate confidence based on recent error rate
        if avg_err > 0.10:
            self._calibration_factor = max(0.5, self._calibration_factor * 0.95)
        elif avg_err < 0.02:
            self._calibration_factor = min(1.2, self._calibration_factor * 1.02)

        recs: List[OptimizationRecommendation] = []

        if avg_lat > 1500.0:
            rec = OptimizationRecommendation(
                action=OptimizationAction.ADJUST_PRIORITY,
                target="execution_pipeline",
                reason=f"Historical latency trend ({avg_lat:.1f}ms) indicates bottleneck",
                expected_improvement="Improve response time via task prioritization",
                confidence=round(0.80 * self._calibration_factor, 2),
                priority=3,
            )
            recs.append(rec)
            self._historical_recommendations.append(rec)

        if avg_err > 0.05:
            rec = OptimizationRecommendation(
                action=OptimizationAction.FLUSH_QUEUE,
                target="message_broker",
                reason=f"Elevated failure trend ({avg_err:.2%}) indicates queue congestion or stale tasks",
                expected_improvement="Clear stale queues to reduce cascading failures",
                confidence=round(0.85 * self._calibration_factor, 2),
                priority=3,
            )
            recs.append(rec)
            self._historical_recommendations.append(rec)

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "avg_latency": round(avg_lat, 2),
            "avg_error_rate": round(avg_err, 4),
            "calibration_factor": round(self._calibration_factor, 2),
            "recommendation_count": len(recs),
        }
        self._improvement_logs.append(log_entry)

        return {
            "trend_status": "degraded" if (avg_lat > 1500 or avg_err > 0.05) else "optimal",
            "avg_latency_ms": round(avg_lat, 2),
            "avg_error_rate": round(avg_err, 4),
            "confidence_calibration": round(self._calibration_factor, 2),
            "recommendations": [r.to_dict() for r in recs],
        }

    def calibrate_confidence(self, base_confidence: float) -> float:
        """Apply dynamic calibration factor to a raw confidence score."""
        calibrated = base_confidence * self._calibration_factor
        return round(max(0.0, min(1.0, calibrated)), 4)

    def get_improvement_summary(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "confidence_calibration_factor": round(self._calibration_factor, 2),
            "total_recommendations_generated": len(self._historical_recommendations),
            "analysis_cycles": len(self._improvement_logs),
            "latest_log": self._improvement_logs[-1] if self._improvement_logs else None,
        }
