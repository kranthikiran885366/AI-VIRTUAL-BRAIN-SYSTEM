import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid

from structlog import get_logger

from ...config import settings

logger = get_logger()

class ContextManager:
    """Context manager component for the Memory Agent."""
    
    def __init__(self):
        """Initialize the context manager."""
        self.current_context: Dict = {}
        self.context_history: List[Dict] = []
        self.max_history = settings.CONTEXT_HISTORY_MAX_SIZE
        self.context_window = settings.CONTEXT_WINDOW_SIZE
        self._initialized = False
    
    async def initialize(self):
        """Initialize the context manager component."""
        if self._initialized:
            return
        
        logger.info("Initializing context manager")
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the context manager component."""
        logger.info("Shutting down context manager")
        self._initialized = False
    
    async def update_context(self, context_data: Dict):
        """Update the current context with new data."""
        if not self._initialized:
            raise RuntimeError("Context manager not initialized")
        
        # Create new context entry
        context_entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "data": context_data,
            "type": context_data.get("type", "general"),
            "importance": context_data.get("importance", 0.5)
        }
        
        # Update current context
        self.current_context = context_entry
        
        # Add to history
        self.context_history.append(context_entry)
        
        # Trim history if needed
        if len(self.context_history) > self.max_history:
            self.context_history = self.context_history[-self.max_history:]
        
        logger.debug(f"Updated context: {context_entry['id']}")
    
    async def get_current_context(self) -> Dict:
        """Get the current context."""
        if not self._initialized:
            raise RuntimeError("Context manager not initialized")
        
        return self.current_context
    
    async def get_context_window(self) -> List[Dict]:
        """Get the recent context history within the window size."""
        if not self._initialized:
            raise RuntimeError("Context manager not initialized")
        
        return self.context_history[-self.context_window:]
    
    async def search_context_history(self, query: Dict) -> List[Dict]:
        """Search context history based on criteria."""
        if not self._initialized:
            raise RuntimeError("Context manager not initialized")
        
        results = []
        
        for context in self.context_history:
            if self._matches_query(context, query):
                results.append(context)
        
        return results
    
    def _matches_query(self, context: Dict, query: Dict) -> bool:
        """Check if a context entry matches the query criteria."""
        # Check type
        if "type" in query and context["type"] != query["type"]:
            return False
        
        # Check time range
        if "start_time" in query:
            context_time = datetime.fromisoformat(context["timestamp"])
            start_time = datetime.fromisoformat(query["start_time"])
            if context_time < start_time:
                return False
        
        if "end_time" in query:
            context_time = datetime.fromisoformat(context["timestamp"])
            end_time = datetime.fromisoformat(query["end_time"])
            if context_time > end_time:
                return False
        
        # Check data fields
        if "data_fields" in query:
            for field, value in query["data_fields"].items():
                if field not in context["data"] or context["data"][field] != value:
                    return False
        
        return True
    
    async def get_context_stats(self) -> Dict:
        """Get context manager statistics."""
        if not self._initialized:
            raise RuntimeError("Context manager not initialized")
        
        return {
            "current_context_id": self.current_context.get("id"),
            "history_size": len(self.context_history),
            "max_history": self.max_history,
            "context_window": self.context_window,
            "oldest_context": min(c["timestamp"] for c in self.context_history) if self.context_history else None,
            "newest_context": max(c["timestamp"] for c in self.context_history) if self.context_history else None
        }
    
    async def clear_context(self):
        """Clear all context history."""
        if not self._initialized:
            raise RuntimeError("Context manager not initialized")
        
        self.current_context = {}
        self.context_history.clear()
        logger.info("Cleared all context history") 