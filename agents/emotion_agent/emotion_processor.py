import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid

from structlog import get_logger

from ...config import settings

logger = get_logger()

class EmotionProcessor:
    """Emotion processor component for the Emotion Agent."""
    
    def __init__(self):
        """Initialize the emotion processor."""
        self.current_emotions: Dict[str, Dict] = {}
        self.emotion_history: List[Dict] = []
        self.max_history = settings.EMOTION_HISTORY_MAX_SIZE
        self.decay_rate = settings.EMOTION_DECAY_RATE
        self._initialized = False
    
    async def initialize(self):
        """Initialize the emotion processor component."""
        if self._initialized:
            return
        
        logger.info("Initializing emotion processor")
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the emotion processor component."""
        logger.info("Shutting down emotion processor")
        self._initialized = False
    
    async def process_emotion(self, emotion_data: Dict) -> Dict:
        """Process a new emotion."""
        if not self._initialized:
            raise RuntimeError("Emotion processor not initialized")
        
        # Create emotion entry
        emotion = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "type": emotion_data["type"],
            "intensity": emotion_data["intensity"],
            "source": emotion_data["source"],
            "context": emotion_data.get("context", {}),
            "duration": emotion_data.get("duration"),
            "decay_start": datetime.utcnow().isoformat()
        }
        
        # Update current emotions
        self.current_emotions[emotion["type"]] = emotion
        
        # Add to history
        self.emotion_history.append(emotion)
        
        # Trim history if needed
        if len(self.emotion_history) > self.max_history:
            self.emotion_history = self.emotion_history[-self.max_history:]
        
        # Start decay process
        asyncio.create_task(self._decay_emotion(emotion))
        
        logger.debug(f"Processed emotion: {emotion['id']}")
        return emotion
    
    async def _decay_emotion(self, emotion: Dict):
        """Decay emotion intensity over time."""
        if emotion.get("duration"):
            await asyncio.sleep(emotion["duration"])
        else:
            while True:
                await asyncio.sleep(1)  # Check every second
                
                # Calculate time elapsed since decay start
                decay_start = datetime.fromisoformat(emotion["decay_start"])
                elapsed = (datetime.utcnow() - decay_start).total_seconds()
                
                # Calculate new intensity
                new_intensity = emotion["intensity"] * (1 - self.decay_rate) ** elapsed
                
                # Update emotion
                emotion["intensity"] = new_intensity
                
                # Remove if intensity is too low
                if new_intensity < settings.EMOTION_MIN_INTENSITY:
                    if emotion["type"] in self.current_emotions:
                        del self.current_emotions[emotion["type"]]
                    break
    
    async def get_current_emotions(self) -> Dict[str, Dict]:
        """Get current emotional state."""
        if not self._initialized:
            raise RuntimeError("Emotion processor not initialized")
        
        return self.current_emotions
    
    async def get_emotion_history(self) -> List[Dict]:
        """Get emotion history."""
        if not self._initialized:
            raise RuntimeError("Emotion processor not initialized")
        
        return self.emotion_history
    
    async def search_emotions(self, query: Dict) -> List[Dict]:
        """Search emotions based on criteria."""
        if not self._initialized:
            raise RuntimeError("Emotion processor not initialized")
        
        results = []
        
        for emotion in self.emotion_history:
            if self._matches_query(emotion, query):
                results.append(emotion)
        
        return results
    
    def _matches_query(self, emotion: Dict, query: Dict) -> bool:
        """Check if an emotion matches the query criteria."""
        # Check type
        if "type" in query and emotion["type"] != query["type"]:
            return False
        
        # Check source
        if "source" in query and emotion["source"] != query["source"]:
            return False
        
        # Check intensity
        if "min_intensity" in query and emotion["intensity"] < query["min_intensity"]:
            return False
        
        # Check time range
        if "start_time" in query:
            emotion_time = datetime.fromisoformat(emotion["timestamp"])
            start_time = datetime.fromisoformat(query["start_time"])
            if emotion_time < start_time:
                return False
        
        if "end_time" in query:
            emotion_time = datetime.fromisoformat(emotion["timestamp"])
            end_time = datetime.fromisoformat(query["end_time"])
            if emotion_time > end_time:
                return False
        
        return True
    
    async def get_stats(self) -> Dict:
        """Get emotion processor statistics."""
        if not self._initialized:
            raise RuntimeError("Emotion processor not initialized")
        
        return {
            "current_emotions": len(self.current_emotions),
            "history_size": len(self.emotion_history),
            "max_history": self.max_history,
            "decay_rate": self.decay_rate,
            "oldest_emotion": min(e["timestamp"] for e in self.emotion_history) if self.emotion_history else None,
            "newest_emotion": max(e["timestamp"] for e in self.emotion_history) if self.emotion_history else None
        }
    
    async def clear_emotions(self):
        """Clear all emotions."""
        if not self._initialized:
            raise RuntimeError("Emotion processor not initialized")
        
        self.current_emotions.clear()
        self.emotion_history.clear()
        logger.info("Cleared all emotions") 