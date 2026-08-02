import asyncio
import logging
import re
from typing import Dict, List, Any
from datetime import datetime

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class LanguageAgent(BaseAgent):
    def __init__(self, agent_id: str = "language_agent"):
        super().__init__(agent_id, "language")
        self.processing_history: List[Dict] = []

    async def initialize(self):
        await super().initialize()
        self.state.update({"texts_processed": 0})
        logger.info(f"Language agent {self.agent_id} initialized")

    async def _update_state(self):
        self.state.update({
            "texts_processed": len(self.processing_history),
            "last_active": datetime.utcnow().isoformat(),
        })

    def _detect_language_task(self, text: str, action: str = "") -> str:
        lower = (text + " " + action).lower()
        if any(w in lower for w in ["summarize", "summary", "tldr", "brief", "shorten", "condense"]):
            return "summarize"
        if any(w in lower for w in ["translate", "in spanish", "in french", "in german", "in hindi", "in arabic"]):
            return "translate"
        if any(w in lower for w in ["improve", "rewrite", "rephrase", "better", "enhance", "polish", "refine"]):
            return "improve"
        if any(w in lower for w in ["grammar", "spelling", "correct", "fix", "proofread", "check"]):
            return "proofread"
        if any(w in lower for w in ["formal", "professional", "business", "official"]):
            return "formalize"
        if any(w in lower for w in ["casual", "informal", "friendly", "conversational", "simple"]):
            return "simplify"
        if any(w in lower for w in ["expand", "elaborate", "more detail", "longer", "extend"]):
            return "expand"
        if any(w in lower for w in ["tone", "style", "voice", "adapt", "adjust"]):
            return "tone_adjust"
        return "analyze"

    def _analyze_text(self, text: str) -> Dict:
        words = text.split()
        sentences = re.split(r'[.!?]+', text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
        avg_sentence_length = len(words) / len(sentences) if sentences else 0

        if avg_sentence_length > 25 or avg_word_length > 6:
            complexity = "complex"
            reading_level = "advanced"
        elif avg_sentence_length > 15 or avg_word_length > 5:
            complexity = "moderate"
            reading_level = "intermediate"
        else:
            complexity = "simple"
            reading_level = "basic"

        passive_count = len(re.findall(r'\b(is|are|was|were|been|being)\s+\w+ed\b', text, re.IGNORECASE))
        filler_words = ["very", "really", "quite", "just", "basically", "literally", "actually", "honestly"]
        filler_count = sum(text.lower().count(w) for w in filler_words)

        return {
            "word_count": len(words),
            "sentence_count": len(sentences),
            "paragraph_count": len(paragraphs),
            "avg_sentence_length": round(avg_sentence_length, 1),
            "avg_word_length": round(avg_word_length, 1),
            "complexity": complexity,
            "reading_level": reading_level,
            "passive_voice_count": passive_count,
            "filler_word_count": filler_count,
            "suggestions": self._generate_writing_suggestions(passive_count, filler_count, avg_sentence_length),
        }

    def _generate_writing_suggestions(self, passive_count: int, filler_count: int, avg_sentence_length: float) -> List[str]:
        suggestions = []
        if passive_count > 2:
            suggestions.append(f"Found {passive_count} passive voice constructions. Consider converting to active voice for stronger, clearer writing.")
        if filler_count > 3:
            suggestions.append(f"Found {filler_count} filler words (very, really, just, etc.). Remove them to make writing more direct and confident.")
        if avg_sentence_length > 30:
            suggestions.append("Sentences are quite long. Break complex sentences into shorter ones for better readability.")
        if avg_sentence_length < 8:
            suggestions.append("Sentences are very short. Consider combining some for better flow and nuance.")
        if not suggestions:
            suggestions.append("Writing quality looks good. No major issues detected.")
        return suggestions

    def _summarize(self, text: str, target_length: str = "medium") -> str:
        sentences = re.split(r'[.!?]+', text.strip())
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        if not sentences:
            return text

        keep_count = {"short": max(1, len(sentences) // 4), "medium": max(2, len(sentences) // 3), "long": max(3, len(sentences) // 2)}.get(target_length, max(2, len(sentences) // 3))

        scored = []
        for i, sentence in enumerate(sentences):
            score = 0
            if i == 0: score += 3
            if i == len(sentences) - 1: score += 2
            score += len(sentence.split()) * 0.1
            important_words = ["important", "key", "main", "primary", "critical", "essential", "significant", "therefore", "conclusion", "result"]
            score += sum(2 for w in important_words if w in sentence.lower())
            scored.append((score, i, sentence))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_sentences = sorted(scored[:keep_count], key=lambda x: x[1])
        return ". ".join(s[2] for s in top_sentences) + "."

    def _improve_text(self, text: str) -> Dict:
        improved = text
        replacements = [
            (r'\bvery\s+good\b', 'excellent'), (r'\bvery\s+bad\b', 'terrible'),
            (r'\bvery\s+big\b', 'enormous'), (r'\bvery\s+small\b', 'tiny'),
            (r'\bvery\s+fast\b', 'rapid'), (r'\bvery\s+slow\b', 'sluggish'),
            (r'\bvery\s+happy\b', 'delighted'), (r'\bvery\s+sad\b', 'devastated'),
            (r'\ba lot of\b', 'numerous'), (r'\bkind of\b', 'somewhat'),
            (r'\bsort of\b', 'somewhat'), (r'\bin order to\b', 'to'),
            (r'\bdue to the fact that\b', 'because'), (r'\bat this point in time\b', 'now'),
            (r'\bfor the purpose of\b', 'to'), (r'\bin the event that\b', 'if'),
        ]
        changes = []
        for pattern, replacement in replacements:
            new_text = re.sub(pattern, replacement, improved, flags=re.IGNORECASE)
            if new_text != improved:
                changes.append(f"Replaced '{pattern.replace(r\"\\b\", \"\").replace(r\"\\s+\", \" \")}' with '{replacement}'")
                improved = new_text

        return {
            "original": text,
            "improved": improved,
            "changes_made": changes,
            "improvement_count": len(changes),
        }

    def _detect_language(self, text: str) -> str:
        lower = text.lower()
        lang_patterns = {
            "spanish": ["el ", "la ", "los ", "las ", "que ", "de ", "en ", "es ", "con ", "por "],
            "french": ["le ", "la ", "les ", "de ", "du ", "des ", "et ", "en ", "je ", "vous "],
            "german": ["der ", "die ", "das ", "und ", "ist ", "ich ", "sie ", "ein ", "mit ", "auf "],
            "hindi": ["है", "का", "की", "के", "में", "और", "को", "से", "पर", "यह"],
            "arabic": ["في", "من", "على", "إلى", "هذا", "هذه", "كان", "مع", "عن", "أن"],
        }
        for lang, patterns in lang_patterns.items():
            if sum(1 for p in patterns if p in lower) >= 3:
                return lang
        return "english"

    async def process(self, text: str, task_type: str = "analyze", options: Dict = None) -> Dict:
        options = options or {}
        result = {"input": text[:200], "task_type": task_type, "timestamp": datetime.utcnow().isoformat()}

        if task_type == "analyze":
            result["analysis"] = self._analyze_text(text)
            result["detected_language"] = self._detect_language(text)

        elif task_type == "summarize":
            length = options.get("length", "medium")
            result["summary"] = self._summarize(text, length)
            result["original_word_count"] = len(text.split())
            result["summary_word_count"] = len(result["summary"].split())
            result["compression_ratio"] = round(result["summary_word_count"] / max(1, result["original_word_count"]), 2)

        elif task_type == "improve":
            result.update(self._improve_text(text))

        elif task_type == "proofread":
            analysis = self._analyze_text(text)
            result["issues"] = analysis["suggestions"]
            result["passive_voice_count"] = analysis["passive_voice_count"]
            result["filler_word_count"] = analysis["filler_word_count"]
            result["overall_quality"] = "good" if len(analysis["suggestions"]) <= 1 else "needs_improvement"

        elif task_type == "formalize":
            formal = re.sub(r"\bcan't\b", "cannot", text, flags=re.IGNORECASE)
            formal = re.sub(r"\bwon't\b", "will not", formal, flags=re.IGNORECASE)
            formal = re.sub(r"\bdon't\b", "do not", formal, flags=re.IGNORECASE)
            formal = re.sub(r"\bisn't\b", "is not", formal, flags=re.IGNORECASE)
            formal = re.sub(r"\baren't\b", "are not", formal, flags=re.IGNORECASE)
            formal = re.sub(r"\bwasn't\b", "was not", formal, flags=re.IGNORECASE)
            formal = re.sub(r"\bweren't\b", "were not", formal, flags=re.IGNORECASE)
            formal = re.sub(r"\bI'm\b", "I am", formal, flags=re.IGNORECASE)
            formal = re.sub(r"\bI've\b", "I have", formal, flags=re.IGNORECASE)
            formal = re.sub(r"\bI'll\b", "I will", formal, flags=re.IGNORECASE)
            result["formalized"] = formal
            result["changes"] = "Expanded contractions and applied formal register"

        elif task_type == "simplify":
            simplified = self._summarize(text, "medium")
            result["simplified"] = simplified
            result["note"] = "Text simplified to core meaning with shorter sentences"

        else:
            result["analysis"] = self._analyze_text(text)

        self.processing_history.append({"task_type": task_type, "word_count": len(text.split()), "timestamp": result["timestamp"]})
        if len(self.processing_history) > 500:
            self.processing_history = self.processing_history[-500:]

        return result

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {})
        text = data.get("content", data.get("text", ""))
        task_type = self._detect_language_task(text, action)
        options = {"length": data.get("length", "medium")}
        return await self.process(text, task_type, options)
