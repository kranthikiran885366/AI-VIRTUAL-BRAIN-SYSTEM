"""
SoundClassifier — Production implementation with lazy imports.

Backends (in priority order):
  1. YAMNet via TensorFlow Hub (521-class audio event recognition)
  2. Acoustic feature classifier using librosa
     (spectral centroid + energy → speech / music / noise / silence)
"""

import asyncio
import logging
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

_DEFAULT_SOUNDS = [
    "Speech", "Music", "Silence", "Noise",
    "Dog", "Cat", "Bird", "Vehicle", "Door", "Alarm",
    "Applause", "Laughter", "Baby cry", "Telephone",
]

_YAMNET_URL = "https://tfhub.dev/google/yamnet/1"


class SoundClassifier:
    """Classifies environmental sounds using YAMNet (primary) or acoustic features (fallback)."""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        sound_cfg = config.get("sound_classification", {})

        self.model_name: str = sound_cfg.get("model", "yamnet")
        self.confidence_threshold: float = float(sound_cfg.get("confidence_threshold", 0.50))
        self._supported_sounds_cfg: List[str] = sound_cfg.get("supported_sounds", _DEFAULT_SOUNDS)
        self.sample_rate: int = int(config.get("audio", {}).get("sample_rate", 16000))
        self.top_k: int = int(sound_cfg.get("top_k", 5))

        self._backend: str = "acoustic"
        self._yamnet_model = None
        self._class_names: List[str] = []
        self.supported_sounds: List[str] = list(self._supported_sounds_cfg)

        self.processing_queue: queue.Queue = queue.Queue()
        self.is_processing: bool = False
        self.processing_thread: Optional[threading.Thread] = None

        self._initialize_model()

    # ─── Model Initialization ─────────────────────────────────────────────────

    def _initialize_model(self):
        if self.model_name in ("yamnet", "auto") and _HAS_NUMPY:
            try:
                import tensorflow as tf
                import tensorflow_hub as hub
                self._yamnet_model = hub.load(_YAMNET_URL)
                raw_names = self._yamnet_model.class_names
                self._class_names = [
                    n.decode("utf-8") if isinstance(n, bytes) else str(n)
                    for n in raw_names
                ]
                self.supported_sounds = [
                    s for s in self._supported_sounds_cfg if s in self._class_names
                ] or self._supported_sounds_cfg
                self._backend = "yamnet"
                self.logger.info(
                    f"SoundClassifier: loaded YAMNet ({len(self._class_names)} classes, "
                    f"{len(self.supported_sounds)} supported)"
                )
                return
            except Exception as e:
                self.logger.warning(f"SoundClassifier: YAMNet load failed — {e}")

        if _HAS_NUMPY:
            self._backend = "acoustic"
            self.logger.info("SoundClassifier: using acoustic feature fallback")
        else:
            self.logger.warning("SoundClassifier: no backend available")

    # ─── Main Classification API ──────────────────────────────────────────────

    async def classify_sound(self, audio_data, sample_rate: int = None) -> List[Dict[str, Any]]:
        sr = sample_rate or self.sample_rate
        try:
            if self._backend == "yamnet":
                return self._classify_yamnet(audio_data, sr)
            return self._classify_acoustic(audio_data, sr)
        except Exception as e:
            self.logger.error(f"SoundClassifier.classify_sound failed: {e}")
            return []

    # ─── YAMNet Backend ───────────────────────────────────────────────────────

    def _classify_yamnet(self, audio_data, sample_rate: int) -> List[Dict[str, Any]]:
        try:
            import numpy as np_local
            audio_f32 = audio_data.astype(np_local.float32) / 32768.0

            if sample_rate != 16000 and _HAS_NUMPY:
                try:
                    import librosa
                    audio_f32 = librosa.resample(audio_f32, orig_sr=sample_rate, target_sr=16000)
                except Exception:
                    ratio = 16000 / sample_rate
                    new_len = int(len(audio_f32) * ratio)
                    indices = [int(i / ratio) for i in range(new_len)]
                    audio_f32 = np_local.array([audio_f32[min(i, len(audio_f32)-1)] for i in indices], dtype=np_local.float32)

            scores, embeddings, spectrogram = self._yamnet_model(audio_f32)
            scores_np = scores.numpy()
            mean_scores = scores_np.mean(axis=0)
            top_indices = mean_scores.argsort()[::-1][:self.top_k]

            ts = datetime.utcnow().isoformat()
            results = []
            for idx in top_indices:
                class_name = self._class_names[int(idx)]
                confidence = round(float(mean_scores[idx]), 4)
                if confidence >= self.confidence_threshold:
                    results.append({
                        "sound": class_name,
                        "confidence": confidence,
                        "timestamp": ts,
                        "backend": "yamnet",
                    })
            return results
        except Exception as e:
            self.logger.error(f"SoundClassifier: YAMNet inference failed: {e}")
            return self._classify_acoustic(audio_data, sample_rate)

    # ─── Acoustic Feature Fallback ────────────────────────────────────────────

    def _classify_acoustic(self, audio_data, sample_rate: int) -> List[Dict[str, Any]]:
        try:
            import numpy as np_local
            audio_f32 = audio_data.astype(np_local.float32) / 32768.0
            rms = float(np_local.sqrt(np_local.mean(audio_f32 ** 2)))
            ts = datetime.utcnow().isoformat()

            if rms < 0.005:
                return [{"sound": "Silence", "confidence": 0.92, "timestamp": ts, "backend": "acoustic"}]

            zcr = float(np_local.mean(np_local.abs(np_local.diff(np_local.sign(audio_f32)))) / 2)

            try:
                import librosa
                sc = float(np_local.mean(librosa.feature.spectral_centroid(y=audio_f32, sr=sample_rate)))
                sr_feat = librosa.feature.spectral_rolloff(y=audio_f32, sr=sample_rate)
                rolloff = float(np_local.mean(sr_feat))
            except Exception:
                sc, rolloff = 2000.0, 4000.0

            if zcr < 0.10 and sc < 2500:
                sound, conf = "Speech", round(min(0.88, 0.55 + rms * 2), 3)
            elif sc > 4000 and rolloff > 8000:
                sound, conf = "Music", round(min(0.85, 0.50 + rms * 1.5), 3)
            elif rms > 0.15:
                sound, conf = "Noise", round(min(0.80, 0.45 + rms), 3)
            else:
                sound, conf = "Speech", round(min(0.75, 0.40 + rms * 2), 3)

            return [{"sound": sound, "confidence": conf, "timestamp": ts, "backend": "acoustic"}]
        except Exception as e:
            self.logger.error(f"SoundClassifier: acoustic fallback failed: {e}")
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
        self.logger.info("SoundClassifier: processing thread started")

    def stop_processing(self):
        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
            self.processing_thread = None

    def _processing_loop(self, callback: Optional[Callable]):
        while self.is_processing:
            try:
                item = self.processing_queue.get(timeout=1.0)
                results = asyncio.run(self.classify_sound(item["audio"]))
                for r in results:
                    r["audio_timestamp"] = item["timestamp"]
                    if callback:
                        callback(r)
                self.processing_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"SoundClassifier: processing loop error: {e}")

    def add_audio_data(self, audio_data, timestamp: float):
        if not self.is_processing:
            return
        self.processing_queue.put({"audio": audio_data, "timestamp": timestamp})

    def get_supported_sounds(self) -> List[str]:
        return list(self.supported_sounds)

    def set_confidence_threshold(self, threshold: float):
        if not 0 <= threshold <= 1:
            raise ValueError("Confidence threshold must be between 0 and 1")
        self.confidence_threshold = threshold

    def cleanup(self):
        self.stop_processing()
        self._yamnet_model = None