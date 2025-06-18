import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid

from structlog import get_logger

from ...config import settings

logger = get_logger()

class EmotionAnalyzer:
    """Emotion analyzer component for the Emotion Agent."""
    
    def __init__(self):
        """Initialize the emotion analyzer."""
        self.analysis_history: List[Dict] = []
        self.max_history = settings.EMOTION_ANALYSIS_HISTORY_SIZE
        self.emotion_patterns: Dict[str, Dict] = {}
        self.emotion_impacts: Dict[str, float] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize the emotion analyzer component."""
        if self._initialized:
            return
        
        logger.info("Initializing emotion analyzer")
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the emotion analyzer component."""
        logger.info("Shutting down emotion analyzer")
        self._initialized = False
    
    async def analyze_emotion(self, emotion: Dict) -> Dict:
        """Analyze an emotion and its impact."""
        if not self._initialized:
            raise RuntimeError("Emotion analyzer not initialized")
        
        # Create analysis entry
        analysis = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "emotion_id": emotion["id"],
            "emotion_type": emotion["type"],
            "intensity": emotion["intensity"],
            "source": emotion["source"],
            "context": emotion.get("context", {}),
            "patterns": await self._detect_patterns(emotion),
            "impact": await self._calculate_impact(emotion),
            "recommendations": await self._generate_recommendations(emotion)
        }
        
        # Add to history
        self.analysis_history.append(analysis)
        
        # Trim history if needed
        if len(self.analysis_history) > self.max_history:
            self.analysis_history = self.analysis_history[-self.max_history:]
        
        # Update patterns and impacts
        await self._update_patterns(emotion)
        await self._update_impacts(emotion)
        
        logger.debug(f"Analyzed emotion: {emotion['id']}")
        return analysis
    
    async def _detect_patterns(self, emotion: Dict) -> List[Dict]:
        """Detect patterns in the emotion."""
        patterns = []
        
        # Check for recurring emotions
        recent_emotions = [
            e for e in self.analysis_history[-10:]
            if e["emotion_type"] == emotion["type"]
        ]
        
        if len(recent_emotions) >= 3:
            patterns.append({
                "type": "recurring",
                "emotion_type": emotion["type"],
                "count": len(recent_emotions),
                "frequency": "high"
            })
        
        # Check for emotion combinations
        if emotion["context"]:
            for pattern_type, pattern_data in self.emotion_patterns.items():
                if self._matches_pattern(emotion, pattern_data):
                    patterns.append({
                        "type": "combination",
                        "pattern_type": pattern_type,
                        "confidence": pattern_data["confidence"]
                    })
        
        return patterns
    
    def _matches_pattern(self, emotion: Dict, pattern: Dict) -> bool:
        """Check if an emotion matches a pattern."""
        # Check emotion type
        if pattern["emotion_type"] != emotion["type"]:
            return False
        
        # Check context
        for key, value in pattern["context"].items():
            if key not in emotion["context"] or emotion["context"][key] != value:
                return False
        
        return True
    
    async def _calculate_impact(self, emotion: Dict) -> Dict:
        """Calculate the impact of an emotion."""
        # Get base impact from emotion type
        base_impact = self.emotion_impacts.get(emotion["type"], 0.5)
        
        # Adjust for intensity
        impact = base_impact * emotion["intensity"]
        
        # Adjust for context
        if emotion["context"]:
            context_factors = self._get_context_factors(emotion["context"])
            impact *= context_factors
        
        return {
            "value": impact,
            "level": self._get_impact_level(impact),
            "factors": {
                "base_impact": base_impact,
                "intensity": emotion["intensity"],
                "context_factors": context_factors if emotion["context"] else 1.0
            }
        }
    
    def _get_context_factors(self, context: Dict) -> float:
        """Get impact factors from context."""
        factors = 1.0
        
        # Example context factors
        if "stress_level" in context:
            factors *= 1 + (context["stress_level"] * 0.2)
        
        if "social_context" in context:
            if context["social_context"] == "group":
                factors *= 1.2
            elif context["social_context"] == "public":
                factors *= 1.5
        
        return factors
    
    def _get_impact_level(self, impact: float) -> str:
        """Get impact level based on impact value."""
        if impact >= 0.8:
            return "high"
        elif impact >= 0.5:
            return "medium"
        else:
            return "low"
    
    async def _generate_recommendations(self, emotion: Dict) -> List[Dict]:
        """Generate recommendations based on emotion analysis."""
        recommendations = []
        
        # Check intensity
        if emotion["intensity"] > 0.8:
            recommendations.append({
                "type": "intensity",
                "action": "reduce",
                "suggestion": "Consider taking a break or practicing relaxation techniques"
            })
        
        # Check patterns
        patterns = await self._detect_patterns(emotion)
        for pattern in patterns:
            if pattern["type"] == "recurring" and pattern["frequency"] == "high":
                recommendations.append({
                    "type": "pattern",
                    "action": "address",
                    "suggestion": f"Address recurring {emotion['type']} emotions"
                })
        
        # Check impact
        impact = await self._calculate_impact(emotion)
        if impact["level"] == "high":
            recommendations.append({
                "type": "impact",
                "action": "mitigate",
                "suggestion": "Consider discussing with a support system"
            })
        
        return recommendations
    
    async def _update_patterns(self, emotion: Dict):
        """Update emotion patterns based on new emotion."""
        # Update pattern confidence
        for pattern_type, pattern_data in self.emotion_patterns.items():
            if self._matches_pattern(emotion, pattern_data):
                pattern_data["confidence"] = min(1.0, pattern_data["confidence"] + 0.1)
            else:
                pattern_data["confidence"] = max(0.0, pattern_data["confidence"] - 0.05)
        
        # Add new pattern if needed
        if emotion["context"]:
            pattern_key = f"{emotion['type']}_{hash(frozenset(emotion['context'].items()))}"
            if pattern_key not in self.emotion_patterns:
                self.emotion_patterns[pattern_key] = {
                    "emotion_type": emotion["type"],
                    "context": emotion["context"],
                    "confidence": 0.5
                }
    
    async def _update_impacts(self, emotion: Dict):
        """Update emotion impacts based on new emotion."""
        # Update impact value
        current_impact = self.emotion_impacts.get(emotion["type"], 0.5)
        new_impact = (current_impact + emotion["intensity"]) / 2
        self.emotion_impacts[emotion["type"]] = new_impact
    
    async def get_analysis(self) -> Dict:
        """Get current analysis state."""
        if not self._initialized:
            raise RuntimeError("Emotion analyzer not initialized")
        
        return {
            "patterns": self.emotion_patterns,
            "impacts": self.emotion_impacts,
            "history_size": len(self.analysis_history),
            "max_history": self.max_history,
            "oldest_analysis": min(a["timestamp"] for a in self.analysis_history) if self.analysis_history else None,
            "newest_analysis": max(a["timestamp"] for a in self.analysis_history) if self.analysis_history else None
        }
    
    async def get_stats(self) -> Dict:
        """Get emotion analyzer statistics."""
        if not self._initialized:
            raise RuntimeError("Emotion analyzer not initialized")
        
        return {
            "analysis_count": len(self.analysis_history),
            "pattern_count": len(self.emotion_patterns),
            "impact_count": len(self.emotion_impacts),
            "max_history": self.max_history,
            "oldest_analysis": min(a["timestamp"] for a in self.analysis_history) if self.analysis_history else None,
            "newest_analysis": max(a["timestamp"] for a in self.analysis_history) if self.analysis_history else None
        }
    
    async def clear_analysis(self):
        """Clear all analysis data."""
        if not self._initialized:
            raise RuntimeError("Emotion analyzer not initialized")
        
        self.analysis_history.clear()
        self.emotion_patterns.clear()
        self.emotion_impacts.clear()
        logger.info("Cleared all analysis data") 