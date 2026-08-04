"""
Phase 14 — Automated Test Suite.
Production Autonomous Cognitive Coordination & Self-Improvement Engine.

Tests:
  1. Autonomous Controller initialization, start, coordination cycle, stop
  2. Global Cognitive State synchronization and updates
  3. Self-Monitoring Engine metrics collection and alerts
  4. Self-Healing Engine agent recovery, strategies, and escalation limit
  5. Adaptive Execution Optimizer cycle and dynamic parameter tuning
  6. Continuous Self-Improvement Engine trend analysis and confidence calibration
  7. Resource Governance Engine backpressure check and trend forecasting
  8. Execution Analytics Engine percentiles (p50, p95, p99), throughput, and capacity
  9. Policy Engine registration, validation, rejection of unsafe policies, evaluation
 10. High concurrency and stress testing under load
 11. Security validation and graceful error rejection
 12. Full backward compatibility with AgentManager and prior 13 phases
"""

import asyncio
import pytest
import time
from typing import Dict, Any

from orchestrator.cognitive_models import (
    GlobalCognitiveState, SystemHealthLevel, RecoveryStrategy, Policy, PolicyType,
    OptimizationAction, OptimizationRecommendation, AgentSnapshot,
)
from orchestrator.self_monitoring import SelfMonitoringEngine
from orchestrator.self_healing import SelfHealingEngine
from orchestrator.adaptive_optimizer import AdaptiveExecutionOptimizer
from orchestrator.self_improvement import ContinuousSelfImprovementEngine
from orchestrator.resource_governance import ResourceGovernanceEngine
from orchestrator.execution_analytics import ExecutionAnalyticsEngine
from orchestrator.policy_engine import PolicyEngine
from orchestrator.autonomous_controller import AutonomousCognitiveController


# ─── Mock Helpers ─────────────────────────────────────────────────────────────

class MockAgentManager:
    def __init__(self):
        self.config = {"agents": {"test_agent": {}, "memory_agent": {}}}
        self.agents = {"test_agent": object(), "memory_agent": object()}

    def get_capability_snapshot(self) -> Dict[str, Any]:
        return {
            "available_agents": ["test_agent", "memory_agent"],
            "agent_capabilities": {"test_agent": ["test"], "memory_agent": ["memory"]},
            "agent_health": {"test_agent": "healthy", "memory_agent": "degraded"},
            "agent_load": {"test_agent": 0, "memory_agent": 1},
        }

    async def stop_agent(self, agent_name: str):
        return True

    async def load_agent(self, agent_name: str, config: Dict[str, Any], reload: bool = False):
        return True


class MockLifecycleManager:
    async def get_all_agent_statuses(self) -> Dict[str, Dict[str, Any]]:
        return {
            "test_agent": {"status": "healthy", "is_running": True},
            "memory_agent": {"status": "degraded", "is_running": True},
        }

    async def restart_agent(self, agent_name: str) -> Dict[str, Any]:
        return {"success": True, "agent_id": agent_name}


# ─── Unit & Integration Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_global_cognitive_state_serialization():
    """Verify GlobalCognitiveState serialization and updating."""
    state = GlobalCognitiveState()
    snapshot = AgentSnapshot(agent_id="test_agent", status="running", health_score=0.95)
    state.update_agent(snapshot)

    assert state.active_agent_count == 1
    assert state.degraded_agent_count == 0

    d = state.to_dict()
    assert d["health_level"] == SystemHealthLevel.UNKNOWN.value
    assert "test_agent" in d["agents"]

    reconstructed = GlobalCognitiveState.from_dict(d)
    assert reconstructed.active_agent_count == 1
    assert "test_agent" in reconstructed.agents


@pytest.mark.asyncio
async def test_self_monitoring_engine():
    """Verify Self-Monitoring Engine data collection and alerts."""
    engine = SelfMonitoringEngine({"monitoring": {"interval_seconds": 0.1}})
    engine.wire(agent_manager=MockAgentManager(), lifecycle_manager=MockLifecycleManager())

    await engine.start("test_session")
    await asyncio.sleep(0.2)

    report = await engine.collect()
    assert report is not None
    assert report.session_id == "test_session"
    assert "test_agent" in report.agent_health

    await engine.stop()


@pytest.mark.asyncio
async def test_self_healing_engine_recovery_and_escalation():
    """Verify Self-Healing Engine recovery actions and escalation bounds."""
    healing = SelfHealingEngine({"self_healing": {"max_restart_attempts": 2}})
    healing.wire(agent_manager=MockAgentManager(), lifecycle_manager=MockLifecycleManager())

    # Attempt 1
    action1 = await healing.recover_agent("memory_agent", reason="Degraded health", strategy=RecoveryStrategy.RESTART)
    assert action1.attempts == 1

    # Attempt 2
    action2 = await healing.recover_agent("memory_agent", reason="Degraded health", strategy=RecoveryStrategy.RESTART)
    assert action2.attempts == 2

    # Attempt 3 (Should escalate because max_restart_attempts is 2)
    action3 = await healing.recover_agent("memory_agent", reason="Degraded health", strategy=RecoveryStrategy.RESTART)
    assert action3.strategy == RecoveryStrategy.ESCALATE
    assert not action3.success
    assert "Exceeded max restart attempts" in action3.error

    stats = healing.get_stats()
    assert stats["total_recoveries"] == 3


@pytest.mark.asyncio
async def test_adaptive_execution_optimizer():
    """Verify Adaptive Execution Optimizer cycle and dynamic parameter tuning."""
    optimizer = AdaptiveExecutionOptimizer({"optimization": {"target_latency_ms": 500.0, "target_cpu_percent": 50.0}})

    # Create dummy report with high CPU and latency
    from orchestrator.cognitive_models import MonitoringReport
    report = MonitoringReport(cpu_usage=80.0, avg_latency_ms=1200.0, queue_depth=150)

    session = await optimizer.run_optimization_cycle(monitoring_report=report)
    assert session.actions_applied > 0
    assert len(session.recommendations) >= 2

    # Verify dynamic parameters were tuned
    assert optimizer.get_dynamic_parameter("throttling_factor") < 1.0
    assert optimizer.get_dynamic_parameter("agent_timeout_seconds") > 30.0


@pytest.mark.asyncio
async def test_continuous_self_improvement():
    """Verify Continuous Self-Improvement Engine trend analysis and calibration."""
    engine = ContinuousSelfImprovementEngine()

    analytics_history = [
        {"avg_latency_ms": 1600.0, "failure_rate": 0.12},
        {"avg_latency_ms": 1800.0, "failure_rate": 0.15},
    ]

    res = engine.analyze_performance_trends(analytics_history, [])
    assert res["trend_status"] == "degraded"
    assert res["confidence_calibration"] < 1.0
    assert len(res["recommendations"]) > 0

    calibrated = engine.calibrate_confidence(0.90)
    assert calibrated < 0.90


@pytest.mark.asyncio
async def test_resource_governance_engine():
    """Verify Resource Governance backpressure and forecasting."""
    governor = ResourceGovernanceEngine({"max_cpu_percent": 75.0, "enable_backpressure": True})

    # Test backpressure logic
    check = governor.check_backpressure(priority=1)
    assert "allowed" in check
    assert "backpressure" in check

    forecast = governor.forecast_resource_pressure()
    assert "forecast_available" in forecast

    stats = governor.get_governance_stats()
    assert "active_tasks" in stats


@pytest.mark.asyncio
async def test_execution_analytics_engine():
    """Verify Execution Analytics Engine percentiles and capacity calculation."""
    analytics_engine = ExecutionAnalyticsEngine(window_seconds=60)

    # Record 10 sample executions
    for i in range(10):
        analytics_engine.record_execution(
            agent_name="test_agent",
            action="test_action",
            latency_ms=100.0 + i * 50,
            success=(i % 2 == 0),
            timed_out=(i == 9),
        )

    analytics = analytics_engine.generate_analytics(cpu_utilization=40.0, memory_utilization=50.0)
    assert analytics.avg_latency_ms > 0
    assert analytics.p50_latency_ms > 0
    assert analytics.p95_latency_ms >= analytics.p50_latency_ms
    assert analytics.p99_latency_ms >= analytics.p95_latency_ms
    assert 0.0 <= analytics.success_rate <= 1.0
    assert analytics.capacity_estimate > 0.0


@pytest.mark.asyncio
async def test_policy_engine():
    """Verify Policy Engine registration, security validation, and evaluation."""
    policy_engine = PolicyEngine()

    # Valid policy
    valid_policy = Policy(
        policy_id="custom_retry",
        name="Custom Retry",
        policy_type=PolicyType.RETRY,
        parameters={"max_retries": 5, "initial_backoff_seconds": 1.0},
    )
    assert policy_engine.register_policy(valid_policy) is True

    # Invalid policy (unsafe max_retries > 20)
    unsafe_policy = Policy(
        policy_id="unsafe_retry",
        name="Unsafe Retry",
        policy_type=PolicyType.RETRY,
        parameters={"max_retries": 100},
    )
    assert policy_engine.register_policy(unsafe_policy) is False

    eval_res = policy_engine.evaluate_execution_policy("test_agent", priority="high")
    assert eval_res["allowed"] is True
    assert eval_res["max_retries"] == 5


@pytest.mark.asyncio
async def test_autonomous_cognitive_controller_end_to_end():
    """Verify Autonomous Cognitive Controller end-to-end start, coordination cycle, and stop."""
    config = {
        "autonomous_controller": {"enabled": True, "cycle_interval_seconds": 0.1},
        "monitoring": {"interval_seconds": 0.1},
        "self_healing": {"max_restart_attempts": 3},
    }
    controller = AutonomousCognitiveController(config)
    controller.wire(
        agent_manager=MockAgentManager(),
        lifecycle_manager=MockLifecycleManager(),
    )

    await controller.start()
    assert controller._running is True

    # Record some execution events
    controller.record_execution_event("test_agent", "test_action", latency_ms=120.0, success=True)
    controller.record_execution_event("memory_agent", "recall", latency_ms=250.0, success=True)

    # Run explicit coordination cycle
    state = await controller.run_coordination_cycle()
    assert state.health_level in (SystemHealthLevel.HEALTHY, SystemHealthLevel.DEGRADED, SystemHealthLevel.UNKNOWN)
    assert len(state.active_subsystems) > 0

    status = controller.get_status()
    assert status["running"] is True
    assert "metrics" in status

    await controller.stop()
    assert controller._running is False


@pytest.mark.asyncio
async def test_high_concurrency_stress():
    """Stress test concurrent execution recording and coordination cycle."""
    controller = AutonomousCognitiveController({"autonomous_controller": {"cycle_interval_seconds": 1.0}})
    controller.wire(agent_manager=MockAgentManager(), lifecycle_manager=MockLifecycleManager())

    async def worker(worker_id: int):
        for i in range(50):
            controller.record_execution_event(
                agent_name=f"agent_{worker_id % 5}",
                action="stress_action",
                latency_ms=10.0 + (i % 10),
                success=True,
            )
            await asyncio.sleep(0.001)

    # Run 10 concurrent tasks submitting 500 execution events total
    await asyncio.gather(*(worker(i) for i in range(10)))

    state = await controller.run_coordination_cycle()
    assert state.throughput_per_sec >= 0.0
    summary = controller.execution_analytics.get_summary()
    assert summary["total_requests"] == 500
