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
    from agents.emotion_agent.emotion_engine import EmotionEngine, EmotionSignal
    from agents.emotion_agent.emotion_context import EmotionContext
    from agents.emotion_agent.recommendation_engine import RecommendationEngine
    from agents.emotion_agent.motivation_engine import MotivationEngine
except ImportError:
    try:
        from .emotion_processor import EmotionProcessor
        from .emotion_store import EmotionStore
        from .emotion_analyzer import EmotionAnalyzer
        from .emotion_automation import EmotionAutomation
        from .emotion_engine import EmotionEngine, EmotionSignal
        from .emotion_context import EmotionContext
        from .recommendation_engine import RecommendationEngine
        from .motivation_engine import MotivationEngine
    except ImportError:
        EmotionProcessor = EmotionStore = EmotionAnalyzer = EmotionAutomation = None
        EmotionEngine = EmotionSignal = EmotionContext = RecommendationEngine = None
        MotivationEngine = None

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
        # Phase 8: production engine + recommendation engine + motivation engine
        self.engine: Optional["EmotionEngine"] = EmotionEngine() if EmotionEngine else None
        self.rec_engine: Optional["RecommendationEngine"] = RecommendationEngine() if RecommendationEngine else None
        self.motivation_engine: Optional["MotivationEngine"] = MotivationEngine() if MotivationEngine else None
        # Broker event config (loaded lazily from engine config)
        self._broker_events_cfg: Dict[str, Any] = {}

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
        if self.engine:
            await self.engine.start()
            # Load broker event config from engine config
            self._broker_events_cfg = self.engine._cfg.get("broker_events", {})
        if self.motivation_engine:
            await self.motivation_engine.start()
        logger.info("Emotion Agent initialized")

    async def shutdown(self):
        if self.motivation_engine:
            await self.motivation_engine.stop()
        if self.engine:
            await self.engine.stop()
        if self.automation:
            await self.automation.shutdown()
        if self.analyzer:
            await self.analyzer.shutdown()
        if self.store:
            await self.store.shutdown()
        if self.processor:
            await self.processor.shutdown()
        await super().shutdown()
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
            result = self._analyze_text(text)
            return {"status": "analyzed", **result}

        if action == "store" and self.processor and self.store:
            processed = await self.processor.process_emotion(input_data)
            emotion_id = await self.store.store_emotion(processed)
            return {"status": "stored", "emotion_id": emotion_id, "emotion": processed}

        if action == "recall" and self.store:
            query = {k: v for k, v in input_data.items() if v is not None}
            emotions = await self.store.search_emotions(query)
            return {"status": "ok", "emotions": emotions, "count": len(emotions)}

        if action == "get_stats":
            stats = {}
            if self.processor:
                stats["processor"] = await self.processor.get_stats()
            if self.store:
                stats["store"] = await self.store.get_stats()
            if self.analyzer:
                stats["analyzer"] = await self.analyzer.get_stats()
            return {"status": "ok", "stats": stats}

        if action == "get_history" and self.processor:
            history = await self.processor.get_emotion_history()
            return {"status": "ok", "history": history, "count": len(history)}

        if action == "clear":
            if self.processor:
                await self.processor.clear_emotions()
            if self.store:
                await self.store.clear_emotions()
            if self.analyzer:
                await self.analyzer.clear_analysis()
            return {"status": "cleared"}

        if action == "get_current" and self.processor:
            current = await self.processor.get_current_emotions()
            return {"status": "ok", "emotions": current}

        # Phase 8: engine state
        if action == "get_state" and self.engine:
            return {"status": "ok", "state": self.engine.get_state(),
                    "dimensions": self.engine.get_dimensions()}

        if action == "get_engine_metrics" and self.engine:
            return {"status": "ok", "metrics": self.engine.get_metrics()}

        if action == "get_analytics" and self.engine:
            return {"status": "ok", "analytics": self.engine.get_analytics()}

        if action == "process_signal" and self.engine and EmotionSignal:
            sig_data = input_data.get("signal", input_data)
            validation = self.engine.validate_signal(sig_data)
            if not validation["valid"]:
                return {"status": "error", "errors": validation["errors"]}
            signal = EmotionSignal(
                source=sig_data.get("source", "unknown"),
                signal_type=sig_data.get("signal_type", "unknown"),
                intensity=float(sig_data.get("intensity", 0.5)),
                context=sig_data.get("context", {}),
                correlation_id=task.get("correlation_id"),
                trace_id=task.get("trace_id"),
            )
            result = await self.engine.process_signal(signal)
            return {"status": "ok", **result}

        if action == "get_recommendations" and self.engine and self.rec_engine:
            motivation_score = float(input_data.get("motivation_score", 0.6))
            recs = self.rec_engine.generate(
                emotional_state=self.engine.get_dimensions(),
                motivation_score=motivation_score,
                context=input_data.get("context", {}),
                correlation_id=task.get("correlation_id"),
                trace_id=task.get("trace_id"),
            )
            return {"status": "ok", "recommendations": [r.to_dict() for r in recs],
                    "count": len(recs)}

        if action == "begin_session" and self.engine:
            session = self.engine.begin_session(
                request_id=input_data.get("request_id"),
                correlation_id=input_data.get("correlation_id"),
                trace_id=input_data.get("trace_id"),
            )
            return {"status": "ok", "session": session.to_dict()}

        if action == "end_session" and self.engine:
            result = self.engine.end_session()
            return {"status": "ok", "session": result}

        if action == "get_audit_trail" and self.engine:
            limit = int(input_data.get("limit", 100))
            return {"status": "ok", "audit_trail": self.engine.get_audit_trail(limit)}

        if action == "get_confidence_influence" and self.engine:
            return {"status": "ok",
                    "confidence_influence": self.engine.get_confidence_influence()}

        # Default: analyze whatever text is present
        result = self._analyze_text(text)
        # Phase 8: also feed text analysis into engine as a signal
        if self.engine and EmotionSignal and result.get("primary_emotion") != "neutral":
            signal_type = result.get("signal_type", "user_feedback_positive")
            signal = EmotionSignal(
                source="conversation_text",
                signal_type=signal_type,
                intensity=float(result.get("confidence", 0.5)),
                context={"primary_emotion": result.get("primary_emotion"),
                         "sentiment": result.get("sentiment")},
                correlation_id=task.get("correlation_id"),
                trace_id=task.get("trace_id"),
            )
            try:
                sig_result = await self.engine.process_signal(signal)
                await self._emit_broker_emotion_update(
                    sig_result, task.get("correlation_id"), task.get("trace_id")
                )
            except Exception:
                pass
        return {"status": "analyzed", **result}

    # ─── Broker Integration ───────────────────────────────────────────────────

    async def _emit_broker_emotion_update(
        self,
        signal_result: Dict[str, Any],
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Emit EMOTION_UPDATE and STATE_UPDATE broker messages so other agents
        (Decision, Reasoning, Planning, Learning) can react to emotional context.
        Only emits via the existing broker — no direct agent-to-agent calls.
        """
        if not self._message_broker:
            return
        cfg = self._broker_events_cfg
        if not cfg.get("emit_emotion_updates", True):
            return

        try:
            from orchestrator.agent_communication import MessageType, MessagePriority

            state = signal_result.get("state", {})
            confidence_influence = signal_result.get("confidence_influence", 0.0)
            min_influence = float(cfg.get("min_influence_to_emit", 0.02))

            # Emit EMOTION_UPDATE to all subscribers
            await self._message_broker.send_message(
                sender_agent_id=self.agent_id,
                recipient_agent_id=None,  # broadcast
                message_type=MessageType.EMOTION_UPDATE,
                content={
                    "emotion_state": state,
                    "dimensions": self.engine.get_dimensions() if self.engine else {},
                    "transitions": signal_result.get("transitions", []),
                    "signal_id": signal_result.get("signal_id"),
                    "source": "emotion_engine",
                },
                priority=MessagePriority.NORMAL,
                correlation_id=correlation_id,
                trace_id=trace_id,
            )

            # Emit STATE_UPDATE with confidence influence if significant
            if cfg.get("emit_confidence_influence", True) and abs(confidence_influence) >= min_influence:
                await self._message_broker.send_message(
                    sender_agent_id=self.agent_id,
                    recipient_agent_id=None,  # broadcast
                    message_type=MessageType.STATE_UPDATE,
                    content={
                        "type": "confidence_influence",
                        "confidence_influence": confidence_influence,
                        "is_stressed": state.get("is_stressed", False),
                        "is_overloaded": state.get("is_overloaded", False),
                        "is_low_confidence": state.get("is_low_confidence", False),
                        "source": "emotion_engine",
                    },
                    priority=MessagePriority.NORMAL,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                )
        except Exception as exc:
            logger.debug("emotion_agent.broker_emit_failed error=%s", exc)


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
