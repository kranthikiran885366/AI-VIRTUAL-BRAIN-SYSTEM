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
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from utils.preprocessing import DataPreprocessor
from utils.metrics import calculate_metrics
from utils.visualize import Visualizer
from utils.split_data import DataSplitter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LanguageModel(nn.Module):
    """Language model architecture using transformer-based model."""
    
    def __init__(self, model_name: str, num_labels: int):
        """Initialize the model.
        
        Args:
            model_name: Name of the pretrained model
            num_labels: Number of output labels
        """
        super().__init__()
        
        # Load pretrained model
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=num_labels
        )
        
        # Freeze base model parameters
        for param in self.model.base_model.parameters():
            param.requires_grad = False
        
        # Add custom classification head
        self.classifier = nn.Sequential(
            nn.Linear(self.model.config.hidden_size, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, num_labels)
        )
    
    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """Forward pass.
        
        Args:
            input_ids: Input token IDs
            attention_mask: Attention mask
            
        Returns:
            Output logits
        """
        # Get base model outputs
        outputs = self.model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_hidden_states=True
        )
        
        # Use last hidden state for classification
        last_hidden_state = outputs.hidden_states[-1]
        pooled_output = last_hidden_state[:, 0, :]  # Use [CLS] token
        
        # Pass through classifier
        logits = self.classifier(pooled_output)
        
        return logits

def train_language_model(
    config_path: str,
    data_dir: str,
    output_dir: str,
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
):
    """Train language model.
    
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
        splitter.split_language_data(
            data_path=data_dir,
            output_path=str(output_dir / 'splits'),
            test_size=config['test_size'],
            val_size=config['val_size']
        )
        
        # Preprocess data
        train_input_ids, train_attention_mask = preprocessor.preprocess_language_data(
            data_path=str(output_dir / 'splits'),
            split='train'
        )
        val_input_ids, val_attention_mask = preprocessor.preprocess_language_data(
            data_path=str(output_dir / 'splits'),
            split='val'
        )
        
        # Create data loaders
        train_dataset = torch.utils.data.TensorDataset(
            train_input_ids,
            train_attention_mask
        )
        val_dataset = torch.utils.data.TensorDataset(
            val_input_ids,
            val_attention_mask
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
        model = LanguageModel(
            model_name=config['model_name'],
            num_labels=len(config['intent_classes'])
        )
        model = model.to(device)
        
        # Initialize optimizer and loss function
        optimizer = optim.AdamW(
            model.parameters(),
            lr=config['learning_rate'],
            weight_decay=config['weight_decay']
        )
        criterion = nn.CrossEntropyLoss()
        
        # Initialize visualizer
        visualizer = Visualizer(str(output_dir / 'plots'))
        
        # Training loop
        best_val_loss = float('inf')
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
            
            for input_ids, attention_mask in train_loader:
                input_ids = input_ids.to(device)
                attention_mask = attention_mask.to(device)
                
                optimizer.zero_grad()
                outputs = model(input_ids, attention_mask)
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
                for input_ids, attention_mask in val_loader:
                    input_ids = input_ids.to(device)
                    attention_mask = attention_mask.to(device)
                    
                    outputs = model(input_ids, attention_mask)
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
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(
                    model.state_dict(),
                    output_dir / 'best_model.pt'
                )
                logger.info(f'Saved best model with validation loss: {val_loss:.4f}')
            
            # Plot training history
            visualizer.plot_training_history(
                history=history,
                model_type='language',
                metrics=['loss', 'accuracy']
            )
        
        # Save final model
        torch.save(
            model.state_dict(),
            output_dir / 'final_model.pt'
        )
        
        # Save tokenizer
        tokenizer = AutoTokenizer.from_pretrained(config['model_name'])
        tokenizer.save_pretrained(output_dir / 'tokenizer')
        
        # Save training configuration
        config['training_completed'] = datetime.now().isoformat()
        with open(output_dir / 'training_config.yaml', 'w') as f:
            yaml.dump(config, f)
        
        logger.info('Training completed successfully')
        
    except Exception as e:
        logger.error(f'Error training language model: {e}')
        raise

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Train language model')
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
    
    train_language_model(
        config_path=args.config,
        data_dir=args.data_dir,
        output_dir=args.output_dir
    ) 