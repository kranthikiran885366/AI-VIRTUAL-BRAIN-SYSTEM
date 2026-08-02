"""
Joint Integration Test Suite — EarAgent + CreativityAgent.

Verifies end-to-end multi-agent integration:
  - Parallel initialization & health checks of EarAgent and CreativityAgent
  - Perception-to-Creativity pipeline via PerceptionToCreativityBridge
  - Emotion-aware creative weight tuning
  - Inter-agent message passing using BaseAgent infrastructure
  - Multi-task execution dispatch across both agents

Run with:
    python -m unittest agents/tests/test_combined_agents.py -v
"""

import asyncio
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.ear_agent.main import EarAgent
from agents.creativity_agent.main import CreativityAgent
from agents.agent_bridge import PerceptionToCreativityBridge


def silence(seconds: float = 0.5, sr: int = 16000) -> np.ndarray:
    return np.zeros(int(sr * seconds), dtype=np.int16)


def speech_like(seconds: float = 0.5, amplitude: float = 5000, sr: int = 16000) -> np.ndarray:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    wave = (amplitude * (
        0.5 * np.sin(2 * np.pi * 200 * t) +
        0.3 * np.sin(2 * np.pi * 350 * t) +
        0.2 * np.sin(2 * np.pi * 500 * t)
    )).astype(np.int16)
    return wave


def make_ear_config() -> Dict[str, Any]:
    return {
        "audio": {"sample_rate": 16000, "channels": 1, "chunk_size": 1024, "format": "int16"},
        "speech_recognition": {"backend": "energy", "language": "en", "confidence_threshold": 0.3},
        "emotion_detection": {"model": "acoustic", "supported_emotions": ["neutral", "happy", "sad", "angry", "excited", "anxious"]},
        "intent_detection": {"model": "keyword", "supported_intents": ["greeting", "task_creation", "help_request", "information_request"]},
        "language_detection": {"model": "heuristic", "supported_languages": ["en", "zh", "ar", "ja"]},
        "sound_classification": {"model": "acoustic"},
        "speaker_identification": {"model": "mfcc", "min_samples": 2, "data_dir": "tests/tmp_combined_speakers"},
        "agent_integration": {"brain_endpoint": "http://localhost:8000"},
        "max_history_length": 50,
    }


def make_creativity_config() -> Dict[str, Any]:
    return {
        "domain": "AI Systems",
        "max_idea_history": 100,
        "default_novelty_weight": 0.35,
        "default_feasibility_weight": 0.35,
        "default_impact_weight": 0.30,
    }


# =============================================================================
# Test Suite
# =============================================================================

class TestCombinedAgentsInitialization(unittest.TestCase):
    """Test parallel instantiation and lifecycle management of both agents."""

    def test_both_agents_initialize_successfully(self):
        ear = EarAgent(config=make_ear_config())
        creativity = CreativityAgent(config=make_creativity_config())

        async def _init():
            await ear.initialize()
            await creativity.initialize()

        asyncio.run(_init())

        self.assertEqual(ear.agent_type, "perception")
        self.assertEqual(creativity.agent_type, "creativity")

        # Health checks
        ear_health = asyncio.run(ear.get_health())
        creativity_health = asyncio.run(creativity.get_health())

        self.assertTrue(ear_health["healthy"])
        self.assertTrue(creativity_health["healthy"])

        # Clean teardown
        asyncio.run(ear.shutdown())
        asyncio.run(creativity.shutdown())


class TestPerceptionToCreativityPipeline(unittest.TestCase):
    """Test the PerceptionToCreativityBridge pipeline."""

    def setUp(self):
        self.ear = EarAgent(config=make_ear_config())
        self.creativity = CreativityAgent(config=make_creativity_config())

        async def _init():
            await self.ear.initialize()
            await self.creativity.initialize()

        asyncio.run(_init())
        self.bridge = PerceptionToCreativityBridge(self.ear, self.creativity)

    def tearDown(self):
        asyncio.run(self.ear.shutdown())
        asyncio.run(self.creativity.shutdown())

    def test_process_text_prompt_to_ideas(self):
        prompt = "Create an automated real-time health monitoring system for elderly care"
        result = asyncio.run(self.bridge.process_speech_to_ideas(
            text=prompt, domain="healthcare", count=3
        ))

        self.assertEqual(result["status"], "success")
        self.assertIn("perception", result)
        self.assertIn("ideas", result)
        self.assertGreater(len(result["ideas"]), 0)

        # Check idea structure
        first_idea = result["ideas"][0]
        self.assertIn("idea", first_idea)
        self.assertIn("scores", first_idea)
        self.assertIn("concept", first_idea["idea"])
        self.assertIn("overall", first_idea["scores"])

    def test_process_audio_prompt_to_ideas(self):
        audio = speech_like(seconds=1.0)
        result = asyncio.run(self.bridge.process_speech_to_ideas(
            audio_data=audio, domain="audio perception", count=2
        ))

        self.assertEqual(result["status"], "success")
        self.assertIn("perception", result)
        self.assertIn("creative_tuning", result)
        self.assertGreater(len(result["ideas"]), 0)

    def test_emotion_weight_mapping(self):
        excited_weights = self.bridge.map_emotion_to_creative_weights("excited")
        anxious_weights = self.bridge.map_emotion_to_creative_weights("anxious")
        angry_weights   = self.bridge.map_emotion_to_creative_weights("angry")
        neutral_weights = self.bridge.map_emotion_to_creative_weights("neutral")

        # Excited should emphasize novelty
        self.assertGreater(excited_weights["novelty_weight"], anxious_weights["novelty_weight"])

        # Anxious should emphasize feasibility
        self.assertGreater(anxious_weights["feasibility_weight"], excited_weights["feasibility_weight"])

        # Angry should emphasize impact
        self.assertGreater(angry_weights["impact_weight"], neutral_weights["impact_weight"])


class TestInterAgentMessaging(unittest.TestCase):
    """Test BaseAgent message bus between EarAgent and CreativityAgent."""

    def test_send_message_between_agents(self):
        ear = EarAgent(agent_id="ear_1", config=make_ear_config())
        creativity = CreativityAgent(agent_id="creativity_1", config=make_creativity_config())

        async def _run():
            await ear.initialize()
            await creativity.initialize()

            # Mock message broker
            bus = {}

            class MockBroker:
                async def send_message(self, msg):
                    rec = msg.get("recipient_id")
                    bus.setdefault(rec, []).append(msg)
                    return True

            ear._message_broker = MockBroker()
            creativity._message_broker = MockBroker()

            # EarAgent sends a perceived event message to CreativityAgent
            payload = {
                "perceived_text": "We need a new AI scheduling assistant",
                "perceived_intent": "task_creation",
                "perceived_emotion": "happy",
            }
            await ear.send_message(
                recipient_id="creativity_1",
                message_type="perception_event",
                content=payload,
            )

            self.assertIn("creativity_1", bus)
            received_msgs = bus["creativity_1"]
            self.assertEqual(len(received_msgs), 1)
            self.assertEqual(received_msgs[0]["content"]["perceived_text"], "We need a new AI scheduling assistant")

            await ear.shutdown()
            await creativity.shutdown()

        asyncio.run(_run())


class TestEndToEndWorkflow(unittest.TestCase):
    """Full end-to-end multi-agent scenario."""

    def test_end_to_end_multimodal_creative_pipeline(self):
        ear = EarAgent(config=make_ear_config())
        creativity = CreativityAgent(config=make_creativity_config())

        async def _run():
            await ear.initialize()
            await creativity.initialize()

            bridge = PerceptionToCreativityBridge(ear, creativity)

            # Scenario 1: User speaks a query about sustainable energy
            prompt = "Design an intelligent solar power grid optimization algorithm"
            res1 = await bridge.process_speech_to_ideas(text=prompt, domain="energy", count=3)

            self.assertEqual(res1["status"], "success")
            self.assertGreaterEqual(len(res1["ideas"]), 1)

            # Scenario 2: Analyze patterns on generated ideas
            ideas = res1["ideas"]
            pattern_task = {
                "action": "analyze_patterns",
                "input_data": {"ideas": ideas},
            }
            pattern_res = await creativity.execute_task(pattern_task)

            self.assertIn("patterns", pattern_res)
            self.assertIn("common_themes", pattern_res["patterns"])

            await ear.shutdown()
            await creativity.shutdown()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main(verbosity=2)
