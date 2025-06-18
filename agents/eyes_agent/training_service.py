import logging
from typing import Dict, Any, Optional, List
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
from PIL import Image
import torchvision
from torchvision import transforms
from datasets import load_dataset
from .base_training import BaseTrainingService

class EyesTrainingService(BaseTrainingService):
    def __init__(self, config_path: str = "config/eyes_agent_config.yaml"):
        super().__init__(config_path)
        self.eyes_config = self.config.get("eyes_training", {})
        
        # Initialize vision-specific parameters
        self.model_name = self.eyes_config.get("model_name", "fasterrcnn_resnet50_fpn")
        self.num_classes = self.eyes_config.get("num_classes", 91)  # COCO classes
        self.image_size = self.eyes_config.get("image_size", (800, 800))
        self.min_size = self.eyes_config.get("min_size", 800)
        self.max_size = self.eyes_config.get("max_size", 1333)
        
        # Initialize components
        self.model = None
        self.transform = None
    
    def download_dataset(self, dataset_name: str, dataset_url: str) -> bool:
        """Download vision dataset"""
        try:
            if dataset_name == "coco":
                # Load COCO dataset
                dataset = load_dataset("coco")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "voc":
                # Load VOC dataset
                dataset = load_dataset("voc")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "openimages":
                # Load OpenImages dataset
                dataset = load_dataset("openimages")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            else:
                return super().download_dataset(dataset_name, dataset_url)
        
        except Exception as e:
            self.logger.error(f"Error downloading vision dataset: {e}")
            return False
    
    def download_model(self, model_name: str, model_url: str) -> bool:
        """Download pre-trained vision model"""
        try:
            if model_name == "fasterrcnn_resnet50_fpn":
                # Download Faster R-CNN model
                self.model = torchvision.models.detection.fasterrcnn_resnet50_fpn(
                    pretrained=True,
                    num_classes=self.num_classes
                )
                
                # Save model
                model_path = self.model_dir / model_name
                model_path.mkdir(parents=True, exist_ok=True)
                torch.save(self.model.state_dict(), model_path / "model.pth")
                
                return True
            
            elif model_name == "maskrcnn_resnet50_fpn":
                # Download Mask R-CNN model
                self.model = torchvision.models.detection.maskrcnn_resnet50_fpn(
                    pretrained=True,
                    num_classes=self.num_classes
                )
                
                # Save model
                model_path = self.model_dir / model_name
                model_path.mkdir(parents=True, exist_ok=True)
                torch.save(self.model.state_dict(), model_path / "model.pth")
                
                return True
            
            else:
                return super().download_model(model_name, model_url)
        
        except Exception as e:
            self.logger.error(f"Error downloading vision model: {e}")
            return False
    
    def prepare_dataset(self, dataset_name: str) -> Optional[Dataset]:
        """Prepare vision dataset for training"""
        try:
            dataset_path = self.dataset_dir / dataset_name
            if not dataset_path.exists():
                raise ValueError(f"Dataset {dataset_name} not found")
            
            # Load dataset
            dataset = load_dataset(str(dataset_path))
            
            # Define transforms
            self.transform = transforms.Compose([
                transforms.ToTensor(),
                transforms.Resize(self.image_size),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])
            
            # Create custom dataset
            class VisionDataset(Dataset):
                def __init__(self, dataset, transform):
                    self.dataset = dataset
                    self.transform = transform
                
                def __len__(self):
                    return len(self.dataset)
                
                def __getitem__(self, idx):
                    item = self.dataset[idx]
                    image = Image.open(item["image"]).convert("RGB")
                    image = self.transform(image)
                    
                    # Prepare targets
                    boxes = torch.as_tensor(item["boxes"], dtype=torch.float32)
                    labels = torch.as_tensor(item["labels"], dtype=torch.int64)
                    
                    target = {
                        "boxes": boxes,
                        "labels": labels
                    }
                    
                    return image, target
            
            return VisionDataset(dataset["train"], self.transform)
        
        except Exception as e:
            self.logger.error(f"Error preparing vision dataset: {e}")
            return None
    
    def create_model(self, model_config: Dict[str, Any]) -> Optional[nn.Module]:
        """Create vision model architecture"""
        try:
            if self.model_name == "fasterrcnn_resnet50_fpn":
                # Create Faster R-CNN model
                self.model = torchvision.models.detection.fasterrcnn_resnet50_fpn(
                    pretrained=False,
                    num_classes=self.num_classes
                )
                return self.model
            
            elif self.model_name == "maskrcnn_resnet50_fpn":
                # Create Mask R-CNN model
                self.model = torchvision.models.detection.maskrcnn_resnet50_fpn(
                    pretrained=False,
                    num_classes=self.num_classes
                )
                return self.model
            
            else:
                raise ValueError(f"Unsupported model: {self.model_name}")
        
        except Exception as e:
            self.logger.error(f"Error creating vision model: {e}")
            return None
    
    def _train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """Train vision model for one epoch"""
        try:
            self.model.train()
            total_loss = 0
            num_batches = 0
            
            for images, targets in train_loader:
                # Move batch to device
                images = [image.to(self.model.device) for image in images]
                targets = [{k: v.to(self.model.device) for k, v in t.items()} for t in targets]
                
                # Forward pass
                loss_dict = self.model(images, targets)
                losses = sum(loss for loss in loss_dict.values())
                
                # Backward pass
                self.optimizer.zero_grad()
                losses.backward()
                self.optimizer.step()
                
                total_loss += losses.item()
                num_batches += 1
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in vision training epoch: {e}")
            return {'loss': float('inf')}
    
    def _validate_epoch(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate vision model for one epoch"""
        try:
            self.model.eval()
            total_loss = 0
            num_batches = 0
            
            with torch.no_grad():
                for images, targets in val_loader:
                    # Move batch to device
                    images = [image.to(self.model.device) for image in images]
                    targets = [{k: v.to(self.model.device) for k, v in t.items()} for t in targets]
                    
                    # Forward pass
                    loss_dict = self.model(images, targets)
                    losses = sum(loss for loss in loss_dict.values())
                    
                    total_loss += losses.item()
                    num_batches += 1
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in vision validation epoch: {e}")
            return {'loss': float('inf')}

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test vision training service
    training_service = EyesTrainingService()
    try:
        # Download datasets
        training_service.download_dataset("coco", "")
        training_service.download_dataset("voc", "")
        training_service.download_dataset("openimages", "")
        
        # Download models
        training_service.download_model("fasterrcnn_resnet50_fpn", "")
        training_service.download_model("maskrcnn_resnet50_fpn", "")
        
        # Prepare dataset
        dataset = training_service.prepare_dataset("coco")
        
        # Create model
        model = training_service.create_model({})
        
        # Train model
        if dataset and model:
            training_service.model = model
            results = training_service.train(dataset)
            print("Training results:", results)
    
    finally:
        training_service.cleanup()