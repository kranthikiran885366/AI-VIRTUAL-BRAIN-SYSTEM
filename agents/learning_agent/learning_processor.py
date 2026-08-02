import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False
    TfidfVectorizer = None

try:
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.corpus import stopwords
    from nltk.tag import pos_tag
    import nltk
    _HAS_NLTK = True
except ImportError:
    _HAS_NLTK = False
    def word_tokenize(text): return text.split()
    def sent_tokenize(text): return re.split(r"[.!?]+\s*", text.strip())
    def pos_tag(tokens): return [(t, "NN") for t in tokens]
    class _SW:
        def words(self, lang): return []
    class _NltkStub:
        def download(self, *a, **kw): pass
    stopwords = _SW()
    nltk = _NltkStub()


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class LearningProcessor:
    """
    Extracts structured knowledge (concepts, relationships, confidence)
    from raw text input. Works without numpy — pure Python fallback.
    """

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config

        if _HAS_SKLEARN:
            self.vectorizer = TfidfVectorizer(
                max_features=1000, stop_words="english", ngram_range=(1, 2)
            )
        else:
            self.vectorizer = None

        if _HAS_NLTK:
            try:
                nltk.download("punkt", quiet=True)
                nltk.download("stopwords", quiet=True)
                nltk.download("averaged_perceptron_tagger", quiet=True)
                self.stop_words = set(stopwords.words("english"))
            except Exception:
                self.stop_words = set()
        else:
            self.stop_words = set()

        # Source reliability scores
        self._source_scores = {
            "textbook": 0.9, "research_paper": 0.85, "expert": 0.8,
            "documentation": 0.75, "website": 0.6, "user": 0.7,
            "experience": 0.65, "unknown": 0.5,
        }

    def extract_knowledge(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured knowledge from input data."""
        try:
            text = self._extract_text_content(input_data)
            if not text.strip():
                return {}

            concepts = self._extract_concepts(text)
            relationships = self._extract_relationships(text, concepts)
            confidence = self._calculate_confidence(input_data, concepts, text)

            return {
                "domain": input_data.get("domain", "general"),
                "concepts": concepts,
                "relationships": relationships,
                "confidence": round(confidence, 3),
                "source": input_data.get("source", "unknown"),
                "word_count": len(text.split()),
                "sentence_count": len(sent_tokenize(text)),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error extracting knowledge: {e}")
            return {}

    def _extract_text_content(self, input_data: Dict[str, Any]) -> str:
        parts = []
        for key in ("information", "description", "content", "text"):
            val = input_data.get(key, "")
            if val:
                parts.append(str(val))
        return " ".join(parts)

    def _extract_concepts(self, text: str) -> List[Dict[str, Any]]:
        try:
            concepts = []
            sentences = sent_tokenize(text)
            for sentence in sentences:
                if not sentence.strip():
                    continue
                tokens = word_tokenize(sentence)
                tagged = pos_tag(tokens)
                noun_phrases = self._extract_noun_phrases(tagged)
                for phrase in noun_phrases:
                    if len(phrase) < 3:
                        continue
                    conf = self._calculate_concept_confidence(phrase, sentence)
                    concepts.append({
                        "term": phrase,
                        "context": sentence[:120],
                        "confidence": round(conf, 3),
                    })
            # Deduplicate by term
            seen = set()
            unique = []
            for c in concepts:
                if c["term"] not in seen:
                    seen.add(c["term"])
                    unique.append(c)
            return unique[:20]
        except Exception as e:
            self.logger.error(f"Error extracting concepts: {e}")
            return []

    def _extract_noun_phrases(self, tagged: List[tuple]) -> List[str]:
        try:
            phrases = []
            current: List[str] = []
            for token, tag in tagged:
                if tag.startswith("NN"):
                    current.append(token)
                else:
                    if current:
                        phrases.append(" ".join(current))
                        current = []
            if current:
                phrases.append(" ".join(current))
            # Filter out stopwords and very short phrases
            return [p for p in phrases if p.lower() not in self.stop_words and len(p) >= 3]
        except Exception as e:
            self.logger.error(f"Error extracting noun phrases: {e}")
            return []

    def _extract_relationships(self, text: str, concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            relationships = []
            sentences = sent_tokenize(text)
            for sentence in sentences:
                sentence_concepts = [c for c in concepts if c["term"].lower() in sentence.lower()]
                for i, c1 in enumerate(sentence_concepts):
                    for c2 in sentence_concepts[i + 1:]:
                        rel_type = self._determine_relationship_type(sentence)
                        relationships.append({
                            "source": c1["term"],
                            "target": c2["term"],
                            "type": rel_type,
                            "context": sentence[:120],
                            "confidence": round(min(c1["confidence"], c2["confidence"]), 3),
                        })
            return relationships[:30]
        except Exception as e:
            self.logger.error(f"Error extracting relationships: {e}")
            return []

    def _determine_relationship_type(self, sentence: str) -> str:
        lower = sentence.lower()
        if any(w in lower for w in ["is", "are", "was", "were", "means", "refers"]):
            return "is_a"
        if any(w in lower for w in ["has", "have", "had", "contains", "includes"]):
            return "has_a"
        if any(w in lower for w in ["can", "could", "able to", "capable"]):
            return "can_do"
        if any(w in lower for w in ["requires", "needs", "depends", "relies"]):
            return "requires"
        if any(w in lower for w in ["similar", "like", "resembles", "same as"]):
            return "similar_to"
        if any(w in lower for w in ["opposite", "different", "unlike", "contrast"]):
            return "opposite_to"
        return "related_to"

    def _calculate_concept_confidence(self, concept: str, context: str) -> float:
        factors = []
        # Length: multi-word concepts are more specific
        word_count = len(concept.split())
        factors.append(min(1.0, word_count / 4.0))
        # Position: earlier in sentence = more important
        words = context.split()
        if words:
            pos = context.lower().find(concept.lower())
            pos_ratio = pos / max(len(context), 1)
            factors.append(max(0.1, 1.0 - pos_ratio))
        # Not a stopword
        factors.append(0.8 if concept.lower() not in self.stop_words else 0.3)
        # Capitalized = proper noun = higher confidence
        factors.append(0.9 if concept[0].isupper() else 0.6)
        return _mean(factors)

    def _calculate_confidence(self, input_data: Dict[str, Any],
                              concepts: List[Dict[str, Any]], text: str) -> float:
        factors = []
        # Source reliability
        source = input_data.get("source", "unknown").lower()
        factors.append(self._source_scores.get(source, 0.5))
        # Text quality
        factors.append(self._calculate_text_quality(text))
        # Concept confidence average
        if concepts:
            factors.append(_mean([c["confidence"] for c in concepts]))
        return _mean(factors)

    def _calculate_text_quality(self, text: str) -> float:
        if not text:
            return 0.0
        words = text.split()
        if not words:
            return 0.0
        factors = [
            min(1.0, len(words) / 100.0),                          # length
            len(set(words)) / len(words),                           # vocabulary diversity
            min(1.0, len(sent_tokenize(text)) / 5.0),              # sentence count
        ]
        return _mean(factors)

    def reset(self):
        if _HAS_SKLEARN:
            self.vectorizer = TfidfVectorizer(
                max_features=1000, stop_words="english", ngram_range=(1, 2)
            )
