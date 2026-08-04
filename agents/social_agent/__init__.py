"""
Social Agent Package — Phase 13.

Exports:
  SocialAgent   — legacy interface (backward compatible)
  SocialEngine  — production engine (Phase 13)
  SocialReasoning, RelationshipManager, SocialSessionManager
  ConsensusEngine, NegotiationEngine, ConflictResolver, CollaborativeExecutor
"""
from agents.social_agent.main import SocialAgent
from agents.social_agent.engine import SocialEngine
from agents.social_agent.social_reasoning import SocialReasoning
from agents.social_agent.relationship_manager import RelationshipManager
from agents.social_agent.social_session import SocialSession, SocialSessionManager
from agents.social_agent.collaboration import (
    ConsensusEngine,
    NegotiationEngine,
    ConflictResolver,
    CollaborativeExecutor,
)

__all__ = [
    "SocialAgent",
    "SocialEngine",
    "SocialReasoning",
    "RelationshipManager",
    "SocialSession",
    "SocialSessionManager",
    "ConsensusEngine",
    "NegotiationEngine",
    "ConflictResolver",
    "CollaborativeExecutor",
]
