import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path

class RelationshipManager:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.relationships = {}
        self.interaction_history = {}
        self.trust_scores = {}
        self._load_existing_relationships()
        
    def _load_existing_relationships(self):
        """Load existing relationships from storage."""
        try:
            storage_path = Path(self.config.get("storage_path", "data/relationships.json"))
            if storage_path.exists():
                with open(storage_path, 'r') as f:
                    data = json.load(f)
                    self.relationships = data.get("relationships", {})
                    self.interaction_history = data.get("interaction_history", {})
                    self.trust_scores = data.get("trust_scores", {})
        except Exception as e:
            self.logger.error(f"Error loading relationships: {e}")
            
    def _save_relationships(self):
        """Save current relationships to storage."""
        try:
            storage_path = Path(self.config.get("storage_path", "data/relationships.json"))
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "relationships": self.relationships,
                "interaction_history": self.interaction_history,
                "trust_scores": self.trust_scores
            }
            
            with open(storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving relationships: {e}")
            
    def update_state(self, parsed_cue: Dict[str, Any]) -> Dict[str, Any]:
        """Update relationship state based on new interaction."""
        try:
            sender = parsed_cue["original"].get("sender", "unknown")
            timestamp = datetime.fromisoformat(parsed_cue["timestamp"])
            
            # Initialize relationship if new
            if sender not in self.relationships:
                self._initialize_relationship(sender)
                
            # Update interaction history
            self._update_interaction_history(sender, parsed_cue, timestamp)
            
            # Update trust score
            self._update_trust_score(sender, parsed_cue)
            
            # Update relationship status
            self._update_relationship_status(sender)
            
            # Save changes
            self._save_relationships()
            
            return self._get_relationship_context(sender)
        except Exception as e:
            self.logger.error(f"Error updating relationship state: {e}")
            return {"error": str(e)}
            
    def _initialize_relationship(self, sender: str):
        """Initialize a new relationship."""
        self.relationships[sender] = {
            "status": "new",
            "first_interaction": datetime.now().isoformat(),
            "interaction_count": 0,
            "last_interaction": None,
            "preferred_formality": "neutral",
            "emotional_trend": []
        }
        
        self.interaction_history[sender] = []
        self.trust_scores[sender] = 0.5  # Neutral starting point
        
    def _update_interaction_history(self, sender: str, parsed_cue: Dict[str, Any], 
                                  timestamp: datetime):
        """Update interaction history for a relationship."""
        interaction = {
            "timestamp": timestamp.isoformat(),
            "type": parsed_cue["interaction_type"],
            "emotions": parsed_cue["emotions"],
            "formality": parsed_cue["formality_level"],
            "context": parsed_cue["social_context"]
        }
        
        self.interaction_history[sender].append(interaction)
        self.relationships[sender]["last_interaction"] = timestamp.isoformat()
        self.relationships[sender]["interaction_count"] += 1
        
        # Keep only last N interactions
        max_history = self.config.get("max_interaction_history", 100)
        if len(self.interaction_history[sender]) > max_history:
            self.interaction_history[sender] = self.interaction_history[sender][-max_history:]
            
    def _update_trust_score(self, sender: str, parsed_cue: Dict[str, Any]):
        """Update trust score based on interaction."""
        current_score = self.trust_scores[sender]
        
        # Factors affecting trust
        factors = {
            "positive_emotion": 0.1,
            "negative_emotion": -0.1,
            "formal_interaction": 0.05,
            "informal_interaction": -0.05,
            "question_answered": 0.15,
            "question_ignored": -0.2
        }
        
        # Calculate trust adjustment
        adjustment = 0
        if "positive" in parsed_cue["emotions"]:
            adjustment += factors["positive_emotion"]
        if "negative" in parsed_cue["emotions"]:
            adjustment += factors["negative_emotion"]
            
        if parsed_cue["formality_level"] == "formal":
            adjustment += factors["formal_interaction"]
        elif parsed_cue["formality_level"] == "informal":
            adjustment += factors["informal_interaction"]
            
        # Update trust score (clamped between 0 and 1)
        new_score = max(0, min(1, current_score + adjustment))
        self.trust_scores[sender] = new_score
        
    def _update_relationship_status(self, sender: str):
        """Update relationship status based on interaction history."""
        relationship = self.relationships[sender]
        interaction_count = relationship["interaction_count"]
        trust_score = self.trust_scores[sender]
        
        if interaction_count < 3:
            status = "new"
        elif trust_score < 0.3:
            status = "distrustful"
        elif trust_score > 0.7:
            status = "trusted"
        else:
            status = "developing"
            
        relationship["status"] = status
        
    def _get_relationship_context(self, sender: str) -> Dict[str, Any]:
        """Get current relationship context for a sender."""
        return {
            "status": self.relationships[sender]["status"],
            "trust_score": self.trust_scores[sender],
            "interaction_count": self.relationships[sender]["interaction_count"],
            "preferred_formality": self.relationships[sender]["preferred_formality"],
            "last_interaction": self.relationships[sender]["last_interaction"]
        }
        
    def get_all_relationships(self) -> Dict[str, Dict[str, Any]]:
        """Get all current relationships."""
        return {
            sender: self._get_relationship_context(sender)
            for sender in self.relationships
        } 