import logging
import asyncio
from typing import Dict, Any, Optional
import json
from pathlib import Path
import aiohttp
import os
import tempfile
from elevenlabs import generate, set_api_key
import pyttsx3
import sounddevice as sd
import numpy as np

class TTSEngine:
    def __init__(self, engine_config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = engine_config
        self.current_engine = self.config.get("default_engine", "elevenlabs")
        self.api_keys = self._load_api_keys()
        self.session = None
        self.engine = None
        
    def _load_api_keys(self) -> Dict[str, str]:
        """Load API keys from environment or config file"""
        try:
            config_path = Path("config/api_keys.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading API keys: {e}")
            return {}

    async def initialize(self):
        """Initialize the TTS engine"""
        try:
            self.session = aiohttp.ClientSession()
            
            # Initialize appropriate engine
            if self.current_engine == "elevenlabs":
                api_key = self.api_keys.get("elevenlabs")
                if api_key:
                    set_api_key(api_key)
            elif self.current_engine == "pyttsx3":
                self.engine = pyttsx3.init()
                
            self.logger.info(f"TTS Engine initialized with {self.current_engine}")
        except Exception as e:
            self.logger.error(f"Error initializing TTS engine: {e}")

    async def speak(self, text: str, voice_config: Dict[str, Any]) -> None:
        """Convert text to speech and play it"""
        try:
            if not self.session:
                await self.initialize()
            
            # Select appropriate TTS engine based on configuration
            if self.current_engine == "elevenlabs":
                await self._speak_elevenlabs(text, voice_config)
            elif self.current_engine == "pyttsx3":
                await self._speak_pyttsx3(text, voice_config)
            else:
                self.logger.error(f"Unsupported TTS engine: {self.current_engine}")
                
        except Exception as e:
            self.logger.error(f"Error in speak method: {e}")

    async def _speak_elevenlabs(self, text: str, voice_config: Dict[str, Any]) -> None:
        """Use ElevenLabs API for speech synthesis"""
        try:
            api_key = self.api_keys.get("elevenlabs")
            if not api_key:
                raise ValueError("ElevenLabs API key not found")
            
            # Generate speech
            audio = generate(
                text=text,
                voice="Josh",  # Default voice, can be configured
                model="eleven_monolingual_v1"
            )
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio)
                temp_path = temp_file.name
            
            # Play audio
            await self._play_audio_file(temp_path)
            
            # Clean up
            os.unlink(temp_path)
            
        except Exception as e:
            self.logger.error(f"Error in ElevenLabs TTS: {e}")
            raise

    async def _speak_pyttsx3(self, text: str, voice_config: Dict[str, Any]) -> None:
        """Use pyttsx3 for speech synthesis"""
        try:
            if not self.engine:
                self.engine = pyttsx3.init()
            
            # Configure voice settings
            self.engine.setProperty('rate', int(200 * voice_config.get("speed", 1.0)))
            self.engine.setProperty('volume', voice_config.get("volume", 1.0))
            
            # Get available voices
            voices = self.engine.getProperty('voices')
            
            # Set voice based on gender
            if voice_config.get("gender") == "female":
                for voice in voices:
                    if "female" in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        break
            
            # Generate speech
            self.engine.say(text)
            self.engine.runAndWait()
            
        except Exception as e:
            self.logger.error(f"Error in pyttsx3 TTS: {e}")
            raise

    async def _play_audio_file(self, file_path: str) -> None:
        """Play audio from file"""
        try:
            # Use system command to play audio
            if os.name == 'nt':  # Windows
                os.system(f'start {file_path}')
            else:  # Unix-like
                os.system(f'play {file_path}')
                
            # Wait for audio to finish playing
            await asyncio.sleep(0.1)  # Adjust based on audio length
            
        except Exception as e:
            self.logger.error(f"Error playing audio file: {e}")
            raise

    async def change_engine(self, engine_name: str) -> None:
        """Change the TTS engine"""
        try:
            if engine_name in ["elevenlabs", "pyttsx3"]:
                self.current_engine = engine_name
                await self.initialize()
                self.logger.info(f"TTS engine changed to {engine_name}")
            else:
                raise ValueError(f"Unsupported TTS engine: {engine_name}")
        except Exception as e:
            self.logger.error(f"Error changing TTS engine: {e}")
            raise

    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.session:
                await self.session.close()
                self.session = None
                
            if self.engine:
                self.engine.stop()
                self.engine = None
                
        except Exception as e:
            self.logger.error(f"Error cleaning up TTS engine: {e}") 