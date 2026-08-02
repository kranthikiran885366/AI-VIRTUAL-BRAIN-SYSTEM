"""Runtime database infrastructure for the orchestrator.

This module provides a lightweight SQLite connection pool, repository base
class, transaction management, and migration validation suitable for the
existing project without introducing a new ORM dependency.
"""

from __future__ import annotations

import contextlib
import logging
import queue
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    database_path: str = "data/brain.db"
    pool_size: int = 4
    timeout_seconds: float = 5.0
    log_queries: bool = True
    enable_wal: bool = True


class SQLiteConnectionPool:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self._pool: "queue.Queue[sqlite3.Connection]" = queue.Queue(maxsize=max(1, config.pool_size))
        self._lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        Path(self.config.database_path).parent.mkdir(parents=True, exist_ok=True)
        for _ in range(self.config.pool_size):
            self._pool.put(self._create_connection())
        self._initialized = True

    def _create_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.config.database_path, timeout=self.config.timeout_seconds, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        if self.config.enable_wal:
            connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextlib.contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        if not self._initialized:
            self.initialize()
        connection = self._pool.get(timeout=self.config.timeout_seconds)
        try:
            yield connection
        finally:
            self._pool.put(connection)

    def close(self) -> None:
        while not self._pool.empty():
            connection = self._pool.get_nowait()
            connection.close()
        self._initialized = False


class QueryLogger:
    def __init__(self, logger_: logging.Logger, enabled: bool = True) -> None:
        self._logger = logger_
        self._enabled = enabled

    def log(self, sql: str, params: Optional[Sequence[Any]] = None, elapsed_ms: Optional[float] = None) -> None:
        if not self._enabled:
            return
        self._logger.info(
            "db.query",
            extra={
                "sql": sql,
                "params_count": len(params) if params is not None else 0,
                "elapsed_ms": elapsed_ms,
            },
        )


class Repository:
    def __init__(self, pool: SQLiteConnectionPool, query_logger: Optional[QueryLogger] = None) -> None:
        self.pool = pool
        self.query_logger = query_logger or QueryLogger(logger, enabled=True)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        start = time.perf_counter()
        with self.pool.get_connection() as connection:
            cursor = connection.execute(sql, params)
            connection.commit()
        self.query_logger.log(sql, params, (time.perf_counter() - start) * 1000)
        return cursor.rowcount

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        start = time.perf_counter()
        with self.pool.get_connection() as connection:
            cursor = connection.execute(sql, params)
            row = cursor.fetchone()
        self.query_logger.log(sql, params, (time.perf_counter() - start) * 1000)
        return dict(row) if row else None

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        start = time.perf_counter()
        with self.pool.get_connection() as connection:
            cursor = connection.execute(sql, params)
            rows = cursor.fetchall()
        self.query_logger.log(sql, params, (time.perf_counter() - start) * 1000)
        return [dict(row) for row in rows]

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> int:
        start = time.perf_counter()
        with self.pool.get_connection() as connection:
            cursor = connection.executemany(sql, rows)
            connection.commit()
        self.query_logger.log(sql, None, (time.perf_counter() - start) * 1000)
        return cursor.rowcount


class TransactionManager:
    def __init__(self, pool: SQLiteConnectionPool) -> None:
        self.pool = pool

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.pool.get_connection() as connection:
            try:
                connection.execute("BEGIN")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise


class MigrationValidator:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def validate(self, required_tables: Sequence[str]) -> Dict[str, Any]:
        rows = self.repository.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row["name"] for row in rows}
        missing = [table for table in required_tables if table not in existing_tables]
        return {
            "ok": not missing,
            "missing_tables": missing,
            "existing_tables": sorted(existing_tables),
        }


class DatabaseManager:
    def __init__(self, config: Optional[DatabaseConfig] = None) -> None:
        self.config = config or DatabaseConfig()
        self.pool = SQLiteConnectionPool(self.config)
        self.repository = Repository(self.pool)
        self.transactions = TransactionManager(self.pool)
        self.migration_validator = MigrationValidator(self.repository)

    def ensure_cognitive_schema(self) -> None:
        """Create cognitive memory tables, run additive column migrations, and build indexes."""
        base_tables = [
            """
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
            """,
            """
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
            """,
            """
            CREATE TABLE IF NOT EXISTS memory_history (
                id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                content_snapshot TEXT,
                change_reason TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
            )
            """,
            """
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
            """,
            """
            CREATE TABLE IF NOT EXISTS retention_policies (
                id TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL UNIQUE,
                ttl_seconds REAL,
                max_capacity INTEGER DEFAULT 10000,
                importance_floor REAL DEFAULT 0.0,
                consolidation_threshold REAL DEFAULT 0.65,
                archival_after_days INTEGER,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            )
            """,
        ]
        with self.pool.get_connection() as conn:
            for sql in base_tables:
                conn.execute(sql)
            conn.commit()

        # Additive column migrations — safe to run repeatedly
        additive_migrations = [
            (1, "ADD tags column",       "ALTER TABLE memories ADD COLUMN tags TEXT DEFAULT '[]'"),
            (2, "ADD category column",   "ALTER TABLE memories ADD COLUMN category TEXT"),
            (3, "ADD priority column",   "ALTER TABLE memories ADD COLUMN priority INTEGER DEFAULT 5"),
            (4, "ADD source_attribution","ALTER TABLE memories ADD COLUMN source_attribution TEXT"),
            (5, "ADD consolidation_count","ALTER TABLE memories ADD COLUMN consolidation_count INTEGER DEFAULT 0"),
        ]
        with self.pool.get_connection() as conn:
            applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
            for version, description, alter_sql in additive_migrations:
                if version not in applied:
                    try:
                        conn.execute(alter_sql)
                    except Exception:
                        pass  # column already exists (e.g. from a previous partial run)
                    conn.execute(
                        "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
                        (version, datetime.utcnow().isoformat(), description),
                    )
            conn.commit()

        # Indexes — all idempotent
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_mem_user_type ON memories(user_id, type, importance DESC, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_mem_conversation ON memories(conversation_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_mem_agent ON memories(agent_id, type)",
            "CREATE INDEX IF NOT EXISTS idx_mem_expiry ON memories(expires_at) WHERE expires_at IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_mem_active ON memories(is_deleted, is_archived, type)",
            "CREATE INDEX IF NOT EXISTS idx_mem_importance ON memories(importance DESC)",
            "CREATE INDEX IF NOT EXISTS idx_mem_category ON memories(category) WHERE category IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_rel_source ON memory_relationships(source_id)",
            "CREATE INDEX IF NOT EXISTS idx_rel_target ON memory_relationships(target_id)",
            "CREATE INDEX IF NOT EXISTS idx_hist_mem ON memory_history(memory_id, version)",
            "CREATE INDEX IF NOT EXISTS idx_consol_log_mem ON memory_consolidation_log(memory_id)",
            "CREATE INDEX IF NOT EXISTS idx_consol_log_ts ON memory_consolidation_log(timestamp DESC)",
        ]
        with self.pool.get_connection() as conn:
            for sql in indexes:
                conn.execute(sql)
            conn.commit()

    def initialize(self) -> None:
        self.pool.initialize()
        self.ensure_cognitive_schema()

    def shutdown(self) -> None:
        self.pool.close()

    def health_check(self) -> Dict[str, Any]:
        try:
            with self.pool.get_connection() as connection:
                connection.execute("SELECT 1")
            return {"ok": True, "status": "healthy"}
        except Exception as exc:
            return {"ok": False, "status": "unhealthy", "error": str(exc)}

