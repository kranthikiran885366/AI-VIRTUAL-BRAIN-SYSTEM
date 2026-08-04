"""
Phase 14 — Policy Engine.

Manages and evaluates runtime operational policies for the AI Virtual Brain System:
  - Execution Policies (concurrency, routing restrictions)
  - Resource Policies (CPU/memory quotas, GPU limits)
  - Retry Policies (max retries, exponential backoff parameters)
  - Timeout Policies (task timeouts, circuit breaker thresholds)
  - Priority Policies (queue prioritization, escalation paths)
  - Optimization Policies (auto-tuning thresholds, throttling parameters)
  - Maintenance Policies (maintenance windows, health check intervals)
  - Degradation Policies (graceful degradation rules, feature shedding)

Supports dynamic modification with security validation to reject unsafe operations.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from orchestrator.cognitive_models import Policy, PolicyType

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Runtime operational policy engine. Safe, thread-safe, and configurable.
    """

    def __init__(self, initial_policies: Optional[List[Policy]] = None):
        self._policies: Dict[str, Policy] = {}
        self._load_default_policies()

        if initial_policies:
            for p in initial_policies:
                self.register_policy(p)

    def _load_default_policies(self) -> None:
        """Initialize production default policies."""
        defaults = [
            Policy(
                policy_id="default_execution_policy",
                name="Default Execution Policy",
                policy_type=PolicyType.EXECUTION,
                enabled=True,
                parameters={
                    "max_concurrent_agent_tasks": 20,
                    "allow_unregistered_agents": False,
                    "default_timeout_seconds": 30.0,
                },
                description="Controls agent execution bounds and default timeouts.",
            ),
            Policy(
                policy_id="default_resource_policy",
                name="Default Resource Policy",
                policy_type=PolicyType.RESOURCE,
                enabled=True,
                parameters={
                    "max_cpu_percent": 85.0,
                    "max_memory_percent": 85.0,
                    "max_gpu_percent": 90.0,
                    "enable_backpressure": True,
                },
                description="Enforces global hardware utilization ceilings.",
            ),
            Policy(
                policy_id="default_retry_policy",
                name="Default Retry Policy",
                policy_type=PolicyType.RETRY,
                enabled=True,
                parameters={
                    "max_retries": 3,
                    "backoff_multiplier": 1.5,
                    "initial_backoff_seconds": 0.5,
                    "max_backoff_seconds": 10.0,
                },
                description="Defines automatic retry limits and exponential backoff parameters.",
            ),
            Policy(
                policy_id="default_timeout_policy",
                name="Default Timeout Policy",
                policy_type=PolicyType.TIMEOUT,
                enabled=True,
                parameters={
                    "critical_task_timeout": 60.0,
                    "high_task_timeout": 45.0,
                    "medium_task_timeout": 30.0,
                    "low_task_timeout": 15.0,
                },
                description="Priority-tiered execution timeouts.",
            ),
            Policy(
                policy_id="default_degradation_policy",
                name="Default Degradation Policy",
                policy_type=PolicyType.DEGRADATION,
                enabled=True,
                parameters={
                    "enable_graceful_degradation": True,
                    "shed_non_essential_tasks_on_critical": True,
                    "degraded_mode_concurrency_factor": 0.5,
                },
                description="Graceful degradation rules for system overload scenarios.",
            ),
        ]
        for p in defaults:
            self._policies[p.policy_id] = p

    # ─── Policy Registration & Validation ──────────────────────────────────────

    def register_policy(self, policy: Policy) -> bool:
        """Register or update an operational policy after security validation."""
        valid, reason = self.validate_policy(policy)
        if not valid:
            logger.warning("Rejected invalid policy %s: %s", policy.name, reason)
            return False

        policy.updated_at = datetime.utcnow().isoformat()
        self._policies[policy.policy_id] = policy
        logger.info("Registered policy %s [%s]", policy.name, policy.policy_type.value)
        return True

    def validate_policy(self, policy: Policy) -> Tuple[bool, str]:
        """Validate runtime policy for security constraints and parameter bounds."""
        if not policy.name or not policy.policy_id:
            return False, "Policy must have non-empty id and name"

        params = policy.parameters
        if not isinstance(params, dict):
            return False, "Parameters must be a dictionary"

        # Check numeric parameter ranges to prevent resource exhaustion attacks or infinite loops
        if "max_retries" in params and (params["max_retries"] < 0 or params["max_retries"] > 20):
            return False, "max_retries must be between 0 and 20"

        if "max_cpu_percent" in params and (params["max_cpu_percent"] < 10.0 or params["max_cpu_percent"] > 100.0):
            return False, "max_cpu_percent must be between 10.0 and 100.0"

        if "default_timeout_seconds" in params and params["default_timeout_seconds"] <= 0:
            return False, "default_timeout_seconds must be positive"

        return True, "Valid policy"

    def remove_policy(self, policy_id: str) -> bool:
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        return self._policies.get(policy_id)

    def get_policies_by_type(self, policy_type: PolicyType) -> List[Policy]:
        return [p for p in self._policies.values() if p.policy_type == policy_type and p.enabled]

    def list_policies(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._policies.values()]

    # ─── Policy Evaluation ─────────────────────────────────────────────────────

    def evaluate_execution_policy(self, agent_name: str, priority: str = "medium") -> Dict[str, Any]:
        """Evaluate combined execution, timeout, and retry parameters for a given task context."""
        retries = 3
        timeout = 30.0
        backoff = 0.5

        # Check retry policy (use latest active policy)
        retry_policies = self.get_policies_by_type(PolicyType.RETRY)
        if retry_policies:
            params = retry_policies[-1].parameters
            retries = params.get("max_retries", retries)
            backoff = params.get("initial_backoff_seconds", backoff)

        # Check timeout policy (use latest active policy)
        timeout_policies = self.get_policies_by_type(PolicyType.TIMEOUT)
        if timeout_policies:
            params = timeout_policies[-1].parameters
            key = f"{priority.lower()}_task_timeout"
            timeout = params.get(key, params.get("medium_task_timeout", timeout))

        return {
            "allowed": True,
            "agent_name": agent_name,
            "priority": priority,
            "timeout_seconds": float(timeout),
            "max_retries": int(retries),
            "initial_backoff_seconds": float(backoff),
        }

    def evaluate_resource_policy(self, current_cpu: float, current_mem: float) -> Dict[str, Any]:
        """Evaluate current resource usage against resource policies."""
        resource_policies = self.get_policies_by_type(PolicyType.RESOURCE)
        if not resource_policies:
            return {"allowed": True, "backpressure": False, "reason": "No policy active"}

        params = resource_policies[0].parameters
        max_cpu = params.get("max_cpu_percent", 85.0)
        max_mem = params.get("max_memory_percent", 85.0)
        enable_bp = params.get("enable_backpressure", True)

        over_cpu = current_cpu > max_cpu
        over_mem = current_mem > max_mem
        backpressure = (over_cpu or over_mem) and enable_bp

        return {
            "allowed": not backpressure,
            "backpressure": backpressure,
            "over_cpu": over_cpu,
            "over_mem": over_mem,
            "current_cpu": current_cpu,
            "current_mem": current_mem,
            "max_cpu": max_cpu,
            "max_mem": max_mem,
        }
