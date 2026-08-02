import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from structlog import get_logger
except ImportError:
    def get_logger():
        return logging.getLogger(__name__)

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

logger = get_logger()


class LearningAgent(BaseAgent):
    def __init__(self, agent_id: str = "learning_agent"):
        super().__init__(agent_id, "learning")
        self.knowledge_base: Dict[str, Any] = {}
        self.user_preferences: Dict[str, Any] = {}
        self.interaction_patterns: List[Dict] = []
        self.topic_frequency: Dict[str, int] = {}
        self.adaptation_log: List[Dict] = []
        self.max_patterns = 2000

    async def initialize(self):
        await super().initialize()
        self.state.update({
            "knowledge_entries": 0,
            "preference_entries": 0,
            "pattern_count": 0,
            "adaptation_count": 0,
            "last_learning": datetime.utcnow().isoformat(),
        })
        logger.info(f"Learning agent {self.agent_id} initialized")

    async def _update_state(self):
        self.state.update({
            "knowledge_entries": len(self.knowledge_base),
            "preference_entries": len(self.user_preferences),
            "pattern_count": len(self.interaction_patterns),
            "adaptation_count": len(self.adaptation_log),
            "last_active": datetime.utcnow().isoformat(),
        })

    async def _process_emotions(self):
        recent = self.adaptation_log[-10:]
        if not recent:
            return
        rate = sum(1 for a in recent if a.get("success", True)) / len(recent)
        if rate > 0.7:
            await self.update_emotion("happiness", min(1.0, self.emotions.get("happiness", 0.5) + 0.05))
        elif rate < 0.3:
            await self.update_emotion("sadness", min(1.0, self.emotions.get("sadness", 0.0) + 0.05))

    async def learn_from_interaction(self, interaction: Dict) -> Dict:
        user_message = interaction.get("user_message", "")
        agent_response = interaction.get("agent_response", "")
        agent_used = interaction.get("agent_used", "orchestrator_agent")
        user_id = interaction.get("user_id", "default")
        feedback = interaction.get("feedback")

        words = user_message.lower().split()
        for word in words:
            if len(word) > 4:
                self.topic_frequency[word] = self.topic_frequency.get(word, 0) + 1

        pattern = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "message_length": len(user_message),
            "agent_used": agent_used,
            "top_words": sorted(words, key=lambda w: self.topic_frequency.get(w, 0), reverse=True)[:5],
            "feedback": feedback,
        }
        self.interaction_patterns.append(pattern)
        if len(self.interaction_patterns) > self.max_patterns:
            self.interaction_patterns = self.interaction_patterns[-self.max_patterns:]

        if feedback is not None:
            pref_key = f"{user_id}:{agent_used}"
            if pref_key not in self.user_preferences:
                self.user_preferences[pref_key] = {"positive": 0, "negative": 0, "total": 0}
            self.user_preferences[pref_key]["total"] += 1
            if feedback > 0:
                self.user_preferences[pref_key]["positive"] += 1
            else:
                self.user_preferences[pref_key]["negative"] += 1

        topic = self._extract_topic(user_message)
        if topic:
            if topic not in self.knowledge_base:
                self.knowledge_base[topic] = {
                    "first_seen": datetime.utcnow().isoformat(),
                    "frequency": 0,
                    "agents_used": [],
                    "sample_queries": [],
                }
            entry = self.knowledge_base[topic]
            entry["frequency"] += 1
            entry["last_seen"] = datetime.utcnow().isoformat()
            if agent_used not in entry["agents_used"]:
                entry["agents_used"].append(agent_used)
            if len(entry["sample_queries"]) < 5:
                entry["sample_queries"].append(user_message[:100])

        adaptation = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "topic": topic,
            "agent_used": agent_used,
            "success": feedback is None or feedback > 0,
        }
        self.adaptation_log.append(adaptation)
        if len(self.adaptation_log) > 500:
            self.adaptation_log = self.adaptation_log[-500:]

        self.state["last_learning"] = datetime.utcnow().isoformat()

        return {
            "learned": True,
            "topic": topic,
            "pattern_id": pattern["id"],
            "knowledge_base_size": len(self.knowledge_base),
            "top_topics": self._get_top_topics(5),
        }

    def _extract_topic(self, text: str) -> Optional[str]:
        topic_map = {
            "memory": ["remember", "recall", "forget", "memory", "store", "save"],
            "emotion": ["feel", "emotion", "mood", "sad", "happy", "angry", "anxious"],
            "task": ["task", "todo", "deadline", "schedule", "reminder", "organize"],
            "creativity": ["create", "idea", "brainstorm", "design", "story", "imagine"],
            "planning": ["plan", "goal", "strategy", "roadmap", "milestone", "achieve"],
            "reasoning": ["analyze", "logic", "reason", "why", "because", "proof"],
            "social": ["friend", "relationship", "communicate", "people", "social"],
            "learning": ["learn", "study", "understand", "teach", "knowledge", "skill"],
            "decision": ["decide", "choose", "option", "compare", "recommend", "best"],
            "motivation": ["motivate", "inspire", "stuck", "tired", "give up", "push"],
        }
        lower = text.lower()
        scores = {}
        for topic, keywords in topic_map.items():
            scores[topic] = sum(1 for kw in keywords if kw in lower)
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else None

    def _get_top_topics(self, n: int) -> List[Dict]:
        sorted_topics = sorted(
            self.knowledge_base.items(),
            key=lambda x: x[1].get("frequency", 0),
            reverse=True
        )
        return [{"topic": k, "frequency": v.get("frequency", 0)} for k, v in sorted_topics[:n]]

    def get_user_agent_preference(self, user_id: str) -> Optional[str]:
        best_agent = None
        best_score = -1
        for key, stats in self.user_preferences.items():
            uid, agent = key.split(":", 1)
            if uid != user_id:
                continue
            total = stats["total"]
            if total == 0:
                continue
            score = stats["positive"] / total
            if score > best_score:
                best_score = score
                best_agent = agent
        return best_agent

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        input_data = task.get("input_data", {})

        if action in ("learn", "learn_from_interaction"):
            return await self.learn_from_interaction(input_data)

        if action == "get_preferences":
            user_id = input_data.get("user_id", "default")
            preferred = self.get_user_agent_preference(user_id)
            return {
                "user_id": user_id,
                "preferred_agent": preferred,
                "top_topics": self._get_top_topics(10),
                "total_interactions": len(self.interaction_patterns),
            }

        if action == "get_stats":
            return {
                "knowledge_base_size": len(self.knowledge_base),
                "user_preferences": len(self.user_preferences),
                "interaction_patterns": len(self.interaction_patterns),
                "adaptation_count": len(self.adaptation_log),
                "top_topics": self._get_top_topics(5),
            }

        if action == "get_topic_knowledge":
            topic = input_data.get("topic", "")
            return self.knowledge_base.get(topic, {"error": "topic not found"})

        return await self.learn_from_interaction({
            "user_message": input_data.get("content", ""),
            "agent_used": input_data.get("agent_used", "orchestrator_agent"),
            "user_id": input_data.get("user_id", "default"),
        })
