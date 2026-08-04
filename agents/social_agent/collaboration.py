"""
Multi-Agent Collaboration Engine — Phase 13

Implements:
- Agent discovery and capability lookup (via AgentManager)
- Parallel collaborative task execution with dependency tracking
- Consensus engine (majority, weighted, confidence-weighted, expert-preference)
- Negotiation engine (resource/task/priority/deadline negotiation)
- Conflict resolution (confidence-priority, ethics-first, recency, majority)
- Shared execution context
- Observability: structured logs, collaboration/consensus/negotiation IDs
- All communication via existing MessageBroker (no direct coupling)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Consensus Engine ───────────────────────────────────────────────────────────

class ConsensusEngine:
    """
    Production consensus engine.
    Supports: majority, weighted, confidence_weighted, expert_preference, fallback.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config.get("consensus", {})
        self._history: Deque[Dict[str, Any]] = deque(
            maxlen=int(self._cfg.get("history_limit", 500))
        )
        self._metrics: Dict[str, int] = {
            "total": 0, "majority": 0, "weighted": 0,
            "confidence_weighted": 0, "expert_preference": 0, "fallback": 0,
        }

    def reach_consensus(
        self,
        votes: List[Dict[str, Any]],
        policy: Optional[str] = None,
        expert_agents: Optional[List[str]] = None,
        consensus_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reach consensus from a list of agent votes.

        Each vote: {"agent_id": str, "value": Any, "confidence": float, "weight": float}
        Returns: {"consensus_value": Any, "policy": str, "confidence": float, ...}
        """
        if not votes:
            return self._empty_result(consensus_id, correlation_id)

        consensus_id = consensus_id or str(uuid.uuid4())
        policy = policy or self._cfg.get("default_policy", "confidence_weighted")
        min_votes = int(self._cfg.get("min_votes", 1))

        if len(votes) < min_votes:
            policy = self._cfg.get("fallback_policy", "majority")

        result = self._apply_policy(votes, policy, expert_agents or [])

        # Fallback if primary policy yields no result
        if result["consensus_value"] is None and policy != "majority":
            result = self._apply_policy(votes, "majority", [])
            result["policy"] = f"fallback_majority"
            self._metrics["fallback"] += 1

        record = {
            "consensus_id": consensus_id,
            "correlation_id": correlation_id,
            "policy": result["policy"],
            "consensus_value": result["consensus_value"],
            "confidence": result["confidence"],
            "vote_count": len(votes),
            "timestamp": _utcnow(),
        }
        self._history.append(record)
        self._metrics["total"] += 1
        self._metrics[result["policy"].replace("fallback_", "")] = (
            self._metrics.get(result["policy"].replace("fallback_", ""), 0) + 1
        )

        logger.debug(
            "consensus.reached consensus_id=%s policy=%s value=%s confidence=%.3f",
            consensus_id, result["policy"], result["consensus_value"], result["confidence"],
        )
        return {**record, "votes": votes}

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self._history)[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self._metrics)

    def _apply_policy(
        self, votes: List[Dict[str, Any]], policy: str, expert_agents: List[str]
    ) -> Dict[str, Any]:
        if policy == "majority":
            return self._majority(votes)
        if policy == "weighted":
            return self._weighted(votes)
        if policy == "confidence_weighted":
            return self._confidence_weighted(votes)
        if policy == "expert_preference":
            return self._expert_preference(votes, expert_agents)
        return self._majority(votes)

    def _majority(self, votes: List[Dict[str, Any]]) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for v in votes:
            key = str(v.get("value", ""))
            counts[key] = counts.get(key, 0) + 1
        best = max(counts, key=lambda k: counts[k])
        confidence = counts[best] / len(votes)
        return {"consensus_value": best, "policy": "majority", "confidence": round(confidence, 4)}

    def _weighted(self, votes: List[Dict[str, Any]]) -> Dict[str, Any]:
        scores: Dict[str, float] = {}
        total_weight = 0.0
        for v in votes:
            key = str(v.get("value", ""))
            w = float(v.get("weight", 1.0))
            scores[key] = scores.get(key, 0.0) + w
            total_weight += w
        if not scores:
            return {"consensus_value": None, "policy": "weighted", "confidence": 0.0}
        best = max(scores, key=lambda k: scores[k])
        confidence = scores[best] / total_weight if total_weight > 0 else 0.0
        return {"consensus_value": best, "policy": "weighted", "confidence": round(confidence, 4)}

    def _confidence_weighted(self, votes: List[Dict[str, Any]]) -> Dict[str, Any]:
        scores: Dict[str, float] = {}
        total_conf = 0.0
        for v in votes:
            key = str(v.get("value", ""))
            c = float(v.get("confidence", 0.5))
            scores[key] = scores.get(key, 0.0) + c
            total_conf += c
        if not scores:
            return {"consensus_value": None, "policy": "confidence_weighted", "confidence": 0.0}
        best = max(scores, key=lambda k: scores[k])
        confidence = scores[best] / total_conf if total_conf > 0 else 0.0
        return {"consensus_value": best, "policy": "confidence_weighted", "confidence": round(confidence, 4)}

    def _expert_preference(
        self, votes: List[Dict[str, Any]], expert_agents: List[str]
    ) -> Dict[str, Any]:
        expert_votes = [v for v in votes if v.get("agent_id") in expert_agents]
        if expert_votes:
            return {**self._confidence_weighted(expert_votes), "policy": "expert_preference"}
        return {**self._confidence_weighted(votes), "policy": "expert_preference"}

    def _empty_result(
        self, consensus_id: Optional[str], correlation_id: Optional[str]
    ) -> Dict[str, Any]:
        return {
            "consensus_id": consensus_id or str(uuid.uuid4()),
            "correlation_id": correlation_id,
            "policy": "none",
            "consensus_value": None,
            "confidence": 0.0,
            "vote_count": 0,
            "timestamp": _utcnow(),
            "votes": [],
        }


# ── Negotiation Engine ─────────────────────────────────────────────────────────

class NegotiationEngine:
    """
    Production negotiation engine.
    Supports: resource, task, priority, deadline, responsibility negotiation.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config.get("negotiation", {})
        self._history: Deque[Dict[str, Any]] = deque(
            maxlen=int(self._cfg.get("history_limit", 500))
        )
        self._metrics: Dict[str, int] = {
            "total": 0, "agreements": 0, "failures": 0, "timeouts": 0,
        }

    def negotiate(
        self,
        proposals: List[Dict[str, Any]],
        negotiation_type: str = "resource",
        negotiation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Negotiate between agent proposals.

        Each proposal: {"agent_id": str, "value": Any, "priority": float,
                        "confidence": float, "constraints": dict}
        Returns: {"agreement": Any, "agreed": bool, "rounds": int, ...}
        """
        negotiation_id = negotiation_id or str(uuid.uuid4())
        max_rounds = int(self._cfg.get("max_rounds", 5))
        agreement_threshold = float(self._cfg.get("agreement_threshold", 0.6))
        concession_rate = float(self._cfg.get("concession_rate", 0.1))

        if not proposals:
            return self._no_agreement(negotiation_id, correlation_id, 0, "no_proposals")

        current_proposals = [dict(p) for p in proposals]
        rounds = 0
        agreement = None

        for round_num in range(1, max_rounds + 1):
            rounds = round_num
            # Check if proposals converge
            values = [str(p.get("value", "")) for p in current_proposals]
            if len(set(values)) == 1:
                agreement = current_proposals[0].get("value")
                break

            # Confidence-weighted midpoint for numeric values
            numeric_vals = []
            for p in current_proposals:
                try:
                    numeric_vals.append((float(p["value"]), float(p.get("confidence", 0.5))))
                except (TypeError, ValueError):
                    pass

            if len(numeric_vals) == len(current_proposals):
                total_conf = sum(c for _, c in numeric_vals)
                if total_conf > 0:
                    midpoint = sum(v * c for v, c in numeric_vals) / total_conf
                    # Apply concessions toward midpoint
                    for p in current_proposals:
                        try:
                            old_val = float(p["value"])
                            p["value"] = old_val + concession_rate * (midpoint - old_val)
                        except (TypeError, ValueError):
                            pass
                    # Check convergence
                    new_vals = [float(p["value"]) for p in current_proposals]
                    spread = max(new_vals) - min(new_vals)
                    if spread < agreement_threshold:
                        agreement = sum(new_vals) / len(new_vals)
                        break
            else:
                # Non-numeric: pick highest-priority proposal
                best = max(current_proposals, key=lambda p: float(p.get("priority", 0.5)))
                agreement = best.get("value")
                break

        agreed = agreement is not None
        record = {
            "negotiation_id": negotiation_id,
            "correlation_id": correlation_id,
            "negotiation_type": negotiation_type,
            "agreed": agreed,
            "agreement": agreement,
            "rounds": rounds,
            "proposal_count": len(proposals),
            "timestamp": _utcnow(),
        }
        self._history.append(record)
        self._metrics["total"] += 1
        if agreed:
            self._metrics["agreements"] += 1
        else:
            self._metrics["failures"] += 1

        logger.debug(
            "negotiation.result negotiation_id=%s agreed=%s rounds=%d",
            negotiation_id, agreed, rounds,
        )
        return {**record, "proposals": proposals}

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self._history)[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self._metrics)

    def _no_agreement(
        self, negotiation_id: str, correlation_id: Optional[str], rounds: int, reason: str
    ) -> Dict[str, Any]:
        return {
            "negotiation_id": negotiation_id,
            "correlation_id": correlation_id,
            "agreed": False,
            "agreement": None,
            "rounds": rounds,
            "reason": reason,
            "timestamp": _utcnow(),
            "proposals": [],
        }


# ── Conflict Resolution ────────────────────────────────────────────────────────

class ConflictResolver:
    """
    Resolves conflicting agent recommendations with explainable decisions.
    Strategies: confidence_priority, ethics_first, recency, majority.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config.get("conflict_resolution", {})
        self._strategy = self._cfg.get("strategy", "confidence_priority")
        self._history: Deque[Dict[str, Any]] = deque(
            maxlen=int(self._cfg.get("history_limit", 200))
        )

    def resolve(
        self,
        conflicts: List[Dict[str, Any]],
        strategy: Optional[str] = None,
        conflict_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve conflicting recommendations.

        Each conflict item: {"agent_id": str, "recommendation": Any,
                             "confidence": float, "priority": float,
                             "timestamp": str, "domain": str}
        """
        conflict_id = conflict_id or str(uuid.uuid4())
        strategy = strategy or self._strategy

        if not conflicts:
            return {
                "conflict_id": conflict_id,
                "resolved": False,
                "resolution": None,
                "strategy": strategy,
                "explanation": "No conflicts provided",
                "timestamp": _utcnow(),
            }

        if strategy == "confidence_priority":
            winner = max(conflicts, key=lambda c: float(c.get("confidence", 0.0)))
            explanation = (
                f"Selected recommendation from '{winner.get('agent_id')}' "
                f"with highest confidence {winner.get('confidence', 0):.3f}"
            )
        elif strategy == "ethics_first":
            ethics = [c for c in conflicts if c.get("agent_id") == self._cfg.get("ethics_agent", "ethics_agent")]
            winner = ethics[0] if ethics else max(conflicts, key=lambda c: float(c.get("confidence", 0.0)))
            explanation = (
                f"Ethics agent recommendation prioritized" if ethics
                else f"No ethics agent vote; fell back to confidence_priority"
            )
        elif strategy == "recency":
            def _ts(c: Dict[str, Any]) -> str:
                return c.get("timestamp", "")
            winner = max(conflicts, key=_ts)
            explanation = f"Most recent recommendation from '{winner.get('agent_id')}' selected"
        elif strategy == "majority":
            counts: Dict[str, int] = {}
            for c in conflicts:
                key = str(c.get("recommendation", ""))
                counts[key] = counts.get(key, 0) + 1
            best_key = max(counts, key=lambda k: counts[k])
            winner = next(c for c in conflicts if str(c.get("recommendation", "")) == best_key)
            explanation = f"Majority recommendation '{best_key}' selected ({counts[best_key]}/{len(conflicts)} votes)"
        else:
            winner = conflicts[0]
            explanation = "Default: first conflict item selected"

        record = {
            "conflict_id": conflict_id,
            "correlation_id": correlation_id,
            "resolved": True,
            "resolution": winner.get("recommendation"),
            "winning_agent": winner.get("agent_id"),
            "strategy": strategy,
            "explanation": explanation,
            "conflict_count": len(conflicts),
            "timestamp": _utcnow(),
        }
        self._history.append(record)
        logger.debug(
            "conflict.resolved conflict_id=%s strategy=%s winner=%s",
            conflict_id, strategy, winner.get("agent_id"),
        )
        return record

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self._history)[-limit:]


# ── Collaborative Task Executor ────────────────────────────────────────────────

class CollaborativeExecutor:
    """
    Executes tasks across multiple agents in parallel with:
    - Dependency tracking
    - Timeout handling
    - Failure recovery
    - Shared execution context
    - Execution metrics
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config.get("collaboration", {})
        self._max_parallel = int(self._cfg.get("max_parallel_agents", 10))
        self._task_timeout = float(self._cfg.get("task_timeout_seconds", 30.0))
        self._metrics: Dict[str, Any] = {
            "total_collaborations": 0,
            "successful": 0,
            "partial": 0,
            "failed": 0,
            "total_latency_ms": 0.0,
        }

    async def execute_parallel(
        self,
        agent_tasks: List[Dict[str, Any]],
        agent_manager: Any,
        shared_context: Optional[Dict[str, Any]] = None,
        collaboration_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute tasks across multiple agents in parallel.

        Each agent_task: {"agent_name": str, "action": str, "input_data": dict,
                          "depends_on": list[str], "required": bool}
        Returns: {"results": dict, "success": bool, "partial": bool, ...}
        """
        collaboration_id = collaboration_id or str(uuid.uuid4())
        start_ms = _now_ms()

        if not agent_tasks:
            return self._empty_result(collaboration_id, correlation_id, trace_id)

        # Resolve execution order respecting dependencies
        ordered = self._topological_sort(agent_tasks)
        results: Dict[str, Any] = {}
        failed_agents: List[str] = []

        # Execute in dependency-respecting batches
        for batch in ordered:
            batch_coros = []
            for task in batch:
                agent_name = task.get("agent_name", "")
                # Skip if a required dependency failed
                deps = task.get("depends_on", [])
                if any(d in failed_agents for d in deps):
                    failed_agents.append(agent_name)
                    results[agent_name] = {"status": "skipped", "reason": "dependency_failed"}
                    continue
                batch_coros.append(
                    self._execute_single(agent_name, task, agent_manager, shared_context or {})
                )

            if batch_coros:
                batch_results = await asyncio.gather(*batch_coros, return_exceptions=True)
                for task, res in zip(
                    [t for t in batch if t.get("agent_name") not in failed_agents],
                    batch_results,
                ):
                    agent_name = task.get("agent_name", "")
                    if isinstance(res, Exception):
                        failed_agents.append(agent_name)
                        results[agent_name] = {"status": "error", "error": str(res)}
                    else:
                        results[agent_name] = res
                        if res.get("status") in ("error", "timeout", "failed"):
                            if task.get("required", False):
                                failed_agents.append(agent_name)

        latency_ms = _now_ms() - start_ms
        total = len(agent_tasks)
        failed_count = len(failed_agents)
        success = failed_count == 0
        partial = 0 < failed_count < total

        self._metrics["total_collaborations"] += 1
        self._metrics["total_latency_ms"] += latency_ms
        if success:
            self._metrics["successful"] += 1
        elif partial:
            self._metrics["partial"] += 1
        else:
            self._metrics["failed"] += 1

        logger.debug(
            "collaboration.executed collaboration_id=%s agents=%d failed=%d latency_ms=%.1f",
            collaboration_id, total, failed_count, latency_ms,
        )
        return {
            "collaboration_id": collaboration_id,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "results": results,
            "success": success,
            "partial": partial,
            "failed_agents": failed_agents,
            "agent_count": total,
            "latency_ms": round(latency_ms, 2),
            "timestamp": _utcnow(),
        }

    def get_metrics(self) -> Dict[str, Any]:
        m = dict(self._metrics)
        total = m.get("total_collaborations", 0)
        m["avg_latency_ms"] = round(
            m["total_latency_ms"] / total if total > 0 else 0.0, 2
        )
        return m

    async def _execute_single(
        self,
        agent_name: str,
        task: Dict[str, Any],
        agent_manager: Any,
        shared_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        timeout = float(task.get("timeout", self._task_timeout))
        task_payload = {
            "action": task.get("action", "process"),
            "input_data": {**task.get("input_data", {}), "shared_context": shared_context},
        }
        try:
            if agent_manager is None:
                return {"status": "error", "error": "agent_manager_unavailable"}
            result = await asyncio.wait_for(
                agent_manager.execute_agent_with_timeout(agent_name, task_payload, timeout_seconds=timeout),
                timeout=timeout + 1.0,
            )
            return result if isinstance(result, dict) else {"status": "completed", "result": result}
        except asyncio.TimeoutError:
            return {"status": "timeout", "error": f"Agent '{agent_name}' timed out after {timeout}s"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _topological_sort(
        self, tasks: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Return tasks grouped into dependency-ordered batches."""
        name_to_task = {t.get("agent_name", ""): t for t in tasks}
        in_degree: Dict[str, int] = {t.get("agent_name", ""): 0 for t in tasks}
        for t in tasks:
            for dep in t.get("depends_on", []):
                if dep in in_degree:
                    in_degree[t.get("agent_name", "")] = in_degree.get(t.get("agent_name", ""), 0) + 1

        batches: List[List[Dict[str, Any]]] = []
        remaining = set(name_to_task.keys())
        while remaining:
            batch_names = {n for n in remaining if in_degree.get(n, 0) == 0}
            if not batch_names:
                # Cycle detected — add all remaining as one batch
                batch_names = remaining
            batch = [name_to_task[n] for n in batch_names]
            batches.append(batch)
            remaining -= batch_names
            for t in batch:
                for other in remaining:
                    if t.get("agent_name") in name_to_task.get(other, {}).get("depends_on", []):
                        in_degree[other] = max(0, in_degree.get(other, 0) - 1)
        return batches

    def _empty_result(
        self,
        collaboration_id: str,
        correlation_id: Optional[str],
        trace_id: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "collaboration_id": collaboration_id,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "results": {},
            "success": True,
            "partial": False,
            "failed_agents": [],
            "agent_count": 0,
            "latency_ms": 0.0,
            "timestamp": _utcnow(),
        }


def _now_ms() -> float:
    return datetime.now(timezone.utc).timestamp() * 1000
