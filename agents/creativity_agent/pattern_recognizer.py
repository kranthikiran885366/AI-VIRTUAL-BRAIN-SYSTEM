import logging
from typing import Dict, Any, List, Optional
import numpy as np
from datetime import datetime
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk

class PatternRecognizer:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.pattern_history = []
        self.max_history = config.get("max_pattern_history", 1000)
        
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
        
    def analyze_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze patterns in the given context."""
        try:
            # Extract different types of patterns
            structural_patterns = self._analyze_structural_patterns(context)
            temporal_patterns = self._analyze_temporal_patterns(context)
            semantic_patterns = self._analyze_semantic_patterns(context)
            
            # Combine all patterns
            patterns = {
                "timestamp": datetime.now().isoformat(),
                "structural": structural_patterns,
                "temporal": temporal_patterns,
                "semantic": semantic_patterns,
                "influence": self._calculate_pattern_influence(
                    structural_patterns,
                    temporal_patterns,
                    semantic_patterns
                )
            }
            
            # Update pattern history
            self._update_pattern_history(patterns)
            
            return patterns
        except Exception as e:
            self.logger.error(f"Error analyzing patterns: {e}")
            return {"error": str(e)}
            
    def _analyze_structural_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze structural patterns in the context."""
        try:
            # Extract text data for analysis
            text_data = self._extract_text_data(context)
            
            # Convert text to TF-IDF vectors
            if text_data:
                vectors = self.vectorizer.fit_transform(text_data)
                
                # Perform clustering to identify structural patterns
                clustering = DBSCAN(eps=0.5, min_samples=2).fit(vectors)
                
                # Extract patterns from clusters
                patterns = {
                    "hierarchies": self._extract_hierarchies(text_data, clustering.labels_),
                    "relationships": self._extract_relationships(text_data, vectors),
                    "dependencies": self._extract_dependencies(text_data, vectors)
                }
                
                return patterns
            return {
                "hierarchies": [],
                "relationships": [],
                "dependencies": []
            }
        except Exception as e:
            self.logger.error(f"Error analyzing structural patterns: {e}")
            return {}
            
    def _analyze_temporal_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze temporal patterns in the context."""
        try:
            # Extract temporal data
            temporal_data = self._extract_temporal_data(context)
            
            if not temporal_data:
                return {
                    "sequences": [],
                    "cycles": [],
                    "trends": []
                }
                
            # Analyze sequences
            sequences = self._analyze_sequences(temporal_data)
            
            # Analyze cycles
            cycles = self._analyze_cycles(temporal_data)
            
            # Analyze trends
            trends = self._analyze_trends(temporal_data)
            
            return {
                "sequences": sequences,
                "cycles": cycles,
                "trends": trends
            }
        except Exception as e:
            self.logger.error(f"Error analyzing temporal patterns: {e}")
            return {}
            
    def _analyze_semantic_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze semantic patterns in the context."""
        try:
            # Extract text data
            text_data = self._extract_text_data(context)
            
            if not text_data:
                return {
                    "themes": [],
                    "concepts": [],
                    "associations": []
                }
                
            # Extract themes
            themes = self._extract_themes(text_data)
            
            # Extract concepts
            concepts = self._extract_concepts(text_data)
            
            # Extract associations
            associations = self._extract_associations(text_data)
            
            return {
                "themes": themes,
                "concepts": concepts,
                "associations": associations
            }
        except Exception as e:
            self.logger.error(f"Error analyzing semantic patterns: {e}")
            return {}
            
    def _extract_text_data(self, context: Dict[str, Any]) -> List[str]:
        """Extract text data from context for analysis."""
        try:
            text_data = []
            
            # Extract text from various context fields
            if "domain" in context:
                text_data.append(context["domain"])
            if "constraints" in context:
                text_data.extend(context["constraints"])
            if "goals" in context:
                text_data.extend(context["goals"])
            if "previous_ideas" in context:
                for idea in context["previous_ideas"]:
                    if isinstance(idea, dict):
                        text_data.extend([
                            idea.get("concept", ""),
                            idea.get("approach", ""),
                            idea.get("implementation", "")
                        ])
                    elif isinstance(idea, str):
                        text_data.append(idea)
                        
            return [text for text in text_data if text]
        except Exception as e:
            self.logger.error(f"Error extracting text data: {e}")
            return []
            
    def _extract_temporal_data(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract temporal data from context."""
        try:
            temporal_data = []
            
            # Extract timestamps and events from context
            if "previous_ideas" in context:
                for idea in context["previous_ideas"]:
                    if isinstance(idea, dict) and "metadata" in idea:
                        temporal_data.append({
                            "timestamp": idea["metadata"].get("timestamp"),
                            "event": "idea_generation",
                            "data": idea
                        })
                        
            return temporal_data
        except Exception as e:
            self.logger.error(f"Error extracting temporal data: {e}")
            return []
            
    def _extract_hierarchies(self, text_data: List[str], labels: np.ndarray) -> List[Dict[str, Any]]:
        """Extract hierarchical patterns from clustered text data."""
        try:
            hierarchies = []
            
            # Group text by cluster
            clusters = {}
            for i, label in enumerate(labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(text_data[i])
                
            # Analyze each cluster for hierarchical relationships
            for label, texts in clusters.items():
                if label == -1:  # Skip noise points
                    continue
                    
                # Extract key terms and their relationships
                key_terms = self._extract_key_terms(texts)
                relationships = self._analyze_term_relationships(texts, key_terms)
                
                hierarchies.append({
                    "cluster_id": int(label),
                    "key_terms": key_terms,
                    "relationships": relationships
                })
                
            return hierarchies
        except Exception as e:
            self.logger.error(f"Error extracting hierarchies: {e}")
            return []
            
    def _extract_relationships(self, text_data: List[str], vectors) -> List[Dict[str, Any]]:
        """Extract relationships between different elements in the text data."""
        try:
            relationships = []
            
            # Calculate cosine similarity between vectors
            similarity_matrix = (vectors * vectors.T).toarray()
            
            # Find significant relationships
            for i in range(len(text_data)):
                for j in range(i + 1, len(text_data)):
                    similarity = similarity_matrix[i, j]
                    if similarity > 0.3:  # Threshold for significant relationship
                        relationships.append({
                            "source": text_data[i],
                            "target": text_data[j],
                            "similarity": float(similarity),
                            "type": self._determine_relationship_type(text_data[i], text_data[j])
                        })
                        
            return relationships
        except Exception as e:
            self.logger.error(f"Error extracting relationships: {e}")
            return []
            
    def _extract_dependencies(self, text_data: List[str], vectors) -> List[Dict[str, Any]]:
        """Extract dependencies between different elements in the text data."""
        try:
            dependencies = []
            
            # Analyze text for dependency indicators
            for text in text_data:
                # Tokenize and analyze text
                tokens = word_tokenize(text.lower())
                
                # Look for dependency indicators
                for i, token in enumerate(tokens):
                    if token in ["requires", "needs", "depends", "relies"]:
                        if i + 1 < len(tokens):
                            dependency = {
                                "source": text,
                                "target": " ".join(tokens[i+1:i+3]),
                                "type": "dependency",
                                "confidence": 0.7
                            }
                            dependencies.append(dependency)
                            
            return dependencies
        except Exception as e:
            self.logger.error(f"Error extracting dependencies: {e}")
            return []
            
    def _analyze_sequences(self, temporal_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze sequences in temporal data."""
        try:
            sequences = []
            
            # Sort data by timestamp
            sorted_data = sorted(temporal_data, key=lambda x: x.get("timestamp", ""))
            
            # Identify sequences of related events
            current_sequence = []
            for i, event in enumerate(sorted_data):
                if not current_sequence:
                    current_sequence.append(event)
                else:
                    # Check if event is related to current sequence
                    if self._are_events_related(current_sequence[-1], event):
                        current_sequence.append(event)
                    else:
                        if len(current_sequence) > 1:
                            sequences.append({
                                "events": current_sequence,
                                "type": "sequence",
                                "confidence": 0.8
                            })
                        current_sequence = [event]
                        
            # Add last sequence if it exists
            if len(current_sequence) > 1:
                sequences.append({
                    "events": current_sequence,
                    "type": "sequence",
                    "confidence": 0.8
                })
                
            return sequences
        except Exception as e:
            self.logger.error(f"Error analyzing sequences: {e}")
            return []
            
    def _analyze_cycles(self, temporal_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze cycles in temporal data."""
        try:
            cycles = []
            
            # Group events by type
            event_groups = {}
            for event in temporal_data:
                event_type = event.get("event", "unknown")
                if event_type not in event_groups:
                    event_groups[event_type] = []
                event_groups[event_type].append(event)
                
            # Analyze each group for cycles
            for event_type, events in event_groups.items():
                if len(events) >= 3:  # Minimum events for a cycle
                    # Calculate time intervals between events
                    intervals = self._calculate_time_intervals(events)
                    
                    # Check for regular intervals
                    if self._is_regular_cycle(intervals):
                        cycles.append({
                            "event_type": event_type,
                            "events": events,
                            "interval": np.mean(intervals),
                            "confidence": 0.7
                        })
                        
            return cycles
        except Exception as e:
            self.logger.error(f"Error analyzing cycles: {e}")
            return []
            
    def _analyze_trends(self, temporal_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze trends in temporal data."""
        try:
            trends = []
            
            # Group events by type
            event_groups = {}
            for event in temporal_data:
                event_type = event.get("event", "unknown")
                if event_type not in event_groups:
                    event_groups[event_type] = []
                event_groups[event_type].append(event)
                
            # Analyze each group for trends
            for event_type, events in event_groups.items():
                if len(events) >= 2:  # Minimum events for a trend
                    # Calculate trend metrics
                    trend_metrics = self._calculate_trend_metrics(events)
                    
                    if trend_metrics["confidence"] > 0.6:
                        trends.append({
                            "event_type": event_type,
                            "direction": trend_metrics["direction"],
                            "magnitude": trend_metrics["magnitude"],
                            "confidence": trend_metrics["confidence"]
                        })
                        
            return trends
        except Exception as e:
            self.logger.error(f"Error analyzing trends: {e}")
            return []
            
    def _extract_themes(self, text_data: List[str]) -> List[Dict[str, Any]]:
        """Extract themes from text data."""
        try:
            themes = []
            
            # Convert text to TF-IDF vectors
            vectors = self.vectorizer.fit_transform(text_data)
            
            # Get feature names (terms)
            feature_names = self.vectorizer.get_feature_names_out()
            
            # Extract top terms for each document
            for i, text in enumerate(text_data):
                vector = vectors[i].toarray()[0]
                top_indices = vector.argsort()[-5:][::-1]  # Top 5 terms
                
                theme = {
                    "text": text,
                    "terms": [feature_names[idx] for idx in top_indices],
                    "scores": [float(vector[idx]) for idx in top_indices],
                    "confidence": 0.8
                }
                themes.append(theme)
                
            return themes
        except Exception as e:
            self.logger.error(f"Error extracting themes: {e}")
            return []
            
    def _extract_concepts(self, text_data: List[str]) -> List[Dict[str, Any]]:
        """Extract concepts from text data."""
        try:
            concepts = []
            
            # Tokenize and process text
            for text in text_data:
                tokens = word_tokenize(text.lower())
                tokens = [t for t in tokens if t not in self.stop_words]
                
                # Extract noun phrases and key terms
                key_terms = self._extract_key_terms([text])
                
                if key_terms:
                    concepts.append({
                        "text": text,
                        "terms": key_terms,
                        "confidence": 0.7
                    })
                    
            return concepts
        except Exception as e:
            self.logger.error(f"Error extracting concepts: {e}")
            return []
            
    def _extract_associations(self, text_data: List[str]) -> List[Dict[str, Any]]:
        """Extract associations between terms in text data."""
        try:
            associations = []
            
            # Convert text to TF-IDF vectors
            vectors = self.vectorizer.fit_transform(text_data)
            
            # Get feature names (terms)
            feature_names = self.vectorizer.get_feature_names_out()
            
            # Calculate term co-occurrence
            for i, text in enumerate(text_data):
                vector = vectors[i].toarray()[0]
                top_indices = vector.argsort()[-10:][::-1]  # Top 10 terms
                
                # Create associations between top terms
                for j in range(len(top_indices)):
                    for k in range(j + 1, len(top_indices)):
                        associations.append({
                            "term1": feature_names[top_indices[j]],
                            "term2": feature_names[top_indices[k]],
                            "strength": float(vector[top_indices[j]] * vector[top_indices[k]]),
                            "context": text
                        })
                        
            return associations
        except Exception as e:
            self.logger.error(f"Error extracting associations: {e}")
            return []
            
    def _calculate_pattern_influence(self, structural: Dict[str, Any],
                                  temporal: Dict[str, Any],
                                  semantic: Dict[str, Any]) -> Dict[str, float]:
        """Calculate the influence of different pattern types."""
        try:
            # Calculate influence based on pattern confidence and quantity
            structural_influence = self._calculate_type_influence(structural)
            temporal_influence = self._calculate_type_influence(temporal)
            semantic_influence = self._calculate_type_influence(semantic)
            
            # Normalize influences
            total = structural_influence + temporal_influence + semantic_influence
            if total > 0:
                return {
                    "structural": structural_influence / total,
                    "temporal": temporal_influence / total,
                    "semantic": semantic_influence / total
                }
            return {
                "structural": 0.33,
                "temporal": 0.33,
                "semantic": 0.34
            }
        except Exception as e:
            self.logger.error(f"Error calculating pattern influence: {e}")
            return {}
            
    def _calculate_type_influence(self, patterns: Dict[str, Any]) -> float:
        """Calculate influence for a specific pattern type."""
        try:
            influence = 0.0
            count = 0
            
            for pattern_list in patterns.values():
                if isinstance(pattern_list, list):
                    for pattern in pattern_list:
                        if isinstance(pattern, dict):
                            influence += pattern.get("confidence", 0.5)
                            count += 1
                            
            return influence / count if count > 0 else 0.0
        except Exception as e:
            self.logger.error(f"Error calculating type influence: {e}")
            return 0.0
            
    def _extract_key_terms(self, texts: List[str]) -> List[str]:
        """Extract key terms from texts."""
        try:
            # Convert text to TF-IDF vectors
            vectors = self.vectorizer.fit_transform(texts)
            
            # Get feature names (terms)
            feature_names = self.vectorizer.get_feature_names_out()
            
            # Extract top terms
            key_terms = []
            for i in range(len(texts)):
                vector = vectors[i].toarray()[0]
                top_indices = vector.argsort()[-5:][::-1]  # Top 5 terms
                key_terms.extend([feature_names[idx] for idx in top_indices])
                
            return list(set(key_terms))  # Remove duplicates
        except Exception as e:
            self.logger.error(f"Error extracting key terms: {e}")
            return []
            
    def _analyze_term_relationships(self, texts: List[str], key_terms: List[str]) -> List[Dict[str, Any]]:
        """Analyze relationships between key terms."""
        try:
            relationships = []
            
            for text in texts:
                tokens = word_tokenize(text.lower())
                
                # Find co-occurrences of key terms
                for i, term1 in enumerate(key_terms):
                    for term2 in key_terms[i+1:]:
                        if term1 in tokens and term2 in tokens:
                            relationships.append({
                                "term1": term1,
                                "term2": term2,
                                "context": text,
                                "type": "co_occurrence"
                            })
                            
            return relationships
        except Exception as e:
            self.logger.error(f"Error analyzing term relationships: {e}")
            return []
            
    def _determine_relationship_type(self, text1: str, text2: str) -> str:
        """Determine the type of relationship between two texts."""
        try:
            # Simple heuristic for relationship type
            if any(word in text1.lower() for word in ["requires", "needs", "depends"]):
                return "dependency"
            elif any(word in text1.lower() for word in ["similar", "like", "resembles"]):
                return "similarity"
            elif any(word in text1.lower() for word in ["opposite", "different", "unlike"]):
                return "contrast"
            return "related"
        except Exception as e:
            self.logger.error(f"Error determining relationship type: {e}")
            return "unknown"
            
    def _are_events_related(self, event1: Dict[str, Any], event2: Dict[str, Any]) -> bool:
        """Check if two events are related."""
        try:
            # Check event types
            if event1.get("event") != event2.get("event"):
                return False
                
            # Check time proximity (within 1 hour)
            time1 = datetime.fromisoformat(event1.get("timestamp", ""))
            time2 = datetime.fromisoformat(event2.get("timestamp", ""))
            time_diff = abs((time2 - time1).total_seconds())
            
            return time_diff <= 3600  # 1 hour in seconds
        except Exception as e:
            self.logger.error(f"Error checking event relationship: {e}")
            return False
            
    def _calculate_time_intervals(self, events: List[Dict[str, Any]]) -> List[float]:
        """Calculate time intervals between events."""
        try:
            intervals = []
            sorted_events = sorted(events, key=lambda x: x.get("timestamp", ""))
            
            for i in range(len(sorted_events) - 1):
                time1 = datetime.fromisoformat(sorted_events[i].get("timestamp", ""))
                time2 = datetime.fromisoformat(sorted_events[i + 1].get("timestamp", ""))
                interval = (time2 - time1).total_seconds()
                intervals.append(interval)
                
            return intervals
        except Exception as e:
            self.logger.error(f"Error calculating time intervals: {e}")
            return []
            
    def _is_regular_cycle(self, intervals: List[float]) -> bool:
        """Check if intervals form a regular cycle."""
        try:
            if len(intervals) < 2:
                return False
                
            # Calculate mean and standard deviation
            mean_interval = np.mean(intervals)
            std_interval = np.std(intervals)
            
            # Check if intervals are relatively consistent
            return std_interval / mean_interval < 0.3  # 30% variation threshold
        except Exception as e:
            self.logger.error(f"Error checking regular cycle: {e}")
            return False
            
    def _calculate_trend_metrics(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate trend metrics for a sequence of events."""
        try:
            if len(events) < 2:
                return {
                    "direction": "unknown",
                    "magnitude": 0.0,
                    "confidence": 0.0
                }
                
            # Sort events by timestamp
            sorted_events = sorted(events, key=lambda x: x.get("timestamp", ""))
            
            # Calculate trend direction and magnitude
            first_event = sorted_events[0]
            last_event = sorted_events[-1]
            
            # Simple trend calculation (placeholder)
            direction = "increasing" if len(sorted_events) > 2 else "stable"
            magnitude = len(sorted_events) / 10.0  # Normalized magnitude
            confidence = min(0.8, magnitude)  # Confidence based on magnitude
            
            return {
                "direction": direction,
                "magnitude": magnitude,
                "confidence": confidence
            }
        except Exception as e:
            self.logger.error(f"Error calculating trend metrics: {e}")
            return {
                "direction": "unknown",
                "magnitude": 0.0,
                "confidence": 0.0
            }
            
    def _update_pattern_history(self, patterns: Dict[str, Any]):
        """Update the history of recognized patterns."""
        try:
            self.pattern_history.append(patterns)
            
            # Maintain history size limit
            if len(self.pattern_history) > self.max_history:
                self.pattern_history = self.pattern_history[-self.max_history:]
        except Exception as e:
            self.logger.error(f"Error updating pattern history: {e}")
            
    def get_pattern_history(self) -> List[Dict[str, Any]]:
        """Get the history of recognized patterns."""
        return self.pattern_history
        
    def clear_pattern_history(self):
        """Clear the history of recognized patterns."""
        self.pattern_history = []
        
    def find_similar_patterns(self, pattern: Dict[str, Any], 
                            threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Find similar patterns in the history."""
        try:
            similar_patterns = []
            
            for historical_pattern in self.pattern_history:
                similarity = self._calculate_pattern_similarity(pattern, historical_pattern)
                if similarity >= threshold:
                    similar_patterns.append({
                        "pattern": historical_pattern,
                        "similarity": similarity
                    })
                    
            return sorted(similar_patterns, key=lambda x: x["similarity"], reverse=True)
        except Exception as e:
            self.logger.error(f"Error finding similar patterns: {e}")
            return []
            
    def _calculate_pattern_similarity(self, pattern1: Dict[str, Any],
                                   pattern2: Dict[str, Any]) -> float:
        """Calculate similarity between two patterns."""
        try:
            # Calculate similarity for each pattern type
            structural_sim = self._calculate_type_similarity(
                pattern1.get("structural", {}),
                pattern2.get("structural", {})
            )
            temporal_sim = self._calculate_type_similarity(
                pattern1.get("temporal", {}),
                pattern2.get("temporal", {})
            )
            semantic_sim = self._calculate_type_similarity(
                pattern1.get("semantic", {}),
                pattern2.get("semantic", {})
            )
            
            # Weighted average of similarities
            weights = pattern1.get("influence", {
                "structural": 0.33,
                "temporal": 0.33,
                "semantic": 0.34
            })
            
            return (
                structural_sim * weights["structural"] +
                temporal_sim * weights["temporal"] +
                semantic_sim * weights["semantic"]
            )
        except Exception as e:
            self.logger.error(f"Error calculating pattern similarity: {e}")
            return 0.0
            
    def _calculate_type_similarity(self, type1: Dict[str, Any],
                                type2: Dict[str, Any]) -> float:
        """Calculate similarity between two pattern types."""
        try:
            if not type1 or not type2:
                return 0.0
                
            # Calculate similarity for each sub-type
            similarities = []
            for key in type1.keys():
                if key in type2:
                    list1 = type1[key]
                    list2 = type2[key]
                    if isinstance(list1, list) and isinstance(list2, list):
                        sim = self._calculate_list_similarity(list1, list2)
                        similarities.append(sim)
                        
            return np.mean(similarities) if similarities else 0.0
        except Exception as e:
            self.logger.error(f"Error calculating type similarity: {e}")
            return 0.0
            
    def _calculate_list_similarity(self, list1: List[Any],
                                list2: List[Any]) -> float:
        """Calculate similarity between two lists of patterns."""
        try:
            if not list1 or not list2:
                return 0.0
                
            # Convert lists to sets of strings for comparison
            set1 = {str(item) for item in list1}
            set2 = {str(item) for item in list2}
            
            # Calculate Jaccard similarity
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            
            return intersection / union if union > 0 else 0.0
        except Exception as e:
            self.logger.error(f"Error calculating list similarity: {e}")
            return 0.0 