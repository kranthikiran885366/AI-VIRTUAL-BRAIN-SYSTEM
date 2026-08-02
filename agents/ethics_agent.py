import asyncio
import logging
from typing import Dict, List, Any
from datetime import datetime

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class EthicsAgent(BaseAgent):
    def __init__(self, agent_id: str = "ethics_agent"):
        super().__init__(agent_id, "ethics")
        self.analysis_history: List[Dict] = []

    async def initialize(self):
        await super().initialize()
        self.state.update({"analyses_performed": 0})
        logger.info(f"Ethics agent {self.agent_id} initialized")

    async def _update_state(self):
        self.state.update({
            "analyses_performed": len(self.analysis_history),
            "last_active": datetime.utcnow().isoformat(),
        })

    def _detect_ethical_dimensions(self, text: str) -> List[str]:
        lower = text.lower()
        dimensions = []
        if any(w in lower for w in ["harm", "hurt", "damage", "injure", "kill", "destroy", "dangerous"]): dimensions.append("harm_prevention")
        if any(w in lower for w in ["fair", "unfair", "equal", "inequality", "discriminat", "bias", "justice"]): dimensions.append("fairness_justice")
        if any(w in lower for w in ["honest", "lie", "deceive", "truth", "transparent", "mislead", "fake"]): dimensions.append("honesty_transparency")
        if any(w in lower for w in ["privacy", "data", "personal", "confidential", "secret", "surveillance"]): dimensions.append("privacy_autonomy")
        if any(w in lower for w in ["consent", "permission", "agree", "allow", "right to", "freedom"]): dimensions.append("consent_autonomy")
        if any(w in lower for w in ["environment", "climate", "sustainable", "pollution", "nature", "future generation"]): dimensions.append("environmental_impact")
        if any(w in lower for w in ["power", "control", "manipulate", "exploit", "vulnerable", "coerce"]): dimensions.append("power_exploitation")
        if any(w in lower for w in ["legal", "illegal", "law", "regulation", "compliance", "crime"]): dimensions.append("legal_compliance")
        return dimensions or ["general_ethics"]

    def _analyze_stakeholders(self, text: str) -> List[str]:
        lower = text.lower()
        stakeholders = []
        if any(w in lower for w in ["user", "customer", "client", "person", "people", "individual"]): stakeholders.append("individuals")
        if any(w in lower for w in ["company", "business", "organization", "employer", "corporation"]): stakeholders.append("organizations")
        if any(w in lower for w in ["society", "community", "public", "everyone", "world"]): stakeholders.append("society")
        if any(w in lower for w in ["environment", "nature", "planet", "ecosystem"]): stakeholders.append("environment")
        if any(w in lower for w in ["future", "next generation", "children", "long-term"]): stakeholders.append("future_generations")
        return stakeholders or ["general_stakeholders"]

    def _generate_ethical_analysis(self, text: str, dimensions: List[str], stakeholders: List[str]) -> Dict:
        frameworks = {
            "utilitarian": "Evaluate based on outcomes: does this action produce the greatest good for the greatest number of people?",
            "deontological": "Evaluate based on duties and rules: are there moral rules or rights that this action respects or violates, regardless of outcomes?",
            "virtue_ethics": "Evaluate based on character: would a person of good character — honest, fair, compassionate — take this action?",
            "care_ethics": "Evaluate based on relationships: does this action maintain and strengthen relationships of care and responsibility?",
        }

        dimension_guidance = {
            "harm_prevention": "Identify all potential harms — physical, psychological, financial, social. Assess probability and severity. Explore alternatives that achieve the goal with less harm.",
            "fairness_justice": "Examine whether all affected parties are treated equitably. Check for hidden biases. Ensure benefits and burdens are distributed fairly.",
            "honesty_transparency": "Verify all claims are accurate. Ensure no material information is withheld. Consider whether the communication could mislead even if technically true.",
            "privacy_autonomy": "Confirm that personal data is handled with consent and minimal collection. Ensure individuals retain control over their own information and choices.",
            "consent_autonomy": "Verify that all affected parties have given informed, voluntary consent. Ensure no coercion or manipulation is present.",
            "environmental_impact": "Assess short and long-term environmental consequences. Consider sustainability and impact on future generations.",
            "power_exploitation": "Examine power dynamics. Ensure no vulnerable parties are being exploited. Check for coercive elements.",
            "legal_compliance": "Verify compliance with applicable laws and regulations. Note that legal does not always mean ethical.",
            "general_ethics": "Apply general ethical principles: do no harm, respect persons, act fairly, be honest.",
        }

        considerations = [dimension_guidance.get(d, "") for d in dimensions if dimension_guidance.get(d)]
        framework_analyses = {name: desc for name, desc in frameworks.items()}

        risk_level = "low"
        if "harm_prevention" in dimensions or "power_exploitation" in dimensions:
            risk_level = "high"
        elif len(dimensions) > 2:
            risk_level = "medium"

        return {
            "ethical_dimensions": dimensions,
            "stakeholders_affected": stakeholders,
            "risk_level": risk_level,
            "framework_analyses": framework_analyses,
            "key_considerations": considerations,
            "recommendation": self._generate_recommendation(risk_level, dimensions),
            "questions_to_consider": self._generate_questions(dimensions),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _generate_recommendation(self, risk_level: str, dimensions: List[str]) -> str:
        if risk_level == "high":
            return "This situation involves significant ethical risks. Proceed with caution. Consult affected stakeholders, seek expert guidance, and consider whether the goal can be achieved through a less risky approach."
        if risk_level == "medium":
            return "This situation has moderate ethical complexity. Take time to consider all perspectives, document your reasoning, and build in safeguards to protect affected parties."
        return "This situation appears ethically straightforward. Apply standard ethical principles — honesty, fairness, respect — and proceed thoughtfully."

    def _generate_questions(self, dimensions: List[str]) -> List[str]:
        question_map = {
            "harm_prevention": "Who could be harmed by this, and how can that harm be minimized?",
            "fairness_justice": "Are all affected parties being treated equitably?",
            "honesty_transparency": "Is all relevant information being shared honestly?",
            "privacy_autonomy": "Do affected individuals have control over their own data and choices?",
            "consent_autonomy": "Have all affected parties given informed, voluntary consent?",
            "environmental_impact": "What are the long-term environmental consequences?",
            "power_exploitation": "Are any vulnerable parties being exploited or coerced?",
            "legal_compliance": "Does this comply with all applicable laws and regulations?",
            "general_ethics": "Would a reasonable, ethical person be comfortable with this decision?",
        }
        return [question_map[d] for d in dimensions if d in question_map]

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {})
        text = data.get("content", data.get("text", data.get("situation", "")))

        if action in ("analyze", "evaluate", "assess", "check", "review"):
            dimensions = self._detect_ethical_dimensions(text)
            stakeholders = self._analyze_stakeholders(text)
            analysis = self._generate_ethical_analysis(text, dimensions, stakeholders)
            self.analysis_history.append({"text": text[:100], "analysis": analysis})
            if len(self.analysis_history) > 200:
                self.analysis_history = self.analysis_history[-200:]
            return analysis

        if action == "get_history":
            return {"history": self.analysis_history[-10:], "total": len(self.analysis_history)}

        dimensions = self._detect_ethical_dimensions(text)
        stakeholders = self._analyze_stakeholders(text)
        analysis = self._generate_ethical_analysis(text, dimensions, stakeholders)
        self.analysis_history.append({"text": text[:100], "analysis": analysis})
        return analysis
