"""Memory agent module exporting production MemoryAgent."""

import logging
from .agent import MemoryAgent

logger = logging.getLogger(__name__)

__all__ = ["MemoryAgent"]