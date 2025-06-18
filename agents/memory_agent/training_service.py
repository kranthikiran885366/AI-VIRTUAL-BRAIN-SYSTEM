import logging
from typing import Dict, Any, Optional, List
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
from transformers import AutoModelForSequenceClassification, AutoTokenizer, AutoConfig
from datasets import load_dataset
from .base_training import BaseTrainingService

class MemoryTrainingService(BaseTrainingService):
    def __init__(self, config_path: str = "config/memory_agent_config.yaml"):
        super().__init__(config_path)
        self.memory_config = self.config.get("memory_training", {})
        
        # Initialize memory-specific parameters
        self.model_name = self.memory_config.get("model_name", "memory-bert-base")
        self.max_length = self.memory_config.get("max_length", 512)
        self.embedding_dim = self.memory_config.get("embedding_dim", 768)
        self.num_memory_slots = self.memory_config.get("num_memory_slots", 1000)
        self.memory_dim = self.memory_config.get("memory_dim", 512)
        
        # Initialize components
        self.tokenizer = None
        self.model = None
        self.memory_matrix = None
    
    def download_dataset(self, dataset_name: str, dataset_url: str) -> bool:
        """Download memory dataset"""
        try:
            if dataset_name == "memory_qa":
                # Load Memory QA dataset
                dataset = load_dataset("memory_qa")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "episodic_memory":
                # Load Episodic Memory dataset
                dataset = load_dataset("episodic_memory")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "semantic_memory":
                # Load Semantic Memory dataset
                dataset = load_dataset("semantic_memory")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            else:
                return super().download_dataset(dataset_name, dataset_url)
        
        except Exception as e:
            self.logger.error(f"Error downloading memory dataset: {e}")
            return False
    
    def download_model(self, model_name: str, model_url: str) -> bool:
        """Download pre-trained memory model"""
        try:
            if model_name == "memory-bert-base":
                # Download BERT model and tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    "bert-base-uncased",
                    num_labels=self.embedding_dim
                )
                
                # Save model and tokenizer
                model_path = self.model_dir / model_name
                model_path.mkdir(parents=True, exist_ok=True)
                
                self.tokenizer.save_pretrained(model_path)
                self.model.save_pretrained(model_path)
                
                return True
            
            elif model_name == "memory-roberta-base":
                # Download RoBERTa model and tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained("roberta-base")
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    "roberta-base",
                    num_labels=self.embedding_dim
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
            self.logger.error(f"Error downloading memory model: {e}")
            return False
    
    def prepare_dataset(self, dataset_name: str) -> Optional[Dataset]:
        """Prepare memory dataset for training"""
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
            self.logger.error(f"Error preparing memory dataset: {e}")
            return None
    
    def create_model(self, model_config: Dict[str, Any]) -> Optional[nn.Module]:
        """Create memory model architecture"""
        try:
            if self.model_name == "memory-bert-base":
                # Create BERT model
                config = AutoConfig.from_pretrained(
                    "bert-base-uncased",
                    num_labels=self.embedding_dim
                )
                
                self.model = AutoModelForSequenceClassification.from_config(config)
                self.tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
                
                # Initialize memory matrix
                self.memory_matrix = nn.Parameter(
                    torch.randn(self.num_memory_slots, self.memory_dim)
                )
                
                return self.model
            
            else:
                raise ValueError(f"Unsupported model: {self.model_name}")
        
        except Exception as e:
            self.logger.error(f"Error creating memory model: {e}")
            return None
    
    def _train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """Train memory model for one epoch"""
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
                
                # Memory encoding
                memory_embeddings = outputs.logits
                memory_scores = torch.matmul(memory_embeddings, self.memory_matrix.t())
                memory_attention = torch.softmax(memory_scores, dim=-1)
                
                # Memory retrieval
                retrieved_memory = torch.matmul(memory_attention, self.memory_matrix)
                
                # Calculate loss
                loss = outputs.loss + self._memory_loss(retrieved_memory, labels)
                
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
            self.logger.error(f"Error in memory training epoch: {e}")
            return {'loss': float('inf')}
    
    def _validate_epoch(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate memory model for one epoch"""
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
                    
                    # Memory encoding
                    memory_embeddings = outputs.logits
                    memory_scores = torch.matmul(memory_embeddings, self.memory_matrix.t())
                    memory_attention = torch.softmax(memory_scores, dim=-1)
                    
                    # Memory retrieval
                    retrieved_memory = torch.matmul(memory_attention, self.memory_matrix)
                    
                    # Calculate loss
                    loss = outputs.loss + self._memory_loss(retrieved_memory, labels)
                    
                    total_loss += loss.item()
                    num_batches += 1
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in memory validation epoch: {e}")
            return {'loss': float('inf')}
    
    def _memory_loss(self, retrieved_memory: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """Calculate memory-specific loss"""
        try:
            # Cosine similarity loss
            similarity = torch.nn.functional.cosine_similarity(
                retrieved_memory, labels, dim=-1
            )
            return 1 - similarity.mean()
        
        except Exception as e:
            self.logger.error(f"Error calculating memory loss: {e}")
            return torch.tensor(0.0, device=self.model.device)

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test memory training service
    training_service = MemoryTrainingService()
    try:
        # Download datasets
        training_service.download_dataset("memory_qa", "")
        training_service.download_dataset("episodic_memory", "")
        training_service.download_dataset("semantic_memory", "")
        
        # Download models
        training_service.download_model("memory-bert-base", "")
        training_service.download_model("memory-roberta-base", "")
        
        # Prepare dataset
        dataset = training_service.prepare_dataset("memory_qa")
        
        # Create model
        model = training_service.create_model({})
        
        # Train model
        if dataset and model:
            training_service.model = model
            results = training_service.train(dataset)
            print("Training results:", results)
    
    finally:
        training_service.cleanup() 