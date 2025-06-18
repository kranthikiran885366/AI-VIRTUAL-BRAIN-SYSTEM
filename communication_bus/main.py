import asyncio
import logging
import os
import signal
import sys
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from prometheus_client import make_asgi_app
from structlog import get_logger

from .message_broker import MessageBroker
from .topic_manager import TopicManager
from .message_processor import MessageProcessor
from .health_monitor import HealthMonitor
from .config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = get_logger()

# Load settings
settings = Settings()

# Create FastAPI app
app = FastAPI(
    title="Virtual Brain Communication Bus",
    description="Message broker and communication hub for the Virtual Brain System",
    version="1.0.0",
)

# Add Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Initialize components
message_broker = MessageBroker()
topic_manager = TopicManager()
message_processor = MessageProcessor()
health_monitor = HealthMonitor()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting up Communication Bus...")
    
    # Initialize components
    await message_broker.initialize()
    await topic_manager.initialize()
    await message_processor.initialize()
    await health_monitor.initialize()
    
    # Start background tasks
    asyncio.create_task(message_broker.process_messages())
    asyncio.create_task(topic_manager.manage_topics())
    asyncio.create_task(message_processor.process_messages())
    asyncio.create_task(health_monitor.monitor_health())

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Communication Bus...")
    
    # Stop background tasks
    await message_broker.shutdown()
    await topic_manager.shutdown()
    await message_processor.shutdown()
    await health_monitor.shutdown()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "components": {
            "message_broker": await message_broker.get_status(),
            "topic_manager": await topic_manager.get_status(),
            "message_processor": await message_processor.get_status(),
            "health_monitor": await health_monitor.get_status(),
        }
    }

@app.get("/topics")
async def list_topics():
    """List all topics."""
    return await topic_manager.list_topics()

@app.get("/topics/{topic_name}")
async def get_topic(topic_name: str):
    """Get topic information."""
    topic = await topic_manager.get_topic(topic_name)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic

@app.post("/topics/{topic_name}")
async def create_topic(topic_name: str, config: dict):
    """Create a new topic."""
    success = await topic_manager.create_topic(topic_name, config)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to create topic")
    return {"status": "created"}

@app.delete("/topics/{topic_name}")
async def delete_topic(topic_name: str):
    """Delete a topic."""
    success = await topic_manager.delete_topic(topic_name)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete topic")
    return {"status": "deleted"}

@app.get("/messages/{topic_name}")
async def get_messages(topic_name: str, limit: int = 100):
    """Get messages from a topic."""
    messages = await message_broker.get_messages(topic_name, limit)
    return messages

@app.post("/messages/{topic_name}")
async def publish_message(topic_name: str, message: dict):
    """Publish a message to a topic."""
    success = await message_broker.publish_message(topic_name, message)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to publish message")
    return {"status": "published"}

def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    sys.exit(0)

def start():
    """Start the Communication Bus server."""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Start the server
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )

if __name__ == "__main__":
    start() 