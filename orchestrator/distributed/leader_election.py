"""
Phase 15 — Distributed Leader Election.

Provides leader election interface, lease renewal, master failover,
and HA coordination across multi-node orchestrator deployments.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class LeaderState(str, Enum):
    LEADER   = "leader"
    FOLLOWER = "follower"
    ELECTING = "electing"


class LeaderElectionManager:
    """
    Distributed Leader Election Manager with lease renewal and automatic failover.
    """

    def __init__(
        self,
        node_id: str,
        lease_duration_seconds: float = 15.0,
        renew_interval_seconds: float = 5.0,
    ):
        self._node_id: str = node_id
        self._lease_duration_seconds: float = lease_duration_seconds
        self._renew_interval_seconds: float = renew_interval_seconds

        self._state: LeaderState = LeaderState.FOLLOWER
        self._current_leader_id: Optional[str] = None
        self._lease_expiry: float = 0.0

        self._running: bool = False
        self._election_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_leader(self) -> bool:
        return self._state == LeaderState.LEADER

    @property
    def state(self) -> LeaderState:
        return self._state

    @property
    def leader_id(self) -> Optional[str]:
        return self._current_leader_id

    async def start(self) -> None:
        """Start the background leader election and lease renewal loop."""
        async with self._lock:
            if self._running:
                return
            self._running = True
            if not self._election_task or self._election_task.done():
                self._election_task = asyncio.create_task(
                    self._election_loop(), name=f"leader_election.{self._node_id}"
                )
            logger.info("LeaderElectionManager started for node_id=%s", self._node_id)

    async def stop(self) -> None:
        """Stop leader election loop and yield lease cleanly."""
        async with self._lock:
            self._running = False
            if self._state == LeaderState.LEADER:
                self._state = LeaderState.FOLLOWER
                self._current_leader_id = None
                logger.info("Node %s yielded leader lease during shutdown", self._node_id)

            if self._election_task and not self._election_task.done():
                self._election_task.cancel()
                try:
                    await self._election_task
                except asyncio.CancelledError:
                    pass

    async def _election_loop(self) -> None:
        """Continuous lease renewal and election loop."""
        while self._running:
            try:
                await self.try_acquire_or_renew_lease()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in leader election loop: %s", e)

            try:
                await asyncio.sleep(self._renew_interval_seconds)
            except asyncio.CancelledError:
                break

    async def try_acquire_or_renew_lease(self) -> bool:
        """Acquire lease if unheld or renew if already leader."""
        now = time.time()

        async with self._lock:
            # If current leader lease expired, reset
            if self._current_leader_id and now > self._lease_expiry:
                logger.warning("Leader lease for %s expired (ts=%.2f)", self._current_leader_id, now)
                self._current_leader_id = None
                self._state = LeaderState.FOLLOWER

            if self._state == LeaderState.LEADER:
                # Renew lease
                self._lease_expiry = now + self._lease_duration_seconds
                logger.debug("Node %s renewed leader lease until %.2f", self._node_id, self._lease_expiry)
                return True

            if self._current_leader_id is None:
                # Acquire lease
                self._state = LeaderState.LEADER
                self._current_leader_id = self._node_id
                self._lease_expiry = now + self._lease_duration_seconds
                logger.info("Node %s successfully acquired leader lease", self._node_id)
                return True

            return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "node_id": self._node_id,
            "state": self._state.value,
            "is_leader": self.is_leader,
            "current_leader_id": self._current_leader_id,
            "lease_expiry_ts": round(self._lease_expiry, 2),
            "lease_duration_seconds": self._lease_duration_seconds,
            "running": self._running,
        }
