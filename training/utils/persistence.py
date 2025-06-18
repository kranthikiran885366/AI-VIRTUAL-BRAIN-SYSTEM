import os
import pickle
import json
import yaml
import logging
from typing import Any, Dict, Optional, Tuple
from datetime import datetime
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

class ModelPersistence:
    """Class for model persistence and loading."""
    
    def __init__(
        self,
        base_dir: str = "models",
        version_format: str = "%Y%m%d_%H%M%S"
    ):
        """Initialize the persistence manager.
        
        Args:
            base_dir: Base directory for model storage
            version_format: Format string for version timestamps
        """
        self.base_dir = Path(base_dir)
        self.version_format = version_format
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save_model(
        self,
        model: Any,
        model_name: str,
        metadata: Optional[Dict] = None,
        version: Optional[str] = None
    ) -> str:
        """Save model and metadata.
        
        Args:
            model: The model to save
            model_name: Name of the model
            metadata: Additional metadata to save
            version: Version identifier (if None, timestamp will be used)
            
        Returns:
            Version identifier
        """
        # Generate version if not provided
        if version is None:
            version = datetime.now().strftime(self.version_format)
        
        # Create model directory
        model_dir = self.base_dir / model_name / version
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = model_dir / "model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        
        # Save metadata
        if metadata is None:
            metadata = {}
        
        metadata["version"] = version
        metadata["timestamp"] = datetime.now().isoformat()
        
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Saved model {model_name} version {version}")
        return version
    
    def load_model(
        self,
        model_name: str,
        version: Optional[str] = None
    ) -> Tuple[Any, Dict]:
        """Load model and metadata.
        
        Args:
            model_name: Name of the model
            version: Version to load (if None, latest version will be loaded)
            
        Returns:
            Tuple of (model, metadata)
        """
        model_base_dir = self.base_dir / model_name
        
        # Get version if not specified
        if version is None:
            versions = sorted(
                [d.name for d in model_base_dir.iterdir() if d.is_dir()],
                reverse=True
            )
            if not versions:
                raise ValueError(f"No versions found for model {model_name}")
            version = versions[0]
        
        model_dir = model_base_dir / version
        
        # Load model
        model_path = model_dir / "model.pkl"
        if not model_path.exists():
            raise ValueError(f"Model file not found: {model_path}")
        
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        
        # Load metadata
        metadata_path = model_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
        else:
            metadata = {}
        
        logger.info(f"Loaded model {model_name} version {version}")
        return model, metadata
    
    def list_models(self) -> Dict[str, list]:
        """List all available models and their versions.
        
        Returns:
            Dictionary mapping model names to lists of versions
        """
        models = {}
        
        for model_dir in self.base_dir.iterdir():
            if model_dir.is_dir():
                versions = sorted(
                    [d.name for d in model_dir.iterdir() if d.is_dir()],
                    reverse=True
                )
                models[model_dir.name] = versions
        
        return models
    
    def delete_model(
        self,
        model_name: str,
        version: Optional[str] = None
    ):
        """Delete model version.
        
        Args:
            model_name: Name of the model
            version: Version to delete (if None, all versions will be deleted)
        """
        model_base_dir = self.base_dir / model_name
        
        if version is None:
            # Delete all versions
            if model_base_dir.exists():
                for version_dir in model_base_dir.iterdir():
                    if version_dir.is_dir():
                        self._delete_directory(version_dir)
                model_base_dir.rmdir()
                logger.info(f"Deleted all versions of model {model_name}")
        else:
            # Delete specific version
            version_dir = model_base_dir / version
            if version_dir.exists():
                self._delete_directory(version_dir)
                logger.info(f"Deleted model {model_name} version {version}")
    
    def _delete_directory(self, directory: Path):
        """Recursively delete directory."""
        for item in directory.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                self._delete_directory(item)
        directory.rmdir()
    
    def save_training_config(
        self,
        config: Dict,
        model_name: str,
        version: Optional[str] = None
    ) -> str:
        """Save training configuration.
        
        Args:
            config: Configuration dictionary
            model_name: Name of the model
            version: Version identifier (if None, timestamp will be used)
            
        Returns:
            Version identifier
        """
        if version is None:
            version = datetime.now().strftime(self.version_format)
        
        config_dir = self.base_dir / model_name / version
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_path = config_dir / "training_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        
        logger.info(f"Saved training config for model {model_name} version {version}")
        return version
    
    def load_training_config(
        self,
        model_name: str,
        version: Optional[str] = None
    ) -> Dict:
        """Load training configuration.
        
        Args:
            model_name: Name of the model
            version: Version to load (if None, latest version will be loaded)
            
        Returns:
            Configuration dictionary
        """
        model_base_dir = self.base_dir / model_name
        
        if version is None:
            versions = sorted(
                [d.name for d in model_base_dir.iterdir() if d.is_dir()],
                reverse=True
            )
            if not versions:
                raise ValueError(f"No versions found for model {model_name}")
            version = versions[0]
        
        config_path = model_base_dir / version / "training_config.yaml"
        if not config_path.exists():
            raise ValueError(f"Training config not found: {config_path}")
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded training config for model {model_name} version {version}")
        return config 