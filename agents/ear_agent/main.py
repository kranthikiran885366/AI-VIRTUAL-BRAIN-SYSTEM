import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import yaml
from pathlib import Path
import asyncio
import queue
import threading
import json
import time
from datetime import datetime

from .audio_listener import AudioListener
from .speech_recognizer import SpeechRecognizer
from .sound_classifier import SoundClassifier
from .speaker_id import SpeakerIdentifier
from .emotion_detector import EmotionDetector
from .language_detector import LanguageDetector
from .intent_detector import IntentDetector

class EarAgent:
    def __init__(self, config_path: str = "config/ear_agent_config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.audio_listener = None
        self.speech_recognizer = None
        self.sound_classifier = None
        self.speaker_identifier = None
        self.emotion_detector = None
        self.language_detector = None
        self.intent_detector = None
        
        # Initialize state
        self.is_running = False
        self.processing_thread = None
        self.last_activity = None
        self.conversation_history = []
        self.max_history_length = 100
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return yaml.safe_load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}
    
    async def initialize(self):
        """Initialize all components"""
        try:
            # Initialize audio listener
            self.audio_listener = AudioListener(self.config)
            
            # Initialize speech recognizer
            self.speech_recognizer = SpeechRecognizer(self.config)
            
            # Initialize sound classifier
            self.sound_classifier = SoundClassifier(self.config)
            
            # Initialize speaker identifier
            self.speaker_identifier = SpeakerIdentifier(self.config)
            
            # Initialize emotion detector
            self.emotion_detector = EmotionDetector(self.config)
            
            # Initialize language detector
            self.language_detector = LanguageDetector(self.config)
            
            # Initialize intent detector
            self.intent_detector = IntentDetector(self.config)
            
            self.logger.info("Initialized all components")
        
        except Exception as e:
            self.logger.error(f"Error initializing components: {e}")
            await self.cleanup()
            raise
    
    async def start(self):
        """Start the Ear Agent"""
        try:
            if self.is_running:
                self.logger.warning("Already running")
                return
            
            self.is_running = True
            
            # Start audio listener
            self.audio_listener.start_listening(self._audio_callback)
            
            # Start speech recognition
            self.speech_recognizer.start_processing(self._speech_callback)
            
            # Start sound classification
            self.sound_classifier.start_processing(self._sound_callback)
            
            # Start speaker identification
            self.speaker_identifier.start_processing(self._speaker_callback)
            
            # Start emotion detection
            self.emotion_detector.start_processing(self._emotion_callback)
            
            # Start language detection
            self.language_detector.start_processing(self._language_callback)
            
            # Start intent detection
            self.intent_detector.start_processing(self._intent_callback)
            
            self.logger.info("Started Ear Agent")
        
        except Exception as e:
            self.logger.error(f"Error starting Ear Agent: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """Stop the Ear Agent"""
        try:
            if not self.is_running:
                return
            
            self.is_running = False
            
            # Stop all components
            if self.audio_listener:
                self.audio_listener.stop_listening()
            
            if self.speech_recognizer:
                self.speech_recognizer.stop_processing()
            
            if self.sound_classifier:
                self.sound_classifier.stop_processing()
            
            if self.speaker_identifier:
                self.speaker_identifier.stop_processing()
            
            if self.emotion_detector:
                self.emotion_detector.stop_processing()
            
            if self.language_detector:
                self.language_detector.stop_processing()
            
            if self.intent_detector:
                self.intent_detector.stop_processing()
            
            self.logger.info("Stopped Ear Agent")
        
        except Exception as e:
            self.logger.error(f"Error stopping Ear Agent: {e}")
            raise
    
    def _audio_callback(self, audio_data: np.ndarray, timestamp: float):
        """Handle incoming audio data"""
        try:
            if not self.is_running:
                return
            
            # Update last activity
            self.last_activity = timestamp
            
            # Process audio data with all components
            self.speech_recognizer.add_audio_data(audio_data, timestamp)
            self.sound_classifier.add_audio_data(audio_data, timestamp)
            self.speaker_identifier.add_audio_data(audio_data, timestamp)
            self.emotion_detector.add_audio_data(audio_data, timestamp)
            self.language_detector.add_audio_data(audio_data, timestamp)
            self.intent_detector.add_audio_data(audio_data, timestamp)
        
        except Exception as e:
            self.logger.error(f"Error in audio callback: {e}")
    
    def _speech_callback(self, result: Dict[str, Any]):
        """Handle speech recognition results"""
        try:
            if not self.is_running:
                return
            
            # Add to conversation history
            self.conversation_history.append({
                "type": "speech",
                "text": result["text"],
                "confidence": result["confidence"],
                "timestamp": result["timestamp"]
            })
            
            # Trim history if needed
            if len(self.conversation_history) > self.max_history_length:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
            
            # Notify other components
            self.language_detector.add_audio_data(result["audio"], result["timestamp"])
            self.intent_detector.add_audio_data(result["audio"], result["timestamp"])
        
        except Exception as e:
            self.logger.error(f"Error in speech callback: {e}")
    
    def _sound_callback(self, result: Dict[str, Any]):
        """Handle sound classification results"""
        try:
            if not self.is_running:
                return
            
            # Add to conversation history
            self.conversation_history.append({
                "type": "sound",
                "sound": result["sound"],
                "confidence": result["confidence"],
                "timestamp": result["timestamp"]
            })
            
            # Trim history if needed
            if len(self.conversation_history) > self.max_history_length:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
        
        except Exception as e:
            self.logger.error(f"Error in sound callback: {e}")
    
    def _speaker_callback(self, result: Dict[str, Any]):
        """Handle speaker identification results"""
        try:
            if not self.is_running:
                return
            
            # Add to conversation history
            self.conversation_history.append({
                "type": "speaker",
                "speaker": result["speaker"],
                "confidence": result["confidence"],
                "timestamp": result["timestamp"]
            })
            
            # Trim history if needed
            if len(self.conversation_history) > self.max_history_length:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
        
        except Exception as e:
            self.logger.error(f"Error in speaker callback: {e}")
    
    def _emotion_callback(self, result: Dict[str, Any]):
        """Handle emotion detection results"""
        try:
            if not self.is_running:
                return
            
            # Add to conversation history
            self.conversation_history.append({
                "type": "emotion",
                "emotion": result["emotion"],
                "confidence": result["confidence"],
                "timestamp": result["timestamp"]
            })
            
            # Trim history if needed
            if len(self.conversation_history) > self.max_history_length:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
        
        except Exception as e:
            self.logger.error(f"Error in emotion callback: {e}")
    
    def _language_callback(self, result: Dict[str, Any]):
        """Handle language detection results"""
        try:
            if not self.is_running:
                return
            
            # Add to conversation history
            self.conversation_history.append({
                "type": "language",
                "language": result["language"],
                "confidence": result["confidence"],
                "timestamp": result["timestamp"]
            })
            
            # Trim history if needed
            if len(self.conversation_history) > self.max_history_length:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
        
        except Exception as e:
            self.logger.error(f"Error in language callback: {e}")
    
    def _intent_callback(self, result: Dict[str, Any]):
        """Handle intent detection results"""
        try:
            if not self.is_running:
                return
            
            # Add to conversation history
            self.conversation_history.append({
                "type": "intent",
                "intent": result["intent"],
                "confidence": result["confidence"],
                "entities": result.get("entities", []),
                "timestamp": result["timestamp"]
            })
            
            # Trim history if needed
            if len(self.conversation_history) > self.max_history_length:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
        
        except Exception as e:
            self.logger.error(f"Error in intent callback: {e}")
    
    def get_conversation_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get conversation history"""
        try:
            if limit is None:
                return self.conversation_history.copy()
            return self.conversation_history[-limit:]
        except Exception as e:
            self.logger.error(f"Error getting conversation history: {e}")
            return []
    
    def get_last_activity(self) -> Optional[float]:
        """Get timestamp of last activity"""
        return self.last_activity
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        try:
            return {
                "is_running": self.is_running,
                "last_activity": self.last_activity,
                "history_length": len(self.conversation_history),
                "components": {
                    "audio_listener": self.audio_listener is not None,
                    "speech_recognizer": self.speech_recognizer is not None,
                    "sound_classifier": self.sound_classifier is not None,
                    "speaker_identifier": self.speaker_identifier is not None,
                    "emotion_detector": self.emotion_detector is not None,
                    "language_detector": self.language_detector is not None,
                    "intent_detector": self.intent_detector is not None
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting agent status: {e}")
            return {}
    
    async def cleanup(self):
        """Clean up all resources"""
        try:
            await self.stop()
            
            # Clean up components
            if self.audio_listener:
                self.audio_listener.cleanup()
            
            if self.speech_recognizer:
                self.speech_recognizer.cleanup()
            
            if self.sound_classifier:
                self.sound_classifier.cleanup()
            
            if self.speaker_identifier:
                self.speaker_identifier.cleanup()
            
            if self.emotion_detector:
                self.emotion_detector.cleanup()
            
            if self.language_detector:
                self.language_detector.cleanup()
            
            if self.intent_detector:
                self.intent_detector.cleanup()
            
            self.logger.info("Cleaned up all resources")
        
        except Exception as e:
            self.logger.error(f"Error cleaning up: {e}")
            raise

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test Ear Agent
    async def test_agent():
        agent = EarAgent()
        try:
            # Initialize agent
            await agent.initialize()
            
            # Start agent
            await agent.start()
            
            # Run for 10 seconds
            print("Running Ear Agent for 10 seconds...")
            await asyncio.sleep(10)
            
            # Get status
            status = agent.get_agent_status()
            print("\nAgent Status:")
            print(json.dumps(status, indent=2))
            
            # Get conversation history
            history = agent.get_conversation_history()
            print("\nConversation History:")
            print(json.dumps(history, indent=2))
            
            # Stop agent
            await agent.stop()
        
        finally:
            await agent.cleanup()
    
    asyncio.run(test_agent()) 