import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from pathlib import Path
import json
from datetime import datetime

from ..inference_api import ModelInferenceAPI
from ...config.model_config import model_config

logger = logging.getLogger(__name__)

class ModelValidator:
    """Validates model performance and outputs."""
    
    def __init__(self):
        """Initialize the model validator."""
        self.inference_api = ModelInferenceAPI()
        self.validation_results = {}
    
    async def initialize(self):
        """Initialize the inference API."""
        try:
            await self.inference_api.initialize()
            logger.info("Initialized model validator")
        except Exception as e:
            logger.error(f"Error initializing validator: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the inference API."""
        try:
            await self.inference_api.shutdown()
            logger.info("Shutdown model validator")
        except Exception as e:
            logger.error(f"Error shutting down validator: {e}")
            raise
    
    async def validate_model(
        self,
        model_type: str,
        test_data: List[Dict[str, Any]],
        expected_outputs: Optional[List[Any]] = None,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Validate a model's performance.
        
        Args:
            model_type: Type of model to validate
            test_data: List of test inputs
            expected_outputs: Optional list of expected outputs
            metrics: Optional list of metrics to calculate
            
        Returns:
            Validation results including metrics and errors
        """
        try:
            results = {
                "model_type": model_type,
                "timestamp": datetime.now().isoformat(),
                "test_cases": len(test_data),
                "predictions": [],
                "metrics": {},
                "errors": []
            }
            
            # Run inference on test data
            for i, data in enumerate(test_data):
                try:
                    prediction = await self.inference_api.inference(
                        model_type=model_type,
                        data=data
                    )
                    
                    results["predictions"].append({
                        "input": data,
                        "output": prediction
                    })
                    
                    # Compare with expected output if provided
                    if expected_outputs and i < len(expected_outputs):
                        expected = expected_outputs[i]
                        if not self._compare_outputs(prediction, expected):
                            results["errors"].append({
                                "case": i,
                                "expected": expected,
                                "got": prediction
                            })
                    
                except Exception as e:
                    logger.error(f"Error in test case {i}: {e}")
                    results["errors"].append({
                        "case": i,
                        "error": str(e)
                    })
            
            # Calculate metrics if specified
            if metrics:
                results["metrics"] = self._calculate_metrics(
                    results["predictions"],
                    expected_outputs,
                    metrics
                )
            
            # Store results
            self.validation_results[model_type] = results
            
            return results
            
        except Exception as e:
            logger.error(f"Error validating model {model_type}: {e}")
            raise
    
    def _compare_outputs(
        self,
        prediction: Any,
        expected: Any,
        tolerance: float = 1e-6
    ) -> bool:
        """Compare prediction with expected output.
        
        Args:
            prediction: Model prediction
            expected: Expected output
            tolerance: Tolerance for numerical comparisons
            
        Returns:
            Whether outputs match
        """
        try:
            # Handle numpy arrays
            if isinstance(prediction, np.ndarray) and isinstance(expected, np.ndarray):
                return np.allclose(prediction, expected, rtol=tolerance)
            
            # Handle lists
            if isinstance(prediction, list) and isinstance(expected, list):
                if len(prediction) != len(expected):
                    return False
                return all(
                    self._compare_outputs(p, e, tolerance)
                    for p, e in zip(prediction, expected)
                )
            
            # Handle dictionaries
            if isinstance(prediction, dict) and isinstance(expected, dict):
                if prediction.keys() != expected.keys():
                    return False
                return all(
                    self._compare_outputs(prediction[k], expected[k], tolerance)
                    for k in prediction.keys()
                )
            
            # Handle basic types
            return prediction == expected
            
        except Exception as e:
            logger.error(f"Error comparing outputs: {e}")
            return False
    
    def _calculate_metrics(
        self,
        predictions: List[Dict[str, Any]],
        expected_outputs: Optional[List[Any]],
        metrics: List[str]
    ) -> Dict[str, float]:
        """Calculate validation metrics.
        
        Args:
            predictions: List of predictions
            expected_outputs: Optional list of expected outputs
            metrics: List of metrics to calculate
            
        Returns:
            Dictionary of calculated metrics
        """
        results = {}
        
        try:
            # Calculate accuracy if expected outputs provided
            if expected_outputs and "accuracy" in metrics:
                correct = sum(
                    1 for p, e in zip(predictions, expected_outputs)
                    if self._compare_outputs(p["output"], e)
                )
                results["accuracy"] = correct / len(predictions)
            
            # Calculate latency metrics
            if "latency" in metrics:
                latencies = [
                    p.get("latency", 0) for p in predictions
                    if "latency" in p
                ]
                if latencies:
                    results["latency_mean"] = np.mean(latencies)
                    results["latency_std"] = np.std(latencies)
                    results["latency_min"] = np.min(latencies)
                    results["latency_max"] = np.max(latencies)
            
            # Calculate confidence metrics
            if "confidence" in metrics:
                confidences = [
                    p["output"].get("confidence", 0) for p in predictions
                    if isinstance(p["output"], dict) and "confidence" in p["output"]
                ]
                if confidences:
                    results["confidence_mean"] = np.mean(confidences)
                    results["confidence_std"] = np.std(confidences)
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
        
        return results
    
    def get_validation_results(
        self,
        model_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get validation results.
        
        Args:
            model_type: Optional specific model type
            
        Returns:
            Validation results
        """
        if model_type:
            return self.validation_results.get(model_type, {})
        return self.validation_results
    
    def save_validation_results(self, output_path: str):
        """Save validation results to file.
        
        Args:
            output_path: Path to save results
        """
        try:
            with open(output_path, "w") as f:
                json.dump(self.validation_results, f, indent=2)
            logger.info(f"Saved validation results to {output_path}")
        except Exception as e:
            logger.error(f"Error saving validation results: {e}")
            raise
    
    def clear_validation_results(self):
        """Clear stored validation results."""
        self.validation_results = {}
        logger.info("Cleared validation results")
    
    async def validate_all_models(
        self,
        test_data: Dict[str, List[Dict[str, Any]]],
        expected_outputs: Optional[Dict[str, List[Any]]] = None,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Validate all models.
        
        Args:
            test_data: Dictionary of test data for each model type
            expected_outputs: Optional dictionary of expected outputs
            metrics: Optional list of metrics to calculate
            
        Returns:
            Dictionary of validation results for each model
        """
        results = {}
        
        for model_type, data in test_data.items():
            try:
                expected = expected_outputs.get(model_type) if expected_outputs else None
                result = await self.validate_model(
                    model_type=model_type,
                    test_data=data,
                    expected_outputs=expected,
                    metrics=metrics
                )
                results[model_type] = result
            except Exception as e:
                logger.error(f"Failed to validate {model_type}: {e}")
                results[model_type] = {
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        return results 