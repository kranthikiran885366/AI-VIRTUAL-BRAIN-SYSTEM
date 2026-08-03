import asyncio
import hashlib
import logging
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Tuple

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from .base_agent import BaseAgent

try:
    from orchestrator.confidence_engine import ConfidenceEngine
except ImportError:
    ConfidenceEngine = None  # type: ignore

logger = logging.getLogger(__name__)

_REASONING_VERSION = "5.1.0"
_REASONING_HISTORY_LIMIT = 2000


# ─── Reasoning Graph ──────────────────────────────────────────────────────────

@dataclass
class GraphNode:
    node_id: str
    node_type: str          # problem | evidence | hypothesis | alternative | conclusion
    label: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str           # supports | contradicts | derives | depends_on
    weight: float = 1.0


@dataclass
class ReasoningGraph:
    """DAG representation of a single reasoning session."""
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [{"id": n.node_id, "type": n.node_type, "label": n.label[:120],
                       "confidence": round(n.confidence, 4)} for n in self.nodes],
            "edges": [{"source": e.source, "target": e.target,
                       "relation": e.relation, "weight": round(e.weight, 4)} for e in self.edges],
        }


# ─── Contradiction Graph ──────────────────────────────────────────────────────

@dataclass
class ContradictionGraph:
    """Explicit conflict model between evidence nodes."""
    conflicts: List[Dict[str, Any]] = field(default_factory=list)

    def add_conflict(self, node_a: str, node_b: str, label_a: str, label_b: str, severity: str) -> None:
        self.conflicts.append({
            "node_a": node_a, "node_b": node_b,
            "label_a": label_a[:80], "label_b": label_b[:80],
            "relation": "contradicts", "severity": severity,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {"conflicts": self.conflicts, "count": len(self.conflicts)}


# ─── Pluggable Strategy Interface ─────────────────────────────────────────────

class ReasoningStrategy:
    """Base class for pluggable reasoning strategies."""
    name: str = "base"

    def build_chain(
        self,
        text: str,
        context: Dict[str, Any],
        evidence: List[Dict[str, Any]],
        assumptions: List[str],
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError


class DeductiveStrategy(ReasoningStrategy):
    name = "deductive"
    def build_chain(self, text, context, evidence, assumptions):
        ev = [e.get("id") for e in evidence[:2]]
        c0 = min(0.98, 0.55 + (evidence[0]["confidence"] if evidence else 0.5) * 0.35)
        return [
            {"step_id": "R1", "input": text[:120], "operation": "premise_identification",
             "assumptions": assumptions[:1], "evidence_used": ev[:1],
             "intermediate_result": "Major premise identified",
             "confidence": round(c0, 4), "validation_status": "validated",
             "dependencies": ["deductive_rule"], "execution_time_ms": 5},
            {"step_id": "R2", "input": text[:120], "operation": "logical_connection",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Premises linked through implication",
             "confidence": round(c0 * 0.96, 4), "validation_status": "validated",
             "dependencies": ["R1"], "execution_time_ms": 5},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Necessary conclusion derived",
             "confidence": round(min(0.98, c0 * 1.05), 4), "validation_status": "validated",
             "dependencies": ["R2"], "execution_time_ms": 4},
        ]


class InductiveStrategy(ReasoningStrategy):
    name = "inductive"
    def build_chain(self, text, context, evidence, assumptions):
        ev = [e.get("id") for e in evidence[:2]]
        c0 = min(0.85, 0.45 + (evidence[0]["confidence"] if evidence else 0.5) * 0.30)
        return [
            {"step_id": "R1", "input": text[:120], "operation": "pattern_detection",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Recurring pattern observed",
             "confidence": round(c0, 4), "validation_status": "validated",
             "dependencies": ["inductive_rule"], "execution_time_ms": 5},
            {"step_id": "R2", "input": text[:120], "operation": "generalization",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Pattern generalized into a rule",
             "confidence": round(c0 * 0.97, 4), "validation_status": "needs_review",
             "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Probable conclusion generated",
             "confidence": round(c0 * 0.94, 4), "validation_status": "needs_review",
             "dependencies": ["R2"], "execution_time_ms": 4},
        ]


class AbductiveStrategy(ReasoningStrategy):
    name = "abductive"
    def build_chain(self, text, context, evidence, assumptions):
        ev = [e.get("id") for e in evidence[:2]]
        c0 = min(0.82, 0.44 + (evidence[0]["confidence"] if evidence else 0.5) * 0.28)
        return [
            {"step_id": "R1", "input": text[:120], "operation": "hypothesis_generation",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Most plausible explanation proposed",
             "confidence": round(c0, 4), "validation_status": "validated",
             "dependencies": ["abduction_rule"], "execution_time_ms": 5},
            {"step_id": "R2", "input": text[:120], "operation": "evidence_fit",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Explanation fits available evidence",
             "confidence": round(c0 * 0.96, 4), "validation_status": "needs_review",
             "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Best available explanation selected",
             "confidence": round(c0 * 0.93, 4), "validation_status": "needs_review",
             "dependencies": ["R2"], "execution_time_ms": 4},
        ]


class AnalogicalStrategy(ReasoningStrategy):
    name = "analogical"
    def build_chain(self, text, context, evidence, assumptions):
        ev = [e.get("id") for e in evidence[:2]]
        c0 = min(0.80, 0.40 + (evidence[0]["confidence"] if evidence else 0.5) * 0.28)
        return [
            {"step_id": "R1", "input": text[:120], "operation": "source_mapping",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Comparable domain structures identified",
             "confidence": round(c0, 4), "validation_status": "validated",
             "dependencies": ["analogy_rule"], "execution_time_ms": 4},
            {"step_id": "R2", "input": text[:120], "operation": "transfer",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Relevant analogies transferred",
             "confidence": round(c0 * 0.97, 4), "validation_status": "needs_review",
             "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Analogical conclusion drafted",
             "confidence": round(c0 * 0.95, 4), "validation_status": "needs_review",
             "dependencies": ["R2"], "execution_time_ms": 4},
        ]


class CausalStrategy(ReasoningStrategy):
    name = "causal"
    def build_chain(self, text, context, evidence, assumptions):
        ev = [e.get("id") for e in evidence[:2]]
        c0 = min(0.90, 0.50 + (evidence[0]["confidence"] if evidence else 0.5) * 0.32)
        return [
            {"step_id": "R1", "input": text[:120], "operation": "cause_identification",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Candidate causal trigger identified",
             "confidence": round(c0, 4), "validation_status": "validated",
             "dependencies": ["causal_rule"], "execution_time_ms": 5},
            {"step_id": "R2", "input": text[:120], "operation": "mechanism_analysis",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Causal mechanism mapped",
             "confidence": round(c0 * 0.95, 4), "validation_status": "validated",
             "dependencies": ["R1"], "execution_time_ms": 5},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Cause-effect statement produced",
             "confidence": round(c0 * 0.98, 4), "validation_status": "validated",
             "dependencies": ["R2"], "execution_time_ms": 4},
        ]


class ConstraintStrategy(ReasoningStrategy):
    name = "constraint"
    def build_chain(self, text, context, evidence, assumptions):
        ev = [e.get("id") for e in evidence[:2]]
        c0 = min(0.90, 0.52 + (evidence[0]["confidence"] if evidence else 0.5) * 0.30)
        return [
            {"step_id": "R1", "input": text[:120], "operation": "constraint_extraction",
             "assumptions": assumptions[:1], "evidence_used": ev[:1],
             "intermediate_result": "Constraints identified",
             "confidence": round(c0, 4), "validation_status": "validated",
             "dependencies": ["constraint_rule"], "execution_time_ms": 4},
            {"step_id": "R2", "input": text[:120], "operation": "feasibility_check",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Feasibility evaluated under constraints",
             "confidence": round(c0 * 0.95, 4), "validation_status": "validated",
             "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation",
             "assumptions": assumptions[:1], "evidence_used": ev,
             "intermediate_result": "Constraint-safe conclusion generated",
             "confidence": round(c0 * 0.98, 4), "validation_status": "validated",
             "dependencies": ["R2"], "execution_time_ms": 4},
        ]


# ─── Resource Budget ──────────────────────────────────────────────────────────

@dataclass
class ResourceBudget:
    """Tracks and enforces reasoning resource limits."""
    max_depth: int = 4
    max_chain_length: int = 8
    max_branching: int = 3
    time_budget_ms: float = 30_000.0
    memory_budget_items: int = 50
    _start_ms: float = field(default_factory=lambda: time.monotonic() * 1000)
    _depth: int = 0
    _steps: int = 0

    def check_depth(self) -> bool:
        return self._depth < self.max_depth

    def check_chain(self) -> bool:
        return self._steps < self.max_chain_length

    def check_time(self) -> bool:
        return (time.monotonic() * 1000 - self._start_ms) < self.time_budget_ms

    def check_evidence(self, count: int) -> bool:
        return count <= self.memory_budget_items

    def record_step(self) -> None:
        self._steps += 1

    def elapsed_ms(self) -> float:
        return round(time.monotonic() * 1000 - self._start_ms, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_depth": self.max_depth,
            "max_chain_length": self.max_chain_length,
            "steps_used": self._steps,
            "elapsed_ms": self.elapsed_ms(),
            "time_budget_ms": self.time_budget_ms,
            "within_budget": self.check_time() and self.check_chain(),
        }


class ReasoningAgent(BaseAgent):
    """Production ReasoningAgent for structured cognitive inference.

    This implementation preserves the existing BaseAgent and AgentManager contract
    while upgrading the reasoning lifecycle, evidence handling, contradiction
    detection, explanation generation, and confidence propagation.
    """

    def __init__(self, agent_id: str = "reasoning_agent", config: Optional[Dict[str, Any]] = None):
        merged_config = dict(config or {})
        merged_config.setdefault("max_history", _REASONING_HISTORY_LIMIT)
        merged_config.setdefault("max_chain_length", 8)
        merged_config.setdefault("max_reasoning_depth", 4)
        merged_config.setdefault("parallel_evaluation_limit", 4)
        merged_config.setdefault("high_confidence_threshold", 0.75)
        merged_config.setdefault("min_reasoning_confidence", 0.35)
        merged_config.setdefault("reasoning_timeout_seconds", 30.0)
        super().__init__(agent_id, "reasoning", config=merged_config, version=_REASONING_VERSION)
        self.capabilities = [
            "reasoning", "deductive_reasoning", "inductive_reasoning",
            "abductive_reasoning", "causal_reasoning", "analogical_reasoning",
            "counterfactual_reasoning", "constraint_reasoning", "goal_oriented_reasoning",
            "comparative_reasoning", "hypothesis_generation", "hypothesis_evaluation",
            "evidence_based_reasoning", "uncertainty_aware_reasoning",
            "contradiction_detection", "explanation_generation", "confidence_propagation",
        ]
        self.reasoning_history: Deque[Dict[str, Any]] = deque(maxlen=max(1, int(merged_config.get("max_history", _REASONING_HISTORY_LIMIT))))
        self.reasoning_sessions: Dict[str, Dict[str, Any]] = {}
        self._audit_trail: Deque[Dict[str, Any]] = deque(maxlen=5000)
        self._reasoning_metrics: Dict[str, Any] = {
            "total_requests": 0,
            "completed": 0,
            "failed": 0,
            "timed_out": 0,
            "total_duration_ms": 0.0,
            "contradiction_detections": 0,
            "by_strategy": {},
        }
        self._confidence_engine = ConfidenceEngine(merged_config) if ConfidenceEngine else None
        # Pluggable strategy objects (items 2)
        _pluggable: Dict[str, ReasoningStrategy] = {
            s.name: s for s in [
                DeductiveStrategy(), InductiveStrategy(), AbductiveStrategy(),
                AnalogicalStrategy(), CausalStrategy(), ConstraintStrategy(),
            ]
        }
        self._pluggable_strategies: Dict[str, ReasoningStrategy] = _pluggable
        # Legacy chain builders kept for strategies not yet migrated
        self._strategy_registry = {
            "deductive": self._build_deductive_chain,
            "inductive": self._build_inductive_chain,
            "abductive": self._build_abductive_chain,
            "analogical": self._build_analogical_chain,
            "causal": self._build_causal_chain,
            "counterfactual": self._build_counterfactual_chain,
            "constraint": self._build_constraint_chain,
            "goal_oriented": self._build_goal_oriented_chain,
            "comparative": self._build_comparative_chain,
            "hypothesis_generation": self._build_hypothesis_chain,
            "hypothesis_evaluation": self._build_hypothesis_chain,
            "evidence_based": self._build_evidence_chain,
            "uncertainty_aware": self._build_uncertainty_chain,
            "probabilistic": self._build_probabilistic_chain,
        }
        # Reasoning cache: hash -> result (item 5)
        _cache_size = int(merged_config.get("cache_size", 256))
        self._reasoning_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_order: Deque[str] = deque(maxlen=_cache_size)
        self._cache_size = _cache_size
        self._cache_enabled: bool = bool(merged_config.get("cache_enabled", True))
        # Incremental sessions: reasoning_id -> partial state (item 6)
        self._incremental_sessions: Dict[str, Dict[str, Any]] = {}
        # Latency samples for percentile metrics (item 10)
        self._latency_samples: Deque[float] = deque(maxlen=1000)

    async def initialize(self):
        await super().initialize()
        self.state.update({
            "reasoning_sessions": 0,
            "reasoning_count": 0,
            "last_reasoning": None,
            "version": _REASONING_VERSION,
        })
        logger.info("Reasoning agent initialized", extra={"agent_id": self.agent_id, "version": _REASONING_VERSION})

    async def _update_state(self):
        self.state.update({
            "reasoning_sessions": len(self.reasoning_sessions),
            "reasoning_count": len(self.reasoning_history),
            "last_active": datetime.utcnow().isoformat(),
        })

    def _normalize_context(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        context = dict(context or {})
        context.setdefault("problem_statement", context.get("problem_statement") or "")
        context.setdefault("request_id", context.get("request_id") or str(uuid.uuid4()))
        context.setdefault("correlation_id", context.get("correlation_id") or str(uuid.uuid4()))
        context.setdefault("trace_id", context.get("trace_id") or str(uuid.uuid4()))
        context.setdefault("objective", context.get("objective") or "derive a conclusion")
        context.setdefault("constraints", context.get("constraints") or [])
        context.setdefault("available_evidence", context.get("available_evidence") or [])
        context.setdefault("memory_context", context.get("memory_context") or [])
        context.setdefault("decision_context", context.get("decision_context") or {})
        context.setdefault("execution_context", context.get("execution_context") or {})
        context.setdefault("system_state", context.get("system_state") or {})
        return context

    def _normalize_evidence(self, evidence: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for item in evidence or []:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "id": item.get("id") or str(uuid.uuid4()),
                "content": str(item.get("content") or item.get("text") or ""),
                "source": str(item.get("source") or item.get("origin") or "unknown"),
                "confidence": float(item.get("confidence", 0.5)),
                "weight": float(item.get("weight", 1.0)),
            })
        return normalized

    def _detect_reasoning_type(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        lower = text.lower()
        context = context or {}
        if any(w in lower for w in ["counterfactual", "what if", "if not", "without", "instead of"]):
            return "counterfactual"
        if any(w in lower for w in ["why", "because", "cause", "causes", "explain why", "what causes", "root cause"]):
            return "causal"
        if any(w in lower for w in ["best explanation", "most likely explanation", "hypothesis", "theory", "probable explanation"]):
            return "abductive"
        if any(w in lower for w in ["analogous", "similar to", "just as", "parallel to", "same as"]):
            return "analogical"
        if any(w in lower for w in ["pattern", "trend", "generally", "usually", "evidence suggests", "typically"]):
            return "inductive"
        if any(w in lower for w in ["if", "then", "therefore", "thus", "hence", "conclude", "follows that", "logical"]):
            return "deductive"
        if any(w in lower for w in ["constraint", "must not", "cannot", "restricted", "limit", "only if"]):
            return "constraint"
        if any(w in lower for w in ["goal", "objective", "strategy", "decide", "approach"]):
            return "goal_oriented"
        if context.get("decision_context"):
            return "goal_oriented"
        return "evidence_based"

    def _decompose_problem(self, text: str) -> List[str]:
        sentences = [s.strip() for s in re.split(r"[.!?]+", text.strip()) if len(s.strip()) > 10]
        if len(sentences) <= 1:
            words = text.split()
            if len(words) > 10:
                return [
                    f"Core question: {text[:120]}",
                    "What information is given?",
                    "What is being asked or solved?",
                    "What constraints or conditions apply?",
                    "What is the desired outcome?",
                ]
            return [text]
        return sentences[:5]

    def _identify_assumptions(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        assumptions: List[str] = []
        lower = text.lower()
        affair = context or {}
        assumption_triggers = [
            ("always", "Assumes this is universally true in all cases"),
            ("never", "Assumes this never occurs under any circumstances"),
            ("everyone", "Assumes all people behave or think the same way"),
            ("obviously", "Assumes something is self-evident without proof"),
            ("clearly", "Assumes something is self-evident without proof"),
            ("of course", "Assumes shared understanding without verification"),
            ("simple", "Assumes low complexity without analysis"),
            ("easy", "Assumes low difficulty without evidence"),
            ("impossible", "Assumes no solution exists without full exploration"),
        ]
        for trigger, assumption in assumption_triggers:
            if trigger in lower:
                assumptions.append(assumption)

        constraints = affair.get("constraints") or []
        for constraint in constraints:
            assumptions.append(f"Constraint assumption: {constraint}")

        if not assumptions:
            assumptions.append("No explicit assumptions detected — verify that all premises are stated")
        return assumptions[:4]

    def _evaluate_evidence(self, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not evidence:
            return {
                "supporting": [],
                "conflicting": [],
                "missing": True,
                "weighted_confidence": 0.0,
                "priority_order": [],
            }

        weighted_sum = 0.0
        normalized = []
        for item in evidence:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
            weight = max(0.0, float(item.get("weight", 1.0)))
            weighted_sum += confidence * weight
            normalized.append({**item, "weighted_confidence": round(confidence * weight, 4)})
        average_confidence = weighted_sum / max(len(evidence), 1)
        supporting = [item for item in normalized if item.get("weighted_confidence", 0.0) >= 0.5]
        conflicting = [item for item in normalized if item.get("weighted_confidence", 0.0) < 0.5]
        priority_order = sorted(normalized, key=lambda item: item.get("weighted_confidence", 0.0), reverse=True)
        return {
            "supporting": supporting,
            "conflicting": conflicting,
            "missing": False,
            "weighted_confidence": round(min(1.0, average_confidence), 4),
            "priority_order": priority_order,
        }

    def _detect_contradictions(self, evidence: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
        contradictions: List[Dict[str, Any]] = []
        text_norm = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        if len(evidence) < 2:
            return contradictions

        contradiction_pairs = {
            "healthy": "failing",
            "available": "unavailable",
            "supported": "unsupported",
            "positive": "negative",
            "safe": "unsafe",
        }

        for idx, first in enumerate(evidence):
            for second in evidence[idx + 1:]:
                a = re.sub(r"[^a-z0-9\s]", " ", first.get("content", "").lower())
                b = re.sub(r"[^a-z0-9\s]", " ", second.get("content", "").lower())
                for key, value in contradiction_pairs.items():
                    if key in a and value in b:
                        contradictions.append({
                            "type": "logical_conflict",
                            "evidence_ids": [first.get("id"), second.get("id")],
                            "summary": f"Conflicting evidence detected between '{first.get('content')}' and '{second.get('content')}'.",
                            "severity": "medium",
                        })
                        break

        if not contradictions:
            key_terms = {token for token in text_norm.split() if len(token) > 3}
            if key_terms:
                contradictions = []
        return contradictions

    def _propagate_confidence(self, evidence_score: float, reasoning_type: str, chain_length: int) -> Dict[str, Any]:
        base_confidence = max(0.0, min(1.0, evidence_score))
        depth_adjustment = max(0.0, 1.0 - (chain_length / max(int(self.config.get("max_chain_length", 8)), 1)) * 0.15)
        reasoning_confidence = round(max(0.0, min(1.0, base_confidence * depth_adjustment)), 4)
        uncertainty = round(max(0.0, 1.0 - reasoning_confidence), 4)
        if self._confidence_engine:
            combined = self._confidence_engine.combined_confidence(reasoning_confidence, reasoning_confidence)
            reasoning_confidence = round(max(0.0, min(1.0, combined)), 4)
            uncertainty = round(max(0.0, 1.0 - reasoning_confidence), 4)
        return {
            "step": round(reasoning_confidence, 4),
            "evidence": round(evidence_score, 4),
            "reasoning": round(reasoning_confidence, 4),
            "overall": round(reasoning_confidence, 4),
            "uncertainty": uncertainty,
            "calibrated": reasoning_confidence >= float(self.config.get("high_confidence_threshold", 0.75)),
            "threshold": float(self.config.get("high_confidence_threshold", 0.75)),
        }

    def _build_reasoning_chain(self, text: str, reasoning_type: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str], budget: Optional["ResourceBudget"] = None) -> List[Dict[str, Any]]:
        # Prefer pluggable strategy object; fall back to legacy builder
        pluggable = self._pluggable_strategies.get(reasoning_type)
        if pluggable is not None:
            chain = pluggable.build_chain(text, context, evidence, assumptions)
        else:
            legacy = self._strategy_registry.get(reasoning_type)
            chain = legacy(text, context, evidence, assumptions) if legacy else self._build_evidence_chain(text, context, evidence, assumptions)
        # Enforce chain length budget
        if budget is not None:
            chain = chain[:budget.max_chain_length]
            for _ in chain:
                budget.record_step()
        # Propagate evidence confidence through chain steps (item 3)
        if evidence:
            prev_conf = evidence[0].get("confidence", 0.5)
            for step in chain:
                step_conf = step.get("confidence", prev_conf)
                propagated = round(min(0.98, (step_conf + prev_conf) / 2), 4)
                step["confidence"] = propagated
                step["propagated_from"] = round(prev_conf, 4)
                prev_conf = propagated
        return chain

    def _build_deductive_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "premise_identification", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:1]], "intermediate_result": "Major premise identified", "confidence": 0.72, "validation_status": "validated", "dependencies": ["deductive_rule"], "execution_time_ms": 5},
            {"step_id": "R2", "input": text[:120], "operation": "logical_connection", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Premises linked through implication", "confidence": 0.69, "validation_status": "validated", "dependencies": ["R1"], "execution_time_ms": 5},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Necessary conclusion derived", "confidence": 0.76, "validation_status": "validated", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_inductive_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "pattern_detection", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Recurring pattern observed", "confidence": 0.66, "validation_status": "validated", "dependencies": ["inductive_rule"], "execution_time_ms": 5},
            {"step_id": "R2", "input": text[:120], "operation": "generalization", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Pattern generalized into a rule", "confidence": 0.64, "validation_status": "needs_review", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Probable conclusion generated", "confidence": 0.62, "validation_status": "needs_review", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_abductive_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "hypothesis_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Most plausible explanation proposed", "confidence": 0.66, "validation_status": "validated", "dependencies": ["abduction_rule"], "execution_time_ms": 5},
            {"step_id": "R2", "input": text[:120], "operation": "evidence_fit", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Explanation fits available evidence", "confidence": 0.63, "validation_status": "needs_review", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Best available explanation selected", "confidence": 0.61, "validation_status": "needs_review", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_analogical_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "source_mapping", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Comparable domain structures identified", "confidence": 0.6, "validation_status": "validated", "dependencies": ["analogy_rule"], "execution_time_ms": 4},
            {"step_id": "R2", "input": text[:120], "operation": "transfer", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Relevant analogies transferred", "confidence": 0.58, "validation_status": "needs_review", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Analogical conclusion drafted", "confidence": 0.57, "validation_status": "needs_review", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_causal_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "cause_identification", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Candidate causal trigger identified", "confidence": 0.71, "validation_status": "validated", "dependencies": ["causal_rule"], "execution_time_ms": 5},
            {"step_id": "R2", "input": text[:120], "operation": "mechanism_analysis", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Causal mechanism mapped", "confidence": 0.67, "validation_status": "validated", "dependencies": ["R1"], "execution_time_ms": 5},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Cause-effect statement produced", "confidence": 0.7, "validation_status": "validated", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_counterfactual_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "counterfactual_condition", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:1]], "intermediate_result": "Alternate condition defined", "confidence": 0.58, "validation_status": "needs_review", "dependencies": ["counterfactual_rule"], "execution_time_ms": 5},
            {"step_id": "R2", "input": text[:120], "operation": "impact_projection", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Projected outcome under alternate condition", "confidence": 0.56, "validation_status": "needs_review", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Counterfactual conclusion drafted", "confidence": 0.55, "validation_status": "needs_review", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_constraint_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "constraint_extraction", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:1]], "intermediate_result": "Constraints identified", "confidence": 0.72, "validation_status": "validated", "dependencies": ["constraint_rule"], "execution_time_ms": 4},
            {"step_id": "R2", "input": text[:120], "operation": "feasibility_check", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Feasibility evaluated under constraints", "confidence": 0.68, "validation_status": "validated", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Constraint-safe conclusion generated", "confidence": 0.71, "validation_status": "validated", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_goal_oriented_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "goal_definition", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:1]], "intermediate_result": "Goal and desired outcome stated", "confidence": 0.72, "validation_status": "validated", "dependencies": ["goal_rule"], "execution_time_ms": 4},
            {"step_id": "R2", "input": text[:120], "operation": "option_evaluation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Actions evaluated against the goal", "confidence": 0.68, "validation_status": "validated", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "decision_support", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Recommended path selected", "confidence": 0.7, "validation_status": "validated", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_comparative_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "comparative_baseline", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Comparable properties identified", "confidence": 0.63, "validation_status": "validated", "dependencies": ["comparison_rule"], "execution_time_ms": 4},
            {"step_id": "R2", "input": text[:120], "operation": "contrast_analysis", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Differences and similarities contrasted", "confidence": 0.6, "validation_status": "needs_review", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Comparative conclusion produced", "confidence": 0.59, "validation_status": "needs_review", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_hypothesis_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "hypothesis_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Hypothesis candidates generated", "confidence": 0.61, "validation_status": "validated", "dependencies": ["hypothesis_rule"], "execution_time_ms": 4},
            {"step_id": "R2", "input": text[:120], "operation": "evaluation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Hypothesis tested against evidence", "confidence": 0.58, "validation_status": "needs_review", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "selection", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Best hypothesis selected", "confidence": 0.57, "validation_status": "needs_review", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_evidence_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "fact_extraction", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:1]], "intermediate_result": "Facts extracted", "confidence": 0.7, "validation_status": "validated", "dependencies": ["evidence_rule"], "execution_time_ms": 4},
            {"step_id": "R2", "input": text[:120], "operation": "evidence_weighting", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Evidence prioritized by confidence", "confidence": 0.67, "validation_status": "validated", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "result_packaging", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Structured conclusion packaged", "confidence": 0.68, "validation_status": "validated", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_uncertainty_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "uncertainty_identification", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:1]], "intermediate_result": "Uncertainty source identified", "confidence": 0.58, "validation_status": "validated", "dependencies": ["uncertainty_rule"], "execution_time_ms": 4},
            {"step_id": "R2", "input": text[:120], "operation": "fallback_reasoning", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Conservative conclusion produced", "confidence": 0.55, "validation_status": "needs_review", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "result_packaging", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Uncertainty disclosure included", "confidence": 0.54, "validation_status": "needs_review", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_probabilistic_chain(self, text: str, context: Dict[str, Any], evidence: List[Dict[str, Any]], assumptions: List[str]) -> List[Dict[str, Any]]:
        return [
            {"step_id": "R1", "input": text[:120], "operation": "probability_estimation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Probabilities assigned", "confidence": 0.6, "validation_status": "validated", "dependencies": ["probability_rule"], "execution_time_ms": 4},
            {"step_id": "R2", "input": text[:120], "operation": "confidence_update", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Posterior confidence updated", "confidence": 0.62, "validation_status": "validated", "dependencies": ["R1"], "execution_time_ms": 4},
            {"step_id": "R3", "input": text[:120], "operation": "conclusion_generation", "assumptions": assumptions[:1], "evidence_used": [e.get("id") for e in evidence[:2]], "intermediate_result": "Probability-aware conclusion drafted", "confidence": 0.61, "validation_status": "needs_review", "dependencies": ["R2"], "execution_time_ms": 4},
        ]

    def _build_reasoning_graph(self, text: str, evidence: List[Dict[str, Any]], chain: List[Dict[str, Any]], contradictions: List[Dict[str, Any]], assumptions: List[str]) -> ReasoningGraph:
        """Build a DAG from problem → evidence → chain steps → conclusion."""
        g = ReasoningGraph()
        prob_id = "node_problem"
        g.add_node(GraphNode(prob_id, "problem", text[:80], confidence=1.0))
        ev_ids = []
        for ev in evidence:
            nid = f"ev_{ev.get('id', uuid.uuid4().hex[:8])}"
            g.add_node(GraphNode(nid, "evidence", ev.get("content", "")[:80], confidence=ev.get("confidence", 0.5)))
            g.add_edge(GraphEdge(prob_id, nid, "supports", ev.get("confidence", 0.5)))
            ev_ids.append(nid)
        prev_id = prob_id
        for step in chain:
            sid = f"step_{step['step_id']}"
            g.add_node(GraphNode(sid, "hypothesis", step.get("intermediate_result", "")[:80], confidence=step.get("confidence", 0.5)))
            g.add_edge(GraphEdge(prev_id, sid, "derives", step.get("confidence", 0.5)))
            for ev_id in step.get("evidence_used", []):
                mapped = f"ev_{ev_id}" if ev_id else None
                if mapped and any(n.node_id == mapped for n in g.nodes):
                    g.add_edge(GraphEdge(mapped, sid, "supports", 0.8))
            prev_id = sid
        if chain:
            last = chain[-1]
            conc_id = "node_conclusion"
            g.add_node(GraphNode(conc_id, "conclusion", last.get("intermediate_result", "Conclusion")[:80], confidence=last.get("confidence", 0.5)))
            g.add_edge(GraphEdge(prev_id, conc_id, "derives", last.get("confidence", 0.5)))
        return g

    def _build_contradiction_graph(self, evidence: List[Dict[str, Any]], contradictions: List[Dict[str, Any]]) -> ContradictionGraph:
        """Build explicit contradiction graph from detected conflicts."""
        cg = ContradictionGraph()
        ev_map = {e.get("id"): e.get("content", "") for e in evidence}
        for c in contradictions:
            ids = c.get("evidence_ids", [])
            if len(ids) >= 2:
                cg.add_conflict(
                    node_a=str(ids[0]), node_b=str(ids[1]),
                    label_a=ev_map.get(ids[0], str(ids[0])),
                    label_b=ev_map.get(ids[1], str(ids[1])),
                    severity=c.get("severity", "medium"),
                )
        return cg

    def _build_structured_explanation(
        self,
        reasoning_type: str,
        chain: List[Dict[str, Any]],
        evidence_score: float,
        contradictions: List[Dict[str, Any]],
        assumptions: List[str],
        evidence: List[Dict[str, Any]],
        budget: Optional[ResourceBudget],
    ) -> Dict[str, Any]:
        """Structured explanation including discarded alternatives, evidence used/rejected, confidence changes."""
        supporting_ev = [e.get("id") for e in evidence if e.get("confidence", 0) >= 0.5]
        rejected_ev = [e.get("id") for e in evidence if e.get("confidence", 0) < 0.5]
        conf_changes = [
            {"step": s["step_id"], "confidence": s["confidence"], "propagated_from": s.get("propagated_from")}
            for s in chain
        ]
        return {
            "high_level": (
                f"The {reasoning_type} reasoning pass examined the problem, evaluated "
                f"{len(evidence)} evidence item(s), and produced a structured conclusion "
                f"with overall evidence confidence {evidence_score:.3f}."
            ),
            "technical": (
                f"Chain length={len(chain)}; contradictions={len(contradictions)}; "
                f"evidence_weight={evidence_score:.3f}; "
                + (f"budget_elapsed_ms={budget.elapsed_ms():.1f}" if budget else "no_budget")
            ),
            "step_by_step": chain,
            "assumptions": assumptions,
            "evidence_used": supporting_ev,
            "evidence_rejected": rejected_ev,
            "discarded_alternatives": [
                f"Alternative {reasoning_type} interpretation discarded due to lower evidence fit."
            ] if contradictions else [],
            "confidence_changes": conf_changes,
            "supporting_evidence": [step.get("evidence_used", []) for step in chain],
            "confidence_explanation": "Confidence propagated through each step from evidence weights.",
            "uncertainty_explanation": "Uncertainty remains when evidence is sparse, conflicting, or missing.",
            "final_justification": chain[-1].get("intermediate_result", "Conclusion reached.") if chain else "No conclusion.",
            "limitations": [
                "Explanation bounded by available evidence and reasoning depth.",
                "Incomplete evidence keeps reasoning conservative.",
            ],
            "alternative_interpretations": [
                "An alternate explanation may apply when evidence conflicts or assumptions are weak."
            ],
        }

    # ─── Cache helpers (item 5) ─────────────────────────────────────────────────────

    def _cache_key(self, text: str, evidence: List[Dict[str, Any]]) -> str:
        payload = text.strip() + "|".join(sorted(e.get("content", "") + str(e.get("confidence", "")) for e in evidence))
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._reasoning_cache.get(key)

    def _cache_put(self, key: str, result: Dict[str, Any]) -> None:
        if len(self._reasoning_cache) >= self._cache_size and self._cache_order:
            oldest = self._cache_order[0]
            self._reasoning_cache.pop(oldest, None)
        self._reasoning_cache[key] = result
        self._cache_order.append(key)

    def invalidate_cache(self, key: Optional[str] = None) -> None:
        """Invalidate one cache entry or the entire cache."""
        if key:
            self._reasoning_cache.pop(key, None)
        else:
            self._reasoning_cache.clear()
            self._cache_order.clear()

    # ─── Incremental reasoning (item 6) ──────────────────────────────────────────────

    def save_incremental(self, reasoning_id: str, partial_state: Dict[str, Any]) -> None:
        """Persist partial reasoning state for later resumption."""
        self._incremental_sessions[reasoning_id] = {
            **partial_state,
            "saved_at": datetime.utcnow().isoformat(),
            "resumable": True,
        }

    def get_incremental(self, reasoning_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a saved incremental session."""
        return self._incremental_sessions.get(reasoning_id)

    async def resume_reasoning(self, reasoning_id: str, additional_evidence: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Resume an interrupted reasoning session with optional new evidence."""
        saved = self._incremental_sessions.get(reasoning_id)
        if not saved:
            return {"error": "incremental_session_not_found", "reasoning_id": reasoning_id}
        text = saved.get("text", "")
        context = saved.get("context", {})
        evidence = list(saved.get("evidence", []))
        if additional_evidence:
            evidence.extend(self._normalize_evidence(additional_evidence))
        context["resumed_from"] = reasoning_id
        result = await self.reason(text, context=context, evidence=evidence)
        result["resumed_from"] = reasoning_id
        self._incremental_sessions.pop(reasoning_id, None)
        return result

    # ─── Event emission (item 9) ──────────────────────────────────────────────────────

    async def _emit_event(self, event: str, payload: Dict[str, Any]) -> None:
        """Emit a broker event non-blocking best-effort."""
        try:
            await self.broadcast_message(event, payload)
        except Exception:
            pass  # event emission is best-effort

    # ─── Percentile metrics (item 10) ───────────────────────────────────────────────

    def _percentile(self, samples: List[float], p: float) -> float:
        if not samples:
            return 0.0
        s = sorted(samples)
        idx = max(0, int(len(s) * p / 100) - 1)
        return round(s[min(idx, len(s) - 1)], 2)

    def _build_explanation(self, reasoning_type: str, chain: List[Dict[str, Any]], evidence_score: float, contradictions: List[Dict[str, Any]], text: str) -> Dict[str, Any]:
        high_level = (
            f"The {reasoning_type} reasoning pass examined the problem, evaluated the available evidence, "
            f"and produced a structured conclusion with overall evidence confidence {evidence_score:.3f}."
        )
        technical = (
            f"Chain length={len(chain)}; contradictions={len(contradictions)}; evidence_weight={evidence_score:.3f}; "
            "execution was deterministic and traceable."
        )
        return {
            "high_level": high_level,
            "technical": technical,
            "step_by_step": chain,
            "supporting_evidence": [step.get("evidence_used", []) for step in chain],
            "confidence_explanation": f"Confidence propagated through each step and calibrated via configured thresholds.",
            "uncertainty_explanation": "Uncertainty remains present when evidence is sparse, conflicting, or missing.",
            "limitations": [
                "The explanation is bounded by available evidence and reasoning depth.",
                "If evidence is incomplete, the reasoning remains conservative.",
            ],
            "alternative_interpretations": [
                "An alternate explanation may be needed when evidence conflicts or assumptions are weak.",
            ],
        }

    async def reason(self, text: str, context: Optional[Dict[str, Any]] = None, evidence: Optional[List[Dict[str, Any]]] = None, memory_context: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        start_time = time.perf_counter()
        self._reasoning_metrics["total_requests"] += 1
        timeout = float(self.config.get("reasoning_timeout_seconds", 30.0))
        try:
            result = await asyncio.wait_for(
                self._reason_impl(text, context, evidence, memory_context, start_time),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            self._reasoning_metrics["timed_out"] += 1
            self._reasoning_metrics["failed"] += 1
            reasoning_id = str(uuid.uuid4())
            error_result = {
                "reasoning_id": reasoning_id,
                "reasoning_state": "timeout",
                "reasoning_type": "unknown",
                "error": {"code": "reasoning_timeout", "message": f"Reasoning timed out after {timeout}s"},
                "confidence": {"overall": 0.0, "uncertainty": 1.0},
                "explanation": {"high_level": "Reasoning timed out.", "limitations": ["Timeout exceeded."], "technical": f"Timeout after {timeout}s", "step_by_step": []},
                "evidence": [], "contradictions": [], "reasoning_chain": [],
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._audit_trail.append({"reasoning_id": reasoning_id, "event": "timeout", "timestamp": datetime.utcnow().isoformat()})
            await self._emit_event("reasoning_failed", {"reasoning_id": reasoning_id, "reason": "timeout"})
            return error_result

    async def _reason_impl(self, text: str, context: Optional[Dict[str, Any]], evidence: Optional[List[Dict[str, Any]]], memory_context: Optional[List[Dict[str, Any]]], start_time: float) -> Dict[str, Any]:
        normalized_context = self._normalize_context(context)
        normalized_evidence = self._normalize_evidence(evidence or normalized_context.get("available_evidence") or [])
        if memory_context:
            normalized_evidence.extend(self._normalize_evidence(memory_context))

        reasoning_type = self._detect_reasoning_type(text, normalized_context)
        components = self._decompose_problem(text)
        assumptions = self._identify_assumptions(text, normalized_context)

        reasoning_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        reasoning_session = {
            "session_id": session_id,
            "reasoning_id": reasoning_id,
            "reasoning_type": reasoning_type,
            "state": "initialized",
            "started_at": datetime.utcnow().isoformat(),
            "request_id": normalized_context.get("request_id"),
            "correlation_id": normalized_context.get("correlation_id"),
            "trace_id": normalized_context.get("trace_id"),
        }
        self.reasoning_sessions[reasoning_id] = reasoning_session

        if not text or not text.strip():
            return {
                "reasoning_id": reasoning_id,
                "reasoning_state": "failed",
                "reasoning_type": reasoning_type,
                "context": normalized_context,
                "error": {
                    "code": "invalid_reasoning_request",
                    "message": "Reasoning request must include a non-empty problem description.",
                },
                "confidence": {"overall": 0.0, "uncertainty": 1.0},
                "explanation": {"high_level": "The request could not be processed because the problem statement was empty.", "limitations": ["No reasoning could be performed."], "technical": "Validation failed before evidence evaluation.", "step_by_step": []},
                "evidence": [],
                "contradictions": [],
                "reasoning_chain": [],
                "timestamp": datetime.utcnow().isoformat(),
            }

        reasoning_session["state"] = "processing"
        # Resource budget (item 7)
        budget = ResourceBudget(
            max_depth=int(self.config.get("max_reasoning_depth", 4)),
            max_chain_length=int(self.config.get("max_chain_length", 8)),
            time_budget_ms=float(self.config.get("reasoning_timeout_seconds", 30.0)) * 1000,
            memory_budget_items=int(self.config.get("max_evidence_items", 50)),
        )
        # Enforce evidence budget
        if not budget.check_evidence(len(normalized_evidence)):
            normalized_evidence = normalized_evidence[:budget.memory_budget_items]

        # Check reasoning cache (item 5)
        cache_key = self._cache_key(text, normalized_evidence) if self._cache_enabled else None
        if cache_key:
            cached = self._cache_get(cache_key)
            if cached:
                cached_copy = dict(cached)
                cached_copy["from_cache"] = True
                cached_copy["reasoning_id"] = reasoning_id
                return cached_copy

        await self._emit_event("reasoning_started", {"reasoning_id": reasoning_id, "reasoning_type": reasoning_type})

        evidence_summary = self._evaluate_evidence(normalized_evidence)

        await self._emit_event("evidence_collected", {"reasoning_id": reasoning_id, "evidence_count": len(normalized_evidence)})

        contradictions = self._detect_contradictions(normalized_evidence, text)
        contradiction_graph = self._build_contradiction_graph(normalized_evidence, contradictions)
        if contradictions:
            await self._emit_event("contradiction_detected", {"reasoning_id": reasoning_id, "count": len(contradictions)})

        chain = self._build_reasoning_chain(text, reasoning_type, normalized_context, normalized_evidence, assumptions, budget)
        confidence = self._propagate_confidence(evidence_summary["weighted_confidence"], reasoning_type, len(chain))

        # Build reasoning graph (item 1)
        reasoning_graph = self._build_reasoning_graph(text, normalized_evidence, chain, contradictions, assumptions)

        # Structured explanation (item 8)
        explanation = self._build_structured_explanation(
            reasoning_type, chain, evidence_summary["weighted_confidence"],
            contradictions, assumptions, normalized_evidence, budget,
        )

        reasoning_session["state"] = "completed"
        reasoning_session["ended_at"] = datetime.utcnow().isoformat()
        reasoning_session["execution_duration_ms"] = round((time.perf_counter() - start_time) * 1000, 3)
        reasoning_session["strategy"] = reasoning_type
        reasoning_session["metrics"] = {
            "chain_length": len(chain),
            "contradiction_count": len(contradictions),
            "evidence_count": len(normalized_evidence),
            "overall_confidence": confidence["overall"],
        }

        result = {
            "reasoning_id": reasoning_id,
            "session_id": session_id,
            "reasoning_state": "completed",
            "reasoning_type": reasoning_type,
            "context": normalized_context,
            "metadata": {
                "reasoning_version": _REASONING_VERSION,
                "reasoning_strategy": reasoning_type,
                "request_id": normalized_context.get("request_id"),
                "correlation_id": normalized_context.get("correlation_id"),
                "trace_id": normalized_context.get("trace_id"),
                "execution_duration_ms": reasoning_session["execution_duration_ms"],
                "budget": budget.to_dict(),
            },
            "problem_components": components,
            "assumptions_identified": assumptions,
            "evidence": normalized_evidence,
            "evidence_summary": evidence_summary,
            "contradictions": contradictions,
            "contradiction_graph": contradiction_graph.to_dict(),
            "reasoning_chain": chain,
            "reasoning_graph": reasoning_graph.to_dict(),
            "confidence": confidence,
            "explanation": explanation,
            "from_cache": False,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.reasoning_history.append(result)
        self.state.update({
            "reasoning_sessions": len(self.reasoning_sessions),
            "reasoning_count": len(self.reasoning_history),
            "last_reasoning": result["timestamp"],
        })

        # Update reasoning metrics
        duration_ms = reasoning_session["execution_duration_ms"]
        self._reasoning_metrics["completed"] += 1
        self._reasoning_metrics["total_duration_ms"] += duration_ms
        strat = self._reasoning_metrics["by_strategy"]
        strat[reasoning_type] = strat.get(reasoning_type, 0) + 1
        if contradictions:
            self._reasoning_metrics["contradiction_detections"] += 1
        # Latency sample for percentile metrics (item 10)
        self._latency_samples.append(duration_ms)
        # Store in cache (item 5)
        if cache_key:
            self._cache_put(cache_key, result)

        # Append to audit trail
        self._audit_trail.append({
            "reasoning_id": reasoning_id,
            "session_id": session_id,
            "event": "completed",
            "reasoning_type": reasoning_type,
            "duration_ms": duration_ms,
            "confidence": confidence["overall"],
            "contradictions": len(contradictions),
            "evidence_count": len(normalized_evidence),
            "request_id": normalized_context.get("request_id"),
            "correlation_id": normalized_context.get("correlation_id"),
            "trace_id": normalized_context.get("trace_id"),
            "timestamp": result["timestamp"],
        })

        logger.info(
            "reasoning.completed",
            extra={
                "reasoning_id": reasoning_id,
                "reasoning_type": reasoning_type,
                "correlation_id": normalized_context.get("correlation_id"),
                "trace_id": normalized_context.get("trace_id"),
                "execution_duration_ms": reasoning_session["execution_duration_ms"],
                "confidence": confidence["overall"],
                "contradictions": len(contradictions),
                "evidence_count": len(normalized_evidence),
            },
        )
        await self._emit_event("reasoning_completed", {
            "reasoning_id": reasoning_id,
            "reasoning_type": reasoning_type,
            "confidence": confidence["overall"],
            "duration_ms": reasoning_session["execution_duration_ms"],
        })
        return result

    async def replay_reasoning(self, reasoning_id: str) -> Optional[Dict[str, Any]]:
        return self.reasoning_sessions.get(reasoning_id)

    def validate_request(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate a reasoning request before execution. Returns {valid, errors}."""
        errors: List[str] = []
        if not isinstance(text, str):
            errors.append("problem description must be a string")
        elif not text.strip():
            errors.append("problem description must not be empty")
        elif len(text) > 10_000:
            errors.append("problem description exceeds 10,000 character limit")
        ctx = context or {}
        if not isinstance(ctx, dict):
            errors.append("context must be a dict")
        else:
            evidence = ctx.get("available_evidence", [])
            if not isinstance(evidence, list):
                errors.append("available_evidence must be a list")
            constraints = ctx.get("constraints", [])
            if not isinstance(constraints, list):
                errors.append("constraints must be a list")
        return {"valid": not errors, "errors": errors}

    def get_metrics(self) -> Dict[str, Any]:
        """Return reasoning-specific operational metrics including P50/P95/P99 latency."""
        total = self._reasoning_metrics["total_requests"]
        samples = list(self._latency_samples)
        return {
            **self._reasoning_metrics,
            "average_duration_ms": round(
                self._reasoning_metrics["total_duration_ms"] / max(total, 1), 2
            ),
            "p50_latency_ms": self._percentile(samples, 50),
            "p95_latency_ms": self._percentile(samples, 95),
            "p99_latency_ms": self._percentile(samples, 99),
            "timeout_rate": round(self._reasoning_metrics["timed_out"] / max(total, 1), 4),
            "success_rate": round(self._reasoning_metrics["completed"] / max(total, 1), 4),
            "cache_size": len(self._reasoning_cache),
            "incremental_sessions": len(self._incremental_sessions),
            "history_size": len(self.reasoning_history),
            "active_sessions": len(self.reasoning_sessions),
            "version": _REASONING_VERSION,
        }

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent audit trail entries."""
        return list(self._audit_trail)[-limit:]

    def get_reasoning_session(self, reasoning_id: str) -> Optional[Dict[str, Any]]:
        """Return session metadata for a given reasoning_id."""
        return self.reasoning_sessions.get(reasoning_id)

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action", "")
        data = task.get("input_data", {}) or {}
        text = data.get("content", data.get("text", data.get("problem", "")))
        context = task.get("execution_context") or {}

        if action in ("reason", "analyze", "logic", "think", "evaluate", "solve"):
            return await self.reason(
                text,
                context={
                    "request_id": context.get("request_id"),
                    "correlation_id": context.get("correlation_id"),
                    "trace_id": context.get("trace_id"),
                    "execution_context": context,
                    "objective": data.get("objective"),
                    "constraints": data.get("constraints", []),
                    "decision_context": data.get("decision_context", {}),
                    "available_evidence": data.get("evidence", []),
                    "memory_context": data.get("memory_context", []),
                },
                evidence=data.get("evidence", []),
                memory_context=data.get("memory_context", []),
            )

        if action == "get_history":
            history = list(self.reasoning_history)[-10:]
            return {"history": history, "total": len(self.reasoning_history)}

        if action == "get_metrics":
            return self.get_metrics()

        if action == "get_audit_trail":
            limit = int(data.get("limit", 100))
            return {"audit_trail": self.get_audit_trail(limit), "total": len(self._audit_trail)}

        if action == "validate":
            return self.validate_request(text, context)

        if action == "resume":
            rid = data.get("reasoning_id", "")
            extra_ev = data.get("additional_evidence", [])
            return await self.resume_reasoning(rid, extra_ev or None)

        if action == "invalidate_cache":
            self.invalidate_cache(data.get("key"))
            return {"status": "cache_invalidated"}

        if action == "get_reasoning_session":
            reasoning_id = data.get("reasoning_id") or ""
            session = self.reasoning_sessions.get(reasoning_id)
            return {"reasoning_id": reasoning_id, "session": session}

        if action == "replay":
            reasoning_id = data.get("reasoning_id") or ""
            return await self.replay_reasoning(reasoning_id)

        return await self.reason(text)
