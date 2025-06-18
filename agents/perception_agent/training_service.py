import logging
from typing import Dict, Any, Optional, List
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
from PIL import Image
import torchvision
from torchvision import transforms
from transformers import AutoModelForVision2Seq, AutoTokenizer, AutoConfig, AutoProcessor
from datasets import load_dataset
from .base_training import BaseTrainingService

class PerceptionTrainingService(BaseTrainingService):
    def __init__(self, config_path: str = "config/perception_agent_config.yaml"):
        super().__init__(config_path)
        self.perception_config = self.config.get("perception_training", {})
        
        # Initialize perception-specific parameters
        self.model_name = self.perception_config.get("model_name", "perception-vilt")
        self.max_length = self.perception_config.get("max_length", 512)
        self.image_size = self.perception_config.get("image_size", (224, 224))
        self.num_labels = self.perception_config.get("num_labels", 1000)
        self.vision_encoder = self.perception_config.get("vision_encoder", "vit")
        self.text_encoder = self.perception_config.get("text_encoder", "bert")
        
        # Initialize components
        self.tokenizer = None
        self.model = None
        self.processor = None
        self.transform = None
    
    def download_dataset(self, dataset_name: str, dataset_url: str) -> bool:
        """Download perception dataset"""
        try:
            if dataset_name == "coco_captions":
                # Load COCO Captions dataset
                dataset = load_dataset("coco_captions")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "visual_genome":
                # Load Visual Genome dataset
                dataset = load_dataset("visual_genome")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "flickr30k":
                # Load Flickr30k dataset
                dataset = load_dataset("flickr30k")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            else:
                return super().download_dataset(dataset_name, dataset_url)
        
        except Exception as e:
            self.logger.error(f"Error downloading perception dataset: {e}")
            return False
    
    def download_model(self, model_name: str, model_url: str) -> bool:
        """Download pre-trained perception model"""
        try:
            if model_name == "perception-vilt":
                # Download ViLT model and tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained("dandelin/vilt-b32-mlm")
                self.model = AutoModelForVision2Seq.from_pretrained("dandelin/vilt-b32-mlm")
                self.processor = AutoProcessor.from_pretrained("dandelin/vilt-b32-mlm")
                
                # Save model and tokenizer
                model_path = self.model_dir / model_name
                model_path.mkdir(parents=True, exist_ok=True)
                
                self.tokenizer.save_pretrained(model_path)
                self.model.save_pretrained(model_path)
                self.processor.save_pretrained(model_path)
                
                return True
            
            elif model_name == "perception-clip":
                # Download CLIP model and tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained("openai/clip-vit-base-patch32")
                self.model = AutoModelForVision2Seq.from_pretrained("openai/clip-vit-base-patch32")
                self.processor = AutoProcessor.from_pretrained("openai/clip-vit-base-patch32")
                
                # Save model and tokenizer
                model_path = self.model_dir / model_name
                model_path.mkdir(parents=True, exist_ok=True)
                
                self.tokenizer.save_pretrained(model_path)
                self.model.save_pretrained(model_path)
                self.processor.save_pretrained(model_path)
                
                return True
            
            else:
                return super().download_model(model_name, model_url)
        
        except Exception as e:
            self.logger.error(f"Error downloading perception model: {e}")
            return False
    
    def prepare_dataset(self, dataset_name: str) -> Optional[Dataset]:
        """Prepare perception dataset for training"""
        try:
            dataset_path = self.dataset_dir / dataset_name
            if not dataset_path.exists():
                raise ValueError(f"Dataset {dataset_name} not found")
            
            # Load dataset
            dataset = load_dataset(str(dataset_path))
            
            # Define transforms
            self.transform = transforms.Compose([
                transforms.Resize(self.image_size),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])
            
            # Create custom dataset
            class PerceptionDataset(Dataset):
                def __init__(self, dataset, tokenizer, processor, transform):
                    self.dataset = dataset
                    self.tokenizer = tokenizer
                    self.processor = processor
                    self.transform = transform
                
                def __len__(self):
                    return len(self.dataset)
                
                def __getitem__(self, idx):
                    item = self.dataset[idx]
                    
                    # Process image
                    image = Image.open(item["image"]).convert("RGB")
                    image = self.transform(image)
                    
                    # Process text
                    text_inputs = self.tokenizer(
                        item["text"],
                        padding="max_length",
                        truncation=True,
                        max_length=self.max_length,
                        return_tensors="pt"
                    )
                    
                    # Process image-text pair
                    inputs = self.processor(
                        images=image,
                        text=item["text"],
                        return_tensors="pt",
                        padding="max_length",
                        truncation=True
                    )
                    
                    return {
                        "pixel_values": inputs["pixel_values"].squeeze(),
                        "input_ids": text_inputs["input_ids"].squeeze(),
                        "attention_mask": text_inputs["attention_mask"].squeeze(),
                        "labels": text_inputs["input_ids"].squeeze()
                    }
            
            return PerceptionDataset(dataset["train"], self.tokenizer, self.processor, self.transform)
        
        except Exception as e:
            self.logger.error(f"Error preparing perception dataset: {e}")
            return None
    
    def create_model(self, model_config: Dict[str, Any]) -> Optional[nn.Module]:
        """Create perception model architecture"""
        try:
            if self.model_name == "perception-vilt":
                # Create ViLT model
                config = AutoConfig.from_pretrained("dandelin/vilt-b32-mlm")
                self.model = AutoModelForVision2Seq.from_config(config)
                self.tokenizer = AutoTokenizer.from_pretrained("dandelin/vilt-b32-mlm")
                self.processor = AutoProcessor.from_pretrained("dandelin/vilt-b32-mlm")
                
                return self.model
            
            else:
                raise ValueError(f"Unsupported model: {self.model_name}")
        
        except Exception as e:
            self.logger.error(f"Error creating perception model: {e}")
            return None
    
    def _train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """Train perception model for one epoch"""
        try:
            self.model.train()
            total_loss = 0
            num_batches = 0
            
            for batch in train_loader:
                # Move batch to device
                pixel_values = batch["pixel_values"].to(self.model.device)
                input_ids = batch["input_ids"].to(self.model.device)
                attention_mask = batch["attention_mask"].to(self.model.device)
                labels = batch["labels"].to(self.model.device)
                
                # Forward pass
                outputs = self.model(
                    pixel_values=pixel_values,
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels
                )
                
                loss = outputs.loss
                
                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
                num_batches += 1
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in perception training epoch: {e}")
            return {'loss': float('inf')}
    
    def _validate_epoch(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate perception model for one epoch"""
        try:
            self.model.eval()
            total_loss = 0
            num_batches = 0
            
            with torch.no_grad():
                for batch in val_loader:
                    # Move batch to device
                    pixel_values = batch["pixel_values"].to(self.model.device)
                    input_ids = batch["input_ids"].to(self.model.device)
                    attention_mask = batch["attention_mask"].to(self.model.device)
                    labels = batch["labels"].to(self.model.device)
                    
                    # Forward pass
                    outputs = self.model(
                        pixel_values=pixel_values,
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        labels=labels
                    )
                    
                    loss = outputs.loss
                    total_loss += loss.item()
                    num_batches += 1
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in perception validation epoch: {e}")
            return {'loss': float('inf')}

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test perception training service
    training_service = PerceptionTrainingService()
    try:
        # Download datasets
        training_service.download_dataset("coco_captions", "")
        training_service.download_dataset("visual_genome", "")
        training_service.download_dataset("flickr30k", "")
        
        # Download models
        training_service.download_model("perception-vilt", "")
        training_service.download_model("perception-clip", "")
        
        # Prepare dataset
        dataset = training_service.prepare_dataset("coco_captions")
        
        # Create model
        model = training_service.create_model({})
        
        # Train model
        if dataset and model:
            training_service.model = model
            results = training_service.train(dataset)
            print("Training results:", results)
    
    finally:
        training_service.cleanup() 