"""Language Intelligence Engine — Phase 9 package."""
from .models import LanguageSession, LanguageQuality, SemanticResult, LanguageMetrics
from .understanding import LanguageUnderstanding
from .semantic import SemanticAnalyzer
from .quality import QualityEngine
from .conversation import ConversationManager
from .document import DocumentProcessor
from .improvement import ImprovementPipeline
from .engine import LanguageEngine

# Import the proper BaseAgent-derived LanguageAgent (has initialize/shutdown/execute_task)
# so that AgentManager can call await agent.initialize() successfully.
# The LanguageEngine itself only has start()/stop() — not the BaseAgent contract.
try:
    # When imported as agents.language_agent package, parent package exposes LanguageAgent
    from agents.language_agent import LanguageAgent as _LanguageAgent  # type: ignore
    LanguageAgent = _LanguageAgent
except ImportError:
    # Fallback: define a thin wrapper so the package always exports LanguageAgent
    import asyncio as _asyncio
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    class LanguageAgent:  # type: ignore[no-redef]
        """Minimal shim: wraps LanguageEngine with the BaseAgent lifecycle contract."""

        agent_id: str = "language_agent"
        agent_type: str = "language"

        def __init__(self, agent_id: str = "language_agent") -> None:
            self.agent_id = agent_id
            self.agent_type = "language"
            self.state: dict = {}
            self.engine = LanguageEngine()

        async def initialize(self) -> None:
            self.state["texts_processed"] = 0
            await self.engine.start()
            _logger.info("language_agent.initialized agent_id=%s", self.agent_id)

        async def shutdown(self) -> None:
            await self.engine.stop()
            _logger.info("language_agent.shutdown agent_id=%s", self.agent_id)

        async def health_check(self) -> dict:
            return {"status": "healthy", "agent_id": self.agent_id}

        async def execute_task(self, task: dict) -> dict:
            action = task.get("action", "analyze")
            data = task.get("input_data", {}) or {}
            text = data.get("content", data.get("text", ""))
            return await self.engine.analyze(text)

__all__ = [
    "LanguageSession", "LanguageQuality", "SemanticResult", "LanguageMetrics",
    "LanguageUnderstanding", "SemanticAnalyzer", "QualityEngine",
    "ConversationManager", "DocumentProcessor", "ImprovementPipeline",
    "LanguageEngine", "LanguageAgent",
]
