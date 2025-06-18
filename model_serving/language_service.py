import os
import yaml
import logging
import torch
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger(__name__)

class LanguageService:
    """Service for language model inference."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the language service.
        
        Args:
            config: Model configuration dictionary
        """
        self.config = config
        self.model = None
        self.tokenizer = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.status = "initialized"
        self.version = config.get('version', '1.0.0')
        
        # Load model and tokenizer
        self._load_model()
    
    def _load_model(self):
        """Load the language model and tokenizer."""
        try:
            model_path = Path(self.config['model_path'])
            if not model_path.exists():
                raise FileNotFoundError(f"Model not found at {model_path}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # Load model
            self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
            self.model.to(self.device)
            self.model.eval()
            
            self.status = "loaded"
            logger.info(f"Language model loaded from {model_path}")
            
        except Exception as e:
            self.status = "error"
            logger.error(f"Error loading language model: {e}")
            raise
    
    async def predict(self, text: str) -> Dict[str, Any]:
        """Process language input.
        
        Args:
            text: Input text string
            
        Returns:
            Dictionary containing intent, confidence, and entities
        """
        try:
            # Tokenize input
            inputs = self.tokenizer(
                text,
                padding=True,
                truncation=True,
                max_length=self.config['max_length'],
                return_tensors="pt"
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Run inference
            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = torch.softmax(outputs.logits, dim=1)
                confidence, prediction = torch.max(probabilities, dim=1)
            
            # Get intent
            intent = self.config['intents'][prediction.item()]
            
            # Extract entities
            entities = self._extract_entities(text, outputs)
            
            return {
                'intent': intent,
                'confidence': confidence.item(),
                'entities': entities
            }
            
        except Exception as e:
            logger.error(f"Error in language processing: {e}")
            raise
    
    def _extract_entities(self, text: str, outputs: Any) -> Dict[str, Any]:
        """Extract named entities from text.
        
        Args:
            text: Input text
            outputs: Model outputs
            
        Returns:
            Dictionary of extracted entities
        """
        entities = {}
        
        try:
            # Get attention weights
            attention = outputs.attentions[-1].mean(dim=1).squeeze()
            
            # Get token spans
            tokens = self.tokenizer.tokenize(text)
            token_spans = self.tokenizer(text, return_offsets_mapping=True)['offset_mapping']
            
            # Extract entities based on attention
            for i, (token, span) in enumerate(zip(tokens, token_spans)):
                if attention[i] > self.config['entity_threshold']:
                    entity_type = self._get_entity_type(token)
                    if entity_type:
                        entities[token] = {
                            'type': entity_type,
                            'span': span,
                            'confidence': float(attention[i])
                        }
            
        except Exception as e:
            logger.warning(f"Error extracting entities: {e}")
        
        return entities
    
    def _get_entity_type(self, token: str) -> Optional[str]:
        """Get entity type for token.
        
        Args:
            token: Input token
            
        Returns:
            Entity type if found, None otherwise
        """
        # Simple rule-based entity type detection
        if token.isdigit():
            return 'NUMBER'
        elif token.startswith('@'):
            return 'USER'
        elif token.startswith('#'):
            return 'HASHTAG'
        elif token.startswith('http'):
            return 'URL'
        return None
    
    async def reload(self):
        """Reload the model."""
        try:
            self._load_model()
            logger.info("Language model reloaded successfully")
        except Exception as e:
            logger.error(f"Error reloading language model: {e}")
            raise 