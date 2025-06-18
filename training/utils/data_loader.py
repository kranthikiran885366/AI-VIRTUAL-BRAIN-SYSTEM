import os
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import logging
import json
import yaml
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)

class DataLoader:
    """Class for loading and processing data."""
    
    def __init__(
        self,
        base_dir: str = "datasets",
        cache_dir: Optional[str] = None
    ):
        """Initialize the data loader.
        
        Args:
            base_dir: Base directory for datasets
            cache_dir: Directory for caching processed data
        """
        self.base_dir = Path(base_dir)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def load_dataset(
        self,
        dataset_name: str,
        file_name: str,
        **kwargs
    ) -> pd.DataFrame:
        """Load dataset from file.
        
        Args:
            dataset_name: Name of the dataset
            file_name: Name of the file
            **kwargs: Additional arguments for pd.read_csv
            
        Returns:
            Loaded DataFrame
        """
        file_path = self.base_dir / dataset_name / file_name
        
        if not file_path.exists():
            raise ValueError(f"Dataset file not found: {file_path}")
        
        # Try to load from cache first
        if self.cache_dir:
            cache_path = self.cache_dir / f"{dataset_name}_{file_name}.parquet"
            if cache_path.exists():
                logger.info(f"Loading from cache: {cache_path}")
                return pd.read_parquet(cache_path)
        
        # Load from original file
        logger.info(f"Loading dataset: {file_path}")
        df = pd.read_csv(file_path, **kwargs)
        
        # Cache the loaded data
        if self.cache_dir:
            cache_path = self.cache_dir / f"{dataset_name}_{file_name}.parquet"
            df.to_parquet(cache_path)
            logger.info(f"Cached dataset to: {cache_path}")
        
        return df
    
    def save_dataset(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        file_name: str,
        format: str = "csv"
    ):
        """Save dataset to file.
        
        Args:
            df: DataFrame to save
            dataset_name: Name of the dataset
            file_name: Name of the file
            format: File format (csv or parquet)
        """
        dataset_dir = self.base_dir / dataset_name
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = dataset_dir / file_name
        
        if format == "csv":
            df.to_csv(file_path, index=False)
        elif format == "parquet":
            df.to_parquet(file_path)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Saved dataset to: {file_path}")
    
    def split_dataset(
        self,
        df: pd.DataFrame,
        target_col: str,
        test_size: float = 0.2,
        val_size: float = 0.1,
        random_state: Optional[int] = None,
        stratify: bool = True
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split dataset into train, validation, and test sets.
        
        Args:
            df: Input DataFrame
            target_col: Name of the target column
            test_size: Proportion of test set
            val_size: Proportion of validation set
            random_state: Random seed
            stratify: Whether to stratify by target
            
        Returns:
            Tuple of (train_df, val_df, test_df)
        """
        # Calculate validation size relative to remaining data
        val_size_adjusted = val_size / (1 - test_size)
        
        # First split: separate test set
        stratify_col = df[target_col] if stratify else None
        train_val_df, test_df = train_test_split(
            df,
            test_size=test_size,
            random_state=random_state,
            stratify=stratify_col
        )
        
        # Second split: separate validation set
        stratify_col = train_val_df[target_col] if stratify else None
        train_df, val_df = train_test_split(
            train_val_df,
            test_size=val_size_adjusted,
            random_state=random_state,
            stratify=stratify_col
        )
        
        return train_df, val_df, test_df
    
    def load_config(
        self,
        dataset_name: str,
        config_name: str = "config.yaml"
    ) -> Dict:
        """Load dataset configuration.
        
        Args:
            dataset_name: Name of the dataset
            config_name: Name of the config file
            
        Returns:
            Configuration dictionary
        """
        config_path = self.base_dir / dataset_name / config_name
        
        if not config_path.exists():
            raise ValueError(f"Config file not found: {config_path}")
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        return config
    
    def save_config(
        self,
        config: Dict,
        dataset_name: str,
        config_name: str = "config.yaml"
    ):
        """Save dataset configuration.
        
        Args:
            config: Configuration dictionary
            dataset_name: Name of the dataset
            config_name: Name of the config file
        """
        dataset_dir = self.base_dir / dataset_name
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        config_path = dataset_dir / config_name
        
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        
        logger.info(f"Saved config to: {config_path}")
    
    def get_dataset_info(
        self,
        dataset_name: str
    ) -> Dict:
        """Get information about a dataset.
        
        Args:
            dataset_name: Name of the dataset
            
        Returns:
            Dictionary with dataset information
        """
        dataset_dir = self.base_dir / dataset_name
        
        if not dataset_dir.exists():
            raise ValueError(f"Dataset directory not found: {dataset_dir}")
        
        info = {
            "name": dataset_name,
            "files": [],
            "config": None
        }
        
        # List all files
        for file_path in dataset_dir.iterdir():
            if file_path.is_file():
                file_info = {
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime
                }
                info["files"].append(file_info)
        
        # Load config if exists
        config_path = dataset_dir / "config.yaml"
        if config_path.exists():
            with open(config_path, "r") as f:
                info["config"] = yaml.safe_load(f)
        
        return info
    
    def list_datasets(self) -> List[str]:
        """List all available datasets.
        
        Returns:
            List of dataset names
        """
        return [
            d.name for d in self.base_dir.iterdir()
            if d.is_dir()
        ]
    
    def clear_cache(self):
        """Clear the cache directory."""
        if self.cache_dir and self.cache_dir.exists():
            for file_path in self.cache_dir.iterdir():
                if file_path.is_file():
                    file_path.unlink()
            logger.info("Cleared cache directory") 