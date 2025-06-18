import logging
from typing import Dict, Any, Optional, List
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
from transformers import AutoModelForTextToSpeech, AutoTokenizer, AutoConfig
from datasets import load_dataset
from .base_training import BaseTrainingService

class MouthTrainingService(BaseTrainingService):
    def __init__(self, config_path: str = "config/mouth_agent_config.yaml"):
        super().__init__(config_path)
        self.mouth_config = self.config.get("mouth_training", {})
        
        # Initialize speech-specific parameters
        self.model_name = self.mouth_config.get("model_name", "speecht5_tts")
        self.max_length = self.mouth_config.get("max_length", 512)
        self.sample_rate = self.mouth_config.get("sample_rate", 16000)
        self.num_mel_bins = self.mouth_config.get("num_mel_bins", 80)
        self.hop_length = self.mouth_config.get("hop_length", 256)
        self.win_length = self.mouth_config.get("win_length", 1024)
        
        # Initialize components
        self.tokenizer = None
        self.model = None
        self.processor = None
    
    def download_dataset(self, dataset_name: str, dataset_url: str) -> bool:
        """Download speech dataset"""
        try:
            if dataset_name == "libritts":
                # Load LibriTTS dataset
                dataset = load_dataset("libritts")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "vctk":
                # Load VCTK dataset
                dataset = load_dataset("vctk")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            elif dataset_name == "ljspeech":
                # Load LJSpeech dataset
                dataset = load_dataset("ljspeech")
                dataset.save_to_disk(self.dataset_dir / dataset_name)
                return True
            
            else:
                return super().download_dataset(dataset_name, dataset_url)
        
        except Exception as e:
            self.logger.error(f"Error downloading speech dataset: {e}")
            return False
    
    def download_model(self, model_name: str, model_url: str) -> bool:
        """Download pre-trained speech model"""
        try:
            if model_name == "speecht5_tts":
                # Download SpeechT5 model and tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained("microsoft/speecht5_tts")
                self.model = AutoModelForTextToSpeech.from_pretrained("microsoft/speecht5_tts")
                self.processor = AutoProcessor.from_pretrained("microsoft/speecht5_tts")
                
                # Save model and tokenizer
                model_path = self.model_dir / model_name
                model_path.mkdir(parents=True, exist_ok=True)
                
                self.tokenizer.save_pretrained(model_path)
                self.model.save_pretrained(model_path)
                self.processor.save_pretrained(model_path)
                
                return True
            
            elif model_name == "fastspeech2":
                # Download FastSpeech2 model and tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained("espnet/fastspeech2_ljspeech")
                self.model = AutoModelForTextToSpeech.from_pretrained("espnet/fastspeech2_ljspeech")
                self.processor = AutoProcessor.from_pretrained("espnet/fastspeech2_ljspeech")
                
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
            self.logger.error(f"Error downloading speech model: {e}")
            return False
    
    def prepare_dataset(self, dataset_name: str) -> Optional[Dataset]:
        """Prepare speech dataset for training"""
        try:
            dataset_path = self.dataset_dir / dataset_name
            if not dataset_path.exists():
                raise ValueError(f"Dataset {dataset_name} not found")
            
            # Load dataset
            dataset = load_dataset(str(dataset_path))
            
            # Create custom dataset
            class SpeechDataset(Dataset):
                def __init__(self, dataset, tokenizer, processor):
                    self.dataset = dataset
                    self.tokenizer = tokenizer
                    self.processor = processor
                
                def __len__(self):
                    return len(self.dataset)
                
                def __getitem__(self, idx):
                    item = self.dataset[idx]
                    
                    # Process text
                    text_inputs = self.tokenizer(
                        item["text"],
                        padding="max_length",
                        truncation=True,
                        max_length=self.max_length,
                        return_tensors="pt"
                    )
                    
                    # Process audio
                    audio_inputs = self.processor(
                        item["audio"],
                        sampling_rate=self.sample_rate,
                        return_tensors="pt"
                    )
                    
                    return {
                        "input_ids": text_inputs["input_ids"].squeeze(),
                        "attention_mask": text_inputs["attention_mask"].squeeze(),
                        "speech_values": audio_inputs["input_values"].squeeze()
                    }
            
            return SpeechDataset(dataset["train"], self.tokenizer, self.processor)
        
        except Exception as e:
            self.logger.error(f"Error preparing speech dataset: {e}")
            return None
    
    def create_model(self, model_config: Dict[str, Any]) -> Optional[nn.Module]:
        """Create speech model architecture"""
        try:
            if self.model_name == "speecht5_tts":
                # Create SpeechT5 model
                config = AutoConfig.from_pretrained("microsoft/speecht5_tts")
                self.model = AutoModelForTextToSpeech.from_config(config)
                self.tokenizer = AutoTokenizer.from_pretrained("microsoft/speecht5_tts")
                self.processor = AutoProcessor.from_pretrained("microsoft/speecht5_tts")
                
                return self.model
            
            else:
                raise ValueError(f"Unsupported model: {self.model_name}")
        
        except Exception as e:
            self.logger.error(f"Error creating speech model: {e}")
            return None
    
    def _train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """Train speech model for one epoch"""
        try:
            self.model.train()
            total_loss = 0
            num_batches = 0
            
            for batch in train_loader:
                # Move batch to device
                input_ids = batch["input_ids"].to(self.model.device)
                attention_mask = batch["attention_mask"].to(self.model.device)
                speech_values = batch["speech_values"].to(self.model.device)
                
                # Forward pass
                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=speech_values
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
            self.logger.error(f"Error in speech training epoch: {e}")
            return {'loss': float('inf')}
    
    def _validate_epoch(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate speech model for one epoch"""
        try:
            self.model.eval()
            total_loss = 0
            num_batches = 0
            
            with torch.no_grad():
                for batch in val_loader:
                    # Move batch to device
                    input_ids = batch["input_ids"].to(self.model.device)
                    attention_mask = batch["attention_mask"].to(self.model.device)
                    speech_values = batch["speech_values"].to(self.model.device)
                    
                    # Forward pass
                    outputs = self.model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        labels=speech_values
                    )
                    
                    loss = outputs.loss
                    total_loss += loss.item()
                    num_batches += 1
            
            return {
                'loss': total_loss / num_batches if num_batches > 0 else 0
            }
        
        except Exception as e:
            self.logger.error(f"Error in speech validation epoch: {e}")
            return {'loss': float('inf')}

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test speech training service
    training_service = MouthTrainingService()
    try:
        # Download datasets
        training_service.download_dataset("libritts", "")
        training_service.download_dataset("vctk", "")
        training_service.download_dataset("ljspeech", "")
        
        # Download models
        training_service.download_model("speecht5_tts", "")
        training_service.download_model("fastspeech2", "")
        
        # Prepare dataset
        dataset = training_service.prepare_dataset("libritts")
        
        # Create model
        model = training_service.create_model({})
        
        # Train model
        if dataset and model:
            training_service.model = model
            results = training_service.train(dataset)
            print("Training results:", results)
    
    finally:
        training_service.cleanup() 