import logging
from typing import Dict, Any, List, Optional
import random
from datetime import datetime
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk
import json
import os

class InspirationEngine:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.inspiration_sources = self._initialize_sources()
        self.inspiration_history = []
        self.max_history = config.get("max_inspiration_history", 1000)
        
        # Initialize NLTK components
        try:
            nltk.download('punkt')
            nltk.download('stopwords')
            self.stop_words = set(stopwords.words('english'))
        except Exception as e:
            self.logger.error(f"Error initializing NLTK: {e}")
            self.stop_words = set()
            
        # Initialize vectorizer for text analysis
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        # Load inspiration data
        self._load_inspiration_data()
        
    def _initialize_sources(self) -> Dict[str, Any]:
        """Initialize inspiration sources."""
        try:
            sources_config = self.config.get("inspiration", {}).get("sources", {})
            
            sources = {}
            for source_name, source_config in sources_config.items():
                if source_config.get("enabled", True):
                    sources[source_name] = {
                        "name": source_name,
                        "type": self._get_source_type(source_name),
                        "elements": source_config.get("elements", []),
                        "weight": source_config.get("weight", 0.2),
                        "data": []
                    }
                    
            return sources
        except Exception as e:
            self.logger.error(f"Error initializing inspiration sources: {e}")
            return {}
            
    def _get_source_type(self, source_name: str) -> str:
        """Get the type of an inspiration source."""
        source_types = {
            "art": "creative",
            "science": "analytical",
            "nature": "organic",
            "technology": "innovative",
            "culture": "social"
        }
        return source_types.get(source_name, "general")
        
    def _load_inspiration_data(self):
        """Load inspiration data from files."""
        try:
            data_path = self.config.get("storage", {}).get("base_path", "data/creativity")
            
            for source_name, source in self.inspiration_sources.items():
                file_path = os.path.join(data_path, f"{source_name}_inspiration.json")
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        source["data"] = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading inspiration data: {e}")
            
    def get_inspiration(self, context: Dict[str, Any], 
                       patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Get creative inspiration based on context and patterns."""
        try:
            # Select relevant sources
            relevant_sources = self._select_relevant_sources(context, patterns)
            
            # Gather inspiration from each source
            inspiration_elements = []
            sources_used = []
            
            for source_name, source in relevant_sources.items():
                elements = self._gather_inspiration_from_source(source, context, patterns)
                if elements:
                    inspiration_elements.extend(elements)
                    sources_used.append(source_name)
                    
            # Combine and process inspiration
            combined_inspiration = self._combine_inspiration_elements(
                inspiration_elements,
                context,
                patterns
            )
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "elements": combined_inspiration,
                "sources": sources_used,
                "relevance": self._calculate_relevance(combined_inspiration, context)
            }
            
            # Update inspiration history
            self._update_inspiration_history(result)
            
            return result
        except Exception as e:
            self.logger.error(f"Error getting inspiration: {e}")
            return {"error": str(e)}
            
    def _select_relevant_sources(self, context: Dict[str, Any],
                               patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Select relevant inspiration sources based on context and patterns."""
        try:
            relevant_sources = {}
            
            # Extract key terms from context
            context_terms = self._extract_key_terms(context)
            
            for source_name, source in self.inspiration_sources.items():
                if self._is_source_relevant(source, context_terms, patterns):
                    relevant_sources[source_name] = source
                    
            return relevant_sources
        except Exception as e:
            self.logger.error(f"Error selecting relevant sources: {e}")
            return {}
            
    def _is_source_relevant(self, source: Dict[str, Any], context_terms: List[str],
                          patterns: Dict[str, Any]) -> bool:
        """Check if an inspiration source is relevant to the context."""
        try:
            # Check source type against context
            source_type = source.get("type", "")
            if source_type == "creative" and "art" in context_terms:
                return True
            if source_type == "analytical" and "science" in context_terms:
                return True
            if source_type == "organic" and "nature" in context_terms:
                return True
            if source_type == "innovative" and "technology" in context_terms:
                return True
            if source_type == "social" and "culture" in context_terms:
                return True
                
            # Check source elements against context terms
            source_elements = source.get("elements", [])
            for element in source_elements:
                if element in context_terms:
                    return True
                    
            # Check patterns
            semantic_patterns = patterns.get("semantic", {})
            themes = semantic_patterns.get("themes", [])
            for theme in themes:
                theme_terms = theme.get("terms", [])
                if any(term in source_elements for term in theme_terms):
                    return True
                    
            return False
        except Exception as e:
            self.logger.error(f"Error checking source relevance: {e}")
            return False
            
    def _gather_inspiration_from_source(self, source: Dict[str, Any],
                                      context: Dict[str, Any],
                                      patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Gather inspiration elements from a source."""
        try:
            elements = []
            source_data = source.get("data", [])
            
            # Extract key terms from context
            context_terms = self._extract_key_terms(context)
            
            # Find relevant elements
            for element in source_data:
                if self._is_element_relevant(element, context_terms, patterns):
                    elements.append({
                        "type": element.get("type", "unknown"),
                        "content": element.get("content", ""),
                        "source": source.get("name", "unknown"),
                        "relevance": self._calculate_element_relevance(element, context_terms)
                    })
                    
            # Limit number of elements
            max_elements = self.config.get("inspiration", {}).get("max_elements_per_source", 10)
            return elements[:max_elements]
        except Exception as e:
            self.logger.error(f"Error gathering inspiration from source: {e}")
            return []
            
    def _is_element_relevant(self, element: Dict[str, Any], context_terms: List[str],
                           patterns: Dict[str, Any]) -> bool:
        """Check if an inspiration element is relevant."""
        try:
            # Check element type
            element_type = element.get("type", "")
            if element_type in context_terms:
                return True
                
            # Check element content
            content = element.get("content", "").lower()
            if any(term in content for term in context_terms):
                return True
                
            # Check against patterns
            semantic_patterns = patterns.get("semantic", {})
            themes = semantic_patterns.get("themes", [])
            for theme in themes:
                theme_terms = theme.get("terms", [])
                if any(term in content for term in theme_terms):
                    return True
                    
            return False
        except Exception as e:
            self.logger.error(f"Error checking element relevance: {e}")
            return False
            
    def _calculate_element_relevance(self, element: Dict[str, Any],
                                   context_terms: List[str]) -> float:
        """Calculate the relevance score of an inspiration element."""
        try:
            content = element.get("content", "").lower()
            
            # Count matching terms
            matches = sum(1 for term in context_terms if term in content)
            
            # Calculate relevance score
            if matches > 0:
                return min(1.0, matches / len(context_terms))
            return 0.0
        except Exception as e:
            self.logger.error(f"Error calculating element relevance: {e}")
            return 0.0
            
    def _combine_inspiration_elements(self, elements: List[Dict[str, Any]],
                                    context: Dict[str, Any],
                                    patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Combine and process inspiration elements."""
        try:
            if not elements:
                return []
                
            # Sort elements by relevance
            sorted_elements = sorted(elements, key=lambda x: x["relevance"], reverse=True)
            
            # Group elements by type
            grouped_elements = {}
            for element in sorted_elements:
                element_type = element["type"]
                if element_type not in grouped_elements:
                    grouped_elements[element_type] = []
                grouped_elements[element_type].append(element)
                
            # Combine elements
            combined = []
            for element_type, type_elements in grouped_elements.items():
                combined.append({
                    "type": element_type,
                    "elements": type_elements,
                    "relevance": np.mean([e["relevance"] for e in type_elements])
                })
                
            return combined
        except Exception as e:
            self.logger.error(f"Error combining inspiration elements: {e}")
            return []
            
    def _calculate_relevance(self, inspiration: List[Dict[str, Any]],
                           context: Dict[str, Any]) -> float:
        """Calculate the overall relevance of inspiration to the context."""
        try:
            if not inspiration:
                return 0.0
                
            # Calculate weighted average of element relevance
            total_weight = 0.0
            weighted_sum = 0.0
            
            for element_group in inspiration:
                weight = self._get_element_type_weight(element_group["type"])
                total_weight += weight
                weighted_sum += element_group["relevance"] * weight
                
            return weighted_sum / total_weight if total_weight > 0 else 0.0
        except Exception as e:
            self.logger.error(f"Error calculating relevance: {e}")
            return 0.0
            
    def _get_element_type_weight(self, element_type: str) -> float:
        """Get the weight for an element type."""
        weights = {
            "concept": 0.4,
            "approach": 0.3,
            "implementation": 0.3
        }
        return weights.get(element_type, 0.2)
        
    def _extract_key_terms(self, context: Dict[str, Any]) -> List[str]:
        """Extract key terms from context."""
        try:
            terms = []
            
            # Extract terms from various context fields
            if "domain" in context:
                terms.extend(self._tokenize_text(context["domain"]))
            if "constraints" in context:
                for constraint in context["constraints"]:
                    terms.extend(self._tokenize_text(constraint))
            if "goals" in context:
                for goal in context["goals"]:
                    terms.extend(self._tokenize_text(goal))
                    
            return list(set(terms))  # Remove duplicates
        except Exception as e:
            self.logger.error(f"Error extracting key terms: {e}")
            return []
            
    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize and clean text."""
        try:
            # Tokenize text
            tokens = word_tokenize(text.lower())
            
            # Remove stop words and short tokens
            tokens = [t for t in tokens if t not in self.stop_words and len(t) > 2]
            
            return tokens
        except Exception as e:
            self.logger.error(f"Error tokenizing text: {e}")
            return []
            
    def _update_inspiration_history(self, inspiration: Dict[str, Any]):
        """Update the history of inspiration."""
        try:
            self.inspiration_history.append(inspiration)
            
            # Maintain history size limit
            if len(self.inspiration_history) > self.max_history:
                self.inspiration_history = self.inspiration_history[-self.max_history:]
        except Exception as e:
            self.logger.error(f"Error updating inspiration history: {e}")
            
    def get_inspiration_history(self) -> List[Dict[str, Any]]:
        """Get the history of inspiration."""
        return self.inspiration_history
        
    def clear_inspiration_history(self):
        """Clear the history of inspiration."""
        self.inspiration_history = []
        
    def _initialize_art_source(self) -> Dict[str, Any]:
        """Initialize the art inspiration source."""
        return {
            "name": "art",
            "type": "creative",
            "elements": ["visual", "conceptual", "emotional"],
            "data": [
                {
                    "type": "concept",
                    "content": "Abstract expressionism in digital form",
                    "category": "visual"
                },
                {
                    "type": "approach",
                    "content": "Using color theory and composition principles",
                    "category": "conceptual"
                }
            ]
        }
        
    def _initialize_science_source(self) -> Dict[str, Any]:
        """Initialize the science inspiration source."""
        return {
            "name": "science",
            "type": "analytical",
            "elements": ["principles", "discoveries", "theories"],
            "data": [
                {
                    "type": "concept",
                    "content": "Applying quantum computing principles",
                    "category": "principles"
                },
                {
                    "type": "approach",
                    "content": "Using scientific method for validation",
                    "category": "theories"
                }
            ]
        }
        
    def _initialize_nature_source(self) -> Dict[str, Any]:
        """Initialize the nature inspiration source."""
        return {
            "name": "nature",
            "type": "organic",
            "elements": ["patterns", "systems", "adaptations"],
            "data": [
                {
                    "type": "concept",
                    "content": "Biomimicry in system design",
                    "category": "patterns"
                },
                {
                    "type": "approach",
                    "content": "Adaptive learning from natural systems",
                    "category": "systems"
                }
            ]
        }
        
    def _initialize_technology_source(self) -> Dict[str, Any]:
        """Initialize the technology inspiration source."""
        return {
            "name": "technology",
            "type": "innovative",
            "elements": ["solutions", "advancements", "applications"],
            "data": [
                {
                    "type": "concept",
                    "content": "Blockchain-based trust systems",
                    "category": "solutions"
                },
                {
                    "type": "approach",
                    "content": "Microservices architecture",
                    "category": "applications"
                }
            ]
        }
        
    def _initialize_culture_source(self) -> Dict[str, Any]:
        """Initialize the culture inspiration source."""
        return {
            "name": "culture",
            "type": "social",
            "elements": ["traditions", "values", "expressions"],
            "data": [
                {
                    "type": "concept",
                    "content": "Cultural heritage preservation",
                    "category": "traditions"
                },
                {
                    "type": "approach",
                    "content": "Community-driven development",
                    "category": "values"
                }
            ]
        } 