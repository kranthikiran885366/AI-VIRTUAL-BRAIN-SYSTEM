"""
Phase 8: Response Engine for Production Motivation System

Implements:
- Configuration-driven response templates
- Adaptive response generation based on struggle context
- Contextual variable substitution
- Response effectiveness tracking
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from .goal_engine import StruggleContext, StruggleType

logger = logging.getLogger(__name__)


@dataclass
class MotivationResponse:
    """A generated motivation response."""
    id: str
    text: str
    struggle_type: str
    confidence: float
    strategy: str  # The strategy used to generate this
    metadata: Dict[str, Any]


class ResponseEngine:
    """
    Generates adaptive motivation responses based on struggle context.
    
    Responsibilities:
    - Load response templates from configuration
    - Generate contextual responses
    - Track effectiveness
    - Perform variable substitution
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the response engine."""
        self.config = config or self._default_config()
        self._response_templates = self.config.get("motivation_responses", {})
        self._effectiveness_history: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default response configuration."""
        return {
            "motivation_responses": {
                "motivation_low": [
                    "I understand you're feeling unmotivated right now. Let's break this down into smaller, more manageable steps. What's one small thing you could do right now?",
                    "Feeling low on motivation is natural. Remember why you started this goal. What was that initial spark?",
                    "Energy is low, I get it. What if we focus on just the next 10 minutes? You might build momentum from there.",
                    "Your motivation dip is temporary. Let's try doing something you enjoy first to build energy, then tackle this.",
                ],
                "time_pressure": [
                    "Time is tight! Let's focus on the most critical parts first. What's the minimum viable outcome?",
                    "Deadline pressure? That's a sign this matters. What's the absolute deadline and what can we achieve by then?",
                    "We're in crunch time. Let's prioritize ruthlessly. What are the top 3 things that must get done?",
                    "Time pressure can be paralyzing. Let's make a quick action plan for the next hour and execute.",
                ],
                "unclear_steps": [
                    "Feeling lost on how to proceed? Let's create a roadmap together. What's the first obstacle you see?",
                    "The path isn't clear yet, and that's okay. What would make the next step obvious?",
                    "When things feel unclear, research helps. What information do you need to move forward?",
                    "Let's break this goal into clear, sequential steps. What comes first?",
                ],
                "resource_constraint": [
                    "You're missing resources. What's the minimum you need to get started? Can we find alternatives?",
                    "Resource limitations are real challenges. What can we work with today?",
                    "Let's be creative within constraints. What resources are actually available to you right now?",
                    "Missing something important? Sometimes constraints force innovation. What can you do with what you have?",
                ],
                "skill_gap": [
                    "This is a skill you need to develop. What's the best way for you to learn it quickly?",
                    "You're outside your comfort zone. That's growth! What's one skill you need most?",
                    "Learning curve ahead. Is there a mentor, course, or resource that could help?",
                    "New skills take time. What's your plan to level up in this area?",
                ],
                "external_blocker": [
                    "You're blocked by something external. Who needs to help? Can we unblock this?",
                    "Sometimes we're at the mercy of others. What leverage do you have?",
                    "External dependencies are frustrating. What CAN you do right now while you wait?",
                    "Let's make a plan to handle this dependency. Who do we need to communicate with?",
                ],
                "fatigue": [
                    "You're running on fumes. Maybe it's time to rest first. Your goal will still be there tomorrow.",
                    "Fatigue clouds judgment. What would restore your energy most effectively?",
                    "Burnout warning. Let's step back and look at your pace. Is this sustainable?",
                    "Energy is depleted. A real break might serve you better than pushing harder.",
                ],
                "distraction": [
                    "Distraction is stealing your focus. What's one thing you can do to minimize interruptions?",
                    "Your attention is scattered. Let's create one focus block with zero distractions.",
                    "Distractions derail progress. What's the biggest distraction factor right now?",
                    "Let's protect your focus. What would help you stay on track?",
                ],
                "doubt": [
                    "Doubt is natural when pursuing worthwhile goals. What would make you feel more confident?",
                    "You're questioning yourself. What evidence shows you CAN do this?",
                    "Doubt and fear often accompany growth. What would help you move past this?",
                    "Let's address the doubt. What specifically are you worried might go wrong?",
                ],
            }
        }
    
    async def generate_response(
        self,
        struggle_context: StruggleContext,
        agent_name: Optional[str] = None,
        goal_title: Optional[str] = None,
    ) -> MotivationResponse:
        """
        Generate an adaptive motivation response.
        
        Args:
            struggle_context: Context about the struggle
            agent_name: Optional agent name for personalization
            goal_title: Optional goal title for context
        
        Returns:
            Generated motivation response
        """
        import uuid
        
        async with self._lock:
            # Get template pool for this struggle type
            struggle_key = struggle_context.struggle_type.value
            templates = self._response_templates.get(struggle_key, [])
            
            if not templates:
                # Fallback generic response
                templates = [
                    f"I understand you're facing challenges with this goal. Let's work through this together.",
                ]
            
            # Select a random template
            template = random.choice(templates)
            
            # Substitute variables
            response_text = await self._substitute_variables(
                template,
                struggle_context=struggle_context,
                agent_name=agent_name,
                goal_title=goal_title,
            )
            
            response = MotivationResponse(
                id=str(uuid.uuid4()),
                text=response_text,
                struggle_type=struggle_key,
                confidence=struggle_context.confidence,
                strategy=self._select_strategy(struggle_context),
                metadata={
                    "goal_difficulty": struggle_context.goal_difficulty,
                    "progress_rate": struggle_context.progress_rate,
                    "emotion_state": struggle_context.current_emotion_state,
                },
            )
            
            # Record for effectiveness tracking
            self._effectiveness_history.append({
                "response_id": response.id,
                "struggle_type": struggle_key,
                "timestamp": str(asyncio.get_event_loop().time()),
            })
            
            logger.info(
                f"Generated response for {struggle_key} "
                f"(confidence={struggle_context.confidence:.2f})"
            )
            
            return response
    
    async def _substitute_variables(
        self,
        template: str,
        struggle_context: StruggleContext,
        agent_name: Optional[str] = None,
        goal_title: Optional[str] = None,
    ) -> str:
        """Substitute variables in response template."""
        text = template
        
        # Add more personalization based on context
        if goal_title and "{goal_title}" in text:
            text = text.replace("{goal_title}", goal_title)
        
        if agent_name and "{agent_name}" in text:
            text = text.replace("{agent_name}", agent_name)
        
        # Add contextual substitutions
        if "{progress_percent}" in text:
            progress_str = f"{int(struggle_context.progress_rate * 100)}%"
            text = text.replace("{progress_percent}", progress_str)
        
        if "{difficulty}" in text:
            difficulty_str = self._difficulty_to_string(struggle_context.goal_difficulty)
            text = text.replace("{difficulty}", difficulty_str)
        
        if "{time_remaining_hours}" in text:
            hours = int(struggle_context.time_remaining / 3600)
            text = text.replace("{time_remaining_hours}", str(hours))
        
        return text
    
    def _difficulty_to_string(self, difficulty: float) -> str:
        """Convert numeric difficulty to string."""
        if difficulty < 0.2:
            return "straightforward"
        elif difficulty < 0.4:
            return "moderately challenging"
        elif difficulty < 0.6:
            return "challenging"
        elif difficulty < 0.8:
            return "very challenging"
        else:
            return "extremely challenging"
    
    def _select_strategy(self, context: StruggleContext) -> str:
        """Select the strategy used for this response."""
        strategies = {
            StruggleType.MOTIVATION_LOW: "break_down_goal",
            StruggleType.TIME_PRESSURE: "prioritize_ruthlessly",
            StruggleType.UNCLEAR_STEPS: "create_roadmap",
            StruggleType.RESOURCE_CONSTRAINT: "creative_alternatives",
            StruggleType.SKILL_GAP: "accelerated_learning",
            StruggleType.EXTERNAL_BLOCKER: "remove_blocker",
            StruggleType.FATIGUE: "strategic_rest",
            StruggleType.DISTRACTION: "protect_focus",
            StruggleType.DOUBT: "build_confidence",
        }
        
        return strategies.get(context.struggle_type, "adaptive_support")
    
    async def get_effectiveness_metrics(self) -> Dict[str, Any]:
        """Get response effectiveness metrics."""
        async with self._lock:
            if not self._effectiveness_history:
                return {
                    "total_responses": 0,
                    "by_struggle_type": {},
                }
            
            by_type = {}
            for entry in self._effectiveness_history:
                struggle_type = entry["struggle_type"]
                by_type[struggle_type] = by_type.get(struggle_type, 0) + 1
            
            return {
                "total_responses": len(self._effectiveness_history),
                "by_struggle_type": by_type,
            }
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update response configuration."""
        self.config.update(new_config)
        self._response_templates = self.config.get("motivation_responses", {})
        logger.info("Updated response engine configuration")
    
    async def clear_history(self) -> None:
        """Clear effectiveness history (for testing)."""
        async with self._lock:
            self._effectiveness_history.clear()


class AdaptiveResponseBuilder:
    """
    Builds highly adaptive responses based on multiple factors.
    
    This is more sophisticated than template selection - it actually
    builds responses dynamically based on context.
    """
    
    def __init__(self, response_engine: ResponseEngine):
        """Initialize the builder."""
        self.engine = response_engine
    
    async def build_contextualized_response(
        self,
        struggle_context: StruggleContext,
        agent_attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build a highly contextualized response that adapts to:
        - Struggle type and severity
        - Goal characteristics
        - Emotional state
        - Personal attributes
        """
        
        base_response = await self.engine.generate_response(struggle_context)
        
        # Build context-aware additions
        additions = []
        
        # Emotional state considerations
        if "sadness" in struggle_context.current_emotion_state:
            sadness = struggle_context.current_emotion_state["sadness"]
            if sadness > 0.6:
                additions.append("Remember that difficult moments are temporary, and you're stronger than you think.")
        
        # Goal difficulty considerations
        if struggle_context.goal_difficulty > 0.7:
            additions.append("This is ambitious - which is good. Ambitious goals sometimes feel overwhelming.")
        
        # Progress rate considerations
        if struggle_context.progress_rate > 0.75:
            additions.append("You're already quite far along. The finish line is in sight.")
        elif struggle_context.progress_rate < 0.1:
            additions.append("You're early in this journey. Progress will compound from here.")
        
        # Time considerations
        if 0 < struggle_context.time_remaining < 3600:  # Less than 1 hour
            additions.append("You have limited time - focus on what matters most.")
        
        full_response = base_response.text
        if additions:
            full_response += " " + " ".join(additions)
        
        return full_response
