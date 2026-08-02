"""
SpeechRecognizer — Production implementation with lazy imports.

Priority order:
  1. faster-whisper (OpenAI Whisper, optimised C++ backend)
  2. HuggingFace transformers Wav2Vec2 (facebook/wav2vec2-base-960h)
  3. Pure-Python energy + ZCR fallback (labels audio as speech/silence/noise)
"""

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


class SpeechRecognizer:
    """
    Multi-backend speech recognizer.
    Selects the best available backend automatically.
    Falls back to energy-based voice/silence classification when no ML model is available.
    """

    _WHISPER_MODEL_SIZE = "tiny"
    _WAV2VEC2_MODEL = "facebook/wav2vec2-base-960h"

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.asr_config = config.get("speech_recognition", {})

        self.sample_rate: int = config.get("audio", {}).get("sample_rate", 16000)
        self.language: str = self.asr_config.get("language", "en")
        self.confidence_threshold: float = float(
            self.asr_config.get("confidence_threshold", 0.5)
        )
        self._preferred_backend: str = self.asr_config.get("backend", "auto")

        self.transcription_history: List[Dict[str, Any]] = []
        self.max_history: int = int(self.asr_config.get("max_history", 500))

        self.processing_queue: queue.Queue = queue.Queue()
        self.is_processing: bool = False
        self.processing_thread: Optional[threading.Thread] = None

        self._whisper_model = None
        self._wav2vec2_model = None
        self._wav2vec2_processor = None
        self._backend: str = "energy"

        self._load_best_model()

    # ─── Model Loading ────────────────────────────────────────────────────────

    def _load_best_model(self):
        if self._preferred_backend in ("auto", "whisper"):
            self._load_whisper()
        if self._backend == "energy" and self._preferred_backend in ("auto", "wav2vec2"):
            self._load_wav2vec2()
        if self._backend == "energy":
            self.logger.warning(
                "SpeechRecognizer: no ASR model available — using energy-based fallback. "
                "Install faster-whisper or transformers for real transcription."
            )
        else:
            self.logger.info(f"SpeechRecognizer: using backend='{self._backend}'")

    def _load_whisper(self):
        model_size = self.asr_config.get("whisper_model_size", self._WHISPER_MODEL_SIZE)
        try:
            from faster_whisper import WhisperModel
            self._whisper_model = WhisperModel(model_size, device="auto", compute_type="int8")
            self._backend = "whisper"
            self.logger.info(f"SpeechRecognizer: loaded faster-whisper '{model_size}'")
        except Exception as e:
            self.logger.warning(f"SpeechRecognizer: faster-whisper load failed: {e}")

    def _load_wav2vec2(self):
        model_name = self.asr_config.get("wav2vec2_model", self._WAV2VEC2_MODEL)
        try:
            from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
            self._wav2vec2_processor = Wav2Vec2Processor.from_pretrained(model_name)
            self._wav2vec2_model = Wav2Vec2ForCTC.from_pretrained(model_name)
            self._backend = "wav2vec2"
            self.logger.info(f"SpeechRecognizer: loaded Wav2Vec2 '{model_name}'")
        except Exception as e:
            self.logger.warning(f"SpeechRecognizer: Wav2Vec2 load failed: {e}")

    # ─── Public API ───────────────────────────────────────────────────────────

    def transcribe(self, audio_data, sample_rate: int = None) -> Dict[str, Any]:
        sr = sample_rate or self.sample_rate
        try:
            if self._backend == "whisper":
                return self._transcribe_whisper(audio_data, sr)
            if self._backend == "wav2vec2":
                return self._transcribe_wav2vec2(audio_data, sr)
            return self._transcribe_energy(audio_data, sr)
        except Exception as e:
            self.logger.error(f"transcribe() failed: {e}")
            return self._error_result(str(e))

    def add_audio_data(self, audio_data, timestamp: float):
        if not self.is_processing:
            return
        self.processing_queue.put({"audio": audio_data, "timestamp": timestamp})

    def start_processing(self, callback: Optional[Callable] = None):
        if self.is_processing:
            return
        self.is_processing = True
        self.processing_thread = threading.Thread(
            target=self._processing_loop, args=(callback,), daemon=True
        )
        self.processing_thread.start()
        self.logger.info("SpeechRecognizer: processing thread started")

    def stop_processing(self):
        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
            self.processing_thread = None

    def cleanup(self):
        self.stop_processing()
        self._whisper_model = None
        self._wav2vec2_model = None
        self._wav2vec2_processor = None

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self.transcription_history)

    @property
    def backend(self) -> str:
        return self._backend

    # ─── Backend Implementations ──────────────────────────────────────────────

    def _transcribe_whisper(self, audio, sample_rate: int) -> Dict[str, Any]:
        import numpy as numpy_local
        audio_f32 = audio.astype(numpy_local.float32) / 32768.0
        segments, info = self._whisper_model.transcribe(
            audio_f32,
            language=self.language if self.language != "auto" else None,
            beam_size=int(self.asr_config.get("beam_size", 5)),
            vad_filter=bool(self.asr_config.get("vad_filter", True)),
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return self._make_result(text, 0.85, "whisper", info.language or self.language)

    def _transcribe_wav2vec2(self, audio, sample_rate: int) -> Dict[str, Any]:
        import numpy as numpy_local
        import torch
        audio_f32 = audio.astype(numpy_local.float32) / 32768.0
        if sample_rate != 16000:
            try:
                import torchaudio
                t = torch.tensor(audio_f32).unsqueeze(0)
                t = torchaudio.transforms.Resample(sample_rate, 16000)(t)
                audio_f32 = t.squeeze(0).numpy()
            except Exception:
                pass
        inputs = self._wav2vec2_processor(
            audio_f32, sampling_rate=16000, return_tensors="pt", padding=True
        )
        with torch.no_grad():
            logits = self._wav2vec2_model(inputs.input_values).logits
        predicted_ids = torch.argmax(logits, dim=-1)
        text = self._wav2vec2_processor.batch_decode(predicted_ids)[0].strip().lower()
        probs = torch.nn.functional.softmax(logits, dim=-1)
        confidence = round(float(probs.max().item()), 4)
        return self._make_result(text, confidence, "wav2vec2", self.language)

    def _transcribe_energy(self, audio, sample_rate: int) -> Dict[str, Any]:
        if audio is None or len(audio) == 0:
            return self._make_result("[silence]", 0.95, "energy", self.language)

        audio_f32 = [float(x) / 32768.0 for x in audio]
        rms = (sum(x ** 2 for x in audio_f32) / max(1, len(audio_f32))) ** 0.5

        silence_threshold = float(self.asr_config.get("silence_threshold", 0.01))
        noise_threshold = float(self.asr_config.get("noise_threshold", 0.05))

        if rms < silence_threshold:
            return self._make_result("[silence]", 0.92, "energy", self.language)

        if rms < noise_threshold:
            return self._make_result("[noise]", 0.70, "energy", self.language)

        zcr = sum(
            1 for i in range(1, len(audio_f32))
            if (audio_f32[i] >= 0) != (audio_f32[i - 1] >= 0)
        ) / max(1, len(audio_f32))

        if zcr > 0.30:
            return self._make_result("[noise]", 0.65, "energy", self.language)

        return self._make_result("[speech detected — install faster-whisper for transcription]", 0.60, "energy", self.language)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _make_result(self, text: str, confidence: float, backend: str, language: str) -> Dict[str, Any]:
        result = {
            "text": text,
            "confidence": round(confidence, 4),
            "backend": backend,
            "language": language,
            "timestamp": datetime.utcnow().isoformat(),
            "word_count": len(text.split()) if text and not text.startswith("[") else 0,
        }
        self._update_history(result)
        return result

    def _error_result(self, error: str) -> Dict[str, Any]:
        return {
            "text": "",
            "confidence": 0.0,
            "backend": self._backend,
            "language": self.language,
            "timestamp": datetime.utcnow().isoformat(),
            "error": error,
            "word_count": 0,
        }

    def _update_history(self, result: Dict[str, Any]):
        self.transcription_history.append(result)
        if len(self.transcription_history) > self.max_history:
            self.transcription_history = self.transcription_history[-self.max_history:]

    def _processing_loop(self, callback: Optional[Callable]):
        while self.is_processing:
            try:
                item = self.processing_queue.get(timeout=1.0)
                result = self.transcribe(item["audio"])
                result["audio_timestamp"] = item["timestamp"]
                if callback and result.get("confidence", 0) >= self.confidence_threshold:
                    callback(result)
                self.processing_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"SpeechRecognizer processing loop error: {e}")