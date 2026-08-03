"""Production MemoryAgent with full cognitive memory system tiers."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from ..base_agent import BaseAgent

from .memory_config_loader import load_memory_config
from .memory_automation import MemoryAutomation
from .memory_processor import MemoryProcessor
from .memory_storage import MemoryStorage
from .memory_types import (
    EmotionType,
    MemoryItem,
    MemoryMetadata,
    MemoryRelationship,
    MemorySearchFilter,
    MemorySource,
    MemoryType,
    RelationshipType,
    RetrievalResult,
    WorkingMemory,
    ShortTermMemory,
    LongTermMemory,
    EmotionalMemory,
    SemanticMemory,
    EpisodicMemory,
    ProceduralMemory,
)

logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):
    """
    Production Cognitive Memory Agent supporting Working, Short-Term, Long-Term,
    Episodic, Semantic, and Procedural memory tiers with hybrid retrieval,
    relationship traversal, consolidation, and audit history.
    """

    def __init__(self, agent_id: str = "memory_agent", config: Optional[Dict[str, Any]] = None):
        # Merge YAML config with any caller-supplied overrides
        merged_config = load_memory_config(config or {})
        super().__init__(agent_id, "memory", config=merged_config)
        self.storage = MemoryStorage(self.config)
        self.processor = MemoryProcessor(self.config, self.storage)
        self.automation = MemoryAutomation(storage=self.storage)
        self.automation._rules_path = self.config.get("automation_rules_path", "data/memory_automation_rules.json")
        self.automation.max_history = int(self.config.get("automation_max_history", 1000))
        self.consolidation_threshold = float(self.config.get("consolidation_threshold", 0.65))

    async def initialize(self):
        await super().initialize()
        await self.processor.initialize()
        await self.automation.initialize()
        self.state.update({
            "status": "active",
            "last_active": datetime.utcnow().isoformat(),
            "short_term_count": 0,
            "long_term_count": 0,
            "working_count": 0,
        })
        logger.info(f"MemoryAgent {self.agent_id} initialized with cognitive architecture")

    async def shutdown(self):
        await self.automation.shutdown()
        await self.processor.shutdown()
        self.storage.close()
        await super().shutdown()

    # ─── High-Level Cognitive Store & Recall API ─────────────────────────────

    async def store(
        self,
        content: Any,
        memory_type: Union[MemoryType, str] = "short_term",
        importance: float = 0.5,
        confidence: float = 1.0,
        tags: Optional[List[str]] = None,
        emotions: Optional[Dict[str, float]] = None,
        user_id: str = "default",
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        source: str = "system",
        ttl: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store new information into the cognitive memory system."""
        data = {
            "content": content,
            "type": memory_type.value if hasattr(memory_type, "value") else str(memory_type),
            "importance": float(importance),
            "confidence": float(confidence),
            "tags": tags or [],
            "emotions": emotions or {},
            "user_id": user_id,
            "agent_id": agent_id or self.agent_id,
            "conversation_id": conversation_id,
            "source": source,
            "ttl": ttl,
            "context": metadata or {},
        }

        res = await self.processor.process_memory(data)
        memory_id = res.get("memory_id")
        item = self.storage.retrieve(memory_id) if memory_id else None

        # Enqueue for automation rule processing (non-blocking)
        if item is not None:
            await self.automation.enqueue({
                "id": item.id,
                "type": item.type.value if hasattr(item.type, "value") else str(item.type),
                "content": item.content,
                "importance": item.metadata.importance,
                "tags": item.metadata.tags or [],
                "user_id": item.user_id,
            })

        await self._update_state()
        return {
            "status": res.get("status", "stored"),
            "memory_id": memory_id,
            "item": item.__dict__ if item and hasattr(item, "__dict__") else item,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def recall(
        self,
        query: str,
        user_id: str = "default",
        memory_type: Optional[Union[MemoryType, str]] = None,
        limit: int = 10,
        min_importance: float = 0.0,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        traverse_relationships: bool = False,
    ) -> List[Dict[str, Any]]:
        """Recall matching memories using cognitive hybrid ranking."""
        filter_opts = MemorySearchFilter(
            query=query,
            user_id=user_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
            memory_type=memory_type,
            min_importance=min_importance,
            tags=tags,
            limit=limit,
            traverse_relationships=traverse_relationships,
        )

        scored_results: List[RetrievalResult] = self.storage.search_hybrid(filter_opts)
        formatted: List[Dict[str, Any]] = []

        for r in scored_results:
            mem = r.memory
            # Lightweight access-count increment — no history snapshot, no INSERT OR REPLACE
            self.storage.update(mem.id, {"access_count": mem.access_count + 1}, reason="recalled")

            formatted.append({
                "id": mem.id,
                "type": mem.type.value if hasattr(mem.type, "value") else str(mem.type),
                "content": mem.content,
                "importance": mem.metadata.importance,
                "confidence": mem.metadata.confidence,
                "user_id": mem.user_id,
                "agent_id": mem.agent_id,
                "conversation_id": mem.conversation_id,
                "created_at": mem.created_at.isoformat() if mem.created_at else None,
                "access_count": mem.access_count,
                "_relevance_score": r.relevance_score,
                "_explanation": r.explanation,
                "linked_memories": [lm.id for lm in r.linked_memories],
            })

        await self._update_state()
        return formatted

    # ─── Specialized Cognitive Tier Methods ─────────────────────────────────

    async def store_working_memory(self, content: Any, user_id: str = "default", conversation_id: Optional[str] = None) -> Dict[str, Any]:
        return await self.store(content=content, memory_type=MemoryType.WORKING, importance=0.4, user_id=user_id, conversation_id=conversation_id, ttl=120.0)

    async def store_short_term_memory(self, content: Any, user_id: str = "default", importance: float = 0.5, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        return await self.store(content=content, memory_type=MemoryType.SHORT_TERM, importance=importance, tags=tags, user_id=user_id, ttl=600.0)

    async def store_long_term_memory(self, content: Any, user_id: str = "default", importance: float = 0.8, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        return await self.store(content=content, memory_type=MemoryType.LONG_TERM, importance=importance, tags=tags, user_id=user_id)

    async def store_episodic_memory(self, event: Any, user_id: str = "default", conversation_id: Optional[str] = None) -> Dict[str, Any]:
        return await self.store(content=event, memory_type=MemoryType.EPISODIC, importance=0.7, user_id=user_id, conversation_id=conversation_id)

    async def store_semantic_memory(self, fact: Any, user_id: str = "default", tags: Optional[List[str]] = None) -> Dict[str, Any]:
        return await self.store(content=fact, memory_type=MemoryType.SEMANTIC, importance=0.9, user_id=user_id, tags=tags)

    async def store_procedural_memory(self, workflow: Any, user_id: str = "default", tags: Optional[List[str]] = None) -> Dict[str, Any]:
        return await self.store(content=workflow, memory_type=MemoryType.PROCEDURAL, importance=0.95, user_id=user_id, tags=tags)

    # ─── Relationship Management ─────────────────────────────────────────────

    async def link_memories(
        self,
        source_id: str,
        target_id: str,
        relationship_type: Union[RelationshipType, str] = RelationshipType.ASSOCIATED,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            rel_enum = RelationshipType(relationship_type) if isinstance(relationship_type, str) else relationship_type
        except ValueError:
            rel_enum = RelationshipType.ASSOCIATED

        rel_id = self.storage.add_relationship(source_id, target_id, rel_enum, weight=weight, metadata=metadata)
        return {"status": "linked", "relationship_id": rel_id, "source_id": source_id, "target_id": target_id}

    # ─── Maintenance & Operations ────────────────────────────────────────────

    async def _update_state(self):
        stats = await self.get_stats()
        self.state.update({
            "short_term_count": stats.get("short_term_count", 0),
            "long_term_count": stats.get("long_term_count", 0),
            "working_count": stats.get("working_count", 0),
            "last_active": datetime.utcnow().isoformat(),
        })

    async def get_stats(self) -> Dict[str, Any]:
        processor_stats = await self.processor.get_stats()
        wt_rows = self.storage._execute_sql("SELECT COUNT(*) as c FROM memories WHERE type = 'working' AND is_deleted = 0")
        st_rows = self.storage._execute_sql("SELECT COUNT(*) as c FROM memories WHERE type = 'short_term' AND is_deleted = 0")
        lt_rows = self.storage._execute_sql("SELECT COUNT(*) as c FROM memories WHERE type = 'long_term' AND is_deleted = 0")
        tot_rows = self.storage._execute_sql("SELECT COUNT(*) as c FROM memories WHERE is_deleted = 0")

        return {
            "working_count": wt_rows[0]["c"] if wt_rows else 0,
            "short_term_count": st_rows[0]["c"] if st_rows else 0,
            "long_term_count": lt_rows[0]["c"] if lt_rows else 0,
            "total": tot_rows[0]["c"] if tot_rows else 0,
            "processor": processor_stats,
            "status": "operational",
        }

    async def clear_memory(self):
        """Clear all active memories."""
        self.storage._write_sql("UPDATE memories SET is_deleted = 1")
        self.storage.lru_cache.clear()
        await self._update_state()
        return {"status": "cleared"}

    # ─── Task Execution Entry Point ──────────────────────────────────────────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {})
        user_id = task.get("user_id") or data.get("user_id", "default")
        conversation_id = task.get("conversation_id") or data.get("conversation_id")

        if action in ("store", "add_memory", "save"):
            return await self.store(
                content=data.get("content", ""),
                memory_type=data.get("memory_type", data.get("type", "short_term")),
                importance=float(data.get("importance", 0.5)),
                confidence=float(data.get("confidence", 1.0)),
                tags=data.get("tags", []),
                user_id=user_id,
                conversation_id=conversation_id,
            )

        if action in ("recall", "search", "retrieve"):
            query = data.get("query", data.get("content", ""))
            memories = await self.recall(
                query=query,
                user_id=user_id,
                memory_type=data.get("memory_type"),
                limit=int(data.get("limit", 10)),
                min_importance=float(data.get("min_importance", 0.0)),
                conversation_id=conversation_id,
                tags=data.get("tags"),
                traverse_relationships=bool(data.get("traverse_relationships", False)),
            )
            return {"memories": memories, "count": len(memories)}

        if action == "link":
            return await self.link_memories(
                source_id=data.get("source_id", ""),
                target_id=data.get("target_id", ""),
                relationship_type=data.get("relationship_type", "associated"),
                weight=float(data.get("weight", 1.0)),
            )

        if action == "consolidate":
            return await self.processor.consolidate()

        if action in ("get_stats", "stats", "metrics"):
            return await self.get_stats()

        if action == "clear":
            return await self.clear_memory()

        return await self.get_stats()
