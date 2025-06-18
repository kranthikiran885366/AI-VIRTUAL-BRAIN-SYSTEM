import numpy as np
import pandas as pd
from pathlib import Path
import json
import yaml
import logging
from typing import Dict, List, Any, Optional, Tuple
from sklearn.preprocessing import StandardScaler, LabelEncoder
import cv2
from PIL import Image
import torch
from transformers import AutoTokenizer

logger = logging.getLogger(__name__)

class DataPreprocessor:
    """Handles data preprocessing for different model types."""
    
    def __init__(self, config_path: str):
        """Initialize the preprocessor.
        
        Args:
            config_path: Path to preprocessing configuration file
        """
        self.config = self._load_config(config_path)
        self.scalers = {}
        self.label_encoders = {}
        self.tokenizer = None
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load preprocessing configuration.
        
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
    
    def preprocess_emotion_data(
        self,
        data_path: str,
        split: str = 'train'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Preprocess emotion recognition data.
        
        Args:
            data_path: Path to emotion dataset
            split: Data split (train/val/test)
            
        Returns:
            Tuple of (features, labels)
        """
        try:
            # Load data
            data_dir = Path(data_path) / split
            features = []
            labels = []
            
            # Process each emotion class
            for emotion in self.config['emotion_classes']:
                emotion_dir = data_dir / emotion
                for img_path in emotion_dir.glob('*.jpg'):
                    # Load and preprocess image
                    img = cv2.imread(str(img_path))
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    img = cv2.resize(img, tuple(self.config['image_size']))
                    img = img / 255.0  # Normalize
                    
                    features.append(img)
                    labels.append(emotion)
            
            # Convert to numpy arrays
            X = np.array(features)
            y = np.array(labels)
            
            # Encode labels
            if 'emotion' not in self.label_encoders:
                self.label_encoders['emotion'] = LabelEncoder()
                self.label_encoders['emotion'].fit(self.config['emotion_classes'])
            
            y = self.label_encoders['emotion'].transform(y)
            
            return X, y
            
        except Exception as e:
            logger.error(f"Error preprocessing emotion data: {e}")
            raise
    
    def preprocess_face_data(
        self,
        data_path: str,
        split: str = 'train'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Preprocess face recognition data.
        
        Args:
            data_path: Path to face dataset
            split: Data split (train/val/test)
            
        Returns:
            Tuple of (features, labels)
        """
        try:
            # Load data
            data_dir = Path(data_path) / split
            features = []
            labels = []
            
            # Process each person's images
            for person_dir in data_dir.iterdir():
                if person_dir.is_dir():
                    for img_path in person_dir.glob('*.jpg'):
                        # Load and preprocess image
                        img = cv2.imread(str(img_path))
                        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        img = cv2.resize(img, tuple(self.config['face_size']))
                        img = img / 255.0  # Normalize
                        
                        features.append(img)
                        labels.append(person_dir.name)
            
            # Convert to numpy arrays
            X = np.array(features)
            y = np.array(labels)
            
            # Encode labels
            if 'face' not in self.label_encoders:
                self.label_encoders['face'] = LabelEncoder()
                self.label_encoders['face'].fit(labels)
            
            y = self.label_encoders['face'].transform(y)
            
            return X, y
            
        except Exception as e:
            logger.error(f"Error preprocessing face data: {e}")
            raise
    
    def preprocess_language_data(
        self,
        data_path: str,
        split: str = 'train'
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Preprocess language model data.
        
        Args:
            data_path: Path to language dataset
            split: Data split (train/val/test)
            
        Returns:
            Tuple of (input_ids, attention_mask)
        """
        try:
            # Initialize tokenizer if not already done
            if self.tokenizer is None:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.config['tokenizer_name']
                )
            
            # Load data
            data_file = Path(data_path) / f"{split}.csv"
            df = pd.read_csv(data_file)
            
            # Tokenize text
            encodings = self.tokenizer(
                df['text'].tolist(),
                truncation=True,
                padding=True,
                max_length=self.config['max_length'],
                return_tensors='pt'
            )
            
            return encodings['input_ids'], encodings['attention_mask']
            
        except Exception as e:
            logger.error(f"Error preprocessing language data: {e}")
            raise
    
    def preprocess_planning_data(
        self,
        data_path: str,
        split: str = 'train'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Preprocess planning model data.
        
        Args:
            data_path: Path to planning dataset
            split: Data split (train/val/test)
            
        Returns:
            Tuple of (features, labels)
        """
        try:
            # Load data
            data_file = Path(data_path) / f"{split}.csv"
            df = pd.read_csv(data_file)
            
            # Extract features and labels
            feature_cols = self.config['feature_columns']
            label_cols = self.config['label_columns']
            
            X = df[feature_cols].values
            y = df[label_cols].values
            
            # Scale features
            if 'planning' not in self.scalers:
                self.scalers['planning'] = StandardScaler()
                self.scalers['planning'].fit(X)
            
            X = self.scalers['planning'].transform(X)
            
            return X, y
            
        except Exception as e:
            logger.error(f"Error preprocessing planning data: {e}")
            raise
    
    def preprocess_motivation_data(
        self,
        data_path: str,
        split: str = 'train'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Preprocess motivation model data.
        
        Args:
            data_path: Path to motivation dataset
            split: Data split (train/val/test)
            
        Returns:
            Tuple of (features, rewards)
        """
        try:
            # Load data
            data_file = Path(data_path) / f"{split}.csv"
            df = pd.read_csv(data_file)
            
            # Extract features and rewards
            feature_cols = self.config['feature_columns']
            reward_cols = self.config['reward_columns']
            
            X = df[feature_cols].values
            y = df[reward_cols].values
            
            # Scale features
            if 'motivation' not in self.scalers:
                self.scalers['motivation'] = StandardScaler()
                self.scalers['motivation'].fit(X)
            
            X = self.scalers['motivation'].transform(X)
            
            return X, y
            
        except Exception as e:
            logger.error(f"Error preprocessing motivation data: {e}")
            raise
    
    def save_preprocessors(self, output_dir: str):
        """Save preprocessors for later use.
        
        Args:
            output_dir: Directory to save preprocessors
        """
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save scalers
            for name, scaler in self.scalers.items():
                np.save(output_dir / f"{name}_scaler.npy", scaler)
            
            # Save label encoders
            for name, encoder in self.label_encoders.items():
                np.save(output_dir / f"{name}_encoder.npy", encoder)
            
            # Save tokenizer
            if self.tokenizer:
                self.tokenizer.save_pretrained(output_dir / "tokenizer")
            
            logger.info(f"Saved preprocessors to {output_dir}")
            
        except Exception as e:
            logger.error(f"Error saving preprocessors: {e}")
            raise
    
    def load_preprocessors(self, input_dir: str):
        """Load saved preprocessors.
        
        Args:
            input_dir: Directory containing saved preprocessors
        """
        try:
            input_dir = Path(input_dir)
            
            # Load scalers
            for scaler_file in input_dir.glob("*_scaler.npy"):
                name = scaler_file.stem.replace("_scaler", "")
                self.scalers[name] = np.load(scaler_file, allow_pickle=True).item()
            
            # Load label encoders
            for encoder_file in input_dir.glob("*_encoder.npy"):
                name = encoder_file.stem.replace("_encoder", "")
                self.label_encoders[name] = np.load(encoder_file, allow_pickle=True).item()
            
            # Load tokenizer
            tokenizer_dir = input_dir / "tokenizer"
            if tokenizer_dir.exists():
                self.tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir))
            
            logger.info(f"Loaded preprocessors from {input_dir}")
            
        except Exception as e:
            logger.error(f"Error loading preprocessors: {e}")
            raise

def load_and_preprocess_data(
    data_path: str,
    config: Dict[str, Any]
) -> Tuple[np.ndarray, np.ndarray, DataPreprocessor]:
    """Load and preprocess data from file."""
    # Load data
    data = pd.read_csv(data_path)
    
    # Create preprocessor
    preprocessor = DataPreprocessor(config)
    
    # Preprocess data
    X, y = preprocessor.preprocess(data)
    
    return X, y, preprocessor

def split_data(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float,
    validation_size: float,
    random_state: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split data into train, validation, and test sets."""
    from sklearn.model_selection import train_test_split
    
    # First split: separate test set
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y,
        test_size=test_size,
        random_state=random_state
    )
    
    # Second split: separate validation set from training set
    val_size_adjusted = validation_size / (1 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp,
        test_size=val_size_adjusted,
        random_state=random_state
    )
    
    return X_train, X_val, X_test, y_train, y_val, y_test