import logging
from typing import Dict, Any, List, Optional
import numpy as np
from datetime import datetime, timedelta
import json
import os

class ExperienceManager:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the experience manager."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.experiences = []
        self.max_experiences = config.get("max_experiences", 1000)
        self.experience_weights = {}
        self.last_update = datetime.now()
        
    def process_experience(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        """Process a new learning experience."""
        try:
            # Add timestamp if not present
            if "timestamp" not in experience:
                experience["timestamp"] = datetime.now().isoformat()
                
            # Calculate experience metrics
            metrics = self._calculate_experience_metrics(experience)
            experience["metrics"] = metrics
            
            # Update experience weights
            self._update_experience_weights(experience)
            
            # Add to experiences list
            self.experiences.append(experience)
            
            # Maintain maximum size
            if len(self.experiences) > self.max_experiences:
                self.experiences = self.experiences[-self.max_experiences:]
                
            # Update last update time
            self.last_update = datetime.now()
            
            return experience
        except Exception as e:
            self.logger.error(f"Error processing experience: {e}")
            return {}
            
    def get_relevant_experiences(self, context: Dict[str, Any],
                               max_experiences: int = 5) -> List[Dict[str, Any]]:
        """Get experiences relevant to the given context."""
        try:
            # Calculate relevance scores
            relevance_scores = []
            for experience in self.experiences:
                score = self._calculate_relevance(experience, context)
                relevance_scores.append((experience, score))
                
            # Sort by relevance
            relevance_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Return top experiences
            return [exp for exp, _ in relevance_scores[:max_experiences]]
        except Exception as e:
            self.logger.error(f"Error getting relevant experiences: {e}")
            return []
            
    def get_experience_insights(self) -> Dict[str, Any]:
        """Get insights from accumulated experiences."""
        try:
            insights = {
                "total_experiences": len(self.experiences),
                "domains": self._get_domain_distribution(),
                "success_rate": self._calculate_success_rate(),
                "learning_trends": self._analyze_learning_trends(),
                "common_patterns": self._identify_common_patterns(),
                "last_update": self.last_update.isoformat()
            }
            
            return insights
        except Exception as e:
            self.logger.error(f"Error getting experience insights: {e}")
            return {}
            
    def _calculate_experience_metrics(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metrics for an experience."""
        try:
            metrics = {
                "complexity": self._calculate_complexity(experience),
                "success": self._calculate_success(experience),
                "learning_value": self._calculate_learning_value(experience),
                "applicability": self._calculate_applicability(experience)
            }
            
            return metrics
        except Exception as e:
            self.logger.error(f"Error calculating experience metrics: {e}")
            return {}
            
    def _calculate_complexity(self, experience: Dict[str, Any]) -> float:
        """Calculate complexity score for an experience."""
        try:
            factors = []
            
            # Input complexity
            if "input" in experience:
                input_complexity = len(str(experience["input"]).split())
                factors.append(min(1.0, input_complexity / 100.0))
                
            # Number of concepts
            if "concepts" in experience:
                concept_count = len(experience["concepts"])
                factors.append(min(1.0, concept_count / 10.0))
                
            # Number of relationships
            if "relationships" in experience:
                relationship_count = len(experience["relationships"])
                factors.append(min(1.0, relationship_count / 10.0))
                
            return np.mean(factors) if factors else 0.5
        except Exception as e:
            self.logger.error(f"Error calculating complexity: {e}")
            return 0.5
            
    def _calculate_success(self, experience: Dict[str, Any]) -> float:
        """Calculate success score for an experience."""
        try:
            factors = []
            
            # Check for explicit success indicators
            if "success" in experience:
                factors.append(float(experience["success"]))
                
            # Check for error indicators
            if "error" in experience:
                factors.append(0.0 if experience["error"] else 1.0)
                
            # Check for confidence scores
            if "confidence" in experience:
                factors.append(float(experience["confidence"]))
                
            return np.mean(factors) if factors else 0.5
        except Exception as e:
            self.logger.error(f"Error calculating success: {e}")
            return 0.5
            
    def _calculate_learning_value(self, experience: Dict[str, Any]) -> float:
        """Calculate learning value score for an experience."""
        try:
            factors = []
            
            # Novelty of concepts
            if "concepts" in experience:
                concept_novelty = self._calculate_concept_novelty(experience["concepts"])
                factors.append(concept_novelty)
                
            # Quality of relationships
            if "relationships" in experience:
                relationship_quality = self._calculate_relationship_quality(
                    experience["relationships"]
                )
                factors.append(relationship_quality)
                
            # Success impact
            success = self._calculate_success(experience)
            factors.append(success)
            
            return np.mean(factors) if factors else 0.5
        except Exception as e:
            self.logger.error(f"Error calculating learning value: {e}")
            return 0.5
            
    def _calculate_applicability(self, experience: Dict[str, Any]) -> float:
        """Calculate applicability score for an experience."""
        try:
            factors = []
            
            # Domain specificity
            if "domain" in experience:
                domain_specificity = self._calculate_domain_specificity(
                    experience["domain"]
                )
                factors.append(domain_specificity)
                
            # Generalizability
            if "concepts" in experience:
                generalizability = self._calculate_generalizability(
                    experience["concepts"]
                )
                factors.append(generalizability)
                
            return np.mean(factors) if factors else 0.5
        except Exception as e:
            self.logger.error(f"Error calculating applicability: {e}")
            return 0.5
            
    def _update_experience_weights(self, experience: Dict[str, Any]):
        """Update weights for experience types."""
        try:
            # Get experience type
            exp_type = experience.get("type", "unknown")
            
            # Update weight based on success
            success = self._calculate_success(experience)
            current_weight = self.experience_weights.get(exp_type, 0.5)
            
            # Exponential moving average
            alpha = 0.1  # Learning rate
            new_weight = (1 - alpha) * current_weight + alpha * success
            
            self.experience_weights[exp_type] = new_weight
        except Exception as e:
            self.logger.error(f"Error updating experience weights: {e}")
            
    def _calculate_relevance(self, experience: Dict[str, Any],
                           context: Dict[str, Any]) -> float:
        """Calculate relevance score between experience and context."""
        try:
            factors = []
            
            # Domain match
            if "domain" in experience and "domain" in context:
                if experience["domain"] == context["domain"]:
                    factors.append(1.0)
                else:
                    factors.append(0.0)
                    
            # Concept overlap
            if "concepts" in experience and "concepts" in context:
                overlap = self._calculate_concept_overlap(
                    experience["concepts"],
                    context["concepts"]
                )
                factors.append(overlap)
                
            # Temporal relevance
            if "timestamp" in experience:
                time_diff = datetime.now() - datetime.fromisoformat(experience["timestamp"])
                time_factor = np.exp(-time_diff.days / 30.0)  # 30-day half-life
                factors.append(time_factor)
                
            return np.mean(factors) if factors else 0.0
        except Exception as e:
            self.logger.error(f"Error calculating relevance: {e}")
            return 0.0
            
    def _get_domain_distribution(self) -> Dict[str, float]:
        """Get distribution of experiences across domains."""
        try:
            domains = {}
            total = len(self.experiences)
            
            for experience in self.experiences:
                domain = experience.get("domain", "unknown")
                domains[domain] = domains.get(domain, 0) + 1
                
            return {domain: count/total for domain, count in domains.items()}
        except Exception as e:
            self.logger.error(f"Error getting domain distribution: {e}")
            return {}
            
    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate of experiences."""
        try:
            if not self.experiences:
                return 0.0
                
            success_scores = [
                self._calculate_success(exp) for exp in self.experiences
            ]
            return np.mean(success_scores)
        except Exception as e:
            self.logger.error(f"Error calculating success rate: {e}")
            return 0.0
            
    def _analyze_learning_trends(self) -> Dict[str, Any]:
        """Analyze trends in learning experiences."""
        try:
            trends = {
                "success_trend": self._calculate_trend("success"),
                "complexity_trend": self._calculate_trend("complexity"),
                "learning_value_trend": self._calculate_trend("learning_value")
            }
            
            return trends
        except Exception as e:
            self.logger.error(f"Error analyzing learning trends: {e}")
            return {}
            
    def _identify_common_patterns(self) -> List[Dict[str, Any]]:
        """Identify common patterns in experiences."""
        try:
            patterns = []
            
            # Group experiences by domain
            domain_groups = {}
            for exp in self.experiences:
                domain = exp.get("domain", "unknown")
                if domain not in domain_groups:
                    domain_groups[domain] = []
                domain_groups[domain].append(exp)
                
            # Analyze patterns in each domain
            for domain, exps in domain_groups.items():
                if len(exps) >= 3:  # Minimum number of experiences for pattern
                    pattern = {
                        "domain": domain,
                        "common_concepts": self._find_common_concepts(exps),
                        "success_factors": self._identify_success_factors(exps)
                    }
                    patterns.append(pattern)
                    
            return patterns
        except Exception as e:
            self.logger.error(f"Error identifying common patterns: {e}")
            return []
            
    def _calculate_trend(self, metric: str) -> float:
        """Calculate trend for a specific metric."""
        try:
            if not self.experiences:
                return 0.0
                
            # Get metric values over time
            values = []
            for exp in self.experiences:
                if "metrics" in exp and metric in exp["metrics"]:
                    values.append(exp["metrics"][metric])
                    
            if not values:
                return 0.0
                
            # Calculate trend using linear regression
            x = np.arange(len(values))
            y = np.array(values)
            slope = np.polyfit(x, y, 1)[0]
            
            return slope
        except Exception as e:
            self.logger.error(f"Error calculating trend: {e}")
            return 0.0
            
    def _find_common_concepts(self, experiences: List[Dict[str, Any]]) -> List[str]:
        """Find common concepts across experiences."""
        try:
            concept_counts = {}
            
            for exp in experiences:
                if "concepts" in exp:
                    for concept in exp["concepts"]:
                        term = concept.get("term", "")
                        if term:
                            concept_counts[term] = concept_counts.get(term, 0) + 1
                            
            # Get concepts that appear in at least 50% of experiences
            threshold = len(experiences) * 0.5
            return [
                concept for concept, count in concept_counts.items()
                if count >= threshold
            ]
        except Exception as e:
            self.logger.error(f"Error finding common concepts: {e}")
            return []
            
    def _identify_success_factors(self, experiences: List[Dict[str, Any]]) -> List[str]:
        """Identify factors contributing to success."""
        try:
            success_factors = []
            
            # Compare successful vs unsuccessful experiences
            successful = [exp for exp in experiences if self._calculate_success(exp) > 0.7]
            unsuccessful = [exp for exp in experiences if self._calculate_success(exp) < 0.3]
            
            if successful and unsuccessful:
                # Find factors present in successful but not in unsuccessful
                for exp in successful:
                    if "factors" in exp:
                        for factor in exp["factors"]:
                            if not any(factor in u.get("factors", []) for u in unsuccessful):
                                success_factors.append(factor)
                                
            return list(set(success_factors))
        except Exception as e:
            self.logger.error(f"Error identifying success factors: {e}")
            return []
            
    def reset(self):
        """Reset the experience manager."""
        try:
            self.experiences = []
            self.experience_weights = {}
            self.last_update = datetime.now()
        except Exception as e:
            self.logger.error(f"Error resetting experience manager: {e}") 