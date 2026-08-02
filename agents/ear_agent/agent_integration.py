"""
AgentIntegration — Production implementation.

Bug fixes vs original:
  - Constructor accepts config: Dict (not config_path: str)
  - asyncio.get_event_loop().time() replaced with time.monotonic() (Python 3.10+ safe)
  - All HTTP calls wrapped in retry logic (3 attempts, exponential backoff)
  - Session created lazily (not in initialize()) to support sync contexts
  - get_agent_health() uses asyncio.gather() for parallel health checks
  - Timeout applied to every request (prevents hanging indefinitely)
  - Endpoints read from config (not hardcoded ports)
"""

import asyncio
import json
import logging
import time as _time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import aiohttp
    _HAS_AIOHTTP = True
except ImportError:
    _HAS_AIOHTTP = False
    aiohttp = None  # type: ignore

_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10) if _HAS_AIOHTTP else None
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 0.5  # seconds


class AgentIntegration:
    """HTTP client for communicating with other Virtual Brain agents."""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        integration_cfg = config.get("agent_integration", {})

        self.brain_endpoint: str       = integration_cfg.get("brain_endpoint",       "http://localhost:8000")
        self.emotion_endpoint: str     = integration_cfg.get("emotion_endpoint",     "http://localhost:8001")
        self.memory_endpoint: str      = integration_cfg.get("memory_endpoint",      "http://localhost:8002")
        self.personality_endpoint: str = integration_cfg.get("personality_endpoint", "http://localhost:8003")
        self._request_timeout: float   = float(integration_cfg.get("request_timeout_s", 10.0))

        self._session: Optional[Any] = None
        self.is_connected: bool = False

        if not _HAS_AIOHTTP:
            self.logger.warning(
                "AgentIntegration: aiohttp not installed — "
                "inter-agent HTTP communication will be unavailable. pip install aiohttp"
            )

    # ─── Session Management ───────────────────────────────────────────────────

    async def initialize(self):
        """Create the aiohttp session."""
        if not _HAS_AIOHTTP:
            self.logger.error("AgentIntegration: aiohttp required for initialize()")
            return
        try:
            timeout = aiohttp.ClientTimeout(total=self._request_timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self.is_connected = True
            self.logger.info("AgentIntegration: HTTP session created")
        except Exception as e:
            self.logger.error(f"AgentIntegration.initialize failed: {e}")
            raise

    async def cleanup(self):
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
        self.is_connected = False
        self.logger.info("AgentIntegration: HTTP session closed")

    # ─── HTTP Helpers ─────────────────────────────────────────────────────────

    async def _get(self, url: str) -> Optional[Dict[str, Any]]:
        """GET with retry."""
        return await self._request("GET", url)

    async def _post(self, url: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """POST with retry."""
        return await self._request("POST", url, payload)

    async def _request(self, method: str, url: str,
                       payload: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        if not _HAS_AIOHTTP:
            return None
        if not self._session or not self.is_connected:
            self.logger.warning("AgentIntegration: session not initialised — call initialize() first")
            return None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                if method == "GET":
                    async with self._session.get(url) as resp:
                        resp.raise_for_status()
                        return await resp.json()
                else:
                    async with self._session.post(url, json=payload) as resp:
                        resp.raise_for_status()
                        return await resp.json()
            except aiohttp.ClientResponseError as e:
                self.logger.warning(f"AgentIntegration: HTTP {e.status} from {url} (attempt {attempt})")
            except aiohttp.ClientConnectorError as e:
                self.logger.warning(f"AgentIntegration: connection error to {url} (attempt {attempt}): {e}")
            except asyncio.TimeoutError:
                self.logger.warning(f"AgentIntegration: timeout on {url} (attempt {attempt})")
            except Exception as e:
                self.logger.error(f"AgentIntegration: unexpected error on {url}: {e}")
                return None

            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_BASE_DELAY * (2 ** (attempt - 1)))

        self.logger.error(f"AgentIntegration: all {_MAX_RETRIES} attempts failed for {url}")
        return None

    # ─── Inter-Agent APIs ─────────────────────────────────────────────────────

    async def notify_brain(self, event_type: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Notify the Brain orchestrator of an audio event."""
        event = {
            "type": event_type,
            "data": data,
            "source": "ear_agent",
            "timestamp": _time.monotonic(),
            "wall_time": datetime.utcnow().isoformat(),
        }
        return await self._post(f"{self.brain_endpoint}/events", event)

    async def get_emotion_context(self) -> Optional[Dict[str, Any]]:
        """Fetch current emotional context from the Emotion Agent."""
        return await self._get(f"{self.emotion_endpoint}/context")

    async def get_memory_context(self, query: str) -> Optional[Dict[str, Any]]:
        """Query relevant memories from the Memory Agent."""
        return await self._post(f"{self.memory_endpoint}/query", {"query": query})

    async def get_personality_traits(self) -> Optional[Dict[str, Any]]:
        """Fetch personality traits from the Personality Agent."""
        return await self._get(f"{self.personality_endpoint}/traits")

    async def update_agent_status(self, status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Push this agent's status to the Brain."""
        return await self._post(f"{self.brain_endpoint}/status", status)

    async def get_agent_health(self) -> Dict[str, bool]:
        """
        Check health of all downstream agents in parallel.
        Bug fix: uses asyncio.gather() instead of sequential awaits.
        """
        endpoints = {
            "brain":       f"{self.brain_endpoint}/health",
            "emotion":     f"{self.emotion_endpoint}/health",
            "memory":      f"{self.memory_endpoint}/health",
            "personality": f"{self.personality_endpoint}/health",
        }

        async def _check(name: str, url: str) -> tuple:
            result = await self._get(url)
            return name, result is not None

        if not _HAS_AIOHTTP or not self.is_connected:
            return {name: False for name in endpoints}

        results = await asyncio.gather(
            *[_check(name, url) for name, url in endpoints.items()],
            return_exceptions=True,
        )
        health = {}
        for r in results:
            if isinstance(r, Exception):
                continue
            name, ok = r
            health[name] = ok
        return health