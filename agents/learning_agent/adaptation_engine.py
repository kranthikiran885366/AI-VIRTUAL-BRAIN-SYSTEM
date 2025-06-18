import logging
from typing import Dict, Any, List, Optional
import numpy as np
from datetime import datetime
import json
import os

class AdaptationEngine:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the adaptation engine."""
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.strategies = self._initialize_strategies()
        self.strategy_weights = self._initialize_weights()
        self.adaptation_history = []
        self.max_history = config.get("max_adaptation_history", 100)
        
    def adapt(self, experience: Dict[str, Any],
              current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt learning strategies based on experience and current state."""
        try:
            # Analyze experience
            experience_analysis = self._analyze_experience(experience)
            
            # Evaluate current strategies
            strategy_evaluation = self._evaluate_strategies(
                experience_analysis,
                current_state
            )
            
            # Generate adaptations
            adaptations = self._generate_adaptations(
                strategy_evaluation,
                current_state
            )
            
            # Apply adaptations
            new_state = self._apply_adaptations(adaptations, current_state)
            
            # Update strategy weights
            self._update_strategy_weights(experience_analysis, adaptations)
            
            # Record adaptation
            self._record_adaptation(experience_analysis, adaptations, new_state)
            
            return new_state
        except Exception as e:
            self.logger.error(f"Error adapting strategies: {e}")
            return current_state
            
    def get_adaptation_insights(self) -> Dict[str, Any]:
        """Get insights about adaptation history."""
        try:
            insights = {
                "total_adaptations": len(self.adaptation_history),
                "strategy_usage": self._get_strategy_usage(),
                "adaptation_trends": self._analyze_adaptation_trends(),
                "success_metrics": self._calculate_success_metrics(),
                "last_adaptation": self.adaptation_history[-1] if self.adaptation_history else None
            }
            
            return insights
        except Exception as e:
            self.logger.error(f"Error getting adaptation insights: {e}")
            return {}
            
    def _initialize_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize learning strategies."""
        try:
            return {
                "exploration": {
                    "description": "Explore new concepts and relationships",
                    "parameters": {
                        "exploration_rate": 0.3,
                        "novelty_threshold": 0.5,
                        "diversity_weight": 0.7
                    }
                },
                "exploitation": {
                    "description": "Focus on known successful patterns",
                    "parameters": {
                        "exploitation_rate": 0.7,
                        "success_threshold": 0.6,
                        "confidence_weight": 0.8
                    }
                },
                "generalization": {
                    "description": "Apply learned patterns to new contexts",
                    "parameters": {
                        "generalization_rate": 0.5,
                        "similarity_threshold": 0.4,
                        "context_weight": 0.6
                    }
                },
                "specialization": {
                    "description": "Deep dive into specific domains",
                    "parameters": {
                        "specialization_rate": 0.6,
                        "domain_focus": 0.8,
                        "depth_weight": 0.9
                    }
                }
            }
        except Exception as e:
            self.logger.error(f"Error initializing strategies: {e}")
            return {}
            
    def _initialize_weights(self) -> Dict[str, float]:
        """Initialize strategy weights."""
        try:
            return {
                "exploration": 0.25,
                "exploitation": 0.25,
                "generalization": 0.25,
                "specialization": 0.25
            }
        except Exception as e:
            self.logger.error(f"Error initializing weights: {e}")
            return {}
            
    def _analyze_experience(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze learning experience for adaptation."""
        try:
            analysis = {
                "success": self._calculate_experience_success(experience),
                "complexity": self._calculate_experience_complexity(experience),
                "novelty": self._calculate_experience_novelty(experience),
                "applicability": self._calculate_experience_applicability(experience),
                "domain": experience.get("domain", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
            
            return analysis
        except Exception as e:
            self.logger.error(f"Error analyzing experience: {e}")
            return {}
            
    def _evaluate_strategies(self, experience_analysis: Dict[str, Any],
                           current_state: Dict[str, Any]) -> Dict[str, float]:
        """Evaluate current strategies based on experience."""
        try:
            evaluations = {}
            
            for strategy, weight in self.strategy_weights.items():
                # Calculate strategy-specific metrics
                metrics = self._calculate_strategy_metrics(
                    strategy,
                    experience_analysis,
                    current_state
                )
                
                # Combine metrics with weight
                evaluation = np.mean([
                    metrics["relevance"] * 0.4,
                    metrics["effectiveness"] * 0.4,
                    metrics["efficiency"] * 0.2
                ])
                
                evaluations[strategy] = evaluation
                
            return evaluations
        except Exception as e:
            self.logger.error(f"Error evaluating strategies: {e}")
            return {}
            
    def _generate_adaptations(self, strategy_evaluation: Dict[str, float],
                            current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate adaptations based on strategy evaluation."""
        try:
            adaptations = []
            
            for strategy, evaluation in strategy_evaluation.items():
                if evaluation < 0.5:  # Strategy needs improvement
                    adaptation = self._create_strategy_adaptation(
                        strategy,
                        evaluation,
                        current_state
                    )
                    if adaptation:
                        adaptations.append(adaptation)
                        
            return adaptations
        except Exception as e:
            self.logger.error(f"Error generating adaptations: {e}")
            return []
            
    def _apply_adaptations(self, adaptations: List[Dict[str, Any]],
                          current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply adaptations to current state."""
        try:
            new_state = current_state.copy()
            
            for adaptation in adaptations:
                strategy = adaptation["strategy"]
                parameters = adaptation["parameters"]
                
                # Update strategy parameters
                if strategy in self.strategies:
                    self.strategies[strategy]["parameters"].update(parameters)
                    
                # Update state
                if "state_updates" in adaptation:
                    new_state.update(adaptation["state_updates"])
                    
            return new_state
        except Exception as e:
            self.logger.error(f"Error applying adaptations: {e}")
            return current_state
            
    def _update_strategy_weights(self, experience_analysis: Dict[str, Any],
                               adaptations: List[Dict[str, Any]]):
        """Update strategy weights based on experience and adaptations."""
        try:
            # Calculate success impact
            success_impact = experience_analysis.get("success", 0.5)
            
            # Update weights for adapted strategies
            for adaptation in adaptations:
                strategy = adaptation["strategy"]
                if strategy in self.strategy_weights:
                    # Increase weight for successful adaptations
                    current_weight = self.strategy_weights[strategy]
                    new_weight = current_weight * (1 + success_impact * 0.1)
                    self.strategy_weights[strategy] = min(new_weight, 1.0)
                    
            # Normalize weights
            total_weight = sum(self.strategy_weights.values())
            if total_weight > 0:
                self.strategy_weights = {
                    k: v/total_weight
                    for k, v in self.strategy_weights.items()
                }
        except Exception as e:
            self.logger.error(f"Error updating strategy weights: {e}")
            
    def _record_adaptation(self, experience_analysis: Dict[str, Any],
                          adaptations: List[Dict[str, Any]],
                          new_state: Dict[str, Any]):
        """Record adaptation in history."""
        try:
            record = {
                "timestamp": datetime.now().isoformat(),
                "experience_analysis": experience_analysis,
                "adaptations": adaptations,
                "new_state": new_state
            }
            
            self.adaptation_history.append(record)
            
            # Maintain maximum history size
            if len(self.adaptation_history) > self.max_history:
                self.adaptation_history = self.adaptation_history[-self.max_history:]
        except Exception as e:
            self.logger.error(f"Error recording adaptation: {e}")
            
    def _calculate_experience_success(self, experience: Dict[str, Any]) -> float:
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
            self.logger.error(f"Error calculating experience success: {e}")
            return 0.5
            
    def _calculate_experience_complexity(self, experience: Dict[str, Any]) -> float:
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
            self.logger.error(f"Error calculating experience complexity: {e}")
            return 0.5
            
    def _calculate_experience_novelty(self, experience: Dict[str, Any]) -> float:
        """Calculate novelty score for an experience."""
        try:
            factors = []
            
            # Concept novelty
            if "concepts" in experience:
                concept_novelty = self._calculate_concept_novelty(experience["concepts"])
                factors.append(concept_novelty)
                
            # Relationship novelty
            if "relationships" in experience:
                relationship_novelty = self._calculate_relationship_novelty(
                    experience["relationships"]
                )
                factors.append(relationship_novelty)
                
            return np.mean(factors) if factors else 0.5
        except Exception as e:
            self.logger.error(f"Error calculating experience novelty: {e}")
            return 0.5
            
    def _calculate_experience_applicability(self, experience: Dict[str, Any]) -> float:
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
            self.logger.error(f"Error calculating experience applicability: {e}")
            return 0.5
            
    def _calculate_strategy_metrics(self, strategy: str,
                                  experience_analysis: Dict[str, Any],
                                  current_state: Dict[str, Any]) -> Dict[str, float]:
        """Calculate metrics for a specific strategy."""
        try:
            metrics = {
                "relevance": self._calculate_strategy_relevance(
                    strategy,
                    experience_analysis
                ),
                "effectiveness": self._calculate_strategy_effectiveness(
                    strategy,
                    experience_analysis
                ),
                "efficiency": self._calculate_strategy_efficiency(
                    strategy,
                    current_state
                )
            }
            
            return metrics
        except Exception as e:
            self.logger.error(f"Error calculating strategy metrics: {e}")
            return {"relevance": 0.5, "effectiveness": 0.5, "efficiency": 0.5}
            
    def _create_strategy_adaptation(self, strategy: str,
                                  evaluation: float,
                                  current_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create adaptation for a specific strategy."""
        try:
            if strategy not in self.strategies:
                return None
                
            # Get current parameters
            current_params = self.strategies[strategy]["parameters"]
            
            # Calculate parameter adjustments
            adjustments = {}
            for param, value in current_params.items():
                if evaluation < 0.3:  # Significant improvement needed
                    adjustments[param] = value * 1.5
                elif evaluation < 0.5:  # Moderate improvement needed
                    adjustments[param] = value * 1.2
                    
            if not adjustments:
                return None
                
            return {
                "strategy": strategy,
                "parameters": adjustments,
                "state_updates": {
                    f"{strategy}_last_adaptation": datetime.now().isoformat(),
                    f"{strategy}_adaptation_count": current_state.get(
                        f"{strategy}_adaptation_count", 0
                    ) + 1
                }
            }
        except Exception as e:
            self.logger.error(f"Error creating strategy adaptation: {e}")
            return None
            
    def _get_strategy_usage(self) -> Dict[str, float]:
        """Get usage statistics for strategies."""
        try:
            usage = {strategy: 0.0 for strategy in self.strategies}
            total_adaptations = len(self.adaptation_history)
            
            if total_adaptations == 0:
                return usage
                
            for record in self.adaptation_history:
                for adaptation in record["adaptations"]:
                    strategy = adaptation["strategy"]
                    if strategy in usage:
                        usage[strategy] += 1.0
                        
            return {
                strategy: count/total_adaptations
                for strategy, count in usage.items()
            }
        except Exception as e:
            self.logger.error(f"Error getting strategy usage: {e}")
            return {}
            
    def _analyze_adaptation_trends(self) -> Dict[str, Any]:
        """Analyze trends in adaptations."""
        try:
            trends = {
                "success_trend": self._calculate_adaptation_trend("success"),
                "complexity_trend": self._calculate_adaptation_trend("complexity"),
                "novelty_trend": self._calculate_adaptation_trend("novelty")
            }
            
            return trends
        except Exception as e:
            self.logger.error(f"Error analyzing adaptation trends: {e}")
            return {}
            
    def _calculate_success_metrics(self) -> Dict[str, float]:
        """Calculate success metrics for adaptations."""
        try:
            if not self.adaptation_history:
                return {}
                
            success_scores = []
            for record in self.adaptation_history:
                if "experience_analysis" in record:
                    success = record["experience_analysis"].get("success", 0.5)
                    success_scores.append(success)
                    
            return {
                "average_success": np.mean(success_scores),
                "success_std": np.std(success_scores),
                "success_trend": self._calculate_adaptation_trend("success")
            }
        except Exception as e:
            self.logger.error(f"Error calculating success metrics: {e}")
            return {}
            
    def _calculate_adaptation_trend(self, metric: str) -> float:
        """Calculate trend for a specific adaptation metric."""
        try:
            if not self.adaptation_history:
                return 0.0
                
            # Get metric values over time
            values = []
            for record in self.adaptation_history:
                if "experience_analysis" in record:
                    value = record["experience_analysis"].get(metric, 0.5)
                    values.append(value)
                    
            if not values:
                return 0.0
                
            # Calculate trend using linear regression
            x = np.arange(len(values))
            y = np.array(values)
            slope = np.polyfit(x, y, 1)[0]
            
            return slope
        except Exception as e:
            self.logger.error(f"Error calculating adaptation trend: {e}")
            return 0.0
            
    def reset(self):
        """Reset the adaptation engine."""
        try:
            self.strategies = self._initialize_strategies()
            self.strategy_weights = self._initialize_weights()
            self.adaptation_history = []
        except Exception as e:
            self.logger.error(f"Error resetting adaptation engine: {e}") 