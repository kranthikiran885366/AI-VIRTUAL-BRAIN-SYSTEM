"""
EmotionDetector — Production implementation with lazy imports.

Backends (in priority order):
  1. SpeechBrain  — speechbrain/emotion-recognition-wav2vec2-IEMOCAP
  2. librosa acoustic features → hand-crafted rule classifier
     (energy, ZCR, spectral centroid, spectral rolloff → 4 emotion buckets)
"""

import asyncio
import logging
import math
import queue
import threading
import time as _time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None  # type: ignore

_DEFAULT_EMOTIONS = ["neutral", "happy", "sad", "angry", "fearful", "disgusted", "surprised"]


class EmotionDetector:
    """Detects emotion from audio using SpeechBrain (primary) or acoustic features (fallback)."""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        emotion_cfg = config.get("emotion_detection", {})

        self.model_name: str = emotion_cfg.get("model", "speechbrain")
        self.supported_emotions: List[str] = emotion_cfg.get("supported_emotions", _DEFAULT_EMOTIONS)
        self.confidence_threshold: float = float(emotion_cfg.get("confidence_threshold", 0.4))
        self.sample_rate: int = int(config.get("audio", {}).get("sample_rate", 16000))
        self._savedir: str = emotion_cfg.get("savedir", "models/emotion-recognition-wav2vec2-IEMOCAP")

        self.classifier = None
        self._backend: str = "acoustic"
        self.processing_queue: queue.Queue = queue.Queue()
        self.is_processing: bool = False
        self.processing_thread: Optional[threading.Thread] = None

        self._initialize_model()

    # ─── Model Initialization ─────────────────────────────────────────────────

    def _initialize_model(self):
        if self.model_name == "speechbrain" and _HAS_NUMPY:
            try:
                try:
                    from speechbrain.inference.classifiers import EncoderClassifier
                except ImportError:
                    from speechbrain.pretrained import EncoderClassifier

                self.classifier = EncoderClassifier.from_hparams(
                    source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
                    savedir=self._savedir,
                )
                self._backend = "speechbrain"
                self.logger.info("EmotionDetector: loaded SpeechBrain model")
                return
            except Exception as e:
                self.logger.warning(f"EmotionDetector: SpeechBrain load failed — {e}. Using acoustic fallback.")

        if _HAS_NUMPY:
            self._backend = "acoustic"
            self.logger.info("EmotionDetector: using acoustic feature fallback")
        else:
            self.logger.warning("EmotionDetector: no backend available")

    # ─── Main Detection API ───────────────────────────────────────────────────

    async def detect_emotion(self, audio_data, sample_rate: int = None) -> List[Dict[str, Any]]:
        sr = sample_rate or self.sample_rate
        try:
            if self._backend == "speechbrain":
                return await self._detect_speechbrain(audio_data, sr)
            return self._detect_acoustic(audio_data, sr)
        except Exception as e:
            self.logger.error(f"EmotionDetector.detect_emotion failed: {e}")
            return []

    # ─── SpeechBrain Backend ──────────────────────────────────────────────────

    async def _detect_speechbrain(self, audio_data, sample_rate: int) -> List[Dict[str, Any]]:
        try:
            import torch
            import torchaudio
            audio_f32 = audio_data.astype(np.float32) / 32768.0
            audio_tensor = torch.tensor(audio_f32).unsqueeze(0)

            if sample_rate != 16000:
                audio_tensor = torchaudio.transforms.Resample(sample_rate, 16000)(audio_tensor)

            with torch.no_grad():
                out_prob, score, index, text_lab = self.classifier.classify_batch(audio_tensor)

            results: List[Dict[str, Any]] = []
            ts = datetime.utcnow().isoformat()
            for prob_val, label in zip(out_prob[0].tolist(), text_lab):
                emotion = label.lower().strip()
                confidence = round(float(prob_val), 4)
                if confidence >= self.confidence_threshold:
                    results.append({"emotion": emotion, "confidence": confidence, "timestamp": ts})

            results.sort(key=lambda x: x["confidence"], reverse=True)
            return results
        except Exception as e:
            self.logger.error(f"EmotionDetector: SpeechBrain inference failed: {e}")
            return self._detect_acoustic(audio_data, sample_rate)

    # ─── Acoustic Feature Fallback ────────────────────────────────────────────

    def _detect_acoustic(self, audio_data, sample_rate: int) -> List[Dict[str, Any]]:
        try:
            if _HAS_NUMPY and audio_data is not None and len(audio_data) > 0:
                audio_f32 = audio_data.astype(np.float32) / 32768.0
            else:
                return []

            rms = float(np.sqrt(np.mean(audio_f32 ** 2)))
            zcr = float(np.mean(np.abs(np.diff(np.sign(audio_f32)))) / 2)

            spec_centroid = 0.0
            try:
                import librosa
                sc = librosa.feature.spectral_centroid(y=audio_f32, sr=sample_rate)
                spec_centroid = float(np.mean(sc))
            except Exception:
                pass

            ts = datetime.utcnow().isoformat()

            if rms < 0.01:
                return [{"emotion": "neutral", "confidence": 0.80, "timestamp": ts}]

            if rms > 0.15 and zcr > 0.15:
                emotion, conf = "angry", round(min(0.90, 0.55 + rms * 2.0), 3)
            elif rms > 0.10 and spec_centroid > 3000:
                emotion, conf = "happy", round(min(0.88, 0.50 + rms * 1.5), 3)
            elif rms < 0.04 and zcr < 0.05:
                emotion, conf = "sad", round(min(0.85, 0.50 + (0.04 - rms) * 10), 3)
            else:
                emotion, conf = "neutral", round(min(0.82, 0.55 + rms), 3)

            return [{"emotion": emotion, "confidence": conf, "timestamp": ts}]
        except Exception as e:
            self.logger.error(f"EmotionDetector: acoustic fallback failed: {e}")
            return []

    # ─── Processing Thread ────────────────────────────────────────────────────

    def start_processing(self, callback: Optional[Callable] = None):
        if self.is_processing:
            return
        self.is_processing = True
        self.processing_thread = threading.Thread(
            target=self._processing_loop, args=(callback,), daemon=True
        )
        self.processing_thread.start()
        self.logger.info("EmotionDetector: processing thread started")

    def stop_processing(self):
        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
            self.processing_thread = None

    def _processing_loop(self, callback: Optional[Callable]):
        while self.is_processing:
            try:
                item = self.processing_queue.get(timeout=1.0)
                results = asyncio.run(self.detect_emotion(item["audio"]))
                for r in results:
                    r["audio_timestamp"] = item["timestamp"]
                    if callback:
                        callback(r)
                self.processing_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"EmotionDetector: processing loop error: {e}")

    def add_audio_data(self, audio_data, timestamp: float):
        if not self.is_processing:
            return
        self.processing_queue.put({"audio": audio_data, "timestamp": timestamp})

    def get_supported_emotions(self) -> List[str]:
        return list(self.supported_emotions)

    def set_confidence_threshold(self, threshold: float):
        if not 0 <= threshold <= 1:
            raise ValueError("Confidence threshold must be between 0 and 1")
        self.confidence_threshold = threshold

    def cleanup(self):
        self.stop_processing()
        self.classifier = None