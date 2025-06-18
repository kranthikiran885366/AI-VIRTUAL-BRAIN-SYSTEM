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

class PlanningModel(nn.Module):
    """Planning model architecture."""
    
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int):
        """Initialize the model.
        
        Args:
            input_dim: Input dimension
            hidden_dim: Hidden dimension
            output_dim: Output dimension
        """
        super().__init__()
        
        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2)
        )
        
        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, output_dim)
        )
        
        # State transition network
        self.transition = nn.Sequential(
            nn.Linear(hidden_dim + output_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim)
        )
    
    def forward(
        self,
        state: torch.Tensor,
        goal: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass.
        
        Args:
            state: Current state
            goal: Goal state
            
        Returns:
            Tuple of (action, next_state)
        """
        # Encode state and goal
        state_encoded = self.encoder(state)
        goal_encoded = self.encoder(goal)
        
        # Generate action
        action = self.decoder(state_encoded)
        
        # Predict next state
        next_state = self.transition(
            torch.cat([state_encoded, action], dim=1)
        )
        
        return action, next_state

def train_planning_model(
    config_path: str,
    data_dir: str,
    output_dir: str,
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
):
    """Train planning model.
    
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
        splitter.split_planning_data(
            data_path=data_dir,
            output_path=str(output_dir / 'splits'),
            test_size=config['test_size'],
            val_size=config['val_size']
        )
        
        # Preprocess data
        train_states, train_goals = preprocessor.preprocess_planning_data(
            data_path=str(output_dir / 'splits'),
            split='train'
        )
        val_states, val_goals = preprocessor.preprocess_planning_data(
            data_path=str(output_dir / 'splits'),
            split='val'
        )
        
        # Create data loaders
        train_dataset = torch.utils.data.TensorDataset(
            torch.FloatTensor(train_states),
            torch.FloatTensor(train_goals)
        )
        val_dataset = torch.utils.data.TensorDataset(
            torch.FloatTensor(val_states),
            torch.FloatTensor(val_goals)
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
        model = PlanningModel(
            input_dim=config['state_dim'],
            hidden_dim=config['hidden_dim'],
            output_dim=config['action_dim']
        )
        model = model.to(device)
        
        # Initialize optimizer and loss functions
        optimizer = optim.Adam(
            model.parameters(),
            lr=config['learning_rate']
        )
        action_criterion = nn.MSELoss()
        state_criterion = nn.MSELoss()
        
        # Initialize visualizer
        visualizer = Visualizer(str(output_dir / 'plots'))
        
        # Training loop
        best_val_loss = float('inf')
        history = {
            'train_loss': [],
            'train_action_loss': [],
            'train_state_loss': [],
            'val_loss': [],
            'val_action_loss': [],
            'val_state_loss': []
        }
        
        for epoch in range(config['epochs']):
            # Training phase
            model.train()
            train_loss = 0.0
            train_action_loss = 0.0
            train_state_loss = 0.0
            
            for states, goals in train_loader:
                states = states.to(device)
                goals = goals.to(device)
                
                optimizer.zero_grad()
                actions, next_states = model(states, goals)
                
                # Calculate losses
                action_loss = action_criterion(actions, goals)
                state_loss = state_criterion(next_states, goals)
                loss = action_loss + config['state_loss_weight'] * state_loss
                
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
                train_action_loss += action_loss.item()
                train_state_loss += state_loss.item()
            
            train_loss = train_loss / len(train_loader)
            train_action_loss = train_action_loss / len(train_loader)
            train_state_loss = train_state_loss / len(train_loader)
            
            # Validation phase
            model.eval()
            val_loss = 0.0
            val_action_loss = 0.0
            val_state_loss = 0.0
            
            with torch.no_grad():
                for states, goals in val_loader:
                    states = states.to(device)
                    goals = goals.to(device)
                    
                    actions, next_states = model(states, goals)
                    
                    # Calculate losses
                    action_loss = action_criterion(actions, goals)
                    state_loss = state_criterion(next_states, goals)
                    loss = action_loss + config['state_loss_weight'] * state_loss
                    
                    val_loss += loss.item()
                    val_action_loss += action_loss.item()
                    val_state_loss += state_loss.item()
            
            val_loss = val_loss / len(val_loader)
            val_action_loss = val_action_loss / len(val_loader)
            val_state_loss = val_state_loss / len(val_loader)
            
            # Update history
            history['train_loss'].append(train_loss)
            history['train_action_loss'].append(train_action_loss)
            history['train_state_loss'].append(train_state_loss)
            history['val_loss'].append(val_loss)
            history['val_action_loss'].append(val_action_loss)
            history['val_state_loss'].append(val_state_loss)
            
            # Log progress
            logger.info(
                f'Epoch {epoch+1}/{config["epochs"]} - '
                f'Train Loss: {train_loss:.4f} (Action: {train_action_loss:.4f}, '
                f'State: {train_state_loss:.4f}) - '
                f'Val Loss: {val_loss:.4f} (Action: {val_action_loss:.4f}, '
                f'State: {val_state_loss:.4f})'
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
                model_type='planning',
                metrics=['loss', 'action_loss', 'state_loss']
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
        logger.error(f'Error training planning model: {e}')
        raise

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Train planning model')
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
    
    train_planning_model(
        config_path=args.config,
        data_dir=args.data_dir,
        output_dir=args.output_dir
    ) 