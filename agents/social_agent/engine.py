"""
SocialAgent — Production Social Intelligence Engine (Phase 13).

Extends BaseAgent for full orchestrator lifecycle integration.
Wraps and coordinates:
  - SocialReasoning       (social cue analysis, strategy selection)
  - RelationshipManager   (trust, rapport, history, persistence)
  - SocialSessionManager  (session lifecycle, shared context, audit)
  - ConsensusEngine       (multi-agent consensus)
  - NegotiationEngine     (resource/task negotiation)
  - ConflictResolver      (conflict resolution)
  - CollaborativeExecutor (parallel agent execution)

All inter-agent collaboration uses the existing MessageBroker.
No direct agent-to-agent calls.
"""
from __future__ import annotations

import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

import yaml

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from ..base_agent import BaseAgent  # type: ignore

try:
    from agents.social_agent.social_reasoning import SocialReasoning
    from agents.social_agent.relationship_manager import RelationshipManager
    from agents.social_agent.social_session import SocialSession, SocialSessionManager
    from agents.social_agent.collaboration import (
        ConsensusEngine, NegotiationEngine, ConflictResolver, CollaborativeExecutor,
    )
except ImportError:
    from .social_reasoning import SocialReasoning          # type: ignore
    from .relationship_manager import RelationshipManager  # type: ignore
    from .social_session import SocialSession, SocialSessionManager  # type: ignore
    from .collaboration import (                           # type: ignore
        ConsensusEngine, NegotiationEngine, ConflictResolver, CollaborativeExecutor,
    )

_DEFAULT_CONFIG_PATH = "agents/social_agent/config.yaml"


def _load_config(path: str) -> Dict[str, Any]:
    try:
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        logging.getLogger(__name__).warning("SocialEngine: config load failed path=%s err=%s", path, e)
    return {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SocialEngine(BaseAgent):
    """
    Production Social Intelligence Engine.

    Lifecycle:
      initialize()        → load config, wire sub-systems, register with broker
      execute_task()      → orchestrator dispatch for all social actions
      shutdown()          → persist relationships, close sessions

    Key actions (via execute_task):
      process            → full social pipeline (cue → relationship → response)
      start_session      → open a social session
      stop_session       → close a social session
      add_turn           → add conversation turn to session
      update_context     → update shared context domain
      get_relationship   → fetch relationship context for a user
      get_all_relationships
      get_session        → fetch session state
      replay_session     → replay conversation turns
      reach_consensus    → multi-agent consensus
      negotiate          → multi-agent negotiation
      resolve_conflict   → conflict resolution
      collaborate        → parallel agent execution
      get_metrics        → all sub-system metrics
      get_audit          → audit trail
      get_status / get_health
    """

    DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_PATH

    def __init__(
        self,
        agent_id: str = "social_agent",
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ):
        super().__init__(agent_id=agent_id, agent_type="social")
        self.logger = logging.getLogger(f"SocialEngine.{agent_id}")

        self._cfg: Dict[str, Any] = (
            config if config is not None
            else _load_config(config_path or self.DEFAULT_CONFIG_PATH)
        )

        # Sub-systems
        self._reasoning = SocialReasoning(self._cfg)
        self._relationships = RelationshipManager(self._cfg)
        self._sessions = SocialSessionManager(self._cfg)
        self._consensus = ConsensusEngine(self._cfg)
        self._negotiation = NegotiationEngine(self._cfg)
        self._conflict = ConflictResolver(self._cfg)
        self._executor = CollaborativeExecutor(self._cfg)

        # Metrics
        self._metrics: Dict[str, int] = {
            "interactions": 0,
            "sessions_created": 0,
            "consensus_operations": 0,
            "negotiation_operations": 0,
            "conflict_resolutions": 0,
            "collaborations": 0,
            "errors": 0,
        }

        # Audit trail
        audit_limit = int(
            self._cfg.get("observability", {}).get("audit_trail_limit", 1000)
        )
        self._audit: Deque[Dict[str, Any]] = deque(maxlen=audit_limit)

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self):
        try:
            await super().initialize()
        except Exception:
            pass
        self.state.update({
            "status": "active",
            "interactions": 0,
            "sessions_created": 0,
            "errors": 0,
        })
        self.logger.info("SocialEngine initialized agent_id=%s", self.agent_id)

    async def shutdown(self):
        # Close all active sessions
        for sid in list(self._sessions._sessions.keys()):
            self._sessions.close_session(sid)
        await super().shutdown()
        self.logger.info("SocialEngine shut down agent_id=%s", self.agent_id)

    # ─── Core Social Pipeline ─────────────────────────────────────────────────

    def process(
        self,
        content: str,
        sender: str = "user",
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full social pipeline:
          1. Analyze social cues
          2. Update relationship state
          3. Generate contextual response
          4. Update session conversation
          5. Broadcast to broker
        """
        try:
            # Get or create session
            session = self._sessions.get_or_create(
                user_id=sender,
                session_id=session_id,
                correlation_id=correlation_id,
                trace_id=trace_id,
            )

            # Relationship context (before update)
            rel_ctx = self._relationships.get_context(sender)

            # Social reasoning
            analysis = self._reasoning.analyze(
                content=content,
                sender=sender,
                relationship_context=rel_ctx,
                session_context=session.get_context("social"),
            )

            # Update relationship
            rel_ctx = self._relationships.update_state(analysis)

            # Build response
            prefix = self._reasoning.build_response_prefix(analysis, rel_ctx)
            base = self._pick_template(analysis, rel_ctx)
            response_text = self._reasoning.adapt_tone(prefix + base, analysis, rel_ctx)

            # Add turn to session
            session.add_turn("user", content, {"analysis": analysis})
            session.add_turn("assistant", response_text, {"relationship": rel_ctx})
            session.update_context("social", {
                "last_interaction_type": analysis.get("interaction_type"),
                "last_emotion": analysis.get("emotion_sentiment"),
                "last_strategy": analysis.get("communication_strategy"),
            }, agent_id=self.agent_id)

            # Metrics
            self._metrics["interactions"] += 1
            self.state["interactions"] = self._metrics["interactions"]

            result = {
                "response_type": analysis.get("interaction_type", "statement"),
                "content": response_text,
                "emotional_tone": analysis.get("emotion_sentiment", "neutral"),
                "formality": analysis.get("formality", "neutral"),
                "strategy": analysis.get("communication_strategy", "conversational_response"),
                "relationship_context": rel_ctx,
                "analysis": analysis,
                "session_id": session.session_id,
                "confidence": rel_ctx.get("confidence", 0.5),
                "timestamp": _utcnow(),
            }

            self._record_audit("process", sender, session.session_id, True,
                               f"type={analysis.get('interaction_type')} strategy={analysis.get('communication_strategy')}")
            return result

        except Exception as e:
            self.logger.error("SocialEngine.process error=%s", e)
            self._metrics["errors"] += 1
            self.state["errors"] = self._metrics["errors"]
            self._record_audit("process", sender, session_id or "", False, str(e))
            return {"error": str(e), "response_type": "error", "timestamp": _utcnow()}

    def _pick_template(self, analysis: Dict[str, Any], rel_ctx: Dict[str, Any]) -> str:
        """Select response template from interaction type + formality."""
        interaction_type = analysis.get("interaction_type", "statement")
        formality = analysis.get("formality", "neutral")
        count = rel_ctx.get("interaction_count", 1)

        _templates: Dict[tuple, List[str]] = {
            ("greeting", "formal"): [
                "Good day. How may I assist you today?",
                "Hello. It's a pleasure to connect with you.",
            ],
            ("greeting", "informal"): [
                "Hey! Great to hear from you. What's up?",
                "Hi there! How's it going?",
            ],
            ("greeting", "neutral"): [
                "Hello! How can I help you today?",
                "Hi there. What would you like to discuss?",
            ],
            ("farewell", "formal"): [
                "Thank you for the conversation. Have a productive day.",
                "It was a pleasure. Until next time.",
            ],
            ("farewell", "informal"): ["Take care! Talk soon.", "Bye! It was great chatting."],
            ("farewell", "neutral"): ["Goodbye! Feel free to return anytime."],
            ("question", "formal"): [
                "That's an excellent question. Let me address it carefully.",
                "I appreciate you asking. Here's what I can share:",
            ],
            ("question", "informal"): ["Good question! Here's what I think:"],
            ("question", "neutral"): ["Let me help you with that."],
            ("statement", "formal"): [
                "I understand your perspective. Allow me to respond thoughtfully.",
            ],
            ("statement", "informal"): ["Got it! Here's my take:"],
            ("statement", "neutral"): ["I see. Here's my response:"],
        }
        key = (interaction_type, formality)
        templates = _templates.get(key, _templates.get((interaction_type, "neutral"), ["I understand. How can I help?"]))
        return templates[count % len(templates)]

    # ─── Session Management ───────────────────────────────────────────────────

    def start_session(
        self,
        user_id: str,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = self._sessions.create_session(user_id, correlation_id, trace_id)
        self._metrics["sessions_created"] += 1
        self.state["sessions_created"] = self._metrics["sessions_created"]
        return {"session_id": session.session_id, "user_id": user_id, "status": "created"}

    def stop_session(self, session_id: str) -> Dict[str, Any]:
        ok = self._sessions.close_session(session_id)
        return {"session_id": session_id, "closed": ok}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        s = self._sessions.get_session(session_id)
        return s.to_dict() if s else None

    def replay_session(self, session_id: str) -> List[Dict[str, Any]]:
        return self._sessions.replay_session(session_id)

    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        s = self._sessions.get_session(session_id)
        if not s:
            return False
        s.add_turn(role, content, metadata)
        return True

    def update_shared_context(
        self,
        session_id: str,
        domain: str,
        data: Dict[str, Any],
        agent_id: Optional[str] = None,
    ) -> bool:
        return self._sessions.update_shared_context(session_id, domain, data, agent_id)

    # ─── Relationship API ─────────────────────────────────────────────────────

    def get_relationship(self, user_id: str) -> Dict[str, Any]:
        return self._relationships.get_context(user_id)

    def get_all_relationships(self) -> Dict[str, Any]:
        return self._relationships.get_all_relationships()

    def get_interaction_history(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self._relationships.get_interaction_history(user_id, limit)

    # ─── Consensus ────────────────────────────────────────────────────────────

    def reach_consensus(
        self,
        votes: List[Dict[str, Any]],
        policy: Optional[str] = None,
        expert_agents: Optional[List[str]] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = self._consensus.reach_consensus(
            votes=votes,
            policy=policy,
            expert_agents=expert_agents,
            correlation_id=correlation_id,
        )
        self._metrics["consensus_operations"] += 1
        self._record_audit("consensus", "system", "", True,
                           f"policy={result.get('policy')} value={result.get('consensus_value')}")
        return result

    # ─── Negotiation ──────────────────────────────────────────────────────────

    def negotiate(
        self,
        proposals: List[Dict[str, Any]],
        negotiation_type: str = "resource",
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = self._negotiation.negotiate(
            proposals=proposals,
            negotiation_type=negotiation_type,
            correlation_id=correlation_id,
        )
        self._metrics["negotiation_operations"] += 1
        self._record_audit("negotiate", "system", "", result.get("agreed", False),
                           f"type={negotiation_type} agreed={result.get('agreed')}")
        return result

    # ─── Conflict Resolution ──────────────────────────────────────────────────

    def resolve_conflict(
        self,
        conflicts: List[Dict[str, Any]],
        strategy: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = self._conflict.resolve(
            conflicts=conflicts,
            strategy=strategy,
            correlation_id=correlation_id,
        )
        self._metrics["conflict_resolutions"] += 1
        self._record_audit("resolve_conflict", "system", "", result.get("resolved", False),
                           f"strategy={result.get('strategy')} winner={result.get('winning_agent')}")
        return result

    # ─── Collaborative Execution ──────────────────────────────────────────────

    async def collaborate(
        self,
        agent_tasks: List[Dict[str, Any]],
        agent_manager: Any,
        shared_context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Merge session shared context if available
        ctx = dict(shared_context or {})
        if session_id:
            s = self._sessions.get_session(session_id)
            if s:
                ctx.update(s.get_context())

        result = await self._executor.execute_parallel(
            agent_tasks=agent_tasks,
            agent_manager=agent_manager,
            shared_context=ctx,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        self._metrics["collaborations"] += 1
        self._record_audit("collaborate", "system", session_id or "", result.get("success", False),
                           f"agents={result.get('agent_count')} failed={len(result.get('failed_agents', []))}")

        # Update session context with collaboration result
        if session_id:
            self._sessions.update_shared_context(
                session_id, "social",
                {"last_collaboration": result.get("collaboration_id")},
                agent_id=self.agent_id,
            )
        return result

    # ─── Broker Collaboration ─────────────────────────────────────────────────

    async def _broadcast_social_event(
        self,
        event_type: str,
        sender: str,
        session_id: str,
        data: Dict[str, Any],
    ):
        if not self._message_broker:
            return
        try:
            from orchestrator.agent_communication import MessageType, MessagePriority
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=None,
                message_type=MessageType.SOCIAL_INTERACTION,
                content={
                    "event_type": event_type,
                    "sender": sender,
                    "session_id": session_id,
                    **data,
                    "timestamp": _utcnow(),
                },
                priority=MessagePriority.NORMAL,
            )
        except Exception as e:
            self.logger.debug("SocialEngine: broker publish failed err=%s", e)

    # ─── Metrics & Audit ─────────────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "social": dict(self._metrics),
            "sessions": self._sessions.get_metrics(),
            "consensus": self._consensus.get_metrics(),
            "negotiation": self._negotiation.get_metrics(),
            "collaboration": self._executor.get_metrics(),
        }

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(self._audit)[-limit:]

    def _record_audit(
        self,
        operation: str,
        actor: str,
        session_id: str,
        success: bool,
        summary: str,
    ):
        self._audit.append({
            "entry_id": str(uuid.uuid4()),
            "operation": operation,
            "actor": actor,
            "session_id": session_id,
            "success": success,
            "summary": summary,
            "timestamp": _utcnow(),
        })

    # ─── State Update ─────────────────────────────────────────────────────────

    async def _update_state(self):
        await super()._update_state()
        self.state["interactions"] = self._metrics["interactions"]
        self.state["sessions_created"] = self._metrics["sessions_created"]
        self.state["active_sessions"] = self._sessions.get_metrics().get("active_sessions", 0)

    # ─── execute_task (Orchestrator Dispatch) ─────────────────────────────────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {}) or {}

        # ── Social pipeline ──
        if action in ("process", "analyze", "respond"):
            content = data.get("content", data.get("text", ""))
            sender = data.get("sender", data.get("user_id", "user"))
            result = self.process(
                content=content,
                sender=sender,
                session_id=data.get("session_id"),
                correlation_id=data.get("correlation_id"),
                trace_id=data.get("trace_id"),
            )
            await self._broadcast_social_event(
                "interaction", sender, result.get("session_id", ""), result
            )
            return result

        # ── Session management ──
        if action == "start_session":
            return self.start_session(
                user_id=data.get("user_id", "user"),
                correlation_id=data.get("correlation_id"),
                trace_id=data.get("trace_id"),
            )

        if action == "stop_session":
            return self.stop_session(data.get("session_id", ""))

        if action == "get_session":
            s = self.get_session(data.get("session_id", ""))
            return {"session": s}

        if action == "replay_session":
            return {"turns": self.replay_session(data.get("session_id", ""))}

        if action == "add_turn":
            ok = self.add_turn(
                data.get("session_id", ""),
                data.get("role", "user"),
                data.get("content", ""),
                data.get("metadata"),
            )
            return {"success": ok}

        if action == "update_context":
            ok = self.update_shared_context(
                data.get("session_id", ""),
                data.get("domain", "social"),
                data.get("data", {}),
                data.get("agent_id"),
            )
            return {"success": ok}

        # ── Relationship ──
        if action == "get_relationship":
            uid = data.get("user_id", data.get("sender", ""))
            return {"relationship": self.get_relationship(uid)}

        if action == "get_all_relationships":
            return {"relationships": self.get_all_relationships()}

        if action == "get_interaction_history":
            uid = data.get("user_id", data.get("sender", ""))
            limit = int(data.get("limit", 20))
            return {"history": self.get_interaction_history(uid, limit)}

        # ── Consensus ──
        if action == "reach_consensus":
            return self.reach_consensus(
                votes=data.get("votes", []),
                policy=data.get("policy"),
                expert_agents=data.get("expert_agents"),
                correlation_id=data.get("correlation_id"),
            )

        # ── Negotiation ──
        if action == "negotiate":
            return self.negotiate(
                proposals=data.get("proposals", []),
                negotiation_type=data.get("negotiation_type", "resource"),
                correlation_id=data.get("correlation_id"),
            )

        # ── Conflict resolution ──
        if action == "resolve_conflict":
            return self.resolve_conflict(
                conflicts=data.get("conflicts", []),
                strategy=data.get("strategy"),
                correlation_id=data.get("correlation_id"),
            )

        # ── Collaboration ──
        if action == "collaborate":
            agent_manager = data.get("agent_manager")  # injected by orchestrator
            return await self.collaborate(
                agent_tasks=data.get("agent_tasks", []),
                agent_manager=agent_manager,
                shared_context=data.get("shared_context"),
                session_id=data.get("session_id"),
                correlation_id=data.get("correlation_id"),
                trace_id=data.get("trace_id"),
            )

        # ── Observability ──
        if action == "get_metrics":
            return self.get_metrics()

        if action == "get_audit":
            return {"audit": self.get_audit_trail(data.get("limit", 100))}

        if action == "get_consensus_history":
            return {"history": self._consensus.get_history(data.get("limit", 50))}

        if action == "get_negotiation_history":
            return {"history": self._negotiation.get_history(data.get("limit", 50))}

        if action == "get_conflict_history":
            return {"history": self._conflict.get_history(data.get("limit", 50))}

        if action == "get_session_audit":
            return {"audit": self._sessions.get_audit_trail(data.get("limit", 100))}

        if action == "get_status":
            return await self.get_status()

        if action == "get_health":
            return await self.get_health()

        # ── Legacy compatibility (existing SocialAgent interface) ──
        if action in ("process_social_cue",):
            content = data.get("content", "")
            sender = data.get("sender", "user")
            return self.process(content=content, sender=sender)

        return await super().execute_task(task)
