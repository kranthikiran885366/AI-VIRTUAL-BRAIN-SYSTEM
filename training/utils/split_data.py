import numpy as np
import pandas as pd
from pathlib import Path
import json
import yaml
import logging
from typing import Dict, List, Any, Optional, Tuple
from sklearn.model_selection import train_test_split
import shutil

logger = logging.getLogger(__name__)

class DataSplitter:
    """Handles dataset splitting for different model types."""
    
    def __init__(self, config_path: str):
        """Initialize the data splitter.
        
        Args:
            config_path: Path to splitting configuration file
        """
        self.config = self._load_config(config_path)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load splitting configuration.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
        """
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise
    
    def split_emotion_data(
        self,
        data_path: str,
        output_path: str,
        test_size: float = 0.2,
        val_size: float = 0.1,
        random_state: int = 42
    ):
        """Split emotion recognition dataset.
        
        Args:
            data_path: Path to emotion dataset
            output_path: Path to save split datasets
            test_size: Proportion of test set
            val_size: Proportion of validation set
            random_state: Random seed
        """
        try:
            data_dir = Path(data_path)
            output_dir = Path(output_path)
            
            # Create output directories
            for split in ['train', 'val', 'test']:
                (output_dir / split).mkdir(parents=True, exist_ok=True)
            
            # Process each emotion class
            for emotion in self.config['emotion_classes']:
                emotion_dir = data_dir / emotion
                if not emotion_dir.exists():
                    continue
                
                # Get all images
                images = list(emotion_dir.glob('*.jpg'))
                
                # Split into train, val, test
                train_imgs, test_imgs = train_test_split(
                    images,
                    test_size=test_size,
                    random_state=random_state
                )
                
                train_imgs, val_imgs = train_test_split(
                    train_imgs,
                    test_size=val_size/(1-test_size),
                    random_state=random_state
                )
                
                # Copy images to respective directories
                for img, split in [
                    (train_imgs, 'train'),
                    (val_imgs, 'val'),
                    (test_imgs, 'test')
                ]:
                    split_dir = output_dir / split / emotion
                    split_dir.mkdir(parents=True, exist_ok=True)
                    
                    for img_path in img:
                        shutil.copy2(img_path, split_dir / img_path.name)
            
            logger.info(f"Split emotion data saved to {output_dir}")
            
        except Exception as e:
            logger.error(f"Error splitting emotion data: {e}")
            raise
    
    def split_face_data(
        self,
        data_path: str,
        output_path: str,
        test_size: float = 0.2,
        val_size: float = 0.1,
        random_state: int = 42
    ):
        """Split face recognition dataset.
        
        Args:
            data_path: Path to face dataset
            output_path: Path to save split datasets
            test_size: Proportion of test set
            val_size: Proportion of validation set
            random_state: Random seed
        """
        try:
            data_dir = Path(data_path)
            output_dir = Path(output_path)
            
            # Create output directories
            for split in ['train', 'val', 'test']:
                (output_dir / split).mkdir(parents=True, exist_ok=True)
            
            # Process each person's images
            for person_dir in data_dir.iterdir():
                if not person_dir.is_dir():
                    continue
                
                # Get all images
                images = list(person_dir.glob('*.jpg'))
                
                # Split into train, val, test
                train_imgs, test_imgs = train_test_split(
                    images,
                    test_size=test_size,
                    random_state=random_state
                )
                
                train_imgs, val_imgs = train_test_split(
                    train_imgs,
                    test_size=val_size/(1-test_size),
                    random_state=random_state
                )
                
                # Copy images to respective directories
                for img, split in [
                    (train_imgs, 'train'),
                    (val_imgs, 'val'),
                    (test_imgs, 'test')
                ]:
                    split_dir = output_dir / split / person_dir.name
                    split_dir.mkdir(parents=True, exist_ok=True)
                    
                    for img_path in img:
                        shutil.copy2(img_path, split_dir / img_path.name)
            
            logger.info(f"Split face data saved to {output_dir}")
            
        except Exception as e:
            logger.error(f"Error splitting face data: {e}")
            raise
    
    def split_language_data(
        self,
        data_path: str,
        output_path: str,
        test_size: float = 0.2,
        val_size: float = 0.1,
        random_state: int = 42
    ):
        """Split language model dataset.
        
        Args:
            data_path: Path to language dataset
            output_path: Path to save split datasets
            test_size: Proportion of test set
            val_size: Proportion of validation set
            random_state: Random seed
        """
        try:
            # Load data
            df = pd.read_csv(data_path)
            
            # Split into train, val, test
            train_df, test_df = train_test_split(
                df,
                test_size=test_size,
                random_state=random_state
            )
            
            train_df, val_df = train_test_split(
                train_df,
                test_size=val_size/(1-test_size),
                random_state=random_state
            )
            
            # Save splits
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for split_df, split_name in [
                (train_df, 'train'),
                (val_df, 'val'),
                (test_df, 'test')
            ]:
                split_df.to_csv(
                    output_dir / f"{split_name}.csv",
                    index=False
                )
            
            logger.info(f"Split language data saved to {output_dir}")
            
        except Exception as e:
            logger.error(f"Error splitting language data: {e}")
            raise
    
    def split_planning_data(
        self,
        data_path: str,
        output_path: str,
        test_size: float = 0.2,
        val_size: float = 0.1,
        random_state: int = 42
    ):
        """Split planning model dataset.
        
        Args:
            data_path: Path to planning dataset
            output_path: Path to save split datasets
            test_size: Proportion of test set
            val_size: Proportion of validation set
            random_state: Random seed
        """
        try:
            # Load data
            df = pd.read_csv(data_path)
            
            # Split into train, val, test
            train_df, test_df = train_test_split(
                df,
                test_size=test_size,
                random_state=random_state
            )
            
            train_df, val_df = train_test_split(
                train_df,
                test_size=val_size/(1-test_size),
                random_state=random_state
            )
            
            # Save splits
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for split_df, split_name in [
                (train_df, 'train'),
                (val_df, 'val'),
                (test_df, 'test')
            ]:
                split_df.to_csv(
                    output_dir / f"{split_name}.csv",
                    index=False
                )
            
            logger.info(f"Split planning data saved to {output_dir}")
            
        except Exception as e:
            logger.error(f"Error splitting planning data: {e}")
            raise
    
    def split_motivation_data(
        self,
        data_path: str,
        output_path: str,
        test_size: float = 0.2,
        val_size: float = 0.1,
        random_state: int = 42
    ):
        """Split motivation model dataset.
        
        Args:
            data_path: Path to motivation dataset
            output_path: Path to save split datasets
            test_size: Proportion of test set
            val_size: Proportion of validation set
            random_state: Random seed
        """
        try:
            # Load data
            df = pd.read_csv(data_path)
            
            # Split into train, val, test
            train_df, test_df = train_test_split(
                df,
                test_size=test_size,
                random_state=random_state
            )
            
            train_df, val_df = train_test_split(
                train_df,
                test_size=val_size/(1-test_size),
                random_state=random_state
            )
            
            # Save splits
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for split_df, split_name in [
                (train_df, 'train'),
                (val_df, 'val'),
                (test_df, 'test')
            ]:
                split_df.to_csv(
                    output_dir / f"{split_name}.csv",
                    index=False
                )
            
            logger.info(f"Split motivation data saved to {output_dir}")
            
        except Exception as e:
            logger.error(f"Error splitting motivation data: {e}")
            raise 