import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import yaml
from pathlib import Path
import asyncio
import queue
import threading
import json
import requests
from rasa.core.agent import Agent
from rasa.core.interpreter import RasaNLUInterpreter
import torch
import torchaudio
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

class IntentDetector:
    def __init__(self, config_path: str = "config/ear_agent_config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.intent_config = self.config.get("intent_detection", {})
        
        # Initialize intent detection parameters
        self.model = self.intent_config.get("model", "rasa")
        self.supported_intents = self.intent_config.get("supported_intents", [])
        self.confidence_threshold = self.intent_config.get("confidence_threshold", 0.6)
        self.rasa_endpoint = self.intent_config.get("rasa_endpoint", "http://localhost:5005")
        
        # Initialize components
        self.interpreter = None
        self.agent = None
        self.processor = None
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
        """Initialize intent detection model"""
        try:
            if self.model == "rasa":
                # Load Rasa model
                model_path = "models/rasa"
                if not Path(model_path).exists():
                    raise ValueError(f"Rasa model not found at {model_path}")
                
                self.interpreter = RasaNLUInterpreter(model_path)
                self.agent = Agent.load(model_path)
                self.logger.info("Initialized Rasa intent detection model")
            
            elif self.model == "wav2vec2":
                # Load Wav2Vec2 model and processor
                self.processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base-960h")
                self.classifier = Wav2Vec2ForCTC.from_pretrained("facebook/wav2vec2-base-960h")
                self.logger.info("Initialized Wav2Vec2 intent detection model")
            
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        
        except Exception as e:
            self.logger.error(f"Error initializing intent detection model: {e}")
            raise
    
    async def detect_intent(self, audio_data: np.ndarray, sample_rate: int = 16000) -> List[Dict[str, Any]]:
        """Detect intent in audio data"""
        try:
            if self.model == "rasa":
                return await self._detect_rasa(audio_data, sample_rate)
            elif self.model == "wav2vec2":
                return await self._detect_wav2vec2(audio_data, sample_rate)
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        
        except Exception as e:
            self.logger.error(f"Error detecting intent: {e}")
            return []
    
    async def _detect_rasa(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
        """Detect intent using Rasa"""
        try:
            # Convert audio to text using speech recognition
            # This is a placeholder - in practice, you'd use a speech recognition model
            text = "This is a placeholder text for intent detection"
            
            # Get predictions from Rasa
            response = requests.post(
                f"{self.rasa_endpoint}/model/parse",
                json={"text": text}
            )
            
            if response.status_code != 200:
                raise ValueError(f"Rasa API error: {response.text}")
            
            result = response.json()
            
            # Process results
            results = []
            for intent in result.get("intent_ranking", []):
                intent_name = intent.get("name")
                confidence = float(intent.get("confidence", 0))
                
                # Only include supported intents above threshold
                if intent_name in self.supported_intents and confidence >= self.confidence_threshold:
                    results.append({
                        "intent": intent_name,
                        "confidence": confidence,
                        "entities": result.get("entities", []),
                        "timestamp": asyncio.get_event_loop().time()
                    })
            
            # Sort by confidence
            results.sort(key=lambda x: x["confidence"], reverse=True)
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error in Rasa intent detection: {e}")
            return []
    
    async def _detect_wav2vec2(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
        """Detect intent using Wav2Vec2"""
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
            for intent in self.supported_intents:
                # Calculate confidence based on transcription
                # This is a placeholder - in practice, you'd use a more sophisticated method
                confidence = 0.8 if intent in transcription[0].lower() else 0.2
                
                if confidence >= self.confidence_threshold:
                    results.append({
                        "intent": intent,
                        "confidence": confidence,
                        "entities": [],
                        "timestamp": asyncio.get_event_loop().time()
                    })
            
            # Sort by confidence
            results.sort(key=lambda x: x["confidence"], reverse=True)
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error in Wav2Vec2 intent detection: {e}")
            return []
    
    def start_processing(self, callback: Optional[callable] = None):
        """Start intent detection processing"""
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
            
            self.logger.info("Started intent detection processing")
        
        except Exception as e:
            self.logger.error(f"Error starting intent detection: {e}")
            self.is_processing = False
            raise
    
    def stop_processing(self):
        """Stop intent detection processing"""
        try:
            if not self.is_processing:
                return
            
            self.is_processing = False
            
            if self.processing_thread:
                self.processing_thread.join(timeout=5)
                self.processing_thread = None
            
            self.logger.info("Stopped intent detection processing")
        
        except Exception as e:
            self.logger.error(f"Error stopping intent detection: {e}")
            raise
    
    def _process_queue(self, callback: Optional[callable] = None):
        """Process audio data from queue"""
        try:
            while self.is_processing:
                try:
                    # Get audio data from queue
                    audio_data = self.processing_queue.get(timeout=1)
                    
                    # Detect intent
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(
                        self.detect_intent(audio_data["audio"])
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
            self.logger.error(f"Error in intent detection thread: {e}")
    
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
    
    def get_supported_intents(self) -> List[str]:
        """Get list of supported intents"""
        return self.supported_intents.copy()
    
    def set_confidence_threshold(self, threshold: float):
        """Set confidence threshold for intent detection"""
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
            if self.interpreter:
                del self.interpreter
            if self.agent:
                del self.agent
            if self.processor:
                del self.processor
            if self.classifier:
                del self.classifier
        except Exception as e:
            self.logger.error(f"Error cleaning up intent detector: {e}")

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test intent detector
    async def test_detector():
        detector = IntentDetector()
        try:
            # Test with dummy audio data
            audio_data = np.zeros(16000, dtype=np.int16)  # 1 second of silence
            results = await detector.detect_intent(audio_data)
            print("Intent detection results:")
            for result in results:
                print(f"- {result['intent']}: {result['confidence']:.2f}")
                if result.get("entities"):
                    print("  Entities:", result["entities"])
        finally:
            detector.cleanup()
    
    asyncio.run(test_detector()) 