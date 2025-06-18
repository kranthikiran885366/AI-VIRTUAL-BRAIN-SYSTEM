import logging
import queue
import threading
import time
from typing import Optional, Callable, Dict, Any
import numpy as np
import sounddevice as sd
import webrtcvad
import rnnoise
from pathlib import Path
import yaml

class AudioListener:
    def __init__(self, config_path: str = "config/ear_agent_config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.audio_config = self.config.get("audio", {})
        
        # Initialize audio parameters
        self.sample_rate = self.audio_config.get("sample_rate", 16000)
        self.channels = self.audio_config.get("channels", 1)
        self.chunk_size = self.audio_config.get("chunk_size", 1024)
        self.format = self.audio_config.get("format", "int16")
        self.device_index = self.audio_config.get("device_index")
        self.timeout = self.audio_config.get("timeout", 5)
        self.silence_threshold = self.audio_config.get("silence_threshold", 0.01)
        self.silence_duration = self.audio_config.get("silence_duration", 1.0)
        
        # Initialize noise filtering
        self.noise_config = self.config.get("noise_filtering", {})
        self.noise_filtering_enabled = self.noise_config.get("enabled", True)
        self.noise_reduction_level = self.noise_config.get("noise_reduction_level", 0.7)
        
        # Initialize components
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self.current_stream = None
        self.vad = webrtcvad.Vad(3)  # Aggressive voice activity detection
        self.noise_filter = None
        
        if self.noise_filtering_enabled:
            self._initialize_noise_filter()
    
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
    
    def _initialize_noise_filter(self):
        """Initialize noise filtering components"""
        try:
            if self.noise_config.get("method") == "rnnoise":
                self.noise_filter = rnnoise.Denoise()
            elif self.noise_config.get("method") == "webrtc":
                # WebRTC noise suppression is handled in the audio callback
                pass
            else:
                self.logger.warning("Unknown noise filtering method, defaulting to WebRTC")
        except Exception as e:
            self.logger.error(f"Error initializing noise filter: {e}")
            self.noise_filtering_enabled = False
    
    def _audio_callback(self, indata, frames, time, status):
        """Callback function for audio stream"""
        if status:
            self.logger.warning(f"Audio callback status: {status}")
        
        try:
            # Convert to numpy array
            audio_data = np.frombuffer(indata, dtype=np.int16)
            
            # Apply noise filtering if enabled
            if self.noise_filtering_enabled:
                if self.noise_config.get("method") == "rnnoise":
                    audio_data = self.noise_filter.process(audio_data)
                elif self.noise_config.get("method") == "webrtc":
                    # WebRTC noise suppression is handled by the VAD
                    pass
            
            # Check for voice activity
            is_speech = self.vad.is_speech(audio_data.tobytes(), self.sample_rate)
            
            # Add to queue if it's speech or if we're in continuous listening mode
            if is_speech or self.config.get("speech_recognition", {}).get("continuous_listening", True):
                self.audio_queue.put({
                    "audio": audio_data,
                    "is_speech": is_speech,
                    "timestamp": time.time()
                })
        
        except Exception as e:
            self.logger.error(f"Error in audio callback: {e}")
    
    def start_listening(self, callback: Optional[Callable] = None):
        """Start listening to audio input"""
        try:
            if self.is_listening:
                self.logger.warning("Already listening")
                return
            
            self.is_listening = True
            self.audio_queue = queue.Queue()
            
            # Start audio stream
            self.current_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.format,
                device=self.device_index,
                blocksize=self.chunk_size,
                callback=self._audio_callback
            )
            
            self.current_stream.start()
            self.logger.info("Started listening to audio input")
            
            # Start processing thread if callback is provided
            if callback:
                threading.Thread(
                    target=self._process_audio,
                    args=(callback,),
                    daemon=True
                ).start()
        
        except Exception as e:
            self.logger.error(f"Error starting audio listener: {e}")
            self.is_listening = False
            raise
    
    def stop_listening(self):
        """Stop listening to audio input"""
        try:
            if not self.is_listening:
                return
            
            self.is_listening = False
            
            if self.current_stream:
                self.current_stream.stop()
                self.current_stream.close()
                self.current_stream = None
            
            self.logger.info("Stopped listening to audio input")
        
        except Exception as e:
            self.logger.error(f"Error stopping audio listener: {e}")
            raise
    
    def _process_audio(self, callback: Callable):
        """Process audio data from queue"""
        try:
            while self.is_listening:
                try:
                    # Get audio data from queue with timeout
                    audio_data = self.audio_queue.get(timeout=self.timeout)
                    
                    # Process audio data
                    if audio_data["is_speech"]:
                        callback(audio_data)
                    
                    self.audio_queue.task_done()
                
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Error processing audio: {e}")
        
        except Exception as e:
            self.logger.error(f"Error in audio processing thread: {e}")
    
    def get_audio_devices(self):
        """Get list of available audio input devices"""
        try:
            devices = sd.query_devices()
            input_devices = [
                {
                    "index": i,
                    "name": device["name"],
                    "channels": device["max_input_channels"],
                    "sample_rate": device["default_samplerate"]
                }
                for i, device in enumerate(devices)
                if device["max_input_channels"] > 0
            ]
            return input_devices
        except Exception as e:
            self.logger.error(f"Error getting audio devices: {e}")
            return []
    
    def set_device(self, device_index: int):
        """Set audio input device"""
        try:
            if self.is_listening:
                self.stop_listening()
            
            self.device_index = device_index
            self.logger.info(f"Set audio input device to index {device_index}")
            
            if self.is_listening:
                self.start_listening()
        
        except Exception as e:
            self.logger.error(f"Error setting audio device: {e}")
            raise
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.stop_listening()
            if self.noise_filter:
                del self.noise_filter
        except Exception as e:
            self.logger.error(f"Error cleaning up audio listener: {e}")

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test audio listener
    def audio_callback(audio_data):
        print(f"Received audio chunk: {len(audio_data['audio'])} samples")
    
    listener = AudioListener()
    try:
        listener.start_listening(audio_callback)
        print("Press Enter to stop...")
        input()
    finally:
        listener.cleanup() 