"""
LanguageDetector — Production implementation with lazy imports.

Backends (in priority order):
  1. FastText  — lid.176.bin (176-language model, downloaded automatically if missing)
  2. langdetect — Python port of Google's language-detection library
  3. Heuristic character-set detector (Latin / CJK / Arabic / Cyrillic / Devanagari)
"""

import asyncio
import logging
import queue
import re
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

_DEFAULT_LANGUAGES = [
    "en", "es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja",
    "ko", "ar", "hi", "tr", "pl", "sv", "da", "fi", "no", "cs",
]

_CHARSET_PATTERNS = [
    ("zh",  re.compile(r"[\u4e00-\u9fff]")),
    ("ja",  re.compile(r"[\u3040-\u30ff]")),
    ("ko",  re.compile(r"[\uac00-\ud7af]")),
    ("ar",  re.compile(r"[\u0600-\u06ff]")),
    ("ru",  re.compile(r"[\u0400-\u04ff]")),
    ("hi",  re.compile(r"[\u0900-\u097f]")),
]


class LanguageDetector:
    """Detects spoken/written language from text or audio."""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        lang_cfg = config.get("language_detection", {})

        self.model_name: str = lang_cfg.get("model", "fasttext")
        self.supported_languages: List[str] = lang_cfg.get("supported_languages", _DEFAULT_LANGUAGES)
        self.confidence_threshold: float = float(lang_cfg.get("confidence_threshold", 0.50))
        self.min_text_length: int = int(lang_cfg.get("min_text_length", 3))
        self.sample_rate: int = int(config.get("audio", {}).get("sample_rate", 16000))
        self._fasttext_model_path: str = lang_cfg.get("fasttext_model_path", "models/lid.176.bin")

        self._backend: str = "heuristic"
        self._ft_model = None

        self.processing_queue: queue.Queue = queue.Queue()
        self._text_queue: queue.Queue = queue.Queue()
        self.is_processing: bool = False
        self.processing_thread: Optional[threading.Thread] = None

        self._initialize_model()

    # ─── Model Initialization ─────────────────────────────────────────────────

    def _initialize_model(self):
        if self.model_name in ("fasttext", "auto") and _HAS_NUMPY:
            try:
                import fasttext
                model_path = Path(self._fasttext_model_path)
                if not model_path.exists():
                    self.logger.info("LanguageDetector: downloading FastText LID model …")
                    fasttext.util.download_model("lid.176.bin", if_exists="ignore")
                    model_path = Path("lid.176.bin")
                self._ft_model = fasttext.load_model(str(model_path))
                self._backend = "fasttext"
                self.logger.info("LanguageDetector: loaded FastText LID model")
                return
            except Exception as e:
                self.logger.warning(f"LanguageDetector: FastText load failed — {e}")

        try:
            from langdetect import detect as _langdetect_detect, detect_langs as _langdetect_langs
            self._backend = "langdetect"
            self.logger.info("LanguageDetector: using langdetect")
            return
        except Exception:
            pass

        self._backend = "heuristic"
        self.logger.info("LanguageDetector: using character-set heuristic")

    # ─── Public APIs ──────────────────────────────────────────────────────────

    async def detect_from_text(self, text: str) -> List[Dict[str, Any]]:
        if not text or len(text.strip()) < self.min_text_length:
            return []
        try:
            if self._backend == "fasttext":
                return self._detect_fasttext(text)
            if self._backend == "langdetect":
                return self._detect_langdetect(text)
            return self._detect_heuristic(text)
        except Exception as e:
            self.logger.error(f"LanguageDetector.detect_from_text failed: {e}")
            return self._detect_heuristic(text)

    async def detect_language(self, audio_data, sample_rate: int = None) -> List[Dict[str, Any]]:
        self.logger.warning("LanguageDetector.detect_language: raw audio requires transcription.")
        return []

    def add_text(self, text: str):
        if self.is_processing and text:
            self._text_queue.put({"text": text, "timestamp": datetime.utcnow().isoformat()})

    def add_audio_data(self, audio_data, timestamp: float):
        if self.is_processing:
            self.processing_queue.put({"audio": audio_data, "timestamp": timestamp})

    # ─── FastText Backend ─────────────────────────────────────────────────────

    def _detect_fasttext(self, text: str) -> List[Dict[str, Any]]:
        try:
            k = min(len(self.supported_languages), 5)
            labels, probs = self._ft_model.predict(text.replace("\n", " "), k=k)
            ts = datetime.utcnow().isoformat()
            results = []
            for label, prob in zip(labels, probs):
                lang = label.replace("__label__", "")
                confidence = round(float(prob), 4)
                if confidence >= self.confidence_threshold:
                    results.append({
                        "language": lang,
                        "confidence": confidence,
                        "timestamp": ts,
                        "backend": "fasttext",
                    })
            results.sort(key=lambda x: x["confidence"], reverse=True)
            return results
        except Exception as e:
            self.logger.error(f"LanguageDetector: FastText inference failed: {e}")
            return self._detect_heuristic(text)

    # ─── langdetect Backend ───────────────────────────────────────────────────

    def _detect_langdetect(self, text: str) -> List[Dict[str, Any]]:
        try:
            from langdetect import detect_langs as _langdetect_langs
            langs = _langdetect_langs(text)
            ts = datetime.utcnow().isoformat()
            results = []
            for lang_prob in langs:
                lang = str(lang_prob.lang)
                confidence = round(float(lang_prob.prob), 4)
                if confidence >= self.confidence_threshold:
                    results.append({
                        "language": lang,
                        "confidence": confidence,
                        "timestamp": ts,
                        "backend": "langdetect",
                    })
            return results
        except Exception as e:
            self.logger.error(f"LanguageDetector: langdetect failed: {e}")
            return self._detect_heuristic(text)

    # ─── Heuristic Character-Set Backend ─────────────────────────────────────

    def _detect_heuristic(self, text: str) -> List[Dict[str, Any]]:
        ts = datetime.utcnow().isoformat()
        for lang, pattern in _CHARSET_PATTERNS:
            if pattern.search(text):
                return [{"language": lang, "confidence": 0.80, "timestamp": ts, "backend": "heuristic"}]
        return [{"language": "en", "confidence": 0.60, "timestamp": ts, "backend": "heuristic"}]

    # ─── Processing Thread ────────────────────────────────────────────────────

    def start_processing(self, callback: Optional[Callable] = None):
        if self.is_processing:
            return
        self.is_processing = True
        self.processing_thread = threading.Thread(
            target=self._processing_loop, args=(callback,), daemon=True
        )
        self.processing_thread.start()
        self.logger.info("LanguageDetector: processing thread started")

    def stop_processing(self):
        self.is_processing = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
            self.processing_thread = None

    def _processing_loop(self, callback: Optional[Callable]):
        while self.is_processing:
            try:
                item = self._text_queue.get(timeout=0.5)
                results = asyncio.run(self.detect_from_text(item["text"]))
                for r in results:
                    r["text"] = item["text"]
                    if callback:
                        callback(r)
                self._text_queue.task_done()
                continue
            except queue.Empty:
                pass
            try:
                self.processing_queue.get(timeout=0.5)
                self.processing_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                self.logger.error(f"LanguageDetector: processing loop error: {e}")

    def get_supported_languages(self) -> List[str]:
        return list(self.supported_languages)

    def set_confidence_threshold(self, threshold: float):
        if not 0 <= threshold <= 1:
            raise ValueError("Confidence threshold must be between 0 and 1")
        self.confidence_threshold = threshold

    def cleanup(self):
        self.stop_processing()
        self._ft_model = None