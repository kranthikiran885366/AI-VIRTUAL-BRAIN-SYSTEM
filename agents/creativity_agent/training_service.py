import logging
from typing import Dict, Any, Optional, List
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
from transformers import GPT2LMHeadModel, GPT2Tokenizer, GPT2Config
from datasets import load_dataset
from .base_training import BaseTrainingService

class CreativityTrainingService(BaseTrainingService):
    def __init__(self, config_path: str = "config/creativity_agent_config.yaml"):
        super().__init__(config_path)
        self.creativity_config = self.config.get("creativity_training", {})
        
        # Initialize creativity-specific parameters
        self.model_name = self.creativity_config.get("model_name", "gpt2")
        self.max_length = self.creativity_config.get("max_length", 1024)
        self.vocab_size = self.creativity_config.get("vocab_size", 50257)
        self.num_layers = self.creativity_config.get("num_layers", 12)
        self.num_heads = self.creativity_config.get("num_heads", 12)
        self.hidden_size = self.creativity_config.get("hidden_size", 768)
        
        # Initialize components
        self.tokenizer = None
        self.model = None
    
    def download_dataset(self, dataset_name: str, dataset_url: str) -> bool:
        """Download creativity dataset"""
        try:
            if dataset_name == "creative_writing":
                # Load Creative Writing dataset
                dataset = load_dataset("creative_writing")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "poetry":
                # Load Poetry dataset
                dataset = load_dataset("poetry")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "story_generation":
                # Load Story Generation dataset
                dataset = load_dataset("story_generation")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            else:
                return super().download_dataset(dataset_name, dataset_url)
        
        except Exception as e:
            self.logger.error(f"Error downloading creativity dataset: {e}")
            return False
    
    def download_model(self, model_name: str, model_url: str) -> bool:
        """Download pre-trained creativity model"""
        try:
            if model_name == "gpt2":
                # Download GPT-2 model and tokenizer
                self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
                self.model = GPT2LMHeadModel.from_pretrained("gpt2")
                
                # Save model and tokenizer
                model_path = self.model_dir / model_name
                model_path.mkdir(parents=True, exist_ok=True)
                
                self.tokenizer.save_pretrained(model_path)
                self.model.save_pretrained(model_path)
                
                return True
            
            elif model_name == "gpt2-medium":
                # Download GPT-2 Medium model and tokenizer
                self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2-medium")
                self.model = GPT2LMHeadModel.from_pretrained("gpt2-medium")
                
                # Save model and tokenizer
                model_path = self.model_dir / model_name
                model_path.mkdir(parents=True, exist_ok=True)
                
                self.tokenizer.save_pretrained(model_path)
                self.model.save_pretrained(model_path)
                
                return True
            
            else:
                return super().download_model(model_name, model_url)
        
        except Exception as e:
            self.logger.error(f"Error downloading creativity model: {e}")
            return False
    
    def prepare_dataset(self, dataset_name: str) -> Optional[Dataset]:
        """Prepare creativity dataset for training"""
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
            self.logger.error(f"Error preparing creativity dataset: {e}")
            return None
    
    def create_model(self, model_config: Dict[str, Any]) -> Optional[nn.Module]:
        """Create creativity model architecture"""
        try:
            if self.model_name == "gpt2":
                # Create GPT-2 model
                config = GPT2Config(
                    vocab_size=self.vocab_size,
                    n_positions=self.max_length,
                    n_ctx=self.max_length,
                    n_layer=self.num_layers,
                    n_head=self.num_heads,
                    n_embd=self.hidden_size
                )
                
                self.model = GPT2LMHeadModel(config)
                self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
                
                return self.model
            
            else:
                raise ValueError(f"Unsupported model: {self.model_name}")
        
        except Exception as e:
            self.logger.error(f"Error creating creativity model: {e}")
            return None
    
    def _train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """Train creativity model for one epoch"""
        try:
            self.model.train()
            total_loss = 0
            num_batches = 0
            
            for batch in train_loader:
                # Move batch to device
                input_ids = batch["input_ids"].to(self.model.device)
                attention_mask = batch["attention_mask"].to(self.model.device)
                
                # Forward pass
                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=input_ids
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
            self.logger.error(f"Error in creativity training epoch: {e}")
            return {'loss': float('inf')}
    
    def _validate_epoch(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate creativity model for one epoch"""
        try:
            self.model.eval()
            total_loss = 0
            num_batches = 0
            
            with torch.no_grad():
                for batch in val_loader:
                    # Move batch to device
                    input_ids = batch["input_ids"].to(self.model.device)
                    attention_mask = batch["attention_mask"].to(self.model.device)
                    
                    # Forward pass
                    outputs = self.model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        labels=input_ids
                    )
                    
                    loss = outputs.loss
                    total_loss += loss.item()
                    num_batches += 1
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in creativity validation epoch: {e}")
            return {'loss': float('inf')}

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test creativity training service
    training_service = CreativityTrainingService()
    try:
        # Download datasets
        training_service.download_dataset("creative_writing", "")
        training_service.download_dataset("poetry", "")
        training_service.download_dataset("story_generation", "")
        
        # Download models
        training_service.download_model("gpt2", "")
        training_service.download_model("gpt2-medium", "")
        
        # Prepare dataset
        dataset = training_service.prepare_dataset("creative_writing")
        
        # Create model
        model = training_service.create_model({})
        
        # Train model
        if dataset and model:
            training_service.model = model
            results = training_service.train(dataset)
            print("Training results:", results)
    
    finally:
        training_service.cleanup() 