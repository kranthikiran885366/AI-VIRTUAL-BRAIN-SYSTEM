import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import json
from datetime import datetime

from ..inference_api import ModelInferenceAPI
from ...config.model_config import model_config

logger = logging.getLogger(__name__)

class ServingOrchestrator:
    """Orchestrates the model serving process."""
    
    def __init__(self):
        """Initialize the serving orchestrator."""
        self.inference_api = ModelInferenceAPI()
        self.serving_status = {}
        self.serving_history = {}
    
    async def initialize_services(self):
        """Initialize all model services."""
        try:
            await self.inference_api.initialize()
            
            # Initialize serving status
            for model_type in model_config.model_paths.keys():
                self.serving_status[model_type] = {
                    "status": "initialized",
                    "start_time": datetime.now().isoformat(),
                    "config": model_config.get_model_config(model_type)
                }
            
            logger.info("All model services initialized")
            
        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            raise
    
    async def shutdown_services(self):
        """Shutdown all model services."""
        try:
            await self.inference_api.shutdown()
            
            # Update serving status
            for model_type in self.serving_status:
                self.serving_status[model_type].update({
                    "status": "shutdown",
                    "end_time": datetime.now().isoformat()
                })
            
            logger.info("All model services shut down")
            
        except Exception as e:
            logger.error(f"Error shutting down services: {e}")
            raise
    
    async def run_inference(
        self,
        model_type: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run inference with a specific model.
        
        Args:
            model_type: Type of model to use
            data: Input data for inference
            options: Optional inference options
            
        Returns:
            Inference results
        """
        try:
            # Record inference request
            request_id = str(datetime.now().timestamp())
            self.serving_history[request_id] = {
                "model_type": model_type,
                "timestamp": datetime.now().isoformat(),
                "data": data,
                "options": options
            }
            
            # Run inference
            result = await self.inference_api.inference(
                model_type=model_type,
                data=data,
                options=options
            )
            
            # Update history
            self.serving_history[request_id].update({
                "status": "completed",
                "result": result
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error during inference: {e}")
            if request_id in self.serving_history:
                self.serving_history[request_id].update({
                    "status": "failed",
                    "error": str(e)
                })
            raise
    
    def get_service_health(self, model_type: Optional[str] = None) -> Dict:
        """Get health status of service(s).
        
        Args:
            model_type: Optional specific model type
            
        Returns:
            Health status information
        """
        if model_type:
            return self.serving_status.get(model_type, {})
        return self.serving_status
    
    def get_inference_history(
        self,
        model_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Dict]:
        """Get inference history.
        
        Args:
            model_type: Optional filter by model type
            limit: Optional limit on number of records
            
        Returns:
            Inference history information
        """
        history = self.serving_history.copy()
        
        # Filter by model type
        if model_type:
            history = {
                k: v for k, v in history.items()
                if v["model_type"] == model_type
            }
        
        # Sort by timestamp
        history = dict(sorted(
            history.items(),
            key=lambda x: x[1]["timestamp"],
            reverse=True
        ))
        
        # Apply limit
        if limit:
            history = dict(list(history.items())[:limit])
        
        return history
    
    def save_serving_summary(self, output_path: str):
        """Save serving summary to file.
        
        Args:
            output_path: Path to save summary
        """
        summary = {
            "timestamp": datetime.now().isoformat(),
            "status": self.serving_status,
            "history": self.serving_history
        }
        
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Saved serving summary to {output_path}")
    
    def clear_inference_history(self):
        """Clear inference history."""
        self.serving_history = {}
        logger.info("Cleared inference history")
    
    async def reload_model(
        self,
        model_type: str,
        version: Optional[str] = None
    ):
        """Reload a specific model.
        
        Args:
            model_type: Type of model to reload
            version: Optional specific version to load
        """
        try:
            # Get service
            service = self.inference_api._get_service(model_type)
            if not service:
                raise ValueError(f"Unknown model type: {model_type}")
            
            # Shutdown service
            await service.shutdown()
            
            # Reinitialize service
            await service.initialize()
            
            # Update status
            self.serving_status[model_type].update({
                "status": "reloaded",
                "version": version,
                "reload_time": datetime.now().isoformat()
            })
            
            logger.info(f"Reloaded model {model_type}")
            
        except Exception as e:
            logger.error(f"Error reloading model {model_type}: {e}")
            raise 