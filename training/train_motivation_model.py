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
from utils.metrics import calculate_metrics
from utils.visualize import Visualizer
from utils.split_data import DataSplitter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MotivationModel(nn.Module):
    """Motivation model architecture."""
    
    def __init__(self, input_dim: int, hidden_dim: int):
        """Initialize the model.
        
        Args:
            input_dim: Input dimension
            hidden_dim: Hidden dimension
        """
        super().__init__()
        
        # Feature encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2)
        )
        
        # Reward predictor
        self.reward_predictor = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim // 2, 1)
        )
        
        # Value function
        self.value_function = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim // 2, 1)
        )
    
    def forward(
        self,
        state: torch.Tensor,
        action: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass.
        
        Args:
            state: Current state
            action: Current action
            
        Returns:
            Tuple of (reward, value)
        """
        # Encode state and action
        x = torch.cat([state, action], dim=1)
        features = self.encoder(x)
        
        # Predict reward and value
        reward = self.reward_predictor(features)
        value = self.value_function(features)
        
        return reward, value

def train_motivation_model(
    config_path: str,
    data_dir: str,
    output_dir: str,
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
):
    """Train motivation model.
    
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
        splitter.split_motivation_data(
            data_path=data_dir,
            output_path=str(output_dir / 'splits'),
            test_size=config['test_size'],
            val_size=config['val_size']
        )
        
        # Preprocess data
        train_states, train_rewards = preprocessor.preprocess_motivation_data(
            data_path=str(output_dir / 'splits'),
            split='train'
        )
        val_states, val_rewards = preprocessor.preprocess_motivation_data(
            data_path=str(output_dir / 'splits'),
            split='val'
        )
        
        # Create data loaders
        train_dataset = torch.utils.data.TensorDataset(
            torch.FloatTensor(train_states),
            torch.FloatTensor(train_rewards)
        )
        val_dataset = torch.utils.data.TensorDataset(
            torch.FloatTensor(val_states),
            torch.FloatTensor(val_rewards)
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
        model = MotivationModel(
            input_dim=config['state_dim'] + config['action_dim'],
            hidden_dim=config['hidden_dim']
        )
        model = model.to(device)
        
        # Initialize optimizer and loss functions
        optimizer = optim.Adam(
            model.parameters(),
            lr=config['learning_rate']
        )
        reward_criterion = nn.MSELoss()
        value_criterion = nn.MSELoss()
        
        # Initialize visualizer
        visualizer = Visualizer(str(output_dir / 'plots'))
        
        # Training loop
        best_val_loss = float('inf')
        history = {
            'train_loss': [],
            'train_reward_loss': [],
            'train_value_loss': [],
            'val_loss': [],
            'val_reward_loss': [],
            'val_value_loss': []
        }
        
        for epoch in range(config['epochs']):
            # Training phase
            model.train()
            train_loss = 0.0
            train_reward_loss = 0.0
            train_value_loss = 0.0
            
            for states, rewards in train_loader:
                states = states.to(device)
                rewards = rewards.to(device)
                
                # Generate random actions for training
                actions = torch.randn(
                    states.size(0),
                    config['action_dim'],
                    device=device
                )
                
                optimizer.zero_grad()
                pred_rewards, pred_values = model(states, actions)
                
                # Calculate losses
                reward_loss = reward_criterion(pred_rewards, rewards)
                value_loss = value_criterion(pred_values, rewards)
                loss = reward_loss + config['value_loss_weight'] * value_loss
                
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
                train_reward_loss += reward_loss.item()
                train_value_loss += value_loss.item()
            
            train_loss = train_loss / len(train_loader)
            train_reward_loss = train_reward_loss / len(train_loader)
            train_value_loss = train_value_loss / len(train_loader)
            
            # Validation phase
            model.eval()
            val_loss = 0.0
            val_reward_loss = 0.0
            val_value_loss = 0.0
            
            with torch.no_grad():
                for states, rewards in val_loader:
                    states = states.to(device)
                    rewards = rewards.to(device)
                    
                    # Generate random actions for validation
                    actions = torch.randn(
                        states.size(0),
                        config['action_dim'],
                        device=device
                    )
                    
                    pred_rewards, pred_values = model(states, actions)
                    
                    # Calculate losses
                    reward_loss = reward_criterion(pred_rewards, rewards)
                    value_loss = value_criterion(pred_values, rewards)
                    loss = reward_loss + config['value_loss_weight'] * value_loss
                    
                    val_loss += loss.item()
                    val_reward_loss += reward_loss.item()
                    val_value_loss += value_loss.item()
            
            val_loss = val_loss / len(val_loader)
            val_reward_loss = val_reward_loss / len(val_loader)
            val_value_loss = val_value_loss / len(val_loader)
            
            # Update history
            history['train_loss'].append(train_loss)
            history['train_reward_loss'].append(train_reward_loss)
            history['train_value_loss'].append(train_value_loss)
            history['val_loss'].append(val_loss)
            history['val_reward_loss'].append(val_reward_loss)
            history['val_value_loss'].append(val_value_loss)
            
            # Log progress
            logger.info(
                f'Epoch {epoch+1}/{config["epochs"]} - '
                f'Train Loss: {train_loss:.4f} (Reward: {train_reward_loss:.4f}, '
                f'Value: {train_value_loss:.4f}) - '
                f'Val Loss: {val_loss:.4f} (Reward: {val_reward_loss:.4f}, '
                f'Value: {val_value_loss:.4f})'
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
                model_type='motivation',
                metrics=['loss', 'reward_loss', 'value_loss']
            )
        
        # Save final model
        torch.save(
            model.state_dict(),
            output_dir / 'final_model.pt'
        )
        
        # Save training configuration
        config['training_completed'] = datetime.now().isoformat()
        with open(output_dir / 'training_config.yaml', 'w') as f:
            yaml.dump(config, f)
        
        logger.info('Training completed successfully')
        
    except Exception as e:
        logger.error(f'Error training motivation model: {e}')
        raise

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Train motivation model')
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
    
    train_motivation_model(
        config_path=args.config,
        data_dir=args.data_dir,
        output_dir=args.output_dir
    ) 