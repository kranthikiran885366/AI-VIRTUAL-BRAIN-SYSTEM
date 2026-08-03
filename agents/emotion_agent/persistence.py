"""
Production Emotion Persistence Layer for Phase 8

Implements SQLite-backed storage with:
- ACID transactions
- Audit trail logging
- Historical data queries
- Correlation tracking
"""

import asyncio
import logging
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from contextlib import asynccontextmanager

from .state_model import (
    EmotionRecord, EmotionState, EmotionType,
    EmotionalContext, TemporalMetadata
)

logger = logging.getLogger(__name__)


class EmotionPersistenceError(Exception):
    """Base exception for persistence errors."""
    pass


class AuditLogEntry:
    """Represents an audit log entry."""
    
    def __init__(
        self,
        emotion_id: str,
        action: str,
        actor: str,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = None  # Will be assigned by database
        self.emotion_id = emotion_id
        self.action = action
        self.actor = actor
        self.timestamp = timestamp
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "emotion_id": self.emotion_id,
            "action": self.action,
            "actor": self.actor,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class EmotionPersistence:
    """
    SQLite-backed persistence for emotion records.
    
    Features:
    - ACID transactions
    - Audit trail for all changes
    - Queryable history
    - Correlation tracking
    - Backup/restore
    """
    
    def __init__(self, db_path: str = "data/emotion_store/emotions.db"):
        """Initialize persistence layer."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection_pool: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return
        
        async with self._lock:
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                
                # Enable foreign keys
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Create tables
                self._create_schema(conn)
                conn.commit()
                conn.close()
                
                self._initialized = True
                logger.info(f"Initialized emotion persistence at {self.db_path}")
            except sqlite3.Error as e:
                raise EmotionPersistenceError(f"Failed to initialize database: {e}")
    
    def _create_schema(self, conn: sqlite3.Connection) -> None:
        """Create database schema."""
        cursor = conn.cursor()
        
        # Emotions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emotions (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                emotion_type TEXT NOT NULL,
                intensity REAL NOT NULL,
                state TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                parent_emotion_id TEXT,
                resolution_data TEXT,
                created_at TEXT NOT NULL,
                activated_at TEXT,
                decay_started_at TEXT,
                resolved_at TEXT,
                last_updated_at TEXT,
                created_timestamp REAL NOT NULL,
                updated_timestamp REAL NOT NULL
            )
        """)
        
        # Create index on agent_id for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emotions_agent_id 
            ON emotions(agent_id)
        """)
        
        # Create index on correlation_id for chain queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emotions_correlation_id 
            ON emotions(correlation_id)
        """)
        
        # Create index on state for state queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emotions_state 
            ON emotions(state)
        """)
        
        # Emotion history table (state transitions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emotion_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emotion_id TEXT NOT NULL,
                old_state TEXT,
                new_state TEXT NOT NULL,
                intensity REAL NOT NULL,
                reason TEXT,
                timestamp TEXT NOT NULL,
                created_timestamp REAL NOT NULL,
                FOREIGN KEY (emotion_id) REFERENCES emotions(id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emotion_history_emotion_id 
            ON emotion_history(emotion_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_emotion_history_timestamp 
            ON emotion_history(timestamp)
        """)
        
        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emotion_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                created_timestamp REAL NOT NULL,
                FOREIGN KEY (emotion_id) REFERENCES emotions(id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_log_emotion_id 
            ON audit_log(emotion_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp 
            ON audit_log(timestamp)
        """)
        
        # Correlation chains table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS correlation_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_emotion_id TEXT,
                child_emotion_id TEXT NOT NULL,
                relationship_type TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (parent_emotion_id) REFERENCES emotions(id),
                FOREIGN KEY (child_emotion_id) REFERENCES emotions(id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_correlation_chains_parent 
            ON correlation_chains(parent_emotion_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_correlation_chains_child 
            ON correlation_chains(child_emotion_id)
        """)
        
        conn.commit()
    
    @asynccontextmanager
    async def _get_connection(self):
        """Get a database connection with locking."""
        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
            finally:
                conn.close()
    
    async def save_emotion(self, emotion: EmotionRecord) -> None:
        """Save an emotion record to persistent storage."""
        if not self._initialized:
            raise EmotionPersistenceError("Persistence layer not initialized")
        
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                now = datetime.utcnow()
                timestamp = now.timestamp()
                
                # Serialize complex fields
                resolution_data = json.dumps(emotion.resolution_data or {})
                
                # Upsert emotion record
                cursor.execute("""
                    INSERT OR REPLACE INTO emotions (
                        id, agent_id, emotion_type, intensity, state,
                        correlation_id, parent_emotion_id, resolution_data,
                        created_at, activated_at, decay_started_at,
                        resolved_at, last_updated_at,
                        created_timestamp, updated_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    emotion.id,
                    emotion.agent_id,
                    emotion.emotion_type.value,
                    emotion.intensity,
                    emotion.state.value,
                    emotion.correlation_id,
                    emotion.parent_emotion_id,
                    resolution_data,
                    emotion.temporal.created_at.isoformat(),
                    emotion.temporal.activated_at.isoformat() if emotion.temporal.activated_at else None,
                    emotion.temporal.decay_started_at.isoformat() if emotion.temporal.decay_started_at else None,
                    emotion.temporal.resolved_at.isoformat() if emotion.temporal.resolved_at else None,
                    emotion.temporal.last_updated_at.isoformat() if emotion.temporal.last_updated_at else None,
                    emotion.temporal.created_at.timestamp(),
                    timestamp,
                ))
                
                # Record state transition if state changed
                await self._record_state_transition(
                    cursor, emotion.id, emotion.state.value, emotion.intensity, now
                )
                
                # Record correlation
                if emotion.parent_emotion_id:
                    cursor.execute("""
                        INSERT OR IGNORE INTO correlation_chains (
                            parent_emotion_id, child_emotion_id, relationship_type, created_at
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        emotion.parent_emotion_id,
                        emotion.id,
                        "causation",
                        now.isoformat(),
                    ))
                
                conn.commit()
                logger.debug(f"Saved emotion {emotion.id} to persistent storage")
            except sqlite3.Error as e:
                conn.rollback()
                raise EmotionPersistenceError(f"Failed to save emotion: {e}")
    
    async def _record_state_transition(
        self,
        cursor: sqlite3.Cursor,
        emotion_id: str,
        new_state: str,
        intensity: float,
        timestamp: datetime,
    ) -> None:
        """Record a state transition in history."""
        cursor.execute("""
            INSERT INTO emotion_history (
                emotion_id, new_state, intensity, timestamp, created_timestamp
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            emotion_id,
            new_state,
            intensity,
            timestamp.isoformat(),
            timestamp.timestamp(),
        ))
    
    async def get_emotion(self, emotion_id: str) -> Optional[EmotionRecord]:
        """Load an emotion record from persistent storage."""
        if not self._initialized:
            raise EmotionPersistenceError("Persistence layer not initialized")
        
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT * FROM emotions WHERE id = ?
                """, (emotion_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return self._row_to_emotion(row)
            except sqlite3.Error as e:
                raise EmotionPersistenceError(f"Failed to retrieve emotion: {e}")
    
    async def get_agent_emotions(
        self,
        agent_id: str,
        state: Optional[str] = None,
    ) -> List[EmotionRecord]:
        """Get all emotions for an agent."""
        if not self._initialized:
            raise EmotionPersistenceError("Persistence layer not initialized")
        
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                if state:
                    cursor.execute("""
                        SELECT * FROM emotions 
                        WHERE agent_id = ? AND state = ?
                        ORDER BY created_timestamp DESC
                    """, (agent_id, state))
                else:
                    cursor.execute("""
                        SELECT * FROM emotions 
                        WHERE agent_id = ?
                        ORDER BY created_timestamp DESC
                    """, (agent_id,))
                
                rows = cursor.fetchall()
                return [self._row_to_emotion(row) for row in rows]
            except sqlite3.Error as e:
                raise EmotionPersistenceError(f"Failed to retrieve emotions: {e}")
    
    async def get_correlation_chain(self, correlation_id: str) -> List[EmotionRecord]:
        """Get all emotions in a correlation chain."""
        if not self._initialized:
            raise EmotionPersistenceError("Persistence layer not initialized")
        
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT * FROM emotions 
                    WHERE correlation_id = ?
                    ORDER BY created_timestamp ASC
                """, (correlation_id,))
                
                rows = cursor.fetchall()
                return [self._row_to_emotion(row) for row in rows]
            except sqlite3.Error as e:
                raise EmotionPersistenceError(f"Failed to retrieve correlation chain: {e}")
    
    async def get_emotion_history(
        self,
        emotion_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get state transition history for an emotion."""
        if not self._initialized:
            raise EmotionPersistenceError("Persistence layer not initialized")
        
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT * FROM emotion_history 
                    WHERE emotion_id = ?
                    ORDER BY created_timestamp DESC
                    LIMIT ?
                """, (emotion_id, limit))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            except sqlite3.Error as e:
                raise EmotionPersistenceError(f"Failed to retrieve history: {e}")
    
    async def add_audit_entry(
        self,
        emotion_id: str,
        action: str,
        actor: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an audit log entry."""
        if not self._initialized:
            raise EmotionPersistenceError("Persistence layer not initialized")
        
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                now = datetime.utcnow()
                cursor.execute("""
                    INSERT INTO audit_log (
                        emotion_id, action, actor, timestamp, metadata, created_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    emotion_id,
                    action,
                    actor,
                    now.isoformat(),
                    json.dumps(metadata or {}),
                    now.timestamp(),
                ))
                conn.commit()
                logger.debug(f"Added audit entry for emotion {emotion_id}: {action} by {actor}")
            except sqlite3.Error as e:
                conn.rollback()
                raise EmotionPersistenceError(f"Failed to add audit entry: {e}")
    
    async def get_audit_log(
        self,
        emotion_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit log."""
        if not self._initialized:
            raise EmotionPersistenceError("Persistence layer not initialized")
        
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                query = "SELECT * FROM audit_log WHERE 1=1"
                params = []
                
                if emotion_id:
                    query += " AND emotion_id = ?"
                    params.append(emotion_id)
                
                if action:
                    query += " AND action = ?"
                    params.append(action)
                
                query += " ORDER BY created_timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                result = []
                for row in rows:
                    entry_dict = dict(row)
                    if entry_dict.get("metadata"):
                        entry_dict["metadata"] = json.loads(entry_dict["metadata"])
                    result.append(entry_dict)
                
                return result
            except sqlite3.Error as e:
                raise EmotionPersistenceError(f"Failed to retrieve audit log: {e}")
    
    def _row_to_emotion(self, row: sqlite3.Row) -> EmotionRecord:
        """Convert database row to EmotionRecord."""
        resolution_data = {}
        if row["resolution_data"]:
            resolution_data = json.loads(row["resolution_data"])
        
        temporal = TemporalMetadata(
            created_at=datetime.fromisoformat(row["created_at"]),
            activated_at=datetime.fromisoformat(row["activated_at"]) if row["activated_at"] else None,
            decay_started_at=datetime.fromisoformat(row["decay_started_at"]) if row["decay_started_at"] else None,
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
            last_updated_at=datetime.fromisoformat(row["last_updated_at"]) if row["last_updated_at"] else None,
        )
        
        return EmotionRecord(
            id=row["id"],
            agent_id=row["agent_id"],
            emotion_type=EmotionType(row["emotion_type"]),
            intensity=row["intensity"],
            state=EmotionState(row["state"]),
            context=EmotionalContext(),  # Load from separate table if needed
            temporal=temporal,
            correlation_id=row["correlation_id"],
            parent_emotion_id=row["parent_emotion_id"],
            resolution_data=resolution_data,
        )
    
    async def cleanup_old_records(self, days: int = 90) -> int:
        """
        Clean up old resolved emotions.
        
        Args:
            days: Number of days to keep (default 90)
        
        Returns:
            Number of records deleted
        """
        if not self._initialized:
            raise EmotionPersistenceError("Persistence layer not initialized")
        
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
                
                cursor.execute("""
                    DELETE FROM emotions 
                    WHERE state = ? AND resolved_at < ?
                """, (EmotionState.RESOLVED.value, cutoff_date))
                
                deleted = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleaned up {deleted} old emotion records")
                return deleted
            except sqlite3.Error as e:
                conn.rollback()
                raise EmotionPersistenceError(f"Failed to cleanup records: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown persistence layer."""
        async with self._lock:
            self._initialized = False
            logger.info("Shutdown emotion persistence")
