import os
import sys
import logging
import yaml
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from models.vision_model import VisionController
from models.face_recognition_model.face_tracking import FaceTracker
from models.emotion_model import EmotionController
from models.planning_model import PlanningController
from models.language_model import LanguageController
from models.motivation_model import MotivationController
from models.voice_model import VoiceController

def setup_logging(config):
    """Setup logging configuration."""
    log_dir = config["paths"]["logs_dir"]
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=config["system"]["logging"]["log_level"],
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "main.log")),
            logging.StreamHandler()
        ]
    )

def load_config(config_path):
    """Load project configuration."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def initialize_components(config):
    """Initialize all system components."""
    components = {}
    
    # Initialize vision system
    components["vision"] = VisionController(config["vision_model"])
    
    # Initialize face recognition system
    components["face_recognition"] = FaceTracker(config["face_recognition_model"])
    
    # Initialize emotion system
    components["emotion"] = EmotionController(config["emotion_model"])
    
    # Initialize planning system
    components["planning"] = PlanningController(config["planning_model"])
    
    # Initialize language system
    components["language"] = LanguageController(config["language_model"])
    
    # Initialize motivation system
    components["motivation"] = MotivationController(config["motivation_model"])
    
    # Initialize voice system
    components["voice"] = VoiceController(config["voice_model"])
    
    return components

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Eyes Agent System")
    parser.add_argument("--config", default="config/project_config.yaml",
                      help="Path to configuration file")
    parser.add_argument("--mode", choices=["vision", "face", "emotion", "planning",
                                         "language", "motivation", "voice", "all"],
                      default="all", help="System mode to run")
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize components
        logger.info("Initializing system components...")
        components = initialize_components(config)
        
        # Start selected components
        if args.mode == "all":
            logger.info("Starting all components...")
            for name, component in components.items():
                component.start()
        else:
            logger.info(f"Starting {args.mode} component...")
            components[args.mode].start()
        
        # Main loop
        try:
            while True:
                # Process events and update components
                for component in components.values():
                    if component.is_running:
                        component.update()
                
                # Check for exit condition
                if any(not component.is_running for component in components.values()):
                    break
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        
        finally:
            # Stop all components
            logger.info("Stopping components...")
            for component in components.values():
                component.stop()
    
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        raise
    
    logger.info("System shutdown complete")

if __name__ == "__main__":
    main() 