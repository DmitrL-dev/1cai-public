"""Micro-Model Swarm — zero-dependency ML inference for 1cAI.

Ported from SENTINEL virtualconv-engine.
Pure Python autograd (Karpathy-inspired), no sklearn/torch at inference.

Usage:
    from micro_swarm import MicroModel, MicroModelConfig, DomainConfig, FeatureSpec

Architecture:
    Value (autograd) → MicroModel (micro-transformer) → DomainConfig (feature extraction)

BSL Domains (Phase 3.5):
    BSL_PATTERN_DOMAIN, BSL_QUALITY_DOMAIN, QUERY_OPTIMIZER_DOMAIN,
    ERROR_PREDICTOR_DOMAIN, CONFIG_SIMILARITY_DOMAIN
"""

from src.micro_swarm.bsl_domains import (
    BSL_PATTERN_DOMAIN,
    BSL_QUALITY_DOMAIN,
    CONFIG_SIMILARITY_DOMAIN,
    ERROR_PREDICTOR_DOMAIN,
    QUERY_OPTIMIZER_DOMAIN,
    extract_bsl_pattern_features,
    extract_bsl_quality_features,
    extract_config_features,
    extract_error_features,
    extract_query_optimizer_features,
)
from src.micro_swarm.domains import (
    ANOMALY_DETECTION_DOMAIN,
    QUERY_INTENT_DOMAIN,
    ROLE_DETECTION_DOMAIN,
    DomainConfig,
    FeatureSpec,
    NormMethod,
)
from src.micro_swarm.engine import Value
from src.micro_swarm.model import MicroModel, MicroModelConfig
from src.micro_swarm.router import (
    RouterDecision,
    RouterResult,
    SwarmRouter,
    TemplateResponder,
)

__all__ = [
    "Value",
    "MicroModel",
    "MicroModelConfig",
    "DomainConfig",
    "FeatureSpec",
    "NormMethod",
    # General domains
    "QUERY_INTENT_DOMAIN",
    "ROLE_DETECTION_DOMAIN",
    "ANOMALY_DETECTION_DOMAIN",
    # BSL domains
    "BSL_PATTERN_DOMAIN",
    "BSL_QUALITY_DOMAIN",
    "QUERY_OPTIMIZER_DOMAIN",
    "ERROR_PREDICTOR_DOMAIN",
    "CONFIG_SIMILARITY_DOMAIN",
    # BSL extractors
    "extract_bsl_pattern_features",
    "extract_bsl_quality_features",
    "extract_query_optimizer_features",
    "extract_error_features",
    "extract_config_features",
    # Router (Phase 5.0)
    "RouterDecision",
    "RouterResult",
    "SwarmRouter",
    "TemplateResponder",
]
