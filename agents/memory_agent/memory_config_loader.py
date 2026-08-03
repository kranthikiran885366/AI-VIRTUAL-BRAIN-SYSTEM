"""Memory agent config loader — reads memory_config.yaml + env overrides."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "memory_config.yaml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        logger.warning("memory_config_loader: PyYAML not installed, using defaults")
        return {}
    except FileNotFoundError:
        logger.warning("memory_config_loader: %s not found, using defaults", path)
        return {}
    except Exception as exc:
        logger.error("memory_config_loader: failed to load %s error=%s", path, exc)
        return {}


def _flatten(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dict with underscore-joined keys."""
    out: Dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}_{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


def load_memory_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Load memory configuration from memory_config.yaml.
    Env vars prefixed MEMORY_ override YAML values.
    Caller-supplied overrides take highest precedence.
    Returns a flat dict suitable for passing as `config` to MemoryStorage / MemoryProcessor.
    """
    raw = _load_yaml(_CONFIG_PATH)

    # Build flat config from nested YAML sections
    cfg: Dict[str, Any] = {}

    storage = raw.get("storage", {})
    cfg["sqlite_path"] = storage.get("sqlite_path", "data/brain.db")
    cfg["cache_capacity"] = int(storage.get("cache_capacity", 2000))
    cfg["embedding_model"] = storage.get("embedding_model", "all-MiniLM-L6-v2")
    cfg["w_keyword"] = float(storage.get("w_keyword", 0.35))
    cfg["w_vector"] = float(storage.get("w_vector", 0.35))
    cfg["w_importance"] = float(storage.get("w_importance", 0.15))
    cfg["w_recency"] = float(storage.get("w_recency", 0.10))
    cfg["w_frequency"] = float(storage.get("w_frequency", 0.05))

    consolidation = raw.get("consolidation", {})
    cfg["consolidation_threshold"] = float(consolidation.get("consolidation_threshold", 0.65))
    cfg["duplicate_similarity_threshold"] = float(consolidation.get("duplicate_similarity_threshold", 0.90))
    cfg["maintenance_interval_seconds"] = float(consolidation.get("maintenance_interval_seconds", 60.0))

    retrieval = raw.get("retrieval", {})
    cfg["default_limit"] = int(retrieval.get("default_limit", 10))
    cfg["max_limit"] = int(retrieval.get("max_limit", 500))
    cfg["max_query_length"] = int(retrieval.get("max_query_length", 2000))
    cfg["max_payload_bytes"] = int(retrieval.get("max_payload_bytes", 65536))
    cfg["traversal_max_depth"] = int(retrieval.get("traversal_max_depth", 3))

    automation = raw.get("automation", {})
    cfg["automation_rules_path"] = automation.get("rules_path", "data/memory_automation_rules.json")
    cfg["automation_max_history"] = int(automation.get("max_history", 1000))

    observability = raw.get("observability", {})
    cfg["log_slow_query_ms"] = float(observability.get("log_slow_query_ms", 100))
    cfg["emit_metrics"] = bool(observability.get("emit_metrics", True))

    # Retention policies — kept as nested dict for MemoryProcessor
    cfg["retention"] = raw.get("retention", {})

    # Env overrides: MEMORY_SQLITE_PATH, MEMORY_CACHE_CAPACITY, etc.
    for key in list(cfg.keys()):
        env_key = f"MEMORY_{key.upper()}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            # Attempt type coercion based on current value type
            current = cfg[key]
            try:
                if isinstance(current, bool):
                    cfg[key] = env_val.lower() in ("1", "true", "yes")
                elif isinstance(current, int):
                    cfg[key] = int(env_val)
                elif isinstance(current, float):
                    cfg[key] = float(env_val)
                else:
                    cfg[key] = env_val
            except (ValueError, TypeError):
                cfg[key] = env_val

    # Caller overrides take highest precedence
    if overrides:
        cfg.update(overrides)

    return cfg
