import logging
import asyncio
import os
from pathlib import Path
from tqdm import tqdm
import torch
import yaml
from download_models_and_datasets import DatasetDownloader

# Import training services
from agents.creativity_agent.training_service import CreativityTrainingService
from agents.emotion_agent.training_service import EmotionTrainingService
from agents.eyes_agent.training_service import EyesTrainingService
from agents.memory_agent.training_service import MemoryTrainingService
from agents.mouth_agent.training_service import MouthTrainingService
from agents.perception_agent.training_service import PerceptionTrainingService
from agents.social_agent.training_service import SocialTrainingService
from agents.task_agent.training_service import TaskTrainingService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AgentTrainer:
    def __init__(self):
        self.base_dir = Path("data")
        self.config_dir = Path("config")
        self.downloader = DatasetDownloader()
        
        # Initialize training services
        self.training_services = {
            "creativity_agent": CreativityTrainingService(),
            "emotion_agent": EmotionTrainingService(),
            "eyes_agent": EyesTrainingService(),
            "memory_agent": MemoryTrainingService(),
            "mouth_agent": MouthTrainingService(),
            "perception_agent": PerceptionTrainingService(),
            "social_agent": SocialTrainingService(),
            "task_agent": TaskTrainingService()
        }
    
    async def download_resources(self):
        """Download all datasets and models"""
        logger.info("Starting download of all resources...")
        await self.downloader.download_all_resources()
        logger.info("All resources downloaded successfully")
    
    def train_agent(self, agent_name: str):
        """Train a specific agent"""
        try:
            logger.info(f"Starting training for {agent_name}")
            service = self.training_services.get(agent_name)
            if not service:
                raise ValueError(f"No training service found for {agent_name}")
            
            # Get the first dataset and model for training
            agent_resources = self.downloader.agent_resources[agent_name]
            dataset_name = list(agent_resources["datasets"].keys())[0]
            model_name = list(agent_resources["models"].keys())[0]
            
            # Prepare dataset
            dataset = service.prepare_dataset(dataset_name)
            if not dataset:
                raise ValueError(f"Failed to prepare dataset {dataset_name}")
            
            # Create model
            model = service.create_model({})
            if not model:
                raise ValueError(f"Failed to create model {model_name}")
            
            # Train model
            service.model = model
            results = service.train(dataset)
            
            logger.info(f"Training completed for {agent_name}")
            logger.info(f"Training results: {results}")
            
            return results
        
        except Exception as e:
            logger.error(f"Error training {agent_name}: {e}")
            return None
    
    def train_all_agents(self):
        """Train all agents sequentially"""
        results = {}
        for agent_name in self.training_services.keys():
            logger.info(f"\n{'='*50}")
            logger.info(f"Training {agent_name}")
            logger.info(f"{'='*50}\n")
            
            result = self.train_agent(agent_name)
            results[agent_name] = result
            
            # Cleanup after each agent
            self.training_services[agent_name].cleanup()
        
        return results

async def main():
    # Create trainer
    trainer = AgentTrainer()
    
    try:
        # Download all resources
        await trainer.download_resources()
        
        # Train all agents
        results = trainer.train_all_agents()
        
        # Print final results
        logger.info("\nTraining Results Summary:")
        logger.info("="*50)
        for agent_name, result in results.items():
            logger.info(f"\n{agent_name}:")
            if result:
                logger.info(f"Success: {result}")
            else:
                logger.info("Failed")
    
    except Exception as e:
        logger.error(f"Error in main process: {e}")
    
    finally:
        # Cleanup
        for service in trainer.training_services.values():
            service.cleanup()

if __name__ == "__main__":
    asyncio.run(main())