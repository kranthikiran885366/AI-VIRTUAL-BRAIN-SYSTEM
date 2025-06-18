import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
import json
import os
import shutil
from datetime import datetime

class BaseTrainingService:
    def __init__(self, config_path: str = "config/training_config.yaml"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize training parameters
        self.model_dir = Path(self.config.get("model_dir", "models"))
        self.dataset_dir = Path(self.config.get("dataset_dir", "datasets"))
        self.checkpoint_dir = Path(self.config.get("checkpoint_dir", "checkpoints"))
        self.log_dir = Path(self.config.get("log_dir", "logs"))
        
        # Create directories if they don't exist
        self._create_directories()
        
        # Initialize training state
        self.model = None
        self.optimizer = None
        self.scheduler = None
        self.current_epoch = 0
        self.best_metric = float('inf')
        self.training_history = []
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return yaml.safe_load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}
    
    def _create_directories(self):
        """Create necessary directories"""
        try:
            self.model_dir.mkdir(parents=True, exist_ok=True)
            self.dataset_dir.mkdir(parents=True, exist_ok=True)
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Error creating directories: {e}")
            raise
    
    def download_dataset(self, dataset_name: str, dataset_url: str) -> bool:
        """Download dataset from URL"""
        try:
            dataset_path = self.dataset_dir / dataset_name
            if dataset_path.exists():
                self.logger.info(f"Dataset {dataset_name} already exists")
                return True
            
            # Create dataset directory
            dataset_path.mkdir(parents=True, exist_ok=True)
            
            # Download dataset
            # This is a placeholder - implement actual download logic
            self.logger.info(f"Downloading dataset {dataset_name} from {dataset_url}")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error downloading dataset: {e}")
            return False
    
    def download_model(self, model_name: str, model_url: str) -> bool:
        """Download pre-trained model from URL"""
        try:
            model_path = self.model_dir / model_name
            if model_path.exists():
                self.logger.info(f"Model {model_name} already exists")
                return True
            
            # Create model directory
            model_path.mkdir(parents=True, exist_ok=True)
            
            # Download model
            # This is a placeholder - implement actual download logic
            self.logger.info(f"Downloading model {model_name} from {model_url}")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error downloading model: {e}")
            return False
    
    def prepare_dataset(self, dataset_name: str) -> Optional[Dataset]:
        """Prepare dataset for training"""
        try:
            # This is a placeholder - implement actual dataset preparation
            self.logger.info(f"Preparing dataset {dataset_name}")
            return None
        
        except Exception as e:
            self.logger.error(f"Error preparing dataset: {e}")
            return None
    
    def create_model(self, model_config: Dict[str, Any]) -> Optional[nn.Module]:
        """Create model architecture"""
        try:
            # This is a placeholder - implement actual model creation
            self.logger.info("Creating model")
            return None
        
        except Exception as e:
            self.logger.error(f"Error creating model: {e}")
            return None
    
    def train(self, 
              train_dataset: Dataset,
              val_dataset: Optional[Dataset] = None,
              epochs: int = 10,
              batch_size: int = 32,
              learning_rate: float = 0.001,
              save_best: bool = True) -> Dict[str, Any]:
        """Train the model"""
        try:
            # Create data loaders
            train_loader = DataLoader(
                train_dataset,
                batch_size=batch_size,
                shuffle=True,
                num_workers=4
            )
            
            val_loader = None
            if val_dataset:
                val_loader = DataLoader(
                    val_dataset,
                    batch_size=batch_size,
                    shuffle=False,
                    num_workers=4
                )
            
            # Initialize optimizer and scheduler
            self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
            self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                self.optimizer,
                mode='min',
                patience=3,
                factor=0.1
            )
            
            # Training loop
            for epoch in range(epochs):
                self.current_epoch = epoch
                
                # Train epoch
                train_metrics = self._train_epoch(train_loader)
                
                # Validate epoch
                val_metrics = None
                if val_loader:
                    val_metrics = self._validate_epoch(val_loader)
                
                # Update learning rate
                if val_metrics:
                    self.scheduler.step(val_metrics['loss'])
                
                # Save checkpoint
                if save_best and val_metrics:
                    if val_metrics['loss'] < self.best_metric:
                        self.best_metric = val_metrics['loss']
                        self._save_checkpoint()
                
                # Log metrics
                self._log_metrics(epoch, train_metrics, val_metrics)
            
            return {
                'training_history': self.training_history,
                'best_metric': self.best_metric
            }
        
        except Exception as e:
            self.logger.error(f"Error during training: {e}")
            return {}
    
    def _train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """Train for one epoch"""
        try:
            self.model.train()
            total_loss = 0
            num_batches = 0
            
            for batch in train_loader:
                # This is a placeholder - implement actual training logic
                pass
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in training epoch: {e}")
            return {'loss': float('inf')}
    
    def _validate_epoch(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate for one epoch"""
        try:
            self.model.eval()
            total_loss = 0
            num_batches = 0
            
            with torch.no_grad():
                for batch in val_loader:
                    # This is a placeholder - implement actual validation logic
                    pass
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in validation epoch: {e}")
            return {'loss': float('inf')}
    
    def _save_checkpoint(self):
        """Save model checkpoint"""
        try:
            checkpoint = {
                'epoch': self.current_epoch,
                'model_state_dict': self.model.state_dict(),
                'optimizer_state_dict': self.optimizer.state_dict(),
                'scheduler_state_dict': self.scheduler.state_dict() if self.scheduler else None,
                'best_metric': self.best_metric,
                'training_history': self.training_history
            }
            
            checkpoint_path = self.checkpoint_dir / f"checkpoint_epoch_{self.current_epoch}.pt"
            torch.save(checkpoint, checkpoint_path)
            
            self.logger.info(f"Saved checkpoint to {checkpoint_path}")
        
        except Exception as e:
            self.logger.error(f"Error saving checkpoint: {e}")
    
    def _log_metrics(self, epoch: int, train_metrics: Dict[str, float], val_metrics: Optional[Dict[str, float]]):
        """Log training metrics"""
        try:
            metrics = {
                'epoch': epoch,
                'train': train_metrics,
                'val': val_metrics
            }
            
            self.training_history.append(metrics)
            
            # Save to log file
            log_path = self.log_dir / f"training_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(log_path, 'w') as f:
                json.dump(metrics, f, indent=2)
            
            self.logger.info(f"Epoch {epoch} - Train Loss: {train_metrics['loss']:.4f}" + 
                           (f" - Val Loss: {val_metrics['loss']:.4f}" if val_metrics else ""))
        
        except Exception as e:
            self.logger.error(f"Error logging metrics: {e}")
    
    def load_checkpoint(self, checkpoint_path: str) -> bool:
        """Load model checkpoint"""
        try:
            checkpoint = torch.load(checkpoint_path)
            
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            
            if self.scheduler and checkpoint['scheduler_state_dict']:
                self.scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
            
            self.current_epoch = checkpoint['epoch']
            self.best_metric = checkpoint['best_metric']
            self.training_history = checkpoint['training_history']
            
            self.logger.info(f"Loaded checkpoint from {checkpoint_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error loading checkpoint: {e}")
            return False
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.model:
                del self.model
            if self.optimizer:
                del self.optimizer
            if self.scheduler:
                del self.scheduler
        except Exception as e:
            self.logger.error(f"Error cleaning up: {e}")

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test base training service
    training_service = BaseTrainingService()
    try:
        # Test dataset download
        training_service.download_dataset("test_dataset", "https://example.com/dataset")
        
        # Test model download
        training_service.download_model("test_model", "https://example.com/model")
        
        # Test dataset preparation
        dataset = training_service.prepare_dataset("test_dataset")
        
        # Test model creation
        model = training_service.create_model({})
        
        # Test training
        if dataset and model:
            training_service.model = model
            results = training_service.train(dataset)
            print("Training results:", results)
    
    finally:
        training_service.cleanup() 
 