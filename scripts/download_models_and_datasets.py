import logging
import asyncio
import aiohttp
import os
from pathlib import Path
from tqdm import tqdm
import torch
from transformers import AutoTokenizer, AutoModel, AutoConfig
from datasets import load_dataset
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatasetDownloader:
    def __init__(self):
        self.base_dir = Path("data")
        self.models_dir = self.base_dir / "models"
        self.datasets_dir = self.base_dir / "datasets"
        
        # Create directories
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        
        # Define datasets and models for each agent
        self.agent_resources = {
            "creativity_agent": {
                "datasets": {
                    "creative_writing": "creative_writing_dataset",
                    "poetry": "poetry_dataset",
                    "story_generation": "story_generation_dataset"
                },
                "models": {
                    "gpt2": "gpt2",
                    "gpt2-medium": "gpt2-medium",
                    "gpt2-large": "gpt2-large"
                }
            },
            "emotion_agent": {
                "datasets": {
                    "emotion": "emotion",
                    "goemotions": "goemotions",
                    "isear": "isear"
                },
                "models": {
                    "emotion-english-distilroberta-base": "emotion-english-distilroberta-base",
                    "emotion-english-roberta-large": "emotion-english-roberta-large"
                }
            },
            "eyes_agent": {
                "datasets": {
                    "coco": "coco",
                    "voc": "voc",
                    "openimages": "openimages"
                },
                "models": {
                    "faster-rcnn": "faster-rcnn",
                    "mask-rcnn": "mask-rcnn",
                    "yolo": "yolo"
                }
            },
            "memory_agent": {
                "datasets": {
                    "memory_qa": "memory_qa_dataset",
                    "episodic_memory": "episodic_memory_dataset",
                    "semantic_memory": "semantic_memory_dataset"
                },
                "models": {
                    "memory-bert-base": "memory-bert-base",
                    "memory-roberta-base": "memory-roberta-base"
                }
            },
            "mouth_agent": {
                "datasets": {
                    "libritts": "libritts",
                    "vctk": "vctk",
                    "ljspeech": "ljspeech"
                },
                "models": {
                    "speecht5_tts": "microsoft/speecht5_tts",
                    "fastspeech2": "espnet/fastspeech2_ljspeech"
                }
            },
            "perception_agent": {
                "datasets": {
                    "coco_captions": "coco_captions",
                    "visual_genome": "visual_genome",
                    "flickr30k": "flickr30k"
                },
                "models": {
                    "perception-vilt": "dandelin/vilt-b32-mlm",
                    "perception-clip": "openai/clip-vit-base-patch32"
                }
            },
            "social_agent": {
                "datasets": {
                    "social_qa": "social_qa_dataset",
                    "empathy": "empathy_dataset",
                    "personality": "personality_dataset"
                },
                "models": {
                    "social-bert": "social-bert-base",
                    "social-roberta": "social-roberta-base"
                }
            },
            "task_agent": {
                "datasets": {
                    "task_qa": "task_qa_dataset",
                    "planning": "planning_dataset",
                    "reasoning": "reasoning_dataset"
                },
                "models": {
                    "task-bert": "task-bert-base",
                    "task-roberta": "task-roberta-base"
                }
            }
        }
    
    async def download_dataset(self, dataset_name: str, dataset_id: str, agent_name: str):
        """Download a dataset using Hugging Face datasets"""
        try:
            logger.info(f"Downloading dataset {dataset_name} for {agent_name}")
            dataset = load_dataset(dataset_id)
            
            # Save dataset to disk
            save_path = self.datasets_dir / agent_name / dataset_name
            save_path.mkdir(parents=True, exist_ok=True)
            dataset.save_to_disk(str(save_path))
            
            logger.info(f"Successfully downloaded dataset {dataset_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error downloading dataset {dataset_name}: {e}")
            return False
    
    async def download_model(self, model_name: str, model_id: str, agent_name: str):
        """Download a model using Hugging Face transformers"""
        try:
            logger.info(f"Downloading model {model_name} for {agent_name}")
            
            # Create model directory
            model_path = self.models_dir / agent_name / model_name
            model_path.mkdir(parents=True, exist_ok=True)
            
            # Download tokenizer
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            tokenizer.save_pretrained(model_path)
            
            # Download model
            model = AutoModel.from_pretrained(model_id)
            model.save_pretrained(model_path)
            
            # Save config
            config = AutoConfig.from_pretrained(model_id)
            config.save_pretrained(model_path)
            
            logger.info(f"Successfully downloaded model {model_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error downloading model {model_name}: {e}")
            return False
    
    async def download_agent_resources(self, agent_name: str):
        """Download all resources for a specific agent"""
        agent_resources = self.agent_resources.get(agent_name)
        if not agent_resources:
            logger.error(f"No resources defined for agent {agent_name}")
            return
        
        # Download datasets
        dataset_tasks = []
        for dataset_name, dataset_id in agent_resources["datasets"].items():
            task = self.download_dataset(dataset_name, dataset_id, agent_name)
            dataset_tasks.append(task)
        
        # Download models
        model_tasks = []
        for model_name, model_id in agent_resources["models"].items():
            task = self.download_model(model_name, model_id, agent_name)
            model_tasks.append(task)
        
        # Wait for all downloads to complete
        await asyncio.gather(*dataset_tasks, *model_tasks)
    
    async def download_all_resources(self):
        """Download resources for all agents"""
        tasks = []
        for agent_name in self.agent_resources.keys():
            task = self.download_agent_resources(agent_name)
            tasks.append(task)
        
        await asyncio.gather(*tasks)

async def main():
    downloader = DatasetDownloader()
    await downloader.download_all_resources()

if __name__ == "__main__":
    asyncio.run(main()) 