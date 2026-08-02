import asyncio
import logging
import uuid
from typing import Dict, List, Any
from datetime import datetime

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class PlanningAgent(BaseAgent):
    def __init__(self, agent_id: str = "planning_agent"):
        super().__init__(agent_id, "planning")
        self.active_plans: Dict[str, Dict] = {}
        self.completed_plans: List[Dict] = []

    async def initialize(self):
        await super().initialize()
        self.state.update({"active_plans": 0, "completed_plans": 0})
        logger.info(f"Planning agent {self.agent_id} initialized")

    async def _update_state(self):
        self.state.update({
            "active_plans": len(self.active_plans),
            "completed_plans": len(self.completed_plans),
            "last_active": datetime.utcnow().isoformat(),
        })

    async def create_plan(self, goal: str, timeframe: str = None, constraints: List[str] = None) -> Dict:
        constraints = constraints or []
        milestones = self._decompose_goal(goal, timeframe)
        plan = {
            "id": str(uuid.uuid4()),
            "goal": goal,
            "created_at": datetime.utcnow().isoformat(),
            "timeframe": timeframe or "flexible",
            "constraints": constraints,
            "milestones": milestones,
            "risks": self._identify_risks(goal, constraints),
            "resources": self._estimate_resources(goal, milestones),
            "status": "active",
            "progress": 0.0,
        }
        self.active_plans[plan["id"]] = plan
        await self.broadcast_message("planning_request", {"plan_id": plan["id"], "goal": goal})
        return plan

    def _decompose_goal(self, goal: str, timeframe: str = None) -> List[Dict]:
        lower = goal.lower()
        if any(w in lower for w in ["build", "create", "develop", "make"]):
            phases = ["Research & Requirements", "Design & Architecture", "Implementation", "Testing & Validation", "Launch & Monitor"]
        elif any(w in lower for w in ["learn", "study", "understand", "master"]):
            phases = ["Assess Current Knowledge", "Gather Learning Resources", "Structured Study", "Practice & Apply", "Review & Consolidate"]
        elif any(w in lower for w in ["improve", "optimize", "enhance", "fix"]):
            phases = ["Diagnose Current State", "Identify Improvement Areas", "Design Solutions", "Implement Changes", "Measure Results"]
        elif any(w in lower for w in ["plan", "organize", "schedule", "manage"]):
            phases = ["Define Scope & Objectives", "Break Down into Tasks", "Prioritize & Schedule", "Execute", "Review & Adjust"]
        else:
            phases = ["Define Clear Objectives", "Research & Gather Information", "Develop Strategy", "Execute Plan", "Evaluate Outcomes"]
        return [
            {
                "id": str(uuid.uuid4()),
                "order": i + 1,
                "title": phase,
                "description": f"Complete '{phase}' for: {goal}",
                "status": "pending",
                "estimated_effort": "high" if any(w in phase.lower() for w in ["implement", "execute", "develop"]) else "medium" if any(w in phase.lower() for w in ["design", "test"]) else "low",
                "success_criteria": f"{phase} deliverables completed and validated",
            }
            for i, phase in enumerate(phases)
        ]

    def _identify_risks(self, goal: str, constraints: List[str]) -> List[Dict]:
        risks = [{"risk": "Timeline slippage", "probability": "medium", "impact": "medium", "mitigation": "Build 20% buffer into each milestone"}]
        if any(w in goal.lower() for w in ["build", "develop", "create"]):
            risks.append({"risk": "Scope creep", "probability": "medium", "impact": "high", "mitigation": "Define clear requirements upfront"})
        if constraints:
            risks.append({"risk": f"Constraint violations: {', '.join(constraints[:2])}", "probability": "low", "impact": "high", "mitigation": "Regular constraint review at each milestone"})
        return risks

    def _estimate_resources(self, goal: str, milestones: List[Dict]) -> Dict:
        high = sum(1 for m in milestones if m.get("estimated_effort") == "high")
        return {
            "estimated_total_effort": f"{high * 3 + (len(milestones) - high) * 2} effort units",
            "recommended_team_size": max(1, high),
            "key_skills_needed": self._extract_skills(goal),
        }

    def _extract_skills(self, goal: str) -> List[str]:
        lower = goal.lower()
        skills = []
        if any(w in lower for w in ["code", "build", "develop", "software"]): skills += ["software development", "testing"]
        if any(w in lower for w in ["design", "ui", "ux"]): skills += ["UI/UX design", "prototyping"]
        if any(w in lower for w in ["manage", "organize", "plan"]): skills += ["project management", "communication"]
        if any(w in lower for w in ["learn", "study"]): skills += ["self-discipline", "research"]
        return skills or ["planning", "execution", "communication"]

    async def update_milestone(self, plan_id: str, milestone_id: str, status: str) -> Dict:
        plan = self.active_plans.get(plan_id)
        if not plan:
            return {"error": "Plan not found"}
        for m in plan["milestones"]:
            if m["id"] == milestone_id:
                m["status"] = status
                if status == "completed":
                    m["completed_at"] = datetime.utcnow().isoformat()
                break
        completed = sum(1 for m in plan["milestones"] if m["status"] == "completed")
        plan["progress"] = round(completed / len(plan["milestones"]), 3)
        if plan["progress"] >= 1.0:
            plan["status"] = "completed"
            plan["completed_at"] = datetime.utcnow().isoformat()
            self.completed_plans.append(plan)
            del self.active_plans[plan_id]
        return plan

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {})
        if action in ("create", "plan", "create_plan"):
            return await self.create_plan(
                goal=data.get("goal", data.get("content", "")),
                timeframe=data.get("timeframe"),
                constraints=data.get("constraints", []),
            )
        if action == "update_milestone":
            return await self.update_milestone(data.get("plan_id", ""), data.get("milestone_id", ""), data.get("status", "completed"))
        if action == "get_plan":
            return self.active_plans.get(data.get("plan_id", ""), {"error": "Plan not found"})
        if action == "list_plans":
            return {"active": list(self.active_plans.values()), "completed": self.completed_plans[-10:], "total_active": len(self.active_plans), "total_completed": len(self.completed_plans)}
        return await self.create_plan(goal=data.get("content", data.get("goal", "achieve the objective")), timeframe=data.get("timeframe"))
