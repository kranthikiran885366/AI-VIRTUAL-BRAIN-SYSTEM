import logging
from typing import Dict, Any, List, Optional, Set
import numpy as np
from datetime import datetime
import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk

class KnowledgeBase:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the knowledge base."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.knowledge = {}
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        # Initialize NLTK components
        try:
            nltk.download('punkt')
            nltk.download('stopwords')
            self.stop_words = set(stopwords.words('english'))
        except Exception as e:
            self.logger.error(f"Error initializing NLTK: {e}")
            self.stop_words = set()
            
        # Load existing knowledge if available
        self._load_knowledge()
        
    def _load_knowledge(self):
        """Load knowledge from storage."""
        try:
            data_path = self.config.get("storage", {}).get("base_path", "data/learning")
            knowledge_file = os.path.join(data_path, "knowledge.json")
            
            if os.path.exists(knowledge_file):
                with open(knowledge_file, 'r') as f:
                    self.knowledge = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading knowledge: {e}")
            
    def _save_knowledge(self):
        """Save knowledge to storage."""
        try:
            data_path = self.config.get("storage", {}).get("base_path", "data/learning")
            os.makedirs(data_path, exist_ok=True)
            
            knowledge_file = os.path.join(data_path, "knowledge.json")
            with open(knowledge_file, 'w') as f:
                json.dump(self.knowledge, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving knowledge: {e}")
            
    def update(self, new_knowledge: Dict[str, Any]) -> Dict[str, Any]:
        """Update the knowledge base with new information."""
        try:
            domain = new_knowledge.get("domain", "general")
            concept = new_knowledge.get("concept", "unknown")
            
            # Initialize domain if not exists
            if domain not in self.knowledge:
                self.knowledge[domain] = {
                    "concepts": {},
                    "relationships": [],
                    "last_update": datetime.now().isoformat()
                }
                
            # Update concept
            if concept not in self.knowledge[domain]["concepts"]:
                self.knowledge[domain]["concepts"][concept] = {
                    "information": [],
                    "confidence": 0.0,
                    "sources": set(),
                    "last_update": datetime.now().isoformat()
                }
                
            # Add new information
            concept_data = self.knowledge[domain]["concepts"][concept]
            concept_data["information"].append({
                "content": new_knowledge.get("information", ""),
                "source": new_knowledge.get("source", "unknown"),
                "confidence": new_knowledge.get("confidence", 0.5),
                "timestamp": datetime.now().isoformat()
            })
            
            # Update confidence
            concept_data["confidence"] = self._calculate_confidence(concept_data)
            
            # Update sources
            concept_data["sources"].add(new_knowledge.get("source", "unknown"))
            
            # Update relationships
            self._update_relationships(domain, concept, new_knowledge)
            
            # Save changes
            self._save_knowledge()
            
            return {
                "domain": domain,
                "concept": concept,
                "confidence": concept_data["confidence"],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error updating knowledge: {e}")
            return {}
            
    def _calculate_confidence(self, concept_data: Dict[str, Any]) -> float:
        """Calculate confidence score for a concept."""
        try:
            if not concept_data["information"]:
                return 0.0
                
            # Calculate weighted average of information confidence
            confidences = [info["confidence"] for info in concept_data["information"]]
            weights = [1.0 / (i + 1) for i in range(len(confidences))]  # Recent info weighted more
            
            return np.average(confidences, weights=weights)
        except Exception as e:
            self.logger.error(f"Error calculating confidence: {e}")
            return 0.0
            
    def _update_relationships(self, domain: str, concept: str, new_knowledge: Dict[str, Any]):
        """Update relationships between concepts."""
        try:
            # Extract related concepts
            related_concepts = self._extract_related_concepts(
                new_knowledge.get("information", ""),
                domain
            )
            
            # Add relationships
            for related in related_concepts:
                relationship = {
                    "source": concept,
                    "target": related,
                    "type": "related",
                    "confidence": new_knowledge.get("confidence", 0.5),
                    "timestamp": datetime.now().isoformat()
                }
                
                if relationship not in self.knowledge[domain]["relationships"]:
                    self.knowledge[domain]["relationships"].append(relationship)
        except Exception as e:
            self.logger.error(f"Error updating relationships: {e}")
            
    def _extract_related_concepts(self, text: str, domain: str) -> Set[str]:
        """Extract related concepts from text."""
        try:
            related = set()
            
            # Tokenize text
            tokens = word_tokenize(text.lower())
            tokens = [t for t in tokens if t not in self.stop_words]
            
            # Check for known concepts
            for concept in self.knowledge[domain]["concepts"]:
                if concept.lower() in tokens:
                    related.add(concept)
                    
            return related
        except Exception as e:
            self.logger.error(f"Error extracting related concepts: {e}")
            return set()
            
    def get_knowledge(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve knowledge from the knowledge base."""
        try:
            if domain:
                return self.knowledge.get(domain, {})
            return self.knowledge
        except Exception as e:
            self.logger.error(f"Error retrieving knowledge: {e}")
            return {}
            
    def get_metrics(self) -> Dict[str, Any]:
        """Get knowledge base metrics."""
        try:
            total_concepts = 0
            total_relationships = 0
            domain_stats = {}
            
            for domain, data in self.knowledge.items():
                num_concepts = len(data["concepts"])
                num_relationships = len(data["relationships"])
                
                total_concepts += num_concepts
                total_relationships += num_relationships
                
                domain_stats[domain] = {
                    "concepts": num_concepts,
                    "relationships": num_relationships,
                    "last_update": data["last_update"]
                }
                
            return {
                "total_concepts": total_concepts,
                "total_relationships": total_relationships,
                "domains": domain_stats,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error getting metrics: {e}")
            return {}
            
    def reset(self):
        """Reset the knowledge base."""
        try:
            self.knowledge = {}
            self._save_knowledge()
        except Exception as e:
            self.logger.error(f"Error resetting knowledge base: {e}")
            
    def find_similar_concepts(self, concept: str, domain: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Find similar concepts in the knowledge base."""
        try:
            if domain not in self.knowledge:
                return []
                
            similar = []
            concept_data = self.knowledge[domain]["concepts"].get(concept, {})
            
            if not concept_data:
                return []
                
            # Get concept information
            concept_info = " ".join([info["content"] for info in concept_data["information"]])
            
            # Compare with other concepts
            for other_concept, other_data in self.knowledge[domain]["concepts"].items():
                if other_concept == concept:
                    continue
                    
                other_info = " ".join([info["content"] for info in other_data["information"]])
                
                # Calculate similarity
                similarity = self._calculate_text_similarity(concept_info, other_info)
                
                if similarity >= threshold:
                    similar.append({
                        "concept": other_concept,
                        "similarity": similarity,
                        "confidence": other_data["confidence"]
                    })
                    
            return sorted(similar, key=lambda x: x["similarity"], reverse=True)
        except Exception as e:
            self.logger.error(f"Error finding similar concepts: {e}")
            return []
            
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        try:
            # Convert texts to TF-IDF vectors
            vectors = self.vectorizer.fit_transform([text1, text2])
            
            # Calculate cosine similarity
            similarity = (vectors * vectors.T).toarray()[0, 1]
            
            return float(similarity)
        except Exception as e:
            self.logger.error(f"Error calculating text similarity: {e}")
            return 0.0 