import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import yaml
from pathlib import Path
import asyncio
import queue
import threading
import torch
import torchaudio
from speechbrain.pretrained import EncoderClassifier
import librosa

class EmotionDetector:
    def __init__(self, config_path: str = "config/ear_agent_config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.emotion_config = self.config.get("emotion_detection", {})
        
        # Initialize emotion detection parameters
        self.model = self.emotion_config.get("model", "speechbrain")
        self.supported_emotions = self.emotion_config.get("supported_emotions", [])
        self.confidence_threshold = self.emotion_config.get("confidence_threshold", 0.6)
        self.window_size = self.emotion_config.get("window_size", 3)
        
        # Initialize components
        self.classifier = None
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
        """Initialize emotion detection model"""
        try:
            if self.model == "speechbrain":
                # Load SpeechBrain model
                self.classifier = EncoderClassifier.from_hparams(
                    source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
                    savedir="models/emotion-recognition-wav2vec2-IEMOCAP"
                )
                self.logger.info("Initialized SpeechBrain emotion detection model")
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        
        except Exception as e:
            self.logger.error(f"Error initializing emotion detection model: {e}")
            raise
    
    async def detect_emotion(self, audio_data: np.ndarray, sample_rate: int = 16000) -> List[Dict[str, Any]]:
        """Detect emotion in audio data"""
        try:
            if self.model == "speechbrain":
                return await self._detect_speechbrain(audio_data, sample_rate)
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        
        except Exception as e:
            self.logger.error(f"Error detecting emotion: {e}")
            return []
    
    async def _detect_speechbrain(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
        """Detect emotion using SpeechBrain"""
        try:
            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_data).float()
            
            # Resample if needed
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                audio_tensor = resampler(audio_tensor)
            
            # Add batch dimension
            audio_tensor = audio_tensor.unsqueeze(0)
            
            # Get predictions
            with torch.no_grad():
                out_prob, score, index, text_lab = self.classifier.classify_batch(audio_tensor)
            
            # Process results
            results = []
            for i, (prob, label) in enumerate(zip(out_prob[0], text_lab)):
                emotion = label.lower()
                confidence = float(prob)
                
                # Only include supported emotions above threshold
                if emotion in self.supported_emotions and confidence >= self.confidence_threshold:
                    results.append({
                        "emotion": emotion,
                        "confidence": confidence,
                        "timestamp": asyncio.get_event_loop().time()
                    })
            
            # Sort by confidence
            results.sort(key=lambda x: x["confidence"], reverse=True)
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error in SpeechBrain emotion detection: {e}")
            return []
    
    def start_processing(self, callback: Optional[callable] = None):
        """Start emotion detection processing"""
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
            
            self.logger.info("Started emotion detection processing")
        
        except Exception as e:
            self.logger.error(f"Error starting emotion detection: {e}")
            self.is_processing = False
            raise
    
    def stop_processing(self):
        """Stop emotion detection processing"""
        try:
            if not self.is_processing:
                return
            
            self.is_processing = False
            
            if self.processing_thread:
                self.processing_thread.join(timeout=5)
                self.processing_thread = None
            
            self.logger.info("Stopped emotion detection processing")
        
        except Exception as e:
            self.logger.error(f"Error stopping emotion detection: {e}")
            raise
    
    def _process_queue(self, callback: Optional[callable] = None):
        """Process audio data from queue"""
        try:
            while self.is_processing:
                try:
                    # Get audio data from queue
                    audio_data = self.processing_queue.get(timeout=1)
                    
                    # Detect emotion
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(
                        self.detect_emotion(audio_data["audio"])
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
            self.logger.error(f"Error in emotion detection thread: {e}")
    
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
    
    def get_supported_emotions(self) -> List[str]:
        """Get list of supported emotions"""
        return self.supported_emotions.copy()
    
    def set_confidence_threshold(self, threshold: float):
        """Set confidence threshold for emotion detection"""
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
            if self.classifier:
                del self.classifier
        except Exception as e:
            self.logger.error(f"Error cleaning up emotion detector: {e}")

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test emotion detector
    async def test_detector():
        detector = EmotionDetector()
        try:
            # Test with dummy audio data
            audio_data = np.zeros(16000, dtype=np.int16)  # 1 second of silence
            results = await detector.detect_emotion(audio_data)
            print("Emotion detection results:")
            for result in results:
                print(f"- {result['emotion']}: {result['confidence']:.2f}")
        finally:
            detector.cleanup()
    
    asyncio.run(test_detector()) 