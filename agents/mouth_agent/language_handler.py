import logging
from typing import Dict, Any, Optional
import json
from pathlib import Path
import aiohttp
from googletrans import Translator

class LanguageHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.translator = Translator()
        self.supported_languages = {
            "en-US": "English (US)",
            "hi-IN": "Hindi",
            "es-ES": "Spanish",
            "fr-FR": "French",
            "de-DE": "German",
            "ja-JP": "Japanese",
            "zh-CN": "Chinese (Simplified)",
            "ru-RU": "Russian"
        }
        self.language_profiles = self._load_language_profiles()
        
    def _load_language_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Load language-specific profiles"""
        try:
            profiles = {}
            profiles_dir = Path("agents/mouth_agent/voice_profiles")
            
            for profile_file in profiles_dir.glob("*.json"):
                with open(profile_file, 'r') as f:
                    profile = json.load(f)
                    language = profile.get("language")
                    if language:
                        profiles[language] = profile
                        
            return profiles
        except Exception as e:
            self.logger.error(f"Error loading language profiles: {e}")
            return {}

    async def translate_text(self, text: str, target_language: str) -> str:
        """Translate text to target language"""
        try:
            # Detect source language
            detection = self.translator.detect(text)
            source_language = detection.lang
            
            # Translate if needed
            if source_language != target_language:
                translation = self.translator.translate(
                    text,
                    src=source_language,
                    dest=target_language
                )
                return translation.text
            return text
        except Exception as e:
            self.logger.error(f"Error translating text: {e}")
            return text

    def get_language_profile(self, language_code: str) -> Optional[Dict[str, Any]]:
        """Get language-specific profile"""
        return self.language_profiles.get(language_code)

    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages"""
        return self.supported_languages.copy()

    def is_language_supported(self, language_code: str) -> bool:
        """Check if language is supported"""
        return language_code in self.supported_languages

    def get_language_name(self, language_code: str) -> Optional[str]:
        """Get language name from code"""
        return self.supported_languages.get(language_code)

    def get_language_code(self, language_name: str) -> Optional[str]:
        """Get language code from name"""
        for code, name in self.supported_languages.items():
            if name.lower() == language_name.lower():
                return code
        return None

    async def detect_language(self, text: str) -> str:
        """Detect language of text"""
        try:
            detection = self.translator.detect(text)
            return detection.lang
        except Exception as e:
            self.logger.error(f"Error detecting language: {e}")
            return "en"

    def get_language_settings(self, language_code: str) -> Dict[str, Any]:
        """Get language-specific settings"""
        profile = self.get_language_profile(language_code)
        if profile:
            return {
                "language": language_code,
                "base_settings": profile.get("base_settings", {}),
                "speech_patterns": profile.get("speech_patterns", {})
            }
        return {
            "language": language_code,
            "base_settings": {},
            "speech_patterns": {}
        }

    async def validate_translation(self, original: str, translated: str, target_language: str) -> bool:
        """Validate translation quality"""
        try:
            # Translate back to original language
            back_translation = await self.translate_text(translated, "en")
            
            # Simple similarity check (can be enhanced with more sophisticated methods)
            original_words = set(original.lower().split())
            back_words = set(back_translation.lower().split())
            
            # Calculate similarity
            common_words = original_words.intersection(back_words)
            similarity = len(common_words) / max(len(original_words), len(back_words))
            
            return similarity > 0.7  # Threshold for acceptable translation
        except Exception as e:
            self.logger.error(f"Error validating translation: {e}")
            return False 