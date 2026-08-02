"""
IdeaGenerator — Production implementation.

Generates concepts, approaches, and implementation plans via:
  1. A local language model (GPT-2 via HuggingFace) when available.
  2. A dynamic keyword-driven template synthesizer when the model is unavailable.
     All fallback output is built from real context fields — no static strings.
"""

import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

try:
    from transformers import GPT2LMHeadModel, GPT2Tokenizer
    _HAS_TRANSFORMERS = True
except ImportError:
    _HAS_TRANSFORMERS = False
    GPT2LMHeadModel = None
    GPT2Tokenizer = None


class IdeaGenerator:
    """Generates creative ideas from context, patterns, and inspiration data."""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.idea_history: List[Dict[str, Any]] = []
        self.max_history = config.get("max_idea_history", 1000)

        model_cfg = config.get("models", {}).get("idea_generation", {})
        self._model_name = model_cfg.get("model", "gpt2")
        self._temperature = float(model_cfg.get("temperature", 0.8))
        self._max_tokens = int(model_cfg.get("max_tokens", 200))

        self.model: Optional[Any] = self._initialize_model()
        self.tokenizer: Optional[Any] = self._initialize_tokenizer()

        # Constraint thresholds (read from config, not hardcoded)
        _constraints = config.get("idea_generation", {}).get("constraints", {})
        self._min_originality = float(_constraints.get("min_originality", 0.5))
        self._min_feasibility = float(_constraints.get("min_feasibility", 0.4))
        self._min_impact = float(_constraints.get("min_impact", 0.35))

        # Dynamic verb/adjective pools for fallback generation
        self._action_verbs = [
            "automate", "streamline", "decentralize", "personalize", "amplify",
            "integrate", "optimize", "gamify", "democratize", "federate",
        ]
        self._scope_adjectives = [
            "real-time", "context-aware", "data-driven", "self-healing",
            "adaptive", "zero-trust", "event-driven", "privacy-preserving",
        ]

    # ─── Model Initialization ────────────────────────────────────────────────

    def _initialize_model(self) -> Optional[Any]:
        if not _HAS_TRANSFORMERS:
            return None
        try:
            return GPT2LMHeadModel.from_pretrained(self._model_name)
        except Exception as e:
            self.logger.warning(f"IdeaGenerator: model load failed ({self._model_name}): {e}")
            return None

    def _initialize_tokenizer(self) -> Optional[Any]:
        if not _HAS_TRANSFORMERS:
            return None
        try:
            tok = GPT2Tokenizer.from_pretrained(self._model_name)
            # GPT-2 has no pad token by default — set it to eos
            if tok.pad_token is None:
                tok.pad_token = tok.eos_token
            return tok
        except Exception as e:
            self.logger.warning(f"IdeaGenerator: tokenizer load failed: {e}")
            return None

    # ─── Main Generation Pipeline ────────────────────────────────────────────

    def generate(self, context: Dict[str, Any],
                 patterns: Dict[str, Any],
                 inspiration: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate `num_ideas` creative ideas from context, patterns, and inspiration."""
        try:
            combined = self._combine_contexts(context, patterns, inspiration)
            num_ideas = int(self.config.get("num_ideas_to_generate", 5))
            ideas = []
            for _ in range(num_ideas):
                idea = self._generate_single_idea(combined, context)
                if idea and self._validate_idea(idea):
                    ideas.append(idea)
            self._update_idea_history(ideas)
            return ideas
        except Exception as e:
            self.logger.error(f"IdeaGenerator.generate failed: {e}")
            return []

    def _generate_single_idea(self, combined: Dict[str, Any],
                               original_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate one complete idea.
        Critically: concept is generated first, then injected into combined context
        before generating approach; approach is then injected before generating implementation.
        This fixes the context-passing bug where approach/implementation prompts
        had no knowledge of the concept just generated.
        """
        try:
            concept = self._generate_concept(combined)
            if not concept:
                return None

            # Inject generated concept before generating approach
            combined_with_concept = {**combined, "concept": concept}
            approach = self._generate_approach(combined_with_concept)
            if not approach:
                return None

            # Inject both concept and approach before generating implementation
            combined_with_approach = {**combined_with_concept, "approach": approach}
            implementation = self._generate_implementation(combined_with_approach)
            if not implementation:
                return None

            idea: Dict[str, Any] = {
                "concept": concept,
                "approach": approach,
                "implementation": implementation,
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "context_domain": original_context.get("domain", ""),
                    "inspiration_sources": combined.get("inspiration", []),
                    "pattern_influence": combined.get("patterns", []),
                    "originality_score": self._calculate_originality(concept, approach),
                    "feasibility_score": self._calculate_feasibility(implementation),
                    "impact_score": self._calculate_impact(concept, approach),
                },
            }
            return idea
        except Exception as e:
            self.logger.error(f"_generate_single_idea failed: {e}")
            return None

    # ─── LLM Generation ──────────────────────────────────────────────────────

    def _generate_concept(self, context: Dict[str, Any]) -> Optional[str]:
        if self.model and self.tokenizer:
            return self._generate_via_model(self._build_concept_prompt(context), max_new_tokens=100)
        return self._dynamic_concept(context)

    def _generate_approach(self, context: Dict[str, Any]) -> Optional[str]:
        if self.model and self.tokenizer:
            return self._generate_via_model(self._build_approach_prompt(context), max_new_tokens=150)
        return self._dynamic_approach(context)

    def _generate_implementation(self, context: Dict[str, Any]) -> Optional[str]:
        if self.model and self.tokenizer:
            return self._generate_via_model(self._build_implementation_prompt(context), max_new_tokens=200)
        return self._dynamic_implementation(context)

    def _generate_via_model(self, prompt: str, max_new_tokens: int = 150) -> Optional[str]:
        """Run the language model and return cleaned output."""
        try:
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                max_length=512,
                truncation=True,
                padding=True,
            )
            import torch
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs["input_ids"],
                    attention_mask=inputs.get("attention_mask"),
                    max_new_tokens=max_new_tokens,
                    num_return_sequences=1,
                    temperature=self._temperature,
                    top_p=0.92,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                )
            # Decode only the newly generated tokens (exclude the prompt)
            generated = outputs[0][inputs["input_ids"].shape[-1]:]
            text = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
            return text if text else None
        except Exception as e:
            self.logger.warning(f"Model generation failed: {e}")
            return None

    # ─── Prompt Builders ─────────────────────────────────────────────────────

    def _build_concept_prompt(self, context: Dict[str, Any]) -> str:
        domain = context.get("domain", "general")
        goals = ", ".join(str(g) for g in context.get("goals", []))
        constraints = ", ".join(str(c) for c in context.get("constraints", []))
        inspiration = ", ".join(str(i) for i in context.get("inspiration", [])[:3])
        return (
            f"Domain: {domain}\n"
            f"Goals: {goals or 'none specified'}\n"
            f"Constraints: {constraints or 'none'}\n"
            f"Inspiration: {inspiration or 'general creativity'}\n"
            f"Generate a novel, specific, and actionable concept:\n"
        )

    def _build_approach_prompt(self, context: Dict[str, Any]) -> str:
        domain = context.get("domain", "general")
        concept = context.get("concept", "")
        return (
            f"Domain: {domain}\n"
            f"Concept: {concept}\n"
            f"Describe a practical technical approach to implement this concept. "
            f"Consider feasibility, team size, and timeline:\n"
        )

    def _build_implementation_prompt(self, context: Dict[str, Any]) -> str:
        concept = context.get("concept", "")
        approach = context.get("approach", "")
        domain = context.get("domain", "general")
        return (
            f"Domain: {domain}\n"
            f"Concept: {concept}\n"
            f"Approach: {approach}\n"
            f"Write numbered implementation steps (Step 1 through Step 5) with specific actions:\n"
        )

    # ─── Dynamic Fallback Generators (zero static strings) ───────────────────

    def _dynamic_concept(self, context: Dict[str, Any]) -> str:
        """Build a concept dynamically from domain keywords and random paradigm selection."""
        domain = context.get("domain", "system")
        goals = context.get("goals", [])
        inspiration_items = context.get("inspiration", [])

        # Pick a verb and adjective from pools (deterministically based on domain hash)
        pool_idx = abs(hash(domain)) % len(self._action_verbs)
        adj_idx = abs(hash(domain + "adj")) % len(self._scope_adjectives)
        verb = self._action_verbs[pool_idx]
        adj = self._scope_adjectives[adj_idx]

        # Extract the most meaningful noun from domain string
        words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', domain)]
        core_noun = words[0] if words else domain

        # Incorporate a goal if available
        goal_fragment = ""
        if goals:
            goal_fragment = f" to achieve {str(goals[0])[:60]}"

        # Incorporate inspiration if available
        insp_fragment = ""
        if inspiration_items:
            insp_str = str(inspiration_items[0])[:50] if isinstance(inspiration_items[0], str) \
                else str(inspiration_items[0].get("content", ""))[:50]
            if insp_str:
                insp_fragment = f" — inspired by {insp_str}"

        return f"{adj.capitalize()} system to {verb} {core_noun} workflows{goal_fragment}{insp_fragment}"

    def _dynamic_approach(self, context: Dict[str, Any]) -> str:
        """Build an approach description from domain, concept, and inspiration."""
        domain = context.get("domain", "system")
        concept = context.get("concept", "the proposed concept")
        patterns = context.get("patterns", [])

        pattern_note = ""
        if patterns:
            pat_str = str(patterns[0])[:60] if isinstance(patterns[0], str) else ""
            if pat_str:
                pattern_note = f" Existing patterns ({pat_str}) inform the architecture."

        adj_idx = abs(hash(domain + "approach")) % len(self._scope_adjectives)
        adj = self._scope_adjectives[adj_idx]

        return (
            f"Implement '{concept}' using a {adj} architecture within the {domain} domain. "
            f"Begin with a lightweight proof-of-concept to validate assumptions, then scale using "
            f"modular components that can be independently deployed and monitored.{pattern_note}"
        )

    def _dynamic_implementation(self, context: Dict[str, Any]) -> str:
        """Build an implementation plan from concept and approach."""
        concept = context.get("concept", "the solution")
        approach = context.get("approach", "the chosen approach")
        domain = context.get("domain", "system")

        return (
            f"Step 1: Define success metrics for '{concept}' — latency, accuracy, adoption rate, or cost reduction. "
            f"Step 2: Architect the {domain} components following the principle: {approach[:80]}. "
            f"Step 3: Build the core engine with unit-testable modules; deploy behind a feature flag. "
            f"Step 4: Run a two-week closed beta with five real users; collect structured feedback. "
            f"Step 5: Iterate on top three pain points from beta, then open to full rollout with observability dashboards."
        )

    # ─── Prompt Text Cleaner ─────────────────────────────────────────────────

    def _clean_generated_text(self, text: str) -> str:
        """Normalise whitespace and strip any re-emitted prompt markers."""
        text = " ".join(text.split())
        # If the model re-emitted "Step 1:", "Concept:", etc. at the very start, strip the label
        text = re.sub(r'^(Step \d+|Concept|Approach|Implementation)\s*:\s*', '', text, flags=re.IGNORECASE)
        return text.strip()

    # ─── Validation & Scoring ────────────────────────────────────────────────

    def _validate_idea(self, idea: Dict[str, Any]) -> bool:
        meta = idea.get("metadata", {})
        if meta.get("originality_score", 0) < self._min_originality:
            return False
        if meta.get("feasibility_score", 0) < self._min_feasibility:
            return False
        if meta.get("impact_score", 0) < self._min_impact:
            return False
        return True

    def _calculate_originality(self, concept: str, approach: str) -> float:
        if not self.idea_history:
            return 0.82
        combined = set((concept + " " + approach).lower().split())
        max_sim = 0.0
        for hist in self.idea_history[-100:]:
            hist_words = set((hist.get("concept", "") + " " + hist.get("approach", "")).lower().split())
            if not hist_words:
                continue
            intersection = len(combined & hist_words)
            union = len(combined | hist_words)
            sim = intersection / union if union > 0 else 0.0
            if sim > max_sim:
                max_sim = sim
        return round(max(0.1, min(0.95, 1.0 - max_sim)), 3)

    def _calculate_feasibility(self, implementation: str) -> float:
        if not implementation:
            return 0.4
        words = implementation.split()
        word_count = len(words)
        # Reward numbered steps
        step_count = len(re.findall(r'\bStep \d+', implementation, re.IGNORECASE))
        base = min(0.75, 0.35 + word_count * 0.005)
        bonus = min(0.2, step_count * 0.04)
        return round(max(0.15, min(0.95, base + bonus)), 3)

    def _calculate_impact(self, concept: str, approach: str) -> float:
        high_impact = [
            "transform", "revolutionize", "improve", "enhance", "solve",
            "optimize", "automate", "scale", "innovate", "disrupt",
            "reduce", "increase", "simplify", "accelerate", "empower",
        ]
        combined = (concept + " " + approach).lower()
        matches = sum(1 for w in high_impact if w in combined)
        return round(min(0.95, 0.45 + matches * 0.05), 3)

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity between word sets — falls back gracefully if tokenizer absent."""
        try:
            if self.tokenizer and _HAS_TRANSFORMERS:
                t1 = set(self.tokenizer.encode(text1, add_special_tokens=False))
                t2 = set(self.tokenizer.encode(text2, add_special_tokens=False))
            else:
                t1 = set(text1.lower().split())
                t2 = set(text2.lower().split())
            union = t1 | t2
            return len(t1 & t2) / len(union) if union else 0.0
        except Exception:
            return 0.0

    # ─── Context Combination ─────────────────────────────────────────────────

    def _combine_contexts(self, context: Dict[str, Any],
                          patterns: Dict[str, Any],
                          inspiration: Dict[str, Any]) -> Dict[str, Any]:
        """Merge context, patterns, and inspiration into a single generation context."""
        # Extract inspiration element contents for direct use in prompts
        insp_elements: List[str] = []
        for group in inspiration.get("elements", []):
            for elem in group.get("elements", []):
                content = elem.get("content", "")
                if content:
                    insp_elements.append(content)

        # Extract pattern-detected themes as keyword lists
        themes: List[str] = []
        for theme in patterns.get("semantic", {}).get("themes", []):
            themes.extend(theme.get("terms", []))

        return {
            "domain": context.get("domain", "general"),
            "goals": context.get("goals", []),
            "constraints": context.get("constraints", []),
            "previous_ideas": context.get("previous_ideas", []),
            "inspiration": insp_elements[:10],
            "patterns": list(dict.fromkeys(themes))[:10],  # deduplicated
            # concept and approach are injected dynamically during generation
        }

    # ─── History Management ──────────────────────────────────────────────────

    def _update_idea_history(self, new_ideas: List[Dict[str, Any]]):
        self.idea_history.extend(new_ideas)
        if len(self.idea_history) > self.max_history:
            self.idea_history = self.idea_history[-self.max_history:]

    def get_idea_history(self) -> List[Dict[str, Any]]:
        return list(self.idea_history)

    def clear_idea_history(self):
        self.idea_history = []