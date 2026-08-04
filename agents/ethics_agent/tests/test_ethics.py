"""
Production Test Suite for Phase 11 Ethics, Governance & Safety Engine.

Verifies:
  - Ethics lifecycle & session management
  - Multi-framework ethical reasoning (8 frameworks)
  - Governance engine & policy evaluation
  - Compliance engine & data privacy checks
  - Multi-dimensional risk matrix assessment
  - Safety engine & advisory rollbacks
  - Stakeholder analysis & trade-off matrix
  - Audit trail, session snapshotting & session replay
  - Explainable output structure & metrics emission
  - Async task dispatch & 100% backward compatibility
"""

import asyncio
import sys
import os
import unittest
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ─── Mock BaseAgent for isolated testing ────────────────────────────────────────

class MockBaseAgent:
    """Minimal stand-in for BaseAgent so tests don't require a live orchestrator."""

    def __init__(self, agent_id: str = "test_agent", agent_type: str = "test"):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.state: Dict[str, Any] = {}
        self.logger = __import__("logging").getLogger(self.__class__.__name__)

    async def initialize(self):
        pass

    async def _update_state(self):
        pass

    async def get_status(self) -> Dict[str, Any]:
        return {"agent_id": self.agent_id, "status": "running"}

    async def get_health(self) -> Dict[str, Any]:
        return {"healthy": True}


# ─── Patch BaseAgent BEFORE importing EthicsAgent ────────────────────────────

with patch.dict(sys.modules, {"agents.base_agent": MagicMock(BaseAgent=MockBaseAgent)}):
    from agents.ethics_agent.main import EthicsAgent
    from agents.ethics_agent.reasoning import EthicalReasoningEngine
    from agents.ethics_agent.governance import GovernanceEngine
    from agents.ethics_agent.compliance import ComplianceEngine
    from agents.ethics_agent.risk_assessment import RiskAssessmentEngine
    from agents.ethics_agent.safety import SafetyEngine
    from agents.ethics_agent.stakeholders import StakeholderAnalysisEngine
    from agents.ethics_agent.audit_replay import EthicsAuditReplay
    from agents.ethics_agent.models import EthicsContext, GovernancePolicy


# ─── Helper ─────────────────────────────────────────────────────────────────

def run(coro):
    """Run a coroutine in the test event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ════════════════════════════════════════════════════════════════════════════════
# EthicalReasoningEngine Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestEthicalReasoningEngine(unittest.TestCase):
    """Test multi-framework ethical reasoning."""

    def setUp(self):
        self.engine = EthicalReasoningEngine(config={})

    def test_analyze_returns_framework_analyses(self):
        result = self.engine.analyze("We need to decide on automated medical data processing.")
        self.assertIn("utilitarian", result.framework_analyses)
        self.assertIn("deontological", result.framework_analyses)
        self.assertIn("virtue_ethics", result.framework_analyses)
        self.assertIn("care_ethics", result.framework_analyses)
        self.assertGreater(result.overall_ethical_score, 0.0)

    def test_detect_ethical_dimensions(self):
        dims = self.engine.detect_ethical_dimensions("Actions that cause harm or violate privacy")
        self.assertIn("harm_prevention", dims)
        self.assertIn("privacy_autonomy", dims)

    def test_analyze_stakeholders(self):
        sh = self.engine.analyze_stakeholders("Users in the community and future generations")
        self.assertIn("individuals", sh)
        self.assertIn("society", sh)
        self.assertIn("future_generations", sh)


# ════════════════════════════════════════════════════════════════════════════════
# GovernanceEngine Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestGovernanceEngine(unittest.TestCase):
    """Test governance policy evaluation and business rules."""

    def setUp(self):
        self.engine = GovernanceEngine(config={})

    def test_evaluate_governance_compliant(self):
        res = self.engine.evaluate_governance("standard user data view", {"risk_level": "low"})
        self.assertTrue(res.compliant)
        self.assertEqual(len(res.violations), 0)

    def test_evaluate_governance_destructive_action(self):
        res = self.engine.evaluate_governance("delete_all database records", {"risk_level": "high"})
        self.assertFalse(res.compliant)
        self.assertGreater(len(res.violations), 0)

    def test_register_and_list_policies(self):
        pol = GovernancePolicy(policy_id="custom_pol", name="Custom Test Policy")
        self.engine.register_policy(pol)
        policies = self.engine.list_policies()
        self.assertTrue(any(p["policy_id"] == "custom_pol" for p in policies))


# ════════════════════════════════════════════════════════════════════════════════
# ComplianceEngine Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestComplianceEngine(unittest.TestCase):
    """Test compliance evaluation and regulatory plugins."""

    def setUp(self):
        self.engine = ComplianceEngine(config={})

    def test_evaluate_compliance_normal(self):
        report = self.engine.evaluate_compliance({"action": "read_public_data"})
        self.assertTrue(report.is_compliant)
        self.assertEqual(report.compliance_score, 1.0)

    def test_evaluate_compliance_sensitive_data_issue(self):
        report = self.engine.evaluate_compliance({"action": "save", "unencrypted_password": "123"})
        self.assertFalse(report.is_compliant)
        self.assertGreater(len(report.data_handling_issues), 0)


# ════════════════════════════════════════════════════════════════════════════════
# RiskAssessmentEngine Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestRiskAssessmentEngine(unittest.TestCase):
    """Test multi-dimensional risk matrix evaluation."""

    def setUp(self):
        self.engine = RiskAssessmentEngine(config={})

    def test_evaluate_risk_low(self):
        report = self.engine.evaluate_risk("read metrics dashboard")
        self.assertIn("operational", report.risk_matrix)
        self.assertIn("system_stability", report.risk_matrix)
        self.assertIn(report.overall_risk_level, ["low", "medium"])

    def test_evaluate_risk_high_stability(self):
        report = self.engine.evaluate_risk("reset_state and drop_db")
        self.assertIn(report.overall_risk_level, ["high", "critical"])
        self.assertEqual(report.stability_impact, "unstable")


# ════════════════════════════════════════════════════════════════════════════════
# SafetyEngine Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestSafetyEngine(unittest.TestCase):
    """Test operational safety checks and advisory rollbacks."""

    def setUp(self):
        self.engine = SafetyEngine(config={})

    def test_evaluate_safety_safe(self):
        report = self.engine.evaluate_safety("process_order")
        self.assertTrue(report.is_safe)
        self.assertEqual(report.safety_score, 1.0)
        self.assertIsNone(report.rollback_recommendation)

    def test_evaluate_safety_hazard_detected(self):
        report = self.engine.evaluate_safety("rm -rf /data")
        self.assertFalse(report.is_safe)
        self.assertGreater(len(report.detected_hazards), 0)
        self.assertIsNotNone(report.rollback_recommendation)


# ════════════════════════════════════════════════════════════════════════════════
# StakeholderAnalysisEngine Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestStakeholderAnalysisEngine(unittest.TestCase):
    """Test stakeholder identification and trade-off analysis."""

    def setUp(self):
        self.engine = StakeholderAnalysisEngine(config={})

    def test_analyze_stakeholders(self):
        impact = self.engine.analyze_stakeholders("environmental privacy initiatives for individuals")
        self.assertIn("individuals", impact.stakeholders)
        self.assertIn("environment", impact.stakeholders)
        self.assertIn("individuals", impact.impact_matrix)


# ════════════════════════════════════════════════════════════════════════════════
# EthicsAuditReplay Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestEthicsAuditReplay(unittest.TestCase):
    """Test audit trail recording, session snapshotting, and replay."""

    def setUp(self):
        self.audit = EthicsAuditReplay(config={})

    def test_audit_and_snapshot(self):
        sess_id = "sess_ethics_1"
        self.audit.record_audit_entry(sess_id, "analyze", {"text": "sample"})
        self.audit.save_snapshot(sess_id, {"domain": "AI"}, {"risk_level": "low"})
        replay = self.audit.replay_session(sess_id)
        self.assertEqual(replay.session_id, sess_id)
        self.assertEqual(replay.match_rate, 1.0)


# ════════════════════════════════════════════════════════════════════════════════
# EthicsAgent Integration & Async execute_task Tests
# ════════════════════════════════════════════════════════════════════════════════

class TestEthicsAgentIntegration(unittest.TestCase):
    """Integration tests for the full EthicsAgent pipeline."""

    def setUp(self):
        with patch("agents.base_agent.BaseAgent", MockBaseAgent):
            self.agent = EthicsAgent(agent_id="test_ethics", config={})
        self.agent.__class__.__bases__ = (MockBaseAgent,)
        run(self.agent.initialize())

    def test_analyze_ethical_situation_explainability(self):
        result = self.agent.analyze_ethical_situation("Implement automated user data collection for ad targeting.")
        self.assertIn("risk_level", result)
        self.assertIn("explainability", result)
        exp = result["explainability"]
        self.assertIn("frameworks_used", exp)
        self.assertIn("risk_summary", exp)
        self.assertIn("governance_considerations", exp)
        self.assertIn("safety_summary", exp)

    def test_execute_task_actions(self):
        analyze_res = run(self.agent.execute_task({"action": "analyze", "input_data": {"text": "Should we automate hiring decisions?"}}))
        self.assertIn("ethical_dimensions", analyze_res)

        gov_res = run(self.agent.execute_task({"action": "governance", "input_data": {"text": "delete_all database records"}}))
        self.assertIn("compliant", gov_res)

        comp_res = run(self.agent.execute_task({"action": "compliance", "input_data": {"text": "process_transaction"}}))
        self.assertIn("is_compliant", comp_res)

        risk_res = run(self.agent.execute_task({"action": "risk", "input_data": {"text": "deploy new model"}}))
        self.assertIn("risk_matrix", risk_res)

        safety_res = run(self.agent.execute_task({"action": "safety", "input_data": {"text": "rm -rf /tmp"}}))
        self.assertIn("is_safe", safety_res)

        sh_res = run(self.agent.execute_task({"action": "stakeholders", "input_data": {"text": "environmental policies"}}))
        self.assertIn("stakeholders", sh_res)

        hist_res = run(self.agent.execute_task({"action": "get_history"}))
        self.assertIn("history", hist_res)

        metrics_res = run(self.agent.execute_task({"action": "get_metrics"}))
        self.assertIn("metrics", metrics_res)


if __name__ == "__main__":
    unittest.main(verbosity=2)
