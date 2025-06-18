import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid
import json
import os

from structlog import get_logger

from ...config import settings

logger = get_logger()

class EmotionStore:
    """Emotion store component for the Emotion Agent."""
    
    def __init__(self):
        """Initialize the emotion store."""
        self.emotions: Dict[str, Dict] = {}
        self.emotion_index: Dict[str, List[str]] = {}
        self.storage_path = settings.EMOTION_STORE_PATH
        self._initialized = False
    
    async def initialize(self):
        """Initialize the emotion store component."""
        if self._initialized:
            return
        
        logger.info("Initializing emotion store")
        
        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_path, exist_ok=True)
        
        # Load existing emotions
        await self._load_emotions()
        
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the emotion store component."""
        logger.info("Shutting down emotion store")
        
        # Save emotions before shutting down
        await self._save_emotions()
        
        self._initialized = False
    
    async def _load_emotions(self):
        """Load emotions from storage."""
        try:
            emotion_file = os.path.join(self.storage_path, "emotions.json")
            if os.path.exists(emotion_file):
                with open(emotion_file, "r") as f:
                    self.emotions = json.load(f)
            
            index_file = os.path.join(self.storage_path, "emotion_index.json")
            if os.path.exists(index_file):
                with open(index_file, "r") as f:
                    self.emotion_index = json.load(f)
            
            logger.info(f"Loaded {len(self.emotions)} emotions from storage")
        except Exception as e:
            logger.error(f"Error loading emotions: {str(e)}")
            self.emotions = {}
            self.emotion_index = {}
    
    async def _save_emotions(self):
        """Save emotions to storage."""
        try:
            # Save emotions
            emotion_file = os.path.join(self.storage_path, "emotions.json")
            with open(emotion_file, "w") as f:
                json.dump(self.emotions, f)
            
            # Save index
            index_file = os.path.join(self.storage_path, "emotion_index.json")
            with open(index_file, "w") as f:
                json.dump(self.emotion_index, f)
            
            logger.info(f"Saved {len(self.emotions)} emotions to storage")
        except Exception as e:
            logger.error(f"Error saving emotions: {str(e)}")
    
    async def store_emotion(self, emotion_data: Dict) -> str:
        """Store a new emotion."""
        if not self._initialized:
            raise RuntimeError("Emotion store not initialized")
        
        emotion_id = str(uuid.uuid4())
        
        emotion = {
            "id": emotion_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": emotion_data["type"],
            "intensity": emotion_data["intensity"],
            "source": emotion_data["source"],
            "context": emotion_data.get("context", {}),
            "duration": emotion_data.get("duration"),
            "decay_start": emotion_data.get("decay_start")
        }
        
        # Store emotion
        self.emotions[emotion_id] = emotion
        
        # Update index
        await self._update_index(emotion)
        
        # Save to storage
        await self._save_emotions()
        
        logger.debug(f"Stored emotion: {emotion_id}")
        return emotion_id
    
    async def _update_index(self, emotion: Dict):
        """Update the emotion index with a new emotion."""
        # Index by type
        if emotion["type"] not in self.emotion_index:
            self.emotion_index[emotion["type"]] = []
        self.emotion_index[emotion["type"]].append(emotion["id"])
        
        # Index by source
        if emotion["source"] not in self.emotion_index:
            self.emotion_index[emotion["source"]] = []
        self.emotion_index[emotion["source"]].append(emotion["id"])
    
    async def get_emotion(self, emotion_id: str) -> Optional[Dict]:
        """Get a specific emotion by ID."""
        if not self._initialized:
            raise RuntimeError("Emotion store not initialized")
        
        return self.emotions.get(emotion_id)
    
    async def search_emotions(self, query: Dict) -> List[Dict]:
        """Search emotions based on criteria."""
        if not self._initialized:
            raise RuntimeError("Emotion store not initialized")
        
        results = []
        
        # If type is specified, use index
        if "type" in query:
            emotion_ids = self.emotion_index.get(query["type"], [])
            emotions = [self.emotions[e_id] for e_id in emotion_ids if e_id in self.emotions]
        else:
            emotions = list(self.emotions.values())
        
        # Filter emotions
        for emotion in emotions:
            if self._matches_query(emotion, query):
                results.append(emotion)
        
        return results
    
    def _matches_query(self, emotion: Dict, query: Dict) -> bool:
        """Check if an emotion matches the query criteria."""
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
    
    async def update_emotion(self, emotion_id: str, updates: Dict) -> bool:
        """Update an existing emotion."""
        if not self._initialized:
            raise RuntimeError("Emotion store not initialized")
        
        if emotion_id not in self.emotions:
            return False
        
        emotion = self.emotions[emotion_id]
        
        # Update fields
        for key, value in updates.items():
            if key in emotion:
                emotion[key] = value
        
        # Update timestamp
        emotion["last_modified"] = datetime.utcnow().isoformat()
        
        # Update index if type or source changed
        if "type" in updates or "source" in updates:
            await self._update_index(emotion)
        
        # Save to storage
        await self._save_emotions()
        
        logger.debug(f"Updated emotion: {emotion_id}")
        return True
    
    async def delete_emotion(self, emotion_id: str) -> bool:
        """Delete an emotion."""
        if not self._initialized:
            raise RuntimeError("Emotion store not initialized")
        
        if emotion_id not in self.emotions:
            return False
        
        # Remove from emotions
        del self.emotions[emotion_id]
        
        # Remove from index
        for index_list in self.emotion_index.values():
            if emotion_id in index_list:
                index_list.remove(emotion_id)
        
        # Save to storage
        await self._save_emotions()
        
        logger.debug(f"Deleted emotion: {emotion_id}")
        return True
    
    async def get_emotion_count(self) -> int:
        """Get the number of emotions in storage."""
        if not self._initialized:
            raise RuntimeError("Emotion store not initialized")
        
        return len(self.emotions)
    
    async def get_stats(self) -> Dict:
        """Get emotion store statistics."""
        if not self._initialized:
            raise RuntimeError("Emotion store not initialized")
        
        return {
            "emotion_count": len(self.emotions),
            "index_size": len(self.emotion_index),
            "oldest_emotion": min(e["timestamp"] for e in self.emotions.values()) if self.emotions else None,
            "newest_emotion": max(e["timestamp"] for e in self.emotions.values()) if self.emotions else None,
            "storage_path": self.storage_path
        }
    
    async def clear_emotions(self):
        """Clear all emotions from storage."""
        if not self._initialized:
            raise RuntimeError("Emotion store not initialized")
        
        self.emotions.clear()
        self.emotion_index.clear()
        
        # Remove storage files
        try:
            emotion_file = os.path.join(self.storage_path, "emotions.json")
            if os.path.exists(emotion_file):
                os.remove(emotion_file)
            
            index_file = os.path.join(self.storage_path, "emotion_index.json")
            if os.path.exists(index_file):
                os.remove(index_file)
        except Exception as e:
            logger.error(f"Error removing storage files: {str(e)}")
        
        logger.info("Cleared all emotions from storage") 