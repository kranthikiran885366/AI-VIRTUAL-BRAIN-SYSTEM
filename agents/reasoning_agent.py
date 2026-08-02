import asyncio
import logging
import re
from typing import Dict, List, Any
from datetime import datetime

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ReasoningAgent(BaseAgent):
    def __init__(self, agent_id: str = "reasoning_agent"):
        super().__init__(agent_id, "reasoning")
        self.reasoning_history: List[Dict] = []

    async def initialize(self):
        await super().initialize()
        self.state.update({"reasoning_sessions": 0})
        logger.info(f"Reasoning agent {self.agent_id} initialized")

    async def _update_state(self):
        self.state.update({
            "reasoning_sessions": len(self.reasoning_history),
            "last_active": datetime.utcnow().isoformat(),
        })

    def _detect_reasoning_type(self, text: str) -> str:
        lower = text.lower()
        if any(w in lower for w in ["why", "because", "cause", "reason", "explain why", "what causes"]):
            return "causal"
        if any(w in lower for w in ["if", "then", "therefore", "thus", "hence", "conclude", "follows that"]):
            return "deductive"
        if any(w in lower for w in ["pattern", "trend", "generally", "usually", "most", "evidence suggests"]):
            return "inductive"
        if any(w in lower for w in ["best explanation", "most likely", "probably", "hypothesis", "theory"]):
            return "abductive"
        if any(w in lower for w in ["similar to", "like", "analogous", "compare", "same as", "just as"]):
            return "analogical"
        if any(w in lower for w in ["problem", "solve", "solution", "how to", "approach", "strategy"]):
            return "problem_solving"
        if any(w in lower for w in ["argue", "argument", "claim", "evidence", "support", "counter"]):
            return "argumentative"
        return "analytical"

    def _decompose_problem(self, text: str) -> List[str]:
        sentences = re.split(r'[.!?]+', text.strip())
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        if len(sentences) <= 1:
            words = text.split()
            if len(words) > 10:
                return [
                    f"Core question: {text[:100]}",
                    "What information is given?",
                    "What is being asked or solved?",
                    "What constraints or conditions apply?",
                    "What is the desired outcome?",
                ]
            return [text]
        return sentences[:5]

    def _identify_assumptions(self, text: str) -> List[str]:
        assumptions = []
        lower = text.lower()
        assumption_triggers = [
            ("always", "Assumes this is universally true in all cases"),
            ("never", "Assumes this never occurs under any circumstances"),
            ("everyone", "Assumes all people behave or think the same way"),
            ("obviously", "Assumes something is self-evident without proof"),
            ("clearly", "Assumes something is self-evident without proof"),
            ("of course", "Assumes shared understanding without verification"),
            ("simple", "Assumes low complexity without analysis"),
            ("easy", "Assumes low difficulty without evidence"),
            ("impossible", "Assumes no solution exists without full exploration"),
        ]
        for trigger, assumption in assumption_triggers:
            if trigger in lower:
                assumptions.append(assumption)
        if not assumptions:
            assumptions.append("No explicit assumptions detected — verify that all premises are stated")
        return assumptions[:4]

    def _build_reasoning_chain(self, text: str, reasoning_type: str) -> List[Dict]:
        steps = []
        if reasoning_type == "causal":
            steps = [
                {"step": 1, "type": "observation", "content": f"Observed situation: {text[:80]}"},
                {"step": 2, "type": "cause_identification", "content": "Identify the direct cause(s) of the observed situation"},
                {"step": 3, "type": "mechanism", "content": "Explain the mechanism by which the cause produces the effect"},
                {"step": 4, "type": "contributing_factors", "content": "Identify contributing factors that amplify or moderate the causal relationship"},
                {"step": 5, "type": "conclusion", "content": "State the causal relationship with appropriate confidence level"},
            ]
        elif reasoning_type == "deductive":
            steps = [
                {"step": 1, "type": "premise_1", "content": "State the general principle or rule (major premise)"},
                {"step": 2, "type": "premise_2", "content": "State the specific case (minor premise)"},
                {"step": 3, "type": "logical_connection", "content": "Verify the logical connection between premises"},
                {"step": 4, "type": "conclusion", "content": "Derive the necessary conclusion from the premises"},
                {"step": 5, "type": "validation", "content": "Check for logical fallacies or invalid inferences"},
            ]
        elif reasoning_type == "problem_solving":
            steps = [
                {"step": 1, "type": "problem_definition", "content": f"Define the problem precisely: {text[:80]}"},
                {"step": 2, "type": "constraint_analysis", "content": "Identify all constraints, requirements, and boundaries"},
                {"step": 3, "type": "solution_generation", "content": "Generate multiple potential solution approaches"},
                {"step": 4, "type": "evaluation", "content": "Evaluate each solution against constraints and desired outcomes"},
                {"step": 5, "type": "selection", "content": "Select the optimal solution with justification"},
                {"step": 6, "type": "implementation_plan", "content": "Outline the implementation steps for the chosen solution"},
            ]
        else:
            steps = [
                {"step": 1, "type": "observation", "content": f"Input to analyze: {text[:80]}"},
                {"step": 2, "type": "decomposition", "content": "Break the problem into its component parts"},
                {"step": 3, "type": "analysis", "content": "Analyze each component individually"},
                {"step": 4, "type": "synthesis", "content": "Synthesize findings across components"},
                {"step": 5, "type": "conclusion", "content": "Draw evidence-based conclusions"},
            ]
        return steps

    def _evaluate_argument_strength(self, text: str) -> Dict:
        lower = text.lower()
        evidence_words = ["study", "research", "data", "evidence", "proven", "demonstrated", "shows", "found", "measured"]
        hedge_words = ["might", "could", "possibly", "perhaps", "maybe", "seems", "appears", "suggests"]
        strong_words = ["definitely", "certainly", "always", "never", "proven", "fact", "undeniable"]

        evidence_count = sum(1 for w in evidence_words if w in lower)
        hedge_count = sum(1 for w in hedge_words if w in lower)
        strong_count = sum(1 for w in strong_words if w in lower)

        if evidence_count >= 2:
            strength = "strong"
            confidence = 0.8
        elif evidence_count == 1 or hedge_count > 0:
            strength = "moderate"
            confidence = 0.6
        elif strong_count > 0 and evidence_count == 0:
            strength = "weak"
            confidence = 0.4
        else:
            strength = "moderate"
            confidence = 0.55

        return {
            "strength": strength,
            "confidence": round(confidence, 2),
            "evidence_signals": evidence_count,
            "hedge_signals": hedge_count,
            "overconfidence_signals": strong_count,
        }

    async def reason(self, text: str) -> Dict:
        reasoning_type = self._detect_reasoning_type(text)
        components = self._decompose_problem(text)
        assumptions = self._identify_assumptions(text)
        chain = self._build_reasoning_chain(text, reasoning_type)
        argument_strength = self._evaluate_argument_strength(text)

        result = {
            "input": text[:200],
            "reasoning_type": reasoning_type,
            "problem_components": components,
            "assumptions_identified": assumptions,
            "reasoning_chain": chain,
            "argument_strength": argument_strength,
            "logical_validity": argument_strength["strength"] in ("strong", "moderate"),
            "confidence": argument_strength["confidence"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.reasoning_history.append(result)
        if len(self.reasoning_history) > 200:
            self.reasoning_history = self.reasoning_history[-200:]

        return result

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {})
        text = data.get("content", data.get("text", data.get("problem", "")))

        if action in ("reason", "analyze", "logic", "think", "evaluate", "solve"):
            return await self.reason(text)

        if action == "get_history":
            return {"history": self.reasoning_history[-10:], "total": len(self.reasoning_history)}

        return await self.reason(text)
