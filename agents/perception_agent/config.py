"""Configuration for the perception agent and its modules."""

import os
from typing import Dict, Any

# Base configuration
BASE_CONFIG = {
    "temporal_window": 30,  # Number of frames to keep in temporal buffer
    "confidence_threshold": 0.7,  # Minimum confidence threshold for detections
}

# Fusion module configuration
FUSION_CONFIG = {
    "device": "cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu",
    "model_path": "openai/clip-vit-base-patch32",
    "confidence_threshold": 0.7,
    "temporal_window": 30,
    "feature_dim": 512
}

# Anomaly detector configuration
ANOMALY_CONFIG = {
    "contamination": 0.1,  # Expected proportion of anomalies in the data
    "n_estimators": 100,  # Number of trees in the isolation forest
    "max_samples": 256,  # Maximum number of samples per tree
    "confidence_threshold": 0.7,
    "temporal_window": 30,
    "feature_dim": 512
}

# Threat analyzer configuration
THREAT_CONFIG = {
    "model_path": "microsoft/deberta-v3-base",  # Pre-trained model for threat classification
    "device": "cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu",
    "confidence_threshold": 0.7,
    "temporal_window": 30,
    "threat_categories": [
        "violence",
        "weapon",
        "suspicious_behavior",
        "unauthorized_access",
        "environmental_hazard",
        "medical_emergency",
        "fire",
        "chemical_spill",
        "natural_disaster",
        "cyber_threat"
    ]
}

# Complete perception agent configuration
PERCEPTION_CONFIG = {
    **BASE_CONFIG,
    "fusion_config": FUSION_CONFIG,
    "anomaly_config": ANOMALY_CONFIG,
    "threat_config": THREAT_CONFIG
}

def get_config() -> Dict[str, Any]:
    """Get the complete configuration for the perception agent."""
    return PERCEPTION_CONFIG 