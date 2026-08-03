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
        session_id = context.session_id or f"session-{uuid.uuid4().hex[:8]}"
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

    async def update_knowledge(self, knowledge_update: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a knowledge update with full validation and tracing."""
        update_id = f"update-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.utcnow().isoformat()
        
        update_record = {
            "update_id": update_id,
            "timestamp": timestamp,
            "type": knowledge_update.get("type", "refinement"),  # refinement, correction, new_knowledge, merge
            "domain": knowledge_update.get("domain", "general"),
            "content": knowledge_update.get("content"),
            "confidence": knowledge_update.get("confidence", 0.5),
            "source": knowledge_update.get("source", "unknown"),
            "affected_entries": [],
            "validation_status": "pending",
            "version_increment": 1,
            "audit_trail": [],
        }
        
        # Validate knowledge update
        validation = self._validate_knowledge(knowledge_update)
        update_record["validation_status"] = validation["status"]
        
        if validation["status"] != "valid":
            logger.warning(f"Knowledge update {update_id} validation failed: {validation['errors']}")
            update_record["errors"] = validation["errors"]
            return update_record
        
        # Apply update
        try:
            affected = self._apply_knowledge_update(knowledge_update, update_record)
            update_record["affected_entries"] = affected
            update_record["validation_status"] = "applied"
            
            # Record in history
            self.knowledge_updates.append(update_record)
            if len(self.knowledge_updates) > self.max_history_size:
                self.knowledge_updates = self.knowledge_updates[-self.max_history_size:]
            
            logger.info(f"Applied knowledge update {update_id}: {validation['status']}")
        except Exception as e:
            logger.error(f"Error applying knowledge update: {e}")
            update_record["validation_status"] = "failed"
            update_record["error"] = str(e)
        
        return update_record
    
    def _validate_knowledge(self, update: Dict) -> Dict[str, Any]:
        """Validate a knowledge update."""
        errors = []
        
        if not update.get("content"):
            errors.append("Missing content")
        
        if update.get("confidence", 0.5) < 0 or update.get("confidence", 0.5) > 1.0:
            errors.append("Invalid confidence value")
        
        if update.get("type") not in ["refinement", "correction", "new_knowledge", "merge"]:
            errors.append("Invalid update type")
        
        return {
            "status": "valid" if not errors else "invalid",
            "errors": errors,
        }
    
    def _apply_knowledge_update(self, update: Dict, record: Dict) -> List[str]:
        """Apply a knowledge update to the knowledge base."""
        affected = []
        domain = update.get("domain", "general")
        
        if domain not in self.knowledge_base:
            self.knowledge_base[domain] = {
                "entries": [],
                "created_at": datetime.utcnow().isoformat(),
                "version": 1,
                "confidence": 0.5,
            }
        
        entry = {
            "id": f"entry-{uuid.uuid4().hex[:8]}",
            "content": update.get("content"),
            "confidence": update.get("confidence", 0.5),
            "created_at": datetime.utcnow().isoformat(),
            "source": update.get("source", "unknown"),
            "type": update.get("type", "refinement"),
        }
        
        self.knowledge_base[domain]["entries"].append(entry)
        self.knowledge_base[domain]["version"] += 1
        self.knowledge_base[domain]["updated_at"] = datetime.utcnow().isoformat()
        
        affected.append(domain)
        return affected
    
    async def apply_adaptation(self, strategy: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply an adaptation strategy with full tracking."""
        adaptation_id = f"adapt-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.utcnow().isoformat()
        
        adaptation_record = {
            "adaptation_id": adaptation_id,
            "timestamp": timestamp,
            "strategy": strategy,
            "parameters": parameters,
            "status": "initiated",
            "components_affected": [],
            "metrics_before": {},
            "metrics_after": {},
            "rollback_available": True,
            "success": False,
        }
        
        try:
            # Apply adaptation based on strategy
            components = self._apply_adaptation_strategy(strategy, parameters)
            adaptation_record["components_affected"] = components
            adaptation_record["status"] = "applied"
            adaptation_record["success"] = True
            
            # Record metric
            self.adaptation_log.append(adaptation_record)
            if len(self.adaptation_log) > self.max_history_size:
                self.adaptation_log = self.adaptation_log[-self.max_history_size:]
            
            logger.info(f"Applied adaptation {adaptation_id}: {strategy}")
        except Exception as e:
            logger.error(f"Error applying adaptation: {e}")
            adaptation_record["status"] = "failed"
            adaptation_record["error"] = str(e)
        
        return adaptation_record
    
    def _apply_adaptation_strategy(self, strategy: str, parameters: Dict) -> List[str]:
        """Apply specific adaptation strategy."""
        components_affected = []
        
        if strategy == "increase_confidence":
            self.confidence_threshold = min(0.95, self.confidence_threshold + parameters.get("delta", 0.05))
            components_affected.append("confidence_calibration")
        
        elif strategy == "increase_timeout":
            self.config["timeout_multiplier"] = self.config.get("timeout_multiplier", 1.0) * parameters.get("factor", 1.5)
            components_affected.append("execution_timing")
        
        elif strategy == "optimize_memory":
            self.max_patterns = int(self.max_patterns * parameters.get("reduction_factor", 0.9))
            self.max_experiences = int(self.max_experiences * parameters.get("reduction_factor", 0.9))
            components_affected.append("memory_management")
        
        elif strategy == "adjust_learning_rate":
            self.learning_interval_seconds = max(10, self.learning_interval_seconds + parameters.get("delta", 0))
            components_affected.append("learning_schedule")
        
        elif strategy == "improve_error_handling":
            components_affected.append("error_handling")
        
        elif strategy == "refine_heuristics":
            components_affected.append("decision_heuristics")
        
        return components_affected
    
    async def analyze_performance(self) -> Dict[str, Any]:
        """Analyze performance metrics comprehensively."""
        if not self.performance_history:
            return {"error": "No performance data available"}
        
        recent_window = self.performance_history[-self.performance_window_size:]
        
        # Calculate metrics
        latencies = [p.get("latency_ms", 0) for p in recent_window]
        success_rate = sum(1 for p in recent_window if p.get("success")) / len(recent_window)
        error_rate = sum(1 for p in recent_window if not p.get("success")) / len(recent_window)
        
        analysis = {
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "window_size": len(recent_window),
            "success_rate": success_rate,
            "error_rate": error_rate,
            "latency_metrics": {
                "average_ms": sum(latencies) / len(latencies) if latencies else 0,
                "min_ms": min(latencies) if latencies else 0,
                "max_ms": max(latencies) if latencies else 0,
                "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
                "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0,
            },
            "quality_score": self._calculate_quality_score(recent_window),
            "health_status": self._assess_health(success_rate, error_rate),
            "top_errors": self._get_top_errors(recent_window),
            "trend": self._detect_trend(recent_window),
        }
        
        return analysis
    
    def _calculate_quality_score(self, window: List[Dict]) -> float:
        """Calculate overall quality score."""
        if not window:
            return 0.5
        
        success_rate = sum(1 for p in window if p.get("success")) / len(window)
        avg_confidence = sum(p.get("confidence", 0.5) for p in window) / len(window)
        error_rate = 1 - success_rate
        
        # Weight: 60% success, 30% confidence, 10% error prevention
        score = (success_rate * 0.6) + (avg_confidence * 0.3) + ((1 - error_rate) * 0.1)
        return max(0.0, min(1.0, score))
    
    def _assess_health(self, success_rate: float, error_rate: float) -> str:
        """Assess system health."""
        if success_rate > 0.95:
            return "excellent"
        elif success_rate > 0.85:
            return "good"
        elif success_rate > 0.70:
            return "acceptable"
        elif success_rate > 0.50:
            return "degraded"
        else:
            return "critical"
    
    def _get_top_errors(self, window: List[Dict]) -> List[Dict]:
        """Get most common errors."""
        error_counts = {}
        for perf in window:
            if not perf.get("success") and "error" in perf:
                error_key = perf["error"]
                error_counts[error_key] = error_counts.get(error_key, 0) + 1
        
        return sorted(
            [{"error": e, "count": c} for e, c in error_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:5]
    
    def _detect_trend(self, window: List[Dict]) -> str:
        """Detect performance trend."""
        if len(window) < 2:
            return "unknown"
        
        first_half = window[:len(window) // 2]
        second_half = window[len(window) // 2:]
        
        first_success = sum(1 for p in first_half if p.get("success")) / len(first_half)
        second_success = sum(1 for p in second_half if p.get("success")) / len(second_half)
        
        delta = second_success - first_success
        
        if delta > 0.05:
            return "improving"
        elif delta < -0.05:
            return "degrading"
        else:
            return "stable"
    
    async def _process_emotions(self):
        """Process emotions based on recent performance."""
        recent = self.adaptation_log[-10:]
        if not recent:
            return
        rate = sum(1 for a in recent if a.get("success", True)) / len(recent)
        
        if rate > 0.8:
            await self.update_emotion("happiness", min(1.0, self.emotions.get("happiness", 0.5) + 0.05))
            await self.update_emotion("confidence", min(1.0, self.emotions.get("confidence", 0.7) + 0.05))
        elif rate < 0.3:
            await self.update_emotion("sadness", min(1.0, self.emotions.get("sadness", 0.0) + 0.05))
            await self.update_emotion("confidence", max(0.1, self.emotions.get("confidence", 0.7) - 0.05))

    async def replay_experiences(self, filter_criteria: Optional[Dict] = None, limit: int = 10) -> List[Dict]:
        """Replay stored experiences for continued learning."""
        candidates = self.replay_buffer
        
        # Apply filters
        if filter_criteria:
            if "classification" in filter_criteria:
                candidates = [e for e in candidates if e.classification == filter_criteria["classification"]]
            if "min_confidence" in filter_criteria:
                candidates = [e for e in candidates if e.confidence >= filter_criteria["min_confidence"]]
            if "days_old" in filter_criteria:
                cutoff_date = datetime.utcnow() - timedelta(days=filter_criteria["days_old"])
                candidates = [e for e in candidates if datetime.fromisoformat(e.timestamp) >= cutoff_date]
        
        # Priority replay: failures first, then edge cases, then successes
        def priority_score(exp: ExperienceRecord) -> Tuple[int, float]:
            priority_map = {
                "failure": 0,
                "timeout": 1,
                "edge_case": 2,
                "anomaly": 3,
                "partial_success": 4,
                "recovery": 5,
                "retry": 6,
                "success": 7,
            }
            priority = priority_map.get(exp.classification, 8)
            return (priority, -exp.confidence)  # Higher confidence = lower sort value
        
        candidates.sort(key=priority_score)
        
        replayed = []
        for exp in candidates[:limit]:
            replay_record = {
                "experience_id": exp.experience_id,
                "session_id": exp.session_id,
                "classification": exp.classification,
                "timestamp": exp.timestamp,
                "recommendations": exp.recommendations,
                "affected_components": exp.affected_components,
                "root_cause": exp.root_cause,
                "patterns_detected": exp.patterns_detected,
                "replayed_at": datetime.utcnow().isoformat(),
            }
            replayed.append(replay_record)
        
        logger.info(f"Replayed {len(replayed)} experiences")
        return replayed
    
    async def evaluate_performance(self, focus_area: Optional[str] = None) -> Dict[str, Any]:
        """Comprehensive self-evaluation of system performance."""
        evaluation = {
            "evaluation_timestamp": datetime.utcnow().isoformat(),
            "learning_cycles": self.total_learning_cycles,
            "experiences_processed": self.total_experiences_processed,
        }
        
        # Performance analysis
        if focus_area is None or focus_area == "performance":
            evaluation["performance"] = await self.analyze_performance()
        
        # Error analysis
        if focus_area is None or focus_area == "errors":
            evaluation["error_analysis"] = {
                "error_patterns_detected": len(self.error_patterns),
                "recurring_failures": len([e for e in self.error_patterns.values() if e["count"] >= self.failure_pattern_threshold]),
                "most_common_errors": self._get_most_common_errors(),
            }
        
        # Knowledge base evaluation
        if focus_area is None or focus_area == "knowledge":
            evaluation["knowledge_evaluation"] = {
                "domains": len(self.knowledge_base),
                "total_entries": sum(len(kb.get("entries", [])) for kb in self.knowledge_base.values()),
                "average_confidence": self._calculate_avg_knowledge_confidence(),
                "update_frequency": len(self.knowledge_updates),
            }
        
        # Adaptation effectiveness
        if focus_area is None or focus_area == "adaptations":
            evaluation["adaptation_effectiveness"] = {
                "total_adaptations": len(self.adaptation_log),
                "successful_adaptations": len([a for a in self.adaptation_log if a.get("success")]),
                "strategies_used": list(set(a.get("strategy") for a in self.adaptation_log)),
            }
        
        # Learning session analysis
        if focus_area is None or focus_area == "sessions":
            evaluation["session_analysis"] = {
                "total_sessions": len(self.learning_sessions),
                "completed_sessions": len([s for s in self.learning_sessions.values() if s["status"] == LearningSessionStatus.COMPLETED.value]),
                "failed_sessions": len([s for s in self.learning_sessions.values() if s["status"] == LearningSessionStatus.FAILED.value]),
            }
        
        # Improvement recommendations
        if focus_area is None or focus_area == "recommendations":
            evaluation["recommendations"] = self._generate_system_recommendations()
        
        return evaluation
    
    def _get_most_common_errors(self) -> List[Dict]:
        """Get most common errors across all patterns."""
        sorted_patterns = sorted(
            self.error_patterns.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        return [{"error_hash": h, "count": p["count"], "first_seen": p["first_seen"]} for h, p in sorted_patterns[:5]]
    
    def _calculate_avg_knowledge_confidence(self) -> float:
        """Calculate average confidence of knowledge base."""
        all_confidence = []
        for domain_data in self.knowledge_base.values():
            for entry in domain_data.get("entries", []):
                all_confidence.append(entry.get("confidence", 0.5))
        
        return sum(all_confidence) / len(all_confidence) if all_confidence else 0.5
    
    def _generate_system_recommendations(self) -> List[Dict]:
        """Generate recommendations for system improvement."""
        recommendations = []
        
        # Performance recommendations
        perf = self.performance_history[-10:] if self.performance_history else []
        if perf:
            success_rate = sum(1 for p in perf if p.get("success")) / len(perf)
            if success_rate < 0.85:
                recommendations.append({
                    "category": "performance",
                    "priority": "high",
                    "recommendation": f"Improve success rate (current: {success_rate:.1%})"
                })
        
        # Knowledge recommendations
        if not self.knowledge_base:
            recommendations.append({
                "category": "knowledge",
                "priority": "high",
                "recommendation": "Build up knowledge base through continuous learning"
            })
        
        # Error pattern recommendations
        if self.error_patterns:
            recurring = len([e for e in self.error_patterns.values() if e["count"] >= self.failure_pattern_threshold])
            if recurring > 0:
                recommendations.append({
                    "category": "error_handling",
                    "priority": "high",
                    "recommendation": f"Address {recurring} recurring error patterns"
                })
        
        return recommendations
    
    async def end_learning_session(self, session_id: str, status: str = "completed") -> Dict:
        """Finalize a learning session."""
        if session_id not in self.learning_sessions:
            return {"error": f"Session {session_id} not found"}
        
        session = self.learning_sessions[session_id]
        session["status"] = status
        session["ended_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Ended learning session {session_id} with status {status}")
        return session
    
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
            # Backward compatible legacy knowledge_base storage (separate from Phase 7)
            if topic not in self.knowledge_base:
                self.knowledge_base[topic] = {
                    "first_seen": datetime.utcnow().isoformat(),
                    "frequency": 0,
                    "agents_used": [],
                    "sample_queries": [],
                    "_legacy_format": True,  # Mark as legacy format
                }
            entry = self.knowledge_base[topic]
            # Handle both legacy and Phase 7 formats
            if entry.get("_legacy_format"):
                entry["frequency"] = entry.get("frequency", 0) + 1
                entry["last_seen"] = datetime.utcnow().isoformat()
                if agent_used not in entry.get("agents_used", []):
                    if "agents_used" not in entry:
                        entry["agents_used"] = []
                    entry["agents_used"].append(agent_used)
                if len(entry.get("sample_queries", [])) < 5:
                    if "sample_queries" not in entry:
                        entry["sample_queries"] = []
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
        """Execute learning tasks with comprehensive action handling."""
        action = task.get("action", "")
        input_data = task.get("input_data", {})
        execution_context = task.get("execution_context", {})
        
        # Create learning context if available
        learning_context = None
        if execution_context:
            learning_context = LearningContext(
                request_id=execution_context.get("request_id", str(uuid.uuid4())),
                correlation_id=execution_context.get("correlation_id", str(uuid.uuid4())),
                trace_id=execution_context.get("trace_id", str(uuid.uuid4())),
                session_id=execution_context.get("session_id", str(uuid.uuid4())),
                conversation_id=execution_context.get("conversation_id"),
                agent_id=execution_context.get("agent_id"),
                user_id=execution_context.get("user_id"),
            )
        
        # Legacy actions for backward compatibility
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
                "experience_count": len(self.experience_records),
                "top_topics": self._get_top_topics(5),
                "total_learning_cycles": self.total_learning_cycles,
            }
        
        if action == "get_topic_knowledge":
            topic = input_data.get("topic", "")
            return self.knowledge_base.get(topic, {"error": "topic not found"})
        
        # Phase 7: Learning lifecycle
        if action == "create_session":
            context = learning_context or LearningContext(
                request_id=str(uuid.uuid4()),
                correlation_id=str(uuid.uuid4()),
                trace_id=str(uuid.uuid4()),
                session_id=str(uuid.uuid4()),
            )
            return await self.create_learning_session(context)
        
        if action == "start_session":
            session_id = input_data.get("session_id")
            return await self.start_learning_session(session_id)
        
        if action == "record_experience":
            session_id = input_data.get("session_id")
            experience = input_data.get("experience", {})
            record = await self.record_experience(session_id, experience)
            return record.as_dict()
        
        if action == "end_session":
            session_id = input_data.get("session_id")
            status = input_data.get("status", "completed")
            return await self.end_learning_session(session_id, status)
        
        # Phase 7: Knowledge management
        if action == "update_knowledge":
            return await self.update_knowledge(input_data)
        
        # Phase 7: Adaptation engine
        if action == "apply_adaptation":
            strategy = input_data.get("strategy")
            parameters = input_data.get("parameters", {})
            return await self.apply_adaptation(strategy, parameters)
        
        # Phase 7: Performance analysis
        if action == "analyze_performance":
            return await self.analyze_performance()
        
        # Phase 7: Self-evaluation
        if action == "evaluate_performance":
            focus_area = input_data.get("focus_area")
            return await self.evaluate_performance(focus_area)
        
        # Phase 7: Experience replay
        if action == "replay_experiences":
            filter_criteria = input_data.get("filter", {})
            limit = input_data.get("limit", 10)
            return await self.replay_experiences(filter_criteria, limit)
        
        # Phase 7: Get learning analytics
        if action == "get_learning_analytics":
            return {
                "total_sessions": len(self.learning_sessions),
                "total_experiences": len(self.experience_records),
                "total_knowledge_updates": len(self.knowledge_updates),
                "error_patterns": len(self.error_patterns),
                "adaptation_count": len(self.adaptation_log),
                "learning_cycles": self.total_learning_cycles,
                "quality_score": self.state.get("quality_score", 0.7),
                "confidence_score": self.state.get("confidence_score", 0.6),
            }
        
        # Default: legacy learn_from_interaction
        return await self.learn_from_interaction({
            "user_message": input_data.get("content", ""),
            "agent_used": input_data.get("agent_used", "orchestrator_agent"),
            "user_id": input_data.get("user_id", "default"),
        })
