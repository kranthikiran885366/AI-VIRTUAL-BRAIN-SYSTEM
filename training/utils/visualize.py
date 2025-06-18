import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging
from typing import Dict, List, Any, Optional, Tuple
import torch
from sklearn.metrics import confusion_matrix, roc_curve, auc
import cv2

logger = logging.getLogger(__name__)

class Visualizer:
    """Handles visualization for different model types."""
    
    def __init__(self, output_dir: str):
        """Initialize the visualizer.
        
        Args:
            output_dir: Directory to save visualizations
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set style
        plt.style.use('seaborn')
        sns.set_palette("husl")
    
    def plot_training_history(
        self,
        history: Dict[str, List[float]],
        model_type: str,
        metrics: List[str] = ['loss', 'accuracy']
    ):
        """Plot training history.
        
        Args:
            history: Dictionary of training metrics
            model_type: Type of model
            metrics: List of metrics to plot
        """
        try:
            plt.figure(figsize=(12, 6))
            
            for metric in metrics:
                if metric in history:
                    plt.plot(history[metric], label=f'Training {metric}')
                    if f'val_{metric}' in history:
                        plt.plot(history[f'val_{metric}'], label=f'Validation {metric}')
            
            plt.title(f'{model_type} Training History')
            plt.xlabel('Epoch')
            plt.ylabel('Metric Value')
            plt.legend()
            plt.grid(True)
            
            # Save plot
            plt.savefig(self.output_dir / f'{model_type}_training_history.png')
            plt.close()
            
            logger.info(f"Saved training history plot for {model_type}")
            
        except Exception as e:
            logger.error(f"Error plotting training history: {e}")
            raise
    
    def plot_confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        model_type: str,
        labels: Optional[List[str]] = None
    ):
        """Plot confusion matrix.
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            model_type: Type of model
            labels: Optional list of label names
        """
        try:
            cm = confusion_matrix(y_true, y_pred)
            
            plt.figure(figsize=(10, 8))
            sns.heatmap(
                cm,
                annot=True,
                fmt='d',
                cmap='Blues',
                xticklabels=labels,
                yticklabels=labels
            )
            
            plt.title(f'{model_type} Confusion Matrix')
            plt.xlabel('Predicted')
            plt.ylabel('True')
            
            # Save plot
            plt.savefig(self.output_dir / f'{model_type}_confusion_matrix.png')
            plt.close()
            
            logger.info(f"Saved confusion matrix plot for {model_type}")
            
        except Exception as e:
            logger.error(f"Error plotting confusion matrix: {e}")
            raise
    
    def plot_roc_curves(
        self,
        y_true: np.ndarray,
        y_scores: np.ndarray,
        model_type: str,
        labels: Optional[List[str]] = None
    ):
        """Plot ROC curves.
        
        Args:
            y_true: True labels
            y_scores: Predicted scores
            model_type: Type of model
            labels: Optional list of label names
        """
        try:
            plt.figure(figsize=(10, 8))
            
            # Convert to one-hot encoding if needed
            if len(y_true.shape) == 1:
                y_true = np.eye(len(labels))[y_true]
            
            # Plot ROC curve for each class
            for i in range(len(labels)):
                fpr, tpr, _ = roc_curve(y_true[:, i], y_scores[:, i])
                roc_auc = auc(fpr, tpr)
                
                plt.plot(
                    fpr,
                    tpr,
                    label=f'{labels[i]} (AUC = {roc_auc:.2f})'
                )
            
            plt.plot([0, 1], [0, 1], 'k--')
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.xlabel('False Positive Rate')
            plt.ylabel('True Positive Rate')
            plt.title(f'{model_type} ROC Curves')
            plt.legend(loc="lower right")
            
            # Save plot
            plt.savefig(self.output_dir / f'{model_type}_roc_curves.png')
            plt.close()
            
            logger.info(f"Saved ROC curves plot for {model_type}")
            
        except Exception as e:
            logger.error(f"Error plotting ROC curves: {e}")
            raise
    
    def plot_emotion_samples(
        self,
        images: np.ndarray,
        predictions: np.ndarray,
        true_labels: np.ndarray,
        model_type: str,
        labels: List[str],
        num_samples: int = 10
    ):
        """Plot emotion recognition samples.
        
        Args:
            images: Batch of images
            predictions: Model predictions
            true_labels: True labels
            model_type: Type of model
            labels: List of emotion labels
            num_samples: Number of samples to plot
        """
        try:
            # Select random samples
            indices = np.random.choice(len(images), num_samples, replace=False)
            
            plt.figure(figsize=(15, 5))
            for i, idx in enumerate(indices):
                plt.subplot(2, 5, i+1)
                
                # Plot image
                plt.imshow(images[idx])
                plt.axis('off')
                
                # Add prediction and true label
                pred = labels[predictions[idx]]
                true = labels[true_labels[idx]]
                color = 'green' if pred == true else 'red'
                plt.title(f'Pred: {pred}\nTrue: {true}', color=color)
            
            plt.suptitle(f'{model_type} Emotion Recognition Samples')
            
            # Save plot
            plt.savefig(self.output_dir / f'{model_type}_emotion_samples.png')
            plt.close()
            
            logger.info(f"Saved emotion samples plot for {model_type}")
            
        except Exception as e:
            logger.error(f"Error plotting emotion samples: {e}")
            raise
    
    def plot_face_samples(
        self,
        images: np.ndarray,
        predictions: np.ndarray,
        true_labels: np.ndarray,
        model_type: str,
        labels: List[str],
        num_samples: int = 10
    ):
        """Plot face recognition samples.
        
        Args:
            images: Batch of face images
            predictions: Model predictions
            true_labels: True labels
            model_type: Type of model
            labels: List of person labels
            num_samples: Number of samples to plot
        """
        try:
            # Select random samples
            indices = np.random.choice(len(images), num_samples, replace=False)
            
            plt.figure(figsize=(15, 5))
            for i, idx in enumerate(indices):
                plt.subplot(2, 5, i+1)
                
                # Plot image
                plt.imshow(images[idx])
                plt.axis('off')
                
                # Add prediction and true label
                pred = labels[predictions[idx]]
                true = labels[true_labels[idx]]
                color = 'green' if pred == true else 'red'
                plt.title(f'Pred: {pred}\nTrue: {true}', color=color)
            
            plt.suptitle(f'{model_type} Face Recognition Samples')
            
            # Save plot
            plt.savefig(self.output_dir / f'{model_type}_face_samples.png')
            plt.close()
            
            logger.info(f"Saved face samples plot for {model_type}")
            
        except Exception as e:
            logger.error(f"Error plotting face samples: {e}")
            raise
    
    def plot_language_attention(
        self,
        text: str,
        attention_weights: np.ndarray,
        model_type: str,
        tokenizer: Any
    ):
        """Plot language model attention weights.
        
        Args:
            text: Input text
            attention_weights: Attention weights
            model_type: Type of model
            tokenizer: Tokenizer object
        """
        try:
            # Tokenize text
            tokens = tokenizer.tokenize(text)
            
            plt.figure(figsize=(12, 8))
            sns.heatmap(
                attention_weights,
                xticklabels=tokens,
                yticklabels=tokens,
                cmap='YlOrRd'
            )
            
            plt.title(f'{model_type} Attention Weights')
            plt.xlabel('Target Token')
            plt.ylabel('Source Token')
            
            # Save plot
            plt.savefig(self.output_dir / f'{model_type}_attention.png')
            plt.close()
            
            logger.info(f"Saved attention weights plot for {model_type}")
            
        except Exception as e:
            logger.error(f"Error plotting attention weights: {e}")
            raise
    
    def plot_planning_trajectory(
        self,
        states: np.ndarray,
        actions: np.ndarray,
        rewards: np.ndarray,
        model_type: str
    ):
        """Plot planning model trajectory.
        
        Args:
            states: State sequence
            actions: Action sequence
            rewards: Reward sequence
            model_type: Type of model
        """
        try:
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12))
            
            # Plot states
            ax1.plot(states)
            ax1.set_title('State Trajectory')
            ax1.set_xlabel('Time Step')
            ax1.set_ylabel('State')
            
            # Plot actions
            ax2.plot(actions)
            ax2.set_title('Action Sequence')
            ax2.set_xlabel('Time Step')
            ax2.set_ylabel('Action')
            
            # Plot rewards
            ax3.plot(rewards)
            ax3.set_title('Reward Sequence')
            ax3.set_xlabel('Time Step')
            ax3.set_ylabel('Reward')
            
            plt.suptitle(f'{model_type} Planning Trajectory')
            plt.tight_layout()
            
            # Save plot
            plt.savefig(self.output_dir / f'{model_type}_trajectory.png')
            plt.close()
            
            logger.info(f"Saved planning trajectory plot for {model_type}")
            
        except Exception as e:
            logger.error(f"Error plotting planning trajectory: {e}")
            raise
    
    def plot_motivation_rewards(
        self,
        rewards: np.ndarray,
        model_type: str,
        window_size: int = 100
    ):
        """Plot motivation model rewards.
        
        Args:
            rewards: Reward sequence
            model_type: Type of model
            window_size: Size of moving average window
        """
        try:
            plt.figure(figsize=(12, 6))
            
            # Plot raw rewards
            plt.plot(rewards, alpha=0.3, label='Raw Rewards')
            
            # Plot moving average
            if len(rewards) >= window_size:
                moving_avg = pd.Series(rewards).rolling(window=window_size).mean()
                plt.plot(moving_avg, label=f'{window_size}-step Moving Average')
            
            plt.title(f'{model_type} Reward Sequence')
            plt.xlabel('Time Step')
            plt.ylabel('Reward')
            plt.legend()
            plt.grid(True)
            
            # Save plot
            plt.savefig(self.output_dir / f'{model_type}_rewards.png')
            plt.close()
            
            logger.info(f"Saved motivation rewards plot for {model_type}")
            
        except Exception as e:
            logger.error(f"Error plotting motivation rewards: {e}")
            raise 