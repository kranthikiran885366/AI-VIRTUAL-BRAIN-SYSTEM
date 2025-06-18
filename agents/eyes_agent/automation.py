import cv2
import numpy as np
import yaml
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import threading
import queue
from dataclasses import dataclass
import json
import os

from .eyes_agent import EyesAgent
from .eye_tracking import EyeTracker
from .gaze_detection import GazeDetector
from .blink_analysis import BlinkAnalyzer
from .pupil_dilation import PupilDilationAnalyzer
from .focus_control import FocusController
from .microsaccades import MicrosaccadeSimulator

@dataclass
class TestCase:
    """Data class for test case information."""
    name: str
    description: str
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    timeout: float
    priority: int

class EyesAgentAutomation:
    def __init__(self, config_path: str = "config/eyes_config.yaml"):
        """Initialize the automation tool."""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize eyes agent
        self.eyes_agent = EyesAgent(config_path)
        
        # Test management
        self.test_cases: List[TestCase] = []
        self.test_results: Dict[str, Dict[str, Any]] = {}
        self.current_test: Optional[TestCase] = None
        
        # Training management
        self.training_data: Dict[str, List[Dict[str, Any]]] = {}
        self.model_paths: Dict[str, str] = {}
        
        # Agent integration
        self.connected_agents = {
            "memory": None,
            "emotion": None,
            "learning": None,
            "task": None,
            "social": None
        }
        
        # Threading
        self.is_running = False
        self.processing_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.processing_thread = None
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def connect_agent(self, agent_type: str, agent_instance: Any):
        """Connect to another agent in the system."""
        if agent_type in self.connected_agents:
            self.connected_agents[agent_type] = agent_instance
            self.eyes_agent.connect_agent(agent_type, agent_instance)
            self.logger.info(f"Connected to {agent_type} agent")
    
    def load_test_cases(self, test_file: str):
        """Load test cases from JSON file."""
        with open(test_file, 'r') as f:
            test_data = json.load(f)
        
        for test in test_data:
            test_case = TestCase(
                name=test["name"],
                description=test["description"],
                input_data=test["input_data"],
                expected_output=test["expected_output"],
                timeout=test.get("timeout", 10.0),
                priority=test.get("priority", 1)
            )
            self.test_cases.append(test_case)
        
        self.logger.info(f"Loaded {len(self.test_cases)} test cases")
    
    def run_tests(self, test_names: Optional[List[str]] = None):
        """Run specified test cases or all if none specified."""
        if test_names:
            tests_to_run = [t for t in self.test_cases if t.name in test_names]
        else:
            tests_to_run = self.test_cases
        
        # Sort by priority
        tests_to_run.sort(key=lambda x: x.priority, reverse=True)
        
        for test in tests_to_run:
            self._run_test_case(test)
    
    def _run_test_case(self, test: TestCase):
        """Run a single test case."""
        self.logger.info(f"Running test case: {test.name}")
        self.current_test = test
        
        start_time = time.time()
        success = False
        error_message = None
        
        try:
            # Prepare test environment
            self._prepare_test_environment(test)
            
            # Run test
            result = self._execute_test(test)
            
            # Verify results
            success = self._verify_test_results(result, test.expected_output)
            
            if not success:
                error_message = "Test results did not match expected output"
        
        except Exception as e:
            success = False
            error_message = str(e)
        
        # Record results
        self.test_results[test.name] = {
            "success": success,
            "error": error_message,
            "duration": time.time() - start_time,
            "timestamp": time.time()
        }
        
        self.current_test = None
    
    def _prepare_test_environment(self, test: TestCase):
        """Prepare environment for test case."""
        # Reset agent state
        self.eyes_agent.reset()
        
        # Set up test-specific configuration
        if "config" in test.input_data:
            self._update_config(test.input_data["config"])
        
        # Connect required agents
        if "agents" in test.input_data:
            self._connect_test_agents(test.input_data["agents"])
    
    def _execute_test(self, test: TestCase) -> Dict[str, Any]:
        """Execute test case and return results."""
        results = {}
        
        # Process input data
        for step in test.input_data.get("steps", []):
            step_result = self._execute_test_step(step)
            results[step["name"]] = step_result
        
        return results
    
    def _execute_test_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single test step."""
        step_type = step["type"]
        
        if step_type == "eye_tracking":
            return self._execute_eye_tracking_step(step)
        elif step_type == "gaze_detection":
            return self._execute_gaze_detection_step(step)
        elif step_type == "blink_analysis":
            return self._execute_blink_analysis_step(step)
        elif step_type == "pupil_dilation":
            return self._execute_pupil_dilation_step(step)
        elif step_type == "focus_control":
            return self._execute_focus_control_step(step)
        elif step_type == "microsaccades":
            return self._execute_microsaccades_step(step)
        else:
            raise ValueError(f"Unknown step type: {step_type}")
    
    def _verify_test_results(self, results: Dict[str, Any],
                           expected: Dict[str, Any]) -> bool:
        """Verify test results against expected output."""
        for key, expected_value in expected.items():
            if key not in results:
                return False
            
            actual_value = results[key]
            
            # Handle different types of comparisons
            if isinstance(expected_value, (int, float)):
                if not self._compare_numeric(actual_value, expected_value):
                    return False
            elif isinstance(expected_value, dict):
                if not self._verify_test_results(actual_value, expected_value):
                    return False
            elif actual_value != expected_value:
                return False
        
        return True
    
    def _compare_numeric(self, actual: float, expected: float,
                        tolerance: float = 0.01) -> bool:
        """Compare numeric values with tolerance."""
        return abs(actual - expected) <= tolerance
    
    def load_training_data(self, data_dir: str):
        """Load training data from directory."""
        data_dir = Path(data_dir)
        
        for data_file in data_dir.glob("*.json"):
            with open(data_file, 'r') as f:
                data = json.load(f)
                self.training_data[data_file.stem] = data
        
        self.logger.info(f"Loaded training data from {len(self.training_data)} files")
    
    def train_models(self):
        """Train all models using loaded training data."""
        # Train eye tracking model
        self._train_eye_tracking_model()
        
        # Train gaze detection model
        self._train_gaze_detection_model()
        
        # Train blink analysis model
        self._train_blink_analysis_model()
        
        # Train pupil dilation model
        self._train_pupil_dilation_model()
        
        # Train focus control model
        self._train_focus_control_model()
        
        # Train microsaccades model
        self._train_microsaccades_model()
    
    def _train_eye_tracking_model(self):
        """Train eye tracking model."""
        if "eye_tracking" not in self.training_data:
            return
        
        data = self.training_data["eye_tracking"]
        
        # Prepare training data
        X = np.array([d["input"] for d in data])
        y = np.array([d["output"] for d in data])
        
        # Train model (implementation depends on chosen ML framework)
        # This is a placeholder for actual training code
        pass
    
    def _train_gaze_detection_model(self):
        """Train gaze detection model."""
        if "gaze_detection" not in self.training_data:
            return
        
        data = self.training_data["gaze_detection"]
        
        # Prepare training data
        X = np.array([d["input"] for d in data])
        y = np.array([d["output"] for d in data])
        
        # Train model (implementation depends on chosen ML framework)
        # This is a placeholder for actual training code
        pass
    
    def _train_blink_analysis_model(self):
        """Train blink analysis model."""
        if "blink_analysis" not in self.training_data:
            return
        
        data = self.training_data["blink_analysis"]
        
        # Prepare training data
        X = np.array([d["input"] for d in data])
        y = np.array([d["output"] for d in data])
        
        # Train model (implementation depends on chosen ML framework)
        # This is a placeholder for actual training code
        pass
    
    def _train_pupil_dilation_model(self):
        """Train pupil dilation model."""
        if "pupil_dilation" not in self.training_data:
            return
        
        data = self.training_data["pupil_dilation"]
        
        # Prepare training data
        X = np.array([d["input"] for d in data])
        y = np.array([d["output"] for d in data])
        
        # Train model (implementation depends on chosen ML framework)
        # This is a placeholder for actual training code
        pass
    
    def _train_focus_control_model(self):
        """Train focus control model."""
        if "focus_control" not in self.training_data:
            return
        
        data = self.training_data["focus_control"]
        
        # Prepare training data
        X = np.array([d["input"] for d in data])
        y = np.array([d["output"] for d in data])
        
        # Train model (implementation depends on chosen ML framework)
        # This is a placeholder for actual training code
        pass
    
    def _train_microsaccades_model(self):
        """Train microsaccades model."""
        if "microsaccades" not in self.training_data:
            return
        
        data = self.training_data["microsaccades"]
        
        # Prepare training data
        X = np.array([d["input"] for d in data])
        y = np.array([d["output"] for d in data])
        
        # Train model (implementation depends on chosen ML framework)
        # This is a placeholder for actual training code
        pass
    
    def save_models(self, output_dir: str):
        """Save trained models to directory."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for model_name, model_path in self.model_paths.items():
            # Save model (implementation depends on chosen ML framework)
            # This is a placeholder for actual model saving code
            pass
    
    def get_test_results(self) -> Dict[str, Dict[str, Any]]:
        """Get test results."""
        return self.test_results
    
    def generate_report(self, output_file: str):
        """Generate test report."""
        report = {
            "timestamp": time.time(),
            "total_tests": len(self.test_cases),
            "passed_tests": sum(1 for r in self.test_results.values() if r["success"]),
            "failed_tests": sum(1 for r in self.test_results.values() if not r["success"]),
            "results": self.test_results
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"Generated test report: {output_file}")
    
    def reset(self):
        """Reset automation tool state."""
        self.test_cases.clear()
        self.test_results.clear()
        self.current_test = None
        self.training_data.clear()
        self.model_paths.clear()
        
        # Reset eyes agent
        self.eyes_agent.reset() 