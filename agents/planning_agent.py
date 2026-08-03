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
        """Build Hierarchical Task Network with proper dependencies and execution ordering."""
        root_task_id = f"task-root-{uuid.uuid4().hex[:8]}"
        
        # Build root task
        root_task = {
            "id": root_task_id,
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
                    "estimated_hours": m.get("estimated_hours", 6),
                }
                for m in milestones
            ],
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Build dependency graph
        dependencies = []
        parallel_tasks = []
        for index in range(1, len(milestones)):
            milestone = milestones[index]
            prev_milestone = milestones[index - 1]
            
            # Check if task is marked as parallel-capable
            if milestone.get("parallel_capable", False):
                parallel_tasks.append(milestone["id"])
            else:
                # Create sequential dependency
                dependencies.append({
                    "from": prev_milestone["id"],
                    "to": milestone["id"],
                    "type": "sequential",
                    "required": True,
                })
        
        # Detect cycles in dependencies
        cycle_detected = self._detect_dependency_cycles(dependencies)
        
        return {
            "root_task": root_task,
            "root_task_id": root_task_id,
            "tasks": milestones,
            "dependencies": dependencies,
            "parallel_tasks": parallel_tasks,
            "constraints": constraints,
            "has_cycles": cycle_detected,
            "task_count": len(milestones),
            "max_depth": self._calculate_htn_depth(root_task),
            "created_at": datetime.utcnow().isoformat(),
        }
    
    def _detect_dependency_cycles(self, dependencies: List[Dict]) -> bool:
        """Detect cycles in task dependency graph."""
        if not dependencies:
            return False
        
        # Build adjacency list
        graph = {}
        for dep in dependencies:
            from_id = dep.get("from")
            to_id = dep.get("to")
            if from_id not in graph:
                graph[from_id] = []
            graph[from_id].append(to_id)
        
        # DFS-based cycle detection
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    return True
        
        return False
    
    def _calculate_htn_depth(self, task: Dict, depth: int = 0) -> int:
        """Calculate maximum depth of HTN task hierarchy."""
        if not task.get("children"):
            return depth
        
        max_child_depth = depth
        for child in task.get("children", []):
            child_depth = self._calculate_htn_depth(child, depth + 1)
            max_child_depth = max(max_child_depth, child_depth)
        
        return max_child_depth

    def _validate_plan(
        self,
        goal: str,
        constraints: List[str],
        milestones: List[Dict],
        htn: Dict[str, Any],
        resources: Dict[str, Any],
        risks: List[Dict],
    ) -> Dict[str, Any]:
        """Comprehensive plan validation with 7-point checks."""
        issues = []
        validation_checks = {
            "goal_validation": self._validate_goal(goal),
            "task_validation": self._validate_tasks(milestones),
            "dependency_validation": self._validate_dependencies(htn.get("dependencies", [])),
            "resource_validation": self._validate_resources(resources),
            "constraint_validation": self._validate_constraints(constraints, len(milestones)),
            "deadline_validation": self._validate_deadlines(milestones),
            "feasibility_validation": self._validate_execution_feasibility(milestones, resources, constraints),
        }
        
        # Collect all issues
        for check_name, result in validation_checks.items():
            if not result.get("valid", True):
                issues.extend(result.get("issues", []))
        
        status = "passed" if not issues else "warning"
        
        return {
            "status": status,
            "issues": issues,
            "checks": validation_checks,
            "dependency_cycles": 1 if htn.get("has_cycles") else 0,
            "missing_resources": 1 if not resources.get("key_skills_needed") else 0,
            "duplicate_tasks": len(self._find_duplicate_tasks(milestones)),
            "conflicting_constraints": len(self._find_conflicting_constraints(constraints)),
            "deadline_conflicts": len(self._find_deadline_conflicts(milestones)),
            "execution_feasibility": "feasible" if status == "passed" else "needs_review",
            "validation_timestamp": datetime.utcnow().isoformat(),
        }
    
    def _validate_goal(self, goal: str) -> Dict[str, Any]:
        """Validate goal structure and clarity."""
        issues = []
        if not goal or not goal.strip():
            issues.append("invalid_goal_empty")
        if len(goal) < 5:
            issues.append("goal_too_short")
        if len(goal) > 500:
            issues.append("goal_too_long")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def _validate_tasks(self, milestones: List[Dict]) -> Dict[str, Any]:
        """Validate task structure and completeness."""
        issues = []
        if not milestones:
            issues.append("missing_tasks")
        if len(milestones) > self.plan_config["max_task_count"]:
            issues.append("too_many_tasks")
        
        for task in milestones:
            if not task.get("title"):
                issues.append("task_missing_title")
            if not task.get("estimated_effort"):
                issues.append("task_missing_effort")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def _validate_dependencies(self, dependencies: List[Dict]) -> Dict[str, Any]:
        """Validate task dependencies."""
        issues = []
        for dep in dependencies:
            if dep.get("from") == dep.get("to"):
                issues.append("self_dependency")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def _validate_resources(self, resources: Dict[str, Any]) -> Dict[str, Any]:
        """Validate resource requirements."""
        issues = []
        if not resources.get("key_skills_needed"):
            issues.append("missing_skills")
        if resources.get("recommended_team_size", 0) < 1:
            issues.append("insufficient_team_size")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def _validate_constraints(self, constraints: List[str], task_count: int) -> Dict[str, Any]:
        """Validate constraints against task count."""
        issues = []
        if constraints and len(constraints) > self.plan_config["max_task_count"]:
            issues.append("constraint_pressure_high")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def _validate_deadlines(self, milestones: List[Dict]) -> Dict[str, Any]:
        """Validate deadline feasibility."""
        issues = []
        # Check for tasks without reasonable time estimates
        for task in milestones:
            if task.get("estimated_hours", 0) > 168:  # More than 1 week
                issues.append("unrealistic_deadline")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def _validate_execution_feasibility(self, milestones: List[Dict], resources: Dict[str, Any], constraints: List[str]) -> Dict[str, Any]:
        """Validate overall execution feasibility."""
        issues = []
        total_effort_hours = sum(m.get("estimated_hours", 6) for m in milestones)
        team_size = resources.get("recommended_team_size", 1)
        
        # Simple feasibility check: estimated hours / team size
        hours_per_person = total_effort_hours / max(1, team_size)
        
        if hours_per_person > 40 * 52:  # More than 1 year for single person
            issues.append("scope_too_large")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def _find_duplicate_tasks(self, milestones: List[Dict]) -> List[Dict]:
        """Find duplicate tasks by title."""
        seen = {}
        duplicates = []
        for task in milestones:
            title = task.get("title", "").lower()
            if title in seen:
                duplicates.append({"task_id": task["id"], "duplicate_of": seen[title]})
            else:
                seen[title] = task["id"]
        return duplicates
    
    def _find_conflicting_constraints(self, constraints: List[str]) -> List[Dict]:
        """Find potentially conflicting constraints."""
        conflicts = []
        for i, c1 in enumerate(constraints):
            for c2 in constraints[i+1:]:
                # Simple conflict detection: common negation patterns
                if any(word in c1.lower() for word in ["no", "not", "never"]) and \
                   any(word in c2.lower() for word in ["must", "required", "always"]):
                    conflicts.append({"constraint1": c1, "constraint2": c2})
        return conflicts
    
    def _find_deadline_conflicts(self, milestones: List[Dict]) -> List[Dict]:
        """Find deadline conflicts in task ordering."""
        conflicts = []
        # Check if tasks with higher effort come before tasks with deadline constraints
        for i, task in enumerate(milestones):
            if task.get("estimated_hours", 0) > 20 and i > len(milestones) * 0.7:
                conflicts.append({"task_id": task["id"], "issue": "high_effort_late_in_plan"})
        return conflicts

    def _build_explanation(
        self,
        goal: str,
        milestones: List[Dict],
        resources: Dict[str, Any],
        risks: List[Dict],
        constraints: List[str],
    ) -> Dict[str, Any]:
        """Build comprehensive plan explanation with reasoning."""
        execution_order = [m["title"] for m in milestones]
        strategy = milestones[0].get("decomposition_strategy", "goal_decomposition") if milestones else "goal_decomposition"
        
        # Calculate confidence with multiple factors
        task_confidence = min(0.9, 0.6 + (0.05 * len(milestones)))
        resource_confidence = resources.get("resource_confidence", 0.7)
        risk_factor = max(0.1, 1.0 - (0.1 * min(len(risks), 5)))
        overall_confidence = (task_confidence + resource_confidence + risk_factor) / 3
        
        # Build reasoning narrative
        reasoning_parts = []
        reasoning_parts.append(f"Goal: {goal}")
        reasoning_parts.append(f"Decomposition strategy: {strategy}")
        reasoning_parts.append(f"Task count: {len(milestones)}")
        reasoning_parts.append(f"Critical path: {resources.get('critical_path_hours', 0):.1f} hours")
        reasoning_parts.append(f"Team size: {resources.get('recommended_team_size', 1)}")
        
        # Top 3 risks
        top_risks = [r.get("risk", "") for r in risks[:3]]
        
        # Alternative strategies based on constraints
        alternatives = []
        if len(milestones) > 5:
            alternatives.append("agile_iterative")
        if resources.get("parallelizable_tasks", 0) > 3:
            alternatives.append("parallel_execution")
        if any("urgent" in c.lower() for c in constraints):
            alternatives.append("fast_track")
        if not alternatives:
            alternatives = ["sequential_execution", "phased_execution"]
        
        # Build limitations list
        limitations = []
        if not resources.get("key_skills_needed"):
            limitations.append("Skills requirements not fully specified")
        if len(risks) > 5:
            limitations.append("Multiple high-priority risks identified")
        if len(constraints) > 3:
            limitations.append("Complex constraint interactions may not be fully captured")
        if not constraints:
            limitations.append("Planning lacks external context constraints")
        if not limitations:
            limitations.append("Plan relies on deterministic decomposition assumptions")
        
        return {
            "goal_summary": f"Production delivery plan for: {goal}",
            "planning_strategy": strategy,
            "reasoning_summary": " → ".join(reasoning_parts),
            "dependency_explanation": "Tasks are sequenced with explicit dependencies to preserve execution flow. " +
                                     f"Parallelizable tasks: {resources.get('parallelizable_tasks', 0)}",
            "resource_explanation": f"Team size: {resources.get('recommended_team_size', 1)} members, " +
                                   f"Total effort: {resources.get('total_effort_hours', 0):.0f} hours, " +
                                   f"Key skills: {', '.join(resources.get('key_skills_needed', []))}",
            "risk_explanation": f"Top risks: {', '.join(top_risks[:3])}. " +
                               f"Overall risk score: {round(max((r.get('score', 0) for r in risks), default=0), 2)}",
            "execution_order": execution_order,
            "critical_path": resources.get("critical_path_hours", 0),
            "confidence": round(overall_confidence, 3),
            "confidence_factors": {
                "task_decomposition": round(task_confidence, 3),
                "resource_planning": round(resource_confidence, 3),
                "risk_mitigation": round(risk_factor, 3),
            },
            "limitations": limitations,
            "alternative_plans_considered": alternatives,
            "created_at": datetime.utcnow().isoformat(),
        }

    def _decompose_goal(self, goal: str, timeframe: str = None) -> List[Dict]:
        """Decompose goal into hierarchical tasks using strategy-based decomposition."""
        lower = goal.lower()
        strategy = self._determine_decomposition_strategy(goal)
        
        # Strategy-based phase generation
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
        
        # Create tasks with extended metadata
        tasks = []
        for i, phase in enumerate(phases):
            task_id = f"task-{uuid.uuid4().hex[:8]}"
            effort = "high" if any(w in phase.lower() for w in ["implement", "execute", "develop"]) else "medium" if any(w in phase.lower() for w in ["design", "test"]) else "low"
            effort_hours = {"high": 12, "medium": 6, "low": 3}.get(effort, 6)
            
            tasks.append({
                "id": task_id,
                "order": i + 1,
                "title": phase,
                "description": f"Complete '{phase}' for: {goal}",
                "status": "pending",
                "estimated_effort": effort,
                "estimated_hours": effort_hours,
                "success_criteria": f"{phase} deliverables completed and validated",
                "decomposition_strategy": strategy,
                "dependencies": [tasks[i-1]["id"]] if i > 0 else [],
                "parallel_capable": False,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            })
        
        return tasks
    
    def _determine_decomposition_strategy(self, goal: str) -> str:
        """Determine optimal decomposition strategy based on goal characteristics."""
        lower = goal.lower()
        
        if any(w in lower for w in ["parallel", "concurrent", "simultaneous"]):
            return "parallel"
        elif any(w in lower for w in ["phased", "staged", "iterative"]):
            return "phased"
        elif any(w in lower for w in ["urgent", "critical", "asap", "immediately"]):
            return "priority_driven"
        elif len(goal.split()) > 20:
            return "complexity_aware"
        else:
            return "goal_decomposition"

    def _identify_risks(self, goal: str, constraints: List[str]) -> List[Dict]:
        """Identify and score risks across multiple categories."""
        risks = []
        
        # Technical risks
        risks.extend(self._identify_technical_risks(goal))
        
        # Execution risks
        risks.extend(self._identify_execution_risks(goal))
        
        # Dependency risks
        risks.extend(self._identify_dependency_risks(goal))
        
        # Resource risks
        risks.extend(self._identify_resource_risks(goal))
        
        # Deadline risks
        risks.extend(self._identify_deadline_risks(goal))
        
        # Constraint-based risks
        if constraints:
            risks.extend(self._identify_constraint_risks(constraints))
        
        # Score and rank risks
        for risk in risks:
            risk["score"] = self._calculate_risk_score(risk)
        
        # Sort by score (highest first)
        risks.sort(key=lambda r: r.get("score", 0), reverse=True)
        
        return risks[:self.plan_config.get("max_risks", 10)]
    
    def _identify_technical_risks(self, goal: str) -> List[Dict]:
        """Identify technical implementation risks."""
        risks = []
        lower = goal.lower()
        
        if any(w in lower for w in ["integration", "third-party", "external", "api"]):
            risks.append({
                "category": "technical",
                "risk": "Third-party API integration failures",
                "probability": 0.3,
                "impact": 0.7,
                "mitigation": "Implement fallback mechanisms and version pinning",
                "severity": "high",
            })
        
        if any(w in lower for w in ["data", "database", "migration"]):
            risks.append({
                "category": "technical",
                "risk": "Data integrity and migration issues",
                "probability": 0.2,
                "impact": 0.9,
                "mitigation": "Comprehensive backup strategy and rollback testing",
                "severity": "critical",
            })
        
        if any(w in lower for w in ["performance", "scale", "load", "concurrent"]):
            risks.append({
                "category": "technical",
                "risk": "Performance degradation under load",
                "probability": 0.4,
                "impact": 0.6,
                "mitigation": "Load testing and monitoring infrastructure setup",
                "severity": "high",
            })
        
        return risks
    
    def _identify_execution_risks(self, goal: str) -> List[Dict]:
        """Identify execution and scheduling risks."""
        risks = [
            {
                "category": "execution",
                "risk": "Timeline slippage",
                "probability": 0.5,
                "impact": 0.6,
                "mitigation": "Build 20-30% buffer into each milestone",
                "severity": "medium",
            }
        ]
        
        lower = goal.lower()
        if any(w in lower for w in ["urgent", "critical", "asap", "immediately"]):
            risks.append({
                "category": "execution",
                "risk": "Rushed implementation causing quality issues",
                "probability": 0.6,
                "impact": 0.7,
                "mitigation": "Prioritize code review and testing over speed",
                "severity": "high",
            })
        
        return risks
    
    def _identify_dependency_risks(self, goal: str) -> List[Dict]:
        """Identify task dependency and blocking risks."""
        risks = []
        lower = goal.lower()
        
        if any(w in lower for w in ["parallel", "concurrent"]):
            risks.append({
                "category": "dependency",
                "risk": "Parallel task synchronization failures",
                "probability": 0.3,
                "impact": 0.6,
                "mitigation": "Define clear synchronization points and mutexes",
                "severity": "medium",
            })
        
        return risks
    
    def _identify_resource_risks(self, goal: str) -> List[Dict]:
        """Identify resource allocation and availability risks."""
        risks = [
            {
                "category": "resource",
                "risk": "Insufficient team capacity",
                "probability": 0.3,
                "impact": 0.8,
                "mitigation": "Pre-allocate resources and define escalation paths",
                "severity": "high",
            }
        ]
        
        lower = goal.lower()
        if any(w in lower for w in ["specialized", "expert", "niche"]):
            risks.append({
                "category": "resource",
                "risk": "Lack of specialized expertise",
                "probability": 0.4,
                "impact": 0.7,
                "mitigation": "Training programs and knowledge transfer sessions",
                "severity": "high",
            })
        
        return risks
    
    def _identify_deadline_risks(self, goal: str) -> List[Dict]:
        """Identify deadline and time-constraint risks."""
        risks = []
        lower = goal.lower()
        
        if any(w in lower for w in ["month", "week", "day", "hours"]):
            risks.append({
                "category": "deadline",
                "risk": "Compressed timeline constraints",
                "probability": 0.5,
                "impact": 0.7,
                "mitigation": "Scope prioritization and MVP definition",
                "severity": "high",
            })
        
        return risks
    
    def _identify_constraint_risks(self, constraints: List[str]) -> List[Dict]:
        """Identify constraint conflict and violation risks."""
        risks = []
        
        if len(constraints) > 5:
            risks.append({
                "category": "constraint",
                "risk": f"High constraint density ({len(constraints)} constraints)",
                "probability": 0.4,
                "impact": 0.6,
                "mitigation": "Regular constraint review and prioritization",
                "severity": "medium",
            })
        
        if any("incompatible" in c.lower() or "conflicting" in c.lower() for c in constraints):
            risks.append({
                "category": "constraint",
                "risk": "Conflicting constraints may be unresolvable",
                "probability": 0.3,
                "impact": 0.8,
                "mitigation": "Constraint negotiation and trade-off analysis",
                "severity": "high",
            })
        
        return risks
    
    def _calculate_risk_score(self, risk: Dict) -> float:
        """Calculate risk score using probability × impact formula."""
        probability = risk.get("probability", 0.5)
        impact = risk.get("impact", 0.5)
        
        if isinstance(probability, str):
            probability = {"low": 0.2, "medium": 0.5, "high": 0.8}.get(probability, 0.5)
        if isinstance(impact, str):
            impact = {"low": 0.2, "medium": 0.5, "high": 0.8}.get(impact, 0.5)
        
        score = probability * impact
        
        # Normalize to 0-1 range
        return min(1.0, max(0.0, score))

    def _estimate_resources(self, goal: str, milestones: List[Dict]) -> Dict:
        """Estimate resource requirements with detailed breakdown."""
        high = sum(1 for m in milestones if m.get("estimated_effort") == "high")
        medium = sum(1 for m in milestones if m.get("estimated_effort") == "medium")
        low = sum(1 for m in milestones if m.get("estimated_effort") == "low")
        
        # Calculate total effort in hours
        total_hours = sum(m.get("estimated_hours", 6) for m in milestones)
        
        # Estimate resource requirements
        estimated_effort_units = high * 3 + medium * 2 + low * 1
        
        # Recommend team size based on effort
        base_team_size = max(1, (high + 1) // 2)
        parallelizable_tasks = sum(1 for m in milestones if m.get("parallel_capable", False))
        optimal_team_size = base_team_size + (parallelizable_tasks // 3)
        
        # Calculate resource allocation
        resource_per_task = total_hours / max(1, optimal_team_size)
        
        # Confidence calculation
        task_confidence = 0.6 + (0.05 * min(len(milestones), 5))
        effort_confidence = 0.7 if estimated_effort_units > 0 else 0.5
        resource_confidence = (task_confidence + effort_confidence) / 2
        
        return {
            "total_effort_hours": total_hours,
            "estimated_effort_units": estimated_effort_units,
            "effort_breakdown": {
                "high_effort_tasks": high,
                "medium_effort_tasks": medium,
                "low_effort_tasks": low,
            },
            "recommended_team_size": optimal_team_size,
            "hours_per_team_member": round(resource_per_task, 1),
            "key_skills_needed": self._extract_skills(goal),
            "resource_confidence": round(max(0.0, min(1.0, resource_confidence)), 3),
            "parallelizable_tasks": parallelizable_tasks,
            "critical_path_hours": self._estimate_critical_path(milestones),
            "resource_allocation": self._estimate_resource_allocation(milestones, optimal_team_size),
        }
    
    def _estimate_critical_path(self, milestones: List[Dict]) -> float:
        """Estimate critical path (longest sequential chain) in hours."""
        if not milestones:
            return 0.0
        
        # Simple critical path: sum of all sequential tasks (ignoring parallel)
        total = 0.0
        for milestone in milestones:
            if not milestone.get("parallel_capable", False):
                total += milestone.get("estimated_hours", 6)
        
        return total
    
    def _estimate_resource_allocation(self, milestones: List[Dict], team_size: int) -> Dict:
        """Estimate resource allocation across tasks."""
        allocation = {
            "frontend_development": 0,
            "backend_development": 0,
            "testing": 0,
            "documentation": 0,
            "project_management": 0,
            "devops_infrastructure": 0,
        }
        
        for milestone in milestones:
            title_lower = milestone.get("title", "").lower()
            hours = milestone.get("estimated_hours", 6)
            
            if any(w in title_lower for w in ["ui", "ux", "design", "frontend"]):
                allocation["frontend_development"] += hours * 0.6
            if any(w in title_lower for w in ["backend", "api", "database"]):
                allocation["backend_development"] += hours * 0.6
            if any(w in title_lower for w in ["test", "validation", "qa"]):
                allocation["testing"] += hours * 0.7
            if any(w in title_lower for w in ["document", "readme", "guide"]):
                allocation["documentation"] += hours * 0.8
            if any(w in title_lower for w in ["launch", "deploy", "monitor"]):
                allocation["devops_infrastructure"] += hours * 0.5
            
            # Project management overhead (10% of all tasks)
            allocation["project_management"] += hours * 0.1
        
        return allocation

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

    async def adapt_plan(self, plan_id: str, changes: Dict[str, Any]) -> Dict:
        """Adaptively update plan based on execution feedback."""
        plan = self.active_plans.get(plan_id)
        if not plan:
            return {"error": "Plan not found"}
        
        # Capture adapter state
        plan["plan_state"]["adapted_at"] = datetime.utcnow().isoformat()
        plan["plan_state"]["adaptations_count"] = plan["plan_state"].get("adaptations_count", 0) + 1
        
        # Apply individual changes
        if "goal" in changes:
            plan["goal"] = changes["goal"]
        if "constraints" in changes:
            plan["constraints"].extend(changes["constraints"])
        if "resources" in changes:
            plan["plan_context"]["resources"] = changes["resources"]
        
        # Recalculate affected sections without full replan
        updated_at = datetime.utcnow().isoformat()
        plan["updated_at"] = updated_at
        plan["plan_state"]["status"] = "adapted"
        
        # Log adaptation
        plan["plan_audit"].append({
            "event": "plan_adapted",
            "timestamp": updated_at,
            "plan_id": plan_id,
            "changes": list(changes.keys()),
        })
        
        return plan
    
    async def get_plan_progress(self, plan_id: str) -> Dict:
        """Get detailed progress metrics for a plan."""
        plan = self.active_plans.get(plan_id)
        if not plan:
            completed_plan = next((p for p in self.completed_plans if p["id"] == plan_id), None)
            if not completed_plan:
                return {"error": "Plan not found"}
            plan = completed_plan
        
        state = plan.get("plan_state", {})
        milestones = plan.get("milestones", [])
        
        completed_count = sum(1 for m in milestones if m.get("status") == "completed")
        failed_count = sum(1 for m in milestones if m.get("status") == "failed")
        cancelled_count = sum(1 for m in milestones if m.get("status") == "cancelled")
        blocked_count = sum(1 for m in milestones if m.get("status") == "blocked")
        waiting_count = sum(1 for m in milestones if m.get("status") == "waiting")
        running_count = sum(1 for m in milestones if m.get("status") == "running")
        
        total_hours = sum(m.get("estimated_hours", 6) for m in milestones)
        completed_hours = sum(m.get("estimated_hours", 6) for m in milestones if m.get("status") == "completed")
        
        return {
            "plan_id": plan_id,
            "goal": plan.get("goal"),
            "status": plan.get("status"),
            "overall_progress": state.get("progress", 0.0),
            "task_breakdown": {
                "total": len(milestones),
                "completed": completed_count,
                "failed": failed_count,
                "cancelled": cancelled_count,
                "blocked": blocked_count,
                "waiting": waiting_count,
                "running": running_count,
                "pending": len(milestones) - (completed_count + failed_count + cancelled_count + blocked_count + waiting_count + running_count),
            },
            "effort_metrics": {
                "total_estimated_hours": total_hours,
                "completed_hours": completed_hours,
                "progress_percentage": round((completed_hours / total_hours * 100) if total_hours > 0 else 0, 1),
            },
            "execution_health": self._assess_plan_health(plan),
            "created_at": plan.get("created_at"),
            "updated_at": plan.get("updated_at"),
        }
    
    def _assess_plan_health(self, plan: Dict) -> Dict:
        """Assess overall health of a plan."""
        state = plan.get("plan_state", {})
        risks = plan.get("risks", [])
        milestones = plan.get("milestones", [])
        
        failed_count = sum(1 for m in milestones if m.get("status") == "failed")
        blocked_count = sum(1 for m in milestones if m.get("status") == "blocked")
        
        # Health score calculation
        failure_rate = failed_count / len(milestones) if milestones else 0
        blockage_rate = blocked_count / len(milestones) if milestones else 0
        risk_score = max((r.get("score", 0) for r in risks), default=0)
        
        health_score = max(0, 1.0 - (failure_rate * 0.3 + blockage_rate * 0.3 + risk_score * 0.4))
        
        if health_score > 0.8:
            status = "healthy"
        elif health_score > 0.6:
            status = "at_risk"
        elif health_score > 0.4:
            status = "poor"
        else:
            status = "critical"
        
        return {
            "status": status,
            "score": round(health_score, 3),
            "failure_rate": round(failure_rate, 3),
            "blockage_rate": round(blockage_rate, 3),
            "risk_exposure": round(risk_score, 3),
        }
    
    async def get_plan_analytics(self, plan_id: str = None) -> Dict:
        """Get comprehensive analytics for one or all plans."""
        if plan_id:
            plans = [self.active_plans.get(plan_id)] if plan_id in self.active_plans else []
            if not plans and any(p["id"] == plan_id for p in self.completed_plans):
                plans = [next(p for p in self.completed_plans if p["id"] == plan_id)]
        else:
            plans = list(self.active_plans.values()) + self.completed_plans
        
        if not plans:
            return {"error": "No plans found"}
        
        total_goals = len(plans)
        completed_goals = sum(1 for p in plans if p.get("status") == "completed")
        total_tasks = sum(len(p.get("milestones", [])) for p in plans)
        total_risks = sum(len(p.get("risks", [])) for p in plans)
        
        avg_confidence = sum(p.get("explanation", {}).get("confidence", 0.7) for p in plans) / len(plans) if plans else 0
        
        return {
            "total_plans": total_goals,
            "completed_plans": completed_goals,
            "active_plans": len(self.active_plans),
            "total_tasks": total_tasks,
            "total_risks": total_risks,
            "average_confidence": round(avg_confidence, 3),
            "plans": [
                {
                    "plan_id": p["id"],
                    "goal": p.get("goal"),
                    "status": p.get("status"),
                    "progress": p.get("progress", 0),
                    "task_count": len(p.get("milestones", [])),
                    "confidence": p.get("explanation", {}).get("confidence", 0),
                }
                for p in plans
            ],
        }

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {})
        
        # Plan creation and management
        if action in ("create", "plan", "create_plan"):
            return await self.create_plan(
                goal=data.get("goal", data.get("content", "")),
                timeframe=data.get("timeframe"),
                constraints=data.get("constraints", []),
                context=data.get("context") or {},
            )
        
        # Milestone updates and execution tracking
        if action == "update_milestone":
            return await self.update_milestone(
                data.get("plan_id", ""),
                data.get("milestone_id", ""),
                data.get("status", "completed")
            )
        
        # Dynamic replanning
        if action == "replan":
            return await self.replan(
                plan_id=data.get("plan_id", ""),
                goal=data.get("goal"),
                timeframe=data.get("timeframe"),
                constraints=data.get("constraints", []),
                context=data.get("context") or {},
            )
        
        # Adaptive plan updates
        if action == "adapt_plan":
            return await self.adapt_plan(
                data.get("plan_id", ""),
                data.get("changes", {})
            )
        
        # Plan retrieval
        if action == "get_plan":
            plan = self.active_plans.get(data.get("plan_id", ""))
            if plan:
                return plan
            completed = next((p for p in self.completed_plans if p.get("id") == data.get("plan_id")), None)
            return completed or {"error": "Plan not found"}
        
        # Plan listing
        if action == "list_plans":
            return {
                "active": list(self.active_plans.values()),
                "completed": self.completed_plans[-10:],
                "total_active": len(self.active_plans),
                "total_completed": len(self.completed_plans),
            }
        
        # Progress tracking
        if action == "get_progress":
            return await self.get_plan_progress(data.get("plan_id", ""))
        
        # Analytics
        if action == "get_analytics":
            return await self.get_plan_analytics(data.get("plan_id"))
        
        # Default: create plan from goal
        return await self.create_plan(
            goal=data.get("content", data.get("goal", "achieve the objective")),
            timeframe=data.get("timeframe")
        )
