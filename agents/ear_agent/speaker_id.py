"""
SpeakerIdentifier — Production implementation with lazy imports.

Backends (in priority order):
  1. Resemblyzer — VoiceEncoder for d-vector speaker embeddings
  2. Pure-numpy cosine similarity on MFCCs (when Resemblyzer unavailable)
"""

import asyncio
import logging
import os
import pickle
import queue
import threading
import time as _time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None  # type: ignore


class SpeakerIdentifier:
    """Identifies speakers in audio using Resemblyzer (primary) or MFCC cosine similarity (fallback)."""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        spk_cfg = config.get("speaker_identification", {})

        self.model_name: str = spk_cfg.get("model", "resemblyzer")
        self.min_samples: int = int(spk_cfg.get("min_samples", 3))
        self.confidence_threshold: float = float(spk_cfg.get("confidence_threshold", 0.70))
        self.max_speakers: int = int(spk_cfg.get("max_speakers", 10))
        self.sample_rate: int = int(config.get("audio", {}).get("sample_rate", 16000))

        _data_dir = spk_cfg.get("data_dir", "data/speakers")
        self._data_dir: Path = Path(_data_dir)
        self._embeddings_file: Path = self._data_dir / "embeddings.pkl"
        self._names_file: Path = self._data_dir / "names.pkl"

        self._backend: str = "mfcc"
        self.encoder = None
        self._preprocess_wav_fn = None
        self.speaker_embeddings: Dict[str, Any] = {}
        self.speaker_names: Dict[str, str] = {}

        self.processing_queue: queue.Queue = queue.Queue()
        self.is_processing: bool = False
        self.processing_thread: Optional[threading.Thread] = None

        self._initialize_model()
        self._load_speaker_data()

    # ─── Model Initialization ─────────────────────────────────────────────────

    def _initialize_model(self):
        if self.model_name in ("resemblyzer", "auto") and _HAS_NUMPY:
            try:
                from resemblyzer import VoiceEncoder, preprocess_wav
                self.encoder = VoiceEncoder()
                self._preprocess_wav_fn = preprocess_wav
                self._backend = "resemblyzer"
                self.logger.info("SpeakerIdentifier: loaded Resemblyzer VoiceEncoder")
                return
            except Exception as e:
                self.logger.warning(f"SpeakerIdentifier: Resemblyzer load failed — {e}")

        if _HAS_NUMPY:
            self._backend = "mfcc"
            self.logger.info("SpeakerIdentifier: using MFCC cosine-similarity fallback")
        else:
            self.logger.warning("SpeakerIdentifier: no backend available")

    # ─── Speaker Data Persistence ─────────────────────────────────────────────

    def _load_speaker_data(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        try:
            if self._embeddings_file.exists():
                with open(self._embeddings_file, "rb") as f:
                    self.speaker_embeddings = pickle.load(f)
            if self._names_file.exists():
                with open(self._names_file, "rb") as f:
                    self.speaker_names = pickle.load(f)
            self.logger.info(f"SpeakerIdentifier: loaded {len(self.speaker_embeddings)} speaker profile(s)")
        except Exception as e:
            self.logger.error(f"SpeakerIdentifier: failed to load speaker data — {e}")
            self.speaker_embeddings = {}
            self.speaker_names = {}

    def _save_speaker_data(self):
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            with open(self._embeddings_file, "wb") as f:
                pickle.dump(self.speaker_embeddings, f)
            with open(self._names_file, "wb") as f:
                pickle.dump(self.speaker_names, f)
            self.logger.info("SpeakerIdentifier: speaker data saved")
        except Exception as e:
            self.logger.error(f"SpeakerIdentifier: failed to save speaker data — {e}")

    # ─── Main Identification API ──────────────────────────────────────────────

    async def identify_speaker(self, audio_data, sample_rate: int = None) -> List[Dict[str, Any]]:
        sr = sample_rate or self.sample_rate
        if not self.speaker_embeddings:
            return [{"speaker_id": "unknown", "name": "Unknown",
                     "confidence": 0.0, "timestamp": datetime.utcnow().isoformat()}]
        try:
            if self._backend == "resemblyzer":
                return self._identify_resemblyzer(audio_data, sr)
            return self._identify_mfcc(audio_data, sr)
        except Exception as e:
            self.logger.error(f"SpeakerIdentifier.identify_speaker failed: {e}")
            return []

    # ─── Resemblyzer Backend ──────────────────────────────────────────────────

    def _identify_resemblyzer(self, audio_data, sample_rate: int) -> List[Dict[str, Any]]:
        try:
            import numpy as np_local
            audio_f32 = audio_data.astype(np_local.float32) / 32768.0
            wav = self._preprocess_wav_fn(audio_f32, source_sr=sample_rate)
            embedding = self.encoder.embed_utterance(wav)
            embedding = embedding / (np_local.linalg.norm(embedding) + 1e-10)

            return self._score_against_profiles(embedding)
        except Exception as e:
            self.logger.error(f"SpeakerIdentifier: Resemblyzer inference failed: {e}")
            return self._identify_mfcc(audio_data, sample_rate)

    # ─── MFCC Cosine Similarity Fallback ─────────────────────────────────────

    def _identify_mfcc(self, audio_data, sample_rate: int) -> List[Dict[str, Any]]:
        try:
            import numpy as np_local
            audio_f32 = audio_data.astype(np_local.float32) / 32768.0

            try:
                import librosa
                mfccs = librosa.feature.mfcc(y=audio_f32, sr=sample_rate, n_mfcc=40)
                embedding = np_local.mean(mfccs, axis=1)
            except Exception:
                chunk_size = max(1, len(audio_f32) // 10)
                embedding = np_local.array([
                    float(np_local.sqrt(np_local.mean(audio_f32[i*chunk_size:(i+1)*chunk_size]**2)))
                    for i in range(10)
                ])

            norm = np_local.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return self._score_against_profiles(embedding)
        except Exception as e:
            self.logger.error(f"SpeakerIdentifier: MFCC fallback failed: {e}")
            return []

    def _score_against_profiles(self, embedding) -> List[Dict[str, Any]]:
        import numpy as np_local
        ts = datetime.utcnow().isoformat()
        results = []
        for speaker_id, known_emb in self.speaker_embeddings.items():
            known_norm = np_local.linalg.norm(known_emb)
            if known_norm > 0:
                known_emb = known_emb / known_norm
            similarity = float(np_local.dot(embedding, known_emb))
            similarity = max(0.0, min(1.0, similarity))

            if similarity >= self.confidence_threshold:
                results.append({
                    "speaker_id": speaker_id,
                    "name": self.speaker_names.get(speaker_id, "Unknown"),
                    "confidence": round(similarity, 4),
                    "timestamp": ts,
                    "backend": self._backend,
                })

        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:self.max_speakers]

    # ─── Speaker Management ───────────────────────────────────────────────────

    def add_speaker(self, speaker_id: str, name: str, audio_samples: List, sample_rate: int = None) -> bool:
        sr = sample_rate or self.sample_rate
        if not speaker_id or not speaker_id.strip():
            self.logger.error("SpeakerIdentifier.add_speaker: speaker_id cannot be empty")
            return False
        if len(audio_samples) < self.min_samples:
            self.logger.error(f"SpeakerIdentifier.add_speaker: need at least {self.min_samples} samples, got {len(audio_samples)}")
            return False

        try:
            import numpy as np_local
            embeddings = []
            for audio in audio_samples:
                if not isinstance(audio, np_local.ndarray):
                    audio = np_local.frombuffer(bytes(audio), dtype=np_local.int16)
                if self._backend == "resemblyzer":
                    audio_f32 = audio.astype(np_local.float32) / 32768.0
                    wav = self._preprocess_wav_fn(audio_f32, source_sr=sr)
                    emb = self.encoder.embed_utterance(wav)
                else:
                    audio_f32 = audio.astype(np_local.float32) / 32768.0
                    try:
                        import librosa
                        mfccs = librosa.feature.mfcc(y=audio_f32, sr=sr, n_mfcc=40)
                        emb = np_local.mean(mfccs, axis=1)
                    except Exception:
                        chunk_size = max(1, len(audio_f32) // 10)
                        emb = np_local.array([
                            float(np_local.sqrt(np_local.mean(audio_f32[i*chunk_size:(i+1)*chunk_size]**2)))
                            for i in range(10)
                        ])
                embeddings.append(emb)

            avg_embedding = np_local.mean(embeddings, axis=0)
            self.speaker_embeddings[speaker_id] = avg_embedding
            self.speaker_names[speaker_id] = name
            self._save_speaker_data()
            self.logger.info(f"SpeakerIdentifier: added profile for '{name}' (id={speaker_id})")
            return True
        except Exception as e:
            self.logger.error(f"SpeakerIdentifier.add_speaker failed: {e}")
            return False

    def remove_speaker(self, speaker_id: str) -> bool:
        if speaker_id not in self.speaker_embeddings:
            return False
        del self.speaker_embeddings[speaker_id]
        del self.speaker_names[speaker_id]
        self._save_speaker_data()
        self.logger.info(f"SpeakerIdentifier: removed profile {speaker_id}")
        return True

    def get_speaker_profiles(self) -> List[Dict[str, Any]]:
        return [
            {"speaker_id": sid, "name": self.speaker_names.get(sid, "Unknown")}
            for sid in self.speaker_embeddings
        ]

    # ─── Processing Thread ────────────────────────────────────────────────────

    def start_processing(self, callback: Optional[Callable] = None):
        if self.is_processing:
            return
        self.is_processing = True
        self.processing_thread = threading.Thread(
            target=self._processing_loop, args=(callback,), daemon=True
        )
        self.processing_thread.start()
        self.logger.info("SpeakerIdentifier: processing thread started")

    def stop_processing(self):
        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
            self.processing_thread = None

    def _processing_loop(self, callback: Optional[Callable]):
        while self.is_processing:
            try:
                item = self.processing_queue.get(timeout=1.0)
                results = asyncio.run(self.identify_speaker(item["audio"]))
                for r in results:
                    r["audio_timestamp"] = item["timestamp"]
                    if callback:
                        callback(r)
                self.processing_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"SpeakerIdentifier: processing loop error: {e}")

    def add_audio_data(self, audio_data, timestamp: float):
        if not self.is_processing:
            return
        self.processing_queue.put({"audio": audio_data, "timestamp": timestamp})

    def cleanup(self):
        self.stop_processing()
        self.encoder = None