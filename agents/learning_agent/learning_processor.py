import logging
from typing import Dict, Any, List, Optional
import numpy as np
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.tag import pos_tag
import nltk

class LearningProcessor:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the learning processor."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        # Initialize NLTK components
        try:
            nltk.download('punkt')
            nltk.download('stopwords')
            nltk.download('averaged_perceptron_tagger')
            self.stop_words = set(stopwords.words('english'))
        except Exception as e:
            self.logger.error(f"Error initializing NLTK: {e}")
            self.stop_words = set()
            
    def extract_knowledge(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract knowledge from input data."""
        try:
            # Extract text content
            text_content = self._extract_text_content(input_data)
            
            # Extract key concepts
            concepts = self._extract_concepts(text_content)
            
            # Extract relationships
            relationships = self._extract_relationships(text_content, concepts)
            
            # Calculate confidence
            confidence = self._calculate_confidence(input_data, concepts)
            
            return {
                "domain": input_data.get("domain", "general"),
                "concepts": concepts,
                "relationships": relationships,
                "confidence": confidence,
                "source": input_data.get("source", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error extracting knowledge: {e}")
            return {}
            
    def _extract_text_content(self, input_data: Dict[str, Any]) -> str:
        """Extract text content from input data."""
        try:
            content = []
            
            # Extract from various fields
            if "information" in input_data:
                content.append(input_data["information"])
            if "description" in input_data:
                content.append(input_data["description"])
            if "content" in input_data:
                content.append(input_data["content"])
                
            return " ".join(content)
        except Exception as e:
            self.logger.error(f"Error extracting text content: {e}")
            return ""
            
    def _extract_concepts(self, text: str) -> List[Dict[str, Any]]:
        """Extract key concepts from text."""
        try:
            concepts = []
            
            # Tokenize text into sentences
            sentences = sent_tokenize(text)
            
            for sentence in sentences:
                # Tokenize and tag parts of speech
                tokens = word_tokenize(sentence)
                tagged = pos_tag(tokens)
                
                # Extract noun phrases and key terms
                noun_phrases = self._extract_noun_phrases(tagged)
                
                for phrase in noun_phrases:
                    concepts.append({
                        "term": phrase,
                        "context": sentence,
                        "confidence": self._calculate_concept_confidence(phrase, sentence)
                    })
                    
            return concepts
        except Exception as e:
            self.logger.error(f"Error extracting concepts: {e}")
            return []
            
    def _extract_noun_phrases(self, tagged: List[tuple]) -> List[str]:
        """Extract noun phrases from POS-tagged tokens."""
        try:
            phrases = []
            current_phrase = []
            
            for token, tag in tagged:
                if tag.startswith('NN'):  # Noun
                    current_phrase.append(token)
                elif current_phrase:
                    phrases.append(" ".join(current_phrase))
                    current_phrase = []
                    
            if current_phrase:
                phrases.append(" ".join(current_phrase))
                
            return phrases
        except Exception as e:
            self.logger.error(f"Error extracting noun phrases: {e}")
            return []
            
    def _extract_relationships(self, text: str, concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships between concepts."""
        try:
            relationships = []
            
            # Tokenize text into sentences
            sentences = sent_tokenize(text)
            
            for sentence in sentences:
                # Find concepts in sentence
                sentence_concepts = [
                    concept for concept in concepts
                    if concept["term"] in sentence
                ]
                
                # Create relationships between concepts in same sentence
                for i, concept1 in enumerate(sentence_concepts):
                    for concept2 in sentence_concepts[i+1:]:
                        relationship = {
                            "source": concept1["term"],
                            "target": concept2["term"],
                            "type": self._determine_relationship_type(sentence),
                            "context": sentence,
                            "confidence": min(
                                concept1["confidence"],
                                concept2["confidence"]
                            )
                        }
                        relationships.append(relationship)
                        
            return relationships
        except Exception as e:
            self.logger.error(f"Error extracting relationships: {e}")
            return []
            
    def _determine_relationship_type(self, sentence: str) -> str:
        """Determine the type of relationship in a sentence."""
        try:
            sentence = sentence.lower()
            
            # Check for relationship indicators
            if any(word in sentence for word in ["is", "are", "was", "were"]):
                return "is_a"
            elif any(word in sentence for word in ["has", "have", "had"]):
                return "has_a"
            elif any(word in sentence for word in ["can", "could", "able to"]):
                return "can_do"
            elif any(word in sentence for word in ["requires", "needs", "depends"]):
                return "requires"
            elif any(word in sentence for word in ["similar", "like", "resembles"]):
                return "similar_to"
            elif any(word in sentence for word in ["opposite", "different", "unlike"]):
                return "opposite_to"
            else:
                return "related_to"
        except Exception as e:
            self.logger.error(f"Error determining relationship type: {e}")
            return "related_to"
            
    def _calculate_concept_confidence(self, concept: str, context: str) -> float:
        """Calculate confidence score for a concept."""
        try:
            # Factors affecting confidence
            factors = []
            
            # Length of concept
            concept_length = len(concept.split())
            factors.append(min(1.0, concept_length / 5.0))  # Longer phrases more likely to be concepts
            
            # Position in sentence
            sentence_length = len(context.split())
            concept_position = context.find(concept)
            position_ratio = concept_position / sentence_length
            factors.append(1.0 - position_ratio)  # Concepts earlier in sentence more likely to be important
            
            # Presence of determiners
            has_determiner = any(word in concept.lower() for word in ["the", "a", "an"])
            factors.append(0.8 if has_determiner else 0.5)
            
            # Calculate final confidence
            return np.mean(factors)
        except Exception as e:
            self.logger.error(f"Error calculating concept confidence: {e}")
            return 0.5
            
    def _calculate_confidence(self, input_data: Dict[str, Any],
                            concepts: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence in extracted knowledge."""
        try:
            # Factors affecting confidence
            factors = []
            
            # Source reliability
            source = input_data.get("source", "unknown")
            source_confidence = self._get_source_confidence(source)
            factors.append(source_confidence)
            
            # Input quality
            text_content = self._extract_text_content(input_data)
            quality_score = self._calculate_text_quality(text_content)
            factors.append(quality_score)
            
            # Concept confidence
            if concepts:
                concept_confidences = [concept["confidence"] for concept in concepts]
                factors.append(np.mean(concept_confidences))
                
            # Calculate final confidence
            return np.mean(factors)
        except Exception as e:
            self.logger.error(f"Error calculating confidence: {e}")
            return 0.5
            
    def _get_source_confidence(self, source: str) -> float:
        """Get confidence score for a knowledge source."""
        try:
            # Define source reliability scores
            source_scores = {
                "textbook": 0.9,
                "research_paper": 0.85,
                "expert": 0.8,
                "documentation": 0.75,
                "website": 0.6,
                "unknown": 0.5
            }
            
            return source_scores.get(source.lower(), 0.5)
        except Exception as e:
            self.logger.error(f"Error getting source confidence: {e}")
            return 0.5
            
    def _calculate_text_quality(self, text: str) -> float:
        """Calculate quality score for text content."""
        try:
            if not text:
                return 0.0
                
            # Factors affecting quality
            factors = []
            
            # Length
            words = text.split()
            factors.append(min(1.0, len(words) / 100.0))  # Longer texts more likely to be informative
            
            # Vocabulary diversity
            unique_words = set(words)
            factors.append(len(unique_words) / len(words))
            
            # Sentence structure
            sentences = sent_tokenize(text)
            avg_sentence_length = np.mean([len(s.split()) for s in sentences])
            factors.append(min(1.0, avg_sentence_length / 20.0))
            
            # Calculate final quality score
            return np.mean(factors)
        except Exception as e:
            self.logger.error(f"Error calculating text quality: {e}")
            return 0.5
            
    def reset(self):
        """Reset the learning processor."""
        try:
            # Reset vectorizer
            self.vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2)
            )
        except Exception as e:
            self.logger.error(f"Error resetting learning processor: {e}") 