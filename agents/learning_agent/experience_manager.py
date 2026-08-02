import logging
import math
from typing import Dict, Any, List, Optional
from datetime import datetime


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _linear_slope(values: List[float]) -> float:
    """Pure Python linear regression slope."""
    n = len(values)
    if n < 2:
        return 0.0
    x = list(range(n))
    sx = sum(x)
    sy = sum(values)
    sxy = sum(x[i] * values[i] for i in range(n))
    sx2 = sum(xi ** 2 for xi in x)
    denom = n * sx2 - sx ** 2
    return (n * sxy - sx * sy) / denom if denom != 0 else 0.0


def _exp_decay(days: float, half_life: float = 30.0) -> float:
    """Exponential decay: value halves every half_life days."""
    return math.exp(-days * math.log(2) / half_life)


class ExperienceManager:
    """
    Manages learning experiences: stores, scores, retrieves, and analyzes them.
    All scoring is pure Python — no numpy dependency.
    """

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.experiences: List[Dict[str, Any]] = []
        self.max_experiences = config.get("max_experiences", 1000)
        self.experience_weights: Dict[str, float] = {}
        self.last_update = datetime.now()

        # Track all seen concepts and relationships for novelty scoring
        self._seen_concepts: set = set()
        self._seen_relationships: set = set()

    def process_experience(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        """Process and store a new learning experience with full metrics."""
        try:
            if "timestamp" not in experience:
                experience["timestamp"] = datetime.now().isoformat()

            metrics = self._calculate_experience_metrics(experience)
            experience["metrics"] = metrics

            self._update_experience_weights(experience)
            self._update_seen_sets(experience)

            self.experiences.append(experience)
            if len(self.experiences) > self.max_experiences:
                # Keep highest-value experiences when trimming
                self.experiences.sort(
                    key=lambda e: e.get("metrics", {}).get("learning_value", 0.5),
                    reverse=True,
                )
                self.experiences = self.experiences[:self.max_experiences]

            self.last_update = datetime.now()
            return experience
        except Exception as e:
            self.logger.error(f"Error processing experience: {e}")
            return experience

    def _update_seen_sets(self, experience: Dict[str, Any]):
        """Track seen concepts and relationships for novelty scoring."""
        for c in experience.get("concepts", []):
            term = c.get("term", "") if isinstance(c, dict) else str(c)
            self._seen_concepts.add(term.lower())
        for r in experience.get("relationships", []):
            if isinstance(r, dict):
                key = f"{r.get('source', '')}:{r.get('target', '')}"
                self._seen_relationships.add(key.lower())

    def get_relevant_experiences(self, context: Dict[str, Any],
                                 max_experiences: int = 5) -> List[Dict[str, Any]]:
        """Return experiences most relevant to the given context, ranked by score."""
        try:
            scored = [(exp, self._calculate_relevance(exp, context)) for exp in self.experiences]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [exp for exp, _ in scored[:max_experiences]]
        except Exception as e:
            self.logger.error(f"Error getting relevant experiences: {e}")
            return []

    def get_experience_insights(self) -> Dict[str, Any]:
        try:
            return {
                "total_experiences": len(self.experiences),
                "domains": self._get_domain_distribution(),
                "success_rate": self._calculate_success_rate(),
                "learning_trends": self._analyze_learning_trends(),
                "common_patterns": self._identify_common_patterns(),
                "seen_concepts": len(self._seen_concepts),
                "seen_relationships": len(self._seen_relationships),
                "last_update": self.last_update.isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error getting experience insights: {e}")
            return {}

    def _calculate_experience_metrics(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "complexity": self._calculate_complexity(experience),
            "success": self._calculate_success(experience),
            "learning_value": self._calculate_learning_value(experience),
            "applicability": self._calculate_applicability(experience),
            "novelty": self._calculate_experience_novelty_score(experience),
        }

    def _calculate_complexity(self, experience: Dict[str, Any]) -> float:
        factors = []
        if "input" in experience:
            factors.append(min(1.0, len(str(experience["input"]).split()) / 100.0))
        concept_count = len(experience.get("concepts", []))
        if concept_count:
            factors.append(min(1.0, concept_count / 10.0))
        rel_count = len(experience.get("relationships", []))
        if rel_count:
            factors.append(min(1.0, rel_count / 10.0))
        return round(_mean(factors) if factors else 0.5, 3)

    def _calculate_success(self, experience: Dict[str, Any]) -> float:
        factors = []
        if "success" in experience:
            factors.append(float(experience["success"]))
        if "error" in experience:
            factors.append(0.0 if experience["error"] else 1.0)
        if "confidence" in experience:
            factors.append(float(experience["confidence"]))
        return round(_mean(factors) if factors else 0.5, 3)

    def _calculate_learning_value(self, experience: Dict[str, Any]) -> float:
        factors = []
        novelty = self._calculate_experience_novelty_score(experience)
        factors.append(novelty)
        rel_quality = self._calculate_relationship_quality(experience.get("relationships", []))
        if rel_quality > 0:
            factors.append(rel_quality)
        factors.append(self._calculate_success(experience))
        return round(_mean(factors), 3)

    def _calculate_applicability(self, experience: Dict[str, Any]) -> float:
        factors = []
        domain = experience.get("domain", "")
        if domain:
            factors.append(self._calculate_domain_specificity(domain))
        concepts = experience.get("concepts", [])
        if concepts:
            factors.append(self._calculate_generalizability(concepts))
        return round(_mean(factors) if factors else 0.5, 3)

    def _calculate_experience_novelty_score(self, experience: Dict[str, Any]) -> float:
        """Score novelty: how many concepts/relationships are new vs already seen."""
        concepts = experience.get("concepts", [])
        relationships = experience.get("relationships", [])

        if not concepts and not relationships:
            return 0.5

        novel_concepts = 0
        for c in concepts:
            term = c.get("term", "") if isinstance(c, dict) else str(c)
            if term.lower() not in self._seen_concepts:
                novel_concepts += 1

        novel_rels = 0
        for r in relationships:
            if isinstance(r, dict):
                key = f"{r.get('source', '')}:{r.get('target', '')}".lower()
                if key not in self._seen_relationships:
                    novel_rels += 1

        total = len(concepts) + len(relationships)
        novel = novel_concepts + novel_rels
        return round(novel / total if total > 0 else 0.5, 3)

    def _calculate_concept_novelty(self, concepts: List[Any]) -> float:
        """Fraction of concepts not previously seen."""
        if not concepts:
            return 0.5
        novel = sum(
            1 for c in concepts
            if (c.get("term", "") if isinstance(c, dict) else str(c)).lower()
            not in self._seen_concepts
        )
        return round(novel / len(concepts), 3)

    def _calculate_relationship_quality(self, relationships: List[Any]) -> float:
        """Score relationship quality by type diversity and confidence."""
        if not relationships:
            return 0.0
        type_set = set()
        confidences = []
        for r in relationships:
            if isinstance(r, dict):
                type_set.add(r.get("type", "related_to"))
                conf = r.get("confidence", 0.5)
                confidences.append(float(conf))
        type_diversity = min(1.0, len(type_set) / 5.0)
        avg_conf = _mean(confidences) if confidences else 0.5
        return round(_mean([type_diversity, avg_conf]), 3)

    def _calculate_domain_specificity(self, domain: str) -> float:
        """
        Specific domains score higher (more focused = more applicable).
        General domains score lower.
        """
        general_domains = {"general", "unknown", "misc", "other", "default"}
        if domain.lower() in general_domains:
            return 0.4
        # Longer domain names tend to be more specific
        return round(min(0.9, 0.5 + len(domain.split()) * 0.1), 3)

    def _calculate_generalizability(self, concepts: List[Any]) -> float:
        """
        More diverse concepts = more generalizable knowledge.
        Single-concept experiences are less generalizable.
        """
        if not concepts:
            return 0.3
        count = len(concepts)
        return round(min(0.9, 0.3 + count * 0.06), 3)

    def _calculate_concept_overlap(self, concepts1: List[Any], concepts2: List[Any]) -> float:
        """Jaccard overlap between two concept lists."""
        try:
            def to_set(concepts):
                return {
                    (c.get("term", "") if isinstance(c, dict) else str(c)).lower()
                    for c in concepts
                }
            s1, s2 = to_set(concepts1), to_set(concepts2)
            union = s1 | s2
            return len(s1 & s2) / len(union) if union else 0.0
        except Exception:
            return 0.0

    def _update_experience_weights(self, experience: Dict[str, Any]):
        exp_type = experience.get("type", "unknown")
        success = self._calculate_success(experience)
        current = self.experience_weights.get(exp_type, 0.5)
        alpha = 0.1
        self.experience_weights[exp_type] = round((1 - alpha) * current + alpha * success, 4)

    def _calculate_relevance(self, experience: Dict[str, Any], context: Dict[str, Any]) -> float:
        factors = []
        # Domain match
        if experience.get("domain") and context.get("domain"):
            factors.append(1.0 if experience["domain"] == context["domain"] else 0.1)
        # Concept overlap
        exp_concepts = experience.get("concepts", [])
        ctx_concepts = context.get("concepts", [])
        if exp_concepts and ctx_concepts:
            factors.append(self._calculate_concept_overlap(exp_concepts, ctx_concepts))
        # Temporal relevance: recent experiences are more relevant
        if "timestamp" in experience:
            try:
                ts = datetime.fromisoformat(experience["timestamp"])
                days_ago = (datetime.now() - ts).days
                factors.append(_exp_decay(days_ago, half_life=30.0))
            except Exception:
                pass
        # Weight by experience type
        exp_type = experience.get("type", "unknown")
        factors.append(self.experience_weights.get(exp_type, 0.5))
        return round(_mean(factors), 3)

    def _get_domain_distribution(self) -> Dict[str, float]:
        total = len(self.experiences)
        if total == 0:
            return {}
        counts: Dict[str, int] = {}
        for exp in self.experiences:
            d = exp.get("domain", "unknown")
            counts[d] = counts.get(d, 0) + 1
        return {d: round(c / total, 3) for d, c in counts.items()}

    def _calculate_success_rate(self) -> float:
        if not self.experiences:
            return 0.0
        return round(_mean([self._calculate_success(e) for e in self.experiences]), 3)

    def _analyze_learning_trends(self) -> Dict[str, Any]:
        return {
            "success_trend": round(self._calculate_trend("success"), 4),
            "complexity_trend": round(self._calculate_trend("complexity"), 4),
            "learning_value_trend": round(self._calculate_trend("learning_value"), 4),
        }

    def _calculate_trend(self, metric: str) -> float:
        values = [
            e.get("metrics", {}).get(metric, 0.5)
            for e in self.experiences
            if "metrics" in e and metric in e["metrics"]
        ]
        return _linear_slope(values) if len(values) >= 2 else 0.0

    def _identify_common_patterns(self) -> List[Dict[str, Any]]:
        try:
            domain_groups: Dict[str, List] = {}
            for exp in self.experiences:
                d = exp.get("domain", "unknown")
                domain_groups.setdefault(d, []).append(exp)
            patterns = []
            for domain, exps in domain_groups.items():
                if len(exps) >= 3:
                    patterns.append({
                        "domain": domain,
                        "count": len(exps),
                        "common_concepts": self._find_common_concepts(exps),
                        "success_factors": self._identify_success_factors(exps),
                        "avg_success": round(_mean([self._calculate_success(e) for e in exps]), 3),
                    })
            return sorted(patterns, key=lambda x: x["count"], reverse=True)
        except Exception as e:
            self.logger.error(f"Error identifying common patterns: {e}")
            return []

    def _find_common_concepts(self, experiences: List[Dict[str, Any]]) -> List[str]:
        counts: Dict[str, int] = {}
        for exp in experiences:
            for c in exp.get("concepts", []):
                term = c.get("term", "") if isinstance(c, dict) else str(c)
                if term:
                    counts[term] = counts.get(term, 0) + 1
        threshold = len(experiences) * 0.5
        return [t for t, cnt in counts.items() if cnt >= threshold]

    def _identify_success_factors(self, experiences: List[Dict[str, Any]]) -> List[str]:
        successful = [e for e in experiences if self._calculate_success(e) > 0.7]
        unsuccessful = [e for e in experiences if self._calculate_success(e) < 0.3]
        if not successful or not unsuccessful:
            return []
        success_factors = []
        for exp in successful:
            for factor in exp.get("factors", []):
                if not any(factor in u.get("factors", []) for u in unsuccessful):
                    success_factors.append(factor)
        return list(set(success_factors))

    def reset(self):
        self.experiences = []
        self.experience_weights = {}
        self._seen_concepts = set()
        self._seen_relationships = set()
        self.last_update = datetime.now()
