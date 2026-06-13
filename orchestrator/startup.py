"""
Virtual Brain System Orchestrator Startup Script

This script initializes and starts all orchestrator components:
1. Message broker for agent communication
2. Agent lifecycle manager for health monitoring
3. All specialized agents
4. API integration server for frontend communication
"""

import asyncio
import logging
import sys
import signal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from orchestrator.agent_communication import (
    initialize_message_broker,
    shutdown_message_broker,
    get_message_broker,
)
from orchestrator.agent_lifecycle import (
    initialize_lifecycle_manager,
    shutdown_lifecycle_manager,
    get_lifecycle_manager,
)
from orchestrator.agent_manager import AgentManager
from orchestrator.api_integration import APIIntegration
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/orchestrator.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Global references for cleanup
message_broker = None
lifecycle_manager = None
agent_manager = None
api_server = None


async def initialize_orchestrator():
    """Initialize all orchestrator components."""
    global message_broker, lifecycle_manager, agent_manager, api_server
    
    logger.info("=" * 60)
    logger.info("Starting Virtual Brain Orchestrator")
    logger.info("=" * 60)
    
    try:
        # Step 1: Initialize message broker
        logger.info("Step 1: Initializing message broker...")
        message_broker = await initialize_message_broker()
        logger.info("✓ Message broker initialized and running")
        
        # Step 2: Initialize lifecycle manager
        logger.info("Step 2: Initializing lifecycle manager...")
        lifecycle_manager = await initialize_lifecycle_manager()
        logger.info("✓ Lifecycle manager initialized and running")
        
        # Step 3: Initialize agent manager
        logger.info("Step 3: Initializing agent manager...")
        # Load configuration (placeholder - would come from YAML)
        agent_config = {
            "agents": {
                "orchestrator_agent": {},
                "memory_agent": {"dependencies": {}},
                "emotion_agent": {"dependencies": {}},
                "decision_agent": {"dependencies": {}},
                "learning_agent": {"dependencies": {}},
                "task_agent": {"dependencies": {}},
                "creativity_agent": {"dependencies": {}},
                "reasoning_agent": {"dependencies": {}},
                "perception_agent": {"dependencies": {}},
                "social_agent": {"dependencies": {}},
                "language_agent": {"dependencies": {}},
                "planning_agent": {"dependencies": {}},
                "motivation_agent": {"dependencies": {}},
                "ethics_agent": {"dependencies": {}},
            },
            "monitor_interval": 30
        }
        
        agent_manager = AgentManager(agent_config)
        logger.info("✓ Agent manager initialized")
        
        # Step 4: Initialize API integration server
        logger.info("Step 4: Initializing API integration server...")
        api_server = APIIntegration(agent_manager, port=8001)
        logger.info("✓ API integration server ready on port 8001")
        
        logger.info("=" * 60)
        logger.info("Orchestrator initialization complete!")
        logger.info("=" * 60)
        logger.info(f"Message Broker: {message_broker}")
        logger.info(f"Lifecycle Manager: {lifecycle_manager}")
        logger.info(f"Agent Manager: {agent_manager}")
        logger.info(f"API Server: {api_server.port}")
        logger.info("=" * 60)
        
        return True
    
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}", exc_info=True)
        return False


async def start_orchestrator():
    """Start the orchestrator and all components."""
    logger.info("Starting orchestrator components...")
    
    try:
        # Start agent manager (loads agents)
        await agent_manager.start()
        
        # Initialize all agents
        logger.info("Initializing agents...")
        agent_count = 0
        for agent_name in agent_manager.agents.keys():
            agent_count += 1
            logger.info(f"  - {agent_name}")
        
        logger.info(f"✓ {agent_count} agents initialized")
        
        return True
    
    except Exception as e:
        logger.error(f"Failed to start orchestrator: {e}", exc_info=True)
        return False


async def run_api_server():
    """Run the API integration server."""
    try:
        logger.info("Starting API integration server on 0.0.0.0:8001...")
        api_server.run(host="0.0.0.0")
    except Exception as e:
        logger.error(f"API server error: {e}", exc_info=True)


async def shutdown_orchestrator():
    """Shutdown all orchestrator components gracefully."""
    logger.info("=" * 60)
    logger.info("Shutting down Virtual Brain Orchestrator")
    logger.info("=" * 60)
    
    try:
        # Stop agent manager
        if agent_manager:
            logger.info("Stopping agent manager...")
            await agent_manager.stop()
        
        # Shutdown lifecycle manager
        if lifecycle_manager:
            logger.info("Shutting down lifecycle manager...")
            await shutdown_lifecycle_manager()
        
        # Shutdown message broker
        if message_broker:
            logger.info("Shutting down message broker...")
            await shutdown_message_broker()
        
        logger.info("=" * 60)
        logger.info("Orchestrator shutdown complete")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    
    # Run shutdown in event loop
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(shutdown_orchestrator())
    except Exception as e:
        logger.error(f"Error handling shutdown signal: {e}")
    
    sys.exit(0)


async def main():
    """Main entry point for the orchestrator."""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Initialize orchestrator
    success = await initialize_orchestrator()
    if not success:
        logger.error("Failed to initialize orchestrator")
        await shutdown_orchestrator()
        sys.exit(1)
    
    # Start orchestrator
    success = await start_orchestrator()
    if not success:
        logger.error("Failed to start orchestrator")
        await shutdown_orchestrator()
        sys.exit(1)
    
    # Run API server (blocking)
    try:
        await run_api_server()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await shutdown_orchestrator()


if __name__ == "__main__":
    # Run the main loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Orchestrator terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
