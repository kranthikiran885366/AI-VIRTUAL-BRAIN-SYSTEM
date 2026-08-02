import asyncio
import logging
import os
import signal
import sys
import uuid
from typing import Dict, List, Optional
import time

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from structlog import get_logger

from .message_broker import MessageBroker
from .topic_manager import TopicManager
from .message_processor import MessageProcessor
from .health_monitor import HealthMonitor
from .config import Settings

try:
    from orchestrator.request_context import build_request_context, clear_request_context, set_request_context
except Exception:
    build_request_context = clear_request_context = set_request_context = None  # type: ignore

try:
    from orchestrator.observability import runtime_observability
except Exception:
    runtime_observability = None  # type: ignore

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

# Module-level background task references — prevent GC on Python 3.11+
_background_tasks: list = []


@app.middleware("http")
async def request_context_middleware(request: Request, call_next) -> Response:
    correlation_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    token = None
    if build_request_context and set_request_context:
        context = build_request_context(correlation_id=correlation_id, request_id=request_id, trace_id=trace_id)
        token = set_request_context(context)
        request.state.request_context = context
    start = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        if runtime_observability:
            entry = runtime_observability.begin_request(f"{request.method} {request.url.path}")
            runtime_observability.end_request(entry, "success", (time.perf_counter() - start) * 1000)
        return response
    except Exception:
        if runtime_observability:
            runtime_observability.record_error()
        raise
    finally:
        if clear_request_context and token is not None:
            clear_request_context(token)

# Initialize components
message_broker = MessageBroker()
topic_manager = TopicManager()
message_processor = MessageProcessor()
health_monitor = HealthMonitor()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global _background_tasks
    logger.info("Starting up Communication Bus...")
    runtime_report = settings.validate_runtime()
    if not runtime_report["ok"]:
        raise RuntimeError("Invalid communication bus configuration: " + "; ".join(runtime_report["errors"]))

    # Initialize components
    await message_broker.initialize()
    await topic_manager.initialize()
    await message_processor.initialize()
    await health_monitor.initialize()

    # Start background tasks and hold module-level references so they
    # are not garbage-collected on Python 3.11+ (asyncio no longer keeps
    # strong references to tasks after creation).
    # FIXED: message_broker.process_messages() was referencing a non-existent
    # method. The broker's internal _process_loop is already launched by
    # initialize()/start(). We only need to keep GC-safe references here.
    t1 = asyncio.create_task(topic_manager.manage_topics(), name="comm_bus.topic_manager")
    t2 = asyncio.create_task(message_processor.process_messages(), name="comm_bus.message_processor")
    t3 = asyncio.create_task(health_monitor.monitor_health(), name="comm_bus.health_monitor")
    _background_tasks.extend([t1, t2, t3])

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
async def health_check(request: Request):
    """Health check endpoint."""
    # FIXED: request context is now accessed from the FastAPI Request object
    # that is properly injected, not from an undefined `request` variable.
    req_ctx = getattr(request.state, "request_context", None)
    return {
        "status": "healthy",
        "version": "1.0.0",
        "components": {
            "message_broker": await message_broker.get_status(),
            "topic_manager": await topic_manager.get_status(),
            "message_processor": await message_processor.get_status(),
            "health_monitor": await health_monitor.get_status(),
        },
        "observability": runtime_observability.snapshot().__dict__ if runtime_observability else {},
        "correlation_id": req_ctx.correlation_id if req_ctx else None,
        "trace_id": req_ctx.trace_id if req_ctx else None,
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