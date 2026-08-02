import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from agents.base_agent import BaseAgent
except ImportError:
    try:
        from ..base_agent import BaseAgent  # type: ignore
    except ImportError:
        class BaseAgent:  # type: ignore
            def __init__(self, agent_id: str = "", agent_type: str = "", **_):
                self.agent_id = agent_id
                self.agent_type = agent_type
                self.state: dict = {}
                self.memory: list = []
                self.emotions: dict = {}
                self.connections: dict = {}
            async def initialize(self): pass
            async def shutdown(self): pass

try:
    from agents.social_agent.social_cues_parser import SocialCuesParser
    from agents.social_agent.relationship_manager import RelationshipManager
except ImportError:
    try:
        from .social_cues_parser import SocialCuesParser
        from .relationship_manager import RelationshipManager
    except ImportError:
        SocialCuesParser = None
        RelationshipManager = None


class SocialAgent(BaseAgent):
    """
    Social Agent — parses social cues, manages relationships,
    and generates contextually appropriate responses.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(agent_id="social_agent", agent_type="social")
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self.social_cues_parser = SocialCuesParser(self.config) if SocialCuesParser else None
        self.relationship_manager = RelationshipManager(self.config) if RelationshipManager else None

        # Response templates keyed by (interaction_type, formality, primary_emotion)
        self._response_templates = {
            ("greeting", "formal"): [
                "Good day. How may I assist you today?",
                "Hello. It's a pleasure to connect with you.",
                "Greetings. I'm here to help — what can I do for you?",
            ],
            ("greeting", "informal"): [
                "Hey! Great to hear from you. What's up?",
                "Hi there! How's it going?",
                "Hey, good to see you! What can I help with?",
            ],
            ("greeting", "neutral"): [
                "Hello! How can I help you today?",
                "Hi there. What would you like to discuss?",
            ],
            ("farewell", "formal"): [
                "Thank you for the conversation. Have a productive day.",
                "It was a pleasure. Until next time.",
            ],
            ("farewell", "informal"): [
                "Take care! Talk soon.",
                "Bye! It was great chatting.",
            ],
            ("farewell", "neutral"): [
                "Goodbye! Feel free to return anytime.",
                "Take care. See you next time.",
            ],
            ("question", "formal"): [
                "That's an excellent question. Let me address it carefully.",
                "I appreciate you asking. Here's what I can share:",
            ],
            ("question", "informal"): [
                "Good question! Here's what I think:",
                "Oh, interesting — let me think about that.",
            ],
            ("question", "neutral"): [
                "Let me help you with that.",
                "Here's what I know about that:",
            ],
            ("statement", "formal"): [
                "I understand your perspective. Allow me to respond thoughtfully.",
                "Thank you for sharing that. My response:",
            ],
            ("statement", "informal"): [
                "Got it! Here's my take:",
                "Interesting point! I'd say:",
            ],
            ("statement", "neutral"): [
                "I see. Here's my response:",
                "Understood. Let me address that:",
            ],
        }

        # Emotion-aware tone modifiers
        self._emotion_modifiers = {
            "positive": "I'm glad to hear that! ",
            "negative": "I understand this might be difficult. ",
            "neutral": "",
        }

        # Trust-based depth modifiers
        self._trust_modifiers = {
            "trusted": "Based on our ongoing conversations, ",
            "developing": "As we continue to build our connection, ",
            "new": "",
            "distrustful": "I want to make sure I'm being clear and transparent: ",
        }

    async def initialize(self):
        """Initialize the social agent — satisfies orchestrator contract."""
        await super().initialize()
        self.state.update({"status": "active", "interactions_processed": 0})
        self.logger.info(f"SocialAgent '{self.agent_id}' initialized")

    async def shutdown(self):
        """Graceful shutdown."""
        await super().shutdown()
        self.logger.info(f"SocialAgent '{self.agent_id}' shut down")

    def process_social_cue(self, cue_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full pipeline: parse cue → update relationship → generate response.
        """
        try:
            # Parse social cue
            if self.social_cues_parser:
                parsed_cue = self.social_cues_parser.parse(cue_data)
            else:
                parsed_cue = self._fallback_parse(cue_data)

            # Update relationship state
            if self.relationship_manager:
                relationship_context = self.relationship_manager.update_state(parsed_cue)
            else:
                relationship_context = {
                    "status": "new",
                    "trust_score": 0.5,
                    "interaction_count": 1,
                    "preferred_formality": "neutral",
                    "last_interaction": datetime.now().isoformat(),
                }

            # Generate contextual response
            response = self._generate_response(parsed_cue, relationship_context)
            return response

        except Exception as e:
            self.logger.error(f"Error processing social cue: {e}")
            return {"error": str(e), "response_type": "error"}

    def _fallback_parse(self, cue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Minimal parser when SocialCuesParser is unavailable."""
        content = cue_data.get("content", "")
        lower = content.lower()

        if any(w in lower for w in ["hi", "hello", "hey", "good morning", "good afternoon"]):
            interaction_type = "greeting"
        elif any(w in lower for w in ["bye", "goodbye", "see you", "farewell"]):
            interaction_type = "farewell"
        elif "?" in content:
            interaction_type = "question"
        else:
            interaction_type = "statement"

        emotions = []
        if any(w in lower for w in ["happy", "great", "wonderful", "excited", "love"]):
            emotions = ["positive"]
        elif any(w in lower for w in ["sad", "angry", "upset", "frustrated", "worried"]):
            emotions = ["negative"]
        else:
            emotions = ["neutral"]

        formal_words = ["please", "kindly", "would you", "could you", "thank you"]
        informal_words = ["hey", "yo", "gonna", "wanna", "sup"]
        formal_score = sum(1 for w in formal_words if w in lower)
        informal_score = sum(1 for w in informal_words if w in lower)
        formality = "formal" if formal_score > informal_score else "informal" if informal_score > formal_score else "neutral"

        return {
            "original": cue_data,
            "timestamp": datetime.now().isoformat(),
            "emotions": emotions,
            "social_context": [interaction_type],
            "formality_level": formality,
            "interaction_type": interaction_type,
        }

    def _generate_response(self, parsed_cue: Dict[str, Any],
                           relationship_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a contextually appropriate response based on:
        - interaction type (greeting/farewell/question/statement)
        - formality level (formal/informal/neutral)
        - detected emotions
        - relationship trust score
        - interaction history depth
        """
        interaction_type = parsed_cue.get("interaction_type", "statement")
        formality = parsed_cue.get("formality_level", "neutral")
        emotions = parsed_cue.get("emotions", ["neutral"])
        trust_score = relationship_context.get("trust_score", 0.5)
        relationship_status = relationship_context.get("status", "new")
        interaction_count = relationship_context.get("interaction_count", 1)

        # Determine primary emotion sentiment
        if "positive" in emotions:
            emotion_sentiment = "positive"
        elif "negative" in emotions:
            emotion_sentiment = "negative"
        else:
            emotion_sentiment = "neutral"

        # Pick response template
        template_key = (interaction_type, formality)
        templates = self._response_templates.get(
            template_key,
            self._response_templates.get((interaction_type, "neutral"), ["I understand. How can I help?"])
        )

        # Select template based on interaction count (vary responses)
        template = templates[interaction_count % len(templates)]

        # Build prefix from emotion + trust modifiers
        emotion_prefix = self._emotion_modifiers.get(emotion_sentiment, "")
        trust_prefix = self._trust_modifiers.get(relationship_status, "")

        # Combine: trust prefix only for non-greeting interactions
        if interaction_type in ("greeting", "farewell"):
            full_response = emotion_prefix + template
        else:
            full_response = emotion_prefix + trust_prefix + template

        # Adapt tone based on trust score
        if trust_score > 0.7 and interaction_type not in ("greeting", "farewell"):
            full_response += " I'm here for you — feel free to share more."
        elif trust_score < 0.3:
            full_response += " Please let me know if you need clarification."

        return {
            "response_type": interaction_type,
            "content": full_response,
            "emotional_tone": emotion_sentiment,
            "formality": formality,
            "relationship_context": relationship_context,
            "confidence": round(min(0.95, 0.5 + trust_score * 0.4 + (interaction_count * 0.01)), 3),
            "timestamp": datetime.now().isoformat(),
        }

    def get_relationship(self, sender: str) -> Optional[Dict[str, Any]]:
        """Get relationship context for a specific sender."""
        if self.relationship_manager:
            return self.relationship_manager._get_relationship_context(sender)
        return None

    def get_all_relationships(self) -> Dict[str, Any]:
        if self.relationship_manager:
            return self.relationship_manager.get_all_relationships()
        return {}

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Called by orchestrator agent_manager — async dispatch."""
        action = task.get("action", "")
        input_data = task.get("input_data", {})

        if action in ("process", "analyze", "respond"):
            content = input_data.get("content", input_data.get("text", ""))
            sender = input_data.get("sender", input_data.get("user_id", "user"))
            cue_data = {"content": content, "sender": sender, "type": input_data.get("type", "")}
            return self.process_social_cue(cue_data)

        if action == "get_relationship":
            sender = input_data.get("sender", input_data.get("user_id", ""))
            rel = self.get_relationship(sender)
            return {"relationship": rel} if rel else {"relationship": None}

        if action == "get_all_relationships":
            return {"relationships": self.get_all_relationships()}

        # Default: process as social cue
        content = input_data.get("content", input_data.get("text", ""))
        return self.process_social_cue({"content": content, "sender": "user"})
