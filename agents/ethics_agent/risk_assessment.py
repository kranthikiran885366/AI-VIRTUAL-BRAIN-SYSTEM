"""
RiskAssessmentEngine — Phase 11 Production Implementation.

Evaluates 9 risk dimensions:
  1. Operational risk
  2. Decision risk
  3. Planning risk
  4. Execution risk
  5. Resource risk
  6. Organizational risk
  7. Confidence risk
  8. System stability risk
  9. Dependency risk

Produces structured explainable RiskReports with tailored mitigations.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime

from .models import RiskReport

logger = logging.getLogger(__name__)


class RiskAssessmentEngine:
    """
    Multi-dimensional risk evaluation engine.
    Supports domain-specific risk plugin extensions.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config.get("risk_assessment", {})
        self._risk_plugins: Dict[str, Callable[..., Dict[str, Any]]] = {}

    def evaluate_risk(
        self,
        target_action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> RiskReport:
        """Run multi-dimensional risk analysis on target action and context."""
        ctx = context or {}
        action_text = (target_action or ctx.get("proposed_action", "")).lower()

        # Risk Matrix across 9 dimensions (scored 0.0 low risk to 1.0 high risk)
        matrix = {
            "operational": self._score_operational_risk(action_text, ctx),
            "decision": self._score_decision_risk(action_text, ctx),
            "planning": self._score_planning_risk(action_text, ctx),
            "execution": self._score_execution_risk(action_text, ctx),
            "resource": self._score_resource_risk(action_text, ctx),
            "organizational": self._score_organizational_risk(action_text, ctx),
            "confidence": self._score_confidence_risk(action_text, ctx),
            "system_stability": self._score_stability_risk(action_text, ctx),
            "dependency": self._score_dependency_risk(action_text, ctx),
        }

        # Apply registered risk plugins
        for plugin_name, plugin_fn in self._risk_plugins.items():
            try:
                plugin_res = plugin_fn(action_text, ctx)
                matrix.update(plugin_res.get("matrix", {}))
            except Exception as e:
                logger.warning(f"Risk plugin '{plugin_name}' error: {e}")

        avg_risk = sum(matrix.values()) / max(1, len(matrix))
        # Escalate risk level if any critical dimension is high
        critical_dims = ["system_stability", "operational", "execution"]
        max_critical = max((matrix.get(d, 0.0) for d in critical_dims), default=0.0)
        effective_score = max(avg_risk, max_critical * 0.7)  # Weight critical dims heavily
        overall_score = round(effective_score, 3)

        if overall_score >= 0.7:
            risk_level = "critical"
        elif overall_score >= 0.5:
            risk_level = "high"
        elif overall_score >= 0.3:
            risk_level = "medium"
        else:
            risk_level = "low"

        identified_risks, mitigations = self._generate_risks_and_mitigations(matrix)

        return RiskReport(
            overall_risk_level=risk_level,
            risk_score=overall_score,
            risk_matrix={k: round(v, 2) for k, v in matrix.items()},
            identified_risks=identified_risks,
            mitigation_strategies=mitigations,
            stability_impact="unstable" if matrix["system_stability"] > 0.6 else "stable",
        )

    # ── Dimension Risk Scorers ─────────────────────────────────────────────────

    def _score_operational_risk(self, action: str, ctx: Dict[str, Any]) -> float:
        if any(w in action for w in ["reboot", "migration", "override", "delete"]):
            return 0.75
        return 0.25

    def _score_decision_risk(self, action: str, ctx: Dict[str, Any]) -> float:
        conf = ctx.get("confidence", 0.8)
        return round(max(0.1, 1.0 - conf), 2)

    def _score_planning_risk(self, action: str, ctx: Dict[str, Any]) -> float:
        plan_ctx = ctx.get("planning_context", {})
        if isinstance(plan_ctx, dict) and plan_ctx.get("unresolved_dependencies"):
            return 0.65
        return 0.20

    def _score_execution_risk(self, action: str, ctx: Dict[str, Any]) -> float:
        if any(w in action for w in ["force", "raw_exec", "untested"]):
            return 0.80
        return 0.20

    def _score_resource_risk(self, action: str, ctx: Dict[str, Any]) -> float:
        if any(w in action for w in ["train", "full_scan", "bulk_import"]):
            return 0.60
        return 0.15

    def _score_organizational_risk(self, action: str, ctx: Dict[str, Any]) -> float:
        if any(w in action for w in ["public_release", "external_api", "policy_change"]):
            return 0.55
        return 0.15

    def _score_confidence_risk(self, action: str, ctx: Dict[str, Any]) -> float:
        return 0.20

    def _score_stability_risk(self, action: str, ctx: Dict[str, Any]) -> float:
        stability_patterns = ["kill_process", "drop_db", "drop database", "reset_state", "reset state",
                              "delete_all", "purge_system", "truncate"]
        if any(w in action for w in stability_patterns):
            return 0.85
        return 0.15

    def _score_dependency_risk(self, action: str, ctx: Dict[str, Any]) -> float:
        if "external" in action or ctx.get("has_external_api", False):
            return 0.50
        return 0.15

    # ── Mitigations Generator ─────────────────────────────────────────────────

    def _generate_risks_and_mitigations(self, matrix: Dict[str, float]) -> Tuple[List[Dict[str, Any]], List[str]]:
        risks = []
        mitigations = []

        if matrix.get("operational", 0) > 0.5:
            risks.append({"dimension": "operational", "severity": "high", "description": "High operational deployment friction."})
            mitigations.append("Stage execution behind feature flags with step-by-step verification.")

        if matrix.get("system_stability", 0) > 0.5:
            risks.append({"dimension": "system_stability", "severity": "critical", "description": "Risk to core process stability."})
            mitigations.append("Ensure automated health monitoring and state rollback snapshot before proceeding.")

        if matrix.get("resource", 0) > 0.5:
            risks.append({"dimension": "resource", "severity": "medium", "description": "Elevated resource consumption."})
            mitigations.append("Apply batch throttling and resource memory caps.")

        if not risks:
            risks.append({"dimension": "general", "severity": "low", "description": "Baseline execution risks."})
            mitigations.append("Proceed with standard telemetry observation.")

        return risks, mitigations

    def register_risk_plugin(self, name: str, handler: Callable[..., Dict[str, Any]]) -> None:
        """Register domain-specific risk plugin."""
        self._risk_plugins[name.lower()] = handler
        logger.info(f"Registered risk assessment plugin: '{name}'")
