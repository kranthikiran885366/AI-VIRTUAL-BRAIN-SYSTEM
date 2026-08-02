"""
Virtual Brain System Orchestrator Startup Script
Initializes all components and starts the API server.
Works without Kafka or PostgreSQL.
"""

import asyncio
import logging
import logging.handlers
import sys
import os
import signal
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ─── Directories ──────────────────────────────────────────────────────────────

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

# ─── Logging ──────────────────────────────────────────────────────────────────

def _configure_logging(log_level: str = "INFO") -> None:
    """Configure production-grade rotating file + stream logging."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    file_handler = logging.handlers.RotatingFileHandler(
        "logs/orchestrator.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    stream_handler.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if called more than once
    if not root.handlers:
        root.addHandler(file_handler)
        root.addHandler(stream_handler)
    else:
        root.handlers.clear()
        root.addHandler(file_handler)
        root.addHandler(stream_handler)


# Bootstrap logging before importing anything else
_configure_logging()
logger = logging.getLogger(__name__)


# ─── Startup Validation ───────────────────────────────────────────────────────

def _validate_environment() -> None:
    """Validate critical environment requirements before starting the server."""
    from orchestrator.config import settings

    report = settings.validate_runtime()
    if report["warnings"]:
        for w in report["warnings"]:
            logger.warning(f"Config warning: {w}")
    if not report["ok"]:
        for e in report["errors"]:
            logger.error(f"Config error: {e}")
        raise RuntimeError(
            "Orchestrator configuration is invalid. Fix the errors above before starting."
        )

    # Reconfigure logging now that settings are loaded
    _configure_logging(settings.LOG_LEVEL)
    logger.info(f"Configuration validated (version={report.get('version', 'unknown')})")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    """Start the orchestrator via uvicorn."""
    import uvicorn
    from orchestrator.config import settings

    _validate_environment()

    logger.info("=" * 60)
    logger.info("AI Virtual Brain Orchestrator")
    logger.info(f"Starting on http://{settings.HOST}:{settings.PORT}")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info("=" * 60)

    config = uvicorn.Config(
        "orchestrator.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        # Graceful shutdown timeout
        timeout_graceful_shutdown=int(settings.SHUTDOWN_TIMEOUT),
    )
    server = uvicorn.Server(config)

    # Forward OS signals to uvicorn for clean shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, server.handle_exit, sig, None)
        except (NotImplementedError, RuntimeError):
            # Windows does not support add_signal_handler for all signals
            pass

    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user")
    except RuntimeError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
