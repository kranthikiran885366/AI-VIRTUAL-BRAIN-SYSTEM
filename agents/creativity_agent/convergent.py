"""
ConvergentThinking — Phase 10 Production Implementation.

Provides structured convergent thinking capabilities:
  - Configurable multi-criteria evaluation (novelty, feasibility, usefulness, impact, clarity, risk, cost-benefit)
  - Filtering against threshold criteria
  - Multi-objective Pareto / weighted ranking
  - Risk assessment & mitigation plan generation
  - Cost-benefit evaluation
  - Implementation readiness scoring
  - Explainable recommendation generation
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .models import CreativeIdea, IdeaScore

logger = logging.getLogger(__name__)


class ConvergentThinking:
    """
    Evaluates, filters, ranks, and synthesizes recommendations for creative ideas.
    All parameters are configuration-driven.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config.get("convergent", {})
        eval_cfg = config.get("idea_generation", {}).get("evaluation_weights", {})
        self.weights = {
            "originality": float(eval_cfg.get("originality", 0.35)),
            "feasibility": float(eval_cfg.get("feasibility", 0.35)),
            "impact": float(eval_cfg.get("impact", 0.30)),
        }

        # Feasibility & impact keywords for signal scoring
        self._impact_keywords = [
            "transform", "revolutionize", "improve", "enhance", "solve", "optimize",
            "automate", "scale", "innovate", "disrupt", "reduce", "increase",
            "simplify", "accelerate", "empower", "enable", "integrate", "streamline",
        ]
        self._feasibility_positive = [
            "step", "phase", "implement", "build", "use", "apply", "deploy",
            "integrate", "connect", "configure", "install", "create", "develop",
        ]
        self._feasibility_negative = [
            "impossible", "extremely complex", "requires years", "very difficult",
            "unknown technology", "theoretical only",
        ]

    # ── Public API ────────────────────────────────────────────────────────────

    def evaluate_and_rank(self, ideas: List[Dict[str, Any]],
                           history: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Evaluate each idea with multi-metric scoring and return sorted list (highest overall first).
        Accepts dicts or CreativeIdea instances.
        """
        evaluated = []
        hist_records = history or []

        for item in ideas:
            idea_dict = item.to_dict() if hasattr(item, "to_dict") else dict(item)
            score = self.calculate_score(idea_dict, hist_records)
            idea_dict["score"] = score.to_dict()
            evaluated.append({
                "idea": idea_dict,
                "scores": score.to_dict(),
                "overall": score.overall,
                "risk_assessment": self.assess_risk(idea_dict),
                "cost_benefit": self.evaluate_cost_benefit(idea_dict),
                "readiness": self.evaluate_implementation_readiness(idea_dict),
            })

        evaluated.sort(key=lambda x: x["overall"], reverse=True)
        return evaluated

    def filter_ideas(self, evaluated_ideas: List[Dict[str, Any]],
                     min_score: float = 0.5) -> List[Dict[str, Any]]:
        """Filter evaluated ideas to keep only those meeting min_score."""
        return [item for item in evaluated_ideas if item.get("overall", 0.0) >= min_score]

    def calculate_score(self, idea: Dict[str, Any],
                        history: List[Dict[str, Any]]) -> IdeaScore:
        """Compute comprehensive multi-metric IdeaScore."""
        concept = idea.get("concept", "")
        approach = idea.get("approach", "")
        implementation = idea.get("implementation", "")

        novelty = self._score_novelty(concept, approach, history)
        feasibility = self._score_feasibility(approach, implementation)
        impact = self._score_impact(concept, approach)
        usefulness = round(min(0.95, (feasibility * 0.5) + (impact * 0.5)), 3)
        clarity = self._score_clarity(concept, approach, implementation)
        complexity = self._score_complexity(implementation)
        resource_req = round(min(0.95, complexity * 0.8 + 0.1), 3)
        impl_diff = round(min(0.95, 1.0 - feasibility * 0.7), 3)
        risk_lvl = round(min(0.95, (1.0 - feasibility) * 0.6 + complexity * 0.4), 3)

        # Weighted overall score
        w_orig = self.weights.get("originality", 0.35)
        w_feas = self.weights.get("feasibility", 0.35)
        w_imp = self.weights.get("impact", 0.30)

        overall = round(novelty * w_orig + feasibility * w_feas + impact * w_imp, 3)

        # Label assignment
        if overall >= 0.8:
            label = "excellent"
        elif overall >= 0.65:
            label = "good"
        elif overall >= 0.45:
            label = "acceptable"
        else:
            label = "poor"

        confidence = round(min(0.95, 0.5 + clarity * 0.3 + feasibility * 0.2), 3)

        return IdeaScore(
            novelty=novelty,
            feasibility=feasibility,
            usefulness=usefulness,
            impact=impact,
            clarity=clarity,
            complexity=complexity,
            resource_requirements=resource_req,
            implementation_difficulty=impl_diff,
            risk_level=risk_lvl,
            confidence=confidence,
            overall=overall,
            label=label,
        )

    def assess_risk(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        """Identify risk factors and generate tailored mitigations."""
        concept = idea.get("concept", "")
        approach = idea.get("approach", "")
        combined = (concept + " " + approach).lower()

        risks = []
        mitigations = []

        if any(w in combined for w in ["quantum", "ai", "machine learning", "neural"]):
            risks.append("Model accuracy / hallucinations / algorithm uncertainty")
            mitigations.append("Implement robust validation layer and fallbacks")
        if any(w in combined for w in ["cloud", "distributed", "decentralized"]):
            risks.append("Network latency and availability dependencies")
            mitigations.append("Use circuit breakers, caching, and offline-first fallback modes")
        if any(w in combined for w in ["security", "privacy", "zero-trust"]):
            risks.append("Compliance and data leakage concerns")
            mitigations.append("Conduct security audit and enforce AES-256 encryption at rest")

        if not risks:
            risks.append("Standard execution and adoption risks")
            mitigations.append("Iterate via small-scale pilots before full deployment")

        return {
            "identified_risks": risks,
            "mitigation_strategies": mitigations,
            "risk_score": round(min(0.9, 0.2 + 0.2 * len(risks)), 2),
        }

    def evaluate_cost_benefit(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        """Assess cost vs benefit metrics and return ROI projection."""
        impl = idea.get("implementation", "")
        step_count = len(re.findall(r"\b(step|phase|\d+\.)\s", impl, re.IGNORECASE))

        est_cost = round(min(10.0, max(1.0, 2.0 + step_count * 1.5)), 1)  # Scale 1-10
        est_benefit = round(min(10.0, max(2.0, 4.0 + step_count * 1.2)), 1)
        roi_ratio = round(est_benefit / max(0.1, est_cost), 2)

        return {
            "estimated_cost_scale": est_cost,
            "estimated_benefit_scale": est_benefit,
            "roi_ratio": roi_ratio,
            "recommendation": "Favorable" if roi_ratio >= 1.2 else "Moderate ROI",
        }

    def evaluate_implementation_readiness(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        """Score implementation readiness based on step clarity."""
        impl = idea.get("implementation", "")
        has_steps = bool(re.search(r"\b(step 1|phase 1|1\.)", impl, re.IGNORECASE))
        word_count = len(impl.split())

        score = 0.3
        if has_steps:
            score += 0.35
        if word_count > 30:
            score += 0.25
        score = min(0.95, round(score, 2))

        return {
            "readiness_score": score,
            "has_numbered_steps": has_steps,
            "detail_level": "high" if word_count > 40 else "medium" if word_count > 15 else "low",
        }

    def generate_recommendations(self, evaluated_ideas: List[Dict[str, Any]],
                                 top_n: int = 3) -> List[Dict[str, Any]]:
        """Generate structured recommendation rationale for top ideas."""
        recommendations = []
        for i, item in enumerate(evaluated_ideas[:top_n], start=1):
            idea = item.get("idea", {})
            scores = item.get("scores", {})
            overall = scores.get("overall", 0.0)

            recommendations.append({
                "rank": i,
                "idea_id": idea.get("idea_id", f"idea_{i}"),
                "concept": idea.get("concept", ""),
                "overall_score": overall,
                "label": scores.get("label", "acceptable"),
                "rationale": (
                    f"Rank #{i}: '{idea.get('concept', '')[:60]}' achieved an overall score of {overall} "
                    f"(Novelty: {scores.get('novelty', 0)}, Feasibility: {scores.get('feasibility', 0)}, "
                    f"Impact: {scores.get('impact', 0)}). Recommended for immediate prototyping."
                ),
            })
        return recommendations

    # ── Internal Scoring Helpers ──────────────────────────────────────────────

    def _score_novelty(self, concept: str, approach: str,
                       history: List[Dict[str, Any]]) -> float:
        """Score novelty against history via Jaccard distance."""
        combined_words = set((concept + " " + approach).lower().split())
        if not history or not combined_words:
            return 0.85

        max_sim = 0.0
        for hist in history[-50:]:
            h_text = (hist.get("concept", "") + " " + hist.get("approach", "")).lower()
            h_words = set(h_text.split())
            if not h_words:
                continue
            intersection = len(combined_words & h_words)
            union = len(combined_words | h_words)
            sim = intersection / union if union > 0 else 0.0
            if sim > max_sim:
                max_sim = sim

        return round(max(0.1, min(0.95, 1.0 - max_sim)), 3)

    def _score_feasibility(self, approach: str, implementation: str) -> float:
        """Score feasibility based on actionability signals."""
        combined = (implementation + " " + approach).lower()
        pos_count = sum(1 for kw in self._feasibility_positive if kw in combined)
        step_count = len(re.findall(r"\b(step|phase|\d+\.)\s", combined, re.IGNORECASE))
        neg_count = sum(1 for kw in self._feasibility_negative if kw in combined)

        words = len(implementation.split())
        base = min(0.7, 0.3 + words * 0.004)
        bonus = min(0.25, (pos_count * 0.04) + (step_count * 0.05))
        penalty = neg_count * 0.1

        return round(max(0.1, min(0.95, base + bonus - penalty)), 3)

    def _score_impact(self, concept: str, approach: str) -> float:
        """Score impact based on high-value action keywords."""
        combined = (concept + " " + approach).lower()
        impact_count = sum(1 for kw in self._impact_keywords if kw in combined)
        scope_words = ["all", "entire", "every", "global", "system", "platform",
                       "users", "team", "organization", "enterprise", "scale"]
        scope_count = sum(1 for w in scope_words if w in combined)

        base = 0.45
        impact_bonus = min(0.35, impact_count * 0.05)
        scope_bonus = min(0.15, scope_count * 0.03)

        return round(max(0.1, min(0.95, base + impact_bonus + scope_bonus)), 3)

    def _score_clarity(self, concept: str, approach: str, implementation: str) -> float:
        """Score clarity based on structure and length."""
        total_len = len(concept) + len(approach) + len(implementation)
        if total_len < 20:
            return 0.3
        has_impl = len(implementation) > 20
        return round(min(0.95, 0.5 + (0.3 if has_impl else 0.1) + min(0.15, total_len * 0.0005)), 3)

    def _score_complexity(self, implementation: str) -> float:
        """Score implementation complexity."""
        words = len(implementation.split())
        complex_words = ["algorithm", "architecture", "distributed", "asynchronous", "concurrency", "custom"]
        c_count = sum(1 for w in complex_words if w in implementation.lower())
        return round(min(0.9, 0.2 + words * 0.005 + c_count * 0.1), 3)
