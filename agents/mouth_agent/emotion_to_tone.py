import logging
from typing import Dict, Any
import json
from pathlib import Path

class EmotionToTone:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.emotion_mappings = self._load_emotion_mappings()
        
    def _load_emotion_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Load emotion to voice configuration mappings"""
        default_mappings = {
            "happy": {
                "pitch": 1.2,
                "speed": 1.1,
                "volume": 1.0,
                "tone": "cheerful",
                "modulation": "high"
            },
            "sad": {
                "pitch": 0.9,
                "speed": 0.9,
                "volume": 0.8,
                "tone": "soft",
                "modulation": "low"
            },
            "angry": {
                "pitch": 1.1,
                "speed": 1.0,
                "volume": 1.2,
                "tone": "harsh",
                "modulation": "medium"
            },
            "fear": {
                "pitch": 1.3,
                "speed": 1.2,
                "volume": 1.1,
                "tone": "nervous",
                "modulation": "high"
            },
            "calm": {
                "pitch": 1.0,
                "speed": 0.9,
                "volume": 0.9,
                "tone": "gentle",
                "modulation": "low"
            },
            "neutral": {
                "pitch": 1.0,
                "speed": 1.0,
                "volume": 1.0,
                "tone": "neutral",
                "modulation": "medium"
            }
        }
        
        try:
            config_path = Path("config/emotion_mappings.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return json.load(f)
            return default_mappings
        except Exception as e:
            self.logger.error(f"Error loading emotion mappings: {e}")
            return default_mappings

    def get_voice_config(self, emotion: str) -> Dict[str, Any]:
        """Get voice configuration for a given emotion"""
        try:
            # Normalize emotion string
            emotion = emotion.lower().strip()
            
            # Get base configuration
            config = self.emotion_mappings.get(emotion, self.emotion_mappings["neutral"])
            
            # Create a copy to avoid modifying the original
            voice_config = config.copy()
            
            # Add additional parameters
            voice_config.update({
                "emotion": emotion,
                "timestamp": "current",  # This would be replaced with actual timestamp
                "confidence": 1.0  # This would be calculated based on emotion detection
            })
            
            return voice_config
        except Exception as e:
            self.logger.error(f"Error getting voice config: {e}")
            return self.emotion_mappings["neutral"]

    def get_emotion_intensity(self, emotion: str, intensity: float) -> Dict[str, Any]:
        """Adjust voice configuration based on emotion intensity"""
        try:
            base_config = self.get_voice_config(emotion)
            
            # Adjust parameters based on intensity
            intensity = max(0.0, min(1.0, intensity))  # Clamp between 0 and 1
            
            # Modify pitch based on intensity
            base_config["pitch"] *= (1 + (intensity - 0.5) * 0.4)
            
            # Modify speed based on intensity
            base_config["speed"] *= (1 + (intensity - 0.5) * 0.2)
            
            # Modify volume based on intensity
            base_config["volume"] *= (1 + (intensity - 0.5) * 0.3)
            
            return base_config
        except Exception as e:
            self.logger.error(f"Error calculating emotion intensity: {e}")
            return self.get_voice_config(emotion)

    def get_combined_emotions(self, emotions: Dict[str, float]) -> Dict[str, Any]:
        """Handle multiple emotions and combine their effects"""
        try:
            if not emotions:
                return self.get_voice_config("neutral")
            
            # Normalize emotion weights
            total_weight = sum(emotions.values())
            if total_weight == 0:
                return self.get_voice_config("neutral")
            
            normalized_emotions = {
                emotion: weight/total_weight 
                for emotion, weight in emotions.items()
            }
            
            # Start with neutral configuration
            combined_config = self.get_voice_config("neutral")
            
            # Blend configurations based on weights
            for emotion, weight in normalized_emotions.items():
                emotion_config = self.get_voice_config(emotion)
                for key in combined_config:
                    if isinstance(combined_config[key], (int, float)):
                        combined_config[key] = (
                            combined_config[key] * (1 - weight) +
                            emotion_config[key] * weight
                        )
            
            return combined_config
        except Exception as e:
            self.logger.error(f"Error combining emotions: {e}")
            return self.get_voice_config("neutral") 