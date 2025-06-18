import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import shutil
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

class ModelDeployment:
    """Manages model versions and deployments."""
    
    def __init__(self, models_dir: str, deployment_dir: str):
        """Initialize the model deployment manager.
        
        Args:
            models_dir: Directory containing model versions
            deployment_dir: Directory for deployment configurations
        """
        self.models_dir = Path(models_dir)
        self.deployment_dir = Path(deployment_dir)
        
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.deployment_dir.mkdir(parents=True, exist_ok=True)
        
        self.deployments = {}
        self._load_deployments()
    
    def _load_deployments(self):
        """Load existing deployment configurations."""
        try:
            deployment_file = self.deployment_dir / "deployments.json"
            if deployment_file.exists():
                with open(deployment_file, "r") as f:
                    self.deployments = json.load(f)
        except Exception as e:
            logger.error(f"Error loading deployments: {e}")
            self.deployments = {}
    
    def _save_deployments(self):
        """Save deployment configurations."""
        try:
            deployment_file = self.deployment_dir / "deployments.json"
            with open(deployment_file, "w") as f:
                json.dump(self.deployments, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving deployments: {e}")
    
    def register_model_version(
        self,
        model_type: str,
        version: str,
        metadata: Dict[str, Any]
    ):
        """Register a new model version.
        
        Args:
            model_type: Type of model
            version: Version identifier
            metadata: Model metadata
        """
        try:
            # Create version directory
            version_dir = self.models_dir / model_type / version
            version_dir.mkdir(parents=True, exist_ok=True)
            
            # Save metadata
            metadata_file = version_dir / "metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Registered model version {version} for {model_type}")
            
        except Exception as e:
            logger.error(f"Error registering model version: {e}")
            raise
    
    def deploy_model(
        self,
        model_type: str,
        version: str,
        config: Dict[str, Any]
    ):
        """Deploy a model version.
        
        Args:
            model_type: Type of model
            version: Version to deploy
            config: Deployment configuration
        """
        try:
            # Verify model version exists
            version_dir = self.models_dir / model_type / version
            if not version_dir.exists():
                raise ValueError(f"Model version {version} not found")
            
            # Create deployment configuration
            deployment = {
                "model_type": model_type,
                "version": version,
                "config": config,
                "deployed_at": datetime.now().isoformat(),
                "status": "active"
            }
            
            # Save deployment config
            deployment_file = self.deployment_dir / f"{model_type}_deployment.yaml"
            with open(deployment_file, "w") as f:
                yaml.dump(deployment, f)
            
            # Update deployments
            self.deployments[model_type] = deployment
            self._save_deployments()
            
            logger.info(f"Deployed model version {version} for {model_type}")
            
        except Exception as e:
            logger.error(f"Error deploying model: {e}")
            raise
    
    def undeploy_model(self, model_type: str):
        """Undeploy a model.
        
        Args:
            model_type: Type of model to undeploy
        """
        try:
            if model_type not in self.deployments:
                logger.warning(f"No deployment found for {model_type}")
                return
            
            # Update deployment status
            self.deployments[model_type]["status"] = "inactive"
            self.deployments[model_type]["undeployed_at"] = datetime.now().isoformat()
            
            # Remove deployment config
            deployment_file = self.deployment_dir / f"{model_type}_deployment.yaml"
            if deployment_file.exists():
                deployment_file.unlink()
            
            self._save_deployments()
            logger.info(f"Undeployed model {model_type}")
            
        except Exception as e:
            logger.error(f"Error undeploying model: {e}")
            raise
    
    def get_deployment(self, model_type: str) -> Optional[Dict]:
        """Get deployment information for a model.
        
        Args:
            model_type: Type of model
            
        Returns:
            Deployment information if available
        """
        return self.deployments.get(model_type)
    
    def list_deployments(self) -> Dict[str, Dict]:
        """List all deployments.
        
        Returns:
            Dictionary of all deployments
        """
        return self.deployments.copy()
    
    def list_model_versions(
        self,
        model_type: str
    ) -> List[Dict[str, Any]]:
        """List all versions of a model.
        
        Args:
            model_type: Type of model
            
        Returns:
            List of model versions with metadata
        """
        try:
            model_dir = self.models_dir / model_type
            if not model_dir.exists():
                return []
            
            versions = []
            for version_dir in model_dir.iterdir():
                if not version_dir.is_dir():
                    continue
                
                metadata_file = version_dir / "metadata.json"
                if not metadata_file.exists():
                    continue
                
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                
                versions.append({
                    "version": version_dir.name,
                    "metadata": metadata
                })
            
            return sorted(versions, key=lambda x: x["version"])
            
        except Exception as e:
            logger.error(f"Error listing model versions: {e}")
            return []
    
    def delete_model_version(
        self,
        model_type: str,
        version: str
    ):
        """Delete a model version.
        
        Args:
            model_type: Type of model
            version: Version to delete
        """
        try:
            version_dir = self.models_dir / model_type / version
            if not version_dir.exists():
                logger.warning(f"Model version {version} not found")
                return
            
            # Check if version is currently deployed
            deployment = self.get_deployment(model_type)
            if deployment and deployment["version"] == version:
                raise ValueError("Cannot delete currently deployed version")
            
            # Delete version directory
            shutil.rmtree(version_dir)
            logger.info(f"Deleted model version {version} for {model_type}")
            
        except Exception as e:
            logger.error(f"Error deleting model version: {e}")
            raise
    
    def update_deployment_config(
        self,
        model_type: str,
        config: Dict[str, Any]
    ):
        """Update deployment configuration.
        
        Args:
            model_type: Type of model
            config: New deployment configuration
        """
        try:
            if model_type not in self.deployments:
                raise ValueError(f"No deployment found for {model_type}")
            
            # Update config
            self.deployments[model_type]["config"].update(config)
            self.deployments[model_type]["updated_at"] = datetime.now().isoformat()
            
            # Save updated config
            deployment_file = self.deployment_dir / f"{model_type}_deployment.yaml"
            with open(deployment_file, "w") as f:
                yaml.dump(self.deployments[model_type], f)
            
            self._save_deployments()
            logger.info(f"Updated deployment config for {model_type}")
            
        except Exception as e:
            logger.error(f"Error updating deployment config: {e}")
            raise 