import asyncio
import logging
import uuid
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib

try:
    from structlog import get_logger
except ImportError:
    def get_logger():
        return logging.getLogger(__name__)

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

logger = get_logger()


class LearningSessionStatus(Enum):
    """Learning session lifecycle states."""
    INITIATED = "initiated"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERED = "recovered"


class ExperienceClassification(Enum):
    """Classification of learning experiences."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    ANOMALY = "anomaly"
    EDGE_CASE = "edge_case"
    TIMEOUT = "timeout"
    RETRY = "retry"
    RECOVERY = "recovery"


@dataclass
class LearningMetrics:
    """Metrics for a learning session."""
    session_id: str
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    improvements_applied: int = 0
    knowledge_updates: int = 0
    average_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    quality_score: float = 0.5
    confidence_score: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def as_dict(self) -> Dict:
        return asdict(self)


@dataclass
class LearningContext:
    """Context for learning operations."""
    request_id: str
    correlation_id: str
    trace_id: str
    session_id: str
    conversation_id: Optional[str] = None
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    system_state: Dict = field(default_factory=dict)
    agent_state: Dict = field(default_factory=dict)
    memory_context: Dict = field(default_factory=dict)
    decision_context: Dict = field(default_factory=dict)
    reasoning_context: Dict = field(default_factory=dict)
    planning_context: Dict = field(default_factory=dict)
    execution_context: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def as_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ExperienceRecord:
    """Complete record of a learning experience."""
    experience_id: str
    session_id: str
    timestamp: str
    classification: str
    description: str
    context: Dict
    performance_metrics: Dict
    error_info: Optional[Dict] = None
    root_cause: Optional[str] = None
    patterns_detected: List[str] = field(default_factory=list)
    affected_components: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.5
    source: str = "execution"
    version: int = 1
    audit_trail: List[Dict] = field(default_factory=list)
    replay_data: Dict = field(default_factory=dict)
    
    def as_dict(self) -> Dict:
        return asdict(self)


class LearningAgent(BaseAgent):
    def __init__(self, agent_id: str = "learning_agent", config: Optional[Dict] = None):
        super().__init__(agent_id, "learning")
        self.config = config or {}
        
        # Core data structures
        self.knowledge_base: Dict[str, Any] = {}
        self.user_preferences: Dict[str, Any] = {}
        self.interaction_patterns: List[Dict] = []
        self.topic_frequency: Dict[str, int] = {}
        self.adaptation_log: List[Dict] = []
        
        # Phase 7 enhancements
        self.learning_sessions: Dict[str, Dict] = {}
        self.experience_records: Dict[str, ExperienceRecord] = {}
        self.knowledge_updates: List[Dict] = []
        self.error_patterns: Dict[str, Dict] = {}
        self.performance_history: List[Dict] = []
        self.adaptation_strategies: Dict[str, Dict] = {}
        self.replay_buffer: List[ExperienceRecord] = []
        self.improvement_recommendations: List[Dict] = []
        self.failure_recovery_log: List[Dict] = []
        
        # Configuration values
        self.max_patterns = self.config.get("max_patterns", 2000)
        self.max_experiences = self.config.get("max_experiences", 5000)
        self.max_learning_sessions = self.config.get("max_learning_sessions", 100)
        self.max_history_size = self.config.get("max_history_size", 1000)
        self.experience_retention_days = self.config.get("experience_retention_days", 30)
        self.learning_interval_seconds = self.config.get("learning_interval_seconds", 60)
        self.performance_window_size = self.config.get("performance_window_size", 100)
        
        # Thresholds
        self.quality_threshold = self.config.get("quality_threshold", 0.7)
        self.confidence_threshold = self.config.get("confidence_threshold", 0.6)
        self.failure_pattern_threshold = self.config.get("failure_pattern_threshold", 3)
        self.improvement_threshold = self.config.get("improvement_threshold", 0.05)
        
        # Status tracking
        self.last_learning_update = datetime.utcnow()
        self.total_learning_cycles = 0
        self.total_experiences_processed = 0

    async def initialize(self):
        """Initialize the production learning agent."""
        await super().initialize()
        self.state.update({
            "knowledge_entries": len(self.knowledge_base),
            "preference_entries": len(self.user_preferences),
            "pattern_count": len(self.interaction_patterns),
            "adaptation_count": len(self.adaptation_log),
            "experience_count": len(self.experience_records),
            "active_sessions": len(self.learning_sessions),
            "quality_score": 0.7,
            "confidence_score": 0.6,
            "learning_cycles": self.total_learning_cycles,
            "last_learning": datetime.utcnow().isoformat(),
        })
        logger.info(f"Learning agent {self.agent_id} initialized with {len(self.knowledge_base)} knowledge entries")

    async def _update_state(self):
        """Update internal agent state metrics."""
        self.state.update({
            "knowledge_entries": len(self.knowledge_base),
            "preference_entries": len(self.user_preferences),
            "pattern_count": len(self.interaction_patterns),
            "adaptation_count": len(self.adaptation_log),
            "experience_count": len(self.experience_records),
            "active_sessions": len(self.learning_sessions),
            "error_patterns_detected": len(self.error_patterns),
            "learning_cycles": self.total_learning_cycles,
            "total_experiences": self.total_experiences_processed,
            "last_active": datetime.utcnow().isoformat(),
        })
    
    async def create_learning_session(self, context: LearningContext) -> Dict[str, Any]:
        """Create a new learning session with full context."""
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        session = {
            "session_id": session_id,
            "context": context.as_dict(),
            "status": LearningSessionStatus.INITIATED.value,
            "created_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "ended_at": None,
            "experiences": [],
            "metrics": LearningMetrics(session_id=session_id).as_dict(),
            "adaptations_applied": [],
            "errors": [],
            "version": 1,
        }
        
        self.learning_sessions[session_id] = session
        logger.info(f"Created learning session {session_id} with correlation_id {context.correlation_id}")
        
        return session
    
    async def start_learning_session(self, session_id: str) -> Dict[str, Any]:
        """Activate a learning session."""
        if session_id not in self.learning_sessions:
            return {"error": f"Session {session_id} not found"}
        
        session = self.learning_sessions[session_id]
        session["status"] = LearningSessionStatus.ACTIVE.value
        session["started_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Started learning session {session_id}")
        return session
    
    async def record_experience(self, session_id: str, experience: Dict[str, Any]) -> ExperienceRecord:
        """Record a learning experience with full classification and metrics."""
        experience_id = f"exp-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.utcnow().isoformat()
        
        # Classify experience
        classification = self._classify_experience(experience)
        
        # Analyze error if present
        error_info = None
        root_cause = None
        if "error" in experience:
            error_info = self._analyze_error(experience["error"])
            root_cause = self._identify_root_cause(experience, error_info)
        
        # Detect patterns
        patterns = self._detect_patterns(experience)
        
        # Get affected components
        affected_components = self._identify_affected_components(experience)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(experience, root_cause, patterns)
        
        # Create experience record
        record = ExperienceRecord(
            experience_id=experience_id,
            session_id=session_id,
            timestamp=timestamp,
            classification=classification.value,
            description=experience.get("description", ""),
            context=experience.get("context", {}),
            performance_metrics=experience.get("metrics", {}),
            error_info=error_info,
            root_cause=root_cause,
            patterns_detected=patterns,
            affected_components=affected_components,
            recommendations=recommendations,
            confidence=experience.get("confidence", 0.5),
            source=experience.get("source", "execution"),
        )
        
        # Store experience
        self.experience_records[experience_id] = record
        self.replay_buffer.append(record)
        
        # Add to session
        if session_id in self.learning_sessions:
            self.learning_sessions[session_id]["experiences"].append(experience_id)
        
        # Trim replay buffer
        if len(self.replay_buffer) > self.max_experiences:
            self.replay_buffer = self.replay_buffer[-self.max_experiences:]
        
        self.total_experiences_processed += 1
        
        logger.info(f"Recorded experience {experience_id}: {classification.value}")
        return record
    
    def _classify_experience(self, experience: Dict) -> ExperienceClassification:
        """Classify an experience based on outcomes and characteristics."""
        if "error" in experience and experience.get("error_type") == "timeout":
            return ExperienceClassification.TIMEOUT
        elif "error" in experience:
            return ExperienceClassification.FAILURE
        elif experience.get("recovery", False):
            return ExperienceClassification.RECOVERY
        elif experience.get("retry", False):
            return ExperienceClassification.RETRY
        elif experience.get("anomaly", False):
            return ExperienceClassification.ANOMALY
        elif experience.get("edge_case", False):
            return ExperienceClassification.EDGE_CASE
        elif experience.get("success_rate", 1.0) < 1.0:
            return ExperienceClassification.PARTIAL_SUCCESS
        else:
            return ExperienceClassification.SUCCESS
    
    def _analyze_error(self, error: Any) -> Optional[Dict]:
        """Analyze error information."""
        return {
            "type": type(error).__name__,
            "message": str(error),
            "hash": hashlib.md5(str(error).encode()).hexdigest(),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _identify_root_cause(self, experience: Dict, error_info: Optional[Dict]) -> Optional[str]:
        """Identify potential root cause of failures."""
        if not error_info:
            return None
        
        # Simple heuristic-based root cause analysis
        msg = error_info.get("message", "").lower()
        
        if "timeout" in msg:
            return "execution_timeout"
        elif "memory" in msg:
            return "memory_exhaustion"
        elif "connection" in msg or "network" in msg:
            return "connectivity_issue"
        elif "permission" in msg or "unauthorized" in msg:
            return "permission_denied"
        elif "not found" in msg or "missing" in msg:
            return "resource_missing"
        else:
            return "unknown_error"
    
    def _detect_patterns(self, experience: Dict) -> List[str]:
        """Detect recurring patterns in experiences."""
        patterns = []
        
        # Check for repeated errors
        if "error" in experience:
            error_hash = experience.get("error_hash")
            if error_hash in self.error_patterns:
                self.error_patterns[error_hash]["count"] += 1
                if self.error_patterns[error_hash]["count"] >= self.failure_pattern_threshold:
                    patterns.append("recurring_failure")
            else:
                self.error_patterns[error_hash] = {
                    "count": 1,
                    "first_seen": datetime.utcnow().isoformat(),
                    "error": experience.get("error"),
                }
        
        # Check for performance degradation
        metrics = experience.get("metrics", {})
        if self.performance_history:
            avg_latency = sum(p.get("latency_ms", 0) for p in self.performance_history[-10:]) / min(10, len(self.performance_history))
            if metrics.get("latency_ms", 0) > avg_latency * 1.5:
                patterns.append("performance_degradation")
        
        # Check for edge cases
        if experience.get("edge_case"):
            patterns.append("edge_case_detected")
        
        return patterns
    
    def _identify_affected_components(self, experience: Dict) -> List[str]:
        """Identify which components are affected by this experience."""
        affected = []
        
        if "agent_type" in experience:
            affected.append(experience["agent_type"])
        
        if "error" in experience:
            if "memory" in str(experience["error"]).lower():
                affected.append("memory_system")
            if "planning" in str(experience["error"]).lower():
                affected.append("planning_system")
            if "decision" in str(experience["error"]).lower():
                affected.append("decision_system")
            if "reasoning" in str(experience["error"]).lower():
                affected.append("reasoning_system")
        
        return affected
    
    def _generate_recommendations(self, experience: Dict, root_cause: Optional[str], patterns: List[str]) -> List[str]:
        """Generate recommendations for improvement."""
        recommendations = []
        
        if root_cause == "execution_timeout":
            recommendations.append("Increase timeout threshold or optimize algorithm")
        elif root_cause == "memory_exhaustion":
            recommendations.append("Implement memory pooling or reduce data retention")
        elif root_cause == "connectivity_issue":
            recommendations.append("Add retry logic with exponential backoff")
        elif root_cause == "permission_denied":
            recommendations.append("Review authorization and access control")
        elif root_cause == "resource_missing":
            recommendations.append("Add resource existence validation")
        
        if "performance_degradation" in patterns:
            recommendations.append("Profile hot paths and optimize critical sections")
        
        if "recurring_failure" in patterns:
            recommendations.append("Add specific error handling for this failure mode")
        
        if "edge_case_detected" in patterns:
            recommendations.append("Add edge case handling to prevent future issues")
        
        return recommendations

    async def _process_emotions(self):
        recent = self.adaptation_log[-10:]
        if not recent:
            return
        rate = sum(1 for a in recent if a.get("success", True)) / len(recent)
        if rate > 0.7:
            await self.update_emotion("happiness", min(1.0, self.emotions.get("happiness", 0.5) + 0.05))
        elif rate < 0.3:
            await self.update_emotion("sadness", min(1.0, self.emotions.get("sadness", 0.0) + 0.05))

    async def learn_from_interaction(self, interaction: Dict) -> Dict:
        user_message = interaction.get("user_message", "")
        agent_response = interaction.get("agent_response", "")
        agent_used = interaction.get("agent_used", "orchestrator_agent")
        user_id = interaction.get("user_id", "default")
        feedback = interaction.get("feedback")

        words = user_message.lower().split()
        for word in words:
            if len(word) > 4:
                self.topic_frequency[word] = self.topic_frequency.get(word, 0) + 1

        pattern = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "message_length": len(user_message),
            "agent_used": agent_used,
            "top_words": sorted(words, key=lambda w: self.topic_frequency.get(w, 0), reverse=True)[:5],
            "feedback": feedback,
        }
        self.interaction_patterns.append(pattern)
        if len(self.interaction_patterns) > self.max_patterns:
            self.interaction_patterns = self.interaction_patterns[-self.max_patterns:]

        if feedback is not None:
            pref_key = f"{user_id}:{agent_used}"
            if pref_key not in self.user_preferences:
                self.user_preferences[pref_key] = {"positive": 0, "negative": 0, "total": 0}
            self.user_preferences[pref_key]["total"] += 1
            if feedback > 0:
                self.user_preferences[pref_key]["positive"] += 1
            else:
                self.user_preferences[pref_key]["negative"] += 1

        topic = self._extract_topic(user_message)
        if topic:
            if topic not in self.knowledge_base:
                self.knowledge_base[topic] = {
                    "first_seen": datetime.utcnow().isoformat(),
                    "frequency": 0,
                    "agents_used": [],
                    "sample_queries": [],
                }
            entry = self.knowledge_base[topic]
            entry["frequency"] += 1
            entry["last_seen"] = datetime.utcnow().isoformat()
            if agent_used not in entry["agents_used"]:
                entry["agents_used"].append(agent_used)
            if len(entry["sample_queries"]) < 5:
                entry["sample_queries"].append(user_message[:100])

        adaptation = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "topic": topic,
            "agent_used": agent_used,
            "success": feedback is None or feedback > 0,
        }
        self.adaptation_log.append(adaptation)
        if len(self.adaptation_log) > 500:
            self.adaptation_log = self.adaptation_log[-500:]

        self.state["last_learning"] = datetime.utcnow().isoformat()

        return {
            "learned": True,
            "topic": topic,
            "pattern_id": pattern["id"],
            "knowledge_base_size": len(self.knowledge_base),
            "top_topics": self._get_top_topics(5),
        }

    def _extract_topic(self, text: str) -> Optional[str]:
        topic_map = {
            "memory": ["remember", "recall", "forget", "memory", "store", "save"],
            "emotion": ["feel", "emotion", "mood", "sad", "happy", "angry", "anxious"],
            "task": ["task", "todo", "deadline", "schedule", "reminder", "organize"],
            "creativity": ["create", "idea", "brainstorm", "design", "story", "imagine"],
            "planning": ["plan", "goal", "strategy", "roadmap", "milestone", "achieve"],
            "reasoning": ["analyze", "logic", "reason", "why", "because", "proof"],
            "social": ["friend", "relationship", "communicate", "people", "social"],
            "learning": ["learn", "study", "understand", "teach", "knowledge", "skill"],
            "decision": ["decide", "choose", "option", "compare", "recommend", "best"],
            "motivation": ["motivate", "inspire", "stuck", "tired", "give up", "push"],
        }
        lower = text.lower()
        scores = {}
        for topic, keywords in topic_map.items():
            scores[topic] = sum(1 for kw in keywords if kw in lower)
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else None

    def _get_top_topics(self, n: int) -> List[Dict]:
        sorted_topics = sorted(
            self.knowledge_base.items(),
            key=lambda x: x[1].get("frequency", 0),
            reverse=True
        )
        return [{"topic": k, "frequency": v.get("frequency", 0)} for k, v in sorted_topics[:n]]

    def get_user_agent_preference(self, user_id: str) -> Optional[str]:
        best_agent = None
        best_score = -1
        for key, stats in self.user_preferences.items():
            uid, agent = key.split(":", 1)
            if uid != user_id:
                continue
            total = stats["total"]
            if total == 0:
                continue
            score = stats["positive"] / total
            if score > best_score:
                best_score = score
                best_agent = agent
        return best_agent

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        input_data = task.get("input_data", {})

        if action in ("learn", "learn_from_interaction"):
            return await self.learn_from_interaction(input_data)

        if action == "get_preferences":
            user_id = input_data.get("user_id", "default")
            preferred = self.get_user_agent_preference(user_id)
            return {
                "user_id": user_id,
                "preferred_agent": preferred,
                "top_topics": self._get_top_topics(10),
                "total_interactions": len(self.interaction_patterns),
            }

        if action == "get_stats":
            return {
                "knowledge_base_size": len(self.knowledge_base),
                "user_preferences": len(self.user_preferences),
                "interaction_patterns": len(self.interaction_patterns),
                "adaptation_count": len(self.adaptation_log),
                "top_topics": self._get_top_topics(5),
            }

        if action == "get_topic_knowledge":
            topic = input_data.get("topic", "")
            return self.knowledge_base.get(topic, {"error": "topic not found"})

        return await self.learn_from_interaction({
            "user_message": input_data.get("content", ""),
            "agent_used": input_data.get("agent_used", "orchestrator_agent"),
            "user_id": input_data.get("user_id", "default"),
        })
