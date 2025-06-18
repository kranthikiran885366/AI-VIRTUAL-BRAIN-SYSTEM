import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ModelConfig:
    """Manages model configurations across different model types and services."""
    
    def __init__(self, base_dir: str):
        """Initialize the model configuration manager.
        
        Args:
            base_dir: Base directory for the project
        """
        self.base_dir = Path(base_dir)
        
        # Define model paths
        self.model_paths = {
            "emotion": self.base_dir / "models/emotion_model",
            "face": self.base_dir / "models/face_recognition_model",
            "language": self.base_dir / "models/language_model",
            "planning": self.base_dir / "models/planning_model",
            "motivation": self.base_dir / "models/motivation_model"
        }
        
        # Define dataset paths
        self.dataset_paths = {
            "emotions": self.base_dir / "datasets/emotions_dataset",
            "face": self.base_dir / "datasets/face_images",
            "conversations": self.base_dir / "datasets/conversations_dataset",
            "movement": self.base_dir / "datasets/movement_data",
            "planning": self.base_dir / "datasets/planning_goals"
        }
        
        # Define training paths
        self.training_paths = {
            "base": self.base_dir / "training",
            "configs": self.base_dir / "training/configs",
            "utils": self.base_dir / "training/utils"
        }
        
        # Define serving paths
        self.serving_paths = {
            "base": self.base_dir / "model_serving",
            "config": self.base_dir / "model_serving/config.yaml"
        }
        
        # Load configurations
        self.configs = {}
        self._load_configs()
    
    def _load_configs(self):
        """Load all configuration files."""
        try:
            # Load model configs
            for model_type, path in self.model_paths.items():
                config_file = path / "config.yaml"
                if config_file.exists():
                    with open(config_file, "r") as f:
                        self.configs[f"{model_type}_model"] = yaml.safe_load(f)
            
            # Load training configs
            configs_dir = self.training_paths["configs"]
            if configs_dir.exists():
                for config_file in configs_dir.glob("*.yaml"):
                    model_type = config_file.stem.replace("_config", "")
                    with open(config_file, "r") as f:
                        self.configs[f"{model_type}_training"] = yaml.safe_load(f)
            
            # Load serving config
            serving_config = self.serving_paths["config"]
            if serving_config.exists():
                with open(serving_config, "r") as f:
                    self.configs["serving"] = yaml.safe_load(f)
            
        except Exception as e:
            logger.error(f"Error loading configurations: {e}")
            raise
    
    def get_model_config(self, model_type: str) -> Dict[str, Any]:
        """Get configuration for a specific model.
        
        Args:
            model_type: Type of model
            
        Returns:
            Model configuration
        """
        config_key = f"{model_type}_model"
        if config_key not in self.configs:
            raise ValueError(f"No configuration found for model type: {model_type}")
        return self.configs[config_key]
    
    def get_training_config(self, model_type: str) -> Dict[str, Any]:
        """Get training configuration for a specific model.
        
        Args:
            model_type: Type of model
            
        Returns:
            Training configuration
        """
        config_key = f"{model_type}_training"
        if config_key not in self.configs:
            raise ValueError(f"No training configuration found for model type: {model_type}")
        return self.configs[config_key]
    
    def get_serving_config(self) -> Dict[str, Any]:
        """Get serving configuration.
        
        Returns:
            Serving configuration
        """
        if "serving" not in self.configs:
            raise ValueError("No serving configuration found")
        return self.configs["serving"]
    
    def get_model_path(self, model_type: str) -> Path:
        """Get path for a specific model.
        
        Args:
            model_type: Type of model
            
        Returns:
            Model directory path
        """
        if model_type not in self.model_paths:
            raise ValueError(f"Unknown model type: {model_type}")
        return self.model_paths[model_type]
    
    def get_dataset_path(self, dataset_type: str) -> Path:
        """Get path for a specific dataset.
        
        Args:
            dataset_type: Type of dataset
            
        Returns:
            Dataset directory path
        """
        if dataset_type not in self.dataset_paths:
            raise ValueError(f"Unknown dataset type: {dataset_type}")
        return self.dataset_paths[dataset_type]
    
    def get_training_path(self, path_type: str) -> Path:
        """Get path for training-related files.
        
        Args:
            path_type: Type of training path
            
        Returns:
            Training path
        """
        if path_type not in self.training_paths:
            raise ValueError(f"Unknown training path type: {path_type}")
        return self.training_paths[path_type]
    
    def get_serving_path(self, path_type: str) -> Path:
        """Get path for serving-related files.
        
        Args:
            path_type: Type of serving path
            
        Returns:
            Serving path
        """
        if path_type not in self.serving_paths:
            raise ValueError(f"Unknown serving path type: {path_type}")
        return self.serving_paths[path_type]
    
    def update_model_config(
        self,
        model_type: str,
        config: Dict[str, Any]
    ):
        """Update configuration for a specific model.
        
        Args:
            model_type: Type of model
            config: New configuration
        """
        try:
            config_file = self.model_paths[model_type] / "config.yaml"
            with open(config_file, "w") as f:
                yaml.dump(config, f)
            
            self.configs[f"{model_type}_model"] = config
            logger.info(f"Updated configuration for model {model_type}")
            
        except Exception as e:
            logger.error(f"Error updating model configuration: {e}")
            raise
    
    def update_training_config(
        self,
        model_type: str,
        config: Dict[str, Any]
    ):
        """Update training configuration for a specific model.
        
        Args:
            model_type: Type of model
            config: New training configuration
        """
        try:
            config_file = self.training_paths["configs"] / f"{model_type}_config.yaml"
            with open(config_file, "w") as f:
                yaml.dump(config, f)
            
            self.configs[f"{model_type}_training"] = config
            logger.info(f"Updated training configuration for model {model_type}")
            
        except Exception as e:
            logger.error(f"Error updating training configuration: {e}")
            raise
    
    def update_serving_config(self, config: Dict[str, Any]):
        """Update serving configuration.
        
        Args:
            config: New serving configuration
        """
        try:
            config_file = self.serving_paths["config"]
            with open(config_file, "w") as f:
                yaml.dump(config, f)
            
            self.configs["serving"] = config
            logger.info("Updated serving configuration")
            
        except Exception as e:
            logger.error(f"Error updating serving configuration: {e}")
            raise
    
    def get_dataset_file(
        self,
        dataset_type: str,
        file_path: str
    ) -> Path:
        """Get path for a specific dataset file.
        
        Args:
            dataset_type: Type of dataset
            file_path: Relative path to file within dataset directory
            
        Returns:
            Full path to dataset file
        """
        dataset_dir = self.get_dataset_path(dataset_type)
        return dataset_dir / file_path
    
    def get_model_file(
        self,
        model_type: str,
        file_name: str
    ) -> Path:
        """Get path for a specific model file.
        
        Args:
            model_type: Type of model
            file_name: Name of model file
            
        Returns:
            Full path to model file
        """
        model_dir = self.get_model_path(model_type)
        return model_dir / file_name

# Create global instance
model_config = ModelConfig(os.getenv("PROJECT_ROOT", os.getcwd())) 