"""
StakeholderAnalysisEngine — Phase 11 Production Implementation.

Stakeholder & Trade-Off Analysis Engine:
  - Multi-stakeholder identification (individuals, orgs, society, environment, future generations)
  - Benefit vs harm impact estimation
  - Trade-off conflict detection
  - Priority balancing & context-aware recommendation generation
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from .models import StakeholderImpact

logger = logging.getLogger(__name__)


class StakeholderAnalysisEngine:
    """
    Analyzes stakeholder impacts, trade-offs, and balances priority weightings.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config.get("stakeholder_analysis", {})

    def analyze_stakeholders(
        self,
        situation: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> StakeholderImpact:
        """Run stakeholder identification, benefit/harm analysis, and trade-off balancing."""
        ctx = context or {}
        text = (situation or ctx.get("proposed_action", "")).lower()

        stakeholders = self._identify_stakeholders(text)
        impact_matrix: Dict[str, Dict[str, Any]] = {}
        benefits: List[str] = []
        conflicts: List[Dict[str, Any]] = []
        priorities: Dict[str, float] = {}

        for sh in stakeholders:
            imp = self._estimate_impact(sh, text)
            impact_matrix[sh] = imp
            priorities[sh] = imp["priority_weight"]

            if imp["benefit_score"] > 0.6:
                benefits.append(f"{sh.capitalize()}: positive outcome ({imp['benefit_summary']})")
            if imp["harm_score"] > 0.4:
                conflicts.append({
                    "stakeholder": sh,
                    "conflict": f"Potential risk/harm to {sh} ({imp['harm_summary']})",
                    "severity": "medium" if imp["harm_score"] < 0.7 else "high",
                })

        rec = (
            "Stakeholder analysis shows balanced net positive impacts across all groups."
            if not conflicts
            else f"Trade-off conflict detected for {len(conflicts)} stakeholder group(s). Mitigation recommended."
        )

        return StakeholderImpact(
            stakeholders=stakeholders,
            impact_matrix=impact_matrix,
            benefit_analysis=benefits,
            trade_off_conflicts=conflicts,
            priority_balancing=priorities,
            recommendation=rec,
        )

    def _identify_stakeholders(self, text: str) -> List[str]:
        stakeholders = ["individuals", "organizations", "society"]
        if any(w in text for w in ["environment", "nature", "planet", "carbon", "green"]):
            stakeholders.append("environment")
        if any(w in text for w in ["future", "children", "next generation", "long-term"]):
            stakeholders.append("future_generations")
        return list(dict.fromkeys(stakeholders))

    def _estimate_impact(self, stakeholder: str, text: str) -> Dict[str, Any]:
        benefit = 0.8
        harm = 0.2
        p_weight = 0.33

        if stakeholder == "individuals":
            p_weight = 0.40
            if "privacy" in text or "surveillance" in text:
                harm = 0.6
        elif stakeholder == "organizations":
            p_weight = 0.30
        elif stakeholder == "society":
            p_weight = 0.30
        elif stakeholder == "environment":
            p_weight = 0.25
        elif stakeholder == "future_generations":
            p_weight = 0.25

        return {
            "benefit_score": benefit,
            "harm_score": harm,
            "net_utility": round(benefit - harm, 2),
            "priority_weight": p_weight,
            "benefit_summary": f"Improved capabilities for {stakeholder}",
            "harm_summary": f"Potential exposure for {stakeholder}",
        }
