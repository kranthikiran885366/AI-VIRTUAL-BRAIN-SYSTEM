import cv2
import numpy as np
import time
import threading
import queue
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import yaml
import torch
from pathlib import Path

from .visual_processor import VisualProcessor
from .audio_processor import AudioProcessor
from .fusion_module import FusionModule
from .perception_model import PerceptionModel
from .context_builder import ContextBuilder
from .anomaly_detector import AnomalyDetector
from .emotion_inference import EmotionInference
from .automation_trigger import AutomationTrigger
from .perception_memory import PerceptionMemory
from .perception_api import PerceptionAPI

@dataclass
class PerceptionConfig:
    """Configuration for perception agent."""
    visual_processing: Dict[str, Any]
    audio_processing: Dict[str, Any]
    fusion: Dict[str, Any]
    model: Dict[str, Any]
    context: Dict[str, Any]
    anomaly: Dict[str, Any]
    emotion: Dict[str, Any]
    automation: Dict[str, Any]
    memory: Dict[str, Any]
    api: Dict[str, Any]

class PerceptionAgent:
    def __init__(self, config_path: str = "config/perception_config.yaml"):
        """Initialize the perception agent."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.visual_processor = VisualProcessor(self.config.visual_processing)
        self.audio_processor = AudioProcessor(self.config.audio_processing)
        self.fusion_module = FusionModule(self.config.fusion)
        self.perception_model = PerceptionModel(self.config.model)
        self.context_builder = ContextBuilder(self.config.context)
        self.anomaly_detector = AnomalyDetector(self.config.anomaly)
        self.emotion_inference = EmotionInference(self.config.emotion)
        self.automation_trigger = AutomationTrigger(self.config.automation)
        self.perception_memory = PerceptionMemory(self.config.memory)
        self.api = PerceptionAPI(self.config.api)
        
        # State management
        self.is_running = False
        self.current_context = None
        self.last_update_time = time.time()
        
        # Threading
        self.processing_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.processing_thread = None
        
        # Connected agents
        self.connected_agents = {
            "eyes": None,
            "ears": None,
            "emotion": None,
            "memory": None,
            "decision": None,
            "language": None,
            "planner": None
        }
        
        # Performance metrics
        self.processing_times = {
            "visual": [],
            "audio": [],
            "fusion": [],
            "perception": [],
            "context": [],
            "anomaly": [],
            "emotion": []
        }
    
    def _load_config(self, config_path: str) -> PerceptionConfig:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return PerceptionConfig(**config_data)
    
    def connect_agent(self, agent_type: str, agent_instance: Any):
        """Connect to another agent in the system."""
        if agent_type in self.connected_agents:
            self.connected_agents[agent_type] = agent_instance
            self.logger.info(f"Connected to {agent_type} agent")
    
    def start(self):
        """Start the perception agent."""
        if self.is_running:
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop)
        self.processing_thread.start()
        self.logger.info("Perception agent started")
    
    def stop(self):
        """Stop the perception agent."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join()
        self.logger.info("Perception agent stopped")
    
    def _processing_loop(self):
        """Main processing loop."""
        while self.is_running:
            try:
                # Get inputs from connected agents
                visual_data = self._get_visual_input()
                audio_data = self._get_audio_input()
                
                # Process visual data
                start_time = time.time()
                visual_results = self.visual_processor.process(visual_data)
                self.processing_times["visual"].append(time.time() - start_time)
                
                # Process audio data
                start_time = time.time()
                audio_results = self.audio_processor.process(audio_data)
                self.processing_times["audio"].append(time.time() - start_time)
                
                # Fuse multi-modal data
                start_time = time.time()
                fused_data = self.fusion_module.fuse(visual_results, audio_results)
                self.processing_times["fusion"].append(time.time() - start_time)
                
                # Run perception model
                start_time = time.time()
                perception = self.perception_model.interpret(fused_data)
                self.processing_times["perception"].append(time.time() - start_time)
                
                # Build context
                start_time = time.time()
                context = self.context_builder.build(perception)
                self.processing_times["context"].append(time.time() - start_time)
                
                # Detect anomalies
                start_time = time.time()
                anomalies = self.anomaly_detector.detect(context)
                self.processing_times["anomaly"].append(time.time() - start_time)
                
                # Infer emotions
                start_time = time.time()
                emotions = self.emotion_inference.analyze(context)
                self.processing_times["emotion"].append(time.time() - start_time)
                
                # Update current context
                self.current_context = {
                    "perception": perception,
                    "context": context,
                    "anomalies": anomalies,
                    "emotions": emotions,
                    "timestamp": time.time()
                }
                
                # Store in memory
                self.perception_memory.store(self.current_context)
                
                # Trigger automation if needed
                if anomalies:
                    self.automation_trigger.trigger_alert(anomalies)
                
                # Notify connected agents
                self._notify_agents(self.current_context)
                
                # Update API state
                self.api.update_state(self.current_context)
                
                # Small delay to prevent CPU overload
                time.sleep(0.01)
            
            except Exception as e:
                self.logger.error(f"Error in processing loop: {str(e)}")
    
    def _get_visual_input(self) -> Optional[np.ndarray]:
        """Get visual input from eyes agent."""
        if self.connected_agents["eyes"]:
            return self.connected_agents["eyes"].get_frame()
        return None
    
    def _get_audio_input(self) -> Optional[np.ndarray]:
        """Get audio input from ears agent."""
        if self.connected_agents["ears"]:
            return self.connected_agents["ears"].get_audio()
        return None
    
    def _notify_agents(self, context: Dict[str, Any]):
        """Notify connected agents of new perception."""
        # Notify emotion agent
        if self.connected_agents["emotion"]:
            self.connected_agents["emotion"].update_emotion(context["emotions"])
        
        # Notify memory agent
        if self.connected_agents["memory"]:
            self.connected_agents["memory"].store_perception(context)
        
        # Notify decision agent
        if self.connected_agents["decision"]:
            self.connected_agents["decision"].update_context(context)
        
        # Notify language agent
        if self.connected_agents["language"]:
            self.connected_agents["language"].describe_perception(context)
        
        # Notify planner agent
        if self.connected_agents["planner"]:
            self.connected_agents["planner"].update_plan(context)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        metrics = {}
        for key, times in self.processing_times.items():
            if times:
                metrics[key] = {
                    "mean": np.mean(times),
                    "std": np.std(times),
                    "min": np.min(times),
                    "max": np.max(times)
                }
        return metrics
    
    def get_current_context(self) -> Optional[Dict[str, Any]]:
        """Get current perception context."""
        return self.current_context
    
    def reset(self):
        """Reset the perception agent."""
        self.stop()
        self.current_context = None
        self.last_update_time = time.time()
        self.processing_times = {key: [] for key in self.processing_times}
        self.logger.info("Perception agent reset")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create and start perception agent
    agent = PerceptionAgent()
    agent.start()
    
    try:
        # Keep main thread alive
        while True:
            # Print performance metrics
            metrics = agent.get_performance_metrics()
            print("\nPerformance Metrics:")
            for key, values in metrics.items():
                print(f"{key}: {values}")
            
            time.sleep(1.0)
    
    except KeyboardInterrupt:
        pass
    
    finally:
        agent.stop() 