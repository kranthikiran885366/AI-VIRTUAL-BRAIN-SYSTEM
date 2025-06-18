import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import yaml
from pathlib import Path
import asyncio
import queue
import threading
import fasttext
import librosa
import torch
import torchaudio
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

class LanguageDetector:
    def __init__(self, config_path: str = "config/ear_agent_config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.language_config = self.config.get("language_detection", {})
        
        # Initialize language detection parameters
        self.model = self.language_config.get("model", "fasttext")
        self.supported_languages = self.language_config.get("supported_languages", [])
        self.confidence_threshold = self.language_config.get("confidence_threshold", 0.6)
        self.min_audio_length = self.language_config.get("min_audio_length", 1.0)  # seconds
        
        # Initialize components
        self.classifier = None
        self.processor = None
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
        """Initialize language detection model"""
        try:
            if self.model == "fasttext":
                # Load FastText model
                model_path = "models/lid.176.bin"
                if not Path(model_path).exists():
                    self.logger.info("Downloading FastText language identification model...")
                    fasttext.util.download_model('lid.176.bin', if_exists='ignore')
                
                self.classifier = fasttext.load_model(model_path)
                self.logger.info("Initialized FastText language detection model")
            
            elif self.model == "wav2vec2":
                # Load Wav2Vec2 model and processor
                self.processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-large-xlsr-53")
                self.classifier = Wav2Vec2ForCTC.from_pretrained("facebook/wav2vec2-large-xlsr-53")
                self.logger.info("Initialized Wav2Vec2 language detection model")
            
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        
        except Exception as e:
            self.logger.error(f"Error initializing language detection model: {e}")
            raise
    
    async def detect_language(self, audio_data: np.ndarray, sample_rate: int = 16000) -> List[Dict[str, Any]]:
        """Detect language in audio data"""
        try:
            if len(audio_data) < sample_rate * self.min_audio_length:
                self.logger.warning(f"Audio too short (minimum {self.min_audio_length}s)")
                return []
            
            if self.model == "fasttext":
                return await self._detect_fasttext(audio_data, sample_rate)
            elif self.model == "wav2vec2":
                return await self._detect_wav2vec2(audio_data, sample_rate)
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        
        except Exception as e:
            self.logger.error(f"Error detecting language: {e}")
            return []
    
    async def _detect_fasttext(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
        """Detect language using FastText"""
        try:
            # Convert audio to text using speech recognition
            # This is a placeholder - in practice, you'd use a speech recognition model
            text = "This is a placeholder text for language detection"
            
            # Get predictions
            predictions = self.classifier.predict(text, k=len(self.supported_languages))
            
            # Process results
            results = []
            for lang, prob in zip(predictions[0], predictions[1]):
                language = lang.replace('__label__', '')
                confidence = float(prob)
                
                # Only include supported languages above threshold
                if language in self.supported_languages and confidence >= self.confidence_threshold:
                    results.append({
                        "language": language,
                        "confidence": confidence,
                        "timestamp": asyncio.get_event_loop().time()
                    })
            
            # Sort by confidence
            results.sort(key=lambda x: x["confidence"], reverse=True)
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error in FastText language detection: {e}")
            return []
    
    async def _detect_wav2vec2(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
        """Detect language using Wav2Vec2"""
        try:
            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_data).float()
            
            # Resample if needed
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                audio_tensor = resampler(audio_tensor)
            
            # Process audio
            inputs = self.processor(
                audio_tensor,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True
            )
            
            # Get predictions
            with torch.no_grad():
                logits = self.classifier(inputs.input_values).logits
                predicted_ids = torch.argmax(logits, dim=-1)
                transcription = self.processor.batch_decode(predicted_ids)
            
            # Process results
            results = []
            for lang in self.supported_languages:
                # Calculate confidence based on transcription
                # This is a placeholder - in practice, you'd use a more sophisticated method
                confidence = 0.8 if lang in transcription[0].lower() else 0.2
                
                if confidence >= self.confidence_threshold:
                    results.append({
                        "language": lang,
                        "confidence": confidence,
                        "timestamp": asyncio.get_event_loop().time()
                    })
            
            # Sort by confidence
            results.sort(key=lambda x: x["confidence"], reverse=True)
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error in Wav2Vec2 language detection: {e}")
            return []
    
    def start_processing(self, callback: Optional[callable] = None):
        """Start language detection processing"""
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
            
            self.logger.info("Started language detection processing")
        
        except Exception as e:
            self.logger.error(f"Error starting language detection: {e}")
            self.is_processing = False
            raise
    
    def stop_processing(self):
        """Stop language detection processing"""
        try:
            if not self.is_processing:
                return
            
            self.is_processing = False
            
            if self.processing_thread:
                self.processing_thread.join(timeout=5)
                self.processing_thread = None
            
            self.logger.info("Stopped language detection processing")
        
        except Exception as e:
            self.logger.error(f"Error stopping language detection: {e}")
            raise
    
    def _process_queue(self, callback: Optional[callable] = None):
        """Process audio data from queue"""
        try:
            while self.is_processing:
                try:
                    # Get audio data from queue
                    audio_data = self.processing_queue.get(timeout=1)
                    
                    # Detect language
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(
                        self.detect_language(audio_data["audio"])
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
            self.logger.error(f"Error in language detection thread: {e}")
    
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
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        return self.supported_languages.copy()
    
    def set_confidence_threshold(self, threshold: float):
        """Set confidence threshold for language detection"""
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
            if self.processor:
                del self.processor
        except Exception as e:
            self.logger.error(f"Error cleaning up language detector: {e}")

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test language detector
    async def test_detector():
        detector = LanguageDetector()
        try:
            # Test with dummy audio data
            audio_data = np.zeros(16000, dtype=np.int16)  # 1 second of silence
            results = await detector.detect_language(audio_data)
            print("Language detection results:")
            for result in results:
                print(f"- {result['language']}: {result['confidence']:.2f}")
        finally:
            detector.cleanup()
    
    asyncio.run(test_detector()) 