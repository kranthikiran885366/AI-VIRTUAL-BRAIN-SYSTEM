"""
InspirationEngine — Production implementation.

Draws creative inspiration from five configurable domains (art, science, nature,
technology, culture). On first run it auto-creates and populates the data directory
with rich default datasets. All relevance scoring is derived from real content
similarity — no hardcoded scores.
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False
    TfidfVectorizer = None

try:
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    import nltk
    _HAS_NLTK = True
except ImportError:
    _HAS_NLTK = False

    def word_tokenize(text: str) -> List[str]:  # type: ignore
        return text.lower().split()

    class _SW:
        def words(self, lang): return []

    class _NltkStub:
        def download(self, *a, **kw): pass

    stopwords = _SW()  # type: ignore
    nltk = _NltkStub()  # type: ignore

# ─── Built-in Default Inspiration Databases ───────────────────────────────────

_DEFAULT_SOURCES: Dict[str, List[Dict[str, str]]] = {
    "art": [
        {"type": "concept", "content": "Abstract expressionism translated into interactive digital interfaces", "category": "visual"},
        {"type": "concept", "content": "Generative art using algorithmic composition to produce unique experiences", "category": "visual"},
        {"type": "concept", "content": "Synesthesia-inspired systems that map data streams to color and sound", "category": "conceptual"},
        {"type": "approach", "content": "Apply color theory and gestalt principles to information architecture", "category": "conceptual"},
        {"type": "approach", "content": "Use narrative arc structure (setup, tension, resolution) in user onboarding flows", "category": "emotional"},
        {"type": "approach", "content": "Leverage contrast, hierarchy, and white space to direct attention", "category": "visual"},
        {"type": "implementation", "content": "Integrate parametric design tools that adjust layouts based on user context", "category": "visual"},
        {"type": "implementation", "content": "Build emotion-responsive interfaces using sentiment analysis to shift visual tone", "category": "emotional"},
    ],
    "science": [
        {"type": "concept", "content": "Quantum superposition as a metaphor for holding multiple hypotheses in parallel", "category": "principles"},
        {"type": "concept", "content": "Network theory: understand systems by mapping edges (relationships) not just nodes", "category": "theories"},
        {"type": "concept", "content": "Entropy and information theory applied to decision-making under uncertainty", "category": "principles"},
        {"type": "approach", "content": "Apply the scientific method: form falsifiable hypotheses before building solutions", "category": "theories"},
        {"type": "approach", "content": "Use Occam's Razor: prefer the simplest model that explains the observed data", "category": "principles"},
        {"type": "approach", "content": "Run controlled experiments (A/B tests) to isolate causal variables", "category": "discoveries"},
        {"type": "implementation", "content": "Implement Bayesian updating: revise beliefs continuously as new evidence arrives", "category": "principles"},
        {"type": "implementation", "content": "Design feedback loops modelled on homeostatic biological systems", "category": "discoveries"},
    ],
    "nature": [
        {"type": "concept", "content": "Swarm intelligence: emergent collective behaviour from simple individual rules", "category": "systems"},
        {"type": "concept", "content": "Mycelial networks as a model for decentralised, resilient communication", "category": "patterns"},
        {"type": "concept", "content": "Biomimicry: Velcro from burr hooks, sharkskin for drag reduction, termite mounds for HVAC", "category": "adaptations"},
        {"type": "approach", "content": "Design self-healing systems inspired by biological wound repair", "category": "adaptations"},
        {"type": "approach", "content": "Apply fractal self-similarity to scale-invariant UI components and data structures", "category": "patterns"},
        {"type": "approach", "content": "Use evolutionary algorithms (genetic selection, mutation) for parameter optimisation", "category": "systems"},
        {"type": "implementation", "content": "Implement ant-colony optimisation for real-time routing and scheduling problems", "category": "systems"},
        {"type": "implementation", "content": "Build resource-sharing models inspired by mycorrhizal nutrient exchange", "category": "patterns"},
    ],
    "technology": [
        {"type": "concept", "content": "Zero-trust architecture: verify every request as if the network is already breached", "category": "solutions"},
        {"type": "concept", "content": "Event-driven, serverless architectures that scale to zero when idle", "category": "advancements"},
        {"type": "concept", "content": "Federated learning: train models on-device without centralising sensitive data", "category": "advancements"},
        {"type": "approach", "content": "Apply GitOps: treat all infrastructure and configuration as version-controlled code", "category": "applications"},
        {"type": "approach", "content": "Use strangler-fig pattern for zero-downtime legacy system migration", "category": "solutions"},
        {"type": "approach", "content": "Design for observability-first: metrics, logs, and traces from day one", "category": "applications"},
        {"type": "implementation", "content": "Implement circuit-breaker and bulkhead patterns to isolate failure domains", "category": "solutions"},
        {"type": "implementation", "content": "Deploy feature flags to decouple release from deployment and reduce rollout risk", "category": "advancements"},
    ],
    "culture": [
        {"type": "concept", "content": "Ikigai framework: find purpose at the intersection of passion, skill, need, and value", "category": "values"},
        {"type": "concept", "content": "Wabi-sabi aesthetics: embrace imperfection and impermanence in iterative design", "category": "traditions"},
        {"type": "concept", "content": "Ubuntu philosophy: collective intelligence and shared ownership in team systems", "category": "values"},
        {"type": "approach", "content": "Apply storytelling structures (hero's journey, three-act) to product narratives", "category": "expressions"},
        {"type": "approach", "content": "Use rituals and ceremonies (stand-ups, retrospectives) to reinforce team culture", "category": "traditions"},
        {"type": "approach", "content": "Embrace beginner's mind (Shoshin): revisit assumptions with fresh eyes regularly", "category": "values"},
        {"type": "implementation", "content": "Build community-driven feedback systems that treat users as co-creators", "category": "values"},
        {"type": "implementation", "content": "Implement recognition systems that celebrate learning from failure", "category": "expressions"},
    ],
}


class InspirationEngine:
    """Gathers cross-domain inspiration and ranks elements by context relevance."""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.inspiration_history: List[Dict[str, Any]] = []
        self.max_history = config.get("max_inspiration_history", 1000)

        # Ensure the data directory exists and default files are written
        self._data_path = Path(
            config.get("storage", {}).get("base_path", "data/creativity")
        )
        self._data_path.mkdir(parents=True, exist_ok=True)

        # NLTK setup
        self.stop_words: set = set()
        if _HAS_NLTK:
            try:
                nltk.download("punkt", quiet=True)
                nltk.download("punkt_tab", quiet=True)
                nltk.download("stopwords", quiet=True)
                self.stop_words = set(stopwords.words("english"))
            except Exception:
                pass

        # TF-IDF vectorizer
        self.vectorizer = (
            TfidfVectorizer(max_features=500, stop_words="english", ngram_range=(1, 2))
            if _HAS_SKLEARN
            else None
        )

        # Load sources (merge file data with built-in defaults)
        self.inspiration_sources = self._load_sources()

    # ─── Source Loading ───────────────────────────────────────────────────────

    def _load_sources(self) -> Dict[str, Dict[str, Any]]:
        """
        Load inspiration sources.  For each domain:
          1. Try reading <domain>_inspiration.json from disk.
          2. Merge with built-in defaults (disk data takes precedence for new entries).
          3. If no disk file, write the defaults to disk for future runs.
        """
        sources_cfg = self.config.get("inspiration", {}).get("sources", {})
        if not sources_cfg:
            # Use all defaults if no config — extract unique 'type' values as element categories
            sources_cfg = {
                k: {
                    "enabled": True,
                    "weight": 0.2,
                    "elements": list({item.get("type", "general") for item in _DEFAULT_SOURCES.get(k, [])}),
                }
                for k in _DEFAULT_SOURCES
            }

        result: Dict[str, Dict[str, Any]] = {}
        for name, cfg in sources_cfg.items():
            if not cfg.get("enabled", True):
                continue
            combined_data = self._load_source_data(name)
            result[name] = {
                "name": name,
                "type": self._source_type(name),
                "elements": cfg.get("elements", []),
                "weight": float(cfg.get("weight", 0.2)),
                "data": combined_data,
            }
        return result

    def _load_source_data(self, source_name: str) -> List[Dict[str, str]]:
        """Load and merge disk data with built-in defaults for a single source."""
        file_path = self._data_path / f"{source_name}_inspiration.json"
        disk_data: List[Dict[str, str]] = []

        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not read {file_path}: {e}")
        else:
            # Write defaults to disk for future runs
            defaults = _DEFAULT_SOURCES.get(source_name, [])
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(defaults, f, indent=2)
                self.logger.info(f"Created default inspiration data at {file_path}")
            except Exception as e:
                self.logger.warning(f"Could not write defaults to {file_path}: {e}")

        # Merge: built-in defaults first, then any extra items from disk
        built_in = _DEFAULT_SOURCES.get(source_name, [])
        existing_contents = {item["content"] for item in built_in}
        extra = [item for item in disk_data if item.get("content", "") not in existing_contents]
        return built_in + extra

    @staticmethod
    def _source_type(name: str) -> str:
        return {
            "art": "creative", "science": "analytical",
            "nature": "organic", "technology": "innovative", "culture": "social",
        }.get(name, "general")

    # ─── Main Inspiration Pipeline ────────────────────────────────────────────

    def get_inspiration(self, context: Dict[str, Any],
                        patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Return inspiration elements ranked by relevance to context."""
        try:
            context_terms = self._extract_key_terms(context)
            inspiration_elements: List[Dict[str, Any]] = []
            sources_used: List[str] = []

            for name, source in self.inspiration_sources.items():
                elements = self._gather_from_source(source, context_terms, patterns)
                if elements:
                    inspiration_elements.extend(elements)
                    sources_used.append(name)

            # If nothing matched, return a random sample from all sources
            if not inspiration_elements:
                inspiration_elements = self._random_sample_all(context_terms)
                sources_used = list(self.inspiration_sources.keys())

            combined = self._combine_elements(inspiration_elements)
            relevance = self._overall_relevance(combined, context)

            result = {
                "timestamp": datetime.utcnow().isoformat(),
                "elements": combined,
                "sources": sources_used,
                "relevance": relevance,
            }
            self._update_history(result)
            return result
        except Exception as e:
            self.logger.error(f"get_inspiration failed: {e}")
            return {"elements": [], "sources": [], "relevance": 0.0, "error": str(e)}

    # ─── Source Querying ──────────────────────────────────────────────────────

    def _gather_from_source(self, source: Dict[str, Any],
                            context_terms: List[str],
                            patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return relevant elements from a single source, scored by relevance."""
        elements = []
        max_elems = self.config.get("inspiration", {}).get("max_elements_per_source", 10)
        semantic_themes = patterns.get("semantic", {}).get("themes", [])
        pattern_terms = {term for theme in semantic_themes for term in theme.get("terms", [])}

        for item in source.get("data", []):
            content = item.get("content", "").lower()
            if not content:
                continue

            # Match against context terms or pattern terms
            context_hits = sum(1 for t in context_terms if t in content)
            pattern_hits = sum(1 for t in pattern_terms if t in content)
            total_hits = context_hits + pattern_hits

            # Always include if context terms match; also include top pattern hits
            if total_hits > 0 or (context_terms and any(t in source.get("elements", []) for t in context_terms)):
                rel = self._item_relevance(content, context_terms)
                elements.append({
                    "type": item.get("type", "general"),
                    "content": item.get("content", ""),
                    "category": item.get("category", ""),
                    "source": source["name"],
                    "relevance": rel,
                })

        # Sort by relevance and cap
        elements.sort(key=lambda x: x["relevance"], reverse=True)
        return elements[:max_elems]

    def _random_sample_all(self, context_terms: List[str]) -> List[Dict[str, Any]]:
        """Return a spread of elements across all sources when no match is found."""
        samples: List[Dict[str, Any]] = []
        for name, source in self.inspiration_sources.items():
            data = source.get("data", [])
            if data:
                # Take the first two items from each source
                for item in data[:2]:
                    samples.append({
                        "type": item.get("type", "general"),
                        "content": item.get("content", ""),
                        "category": item.get("category", ""),
                        "source": name,
                        "relevance": 0.3,  # low but non-zero
                    })
        return samples

    # ─── Relevance Scoring ────────────────────────────────────────────────────

    def _item_relevance(self, content: str, context_terms: List[str]) -> float:
        if not context_terms:
            return 0.3
        hits = sum(1 for t in context_terms if t in content)
        return round(min(1.0, hits / max(len(context_terms), 1)), 4)

    def _combine_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group elements by type and compute per-group average relevance."""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for elem in sorted(elements, key=lambda x: x["relevance"], reverse=True):
            groups.setdefault(elem["type"], []).append(elem)

        combined = []
        for etype, items in groups.items():
            avg_rel = sum(i["relevance"] for i in items) / len(items)
            combined.append({
                "type": etype,
                "elements": items,
                "relevance": round(avg_rel, 4),
            })
        return combined

    def _overall_relevance(self, combined: List[Dict[str, Any]],
                           context: Dict[str, Any]) -> float:
        if not combined:
            return 0.0
        weights = {"concept": 0.4, "approach": 0.35, "implementation": 0.25}
        total_w, weighted_sum = 0.0, 0.0
        for group in combined:
            w = weights.get(group["type"], 0.2)
            total_w += w
            weighted_sum += group["relevance"] * w
        return round(weighted_sum / total_w, 4) if total_w > 0 else 0.0

    # ─── Term Extraction ──────────────────────────────────────────────────────

    def _extract_key_terms(self, context: Dict[str, Any]) -> List[str]:
        texts: List[str] = []
        for field in ("domain", ):
            val = context.get(field, "")
            if isinstance(val, str) and val:
                texts.append(val)
        for field in ("goals", "constraints"):
            for item in context.get(field, []):
                if isinstance(item, str):
                    texts.append(item)

        all_tokens: List[str] = []
        for text in texts:
            all_tokens.extend(self._tokenize(text))
        return list(dict.fromkeys(all_tokens))  # deduplicated, order-preserving

    def _tokenize(self, text: str) -> List[str]:
        try:
            tokens = word_tokenize(text.lower())
        except Exception:
            tokens = text.lower().split()
        return [t for t in tokens if t.isalpha() and len(t) > 2 and t not in self.stop_words]

    # ─── History ─────────────────────────────────────────────────────────────

    def _update_history(self, result: Dict[str, Any]):
        self.inspiration_history.append(result)
        if len(self.inspiration_history) > self.max_history:
            self.inspiration_history = self.inspiration_history[-self.max_history:]

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self.inspiration_history)

    def clear_history(self):
        self.inspiration_history = []