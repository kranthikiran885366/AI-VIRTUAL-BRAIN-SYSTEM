"""
Agent Bridge — Perception-to-Creativity Integration Pipeline.

Connects EarAgent (perception) and CreativityAgent (creative synthesis).
Pipeline flow:
  1. EarAgent perceives audio/text → extracts text, emotion, intent, language
  2. Bridge transforms emotion & intent into creative tuning parameters
  3. CreativityAgent generates, scores, and ranks ideas based on perception context
  4. Returns unified PerceptionCreativeResult
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from agents.ear_agent.main import EarAgent
    from agents.creativity_agent.main import CreativityAgent
except ImportError:
    from ear_agent.main import EarAgent            # type: ignore
    from creativity_agent.main import CreativityAgent  # type: ignore


logger = logging.getLogger("AgentBridge")


class PerceptionToCreativityBridge:
    """
    Bridge coordinating perception events from EarAgent to creative actions in CreativityAgent.
    """

    def __init__(self, ear_agent: EarAgent, creativity_agent: CreativityAgent):
        self.ear_agent = ear_agent
        self.creativity_agent = creativity_agent
        self.logger = logging.getLogger(__name__)

    # ─── Emotional Tuning Mapping ─────────────────────────────────────────────

    @staticmethod
    def map_emotion_to_creative_weights(emotion: str) -> Dict[str, float]:
        """
        Maps user emotional state perceived by EarAgent into CreativityAgent scoring weights.
          - excited/happy  : higher novelty weight (encourages bold, risk-taking ideas)
          - anxious/fearful: higher feasibility weight (encourages practical, safe solutions)
          - angry/frustrated: higher impact weight (encourages rapid problem-solving)
          - neutral/curious: balanced weights
        """
        e = (emotion or "neutral").lower()
        if e in ("excited", "happy", "surprised"):
            return {"novelty_weight": 0.50, "feasibility_weight": 0.20, "impact_weight": 0.30}
        if e in ("anxious", "fearful", "sad"):
            return {"novelty_weight": 0.20, "feasibility_weight": 0.50, "impact_weight": 0.30}
        if e in ("angry", "disgusted", "frustrated"):
            return {"novelty_weight": 0.25, "feasibility_weight": 0.25, "impact_weight": 0.50}
        # Neutral / default balance
        return {"novelty_weight": 0.35, "feasibility_weight": 0.35, "impact_weight": 0.30}

    # ─── Main Pipeline Execution ──────────────────────────────────────────────

    async def process_speech_to_ideas(
        self,
        text: Optional[str] = None,
        audio_data: Optional[Any] = None,
        sample_rate: int = 16000,
        domain: str = "general",
        count: int = 3,
    ) -> Dict[str, Any]:
        """
        Executes perception → creative synthesis workflow.
        Returns combined payload with speech perception and generated creative ideas.
        """
        # Step 1: Perception via EarAgent
        perception_result = await self._run_perception(text, audio_data, sample_rate)

        transcribed_text = perception_result.get("text", text or "")
        detected_emotion = perception_result.get("top_emotion", "neutral")
        detected_intent = perception_result.get("top_intent", "unknown")
        detected_language = perception_result.get("top_language", "en")

        # Step 2: Determine creative weights based on perceived emotion
        creative_weights = self.map_emotion_to_creative_weights(detected_emotion)

        # Step 3: Dispatch to CreativityAgent
        creative_task = {
            "action": "generate_ideas",
            "input_data": {
                "prompt": transcribed_text or f"Generate creative ideas for {domain}",
                "domain": domain,
                "count": count,
                "context": {
                    "perceived_emotion": detected_emotion,
                    "perceived_intent": detected_intent,
                    "perceived_language": detected_language,
                    "speaker_id": perception_result.get("top_speaker", "unknown"),
                    "weights": creative_weights,
                },
            },
        }

        creative_response = await self.creativity_agent.execute_task(creative_task)

        # Step 4: Gather inspirations if requested
        inspiration_response = {}
        if transcribed_text and not transcribed_text.startswith("["):
            insp_task = {
                "action": "gather_inspirations",
                "input_data": {"query": transcribed_text, "domain": domain, "count": 2},
            }
            inspiration_response = await self.creativity_agent.execute_task(insp_task)

        # Step 5: Build unified result
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "perception": {
                "text": transcribed_text,
                "emotion": detected_emotion,
                "intent": detected_intent,
                "language": detected_language,
                "confidence": perception_result.get("confidence", 0.0),
                "backend": perception_result.get("backend", "none"),
            },
            "creative_tuning": creative_weights,
            "ideas": creative_response.get("ideas", []),
            "inspirations": inspiration_response.get("inspirations", []),
        }

    async def _run_perception(
        self, text: Optional[str], audio_data: Optional[Any], sample_rate: int
    ) -> Dict[str, Any]:
        """Runs EarAgent task pipeline."""
        res: Dict[str, Any] = {
            "text": text or "",
            "top_emotion": "neutral",
            "top_intent": "unknown",
            "top_language": "en",
            "top_speaker": "unknown",
            "confidence": 0.8,
            "backend": "text_input",
        }

        if audio_data is not None:
            asr_res = await self.ear_agent.execute_task({
                "action": "transcribe",
                "input_data": {"audio": audio_data, "sample_rate": sample_rate},
            })
            res["text"] = asr_res.get("text", "")
            res["confidence"] = asr_res.get("confidence", 0.0)
            res["backend"] = asr_res.get("backend", "audio")

        # Intent detection
        effective_text = res["text"] or text or ""
        if effective_text:
            intent_res = await self.ear_agent.execute_task({
                "action": "detect_intent",
                "input_data": {"text": effective_text},
            })
            top_intent = intent_res.get("top")
            if top_intent:
                res["top_intent"] = top_intent.get("intent", "unknown")

            # Language detection
            lang_res = await self.ear_agent.execute_task({
                "action": "detect_language",
                "input_data": {"text": effective_text},
            })
            top_lang = lang_res.get("top")
            if top_lang:
                res["top_language"] = top_lang.get("language", "en")

        # Emotion detection
        if audio_data is not None:
            emo_res = await self.ear_agent.execute_task({
                "action": "detect_emotion",
                "input_data": {"audio": audio_data},
            })
            top_emo = emo_res.get("top")
            if top_emo:
                res["top_emotion"] = top_emo.get("emotion", "neutral")

        return res
