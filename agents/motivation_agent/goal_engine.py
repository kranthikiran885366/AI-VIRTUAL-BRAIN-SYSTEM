"""
Phase 8: Goal Engine for Production Motivation System

Implements:
- Goal CRUD operations with versioning
- Progress tracking
- Difficulty estimation
- Struggle detection and classification
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Set

logger = logging.getLogger(__name__)


class GoalStatus(Enum):
    """Goal lifecycle status."""
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DifficultyLevel(Enum):
    """Goal difficulty classification."""
    TRIVIAL = "trivial"           # 0.0 - 0.2
    EASY = "easy"                 # 0.2 - 0.4
    MODERATE = "moderate"         # 0.4 - 0.6
    CHALLENGING = "challenging"   # 0.6 - 0.8
    VERY_DIFFICULT = "very_difficult"  # 0.8 - 1.0


class StruggleType(Enum):
    """Classification of struggle types."""
    MOTIVATION_LOW = "motivation_low"
    TIME_PRESSURE = "time_pressure"
    UNCLEAR_STEPS = "unclear_steps"
    RESOURCE_CONSTRAINT = "resource_constraint"
    SKILL_GAP = "skill_gap"
    EXTERNAL_BLOCKER = "external_blocker"
    FATIGUE = "fatigue"
    DISTRACTION = "distraction"
    DOUBT = "doubt"


@dataclass
class Milestone:
    """A milestone within a goal."""
    id: str
    name: str
    description: str
    target_completion: datetime
    completion_percentage: float = 0.0
    completed_at: Optional[datetime] = None
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "target_completion": self.target_completion.isoformat(),
            "completion_percentage": self.completion_percentage,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Milestone":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            target_completion=datetime.fromisoformat(data["target_completion"]),
            completion_percentage=data.get("completion_percentage", 0.0),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            notes=data.get("notes", ""),
        )


@dataclass
class GoalProgress:
    """Progress tracking for a goal."""
    completion_percentage: float = 0.0
    completed_at: Optional[datetime] = None
    time_spent_seconds: float = 0.0
    last_update: datetime = field(default_factory=datetime.utcnow)
    checkpoint_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "completion_percentage": self.completion_percentage,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "time_spent_seconds": self.time_spent_seconds,
            "last_update": self.last_update.isoformat(),
            "checkpoint_count": self.checkpoint_count,
        }


@dataclass
class Goal:
    """A goal with full lifecycle and progress tracking."""
    id: str
    agent_id: str
    title: str
    description: str
    status: GoalStatus
    created_at: datetime
    target_completion: datetime
    difficulty_estimate: float  # 0.0-1.0
    priority: int  # 1-10, higher = more important
    context: Dict[str, Any] = field(default_factory=dict)
    milestones: List[Milestone] = field(default_factory=list)
    progress: GoalProgress = field(default_factory=GoalProgress)
    tags: List[str] = field(default_factory=list)
    related_goal_ids: List[str] = field(default_factory=list)
    notes: str = ""
    version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "target_completion": self.target_completion.isoformat(),
            "difficulty_estimate": self.difficulty_estimate,
            "priority": self.priority,
            "context": self.context,
            "milestones": [m.to_dict() for m in self.milestones],
            "progress": self.progress.to_dict(),
            "tags": self.tags,
            "related_goal_ids": self.related_goal_ids,
            "notes": self.notes,
            "version": self.version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        """Create from dictionary."""
        milestones = [
            Milestone.from_dict(m) for m in data.get("milestones", [])
        ]
        
        progress_data = data.get("progress", {})
        progress = GoalProgress(
            completion_percentage=progress_data.get("completion_percentage", 0.0),
            completed_at=datetime.fromisoformat(progress_data["completed_at"]) if progress_data.get("completed_at") else None,
            time_spent_seconds=progress_data.get("time_spent_seconds", 0.0),
            last_update=datetime.fromisoformat(progress_data["last_update"]) if progress_data.get("last_update") else datetime.utcnow(),
            checkpoint_count=progress_data.get("checkpoint_count", 0),
        )
        
        return cls(
            id=data["id"],
            agent_id=data["agent_id"],
            title=data["title"],
            description=data["description"],
            status=GoalStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            target_completion=datetime.fromisoformat(data["target_completion"]),
            difficulty_estimate=data["difficulty_estimate"],
            priority=data["priority"],
            context=data.get("context", {}),
            milestones=milestones,
            progress=progress,
            tags=data.get("tags", []),
            related_goal_ids=data.get("related_goal_ids", []),
            notes=data.get("notes", ""),
            version=data.get("version", 1),
        )


@dataclass
class StruggleContext:
    """Context for a detected struggle."""
    struggle_type: StruggleType
    confidence: float  # 0.0-1.0
    current_emotion_state: Dict[str, float]
    goal_difficulty: float
    progress_rate: float  # 0.0-1.0
    time_elapsed: float  # seconds
    time_remaining: float  # seconds
    context_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "struggle_type": self.struggle_type.value,
            "confidence": self.confidence,
            "current_emotion_state": self.current_emotion_state,
            "goal_difficulty": self.goal_difficulty,
            "progress_rate": self.progress_rate,
            "time_elapsed": self.time_elapsed,
            "time_remaining": self.time_remaining,
            "context_data": self.context_data,
        }


class GoalEngine:
    """
    Goal management engine with CRUD, progress tracking, and difficulty estimation.
    
    Responsibilities:
    - Goal lifecycle management
    - Progress tracking and checkpoints
    - Difficulty estimation
    - Struggle detection and classification
    """
    
    def __init__(self):
        """Initialize the goal engine."""
        self._goals: Dict[str, Goal] = {}
        self._agent_goals: Dict[str, List[str]] = {}  # agent_id -> [goal_ids]
        self._lock = asyncio.Lock()
    
    async def create_goal(
        self,
        agent_id: str,
        title: str,
        description: str,
        target_completion: datetime,
        difficulty_estimate: Optional[float] = None,
        priority: int = 5,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Goal:
        """
        Create a new goal.
        
        Args:
            agent_id: ID of agent managing the goal
            title: Goal title
            description: Goal description
            target_completion: Target completion date
            difficulty_estimate: Optional difficulty (0.0-1.0, auto-estimated if None)
            priority: Priority 1-10
            context: Optional context data
            tags: Optional tags for categorization
        
        Returns:
            Created Goal
        """
        async with self._lock:
            goal_id = str(uuid.uuid4())
            
            # Estimate difficulty if not provided
            if difficulty_estimate is None:
                difficulty_estimate = self._estimate_difficulty({
                    "title": title,
                    "description": description,
                    "target_completion": target_completion,
                })
            
            goal = Goal(
                id=goal_id,
                agent_id=agent_id,
                title=title,
                description=description,
                status=GoalStatus.CREATED,
                created_at=datetime.utcnow(),
                target_completion=target_completion,
                difficulty_estimate=max(0.0, min(1.0, difficulty_estimate)),
                priority=max(1, min(10, priority)),
                context=context or {},
                tags=tags or [],
            )
            
            # Store goal
            self._goals[goal_id] = goal
            
            # Index by agent
            if agent_id not in self._agent_goals:
                self._agent_goals[agent_id] = []
            self._agent_goals[agent_id].append(goal_id)
            
            logger.info(
                f"Created goal {goal_id}: {title} "
                f"(difficulty={goal.difficulty_estimate}, priority={priority})"
            )
            
            return goal_id
    
    async def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Get a goal by ID."""
        async with self._lock:
            return self._goals.get(goal_id)
    
    async def get_agent_goals(
        self,
        agent_id: str,
        status: Optional[GoalStatus] = None,
    ) -> List[Goal]:
        """Get all goals for an agent, optionally filtered by status."""
        async with self._lock:
            goal_ids = self._agent_goals.get(agent_id, [])
            goals = [self._goals[gid] for gid in goal_ids if gid in self._goals]
            
            if status:
                goals = [g for g in goals if g.status == status]
            
            return goals
    
    async def update_progress(
        self,
        goal_id: str,
        completion_percentage: Optional[float] = None,
        time_spent_seconds: Optional[float] = None,
        add_checkpoint: bool = False,
        notes: Optional[str] = None,
    ) -> Goal:
        """
        Update goal progress.
        
        Args:
            goal_id: ID of goal
            completion_percentage: New completion percentage
            time_spent_seconds: Additional time spent
            add_checkpoint: Whether to add a progress checkpoint
            notes: Optional progress notes
        
        Returns:
            Updated Goal
        
        Raises:
            ValueError: If goal not found
        """
        async with self._lock:
            if goal_id not in self._goals:
                raise ValueError(f"Goal {goal_id} not found")
            
            goal = self._goals[goal_id]
            
            # Update completion percentage
            if completion_percentage is not None:
                goal.progress.completion_percentage = max(0.0, min(1.0, completion_percentage))
            
            # Update time spent
            if time_spent_seconds is not None:
                goal.progress.time_spent_seconds += time_spent_seconds
            
            # Add checkpoint
            if add_checkpoint:
                goal.progress.checkpoint_count += 1
            
            # Update timestamp
            goal.progress.last_update = datetime.utcnow()
            
            # Append notes
            if notes:
                goal.notes += f"\n[{datetime.utcnow().isoformat()}] {notes}"
            
            # Auto-transition to IN_PROGRESS if not already
            if goal.status == GoalStatus.CREATED and goal.progress.completion_percentage > 0:
                goal.status = GoalStatus.IN_PROGRESS
            
            # Auto-complete if 100%
            if goal.progress.completion_percentage >= 1.0 and goal.status in (
                GoalStatus.CREATED, GoalStatus.IN_PROGRESS
            ):
                goal.status = GoalStatus.COMPLETED
                goal.progress.completed_at = datetime.utcnow()
            
            logger.info(
                f"Updated goal {goal_id} progress to {goal.progress.completion_percentage * 100:.0f}%"
            )
            
            return goal
    
    async def add_milestone(
        self,
        goal_id: str,
        name: str,
        description: str,
        target_completion: datetime,
    ) -> Goal:
        """Add a milestone to a goal."""
        async with self._lock:
            if goal_id not in self._goals:
                raise ValueError(f"Goal {goal_id} not found")
            
            goal = self._goals[goal_id]
            
            milestone = Milestone(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                target_completion=target_completion,
            )
            
            goal.milestones.append(milestone)
            logger.info(f"Added milestone to goal {goal_id}: {name}")
            
            return goal
    
    async def complete_milestone(
        self,
        goal_id: str,
        milestone_id: str,
    ) -> Goal:
        """Mark a milestone as complete."""
        async with self._lock:
            if goal_id not in self._goals:
                raise ValueError(f"Goal {goal_id} not found")
            
            goal = self._goals[goal_id]
            
            for milestone in goal.milestones:
                if milestone.id == milestone_id:
                    milestone.completion_percentage = 1.0
                    milestone.completed_at = datetime.utcnow()
                    logger.info(f"Completed milestone {milestone_id} in goal {goal_id}")
                    break
            
            return goal
    
    async def mark_failed(
        self,
        goal_id: str,
        reason: Optional[str] = None,
    ) -> Goal:
        """Mark a goal as failed."""
        async with self._lock:
            if goal_id not in self._goals:
                raise ValueError(f"Goal {goal_id} not found")
            
            goal = self._goals[goal_id]
            goal.status = GoalStatus.FAILED
            
            if reason:
                goal.notes += f"\n[{datetime.utcnow().isoformat()}] Failed: {reason}"
            
            logger.info(f"Marked goal {goal_id} as failed")
            
            return goal
    
    def _estimate_difficulty(self, goal_spec: Dict[str, Any]) -> float:
        """
        Estimate goal difficulty heuristically.
        
        Factors:
        - Time available (shorter = harder)
        - Complexity of description (longer = harder)
        - Priority (higher = perceived as harder)
        """
        base_difficulty = 0.5
        
        # Time factor
        if "target_completion" in goal_spec:
            target = goal_spec["target_completion"]
            now = datetime.utcnow()
            days_available = (target - now).days
            
            if days_available < 1:
                base_difficulty += 0.3
            elif days_available < 3:
                base_difficulty += 0.2
            elif days_available < 7:
                base_difficulty += 0.1
        
        # Description complexity (word count as proxy)
        if "description" in goal_spec:
            word_count = len(goal_spec["description"].split())
            if word_count > 100:
                base_difficulty += 0.1
            elif word_count > 200:
                base_difficulty += 0.2
        
        return min(1.0, base_difficulty)
    
    async def detect_struggle(
        self,
        agent_id: str,
        goal_id: str,
        text: str,
        current_emotion_state: Optional[Dict[str, float]] = None,
    ) -> StruggleContext:
        """
        Detect struggle type from text and context.
        
        Uses heuristic classification to identify struggle types.
        """
        goal = await self.get_goal(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        
        # Analyze text for struggle indicators
        text_lower = text.lower()
        
        # Calculate struggle scores
        struggle_scores = {
            StruggleType.MOTIVATION_LOW: self._score_motivation_low(text_lower),
            StruggleType.TIME_PRESSURE: self._score_time_pressure(text_lower, goal),
            StruggleType.UNCLEAR_STEPS: self._score_unclear_steps(text_lower),
            StruggleType.RESOURCE_CONSTRAINT: self._score_resource_constraint(text_lower),
            StruggleType.SKILL_GAP: self._score_skill_gap(text_lower),
            StruggleType.EXTERNAL_BLOCKER: self._score_external_blocker(text_lower),
            StruggleType.FATIGUE: self._score_fatigue(text_lower),
            StruggleType.DISTRACTION: self._score_distraction(text_lower),
            StruggleType.DOUBT: self._score_doubt(text_lower),
        }
        
        # Find dominant struggle type
        best_struggle = max(struggle_scores, key=struggle_scores.get)
        confidence = struggle_scores[best_struggle]
        
        # Calculate progress rate
        progress_rate = goal.progress.completion_percentage
        
        # Calculate time metrics
        time_spent = goal.progress.time_spent_seconds
        time_available = (goal.target_completion - datetime.utcnow()).total_seconds()
        time_remaining = max(0, time_available)
        
        return StruggleContext(
            struggle_type=best_struggle,
            confidence=confidence,
            current_emotion_state=current_emotion_state or {},
            goal_difficulty=goal.difficulty_estimate,
            progress_rate=progress_rate,
            time_elapsed=time_spent,
            time_remaining=time_remaining,
            context_data={
                "goal_title": goal.title,
                "goal_priority": goal.priority,
                "milestones_completed": sum(1 for m in goal.milestones if m.completed_at),
            },
        )
    
    # Struggle detection scoring methods
    def _score_motivation_low(self, text: str) -> float:
        """Score for low motivation struggle."""
        keywords = ["don't feel", "no energy", "unmotivated", "procrastinating", "lazy"]
        return sum(1 for kw in keywords if kw in text) / 5.0
    
    def _score_time_pressure(self, text: str, goal: Goal) -> float:
        """Score for time pressure struggle."""
        keywords = ["rush", "deadline", "not enough time", "running out", "time pressure"]
        time_score = sum(1 for kw in keywords if kw in text) / 5.0
        
        # Boost if actually running out of time
        time_remaining = (goal.target_completion - datetime.utcnow()).days
        if time_remaining < 1:
            time_score = max(time_score, 0.7)
        elif time_remaining < 3:
            time_score = max(time_score, 0.5)
        
        return min(1.0, time_score)
    
    def _score_unclear_steps(self, text: str) -> float:
        """Score for unclear steps struggle."""
        keywords = ["confused", "not sure", "how to", "don't know where", "unclear"]
        return sum(1 for kw in keywords if kw in text) / 5.0
    
    def _score_resource_constraint(self, text: str) -> float:
        """Score for resource constraint struggle."""
        keywords = ["need", "missing", "can't access", "don't have", "limited"]
        return sum(1 for kw in keywords if kw in text) / 5.0
    
    def _score_skill_gap(self, text: str) -> float:
        """Score for skill gap struggle."""
        keywords = ["skill", "don't know how", "learn", "never done", "unfamiliar"]
        return sum(1 for kw in keywords if kw in text) / 5.0
    
    def _score_external_blocker(self, text: str) -> float:
        """Score for external blocker."""
        keywords = ["waiting for", "depends on", "blocked", "external", "other"]
        return sum(1 for kw in keywords if kw in text) / 5.0
    
    def _score_fatigue(self, text: str) -> float:
        """Score for fatigue struggle."""
        keywords = ["tired", "exhausted", "burned out", "fatigue", "drained"]
        return sum(1 for kw in keywords if kw in text) / 5.0
    
    def _score_distraction(self, text: str) -> float:
        """Score for distraction struggle."""
        keywords = ["distracted", "focus", "attention", "sidetracked"]
        return sum(1 for kw in keywords if kw in text) / 5.0
    
    def _score_doubt(self, text: str) -> float:
        """Score for doubt struggle."""
        keywords = ["doubt", "unsure", "question", "wrong", "mistake"]
        return sum(1 for kw in keywords if kw in text) / 5.0
    
    async def to_dict(self) -> Dict[str, Any]:
        """Serialize engine state."""
        async with self._lock:
            return {
                "goals": {gid: goal.to_dict() for gid, goal in self._goals.items()},
                "agent_goals": self._agent_goals.copy(),
            }
    
    async def from_dict(self, data: Dict[str, Any]) -> None:
        """Deserialize engine state."""
        async with self._lock:
            self._goals = {
                gid: Goal.from_dict(goal_data)
                for gid, goal_data in data.get("goals", {}).items()
            }
            self._agent_goals = data.get("agent_goals", {})
    
    async def clear(self) -> None:
        """Clear all goals (for testing)."""
        async with self._lock:
            self._goals.clear()
            self._agent_goals.clear()
