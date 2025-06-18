import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from structlog import get_logger

from .base_agent import BaseAgent
from ..config import settings

logger = get_logger()

class LearningAgent(BaseAgent):
    """Agent responsible for learning and adaptation."""
    
    def __init__(self, agent_id: str):
        """Initialize the learning agent."""
        super().__init__(agent_id, "learning")
        self.knowledge_base: Dict[str, Any] = {}
        self.learning_patterns: Dict[str, List[Dict]] = {}
        self.adaptation_history: List[Dict] = []
        self.learning_rate = 0.1
        self.max_patterns = 1000
    
    async def initialize(self):
        """Initialize the learning agent."""
        await super().initialize()
        
        # Initialize learning-specific state
        self.state.update({
            "knowledge_base_size": 0,
            "pattern_count": 0,
            "adaptation_count": 0,
            "last_learning": datetime.utcnow().isoformat(),
            "success_rate": 0.0
        })
        
        logger.info(f"Learning agent {self.agent_id} initialized")
    
    async def _process_messages(self):
        """Process incoming messages."""
        # Process learning-related messages
        # This would typically involve receiving messages from the communication bus
        pass
    
    async def _update_state(self):
        """Update agent state."""
        self.state.update({
            "knowledge_base_size": len(self.knowledge_base),
            "pattern_count": len(self.learning_patterns),
            "last_active": datetime.utcnow().isoformat()
        })
    
    async def _process_emotions(self):
        """Process and update emotions based on learning progress."""
        # Calculate learning progress
        recent_adaptations = self.adaptation_history[-10:]  # Last 10 adaptations
        success_rate = sum(1 for a in recent_adaptations if a["success"]) / len(recent_adaptations) if recent_adaptations else 0.0
        
        # Update emotions based on learning success
        if success_rate > 0.7:
            await self.update_emotion("happiness", min(1.0, self.emotions["happiness"] + 0.1))
        elif success_rate < 0.3:
            await self.update_emotion("frustration", min(1.0, self.emotions["frustration"] + 0.1))
    
    async def _maintain_connections(self):
        """Maintain connections with other agents."""
        # Check for learning-related connections
        # This would typically involve communicating with other agents
        pass
    
    async def learn_from_experience(self, experience: Dict):
        """Learn from a new experience."""
        # Extract patterns from experience
        patterns = self._extract_patterns(experience)
        
        # Update knowledge base
        for pattern in patterns:
            await self._update_knowledge(pattern)
        
        # Record adaptation
        adaptation = {
            "timestamp": datetime.utcnow().isoformat(),
            "experience_id": experience.get("id"),
            "patterns": patterns,
            "success": experience.get("success", True)
        }
        self.adaptation_history.append(adaptation)
        
        # Update state
        self.state["adaptation_count"] += 1
        self.state["last_learning"] = datetime.utcnow().isoformat()
        
        logger.info(f"Learned from experience: {experience.get('id')}")
    
    def _extract_patterns(self, experience: Dict) -> List[Dict]:
        """Extract learning patterns from an experience."""
        patterns = []
        
        # Extract basic patterns
        if "action" in experience and "outcome" in experience:
            pattern = {
                "type": "action_outcome",
                "action": experience["action"],
                "outcome": experience["outcome"],
                "context": experience.get("context", {}),
                "confidence": 0.5
            }
            patterns.append(pattern)
        
        # Extract temporal patterns
        if "sequence" in experience:
            pattern = {
                "type": "temporal",
                "sequence": experience["sequence"],
                "duration": experience.get("duration"),
                "confidence": 0.5
            }
            patterns.append(pattern)
        
        # Extract causal patterns
        if "cause" in experience and "effect" in experience:
            pattern = {
                "type": "causal",
                "cause": experience["cause"],
                "effect": experience["effect"],
                "confidence": 0.5
            }
            patterns.append(pattern)
        
        return patterns
    
    async def _update_knowledge(self, pattern: Dict):
        """Update the knowledge base with a new pattern."""
        pattern_type = pattern["type"]
        
        if pattern_type not in self.knowledge_base:
            self.knowledge_base[pattern_type] = {}
        
        # Update pattern in knowledge base
        if pattern_type == "action_outcome":
            key = f"{pattern['action']}_{pattern['outcome']}"
            if key in self.knowledge_base[pattern_type]:
                # Update existing pattern
                existing = self.knowledge_base[pattern_type][key]
                existing["confidence"] = (existing["confidence"] * 0.7 + pattern["confidence"] * 0.3)
                existing["count"] += 1
            else:
                # Add new pattern
                pattern["count"] = 1
                self.knowledge_base[pattern_type][key] = pattern
        
        # Update learning patterns
        if pattern_type not in self.learning_patterns:
            self.learning_patterns[pattern_type] = []
        
        self.learning_patterns[pattern_type].append(pattern)
        
        # Maintain pattern limit
        if len(self.learning_patterns[pattern_type]) > self.max_patterns:
            self.learning_patterns[pattern_type] = self.learning_patterns[pattern_type][-self.max_patterns:]
    
    async def apply_learning(self, situation: Dict) -> Dict:
        """Apply learned knowledge to a new situation."""
        result = {
            "action": None,
            "confidence": 0.0,
            "explanation": []
        }
        
        # Find relevant patterns
        relevant_patterns = self._find_relevant_patterns(situation)
        
        if relevant_patterns:
            # Select best pattern
            best_pattern = max(relevant_patterns, key=lambda p: p["confidence"])
            
            # Apply pattern
            if best_pattern["type"] == "action_outcome":
                result["action"] = best_pattern["action"]
                result["confidence"] = best_pattern["confidence"]
                result["explanation"].append(f"Based on previous experience with {best_pattern['action']}")
        
        return result
    
    def _find_relevant_patterns(self, situation: Dict) -> List[Dict]:
        """Find patterns relevant to the current situation."""
        relevant_patterns = []
        
        # Search in knowledge base
        for pattern_type, patterns in self.knowledge_base.items():
            for pattern in patterns.values():
                if self._is_pattern_relevant(pattern, situation):
                    relevant_patterns.append(pattern)
        
        return relevant_patterns
    
    def _is_pattern_relevant(self, pattern: Dict, situation: Dict) -> bool:
        """Check if a pattern is relevant to the current situation."""
        if pattern["type"] == "action_outcome":
            # Check if action is applicable
            return self._check_action_applicability(pattern["action"], situation)
        elif pattern["type"] == "temporal":
            # Check if sequence matches
            return self._check_sequence_match(pattern["sequence"], situation)
        elif pattern["type"] == "causal":
            # Check if cause matches
            return self._check_cause_match(pattern["cause"], situation)
        
        return False
    
    def _check_action_applicability(self, action: Dict, situation: Dict) -> bool:
        """Check if an action is applicable to the current situation."""
        # Simple implementation - can be enhanced
        return all(k in situation for k in action.get("requirements", []))
    
    def _check_sequence_match(self, sequence: List, situation: Dict) -> bool:
        """Check if a sequence matches the current situation."""
        # Simple implementation - can be enhanced
        return all(s in situation.get("sequence", []) for s in sequence)
    
    def _check_cause_match(self, cause: Dict, situation: Dict) -> bool:
        """Check if a cause matches the current situation."""
        # Simple implementation - can be enhanced
        return all(k in situation for k in cause.keys())
    
    async def get_learning_stats(self) -> Dict:
        """Get learning statistics."""
        return {
            "knowledge_base_size": len(self.knowledge_base),
            "pattern_count": sum(len(patterns) for patterns in self.learning_patterns.values()),
            "adaptation_count": len(self.adaptation_history),
            "success_rate": self.state["success_rate"],
            "last_learning": self.state["last_learning"]
        }
    
    async def clear_learning(self):
        """Clear all learned knowledge."""
        self.knowledge_base.clear()
        self.learning_patterns.clear()
        self.adaptation_history.clear()
        self.state.update({
            "knowledge_base_size": 0,
            "pattern_count": 0,
            "adaptation_count": 0,
            "success_rate": 0.0
        })
        logger.info(f"Cleared all learning for agent {self.agent_id}") 