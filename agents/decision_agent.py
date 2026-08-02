import asyncio
import logging
import uuid
import random
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from structlog import get_logger
except ImportError:
    def get_logger():
        return logging.getLogger(__name__)

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

logger = get_logger()


class DecisionAgent(BaseAgent):
    def __init__(self, agent_id: str = "decision_agent"):
        super().__init__(agent_id, "decision")
        self.decision_history: List[Dict] = []
        self.action_outcomes: Dict[str, List[bool]] = {}
        self.exploration_rate = 0.1
        self.max_history = 1000

    async def initialize(self):
        await super().initialize()
        self.state.update({
            "decision_count": 0,
            "success_rate": 0.0,
            "last_decision": datetime.utcnow().isoformat(),
        })
        logger.info(f"Decision agent {self.agent_id} initialized")

    async def _update_state(self):
        total = len(self.decision_history)
        successes = sum(1 for d in self.decision_history if d.get("success") is True)
        self.state.update({
            "decision_count": total,
            "success_rate": round(successes / total, 3) if total else 0.0,
            "last_active": datetime.utcnow().isoformat(),
        })

    async def _process_emotions(self):
        recent = self.decision_history[-10:]
        if not recent:
            return
        rate = sum(1 for d in recent if d.get("success") is True) / len(recent)
        if rate > 0.7:
            await self.update_emotion("confidence", min(1.0, self.emotions.get("confidence", 0.7) + 0.05))
            await self.update_emotion("uncertainty", max(0.0, self.emotions.get("uncertainty", 0.1) - 0.03))
        elif rate < 0.3:
            await self.update_emotion("uncertainty", min(1.0, self.emotions.get("uncertainty", 0.1) + 0.05))
            await self.update_emotion("confidence", max(0.0, self.emotions.get("confidence", 0.7) - 0.03))

    async def make_decision(self, context: Dict) -> Dict:
        options = context.get("options", [])
        goal = context.get("goal", "")
        constraints = context.get("constraints", [])

        if not options:
            options = self._infer_options(goal)

        scored = []
        for option in options:
            score = self._score_option(option, goal, constraints)
            scored.append({"option": option, "score": score})

        scored.sort(key=lambda x: x["score"], reverse=True)

        if random.random() < self.exploration_rate and len(scored) > 1:
            chosen = random.choice(scored[1:])
            method = "exploration"
        else:
            chosen = scored[0] if scored else {"option": "proceed", "score": 0.5}
            method = "exploitation"

        confidence = min(0.95, 0.4 + chosen["score"] * 0.55)

        decision = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "goal": goal,
            "chosen_option": chosen["option"],
            "confidence": round(confidence, 3),
            "method": method,
            "all_options": scored,
            "constraints_applied": constraints,
            "success": None,
        }

        self.decision_history.append(decision)
        if len(self.decision_history) > self.max_history:
            self.decision_history = self.decision_history[-self.max_history:]

        self.state["decision_count"] = len(self.decision_history)
        self.state["last_decision"] = datetime.utcnow().isoformat()

        await self.broadcast_message("decision_result", {
            "decision_id": decision["id"],
            "chosen": chosen["option"],
            "confidence": confidence,
            "goal": goal,
        })

        return decision

    def _infer_options(self, goal: str) -> List[str]:
        lower = goal.lower()
        if any(w in lower for w in ["plan", "schedule", "organize"]):
            return ["create_detailed_plan", "create_quick_outline", "delegate_planning"]
        if any(w in lower for w in ["decide", "choose", "pick", "select"]):
            return ["gather_more_info", "decide_now", "defer_decision"]
        if any(w in lower for w in ["problem", "issue", "fix", "solve"]):
            return ["analyze_root_cause", "apply_quick_fix", "escalate"]
        return ["proceed", "pause_and_reflect", "seek_input"]

    def _score_option(self, option: str, goal: str, constraints: List[str]) -> float:
        base = 0.5
        lower_option = option.lower()
        lower_goal = goal.lower()

        goal_words = set(lower_goal.split())
        option_words = set(lower_option.replace("_", " ").split())
        overlap = len(goal_words & option_words)
        base += overlap * 0.1

        past = self.action_outcomes.get(option, [])
        if past:
            base += (sum(past) / len(past)) * 0.3

        for constraint in constraints:
            if constraint.lower() in lower_option:
                base -= 0.15

        return round(min(1.0, max(0.0, base)), 3)

    async def record_outcome(self, decision_id: str, success: bool):
        for d in self.decision_history:
            if d["id"] == decision_id:
                d["success"] = success
                option = d["chosen_option"]
                if option not in self.action_outcomes:
                    self.action_outcomes[option] = []
                self.action_outcomes[option].append(success)
                if len(self.action_outcomes[option]) > 100:
                    self.action_outcomes[option] = self.action_outcomes[option][-100:]
                break

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        input_data = task.get("input_data", {})

        if action in ("decide", "make_decision", "choose"):
            return await self.make_decision(input_data)

        if action == "record_outcome":
            await self.record_outcome(
                input_data.get("decision_id", ""),
                input_data.get("success", True)
            )
            return {"status": "recorded"}

        if action == "get_stats":
            return {
                "decision_count": len(self.decision_history),
                "success_rate": self.state.get("success_rate", 0.0),
                "exploration_rate": self.exploration_rate,
                "tracked_options": len(self.action_outcomes),
            }

        return await self.make_decision({"goal": input_data.get("content", action), "options": []})
