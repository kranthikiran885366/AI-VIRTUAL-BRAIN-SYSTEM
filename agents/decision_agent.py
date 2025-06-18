import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from structlog import get_logger

from .base_agent import BaseAgent
from ..config import settings

logger = get_logger()

class DecisionAgent(BaseAgent):
    """Agent responsible for decision making and action selection."""
    
    def __init__(self, agent_id: str):
        """Initialize the decision agent."""
        super().__init__(agent_id, "decision")
        self.decision_history: List[Dict] = []
        self.action_space: Dict[str, Dict] = {}
        self.decision_rules: Dict[str, List[Dict]] = {}
        self.exploration_rate = 0.1
        self.max_history = 1000
    
    async def initialize(self):
        """Initialize the decision agent."""
        await super().initialize()
        
        # Initialize decision-specific state
        self.state.update({
            "decision_count": 0,
            "success_rate": 0.0,
            "last_decision": datetime.utcnow().isoformat(),
            "exploration_rate": self.exploration_rate
        })
        
        logger.info(f"Decision agent {self.agent_id} initialized")
    
    async def _process_messages(self):
        """Process incoming messages."""
        # Process decision-related messages
        # This would typically involve receiving messages from the communication bus
        pass
    
    async def _update_state(self):
        """Update agent state."""
        self.state.update({
            "decision_count": len(self.decision_history),
            "last_active": datetime.utcnow().isoformat()
        })
    
    async def _process_emotions(self):
        """Process and update emotions based on decision outcomes."""
        # Calculate decision success rate
        recent_decisions = self.decision_history[-10:]  # Last 10 decisions
        success_rate = sum(1 for d in recent_decisions if d["success"]) / len(recent_decisions) if recent_decisions else 0.0
        
        # Update emotions based on decision success
        if success_rate > 0.7:
            await self.update_emotion("confidence", min(1.0, self.emotions["confidence"] + 0.1))
        elif success_rate < 0.3:
            await self.update_emotion("uncertainty", min(1.0, self.emotions["uncertainty"] + 0.1))
    
    async def _maintain_connections(self):
        """Maintain connections with other agents."""
        # Check for decision-related connections
        # This would typically involve communicating with other agents
        pass
    
    async def make_decision(self, context: Dict) -> Dict:
        """Make a decision based on the current context."""
        # Evaluate available actions
        available_actions = self._evaluate_actions(context)
        
        # Apply decision rules
        filtered_actions = self._apply_decision_rules(available_actions, context)
        
        # Select action
        selected_action = await self._select_action(filtered_actions, context)
        
        # Record decision
        decision = {
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
            "action": selected_action,
            "confidence": selected_action.get("confidence", 0.0),
            "explanation": selected_action.get("explanation", []),
            "success": None  # Will be updated when outcome is known
        }
        self.decision_history.append(decision)
        
        # Update state
        self.state["decision_count"] += 1
        self.state["last_decision"] = datetime.utcnow().isoformat()
        
        logger.info(f"Made decision: {selected_action.get('action_id')}")
        return decision
    
    def _evaluate_actions(self, context: Dict) -> List[Dict]:
        """Evaluate available actions in the current context."""
        available_actions = []
        
        for action_id, action in self.action_space.items():
            # Check if action is applicable
            if self._is_action_applicable(action, context):
                # Calculate action score
                score = self._calculate_action_score(action, context)
                
                action_info = {
                    "action_id": action_id,
                    "action": action,
                    "score": score,
                    "confidence": 0.5,  # Initial confidence
                    "explanation": []
                }
                available_actions.append(action_info)
        
        return available_actions
    
    def _is_action_applicable(self, action: Dict, context: Dict) -> bool:
        """Check if an action is applicable in the current context."""
        # Check prerequisites
        if "prerequisites" in action:
            for prereq in action["prerequisites"]:
                if not self._check_prerequisite(prereq, context):
                    return False
        
        # Check constraints
        if "constraints" in action:
            for constraint in action["constraints"]:
                if not self._check_constraint(constraint, context):
                    return False
        
        return True
    
    def _check_prerequisite(self, prereq: Dict, context: Dict) -> bool:
        """Check if a prerequisite is met."""
        # Simple implementation - can be enhanced
        return all(k in context for k in prereq.get("required_keys", []))
    
    def _check_constraint(self, constraint: Dict, context: Dict) -> bool:
        """Check if a constraint is satisfied."""
        # Simple implementation - can be enhanced
        return all(context.get(k) == v for k, v in constraint.get("conditions", {}).items())
    
    def _calculate_action_score(self, action: Dict, context: Dict) -> float:
        """Calculate a score for an action in the current context."""
        score = 0.0
        
        # Consider action utility
        if "utility" in action:
            score += action["utility"]
        
        # Consider context relevance
        if "context_relevance" in action:
            relevance = self._calculate_context_relevance(action["context_relevance"], context)
            score += relevance
        
        # Consider historical success
        if "historical_success" in action:
            score += action["historical_success"]
        
        return score
    
    def _calculate_context_relevance(self, relevance_rules: Dict, context: Dict) -> float:
        """Calculate how relevant an action is to the current context."""
        relevance = 0.0
        
        for rule in relevance_rules.get("rules", []):
            if self._evaluate_relevance_rule(rule, context):
                relevance += rule.get("weight", 1.0)
        
        return min(1.0, relevance)
    
    def _evaluate_relevance_rule(self, rule: Dict, context: Dict) -> bool:
        """Evaluate a relevance rule against the context."""
        # Simple implementation - can be enhanced
        return all(context.get(k) == v for k, v in rule.get("conditions", {}).items())
    
    def _apply_decision_rules(self, actions: List[Dict], context: Dict) -> List[Dict]:
        """Apply decision rules to filter and modify actions."""
        filtered_actions = actions.copy()
        
        for rule in self.decision_rules.get("rules", []):
            if self._is_rule_applicable(rule, context):
                filtered_actions = self._apply_rule(rule, filtered_actions, context)
        
        return filtered_actions
    
    def _is_rule_applicable(self, rule: Dict, context: Dict) -> bool:
        """Check if a decision rule is applicable."""
        # Simple implementation - can be enhanced
        return all(context.get(k) == v for k, v in rule.get("conditions", {}).items())
    
    def _apply_rule(self, rule: Dict, actions: List[Dict], context: Dict) -> List[Dict]:
        """Apply a decision rule to the actions."""
        if rule["type"] == "filter":
            # Filter out actions that don't match the rule
            return [a for a in actions if self._matches_rule(a, rule)]
        elif rule["type"] == "modify":
            # Modify action scores based on the rule
            for action in actions:
                if self._matches_rule(action, rule):
                    action["score"] *= rule.get("multiplier", 1.0)
            return actions
        return actions
    
    def _matches_rule(self, action: Dict, rule: Dict) -> bool:
        """Check if an action matches a rule."""
        # Simple implementation - can be enhanced
        return all(action["action"].get(k) == v for k, v in rule.get("action_conditions", {}).items())
    
    async def _select_action(self, actions: List[Dict], context: Dict) -> Dict:
        """Select an action from the available options."""
        if not actions:
            return {
                "action_id": "no_action",
                "action": {"type": "no_action"},
                "confidence": 0.0,
                "explanation": ["No applicable actions found"]
            }
        
        # Exploration vs exploitation
        if self._should_explore():
            # Select random action
            selected = actions[0]  # Simplified random selection
            selected["explanation"].append("Selected through exploration")
        else:
            # Select best action
            selected = max(actions, key=lambda x: x["score"])
            selected["explanation"].append("Selected based on highest score")
        
        return selected
    
    def _should_explore(self) -> bool:
        """Determine if the agent should explore or exploit."""
        return self.exploration_rate > 0 and self.exploration_rate > self._get_random_value()
    
    def _get_random_value(self) -> float:
        """Get a random value between 0 and 1."""
        # Simple implementation - can be enhanced
        return 0.5  # Placeholder
    
    async def update_decision_outcome(self, decision_id: str, outcome: Dict):
        """Update the outcome of a decision."""
        for decision in self.decision_history:
            if decision["action"]["action_id"] == decision_id:
                decision["success"] = outcome.get("success", False)
                decision["outcome"] = outcome
                
                # Update action space
                if decision_id in self.action_space:
                    self._update_action_space(decision_id, outcome)
                
                logger.info(f"Updated decision outcome: {decision_id}")
                break
    
    def _update_action_space(self, action_id: str, outcome: Dict):
        """Update the action space based on decision outcome."""
        action = self.action_space[action_id]
        
        # Update historical success
        if "historical_success" not in action:
            action["historical_success"] = 0.0
        
        # Update success rate
        success = outcome.get("success", False)
        action["historical_success"] = (action["historical_success"] * 0.7 + (1.0 if success else 0.0) * 0.3)
    
    async def add_action(self, action: Dict):
        """Add a new action to the action space."""
        action_id = action.get("action_id", str(uuid.uuid4()))
        self.action_space[action_id] = action
        logger.info(f"Added new action: {action_id}")
    
    async def add_decision_rule(self, rule: Dict):
        """Add a new decision rule."""
        if "rules" not in self.decision_rules:
            self.decision_rules["rules"] = []
        
        self.decision_rules["rules"].append(rule)
        logger.info("Added new decision rule")
    
    async def get_decision_stats(self) -> Dict:
        """Get decision statistics."""
        return {
            "decision_count": len(self.decision_history),
            "success_rate": self.state["success_rate"],
            "action_count": len(self.action_space),
            "rule_count": len(self.decision_rules.get("rules", [])),
            "last_decision": self.state["last_decision"]
        }
    
    async def clear_decisions(self):
        """Clear all decision history."""
        self.decision_history.clear()
        self.state.update({
            "decision_count": 0,
            "success_rate": 0.0
        })
        logger.info(f"Cleared all decisions for agent {self.agent_id}") 