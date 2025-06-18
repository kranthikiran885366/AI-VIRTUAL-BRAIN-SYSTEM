import logging
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
from typing import Dict, Any, List, Tuple, Optional
import yaml
from pathlib import Path
import asyncio
import queue
import threading

class SoundClassifier:
    def __init__(self, config_path: str = "config/ear_agent_config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.sound_config = self.config.get("sound_classification", {})
        
        # Initialize sound classification parameters
        self.model = self.sound_config.get("model", "yamnet")
        self.confidence_threshold = self.sound_config.get("confidence_threshold", 0.6)
        self.supported_sounds = self.sound_config.get("supported_sounds", [])
        
        # Initialize components
        self.yamnet_model = None
        self.class_names = None
        self.processing_queue = queue.Queue()
        self.is_processing = False
        self.processing_thread = None
        
        # Load model
        self._initialize_model()
    
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
    
    def _initialize_model(self):
        """Initialize sound classification model"""
        try:
            if self.model == "yamnet":
                # Load YAMNet model
                self.yamnet_model = hub.load('https://tfhub.dev/google/yamnet/1')
                
                # Get class names
                self.class_names = self.yamnet_model.class_names
                
                # Filter supported sounds
                self.supported_sounds = [
                    sound for sound in self.supported_sounds
                    if sound in self.class_names
                ]
                
                self.logger.info(f"Initialized YAMNet model with {len(self.supported_sounds)} supported sounds")
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        
        except Exception as e:
            self.logger.error(f"Error initializing sound classification model: {e}")
            raise
    
    async def classify_sound(self, audio_data: np.ndarray, sample_rate: int = 16000) -> List[Dict[str, Any]]:
        """Classify sound in audio data"""
        try:
            if self.model == "yamnet":
                return await self._classify_yamnet(audio_data, sample_rate)
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        
        except Exception as e:
            self.logger.error(f"Error classifying sound: {e}")
            return []
    
    async def _classify_yamnet(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
        """Classify sound using YAMNet"""
        try:
            # Convert audio to float32
            audio_float32 = audio_data.astype(np.float32) / 32768.0
            
            # Add batch dimension
            audio_batch = np.expand_dims(audio_float32, axis=0)
            
            # Get predictions
            scores, embeddings, spectrogram = self.yamnet_model(audio_batch)
            
            # Get top predictions
            scores = scores.numpy()[0]
            top_indices = np.argsort(scores)[::-1][:5]  # Top 5 predictions
            
            results = []
            for idx in top_indices:
                class_name = self.class_names[idx].decode('utf-8')
                confidence = float(scores[idx])
                
                # Only include supported sounds above threshold
                if class_name in self.supported_sounds and confidence >= self.confidence_threshold:
                    results.append({
                        "sound": class_name,
                        "confidence": confidence,
                        "timestamp": asyncio.get_event_loop().time()
                    })
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error in YAMNet classification: {e}")
            return []
    
    def start_processing(self, callback: Optional[callable] = None):
        """Start sound classification processing"""
        try:
            if self.is_processing:
                self.logger.warning("Already processing")
                return
            
            self.is_processing = True
            
            # Start processing thread
            self.processing_thread = threading.Thread(
                target=self._process_queue,
                args=(callback,) if callback else (),
                daemon=True
            )
            self.processing_thread.start()
            
            self.logger.info("Started sound classification processing")
        
        except Exception as e:
            self.logger.error(f"Error starting sound classification: {e}")
            self.is_processing = False
            raise
    
    def stop_processing(self):
        """Stop sound classification processing"""
        try:
            if not self.is_processing:
                return
            
            self.is_processing = False
            
            if self.processing_thread:
                self.processing_thread.join(timeout=5)
                self.processing_thread = None
            
            self.logger.info("Stopped sound classification processing")
        
        except Exception as e:
            self.logger.error(f"Error stopping sound classification: {e}")
            raise
    
    def _process_queue(self, callback: Optional[callable] = None):
        """Process audio data from queue"""
        try:
            while self.is_processing:
                try:
                    # Get audio data from queue
                    audio_data = self.processing_queue.get(timeout=1)
                    
                    # Classify sound
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(
                        self.classify_sound(audio_data["audio"])
                    )
                    loop.close()
                    
                    # Call callback if provided
                    if callback and results:
                        callback({
                            "results": results,
                            "timestamp": audio_data["timestamp"]
                        })
                    
                    self.processing_queue.task_done()
                
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Error processing audio: {e}")
        
        except Exception as e:
            self.logger.error(f"Error in sound classification thread: {e}")
    
    def add_audio_data(self, audio_data: np.ndarray, timestamp: float):
        """Add audio data to processing queue"""
        try:
            if not self.is_processing:
                return
            
            self.processing_queue.put({
                "audio": audio_data,
                "timestamp": timestamp
            })
        
        except Exception as e:
            self.logger.error(f"Error adding audio data: {e}")
    
    def get_supported_sounds(self) -> List[str]:
        """Get list of supported sounds"""
        return self.supported_sounds.copy()
    
    def set_confidence_threshold(self, threshold: float):
        """Set confidence threshold for sound classification"""
        try:
            if not 0 <= threshold <= 1:
                raise ValueError("Confidence threshold must be between 0 and 1")
            
            self.confidence_threshold = threshold
            self.logger.info(f"Set confidence threshold to {threshold}")
        
        except Exception as e:
            self.logger.error(f"Error setting confidence threshold: {e}")
            raise
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.stop_processing()
            if self.yamnet_model:
                del self.yamnet_model
        except Exception as e:
            self.logger.error(f"Error cleaning up sound classifier: {e}")

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test sound classifier
    async def test_classifier():
        classifier = SoundClassifier()
        try:
            # Test with dummy audio data
            audio_data = np.zeros(16000, dtype=np.int16)  # 1 second of silence
            results = await classifier.classify_sound(audio_data)
            print("Classification results:")
            for result in results:
                print(f"- {result['sound']}: {result['confidence']:.2f}")
        finally:
            classifier.cleanup()
    
    asyncio.run(test_classifier()) 