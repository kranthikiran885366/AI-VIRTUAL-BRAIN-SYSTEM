"""
EarAgent — Production implementation.

Inherits from BaseAgent for full orchestrator lifecycle integration.
Coordinates all audio sub-components:
  AudioListener → SpeechRecognizer → SoundClassifier → SpeakerIdentifier
                                  → EmotionDetector → LanguageDetector → IntentDetector

Bug fixes vs original:
  - Now inherits BaseAgent (was standalone class)
  - execute_task() added for orchestrator dispatch
  - Config is a parsed dict, passed as dict to all sub-components (was passing path string)
  - YAML config file loaded once here, then shared — no repeated disk reads
  - start()/stop() renamed internally so they don't conflict with BaseAgent lifecycle
  - _speech_callback no longer passes result["audio"] (key doesn't exist in result dict)
  - Full cleanup on initialize() failure
"""

import asyncio
import json
import logging
import threading
import time as _time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from ..base_agent import BaseAgent  # type: ignore

try:
    from agents.ear_agent.audio_utils import coerce_audio_array
    from agents.ear_agent.audio_listener import AudioListener
    from agents.ear_agent.speech_recognizer import SpeechRecognizer
    from agents.ear_agent.sound_classifier import SoundClassifier
    from agents.ear_agent.speaker_id import SpeakerIdentifier
    from agents.ear_agent.emotion_detector import EmotionDetector
    from agents.ear_agent.language_detector import LanguageDetector
    from agents.ear_agent.intent_detector import IntentDetector
except ImportError:
    from .audio_utils import coerce_audio_array  # type: ignore
    from .audio_listener import AudioListener          # type: ignore
    from .speech_recognizer import SpeechRecognizer    # type: ignore
    from .sound_classifier import SoundClassifier      # type: ignore
    from .speaker_id import SpeakerIdentifier          # type: ignore
    from .emotion_detector import EmotionDetector      # type: ignore
    from .language_detector import LanguageDetector    # type: ignore
    from .intent_detector import IntentDetector        # type: ignore


class EarAgent(BaseAgent):
    """
    Ear Agent — real-time audio perception pipeline.

    Lifecycle:
      initialize()    → load config, instantiate sub-components
      _start_audio()  → start mic capture and all processors
      execute_task()  → orchestrator dispatch (transcribe, detect_emotion, etc.)
      shutdown()      → stop all processors, release mic
    """

    DEFAULT_CONFIG_PATH = "config/ear_agent_config.yaml"

    def __init__(
        self,
        agent_id: str = "ear_agent",
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ):
        super().__init__(agent_id=agent_id, agent_type="perception")

        # Config: explicit dict > yaml file > empty dict
        if config is not None:
            self.config = config
        else:
            self.config = self._load_yaml_config(config_path or self.DEFAULT_CONFIG_PATH)

        self.is_capturing: bool = False
        self.last_activity: Optional[float] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_history_length: int = int(self.config.get("max_history_length", 200))

        # Sub-components (instantiated in initialize())
        self.audio_listener: Optional[AudioListener] = None
        self.speech_recognizer: Optional[SpeechRecognizer] = None
        self.sound_classifier: Optional[SoundClassifier] = None
        self.speaker_identifier: Optional[SpeakerIdentifier] = None
        self.emotion_detector: Optional[EmotionDetector] = None
        self.language_detector: Optional[LanguageDetector] = None
        self.intent_detector: Optional[IntentDetector] = None

    # ─── Config ───────────────────────────────────────────────────────────────

    @staticmethod
    def _load_yaml_config(config_path: str) -> Dict[str, Any]:
        try:
            p = Path(config_path)
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logging.getLogger(__name__).warning(f"EarAgent: could not load {config_path}: {e}")
        return {}

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self):
        """Initialize all sub-components. Called by orchestrator on startup."""
        try:
            await super().initialize()
        except Exception:
            pass  # BaseAgent.initialize() may raise if broker unavailable

        if not hasattr(self, "logger") or self.logger is None:
            self.logger = logging.getLogger(f"EarAgent.{self.agent_id}")

        errors: List[str] = []

        def _safe_init(cls, name: str):
            try:
                return cls(self.config)
            except Exception as e:
                self.logger.warning(f"EarAgent: {name} init failed — {e}")
                errors.append(name)
                return None

        self.audio_listener    = _safe_init(AudioListener,    "AudioListener")
        self.speech_recognizer = _safe_init(SpeechRecognizer, "SpeechRecognizer")
        self.sound_classifier  = _safe_init(SoundClassifier,  "SoundClassifier")
        self.speaker_identifier= _safe_init(SpeakerIdentifier,"SpeakerIdentifier")
        self.emotion_detector  = _safe_init(EmotionDetector,  "EmotionDetector")
        self.language_detector = _safe_init(LanguageDetector, "LanguageDetector")
        self.intent_detector   = _safe_init(IntentDetector,   "IntentDetector")

        self.state.update({
            "utterances_processed": 0,
            "sounds_classified": 0,
            "emotions_detected": 0,
            "last_activity": None,
            "failed_components": errors,
            "audio_capturing": False,
        })
        self.logger.info(f"EarAgent initialized. Failed components: {errors or 'none'}")

    async def _update_state(self):
        try:
            await super()._update_state()
        except Exception:
            pass
        self.state["history_length"] = len(self.conversation_history)
        self.state["audio_capturing"] = self.is_capturing
        self.state["last_activity"] = self.last_activity

    # ─── Audio Capture Control ────────────────────────────────────────────────

    def _start_audio(self):
        """Start microphone capture and all processor threads."""
        if self.is_capturing:
            return
        self.is_capturing = True

        if self.audio_listener:
            try:
                self.audio_listener.start_listening(self._audio_callback)
            except Exception as e:
                self.logger.error(f"EarAgent: audio_listener.start_listening failed: {e}")

        for name, component, cb in [
            ("speech_recognizer",  self.speech_recognizer,  self._speech_callback),
            ("sound_classifier",   self.sound_classifier,   self._sound_callback),
            ("speaker_identifier", self.speaker_identifier, self._speaker_callback),
            ("emotion_detector",   self.emotion_detector,   self._emotion_callback),
            ("language_detector",  self.language_detector,  self._language_callback),
            ("intent_detector",    self.intent_detector,    self._intent_callback),
        ]:
            if component:
                try:
                    component.start_processing(cb)
                except Exception as e:
                    self.logger.error(f"EarAgent: {name}.start_processing failed: {e}")

        self.logger.info("EarAgent: audio capture started")

    def _stop_audio(self):
        """Stop all processors and release microphone."""
        if not self.is_capturing:
            return
        self.is_capturing = False

        if self.audio_listener:
            try:
                self.audio_listener.stop_listening()
            except Exception as e:
                self.logger.error(f"EarAgent: audio_listener.stop_listening failed: {e}")

        for name, component in [
            ("speech_recognizer",  self.speech_recognizer),
            ("sound_classifier",   self.sound_classifier),
            ("speaker_identifier", self.speaker_identifier),
            ("emotion_detector",   self.emotion_detector),
            ("language_detector",  self.language_detector),
            ("intent_detector",    self.intent_detector),
        ]:
            if component:
                try:
                    component.stop_processing()
                except Exception as e:
                    self.logger.error(f"EarAgent: {name}.stop_processing failed: {e}")

        self.logger.info("EarAgent: audio capture stopped")

    async def shutdown(self):
        """Orchestrator teardown hook."""
        self._stop_audio()
        await self._cleanup_components()

    async def _cleanup_components(self):
        for name, component in [
            ("audio_listener",    self.audio_listener),
            ("speech_recognizer", self.speech_recognizer),
            ("sound_classifier",  self.sound_classifier),
            ("speaker_identifier",self.speaker_identifier),
            ("emotion_detector",  self.emotion_detector),
            ("language_detector", self.language_detector),
            ("intent_detector",   self.intent_detector),
        ]:
            if component:
                try:
                    component.cleanup()
                except Exception as e:
                    self.logger.error(f"EarAgent: {name}.cleanup failed: {e}")

    # ─── Audio Callbacks ──────────────────────────────────────────────────────

    def _audio_callback(self, audio_data, timestamp: float):
        """Distribute raw audio to all processing components."""
        if not self.is_capturing:
            return
        self.last_activity = timestamp
        for component in [
            self.speech_recognizer, self.sound_classifier,
            self.speaker_identifier, self.emotion_detector,
            self.language_detector, self.intent_detector,
        ]:
            if component:
                try:
                    component.add_audio_data(audio_data, timestamp)
                except Exception as e:
                    self.logger.error(f"EarAgent: add_audio_data failed: {e}")

    def _speech_callback(self, result: Dict[str, Any]):
        if not self.is_capturing:
            return
        entry = {
            "type": "speech",
            "text": result.get("text", ""),
            "confidence": result.get("confidence", 0.0),
            "language": result.get("language", "unknown"),
            "backend": result.get("backend", "unknown"),
            "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
        }
        self._append_history(entry)
        self.state["utterances_processed"] = self.state.get("utterances_processed", 0) + 1

        # Feed recognised text to language and intent detectors
        text = result.get("text", "")
        if text and not text.startswith("["):
            if self.language_detector:
                try:
                    self.language_detector.add_text(text)
                except AttributeError:
                    pass  # older API — skip
            if self.intent_detector:
                try:
                    self.intent_detector.add_text(text)
                except AttributeError:
                    pass

    def _sound_callback(self, result: Dict[str, Any]):
        if not self.is_capturing:
            return
        self._append_history({
            "type": "sound",
            "sound": result.get("sound", ""),
            "confidence": result.get("confidence", 0.0),
            "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
        })
        self.state["sounds_classified"] = self.state.get("sounds_classified", 0) + 1

    def _speaker_callback(self, result: Dict[str, Any]):
        if not self.is_capturing:
            return
        self._append_history({
            "type": "speaker",
            "speaker_id": result.get("speaker_id", "unknown"),
            "name": result.get("name", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
        })

    def _emotion_callback(self, result: Dict[str, Any]):
        if not self.is_capturing:
            return
        self._append_history({
            "type": "emotion",
            "emotion": result.get("emotion", "neutral"),
            "confidence": result.get("confidence", 0.0),
            "scores": result.get("scores", {}),
            "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
        })
        self.state["emotions_detected"] = self.state.get("emotions_detected", 0) + 1

    def _language_callback(self, result: Dict[str, Any]):
        if not self.is_capturing:
            return
        self._append_history({
            "type": "language",
            "language": result.get("language", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
        })

    def _intent_callback(self, result: Dict[str, Any]):
        if not self.is_capturing:
            return
        self._append_history({
            "type": "intent",
            "intent": result.get("intent", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "entities": result.get("entities", []),
            "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
        })

    def _append_history(self, entry: Dict[str, Any]):
        self.conversation_history.append(entry)
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]

    # ─── execute_task (Orchestrator Dispatch) ─────────────────────────────────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Async task dispatch called by the orchestrator agent manager."""
        action = task.get("action", "")
        data   = task.get("input_data", {}) or {}

        if action == "start_listening":
            self._start_audio()
            return {"status": "started", "capturing": self.is_capturing}

        if action == "stop_listening":
            self._stop_audio()
            return {"status": "stopped", "capturing": self.is_capturing}

        if action in ("transcribe", "recognize_speech"):
            # Accepts raw audio bytes or numpy array in data["audio"]
            audio = data.get("audio")
            if audio is None:
                return {"error": "No audio data provided"}
            if self.speech_recognizer:
                sr = int(data.get("sample_rate", self.config.get("audio", {}).get("sample_rate", 16000)))
                audio = coerce_audio_array(audio)
                return self.speech_recognizer.transcribe(audio, sample_rate=sr)
            return {"error": "SpeechRecognizer not available"}

        if action == "detect_emotion":
            audio = data.get("audio")
            if audio is None:
                return {"error": "No audio data provided"}
            if self.emotion_detector:
                audio = coerce_audio_array(audio)
                results = await self.emotion_detector.detect_emotion(audio)
                return {"emotions": results, "top": results[0] if results else None}
            return {"error": "EmotionDetector not available"}

        if action == "detect_intent":
            text = data.get("text", "")
            audio = data.get("audio")
            if self.intent_detector:
                if text:
                    results = await self.intent_detector.detect_from_text(text)
                elif audio is not None:
                    audio = coerce_audio_array(audio)
                    results = await self.intent_detector.detect_intent(audio)
                else:
                    return {"error": "Provide either text or audio"}
                return {"intents": results, "top": results[0] if results else None}
            return {"error": "IntentDetector not available"}

        if action == "detect_language":
            text = data.get("text", "")
            audio = data.get("audio")
            if self.language_detector:
                if text:
                    results = await self.language_detector.detect_from_text(text)
                elif audio is not None:
                    audio = coerce_audio_array(audio)
                    results = await self.language_detector.detect_language(audio)
                else:
                    return {"error": "Provide either text or audio"}
                return {"languages": results, "top": results[0] if results else None}
            return {"error": "LanguageDetector not available"}

        if action == "classify_sound":
            audio = data.get("audio")
            if audio is None:
                return {"error": "No audio data provided"}
            if self.sound_classifier:
                audio = coerce_audio_array(audio)
                results = await self.sound_classifier.classify_sound(audio)
                return {"sounds": results, "top": results[0] if results else None}
            return {"error": "SoundClassifier not available"}

        if action == "identify_speaker":
            audio = data.get("audio")
            if audio is None:
                return {"error": "No audio data provided"}
            if self.speaker_identifier:
                audio = coerce_audio_array(audio)
                results = await self.speaker_identifier.identify_speaker(audio)
                return {"speakers": results, "top": results[0] if results else None}
            return {"error": "SpeakerIdentifier not available"}

        if action == "add_speaker":
            if self.speaker_identifier:
                samples = [coerce_audio_array(s) for s in data.get("audio_samples", [])]
                success = self.speaker_identifier.add_speaker(
                    data.get("speaker_id", ""),
                    data.get("name", "Unknown"),
                    samples,
                )
                return {"success": success}
            return {"error": "SpeakerIdentifier not available"}

        if action == "get_history":
            limit = data.get("limit")
            return {"history": self.get_conversation_history(limit)}

        if action == "clear_history":
            self.conversation_history.clear()
            return {"status": "cleared"}

        if action == "get_status":
            return await self.get_status()

        if action == "get_health":
            return await self.get_health()

        if action == "get_devices":
            if self.audio_listener:
                return {"devices": self.audio_listener.get_audio_devices()}
            return {"devices": []}

        if action == "set_device":
            device_index = data.get("device_index")
            if device_index is None:
                return {"error": "device_index required"}
            if self.audio_listener:
                self.audio_listener.set_device(int(device_index))
                return {"status": "device set", "device_index": device_index}
            return {"error": "AudioListener not available"}

        # Default: echo back status
        return await self.get_status()

    # ─── Public API ───────────────────────────────────────────────────────────

    def get_conversation_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if limit is None:
            return list(self.conversation_history)
        return self.conversation_history[-limit:]

    def get_agent_status(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "is_capturing": self.is_capturing,
            "last_activity": self.last_activity,
            "history_length": len(self.conversation_history),
            "components": {
                "audio_listener":    self.audio_listener is not None,
                "speech_recognizer": self.speech_recognizer is not None,
                "sound_classifier":  self.sound_classifier is not None,
                "speaker_identifier":self.speaker_identifier is not None,
                "emotion_detector":  self.emotion_detector is not None,
                "language_detector": self.language_detector is not None,
                "intent_detector":   self.intent_detector is not None,
            },
            "speech_backend": (
                self.speech_recognizer.backend if self.speech_recognizer else "none"
            ),
        }

    async def get_health(self) -> Dict[str, Any]:
        status = self.get_agent_status()
        healthy = any(status["components"].values())
        return {
            "healthy": healthy,
            "agent_id": self.agent_id,
            "components": status["components"],
            "timestamp": datetime.utcnow().isoformat(),
        }


# ─── Standalone entry-point ────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    async def _run():
        agent = EarAgent()
        try:
            await agent.initialize()
            agent._start_audio()
            print("EarAgent running for 10 s — speak into your microphone …")
            await asyncio.sleep(10)
            print("\nStatus:", json.dumps(agent.get_agent_status(), indent=2))
            print("\nHistory:", json.dumps(agent.get_conversation_history(10), indent=2))
        finally:
            await agent.shutdown()

    asyncio.run(_run())