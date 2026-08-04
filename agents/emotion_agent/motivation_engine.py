"""
Production Motivation Engine — Phase 8
Structured motivation lifecycle: goal tracking, scoring, history,
metrics, audit trail, burnout/stagnation detection, adaptation.
All thresholds are configuration-driven.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

logger = logging.getLogger(__name__)

_MOTIVATION_VERSION = "8.0.0"
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "emotion_config.yaml"


# ─── Config loader ────────────────────────────────────────────────────────────

def _load_motivation_config() -> Dict[str, Any]:
    if not _YAML_AVAILABLE or not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = _yaml.safe_load(f) or {}
        return raw.get("motivation", {})
    except Exception as exc:
        logger.warning("motivation_config.load_failed error=%s", exc)
        return {}


# ─── Goal Model ───────────────────────────────────────────────────────────────

@dataclass
class Goal:
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "default"
    title: str = ""
    description: str = ""
    status: str = "active"          # active | completed | abandoned | stagnant
    priority: int = 2               # 1=critical, 2=high, 3=medium, 4=low
    difficulty: float = 0.5         # 0.0–1.0
    progress: float = 0.0           # 0.0–1.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    check_ins: int = 0
    consecutive_failures: int = 0
    streak_days: int = 0
    last_activity_at: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def hours_since_activity(self) -> float:
        if not self.last_activity_at:
            created = datetime.fromisoformat(self.created_at)
            return (datetime.utcnow() - created).total_seconds() / 3600
        last = datetime.fromisoformat(self.last_activity_at)
        return (datetime.utcnow() - last).total_seconds() / 3600


# ─── Motivation Score ─────────────────────────────────────────────────────────

@dataclass
class MotivationScore:
    score_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    user_id: str = "default"
    overall: float = 0.60
    goal_motivation: float = 0.60
    task_motivation: float = 0.60
    confidence_influence: float = 0.0
    is_burned_out: bool = False
    is_stagnant: bool = False
    active_goals: int = 0
    completed_goals: int = 0
    components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Motivation Metrics ───────────────────────────────────────────────────────

@dataclass
class MotivationMetrics:
    total_goals_created: int = 0
    total_goals_completed: int = 0
    total_goals_abandoned: int = 0
    total_check_ins: int = 0
    burnout_detections: int = 0
    stagnation_detections: int = 0
    recommendations_generated: int = 0
    total_scoring_ms: float = 0.0
    sessions_created: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Production Motivation Engine ────────────────────────────────────────────

class MotivationEngine:
    """
    Production motivation engine.
    Manages goal lifecycle, motivation scoring, history, metrics,
    audit trail, burnout/stagnation detection, and adaptive recommendations.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        file_cfg = _load_motivation_config()
        self._cfg = {**file_cfg, **(config or {})}

        goal_cfg = self._cfg.get("goals", {})
        score_cfg = self._cfg.get("scoring", {})
        hist_cfg = self._cfg.get("history", {})

        self._max_goals_per_user = int(goal_cfg.get("max_goals_per_user", 50))
        self._max_total_goals = int(goal_cfg.get("max_total_goals", 500))
        self._default_difficulty = float(goal_cfg.get("default_difficulty", 0.5))
        self._stagnation_hours = float(goal_cfg.get("stagnation_threshold_hours", 24))
        self._burnout_window = int(goal_cfg.get("burnout_check_window", 10))
        self._burnout_failure_rate = float(goal_cfg.get("burnout_failure_rate_threshold", 0.70))

        self._base_motivation = float(score_cfg.get("base_motivation", 0.60))
        self._progress_weight = float(score_cfg.get("progress_weight", 0.30))
        self._difficulty_weight = float(score_cfg.get("difficulty_weight", 0.20))
        self._recency_weight = float(score_cfg.get("recency_weight", 0.15))
        self._streak_bonus = float(score_cfg.get("streak_bonus_per_day", 0.03))
        self._max_streak_bonus = float(score_cfg.get("max_streak_bonus", 0.20))
        self._failure_penalty = float(score_cfg.get("failure_penalty", 0.08))
        self._recovery_bonus = float(score_cfg.get("recovery_bonus", 0.05))

        max_hist = int(hist_cfg.get("max_motivation_history", 2000))
        max_audit = int(hist_cfg.get("max_audit_trail", 3000))

        # Goal registry: user_id -> {goal_id -> Goal}
        self._goals: Dict[str, Dict[str, Goal]] = {}
        self._score_history: Deque[Dict] = deque(maxlen=max_hist)
        self._audit_trail: Deque[Dict] = deque(maxlen=max_audit)
        self._adaptation_history: Deque[Dict] = deque(
            maxlen=int(self._cfg.get("adaptation", {}).get("max_adaptation_history", 1000))
        )
        self._metrics = MotivationMetrics()
        self._version = _MOTIVATION_VERSION
        self._running = False
        self._maintenance_task: Optional[asyncio.Task] = None
        self._maintenance_interval = float(
            self._cfg.get("maintenance", {}).get("interval_seconds", 300.0)
        )
        # Persistence
        persist_cfg = self._cfg.get("persistence", {})
        self._persist_enabled = bool(persist_cfg.get("enabled", True))
        self._persist_path = Path(
            persist_cfg.get("path", "data/motivation_state.json")
        )

    # ─── Engine Lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._load_persisted_state()
        self._maintenance_task = asyncio.create_task(
            self._maintenance_loop(), name="motivation_engine.maintenance"
        )
        logger.info("motivation_engine.started version=%s", self._version)

    async def stop(self) -> None:
        self._running = False
        if self._maintenance_task and not self._maintenance_task.done():
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        self._persist_state()
        logger.info("motivation_engine.stopped")

    async def _maintenance_loop(self) -> None:
        """Background: mark stagnant goals and persist state periodically."""
        while self._running:
            try:
                await asyncio.sleep(self._maintenance_interval)
                for user_id in list(self._goals.keys()):
                    self.mark_stagnant_goals(user_id)
                self._persist_state()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("motivation_engine.maintenance_error error=%s", exc)

    # ─── Persistence ──────────────────────────────────────────────────────────

    def _persist_state(self) -> None:
        if not self._persist_enabled:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": self._version,
                "timestamp": datetime.utcnow().isoformat(),
                "goals": {
                    uid: {gid: g.to_dict() for gid, g in user_goals.items()}
                    for uid, user_goals in self._goals.items()
                },
                "metrics": self._metrics.as_dict(),
                "score_history": list(self._score_history)[-200:],
                "audit_trail": list(self._audit_trail)[-500:],
            }
            self._persist_path.write_text(
                json.dumps(payload, default=str), encoding="utf-8"
            )
        except Exception as exc:
            logger.debug("motivation_engine.persist_error error=%s", exc)

    def _load_persisted_state(self) -> None:
        if not self._persist_enabled or not self._persist_path.exists():
            return
        try:
            raw = json.loads(self._persist_path.read_text(encoding="utf-8"))
            for uid, user_goals in raw.get("goals", {}).items():
                self._goals[uid] = {}
                for gid, gdata in user_goals.items():
                    # Reconstruct Goal from dict — only known fields
                    known = {k: v for k, v in gdata.items()
                             if k in Goal.__dataclass_fields__}
                    self._goals[uid][gid] = Goal(**known)
            for entry in raw.get("score_history", []):
                self._score_history.append(entry)
            for entry in raw.get("audit_trail", []):
                self._audit_trail.append(entry)
            logger.info("motivation_engine.state_loaded users=%d", len(self._goals))
        except Exception as exc:
            logger.warning("motivation_engine.load_error error=%s", exc)

    # ─── Goal Lifecycle ───────────────────────────────────────────────────────

    def create_goal(
        self,
        user_id: str,
        title: str,
        description: str = "",
        priority: int = 2,
        difficulty: Optional[float] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Goal:
        user_goals = self._goals.setdefault(user_id, {})
        if len(user_goals) >= self._max_goals_per_user:
            # Remove oldest completed/abandoned goal to make room
            removable = [g for g in user_goals.values() if g.status in ("completed", "abandoned")]
            if removable:
                oldest = min(removable, key=lambda g: g.created_at)
                del user_goals[oldest.goal_id]
            else:
                raise ValueError(f"User {user_id} has reached max goals ({self._max_goals_per_user})")

        goal = Goal(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            difficulty=difficulty if difficulty is not None else self._default_difficulty,
            last_activity_at=datetime.utcnow().isoformat(),
            tags=tags or [],
            metadata=metadata or {},
        )
        user_goals[goal.goal_id] = goal
        self._metrics.total_goals_created += 1
        self._audit("goal_created", {"goal_id": goal.goal_id, "user_id": user_id, "title": title})
        return goal

    def update_goal_progress(
        self,
        user_id: str,
        goal_id: str,
        progress: float,
        success: bool = True,
    ) -> Optional[Goal]:
        goal = self._get_goal(user_id, goal_id)
        if not goal:
            return None
        goal.progress = max(0.0, min(1.0, progress))
        goal.check_ins += 1
        goal.updated_at = datetime.utcnow().isoformat()
        goal.last_activity_at = datetime.utcnow().isoformat()
        self._metrics.total_check_ins += 1

        if success:
            goal.consecutive_failures = 0
            goal.streak_days = min(goal.streak_days + 1, 365)
        else:
            goal.consecutive_failures += 1
            goal.streak_days = 0

        if goal.progress >= 1.0:
            goal.status = "completed"
            goal.completed_at = datetime.utcnow().isoformat()
            self._metrics.total_goals_completed += 1
            self._audit("goal_completed", {"goal_id": goal_id, "user_id": user_id})

        self._audit("goal_progress_updated", {
            "goal_id": goal_id, "user_id": user_id,
            "progress": goal.progress, "success": success,
        })
        return goal

    def abandon_goal(self, user_id: str, goal_id: str, reason: str = "") -> bool:
        goal = self._get_goal(user_id, goal_id)
        if not goal:
            return False
        goal.status = "abandoned"
        goal.updated_at = datetime.utcnow().isoformat()
        self._metrics.total_goals_abandoned += 1
        self._audit("goal_abandoned", {"goal_id": goal_id, "user_id": user_id, "reason": reason})
        return True

    def get_goals(self, user_id: str, status: Optional[str] = None) -> List[Goal]:
        user_goals = self._goals.get(user_id, {})
        goals = list(user_goals.values())
        if status:
            goals = [g for g in goals if g.status == status]
        return goals

    def _get_goal(self, user_id: str, goal_id: str) -> Optional[Goal]:
        return self._goals.get(user_id, {}).get(goal_id)

    # ─── Motivation Scoring ───────────────────────────────────────────────────

    def compute_score(
        self,
        user_id: str,
        confidence_influence: float = 0.0,
        task_completion_rate: float = 0.5,
    ) -> MotivationScore:
        start = time.perf_counter()
        active_goals = self.get_goals(user_id, status="active")
        completed_goals = self.get_goals(user_id, status="completed")

        # Detect burnout and stagnation
        is_burned_out = self._detect_burnout(active_goals)
        is_stagnant = self._detect_stagnation(active_goals)

        if is_burned_out:
            self._metrics.burnout_detections += 1
        if is_stagnant:
            self._metrics.stagnation_detections += 1

        # Compute goal motivation
        goal_motivation = self._compute_goal_motivation(active_goals, completed_goals)

        # Compute task motivation from task completion rate
        task_motivation = self._base_motivation + (task_completion_rate - 0.5) * 0.4

        # Apply confidence influence
        task_motivation = max(0.0, min(1.0, task_motivation + confidence_influence))

        # Burnout/stagnation penalties
        if is_burned_out:
            goal_motivation = max(0.0, goal_motivation - 0.20)
            task_motivation = max(0.0, task_motivation - 0.15)
        if is_stagnant:
            goal_motivation = max(0.0, goal_motivation - 0.10)

        overall = round((goal_motivation * 0.6 + task_motivation * 0.4), 4)

        score = MotivationScore(
            user_id=user_id,
            overall=overall,
            goal_motivation=round(goal_motivation, 4),
            task_motivation=round(task_motivation, 4),
            confidence_influence=round(confidence_influence, 4),
            is_burned_out=is_burned_out,
            is_stagnant=is_stagnant,
            active_goals=len(active_goals),
            completed_goals=len(completed_goals),
            components={
                "base": self._base_motivation,
                "progress_contribution": self._progress_contribution(active_goals),
                "streak_bonus": self._streak_contribution(active_goals),
                "failure_penalty": self._failure_contribution(active_goals),
                "task_completion_rate": task_completion_rate,
                "confidence_influence": confidence_influence,
            },
        )

        self._score_history.append(score.to_dict())
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._metrics.total_scoring_ms += duration_ms
        self._audit("motivation_scored", {
            "user_id": user_id, "overall": overall,
            "is_burned_out": is_burned_out, "is_stagnant": is_stagnant,
            "duration_ms": duration_ms,
        })
        return score

    def _compute_goal_motivation(
        self, active: List[Goal], completed: List[Goal]
    ) -> float:
        if not active and not completed:
            return self._base_motivation

        score = self._base_motivation

        # Progress contribution
        score += self._progress_contribution(active) * self._progress_weight

        # Difficulty contribution (harder goals = more motivation when progressing)
        if active:
            avg_difficulty = sum(g.difficulty for g in active) / len(active)
            score += avg_difficulty * self._difficulty_weight * 0.5

        # Recency contribution
        score += self._recency_contribution(active) * self._recency_weight

        # Streak bonus
        score += self._streak_contribution(active)

        # Failure penalty
        score -= self._failure_contribution(active)

        # Completion bonus
        if completed:
            score += min(0.10, len(completed) * 0.01)

        return max(0.0, min(1.0, score))

    def _progress_contribution(self, goals: List[Goal]) -> float:
        if not goals:
            return 0.0
        return sum(g.progress for g in goals) / len(goals)

    def _recency_contribution(self, goals: List[Goal]) -> float:
        if not goals:
            return 0.0
        recent = [g for g in goals if g.hours_since_activity() < 24]
        return len(recent) / len(goals)

    def _streak_contribution(self, goals: List[Goal]) -> float:
        if not goals:
            return 0.0
        max_streak = max(g.streak_days for g in goals)
        return min(self._max_streak_bonus, max_streak * self._streak_bonus)

    def _failure_contribution(self, goals: List[Goal]) -> float:
        if not goals:
            return 0.0
        total_failures = sum(g.consecutive_failures for g in goals)
        return min(0.30, total_failures * self._failure_penalty)

    # ─── Burnout / Stagnation Detection ──────────────────────────────────────

    def _detect_burnout(self, active_goals: List[Goal]) -> bool:
        if not active_goals:
            return False
        recent_checkins = []
        for g in active_goals:
            recent_checkins.extend([g.consecutive_failures] * min(g.check_ins, self._burnout_window))
        if len(recent_checkins) < self._burnout_window:
            return False
        failure_rate = sum(1 for f in recent_checkins[-self._burnout_window:] if f > 0) / self._burnout_window
        return failure_rate >= self._burnout_failure_rate

    def _detect_stagnation(self, active_goals: List[Goal]) -> bool:
        if not active_goals:
            return False
        stagnant = [g for g in active_goals if g.hours_since_activity() >= self._stagnation_hours]
        return len(stagnant) > len(active_goals) * 0.5

    # ─── Stagnation Marking ───────────────────────────────────────────────────

    def mark_stagnant_goals(self, user_id: str) -> List[str]:
        """Mark goals that have been inactive beyond the stagnation threshold."""
        stagnant_ids = []
        for goal in self.get_goals(user_id, status="active"):
            if goal.hours_since_activity() >= self._stagnation_hours:
                goal.status = "stagnant"
                goal.updated_at = datetime.utcnow().isoformat()
                stagnant_ids.append(goal.goal_id)
                self._audit("goal_stagnant", {"goal_id": goal.goal_id, "user_id": user_id})
        return stagnant_ids

    # ─── History & Analytics ──────────────────────────────────────────────────

    def get_score_history(self, user_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        history = list(self._score_history)[-limit:]
        if user_id:
            history = [h for h in history if h.get("user_id") == user_id]
        return history

    def get_audit_trail(self, limit: int = 100) -> List[Dict]:
        return list(self._audit_trail)[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        m = self._metrics.as_dict()
        m["version"] = self._version
        m["score_history_size"] = len(self._score_history)
        m["total_users"] = len(self._goals)
        m["total_active_goals"] = sum(
            len([g for g in user_goals.values() if g.status == "active"])
            for user_goals in self._goals.values()
        )
        m["avg_scoring_ms"] = round(
            self._metrics.total_scoring_ms / max(1, len(self._score_history)), 2
        )
        return m

    def get_analytics(self, user_id: str) -> Dict[str, Any]:
        history = [h for h in self._score_history if h.get("user_id") == user_id]
        if not history:
            return {"error": "no_history", "user_id": user_id}

        scores = [h["overall"] for h in history[-20:]]
        trend = "increasing" if scores[-1] > scores[0] else "decreasing" if scores[-1] < scores[0] else "stable"

        active = self.get_goals(user_id, status="active")
        completed = self.get_goals(user_id, status="completed")

        return {
            "user_id": user_id,
            "score_snapshots": len(history),
            "current_score": round(scores[-1], 4) if scores else 0.0,
            "average_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "trend": trend,
            "active_goals": len(active),
            "completed_goals": len(completed),
            "burnout_risk": self._detect_burnout(active),
            "stagnation_risk": self._detect_stagnation(active),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ─── Validation ───────────────────────────────────────────────────────────

    def validate_goal_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        if not isinstance(data.get("title", ""), str) or not data.get("title", "").strip():
            errors.append("title must be a non-empty string")
        difficulty = data.get("difficulty", self._default_difficulty)
        if not isinstance(difficulty, (int, float)) or not (0.0 <= float(difficulty) <= 1.0):
            errors.append("difficulty must be a float in [0.0, 1.0]")
        priority = data.get("priority", 2)
        if not isinstance(priority, int) or priority not in (1, 2, 3, 4):
            errors.append("priority must be an integer in {1, 2, 3, 4}")
        return {"valid": len(errors) == 0, "errors": errors}

    def validate_signal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate an incoming motivation signal payload."""
        errors = []
        if not isinstance(data.get("user_id", "default"), str):
            errors.append("user_id must be a string")
        score = data.get("score")
        if score is not None and not isinstance(score, (int, float)):
            errors.append("score must be numeric")
        return {"valid": len(errors) == 0, "errors": errors}

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _audit(self, event: str, data: Dict[str, Any]) -> None:
        self._audit_trail.append({
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            **data,
        })
