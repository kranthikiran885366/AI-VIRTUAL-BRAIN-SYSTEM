import numpy as np
import torch
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import librosa
import soundfile as sf
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
import torchaudio

@dataclass
class AudioConfig:
    """Configuration for audio processing."""
    sample_rate: int
    frame_length: int
    hop_length: int
    n_mels: int
    n_fft: int
    device: str
    model_path: str
    confidence_threshold: float

class AudioProcessor:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the audio processor."""
        self.logger = logging.getLogger(__name__)
        self.config = AudioConfig(**config)
        
        # Initialize models
        self._init_models()
        
        # Performance metrics
        self.processing_times = []
    
    def _init_models(self):
        """Initialize audio processing models."""
        # Initialize speech recognition model
        self.processor = Wav2Vec2Processor.from_pretrained(self.config.model_path)
        self.model = Wav2Vec2ForCTC.from_pretrained(self.config.model_path)
        
        # Move model to specified device
        if self.config.device == "cuda" and torch.cuda.is_available():
            self.model = self.model.to("cuda")
    
    def process(self, audio_data: Optional[np.ndarray]) -> Dict[str, Any]:
        """Process audio data."""
        if audio_data is None:
            return {"error": "No audio data provided"}
        
        start_time = time.time()
        
        try:
            # Extract audio features
            features = self._extract_features(audio_data)
            
            # Perform speech recognition
            transcription = self._recognize_speech(audio_data)
            
            # Analyze audio characteristics
            characteristics = self._analyze_characteristics(audio_data)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            return {
                "features": features,
                "transcription": transcription,
                "characteristics": characteristics,
                "processing_time": processing_time,
                "timestamp": time.time()
            }
        
        except Exception as e:
            self.logger.error(f"Error in audio processing: {str(e)}")
            return {"error": str(e)}
    
    def _extract_features(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Extract audio features."""
        features = {}
        
        try:
            # Extract mel spectrogram
            mel_spec = librosa.feature.melspectrogram(
                y=audio_data,
                sr=self.config.sample_rate,
                n_mels=self.config.n_mels,
                n_fft=self.config.n_fft,
                hop_length=self.config.hop_length
            )
            
            # Extract MFCCs
            mfccs = librosa.feature.mfcc(
                y=audio_data,
                sr=self.config.sample_rate,
                n_mfcc=13,
                n_fft=self.config.n_fft,
                hop_length=self.config.hop_length
            )
            
            # Extract spectral contrast
            contrast = librosa.feature.spectral_contrast(
                y=audio_data,
                sr=self.config.sample_rate,
                n_fft=self.config.n_fft,
                hop_length=self.config.hop_length
            )
            
            features = {
                "mel_spectrogram": mel_spec.tolist(),
                "mfccs": mfccs.tolist(),
                "spectral_contrast": contrast.tolist()
            }
        
        except Exception as e:
            self.logger.error(f"Error in feature extraction: {str(e)}")
        
        return features
    
    def _recognize_speech(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Perform speech recognition."""
        result = {
            "text": "",
            "confidence": 0.0
        }
        
        try:
            # Prepare audio for model
            inputs = self.processor(
                audio_data,
                sampling_rate=self.config.sample_rate,
                return_tensors="pt"
            )
            
            # Move inputs to device
            if self.config.device == "cuda" and torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # Perform inference
            with torch.no_grad():
                logits = self.model(**inputs).logits
            
            # Decode predictions
            predicted_ids = torch.argmax(logits, dim=-1)
            transcription = self.processor.batch_decode(predicted_ids)
            
            # Calculate confidence
            probs = torch.nn.functional.softmax(logits, dim=-1)
            confidence = torch.mean(torch.max(probs, dim=-1)[0]).item()
            
            result = {
                "text": transcription[0],
                "confidence": confidence
            }
        
        except Exception as e:
            self.logger.error(f"Error in speech recognition: {str(e)}")
        
        return result
    
    def _analyze_characteristics(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Analyze audio characteristics."""
        characteristics = {}
        
        try:
            # Calculate RMS energy
            rms = librosa.feature.rms(y=audio_data)[0]
            
            # Calculate zero crossing rate
            zcr = librosa.feature.zero_crossing_rate(audio_data)[0]
            
            # Calculate spectral centroid
            centroid = librosa.feature.spectral_centroid(
                y=audio_data,
                sr=self.config.sample_rate,
                n_fft=self.config.n_fft,
                hop_length=self.config.hop_length
            )[0]
            
            # Calculate spectral bandwidth
            bandwidth = librosa.feature.spectral_bandwidth(
                y=audio_data,
                sr=self.config.sample_rate,
                n_fft=self.config.n_fft,
                hop_length=self.config.hop_length
            )[0]
            
            characteristics = {
                "rms": float(np.mean(rms)),
                "zcr": float(np.mean(zcr)),
                "centroid": float(np.mean(centroid)),
                "bandwidth": float(np.mean(bandwidth))
            }
        
        except Exception as e:
            self.logger.error(f"Error in characteristic analysis: {str(e)}")
        
        return characteristics
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        if not self.processing_times:
            return {}
        
        return {
            "mean": np.mean(self.processing_times),
            "std": np.std(self.processing_times),
            "min": np.min(self.processing_times),
            "max": np.max(self.processing_times)
        }
    
    def reset(self):
        """Reset the audio processor."""
        self.processing_times = []
        self.logger.info("Audio processor reset") 