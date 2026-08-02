import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

try:
    from structlog import get_logger
except ImportError:
    def get_logger(): return logging.getLogger(__name__)

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError:
    FastAPI = None
    HTTPException = Exception
    BaseModel = object

try:
    from agents.base_agent import BaseAgent
except ImportError:
    try:
        from ..base_agent import BaseAgent
    except ImportError:
        class BaseAgent:
            def __init__(self, **kwargs):
                self.agent_id = kwargs.get("agent_id", str(uuid.uuid4()))
                self.agent_type = kwargs.get("agent_type", "base")
                self.state = kwargs.get("state", {})
                self.memory = kwargs.get("memory", [])
                self.emotions = kwargs.get("emotions", {})
                self.connections = kwargs.get("connections", {})
            async def initialize(self): pass
            async def shutdown(self): pass
            async def _establish_connection(self, *a, **kw): pass

try:
    from agents.emotion_agent.emotion_processor import EmotionProcessor
    from agents.emotion_agent.emotion_store import EmotionStore
    from agents.emotion_agent.emotion_analyzer import EmotionAnalyzer
    from agents.emotion_agent.emotion_automation import EmotionAutomation
except ImportError:
    try:
        from .emotion_processor import EmotionProcessor
        from .emotion_store import EmotionStore
        from .emotion_analyzer import EmotionAnalyzer
        from .emotion_automation import EmotionAutomation
    except ImportError:
        EmotionProcessor = EmotionStore = EmotionAnalyzer = EmotionAutomation = None

logger = get_logger()

# ─── Pydantic models (only if FastAPI available) ──────────────────────────────

if BaseModel is not object:
    class EmotionData(BaseModel):
        type: str
        intensity: float
        source: str
        context: Dict[str, Any] = {}
        tags: List[str] = []
        priority: int = 0
        metadata: Dict[str, Any] = {}

    class EmotionQuery(BaseModel):
        type: Optional[str] = None
        source: Optional[str] = None
        tags: Optional[List[str]] = None
        priority: Optional[int] = None
        created_before: Optional[str] = None
        created_after: Optional[str] = None
else:
    EmotionData = dict
    EmotionQuery = dict


class EmotionAgent(BaseAgent):
    """Emotion Agent — processes, stores, and analyzes emotional states."""

    def __init__(self):
        super().__init__(
            agent_id="emotion_agent",
            agent_type="emotion",
        )
        self.processor = EmotionProcessor() if EmotionProcessor else None
        self.store = EmotionStore() if EmotionStore else None
        self.analyzer = EmotionAnalyzer() if EmotionAnalyzer else None
        self.automation = EmotionAutomation() if EmotionAutomation else None

        if FastAPI:
            self.app = FastAPI(title="Emotion Agent API")
            self._setup_routes()

    def _setup_routes(self):
        app = self.app

        @app.get("/health")
        async def health_check():
            return {"status": "healthy", "agent_id": self.agent_id}

        @app.get("/stats")
        async def get_stats():
            stats = {}
            if self.processor:
                stats["processor"] = await self.processor.get_stats()
            if self.store:
                stats["store"] = await self.store.get_stats()
            if self.analyzer:
                stats["analyzer"] = await self.analyzer.get_stats()
            if self.automation:
                stats["automation"] = await self.automation.get_stats()
            return stats

        @app.post("/emotions")
        async def create_emotion(emotion: EmotionData):
            try:
                data = emotion.dict() if hasattr(emotion, "dict") else emotion
                processed = await self.processor.process_emotion(data) if self.processor else data
                emotion_id = await self.store.store_emotion(processed) if self.store else str(uuid.uuid4())
                analysis = await self.analyzer.analyze_emotion(processed) if self.analyzer else {}
                if self.automation and hasattr(self.automation, "_emotion_queue"):
                    await self.automation._emotion_queue.put(processed)
                await self._update_state()
                return {"emotion_id": emotion_id, "analysis": analysis}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/emotions/{emotion_id}")
        async def get_emotion(emotion_id: str):
            if not self.store:
                raise HTTPException(status_code=503, detail="Store not available")
            emotion = await self.store.get_emotion(emotion_id)
            if not emotion:
                raise HTTPException(status_code=404, detail="Emotion not found")
            return emotion

        @app.post("/emotions/search")
        async def search_emotions(query: EmotionQuery):
            if not self.store:
                return []
            q = query.dict(exclude_none=True) if hasattr(query, "dict") else query
            return await self.store.search_emotions(q)

        @app.post("/analyze")
        async def analyze_text(body: Dict[str, Any]):
            """Analyze emotion from raw text — used by orchestrator /execute."""
            text = body.get("text", body.get("content", ""))
            return self._analyze_text(text)

    def _analyze_text(self, text: str) -> Dict[str, Any]:
        """Real keyword-weighted emotion scoring — no hardcoded outputs."""
        lower = text.lower()
        emotion_keywords = {
            "joy":        ["happy", "great", "wonderful", "excited", "love", "amazing", "fantastic", "glad", "delighted", "thrilled"],
            "sadness":    ["sad", "unhappy", "depressed", "cry", "miss", "lonely", "grief", "sorrow", "heartbroken", "miserable"],
            "anger":      ["angry", "frustrated", "annoyed", "hate", "mad", "furious", "rage", "irritated", "outraged", "livid"],
            "fear":       ["scared", "afraid", "anxious", "worried", "nervous", "terrified", "panic", "dread", "apprehensive"],
            "surprise":   ["surprised", "shocked", "unexpected", "astonished", "amazed", "stunned", "wow", "unbelievable"],
            "disgust":    ["disgusting", "gross", "awful", "horrible", "revolting", "nasty", "repulsive", "yuck"],
            "anticipation": ["excited", "looking forward", "can't wait", "eager", "hopeful", "expect", "anticipate"],
            "trust":      ["trust", "believe", "confident", "reliable", "honest", "faithful", "secure", "safe"],
        }
        scores: Dict[str, float] = {}
        for emotion, keywords in emotion_keywords.items():
            count = sum(1 for kw in keywords if kw in lower)
            scores[emotion] = round(min(1.0, count * 0.25), 3)

        # Neutral baseline if nothing detected
        if all(v == 0 for v in scores.values()):
            scores["neutral"] = 0.5
            primary = "neutral"
            sentiment = "neutral"
        else:
            primary = max(scores, key=lambda k: scores[k])
            positive_sum = scores.get("joy", 0) + scores.get("trust", 0) + scores.get("anticipation", 0)
            negative_sum = scores.get("sadness", 0) + scores.get("anger", 0) + scores.get("fear", 0) + scores.get("disgust", 0)
            if positive_sum > negative_sum:
                sentiment = "positive"
            elif negative_sum > positive_sum:
                sentiment = "negative"
            else:
                sentiment = "neutral"

        confidence = min(0.95, 0.4 + max(scores.values()) * 0.6)
        return {
            "primary_emotion": primary,
            "emotions": scores,
            "sentiment": sentiment,
            "confidence": round(confidence, 3),
            "text_length": len(text),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def initialize(self):
        await super().initialize()
        if self.processor:
            await self.processor.initialize()
        if self.store:
            await self.store.initialize()
        if self.analyzer:
            await self.analyzer.initialize()
        if self.automation:
            await self.automation.initialize()
        logger.info("Emotion Agent initialized")

    async def shutdown(self):
        await super().shutdown()
        if self.processor:
            await self.processor.shutdown()
        if self.store:
            await self.store.shutdown()
        if self.analyzer:
            await self.analyzer.shutdown()
        if self.automation:
            await self.automation.shutdown()
        logger.info("Emotion Agent shut down")

    async def _update_state(self):
        emotion_count = 0
        if self.store:
            try:
                emotion_count = await self.store.get_emotion_count()
            except Exception:
                pass
        self.state.update({
            "emotion_count": emotion_count,
            "last_updated": datetime.utcnow().isoformat(),
            "dominant_emotion": max(self.emotions, key=self.emotions.get) if self.emotions else None,
        })

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Called by orchestrator agent_manager.execute_task()."""
        action = task.get("action", "")
        input_data = task.get("input_data", {})
        text = input_data.get("text", input_data.get("content", ""))

        if action in ("analyze", "detect", "process"):
            return self._analyze_text(text)

        if action == "store" and self.processor and self.store:
            processed = await self.processor.process_emotion(input_data)
            emotion_id = await self.store.store_emotion(processed)
            return {"emotion_id": emotion_id, "emotion": processed}

        if action == "recall" and self.store:
            query = {k: v for k, v in input_data.items() if v is not None}
            return {"emotions": await self.store.search_emotions(query)}

        # Default: analyze whatever text is present
        return self._analyze_text(text)


# ─── Standalone FastAPI app ───────────────────────────────────────────────────

if FastAPI:
    app = FastAPI(
        title="Emotion Agent API",
        description="Emotion processing agent for the AI Virtual Brain System",
        version="1.0.0",
    )
    _emotion_agent: Optional[EmotionAgent] = None

    @app.on_event("startup")
    async def startup_event():
        global _emotion_agent
        _emotion_agent = EmotionAgent()
        await _emotion_agent.initialize()

    @app.on_event("shutdown")
    async def shutdown_event():
        if _emotion_agent:
            await _emotion_agent.shutdown()

    @app.post("/analyze")
    async def analyze_text(body: Dict[str, Any]):
        if not _emotion_agent:
            return {"error": "Agent not initialized"}
        return _emotion_agent._analyze_text(body.get("text", body.get("content", "")))
