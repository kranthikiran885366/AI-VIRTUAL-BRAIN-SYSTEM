import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import json
from datetime import datetime

from .data_loader import DataLoader
from .metrics import calculate_metrics, save_metrics
from .validation import ModelValidator
from .persistence import ModelPersistence
from ..config.model_config import model_config

logger = logging.getLogger(__name__)

class TrainingOrchestrator:
    """Orchestrates the training process for all models."""
    
    def __init__(self):
        """Initialize the training orchestrator."""
        self.data_loader = DataLoader()
        self.model_persistence = ModelPersistence()
        self.training_status = {}
        self.training_history = {}
    
    async def train_model(
        self,
        model_type: str,
        config: Optional[Dict] = None,
        force_retrain: bool = False
    ) -> Dict[str, Any]:
        """Train a specific model.
        
        Args:
            model_type: Type of model to train
            config: Optional configuration override
            force_retrain: Whether to force retraining even if model exists
            
        Returns:
            Training results and metrics
        """
        try:
            # Load model configuration
            if config is None:
                config = model_config.get_model_config(model_type)
            
            # Check if model exists and retraining is needed
            if not force_retrain:
                existing_models = self.model_persistence.list_models()
                if model_type in existing_models:
                    logger.info(f"Model {model_type} already exists. Skipping training.")
                    return {
                        "status": "skipped",
                        "message": "Model already exists",
                        "existing_versions": existing_models[model_type]
                    }
            
            # Initialize training status
            self.training_status[model_type] = {
                "status": "training",
                "start_time": datetime.now().isoformat(),
                "config": config
            }
            
            # Load and preprocess data
            dataset_config = self.data_loader.load_config(
                model_config.get_dataset_path(model_type).name
            )
            
            # Train model based on type
            if model_type == "emotion":
                from ..train_emotion_model import EmotionModelTrainer
                trainer = EmotionModelTrainer()
                metrics = trainer.train()
            
            elif model_type == "face":
                from ..train_face_model import FaceModelTrainer
                trainer = FaceModelTrainer()
                metrics = trainer.train()
            
            elif model_type == "language":
                from ..train_language_model import LanguageModelTrainer
                trainer = LanguageModelTrainer()
                metrics = trainer.train()
            
            elif model_type == "planning":
                from ..train_planning_model import PlanningModelTrainer
                trainer = PlanningModelTrainer()
                metrics = trainer.train()
            
            elif model_type == "motivation":
                from ..train_motivation_model import MotivationModelTrainer
                trainer = MotivationModelTrainer()
                metrics = trainer.train()
            
            else:
                raise ValueError(f"Unknown model type: {model_type}")
            
            # Save training results
            self.training_history[model_type] = {
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics,
                "config": config
            }
            
            # Update training status
            self.training_status[model_type].update({
                "status": "completed",
                "end_time": datetime.now().isoformat(),
                "metrics": metrics
            })
            
            return {
                "status": "completed",
                "metrics": metrics,
                "config": config
            }
            
        except Exception as e:
            logger.error(f"Error training model {model_type}: {e}")
            self.training_status[model_type].update({
                "status": "failed",
                "error": str(e),
                "end_time": datetime.now().isoformat()
            })
            raise
    
    async def train_all_models(
        self,
        configs: Optional[Dict[str, Dict]] = None,
        force_retrain: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """Train all models.
        
        Args:
            configs: Optional configuration overrides for each model
            force_retrain: Whether to force retraining of existing models
            
        Returns:
            Dictionary of training results for each model
        """
        results = {}
        
        for model_type in model_config.model_paths.keys():
            try:
                model_config = configs.get(model_type) if configs else None
                result = await self.train_model(
                    model_type,
                    config=model_config,
                    force_retrain=force_retrain
                )
                results[model_type] = result
            except Exception as e:
                logger.error(f"Failed to train {model_type}: {e}")
                results[model_type] = {
                    "status": "failed",
                    "error": str(e)
                }
        
        return results
    
    def get_training_status(self, model_type: Optional[str] = None) -> Dict:
        """Get training status for model(s).
        
        Args:
            model_type: Optional specific model type
            
        Returns:
            Training status information
        """
        if model_type:
            return self.training_status.get(model_type, {})
        return self.training_status
    
    def get_training_history(self, model_type: Optional[str] = None) -> Dict:
        """Get training history for model(s).
        
        Args:
            model_type: Optional specific model type
            
        Returns:
            Training history information
        """
        if model_type:
            return self.training_history.get(model_type, {})
        return self.training_history
    
    def save_training_summary(self, output_path: str):
        """Save training summary to file.
        
        Args:
            output_path: Path to save summary
        """
        summary = {
            "timestamp": datetime.now().isoformat(),
            "status": self.training_status,
            "history": self.training_history
        }
        
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Saved training summary to {output_path}")
    
    def clear_training_history(self):
        """Clear training history."""
        self.training_status = {}
        self.training_history = {}
        logger.info("Cleared training history") 