import logging
import re
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
    from agents.perception_agent.context_builder import ContextBuilder
except ImportError:
    try:
        from .context_builder import ContextBuilder
    except ImportError:
        ContextBuilder = None

try:
    from agents.perception_agent.anomaly_detector import AnomalyDetector
except ImportError:
    try:
        from .anomaly_detector import AnomalyDetector
    except ImportError:
        AnomalyDetector = None


class PerceptionAgent(BaseAgent):
    """
    Perception Agent — parses and understands text input.
    Extracts intent, entities, sentiment, urgency, and context.
    Works fully in text mode without camera or audio hardware.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(agent_id="perception_agent", agent_type="perception")
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self.is_running = False
        self.perception_history: List[Dict[str, Any]] = []
        self.max_history = self.config.get("max_history", 500)

        self.context_builder = ContextBuilder(self.config.get("context", {
            "max_entities": 20,
            "max_actions": 10,
            "max_relationships": 10,
            "confidence_threshold": 0.5,
            "temporal_window": 5,
            "location_threshold": 0.1,
        })) if ContextBuilder else None

        self.anomaly_detector = AnomalyDetector(self.config.get("anomaly", {})) if AnomalyDetector else None

        # Intent patterns: (pattern, intent_label, confidence_boost)
        self._intent_patterns = [
            (r"\b(create|make|build|generate|write|design)\b", "creation", 0.15),
            (r"\b(find|search|look for|get|fetch|retrieve|show)\b", "retrieval", 0.15),
            (r"\b(update|change|modify|edit|fix|correct|improve)\b", "modification", 0.15),
            (r"\b(delete|remove|clear|cancel|stop|end)\b", "deletion", 0.15),
            (r"\b(explain|describe|what is|how does|tell me|help me understand)\b", "explanation", 0.15),
            (r"\b(analyze|evaluate|assess|review|check|compare)\b", "analysis", 0.15),
            (r"\b(plan|schedule|organize|arrange|prepare)\b", "planning", 0.15),
            (r"\b(remember|save|store|keep|note)\b", "memory_store", 0.15),
            (r"\b(recall|remind|what did|do you remember)\b", "memory_recall", 0.15),
            (r"\b(feel|emotion|mood|sad|happy|angry|anxious|stress)\b", "emotional", 0.15),
            (r"\b(should i|which is better|recommend|suggest|advise)\b", "decision_support", 0.15),
            (r"\b(learn|study|understand|teach|explain how)\b", "learning", 0.15),
        ]

        # Entity type patterns
        self._entity_patterns = {
            "person": r"\b(I|me|my|myself|you|he|she|they|user|person|people|team|colleague)\b",
            "time": r"\b(today|tomorrow|yesterday|now|later|soon|morning|evening|week|month|year|\d{1,2}[:/]\d{2})\b",
            "task": r"\b(task|todo|project|work|assignment|deadline|goal|objective)\b",
            "emotion": r"\b(happy|sad|angry|anxious|excited|worried|frustrated|confused|confident|tired)\b",
            "topic": r"\b(about|regarding|concerning|related to|on the topic of)\s+(\w+(?:\s+\w+){0,2})",
            "quantity": r"\b(\d+(?:\.\d+)?(?:\s*(?:items?|things?|points?|steps?|days?|hours?|minutes?)))\b",
        }

        # Urgency signals
        self._urgency_signals = {
            "critical": ["urgent", "emergency", "immediately", "asap", "critical", "now", "right now"],
            "high": ["soon", "quickly", "fast", "important", "priority", "deadline", "today"],
            "medium": ["when possible", "sometime", "eventually", "would like"],
            "low": ["no rush", "whenever", "if you can", "optional"],
        }

    def start(self):
        self.is_running = True
        self.logger.info("Perception agent started")

    def stop(self):
        self.is_running = False
        self.logger.info("Perception agent stopped")

    async def initialize(self):
        """Initialize the perception agent — satisfies orchestrator contract."""
        await super().initialize()
        self.is_running = True
        self.state.update({"status": "active", "perceptions_processed": 0})
        self.logger.info(f"PerceptionAgent '{self.agent_id}' initialized")

    async def shutdown(self):
        """Graceful shutdown."""
        self.is_running = False
        await super().shutdown()
        self.logger.info(f"PerceptionAgent '{self.agent_id}' shut down")

    def perceive(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full perception pipeline for text input.
        Returns structured perception with intent, entities, urgency, context.
        """
        try:
            text = input_data.get("text", input_data.get("content", ""))
            if not text:
                return {"error": "No text input provided", "timestamp": datetime.utcnow().isoformat()}

            # Core perception components
            intent = self._detect_intent(text)
            entities = self._extract_entities(text)
            urgency = self._assess_urgency(text)
            sentiment = self._analyze_sentiment(text)
            ambiguities = self._detect_ambiguities(text)
            context_signals = self._extract_context_signals(text)

            perception = {
                "raw_input": text,
                "intent": intent,
                "entities": entities,
                "urgency": urgency,
                "sentiment": sentiment,
                "ambiguities": ambiguities,
                "context_signals": context_signals,
                "word_count": len(text.split()),
                "is_question": "?" in text,
                "is_command": intent["primary"] in ("creation", "modification", "deletion", "planning"),
                "confidence": self._calculate_confidence(intent, entities, text),
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Store in history
            self.perception_history.append(perception)
            if len(self.perception_history) > self.max_history:
                self.perception_history = self.perception_history[-self.max_history:]

            return perception

        except Exception as e:
            self.logger.error(f"Error in perception: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    def _detect_intent(self, text: str) -> Dict[str, Any]:
        """Detect primary and secondary intents from text."""
        lower = text.lower()
        intent_scores: Dict[str, float] = {}

        for pattern, intent_label, boost in self._intent_patterns:
            matches = len(re.findall(pattern, lower, re.IGNORECASE))
            if matches > 0:
                intent_scores[intent_label] = intent_scores.get(intent_label, 0.4) + (matches * boost)

        if not intent_scores:
            # Default: conversational
            return {
                "primary": "conversational",
                "secondary": [],
                "scores": {"conversational": 0.5},
                "confidence": 0.5,
            }

        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_intents[0][0]
        secondary = [i for i, _ in sorted_intents[1:3]]
        confidence = min(0.95, sorted_intents[0][1])

        return {
            "primary": primary,
            "secondary": secondary,
            "scores": {k: round(v, 3) for k, v in intent_scores.items()},
            "confidence": round(confidence, 3),
        }

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract named entities by type from text."""
        entities: Dict[str, List[str]] = {}
        for entity_type, pattern in self._entity_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            # Flatten tuples from groups
            flat = []
            for m in matches:
                if isinstance(m, tuple):
                    flat.extend([x.strip() for x in m if x.strip()])
                else:
                    flat.append(m.strip())
            unique = list(dict.fromkeys(flat))  # deduplicate preserving order
            if unique:
                entities[entity_type] = unique[:5]
        return entities

    def _assess_urgency(self, text: str) -> Dict[str, Any]:
        """Assess urgency level from text signals."""
        lower = text.lower()
        for level, signals in self._urgency_signals.items():
            for signal in signals:
                if signal in lower:
                    return {
                        "level": level,
                        "signal": signal,
                        "score": {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}[level],
                    }
        return {"level": "normal", "signal": None, "score": 0.4}

    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment polarity and intensity."""
        lower = text.lower()
        positive_words = [
            "good", "great", "excellent", "amazing", "wonderful", "fantastic", "love",
            "happy", "excited", "perfect", "awesome", "brilliant", "helpful", "thanks",
        ]
        negative_words = [
            "bad", "terrible", "awful", "horrible", "hate", "angry", "frustrated",
            "confused", "broken", "wrong", "fail", "error", "problem", "issue", "stuck",
        ]
        pos_count = sum(1 for w in positive_words if w in lower)
        neg_count = sum(1 for w in negative_words if w in lower)

        if pos_count > neg_count:
            polarity = "positive"
            score = min(0.95, 0.5 + pos_count * 0.1)
        elif neg_count > pos_count:
            polarity = "negative"
            score = min(0.95, 0.5 + neg_count * 0.1)
        else:
            polarity = "neutral"
            score = 0.5

        return {"polarity": polarity, "score": round(score, 3), "positive_signals": pos_count, "negative_signals": neg_count}

    def _detect_ambiguities(self, text: str) -> List[str]:
        """Detect potentially ambiguous phrases that may need clarification."""
        ambiguities = []
        ambiguous_patterns = [
            (r"\bit\b", "pronoun 'it' — unclear referent"),
            (r"\bthis\b", "pronoun 'this' — unclear referent"),
            (r"\bthat\b", "pronoun 'that' — unclear referent"),
            (r"\bsomething\b", "vague noun 'something'"),
            (r"\bsomewhere\b", "vague location 'somewhere'"),
            (r"\bsomeone\b", "vague person 'someone'"),
            (r"\bmaybe\b|\bperhaps\b|\bpossibly\b", "uncertain qualifier"),
        ]
        lower = text.lower()
        for pattern, description in ambiguous_patterns:
            if re.search(pattern, lower):
                ambiguities.append(description)
        return ambiguities[:3]  # Return top 3 ambiguities

    def _extract_context_signals(self, text: str) -> Dict[str, Any]:
        """Extract contextual signals: topic domain, action verbs, key nouns."""
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text)
        stop = {"that", "this", "with", "from", "have", "been", "will", "would", "could", "should"}
        keywords = [w.lower() for w in words if w.lower() not in stop]

        # Detect domain hints
        domain_hints = {
            "technical": ["code", "software", "system", "api", "database", "server", "deploy", "bug", "function"],
            "personal": ["feel", "life", "family", "friend", "health", "relationship", "personal"],
            "business": ["project", "team", "meeting", "deadline", "client", "revenue", "strategy", "market"],
            "creative": ["idea", "design", "story", "art", "create", "imagine", "write", "poem"],
            "learning": ["learn", "study", "understand", "course", "skill", "knowledge", "practice"],
        }
        detected_domains = []
        lower = text.lower()
        for domain, hints in domain_hints.items():
            if any(h in lower for h in hints):
                detected_domains.append(domain)

        return {
            "keywords": list(dict.fromkeys(keywords))[:10],
            "detected_domains": detected_domains,
            "sentence_count": len(re.split(r"[.!?]+", text.strip())),
            "has_numbers": bool(re.search(r"\d+", text)),
            "has_urls": bool(re.search(r"https?://\S+", text)),
        }

    def _calculate_confidence(self, intent: Dict[str, Any], entities: Dict[str, List[str]], text: str) -> float:
        """Overall perception confidence based on intent clarity and entity richness."""
        intent_conf = intent.get("confidence", 0.5)
        entity_bonus = min(0.2, len(entities) * 0.04)
        length_bonus = min(0.1, len(text.split()) * 0.005)
        return round(min(0.95, intent_conf + entity_bonus + length_bonus), 3)

    def get_recent_perceptions(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.perception_history[-limit:]

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Called by orchestrator agent_manager — async dispatch."""
        action = task.get("action", "")
        input_data = task.get("input_data", {})

        if action in ("perceive", "analyze", "parse", "understand", "process"):
            return self.perceive(input_data)

        if action == "get_history":
            limit = input_data.get("limit", 10)
            return {"perceptions": self.get_recent_perceptions(limit), "count": len(self.perception_history)}

        if action == "detect_intent":
            text = input_data.get("text", input_data.get("content", ""))
            return self._detect_intent(text)

        if action == "extract_entities":
            text = input_data.get("text", input_data.get("content", ""))
            return {"entities": self._extract_entities(text)}

        # Default: full perception
        return self.perceive(input_data)
