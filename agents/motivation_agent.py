"""
Production Motivation Agent — Phase 8
Integrates MotivationEngine for goal lifecycle, scoring, history,
metrics, audit trail, burnout/stagnation detection.
Backward compatible with all existing execute_task actions.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

try:
    from agents.emotion_agent.motivation_engine import MotivationEngine, Goal
except ImportError:
    try:
        from emotion_agent.motivation_engine import MotivationEngine, Goal
    except ImportError:
        MotivationEngine = None
        Goal = None

logger = logging.getLogger(__name__)


class MotivationAgent(BaseAgent):
    """
    Production Motivation Agent — Phase 8.
    Wraps MotivationEngine for goal lifecycle, scoring, history, metrics,
    audit trail, burnout/stagnation detection, and adaptive recommendations.
    Preserves all Phase 1–7 execute_task actions.
    """

    def __init__(self, agent_id: str = "motivation_agent", config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id, "motivation")
        self._config = config or {}
        # Phase 1–7 state (preserved for backward compatibility)
        self.user_goals: Dict[str, List[Dict]] = {}
        self.encouragement_count: int = 0
        # Phase 8: production engine
        engine_cfg = self._config.get("engine")
        self.engine: Optional[MotivationEngine] = (
            MotivationEngine(engine_cfg) if MotivationEngine else None
        )

    async def initialize(self):
        await super().initialize()
        self.state.update({"encouragements_given": 0, "goals_tracked": 0})
        if self.engine:
            await self.engine.start()
        logger.info("Motivation agent %s initialized (engine=%s)",
                    self.agent_id, self.engine is not None)

    async def shutdown(self):
        if self.engine:
            await self.engine.stop()
        await super().shutdown()
        logger.info("Motivation agent %s shut down", self.agent_id)

    async def _update_state(self):
        self.state.update({
            "encouragements_given": self.encouragement_count,
            "goals_tracked": sum(len(v) for v in self.user_goals.values()),
            "last_active": datetime.utcnow().isoformat(),
        })

    # ─── Phase 1–7 helpers (preserved) ───────────────────────────────────────

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

    # ─── Phase 8: execute_task ────────────────────────────────────────────────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {})
        text = data.get("content", data.get("text", ""))
        user_id = task.get("user_id") or data.get("user_id", "default")

        # ── Phase 1–7 actions (preserved) ────────────────────────────────────
        if action in ("motivate", "encourage", "inspire", "help"):
            struggle = self._detect_struggle(text)
            result = self._generate_motivation(struggle, text)
            # Phase 8: also compute motivation score if engine available
            if self.engine:
                score = self.engine.compute_score(user_id)
                result["motivation_score"] = score.overall
                result["is_burned_out"] = score.is_burned_out
            return result

        if action == "celebrate":
            achievement = data.get("achievement", text)
            return self._celebrate_progress(achievement)

        if action == "track_goal":
            goal_text = data.get("goal", text)
            result = self.track_goal(user_id, goal_text)
            # Phase 8: also create in engine
            if self.engine:
                try:
                    goal_obj = self.engine.create_goal(
                        user_id=user_id,
                        title=goal_text,
                        difficulty=float(data.get("difficulty", 0.5)),
                        priority=int(data.get("priority", 2)),
                    )
                    result["goal_id"] = goal_obj.goal_id
                except Exception:
                    pass
            return result

        if action == "get_goals":
            goals = self.user_goals.get(user_id, [])
            result: Dict[str, Any] = {"goals": goals, "count": len(goals)}
            # Phase 8: also return engine goals
            if self.engine:
                engine_goals = [g.to_dict() for g in self.engine.get_goals(user_id)]
                result["engine_goals"] = engine_goals
                result["engine_goal_count"] = len(engine_goals)
            return result

        # ── Phase 8 actions ───────────────────────────────────────────────────

        if action == "create_goal" and self.engine:
            validation = self.engine.validate_goal_data(data)
            if not validation["valid"]:
                return {"status": "error", "errors": validation["errors"]}
            goal_obj = self.engine.create_goal(
                user_id=user_id,
                title=data.get("title", text),
                description=data.get("description", ""),
                priority=int(data.get("priority", 2)),
                difficulty=float(data.get("difficulty", 0.5)),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
            )
            return {"status": "created", "goal": goal_obj.to_dict()}

        if action == "update_progress" and self.engine:
            goal_id = data.get("goal_id", "")
            progress = float(data.get("progress", 0.0))
            success = bool(data.get("success", True))
            goal_obj = self.engine.update_goal_progress(user_id, goal_id, progress, success)
            if not goal_obj:
                return {"status": "error", "error": f"Goal {goal_id} not found"}
            return {"status": "updated", "goal": goal_obj.to_dict()}

        if action == "abandon_goal" and self.engine:
            goal_id = data.get("goal_id", "")
            reason = data.get("reason", "")
            ok = self.engine.abandon_goal(user_id, goal_id, reason)
            return {"status": "abandoned" if ok else "error",
                    "goal_id": goal_id}

        if action == "get_motivation_score" and self.engine:
            confidence_influence = float(data.get("confidence_influence", 0.0))
            task_completion_rate = float(data.get("task_completion_rate", 0.5))
            score = self.engine.compute_score(user_id, confidence_influence, task_completion_rate)
            return {"status": "ok", "score": score.to_dict()}

        if action == "get_engine_goals" and self.engine:
            status_filter = data.get("status")
            goals = self.engine.get_goals(user_id, status=status_filter)
            return {"status": "ok", "goals": [g.to_dict() for g in goals],
                    "count": len(goals)}

        if action == "get_analytics" and self.engine:
            return {"status": "ok", "analytics": self.engine.get_analytics(user_id)}

        if action == "get_metrics" and self.engine:
            return {"status": "ok", "metrics": self.engine.get_metrics()}

        if action == "get_audit_trail" and self.engine:
            limit = int(data.get("limit", 100))
            return {"status": "ok", "audit_trail": self.engine.get_audit_trail(limit)}

        if action == "get_score_history" and self.engine:
            limit = int(data.get("limit", 50))
            return {"status": "ok",
                    "history": self.engine.get_score_history(user_id, limit)}

        if action == "mark_stagnant" and self.engine:
            stagnant_ids = self.engine.mark_stagnant_goals(user_id)
            return {"status": "ok", "stagnant_goals": stagnant_ids,
                    "count": len(stagnant_ids)}

        # Default: motivate
        struggle = self._detect_struggle(text)
        result = self._generate_motivation(struggle, text)
        if self.engine:
            score = self.engine.compute_score(user_id)
            result["motivation_score"] = score.overall
            result["is_burned_out"] = score.is_burned_out
        return result
