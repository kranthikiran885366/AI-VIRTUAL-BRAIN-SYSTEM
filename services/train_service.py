import os
import sys
import logging
import yaml
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import threading
import queue
from dataclasses import dataclass

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from agents.eyes_agent.automation import EyesAgentAutomation
from agents.memory_agent.memory_agent import MemoryAgent
from agents.emotion_agent.emotion_agent import EmotionAgent
from agents.learning_agent.learning_agent import LearningAgent
from agents.task_agent.task_agent import TaskAgent
from agents.social_agent.social_agent import SocialAgent

@dataclass
class TrainingConfig:
    """Data class for training configuration."""
    data_dir: str
    output_dir: str
    model_dir: str
    test_dir: str
    batch_size: int
    epochs: int
    learning_rate: float
    validation_split: float
    early_stopping_patience: int

class TrainingService:
    def __init__(self, config_path: str = "config/training_config.yaml"):
        """Initialize training service."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize automation tool
        self.automation = EyesAgentAutomation()
        
        # Initialize agents
        self.memory_agent = MemoryAgent()
        self.emotion_agent = EmotionAgent()
        self.learning_agent = LearningAgent()
        self.task_agent = TaskAgent()
        self.social_agent = SocialAgent()
        
        # Connect agents
        self._connect_agents()
        
        # Training state
        self.is_training = False
        self.current_epoch = 0
        self.best_accuracy = 0.0
        self.training_history: List[Dict[str, Any]] = []
        
        # Threading
        self.training_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.training_thread = None
    
    def _load_config(self, config_path: str) -> TrainingConfig:
        """Load training configuration."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return TrainingConfig(
            data_dir=config_data["data_dir"],
            output_dir=config_data["output_dir"],
            model_dir=config_data["model_dir"],
            test_dir=config_data["test_dir"],
            batch_size=config_data["batch_size"],
            epochs=config_data["epochs"],
            learning_rate=config_data["learning_rate"],
            validation_split=config_data["validation_split"],
            early_stopping_patience=config_data["early_stopping_patience"]
        )
    
    def _connect_agents(self):
        """Connect all agents together."""
        # Connect eyes agent to other agents
        self.automation.connect_agent("memory", self.memory_agent)
        self.automation.connect_agent("emotion", self.emotion_agent)
        self.automation.connect_agent("learning", self.learning_agent)
        self.automation.connect_agent("task", self.task_agent)
        self.automation.connect_agent("social", self.social_agent)
        
        # Connect agents to each other
        self.memory_agent.connect_agent("emotion", self.emotion_agent)
        self.memory_agent.connect_agent("learning", self.learning_agent)
        self.memory_agent.connect_agent("task", self.task_agent)
        self.memory_agent.connect_agent("social", self.social_agent)
        
        self.emotion_agent.connect_agent("memory", self.memory_agent)
        self.emotion_agent.connect_agent("learning", self.learning_agent)
        self.emotion_agent.connect_agent("task", self.task_agent)
        self.emotion_agent.connect_agent("social", self.social_agent)
        
        self.learning_agent.connect_agent("memory", self.memory_agent)
        self.learning_agent.connect_agent("emotion", self.emotion_agent)
        self.learning_agent.connect_agent("task", self.task_agent)
        self.learning_agent.connect_agent("social", self.social_agent)
        
        self.task_agent.connect_agent("memory", self.memory_agent)
        self.task_agent.connect_agent("emotion", self.emotion_agent)
        self.task_agent.connect_agent("learning", self.learning_agent)
        self.task_agent.connect_agent("social", self.social_agent)
        
        self.social_agent.connect_agent("memory", self.memory_agent)
        self.social_agent.connect_agent("emotion", self.emotion_agent)
        self.social_agent.connect_agent("learning", self.learning_agent)
        self.social_agent.connect_agent("task", self.task_agent)
    
    def start_training(self):
        """Start the training process."""
        if self.is_training:
            self.logger.warning("Training already in progress")
            return
        
        self.is_training = True
        self.training_thread = threading.Thread(target=self._training_loop)
        self.training_thread.start()
        self.logger.info("Training started")
    
    def stop_training(self):
        """Stop the training process."""
        if not self.is_training:
            return
        
        self.is_training = False
        if self.training_thread:
            self.training_thread.join()
        self.logger.info("Training stopped")
    
    def _training_loop(self):
        """Main training loop."""
        try:
            # Load training data
            self.automation.load_training_data(self.config.data_dir)
            
            # Load test cases
            self.automation.load_test_cases(self.config.test_dir)
            
            # Training loop
            for epoch in range(self.config.epochs):
                if not self.is_training:
                    break
                
                self.current_epoch = epoch
                self._train_epoch()
                
                # Run validation
                validation_results = self._validate()
                
                # Update training history
                self.training_history.append({
                    "epoch": epoch,
                    "validation_results": validation_results
                })
                
                # Check early stopping
                if self._should_stop_early(validation_results):
                    self.logger.info("Early stopping triggered")
                    break
            
            # Save final models
            self.automation.save_models(self.config.model_dir)
            
            # Generate final report
            self._generate_training_report()
        
        except Exception as e:
            self.logger.error(f"Error in training loop: {str(e)}")
        finally:
            self.is_training = False
    
    def _train_epoch(self):
        """Train for one epoch."""
        # Train all models
        self.automation.train_models()
        
        # Update learning agent
        self.learning_agent.update_models()
        
        # Update task agent
        self.task_agent.update_tasks()
        
        # Update social agent
        self.social_agent.update_interactions()
    
    def _validate(self) -> Dict[str, Any]:
        """Run validation tests."""
        # Run test cases
        self.automation.run_tests()
        
        # Get test results
        results = self.automation.get_test_results()
        
        # Calculate metrics
        metrics = self._calculate_metrics(results)
        
        return {
            "results": results,
            "metrics": metrics
        }
    
    def _calculate_metrics(self, results: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """Calculate training metrics."""
        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if r["success"])
        
        return {
            "accuracy": passed_tests / total_tests if total_tests > 0 else 0.0,
            "total_tests": total_tests,
            "passed_tests": passed_tests
        }
    
    def _should_stop_early(self, validation_results: Dict[str, Any]) -> bool:
        """Check if training should stop early."""
        current_accuracy = validation_results["metrics"]["accuracy"]
        
        if current_accuracy > self.best_accuracy:
            self.best_accuracy = current_accuracy
            self.patience_counter = 0
        else:
            self.patience_counter += 1
        
        return self.patience_counter >= self.config.early_stopping_patience
    
    def _generate_training_report(self):
        """Generate final training report."""
        report = {
            "timestamp": time.time(),
            "total_epochs": self.current_epoch + 1,
            "best_accuracy": self.best_accuracy,
            "training_history": self.training_history,
            "final_metrics": self.training_history[-1]["metrics"] if self.training_history else None
        }
        
        output_file = os.path.join(self.config.output_dir, "training_report.json")
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"Generated training report: {output_file}")
    
    def get_training_status(self) -> Dict[str, Any]:
        """Get current training status."""
        return {
            "is_training": self.is_training,
            "current_epoch": self.current_epoch,
            "best_accuracy": self.best_accuracy,
            "total_epochs": self.config.epochs
        }
    
    def get_training_history(self) -> List[Dict[str, Any]]:
        """Get training history."""
        return self.training_history
    
    def reset(self):
        """Reset training service state."""
        self.stop_training()
        self.current_epoch = 0
        self.best_accuracy = 0.0
        self.training_history.clear()
        self.automation.reset()
        
        # Reset agents
        self.memory_agent.reset()
        self.emotion_agent.reset()
        self.learning_agent.reset()
        self.task_agent.reset()
        self.social_agent.reset()

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create and start training service
    service = TrainingService()
    service.start_training()
    
    try:
        # Keep main thread alive
        while service.is_training:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop_training() 