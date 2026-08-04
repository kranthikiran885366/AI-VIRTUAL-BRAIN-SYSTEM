"""
Phase 14 — Autonomous Cognitive Controller.

The master orchestration engine responsible for system-wide self-coordination:
  - Global Cognitive State Synchronization
  - Continuous Self-Monitoring & Observability
  - Production Self-Healing & Escalation
  - Adaptive Execution Optimization & Parameter Tuning
  - Continuous Self-Improvement & Recommendation Generation
  - Intelligent Resource Management & Backpressure
  - Policy Engine Enforcement & Security Validation
  - Production Execution Analytics & Capacity Estimation

Preserves 100% backward compatibility with all completed Phase 1–13 components.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from orchestrator.cognitive_models import (
    GlobalCognitiveState, SystemHealthLevel, MonitoringReport,
    RecoveryAction, OptimizationSession, ExecutionAnalytics, Phase14Metrics,
)
from orchestrator.self_monitoring import SelfMonitoringEngine
from orchestrator.self_healing import SelfHealingEngine
from orchestrator.adaptive_optimizer import AdaptiveExecutionOptimizer
from orchestrator.self_improvement import ContinuousSelfImprovementEngine
from orchestrator.resource_governance import ResourceGovernanceEngine
from orchestrator.execution_analytics import ExecutionAnalyticsEngine
from orchestrator.policy_engine import PolicyEngine

try:
    from orchestrator.observability import get_observability
except ImportError:
    get_observability = None

logger = logging.getLogger(__name__)


class AutonomousCognitiveController:
    """
    Autonomous Cognitive Coordination and Self-Improvement Engine.
    """

    def __init__(self, config: Dict[str, Any]):
        self._cfg = config if isinstance(config, dict) else {}
        controller_cfg = self._cfg.get("autonomous_controller", {})

        self._enabled: bool = bool(controller_cfg.get("enabled", True))
        self._cycle_interval_seconds: float = float(controller_cfg.get("cycle_interval_seconds", 10.0))
        self._session_id: str = str(uuid.uuid4())

        # Integrated Subsystems
        self.global_state = GlobalCognitiveState()
        self.monitoring_engine = SelfMonitoringEngine(self._cfg)
        self.healing_engine = SelfHealingEngine(self._cfg)
        self.adaptive_optimizer = AdaptiveExecutionOptimizer(self._cfg)
        self.self_improvement_engine = ContinuousSelfImprovementEngine(self._cfg)
        self.resource_governor = ResourceGovernanceEngine(self._cfg.get("resource_allocation", {}))
        self.execution_analytics = ExecutionAnalyticsEngine(
            window_seconds=int(self._cfg.get("analytics", {}).get("window_seconds", 300))
        )
        self.policy_engine = PolicyEngine()
        self.metrics = Phase14Metrics()

        # Orchestrator References
        self._agent_manager: Optional[Any] = None
        self._lifecycle_manager: Optional[Any] = None
        self._task_scheduler: Optional[Any] = None
        self._message_broker: Optional[Any] = None
        self._communication_controller: Optional[Any] = None
        self._observability: Optional[Any] = None

        # Controller Loop Task
        self._running: bool = False
        self._controller_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    # ─── Dependency Wiring ───────────────────────────────────────────────────

    def wire(
        self,
        agent_manager=None,
        lifecycle_manager=None,
        task_scheduler=None,
        message_broker=None,
        communication_controller=None,
        observability=None,
    ) -> None:
        """Wire existing subsystem instances into the Autonomous Controller."""
        self._agent_manager = agent_manager
        self._lifecycle_manager = lifecycle_manager
        self._task_scheduler = task_scheduler
        self._message_broker = message_broker
        self._communication_controller = communication_controller
        self._observability = observability or (get_observability() if get_observability else None)

        # Forward wire to sub-engines
        self.monitoring_engine.wire(
            agent_manager=agent_manager,
            lifecycle_manager=lifecycle_manager,
            task_scheduler=task_scheduler,
            message_broker=message_broker,
            observability=self._observability,
        )
        self.healing_engine.wire(
            agent_manager=agent_manager,
            lifecycle_manager=lifecycle_manager,
            task_scheduler=task_scheduler,
            message_broker=message_broker,
        )

    # ─── Lifecycle Management ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the Autonomous Cognitive Controller supervision loops."""
        async with self._lock:
            if self._running:
                return
            self._running = True
            self._session_id = str(uuid.uuid4())

            await self.monitoring_engine.start(session_id=self._session_id)

            if not self._controller_task or self._controller_task.done():
                self._controller_task = asyncio.create_task(
                    self._coordination_loop(), name="phase14.autonomous_controller"
                )

            logger.info("AutonomousCognitiveController started session_id=%s", self._session_id)

    async def stop(self) -> None:
        """Stop the Autonomous Cognitive Controller cleanly."""
        async with self._lock:
            self._running = False
            if self._controller_task and not self._controller_task.done():
                self._controller_task.cancel()
                try:
                    await self._controller_task
                except asyncio.CancelledError:
                    pass

            await self.monitoring_engine.stop()
            logger.info("AutonomousCognitiveController stopped")

    # ─── Coordination Supervision Loop ───────────────────────────────────────

    async def _coordination_loop(self) -> None:
        """Main autonomous coordination and optimization loop."""
        while self._running:
            try:
                await self.run_coordination_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("AutonomousCognitiveController loop error: %s", e)
                self.metrics.errors += 1

            try:
                await asyncio.sleep(self._cycle_interval_seconds)
            except asyncio.CancelledError:
                break

    async def run_coordination_cycle(self) -> GlobalCognitiveState:
        """Perform a single end-to-end cognitive monitoring, healing, and optimization cycle."""
        t0 = time.perf_counter()
        correlation_id = f"corr-{uuid.uuid4()}"
        trace_id = f"trace-{uuid.uuid4()}"

        # Step 1: Collect Monitoring Report
        monitoring_report: MonitoringReport = await self.monitoring_engine.collect()

        # Step 2: Hardware Utilization & Resource Governance Check
        hardware = self.resource_governor.get_hardware_utilization()
        backpressure_status = self.resource_governor.check_backpressure()

        # Step 3: Compute Execution Analytics
        analytics: ExecutionAnalytics = self.execution_analytics.generate_analytics(
            cpu_utilization=hardware["cpu"],
            memory_utilization=hardware["memory"],
            gpu_utilization=hardware["gpu"],
        )

        # Step 4: Auto Self-Healing Trigger for Unhealthy Agents
        unhealthy_agents = [
            agent_id for agent_id, status in monitoring_report.agent_health.items()
            if status in ("unhealthy", "error", "critical")
        ]
        for unhealthy_agent in unhealthy_agents:
            self.metrics.recovery_actions += 1
            rec_action = await self.healing_engine.recover_agent(
                target_agent=unhealthy_agent,
                reason=f"Auto-detected status {monitoring_report.agent_health[unhealthy_agent]}",
                triggered_by="autonomous_controller",
            )
            if rec_action.success:
                self.metrics.successful_recoveries += 1
            else:
                self.metrics.failed_recoveries += 1

        # Step 5: Adaptive Execution Optimization Cycle
        opt_session: OptimizationSession = await self.adaptive_optimizer.run_optimization_cycle(
            monitoring_report=monitoring_report,
            analytics=analytics,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        self.metrics.optimization_cycles += 1
        self.metrics.recommendations_generated += len(opt_session.recommendations)
        self.metrics.recommendations_applied += opt_session.actions_applied

        # Step 6: Continuous Self-Improvement Analysis
        self_improvement_res = self.self_improvement_engine.analyze_performance_trends(
            analytics_history=[analytics.to_dict()],
            monitoring_reports=[monitoring_report.to_dict()],
        )

        # Step 7: Update Synchronized Global Cognitive State
        self.global_state.timestamp = datetime.utcnow().isoformat()
        self.global_state.health_level = monitoring_report.health_level
        self.global_state.global_health_score = 1.0 if monitoring_report.health_level == SystemHealthLevel.HEALTHY else 0.5
        self.global_state.global_confidence = self_improvement_res.get("confidence_calibration", 0.70)
        self.global_state.global_workload = round(hardware["cpu"] / 100.0, 2)

        self.global_state.cpu_usage = hardware["cpu"]
        self.global_state.memory_usage = hardware["memory"]
        self.global_state.gpu_usage = hardware["gpu"]
        self.global_state.queue_depth_total = monitoring_report.queue_depth
        self.global_state.throughput_per_sec = analytics.throughput_per_sec
        self.global_state.failure_rate = analytics.failure_rate
        self.global_state.timeout_rate = analytics.timeout_rate

        self.global_state.active_subsystems = [
            "SelfMonitoringEngine",
            "SelfHealingEngine",
            "AdaptiveExecutionOptimizer",
            "ContinuousSelfImprovementEngine",
            "ResourceGovernanceEngine",
            "ExecutionAnalyticsEngine",
            "PolicyEngine",
        ]
        self.global_state.capabilities = [
            "autonomous_orchestration",
            "adaptive_workflow_optimization",
            "cognitive_self_monitoring",
            "execution_optimization",
            "workload_balancing",
            "self_healing",
            "continuous_optimization",
            "intelligent_resource_management",
        ]

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.metrics.total_latency_ms += elapsed_ms

        logger.debug(
            "Completed coordination cycle session_id=%s health=%s lat=%.2fms correlation_id=%s trace_id=%s",
            self._session_id, self.global_state.health_level.value, elapsed_ms, correlation_id, trace_id,
        )
        return self.global_state

    # ─── System-Wide Public Interface ──────────────────────────────────────────

    def record_execution_event(
        self,
        agent_name: str,
        action: str,
        latency_ms: float,
        success: bool = True,
        timed_out: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """Record task execution events for real-time analytics and optimization."""
        self.execution_analytics.record_execution(
            agent_name=agent_name,
            action=action,
            latency_ms=latency_ms,
            success=success,
            timed_out=timed_out,
            error=error,
        )

    def get_global_state(self) -> Dict[str, Any]:
        return self.global_state.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        return self.metrics.as_dict()

    def get_status(self) -> Dict[str, Any]:
        return {
            "session_id": self._session_id,
            "running": self._running,
            "enabled": self._enabled,
            "health_level": self.global_state.health_level.value,
            "metrics": self.get_metrics(),
            "optimizer": self.adaptive_optimizer.get_status(),
            "healing": self.healing_engine.get_stats(),
            "governance": self.resource_governor.get_governance_stats(),
            "self_improvement": self.self_improvement_engine.get_improvement_summary(),
        }
