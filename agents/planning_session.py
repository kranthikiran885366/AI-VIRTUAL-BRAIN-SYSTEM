"""
Planning Session & Lifecycle Management for Phase 6 Planning Engine

Implements:
- Plan session tracking and lifecycle
- Plan state machine (DRAFT → ACTIVE → COMPLETED)
- Plan versioning with change tracking
- Plan recovery on failure
- Session checkpoint management
- Audit trail maintenance

Production-grade session management integrated with planning system.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

try:
    from agents.planning_models import (
        PlanStatus,
        PlanSession,
        PlanVersion,
        AuditRecord,
        ProductionPlan,
    )
except ImportError:
    from planning_models import (  # type: ignore[no-redef]
        PlanStatus,
        PlanSession,
        PlanVersion,
        AuditRecord,
        ProductionPlan,
    )

logger = logging.getLogger(__name__)


class PlanTransition(str, Enum):
    """Valid plan state transitions."""
    DRAFT_TO_ACTIVE = "draft_to_active"
    ACTIVE_TO_PAUSED = "active_to_paused"
    PAUSED_TO_ACTIVE = "paused_to_active"
    ACTIVE_TO_COMPLETED = "active_to_completed"
    ACTIVE_TO_FAILED = "active_to_failed"
    DRAFT_TO_CANCELLED = "draft_to_cancelled"
    ANY_TO_CANCELLED = "any_to_cancelled"


class PlanningSessionManager:
    """Production plan session management."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize session manager."""
        self.config = config or {}
        self.version = "1.0.0"
        self.sessions: Dict[str, PlanSession] = {}
        self.checkpoints: Dict[str, List[Dict[str, Any]]] = {}
        self.max_session_duration_hours = self.config.get("max_session_duration_hours", 24)
        self.checkpoint_interval_minutes = self.config.get("checkpoint_interval_minutes", 15)
        self.enable_recovery = self.config.get("enable_recovery", True)
        self.recovery_retention_days = self.config.get("recovery_retention_days", 30)
        self.valid_transitions = self._initialize_transitions()
        logger.info("PlanningSessionManager initialized", extra={"version": self.version})

    def _initialize_transitions(self) -> Dict[PlanStatus, List[PlanStatus]]:
        """Initialize valid state transitions."""
        return {
            PlanStatus.DRAFT: [PlanStatus.ACTIVE, PlanStatus.CANCELLED],
            PlanStatus.ACTIVE: [PlanStatus.PAUSED, PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED],
            PlanStatus.PAUSED: [PlanStatus.ACTIVE, PlanStatus.CANCELLED],
            PlanStatus.COMPLETED: [PlanStatus.CANCELLED],
            PlanStatus.FAILED: [PlanStatus.ACTIVE, PlanStatus.CANCELLED],
            PlanStatus.CANCELLED: [],
        }

    async def create_session(
        self,
        plan_id: str,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        planning_strategy: str = "goal_decomposition",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PlanSession:
        """
        Create a new planning session.

        Args:
            plan_id: Plan ID
            request_id: Request ID for tracing
            correlation_id: Correlation ID for tracing
            trace_id: Trace ID for observability
            planning_strategy: Planning strategy used
            metadata: Additional session metadata

        Returns:
            Created PlanSession
        """
        session_id = str(uuid.uuid4())
        metadata = metadata or {}

        session = PlanSession(
            session_id=session_id,
            plan_id=plan_id,
            request_id=request_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            created_at=datetime.utcnow().isoformat(),
            planning_strategy=planning_strategy,
            metadata=metadata,
        )

        self.sessions[session_id] = session
        self.checkpoints[session_id] = []

        logger.info(
            "Planning session created",
            extra={
                "session_id": session_id,
                "plan_id": plan_id,
                "correlation_id": correlation_id,
            },
        )
        return session

    async def end_session(
        self,
        session_id: str,
        success: bool = True,
    ) -> PlanSession:
        """
        End a planning session.

        Args:
            session_id: Session ID
            success: Whether session completed successfully

        Returns:
            Updated session

        Raises:
            ValueError: If session not found
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.sessions[session_id]
        session.completed_at = datetime.utcnow().isoformat()

        # Calculate duration
        start = datetime.fromisoformat(session.created_at)
        end = datetime.fromisoformat(session.completed_at)
        session.duration_seconds = (end - start).total_seconds()

        logger.info(
            "Planning session ended",
            extra={
                "session_id": session_id,
                "success": success,
                "duration_seconds": session.duration_seconds,
            },
        )
        return session

    async def get_session(self, session_id: str) -> Optional[PlanSession]:
        """Get session by ID."""
        return self.sessions.get(session_id)

    async def list_sessions_for_plan(self, plan_id: str) -> List[PlanSession]:
        """Get all sessions for a plan."""
        return [s for s in self.sessions.values() if s.plan_id == plan_id]


class PlanStateMachine:
    """Plan lifecycle state machine."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize state machine."""
        self.config = config or {}
        self.version = "1.0.0"
        self.state_history: Dict[str, List[Dict[str, Any]]] = {}
        self.valid_transitions = self._initialize_transitions()
        self.state_handlers: Dict[str, List[callable]] = {}
        logger.info("PlanStateMachine initialized", extra={"version": self.version})

    def _initialize_transitions(self) -> Dict[PlanStatus, List[PlanStatus]]:
        """Initialize valid state transitions."""
        return {
            PlanStatus.DRAFT: [PlanStatus.ACTIVE, PlanStatus.CANCELLED],
            PlanStatus.ACTIVE: [PlanStatus.PAUSED, PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED],
            PlanStatus.PAUSED: [PlanStatus.ACTIVE, PlanStatus.CANCELLED],
            PlanStatus.COMPLETED: [],
            PlanStatus.FAILED: [PlanStatus.ACTIVE, PlanStatus.CANCELLED],
            PlanStatus.CANCELLED: [],
        }

    async def transition_plan(
        self,
        plan: ProductionPlan,
        new_status: PlanStatus,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProductionPlan:
        """
        Transition plan to new status.

        Args:
            plan: Plan to transition
            new_status: New status
            reason: Reason for transition
            metadata: Additional metadata

        Returns:
            Updated plan

        Raises:
            ValueError: If transition not valid
        """
        current_status = plan.status
        metadata = metadata or {}

        # Validate transition
        if new_status not in self.valid_transitions.get(current_status, []):
            raise ValueError(
                f"Invalid transition: {current_status.value} → {new_status.value}"
            )

        # Perform transition
        old_status = plan.status
        plan.status = new_status
        plan.updated_at = datetime.utcnow().isoformat()

        # Set timestamps based on status
        if new_status == PlanStatus.ACTIVE and not plan.started_at:
            plan.started_at = datetime.utcnow().isoformat()
        elif new_status in (PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED):
            if not plan.completed_at:
                plan.completed_at = datetime.utcnow().isoformat()

        # Add to history
        plan.version_history.append(
            PlanVersion(
                version_number=len(plan.version_history) + 1,
                created_at=datetime.utcnow().isoformat(),
                change_reason=reason or f"Status: {old_status.value} → {new_status.value}",
                changes_summary=f"Plan transitioned from {old_status.value} to {new_status.value}",
                metadata=metadata,
            )
        )

        # Add audit record
        plan.audit_trail.append(
            AuditRecord(
                plan_id=plan.plan_id,
                goal_id=plan.goal_id,
                event_type="plan_status_changed",
                event_time=datetime.utcnow().isoformat(),
                details={
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "reason": reason,
                },
                correlation_id=plan.plan_context.correlation_id,
                trace_id=plan.plan_context.trace_id,
            )
        )

        logger.info(
            "Plan transitioned",
            extra={
                "plan_id": plan.plan_id,
                "old_status": old_status.value,
                "new_status": new_status.value,
                "reason": reason,
            },
        )
        return plan

    async def can_transition(
        self,
        current_status: PlanStatus,
        target_status: PlanStatus,
    ) -> bool:
        """Check if transition is valid."""
        return target_status in self.valid_transitions.get(current_status, [])

    async def get_valid_transitions(
        self,
        current_status: PlanStatus,
    ) -> List[PlanStatus]:
        """Get valid target statuses from current status."""
        return self.valid_transitions.get(current_status, [])


class PlanCheckpointManager:
    """Manage plan checkpoints for recovery."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize checkpoint manager."""
        self.config = config or {}
        self.version = "1.0.0"
        self.checkpoints: Dict[str, List[Dict[str, Any]]] = {}
        self.max_checkpoints_per_plan = self.config.get("max_checkpoints_per_plan", 10)
        logger.info("PlanCheckpointManager initialized", extra={"version": self.version})

    async def create_checkpoint(
        self,
        plan: ProductionPlan,
        reason: str = "automatic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a checkpoint of current plan state.

        Args:
            plan: Plan to checkpoint
            reason: Reason for checkpoint
            metadata: Additional metadata

        Returns:
            Checkpoint record
        """
        checkpoint = {
            "checkpoint_id": str(uuid.uuid4()),
            "plan_id": plan.plan_id,
            "timestamp": datetime.utcnow().isoformat(),
            "version": plan.current_version,
            "status": plan.status.value,
            "progress": plan.execution_progress.progress_percentage,
            "reason": reason,
            "metadata": metadata or {},
            "plan_snapshot": plan.to_dict(),
        }

        if plan.plan_id not in self.checkpoints:
            self.checkpoints[plan.plan_id] = []

        self.checkpoints[plan.plan_id].append(checkpoint)

        # Limit checkpoints retained
        if len(self.checkpoints[plan.plan_id]) > self.max_checkpoints_per_plan:
            self.checkpoints[plan.plan_id].pop(0)

        logger.info(
            "Plan checkpoint created",
            extra={
                "plan_id": plan.plan_id,
                "checkpoint_id": checkpoint["checkpoint_id"],
                "reason": reason,
            },
        )
        return checkpoint

    async def recover_from_checkpoint(
        self,
        plan_id: str,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Recover plan from checkpoint.

        Args:
            plan_id: Plan ID
            checkpoint_id: Specific checkpoint to recover (None = latest)

        Returns:
            Checkpoint data or None if not found

        Raises:
            ValueError: If plan has no checkpoints
        """
        if plan_id not in self.checkpoints or not self.checkpoints[plan_id]:
            raise ValueError(f"No checkpoints found for plan {plan_id}")

        if checkpoint_id:
            # Find specific checkpoint
            checkpoint = next(
                (c for c in self.checkpoints[plan_id] if c["checkpoint_id"] == checkpoint_id),
                None,
            )
            if not checkpoint:
                raise ValueError(f"Checkpoint {checkpoint_id} not found")
        else:
            # Use latest checkpoint
            checkpoint = self.checkpoints[plan_id][-1]

        logger.info(
            "Plan recovered from checkpoint",
            extra={
                "plan_id": plan_id,
                "checkpoint_id": checkpoint["checkpoint_id"],
                "timestamp": checkpoint["timestamp"],
            },
        )
        return checkpoint

    async def list_checkpoints(self, plan_id: str) -> List[Dict[str, Any]]:
        """Get all checkpoints for a plan."""
        return self.checkpoints.get(plan_id, [])

    async def cleanup_old_checkpoints(
        self,
        retention_days: int = 30,
    ) -> int:
        """
        Clean up old checkpoints beyond retention period.

        Args:
            retention_days: Days to retain checkpoints

        Returns:
            Number of checkpoints deleted
        """
        deleted = 0
        cutoff_time = datetime.utcnow() - timedelta(days=retention_days)

        for plan_id, checkpoints in list(self.checkpoints.items()):
            remaining = []
            for checkpoint in checkpoints:
                checkpoint_time = datetime.fromisoformat(checkpoint["timestamp"])
                if checkpoint_time > cutoff_time:
                    remaining.append(checkpoint)
                else:
                    deleted += 1

            if remaining:
                self.checkpoints[plan_id] = remaining
            else:
                del self.checkpoints[plan_id]

        logger.info(
            "Checkpoints cleaned up",
            extra={"deleted_count": deleted, "retention_days": retention_days},
        )
        return deleted


class PlanVersionManager:
    """Manage plan versioning and change tracking."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize version manager."""
        self.config = config or {}
        self.version = "1.0.0"
        self.max_versions_retained = self.config.get("max_versions_retained", 20)
        logger.info("PlanVersionManager initialized", extra={"version": self.version})

    async def record_version(
        self,
        plan: ProductionPlan,
        change_reason: str,
        changed_by: str = "system",
        changes_summary: str = "",
    ) -> PlanVersion:
        """
        Record a new plan version.

        Args:
            plan: Plan being versioned
            change_reason: Reason for version change
            changed_by: Who made the change
            changes_summary: Summary of changes

        Returns:
            Version record
        """
        version_num = len(plan.version_history) + 1
        plan_version = PlanVersion(
            version_number=version_num,
            created_at=datetime.utcnow().isoformat(),
            change_reason=change_reason,
            changed_by=changed_by,
            changes_summary=changes_summary,
        )

        plan.version_history.append(plan_version)
        plan.current_version = version_num

        # Trim old versions if needed
        if len(plan.version_history) > self.max_versions_retained:
            plan.version_history = plan.version_history[-self.max_versions_retained:]

        logger.info(
            "Plan version recorded",
            extra={
                "plan_id": plan.plan_id,
                "version": version_num,
                "reason": change_reason,
            },
        )
        return plan_version

    async def get_version(
        self,
        plan: ProductionPlan,
        version_num: int,
    ) -> Optional[PlanVersion]:
        """Get specific version of a plan."""
        return next(
            (v for v in plan.version_history if v.version_number == version_num),
            None,
        )

    async def rollback_to_version(
        self,
        plan: ProductionPlan,
        target_version: int,
    ) -> ProductionPlan:
        """
        Rollback plan to previous version (conceptual).

        Note: In production, you'd need full plan snapshot history.
        This is a placeholder for the rollback concept.

        Args:
            plan: Plan to rollback
            target_version: Target version number

        Returns:
            Updated plan

        Raises:
            ValueError: If version not found
        """
        version = await self.get_version(plan, target_version)
        if not version:
            raise ValueError(f"Version {target_version} not found")

        # Record the rollback as a version
        await self.record_version(
            plan=plan,
            change_reason="rollback",
            changed_by="system",
            changes_summary=f"Rolled back to version {target_version}",
        )

        logger.info(
            "Plan rolled back",
            extra={
                "plan_id": plan.plan_id,
                "target_version": target_version,
            },
        )
        return plan

    async def get_version_history(
        self,
        plan: ProductionPlan,
    ) -> List[PlanVersion]:
        """Get complete version history for a plan."""
        return plan.version_history


class PlanAuditTrail:
    """Maintain and query plan audit trail."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize audit trail manager."""
        self.config = config or {}
        self.version = "1.0.0"
        self.max_audit_records = self.config.get("max_audit_records", 5000)
        logger.info("PlanAuditTrail initialized", extra={"version": self.version})

    async def log_event(
        self,
        plan: ProductionPlan,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        actor: str = "system",
    ) -> AuditRecord:
        """
        Log an event to plan audit trail.

        Args:
            plan: Plan being modified
            event_type: Type of event
            details: Event details
            actor: Who performed the action

        Returns:
            Audit record
        """
        record = AuditRecord(
            plan_id=plan.plan_id,
            goal_id=plan.goal_id,
            event_type=event_type,
            event_time=datetime.utcnow().isoformat(),
            actor=actor,
            details=details or {},
            correlation_id=plan.plan_context.correlation_id,
            trace_id=plan.plan_context.trace_id,
        )

        plan.audit_trail.append(record)

        # Trim old records if needed
        if len(plan.audit_trail) > self.max_audit_records:
            plan.audit_trail = plan.audit_trail[-self.max_audit_records:]

        logger.info(
            "Audit event logged",
            extra={
                "plan_id": plan.plan_id,
                "event_type": event_type,
                "actor": actor,
            },
        )
        return record

    async def get_audit_trail(self, plan: ProductionPlan) -> List[AuditRecord]:
        """Get complete audit trail for a plan."""
        return plan.audit_trail

    async def query_audit_events(
        self,
        plan: ProductionPlan,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[AuditRecord]:
        """
        Query audit trail with filters.

        Args:
            plan: Plan to query
            event_type: Filter by event type
            actor: Filter by actor
            start_time: Start time (ISO string)
            end_time: End time (ISO string)

        Returns:
            Filtered audit records
        """
        records = plan.audit_trail

        if event_type:
            records = [r for r in records if r.event_type == event_type]

        if actor:
            records = [r for r in records if r.actor == actor]

        if start_time:
            start = datetime.fromisoformat(start_time)
            records = [r for r in records if datetime.fromisoformat(r.event_time) >= start]

        if end_time:
            end = datetime.fromisoformat(end_time)
            records = [r for r in records if datetime.fromisoformat(r.event_time) <= end]

        return records

    async def get_stats(self) -> Dict[str, Any]:
        """Get audit trail statistics."""
        return {
            "version": self.version,
            "max_audit_records": self.max_audit_records,
        }


# ── Sync-compatible PlanningSession facade (test API) ─────────────────────

class PlanningSession:
    """Sync-compatible planning session for tests."""

    def __init__(self, config=None):
        self._mgr = PlanningSessionManager(config)
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, user: str, name: str) -> Dict[str, Any]:
        import asyncio, uuid
        session_id = str(uuid.uuid4())
        session = {"session_id": session_id, "user": user, "name": name, "status": "active"}
        self._sessions[session_id] = session
        return session
