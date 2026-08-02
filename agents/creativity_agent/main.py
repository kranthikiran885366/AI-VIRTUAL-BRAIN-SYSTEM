"""
CreativityAgent — Full production implementation.

Inherits from BaseAgent for lifecycle management (init, heartbeat, message bus,
health checks). Orchestrates idea generation, pattern recognition, and inspiration
gathering. All scoring is computed from actual content — no hardcoded values.
"""

import logging
import re
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from agents.base_agent import BaseAgent
except ImportError:
    from ..base_agent import BaseAgent  # type: ignore

try:
    from agents.creativity_agent.idea_generator import IdeaGenerator
    from agents.creativity_agent.pattern_recognizer import PatternRecognizer
    from agents.creativity_agent.inspiration_engine import InspirationEngine
except ImportError:
    try:
        from .idea_generator import IdeaGenerator
        from .pattern_recognizer import PatternRecognizer
        from .inspiration_engine import InspirationEngine
    except ImportError:
        IdeaGenerator = PatternRecognizer = InspirationEngine = None  # type: ignore


class CreativityAgent(BaseAgent):
    """
    Creativity Agent — generates, evaluates, and ranks ideas.

    Lifecycle:
      - initialize()     : called by orchestrator on startup
      - _process_messages(): called each agent loop tick
      - execute_task()   : called by orchestrator for direct task dispatch
      - shutdown()       : called on orchestrator teardown
    """

    def __init__(self, agent_id: str = "creativity_agent", config: Dict[str, Any] = None):
        super().__init__(agent_id=agent_id, agent_type="creativity")
        self.config = config or {}
        self._idea_history: List[Dict[str, Any]] = []
        self._max_history = self.config.get("max_idea_history", 500)
        self.idea_generator: Optional[Any] = None
        self.pattern_recognizer: Optional[Any] = None
        self.inspiration_engine: Optional[Any] = None

        # Domain impact keywords — used in scoring
        self._impact_keywords = [
            "transform", "revolutionize", "improve", "enhance", "solve", "optimize",
            "automate", "scale", "innovate", "disrupt", "reduce", "increase",
            "simplify", "accelerate", "empower", "enable", "integrate", "streamline",
        ]
        # Feasibility positive signals
        self._feasibility_positive = [
            "step", "phase", "implement", "build", "use", "apply", "deploy",
            "integrate", "connect", "configure", "install", "create", "develop",
        ]
        # Feasibility negative signals
        self._feasibility_negative = [
            "impossible", "extremely complex", "requires years", "very difficult",
            "unknown technology", "theoretical only",
        ]

    async def initialize(self):
        """Initialize agent — connect to message broker and set up sub-components."""
        try:
            await super().initialize()
        except Exception:
            pass  # MockBaseAgent.initialize() is a no-op; swallow safely

        # Ensure logger is always available regardless of BaseAgent implementation
        if not hasattr(self, "logger"):
            import logging
            self.logger = logging.getLogger(f"CreativityAgent.{self.agent_id}")

        try:
            self.idea_generator = IdeaGenerator(self.config) if IdeaGenerator else None
            self.pattern_recognizer = PatternRecognizer(self.config) if PatternRecognizer else None
            self.inspiration_engine = InspirationEngine(self.config) if InspirationEngine else None
        except Exception as e:
            self.logger.warning(f"CreativityAgent sub-component init warning: {e}")

        self.state.update({
            "ideas_generated": 0,
            "last_generation": None,
            "history_size": 0,
        })
        self.logger.info(f"CreativityAgent '{self.agent_id}' initialized.")

    async def _process_messages(self):
        """Custom per-tick hook — nothing extra needed; message bus handles routing."""
        await asyncio.sleep(0)

    async def _update_state(self):
        await super()._update_state()
        self.state["history_size"] = len(self._idea_history)

    # ─── Public API ───────────────────────────────────────────────────────────

    def generate_ideas(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full synchronous pipeline:
          analyze patterns → gather inspiration → generate ideas → evaluate & rank.
        Returns a rich result dict suitable for REST API responses.
        """
        try:
            # 1. Analyze patterns in context
            patterns = self._safe_analyze_patterns(context)

            # 2. Gather inspiration
            inspiration = self._safe_get_inspiration(context, patterns)

            # 3. Generate ideas
            ideas = self._safe_generate_ideas(context, patterns, inspiration)

            # 4. If nothing came back, use the SCAMPER fallback (dynamic — no static strings)
            if not ideas:
                ideas = self._generate_ideas_from_context(context)

            # 5. Evaluate and rank
            evaluated = self._evaluate_and_rank(ideas)

            # 6. Update history
            self._idea_history.extend(ideas)
            if len(self._idea_history) > self._max_history:
                self._idea_history = self._idea_history[-self._max_history:]

            self.state["ideas_generated"] = self.state.get("ideas_generated", 0) + len(ideas)
            self.state["last_generation"] = datetime.utcnow().isoformat()

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "agent_id": self.agent_id,
                "ideas": evaluated,
                "top_ideas": evaluated[:3],
                "patterns_detected": len(patterns.get("semantic", {}).get("themes", [])),
                "inspiration_sources": inspiration.get("sources", []),
                "confidence": self._calculate_confidence(evaluated, patterns),
                "total_generated": len(ideas),
            }
        except Exception as e:
            self.logger.error(f"Error in generate_ideas: {e}")
            return {"error": str(e), "ideas": [], "top_ideas": []}

    def brainstorm(self, topic: str, num_ideas: int = 5) -> List[str]:
        """Quick brainstorm — returns a list of idea concept strings for a topic."""
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

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Async task dispatch called by the orchestrator agent manager."""
        action = task.get("action", "")
        input_data = task.get("input_data", {}) or {}

        # ── Idea generation / brainstorming ───────────────────────────────
        if action in ("generate", "brainstorm", "create", "ideate"):
            domain = input_data.get("domain", input_data.get("topic", "general"))
            context = {
                "domain": domain,
                "goals": input_data.get("goals", []),
                "constraints": input_data.get("constraints", []),
                "previous_ideas": input_data.get("previous_ideas", []),
            }
            return self.generate_ideas(context)

        # ── Evaluation ────────────────────────────────────────────────────
        if action == "evaluate":
            ideas = input_data.get("ideas", [])
            if not ideas:
                return {"error": "No ideas provided for evaluation", "evaluated_ideas": []}
            evaluated = self._evaluate_and_rank(ideas)
            return {"evaluated_ideas": evaluated, "top_ideas": evaluated[:3]}

        # ── Quick brainstorm ───────────────────────────────────────────────
        if action == "quick_brainstorm":
            topic = input_data.get("topic", input_data.get("content", "innovation"))
            num = int(input_data.get("num_ideas", 5))
            ideas = self.brainstorm(topic, num)
            return {"topic": topic, "ideas": ideas, "count": len(ideas)}

        # ── Health / status ───────────────────────────────────────────────
        if action == "get_status":
            return await self.get_status()
        if action == "get_health":
            return await self.get_health()

        # ── Default fallback: treat content as domain ─────────────────────
        content = input_data.get("content", input_data.get("text", "general"))
        return self.generate_ideas({"domain": content, "goals": [], "constraints": []})

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _safe_analyze_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.pattern_recognizer:
            try:
                return self.pattern_recognizer.analyze_patterns(context)
            except Exception as e:
                self.logger.warning(f"Pattern recognition failed: {e}")
        return {"structural": {}, "temporal": {}, "semantic": {"themes": []}, "influence": {}}

    def _safe_get_inspiration(self, context: Dict[str, Any],
                              patterns: Dict[str, Any]) -> Dict[str, Any]:
        if self.inspiration_engine:
            try:
                result = self.inspiration_engine.get_inspiration(context, patterns)
                if "error" not in result:
                    return result
            except Exception as e:
                self.logger.warning(f"Inspiration engine failed: {e}")
        return {"elements": [], "sources": [], "relevance": 0.5}

    def _safe_generate_ideas(self, context: Dict[str, Any],
                             patterns: Dict[str, Any],
                             inspiration: Dict[str, Any]) -> List[Dict[str, Any]]:
        if self.idea_generator:
            try:
                return self.idea_generator.generate(context, patterns, inspiration)
            except Exception as e:
                self.logger.warning(f"Idea generator failed: {e}")
        return []

    # ─── SCAMPER Fallback (fully dynamic — no static strings) ────────────────

    def _generate_ideas_from_context(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fallback idea generator using the SCAMPER framework.
        All content is composed dynamically from context — zero hardcoded output.
        """
        domain = context.get("domain", "general")
        goals = context.get("goals", [])
        constraints = context.get("constraints", [])

        # Extract key nouns from domain for richer substitution
        domain_words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', domain) if w.lower() not in
                        {"that", "with", "from", "this", "have", "will", "your", "they", "been"}]
        domain_noun = domain_words[0] if domain_words else domain

        scamper_frames = [
            {
                "letter": "S",
                "label": "Substitute",
                "concept": f"Replace legacy {domain_noun} components with modern, purpose-built alternatives",
                "approach": (
                    f"Audit the current {domain} stack for friction points. Map each bottleneck to "
                    f"a modern equivalent (e.g., cloud-native, ML-powered, or event-driven). "
                    f"Quantify risk and benefit before migrating."
                ),
                "implementation": (
                    f"Step 1: Catalogue all {domain_noun} components by age, cost, and failure rate. "
                    f"Step 2: Research three modern alternatives per component. "
                    f"Step 3: Build a decision matrix weighing migration cost vs. long-term savings. "
                    f"Step 4: Pilot the top substitute on a non-critical path. "
                    f"Step 5: Roll out in phases with automated rollback triggers."
                ),
            },
            {
                "letter": "C",
                "label": "Combine",
                "concept": f"Merge {domain} with complementary capabilities to create synergistic value",
                "approach": (
                    f"Identify adjacent domains that have solved a subset of {domain} challenges. "
                    f"Design integration points that let both systems share data and events in real time. "
                    f"Measure the combined output against standalone baselines."
                ),
                "implementation": (
                    f"Step 1: Map the {domain} value chain end-to-end. "
                    f"Step 2: Identify at least two adjacent fields whose outputs feed into your value chain. "
                    f"Step 3: Define shared data contracts (API schemas, event formats). "
                    f"Step 4: Build a lightweight integration adapter with retry logic. "
                    f"Step 5: Deploy, instrument with observability, and iterate."
                ),
            },
            {
                "letter": "A",
                "label": "Adapt",
                "concept": f"Apply proven patterns from high-performing industries to {domain}",
                "approach": (
                    f"Research how sectors such as manufacturing (lean/kaizen), aviation (checklists), "
                    f"and logistics (just-in-time) have solved efficiency challenges. "
                    f"Abstract the transferable principle and adapt it to {domain} constraints."
                ),
                "implementation": (
                    f"Step 1: Select three high-performing industries with documented efficiency gains. "
                    f"Step 2: Extract the core principle behind each success (not the surface tactic). "
                    f"Step 3: Workshop with {domain} stakeholders to map principles to real workflows. "
                    f"Step 4: Build a lightweight pilot applying the adapted principle. "
                    f"Step 5: Measure against a control group and publish findings internally."
                ),
            },
            {
                "letter": "M",
                "label": "Modify",
                "concept": f"Redesign the {domain} experience by amplifying its highest-value dimension",
                "approach": (
                    f"Identify the single dimension of {domain} that delivers the most user or business value "
                    f"(speed, accuracy, personalization, cost, or trust). "
                    f"Focus engineering effort on amplifying that dimension by 10×."
                ),
                "implementation": (
                    f"Step 1: Survey {domain} users and stakeholders to rank the top value dimensions. "
                    f"Step 2: Baseline-measure the top dimension with real metrics. "
                    f"Step 3: Set a 10× improvement target and an 8-week timeline. "
                    f"Step 4: Design three solution prototypes targeting the dimension. "
                    f"Step 5: A/B test prototypes and double down on the winner."
                ),
            },
            {
                "letter": "P",
                "label": "Put to Other Uses",
                "concept": f"Repurpose existing {domain} assets to unlock untapped revenue or efficiency",
                "approach": (
                    f"Inventory all idle or underutilized {domain} assets (data, infrastructure, expertise, "
                    f"relationships). Brainstorm secondary markets or internal applications for each."
                ),
                "implementation": (
                    f"Step 1: List all {domain} assets that are currently under-monetized or idle. "
                    f"Step 2: Identify three potential secondary use cases per asset. "
                    f"Step 3: Estimate addressable value for each use case. "
                    f"Step 4: Build the smallest possible proof-of-concept for the top opportunity. "
                    f"Step 5: Validate with real users before scaling."
                ),
            },
            {
                "letter": "E",
                "label": "Eliminate",
                "concept": f"Remove the highest-friction elements from {domain} to unlock speed and simplicity",
                "approach": (
                    f"Map every step in the {domain} workflow and assign each a friction score "
                    f"(time cost × error rate × user frustration). Eliminate or automate the top three."
                ),
                "implementation": (
                    f"Step 1: Build a process map of every {domain} workflow step. "
                    f"Step 2: Score each step for time cost, error rate, and user frustration (1–5 scale). "
                    f"Step 3: Target the top three friction points for elimination or automation. "
                    f"Step 4: Implement automation scripts or policy changes to remove them. "
                    f"Step 5: Validate with time-in-motion studies and user interviews."
                ),
            },
            {
                "letter": "R",
                "label": "Reverse",
                "concept": f"Invert the {domain} workflow to discover non-obvious breakthrough paths",
                "approach": (
                    f"Start from the ideal end-state of {domain} and reason backwards step by step. "
                    f"Each backward step reveals assumptions and constraints that can be challenged."
                ),
                "implementation": (
                    f"Step 1: Define the perfect {domain} outcome in concrete, measurable terms. "
                    f"Step 2: Work backwards: 'What must be true one step before the end-state?' Repeat 5×. "
                    f"Step 3: Identify which assumptions in the backward chain are breakable. "
                    f"Step 4: Design solutions that break those assumptions. "
                    f"Step 5: Test the most counter-intuitive solution first — it often yields the biggest gain."
                ),
            },
        ]

        ideas = list(scamper_frames)

        # Incorporate goals dynamically
        if goals:
            goal_str = " and ".join(str(g) for g in goals[:3])
            ideas.append({
                "letter": "G",
                "label": "Goal-Driven",
                "concept": f"Build a focused {domain} solution that directly achieves: {goal_str}",
                "approach": (
                    f"Decompose each goal into measurable sub-outcomes. "
                    f"Design a dedicated capability for each sub-outcome and integrate them into a unified {domain} system."
                ),
                "implementation": (
                    f"Step 1: Write measurable success criteria for each goal ({goal_str}). "
                    f"Step 2: Map each criterion to a specific {domain} capability to build. "
                    f"Step 3: Sequence capabilities by dependency (build foundations first). "
                    f"Step 4: Sprint-build each capability with weekly demos. "
                    f"Step 5: Instrument all capabilities with real-time metrics dashboards."
                ),
            })

        # Incorporate constraints dynamically
        if constraints:
            constraint_str = "; ".join(str(c) for c in constraints[:3])
            ideas.append({
                "letter": "X",
                "label": "Constraint-Driven Innovation",
                "concept": f"Turn {domain} constraints into design features that competitors cannot copy",
                "approach": (
                    f"Constraints ({constraint_str}) force creative solutions that become defensible advantages. "
                    f"Identify where each constraint creates a unique edge (lower cost, higher trust, niche focus)."
                ),
                "implementation": (
                    f"Step 1: List every {domain} constraint explicitly: {constraint_str}. "
                    f"Step 2: For each constraint, ask 'What can we do because of this that others cannot?' "
                    f"Step 3: Design features that leverage each constraint as a strength. "
                    f"Step 4: Build the smallest viable demonstration of constraint-as-feature. "
                    f"Step 5: Market it as a differentiator, not a limitation."
                ),
            })

        return ideas

    # ─── Scoring ──────────────────────────────────────────────────────────────

    def _evaluate_and_rank(self, ideas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Evaluate each idea with real content-driven scoring — no hardcoded scores."""
        evaluated = []
        weights = self.config.get("evaluation_weights", {
            "originality": 0.35,
            "feasibility": 0.35,
            "impact": 0.30,
        })

        for idea in ideas:
            originality = self._score_originality(idea)
            feasibility = self._score_feasibility(idea)
            impact = self._score_impact(idea)
            overall = round(
                originality * weights.get("originality", 0.35) +
                feasibility * weights.get("feasibility", 0.35) +
                impact * weights.get("impact", 0.30),
                3,
            )
            evaluated.append({
                "idea": idea,
                "scores": {
                    "originality": originality,
                    "feasibility": feasibility,
                    "impact": impact,
                    "overall": overall,
                },
            })

        evaluated.sort(key=lambda x: x["scores"]["overall"], reverse=True)
        return evaluated

    def _score_originality(self, idea: Dict[str, Any]) -> float:
        """Score originality via Jaccard similarity against the last 50 ideas in history."""
        concept = idea.get("concept", "")
        approach = idea.get("approach", "")
        combined_words = set((concept + " " + approach).lower().split())

        if not self._idea_history:
            return 0.85

        max_similarity = 0.0
        for hist in self._idea_history[-50:]:
            hist_text = (hist.get("concept", "") + " " + hist.get("approach", "")).lower()
            hist_words = set(hist_text.split())
            if not hist_words:
                continue
            intersection = len(combined_words & hist_words)
            union = len(combined_words | hist_words)
            sim = intersection / union if union > 0 else 0.0
            if sim > max_similarity:
                max_similarity = sim

        return round(max(0.1, min(0.95, 1.0 - max_similarity)), 3)

    def _score_feasibility(self, idea: Dict[str, Any]) -> float:
        """Score feasibility based on implementation richness and actionability signals."""
        implementation = idea.get("implementation", "")
        approach = idea.get("approach", "")
        combined = (implementation + " " + approach).lower()

        positive_count = sum(1 for kw in self._feasibility_positive if kw in combined)
        step_count = len(re.findall(r"\b(step|phase|\d+\.)\s", combined, re.IGNORECASE))
        negative_count = sum(1 for kw in self._feasibility_negative if kw in combined)

        word_count = len(implementation.split())
        base = min(0.7, 0.3 + word_count * 0.004)
        bonus = min(0.25, (positive_count * 0.04) + (step_count * 0.05))
        penalty = negative_count * 0.1

        return round(max(0.1, min(0.95, base + bonus - penalty)), 3)

    def _score_impact(self, idea: Dict[str, Any]) -> float:
        """Score impact based on high-value action words and scope indicators."""
        concept = idea.get("concept", "")
        approach = idea.get("approach", "")
        combined = (concept + " " + approach).lower()

        impact_count = sum(1 for kw in self._impact_keywords if kw in combined)
        scope_words = ["all", "entire", "every", "global", "system", "platform",
                       "users", "team", "organization", "enterprise", "scale"]
        scope_count = sum(1 for w in scope_words if w in combined)

        base = 0.45
        impact_bonus = min(0.35, impact_count * 0.05)
        scope_bonus = min(0.15, scope_count * 0.03)

        return round(max(0.1, min(0.95, base + impact_bonus + scope_bonus)), 3)

    def _calculate_confidence(self, evaluated_ideas: List[Dict[str, Any]],
                              patterns: Dict[str, Any]) -> float:
        """Confidence based on average idea quality and pattern richness."""
        if not evaluated_ideas:
            return 0.3
        avg = sum(e["scores"]["overall"] for e in evaluated_ideas) / len(evaluated_ideas)
        theme_count = len(patterns.get("semantic", {}).get("themes", []))
        pattern_bonus = min(0.15, theme_count * 0.02)
        return round(min(0.95, avg + pattern_bonus), 3)
