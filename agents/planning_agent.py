import asyncio
import logging
import uuid
from typing import Dict, List, Any, Optional
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
        self.plan_config = {
            "max_planning_depth": 3,
            "max_task_count": 12,
            "parallel_task_limit": 3,
            "confidence_threshold": 0.55,
            "risk_threshold": 0.65,
        }

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

    async def create_plan(
        self,
        goal: str,
        timeframe: str = None,
        constraints: List[str] = None,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        if not goal:
            raise ValueError("goal is required")

        constraints = list(constraints or [])
        context = dict(context or {})
        metadata = dict(metadata or {})
        timestamp = datetime.utcnow().isoformat()
        plan_id = str(uuid.uuid4())
        goal_id = str(uuid.uuid4())
        milestones = self._decompose_goal(goal, timeframe)
        htn = self._build_htn(goal, milestones, constraints)
        resources = self._estimate_resources(goal, milestones)
        risks = self._identify_risks(goal, constraints)
        validation = self._validate_plan(goal, constraints, milestones, htn, resources, risks)
        explanation = self._build_explanation(goal, milestones, resources, risks, constraints)
        plan = {
            "plan_id": plan_id,
            "id": plan_id,
            "goal_id": goal_id,
            "goal": goal,
            "created_at": timestamp,
            "updated_at": timestamp,
            "timeframe": timeframe or "flexible",
            "constraints": constraints,
            "milestones": milestones,
            "tasks": milestones,
            "plan_context": self._build_plan_context(context),
            "plan_metadata": self._build_plan_metadata(goal, timeframe, constraints, metadata),
            "plan_session": {
                "session_id": str(uuid.uuid4()),
                "request_id": context.get("request_id"),
                "correlation_id": context.get("correlation_id"),
                "trace_id": context.get("trace_id"),
            },
            "plan_state": {
                "status": "active",
                "progress": 0.0,
                "running_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "cancelled_tasks": 0,
                "blocked_tasks": 0,
                "waiting_tasks": 0,
            },
            "plan_history": [],
            "history": [],
            "plan_audit": [],
            "version": 1,
            "version_history": [{"version": 1, "updated_at": timestamp, "reason": "initial_plan"}],
            "htn": htn,
            "validation": validation,
            "risks": risks,
            "resources": resources,
            "status": "active",
            "progress": 0.0,
        }
        plan["history"].append({
            "version": 1,
            "event": "created",
            "timestamp": timestamp,
            "summary": f"Plan created for goal: {goal}",
        })
        plan["plan_history"] = list(plan["history"])
        plan["plan_audit"].append({
            "event": "plan_created",
            "timestamp": timestamp,
            "plan_id": plan_id,
            "goal_id": goal_id,
            "correlation_id": context.get("correlation_id"),
            "trace_id": context.get("trace_id"),
        })
        plan["explanation"] = explanation
        self.active_plans[plan_id] = plan
        await self.broadcast_message("planning_request", {
            "plan_id": plan_id,
            "goal_id": goal_id,
            "goal": goal,
            "correlation_id": context.get("correlation_id"),
            "trace_id": context.get("trace_id"),
        })
        await self._update_state()
        return plan

    def _build_plan_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "goal": context.get("goal"),
            "conversation_context": context.get("conversation_context", {}),
            "memory_context": context.get("memory_context", {}),
            "decision_context": context.get("decision_context", {}),
            "reasoning_context": context.get("reasoning_context", {}),
            "execution_context": context.get("execution_context", {}),
            "request_id": context.get("request_id"),
            "correlation_id": context.get("correlation_id"),
            "trace_id": context.get("trace_id"),
            "constraints": context.get("constraints", []),
            "resources": context.get("resources", {}),
            "deadlines": context.get("deadlines", {}),
            "system_state": context.get("system_state", {}),
            "priority": context.get("priority", 2),
        }

    def _build_plan_metadata(self, goal: str, timeframe: Optional[str], constraints: List[str], metadata: Dict[str, Any]) -> Dict[str, Any]:
        lower = goal.lower()
        category = "execution"
        if any(word in lower for word in ["build", "create", "develop", "code", "software"]):
            category = "development"
        elif any(word in lower for word in ["learn", "study", "understand", "master"]):
            category = "learning"
        elif any(word in lower for word in ["improve", "optimize", "enhance", "fix"]):
            category = "improvement"

        return {
            "goal_category": category,
            "goal_priority": metadata.get("goal_priority", 2),
            "owner": metadata.get("owner", "planning_agent"),
            "deadline": metadata.get("deadline", timeframe),
            "constraints": constraints,
            "resource_profile": metadata.get("resource_profile", "balanced"),
            "planning_strategy": metadata.get("planning_strategy", "goal_decomposition"),
        }

    def _build_htn(self, goal: str, milestones: List[Dict], constraints: List[str]) -> Dict[str, Any]:
        root_task = {
            "id": f"task-root-{uuid.uuid4().hex[:8]}",
            "title": goal,
            "type": "compound",
            "status": "pending",
            "priority": 2,
            "children": [
                {
                    "id": m["id"],
                    "title": m["title"],
                    "type": "atomic" if m["estimated_effort"] in {"low", "medium"} else "compound",
                    "status": m["status"],
                    "priority": 2,
                    "children": [],
                }
                for m in milestones
            ],
        }
        dependencies = []
        for index in range(1, len(milestones)):
            dependencies.append({
                "from": milestones[index - 1]["id"],
                "to": milestones[index]["id"],
                "type": "sequential",
            })
        return {
            "root_task": root_task,
            "tasks": milestones,
            "dependencies": dependencies,
            "parallel_tasks": [],
            "constraints": constraints,
        }

    def _validate_plan(
        self,
        goal: str,
        constraints: List[str],
        milestones: List[Dict],
        htn: Dict[str, Any],
        resources: Dict[str, Any],
        risks: List[Dict],
    ) -> Dict[str, Any]:
        issues = []
        if not goal.strip():
            issues.append("invalid_goal")
        if not milestones:
            issues.append("missing_tasks")
        if not resources.get("key_skills_needed"):
            issues.append("missing_resources")
        for dependency in htn.get("dependencies", []):
            if dependency.get("from") == dependency.get("to"):
                issues.append("dependency_cycle")
                break
        if constraints and len(constraints) > self.plan_config["max_task_count"]:
            issues.append("constraint_pressure")

        status = "passed"
        if issues:
            status = "warning"
        return {
            "status": status,
            "issues": issues,
            "dependency_cycles": 0,
            "missing_resources": 1 if not resources.get("key_skills_needed") else 0,
            "duplicate_tasks": 0,
            "conflicting_constraints": 0,
            "deadline_conflicts": 0,
            "execution_feasibility": "feasible" if status == "passed" else "needs_review",
        }

    def _build_explanation(
        self,
        goal: str,
        milestones: List[Dict],
        resources: Dict[str, Any],
        risks: List[Dict],
        constraints: List[str],
    ) -> Dict[str, Any]:
        execution_order = [m["title"] for m in milestones]
        confidence = max(0.0, min(1.0, 0.66 + (0.04 * min(len(milestones), 5)) - (0.03 * len(risks))))
        return {
            "goal_summary": f"Create a production delivery plan for: {goal}",
            "planning_strategy": "goal_decomposition",
            "reasoning_summary": "The plan was decomposed into ordered tasks with explicit dependency sequencing and resource estimation.",
            "dependency_explanation": "Each task depends on the preceding task to preserve deterministic execution flow.",
            "resource_explanation": f"Resource planning is driven by {resources.get('recommended_team_size', 1)} recommended contributor(s) and key skills: {', '.join(resources.get('key_skills_needed', []))}.",
            "risk_explanation": f"Known risks: {', '.join(r.get('risk', '') for r in risks)}.",
            "execution_order": execution_order,
            "confidence": round(confidence, 3),
            "limitations": ["No external execution telemetry was available during planning."] if constraints else ["Planning relies on available context and deterministic decomposition."] ,
            "alternative_plans_considered": ["sequential_execution", "parallel_execution"],
        }

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
            "resource_confidence": round(max(0.0, min(1.0, 0.7 + (0.05 * high))), 3),
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
        plan["plan_state"]["progress"] = plan["progress"]
        plan["plan_state"]["completed_tasks"] = completed
        plan["plan_state"]["running_tasks"] = max(0, len(plan["milestones"]) - completed)
        plan["updated_at"] = datetime.utcnow().isoformat()
        if plan["progress"] >= 1.0:
            plan["status"] = "completed"
            plan["plan_state"]["status"] = "completed"
            plan["completed_at"] = datetime.utcnow().isoformat()
            self.completed_plans.append(plan)
            del self.active_plans[plan_id]
        plan["history"].append({
            "version": plan.get("version", 1),
            "event": "milestone_update",
            "timestamp": plan["updated_at"],
            "summary": f"Milestone {milestone_id} marked {status}",
        })
        plan["plan_history"] = list(plan["history"])
        return plan

    async def replan(self, plan_id: str, goal: Optional[str] = None, timeframe: Optional[str] = None, constraints: Optional[List[str]] = None, context: Optional[Dict[str, Any]] = None) -> Dict:
        plan = self.active_plans.get(plan_id)
        if not plan:
            return {"error": "Plan not found"}
        plan["goal"] = goal or plan["goal"]
        plan["timeframe"] = timeframe or plan.get("timeframe", "flexible")
        plan["constraints"] = list(constraints or plan.get("constraints", []))
        plan["updated_at"] = datetime.utcnow().isoformat()
        plan["version"] = int(plan.get("version", 1)) + 1
        plan["version_history"].append({
            "version": plan["version"],
            "updated_at": plan["updated_at"],
            "reason": "replan",
        })
        milestones = self._decompose_goal(plan["goal"], plan["timeframe"])
        htn = self._build_htn(plan["goal"], milestones, plan["constraints"])
        resources = self._estimate_resources(plan["goal"], milestones)
        risks = self._identify_risks(plan["goal"], plan["constraints"])
        validation = self._validate_plan(plan["goal"], plan["constraints"], milestones, htn, resources, risks)
        explanation = self._build_explanation(plan["goal"], milestones, resources, risks, plan["constraints"])

        plan["milestones"] = milestones
        plan["tasks"] = milestones
        plan["htn"] = htn
        plan["validation"] = validation
        plan["resources"] = resources
        plan["risks"] = risks
        plan["explanation"] = explanation
        if context:
            plan["plan_context"] = self._build_plan_context({**plan.get("plan_context", {}), **context})
        plan["plan_state"]["status"] = "active"
        plan["history"].append({
            "version": plan["version"],
            "event": "replanned",
            "timestamp": plan["updated_at"],
            "summary": f"Plan replanned for goal: {plan['goal']}",
        })
        plan["plan_history"] = list(plan["history"])
        plan["plan_audit"].append({
            "event": "plan_replanned",
            "timestamp": plan["updated_at"],
            "plan_id": plan_id,
            "goal_id": plan.get("goal_id"),
            "correlation_id": plan.get("plan_context", {}).get("correlation_id"),
            "trace_id": plan.get("plan_context", {}).get("trace_id"),
        })
        await self._update_state()
        return plan

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {})
        if action in ("create", "plan", "create_plan"):
            return await self.create_plan(
                goal=data.get("goal", data.get("content", "")),
                timeframe=data.get("timeframe"),
                constraints=data.get("constraints", []),
                context=data.get("context") or {},
            )
        if action == "update_milestone":
            return await self.update_milestone(data.get("plan_id", ""), data.get("milestone_id", ""), data.get("status", "completed"))
        if action == "replan":
            return await self.replan(
                plan_id=data.get("plan_id", ""),
                goal=data.get("goal"),
                timeframe=data.get("timeframe"),
                constraints=data.get("constraints", []),
                context=data.get("context") or {},
            )
        if action == "get_plan":
            plan = self.active_plans.get(data.get("plan_id", ""))
            if plan:
                return plan
            return self.completed_plans[-1] if self.completed_plans else {"error": "Plan not found"}
        if action == "list_plans":
            return {"active": list(self.active_plans.values()), "completed": self.completed_plans[-10:], "total_active": len(self.active_plans), "total_completed": len(self.completed_plans)}
        return await self.create_plan(goal=data.get("content", data.get("goal", "achieve the objective")), timeframe=data.get("timeframe"))
