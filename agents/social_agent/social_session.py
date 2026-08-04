"""
Social Session & Shared Context Engine — Phase 13

Manages:
- Social session lifecycle (create, update, close, replay)
- Shared context synchronized across agents
- Conversation memory per session
- Audit trail with correlation/trace IDs
"""

from __future__ import annotations

import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SocialSession:
    """Single social session with conversation memory and shared context."""

    def __init__(
        self,
        session_id: str,
        user_id: str,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        context_window: int = 10,
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.trace_id = trace_id or str(uuid.uuid4())
        self.created_at = _utcnow()
        self.updated_at = self.created_at
        self.closed_at: Optional[str] = None
        self.active = True
        self._context_window = context_window
        # Conversation memory (bounded)
        self.conversation: Deque[Dict[str, Any]] = deque(maxlen=context_window)
        # Shared context across agents
        self.shared_context: Dict[str, Any] = {
            "conversation": [],
            "memory": {},
            "decision": {},
            "reasoning": {},
            "planning": {},
            "learning": {},
            "emotion": {},
            "language": {},
            "creativity": {},
            "ethics": {},
            "perception": {},
            "social": {},
            "system_state": {},
        }
        self.metrics: Dict[str, Any] = {
            "turns": 0,
            "context_updates": 0,
            "agent_contributions": {},
        }

    def add_turn(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        turn = {
            "turn_id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": _utcnow(),
            "metadata": metadata or {},
        }
        self.conversation.append(turn)
        self.shared_context["conversation"] = list(self.conversation)
        self.metrics["turns"] += 1
        self.updated_at = _utcnow()

    def update_context(self, domain: str, data: Dict[str, Any], agent_id: Optional[str] = None) -> None:
        if domain in self.shared_context:
            self.shared_context[domain].update(data)
        else:
            self.shared_context[domain] = dict(data)
        self.metrics["context_updates"] += 1
        if agent_id:
            self.metrics["agent_contributions"][agent_id] = (
                self.metrics["agent_contributions"].get(agent_id, 0) + 1
            )
        self.updated_at = _utcnow()

    def get_context(self, domain: Optional[str] = None) -> Dict[str, Any]:
        if domain:
            return dict(self.shared_context.get(domain, {}))
        return dict(self.shared_context)

    def close(self) -> None:
        self.active = False
        self.closed_at = _utcnow()
        self.updated_at = self.closed_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "closed_at": self.closed_at,
            "active": self.active,
            "conversation": list(self.conversation),
            "shared_context": self.shared_context,
            "metrics": self.metrics,
        }


class SocialSessionManager:
    """Manages the lifecycle of all social sessions with audit trail."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config
        self._sessions: Dict[str, SocialSession] = {}
        self._audit: Deque[Dict[str, Any]] = deque(
            maxlen=int(config.get("observability", {}).get("audit_trail_limit", 1000))
        )
        self._session_ttl = int(
            config.get("session", {}).get("session_ttl_seconds", 3600)
        )
        self._max_sessions = int(
            config.get("session", {}).get("max_active_sessions", 500)
        )
        self._context_window = int(
            config.get("session", {}).get("context_window", 10)
        )

    def create_session(
        self,
        user_id: str,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> SocialSession:
        # Evict oldest closed session if at capacity
        if len(self._sessions) >= self._max_sessions:
            self._evict_oldest()

        session_id = str(uuid.uuid4())
        session = SocialSession(
            session_id=session_id,
            user_id=user_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            context_window=self._context_window,
        )
        self._sessions[session_id] = session
        self._record_audit("session_created", session_id, user_id, correlation_id, trace_id)
        logger.debug("social_session.created session_id=%s user_id=%s", session_id, user_id)
        return session

    def get_session(self, session_id: str) -> Optional[SocialSession]:
        return self._sessions.get(session_id)

    def get_or_create(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> SocialSession:
        if session_id and session_id in self._sessions:
            s = self._sessions[session_id]
            if s.active:
                return s
        return self.create_session(user_id, correlation_id, trace_id)

    def close_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.close()
        self._record_audit("session_closed", session_id, session.user_id)
        logger.debug("social_session.closed session_id=%s", session_id)
        return True

    def update_shared_context(
        self,
        session_id: str,
        domain: str,
        data: Dict[str, Any],
        agent_id: Optional[str] = None,
    ) -> bool:
        session = self._sessions.get(session_id)
        if not session or not session.active:
            return False
        session.update_context(domain, data, agent_id)
        return True

    def replay_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Return ordered conversation turns for replay/audit."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        return list(session.conversation)

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(self._audit)[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        active = sum(1 for s in self._sessions.values() if s.active)
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": active,
            "closed_sessions": len(self._sessions) - active,
            "audit_entries": len(self._audit),
        }

    def _evict_oldest(self) -> None:
        closed = [sid for sid, s in self._sessions.items() if not s.active]
        if closed:
            del self._sessions[closed[0]]
            return
        # Evict oldest active session
        if self._sessions:
            oldest = min(self._sessions, key=lambda sid: self._sessions[sid].created_at)
            del self._sessions[oldest]

    def _record_audit(
        self,
        event: str,
        session_id: str,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self._audit.append({
            "event": event,
            "session_id": session_id,
            "user_id": user_id,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "timestamp": _utcnow(),
        })
