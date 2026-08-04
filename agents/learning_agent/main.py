import asyncio
import logging
from typing import Dict, Any, Optional, List
import yaml
from pathlib import Path
from datetime import datetime
import os

try:
    from structlog import get_logger
except ImportError:
    def get_logger(): return logging.getLogger(__name__)

try:
    from agents.base_agent import BaseAgent
except ImportError:
    try:
        from ..base_agent import BaseAgent  # type: ignore
    except ImportError:
        class BaseAgent:  # type: ignore
            def __init__(self, agent_id: str = "", agent_type: str = "", **_):
                self.agent_id = agent_id
                self.agent_type = agent_type
                self.state: dict = {}
                self.memory: list = []
                self.emotions: dict = {}
                self.connections: dict = {}
            async def initialize(self): pass
            async def shutdown(self): pass

from .knowledge_updater import KnowledgeUpdater
from .knowledge_base import KnowledgeBase
from .learning_processor import LearningProcessor
from .experience_manager import ExperienceManager
from .adaptation_engine import AdaptationEngine

# Optional modules — stub if missing
try:
    from .error_correction import ErrorCorrector
except ImportError:
    class ErrorCorrector:
        def __init__(self, config): pass
        async def start(self): pass
        async def stop(self): pass
        async def check_and_correct(self): return []
        async def check_experience(self, exp): pass
        async def get_status(self): return {"status": "stub"}

try:
    from .self_improvement import SelfImprovement
except ImportError:
    class SelfImprovement:
        def __init__(self, config): pass
        async def start(self): pass
        async def stop(self): pass
        async def analyze(self): return []
        async def analyze_experience(self, exp): pass
        async def get_status(self): return {"status": "stub"}

logger = get_logger()

class LearningAgent(BaseAgent):
    """Main learning agent that coordinates learning activities and knowledge management."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the learning agent."""
        super().__init__(agent_id="learning_agent", agent_type="learning")
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.knowledge_updater = KnowledgeUpdater(self.config)
        self.error_corrector = ErrorCorrector(self.config)
        self.self_improvement = SelfImprovement(self.config)
        self.knowledge_base = KnowledgeBase(self.config)
        self.learning_processor = LearningProcessor(self.config)
        self.experience_manager = ExperienceManager(self.config)
        self.adaptation_engine = AdaptationEngine(self.config)
        
        # Initialize learning state
        self.learning_state = {
            "last_update": datetime.now().isoformat(),
            "knowledge_domains": set(),
            "learning_rate": 0.5,
            "confidence": 0.5
        }
        
        # Learning-specific metrics (separate from BaseAgent.metrics dataclass)
        self.learning_metrics = {
            "total_learning_cycles": 0,
            "successful_updates": 0,
            "failed_updates": 0,
            "error_corrections": 0,
            "improvement_suggestions": 0
        }
    
    def _load_config(self, config_path) -> Dict[str, Any]:
        """Load configuration from file or accept a pre-loaded dict."""
        if isinstance(config_path, dict):
            return config_path
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            return {}
    
    async def initialize(self):
        """Initialize the learning agent — satisfies BaseAgent/orchestrator contract."""
        await super().initialize()
        self.knowledge_updater = KnowledgeUpdater(self.config)
        self.error_corrector = ErrorCorrector(self.config)
        self.self_improvement = SelfImprovement(self.config)
        self.knowledge_base = KnowledgeBase(self.config)
        self.learning_processor = LearningProcessor(self.config)
        self.experience_manager = ExperienceManager(self.config)
        self.adaptation_engine = AdaptationEngine(self.config)
        self.state.update({
            "status": "active",
            "total_learning_cycles": 0,
            "knowledge_domains": [],
        })
        logger.info(f"LearningAgent '{self.agent_id}' initialized")

    async def start(self):
        """Start the learning agent."""
        logger.info("Starting learning agent...")
        try:
            await self.knowledge_updater.start()
            await self.error_corrector.start()
            await self.self_improvement.start()
            # Track the loop task so it can be cancelled on shutdown
            self._learning_loop_task = self.create_managed_task(
                self._learning_loop(), name="learning_agent.loop"
            )
            logger.info("Learning agent started successfully")
        except Exception as e:
            logger.error(f"Failed to start learning agent: {e}")
            raise
    
    async def stop(self):
        """Stop the learning agent."""
        logger.info("Stopping learning agent...")
        
        # Stop components
        await self.knowledge_updater.stop()
        await self.error_corrector.stop()
        await self.self_improvement.stop()
        await super().shutdown()
        
        logger.info("Learning agent stopped successfully")

    async def shutdown(self):
        """Alias for stop() — satisfies orchestrator shutdown contract."""
        await self.stop()
    
    async def _learning_loop(self):
        """Main learning loop — exits cleanly when agent shuts down."""
        while not self._shutdown:
            try:
                update_success = await self.knowledge_updater.update()
                if update_success:
                    self.learning_metrics["successful_updates"] += 1
                else:
                    self.learning_metrics["failed_updates"] += 1

                corrections = await self.error_corrector.check_and_correct()
                self.learning_metrics["error_corrections"] += len(corrections)

                improvements = await self.self_improvement.analyze()
                self.learning_metrics["improvement_suggestions"] += len(improvements)

                self.learning_metrics["total_learning_cycles"] += 1

                await asyncio.sleep(self.config.get("learning_interval", 300))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in learning loop: {e}")
                await asyncio.sleep(5)
    
    async def learn_from_experience(self, experience: Dict[str, Any]):
        """Learn from a new experience."""
        try:
            # Update knowledge base with experience
            await self.knowledge_updater.add_experience(experience)
            
            # Check for errors in learning
            await self.error_corrector.check_experience(experience)
            
            # Look for improvement opportunities
            await self.self_improvement.analyze_experience(experience)
            
            logger.info(f"Successfully learned from experience: {experience.get('id', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Error learning from experience: {e}")
            raise
    
    def learn(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process new information and update knowledge."""
        try:
            # Validate input
            if not self._validate_input(input_data):
                return {"error": "Invalid input data"}
                
            # Extract knowledge
            knowledge = self.learning_processor.extract_knowledge(input_data)
            if not knowledge:
                return {"error": "Failed to extract knowledge"}
                
            # Update knowledge base
            self.knowledge_base.update(knowledge)
            
            # Process experience
            experience = {
                "domain": input_data.get("domain", "unknown"),
                "input": input_data,
                "output": knowledge,
                "timestamp": datetime.now().isoformat()
            }
            processed_experience = self.experience_manager.process_experience(experience)
            
            # Adapt learning strategy
            new_state = self.adaptation_engine.adapt(processed_experience, self.learning_state)
            self._update_learning_state(new_state)
            
            return {
                "knowledge": knowledge,
                "experience": processed_experience,
                "adaptation": new_state,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error in learning process: {e}")
            return {"error": str(e)}
            
    def _validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input data."""
        try:
            # Check required fields
            required_fields = ["domain", "information"]
            if not all(field in input_data for field in required_fields):
                return False
                
            # Validate domain
            if not isinstance(input_data["domain"], str):
                return False
                
            # Validate information
            if not isinstance(input_data["information"], str):
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"Error validating input: {e}")
            return False
            
    def _update_learning_state(self, new_state: Dict[str, Any]):
        """Update learning state with new information."""
        try:
            # Update timestamp
            self.learning_state["last_update"] = datetime.now().isoformat()
            
            # Update knowledge domains
            if "domain" in new_state:
                self.learning_state["knowledge_domains"].add(new_state["domain"])
                
            # Update learning rate
            if "learning_rate" in new_state:
                self.learning_state["learning_rate"] = new_state["learning_rate"]
                
            # Update confidence
            if "confidence" in new_state:
                self.learning_state["confidence"] = new_state["confidence"]
        except Exception as e:
            self.logger.error(f"Error updating learning state: {e}")
            
    def get_knowledge(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve knowledge from the knowledge base."""
        try:
            return self.knowledge_base.get_knowledge(domain)
        except Exception as e:
            self.logger.error(f"Error retrieving knowledge: {e}")
            return {}
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the learning agent."""
        return {
            "status": "running",
            "metrics": self.learning_metrics,
            "components": {
                "knowledge_updater": await self.knowledge_updater.get_status(),
                "error_corrector": await self.error_corrector.get_status(),
                "self_improvement": await self.self_improvement.get_status()
            }
        }

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Called by orchestrator agent_manager — async dispatch."""
        action = task.get("action", "")
        input_data = task.get("input_data", {})

        if action in ("learn", "update", "process"):
            domain = input_data.get("domain", "general")
            information = input_data.get("information", input_data.get("content", ""))
            if domain and information:
                result = self.learn({"domain": domain, "information": information,
                                     "source": input_data.get("source", "user")})
                return {"status": "learned", "result": result}
            return {"status": "skipped", "reason": "missing domain or information"}

        if action in ("get_knowledge", "recall"):
            domain = input_data.get("domain")
            knowledge = self.get_knowledge(domain)
            return {"status": "ok", "knowledge": knowledge}

        if action == "metrics":
            return {"status": "ok", "metrics": self.get_learning_metrics()}

        return {"status": "ok", "metrics": self.learning_metrics,
                "learning_state": {k: list(v) if isinstance(v, set) else v
                                   for k, v in self.learning_state.items()}}
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get learning metrics."""
        return self.learning_metrics
    
    async def clear_metrics(self):
        """Clear learning metrics."""
        self.learning_metrics = {
            "total_learning_cycles": 0,
            "successful_updates": 0,
            "failed_updates": 0,
            "error_corrections": 0,
            "improvement_suggestions": 0
        }
        logger.info("Learning metrics cleared")
    
    def get_learning_metrics(self) -> Dict[str, Any]:
        """Get learning metrics and insights."""
        try:
            metrics = {
                "state": self.learning_state,
                "experience_insights": self.experience_manager.get_experience_insights(),
                "adaptation_insights": self.adaptation_engine.get_adaptation_insights(),
                "knowledge_metrics": self.knowledge_base.get_metrics()
            }
            
            return metrics
        except Exception as e:
            self.logger.error(f"Error getting learning metrics: {e}")
            return {}
            
    def reset(self):
        """Reset the learning agent."""
        try:
            self.knowledge_base.reset()
            self.learning_processor.reset()
            self.experience_manager.reset()
            self.adaptation_engine.reset()
            
            self.learning_state = {
                "last_update": datetime.now().isoformat(),
                "knowledge_domains": set(),
                "learning_rate": 0.5,
                "confidence": 0.5
            }
        except Exception as e:
            self.logger.error(f"Error resetting learning agent: {e}")

async def main():
    """Main entry point for the learning agent."""
    try:
        # Create and start learning agent
        agent = LearningAgent()
        await agent.start()
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down learning agent...")
        await agent.stop()
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 