import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import cv2
import numpy as np
from pathlib import Path
import logging
from typing import Dict, Any, List, Tuple
import json
from datetime import datetime
import yaml
from tqdm import tqdm

class FaceDataset(Dataset):
    def __init__(self, data_dir: Path, transform=None):
        """Initialize face dataset."""
        self.data_dir = data_dir
        self.transform = transform
        self.samples = []
        
        # Load dataset
        self._load_dataset()
        
    def _load_dataset(self):
        """Load dataset samples."""
        # Load WIDER FACE dataset
        wider_face_dir = self.data_dir / "wider_face"
        if wider_face_dir.exists():
            self._load_wider_face(wider_face_dir)
        
        # Load CelebA dataset
        celeba_dir = self.data_dir / "celeba"
        if celeba_dir.exists():
            self._load_celeba(celeba_dir)
    
    def _load_wider_face(self, data_dir: Path):
        """Load WIDER FACE dataset."""
        # Load annotations
        annotations_file = data_dir / "wider_face_train_bbx_gt.txt"
        if not annotations_file.exists():
            return
        
        with open(annotations_file, 'r') as f:
            lines = f.readlines()
        
        i = 0
        while i < len(lines):
            # Get image path
            image_path = data_dir / "WIDER_train" / lines[i].strip()
            if not image_path.exists():
                i += 1
                continue
            
            # Get number of faces
            num_faces = int(lines[i + 1])
            
            # Get face boxes
            boxes = []
            for j in range(num_faces):
                box = list(map(int, lines[i + 2 + j].strip().split()[:4]))
                boxes.append(box)
            
            # Add sample
            self.samples.append({
                "image_path": str(image_path),
                "boxes": boxes
            })
            
            i += 2 + num_faces
    
    def _load_celeba(self, data_dir: Path):
        """Load CelebA dataset."""
        # Load annotations
        annotations_file = data_dir / "list_bbox_celeba.txt"
        if not annotations_file.exists():
            return
        
        with open(annotations_file, 'r') as f:
            lines = f.readlines()[2:]  # Skip header
        
        for line in lines:
            parts = line.strip().split()
            image_path = data_dir / "img_celeba" / parts[0]
            if not image_path.exists():
                continue
            
            # Get face box
            box = list(map(int, parts[1:5]))
            
            # Add sample
            self.samples.append({
                "image_path": str(image_path),
                "boxes": [box]
            })
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        sample = self.samples[idx]
        
        # Load image
        image = cv2.imread(sample["image_path"])
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Apply transform
        if self.transform:
            image = self.transform(image)
        
        return image, sample["boxes"]

class FaceDetectionModel(nn.Module):
    def __init__(self):
        """Initialize face detection model."""
        super().__init__()
        
        # Feature extraction
        self.features = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            
            nn.Conv2d(256, 512, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            
            nn.Conv2d(512, 512, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )
        
        # Detection head
        self.detector = nn.Sequential(
            nn.Conv2d(512, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 128, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 4, kernel_size=1)  # 4 values for bounding box
        )
        
        # Classification head
        self.classifier = nn.Sequential(
            nn.Conv2d(512, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 128, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 1, kernel_size=1),  # 1 value for face/not face
            nn.Sigmoid()
        )
    
    def forward(self, x):
        features = self.features(x)
        boxes = self.detector(features)
        scores = self.classifier(features)
        return boxes, scores

class ModelTrainer:
    def __init__(self, config: Dict[str, Any]):
        """Initialize model trainer."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Training settings
        self.batch_size = config.get("batch_size", 32)
        self.num_epochs = config.get("num_epochs", 100)
        self.learning_rate = config.get("learning_rate", 0.001)
        self.weight_decay = config.get("weight_decay", 0.0001)
        
        # Model settings
        self.model = FaceDetectionModel()
        if torch.cuda.is_available():
            self.model = self.model.cuda()
        
        # Optimizer
        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay
        )
        
        # Loss functions
        self.box_loss = nn.SmoothL1Loss()
        self.cls_loss = nn.BCELoss()
        
        # Metrics
        self.metrics = {
            "train_loss": [],
            "val_loss": [],
            "train_box_loss": [],
            "train_cls_loss": [],
            "val_box_loss": [],
            "val_cls_loss": [],
            "start_time": datetime.utcnow().isoformat()
        }
    
    def train(self, train_loader: DataLoader, val_loader: DataLoader = None):
        """Train the model."""
        self.logger.info("Starting training...")
        
        for epoch in range(self.num_epochs):
            # Training phase
            self.model.train()
            train_loss = 0
            train_box_loss = 0
            train_cls_loss = 0
            
            for images, boxes in tqdm(train_loader, desc=f"Epoch {epoch + 1}/{self.num_epochs}"):
                if torch.cuda.is_available():
                    images = images.cuda()
                    boxes = [b.cuda() for b in boxes]
                
                # Forward pass
                pred_boxes, pred_scores = self.model(images)
                
                # Calculate losses
                box_loss = self.box_loss(pred_boxes, boxes)
                cls_loss = self.cls_loss(pred_scores, torch.ones_like(pred_scores))
                loss = box_loss + cls_loss
                
                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
                
                # Update metrics
                train_loss += loss.item()
                train_box_loss += box_loss.item()
                train_cls_loss += cls_loss.item()
            
            # Calculate average losses
            train_loss /= len(train_loader)
            train_box_loss /= len(train_loader)
            train_cls_loss /= len(train_loader)
            
            # Update metrics
            self.metrics["train_loss"].append(train_loss)
            self.metrics["train_box_loss"].append(train_box_loss)
            self.metrics["train_cls_loss"].append(train_cls_loss)
            
            # Validation phase
            if val_loader:
                val_loss, val_box_loss, val_cls_loss = self._validate(val_loader)
                self.metrics["val_loss"].append(val_loss)
                self.metrics["val_box_loss"].append(val_box_loss)
                self.metrics["val_cls_loss"].append(val_cls_loss)
            
            # Log progress
            self.logger.info(
                f"Epoch {epoch + 1}/{self.num_epochs} - "
                f"Train Loss: {train_loss:.4f} - "
                f"Val Loss: {val_loss if val_loader else 'N/A':.4f}"
            )
            
            # Save checkpoint
            self._save_checkpoint(epoch + 1)
    
    def _validate(self, val_loader: DataLoader) -> Tuple[float, float, float]:
        """Validate the model."""
        self.model.eval()
        val_loss = 0
        val_box_loss = 0
        val_cls_loss = 0
        
        with torch.no_grad():
            for images, boxes in val_loader:
                if torch.cuda.is_available():
                    images = images.cuda()
                    boxes = [b.cuda() for b in boxes]
                
                # Forward pass
                pred_boxes, pred_scores = self.model(images)
                
                # Calculate losses
                box_loss = self.box_loss(pred_boxes, boxes)
                cls_loss = self.cls_loss(pred_scores, torch.ones_like(pred_scores))
                loss = box_loss + cls_loss
                
                # Update metrics
                val_loss += loss.item()
                val_box_loss += box_loss.item()
                val_cls_loss += cls_loss.item()
        
        # Calculate average losses
        val_loss /= len(val_loader)
        val_box_loss /= len(val_loader)
        val_cls_loss /= len(val_loader)
        
        return val_loss, val_box_loss, val_cls_loss
    
    def _save_checkpoint(self, epoch: int):
        """Save model checkpoint."""
        checkpoint = {
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "metrics": self.metrics
        }
        
        checkpoint_dir = Path(self.config.get("checkpoint_dir", "checkpoints"))
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        checkpoint_path = checkpoint_dir / f"checkpoint_epoch_{epoch}.pt"
        torch.save(checkpoint, checkpoint_path)
        
        self.logger.info(f"Checkpoint saved: {checkpoint_path}")
    
    def load_checkpoint(self, checkpoint_path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(checkpoint_path)
        
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.metrics = checkpoint["metrics"]
        
        self.logger.info(f"Checkpoint loaded: {checkpoint_path}")
    
    def export_model(self, output_path: str):
        """Export model to ONNX format."""
        self.model.eval()
        
        # Create dummy input
        dummy_input = torch.randn(1, 3, 416, 416)
        if torch.cuda.is_available():
            dummy_input = dummy_input.cuda()
        
        # Export model
        torch.onnx.export(
            self.model,
            dummy_input,
            output_path,
            input_names=["input"],
            output_names=["boxes", "scores"],
            dynamic_axes={
                "input": {0: "batch_size"},
                "boxes": {0: "batch_size"},
                "scores": {0: "batch_size"}
            }
        )
        
        self.logger.info(f"Model exported to: {output_path}")

def main():
    """Main function to train the model."""
    # Load configuration
    config_path = Path("config/training_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Create dataset
    dataset = FaceDataset(
        data_dir=Path("datasets"),
        transform=None  # Add transforms as needed
    )
    
    # Split dataset
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    # Create data loaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=config["batch_size"],
        shuffle=True,
        num_workers=4
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=config["batch_size"],
        shuffle=False,
        num_workers=4
    )
    
    # Create trainer
    trainer = ModelTrainer(config)
    
    # Train model
    trainer.train(train_loader, val_loader)
    
    # Export model
    trainer.export_model("models/face_detection_model.onnx")

if __name__ == "__main__":
    main() 