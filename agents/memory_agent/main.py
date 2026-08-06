"""Memory agent package entry — orchestrator loads MemoryAgent from here."""

from .agent import MemoryAgent

try:
    from pydantic import BaseModel
    from typing import Optional, Dict, Any, List

    class MemoryData(BaseModel):
        """Legacy Pydantic model — kept for backward-compatible imports."""
        type: str = "short_term"
        content: str = ""
        importance: float = 0.5
        emotions: Dict[str, float] = {}
        connections: List[str] = []
        tags: List[str] = []
        metadata: Dict[str, Any] = {}

    class MemoryQuery(BaseModel):
        """Legacy Pydantic model — kept for backward-compatible imports."""
        type: Optional[str] = None
        content: Optional[str] = None
        tags: Optional[List[str]] = None
        min_importance: Optional[float] = None
        limit: int = 10

except ImportError:
    MemoryData = dict  # type: ignore
    MemoryQuery = dict  # type: ignore

from .agent import MemoryAgent

__all__ = ["MemoryAgent", "MemoryData", "MemoryQuery"]
