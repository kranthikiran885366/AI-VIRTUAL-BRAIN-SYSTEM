import logging
from typing import Dict, Any, Optional
import json
from pathlib import Path

class VoiceController:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_settings = self._get_default_settings()
        self.voice_profiles = self._load_voice_profiles()
        
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default voice settings"""
        return {
            "pitch": 1.0,
            "speed": 1.0,
            "volume": 1.0,
            "tone": "neutral",
            "modulation": "medium",
            "language": "en-US",
            "gender": "neutral"
        }
        
    def _load_voice_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Load voice profiles from configuration"""
        default_profiles = {
            "english_male": {
                "pitch": 1.0,
                "speed": 1.0,
                "volume": 1.0,
                "tone": "neutral",
                "modulation": "medium",
                "language": "en-US",
                "gender": "male"
            },
            "english_female": {
                "pitch": 1.1,
                "speed": 1.0,
                "volume": 1.0,
                "tone": "neutral",
                "modulation": "medium",
                "language": "en-US",
                "gender": "female"
            },
            "hindi_female": {
                "pitch": 1.0,
                "speed": 1.0,
                "volume": 1.0,
                "tone": "neutral",
                "modulation": "medium",
                "language": "hi-IN",
                "gender": "female"
            }
        }
        
        try:
            config_path = Path("config/voice_profiles.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return json.load(f)
            return default_profiles
        except Exception as e:
            self.logger.error(f"Error loading voice profiles: {e}")
            return default_profiles

    def apply_settings(self, settings: Dict[str, Any]) -> None:
        """Apply voice settings"""
        try:
            # Validate settings
            self._validate_settings(settings)
            
            # Update current settings
            self.current_settings.update(settings)
            
            self.logger.info(f"Voice settings updated: {settings}")
        except Exception as e:
            self.logger.error(f"Error applying voice settings: {e}")
            raise

    def load_profile(self, profile_name: str) -> None:
        """Load a voice profile"""
        try:
            if profile_name not in self.voice_profiles:
                raise ValueError(f"Voice profile not found: {profile_name}")
            
            self.current_settings = self.voice_profiles[profile_name].copy()
            self.logger.info(f"Loaded voice profile: {profile_name}")
        except Exception as e:
            self.logger.error(f"Error loading voice profile: {e}")
            raise

    def get_current_settings(self) -> Dict[str, Any]:
        """Get current voice settings"""
        return self.current_settings.copy()

    def _validate_settings(self, settings: Dict[str, Any]) -> None:
        """Validate voice settings"""
        try:
            # Check required parameters
            required_params = ["pitch", "speed", "volume", "tone"]
            for param in required_params:
                if param not in settings:
                    raise ValueError(f"Missing required parameter: {param}")
            
            # Validate parameter ranges
            if not 0.5 <= settings["pitch"] <= 2.0:
                raise ValueError("Pitch must be between 0.5 and 2.0")
            
            if not 0.5 <= settings["speed"] <= 2.0:
                raise ValueError("Speed must be between 0.5 and 2.0")
            
            if not 0.0 <= settings["volume"] <= 1.0:
                raise ValueError("Volume must be between 0.0 and 1.0")
            
            # Validate tone
            valid_tones = ["neutral", "cheerful", "soft", "harsh", "nervous", "gentle"]
            if settings["tone"] not in valid_tones:
                raise ValueError(f"Invalid tone. Must be one of: {valid_tones}")
                
        except Exception as e:
            self.logger.error(f"Error validating settings: {e}")
            raise

    def create_profile(self, name: str, settings: Dict[str, Any]) -> None:
        """Create a new voice profile"""
        try:
            # Validate settings
            self._validate_settings(settings)
            
            # Add profile
            self.voice_profiles[name] = settings.copy()
            
            # Save to file
            self._save_profiles()
            
            self.logger.info(f"Created new voice profile: {name}")
        except Exception as e:
            self.logger.error(f"Error creating voice profile: {e}")
            raise

    def delete_profile(self, name: str) -> None:
        """Delete a voice profile"""
        try:
            if name not in self.voice_profiles:
                raise ValueError(f"Voice profile not found: {name}")
            
            del self.voice_profiles[name]
            
            # Save to file
            self._save_profiles()
            
            self.logger.info(f"Deleted voice profile: {name}")
        except Exception as e:
            self.logger.error(f"Error deleting voice profile: {e}")
            raise

    def _save_profiles(self) -> None:
        """Save voice profiles to file"""
        try:
            config_path = Path("config/voice_profiles.json")
            with open(config_path, 'w') as f:
                json.dump(self.voice_profiles, f, indent=4)
        except Exception as e:
            self.logger.error(f"Error saving voice profiles: {e}")
            raise 