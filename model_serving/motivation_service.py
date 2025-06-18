import os
import yaml
import logging
import torch
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class MotivationService:
    """Service for motivation model inference."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the motivation service.
        
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
        """Load the motivation model."""
        try:
            model_path = Path(self.config['model_path'])
            if not model_path.exists():
                raise FileNotFoundError(f"Model not found at {model_path}")
            
            self.model = torch.load(model_path, map_location=self.device)
            self.model.eval()
            self.status = "loaded"
            logger.info(f"Motivation model loaded from {model_path}")
            
        except Exception as e:
            self.status = "error"
            logger.error(f"Error loading motivation model: {e}")
            raise
    
    async def predict(self, state: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
        """Predict motivation based on state and action.
        
        Args:
            state: Current state dictionary
            action: Action dictionary
            
        Returns:
            Dictionary containing reward and value predictions
        """
        try:
            # Preprocess inputs
            state_tensor = self._preprocess_state(state)
            action_tensor = self._preprocess_action(action)
            
            # Run inference
            with torch.no_grad():
                # Get reward and value predictions
                reward_output, value_output = self.model(state_tensor, action_tensor)
                
                # Get reward prediction
                reward = reward_output.item()
                
                # Get value prediction
                value = value_output.item()
            
            return {
                'reward': reward,
                'value': value
            }
            
        except Exception as e:
            logger.error(f"Error in motivation prediction: {e}")
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
    
    def _preprocess_action(self, action: Dict[str, Any]) -> torch.Tensor:
        """Preprocess action dictionary to tensor.
        
        Args:
            action: Action dictionary
            
        Returns:
            Preprocessed action tensor
        """
        # Convert action to feature vector
        features = []
        for key in self.config['action_features']:
            if key in action:
                value = action[key]
                if isinstance(value, (int, float)):
                    features.append(float(value))
                elif isinstance(value, bool):
                    features.append(float(value))
                elif isinstance(value, list):
                    features.extend([float(x) for x in value])
                else:
                    logger.warning(f"Unsupported action feature type for {key}: {type(value)}")
                    features.append(0.0)
            else:
                features.append(0.0)
        
        # Convert to tensor
        action_tensor = torch.tensor(features, dtype=torch.float32)
        action_tensor = action_tensor.unsqueeze(0)  # Add batch dimension
        action_tensor = action_tensor.to(self.device)
        
        return action_tensor
    
    async def reload(self):
        """Reload the model."""
        try:
            self._load_model()
            logger.info("Motivation model reloaded successfully")
        except Exception as e:
            logger.error(f"Error reloading motivation model: {e}")
            raise 