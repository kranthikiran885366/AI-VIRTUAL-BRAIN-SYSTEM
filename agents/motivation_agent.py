import asyncio
import logging
from typing import Dict, List, Any
from datetime import datetime

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class MotivationAgent(BaseAgent):
    def __init__(self, agent_id: str = "motivation_agent"):
        super().__init__(agent_id, "motivation")
        self.user_goals: Dict[str, List[Dict]] = {}
        self.encouragement_count: int = 0

    async def initialize(self):
        await super().initialize()
        self.state.update({"encouragements_given": 0, "goals_tracked": 0})
        logger.info(f"Motivation agent {self.agent_id} initialized")

    async def _update_state(self):
        self.state.update({
            "encouragements_given": self.encouragement_count,
            "goals_tracked": sum(len(v) for v in self.user_goals.values()),
            "last_active": datetime.utcnow().isoformat(),
        })

    def _detect_struggle(self, text: str) -> str:
        lower = text.lower()
        if any(w in lower for w in ["give up", "quit", "can't do", "impossible", "hopeless", "failed", "failure"]):
            return "giving_up"
        if any(w in lower for w in ["stuck", "blocked", "don't know how", "confused", "lost", "overwhelmed"]):
            return "stuck"
        if any(w in lower for w in ["tired", "exhausted", "burned out", "no energy", "drained"]):
            return "burnout"
        if any(w in lower for w in ["procrastinat", "lazy", "can't start", "avoiding", "putting off"]):
            return "procrastination"
        if any(w in lower for w in ["scared", "afraid", "fear", "nervous", "anxious about"]):
            return "fear"
        if any(w in lower for w in ["not good enough", "imposter", "fraud", "don't deserve", "not smart"]):
            return "imposter_syndrome"
        return "general"

    def _generate_motivation(self, struggle_type: str, context: str) -> Dict:
        responses = {
            "giving_up": {
                "message": "Every expert was once a beginner who refused to quit. The fact that you're still here, still trying, means you have what it takes. What feels like failure right now is actually data — it's showing you exactly what to adjust. One more attempt, with what you've learned, is all it takes.",
                "action": "Break your goal into the smallest possible next step. What is the one thing you can do in the next 10 minutes?",
                "affirmation": "You are closer than you think.",
            },
            "stuck": {
                "message": "Being stuck is not a sign of weakness — it's a sign that you're working on something genuinely challenging. The path forward is almost always through a different angle. Let's find that angle together.",
                "action": "Describe the exact point where you're stuck. Sometimes articulating the problem reveals the solution.",
                "affirmation": "Every problem has a solution. You have the intelligence to find it.",
            },
            "burnout": {
                "message": "Rest is not giving up — it's part of the process. High performance requires recovery. The most productive thing you can do right now might be to step away for a defined period, then return with fresh energy.",
                "action": "Schedule a specific rest period — even 20 minutes. Then schedule your return time. Rest with intention.",
                "affirmation": "Taking care of yourself is taking care of your goals.",
            },
            "procrastination": {
                "message": "Procrastination is usually fear in disguise — fear of failure, fear of imperfection, or fear of the unknown. The antidote is action, not motivation. Start with two minutes. Just two minutes.",
                "action": "Use the 2-minute rule: commit to working on this for exactly 2 minutes. Most of the time, you'll keep going.",
                "affirmation": "Starting is the hardest part. You've already started by thinking about it.",
            },
            "fear": {
                "message": "Fear means you care about the outcome. That caring is your greatest asset. The goal is not to eliminate fear but to act alongside it. Courage is not the absence of fear — it's moving forward despite it.",
                "action": "Name the specific fear. Write it down. Then write the realistic worst case, and your plan if that happens. Fear loses power when it's specific.",
                "affirmation": "You are braver than you believe.",
            },
            "imposter_syndrome": {
                "message": "The fact that you question your own competence is actually a sign of high intelligence and self-awareness. People who truly don't know what they're doing rarely worry about it. Your doubt is evidence of your standards — and your standards are what will make you great.",
                "action": "Write down three things you have accomplished that required real skill. Read them out loud.",
                "affirmation": "You earned your place. You belong here.",
            },
            "general": {
                "message": "Every journey has difficult moments. What matters is not the absence of difficulty but your response to it. You have overcome challenges before — this one is no different.",
                "action": "Reconnect with your 'why'. Why does this goal matter to you? Write it down in one sentence.",
                "affirmation": "Progress, not perfection. Keep moving.",
            },
        }
        response = responses.get(struggle_type, responses["general"])
        self.encouragement_count += 1
        return {
            "struggle_detected": struggle_type,
            "message": response["message"],
            "action_step": response["action"],
            "affirmation": response["affirmation"],
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _celebrate_progress(self, achievement: str) -> Dict:
        return {
            "type": "celebration",
            "message": f"This is a real achievement: {achievement}. Acknowledge it fully. Progress compounds — every win, no matter how small, builds momentum for the next one. You did this.",
            "next_step": "Capture what worked. What did you do that led to this success? That's your formula.",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def track_goal(self, user_id: str, goal: str) -> Dict:
        if user_id not in self.user_goals:
            self.user_goals[user_id] = []
        entry = {"goal": goal, "added_at": datetime.utcnow().isoformat(), "status": "active", "check_ins": 0}
        self.user_goals[user_id].append(entry)
        return {"tracked": True, "goal": goal, "total_goals": len(self.user_goals[user_id])}

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {})
        text = data.get("content", data.get("text", ""))
        user_id = task.get("user_id") or data.get("user_id", "default")

        if action in ("motivate", "encourage", "inspire", "help"):
            struggle = self._detect_struggle(text)
            return self._generate_motivation(struggle, text)

        if action == "celebrate":
            achievement = data.get("achievement", text)
            return self._celebrate_progress(achievement)

        if action == "track_goal":
            goal = data.get("goal", text)
            return self.track_goal(user_id, goal)

        if action == "get_goals":
            goals = self.user_goals.get(user_id, [])
            return {"goals": goals, "count": len(goals)}

        struggle = self._detect_struggle(text)
        return self._generate_motivation(struggle, text)
