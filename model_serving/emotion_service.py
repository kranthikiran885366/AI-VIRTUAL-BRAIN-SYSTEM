import os
import yaml
import logging
import torch
import numpy as np
import base64
from io import BytesIO
from PIL import Image
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class EmotionService:
    """Service for emotion recognition model inference."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the emotion service.
        
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
        """Load the emotion recognition model."""
        try:
            model_path = Path(self.config['model_path'])
            if not model_path.exists():
                raise FileNotFoundError(f"Model not found at {model_path}")
            
            self.model = torch.load(model_path, map_location=self.device)
            self.model.eval()
            self.status = "loaded"
            logger.info(f"Emotion model loaded from {model_path}")
            
        except Exception as e:
            self.status = "error"
            logger.error(f"Error loading emotion model: {e}")
            raise
    
    async def predict(self, image: str) -> Dict[str, Any]:
        """Predict emotion from image.
        
        Args:
            image: Base64 encoded image string
            
        Returns:
            Dictionary containing emotion prediction and confidence
        """
        try:
            # Decode base64 image
            image_data = base64.b64decode(image)
            image = Image.open(BytesIO(image_data))
            
            # Preprocess image
            image_tensor = self._preprocess_image(image)
            
            # Run inference
            with torch.no_grad():
                outputs = self.model(image_tensor)
                probabilities = torch.softmax(outputs, dim=1)
                confidence, prediction = torch.max(probabilities, dim=1)
            
            # Get emotion label
            emotion = self.config['labels'][prediction.item()]
            
            return {
                'emotion': emotion,
                'confidence': confidence.item()
            }
            
        except Exception as e:
            logger.error(f"Error in emotion prediction: {e}")
            raise
    
    def _preprocess_image(self, image: Image.Image) -> torch.Tensor:
        """Preprocess image for model input.
        
        Args:
            image: PIL Image object
            
        Returns:
            Preprocessed image tensor
        """
        # Resize image
        image = image.resize(
            (self.config['input_size'], self.config['input_size'])
        )
        
        # Convert to tensor and normalize
        image_tensor = torch.from_numpy(
            np.array(image)
        ).float()
        
        # Add batch dimension and normalize
        image_tensor = image_tensor.unsqueeze(0)
        image_tensor = image_tensor / 255.0
        
        # Move to device
        image_tensor = image_tensor.to(self.device)
        
        return image_tensor
    
    async def reload(self):
        """Reload the model."""
        try:
            self._load_model()
            logger.info("Emotion model reloaded successfully")
        except Exception as e:
            logger.error(f"Error reloading emotion model: {e}")
            raise 