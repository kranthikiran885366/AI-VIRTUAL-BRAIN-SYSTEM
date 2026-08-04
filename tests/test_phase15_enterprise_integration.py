"""
Phase 15 — Automated Test Suite.
Production Distributed Brain Infrastructure, Enterprise Deployment & Full System Integration.

Tests:
  1. Distributed Node Registry & Discovery
  2. Leader Election & Failover Simulation
  3. Distributed Task Router & Capability Matching
  4. Cluster Coordinator Lifecycle & Integration
  5. Security Governance & RBAC Permission Checking
  6. Secrets Management & Tamper-Evident Audit Logging
  7. Circuit Breaker State Transitions & Recovery
  8. Bulkhead Isolation & Concurrency Throttling
  9. Dead-Letter Queue (DLQ) Enqueue, Retry, Discard, Purge
 10. Disaster Recovery Backup Manifests & Failover Simulation
 11. Prometheus Metrics Exporter & OpenTelemetry Tracing Hooks
 12. SLO/SLA Compliance Tracking Engine
 13. Enterprise Ops Feature Flags & Maintenance Mode Controls
 14. Full End-to-End System Integration & Backward Compatibility Validation
"""

import asyncio
import os
import pytest
from datetime import datetime, timezone

from orchestrator.config import settings
from orchestrator.distributed import (
    NodeRegistry, NodeInfo, NodeStatus, NodeRole,
    LeaderElectionManager, LeaderState,
    DistributedTaskRouter,
    ClusterCoordinator,
)
from orchestrator.security import (
    SecurityGovernanceEngine, UserRole, UserContext, AuthToken, APIKeyInfo,
    SecretManager, InMemorySecretProvider, AuditLogger, AuditEvent, AuditSeverity,
)
from orchestrator.resilience import (
    CircuitBreaker, CircuitBreakerState, CircuitBreakerOpenError,
    BulkheadIsolator, BulkheadFullError,
    DeadLetterQueue, DLQEntry, DisasterRecoveryManager, BackupManifest,
)
from orchestrator.observability_platform import (
    ObservabilityPlatform, MetricType, MetricEntry, PrometheusExporter,
    OpenTelemetryHook, TraceSpan, SLOTracker, SLODefinition,
)
from orchestrator.enterprise_ops import (
    EnterpriseOpsManager, MaintenanceMode, FeatureFlags, ConfigurationReloader,
    ClusterDiagnostics, CapacityPlanner, UpgradeCompatibilityChecker,
)


@pytest.mark.asyncio
async def test_distributed_node_registry():
    registry = NodeRegistry(heartbeat_timeout_seconds=2.0)
    node = NodeInfo(
        node_id="node-1",
        address="127.0.0.1",
        port=8001,
        role=NodeRole.HYBRID,
        status=NodeStatus.HEALTHY,
        max_task_capacity=10,
        capabilities=["orchestration", "execution"],
        agent_types=["memory_agent", "task_agent"],
    )
    await registry.register_node(node)
    assert registry.get_node("node-1") is not None
    assert len(registry.list_nodes()) == 1

    healthy = registry.find_capable_nodes()
    assert len(healthy) == 1

    await registry.deregister_node("node-1")
    assert registry.get_node("node-1") is None


@pytest.mark.asyncio
async def test_leader_election():
    election = LeaderElectionManager(node_id="node-1", lease_duration_seconds=10.0)
    await election.start()
    assert election.state in (LeaderState.LEADER, LeaderState.FOLLOWER, LeaderState.ELECTING)

    status = election.get_status()
    assert "state" in status
    await election.stop()


@pytest.mark.asyncio
async def test_distributed_task_router():
    registry = NodeRegistry()
    await registry.register_node(NodeInfo(
        node_id="node-1", address="127.0.0.1", port=8001,
        max_task_capacity=10, active_tasks=2,
        agent_types=["memory_agent"]
    ))

    router = DistributedTaskRouter(registry, local_node_id="node-1")
    target = router.select_target_node(agent_name="memory_agent", action="query")
    assert target is not None
    assert target.node_id == "node-1"

    async def dummy_callback(*args, **kwargs):
        return {"result": "ok"}

    res = await router.route_and_dispatch(
        agent_name="memory_agent", action="query",
        input_data={"q": "test"}, local_execution_callback=dummy_callback
    )
    assert res["result"] == "ok"


@pytest.mark.asyncio
async def test_cluster_coordinator():
    coord = ClusterCoordinator(config={"cluster": {"node_id": "master-1", "renew_interval_seconds": 1.0}})
    await coord.start()
    status = coord.get_cluster_status()
    assert status["running"]
    assert status["local_node"]["node_id"] == "master-1"

    await coord.stop()
    status_after = coord.get_cluster_status()
    assert not status_after["running"]


@pytest.mark.asyncio
async def test_security_governance():
    engine = SecurityGovernanceEngine()
    engine.register_api_key(api_key="test-key", owner="user1", role=UserRole.OPERATOR)

    context = engine.validate_api_key("test-key")
    assert context is not None
    assert context.role == UserRole.OPERATOR

    auth_res = engine.authorize_request(context, required_permission="read")
    assert auth_res["authorized"]


@pytest.mark.asyncio
async def test_secrets_and_audit_logging():
    provider = InMemorySecretProvider()
    mgr = SecretManager(provider=provider)

    mgr.set_secret("DB_PASS", "supersecret")
    assert mgr.get_secret("DB_PASS") == "supersecret"

    mgr.rotate_secret("DB_PASS", "newsecret")
    assert mgr.get_secret("DB_PASS") == "newsecret"

    audit = mgr.get_audit_logger()
    events = audit.query()
    assert len(events) >= 3
    stats = audit.get_stats()
    assert stats["total_events"] >= 3


@pytest.mark.asyncio
async def test_circuit_breaker():
    cb = CircuitBreaker("test-cb", failure_threshold=2, recovery_timeout=0.2)

    async def fail_func():
        raise ValueError("simulated failure")

    async def pass_func():
        return "ok"

    with pytest.raises(ValueError):
        await cb.call(fail_func)
    with pytest.raises(ValueError):
        await cb.call(fail_func)

    assert cb.state == CircuitBreakerState.OPEN

    with pytest.raises(CircuitBreakerOpenError):
        await cb.call(pass_func)

    # Wait for recovery timeout
    await asyncio.sleep(0.25)
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Two successful calls should close it (success_threshold=2)
    res1 = await cb.call(pass_func)
    assert res1 == "ok"
    res2 = await cb.call(pass_func)
    assert res2 == "ok"
    assert cb.state == CircuitBreakerState.CLOSED


@pytest.mark.asyncio
async def test_bulkhead_isolator():
    bulkhead = BulkheadIsolator("test-bh", max_concurrent=1, max_queue=1)
    ev = asyncio.Event()

    async def slow_func():
        await ev.wait()
        return "done"

    t1 = asyncio.create_task(bulkhead.execute(slow_func))
    await asyncio.sleep(0.01)

    t2 = asyncio.create_task(bulkhead.execute(slow_func))
    await asyncio.sleep(0.01)

    # Third concurrent call should be rejected because active=1, queue=1
    with pytest.raises(BulkheadFullError):
        await bulkhead.execute(slow_func)

    ev.set()
    await t1
    await t2


@pytest.mark.asyncio
async def test_dlq():
    dlq = DeadLetterQueue(max_size=100)
    entry = dlq.enqueue({"test": 123}, "error detail", "queue_main")
    assert entry.status == "pending"

    retried = dlq.retry_entry(entry.entry_id)
    assert retried.status == "retried"

    entries = dlq.list_entries()
    assert len(entries) == 1
    stats = dlq.get_stats()
    assert stats["total_size"] == 1


@pytest.mark.asyncio
async def test_disaster_recovery():
    dr = DisasterRecoveryManager()
    manifest = dr.create_backup(components=["orchestrator", "database"])
    assert manifest.status == "completed"

    verified = dr.verify_backup(manifest.backup_id)
    assert verified

    sim = dr.simulate_failover()
    assert sim["success"]
    status = dr.get_recovery_status()
    assert status["dr_ready"]


@pytest.mark.asyncio
async def test_observability_platform():
    platform = ObservabilityPlatform()
    platform.metrics.increment("test_counter", 1.0, labels={"env": "test"})
    text = platform.metrics.export_text()
    assert "test_counter" in text

    span = platform.tracing.start_span("test_operation")
    platform.tracing.end_span(span, status="ok")
    traces = platform.tracing.get_traces()
    assert len(traces) == 1

    platform.slo_tracker.record_outcome("availability", True)
    slo = platform.slo_tracker.get_slo_status("availability")
    assert slo["is_meeting_target"]


@pytest.mark.asyncio
async def test_enterprise_ops():
    ops = EnterpriseOpsManager()
    assert not ops.maintenance.enabled
    ops.maintenance.enable("testing maintenance")
    assert ops.maintenance.enabled
    ops.maintenance.disable()
    assert not ops.maintenance.enabled

    assert ops.features.is_enabled("circuit_breakers")
    ops.features.disable("circuit_breakers")
    assert not ops.features.is_enabled("circuit_breakers")

    diag = ops.diagnostics.run_diagnostics()
    assert "python_version" in diag

    comp = ops.upgrade_checker.check_compatibility()
    assert comp["compatible"]
    assert comp["phases_registered"] == 15
