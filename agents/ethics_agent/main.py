"""
EthicsAgent Main Package Entry Point — Phase 11 Production Implementation.

Inherits from BaseAgent for lifecycle management (init, heartbeat, message bus,
health checks). Orchestrates the complete Ethics, Governance & Safety Engine:
  - Multi-Framework Ethical Reasoning (8 modular frameworks)
  - Production Governance Engine (policy evaluation, versioning, approvals)
  - Compliance Evaluation Engine (workflow, config, data handling, regulatory plugins)
  - Multi-Dimensional Risk Assessment Engine (9 risk matrix dimensions)
  - Operational Safety Assessment Engine (unsafe workflow detection, safeguards, advisory rollbacks)
  - Stakeholder & Trade-off Analysis Engine
  - Audit Trail, Session Snapshotting, Replay & Security Recovery
  - Observability & Explainable Output Generation
"""

import logging
import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from ..base_agent import BaseAgent  # type: ignore

from .models import (
    EthicsContext,
    EthicalAnalysisResult,
    GovernanceResult,
    ComplianceReport,
    RiskReport,
    SafetyReport,
    StakeholderImpact,
    EthicsSession,
    EthicsMetrics,
)
from .reasoning import EthicalReasoningEngine
from .governance import GovernanceEngine
from .compliance import ComplianceEngine
from .risk_assessment import RiskAssessmentEngine
from .safety import SafetyEngine
from .stakeholders import StakeholderAnalysisEngine
from .audit_replay import EthicsAuditReplay


class EthicsAgent(BaseAgent):
    """
    Production Ethics, Governance & Safety Agent.

    Lifecycle:
      - initialize()     : called on startup by orchestrator / agent manager
      - _process_messages(): per-tick hook for message bus processing
      - execute_task()   : orchestrator task dispatch
      - shutdown()       : cleanup on orchestrator teardown
    """

    def __init__(self, agent_id: str = "ethics_agent", config: Dict[str, Any] = None):
        super().__init__(agent_id=agent_id, agent_type="ethics")
        self.config = config or {}
        self.analysis_history: List[Dict[str, Any]] = []
        self._max_history = self.config.get("storage", {}).get("max_history_entries", 200)

        # Operational metrics tracking
        self.metrics = EthicsMetrics()

        # Active session registry
        self._sessions: Dict[str, EthicsSession] = {}

        # Sub-engine instances
        self.reasoning_engine = EthicalReasoningEngine(self.config)
        self.governance_engine = GovernanceEngine(self.config)
        self.compliance_engine = ComplianceEngine(self.config)
        self.risk_engine = RiskAssessmentEngine(self.config)
        self.safety_engine = SafetyEngine(self.config)
        self.stakeholder_engine = StakeholderAnalysisEngine(self.config)
        self.audit_replay_engine = EthicsAuditReplay(self.config)

    async def initialize(self):
        """Initialize agent — connect to message broker and set up sub-engines."""
        try:
            await super().initialize()
        except Exception:
            pass  # MockBaseAgent fallback

        if not hasattr(self, "logger"):
            self.logger = logging.getLogger(f"EthicsAgent.{self.agent_id}")

        self.state.update({
            "analyses_performed": 0,
            "governance_evaluations": 0,
            "compliance_checks": 0,
            "safety_evaluations": 0,
            "last_active": datetime.utcnow().isoformat(),
        })
        self.logger.info(f"EthicsAgent '{self.agent_id}' fully initialized with all Phase 11 engines.")

    async def _process_messages(self):
        """Custom per-tick hook."""
        await asyncio.sleep(0)

    async def _update_state(self):
        await super()._update_state()
        self.state["analyses_performed"] = len(self.analysis_history)
        self.state["governance_evaluations"] = self.metrics.governance_checks
        self.state["compliance_checks"] = self.metrics.compliance_evaluations
        self.state["safety_evaluations"] = self.metrics.safety_evaluations
        self.state["last_active"] = datetime.utcnow().isoformat()

    # ─── Legacy Helper Methods (100% Backward Compatibility) ──────────────────

    def _detect_ethical_dimensions(self, text: str) -> List[str]:
        return self.reasoning_engine.detect_ethical_dimensions(text)

    def _analyze_stakeholders(self, text: str) -> List[str]:
        return self.reasoning_engine.analyze_stakeholders(text)

    def _generate_ethical_analysis(self, text: str, dimensions: List[str], stakeholders: List[str]) -> Dict[str, Any]:
        result_obj = self.reasoning_engine.analyze(text)
        return result_obj.to_dict()

    def _generate_recommendation(self, risk_level: str, dimensions: List[str]) -> str:
        return self.reasoning_engine._generate_recommendation(risk_level, dimensions, 0.7)

    def _generate_questions(self, dimensions: List[str]) -> List[str]:
        return self.reasoning_engine._generate_questions(dimensions)

    # ─── Public Analysis Entry Point ──────────────────────────────────────────

    def analyze_ethical_situation(self, situation: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Full ethics & governance evaluation pipeline:
          validate request → run multi-framework reasoning → evaluate governance →
          assess risk & safety → analyze stakeholders → record audit & snapshot → format explainable output.
        """
        start_time = time.time()
        ctx = context or {}
        session_id = str(uuid.uuid4())
        req_id = ctx.get("request_id", str(uuid.uuid4()))
        corr_id = ctx.get("correlation_id", str(uuid.uuid4()))
        tr_id = ctx.get("trace_id", str(uuid.uuid4()))

        # Request Validation
        valid, err_msg = self.audit_replay_engine.validate_request({"situation": situation, **ctx})
        if not valid:
            self.metrics.error_count += 1
            return {"error": err_msg, "risk_level": "high"}

        try:
            # 1. Multi-Framework Ethical Reasoning
            analysis = self.reasoning_engine.analyze(situation, ctx)

            # 2. Governance Evaluation
            gov_res = self.governance_engine.evaluate_governance(situation, {"risk_level": analysis.risk_level})

            # 3. Compliance Check
            comp_res = self.compliance_engine.evaluate_compliance({"action": situation}, ctx)

            # 4. Multi-Dimensional Risk Assessment
            risk_res = self.risk_engine.evaluate_risk(situation, ctx)

            # 5. Operational Safety Assessment
            safety_res = self.safety_engine.evaluate_safety(situation, ctx)

            # 6. Stakeholder & Trade-off Analysis
            stakeholder_res = self.stakeholder_engine.analyze_stakeholders(situation, ctx)

            # Update Metrics
            processing_ms = round((time.time() - start_time) * 1000, 2)
            self.metrics.total_sessions += 1
            self.metrics.total_analyses += 1
            self.metrics.governance_checks += 1
            self.metrics.compliance_evaluations += 1
            self.metrics.risk_assessments += 1
            self.metrics.safety_evaluations += 1
            self.metrics.stakeholder_analyses += 1
            self.metrics.total_processing_ms += processing_ms

            # History Update
            analysis_dict = analysis.to_dict()
            self.analysis_history.append({"text": situation[:100], "analysis": analysis_dict, "timestamp": datetime.utcnow().isoformat()})
            if len(self.analysis_history) > self._max_history:
                self.analysis_history = self.analysis_history[-self._max_history:]

            # Record Audit Trail & Save Snapshot
            self.audit_replay_engine.record_audit_entry(
                session_id=session_id,
                action="analyze_ethical_situation",
                input_summary={"situation": situation[:100], "domain": ctx.get("domain", "general")},
                frameworks_used=list(analysis.framework_analyses.keys()),
                reasoning_summary=f"Analyzed situation across {len(analysis.framework_analyses)} frameworks. Overall score: {analysis.overall_ethical_score}.",
                risk_level=analysis.risk_level,
                recommendation_rationale=analysis.recommendation,
                confidence=analysis.confidence,
                request_id=req_id,
                correlation_id=corr_id,
                trace_id=tr_id,
            )
            self.audit_replay_engine.save_snapshot(session_id=session_id, context=ctx, analysis_results=analysis_dict)

            # Format Explainable Output Structure
            explainability = {
                "analysis_summary": f"Ethical evaluation completed for situation in domain '{ctx.get('domain', 'general')}'. Overall score: {analysis.overall_ethical_score}.",
                "frameworks_used": list(analysis.framework_analyses.keys()),
                "confidence": analysis.confidence,
                "stakeholders_considered": analysis.stakeholders_affected,
                "risk_summary": {
                    "risk_level": analysis.risk_level,
                    "overall_risk_score": risk_res.risk_score,
                    "risk_matrix": risk_res.risk_matrix,
                },
                "governance_considerations": {
                    "compliant": gov_res.compliant,
                    "policies_checked": gov_res.policies_checked,
                    "approvals_required": gov_res.approvals_required,
                },
                "safety_summary": {
                    "is_safe": safety_res.is_safe,
                    "safety_score": safety_res.safety_score,
                    "safeguards": safety_res.execution_safeguards,
                    "rollback_recommendation": safety_res.rollback_recommendation,
                },
                "compliance_summary": {
                    "is_compliant": comp_res.is_compliant,
                    "compliance_score": comp_res.compliance_score,
                },
                "processing_stages": [
                    "1. Multi-Framework Reasoning",
                    "2. Governance Policy Evaluation",
                    "3. Compliance Audit",
                    "4. Multi-Dimensional Risk Scoring",
                    "5. Operational Safety Assessment",
                    "6. Stakeholder Trade-Off Analysis",
                ],
                "limitations": ["Ethical recommendations are advisory and designed to support governance."],
                "alternative_recommendations": analysis.questions_to_consider,
            }

            return {
                **analysis_dict,
                "session_id": session_id,
                "request_id": req_id,
                "correlation_id": corr_id,
                "trace_id": tr_id,
                "governance": gov_res.to_dict(),
                "compliance": comp_res.to_dict(),
                "risk_report": risk_res.to_dict(),
                "safety_report": safety_res.to_dict(),
                "stakeholder_impact": stakeholder_res.to_dict(),
                "explainability": explainability,
                "processing_ms": processing_ms,
            }
        except Exception as e:
            self.logger.error(f"Error in analyze_ethical_situation: {e}")
            self.metrics.error_count += 1
            return self.audit_replay_engine.recover_from_error(e, ctx, lambda s, c: self._generate_ethical_analysis(s, ["general_ethics"], ["general_stakeholders"]))

    # ─── Async Task Dispatch (Orchestrator Contract) ──────────────────────────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Async task dispatch called by orchestrator AgentManager and API gateway routes."""
        action = (task.get("action", "") or "").lower()
        data = task.get("input_data", {}) or {}

        req_id = task.get("request_id") or data.get("request_id")
        corr_id = task.get("correlation_id") or data.get("correlation_id")
        tr_id = task.get("trace_id") or data.get("trace_id")

        text = data.get("content", data.get("text", data.get("situation", data.get("proposed_action", ""))))
        ctx = {"domain": data.get("domain", "general"), "request_id": req_id, "correlation_id": corr_id, "trace_id": tr_id, **data}

        # ── Multi-Framework Analysis ─────────────────────────────────────
        if action in ("analyze", "evaluate", "assess", "check", "review", "ethical_analysis"):
            return self.analyze_ethical_situation(text, ctx)

        # ── Governance Evaluation ─────────────────────────────────────────
        if action in ("governance", "evaluate_governance"):
            self.metrics.governance_checks += 1
            gov_res = self.governance_engine.evaluate_governance(text, ctx)
            return gov_res.to_dict()

        # ── Compliance Audit ──────────────────────────────────────────────
        if action in ("compliance", "evaluate_compliance"):
            self.metrics.compliance_evaluations += 1
            comp_res = self.compliance_engine.evaluate_compliance({"action": text}, ctx)
            return comp_res.to_dict()

        # ── Risk Assessment ───────────────────────────────────────────────
        if action in ("risk", "evaluate_risk"):
            self.metrics.risk_assessments += 1
            risk_res = self.risk_engine.evaluate_risk(text, ctx)
            return risk_res.to_dict()

        # ── Operational Safety Assessment ────────────────────────────────
        if action in ("safety", "evaluate_safety"):
            self.metrics.safety_evaluations += 1
            safety_res = self.safety_engine.evaluate_safety(text, ctx)
            return safety_res.to_dict()

        # ── Stakeholder Analysis ──────────────────────────────────────────
        if action in ("stakeholders", "analyze_stakeholders"):
            self.metrics.stakeholder_analyses += 1
            sh_res = self.stakeholder_engine.analyze_stakeholders(text, ctx)
            return sh_res.to_dict()

        # ── History & Metrics ─────────────────────────────────────────────
        if action == "get_history":
            return {"history": self.analysis_history[-10:], "total": len(self.analysis_history)}

        if action == "get_metrics":
            return {"metrics": self.metrics.as_dict()}

        if action == "replay_session":
            self.metrics.replay_count += 1
            session_id = data.get("session_id", "")
            if session_id:
                replay_res = self.audit_replay_engine.replay_session(session_id, lambda c: self.analyze_ethical_situation(c.get("situation", ""), c))
                return replay_res.to_dict()
            return {"error": "session_id required for replay"}

        if action == "get_status":
            return await self.get_status()
        if action == "get_health":
            return await self.get_health()

        # ── Default Fallback Handler ──────────────────────────────────────
        return self.analyze_ethical_situation(text or "general ethical evaluation", ctx)
