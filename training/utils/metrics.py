import numpy as np
from typing import Dict, List, Any
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_curve,
    auc,
    precision_recall_curve
)
import matplotlib.pyplot as plt
import seaborn as sns

def calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray] = None
) -> Dict[str, float]:
    """Calculate various classification metrics."""
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, average="weighted"),
        "recall": recall_score(y_true, y_pred, average="weighted"),
        "f1": f1_score(y_true, y_pred, average="weighted")
    }
    
    # Add ROC AUC if probabilities are provided
    if y_prob is not None:
        metrics["roc_auc"] = calculate_roc_auc(y_true, y_prob)
    
    return metrics

def calculate_roc_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculate ROC AUC score."""
    # Convert to one-hot encoding if needed
    if len(y_prob.shape) == 1:
        y_prob = np.vstack([1 - y_prob, y_prob]).T
    
    # Calculate ROC curve and AUC for each class
    n_classes = y_prob.shape[1]
    auc_scores = []
    
    for i in range(n_classes):
        fpr, tpr, _ = roc_curve(y_true == i, y_prob[:, i])
        auc_scores.append(auc(fpr, tpr))
    
    # Return mean AUC
    return np.mean(auc_scores)

def plot_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    labels: List[str],
    title: str = "Confusion Matrix",
    save_path: Optional[str] = None
):
    """Plot confusion matrix."""
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels
    )
    plt.title(title)
    plt.xlabel("Predicted")
    plt.ylabel("True")
    
    if save_path:
        plt.savefig(save_path)
    plt.close()

def plot_roc_curves(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    labels: List[str],
    title: str = "ROC Curves",
    save_path: Optional[str] = None
):
    """Plot ROC curves for each class."""
    plt.figure(figsize=(10, 8))
    
    # Convert to one-hot encoding if needed
    if len(y_prob.shape) == 1:
        y_prob = np.vstack([1 - y_prob, y_prob]).T
    
    # Plot ROC curve for each class
    for i, label in enumerate(labels):
        fpr, tpr, _ = roc_curve(y_true == i, y_prob[:, i])
        roc_auc = auc(fpr, tpr)
        plt.plot(
            fpr,
            tpr,
            label=f"{label} (AUC = {roc_auc:.2f})"
        )
    
    plt.plot([0, 1], [0, 1], "k--")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title(title)
    plt.legend(loc="lower right")
    
    if save_path:
        plt.savefig(save_path)
    plt.close()

def plot_precision_recall_curves(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    labels: List[str],
    title: str = "Precision-Recall Curves",
    save_path: Optional[str] = None
):
    """Plot precision-recall curves for each class."""
    plt.figure(figsize=(10, 8))
    
    # Convert to one-hot encoding if needed
    if len(y_prob.shape) == 1:
        y_prob = np.vstack([1 - y_prob, y_prob]).T
    
    # Plot PR curve for each class
    for i, label in enumerate(labels):
        precision, recall, _ = precision_recall_curve(y_true == i, y_prob[:, i])
        plt.plot(
            recall,
            precision,
            label=label
        )
    
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title(title)
    plt.legend(loc="lower left")
    
    if save_path:
        plt.savefig(save_path)
    plt.close()

def plot_training_history(
    history: Dict[str, List[float]],
    title: str = "Training History",
    save_path: Optional[str] = None
):
    """Plot training history metrics."""
    plt.figure(figsize=(12, 4))
    
    # Plot training metrics
    plt.subplot(1, 2, 1)
    for metric in ["loss", "accuracy"]:
        if metric in history:
            plt.plot(history[metric], label=f"Training {metric}")
            if f"val_{metric}" in history:
                plt.plot(history[f"val_{metric}"], label=f"Validation {metric}")
    plt.title("Training Metrics")
    plt.xlabel("Epoch")
    plt.ylabel("Value")
    plt.legend()
    
    # Plot learning rate if available
    if "lr" in history:
        plt.subplot(1, 2, 2)
        plt.plot(history["lr"])
        plt.title("Learning Rate")
        plt.xlabel("Epoch")
        plt.ylabel("Learning Rate")
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path)
    plt.close()

def save_metrics(
    metrics: Dict[str, float],
    save_path: str
):
    """Save metrics to file."""
    import json
    
    with open(save_path, "w") as f:
        json.dump(metrics, f, indent=2) 