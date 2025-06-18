import os
import yaml
import logging
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from pathlib import Path
import numpy as np
from datetime import datetime

from utils.preprocessing import DataPreprocessor
from utils.metrics import calculate_metrics, plot_confusion_matrix, plot_roc_curves
from utils.visualize import Visualizer
from utils.split_data import DataSplitter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmotionModel(nn.Module):
    """Emotion recognition model architecture."""
    
    def __init__(self, num_classes: int):
        """Initialize the model.
        
        Args:
            num_classes: Number of emotion classes
        """
        super().__init__()
        
        # Convolutional layers
        self.conv1 = nn.Conv2d(3, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        
        # Pooling and dropout
        self.pool = nn.MaxPool2d(2, 2)
        self.dropout = nn.Dropout(0.5)
        
        # Fully connected layers
        self.fc1 = nn.Linear(128 * 8 * 8, 512)
        self.fc2 = nn.Linear(512, num_classes)
        
        # Activation functions
        self.relu = nn.ReLU()
        self.softmax = nn.Softmax(dim=1)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.
        
        Args:
            x: Input tensor
            
        Returns:
            Output tensor
        """
        # Convolutional layers
        x = self.pool(self.relu(self.conv1(x)))
        x = self.pool(self.relu(self.conv2(x)))
        x = self.pool(self.relu(self.conv3(x)))
        
        # Flatten
        x = x.view(-1, 128 * 8 * 8)
        
        # Fully connected layers
        x = self.dropout(self.relu(self.fc1(x)))
        x = self.fc2(x)
        
        return self.softmax(x)

def train_emotion_model(
    config_path: str,
    data_dir: str,
    output_dir: str,
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
):
    """Train emotion recognition model.
    
    Args:
        config_path: Path to training configuration
        data_dir: Path to dataset directory
        output_dir: Path to save model and results
        device: Device to train on
    """
    try:
        # Load configuration
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Create output directory
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize data preprocessor and splitter
        preprocessor = DataPreprocessor(config['preprocessing_config'])
        splitter = DataSplitter(config['splitting_config'])
        
        # Split data
        splitter.split_emotion_data(
            data_path=data_dir,
            output_path=str(output_dir / 'splits'),
            test_size=config['test_size'],
            val_size=config['val_size']
        )
        
        # Preprocess data
        train_data, train_labels = preprocessor.preprocess_emotion_data(
            data_path=str(output_dir / 'splits'),
            split='train'
        )
        val_data, val_labels = preprocessor.preprocess_emotion_data(
            data_path=str(output_dir / 'splits'),
            split='val'
        )
        
        # Create data loaders
        train_dataset = torch.utils.data.TensorDataset(
            torch.FloatTensor(train_data),
            torch.LongTensor(train_labels)
        )
        val_dataset = torch.utils.data.TensorDataset(
            torch.FloatTensor(val_data),
            torch.LongTensor(val_labels)
        )
        
        train_loader = DataLoader(
            train_dataset,
            batch_size=config['batch_size'],
            shuffle=True
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=config['batch_size']
        )
        
        # Initialize model
        model = EmotionModel(num_classes=len(config['emotion_classes']))
        model = model.to(device)
        
        # Initialize optimizer and loss function
        optimizer = optim.Adam(
            model.parameters(),
            lr=config['learning_rate']
        )
        criterion = nn.CrossEntropyLoss()
        
        # Initialize visualizer
        visualizer = Visualizer(str(output_dir / 'plots'))
        
        # Training loop
        best_val_acc = 0.0
        history = {
            'train_loss': [],
            'train_acc': [],
            'val_loss': [],
            'val_acc': []
        }
        
        for epoch in range(config['epochs']):
            # Training phase
            model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0
            
            for inputs, labels in train_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                
                optimizer.zero_grad()
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
                _, predicted = outputs.max(1)
                train_total += labels.size(0)
                train_correct += predicted.eq(labels).sum().item()
            
            train_loss = train_loss / len(train_loader)
            train_acc = train_correct / train_total
            
            # Validation phase
            model.eval()
            val_loss = 0.0
            val_correct = 0
            val_total = 0
            
            with torch.no_grad():
                for inputs, labels in val_loader:
                    inputs, labels = inputs.to(device), labels.to(device)
                    
                    outputs = model(inputs)
                    loss = criterion(outputs, labels)
                    
                    val_loss += loss.item()
                    _, predicted = outputs.max(1)
                    val_total += labels.size(0)
                    val_correct += predicted.eq(labels).sum().item()
            
            val_loss = val_loss / len(val_loader)
            val_acc = val_correct / val_total
            
            # Update history
            history['train_loss'].append(train_loss)
            history['train_acc'].append(train_acc)
            history['val_loss'].append(val_loss)
            history['val_acc'].append(val_acc)
            
            # Log progress
            logger.info(
                f'Epoch {epoch+1}/{config["epochs"]} - '
                f'Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f} - '
                f'Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}'
            )
            
            # Save best model
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                torch.save(
                    model.state_dict(),
                    output_dir / 'best_model.pth'
                )
                logger.info(f'Saved best model with validation accuracy: {val_acc:.4f}')
            
            # Plot training history
            visualizer.plot_training_history(
                history=history,
                model_type='emotion',
                metrics=['loss', 'accuracy']
            )
        
        # Save final model
        torch.save(
            model.state_dict(),
            output_dir / 'final_model.pth'
        )
        
        # Save training configuration
        config['training_completed'] = datetime.now().isoformat()
        with open(output_dir / 'training_config.yaml', 'w') as f:
            yaml.dump(config, f)
        
        logger.info('Training completed successfully')
        
    except Exception as e:
        logger.error(f'Error training emotion model: {e}')
        raise

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Train emotion recognition model')
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to training configuration file'
    )
    parser.add_argument(
        '--data_dir',
        type=str,
        required=True,
        help='Path to dataset directory'
    )
    parser.add_argument(
        '--output_dir',
        type=str,
        required=True,
        help='Path to save model and results'
    )
    
    args = parser.parse_args()
    
    train_emotion_model(
        config_path=args.config,
        data_dir=args.data_dir,
        output_dir=args.output_dir
    ) 