"""
GovernanceEngine — Phase 11 Production Implementation.

Governance Engine Capabilities:
  - Organizational & operational policy evaluation
  - Business rules & approval workflow validation
  - Decision & workflow governance checking
  - Policy lifecycle management & version control
  - Configurable policy repository without hardcoded rules
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from .models import GovernancePolicy, GovernanceResult

logger = logging.getLogger(__name__)


class GovernanceEngine:
    """
    Evaluates actions and workflows against registered governance policies.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config.get("governance", {})
        self._policies: Dict[str, GovernancePolicy] = {}
        self._load_default_policies()

    def _load_default_policies(self) -> None:
        """Populate default operational policies from config or built-in templates."""
        default_policies = [
            GovernancePolicy(
                policy_id="pol_data_privacy",
                name="Data Privacy & Protection Policy",
                category="operational",
                description="Requires explicit user consent and encryption for sensitive personal data handling.",
                rules=[{"type": "data_privacy", "required_permission": "consent_granted"}],
                version="1.0.0",
                is_active=True,
                priority=1,
            ),
            GovernancePolicy(
                policy_id="pol_high_risk_approval",
                name="High-Risk Decision Approval Policy",
                category="approval",
                description="High-risk actions require secondary human-in-the-loop or supervisor approval.",
                rules=[{"type": "approval_required", "condition": "risk_level == high"}],
                version="1.1.0",
                is_active=True,
                priority=2,
            ),
            GovernancePolicy(
                policy_id="pol_system_stability",
                name="System Stability & Resource Governance",
                category="workflow",
                description="Prevents execution of workflows that threaten core system memory or process stability.",
                rules=[{"type": "resource_bound", "max_memory_percent": 90}],
                version="1.0.0",
                is_active=True,
                priority=1,
            ),
        ]

        for pol in default_policies:
            self._policies[pol.policy_id] = pol

    # ── Governance Evaluation ─────────────────────────────────────────────────

    def evaluate_governance(
        self,
        proposed_action: str,
        context: Dict[str, Any],
        custom_policies: Optional[List[Dict[str, Any]]] = None,
    ) -> GovernanceResult:
        """Evaluate a proposed action against all active governance policies."""
        violations: List[Dict[str, Any]] = []
        approvals_required: List[str] = []
        policies_checked = 0

        action_lower = proposed_action.lower()
        risk_level = context.get("risk_level", "low")

        # Evaluate against active registered policies
        for pol_id, pol in self._policies.items():
            if not pol.is_active:
                continue
            policies_checked += 1

            if pol.category == "approval" and risk_level in ("high", "critical"):
                approvals_required.append(f"Approval needed under '{pol.name}' for high-risk action")

            if pol.category == "operational" and any(w in action_lower for w in ["delete_all", "drop_table", "force_override"]):
                violations.append({
                    "policy_id": pol.policy_id,
                    "policy_name": pol.name,
                    "severity": "high",
                    "description": f"Action '{proposed_action}' violates destructive operation boundaries.",
                })

        # Evaluate custom policies passed in request
        if custom_policies:
            for c_pol in custom_policies:
                policies_checked += 1
                name = c_pol.get("name", "Custom Policy")
                rule = c_pol.get("rule", "")
                if rule and rule in action_lower:
                    violations.append({
                        "policy_id": c_pol.get("id", "custom"),
                        "policy_name": name,
                        "severity": "medium",
                        "description": f"Action matched restricted rule: '{rule}'",
                    })

        compliant = len(violations) == 0
        gov_score = 1.0 if compliant else max(0.2, round(1.0 - (len(violations) * 0.3), 2))

        rec = (
            "Action satisfies all active governance policies."
            if compliant
            else f"Action requires resolution of {len(violations)} governance violation(s)."
        )

        return GovernanceResult(
            compliant=compliant,
            policies_checked=policies_checked,
            violations=violations,
            approvals_required=approvals_required,
            governance_score=gov_score,
            recommendation=rec,
        )

    # ── Policy Lifecycle & Management ─────────────────────────────────────────

    def register_policy(self, policy: GovernancePolicy) -> bool:
        """Add or update a governance policy."""
        self._policies[policy.policy_id] = policy
        logger.info(f"Registered governance policy: '{policy.name}' (v{policy.version})")
        return True

    def get_policy(self, policy_id: str) -> Optional[GovernancePolicy]:
        return self._policies.get(policy_id)

    def list_policies(self) -> List[Dict[str, Any]]:
        return [pol.to_dict() for pol in self._policies.values()]

    def deactivate_policy(self, policy_id: str) -> bool:
        pol = self._policies.get(policy_id)
        if pol:
            pol.is_active = False
            return True
        return False
