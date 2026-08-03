"""
Routing Engine — Phase 4

Production capability-based agent router.
Supports: single-agent, multi-agent, parallel, sequential, collaborative,
fallback, capability-based, priority-based, health-aware, load-aware,
availability-aware, timeout-aware, and dynamic routing.

No fixed keyword routing unless used as a configurable last-resort fallback.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .decision_context import (
    DecisionContext,
    DetectedIntent,
    ExecutionFeedback,
    IntentType,
    RoutingDecision,
    RoutingStrategy,
)
from .confidence_engine import ConfidenceEngine

logger = logging.getLogger(__name__)


@dataclass
class AgentNode:
    """A node in the multi-agent dependency graph."""
    agent: str
    depends_on: List[str] = field(default_factory=list)  # agents that must complete first
    decision: Optional["RoutingDecision"] = None


@dataclass
class MultiAgentPlan:
    """
    Execution plan for multi-agent coordination.
    Defines order, dependencies, and how results are aggregated.
    """
    nodes: List[AgentNode] = field(default_factory=list)
    # Aggregation strategy: 'first' | 'merge' | 'vote' | 'sequential'
    aggregation: str = "merge"
    # Agents that can run in parallel (no dependencies between them)
    parallel_groups: List[List[str]] = field(default_factory=list)

    def execution_order(self) -> List[List[str]]:
        """Topological sort — returns groups that can run in parallel."""
        remaining = {n.agent: set(n.depends_on) for n in self.nodes}
        order: List[List[str]] = []
        while remaining:
            ready = [a for a, deps in remaining.items() if not deps]
            if not ready:
                # Cycle or unresolvable — run all remaining together
                order.append(list(remaining.keys()))
                break
            order.append(ready)
            for a in ready:
                del remaining[a]
            for deps in remaining.values():
                deps -= set(ready)
        return order


@dataclass
class RoutingPolicy:
    """
    Declarative routing policy — separates policy from execution.
    Evaluated before candidate selection; constraints are hard filters.
    """
    name: str = "default"
    # Hard constraints: agents that must never be selected
    blocked_agents: List[str] = field(default_factory=list)
    # Soft preference: agents to prefer when confidence is equal
    preferred_agents: List[str] = field(default_factory=list)
    # Minimum combined confidence to accept without fallback
    min_confidence: float = 0.35
    # Force fallback when True (e.g. maintenance mode)
    force_fallback: bool = False
    # Maximum agents allowed in multi-agent execution
    max_agents: int = 5

    def is_allowed(self, agent: str) -> bool:
        return agent not in self.blocked_agents

    def apply_preference(
        self, candidates: List[str], scores: Dict[str, float]
    ) -> List[str]:
        """Re-rank candidates: preferred agents bubble up when scores are close."""
        def _key(a: str) -> float:
            base = scores.get(a, 0.0)
            return base + (0.05 if a in self.preferred_agents else 0.0)
        return sorted(candidates, key=_key, reverse=True)


class PolicyEngine:
    """
    Evaluates RoutingPolicy constraints and preferences against a routing decision.
    Sits between candidate ranking and final selection.
    """

    def __init__(self, policy: Optional[RoutingPolicy] = None) -> None:
        self._policy = policy or RoutingPolicy()

    def set_policy(self, policy: RoutingPolicy) -> None:
        self._policy = policy

    def get_policy(self) -> RoutingPolicy:
        return self._policy

    def enforce(
        self,
        decision: RoutingDecision,
        ctx: DecisionContext,
        fallback_agent: str,
    ) -> RoutingDecision:
        """
        Apply policy constraints to a routing decision.
        Steps: block check → force_fallback → confidence floor → preference.
        Returns a (possibly modified) RoutingDecision.
        """
        p = self._policy

        # Force fallback (e.g. maintenance)
        if p.force_fallback:
            return RoutingDecision(
                selected_agent=fallback_agent,
                confidence=0.45,
                strategy=RoutingStrategy.FALLBACK,
                reasoning=f"Policy '{p.name}': force_fallback=True",
                is_fallback=True,
            )

        # Block check
        if not p.is_allowed(decision.selected_agent):
            # Try alternatives
            for alt in decision.alternative_agents:
                if p.is_allowed(alt) and self._is_healthy(alt, ctx):
                    return RoutingDecision(
                        selected_agent=alt,
                        confidence=decision.confidence * 0.90,
                        strategy=decision.strategy,
                        reasoning=f"Policy '{p.name}': {decision.selected_agent} blocked → {alt}",
                        alternative_agents=[a for a in decision.alternative_agents if a != alt],
                        is_fallback=True,
                        capability_match=decision.capability_match,
                    )
            return RoutingDecision(
                selected_agent=fallback_agent,
                confidence=0.45,
                strategy=RoutingStrategy.FALLBACK,
                reasoning=f"Policy '{p.name}': all candidates blocked",
                is_fallback=True,
            )

        # Confidence floor
        if decision.confidence < p.min_confidence:
            return RoutingDecision(
                selected_agent=fallback_agent,
                confidence=decision.confidence,
                strategy=RoutingStrategy.FALLBACK,
                reasoning=f"Policy '{p.name}': confidence {decision.confidence:.3f} < floor {p.min_confidence}",
                is_fallback=True,
            )

        # Preference re-rank among alternatives
        if p.preferred_agents:
            all_candidates = [decision.selected_agent] + list(decision.alternative_agents)
            scores = {a: (decision.confidence if a == decision.selected_agent else 0.0)
                      for a in all_candidates}
            ranked = p.apply_preference(all_candidates, scores)
            best = ranked[0]
            if best != decision.selected_agent and p.is_allowed(best):
                return RoutingDecision(
                    selected_agent=best,
                    confidence=decision.confidence,
                    strategy=decision.strategy,
                    reasoning=f"Policy '{p.name}': preferred agent {best}",
                    alternative_agents=[a for a in ranked[1:] if a != best],
                    capability_match=decision.capability_match,
                )

        return decision

    @staticmethod
    def _is_healthy(agent: str, ctx: DecisionContext) -> bool:
        health = ctx.agent_health.get(agent, "healthy")
        return health in {"healthy", "running", "active", "initialized", "idle", ""}

# Keyword fallback map — used ONLY when semantic + capability routing both fail.
# Configurable via routing.strategy_order in decision_config.yaml.
_KEYWORD_FALLBACK: Dict[str, List[str]] = {
    "memory_agent": ["remember", "recall", "memory", "forget", "store", "history"],
    "emotion_agent": ["feel", "emotion", "mood", "sentiment", "sad", "happy", "angry"],
    "creativity_agent": ["create", "idea", "brainstorm", "creative", "imagine", "invent"],
    "task_agent": ["task", "todo", "schedule", "deadline", "reminder", "organize"],
    "reasoning_agent": ["analyze", "logic", "reason", "why", "argument", "deduce"],
    "learning_agent": ["learn", "study", "understand", "teach", "tutorial"],
    "planning_agent": ["plan", "goal", "strategy", "roadmap", "milestone"],
    "social_agent": ["social", "relationship", "friend", "communicate", "interact"],
    "language_agent": ["write", "code", "program", "translate", "grammar", "text"],
    "motivation_agent": ["motivate", "inspire", "encourage", "stuck", "give up"],
    "ethics_agent": ["ethics", "moral", "right", "wrong", "fair", "justice"],
    "decision_agent": ["decide", "choice", "option", "should i", "which", "compare"],
    "perception_agent": ["see", "hear", "sense", "detect", "recognize", "perceive"],
}

# Intent type → preferred agent capability tags
_INTENT_CAPABILITY_MAP: Dict[IntentType, List[str]] = {
    IntentType.TASK: ["task_management", "scheduling", "task"],
    IntentType.PLANNING_REQUEST: ["planning", "goal_management", "strategy"],
    IntentType.ANALYSIS_REQUEST: ["reasoning", "analysis", "logic"],
    IntentType.CREATIVE_REQUEST: ["creativity", "generation", "creative"],
    IntentType.INFORMATION_REQUEST: ["knowledge", "language", "information"],
    IntentType.QUESTION: ["reasoning", "knowledge", "language"],
    IntentType.COMMAND: ["task_management", "execution", "command"],
    IntentType.WORKFLOW: ["planning", "task_management", "workflow"],
    IntentType.CONVERSATION: ["language", "social", "conversation"],
}


class RoutingEngine:
    """
    Production routing engine.
    Evaluates semantic, capability, and keyword strategies in configured order.
    Applies health, load, and availability filters before finalizing routing.
    """

    def __init__(
        self,
        confidence_engine: Optional[ConfidenceEngine] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._confidence = confidence_engine or ConfidenceEngine()
        cfg = config or {}
        self._fallback_agent: str = cfg.get("fallback_agent", "orchestrator_agent")
        self._max_alternatives: int = int(cfg.get("max_alternatives", 3))
        self._capability_routing: bool = bool(cfg.get("capability_routing_enabled", True))
        self._health_aware: bool = bool(cfg.get("health_aware_routing", True))
        self._load_aware: bool = bool(cfg.get("load_aware_routing", True))
        self._max_parallel: int = int(cfg.get("max_parallel_agents", 5))
        self._fallback_chain: List[str] = list(cfg.get("fallback_chain", ["orchestrator_agent"]))
        self._strategy_order: List[str] = list(
            cfg.get("strategy_order", ["semantic", "capability", "keyword"])
        )
        # Cached capability lookups: agent_name -> set of capability tags
        self._capability_cache: Dict[str, Set[str]] = {}
        # TTL tracking: agent_name -> last_updated timestamp
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl: float = float(cfg.get("capability_cache_ttl", 60.0))
        # Real-time resource metrics: agent_name -> {cpu, queue_depth, memory_mb}
        self._load_metrics: Dict[str, Dict[str, float]] = {}
        # Policy engine — enforces constraints and preferences post-routing
        self._policy_engine = PolicyEngine()

    # ─── Public API ───────────────────────────────────────────────────────────

    def route(
        self,
        ctx: DecisionContext,
        semantic_router: Optional[Any] = None,
    ) -> RoutingDecision:
        """
        Determine the best single agent for the request.
        Evaluates strategies in configured order, applies health/load filters.
        """
        # Refresh capability cache from context
        self._refresh_cache(ctx)

        for strategy in self._strategy_order:
            decision = self._try_strategy(strategy, ctx, semantic_router)
            if decision is not None:
                decision = self._apply_filters(decision, ctx)
                decision = self._policy_engine.enforce(decision, ctx, self._fallback_agent)
                return decision

        return self._make_fallback(ctx, reason="all strategies exhausted")

    def route_multi_agent(
        self,
        ctx: DecisionContext,
        semantic_router: Optional[Any] = None,
    ) -> List[RoutingDecision]:
        """
        Determine multiple agents for collaborative execution.
        Returns ordered list: primary first, then secondary agents.
        """
        primary = self.route(ctx, semantic_router)
        results = [primary]

        # Add secondary agents from alternatives if multi-intent
        if len(ctx.record.intents) > 1:
            seen: Set[str] = {primary.selected_agent}
            for intent in ctx.record.intents[1:]:
                agent = self._route_for_intent(intent, ctx, semantic_router)
                if agent and agent not in seen:
                    seen.add(agent)
                    results.append(RoutingDecision(
                        selected_agent=agent,
                        confidence=intent.confidence * 0.85,
                        strategy=RoutingStrategy.SEMANTIC,
                        reasoning=f"Secondary intent: {intent.intent_type.value}",
                        is_fallback=False,
                    ))
                if len(results) >= self._max_parallel:
                    break

        # If the request contains multiple intents and the primary decision is
        # still low-confidence, preserve an ordered fallback chain rather than
        # forcing a single agent choice.
        if primary.confidence < self._confidence._min_routing and self._fallback_chain:
            for fallback_agent in self._fallback_chain:
                if fallback_agent not in seen and self._is_healthy(fallback_agent, ctx):
                    results.append(RoutingDecision(
                        selected_agent=fallback_agent,
                        confidence=max(primary.confidence, 0.45),
                        strategy=RoutingStrategy.FALLBACK,
                        reasoning=f"Configured fallback chain: {fallback_agent}",
                        is_fallback=True,
                    ))
                    seen.add(fallback_agent)
                    break

        return results

    def explain_routing(
        self,
        decision: "RoutingDecision",
        ctx: "DecisionContext",
    ) -> str:
        """
        Return a human-readable explanation answering:
        - Why this agent?
        - Why not the others?
        - Which capability matched?
        - Which confidence factors contributed?
        - Was a fallback used?
        """
        lines: List[str] = []
        agent = decision.selected_agent
        lines.append(f"Selected: {agent} (strategy={decision.strategy.value}, confidence={decision.confidence:.3f})")

        # Why this agent
        if decision.capability_match:
            primary = ctx.record.primary_intent
            if primary:
                required = _INTENT_CAPABILITY_MAP.get(primary.intent_type, [])
                agent_caps = self._capability_cache.get(agent, set())
                matched = [c for c in required if c in agent_caps]
                lines.append(f"Capability match: {matched} for intent={primary.intent_type.value}")
        if decision.reasoning:
            lines.append(f"Reasoning: {decision.reasoning}")

        # Why not others
        rejected: List[str] = []
        for other in ctx.available_agents:
            if other == agent:
                continue
            health = ctx.agent_health.get(other, "healthy")
            if health not in {"healthy", "running", "active", "initialized", "idle", ""}:
                rejected.append(f"{other} (unhealthy={health})")
            elif other in decision.alternative_agents:
                rejected.append(f"{other} (lower score)")
        if rejected:
            lines.append("Not selected: " + ", ".join(rejected[:4]))

        if decision.is_fallback:
            lines.append("Fallback was used.")

        return " | ".join(lines)

    def build_execution_plan(
        self,
        decisions: List[RoutingDecision],
        aggregation: str = "merge",
    ) -> MultiAgentPlan:
        """
        Build a dependency-aware execution plan from a list of routing decisions.
        Sequential: each agent depends on the previous.
        Parallel (default): all agents run independently.
        """
        if not decisions:
            return MultiAgentPlan()
        nodes: List[AgentNode] = []
        if aggregation == "sequential":
            prev = ""
            for d in decisions:
                deps = [prev] if prev else []
                nodes.append(AgentNode(agent=d.selected_agent, depends_on=deps, decision=d))
                prev = d.selected_agent
        else:
            for d in decisions:
                nodes.append(AgentNode(agent=d.selected_agent, depends_on=[], decision=d))
        plan = MultiAgentPlan(nodes=nodes, aggregation=aggregation)
        plan.parallel_groups = plan.execution_order()
        return plan

    def set_policy(self, policy: RoutingPolicy) -> None:
        """Hot-swap the active routing policy."""
        self._policy_engine.set_policy(policy)

    def get_policy(self) -> RoutingPolicy:
        return self._policy_engine.get_policy()

    def update_load_metrics(
        self,
        agent_name: str,
        cpu: float = 0.0,
        queue_depth: int = 0,
        memory_mb: float = 0.0,
    ) -> None:
        """Record real-time resource metrics for load-aware routing."""
        self._load_metrics[agent_name] = {
            "cpu": cpu,
            "queue_depth": queue_depth,
            "memory_mb": memory_mb,
        }

    def _composite_load(self, agent: str) -> float:
        """
        Composite load score [0, 1] — higher means more loaded.
        Combines: execution count (from ctx), CPU, queue depth, memory.
        """
        m = self._load_metrics.get(agent, {})
        cpu = min(1.0, m.get("cpu", 0.0) / 100.0)          # 0-100% → 0-1
        queue = min(1.0, m.get("queue_depth", 0) / 50.0)    # 0-50 tasks → 0-1
        mem = min(1.0, m.get("memory_mb", 0.0) / 4096.0)    # 0-4GB → 0-1
        return round((cpu * 0.4 + queue * 0.4 + mem * 0.2), 4)

    def update_capability_cache(self, agent_name: str, capabilities: List[str]) -> None:
        self._capability_cache[agent_name] = set(capabilities)
        self._cache_timestamps[agent_name] = time.monotonic()

    def invalidate_cache(self, agent_name: Optional[str] = None) -> None:
        """Invalidate capability cache for one agent or all agents."""
        if agent_name:
            self._capability_cache.pop(agent_name, None)
            self._cache_timestamps.pop(agent_name, None)
        else:
            self._capability_cache.clear()
            self._cache_timestamps.clear()

    # ─── Strategy Implementations ─────────────────────────────────────────────

    def _try_strategy(
        self,
        strategy: str,
        ctx: DecisionContext,
        semantic_router: Optional[Any],
    ) -> Optional[RoutingDecision]:
        if strategy == "semantic" and semantic_router is not None:
            return self._semantic_route(ctx, semantic_router)
        if strategy == "capability" and self._capability_routing:
            return self._capability_route(ctx)
        if strategy == "keyword":
            return self._keyword_route(ctx)
        return None

    def _semantic_route(
        self, ctx: DecisionContext, semantic_router: Any
    ) -> Optional[RoutingDecision]:
        try:
            perf_weights = self._confidence.get_performance_weights()
            result = semantic_router.route(
                ctx.content,
                agent_hint=ctx.agent_hint,
                performance_weights=perf_weights or None,
            )
            if not self._confidence.is_above_routing_threshold(result.confidence):
                return None

            cap_match = self._has_capability_match(result.selected_agent, ctx)
            conf = self._confidence.routing_confidence(
                semantic_score=result.confidence,
                margin=getattr(result, "uncertainty", 0.0),
                capability_match=cap_match,
                agent_name=result.selected_agent,
            )
            return RoutingDecision(
                selected_agent=result.selected_agent,
                confidence=conf,
                strategy=RoutingStrategy.SEMANTIC,
                reasoning=getattr(result, "reasoning", "semantic match"),
                alternative_agents=getattr(result, "alternative_agents", []),
                scores=getattr(result, "scores", {}),
                uncertainty=getattr(result, "uncertainty", 0.0),
                capability_match=cap_match,
            )
        except Exception as exc:
            logger.warning(f"routing_engine.semantic_failed error={exc}")
            return None

    def _capability_route(self, ctx: DecisionContext) -> Optional[RoutingDecision]:
        """Route based on intent → capability tag mapping."""
        primary_intent = ctx.record.primary_intent
        if primary_intent is None:
            return None

        required_caps = _INTENT_CAPABILITY_MAP.get(primary_intent.intent_type, [])
        if not required_caps:
            return None

        best_agent: Optional[str] = None
        best_overlap = 0

        for agent in ctx.available_agents:
            caps = self._capability_cache.get(agent, set())
            overlap = sum(1 for cap in required_caps if cap in caps)
            if overlap > best_overlap:
                best_overlap = overlap
                best_agent = agent

        if best_agent is None or best_overlap == 0:
            return None

        conf = self._confidence.routing_confidence(
            semantic_score=min(0.8, 0.4 + best_overlap * 0.15),
            capability_match=True,
            agent_name=best_agent,
        )
        if not self._confidence.is_above_routing_threshold(conf):
            return None

        return RoutingDecision(
            selected_agent=best_agent,
            confidence=conf,
            strategy=RoutingStrategy.CAPABILITY,
            reasoning=f"Capability match: {best_overlap}/{len(required_caps)} tags for {primary_intent.intent_type.value}",
            capability_match=True,
        )

    def _keyword_route(self, ctx: DecisionContext) -> Optional[RoutingDecision]:
        """Last-resort keyword fallback — configurable, not primary routing."""
        lower = ctx.content.lower()
        scores: Dict[str, int] = {}
        for agent, keywords in _KEYWORD_FALLBACK.items():
            score = sum(1 for kw in keywords if kw in lower)
            if score > 0:
                scores[agent] = score

        if not scores:
            return None

        best = max(scores, key=lambda k: scores[k])
        conf = self._confidence.routing_confidence(
            semantic_score=min(0.6, 0.3 + scores[best] * 0.08),
            agent_name=best,
        )
        alts = sorted([a for a in scores if a != best], key=lambda k: scores[k], reverse=True)

        return RoutingDecision(
            selected_agent=best,
            confidence=conf,
            strategy=RoutingStrategy.KEYWORD,
            reasoning=f"Keyword fallback: {scores[best]} match(es) for {best}",
            alternative_agents=alts[:self._max_alternatives],
            is_fallback=True,
        )

    # ─── Filters ──────────────────────────────────────────────────────────────

    def _apply_filters(self, decision: RoutingDecision, ctx: DecisionContext) -> RoutingDecision:
        """Apply health and load filters; reroute to alternative if needed."""
        agent = decision.selected_agent

        if self._health_aware and not self._is_healthy(agent, ctx):
            # Try alternatives
            for alt in decision.alternative_agents:
                if self._is_healthy(alt, ctx):
                    logger.info(f"routing_engine.health_reroute from={agent} to={alt}")
                    return RoutingDecision(
                        selected_agent=alt,
                        confidence=decision.confidence * 0.90,
                        strategy=decision.strategy,
                        reasoning=f"Health reroute from {agent} → {alt}",
                        alternative_agents=[a for a in decision.alternative_agents if a != alt],
                        is_fallback=True,
                        capability_match=decision.capability_match,
                    )
            # All alternatives unhealthy — use fallback
            return self._make_fallback(ctx, reason=f"agent {agent} unhealthy, no healthy alternatives")

        if self._load_aware:
            load = self._composite_load(agent)
            for alt in decision.alternative_agents:
                alt_load = self._composite_load(alt)
                if alt_load < load * 0.6 and self._is_healthy(alt, ctx):
                    logger.debug(f"routing_engine.load_balance from={agent}(load={load:.2f}) to={alt}(load={alt_load:.2f})")
                    return RoutingDecision(
                        selected_agent=alt,
                        confidence=decision.confidence * 0.95,
                        strategy=decision.strategy,
                        reasoning=f"Load balance: {agent}(load={load:.2f}) → {alt}(load={alt_load:.2f})",
                        alternative_agents=[a for a in decision.alternative_agents if a != alt],
                        capability_match=decision.capability_match,
                    )

        return decision

    def _is_healthy(self, agent: str, ctx: DecisionContext) -> bool:
        if not ctx.available_agents:
            return True  # no availability info — assume healthy
        if agent not in ctx.available_agents:
            return False
        health = ctx.agent_health.get(agent, "healthy")
        return health in {"healthy", "running", "active", "initialized", "idle", ""}

    def _has_capability_match(self, agent: str, ctx: DecisionContext) -> bool:
        primary_intent = ctx.record.primary_intent
        if primary_intent is None:
            return False
        required = set(_INTENT_CAPABILITY_MAP.get(primary_intent.intent_type, []))
        caps = self._capability_cache.get(agent, set())
        return bool(required & caps)

    def _route_for_intent(
        self,
        intent: DetectedIntent,
        ctx: DecisionContext,
        semantic_router: Optional[Any],
    ) -> Optional[str]:
        """Find best agent for a secondary intent."""
        required_caps = _INTENT_CAPABILITY_MAP.get(intent.intent_type, [])
        for agent in ctx.available_agents:
            caps = self._capability_cache.get(agent, set())
            if any(cap in caps for cap in required_caps):
                return agent
        return None

    def _make_fallback(self, ctx: DecisionContext, reason: str) -> RoutingDecision:
        agent = self._fallback_agent
        # Prefer a healthy fallback from the configured chain, then from the
        # current registry snapshot, preserving the runtime's compatibility.
        for candidate in self._fallback_chain + list(ctx.available_agents):
            if candidate and self._is_healthy(candidate, ctx):
                agent = candidate
                break
        return RoutingDecision(
            selected_agent=agent,
            confidence=0.45,
            strategy=RoutingStrategy.FALLBACK,
            reasoning=f"Fallback routing: {reason}",
            is_fallback=True,
        )

    def _refresh_cache(self, ctx: DecisionContext) -> None:
        """Sync capability cache from context; evict entries older than TTL."""
        now = time.monotonic()
        # Evict stale entries
        stale = [
            a for a, ts in self._cache_timestamps.items()
            if now - ts > self._cache_ttl
        ]
        for a in stale:
            self._capability_cache.pop(a, None)
            self._cache_timestamps.pop(a, None)
        # Refresh from context snapshot
        for agent, caps in ctx.agent_capabilities.items():
            self._capability_cache[agent] = set(caps)
            self._cache_timestamps[agent] = now
