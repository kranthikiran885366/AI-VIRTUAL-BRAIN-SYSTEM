"""Main memory agent module for coordinating memory operations."""

import logging
import threading
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from .memory_types import (
    MemorySource,
    EmotionType,
    MemoryType
)
from .memory_storage import MemoryStorage
from .short_term_memory import ShortTermMemoryManager
from .long_term_memory import LongTermMemoryManager

class MemoryAgent:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the memory agent."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Initialize storage
        self.storage = MemoryStorage(config)
        
        # Initialize memory managers
        self.short_term = ShortTermMemoryManager(config, self.storage)
        self.long_term = LongTermMemoryManager(config, self.storage)
        
        # Initialize performance metrics
        self.metrics = {
            "operations": {
                "store": 0,
                "retrieve": 0,
                "search": 0,
                "update": 0,
                "delete": 0
            },
            "errors": 0,
            "start_time": datetime.now()
        }
        
        # Start background tasks
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """Start background tasks for memory management."""
        # Start cleanup task
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_task,
            daemon=True
        )
        self.cleanup_thread.start()
        
        # Start consolidation task
        self.consolidation_thread = threading.Thread(
            target=self._consolidation_task,
            daemon=True
        )
        self.consolidation_thread.start()
    
    def _cleanup_task(self):
        """Background task for cleaning up expired memories."""
        while True:
            try:
                self.short_term.cleanup()
                time.sleep(300)  # Run every 5 minutes
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {str(e)}")
                time.sleep(60)  # Wait before retrying
    
    def _consolidation_task(self):
        """Background task for consolidating memories."""
        while True:
            try:
                # Get short-term memories
                short_term_memories = list(self.short_term.memory_buffer)
                
                # Consolidate important memories
                consolidated_ids = self.long_term.consolidate_memories(short_term_memories)
                
                # Delete consolidated memories from short-term storage
                for memory_id in consolidated_ids:
                    self.short_term.delete(memory_id)
                
                time.sleep(3600)  # Run every hour
            except Exception as e:
                self.logger.error(f"Error in consolidation task: {str(e)}")
                time.sleep(60)  # Wait before retrying
    
    def store(self, data: Dict[str, Any], source: MemorySource,
              emotion: Optional[EmotionType] = None) -> Optional[str]:
        """Store new data in memory."""
        try:
            # Store in short-term memory
            memory_id = self.short_term.store(data, source, emotion)
            
            if memory_id:
                self.metrics["operations"]["store"] += 1
                return memory_id
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error storing memory: {str(e)}")
            self.metrics["errors"] += 1
            return None
    
    def retrieve(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a memory by ID."""
        try:
            # Try short-term memory first
            memory = self.short_term.retrieve(memory_id)
            
            if not memory:
                # Try long-term memory
                memory = self.long_term.retrieve(memory_id)
            
            if memory:
                self.metrics["operations"]["retrieve"] += 1
                return {
                    "id": memory.id,
                    "type": memory.type.value,
                    "content": memory.content,
                    "metadata": memory.metadata.__dict__
                }
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error retrieving memory: {str(e)}")
            self.metrics["errors"] += 1
            return None
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories by semantic similarity."""
        try:
            # Search both short-term and long-term memories
            short_term_results = self.short_term.search(query, limit)
            long_term_results = self.long_term.search(query, limit)
            
            # Combine and sort results
            all_results = short_term_results + long_term_results
            all_results.sort(key=lambda x: x.metadata.importance, reverse=True)
            
            # Convert to dictionary format
            results = []
            for memory in all_results[:limit]:
                results.append({
                    "id": memory.id,
                    "type": memory.type.value,
                    "content": memory.content,
                    "metadata": memory.metadata.__dict__
                })
            
            self.metrics["operations"]["search"] += 1
            return results
        
        except Exception as e:
            self.logger.error(f"Error searching memories: {str(e)}")
            self.metrics["errors"] += 1
            return []
    
    def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a memory."""
        try:
            # Try short-term memory first
            success = self.short_term.update(memory_id, updates)
            
            if not success:
                # Try long-term memory
                success = self.long_term.update(memory_id, updates)
            
            if success:
                self.metrics["operations"]["update"] += 1
            
            return success
        
        except Exception as e:
            self.logger.error(f"Error updating memory: {str(e)}")
            self.metrics["errors"] += 1
            return False
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        try:
            # Try short-term memory first
            success = self.short_term.delete(memory_id)
            
            if not success:
                # Try long-term memory
                success = self.long_term.delete(memory_id)
            
            if success:
                self.metrics["operations"]["delete"] += 1
            
            return success
        
        except Exception as e:
            self.logger.error(f"Error deleting memory: {str(e)}")
            self.metrics["errors"] += 1
            return False
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        try:
            # Get metrics from memory managers
            short_term_metrics = self.short_term.get_performance_metrics()
            long_term_metrics = self.long_term.get_memory_stats()
            
            # Calculate uptime
            uptime = (datetime.now() - self.metrics["start_time"]).total_seconds()
            
            return {
                "uptime_seconds": uptime,
                "operations": self.metrics["operations"],
                "errors": self.metrics["errors"],
                "short_term_metrics": short_term_metrics,
                "long_term_metrics": long_term_metrics
            }
        
        except Exception as e:
            self.logger.error(f"Error getting performance metrics: {str(e)}")
            return {}
    
    def reset(self):
        """Reset the memory agent."""
        try:
            # Reset memory managers
            self.short_term.reset()
            
            # Reset metrics
            self.metrics = {
                "operations": {
                    "store": 0,
                    "retrieve": 0,
                    "search": 0,
                    "update": 0,
                    "delete": 0
                },
                "errors": 0,
                "start_time": datetime.now()
            }
            
            self.logger.info("Memory agent reset")
        
        except Exception as e:
            self.logger.error(f"Error resetting memory agent: {str(e)}")
    
    def close(self):
        """Close the memory agent."""
        try:
            # Stop background tasks
            if hasattr(self, 'cleanup_thread'):
                self.cleanup_thread.join(timeout=1.0)
            if hasattr(self, 'consolidation_thread'):
                self.consolidation_thread.join(timeout=1.0)
            
            # Close storage
            self.storage.close()
            
            self.logger.info("Memory agent closed")
        
        except Exception as e:
            self.logger.error(f"Error closing memory agent: {str(e)}") 