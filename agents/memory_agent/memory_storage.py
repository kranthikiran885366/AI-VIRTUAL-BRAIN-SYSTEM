"""Memory storage module for production cognitive memory architecture."""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    import faiss
    _HAS_FAISS = True
except Exception:
    faiss = None
    _HAS_FAISS = False

try:
    from sentence_transformers import SentenceTransformer
    _HAS_ST = True
except Exception:
    SentenceTransformer = None
    _HAS_ST = False

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
)


class LRUCache:
    """Bounded LRU cache for memory lookups."""

    def __init__(self, capacity: int = 2000):
        self.capacity = max(1, capacity)
        self._cache: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: str, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)

    def remove(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()


class MemoryStorage:
    """
    Production-grade cognitive memory storage backend with SQLite database pool,
    vector indexing, LRU caching, relationship graph support, and hybrid search.
    """

    def __init__(self, config: Dict[str, Any], db_manager: Optional[Any] = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self.db_manager = db_manager

        # Path fallback if no db_manager
        self.db_path = self.config.get("sqlite_path", "data/brain.db")
        self.conn: Optional[sqlite3.Connection] = None

        if self.db_manager is None:
            self._init_sqlite()

        self.vector_dim = int(self.config.get("vector_dim", 768))
        self.lru_cache = LRUCache(capacity=int(self.config.get("cache_capacity", 2000)))

        # FAISS / Simple Vector Index
        self._init_vector_index()
        self._init_embedding_model()

        # Hybrid search weights
        self.w_keyword = float(self.config.get("w_keyword", 0.35))
        self.w_vector = float(self.config.get("w_vector", 0.35))
        self.w_importance = float(self.config.get("w_importance", 0.15))
        self.w_recency = float(self.config.get("w_recency", 0.10))
        self.w_frequency = float(self.config.get("w_frequency", 0.05))

    def _init_sqlite(self):
        """Initialize direct SQLite connection if DatabaseManager was not injected."""
        try:
            import os
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self._create_tables_direct()
        except Exception as exc:
            self.logger.error(f"sqlite_init_failed error={exc}")

    def _create_tables_direct(self):
        if not self.conn:
            return
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    user_id TEXT DEFAULT 'default',
                    agent_id TEXT,
                    conversation_id TEXT,
                    importance REAL DEFAULT 0.5,
                    confidence REAL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    expires_at TEXT,
                    is_archived INTEGER DEFAULT 0,
                    is_deleted INTEGER DEFAULT 0,
                    version INTEGER DEFAULT 1,
                    embedding BLOB,
                    ttl REAL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_relationships (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES memories(id) ON DELETE CASCADE,
                    FOREIGN KEY(target_id) REFERENCES memories(id) ON DELETE CASCADE
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_history (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content_snapshot TEXT,
                    change_reason TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_consolidation_log (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    from_type TEXT NOT NULL,
                    to_type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    importance_at_consolidation REAL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    description TEXT
                )
            """)

        # Additive column migrations — safe to run repeatedly
        additive = [
            (1, "ADD tags",                "ALTER TABLE memories ADD COLUMN tags TEXT DEFAULT '[]'"),
            (2, "ADD category",            "ALTER TABLE memories ADD COLUMN category TEXT"),
            (3, "ADD priority",            "ALTER TABLE memories ADD COLUMN priority INTEGER DEFAULT 5"),
            (4, "ADD source_attribution",  "ALTER TABLE memories ADD COLUMN source_attribution TEXT"),
            (5, "ADD consolidation_count", "ALTER TABLE memories ADD COLUMN consolidation_count INTEGER DEFAULT 0"),
        ]
        with self.conn:
            applied = {r[0] for r in self.conn.execute("SELECT version FROM schema_migrations").fetchall()}
            for ver, desc, alter_sql in additive:
                if ver not in applied:
                    try:
                        self.conn.execute(alter_sql)
                    except Exception:
                        pass  # column already exists
                    self.conn.execute(
                        "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
                        (ver, datetime.utcnow().isoformat(), desc),
                    )
            # Composite indexes
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_mem_user_type ON memories(user_id, type, importance DESC, created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_mem_active ON memories(is_deleted, is_archived, type)",
                "CREATE INDEX IF NOT EXISTS idx_mem_expiry ON memories(expires_at) WHERE expires_at IS NOT NULL",
                "CREATE INDEX IF NOT EXISTS idx_mem_category ON memories(category) WHERE category IS NOT NULL",
                "CREATE INDEX IF NOT EXISTS idx_rel_source ON memory_relationships(source_id)",
                "CREATE INDEX IF NOT EXISTS idx_rel_target ON memory_relationships(target_id)",
            ]:
                try:
                    self.conn.execute(idx_sql)
                except Exception:
                    pass

    def _init_vector_index(self):
        if _HAS_FAISS and faiss is not None:
            self.index = faiss.IndexFlatL2(self.vector_dim)
        else:
            class SimpleIndex:
                def __init__(self, dim):
                    self.vectors: List[np.ndarray] = []
                    self.dim = dim

                @property
                def ntotal(self):
                    return len(self.vectors)

                def add(self, vecs):
                    for v in vecs:
                        self.vectors.append(np.array(v, dtype=np.float32))

                def search(self, query_vecs, topk):
                    q = np.array(query_vecs, dtype=np.float32)
                    dists, inds = [], []
                    for qv in q:
                        if not self.vectors:
                            dists.append(np.array([]))
                            inds.append(np.array([]))
                            continue
                        arr = np.stack(self.vectors)
                        dist = np.linalg.norm(arr - qv, axis=1)
                        idx = np.argsort(dist)[:topk]
                        dists.append(dist[idx])
                        inds.append(idx)
                    return np.array(dists), np.array(inds)

            self.index = SimpleIndex(self.vector_dim)
        self.memory_map: Dict[int, str] = {}

    def _init_embedding_model(self):
        model_name = self.config.get("embedding_model", "all-MiniLM-L6-v2")
        if _HAS_ST and SentenceTransformer is not None:
            try:
                self.embedding_model = SentenceTransformer(model_name)
                # Detect actual output dimension from the model and override vector_dim.
                # This prevents shape mismatches when the model produces 384-dim vectors
                # but vector_dim was initialised to 768 (the old hash-fallback default).
                probe = self.embedding_model.encode("probe")
                actual_dim = int(probe.shape[0]) if hasattr(probe, "shape") else len(probe)
                if actual_dim != self.vector_dim:
                    self.logger.info(
                        f"memory_storage.embedding_dim_updated "
                        f"old={self.vector_dim} new={actual_dim} model={model_name}"
                    )
                    self.vector_dim = actual_dim
                    # Rebuild the vector index with the correct dimension.
                    self._init_vector_index()
            except Exception as exc:
                self.logger.warning(f"memory_storage.embedding_model_load_failed error={exc}")
                self.embedding_model = None
        else:
            self.embedding_model = None

    def _generate_embedding(self, text_str: str) -> List[float]:
        if self.embedding_model is not None:
            try:
                vec = self.embedding_model.encode(text_str)
                return vec.tolist() if hasattr(vec, "tolist") else list(vec)
            except Exception:
                pass

        # Hash-based fallback — uses current vector_dim so it always matches.
        tokens = str(text_str).lower().split()
        vec = np.zeros(self.vector_dim, dtype=np.float32)
        for i, t in enumerate(tokens):
            vec[i % self.vector_dim] += (hash(t) % 1000) / 1000.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    # ─── Connection Context Helper ────────────────────────────────────────────

    def _execute_sql(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        if self.db_manager is not None:
            return self.db_manager.repository.fetch_all(sql, params)

        if not self.conn:
            return []
        with self.conn:
            cursor = self.conn.execute(sql, params)
            if cursor.description:
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
            return []

    def _write_sql(self, sql: str, params: Sequence[Any] = ()) -> int:
        if self.db_manager is not None:
            return self.db_manager.repository.execute(sql, params)

        if not self.conn:
            return 0
        with self.conn:
            cursor = self.conn.execute(sql, params)
            self.conn.commit()
            return cursor.rowcount

    # ─── Store / Create ───────────────────────────────────────────────────────

    def store(self, memory: MemoryItem) -> bool:
        """Store a MemoryItem into SQLite, update cache, and index vector."""
        try:
            content_str = json.dumps(memory.content) if not isinstance(memory.content, str) else memory.content

            # Always regenerate embedding if missing or if dimension doesn't match current model.
            if memory.embedding is None or len(memory.embedding) != self.vector_dim:
                memory.embedding = self._generate_embedding(content_str)

            meta_dict = {
                "source": memory.metadata.source.value if hasattr(memory.metadata.source, "value") else str(memory.metadata.source),
                "timestamp": memory.metadata.timestamp.isoformat() if isinstance(memory.metadata.timestamp, datetime) else str(memory.metadata.timestamp),
                "emotion": memory.metadata.emotion.value if hasattr(memory.metadata.emotion, "value") and memory.metadata.emotion else None,
                "importance": memory.metadata.importance,
                "confidence": memory.metadata.confidence,
                "location": memory.metadata.location,
                "context": memory.metadata.context or {},
                "tags": memory.metadata.tags or [],
                "category": getattr(memory.metadata, "category", None),
                "priority": getattr(memory.metadata, "priority", 5),
                "source_attribution": getattr(memory.metadata, "source_attribution", None),
            }

            emb_blob = np.array(memory.embedding, dtype=np.float32).tobytes() if memory.embedding else None
            mem_type_val = memory.type.value if hasattr(memory.type, "value") else str(memory.type)
            tags_json = json.dumps(memory.metadata.tags or [])
            category = getattr(memory.metadata, "category", None)
            priority = getattr(memory.metadata, "priority", 5)
            source_attr = getattr(memory.metadata, "source_attribution", None)
            consol_count = getattr(memory, "consolidation_count", 0)

            # Use INSERT OR REPLACE with all columns including new Phase 3 additions.
            # Columns that may not exist yet (pre-migration DBs) are handled by the
            # additive migration in _create_tables_direct / ensure_cognitive_schema.
            sql = """
            INSERT OR REPLACE INTO memories
            (id, type, content, metadata, user_id, agent_id, conversation_id, importance, confidence,
             access_count, last_accessed, created_at, updated_at, expires_at, is_archived, is_deleted,
             version, embedding, ttl, tags, category, priority, source_attribution, consolidation_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                memory.id,
                mem_type_val,
                content_str,
                json.dumps(meta_dict),
                memory.user_id,
                memory.agent_id,
                memory.conversation_id,
                memory.metadata.importance,
                memory.metadata.confidence,
                memory.access_count,
                memory.last_accessed.isoformat() if memory.last_accessed else None,
                memory.created_at.isoformat() if memory.created_at else datetime.utcnow().isoformat(),
                memory.updated_at.isoformat() if memory.updated_at else None,
                memory.expires_at.isoformat() if memory.expires_at else None,
                1 if memory.is_archived else 0,
                1 if memory.is_deleted else 0,
                memory.version,
                emb_blob,
                memory.ttl,
                tags_json,
                category,
                priority,
                source_attr,
                consol_count,
            )

            self._write_sql(sql, params)
            self.lru_cache.put(memory.id, memory)

            if memory.embedding:
                idx = self.index.ntotal
                self.index.add(np.array([memory.embedding], dtype=np.float32))
                self.memory_map[idx] = memory.id

            return True

        except Exception as exc:
            self.logger.error(f"memory_storage.store_error id={memory.id} error={exc}")
            # Fallback: try without new columns in case migration hasn't run yet
            try:
                return self._store_legacy(memory)
            except Exception:
                return False

    def _store_legacy(self, memory: MemoryItem) -> bool:
        """Fallback store without Phase 3 columns for pre-migration databases."""
        content_str = json.dumps(memory.content) if not isinstance(memory.content, str) else memory.content
        if memory.embedding is None or len(memory.embedding) != self.vector_dim:
            memory.embedding = self._generate_embedding(content_str)
        meta_dict = {
            "source": memory.metadata.source.value if hasattr(memory.metadata.source, "value") else str(memory.metadata.source),
            "timestamp": memory.metadata.timestamp.isoformat() if isinstance(memory.metadata.timestamp, datetime) else str(memory.metadata.timestamp),
            "emotion": memory.metadata.emotion.value if hasattr(memory.metadata.emotion, "value") and memory.metadata.emotion else None,
            "importance": memory.metadata.importance,
            "confidence": memory.metadata.confidence,
            "location": memory.metadata.location,
            "context": memory.metadata.context or {},
            "tags": memory.metadata.tags or [],
        }
        emb_blob = np.array(memory.embedding, dtype=np.float32).tobytes() if memory.embedding else None
        mem_type_val = memory.type.value if hasattr(memory.type, "value") else str(memory.type)
        sql = """
        INSERT OR REPLACE INTO memories
        (id, type, content, metadata, user_id, agent_id, conversation_id, importance, confidence,
         access_count, last_accessed, created_at, updated_at, expires_at, is_archived, is_deleted, version, embedding, ttl)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            memory.id, mem_type_val, content_str, json.dumps(meta_dict),
            memory.user_id, memory.agent_id, memory.conversation_id,
            memory.metadata.importance, memory.metadata.confidence,
            memory.access_count,
            memory.last_accessed.isoformat() if memory.last_accessed else None,
            memory.created_at.isoformat() if memory.created_at else datetime.utcnow().isoformat(),
            memory.updated_at.isoformat() if memory.updated_at else None,
            memory.expires_at.isoformat() if memory.expires_at else None,
            1 if memory.is_archived else 0,
            1 if memory.is_deleted else 0,
            memory.version, emb_blob, memory.ttl,
        )
        self._write_sql(sql, params)
        self.lru_cache.put(memory.id, memory)
        return True

    # ─── Retrieve / Fetch ─────────────────────────────────────────────────────

    def retrieve(self, memory_id: str) -> Optional[MemoryItem]:
        """Retrieve a memory item by ID (checking cache first)."""
        cached = self.lru_cache.get(memory_id)
        if cached:
            return cached

        rows = self._execute_sql("SELECT * FROM memories WHERE id = ? AND is_deleted = 0", (memory_id,))
        if not rows:
            return None

        memory = self._row_to_memory(rows[0])
        if memory:
            self.lru_cache.put(memory.id, memory)
        return memory

    def _row_to_memory(self, row: Dict[str, Any]) -> MemoryItem:
        meta_json = row.get("metadata")
        meta_dict = json.loads(meta_json) if meta_json else {}

        source_val = meta_dict.get("source", "system")
        try:
            source_enum = MemorySource(source_val)
        except ValueError:
            source_enum = MemorySource.SYSTEM

        emotion_val = meta_dict.get("emotion")
        emotion_enum = None
        if emotion_val:
            try:
                emotion_enum = EmotionType(emotion_val)
            except ValueError:
                emotion_enum = None

        created_str = row.get("created_at")
        created_dt = datetime.fromisoformat(created_str) if created_str else datetime.utcnow()

        # Read new Phase 3 columns with safe fallbacks for pre-migration rows
        tags_col = row.get("tags")
        if tags_col:
            try:
                tags_list = json.loads(tags_col)
            except Exception:
                tags_list = meta_dict.get("tags", [])
        else:
            tags_list = meta_dict.get("tags", [])

        metadata = MemoryMetadata(
            source=source_enum,
            timestamp=created_dt,
            emotion=emotion_enum,
            importance=float(row.get("importance", 0.5)),
            confidence=float(row.get("confidence", 1.0)),
            location=meta_dict.get("location"),
            context=meta_dict.get("context", {}),
            tags=tags_list,
            category=row.get("category") or meta_dict.get("category"),
            priority=int(row.get("priority") or meta_dict.get("priority") or 5),
            source_attribution=row.get("source_attribution") or meta_dict.get("source_attribution"),
        )

        content_raw = row.get("content", "")
        try:
            content_parsed = json.loads(content_raw)
        except Exception:
            content_parsed = content_raw

        emb_bytes = row.get("embedding")
        if emb_bytes:
            raw_vec = np.frombuffer(emb_bytes, dtype=np.float32)
            # Only use the stored embedding if its dimension matches the current model.
            # Stale embeddings from a different model are discarded so store() will
            # regenerate them on the next write.
            embedding = raw_vec.tolist() if raw_vec.shape[0] == self.vector_dim else None
        else:
            embedding = None

        last_acc_str = row.get("last_accessed")
        last_accessed = datetime.fromisoformat(last_acc_str) if last_acc_str else None

        upd_str = row.get("updated_at")
        updated_at = datetime.fromisoformat(upd_str) if upd_str else None

        exp_str = row.get("expires_at")
        expires_at = datetime.fromisoformat(exp_str) if exp_str else None

        mem_type_str = row.get("type", "short_term")
        try:
            mem_type = MemoryType(mem_type_str)
        except ValueError:
            mem_type = MemoryType.SHORT_TERM

        return MemoryItem(
            id=row["id"],
            type=mem_type,
            content=content_parsed,
            metadata=metadata,
            user_id=row.get("user_id", "default"),
            agent_id=row.get("agent_id"),
            conversation_id=row.get("conversation_id"),
            embedding=embedding,
            access_count=int(row.get("access_count", 0)),
            last_accessed=last_accessed,
            created_at=created_dt,
            updated_at=updated_at,
            expires_at=expires_at,
            is_archived=bool(row.get("is_archived", 0)),
            is_deleted=bool(row.get("is_deleted", 0)),
            version=int(row.get("version", 1)),
            ttl=float(row["ttl"]) if row.get("ttl") is not None else None,
            consolidation_count=int(row.get("consolidation_count") or 0),
        )

    # ─── Hybrid Search & Ranking ──────────────────────────────────────────────

    def search_hybrid(self, filter_opts: MemorySearchFilter) -> List[RetrievalResult]:
        """
        Production hybrid memory retrieval:
        Combines keyword token overlap, vector cosine similarity, importance,
        recency decay, and frequency weighting.
        """
        conditions = ["is_deleted = 0"]
        params: List[Any] = []

        if not filter_opts.include_archived:
            conditions.append("is_archived = 0")
        # Only filter by user_id when a non-empty value is provided.
        # Consolidation sweeps pass user_id="" to scan all users.
        if filter_opts.user_id and filter_opts.user_id.strip():
            conditions.append("user_id = ?")
            params.append(filter_opts.user_id)
        if filter_opts.agent_id:
            conditions.append("agent_id = ?")
            params.append(filter_opts.agent_id)
        if filter_opts.conversation_id:
            conditions.append("conversation_id = ?")
            params.append(filter_opts.conversation_id)
        if filter_opts.min_importance > 0.0:
            conditions.append("importance >= ?")
            params.append(filter_opts.min_importance)
        if filter_opts.min_confidence > 0.0:
            conditions.append("confidence >= ?")
            params.append(filter_opts.min_confidence)

        if filter_opts.memory_type:
            type_val = filter_opts.memory_type.value if hasattr(filter_opts.memory_type, "value") else str(filter_opts.memory_type)
            conditions.append("type = ?")
            params.append(type_val)
        elif filter_opts.memory_types:
            type_vals = [t.value if hasattr(t, "value") else str(t) for t in filter_opts.memory_types]
            placeholders = ",".join("?" for _ in type_vals)
            conditions.append(f"type IN ({placeholders})")
            params.extend(type_vals)

        if filter_opts.start_time:
            conditions.append("created_at >= ?")
            params.append(filter_opts.start_time.isoformat())
        if filter_opts.end_time:
            conditions.append("created_at <= ?")
            params.append(filter_opts.end_time.isoformat())

        sql = f"SELECT * FROM memories WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT 500"
        rows = self._execute_sql(sql, params)
        if not rows:
            return []

        candidates = [self._row_to_memory(r) for r in rows]
        query_text = filter_opts.query.strip().lower()
        query_tokens = set(query_text.split()) if query_text else set()
        query_vec = np.array(self._generate_embedding(query_text), dtype=np.float32) if query_text else None

        results: List[RetrievalResult] = []
        now = datetime.utcnow()

        for mem in candidates:
            # Check tag filter
            if filter_opts.tags:
                mem_tags = [t.lower() for t in (mem.metadata.tags or [])]
                if not any(t.lower() in mem_tags for t in filter_opts.tags):
                    continue

            content_str = json.dumps(mem.content).lower() if isinstance(mem.content, (dict, list)) else str(mem.content).lower()
            content_tokens = set(content_str.split())

            # 1. Keyword Score (Jaccard token overlap + substring match)
            kw_score = 0.0
            if query_tokens and content_tokens:
                overlap = len(query_tokens & content_tokens)
                union = len(query_tokens | content_tokens)
                jaccard = overlap / max(1, union)
                substr_boost = 0.3 if query_text in content_str else 0.0
                kw_score = min(1.0, jaccard * 2.0 + substr_boost)

            # 2. Vector Semantic Score (Cosine similarity)
            # Guard against dimension mismatch: stale DB rows may have been stored
            # with a different embedding model (e.g. 768-dim hash vs 384-dim ST).
            # When dimensions differ we skip the vector score rather than crashing.
            vec_score = 0.0
            if query_vec is not None and mem.embedding:
                mem_vec = np.array(mem.embedding, dtype=np.float32)
                if mem_vec.shape[0] == query_vec.shape[0]:
                    norm_q = np.linalg.norm(query_vec)
                    norm_m = np.linalg.norm(mem_vec)
                    if norm_q > 0 and norm_m > 0:
                        cos_sim = float(np.dot(query_vec, mem_vec)) / (norm_q * norm_m)
                        vec_score = max(0.0, cos_sim)
                else:
                    # Dimension mismatch — re-embed from stored content so the
                    # next store() call will persist the corrected embedding.
                    mem.embedding = None

            # 3. Importance Score
            imp_score = float(mem.metadata.importance)

            # 4. Recency Score (Exponential time-decay: e^(-0.01 * hours))
            created_dt = mem.created_at or now
            hours_old = max(0.0, (now - created_dt).total_seconds() / 3600.0)
            rec_score = math.exp(-0.01 * hours_old)

            # 5. Frequency Score (ln(1 + access_count) normalized)
            freq_score = min(1.0, math.log1p(mem.access_count) / 5.0)

            # Composite hybrid score
            total_score = (
                self.w_keyword * kw_score +
                self.w_vector * vec_score +
                self.w_importance * imp_score +
                self.w_recency * rec_score +
                self.w_frequency * freq_score
            )

            explanation = (
                f"HybridScore: {total_score:.3f} (KW: {kw_score:.2f}, Vec: {vec_score:.2f}, "
                f"Imp: {imp_score:.2f}, Rec: {rec_score:.2f}, Freq: {freq_score:.2f})"
            )

            linked: List[MemoryItem] = []
            if filter_opts.traverse_relationships:
                linked = self.get_linked_memories(mem.id, depth=filter_opts.traversal_depth)

            results.append(RetrievalResult(
                memory=mem,
                relevance_score=round(total_score, 4),
                keyword_score=round(kw_score, 3),
                semantic_score=round(vec_score, 3),
                importance_score=round(imp_score, 3),
                recency_score=round(rec_score, 3),
                frequency_score=round(freq_score, 3),
                explanation=explanation,
                linked_memories=linked,
            ))

        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[filter_opts.offset : filter_opts.offset + filter_opts.limit]

    def search(self, query: str, limit: int = 10, user_id: str = "default") -> List[MemoryItem]:
        """Backward-compatible search wrapper."""
        filter_opts = MemorySearchFilter(query=query, user_id=user_id, limit=limit)
        results = self.search_hybrid(filter_opts)
        return [r.memory for r in results]

    # ─── Relationships ────────────────────────────────────────────────────────

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: RelationshipType,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a directed relationship link between two memory items."""
        rel_id = f"rel-{uuid.uuid4().hex[:12]}"
        rel_type_val = relationship_type.value if hasattr(relationship_type, "value") else str(relationship_type)
        sql = """
        INSERT INTO memory_relationships (id, source_id, target_id, relationship_type, weight, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            rel_id,
            source_id,
            target_id,
            rel_type_val,
            weight,
            json.dumps(metadata or {}),
            datetime.utcnow().isoformat(),
        )
        self._write_sql(sql, params)
        return rel_id

    def get_linked_memories(self, memory_id: str, depth: int = 1) -> List[MemoryItem]:
        """Traverse relationships to fetch linked memory items up to specified depth."""
        if depth <= 0:
            return []

        # Use a single column alias so the UNION result always has a consistent key.
        rows = self._execute_sql(
            "SELECT target_id AS linked_id FROM memory_relationships WHERE source_id = ? "
            "UNION SELECT source_id AS linked_id FROM memory_relationships WHERE target_id = ?",
            (memory_id, memory_id),
        )
        linked_ids = [r["linked_id"] for r in rows if r.get("linked_id")]

        memories: List[MemoryItem] = []
        for lid in linked_ids[:10]:
            mem = self.retrieve(lid)
            if mem:
                memories.append(mem)

        return memories

    # ─── Update / Delete / Archive ────────────────────────────────────────────

    def update(self, memory_id: str, updates: Dict[str, Any], reason: str = "update") -> bool:
        """Update a memory item and save version snapshot to history."""
        memory = self.retrieve(memory_id)
        if not memory:
            return False

        # Apply updates to the in-memory object first
        memory.version += 1
        memory.updated_at = datetime.utcnow()

        for k, v in updates.items():
            if k == "content":
                memory.content = v
            elif k == "importance":
                memory.metadata.importance = float(v)
            elif k == "confidence":
                memory.metadata.confidence = float(v)
            elif k == "tags":
                memory.metadata.tags = v
            elif hasattr(memory, k):
                setattr(memory, k, v)

        # Persist the updated row first so the FK constraint is satisfied
        stored = self.store(memory)

        # Save snapshot AFTER store so the FK reference is valid
        snapshot_sql = """
        INSERT INTO memory_history (id, memory_id, version, content_snapshot, change_reason, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        self._write_sql(
            snapshot_sql,
            (
                f"hist-{uuid.uuid4().hex[:12]}",
                memory.id,
                memory.version,
                json.dumps(memory.content),
                reason,
                datetime.utcnow().isoformat(),
            ),
        )

        return stored

    def delete(self, memory_id: str, hard: bool = False) -> bool:
        """Delete a memory item (soft delete by default, hard delete optional)."""
        self.lru_cache.remove(memory_id)
        if hard:
            self._write_sql("DELETE FROM memory_relationships WHERE source_id = ? OR target_id = ?", (memory_id, memory_id))
            self._write_sql("DELETE FROM memory_history WHERE memory_id = ?", (memory_id,))
            return self._write_sql("DELETE FROM memories WHERE id = ?", (memory_id,)) > 0

        return self._write_sql("UPDATE memories SET is_deleted = 1, updated_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), memory_id)) > 0

    def archive(self, memory_id: str) -> bool:
        """Archive a memory item."""
        self.lru_cache.remove(memory_id)
        return self._write_sql("UPDATE memories SET is_archived = 1, updated_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), memory_id)) > 0

    def restore(self, memory_id: str) -> bool:
        """Restore an archived or soft-deleted memory item."""
        self.lru_cache.remove(memory_id)
        return self._write_sql("UPDATE memories SET is_archived = 0, is_deleted = 0, updated_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), memory_id)) > 0

    # ─── Maintenance & Cleanup ────────────────────────────────────────────────

    def cleanup_expired(self) -> int:
        """Purge soft-deleted or TTL-expired memories."""
        now_iso = datetime.utcnow().isoformat()
        rows = self._execute_sql(
            "SELECT id FROM memories WHERE is_deleted = 1 OR (expires_at IS NOT NULL AND expires_at < ?)",
            (now_iso,),
        )
        expired_ids = [r["id"] for r in rows]
        for mid in expired_ids:
            self.delete(mid, hard=True)
        return len(expired_ids)

    def close(self):
        """Close direct SQLite connection if owned."""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        self.lru_cache.clear()