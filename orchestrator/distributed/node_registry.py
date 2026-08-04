"""
Phase 15 — Distributed Node Registry.

Manages cluster node registration, capability discovery, worker capacity,
heartbeat tracking, and node health status across multi-node orchestrator deployments.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NodeRole(str, Enum):
    MASTER = "master"
    WORKER = "worker"
    HYBRID = "hybrid"


class NodeStatus(str, Enum):
    HEALTHY  = "healthy"
    DEGRADED = "degraded"
    OFFLINE  = "offline"
    UNKNOWN  = "unknown"


@dataclass
class NodeInfo:
    node_id: str = field(default_factory=lambda: f"node-{uuid.uuid4().hex[:8]}")
    address: str = "127.0.0.1"
    port: int = 8001
    role: NodeRole = NodeRole.HYBRID
    status: NodeStatus = NodeStatus.HEALTHY
    max_task_capacity: int = 50
    active_tasks: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    capabilities: List[str] = field(default_factory=list)
    agent_types: List[str] = field(default_factory=list)
    last_heartbeat: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    registered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def available_capacity(self) -> int:
        return max(0, self.max_task_capacity - self.active_tasks)

    @property
    def load_factor(self) -> float:
        if self.max_task_capacity <= 0:
            return 1.0
        return round(self.active_tasks / self.max_task_capacity, 4)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["role"] = self.role.value if isinstance(self.role, NodeRole) else str(self.role)
        d["status"] = self.status.value if isinstance(self.status, NodeStatus) else str(self.status)
        d["available_capacity"] = self.available_capacity
        d["load_factor"] = self.load_factor
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NodeInfo:
        role_raw = data.get("role", "hybrid")
        try:
            r = NodeRole(role_raw)
        except ValueError:
            r = NodeRole.HYBRID

        status_raw = data.get("status", "healthy")
        try:
            s = NodeStatus(status_raw)
        except ValueError:
            s = NodeStatus.HEALTHY

        return cls(
            node_id=data.get("node_id", f"node-{uuid.uuid4().hex[:8]}"),
            address=data.get("address", "127.0.0.1"),
            port=int(data.get("port", 8001)),
            role=r,
            status=s,
            max_task_capacity=int(data.get("max_task_capacity", 50)),
            active_tasks=int(data.get("active_tasks", 0)),
            cpu_usage=float(data.get("cpu_usage", 0.0)),
            memory_usage=float(data.get("memory_usage", 0.0)),
            capabilities=list(data.get("capabilities", [])),
            agent_types=list(data.get("agent_types", [])),
            last_heartbeat=data.get("last_heartbeat", datetime.utcnow().isoformat()),
            registered_at=data.get("registered_at", datetime.utcnow().isoformat()),
        )


class NodeRegistry:
    """
    Cluster Node Registry managing node states and capability discovery.
    """

    def __init__(self, heartbeat_timeout_seconds: float = 30.0):
        self._nodes: Dict[str, NodeInfo] = {}
        self._heartbeat_timeout_seconds: float = heartbeat_timeout_seconds
        self._lock = asyncio.Lock()

    async def register_node(self, node: NodeInfo) -> NodeInfo:
        """Register or update a cluster node."""
        async with self._lock:
            node.last_heartbeat = datetime.utcnow().isoformat()
            node.status = NodeStatus.HEALTHY
            self._nodes[node.node_id] = node
            logger.info("Registered cluster node %s at %s:%d role=%s", node.node_id, node.address, node.port, node.role.value)
            return node

    async def deregister_node(self, node_id: str) -> bool:
        """Remove a node from the cluster registry."""
        async with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                logger.info("Deregistered cluster node %s", node_id)
                return True
            return False

    async def record_heartbeat(
        self,
        node_id: str,
        active_tasks: Optional[int] = None,
        cpu_usage: Optional[float] = None,
        memory_usage: Optional[float] = None,
    ) -> bool:
        """Update node heartbeat and current load parameters."""
        async with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False

            node.last_heartbeat = datetime.utcnow().isoformat()
            if active_tasks is not None:
                node.active_tasks = active_tasks
            if cpu_usage is not None:
                node.cpu_usage = cpu_usage
            if memory_usage is not None:
                node.memory_usage = memory_usage

            node.status = NodeStatus.HEALTHY
            return True

    def find_capable_nodes(
        self,
        required_capability: Optional[str] = None,
        agent_type: Optional[str] = None,
        min_available_capacity: int = 1,
    ) -> List[NodeInfo]:
        """Find healthy cluster nodes matching capability and capacity criteria."""
        now = datetime.utcnow()
        capable: List[NodeInfo] = []

        for node in self._nodes.values():
            if node.status == NodeStatus.OFFLINE:
                continue

            if node.available_capacity < min_available_capacity:
                continue

            if required_capability and required_capability not in node.capabilities:
                continue

            if agent_type and agent_type not in node.agent_types and agent_type not in node.capabilities:
                continue

            capable.append(node)

        # Sort by load factor (least loaded nodes first)
        capable.sort(key=lambda n: n.load_factor)
        return capable

    async def prune_stale_nodes(self) -> List[str]:
        """Prune nodes whose heartbeats have expired."""
        pruned: List[str] = []
        now_ts = time.time()

        async with self._lock:
            for node_id, node in list(self._nodes.items()):
                try:
                    hb_dt = datetime.fromisoformat(node.last_heartbeat)
                    age_seconds = (datetime.utcnow() - hb_dt).total_seconds()
                    if age_seconds > self._heartbeat_timeout_seconds:
                        node.status = NodeStatus.OFFLINE
                        pruned.append(node_id)
                        logger.warning("Node %s marked OFFLINE due to stale heartbeat (age=%.1fs)", node_id, age_seconds)
                except Exception:
                    pass

        return pruned

    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        return self._nodes.get(node_id)

    def list_nodes(self) -> List[Dict[str, Any]]:
        return [n.to_dict() for n in self._nodes.values()]

    def get_cluster_stats(self) -> Dict[str, Any]:
        nodes = list(self._nodes.values())
        total_nodes = len(nodes)
        healthy_nodes = sum(1 for n in nodes if n.status == NodeStatus.HEALTHY)
        total_capacity = sum(n.max_task_capacity for n in nodes)
        total_active = sum(n.active_tasks for n in nodes)

        return {
            "total_nodes": total_nodes,
            "healthy_nodes": healthy_nodes,
            "total_task_capacity": total_capacity,
            "total_active_tasks": total_active,
            "cluster_load_factor": round(total_active / max(1, total_capacity), 4),
        }
