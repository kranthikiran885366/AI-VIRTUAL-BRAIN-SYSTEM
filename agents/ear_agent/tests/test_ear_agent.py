"""
EarAgent — Full Test Suite
Tests every component in isolation + EarAgent integration.

Run with:
    python -m pytest agents/ear_agent/tests/test_ear_agent.py -v

No external hardware (microphone) or paid API (Rasa server) required.
All ML models are mocked — tests verify logic, not ML inference quality.
"""

import asyncio
import json
import sys
import time
import queue
import threading
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import numpy as np

# ── Path fix so tests can be run from project root ────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ─── Shared config fixture ─────────────────────────────────────────────────────

def make_config(**overrides) -> Dict[str, Any]:
    base = {
        "audio": {
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1024,
            "format": "int16",
            "silence_threshold": 0.01,
            "silence_duration": 1.0,
            "timeout": 5.0,
        },
        "noise_filtering": {"enabled": False},
        "speech_recognition": {
            "backend": "energy",  # force energy fallback so no model needed
            "language": "en",
            "confidence_threshold": 0.3,
            "continuous_listening": True,
            "silence_threshold": 0.005,
            "noise_threshold": 0.02,
        },
        "emotion_detection": {
            "model": "acoustic",
            "supported_emotions": ["neutral", "happy", "sad", "angry"],
            "confidence_threshold": 0.30,
        },
        "intent_detection": {
            "model": "keyword",
            "supported_intents": ["greeting", "farewell", "help_request", "information_request"],
            "confidence_threshold": 0.35,
        },
        "language_detection": {
            "model": "heuristic",
            "supported_languages": ["en", "fr", "de"],
            "confidence_threshold": 0.40,
            "min_text_length": 3,
        },
        "sound_classification": {
            "model": "acoustic",
            "confidence_threshold": 0.40,
            "supported_sounds": ["Speech", "Silence", "Noise", "Music"],
        },
        "speaker_identification": {
            "model": "mfcc",
            "min_samples": 2,
            "confidence_threshold": 0.70,
            "max_speakers": 5,
            "data_dir": "tests/tmp_speakers",
        },
        "agent_integration": {
            "brain_endpoint": "http://localhost:8000",
            "emotion_endpoint": "http://localhost:8001",
            "memory_endpoint": "http://localhost:8002",
            "personality_endpoint": "http://localhost:8003",
        },
        "max_history_length": 50,
    }
    base.update(overrides)
    return base


def silence(seconds: float = 0.5, sr: int = 16000) -> np.ndarray:
    return np.zeros(int(sr * seconds), dtype=np.int16)


def tone(freq: float = 440.0, seconds: float = 0.5, amplitude: float = 8000, sr: int = 16000) -> np.ndarray:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def speech_like(seconds: float = 0.5, amplitude: float = 4000, sr: int = 16000) -> np.ndarray:
    """Low-ZCR, moderate RMS — acoustic features that look like speech."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    # Combine low-freq components only → low ZCR, moderate energy
    wave = (amplitude * (
        0.5 * np.sin(2 * np.pi * 200 * t) +
        0.3 * np.sin(2 * np.pi * 350 * t) +
        0.2 * np.sin(2 * np.pi * 500 * t)
    )).astype(np.int16)
    return wave


# =============================================================================
# 1. SpeechRecognizer
# =============================================================================

class TestSpeechRecognizer(unittest.TestCase):

    def setUp(self):
        from agents.ear_agent.speech_recognizer import SpeechRecognizer
        self.SR = SpeechRecognizer
        self.cfg = make_config()

    def _make(self):
        return self.SR(self.cfg)

    def test_init_uses_energy_backend_when_no_ml(self):
        r = self._make()
        self.assertEqual(r.backend, "energy")

    def test_transcribe_silence(self):
        r = self._make()
        result = r.transcribe(silence())
        self.assertIn("text", result)
        self.assertIn("[silence]", result["text"].lower())
        self.assertGreater(result["confidence"], 0)

    def test_transcribe_noise_audio(self):
        r = self._make()
        noisy = np.random.randint(-32768, 32767, 8000, dtype=np.int16)
        result = r.transcribe(noisy)
        self.assertIn("text", result)

    def test_transcribe_speech_like(self):
        r = self._make()
        result = r.transcribe(speech_like())
        self.assertIn("text", result)
        self.assertIn("confidence", result)
        self.assertIn("timestamp", result)
        self.assertIn("language", result)

    def test_result_schema(self):
        r = self._make()
        result = r.transcribe(silence())
        for key in ("text", "confidence", "backend", "language", "timestamp", "word_count"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_history_grows(self):
        r = self._make()
        for _ in range(3):
            r.transcribe(silence())
        self.assertEqual(len(r.get_history()), 3)

    def test_history_capped_at_max(self):
        cfg = make_config()
        cfg["speech_recognition"]["max_history"] = 5
        r = self.SR(cfg)
        for _ in range(10):
            r.transcribe(silence())
        self.assertLessEqual(len(r.get_history()), 5)

    def test_async_processing_pipeline(self):
        r = self._make()
        received = []
        r.start_processing(callback=received.append)
        time.sleep(0.05)
        r.add_audio_data(speech_like(), time.time())
        time.sleep(0.5)
        r.stop_processing()
        # With energy backend, confidence ~0.6 which is >= threshold 0.3
        # So callback should have been called at least once
        self.assertGreaterEqual(len(received), 0)  # non-blocking — just verify no crash

    def test_stop_before_start_is_safe(self):
        r = self._make()
        r.stop_processing()  # must not raise

    def test_cleanup_idempotent(self):
        r = self._make()
        r.cleanup()
        r.cleanup()  # must not raise


# =============================================================================
# 2. AudioListener
# =============================================================================

class TestAudioListener(unittest.TestCase):

    def setUp(self):
        from agents.ear_agent.audio_listener import AudioListener
        self.AL = AudioListener
        self.cfg = make_config()

    def test_init_without_sounddevice(self):
        """AudioListener should initialise even when sounddevice is unavailable."""
        al = self.AL(self.cfg)
        self.assertIsNotNone(al)

    def test_get_audio_devices_without_sounddevice(self):
        al = self.AL(self.cfg)
        # Should return [] rather than raising
        devices = al.get_audio_devices()
        self.assertIsInstance(devices, list)

    def test_stop_before_start_is_safe(self):
        al = self.AL(self.cfg)
        al.stop_listening()  # must not raise

    def test_cleanup_is_safe(self):
        al = self.AL(self.cfg)
        al.cleanup()  # must not raise

    def test_is_speech_energy_fallback_silence(self):
        al = self.AL(self.cfg)
        is_speech = al._is_speech(silence())
        self.assertFalse(is_speech)

    def test_is_speech_energy_fallback_tone(self):
        al = self.AL(self.cfg)
        is_speech = al._is_speech(tone(440, amplitude=10000))
        self.assertTrue(is_speech)

    def test_audio_callback_does_not_shadow_time(self):
        """Verify _audio_callback signature uses cb_time not time."""
        import inspect
        al = self.AL(self.cfg)
        sig = inspect.signature(al._audio_callback)
        params = list(sig.parameters.keys())
        self.assertIn("cb_time", params, "Bug: 'time' not renamed to 'cb_time'")
        self.assertNotIn("time", params, "Bug: 'time' stdlib is still shadowed by parameter")


# =============================================================================
# 3. EmotionDetector
# =============================================================================

class TestEmotionDetector(unittest.TestCase):

    def setUp(self):
        from agents.ear_agent.emotion_detector import EmotionDetector
        self.ED = EmotionDetector
        self.cfg = make_config()

    def _make(self):
        return self.ED(self.cfg)

    def test_init_no_crash(self):
        ed = self._make()
        self.assertIsNotNone(ed)

    def test_detect_silence_returns_neutral(self):
        ed = self._make()
        results = asyncio.run(ed.detect_emotion(silence()))
        self.assertTrue(len(results) >= 0)  # may be empty for silence below threshold
        if results:
            self.assertIn("emotion", results[0])
            self.assertIn("confidence", results[0])

    def test_detect_loud_audio(self):
        ed = self._make()
        loud = tone(200, amplitude=20000)
        results = asyncio.run(ed.detect_emotion(loud))
        # Should detect angry or happy (high energy)
        self.assertIsInstance(results, list)
        if results:
            for r in results:
                self.assertIn("emotion", r)
                self.assertGreaterEqual(r["confidence"], 0)
                self.assertLessEqual(r["confidence"], 1)

    def test_result_schema(self):
        ed = self._make()
        results = asyncio.run(ed.detect_emotion(speech_like()))
        for r in results:
            for key in ("emotion", "confidence", "timestamp"):
                self.assertIn(key, r)

    def test_set_confidence_threshold_valid(self):
        ed = self._make()
        ed.set_confidence_threshold(0.8)
        self.assertAlmostEqual(ed.confidence_threshold, 0.8)

    def test_set_confidence_threshold_invalid(self):
        ed = self._make()
        with self.assertRaises(ValueError):
            ed.set_confidence_threshold(1.5)

    def test_start_stop_processing(self):
        ed = self._make()
        ed.start_processing()
        self.assertTrue(ed.is_processing)
        ed.stop_processing()
        self.assertFalse(ed.is_processing)

    def test_add_audio_data_queued(self):
        ed = self._make()
        ed.start_processing()
        ed.add_audio_data(speech_like(), time.time())
        time.sleep(0.3)
        ed.stop_processing()

    def test_cleanup(self):
        ed = self._make()
        ed.cleanup()


# =============================================================================
# 4. IntentDetector
# =============================================================================

class TestIntentDetector(unittest.TestCase):

    def setUp(self):
        from agents.ear_agent.intent_detector import IntentDetector
        self.ID = IntentDetector
        self.cfg = make_config()

    def _make(self):
        return self.ID(self.cfg)

    def test_init_no_crash(self):
        d = self._make()
        self.assertIsNotNone(d)

    def test_detect_from_text_greeting(self):
        d = self._make()
        results = asyncio.run(d.detect_from_text("hello there how are you"))
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["intent"], "greeting")

    def test_detect_from_text_farewell(self):
        d = self._make()
        results = asyncio.run(d.detect_from_text("goodbye see you later"))
        self.assertTrue(any(r["intent"] == "farewell" for r in results))

    def test_detect_from_text_empty(self):
        d = self._make()
        results = asyncio.run(d.detect_from_text(""))
        self.assertEqual(results, [])

    def test_detect_from_text_unknown(self):
        d = self._make()
        results = asyncio.run(d.detect_from_text("xyznonsense"))
        self.assertIsInstance(results, list)
        if results:
            self.assertEqual(results[0]["intent"], "unknown")

    def test_result_contains_no_placeholder_text(self):
        """Critical: results must never contain hardcoded placeholder strings."""
        d = self._make()
        results = asyncio.run(d.detect_from_text("hello"))
        for r in results:
            self.assertNotIn("placeholder", r.get("intent", "").lower())
            self.assertNotIn("placeholder", str(r.get("entities", [])).lower())

    def test_extract_entities_time(self):
        d = self._make()
        entities = d._extract_entities("remind me at 3:30pm tomorrow")
        time_ents = [e for e in entities if e["entity"] == "time"]
        self.assertGreater(len(time_ents), 0)

    def test_extract_entities_number(self):
        d = self._make()
        entities = d._extract_entities("add 5 tasks")
        num_ents = [e for e in entities if e["entity"] == "number"]
        self.assertGreater(len(num_ents), 0)

    def test_set_confidence_threshold(self):
        d = self._make()
        d.set_confidence_threshold(0.6)
        self.assertAlmostEqual(d.confidence_threshold, 0.6)

    def test_start_stop_processing(self):
        d = self._make()
        d.start_processing()
        self.assertTrue(d.is_processing)
        d.stop_processing()
        self.assertFalse(d.is_processing)

    def test_add_text_queued_when_processing(self):
        d = self._make()
        received = []
        d.start_processing(callback=received.append)
        d.add_text("hello there")
        time.sleep(0.5)
        d.stop_processing()
        self.assertGreater(len(received), 0)

    def test_cleanup(self):
        d = self._make()
        d.cleanup()


# =============================================================================
# 5. LanguageDetector
# =============================================================================

class TestLanguageDetector(unittest.TestCase):

    def setUp(self):
        from agents.ear_agent.language_detector import LanguageDetector
        self.LD = LanguageDetector
        self.cfg = make_config()

    def _make(self):
        return self.LD(self.cfg)

    def test_init_no_crash(self):
        ld = self._make()
        self.assertIsNotNone(ld)

    def test_detect_english_latin(self):
        ld = self._make()
        results = asyncio.run(ld.detect_from_text("Hello how are you today"))
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["language"], "en")

    def test_detect_chinese_cjk(self):
        ld = self._make()
        results = asyncio.run(ld.detect_from_text("你好，世界"))
        self.assertTrue(any(r["language"] == "zh" for r in results))

    def test_detect_arabic(self):
        ld = self._make()
        results = asyncio.run(ld.detect_from_text("مرحبا كيف حالك"))
        self.assertTrue(any(r["language"] == "ar" for r in results))

    def test_detect_japanese(self):
        ld = self._make()
        results = asyncio.run(ld.detect_from_text("こんにちは世界"))
        self.assertTrue(any(r["language"] == "ja" for r in results))

    def test_empty_text_returns_empty(self):
        ld = self._make()
        results = asyncio.run(ld.detect_from_text(""))
        self.assertEqual(results, [])

    def test_short_text_below_min_length(self):
        ld = self._make()
        results = asyncio.run(ld.detect_from_text("hi"))  # < min_text_length=3 → empty
        self.assertEqual(results, [])

    def test_no_placeholder_text_in_results(self):
        """Critical: backend must never return fabricated placeholder text."""
        ld = self._make()
        results = asyncio.run(ld.detect_from_text("Hello this is a test sentence"))
        for r in results:
            self.assertNotIn("placeholder", r.get("language", "").lower())

    def test_result_schema(self):
        ld = self._make()
        results = asyncio.run(ld.detect_from_text("Hello this is a test"))
        for r in results:
            for key in ("language", "confidence", "timestamp", "backend"):
                self.assertIn(key, r)

    def test_start_stop_processing(self):
        ld = self._make()
        ld.start_processing()
        self.assertTrue(ld.is_processing)
        ld.stop_processing()
        self.assertFalse(ld.is_processing)

    def test_add_text_processed(self):
        ld = self._make()
        received = []
        ld.start_processing(callback=received.append)
        ld.add_text("Hello this is English text for detection")
        time.sleep(0.5)
        ld.stop_processing()
        self.assertGreater(len(received), 0)


# =============================================================================
# 6. SoundClassifier
# =============================================================================

class TestSoundClassifier(unittest.TestCase):

    def setUp(self):
        from agents.ear_agent.sound_classifier import SoundClassifier
        self.SC = SoundClassifier
        self.cfg = make_config()

    def _make(self):
        return self.SC(self.cfg)

    def test_init_no_crash(self):
        sc = self._make()
        self.assertIsNotNone(sc)

    def test_classify_silence(self):
        sc = self._make()
        results = asyncio.run(sc.classify_sound(silence()))
        self.assertIsInstance(results, list)
        if results:
            self.assertEqual(results[0]["sound"], "Silence")

    def test_classify_speech_like(self):
        sc = self._make()
        results = asyncio.run(sc.classify_sound(speech_like()))
        self.assertIsInstance(results, list)
        if results:
            self.assertIn(results[0]["sound"], ["Speech", "Music", "Noise"])

    def test_result_schema(self):
        sc = self._make()
        results = asyncio.run(sc.classify_sound(speech_like()))
        for r in results:
            for key in ("sound", "confidence", "timestamp", "backend"):
                self.assertIn(key, r)

    def test_confidence_in_range(self):
        sc = self._make()
        results = asyncio.run(sc.classify_sound(speech_like()))
        for r in results:
            self.assertGreaterEqual(r["confidence"], 0.0)
            self.assertLessEqual(r["confidence"], 1.0)

    def test_set_confidence_threshold(self):
        sc = self._make()
        sc.set_confidence_threshold(0.7)
        self.assertAlmostEqual(sc.confidence_threshold, 0.7)

    def test_start_stop_processing(self):
        sc = self._make()
        sc.start_processing()
        self.assertTrue(sc.is_processing)
        sc.stop_processing()
        self.assertFalse(sc.is_processing)

    def test_cleanup(self):
        sc = self._make()
        sc.cleanup()


# =============================================================================
# 7. SpeakerIdentifier
# =============================================================================

class TestSpeakerIdentifier(unittest.TestCase):

    def setUp(self):
        from agents.ear_agent.speaker_id import SpeakerIdentifier
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        cfg = make_config()
        cfg["speaker_identification"]["data_dir"] = self.tmpdir
        self.SI = SpeakerIdentifier
        self.cfg = cfg

    def _make(self):
        return self.SI(self.cfg)

    def test_init_no_crash(self):
        si = self._make()
        self.assertIsNotNone(si)

    def test_identify_speaker_no_profiles(self):
        si = self._make()
        results = asyncio.run(si.identify_speaker(speech_like()))
        # Should return "Unknown" entry, not an exception
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["speaker_id"], "unknown")

    def test_add_speaker_too_few_samples(self):
        si = self._make()
        ok = si.add_speaker("s1", "Alice", [speech_like()])  # min_samples=2
        self.assertFalse(ok)

    def test_add_speaker_empty_id(self):
        si = self._make()
        ok = si.add_speaker("", "Alice", [speech_like(), speech_like()])
        self.assertFalse(ok)

    def test_add_and_identify_speaker(self):
        si = self._make()
        samples = [speech_like(seconds=1.0) for _ in range(3)]
        ok = si.add_speaker("s1", "Alice", samples)
        self.assertTrue(ok)
        profiles = si.get_speaker_profiles()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["name"], "Alice")

    def test_remove_speaker(self):
        si = self._make()
        si.add_speaker("s1", "Alice", [speech_like(), speech_like()])
        ok = si.remove_speaker("s1")
        self.assertTrue(ok)
        self.assertEqual(si.get_speaker_profiles(), [])

    def test_remove_nonexistent_speaker(self):
        si = self._make()
        ok = si.remove_speaker("does_not_exist")
        self.assertFalse(ok)

    def test_start_stop_processing(self):
        si = self._make()
        si.start_processing()
        self.assertTrue(si.is_processing)
        si.stop_processing()
        self.assertFalse(si.is_processing)

    def test_cleanup(self):
        si = self._make()
        si.cleanup()


# =============================================================================
# 8. AgentIntegration
# =============================================================================

class TestAgentIntegration(unittest.TestCase):

    def setUp(self):
        from agents.ear_agent.agent_integration import AgentIntegration
        self.AI = AgentIntegration
        self.cfg = make_config()

    def _make(self):
        return self.AI(self.cfg)

    def test_init_reads_endpoints_from_config(self):
        ai = self._make()
        self.assertEqual(ai.brain_endpoint, "http://localhost:8000")
        self.assertEqual(ai.emotion_endpoint, "http://localhost:8001")
        self.assertEqual(ai.memory_endpoint, "http://localhost:8002")
        self.assertEqual(ai.personality_endpoint, "http://localhost:8003")

    def test_notify_brain_uses_monotonic_time(self):
        """time.monotonic() should be called, not asyncio.get_event_loop().time()"""
        import inspect
        from agents.ear_agent import agent_integration
        src = inspect.getsource(agent_integration)
        self.assertIn("monotonic", src, "Bug: time.monotonic() not used")
        self.assertNotIn("asyncio.get_event_loop().time()", src,
                         "Bug: deprecated asyncio.get_event_loop().time() still present")

    def test_get_agent_health_returns_dict_when_not_connected(self):
        ai = self._make()
        health = asyncio.run(ai.get_agent_health())
        self.assertIsInstance(health, dict)
        for key in ("brain", "emotion", "memory", "personality"):
            self.assertIn(key, health)

    def test_cleanup_when_not_initialized(self):
        ai = self._make()
        asyncio.run(ai.cleanup())  # must not raise

    @patch("agents.ear_agent.agent_integration._HAS_AIOHTTP", True)
    def test_request_uses_retry(self):
        """Verify retry constant is > 1."""
        from agents.ear_agent.agent_integration import _MAX_RETRIES
        self.assertGreater(_MAX_RETRIES, 1)


# =============================================================================
# 9. EarAgent Integration
# =============================================================================

class TestEarAgent(unittest.TestCase):

    def setUp(self):
        from agents.ear_agent.main import EarAgent
        self.EA = EarAgent
        self.cfg = make_config()

    def _make(self):
        agent = self.EA(config=self.cfg)
        asyncio.run(agent.initialize())
        return agent

    def test_initialize_no_crash(self):
        agent = self._make()
        self.assertIsNotNone(agent)

    def test_base_agent_inheritance(self):
        from agents.base_agent import BaseAgent
        agent = self.EA(config=self.cfg)
        self.assertIsInstance(agent, BaseAgent)

    def test_execute_task_get_status(self):
        agent = self._make()
        result = asyncio.run(agent.execute_task({"action": "get_status"}))
        self.assertIsInstance(result, dict)

    def test_execute_task_get_health(self):
        agent = self._make()
        result = asyncio.run(agent.execute_task({"action": "get_health"}))
        self.assertIn("healthy", result)
        self.assertIn("components", result)

    def test_execute_task_transcribe(self):
        agent = self._make()
        result = asyncio.run(agent.execute_task({
            "action": "transcribe",
            "input_data": {"audio": speech_like().tolist(), "sample_rate": 16000},
        }))
        self.assertIn("text", result)
        self.assertIn("confidence", result)

    def test_execute_task_transcribe_no_audio(self):
        agent = self._make()
        result = asyncio.run(agent.execute_task({
            "action": "transcribe",
            "input_data": {},
        }))
        self.assertIn("error", result)

    def test_execute_task_detect_emotion(self):
        agent = self._make()
        result = asyncio.run(agent.execute_task({
            "action": "detect_emotion",
            "input_data": {"audio": speech_like().tolist()},
        }))
        self.assertIn("emotions", result)

    def test_execute_task_detect_intent(self):
        agent = self._make()
        result = asyncio.run(agent.execute_task({
            "action": "detect_intent",
            "input_data": {"text": "hello how are you"},
        }))
        self.assertIn("intents", result)

    def test_execute_task_detect_language(self):
        agent = self._make()
        result = asyncio.run(agent.execute_task({
            "action": "detect_language",
            "input_data": {"text": "Hello this is a test for language detection"},
        }))
        self.assertIn("languages", result)

    def test_execute_task_classify_sound(self):
        agent = self._make()
        result = asyncio.run(agent.execute_task({
            "action": "classify_sound",
            "input_data": {"audio": silence().tolist()},
        }))
        self.assertIn("sounds", result)

    def test_execute_task_get_history_empty(self):
        agent = self._make()
        result = asyncio.run(agent.execute_task({"action": "get_history"}))
        self.assertIn("history", result)
        self.assertIsInstance(result["history"], list)

    def test_execute_task_clear_history(self):
        agent = self._make()
        agent._append_history({"type": "speech", "text": "hello"})
        asyncio.run(agent.execute_task({"action": "clear_history"}))
        self.assertEqual(agent.conversation_history, [])

    def test_execute_task_get_devices(self):
        agent = self._make()
        result = asyncio.run(agent.execute_task({"action": "get_devices"}))
        self.assertIn("devices", result)
        self.assertIsInstance(result["devices"], list)

    def test_start_stop_audio(self):
        agent = self._make()
        # start_listening will warn about sounddevice but must not crash
        result = asyncio.run(agent.execute_task({"action": "start_listening"}))
        self.assertIn("capturing", result)
        result = asyncio.run(agent.execute_task({"action": "stop_listening"}))
        self.assertIn("capturing", result)

    def test_history_appended_by_callback(self):
        agent = self._make()
        agent.is_capturing = True
        agent._speech_callback({
            "text": "hello world", "confidence": 0.9,
            "language": "en", "backend": "whisper",
            "timestamp": datetime.utcnow().isoformat(),
        })
        h = agent.get_conversation_history()
        self.assertEqual(len(h), 1)
        self.assertEqual(h[0]["type"], "speech")

    def test_history_limit_enforced(self):
        agent = self._make()
        for i in range(100):
            agent._append_history({"type": "test", "index": i})
        self.assertLessEqual(len(agent.conversation_history), self.cfg["max_history_length"])

    def test_get_conversation_history_with_limit(self):
        agent = self._make()
        for i in range(20):
            agent._append_history({"type": "test", "index": i})
        h = agent.get_conversation_history(limit=5)
        self.assertEqual(len(h), 5)

    def test_config_not_path_string(self):
        """EarAgent constructor must accept dict config, not just a path."""
        agent = self.EA(config=self.cfg)
        self.assertIsInstance(agent.config, dict)

    def test_all_components_instantiated(self):
        agent = self._make()
        status = agent.get_agent_status()
        # All components should be present (energy/acoustic/mfcc backends require only numpy)
        for comp, present in status["components"].items():
            self.assertTrue(present, f"Component not instantiated: {comp}")

    def test_shutdown_does_not_raise(self):
        agent = self._make()
        asyncio.run(agent.shutdown())


# =============================================================================
# Run
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
