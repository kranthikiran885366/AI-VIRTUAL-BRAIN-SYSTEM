"""
CreativityAgent — Phase 10 Production Implementation.

Inherits from BaseAgent for lifecycle management (init, heartbeat, message bus,
health checks). Orchestrates the entire Creativity & Innovation Engine:
  - Structured Idea Generation (11 ideation modes)
  - Divergent & Convergent Thinking Engine
  - Design Thinking Workflow Engine
  - Concept Synthesis & Knowledge Fusion Engine
  - Innovation Engine (incremental, radical, process, product, service, workflow, architecture)
  - Audit Trail, Session Snapshotting, Session Replay, Security Validation & Recovery Engine
  - Observability & Metrics Emission
  - Explainable Output Generation
"""

import logging
import re
import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from ..base_agent import BaseAgent  # type: ignore

try:
    from agents.creativity_agent.models import (
        CreativeContext,
        CreativeIdea,
        IdeaScore,
        CreativeSession,
        CreativityMetrics,
        DesignThinkingSession,
        ConceptSynthesisResult,
        InnovationPlan,
        CreativeAuditTrail,
        ReplayResult,
    )
    from agents.creativity_agent.idea_generator import IdeaGenerator
    from agents.creativity_agent.pattern_recognizer import PatternRecognizer
    from agents.creativity_agent.inspiration_engine import InspirationEngine
    from agents.creativity_agent.divergent import DivergentThinking
    from agents.creativity_agent.convergent import ConvergentThinking
    from agents.creativity_agent.design_thinking import DesignThinkingEngine
    from agents.creativity_agent.concept_synthesis import ConceptSynthesisEngine
    from agents.creativity_agent.innovation_engine import InnovationEngine
    from agents.creativity_agent.audit_replay import CreativeAuditReplay
except ImportError:
    try:
        from .models import (
            CreativeContext,
            CreativeIdea,
            IdeaScore,
            CreativeSession,
            CreativityMetrics,
            DesignThinkingSession,
            ConceptSynthesisResult,
            InnovationPlan,
            CreativeAuditTrail,
            ReplayResult,
        )
        from .idea_generator import IdeaGenerator
        from .pattern_recognizer import PatternRecognizer
        from .inspiration_engine import InspirationEngine
        from .divergent import DivergentThinking
        from .convergent import ConvergentThinking
        from .design_thinking import DesignThinkingEngine
        from .concept_synthesis import ConceptSynthesisEngine
        from .innovation_engine import InnovationEngine
        from .audit_replay import CreativeAuditReplay
    except ImportError:
        IdeaGenerator = PatternRecognizer = InspirationEngine = None  # type: ignore
        DivergentThinking = ConvergentThinking = DesignThinkingEngine = None  # type: ignore
        ConceptSynthesisEngine = InnovationEngine = CreativeAuditReplay = None  # type: ignore


class CreativityAgent(BaseAgent):
    """
    Production Creativity & Innovation Engine.

    Lifecycle:
      - initialize()     : called on startup by orchestrator / agent manager
      - _process_messages(): per-tick hook for message bus processing
      - execute_task()   : orchestrator task dispatch
      - shutdown()       : cleanup on orchestrator teardown
    """

    def __init__(self, agent_id: str = "creativity_agent", config: Dict[str, Any] = None):
        super().__init__(agent_id=agent_id, agent_type="creativity")
        self.config = config or {}
        self._idea_history: List[Dict[str, Any]] = []
        self._max_history = self.config.get("max_idea_history", 1000)

        # Operational metrics tracking
        self.creativity_metrics = CreativityMetrics()

        # Active session registry
        self._sessions: Dict[str, CreativeSession] = {}

        # Sub-component initializers
        self.idea_generator: Optional[Any] = None
        self.pattern_recognizer: Optional[Any] = None
        self.inspiration_engine: Optional[Any] = None
        self.divergent_engine: Optional[Any] = None
        self.convergent_engine: Optional[Any] = None
        self.design_thinking_engine: Optional[Any] = None
        self.synthesis_engine: Optional[Any] = None
        self.innovation_engine: Optional[Any] = None
        self.audit_replay_engine: Optional[Any] = None

    async def initialize(self):
        """Initialize agent — connect to message broker and set up all sub-engines."""
        try:
            await super().initialize()
        except Exception:
            pass  # MockBaseAgent fallback

        if not hasattr(self, "logger"):
            self.logger = logging.getLogger(f"CreativityAgent.{self.agent_id}")

        try:
            self.idea_generator = IdeaGenerator(self.config) if IdeaGenerator else None
            self.pattern_recognizer = PatternRecognizer(self.config) if PatternRecognizer else None
            self.inspiration_engine = InspirationEngine(self.config) if InspirationEngine else None
            self.divergent_engine = DivergentThinking(self.config) if DivergentThinking else None
            self.convergent_engine = ConvergentThinking(self.config) if ConvergentThinking else None
            self.design_thinking_engine = DesignThinkingEngine(self.config) if DesignThinkingEngine else None
            self.synthesis_engine = ConceptSynthesisEngine(self.config) if ConceptSynthesisEngine else None
            self.innovation_engine = InnovationEngine(self.config) if InnovationEngine else None
            self.audit_replay_engine = CreativeAuditReplay(self.config) if CreativeAuditReplay else None
        except Exception as e:
            self.logger.warning(f"CreativityAgent sub-engine init warning: {e}")

        self.state.update({
            "ideas_generated": 0,
            "sessions_count": 0,
            "last_generation": None,
            "history_size": 0,
        })
        self.logger.info(f"CreativityAgent '{self.agent_id}' fully initialized with all Phase 10 engines.")

    async def _process_messages(self):
        """Custom per-tick hook."""
        await asyncio.sleep(0)

    async def _update_state(self):
        await super()._update_state()
        self.state["history_size"] = len(self._idea_history)
        self.state["ideas_generated"] = self.creativity_metrics.total_ideas_generated
        self.state["sessions_count"] = self.creativity_metrics.total_sessions

    # ─── Public API (Synchronous & Backward Compatible) ───────────────────────

    def generate_ideas(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full creative pipeline:
          validate request → analyze patterns → gather inspiration →
          generate ideas → evaluate & rank → audit & snapshot → format explainable result.
        """
        start_time = time.time()
        session_id = str(uuid.uuid4())
        req_id = context.get("request_id", str(uuid.uuid4()))
        corr_id = context.get("correlation_id", str(uuid.uuid4()))
        tr_id = context.get("trace_id", str(uuid.uuid4()))

        # Request Validation
        if self.audit_replay_engine:
            valid, err_msg = self.audit_replay_engine.validate_request(context)
            if not valid:
                self.creativity_metrics.error_count += 1
                return {"error": err_msg, "ideas": [], "top_ideas": []}

        try:
            domain = context.get("domain", "general")
            strategy = context.get("strategy", "auto")

            # 1. Pattern Recognition
            patterns = self._safe_analyze_patterns(context)

            # 2. Inspiration Gathering
            inspiration = self._safe_get_inspiration(context, patterns)

            # 3. Idea Generation
            ideas = self._safe_generate_ideas(context, patterns, inspiration, strategy=strategy)

            # Fallback to SCAMPER if empty
            if not ideas:
                ideas = self._generate_fallback_scamper(context)

            # 4. Convergent Evaluation & Ranking
            evaluated = self._evaluate_and_rank(ideas)

            # 5. History & Session Updates
            self._idea_history.extend(ideas)
            if len(self._idea_history) > self._max_history:
                self._idea_history = self._idea_history[-self._max_history:]

            processing_ms = round((time.time() - start_time) * 1000, 2)
            self.creativity_metrics.total_sessions += 1
            self.creativity_metrics.total_ideas_generated += len(ideas)
            self.creativity_metrics.total_ideas_accepted += len(evaluated)
            self.creativity_metrics.total_processing_ms += processing_ms
            self.state["last_generation"] = datetime.utcnow().isoformat()

            # Record Audit Trail Entry
            if self.audit_replay_engine:
                self.audit_replay_engine.record_audit_entry(
                    session_id=session_id,
                    action="generate_ideas",
                    strategy=strategy,
                    input_summary={"domain": domain, "goals_count": len(context.get("goals", []))},
                    supporting_knowledge=inspiration.get("sources", []),
                    reasoning_summary=f"Generated {len(ideas)} ideas for domain '{domain}' using strategy '{strategy}'.",
                    alternatives_considered=[f"Idea {i+1}: {item.get('idea', {}).get('concept', '')[:40]}" for i, item in enumerate(evaluated[3:])],
                    recommendation_rationale="Ranked top 3 ideas using multi-criteria weighted scoring.",
                    confidence=self._calculate_confidence(evaluated, patterns),
                    request_id=req_id,
                    correlation_id=corr_id,
                    trace_id=tr_id,
                )
                self.audit_replay_engine.save_snapshot(
                    session_id=session_id,
                    context=context,
                    ideas_generated=ideas,
                    metrics_snapshot=self.creativity_metrics.as_dict(),
                )

            # Explainable Output Structure
            top_ideas = evaluated[:3]
            explanation = {
                "generation_strategy": strategy,
                "supporting_knowledge": inspiration.get("sources", []),
                "reasoning_summary": (
                    f"Analyzed {len(patterns.get('semantic', {}).get('themes', []))} semantic themes "
                    f"and gathered cross-domain inspiration from {len(inspiration.get('sources', []))} sources. "
                    f"Evaluated {len(ideas)} candidate ideas against novelty, feasibility, and impact metrics."
                ),
                "confidence": self._calculate_confidence(evaluated, patterns),
                "evaluation_metrics": self.config.get("idea_generation", {}).get("evaluation_weights", {}),
                "limitations": ["Feasibility scores are based on step detail heuristic signals"],
                "alternative_ideas_count": max(0, len(ideas) - 3),
                "recommendation_rationale": "Top ideas selected for maximum overall score and feasibility.",
            }

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "agent_id": self.agent_id,
                "session_id": session_id,
                "request_id": req_id,
                "correlation_id": corr_id,
                "trace_id": tr_id,
                "domain": domain,
                "ideas": evaluated,
                "top_ideas": top_ideas,
                "patterns_detected": len(patterns.get("semantic", {}).get("themes", [])),
                "inspiration_sources": inspiration.get("sources", []),
                "confidence": explanation["confidence"],
                "total_generated": len(ideas),
                "explainability": explanation,
                "processing_ms": processing_ms,
            }
        except Exception as e:
            self.logger.error(f"Error in generate_ideas: {e}")
            self.creativity_metrics.error_count += 1
            if self.audit_replay_engine:
                return self.audit_replay_engine.recover_from_error(
                    e, context, self._generate_fallback_scamper
                )
            return {"error": str(e), "ideas": [], "top_ideas": []}

    def brainstorm(self, topic: str, num_ideas: int = 5) -> List[str]:
        """Quick brainstorm — returns a list of concept strings for a topic."""
        self.creativity_metrics.brainstorm_count += 1
        context = {
            "domain": topic,
            "goals": [f"improve {topic}", f"innovate in {topic}"],
            "constraints": [],
        }
        result = self.generate_ideas(context)
        ideas_out = []
        for item in result.get("ideas", [])[:num_ideas]:
            idea = item.get("idea", item)
            concept = idea.get("concept", "")
            if concept:
                ideas_out.append(concept)
        return ideas_out

    # ─── Async Task Dispatch (Orchestrator Execution Pipeline Interface) ───────

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Async task dispatch called by orchestrator AgentManager and API gateway routes."""
        action = (task.get("action", "") or "").lower()
        input_data = task.get("input_data", {}) or {}

        req_id = task.get("request_id") or input_data.get("request_id")
        corr_id = task.get("correlation_id") or input_data.get("correlation_id")
        tr_id = task.get("trace_id") or input_data.get("trace_id")

        # ── Idea Generation & Brainstorming ───────────────────────────────
        if action in ("generate", "brainstorm", "create", "ideate", "generate_ideas"):
            prompt = input_data.get("prompt", "")
            domain = input_data.get("domain", input_data.get("topic", prompt or "general"))
            strategy = input_data.get("strategy", "auto")
            context = {
                "domain": domain,
                "goals": input_data.get("goals", []),
                "constraints": input_data.get("constraints", []),
                "previous_ideas": input_data.get("previous_ideas", []),
                "strategy": strategy,
                "request_id": req_id,
                "correlation_id": corr_id,
                "trace_id": tr_id,
            }
            if "context" in input_data and isinstance(input_data["context"], dict):
                context.update(input_data["context"])
            return self.generate_ideas(context)

        # ── Pattern Recognition ───────────────────────────────────────────
        if action in ("analyze_patterns", "pattern_recognition"):
            ctx = input_data if isinstance(input_data, dict) else {}
            patterns = self._safe_analyze_patterns(ctx)
            themes = patterns.get("semantic", {}).get("themes", [])
            common_themes = [t.get("terms", []) for t in themes]
            return {
                "patterns": {
                    "common_themes": common_themes,
                    "structural": patterns.get("structural", {}),
                    "temporal": patterns.get("temporal", {}),
                    "semantic": patterns.get("semantic", {}),
                    "influence": patterns.get("influence", {}),
                }
            }

        # ── Gather Inspirations ───────────────────────────────────────────
        if action in ("gather_inspirations", "inspiration"):
            self.creativity_metrics.scamper_count += 1
            query = input_data.get("query", input_data.get("domain", "general"))
            ctx = {"domain": query}
            patterns = self._safe_analyze_patterns(ctx)
            insp = self._safe_get_inspiration(ctx, patterns)
            return {
                "query": query,
                "inspirations": insp.get("elements", []),
                "sources": insp.get("sources", []),
                "relevance": insp.get("relevance", 0.0),
            }

        # ── Convergent Evaluation & Ranking ──────────────────────────────
        if action in ("evaluate", "convergent_rank"):
            self.creativity_metrics.evaluation_count += 1
            ideas = input_data.get("ideas", [])
            if not ideas:
                return {"error": "No ideas provided for evaluation", "evaluated_ideas": []}
            evaluated = self._evaluate_and_rank(ideas)
            recommendations = []
            if self.convergent_engine:
                recommendations = self.convergent_engine.generate_recommendations(evaluated)
            return {
                "evaluated_ideas": evaluated,
                "top_ideas": evaluated[:3],
                "recommendations": recommendations,
            }

        # ── Concept Synthesis & Blending ─────────────────────────────────
        if action in ("synthesis", "blend_concepts"):
            self.creativity_metrics.synthesis_count += 1
            concepts = input_data.get("concepts", input_data.get("source_concepts", []))
            domains = input_data.get("domains", [input_data.get("domain", "general")])
            if self.synthesis_engine:
                result_obj = self.synthesis_engine.synthesize(concepts, domains)
                return result_obj.to_dict()
            return {"error": "ConceptSynthesisEngine unavailable"}

        # ── Design Thinking Workflow ─────────────────────────────────────
        if action in ("design_thinking", "design_thinking_session"):
            self.creativity_metrics.design_thinking_count += 1
            domain = input_data.get("domain", "general")
            ctx = {
                "goals": input_data.get("goals", []),
                "constraints": input_data.get("constraints", []),
            }
            if self.design_thinking_engine:
                session_obj = self.design_thinking_engine.run_session(domain, ctx)
                return session_obj.to_dict()
            return {"error": "DesignThinkingEngine unavailable"}

        # ── Innovation Engine Workflows ──────────────────────────────────
        if action in ("innovation", "innovation_plan"):
            self.creativity_metrics.innovation_count += 1
            domain = input_data.get("domain", "general")
            itype = input_data.get("innovation_type", "incremental")
            ctx = {"goals": input_data.get("goals", []), "constraints": input_data.get("constraints", [])}
            if self.innovation_engine:
                plan_obj = self.innovation_engine.generate_innovation_plan(domain, ctx, itype)
                return plan_obj.to_dict()
            return {"error": "InnovationEngine unavailable"}

        # ── Audit & Replay Session ───────────────────────────────────────
        if action == "replay_session":
            self.creativity_metrics.replay_count += 1
            session_id = input_data.get("session_id", "")
            if self.audit_replay_engine and session_id:
                replay_obj = self.audit_replay_engine.replay_session(
                    session_id, re_generator=lambda ctx: self._safe_generate_ideas(ctx, {}, {})
                )
                return replay_obj.to_dict()
            return {"error": "Session ID required or AuditReplay unavailable"}

        if action == "audit_log":
            session_id = input_data.get("session_id", "")
            if self.audit_replay_engine and session_id:
                trail = self.audit_replay_engine.get_audit_trail(session_id)
                return {"session_id": session_id, "audit_trail": trail}
            return {"error": "Session ID required or AuditReplay unavailable"}

        # ── Metrics & Health ──────────────────────────────────────────────
        if action == "get_metrics":
            return {"metrics": self.creativity_metrics.as_dict()}
        if action == "get_status":
            return await self.get_status()
        if action == "get_health":
            return await self.get_health()

        # ── Quick Brainstorm ──────────────────────────────────────────────
        if action == "quick_brainstorm":
            topic = input_data.get("topic", input_data.get("content", "innovation"))
            num = int(input_data.get("num_ideas", 5))
            ideas = self.brainstorm(topic, num)
            return {"topic": topic, "ideas": ideas, "count": len(ideas)}

        # ── Default Fallback Handler ──────────────────────────────────────
        content = input_data.get("content", input_data.get("text", "general"))
        return self.generate_ideas({"domain": content, "goals": [], "constraints": []})

    # ─── Internal Sub-Engine Dispatchers ──────────────────────────────────────

    def _safe_analyze_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.pattern_recognizer:
            try:
                return self.pattern_recognizer.analyze_patterns(context)
            except Exception as e:
                self.logger.warning(f"Pattern recognition failed: {e}")
        return {"structural": {}, "temporal": {}, "semantic": {"themes": []}, "influence": {}}

    def _safe_get_inspiration(self, context: Dict[str, Any], patterns: Dict[str, Any]) -> Dict[str, Any]:
        if self.inspiration_engine:
            try:
                result = self.inspiration_engine.get_inspiration(context, patterns)
                if "error" not in result:
                    return result
            except Exception as e:
                self.logger.warning(f"Inspiration engine failed: {e}")
        return {"elements": [], "sources": [], "relevance": 0.5}

    def _safe_generate_ideas(
        self,
        context: Dict[str, Any],
        patterns: Dict[str, Any],
        inspiration: Dict[str, Any],
        strategy: str = "auto",
    ) -> List[Dict[str, Any]]:
        if self.idea_generator:
            try:
                return self.idea_generator.generate(context, patterns, inspiration, strategy=strategy)
            except Exception as e:
                self.logger.warning(f"Idea generator failed: {e}")
        return []

    def _evaluate_and_rank(self, ideas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.convergent_engine:
            try:
                return self.convergent_engine.evaluate_and_rank(ideas, self._idea_history)
            except Exception as e:
                self.logger.warning(f"Convergent engine scoring failed: {e}")
        return self._legacy_evaluate_and_rank(ideas)

    def _legacy_evaluate_and_rank(self, ideas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        evaluated = []
        for idea in ideas:
            overall = 0.75
            evaluated.append({
                "idea": idea,
                "scores": {"originality": 0.8, "feasibility": 0.7, "impact": 0.75, "overall": overall},
                "overall": overall,
            })
        return evaluated

    def _generate_fallback_scamper(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        domain = context.get("domain", "general")
        goals = context.get("goals", [])
        constraints = context.get("constraints", [])
        if self.divergent_engine:
            ideas = self.divergent_engine.generate_scamper(domain, goals, constraints)
            return [i.to_dict() for i in ideas]
        return [
            {
                "concept": f"Dynamic optimization of {domain} system",
                "approach": f"Refactor core {domain} modules for modularity and fault-tolerance.",
                "implementation": "Step 1: Audit stack. Step 2: Implement updates. Step 3: Verify.",
                "strategy": "scamper_fallback",
                "domain": domain,
            }
        ]

    def _calculate_confidence(self, evaluated_ideas: List[Dict[str, Any]], patterns: Dict[str, Any]) -> float:
        if not evaluated_ideas:
            return 0.3
        avg = sum(e.get("overall", 0.7) for e in evaluated_ideas) / len(evaluated_ideas)
        theme_count = len(patterns.get("semantic", {}).get("themes", []))
        pattern_bonus = min(0.15, theme_count * 0.02)
        return round(min(0.95, avg + pattern_bonus), 3)
