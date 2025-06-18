import asyncio
import logging
import os
from typing import Dict, Any, List
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from structlog import get_logger
from starlette.middleware.base import BaseHTTPMiddleware

from routes import router as api_router
from auth import get_current_user
from schemas import User, SystemStatus
from config import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load settings
settings = Settings()

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            logger.error(f"Unhandled error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up API Gateway...")
    try:
        # Initialize connections to other services
        # Add any startup initialization here
        yield
    finally:
        # Shutdown
        logger.info("Shutting down API Gateway...")
        # Close connections to other services
        # Add any cleanup code here

# Create FastAPI app
app = FastAPI(
    title="Virtual Brain System API",
    description="API Gateway for the Virtual Brain System",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

# Add error handling middleware
app.add_middleware(ErrorHandlingMiddleware)

# Add Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        # Check system components
        system_status = await get_system_status()
        return {
            "status": "healthy",
            "version": "1.0.0",
            "components": system_status.components
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "version": "1.0.0",
            "error": str(e)
        }

@app.get("/protected", dependencies=[Depends(get_current_user)])
async def protected_route(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Example protected route."""
    return {
        "message": "This is a protected route",
        "user": user.username
    }

def start():
    """Start the API Gateway server."""
    uvicorn.run(
        "api_gateway.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL
    )

if __name__ == "__main__":
    start() 