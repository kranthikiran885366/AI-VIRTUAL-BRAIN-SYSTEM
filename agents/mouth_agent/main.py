import asyncio
import json
from typing import Dict, Any, Optional
from pathlib import Path
import logging
from datetime import datetime
import yaml

# Import internal components
from .speech_generator import SpeechGenerator
from .emotion_to_tone import EmotionToTone
from .tts_engine import TTSEngine
from .voice_controller import VoiceController
from .mouth_api import MouthAPI
from .agent_integration import AgentIntegration
from .language_handler import LanguageHandler

class MouthAgent:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()
        
        # Initialize components
        self.speech_generator = SpeechGenerator()
        self.emotion_to_tone = EmotionToTone()
        self.tts_engine = TTSEngine(self.config)
        self.voice_controller = VoiceController()
        self.agent_integration = AgentIntegration()
        self.language_handler = LanguageHandler()
        self.api = MouthAPI(self)
        
        # State variables
        self.is_speaking = False
        self.current_emotion = "neutral"
        self.current_voice_profile = self.config.get("default_voice_profile", "english_male")
        self.current_language = "en-US"
        self.feedback_mode = False
        
        self.logger.info("Mouth Agent initialized successfully")

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            config_path = Path("config/mouth_agent_config.yaml")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}

    async def initialize(self):
        """Initialize all components"""
        try:
            await self.tts_engine.initialize()
            await self.agent_integration.initialize()
            self.logger.info("Mouth Agent initialized")
        except Exception as e:
            self.logger.error(f"Error initializing Mouth Agent: {e}")
            raise

    async def speak(self, text: str, emotion: Optional[str] = None, language: Optional[str] = None) -> None:
        """Generate and speak text with optional emotion and language"""
        try:
            self.is_speaking = True
            
            # Get emotional context if not provided
            if not emotion:
                emotion_context = await self.agent_integration.get_emotion_context()
                emotion = emotion_context.get("emotion", "neutral")
            
            # Get personality traits for speech style
            personality = await self.agent_integration.get_personality_traits()
            
            # Handle language translation if needed
            if language and language != self.current_language:
                if self.language_handler.is_language_supported(language):
                    text = await self.language_handler.translate_text(text, language)
                    self.current_language = language
                else:
                    self.logger.warning(f"Language {language} not supported, using current language")
            
            # Generate speech with context
            generated_text = await self.speech_generator.generate(text)
            
            # Get voice configuration based on emotion
            voice_config = self.emotion_to_tone.get_voice_config(emotion)
            
            # Apply personality traits to voice configuration
            voice_config = self._apply_personality_to_voice(voice_config, personality)
            
            # Apply language-specific settings
            language_settings = self.language_handler.get_language_settings(self.current_language)
            voice_config.update(language_settings.get("base_settings", {}))
            
            # Speak the text
            await self.tts_engine.speak(generated_text, voice_config)
            
            # Notify brain of speech event
            await self.agent_integration.notify_brain("speech", {
                "text": generated_text,
                "emotion": emotion,
                "voice_config": voice_config,
                "language": self.current_language
            })
            
            self.current_emotion = emotion
            self.is_speaking = False
            
        except Exception as e:
            self.logger.error(f"Error in speak method: {e}")
            self.is_speaking = False
            raise

    async def respond(self, context: Dict[str, Any]) -> None:
        """Generate and speak a response based on context"""
        try:
            # Get memory context for better response
            memory_context = await self.agent_integration.get_memory_context(
                context.get("query", "")
            )
            
            # Get conversation history
            history = await self.agent_integration.get_conversation_history()
            
            # Merge contexts
            full_context = {
                **context,
                "memory": memory_context,
                "history": history,
                "language": self.current_language
            }
            
            # Generate response
            response = await self.speech_generator.generate_response(full_context)
            
            # Speak the response
            await self.speak(
                response,
                context.get("emotion"),
                context.get("language")
            )
            
        except Exception as e:
            self.logger.error(f"Error in respond method: {e}")
            raise

    async def say_thought(self, thought: Dict[str, Any]) -> None:
        """Convert and speak a thought"""
        try:
            # Get emotional context
            emotion_context = await self.agent_integration.get_emotion_context()
            
            # Get personality traits
            personality = await self.agent_integration.get_personality_traits()
            
            # Convert thought to speech
            speech = await self.speech_generator.thought_to_speech(thought)
            
            # Speak with appropriate emotion and personality
            await self.speak(
                speech,
                emotion_context.get("emotion"),
                thought.get("language")
            )
            
        except Exception as e:
            self.logger.error(f"Error in say_thought method: {e}")
            raise

    def adjust_voice(self, settings: Dict[str, Any]) -> None:
        """Adjust voice settings"""
        try:
            self.voice_controller.apply_settings(settings)
        except Exception as e:
            self.logger.error(f"Error adjusting voice: {e}")
            raise

    def _apply_personality_to_voice(self, voice_config: Dict[str, Any], personality: Dict[str, Any]) -> Dict[str, Any]:
        """Apply personality traits to voice configuration"""
        try:
            traits = personality.get("traits", {})
            
            # Adjust pitch based on confidence
            if "confidence" in traits:
                voice_config["pitch"] *= (1 + (traits["confidence"] - 0.5) * 0.2)
            
            # Adjust speed based on energy
            if "energy" in traits:
                voice_config["speed"] *= (1 + (traits["energy"] - 0.5) * 0.2)
            
            # Adjust volume based on assertiveness
            if "assertiveness" in traits:
                voice_config["volume"] *= (1 + (traits["assertiveness"] - 0.5) * 0.2)
            
            return voice_config
        except Exception as e:
            self.logger.error(f"Error applying personality to voice: {e}")
            return voice_config

    async def set_language(self, language_code: str) -> bool:
        """Set the current language"""
        try:
            if self.language_handler.is_language_supported(language_code):
                self.current_language = language_code
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error setting language: {e}")
            return False

    async def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages"""
        return self.language_handler.get_supported_languages()

    async def enable_feedback_mode(self, enable: bool = True) -> None:
        """Enable or disable feedback mode for speech adaptation"""
        self.feedback_mode = enable

    async def cleanup(self):
        """Clean up resources"""
        try:
            await self.tts_engine.cleanup()
            await self.agent_integration.cleanup()
        except Exception as e:
            self.logger.error(f"Error cleaning up Mouth Agent: {e}")
            raise

    async def start(self):
        """Start the Mouth Agent"""
        try:
            await self.api.start()
            self.logger.info("Mouth Agent started successfully")
        except Exception as e:
            self.logger.error(f"Error starting Mouth Agent: {e}")

    async def stop(self):
        """Stop the Mouth Agent"""
        try:
            await self.api.stop()
            self.logger.info("Mouth Agent stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping Mouth Agent: {e}")

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run the agent
    async def main():
        agent = MouthAgent()
        await agent.initialize()
        
        try:
            # Example usage
            await agent.speak("Hello! I am the Mouth Agent.", "happy")
            await asyncio.sleep(2)
            await agent.speak("I can speak in multiple languages.", "calm")
            await asyncio.sleep(2)
            await agent.speak("नमस्ते! मैं हिंदी में बोल सकती हूं।", "happy", "hi-IN")
        finally:
            await agent.cleanup()
    
    asyncio.run(main()) 