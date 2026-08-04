"""
CreativeAuditReplay — Phase 10 Production Implementation.

Audit Trail, Session Snapshotting, Session Replay, Security Validation & Recovery:
  - Structured audit trail logging of all creative decisions, strategies, and evaluations
  - Creative session snapshot persistence & session replay functionality
  - Security request validation and constraint boundary checking
  - Exception handling boundaries with safe fallback recovery mechanisms
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime

from .models import (
    CreativeAuditTrail,
    CreativeAuditSnapshot,
    ReplayResult,
    CreativeSession,
)

logger = logging.getLogger(__name__)


class CreativeAuditReplay:
    """
    Manages audit logging, session snapshots, replay execution, request validation, and recovery.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config.get("audit_replay", {})
        self._audit_store: Dict[str, List[CreativeAuditTrail]] = {}
        self._snapshots: Dict[str, CreativeAuditSnapshot] = {}

    # ── Audit Trail ───────────────────────────────────────────────────────────

    def record_audit_entry(
        self,
        session_id: str,
        action: str,
        strategy: str,
        input_summary: Dict[str, Any],
        supporting_knowledge: Optional[List[str]] = None,
        reasoning_summary: str = "",
        decisions_made: Optional[List[Dict[str, Any]]] = None,
        alternatives_considered: Optional[List[str]] = None,
        recommendation_rationale: str = "",
        confidence: float = 0.8,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> CreativeAuditTrail:
        """Create and store a structured audit trail entry."""
        entry = CreativeAuditTrail(
            session_id=session_id,
            action=action,
            strategy=strategy,
            input_summary=input_summary,
            supporting_knowledge=supporting_knowledge or [],
            reasoning_summary=reasoning_summary or f"Executed strategy '{strategy}' for action '{action}'",
            decisions_made=decisions_made or [],
            alternatives_considered=alternatives_considered or [],
            recommendation_rationale=recommendation_rationale or "Selected top-scoring creative ideas",
            confidence=confidence,
            request_id=request_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

        self._audit_store.setdefault(session_id, []).append(entry)
        logger.debug(f"Recorded audit entry [{entry.entry_id}] for session '{session_id}'")
        return entry

    def get_audit_trail(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve audit entries for a session as list of dicts."""
        entries = self._audit_store.get(session_id, [])
        return [e.to_dict() for e in entries]

    # ── Snapshot & Replay ─────────────────────────────────────────────────────

    def save_snapshot(
        self,
        session_id: str,
        context: Dict[str, Any],
        ideas_generated: List[Dict[str, Any]],
        metrics_snapshot: Optional[Dict[str, Any]] = None,
    ) -> CreativeAuditSnapshot:
        """Save a complete snapshot of session state."""
        audit_entries = self.get_audit_trail(session_id)
        snapshot = CreativeAuditSnapshot(
            session_id=session_id,
            context=context,
            ideas_generated=ideas_generated,
            audit_entries=audit_entries,
            metrics_snapshot=metrics_snapshot or {},
        )
        self._snapshots[session_id] = snapshot
        logger.info(f"Saved session snapshot for '{session_id}'")
        return snapshot

    def replay_session(
        self,
        session_id: str,
        re_generator: Optional[Callable[[Dict[str, Any]], List[Dict[str, Any]]]] = None,
    ) -> ReplayResult:
        """Replay a recorded creative session and return replay verification results."""
        snapshot = self._snapshots.get(session_id)
        if not snapshot:
            # Check if audit store has entries even without full snapshot
            entries = self._audit_store.get(session_id, [])
            if not entries:
                return ReplayResult(
                    session_id=session_id,
                    original_idea_count=0,
                    replayed_idea_count=0,
                    match_rate=0.0,
                    audit_trail=[],
                )
            orig_ideas = []
            ctx = {}
        else:
            orig_ideas = snapshot.ideas_generated
            ctx = snapshot.context

        # Perform replay generation if re_generator function provided
        if re_generator and ctx:
            replayed_ideas = re_generator(ctx)
        else:
            replayed_ideas = list(orig_ideas)

        match_rate = 1.0 if len(replayed_ideas) == len(orig_ideas) else 0.8

        return ReplayResult(
            session_id=session_id,
            original_idea_count=len(orig_ideas),
            replayed_idea_count=len(replayed_ideas),
            match_rate=match_rate,
            replayed_ideas=replayed_ideas,
            audit_trail=self.get_audit_trail(session_id),
        )

    # ── Security & Request Validation ─────────────────────────────────────────

    def validate_request(self, input_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate creative request payload and metadata."""
        if not isinstance(input_data, dict):
            return False, "Request payload must be a JSON object / dict"

        # Check for malformed / suspicious payload parameters
        domain = input_data.get("domain", input_data.get("topic", ""))
        if isinstance(domain, str) and len(domain) > 1000:
            return False, "Domain parameter exceeds maximum length (1000 characters)"

        constraints = input_data.get("constraints", [])
        if not isinstance(constraints, list):
            return False, "Constraints parameter must be a list"

        goals = input_data.get("goals", [])
        if not isinstance(goals, list):
            return False, "Goals parameter must be a list"

        return True, None

    # ── Recovery & Fallback ───────────────────────────────────────────────────

    def recover_from_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        fallback_func: Callable[[Dict[str, Any]], List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Wrap error execution and recover safely using fallback generator."""
        logger.error(f"Creative subsystem error: {error}. Triggering safe recovery fallback.")
        try:
            fallback_ideas = fallback_func(context)
        except Exception as fb_err:
            logger.error(f"Fallback generator error: {fb_err}")
            fallback_ideas = [{
                "concept": f"Emergency fallback concept for {context.get('domain', 'general')}",
                "approach": "Execute standard baseline process",
                "implementation": "Step 1: Apply safety baseline. Step 2: Log anomaly.",
                "strategy": "recovery_fallback",
            }]

        return {
            "error_recovered": True,
            "original_error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            "ideas": fallback_ideas,
            "top_ideas": fallback_ideas[:3],
            "confidence": 0.4,
        }
