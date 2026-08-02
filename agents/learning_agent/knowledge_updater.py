import asyncio
import logging
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

try:
    from structlog import get_logger
except ImportError:
    def get_logger(): return logging.getLogger(__name__)

logger = get_logger()


class KnowledgeUpdater:
    """
    Manages the agent's knowledge base.
    Accepts text chunks via ingest_text(), persists to JSON,
    and supports keyword + recency search.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_running = False

        data_dir = config.get("storage", {}).get("base_path", "data/learning")
        self.knowledge_file = Path(config.get("knowledge_file", f"{data_dir}/knowledge_base.json"))

        # In-memory store: id -> entry
        self.knowledge_base: Dict[str, Any] = {}
        # Queue for text chunks to ingest on next update cycle
        self._ingest_queue: List[Dict[str, Any]] = []

        self.learning_history: List[Dict[str, Any]] = []
        self.max_history_size = config.get("max_history_size", 1000)

        self.metrics = {
            "total_updates": 0,
            "successful_updates": 0,
            "failed_updates": 0,
            "knowledge_size": 0,
        }

    async def start(self):
        logger.info("Starting knowledge updater...")
        try:
            await self._load_knowledge_base()
            self.is_running = True
            logger.info(f"Knowledge updater started — {len(self.knowledge_base)} entries loaded")
        except Exception as e:
            logger.error(f"Failed to start knowledge updater: {e}")
            self.is_running = True  # still run in-memory

    async def stop(self):
        logger.info("Stopping knowledge updater...")
        self.is_running = False
        await self._save_knowledge_base()
        logger.info("Knowledge updater stopped")

    async def _load_knowledge_base(self):
        try:
            if self.knowledge_file.exists():
                with open(self.knowledge_file, "r", encoding="utf-8") as f:
                    self.knowledge_base = json.load(f)
        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")
            self.knowledge_base = {}

    async def _save_knowledge_base(self):
        try:
            self.knowledge_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.knowledge_file, "w", encoding="utf-8") as f:
                json.dump(self.knowledge_base, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving knowledge base: {e}")

    def ingest_text(self, text: str, domain: str = "general", source: str = "user",
                    confidence: float = 0.8, metadata: Dict[str, Any] = None):
        """Queue a text chunk for ingestion on next update cycle."""
        self._ingest_queue.append({
            "text": text,
            "domain": domain,
            "source": source,
            "confidence": confidence,
            "metadata": metadata or {},
            "queued_at": datetime.utcnow().isoformat(),
        })

    async def update(self) -> bool:
        """Process queued text chunks and integrate into knowledge base."""
        try:
            new_info = await self._gather_new_information()
            success = await self._integrate_information(new_info)

            self.metrics["total_updates"] += 1
            if success:
                self.metrics["successful_updates"] += 1
            else:
                self.metrics["failed_updates"] += 1
            self.metrics["knowledge_size"] = len(self.knowledge_base)

            if self.metrics["total_updates"] % self.config.get("save_interval", 10) == 0:
                await self._save_knowledge_base()

            return success
        except Exception as e:
            logger.error(f"Error updating knowledge base: {e}")
            return False

    async def _gather_new_information(self) -> List[Dict[str, Any]]:
        """Drain the ingest queue and convert to knowledge entries."""
        if not self._ingest_queue:
            return []

        entries = []
        while self._ingest_queue:
            item = self._ingest_queue.pop(0)
            text = item["text"].strip()
            if not text:
                continue

            # Extract sentences as individual facts
            sentences = [s.strip() for s in re.split(r"[.!?]\s+", text) if len(s.strip()) > 10]
            if not sentences:
                sentences = [text]

            for sentence in sentences:
                entry_id = f"{item['domain']}_{hash(sentence) & 0xFFFFFF}_{datetime.utcnow().timestamp():.0f}"
                entries.append({
                    "id": entry_id,
                    "domain": item["domain"],
                    "concept": self._extract_concept(sentence),
                    "information": sentence,
                    "source": item["source"],
                    "confidence": item["confidence"],
                    "keywords": self._extract_keywords(sentence),
                    "metadata": item["metadata"],
                    "timestamp": datetime.utcnow().isoformat(),
                })
        return entries

    def _extract_concept(self, text: str) -> str:
        """Extract the main concept (first noun phrase) from a sentence."""
        words = text.split()
        # Take first 3 meaningful words as concept label
        stop = {"the", "a", "an", "is", "are", "was", "were", "it", "this", "that", "and", "or"}
        concept_words = [w for w in words[:6] if w.lower() not in stop]
        return " ".join(concept_words[:3]) if concept_words else words[0] if words else "unknown"

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords by removing stopwords and short tokens."""
        stop = {
            "the", "a", "an", "is", "are", "was", "were", "it", "this", "that",
            "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
            "by", "from", "as", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "could", "should", "may",
            "might", "can", "not", "no", "so", "if", "then", "than", "when",
        }
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        return list(dict.fromkeys(w for w in words if w not in stop))[:10]

    async def _integrate_information(self, new_info: List[Dict[str, Any]]) -> bool:
        try:
            for info in new_info:
                key = info["id"]
                # Merge if concept already exists in same domain
                existing_key = self._find_existing(info["domain"], info["concept"])
                if existing_key:
                    existing = self.knowledge_base[existing_key]
                    # Append new information, update confidence as weighted avg
                    existing_info = existing.get("information", "")
                    if info["information"] not in existing_info:
                        existing["information"] = existing_info + " " + info["information"]
                    existing["confidence"] = round(
                        (existing["confidence"] + info["confidence"]) / 2, 3
                    )
                    existing["last_updated"] = datetime.utcnow().isoformat()
                    existing["keywords"] = list(set(
                        existing.get("keywords", []) + info["keywords"]
                    ))[:15]
                else:
                    self.knowledge_base[key] = info

                self.learning_history.append(info)
                if len(self.learning_history) > self.max_history_size:
                    self.learning_history.pop(0)

            return True
        except Exception as e:
            logger.error(f"Error integrating information: {e}")
            return False

    def _find_existing(self, domain: str, concept: str) -> Optional[str]:
        """Find an existing entry with same domain and similar concept."""
        concept_lower = concept.lower()
        for key, entry in self.knowledge_base.items():
            if entry.get("domain") == domain:
                existing_concept = entry.get("concept", "").lower()
                # Simple overlap check
                if concept_lower in existing_concept or existing_concept in concept_lower:
                    return key
        return None

    async def add_experience(self, experience: Dict[str, Any]):
        """Add a learning experience directly."""
        try:
            domain = experience.get("domain", "general")
            information = experience.get("information", experience.get("content", ""))
            if information:
                self.ingest_text(
                    text=str(information),
                    domain=domain,
                    source=experience.get("source", "experience"),
                    confidence=experience.get("confidence", 0.7),
                )
                await self.update()

            key = experience.get("id", f"exp_{len(self.knowledge_base)}_{datetime.utcnow().timestamp():.0f}")
            self.knowledge_base[key] = {**experience, "timestamp": datetime.utcnow().isoformat()}
            self.learning_history.append(experience)
            if len(self.learning_history) > self.max_history_size:
                self.learning_history.pop(0)

            self.metrics["total_updates"] += 1
            self.metrics["successful_updates"] += 1
            self.metrics["knowledge_size"] = len(self.knowledge_base)
            logger.info(f"Added experience {key} to knowledge base")
        except Exception as e:
            logger.error(f"Error adding experience: {e}")
            raise

    def search(self, query: str, domain: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Full keyword search across knowledge base.
        Returns entries ranked by keyword overlap with query.
        """
        query_keywords = set(self._extract_keywords(query))
        if not query_keywords:
            query_keywords = set(query.lower().split())

        scored = []
        for entry in self.knowledge_base.values():
            if domain and entry.get("domain") != domain:
                continue
            entry_keywords = set(entry.get("keywords", []))
            entry_text = (entry.get("information", "") + " " + entry.get("concept", "")).lower()
            # Keyword overlap score
            overlap = len(query_keywords & entry_keywords)
            # Direct text match bonus
            text_bonus = sum(1 for kw in query_keywords if kw in entry_text)
            score = overlap * 2 + text_bonus
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    async def query(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Query the knowledge base by key or text search."""
        try:
            # Direct key lookup
            key = query.get("key")
            if key and key in self.knowledge_base:
                return self.knowledge_base[key]

            # Text search
            text = query.get("text", query.get("query", ""))
            domain = query.get("domain")
            if text:
                results = self.search(text, domain=domain, limit=5)
                return {"results": results, "count": len(results)} if results else None

            return None
        except Exception as e:
            logger.error(f"Error querying knowledge base: {e}")
            return None

    def get_all(self, domain: Optional[str] = None) -> Dict[str, Any]:
        if domain:
            return {k: v for k, v in self.knowledge_base.items() if v.get("domain") == domain}
        return self.knowledge_base

    async def get_status(self) -> Dict[str, Any]:
        return {
            "status": "running" if self.is_running else "stopped",
            "metrics": self.metrics,
            "knowledge_base_size": len(self.knowledge_base),
            "learning_history_size": len(self.learning_history),
            "pending_ingest": len(self._ingest_queue),
        }

    async def get_metrics(self) -> Dict[str, Any]:
        return self.metrics

    async def clear_metrics(self):
        self.metrics = {
            "total_updates": 0,
            "successful_updates": 0,
            "failed_updates": 0,
            "knowledge_size": len(self.knowledge_base),
        }
