"""
Phase 15 — Master Cluster Coordinator.

Integrates Node Registry, Leader Election, and Distributed Task Routing
into a unified cluster coordination layer for multi-node deployments.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from orchestrator.distributed.node_registry import NodeRegistry, NodeInfo, NodeRole, NodeStatus
from orchestrator.distributed.leader_election import LeaderElectionManager, LeaderState
from orchestrator.distributed.distributed_router import DistributedTaskRouter

logger = logging.getLogger(__name__)


class ClusterCoordinator:
    """
    Unified cluster coordinator for distributed orchestrator deployments.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        cluster_cfg = cfg.get("cluster", {})

        self._node_id: str = cluster_cfg.get("node_id", f"node-{uuid.uuid4().hex[:8]}")
        self._address: str = cluster_cfg.get("address", "127.0.0.1")
        self._port: int = int(cluster_cfg.get("port", 8001))
        self._role: NodeRole = NodeRole(cluster_cfg.get("role", "hybrid"))

        self.node_registry = NodeRegistry(
            heartbeat_timeout_seconds=float(cluster_cfg.get("heartbeat_timeout_seconds", 30.0))
        )
        self.leader_election = LeaderElectionManager(
            node_id=self._node_id,
            lease_duration_seconds=float(cluster_cfg.get("lease_duration_seconds", 15.0)),
            renew_interval_seconds=float(cluster_cfg.get("renew_interval_seconds", 5.0)),
        )
        self.router = DistributedTaskRouter(
            node_registry=self.node_registry,
            local_node_id=self._node_id,
        )

        self._local_node_info = NodeInfo(
            node_id=self._node_id,
            address=self._address,
            port=self._port,
            role=self._role,
            status=NodeStatus.HEALTHY,
            max_task_capacity=int(cluster_cfg.get("max_task_capacity", 50)),
            capabilities=[
                "memory", "emotion", "reasoning", "planning", "learning",
                "task", "social", "perception", "creativity", "ethics",
            ],
        )

        self._running: bool = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_leader(self) -> bool:
        return self.leader_election.is_leader

    async def start(self) -> None:
        """Start cluster coordinator, register local node, and launch background loops."""
        async with self._lock:
            if self._running:
                return
            self._running = True

            # Register local node
            await self.node_registry.register_node(self._local_node_info)

            # Start leader election
            await self.leader_election.start()

            # Start heartbeat loop
            if not self._heartbeat_task or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(
                    self._heartbeat_loop(), name=f"cluster_coordinator.heartbeat.{self._node_id}"
                )

            logger.info("ClusterCoordinator started node_id=%s role=%s", self._node_id, self._role.value)

    async def stop(self) -> None:
        """Stop cluster coordinator cleanly."""
        async with self._lock:
            self._running = False

            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass

            await self.leader_election.stop()
            await self.node_registry.deregister_node(self._node_id)
            logger.info("ClusterCoordinator stopped node_id=%s", self._node_id)

    async def _heartbeat_loop(self) -> None:
        """Periodic local node heartbeat & stale node pruning."""
        while self._running:
            try:
                await self.node_registry.record_heartbeat(self._node_id)
                await self.node_registry.prune_stale_nodes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cluster heartbeat loop: %s", e)

            try:
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break

    def get_status(self) -> Dict[str, Any]:
        return self.get_cluster_status()

    def get_cluster_status(self) -> Dict[str, Any]:
        return {
            "local_node": self._local_node_info.to_dict(),
            "leader": self.leader_election.get_status(),
            "registry_stats": self.node_registry.get_cluster_stats(),
            "nodes": self.node_registry.list_nodes(),
            "router_stats": self.router.get_stats(),
            "running": self._running,
        }
