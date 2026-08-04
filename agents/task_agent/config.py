from typing import Dict, List, Optional
import os

class TaskAgentSettings:
    """Settings for the Task Agent — loaded from env with safe defaults."""

    API_HOST: str = os.environ.get("TASK_AGENT_HOST", "0.0.0.0")
    API_PORT: int = int(os.environ.get("TASK_AGENT_PORT", 8004))
    API_PREFIX: str = "/api/v1/tasks"
    TASK_PROCESSING_INTERVAL: float = float(os.environ.get("TASK_PROCESSING_INTERVAL", 1.0))
    TASK_HISTORY_MAX_SIZE: int = int(os.environ.get("TASK_HISTORY_MAX_SIZE", 1000))
    TASK_ANALYSIS_HISTORY_SIZE: int = int(os.environ.get("TASK_ANALYSIS_HISTORY_SIZE", 1000))
    TASK_AUTOMATION_HISTORY_SIZE: int = int(os.environ.get("TASK_AUTOMATION_HISTORY_SIZE", 1000))
    TASK_STORE_PATH: str = os.environ.get("TASK_STORE_PATH", "data/tasks")
    TASK_AUTOMATION_RULES_PATH: str = os.environ.get("TASK_AUTOMATION_RULES_PATH", "data/tasks/automation_rules.json")
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    MEMORY_AGENT_URL: str = os.environ.get("MEMORY_AGENT_URL", "http://localhost:8001")
    EMOTION_AGENT_URL: str = os.environ.get("EMOTION_AGENT_URL", "http://localhost:8001")

    def __init__(self):
        os.makedirs(self.TASK_STORE_PATH, exist_ok=True)

# Singleton
settings = TaskAgentSettings() 