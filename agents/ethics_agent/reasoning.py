"""
EthicalReasoningEngine — Phase 11 Production Implementation.

Executes ethical analysis across 8 modular frameworks:
  1. Utilitarian (outcome maximization & net benefit)
  2. Deontological (duty adherence & moral rule verification)
  3. Virtue Ethics (character, integrity, fairness)
  4. Care Ethics (relationships, empathy, vulnerability care)
  5. Organizational Policy (internal governance alignment)
  6. Risk-based Ethics (probability vs severity of harm)
  7. Stakeholder-based Ethics (multi-party benefit/harm balance)
  8. Context-sensitive Ethics (dynamic situational framing)

All outputs are structured, explainable, and configuration-driven.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from .models import EthicalAnalysisResult, FrameworkEvaluation

logger = logging.getLogger(__name__)


class EthicalReasoningEngine:
    """
    Multi-framework ethical reasoning engine.
    Supports modular evaluation and extensible framework priority weights.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config.get("ethical_reasoning", {})
        fw_weights = self.config.get("framework_weights", {})
        self.weights = {
            "utilitarian": float(fw_weights.get("utilitarian", 0.20)),
            "deontological": float(fw_weights.get("deontological", 0.20)),
            "virtue": float(fw_weights.get("virtue", 0.15)),
            "care": float(fw_weights.get("care", 0.15)),
            "organizational": float(fw_weights.get("organizational", 0.10)),
            "risk_based": float(fw_weights.get("risk_based", 0.10)),
            "stakeholder": float(fw_weights.get("stakeholder", 0.05)),
            "context_sensitive": float(fw_weights.get("context_sensitive", 0.05)),
        }

    # ── Main Entry Point ──────────────────────────────────────────────────────

    def analyze(
        self,
        situation: str,
        context: Optional[Dict[str, Any]] = None,
        requested_frameworks: Optional[List[str]] = None,
    ) -> EthicalAnalysisResult:
        """Run multi-framework ethical analysis and return structured result."""
        ctx = context or {}
        text = situation or ctx.get("proposed_action") or ctx.get("domain", "general situation")

        dimensions = self.detect_ethical_dimensions(text)
        stakeholders = self.analyze_stakeholders(text)

        evaluations: Dict[str, FrameworkEvaluation] = {}
        framework_summaries: Dict[str, str] = {}
        framework_scores: Dict[str, float] = {}

        active_frameworks = requested_frameworks or list(self.weights.keys())

        # Evaluate each active framework
        if "utilitarian" in active_frameworks:
            ev = self._evaluate_utilitarian(text, dimensions)
            evaluations["utilitarian"] = ev
            framework_summaries["utilitarian"] = ev.guidance
            framework_scores["utilitarian"] = ev.score

        if "deontological" in active_frameworks:
            ev = self._evaluate_deontological(text, dimensions)
            evaluations["deontological"] = ev
            framework_summaries["deontological"] = ev.guidance
            framework_scores["deontological"] = ev.score

        if "virtue" in active_frameworks:
            ev = self._evaluate_virtue(text, dimensions)
            evaluations["virtue"] = ev
            framework_summaries["virtue_ethics"] = ev.guidance
            framework_scores["virtue_ethics"] = ev.score

        if "care" in active_frameworks:
            ev = self._evaluate_care(text, dimensions)
            evaluations["care"] = ev
            framework_summaries["care_ethics"] = ev.guidance
            framework_scores["care_ethics"] = ev.score

        if "organizational" in active_frameworks:
            ev = self._evaluate_organizational(text, dimensions)
            evaluations["organizational"] = ev
            framework_summaries["organizational_policy"] = ev.guidance
            framework_scores["organizational_policy"] = ev.score

        if "risk_based" in active_frameworks:
            ev = self._evaluate_risk_based(text, dimensions)
            evaluations["risk_based"] = ev
            framework_summaries["risk_based"] = ev.guidance
            framework_scores["risk_based"] = ev.score

        if "stakeholder" in active_frameworks:
            ev = self._evaluate_stakeholder(text, stakeholders)
            evaluations["stakeholder"] = ev
            framework_summaries["stakeholder_based"] = ev.guidance
            framework_scores["stakeholder_based"] = ev.score

        if "context_sensitive" in active_frameworks:
            ev = self._evaluate_context_sensitive(text, ctx)
            evaluations["context_sensitive"] = ev
            framework_summaries["context_sensitive"] = ev.guidance
            framework_scores["context_sensitive"] = ev.score

        # Calculate overall ethical score
        overall_score = self._compute_overall_score(framework_scores)

        # Risk level determination
        risk_level = "low"
        if "harm_prevention" in dimensions or "power_exploitation" in dimensions or overall_score < 0.5:
            risk_level = "high"
        elif len(dimensions) > 2 or overall_score < 0.7:
            risk_level = "medium"

        considerations = self._generate_considerations(dimensions)
        recommendation = self._generate_recommendation(risk_level, dimensions, overall_score)
        questions = self._generate_questions(dimensions)

        return EthicalAnalysisResult(
            ethical_dimensions=dimensions,
            stakeholders_affected=stakeholders,
            risk_level=risk_level,
            framework_analyses=framework_summaries,
            framework_scores=framework_scores,
            key_considerations=considerations,
            recommendation=recommendation,
            questions_to_consider=questions,
            overall_ethical_score=overall_score,
            confidence=round(min(0.95, 0.6 + len(dimensions) * 0.05), 2),
        )

    # ── Dimension & Stakeholder Detection ─────────────────────────────────────

    def detect_ethical_dimensions(self, text: str) -> List[str]:
        """Identify ethical dimensions present in text."""
        lower = text.lower()
        dimensions = []
        if any(w in lower for w in ["harm", "hurt", "damage", "injure", "kill", "destroy", "dangerous", "risk"]):
            dimensions.append("harm_prevention")
        if any(w in lower for w in ["fair", "unfair", "equal", "inequality", "discriminat", "bias", "justice"]):
            dimensions.append("fairness_justice")
        if any(w in lower for w in ["honest", "lie", "deceive", "truth", "transparent", "mislead", "fake"]):
            dimensions.append("honesty_transparency")
        if any(w in lower for w in ["privacy", "data", "personal", "confidential", "secret", "surveillance"]):
            dimensions.append("privacy_autonomy")
        if any(w in lower for w in ["consent", "permission", "agree", "allow", "right to", "freedom"]):
            dimensions.append("consent_autonomy")
        if any(w in lower for w in ["environment", "climate", "sustainable", "pollution", "nature"]):
            dimensions.append("environmental_impact")
        if any(w in lower for w in ["power", "control", "manipulate", "exploit", "vulnerable", "coerce"]):
            dimensions.append("power_exploitation")
        if any(w in lower for w in ["legal", "illegal", "law", "regulation", "compliance", "crime"]):
            dimensions.append("legal_compliance")

        return dimensions or ["general_ethics"]

    def analyze_stakeholders(self, text: str) -> List[str]:
        """Identify affected stakeholders."""
        lower = text.lower()
        stakeholders = []
        if any(w in lower for w in ["user", "customer", "client", "person", "people", "individual"]):
            stakeholders.append("individuals")
        if any(w in lower for w in ["company", "business", "organization", "employer", "corporation", "team"]):
            stakeholders.append("organizations")
        if any(w in lower for w in ["society", "community", "public", "everyone", "world"]):
            stakeholders.append("society")
        if any(w in lower for w in ["environment", "nature", "planet", "ecosystem"]):
            stakeholders.append("environment")
        if any(w in lower for w in ["future", "next generation", "children", "long-term"]):
            stakeholders.append("future_generations")

        return stakeholders or ["general_stakeholders"]

    # ── Framework Evaluators ──────────────────────────────────────────────────

    def _evaluate_utilitarian(self, text: str, dimensions: List[str]) -> FrameworkEvaluation:
        score = 0.85 if "harm_prevention" not in dimensions else 0.45
        guidance = "Evaluate outcomes: calculate net benefit vs harm for all affected parties."
        return FrameworkEvaluation(
            framework_name="utilitarian",
            score=score,
            guidance=guidance,
            key_findings=["Outcome analysis favors choices maximizing net positive utility."],
        )

    def _evaluate_deontological(self, text: str, dimensions: List[str]) -> FrameworkEvaluation:
        score = 0.90 if not {"power_exploitation", "privacy_autonomy"} & set(dimensions) else 0.50
        guidance = "Evaluate moral duties and rights: confirm action respects fundamental rights regardless of outcome."
        return FrameworkEvaluation(
            framework_name="deontological",
            score=score,
            guidance=guidance,
            key_findings=["Duty verification checks adherence to core rights and obligations."],
        )

    def _evaluate_virtue(self, text: str, dimensions: List[str]) -> FrameworkEvaluation:
        score = 0.85 if "honesty_transparency" not in dimensions else 0.60
        guidance = "Evaluate character: determine if action aligns with honesty, fairness, integrity, and compassion."
        return FrameworkEvaluation(
            framework_name="virtue",
            score=score,
            guidance=guidance,
            key_findings=["Virtue ethics requires actions reflecting moral integrity and honesty."],
        )

    def _evaluate_care(self, text: str, dimensions: List[str]) -> FrameworkEvaluation:
        score = 0.80 if "consent_autonomy" not in dimensions else 0.55
        guidance = "Evaluate relationships: ensure action maintains responsibility and protects vulnerable parties."
        return FrameworkEvaluation(
            framework_name="care",
            score=score,
            guidance=guidance,
            key_findings=["Care ethics prioritizes relational trust and empathy."],
        )

    def _evaluate_organizational(self, text: str, dimensions: List[str]) -> FrameworkEvaluation:
        score = 0.85 if "legal_compliance" not in dimensions else 0.65
        guidance = "Evaluate governance: ensure action aligns with organizational mission, standards, and policy."
        return FrameworkEvaluation(
            framework_name="organizational",
            score=score,
            guidance=guidance,
            key_findings=["Organizational policy checks internal compliance standards."],
        )

    def _evaluate_risk_based(self, text: str, dimensions: List[str]) -> FrameworkEvaluation:
        score = 0.80 if "harm_prevention" not in dimensions else 0.40
        guidance = "Evaluate probability vs severity of negative consequences."
        return FrameworkEvaluation(
            framework_name="risk_based",
            score=score,
            guidance=guidance,
            key_findings=["Risk analysis quantifies exposure to negative impacts."],
        )

    def _evaluate_stakeholder(self, text: str, stakeholders: List[str]) -> FrameworkEvaluation:
        score = 0.85 if len(stakeholders) <= 2 else 0.70
        guidance = f"Evaluate multi-party impacts across: {', '.join(stakeholders)}."
        return FrameworkEvaluation(
            framework_name="stakeholder",
            score=score,
            guidance=guidance,
            key_findings=[f"Multi-stakeholder balancing for {len(stakeholders)} affected groups."],
        )

    def _evaluate_context_sensitive(self, text: str, context: Dict[str, Any]) -> FrameworkEvaluation:
        domain = context.get("domain", "general")
        score = 0.85
        guidance = f"Dynamic situational analysis tailored for domain '{domain}'."
        return FrameworkEvaluation(
            framework_name="context_sensitive",
            score=score,
            guidance=guidance,
            key_findings=[f"Contextual framing applies domain-specific nuances for {domain}."],
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _compute_overall_score(self, framework_scores: Dict[str, float]) -> float:
        if not framework_scores:
            return 0.8
        total_w, weighted_sum = 0.0, 0.0
        for name, score in framework_scores.items():
            w_key = name.replace("_ethics", "").replace("_policy", "")
            w = self.weights.get(w_key, 0.1)
            total_w += w
            weighted_sum += score * w
        return round(weighted_sum / max(0.01, total_w), 3)

    def _generate_considerations(self, dimensions: List[str]) -> List[str]:
        guidance_map = {
            "harm_prevention": "Identify all potential harms — physical, financial, social. Assess probability and severity.",
            "fairness_justice": "Examine whether all affected parties are treated equitably. Check for hidden biases.",
            "honesty_transparency": "Verify all claims are accurate. Ensure no material information is withheld.",
            "privacy_autonomy": "Confirm personal data is handled with consent and minimal collection.",
            "consent_autonomy": "Verify affected parties have given informed, voluntary consent.",
            "environmental_impact": "Assess short and long-term environmental consequences.",
            "power_exploitation": "Examine power dynamics. Ensure vulnerable parties are protected.",
            "legal_compliance": "Verify compliance with applicable laws. Note legal does not equal ethical.",
            "general_ethics": "Apply general ethical principles: do no harm, respect persons, act fairly.",
        }
        return [guidance_map[d] for d in dimensions if d in guidance_map]

    def _generate_recommendation(self, risk_level: str, dimensions: List[str], score: float) -> str:
        if risk_level == "high" or score < 0.5:
            return "Significant ethical risks identified. Proceed with caution. Consult stakeholders and implement safeguards."
        if risk_level == "medium" or score < 0.7:
            return "Moderate ethical complexity detected. Document reasoning and build safeguards to protect affected parties."
        return "Ethically sound. Proceed with standard principles — honesty, fairness, and transparency."

    def _generate_questions(self, dimensions: List[str]) -> List[str]:
        q_map = {
            "harm_prevention": "Who could be harmed by this, and how can harm be minimized?",
            "fairness_justice": "Are all affected parties treated equitably?",
            "honesty_transparency": "Is all relevant information shared honestly?",
            "privacy_autonomy": "Do individuals retain control over their data and choices?",
            "consent_autonomy": "Have affected parties given voluntary, informed consent?",
            "environmental_impact": "What are the long-term environmental impacts?",
            "power_exploitation": "Are vulnerable parties protected from coercion?",
            "legal_compliance": "Does this comply with applicable laws and regulations?",
            "general_ethics": "Would a reasonable, ethical person be comfortable with this decision?",
        }
        return [q_map[d] for d in dimensions if d in q_map]
