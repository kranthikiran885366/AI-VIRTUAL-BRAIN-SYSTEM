"""Learning agent package."""
from .main import LearningAgent  # noqa: F401

# Re-export data models from the top-level agents/learning_agent.py module
# These are used by test suites that do `from agents.learning_agent import ...`
try:
    from agents.learning_agent import (  # type: ignore[attr-defined]
        LearningContext,
        LearningSessionStatus,
        ExperienceClassification,
        ExperienceRecord,
    )
except (ImportError, AttributeError):
    # Fallback: define stubs so the package is still importable
    LearningContext = None  # type: ignore[assignment,misc]
    LearningSessionStatus = None  # type: ignore[assignment,misc]
    ExperienceClassification = None  # type: ignore[assignment,misc]
    ExperienceRecord = None  # type: ignore[assignment,misc]
