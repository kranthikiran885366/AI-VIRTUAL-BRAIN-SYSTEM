"""
Ethics Agent — Backward Compatibility Wrapper File.

Re-exports EthicsAgent from the production package `agents.ethics_agent.main`
to ensure 100% backward compatibility with legacy single-file imports.
"""

from agents.ethics_agent.main import EthicsAgent
from agents.ethics_agent.models import (
    EthicsContext,
    EthicalAnalysisResult,
    GovernancePolicy,
    GovernanceResult,
    ComplianceReport,
    RiskReport,
    SafetyReport,
    StakeholderImpact,
    EthicsAuditTrail,
    EthicsMetrics,
)

__all__ = [
    "EthicsAgent",
    "EthicsContext",
    "EthicalAnalysisResult",
    "GovernancePolicy",
    "GovernanceResult",
    "ComplianceReport",
    "RiskReport",
    "SafetyReport",
    "StakeholderImpact",
    "EthicsAuditTrail",
    "EthicsMetrics",
]
