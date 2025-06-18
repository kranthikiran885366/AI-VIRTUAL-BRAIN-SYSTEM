import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from sklearn.model_selection import (
    KFold,
    StratifiedKFold,
    cross_val_score,
    cross_validate
)
from sklearn.metrics import make_scorer, accuracy_score, precision_score, recall_score, f1_score
import logging

logger = logging.getLogger(__name__)

class ModelValidator:
    """Class for model validation and cross-validation."""
    
    def __init__(
        self,
        model: Any,
        n_splits: int = 5,
        random_state: Optional[int] = None,
        metrics: Optional[List[str]] = None
    ):
        """Initialize the validator.
        
        Args:
            model: The model to validate
            n_splits: Number of folds for cross-validation
            random_state: Random seed for reproducibility
            metrics: List of metrics to calculate
        """
        self.model = model
        self.n_splits = n_splits
        self.random_state = random_state
        self.metrics = metrics or ["accuracy", "precision", "recall", "f1"]
        
        # Initialize scorers
        self.scorers = {
            "accuracy": make_scorer(accuracy_score),
            "precision": make_scorer(precision_score, average="weighted"),
            "recall": make_scorer(recall_score, average="weighted"),
            "f1": make_scorer(f1_score, average="weighted")
        }
    
    def cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        stratified: bool = True
    ) -> Dict[str, Dict[str, float]]:
        """Perform cross-validation.
        
        Args:
            X: Feature matrix
            y: Target vector
            stratified: Whether to use stratified k-fold
            
        Returns:
            Dictionary of metrics with mean and std scores
        """
        # Select appropriate cross-validator
        if stratified:
            cv = StratifiedKFold(
                n_splits=self.n_splits,
                shuffle=True,
                random_state=self.random_state
            )
        else:
            cv = KFold(
                n_splits=self.n_splits,
                shuffle=True,
                random_state=self.random_state
            )
        
        # Perform cross-validation
        results = cross_validate(
            self.model,
            X,
            y,
            cv=cv,
            scoring=self.scorers,
            return_train_score=True
        )
        
        # Process results
        metrics_summary = {}
        for metric in self.metrics:
            train_scores = results[f"train_{metric}"]
            test_scores = results[f"test_{metric}"]
            
            metrics_summary[metric] = {
                "train_mean": np.mean(train_scores),
                "train_std": np.std(train_scores),
                "test_mean": np.mean(test_scores),
                "test_std": np.std(test_scores)
            }
        
        return metrics_summary
    
    def validate_split(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> Dict[str, float]:
        """Validate model on a single train-validation split.
        
        Args:
            X_train: Training features
            y_train: Training targets
            X_val: Validation features
            y_val: Validation targets
            
        Returns:
            Dictionary of validation metrics
        """
        # Train model
        self.model.fit(X_train, y_train)
        
        # Make predictions
        y_pred = self.model.predict(X_val)
        
        # Calculate metrics
        metrics = {}
        for metric in self.metrics:
            scorer = self.scorers[metric]
            metrics[metric] = scorer(self.model, X_val, y_val)
        
        return metrics
    
    def learning_curve(
        self,
        X: np.ndarray,
        y: np.ndarray,
        train_sizes: List[float] = None
    ) -> Dict[str, List[float]]:
        """Calculate learning curve.
        
        Args:
            X: Feature matrix
            y: Target vector
            train_sizes: List of training set sizes to evaluate
            
        Returns:
            Dictionary of training and validation scores
        """
        if train_sizes is None:
            train_sizes = np.linspace(0.1, 1.0, 10)
        
        train_scores = []
        val_scores = []
        
        for size in train_sizes:
            # Calculate split size
            n_samples = int(len(X) * size)
            
            # Split data
            indices = np.random.permutation(len(X))
            train_indices = indices[:n_samples]
            val_indices = indices[n_samples:]
            
            X_train, y_train = X[train_indices], y[train_indices]
            X_val, y_val = X[val_indices], y[val_indices]
            
            # Train and evaluate
            self.model.fit(X_train, y_train)
            train_score = self.model.score(X_train, y_train)
            val_score = self.model.score(X_val, y_val)
            
            train_scores.append(train_score)
            val_scores.append(val_score)
        
        return {
            "train_sizes": train_sizes,
            "train_scores": train_scores,
            "val_scores": val_scores
        }
    
    def hyperparameter_tuning(
        self,
        X: np.ndarray,
        y: np.ndarray,
        param_grid: Dict[str, List[Any]],
        metric: str = "accuracy"
    ) -> Tuple[Dict[str, Any], float]:
        """Perform hyperparameter tuning using grid search.
        
        Args:
            X: Feature matrix
            y: Target vector
            param_grid: Dictionary of parameter names and values to try
            metric: Metric to optimize
            
        Returns:
            Tuple of best parameters and best score
        """
        from sklearn.model_selection import GridSearchCV
        
        # Initialize grid search
        grid_search = GridSearchCV(
            self.model,
            param_grid,
            cv=self.n_splits,
            scoring=self.scorers[metric],
            n_jobs=-1
        )
        
        # Perform grid search
        grid_search.fit(X, y)
        
        return grid_search.best_params_, grid_search.best_score_ 