"""
PatternRecognizer — Production implementation.

Extracts structural, temporal, and semantic patterns from context data.
Works with or without scikit-learn (full pure-Python fallback paths).
"""

import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

    class _NpStub:
        def mean(self, x): return sum(x) / len(x) if x else 0.0
        def std(self, x):
            if not x:
                return 0.0
            m = sum(x) / len(x)
            return (sum((v - m) ** 2 for v in x) / len(x)) ** 0.5

    np = _NpStub()  # type: ignore

try:
    from sklearn.cluster import DBSCAN
    from sklearn.feature_extraction.text import TfidfVectorizer
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False
    DBSCAN = None  # type: ignore
    TfidfVectorizer = None  # type: ignore

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


class PatternRecognizer:
    """Extracts structural, temporal, and semantic patterns from agent context."""

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.pattern_history: List[Dict[str, Any]] = []
        self.max_history = int(config.get("max_pattern_history", 1000))

        self.stop_words: set = set()
        if _HAS_NLTK:
            try:
                nltk.download("punkt", quiet=True)
                nltk.download("punkt_tab", quiet=True)
                nltk.download("stopwords", quiet=True)
                self.stop_words = set(stopwords.words("english"))
            except Exception:
                pass

        self.vectorizer = (
            TfidfVectorizer(max_features=1000, stop_words="english", ngram_range=(1, 2))
            if _HAS_SKLEARN else None
        )

    # ─── Main Entry Point ─────────────────────────────────────────────────────

    def analyze_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run all three pattern analyses and return a unified result."""
        try:
            structural = self._analyze_structural(context)
            temporal = self._analyze_temporal(context)
            semantic = self._analyze_semantic(context)
            patterns = {
                "timestamp": datetime.utcnow().isoformat(),
                "structural": structural,
                "temporal": temporal,
                "semantic": semantic,
                "influence": self._pattern_influence(structural, temporal, semantic),
            }
            self._update_history(patterns)
            return patterns
        except Exception as e:
            self.logger.error(f"analyze_patterns failed: {e}")
            return {"structural": {}, "temporal": {}, "semantic": {"themes": []}, "influence": {}}

    # ─── Structural Patterns ──────────────────────────────────────────────────

    def _analyze_structural(self, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            texts = self._extract_texts(context)
            if not texts:
                return {"hierarchies": [], "relationships": [], "dependencies": []}

            if _HAS_SKLEARN and self.vectorizer and len(texts) >= 2:
                return self._structural_sklearn(texts)
            return self._structural_fallback(texts)
        except Exception as e:
            self.logger.error(f"_analyze_structural failed: {e}")
            return {"hierarchies": [], "relationships": [], "dependencies": []}

    def _structural_sklearn(self, texts: List[str]) -> Dict[str, Any]:
        vectors = self.vectorizer.fit_transform(texts)
        labels = DBSCAN(eps=0.5, min_samples=2).fit(vectors).labels_
        hierarchies = self._hierarchies_from_clusters(texts, labels)
        relationships = self._relationships_from_vectors(texts, vectors)
        dependencies = self._extract_dependencies(texts)
        return {"hierarchies": hierarchies, "relationships": relationships, "dependencies": dependencies}

    def _structural_fallback(self, texts: List[str]) -> Dict[str, Any]:
        """Pure-Python structural analysis using word-overlap clustering."""
        # Simple greedy clustering: group texts that share ≥30% word overlap
        clusters: Dict[int, List[str]] = {}
        cluster_id = 0
        assigned = {}

        for i, t1 in enumerate(texts):
            if i in assigned:
                continue
            cid = cluster_id
            clusters[cid] = [t1]
            assigned[i] = cid
            for j, t2 in enumerate(texts):
                if j <= i or j in assigned:
                    continue
                if self._word_overlap(t1, t2) >= 0.3:
                    clusters[cid].append(t2)
                    assigned[j] = cid
            cluster_id += 1

        hierarchies = []
        for cid, cluster_texts in clusters.items():
            terms = self._key_terms_from_texts(cluster_texts)
            hierarchies.append({
                "cluster_id": cid,
                "key_terms": terms,
                "relationships": self._term_co_occurrences(cluster_texts, terms),
            })

        relationships = []
        for i, t1 in enumerate(texts):
            for j, t2 in enumerate(texts):
                if j <= i:
                    continue
                sim = self._word_overlap(t1, t2)
                if sim > 0.25:
                    relationships.append({
                        "source": t1[:80], "target": t2[:80],
                        "similarity": round(sim, 3),
                        "type": self._rel_type(t1, t2),
                    })

        return {
            "hierarchies": hierarchies,
            "relationships": relationships[:30],
            "dependencies": self._extract_dependencies(texts),
        }

    # ─── Temporal Patterns ────────────────────────────────────────────────────

    def _analyze_temporal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            events = self._extract_temporal_events(context)
            if not events:
                return {"sequences": [], "cycles": [], "trends": []}
            return {
                "sequences": self._sequences(events),
                "cycles": self._cycles(events),
                "trends": self._trends(events),
            }
        except Exception as e:
            self.logger.error(f"_analyze_temporal failed: {e}")
            return {"sequences": [], "cycles": [], "trends": []}

    def _extract_temporal_events(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        events = []
        for idea in context.get("previous_ideas", []):
            if isinstance(idea, dict):
                meta = idea.get("metadata", {})
                ts = meta.get("timestamp", "")
                if ts:
                    events.append({"timestamp": ts, "event": "idea", "data": idea})
        return events

    def _sequences(self, events: List[Dict]) -> List[Dict]:
        sorted_evs = sorted(events, key=lambda x: x.get("timestamp", ""))
        sequences, current = [], []
        for ev in sorted_evs:
            if not current or self._events_related(current[-1], ev):
                current.append(ev)
            else:
                if len(current) > 1:
                    sequences.append({"events": current[:5], "type": "sequence", "confidence": 0.75})
                current = [ev]
        if len(current) > 1:
            sequences.append({"events": current[:5], "type": "sequence", "confidence": 0.75})
        return sequences

    def _cycles(self, events: List[Dict]) -> List[Dict]:
        groups: Dict[str, List] = {}
        for ev in events:
            groups.setdefault(ev.get("event", "unknown"), []).append(ev)
        cycles = []
        for etype, evs in groups.items():
            if len(evs) >= 3:
                intervals = self._time_intervals(evs)
                if intervals and self._is_cyclic(intervals):
                    cycles.append({
                        "event_type": etype,
                        "count": len(evs),
                        "interval_mean_seconds": round(sum(intervals) / len(intervals), 1),
                        "confidence": 0.7,
                    })
        return cycles

    def _trends(self, events: List[Dict]) -> List[Dict]:
        groups: Dict[str, List] = {}
        for ev in events:
            groups.setdefault(ev.get("event", "unknown"), []).append(ev)
        trends = []
        for etype, evs in groups.items():
            if len(evs) >= 2:
                n = len(evs)
                direction = "increasing" if n > 2 else "stable"
                magnitude = round(min(1.0, n / 10.0), 3)
                confidence = round(min(0.85, 0.5 + (n - 2) * 0.05), 3)
                if confidence > 0.55:
                    trends.append({
                        "event_type": etype,
                        "direction": direction,
                        "magnitude": magnitude,
                        "confidence": confidence,
                    })
        return trends

    # ─── Semantic Patterns ────────────────────────────────────────────────────

    def _analyze_semantic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            texts = self._extract_texts(context)
            if not texts:
                return {"themes": [], "concepts": [], "associations": []}

            themes = self._extract_themes(texts)
            concepts = self._extract_concepts(texts)
            associations = self._extract_associations(texts)
            return {"themes": themes, "concepts": concepts, "associations": associations}
        except Exception as e:
            self.logger.error(f"_analyze_semantic failed: {e}")
            return {"themes": [], "concepts": [], "associations": []}

    def _extract_themes(self, texts: List[str]) -> List[Dict[str, Any]]:
        if _HAS_SKLEARN and self.vectorizer and len(texts) >= 2:
            return self._themes_sklearn(texts)
        return self._themes_fallback(texts)

    def _themes_sklearn(self, texts: List[str]) -> List[Dict[str, Any]]:
        try:
            vectors = self.vectorizer.fit_transform(texts)
            feature_names = self.vectorizer.get_feature_names_out()
            themes = []
            for i, text in enumerate(texts):
                vec = vectors[i].toarray()[0]
                top_idx = vec.argsort()[-5:][::-1]
                terms = [feature_names[j] for j in top_idx if vec[j] > 0]
                scores = [round(float(vec[j]), 4) for j in top_idx if vec[j] > 0]
                if terms:
                    themes.append({"text": text[:80], "terms": terms, "scores": scores, "confidence": 0.85})
            return themes
        except Exception:
            return self._themes_fallback(texts)

    def _themes_fallback(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Pure-Python theme extraction using word frequency."""
        themes = []
        for text in texts:
            words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", text)
                     if w.lower() not in self.stop_words]
            if not words:
                continue
            freq = Counter(words)
            top = freq.most_common(5)
            total = len(words)
            themes.append({
                "text": text[:80],
                "terms": [t for t, _ in top],
                "scores": [round(c / total, 4) for _, c in top],
                "confidence": 0.65,
            })
        return themes

    def _extract_concepts(self, texts: List[str]) -> List[Dict[str, Any]]:
        concepts = []
        for text in texts:
            terms = self._key_terms_from_texts([text])
            if terms:
                concepts.append({"text": text[:80], "terms": terms[:8], "confidence": 0.7})
        return concepts

    def _extract_associations(self, texts: List[str]) -> List[Dict[str, Any]]:
        if _HAS_SKLEARN and self.vectorizer and len(texts) >= 2:
            return self._associations_sklearn(texts)
        return self._associations_fallback(texts)

    def _associations_sklearn(self, texts: List[str]) -> List[Dict[str, Any]]:
        try:
            vectors = self.vectorizer.fit_transform(texts)
            feature_names = self.vectorizer.get_feature_names_out()
            associations = []
            for i, text in enumerate(texts):
                vec = vectors[i].toarray()[0]
                top_idx = vec.argsort()[-8:][::-1]
                active = [j for j in top_idx if vec[j] > 0]
                for a in range(len(active)):
                    for b in range(a + 1, len(active)):
                        strength = round(float(vec[active[a]] * vec[active[b]]), 4)
                        if strength > 0:
                            associations.append({
                                "term1": feature_names[active[a]],
                                "term2": feature_names[active[b]],
                                "strength": strength,
                                "context": text[:60],
                            })
            return associations[:50]
        except Exception:
            return self._associations_fallback(texts)

    def _associations_fallback(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Pure-Python association detection via co-occurrence in the same text."""
        associations = []
        for text in texts:
            terms = self._key_terms_from_texts([text])[:8]
            for i in range(len(terms)):
                for j in range(i + 1, len(terms)):
                    associations.append({
                        "term1": terms[i], "term2": terms[j],
                        "strength": round(1.0 / (j - i + 1), 4),
                        "context": text[:60],
                    })
        return associations[:50]

    # ─── Pattern Influence ────────────────────────────────────────────────────

    def _pattern_influence(self, structural: Dict, temporal: Dict, semantic: Dict) -> Dict[str, float]:
        s = self._type_influence(structural)
        t = self._type_influence(temporal)
        sem = self._type_influence(semantic)
        total = s + t + sem
        if total == 0:
            return {"structural": 0.33, "temporal": 0.33, "semantic": 0.34}
        return {
            "structural": round(s / total, 3),
            "temporal": round(t / total, 3),
            "semantic": round(sem / total, 3),
        }

    def _type_influence(self, patterns: Dict[str, Any]) -> float:
        influence, count = 0.0, 0
        for v in patterns.values():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        influence += item.get("confidence", 0.5)
                        count += 1
        return influence / count if count > 0 else 0.0

    # ─── History & Search ─────────────────────────────────────────────────────

    def _update_history(self, patterns: Dict[str, Any]):
        self.pattern_history.append(patterns)
        if len(self.pattern_history) > self.max_history:
            self.pattern_history = self.pattern_history[-self.max_history:]

    def get_pattern_history(self) -> List[Dict[str, Any]]:
        return list(self.pattern_history)

    def clear_pattern_history(self):
        self.pattern_history = []

    def find_similar_patterns(self, pattern: Dict[str, Any],
                              threshold: float = 0.7) -> List[Dict[str, Any]]:
        results = []
        for hist in self.pattern_history:
            sim = self._pattern_similarity(pattern, hist)
            if sim >= threshold:
                results.append({"pattern": hist, "similarity": sim})
        return sorted(results, key=lambda x: x["similarity"], reverse=True)

    def _pattern_similarity(self, p1: Dict, p2: Dict) -> float:
        s = self._type_similarity(p1.get("structural", {}), p2.get("structural", {}))
        t = self._type_similarity(p1.get("temporal", {}), p2.get("temporal", {}))
        sem = self._type_similarity(p1.get("semantic", {}), p2.get("semantic", {}))
        inf = p1.get("influence", {"structural": 0.33, "temporal": 0.33, "semantic": 0.34})
        return round(
            s * inf.get("structural", 0.33) +
            t * inf.get("temporal", 0.33) +
            sem * inf.get("semantic", 0.34),
            3,
        )

    def _type_similarity(self, t1: Dict, t2: Dict) -> float:
        sims = []
        for key in t1:
            if key in t2:
                l1, l2 = t1[key], t2[key]
                if isinstance(l1, list) and isinstance(l2, list):
                    s1 = {str(x) for x in l1}
                    s2 = {str(x) for x in l2}
                    union = s1 | s2
                    sims.append(len(s1 & s2) / len(union) if union else 0.0)
        return round(sum(sims) / len(sims), 3) if sims else 0.0

    # ─── Text Utilities ───────────────────────────────────────────────────────

    def _extract_texts(self, context: Dict[str, Any]) -> List[str]:
        texts = []
        if "domain" in context:
            texts.append(str(context["domain"]))
        for field in ("goals", "constraints"):
            for item in context.get(field, []):
                if isinstance(item, str) and item.strip():
                    texts.append(item)
        for idea in context.get("previous_ideas", []):
            if isinstance(idea, dict):
                for k in ("concept", "approach", "implementation"):
                    v = idea.get(k, "")
                    if v:
                        texts.append(v)
            elif isinstance(idea, str) and idea.strip():
                texts.append(idea)
        return [t for t in texts if t.strip()]

    def _key_terms_from_texts(self, texts: List[str]) -> List[str]:
        if _HAS_SKLEARN and self.vectorizer and len(texts) >= 2:
            try:
                vecs = self.vectorizer.fit_transform(texts)
                fnames = self.vectorizer.get_feature_names_out()
                terms = []
                for i in range(len(texts)):
                    vec = vecs[i].toarray()[0]
                    top = vec.argsort()[-5:][::-1]
                    terms.extend(fnames[j] for j in top if vec[j] > 0)
                return list(dict.fromkeys(terms))
            except Exception:
                pass
        # Pure-Python fallback
        all_words: List[str] = []
        for text in texts:
            all_words.extend(
                w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", text)
                if w.lower() not in self.stop_words
            )
        freq = Counter(all_words)
        return [w for w, _ in freq.most_common(10)]

    def _term_co_occurrences(self, texts: List[str], terms: List[str]) -> List[Dict[str, Any]]:
        results = []
        for text in texts:
            tokens = set(word_tokenize(text.lower()))
            for i, t1 in enumerate(terms):
                for t2 in terms[i + 1:]:
                    if t1 in tokens and t2 in tokens:
                        results.append({"term1": t1, "term2": t2, "context": text[:60], "type": "co_occurrence"})
        return results

    def _extract_dependencies(self, texts: List[str]) -> List[Dict[str, Any]]:
        dep_words = {"requires", "needs", "depends", "relies", "uses"}
        deps = []
        for text in texts:
            tokens = word_tokenize(text.lower())
            for i, tok in enumerate(tokens):
                if tok in dep_words and i + 1 < len(tokens):
                    deps.append({
                        "source": text[:80],
                        "target": " ".join(tokens[i + 1: i + 3]),
                        "type": "dependency",
                        "confidence": 0.7,
                    })
        return deps

    def _word_overlap(self, text1: str, text2: str) -> float:
        """Jaccard similarity between word sets."""
        s1 = set(re.findall(r"\b[a-zA-Z]{3,}\b", text1.lower()))
        s2 = set(re.findall(r"\b[a-zA-Z]{3,}\b", text2.lower()))
        s1 -= self.stop_words
        s2 -= self.stop_words
        union = s1 | s2
        return len(s1 & s2) / len(union) if union else 0.0

    def _rel_type(self, text1: str, text2: str) -> str:
        lower = text1.lower()
        if any(w in lower for w in ("requires", "needs", "depends")):
            return "dependency"
        if any(w in lower for w in ("similar", "like", "resembles")):
            return "similarity"
        if any(w in lower for w in ("opposite", "different", "unlike")):
            return "contrast"
        return "related"

    def _hierarchies_from_clusters(self, texts: List[str], labels) -> List[Dict[str, Any]]:
        clusters: Dict[int, List[str]] = {}
        for i, label in enumerate(labels):
            lbl = int(label)
            if lbl == -1:
                continue
            clusters.setdefault(lbl, []).append(texts[i])
        hierarchies = []
        for cid, cluster_texts in clusters.items():
            terms = self._key_terms_from_texts(cluster_texts)
            hierarchies.append({
                "cluster_id": cid,
                "key_terms": terms,
                "relationships": self._term_co_occurrences(cluster_texts, terms),
            })
        return hierarchies

    def _relationships_from_vectors(self, texts: List[str], vectors) -> List[Dict[str, Any]]:
        try:
            sim_matrix = (vectors * vectors.T).toarray()
            rels = []
            for i in range(len(texts)):
                for j in range(i + 1, len(texts)):
                    sim = float(sim_matrix[i, j])
                    if sim > 0.2:
                        rels.append({
                            "source": texts[i][:80], "target": texts[j][:80],
                            "similarity": round(sim, 3),
                            "type": self._rel_type(texts[i], texts[j]),
                        })
            return rels
        except Exception:
            return []

    def _events_related(self, e1: Dict, e2: Dict) -> bool:
        if e1.get("event") != e2.get("event"):
            return False
        try:
            t1 = datetime.fromisoformat(e1["timestamp"])
            t2 = datetime.fromisoformat(e2["timestamp"])
            return abs((t2 - t1).total_seconds()) <= 3600
        except Exception:
            return False

    def _time_intervals(self, events: List[Dict]) -> List[float]:
        evs = sorted(events, key=lambda x: x.get("timestamp", ""))
        intervals = []
        for i in range(len(evs) - 1):
            try:
                t1 = datetime.fromisoformat(evs[i]["timestamp"])
                t2 = datetime.fromisoformat(evs[i + 1]["timestamp"])
                intervals.append(abs((t2 - t1).total_seconds()))
            except Exception:
                pass
        return intervals

    def _is_cyclic(self, intervals: List[float]) -> bool:
        if len(intervals) < 2:
            return False
        mean = sum(intervals) / len(intervals)
        if mean == 0:
            return False
        std = (sum((v - mean) ** 2 for v in intervals) / len(intervals)) ** 0.5
        return (std / mean) < 0.35
