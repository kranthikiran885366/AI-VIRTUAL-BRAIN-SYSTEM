from typing import Optional, List
import os

try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        class BaseSettings:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

class EmotionAgentSettings:
    """Settings for the Emotion Agent — loaded from env with safe defaults."""

    EMOTION_HISTORY_MAX_SIZE: int = int(os.environ.get("EMOTION_HISTORY_MAX_SIZE", 1000))
    EMOTION_DECAY_RATE: float = float(os.environ.get("EMOTION_DECAY_RATE", 0.1))
    EMOTION_MIN_INTENSITY: float = float(os.environ.get("EMOTION_MIN_INTENSITY", 0.1))
    EMOTION_ANALYSIS_HISTORY_SIZE: int = int(os.environ.get("EMOTION_ANALYSIS_HISTORY_SIZE", 100))
    EMOTION_PATTERN_CONFIDENCE_THRESHOLD: float = float(os.environ.get("EMOTION_PATTERN_CONFIDENCE_THRESHOLD", 0.7))
    EMOTION_IMPACT_THRESHOLD: float = float(os.environ.get("EMOTION_IMPACT_THRESHOLD", 0.8))
    EMOTION_STORE_PATH: str = os.environ.get("EMOTION_STORE_PATH", "data/emotion_store")
    API_HOST: str = os.environ.get("EMOTION_AGENT_HOST", "localhost")
    API_PORT: int = int(os.environ.get("EMOTION_AGENT_PORT", 8003))
    API_DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    ORCHESTRATOR_URL: str = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8001")
    MEMORY_AGENT_URL: str = os.environ.get("MEMORY_AGENT_URL", "http://localhost:8001")
    TASK_AGENT_URL: str = os.environ.get("TASK_AGENT_URL", "http://localhost:8001")
    EMOTION_AUTOMATION_HISTORY_SIZE: int = int(os.environ.get("EMOTION_AUTOMATION_HISTORY_SIZE", 500))
    EMOTION_AUTOMATION_RULES_PATH: str = os.environ.get("EMOTION_AUTOMATION_RULES_PATH", "data/emotion_store/automation_rules.json")

    def __init__(self):
        os.makedirs(self.EMOTION_STORE_PATH, exist_ok=True)

# Singleton
settings = EmotionAgentSettings() 