"""Memory storage module for handling different storage backends."""

import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from .memory_types import MemoryItem, MemoryType, MemorySource

class MemoryStorage:
    def __init__(self, config: Dict[str, Any]):
        """Initialize memory storage with specified backends."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Initialize storage backends
        self._init_storage()
        
        # Initialize embedding model
        self._init_embedding_model()
    
    def _init_storage(self):
        """Initialize storage backends."""
        # Initialize SQLite for structured data
        self.db_path = self.config.get("sqlite_path", "memory.db")
        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()
        
        # Initialize FAISS for vector storage
        self.vector_dim = self.config.get("vector_dim", 768)
        self.index = faiss.IndexFlatL2(self.vector_dim)
        self.memory_map = {}  # Maps FAISS indices to memory IDs
    
    def _init_embedding_model(self):
        """Initialize the embedding model."""
        model_name = self.config.get("embedding_model", "all-MiniLM-L6-v2")
        self.embedding_model = SentenceTransformer(model_name)
    
    def _create_tables(self):
        """Create necessary database tables."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    content TEXT,
                    metadata TEXT,
                    embedding BLOB,
                    access_count INTEGER,
                    last_accessed TEXT,
                    ttl REAL
                )
            """)
    
    def store(self, memory: MemoryItem) -> bool:
        """Store a memory item in all backends."""
        try:
            # Generate embedding if not present
            if memory.embedding is None:
                memory.embedding = self._generate_embedding(memory)
            
            # Store in SQLite
            self._store_sqlite(memory)
            
            # Store in FAISS
            self._store_faiss(memory)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error storing memory: {str(e)}")
            return False
    
    def _store_sqlite(self, memory: MemoryItem):
        """Store memory in SQLite database."""
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO memories
                (id, type, content, metadata, embedding, access_count, last_accessed, ttl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.type.value,
                    json.dumps(memory.content),
                    json.dumps(memory.metadata.__dict__),
                    np.array(memory.embedding).tobytes(),
                    memory.access_count,
                    memory.last_accessed.isoformat() if memory.last_accessed else None,
                    memory.ttl
                )
            )
    
    def _store_faiss(self, memory: MemoryItem):
        """Store memory in FAISS index."""
        if memory.embedding:
            idx = self.index.ntotal
            self.index.add(np.array([memory.embedding], dtype=np.float32))
            self.memory_map[idx] = memory.id
    
    def _generate_embedding(self, memory: MemoryItem) -> List[float]:
        """Generate embedding for a memory item."""
        # Combine content and metadata for embedding
        text = f"{memory.content} {memory.metadata.context if memory.metadata.context else ''}"
        embedding = self.embedding_model.encode(text)
        return embedding.tolist()
    
    def retrieve(self, memory_id: str) -> Optional[MemoryItem]:
        """Retrieve a memory by ID."""
        try:
            # Retrieve from SQLite
            with self.conn:
                cursor = self.conn.execute(
                    "SELECT * FROM memories WHERE id = ?",
                    (memory_id,)
                )
                row = cursor.fetchone()
            
            if row:
                return self._row_to_memory(row)
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error retrieving memory: {str(e)}")
            return None
    
    def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """Search memories by semantic similarity."""
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query)
            
            # Search in FAISS
            distances, indices = self.index.search(
                np.array([query_embedding], dtype=np.float32),
                limit
            )
            
            # Retrieve memories
            memories = []
            for idx in indices[0]:
                if idx in self.memory_map:
                    memory_id = self.memory_map[idx]
                    memory = self.retrieve(memory_id)
                    if memory:
                        memories.append(memory)
            
            return memories
        
        except Exception as e:
            self.logger.error(f"Error searching memories: {str(e)}")
            return []
    
    def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a memory item."""
        try:
            memory = self.retrieve(memory_id)
            if not memory:
                return False
            
            # Update memory fields
            for key, value in updates.items():
                if hasattr(memory, key):
                    setattr(memory, key, value)
            
            # Update last accessed
            memory.last_accessed = datetime.now()
            memory.access_count += 1
            
            # Store updated memory
            return self.store(memory)
        
        except Exception as e:
            self.logger.error(f"Error updating memory: {str(e)}")
            return False
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory item."""
        try:
            # Delete from SQLite
            with self.conn:
                self.conn.execute(
                    "DELETE FROM memories WHERE id = ?",
                    (memory_id,)
                )
            
            # Delete from FAISS (requires rebuilding index)
            self._rebuild_faiss_index()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error deleting memory: {str(e)}")
            return False
    
    def _rebuild_faiss_index(self):
        """Rebuild FAISS index from SQLite data."""
        try:
            # Create new index
            self.index = faiss.IndexFlatL2(self.vector_dim)
            self.memory_map = {}
            
            # Retrieve all memories
            with self.conn:
                cursor = self.conn.execute("SELECT id, embedding FROM memories")
                rows = cursor.fetchall()
            
            # Add to FAISS
            for idx, (memory_id, embedding_bytes) in enumerate(rows):
                embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                self.index.add(np.array([embedding], dtype=np.float32))
                self.memory_map[idx] = memory_id
        
        except Exception as e:
            self.logger.error(f"Error rebuilding FAISS index: {str(e)}")
    
    def _row_to_memory(self, row: tuple) -> MemoryItem:
        """Convert database row to MemoryItem."""
        from .memory_types import MemoryMetadata
        
        # Parse metadata
        metadata_dict = json.loads(row[3])
        metadata = MemoryMetadata(**metadata_dict)
        
        # Create memory item
        memory = MemoryItem(
            id=row[0],
            type=MemoryType(row[1]),
            content=json.loads(row[2]),
            metadata=metadata,
            embedding=np.frombuffer(row[4], dtype=np.float32).tolist() if row[4] else None,
            access_count=row[5],
            last_accessed=datetime.fromisoformat(row[6]) if row[6] else None,
            ttl=row[7]
        )
        
        return memory
    
    def cleanup(self):
        """Clean up expired memories."""
        try:
            # Get current time
            now = datetime.now()
            
            # Find expired memories
            with self.conn:
                cursor = self.conn.execute(
                    """
                    SELECT id FROM memories
                    WHERE ttl IS NOT NULL
                    AND datetime(last_accessed) + ttl < datetime(?)
                    """,
                    (now.isoformat(),)
                )
                expired_ids = [row[0] for row in cursor.fetchall()]
            
            # Delete expired memories
            for memory_id in expired_ids:
                self.delete(memory_id)
        
        except Exception as e:
            self.logger.error(f"Error cleaning up memories: {str(e)}")
    
    def close(self):
        """Close storage connections."""
        try:
            self.conn.close()
        except Exception as e:
            self.logger.error(f"Error closing storage: {str(e)}") 