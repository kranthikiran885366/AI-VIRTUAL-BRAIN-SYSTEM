import logging
from typing import Dict, Any, List, Optional
import random
from datetime import datetime
import numpy as np
from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch

class IdeaGenerator:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.idea_history = []
        self.max_history = config.get("max_idea_history", 1000)
        
        # Initialize language model for idea generation
        self.model = self._initialize_model()
        self.tokenizer = self._initialize_tokenizer()
        
    def _initialize_model(self) -> Optional[GPT2LMHeadModel]:
        """Initialize the language model for idea generation."""
        try:
            model_name = self.config.get("models", {}).get("idea_generation", {}).get("model", "gpt2")
            return GPT2LMHeadModel.from_pretrained(model_name)
        except Exception as e:
            self.logger.error(f"Error initializing model: {e}")
            return None
            
    def _initialize_tokenizer(self) -> Optional[GPT2Tokenizer]:
        """Initialize the tokenizer for the language model."""
        try:
            model_name = self.config.get("models", {}).get("idea_generation", {}).get("model", "gpt2")
            return GPT2Tokenizer.from_pretrained(model_name)
        except Exception as e:
            self.logger.error(f"Error initializing tokenizer: {e}")
            return None
            
    def generate(self, context: Dict[str, Any], patterns: Dict[str, Any], 
                inspiration: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate creative ideas based on context, patterns, and inspiration."""
        try:
            ideas = []
            num_ideas = self.config.get("num_ideas_to_generate", 5)
            
            # Generate multiple ideas
            for _ in range(num_ideas):
                idea = self._generate_single_idea(context, patterns, inspiration)
                if idea and self._validate_idea(idea):
                    ideas.append(idea)
                    
            # Update idea history
            self._update_idea_history(ideas)
            
            return ideas
        except Exception as e:
            self.logger.error(f"Error generating ideas: {e}")
            return []
            
    def _generate_single_idea(self, context: Dict[str, Any], patterns: Dict[str, Any],
                            inspiration: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate a single creative idea."""
        try:
            # Combine context, patterns, and inspiration
            combined_context = self._combine_contexts(context, patterns, inspiration)
            
            # Generate idea components using the language model
            concept = self._generate_concept(combined_context)
            approach = self._generate_approach(combined_context)
            implementation = self._generate_implementation(combined_context)
            
            if not all([concept, approach, implementation]):
                return None
                
            idea = {
                "concept": concept,
                "approach": approach,
                "implementation": implementation,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "context": context.get("domain"),
                    "inspiration_sources": inspiration.get("sources", []),
                    "pattern_influence": patterns.get("influence", {}),
                    "originality_score": self._calculate_originality(concept, approach),
                    "feasibility_score": self._calculate_feasibility(implementation),
                    "impact_score": self._calculate_impact(concept, approach)
                }
            }
            
            return idea
        except Exception as e:
            self.logger.error(f"Error generating single idea: {e}")
            return None
            
    def _generate_concept(self, context: Dict[str, Any]) -> Optional[str]:
        """Generate the core concept of an idea using the language model."""
        try:
            if not self.model or not self.tokenizer:
                return "Innovative concept based on context"
                
            # Prepare prompt for concept generation
            prompt = self._create_concept_prompt(context)
            
            # Generate concept using the model
            inputs = self.tokenizer(prompt, return_tensors="pt", max_length=100, truncation=True)
            outputs = self.model.generate(
                inputs["input_ids"],
                max_length=150,
                num_return_sequences=1,
                temperature=0.8,
                top_p=0.9,
                do_sample=True
            )
            
            # Decode and clean the generated concept
            concept = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return self._clean_generated_text(concept)
        except Exception as e:
            self.logger.error(f"Error generating concept: {e}")
            return None
            
    def _generate_approach(self, context: Dict[str, Any]) -> Optional[str]:
        """Generate the approach for implementing the concept."""
        try:
            if not self.model or not self.tokenizer:
                return "Practical approach to implement the concept"
                
            # Prepare prompt for approach generation
            prompt = self._create_approach_prompt(context)
            
            # Generate approach using the model
            inputs = self.tokenizer(prompt, return_tensors="pt", max_length=100, truncation=True)
            outputs = self.model.generate(
                inputs["input_ids"],
                max_length=200,
                num_return_sequences=1,
                temperature=0.7,
                top_p=0.9,
                do_sample=True
            )
            
            # Decode and clean the generated approach
            approach = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return self._clean_generated_text(approach)
        except Exception as e:
            self.logger.error(f"Error generating approach: {e}")
            return None
            
    def _generate_implementation(self, context: Dict[str, Any]) -> Optional[str]:
        """Generate implementation details for the idea."""
        try:
            if not self.model or not self.tokenizer:
                return "Detailed implementation steps"
                
            # Prepare prompt for implementation generation
            prompt = self._create_implementation_prompt(context)
            
            # Generate implementation using the model
            inputs = self.tokenizer(prompt, return_tensors="pt", max_length=100, truncation=True)
            outputs = self.model.generate(
                inputs["input_ids"],
                max_length=300,
                num_return_sequences=1,
                temperature=0.6,
                top_p=0.9,
                do_sample=True
            )
            
            # Decode and clean the generated implementation
            implementation = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return self._clean_generated_text(implementation)
        except Exception as e:
            self.logger.error(f"Error generating implementation: {e}")
            return None
            
    def _create_concept_prompt(self, context: Dict[str, Any]) -> str:
        """Create a prompt for concept generation."""
        domain = context.get("domain", "general")
        constraints = ", ".join(context.get("constraints", []))
        goals = ", ".join(context.get("goals", []))
        
        return f"Generate an innovative concept in the domain of {domain}. " \
               f"Consider the following constraints: {constraints}. " \
               f"Goals to achieve: {goals}. " \
               f"Concept:"
               
    def _create_approach_prompt(self, context: Dict[str, Any]) -> str:
        """Create a prompt for approach generation."""
        concept = context.get("concept", "")
        domain = context.get("domain", "general")
        
        return f"Given the concept: {concept} in the domain of {domain}, " \
               f"describe a practical approach to implement it. " \
               f"Consider technical feasibility and resource requirements. " \
               f"Approach:"
               
    def _create_implementation_prompt(self, context: Dict[str, Any]) -> str:
        """Create a prompt for implementation generation."""
        concept = context.get("concept", "")
        approach = context.get("approach", "")
        
        return f"Given the concept: {concept} and approach: {approach}, " \
               f"provide detailed implementation steps. " \
               f"Include technical details, required resources, and timeline. " \
               f"Implementation:"
               
    def _clean_generated_text(self, text: str) -> str:
        """Clean and format the generated text."""
        # Remove extra whitespace
        text = " ".join(text.split())
        
        # Remove any prompt text that might have been included
        if ":" in text:
            text = text.split(":", 1)[1].strip()
            
        return text
        
    def _validate_idea(self, idea: Dict[str, Any]) -> bool:
        """Validate the generated idea against constraints."""
        try:
            constraints = self.config.get("idea_generation", {}).get("constraints", {})
            
            # Check minimum scores
            if idea["metadata"]["originality_score"] < constraints.get("min_originality", 0.6):
                return False
            if idea["metadata"]["feasibility_score"] < constraints.get("min_feasibility", 0.5):
                return False
            if idea["metadata"]["impact_score"] < constraints.get("min_impact", 0.4):
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"Error validating idea: {e}")
            return False
            
    def _calculate_originality(self, concept: str, approach: str) -> float:
        """Calculate the originality score of an idea."""
        try:
            # Compare with idea history
            if not self.idea_history:
                return 0.8  # First idea is considered original
                
            # Calculate similarity with historical ideas
            similarities = []
            for historical_idea in self.idea_history:
                concept_similarity = self._calculate_text_similarity(
                    concept,
                    historical_idea["concept"]
                )
                approach_similarity = self._calculate_text_similarity(
                    approach,
                    historical_idea["approach"]
                )
                similarities.append(max(concept_similarity, approach_similarity))
                
            # Originality is inverse of maximum similarity
            return 1.0 - max(similarities) if similarities else 0.8
        except Exception as e:
            self.logger.error(f"Error calculating originality: {e}")
            return 0.5
            
    def _calculate_feasibility(self, implementation: str) -> float:
        """Calculate the feasibility score of an idea."""
        try:
            # Implement feasibility calculation based on implementation details
            # This is a placeholder - replace with actual feasibility calculation
            return 0.7
        except Exception as e:
            self.logger.error(f"Error calculating feasibility: {e}")
            return 0.5
            
    def _calculate_impact(self, concept: str, approach: str) -> float:
        """Calculate the potential impact score of an idea."""
        try:
            # Implement impact calculation based on concept and approach
            # This is a placeholder - replace with actual impact calculation
            return 0.8
        except Exception as e:
            self.logger.error(f"Error calculating impact: {e}")
            return 0.5
            
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        try:
            if not self.tokenizer:
                return 0.0
                
            # Tokenize texts
            tokens1 = self.tokenizer.encode(text1, add_special_tokens=True)
            tokens2 = self.tokenizer.encode(text2, add_special_tokens=True)
            
            # Calculate Jaccard similarity
            set1 = set(tokens1)
            set2 = set(tokens2)
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            
            return intersection / union if union > 0 else 0.0
        except Exception as e:
            self.logger.error(f"Error calculating text similarity: {e}")
            return 0.0
            
    def _combine_contexts(self, context: Dict[str, Any], patterns: Dict[str, Any],
                         inspiration: Dict[str, Any]) -> Dict[str, Any]:
        """Combine different context sources for idea generation."""
        try:
            return {
                "domain": context.get("domain"),
                "constraints": context.get("constraints", []),
                "goals": context.get("goals", []),
                "patterns": patterns.get("identified", []),
                "inspiration": inspiration.get("elements", []),
                "previous_ideas": context.get("previous_ideas", []),
                "concept": context.get("concept", ""),
                "approach": context.get("approach", "")
            }
        except Exception as e:
            self.logger.error(f"Error combining contexts: {e}")
            return {}
            
    def _update_idea_history(self, new_ideas: List[Dict[str, Any]]):
        """Update the history of generated ideas."""
        try:
            self.idea_history.extend(new_ideas)
            
            # Maintain history size limit
            if len(self.idea_history) > self.max_history:
                self.idea_history = self.idea_history[-self.max_history:]
        except Exception as e:
            self.logger.error(f"Error updating idea history: {e}")
            
    def get_idea_history(self) -> List[Dict[str, Any]]:
        """Get the history of generated ideas."""
        return self.idea_history
        
    def clear_idea_history(self):
        """Clear the history of generated ideas."""
        self.idea_history = [] 