"""Perception agent package."""

from .perception_agent import PerceptionAgent
from .perception_model import PerceptionModel
from .context_builder import ContextBuilder
from .config import PERCEPTION_CONFIG, FUSION_CONFIG, ANOMALY_CONFIG

# Backward-compatible aliases
AGENT_CONFIG = PERCEPTION_CONFIG
MODEL_CONFIG = FUSION_CONFIG
CONTEXT_CONFIG = ANOMALY_CONFIG

__all__ = [
    "PerceptionAgent",
    "PerceptionModel",
    "ContextBuilder",
    "AGENT_CONFIG",
    "MODEL_CONFIG",
    "CONTEXT_CONFIG",
    "PERCEPTION_CONFIG",
]