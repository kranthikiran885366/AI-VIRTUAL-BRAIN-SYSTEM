import logging
from typing import Dict, Any, Optional, List
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
from transformers import AutoModelForSequenceClassification, AutoTokenizer, AutoConfig
from datasets import load_dataset
from .base_training import BaseTrainingService

class EmotionTrainingService(BaseTrainingService):
    def __init__(self, config_path: str = "config/emotion_agent_config.yaml"):
        super().__init__(config_path)
        self.emotion_config = self.config.get("emotion_training", {})
        
        # Initialize emotion-specific parameters
        self.model_name = self.emotion_config.get("model_name", "emotion-english-distilroberta-base")
        self.num_labels = self.emotion_config.get("num_labels", 6)
        self.max_length = self.emotion_config.get("max_length", 128)
        self.emotion_labels = self.emotion_config.get("emotion_labels", [
            "sadness", "joy", "love", "anger", "fear", "surprise"
        ])
        
        # Initialize components
        self.tokenizer = None
        self.model = None
    
    def download_dataset(self, dataset_name: str, dataset_url: str) -> bool:
        """Download emotion dataset"""
        try:
            if dataset_name == "emotion":
                # Load Emotion dataset
                dataset = load_dataset("emotion")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "goemotions":
                # Load GoEmotions dataset
                dataset = load_dataset("goemotions")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "isear":
                # Load ISEAR dataset
                dataset = load_dataset("isear")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            else:
                return super().download_dataset(dataset_name, dataset_url)
        
        except Exception as e:
            self.logger.error(f"Error downloading emotion dataset: {e}")
            return False
    
    def download_model(self, model_name: str, model_url: str) -> bool:
        """Download pre-trained emotion model"""
        try:
            if model_name == "emotion-english-distilroberta-base":
                # Download DistilRoBERTa model and tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained("j-hartmann/emotion-english-distilroberta-base")
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    "j-hartmann/emotion-english-distilroberta-base",
                    num_labels=self.num_labels
                )
                
                # Save model and tokenizer
                model_path = self.model_dir / model_name
                model_path.mkdir(parents=True, exist_ok=True)
                
                self.tokenizer.save_pretrained(model_path)
                self.model.save_pretrained(model_path)
                
                return True
            
            elif model_name == "emotion-english-roberta-large":
                # Download RoBERTa Large model and tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained("j-hartmann/emotion-english-roberta-large")
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    "j-hartmann/emotion-english-roberta-large",
                    num_labels=self.num_labels
                )
                
                # Save model and tokenizer
                model_path = self.model_dir / model_name
                model_path.mkdir(parents=True, exist_ok=True)
                
                self.tokenizer.save_pretrained(model_path)
                self.model.save_pretrained(model_path)
                
                return True
            
            else:
                return super().download_model(model_name, model_url)
        
        except Exception as e:
            self.logger.error(f"Error downloading emotion model: {e}")
            return False
    
    def prepare_dataset(self, dataset_name: str) -> Optional[Dataset]:
        """Prepare emotion dataset for training"""
        try:
            dataset_path = self.dataset_dir / dataset_name
            if not dataset_path.exists():
                raise ValueError(f"Dataset {dataset_name} not found")
            
            # Load dataset
            dataset = load_dataset(str(dataset_path))
            
            # Tokenize dataset
            def tokenize_function(examples):
                return self.tokenizer(
                    examples["text"],
                    padding="max_length",
                    truncation=True,
                    max_length=self.max_length
                )
            
            tokenized_dataset = dataset.map(
                tokenize_function,
                batched=True,
                remove_columns=dataset["train"].column_names
            )
            
            return tokenized_dataset["train"]
        
        except Exception as e:
            self.logger.error(f"Error preparing emotion dataset: {e}")
            return None
    
    def create_model(self, model_config: Dict[str, Any]) -> Optional[nn.Module]:
        """Create emotion model architecture"""
        try:
            if self.model_name == "emotion-english-distilroberta-base":
                # Create DistilRoBERTa model
                config = AutoConfig.from_pretrained(
                    "j-hartmann/emotion-english-distilroberta-base",
                    num_labels=self.num_labels
                )
                
                self.model = AutoModelForSequenceClassification.from_config(config)
                self.tokenizer = AutoTokenizer.from_pretrained("j-hartmann/emotion-english-distilroberta-base")
                
                return self.model
            
            else:
                raise ValueError(f"Unsupported model: {self.model_name}")
        
        except Exception as e:
            self.logger.error(f"Error creating emotion model: {e}")
            return None
    
    def _train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """Train emotion model for one epoch"""
        try:
            self.model.train()
            total_loss = 0
            num_batches = 0
            
            for batch in train_loader:
                # Move batch to device
                input_ids = batch["input_ids"].to(self.model.device)
                attention_mask = batch["attention_mask"].to(self.model.device)
                labels = batch["labels"].to(self.model.device)
                
                # Forward pass
                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels
                )
                
                loss = outputs.loss
                
                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
                num_batches += 1
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in emotion training epoch: {e}")
            return {'loss': float('inf')}
    
    def _validate_epoch(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate emotion model for one epoch"""
        try:
            self.model.eval()
            total_loss = 0
            num_batches = 0
            
            with torch.no_grad():
                for batch in val_loader:
                    # Move batch to device
                    input_ids = batch["input_ids"].to(self.model.device)
                    attention_mask = batch["attention_mask"].to(self.model.device)
                    labels = batch["labels"].to(self.model.device)
                    
                    # Forward pass
                    outputs = self.model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        labels=labels
                    )
                    
                    loss = outputs.loss
                    total_loss += loss.item()
                    num_batches += 1
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in emotion validation epoch: {e}")
            return {'loss': float('inf')}

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test emotion training service
    training_service = EmotionTrainingService()
    try:
        # Download datasets
        training_service.download_dataset("emotion", "")
        training_service.download_dataset("goemotions", "")
        training_service.download_dataset("isear", "")
        
        # Download models
        training_service.download_model("emotion-english-distilroberta-base", "")
        training_service.download_model("emotion-english-roberta-large", "")
        
        # Prepare dataset
        dataset = training_service.prepare_dataset("emotion")
        
        # Create model
        model = training_service.create_model({})
        
        # Train model
        if dataset and model:
            training_service.model = model
            results = training_service.train(dataset)
            print("Training results:", results)
    
    finally:
        training_service.cleanup() 