"""
IntentDetector — Production implementation with lazy imports.

Backends (in priority order):
  1. Rasa NLU HTTP API  — calls running Rasa server /model/parse
  2. HuggingFace zero-shot classification (cross-encoder/nli-base-chunk-v1)
  3. Keyword-match rule engine (no ML dependency)
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

_DEFAULT_INTENTS = [
    "greeting", "farewell", "help_request", "information_request",
    "task_creation", "task_query", "memory_recall", "memory_store",
    "emotion_expression", "affirmation", "negation", "question",
    "command", "feedback", "complaint",
]

_KEYWORD_MAP: Dict[str, List[str]] = {
    "greeting":           ["hello", "hi", "hey", "good morning", "good evening", "howdy"],
    "farewell":           ["bye", "goodbye", "see you", "later", "take care"],
    "help_request":       ["help", "assist", "support", "how do i", "can you"],
    "information_request":["what", "when", "where", "who", "explain", "tell me"],
    "task_creation":      ["create", "add", "set", "make", "schedule", "remind"],
    "task_query":         ["list", "show", "what tasks", "my tasks", "pending"],
    "memory_recall":      ["remember", "recall", "what did", "last time"],
    "memory_store":       ["remember this", "don't forget", "save", "note that"],
    "emotion_expression": ["feel", "feeling", "i am", "i'm sad", "happy", "anxious"],
    "affirmation":        ["yes", "yeah", "sure", "ok", "okay", "correct", "right"],
    "negation":           ["no", "nope", "not", "never", "don't", "won't"],
    "question":           ["?", "could you", "would you", "is it", "are you"],
    "command":            ["do", "run", "execute", "start", "stop", "open", "close"],
    "feedback":           ["good job", "well done", "nice", "great", "perfect"],
    "complaint":          ["wrong", "bad", "error", "failed", "broken", "issue"],
}


class IntentDetector:
    """Detects user intent from text or raw audio."""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        intent_cfg = config.get("intent_detection", {})

        self.model_name: str = intent_cfg.get("model", "rasa")
        self.supported_intents: List[str] = intent_cfg.get("supported_intents", _DEFAULT_INTENTS)
        self.confidence_threshold: float = float(intent_cfg.get("confidence_threshold", 0.5))
        self.rasa_endpoint: str = intent_cfg.get("rasa_endpoint", "http://localhost:5005")
        self.sample_rate: int = int(config.get("audio", {}).get("sample_rate", 16000))

        self._backend: str = "keyword"
        self._zsc_pipeline = None

        self.processing_queue: queue.Queue = queue.Queue()
        self._text_queue: queue.Queue = queue.Queue()
        self.is_processing: bool = False
        self.processing_thread: Optional[threading.Thread] = None

        self._initialize_model()

    # ─── Model Initialization ─────────────────────────────────────────────────

    def _initialize_model(self):
        if self.model_name in ("auto", "transformers", "zsc"):
            try:
                from transformers import pipeline as hf_pipeline
                self._zsc_pipeline = hf_pipeline(
                    "zero-shot-classification",
                    model="cross-encoder/nli-base-chunk-v1",
                    device=-1,
                )
                self._backend = "zsc"
                self.logger.info("IntentDetector: loaded zero-shot classification model")
                return
            except Exception as e:
                self.logger.warning(f"IntentDetector: ZSC model load failed — {e}")

        if self.model_name == "rasa":
            self._backend = "rasa"
            self.logger.info(f"IntentDetector: using Rasa API at {self.rasa_endpoint}")
            return

        self._backend = "keyword"
        self.logger.info("IntentDetector: using keyword-match fallback")

    # ─── Main Detection APIs ──────────────────────────────────────────────────

    async def detect_from_text(self, text: str) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []
        text = text.strip()
        try:
            if self._backend == "rasa":
                return await self._detect_rasa(text)
            if self._backend == "zsc":
                return self._detect_zsc(text)
            return self._detect_keyword(text)
        except Exception as e:
            self.logger.error(f"IntentDetector.detect_from_text failed: {e}")
            return self._detect_keyword(text)

    async def detect_intent(self, audio_data, sample_rate: int = None) -> List[Dict[str, Any]]:
        self.logger.warning("IntentDetector.detect_intent called with raw audio — transcribe first via SpeechRecognizer")
        return []

    def add_text(self, text: str):
        if self.is_processing and text:
            self._text_queue.put({"text": text, "timestamp": datetime.utcnow().isoformat()})

    def add_audio_data(self, audio_data, timestamp: float):
        if self.is_processing:
            self.processing_queue.put({"audio": audio_data, "timestamp": timestamp})

    # ─── Rasa Backend ─────────────────────────────────────────────────────────

    async def _detect_rasa(self, text: str) -> List[Dict[str, Any]]:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.rasa_endpoint}/model/parse",
                    json={"text": text},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status != 200:
                        raise ValueError(f"Rasa API returned {response.status}: {await response.text()}")
                    result = await response.json()

            ts = datetime.utcnow().isoformat()
            results: List[Dict[str, Any]] = []
            for intent in result.get("intent_ranking", []):
                name = intent.get("name", "")
                confidence = round(float(intent.get("confidence", 0)), 4)
                if confidence >= self.confidence_threshold:
                    results.append({
                        "intent": name,
                        "confidence": confidence,
                        "entities": result.get("entities", []),
                        "timestamp": ts,
                        "backend": "rasa",
                    })
            results.sort(key=lambda x: x["confidence"], reverse=True)
            return results
        except Exception as e:
            self.logger.warning(f"IntentDetector: Rasa API failed — {e}. Falling back to keyword.")
            return self._detect_keyword(text)

    # ─── Zero-Shot Classification Backend ─────────────────────────────────────

    def _detect_zsc(self, text: str) -> List[Dict[str, Any]]:
        try:
            candidate_labels = self.supported_intents or _DEFAULT_INTENTS
            result = self._zsc_pipeline(text, candidate_labels, multi_label=True)
            ts = datetime.utcnow().isoformat()
            results = []
            for label, score in zip(result["labels"], result["scores"]):
                confidence = round(float(score), 4)
                if confidence >= self.confidence_threshold:
                    results.append({
                        "intent": label,
                        "confidence": confidence,
                        "entities": [],
                        "timestamp": ts,
                        "backend": "zsc",
                    })
            return results
        except Exception as e:
            self.logger.error(f"IntentDetector: ZSC inference failed: {e}")
            return self._detect_keyword(text)

    # ─── Keyword-Match Fallback ───────────────────────────────────────────────

    def _detect_keyword(self, text: str) -> List[Dict[str, Any]]:
        lower = text.lower()
        ts = datetime.utcnow().isoformat()
        hits: Dict[str, int] = {}
        for intent, keywords in _KEYWORD_MAP.items():
            if intent not in (self.supported_intents or _DEFAULT_INTENTS):
                continue
            count = sum(1 for kw in keywords if kw in lower)
            if count > 0:
                hits[intent] = count

        if not hits:
            return [{
                "intent": "unknown",
                "confidence": 0.30,
                "entities": [],
                "timestamp": ts,
                "backend": "keyword",
            }]

        total = sum(hits.values())
        results = [
            {
                "intent": intent,
                "confidence": round(min(0.90, 0.40 + count / total * 0.50), 4),
                "entities": self._extract_entities(text),
                "timestamp": ts,
                "backend": "keyword",
            }
            for intent, count in sorted(hits.items(), key=lambda x: x[1], reverse=True)
        ]
        return results

    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        import re
        entities = []
        for m in re.finditer(r'\b(\d{1,2}:\d{2}(?:\s?[ap]m)?)\b', text, re.IGNORECASE):
            entities.append({"entity": "time", "value": m.group(), "start": m.start(), "end": m.end()})
        for m in re.finditer(r'\b\d+\b', text):
            entities.append({"entity": "number", "value": m.group(), "start": m.start(), "end": m.end()})
        for m in re.finditer(r'"([^"]+)"', text):
            entities.append({"entity": "quoted", "value": m.group(1), "start": m.start(), "end": m.end()})
        return entities

    # ─── Processing Thread ────────────────────────────────────────────────────

    def start_processing(self, callback: Optional[Callable] = None):
        if self.is_processing:
            return
        self.is_processing = True
        self.processing_thread = threading.Thread(
            target=self._processing_loop, args=(callback,), daemon=True
        )
        self.processing_thread.start()
        self.logger.info("IntentDetector: processing thread started")

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
                self.logger.error(f"IntentDetector: processing loop error: {e}")

    def get_supported_intents(self) -> List[str]:
        return list(self.supported_intents)

    def set_confidence_threshold(self, threshold: float):
        if not 0 <= threshold <= 1:
            raise ValueError("Confidence threshold must be between 0 and 1")
        self.confidence_threshold = threshold

    def cleanup(self):
        self.stop_processing()
        self._zsc_pipeline = None