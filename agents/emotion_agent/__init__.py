"""Emotion agent package — Phase 8 exports."""
from .emotion_engine import EmotionEngine, EmotionalState, EmotionSignal, EmotionSession, EmotionMetrics
from .motivation_engine import MotivationEngine, Goal, MotivationScore, MotivationMetrics
from .recommendation_engine import RecommendationEngine, Recommendation
from .emotion_context import EmotionContext

__all__ = [
    "EmotionEngine", "EmotionalState", "EmotionSignal", "EmotionSession", "EmotionMetrics",
    "MotivationEngine", "Goal", "MotivationScore", "MotivationMetrics",
    "RecommendationEngine", "Recommendation",
    "EmotionContext",
]
