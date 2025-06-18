import os
import yaml
import logging
import torch
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PlanningService:
    """Service for planning model inference."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the planning service.
        
        Args:
            config: Model configuration dictionary
        """
        self.config = config
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.status = "initialized"
        self.version = config.get('version', '1.0.0')
        
        # Load model
        self._load_model()
    
    def _load_model(self):
        """Load the planning model."""
        try:
            model_path = Path(self.config['model_path'])
            if not model_path.exists():
                raise FileNotFoundError(f"Model not found at {model_path}")
            
            self.model = torch.load(model_path, map_location=self.device)
            self.model.eval()
            self.status = "loaded"
            logger.info(f"Planning model loaded from {model_path}")
            
        except Exception as e:
            self.status = "error"
            logger.error(f"Error loading planning model: {e}")
            raise
    
    async def predict(self, state: Dict[str, Any], goal: Dict[str, Any]) -> Dict[str, Any]:
        """Plan action based on state and goal.
        
        Args:
            state: Current state dictionary
            goal: Goal state dictionary
            
        Returns:
            Dictionary containing action, next state, and confidence
        """
        try:
            # Preprocess inputs
            state_tensor = self._preprocess_state(state)
            goal_tensor = self._preprocess_state(goal)
            
            # Run inference
            with torch.no_grad():
                # Get action and next state predictions
                action_outputs, state_outputs = self.model(state_tensor, goal_tensor)
                
                # Get action probabilities
                action_probs = torch.softmax(action_outputs, dim=1)
                confidence, action_idx = torch.max(action_probs, dim=1)
                
                # Get next state
                next_state = self._postprocess_state(state_outputs)
                
                # Get action
                action = self.config['actions'][action_idx.item()]
            
            return {
                'action': action,
                'next_state': next_state,
                'confidence': confidence.item()
            }
            
        except Exception as e:
            logger.error(f"Error in planning: {e}")
            raise
    
    def _preprocess_state(self, state: Dict[str, Any]) -> torch.Tensor:
        """Preprocess state dictionary to tensor.
        
        Args:
            state: State dictionary
            
        Returns:
            Preprocessed state tensor
        """
        # Convert state to feature vector
        features = []
        for key in self.config['state_features']:
            if key in state:
                value = state[key]
                if isinstance(value, (int, float)):
                    features.append(float(value))
                elif isinstance(value, bool):
                    features.append(float(value))
                elif isinstance(value, list):
                    features.extend([float(x) for x in value])
                else:
                    logger.warning(f"Unsupported state feature type for {key}: {type(value)}")
                    features.append(0.0)
            else:
                features.append(0.0)
        
        # Convert to tensor
        state_tensor = torch.tensor(features, dtype=torch.float32)
        state_tensor = state_tensor.unsqueeze(0)  # Add batch dimension
        state_tensor = state_tensor.to(self.device)
        
        return state_tensor
    
    def _postprocess_state(self, state_tensor: torch.Tensor) -> Dict[str, Any]:
        """Convert state tensor back to dictionary.
        
        Args:
            state_tensor: State tensor
            
        Returns:
            State dictionary
        """
        state = {}
        features = state_tensor.squeeze().cpu().numpy()
        
        # Convert features back to state dictionary
        for i, key in enumerate(self.config['state_features']):
            if i < len(features):
                state[key] = float(features[i])
            else:
                state[key] = 0.0
        
        return state
    
    async def reload(self):
        """Reload the model."""
        try:
            self._load_model()
            logger.info("Planning model reloaded successfully")
        except Exception as e:
            logger.error(f"Error reloading planning model: {e}")
            raise 