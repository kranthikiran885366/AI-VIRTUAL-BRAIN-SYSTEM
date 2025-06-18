import unittest
from datetime import datetime
import yaml
import os
import sys

# Add parent directory to path to import agent modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import LearningAgent
from knowledge_base import KnowledgeBase
from learning_processor import LearningProcessor
from experience_manager import ExperienceManager
from adaptation_engine import AdaptationEngine

class TestLearningAgent(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        # Load configuration
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml"
        )
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        # Initialize agent
        self.agent = LearningAgent(self.config)
        
    def test_agent_initialization(self):
        """Test agent initialization."""
        self.assertIsNotNone(self.agent)
        self.assertIsNotNone(self.agent.knowledge_base)
        self.assertIsNotNone(self.agent.learning_processor)
        self.assertIsNotNone(self.agent.experience_manager)
        self.assertIsNotNone(self.agent.adaptation_engine)
        
    def test_learning_process(self):
        """Test the learning process."""
        # Create test input
        input_data = {
            "domain": "test_domain",
            "information": "This is a test information about machine learning.",
            "source": "test",
            "timestamp": datetime.now().isoformat()
        }
        
        # Process learning
        result = self.agent.learn(input_data)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertIn("knowledge", result)
        self.assertIn("experience", result)
        self.assertIn("adaptation", result)
        
    def test_knowledge_base(self):
        """Test knowledge base functionality."""
        # Create test knowledge
        knowledge = {
            "domain": "test_domain",
            "concepts": [
                {
                    "term": "machine learning",
                    "context": "Machine learning is a subset of artificial intelligence.",
                    "confidence": 0.8
                }
            ],
            "relationships": [
                {
                    "source": "machine learning",
                    "target": "artificial intelligence",
                    "type": "is_a",
                    "confidence": 0.7
                }
            ]
        }
        
        # Update knowledge base
        self.agent.knowledge_base.update(knowledge)
        
        # Retrieve knowledge
        retrieved = self.agent.knowledge_base.get_knowledge("test_domain")
        
        # Verify knowledge
        self.assertIsNotNone(retrieved)
        self.assertIn("concepts", retrieved)
        self.assertIn("relationships", retrieved)
        
    def test_learning_processor(self):
        """Test learning processor functionality."""
        # Create test input
        input_data = {
            "domain": "test_domain",
            "information": "Machine learning is a subset of artificial intelligence.",
            "source": "test"
        }
        
        # Extract knowledge
        knowledge = self.agent.learning_processor.extract_knowledge(input_data)
        
        # Verify knowledge extraction
        self.assertIsNotNone(knowledge)
        self.assertIn("concepts", knowledge)
        self.assertIn("relationships", knowledge)
        self.assertIn("confidence", knowledge)
        
    def test_experience_manager(self):
        """Test experience manager functionality."""
        # Create test experience
        experience = {
            "domain": "test_domain",
            "input": "Test input",
            "output": "Test output",
            "success": 0.8,
            "timestamp": datetime.now().isoformat()
        }
        
        # Process experience
        processed = self.agent.experience_manager.process_experience(experience)
        
        # Verify experience processing
        self.assertIsNotNone(processed)
        self.assertIn("metrics", processed)
        self.assertIn("timestamp", processed)
        
    def test_adaptation_engine(self):
        """Test adaptation engine functionality."""
        # Create test experience and state
        experience = {
            "domain": "test_domain",
            "success": 0.8,
            "complexity": 0.6,
            "timestamp": datetime.now().isoformat()
        }
        current_state = {
            "exploration_rate": 0.3,
            "exploitation_rate": 0.7
        }
        
        # Adapt strategies
        new_state = self.agent.adaptation_engine.adapt(experience, current_state)
        
        # Verify adaptation
        self.assertIsNotNone(new_state)
        self.assertNotEqual(new_state, current_state)
        
    def test_invalid_input(self):
        """Test handling of invalid input."""
        # Test with empty input
        result = self.agent.learn({})
        self.assertIsNotNone(result)
        self.assertIn("error", result)
        
        # Test with invalid domain
        result = self.agent.learn({"domain": None})
        self.assertIsNotNone(result)
        self.assertIn("error", result)
        
    def test_knowledge_retrieval(self):
        """Test knowledge retrieval functionality."""
        # Add test knowledge
        knowledge = {
            "domain": "test_domain",
            "concepts": [
                {
                    "term": "test concept",
                    "context": "Test context",
                    "confidence": 0.8
                }
            ]
        }
        self.agent.knowledge_base.update(knowledge)
        
        # Retrieve knowledge
        retrieved = self.agent.get_knowledge("test_domain")
        
        # Verify retrieval
        self.assertIsNotNone(retrieved)
        self.assertIn("concepts", retrieved)
        self.assertTrue(len(retrieved["concepts"]) > 0)
        
    def test_experience_insights(self):
        """Test experience insights functionality."""
        # Add test experiences
        for i in range(3):
            experience = {
                "domain": "test_domain",
                "success": 0.8,
                "timestamp": datetime.now().isoformat()
            }
            self.agent.experience_manager.process_experience(experience)
            
        # Get insights
        insights = self.agent.experience_manager.get_experience_insights()
        
        # Verify insights
        self.assertIsNotNone(insights)
        self.assertIn("total_experiences", insights)
        self.assertIn("domains", insights)
        self.assertIn("success_rate", insights)
        
    def test_adaptation_insights(self):
        """Test adaptation insights functionality."""
        # Add test adaptations
        experience = {
            "domain": "test_domain",
            "success": 0.8,
            "timestamp": datetime.now().isoformat()
        }
        current_state = {"exploration_rate": 0.3}
        
        for i in range(3):
            self.agent.adaptation_engine.adapt(experience, current_state)
            
        # Get insights
        insights = self.agent.adaptation_engine.get_adaptation_insights()
        
        # Verify insights
        self.assertIsNotNone(insights)
        self.assertIn("total_adaptations", insights)
        self.assertIn("strategy_usage", insights)
        self.assertIn("adaptation_trends", insights)
        
    def test_reset_functionality(self):
        """Test reset functionality."""
        # Add test data
        knowledge = {
            "domain": "test_domain",
            "concepts": [{"term": "test", "confidence": 0.8}]
        }
        self.agent.knowledge_base.update(knowledge)
        
        experience = {
            "domain": "test_domain",
            "success": 0.8
        }
        self.agent.experience_manager.process_experience(experience)
        
        # Reset agent
        self.agent.reset()
        
        # Verify reset
        self.assertEqual(len(self.agent.knowledge_base.get_knowledge("test_domain")["concepts"]), 0)
        self.assertEqual(len(self.agent.experience_manager.experiences), 0)
        self.assertEqual(len(self.agent.adaptation_engine.adaptation_history), 0)
        
if __name__ == '__main__':
    unittest.main() 