import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import yaml
from pathlib import Path
import asyncio
import queue
import threading
from resemblyzer import VoiceEncoder, preprocess_wav
from pathlib import Path
import librosa
import pickle
import os

class SpeakerIdentifier:
    def __init__(self, config_path: str = "config/ear_agent_config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.speaker_config = self.config.get("speaker_identification", {})
        
        # Initialize speaker identification parameters
        self.model = self.speaker_config.get("model", "resemblyzer")
        self.min_samples = self.speaker_config.get("min_samples", 3)
        self.confidence_threshold = self.speaker_config.get("confidence_threshold", 0.7)
        self.max_speakers = self.speaker_config.get("max_speakers", 5)
        
        # Initialize components
        self.encoder = None
        self.speaker_embeddings = {}
        self.speaker_names = {}
        self.processing_queue = queue.Queue()
        self.is_processing = False
        self.processing_thread = None
        
        # Load model and speaker data
        self._initialize_model()
        self._load_speaker_data()
    
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
        """Initialize speaker identification model"""
        try:
            if self.model == "resemblyzer":
                self.encoder = VoiceEncoder()
                self.logger.info("Initialized Resemblyzer model")
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        
        except Exception as e:
            self.logger.error(f"Error initializing speaker identification model: {e}")
            raise
    
    def _load_speaker_data(self):
        """Load speaker embeddings and names"""
        try:
            data_dir = Path("data/speakers")
            if not data_dir.exists():
                data_dir.mkdir(parents=True)
                return
            
            # Load speaker embeddings
            embeddings_file = data_dir / "embeddings.pkl"
            if embeddings_file.exists():
                with open(embeddings_file, "rb") as f:
                    self.speaker_embeddings = pickle.load(f)
            
            # Load speaker names
            names_file = data_dir / "names.pkl"
            if names_file.exists():
                with open(names_file, "rb") as f:
                    self.speaker_names = pickle.load(f)
            
            self.logger.info(f"Loaded {len(self.speaker_embeddings)} speaker profiles")
        
        except Exception as e:
            self.logger.error(f"Error loading speaker data: {e}")
    
    def _save_speaker_data(self):
        """Save speaker embeddings and names"""
        try:
            data_dir = Path("data/speakers")
            if not data_dir.exists():
                data_dir.mkdir(parents=True)
            
            # Save speaker embeddings
            with open(data_dir / "embeddings.pkl", "wb") as f:
                pickle.dump(self.speaker_embeddings, f)
            
            # Save speaker names
            with open(data_dir / "names.pkl", "wb") as f:
                pickle.dump(self.speaker_names, f)
            
            self.logger.info("Saved speaker data")
        
        except Exception as e:
            self.logger.error(f"Error saving speaker data: {e}")
    
    async def identify_speaker(self, audio_data: np.ndarray, sample_rate: int = 16000) -> List[Dict[str, Any]]:
        """Identify speaker in audio data"""
        try:
            if self.model == "resemblyzer":
                return await self._identify_resemblyzer(audio_data, sample_rate)
            else:
                raise ValueError(f"Unsupported model: {self.model}")
        
        except Exception as e:
            self.logger.error(f"Error identifying speaker: {e}")
            return []
    
    async def _identify_resemblyzer(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
        """Identify speaker using Resemblyzer"""
        try:
            # Preprocess audio
            audio_float32 = audio_data.astype(np.float32) / 32768.0
            wav = preprocess_wav(audio_float32, sample_rate)
            
            # Get embedding
            embedding = self.encoder.embed_utterance(wav)
            
            # Compare with known speakers
            results = []
            for speaker_id, known_embedding in self.speaker_embeddings.items():
                similarity = np.dot(embedding, known_embedding)
                
                if similarity >= self.confidence_threshold:
                    results.append({
                        "speaker_id": speaker_id,
                        "name": self.speaker_names.get(speaker_id, "Unknown"),
                        "confidence": float(similarity),
                        "timestamp": asyncio.get_event_loop().time()
                    })
            
            # Sort by confidence
            results.sort(key=lambda x: x["confidence"], reverse=True)
            
            return results[:self.max_speakers]
        
        except Exception as e:
            self.logger.error(f"Error in Resemblyzer identification: {e}")
            return []
    
    def add_speaker(self, speaker_id: str, name: str, audio_samples: List[np.ndarray], sample_rate: int = 16000) -> bool:
        """Add a new speaker profile"""
        try:
            if len(audio_samples) < self.min_samples:
                raise ValueError(f"Need at least {self.min_samples} samples")
            
            # Process each sample
            embeddings = []
            for audio in audio_samples:
                # Preprocess audio
                audio_float32 = audio.astype(np.float32) / 32768.0
                wav = preprocess_wav(audio_float32, sample_rate)
                
                # Get embedding
                embedding = self.encoder.embed_utterance(wav)
                embeddings.append(embedding)
            
            # Average embeddings
            avg_embedding = np.mean(embeddings, axis=0)
            
            # Save speaker data
            self.speaker_embeddings[speaker_id] = avg_embedding
            self.speaker_names[speaker_id] = name
            
            # Save to disk
            self._save_speaker_data()
            
            self.logger.info(f"Added speaker profile for {name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error adding speaker: {e}")
            return False
    
    def remove_speaker(self, speaker_id: str) -> bool:
        """Remove a speaker profile"""
        try:
            if speaker_id not in self.speaker_embeddings:
                return False
            
            # Remove speaker data
            del self.speaker_embeddings[speaker_id]
            del self.speaker_names[speaker_id]
            
            # Save to disk
            self._save_speaker_data()
            
            self.logger.info(f"Removed speaker profile {speaker_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error removing speaker: {e}")
            return False
    
    def get_speaker_profiles(self) -> List[Dict[str, Any]]:
        """Get list of speaker profiles"""
        try:
            return [
                {
                    "speaker_id": speaker_id,
                    "name": self.speaker_names.get(speaker_id, "Unknown")
                }
                for speaker_id in self.speaker_embeddings
            ]
        except Exception as e:
            self.logger.error(f"Error getting speaker profiles: {e}")
            return []
    
    def start_processing(self, callback: Optional[callable] = None):
        """Start speaker identification processing"""
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
            
            self.logger.info("Started speaker identification processing")
        
        except Exception as e:
            self.logger.error(f"Error starting speaker identification: {e}")
            self.is_processing = False
            raise
    
    def stop_processing(self):
        """Stop speaker identification processing"""
        try:
            if not self.is_processing:
                return
            
            self.is_processing = False
            
            if self.processing_thread:
                self.processing_thread.join(timeout=5)
                self.processing_thread = None
            
            self.logger.info("Stopped speaker identification processing")
        
        except Exception as e:
            self.logger.error(f"Error stopping speaker identification: {e}")
            raise
    
    def _process_queue(self, callback: Optional[callable] = None):
        """Process audio data from queue"""
        try:
            while self.is_processing:
                try:
                    # Get audio data from queue
                    audio_data = self.processing_queue.get(timeout=1)
                    
                    # Identify speaker
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(
                        self.identify_speaker(audio_data["audio"])
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
            self.logger.error(f"Error in speaker identification thread: {e}")
    
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
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.stop_processing()
            if self.encoder:
                del self.encoder
        except Exception as e:
            self.logger.error(f"Error cleaning up speaker identifier: {e}")

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test speaker identifier
    async def test_identifier():
        identifier = SpeakerIdentifier()
        try:
            # Test with dummy audio data
            audio_data = np.zeros(16000, dtype=np.int16)  # 1 second of silence
            results = await identifier.identify_speaker(audio_data)
            print("Identification results:")
            for result in results:
                print(f"- {result['name']}: {result['confidence']:.2f}")
        finally:
            identifier.cleanup()
    
    asyncio.run(test_identifier()) 