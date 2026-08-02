"""Production Memory Processor for consolidation, duplicate detection, and memory lifecycle."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .memory_storage import MemoryStorage
from .memory_types import (
    MemoryItem,
    MemoryMetadata,
    MemorySearchFilter,
    MemorySource,
    MemoryType,
    WorkingMemory,
    ShortTermMemory,
    LongTermMemory,
)

logger = logging.getLogger(__name__)


class MemoryProcessor:
    """
    Production cognitive memory processor handling:
    - Working → Short-Term → Long-Term consolidation pipeline
    - Duplicate detection & content merging
    - Conflict resolution & importance evaluation
    - Expiration & controlled cleanup
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, storage: Optional[MemoryStorage] = None):
        self.config = config or {}
        self.storage = storage or MemoryStorage(self.config)
        self.consolidation_threshold = float(self.config.get("consolidation_threshold", 0.65))
        self.duplicate_similarity_threshold = float(self.config.get("duplicate_similarity_threshold", 0.90))
        self.maintenance_interval = float(self.config.get("maintenance_interval_seconds", 60.0))
        self._is_running = False
        self._maintenance_task: Optional[asyncio.Task] = None
        self.metrics = {
            "processed_count": 0,
            "consolidated_count": 0,
            "duplicates_merged": 0,
            "expired_cleaned": 0,
            "last_maintenance_at": None,
        }

    async def initialize(self):
        self._is_running = True
        if not self._maintenance_task or self._maintenance_task.done():
            self._maintenance_task = asyncio.create_task(self._maintenance_loop(), name="memory_processor.maintenance")
        logger.info("memory_processor.initialized")

    async def shutdown(self):
        self._is_running = False
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        logger.info("memory_processor.shutdown")

    async def process_memory(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingest raw memory data, detect duplicates, apply classification,
        and route to working / short-term / long-term storage.
        """
        content = data.get("content", "")
        content_str = json.dumps(content) if isinstance(content, (dict, list)) else str(content)
        user_id = data.get("user_id", "default")

        # 1. Duplicate detection
        dup_filter = MemorySearchFilter(query=content_str, user_id=user_id, limit=3)
        existing_results = self.storage.search_hybrid(dup_filter)

        for res in existing_results:
            if res.semantic_score >= self.duplicate_similarity_threshold or res.keyword_score > 0.95:
                # Merge into existing memory
                existing_mem = res.memory
                existing_mem.access_count += 1
                existing_mem.metadata.importance = max(existing_mem.metadata.importance, float(data.get("importance", 0.5)))
                existing_mem.last_accessed = datetime.utcnow()
                self.storage.update(existing_mem.id, {"importance": existing_mem.metadata.importance, "access_count": existing_mem.access_count}, reason="duplicate_merge")
                self.metrics["duplicates_merged"] += 1
                return {"status": "merged", "memory_id": existing_mem.id, "merged_with": existing_mem.id}

        # 2. Construct MemoryItem
        raw_type = data.get("type") or data.get("memory_type", "short_term")
        try:
            mem_type = MemoryType(raw_type)
        except ValueError:
            mem_type = MemoryType.SHORT_TERM

        source_str = data.get("source", "system")
        try:
            source = MemorySource(source_str)
        except ValueError:
            source = MemorySource.SYSTEM

        meta = MemoryMetadata(
            source=source,
            timestamp=datetime.utcnow(),
            importance=float(data.get("importance", 0.5)),
            confidence=float(data.get("confidence", 1.0)),
            location=data.get("location"),
            context=data.get("context", {}),
            tags=data.get("tags", []),
        )

        import uuid
        mem_id = data.get("id") or f"mem-{uuid.uuid4().hex[:12]}"
        ttl_val = data.get("ttl")

        item = MemoryItem(
            id=mem_id,
            type=mem_type,
            content=content,
            metadata=meta,
            user_id=user_id,
            agent_id=data.get("agent_id"),
            conversation_id=data.get("conversation_id"),
            ttl=float(ttl_val) if ttl_val is not None else None,
        )

        # 3. Store in cognitive storage
        self.storage.store(item)
        self.metrics["processed_count"] += 1

        # 4. Immediate consolidation check if high importance
        if meta.importance >= self.consolidation_threshold and mem_type != MemoryType.LONG_TERM:
            self._promote_to_long_term(item)

        return {"status": "created", "memory_id": item.id, "type": mem_type.value}

    def _promote_to_long_term(self, item: MemoryItem):
        """Promote a short-term/working memory item to long-term memory."""
        item.type = MemoryType.LONG_TERM
        item.ttl = None
        self.storage.store(item)
        self.metrics["consolidated_count"] += 1
        logger.info(f"memory_processor.promoted_to_long_term id={item.id}")

    async def consolidate(self) -> Dict[str, Any]:
        """Trigger explicit consolidation sweep over active short-term memories."""
        filter_opts = MemorySearchFilter(
            query="",
            user_id="",  # empty string bypasses user_id filter in search_hybrid
            memory_type=MemoryType.SHORT_TERM,
            min_importance=self.consolidation_threshold,
            limit=500,
        )
        candidates = self.storage.search_hybrid(filter_opts)
        promoted = 0
        for res in candidates:
            self._promote_to_long_term(res.memory)
            promoted += 1

        return {
            "status": "consolidated",
            "promoted_count": promoted,
            "total_consolidated": self.metrics["consolidated_count"],
        }

    async def _maintenance_loop(self):
        """Periodic background task for TTL cleanup and memory consolidation."""
        while self._is_running:
            try:
                await asyncio.sleep(self.maintenance_interval)
                if not self._is_running:
                    break

                # Clean up expired memories
                cleaned = self.storage.cleanup_expired()
                self.metrics["expired_cleaned"] += cleaned

                # Perform periodic consolidation sweep
                await self.consolidate()
                self.metrics["last_maintenance_at"] = datetime.utcnow().isoformat()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"memory_processor.maintenance_error error={exc}")
                await asyncio.sleep(10.0)

    async def get_stats(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics,
            "consolidation_threshold": self.consolidation_threshold,
            "duplicate_threshold": self.duplicate_similarity_threshold,
            "is_running": self._is_running,
        }
