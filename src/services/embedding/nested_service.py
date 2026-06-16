"""
Nested Embedding Service

Embedding service with Continuum Memory System for continual learning.

Implements 4-level memory:
- L0 (token): Fast updates, token-level patterns
- L1 (function): Medium updates, function-level patterns
- L2 (config): Slow updates, configuration-level knowledge
- L3 (platform): Static, core 1C platform knowledge
"""

import hashlib
from typing import Any, Dict, List, Optional, Union

import numpy as np

from src.ml.continual_learning.cms import ContinuumMemorySystem
from src.ml.continual_learning.memory_level import MemoryLevel, MemoryLevelConfig
from src.ml.continual_learning.surprise_calculator import SurpriseCalculator
from src.services.embedding.service import EmbeddingService
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class CodeMemoryLevel(MemoryLevel):
    """Memory level specialized for code embeddings"""

    def __init__(self, config: MemoryLevelConfig, base_model):
        """
        Initialize code memory level

        Args:
            config: Level configuration
            base_model: Base embedding model
        """
        super().__init__(config)
        self.model = base_model

    def encode(self, data: Any, context: Dict) -> np.ndarray:
        """
        Encode code using base model

        Args:
            data: Code string or data to encode
            context: Additional context

        Returns:
            Embedding vector
        """
        self.stats.total_encodes += 1

        if isinstance(data, str):
            # Encode single string
            embedding = self.model.encode([data], show_progress_bar=False)[0]
        elif isinstance(data, list):
            # Encode batch
            embedding = self.model.encode(data, show_progress_bar=False)[0]
        else:
            # Convert to string
            embedding = self.model.encode([str(data)], show_progress_bar=False)[0]

        # Convert to numpy array
        if hasattr(embedding, "tolist"):
            embedding = np.array(embedding.tolist(), dtype="float32")
        else:
            embedding = np.array(embedding, dtype="float32")

        return embedding


class NestedEmbeddingService:
    """
    Embedding service with Continuum Memory System

    Prevents catastrophic forgetting through multi-level memory
    with different update frequencies.

    Levels:
    - token (L0): Fast updates (every step), token-level patterns
    - function (L1): Medium updates (every 100 steps), function patterns
    - config (L2): Slow updates (every 10k steps), config knowledge
    - platform (L3): Static (never updates), core 1C platform

    Example:
        >>> service = NestedEmbeddingService(base_service)
        >>> embedding = service.encode("Функция Test() Возврат 1; КонецФункции")
        >>> service.update_with_surprise(code, actual, predicted)
    """

    def __init__(self, base_service: EmbeddingService):
        """
        Initialize nested embedding service

        Args:
            base_service: Base embedding service
        """
        self.base_service = base_service

        # Get base model
        self.base_model = base_service.model_manager.get_model()
        if not self.base_model:
            raise ValueError("Base service has no model available")

        # Create CMS with 4 levels
        self.cms = self._create_cms()

        # Surprise calculator
        self.surprise_calc = SurpriseCalculator(method="cosine")

        # Statistics
        self.stats = {
            "total_encodes": 0,
            "total_updates": 0,
            "total_high_surprise": 0,
            "total_medium_surprise": 0,
            "total_low_surprise": 0,
        }

        logger.info("Created NestedEmbeddingService with 4-level CMS")

    def _create_cms(self) -> ContinuumMemorySystem:
        """Create CMS with code-specific levels"""
        # Define levels with update frequencies
        levels = [
            ("token", 1, 0.001),  # Update every step
            ("function", 100, 0.0001),  # Update every 100 steps
            ("config", 10000, 0.00001),  # Update every 10k steps
            ("platform", int(1e9), 0.0),  # Effectively frozen
        ]

        # Create CMS
        cms = ContinuumMemorySystem(levels, embedding_dim=768)

        # Override levels with CodeMemoryLevel
        for name, level in cms.levels.items():
            config = level.config

            # Mark platform as frozen
            if name == "platform":
                config.frozen = True

            cms.levels[name] = CodeMemoryLevel(config, self.base_model)

        return cms

    def encode(
        self, code: Union[str, List[str]], context: Optional[Dict] = None
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Encode code using multi-level CMS

        Args:
            code: BSL code to encode (string or list)
            context: Optional context (type, age, etc.)

        Returns:
            Multi-level embedding(s)
        """
        context = context or {}
        self.stats["total_encodes"] += 1

        # Handle batch encoding
        if isinstance(code, list):
            return [self.encode(c, context) for c in code]

        # Compute weights based on context
        weights = self._compute_weights(context)

        # Multi-level encoding
        embedding = self.cms.encode_multi_level(code, context, weights)

        logger.debug(
            "Encoded with nested CMS",
            extra={"code_length": len(code), "weights": weights,
                                      "embedding_shape": embedding.shape},
        )

        return embedding

    def update_with_surprise(self, code: str, actual: Any, predicted: Any, context: Optional[Dict] = None):
        """
        Update CMS based on prediction surprise

        High surprise → update fast levels (token, function)
        Medium surprise → update medium levels (function)
        Low surprise → no updates (rely on existing knowledge)

        Args:
            code: Code that was encoded
            actual: Actual outcome
            predicted: Predicted outcome
            context: Optional context
        """
        context = context or {}
        self.stats["total_updates"] += 1

        # Compute surprise
        surprise = self.surprise_calc.compute(actual, predicted, context)

        # Categorize surprise
        if surprise > 0.7:
            self.stats["total_high_surprise"] += 1
            surprise_level = "high"
        elif surprise > 0.4:
            self.stats["total_medium_surprise"] += 1
            surprise_level = "medium"
        else:
            self.stats["total_low_surprise"] += 1
            surprise_level = "low"

        # Generate key
        key = self._compute_key(code)

        # Update appropriate levels based on surprise
        if surprise > 0.7:  # High surprise
            # Update fast and medium levels
            self.cms.update_level("token", key, code, surprise)
            self.cms.update_level("function", key, code, surprise)

        elif surprise > 0.4:  # Medium surprise
            # Update only fast level
            self.cms.update_level("token", key, code, surprise)

        # Low surprise: no updates (rely on existing knowledge)

        # Advance step
        self.cms.step()

        logger.debug(
            "Updated CMS with surprise",
            extra={"surprise": surprise, "surprise_level": surprise_level,
                "key": key[:16] + "..."},
        )

    def _compute_weights(self, context: Dict) -> Dict[str, float]:
        """
        Compute level weights based on context

        Args:
            context: Context dictionary with keys:
                - type: "platform" | "config" | "function" | "token"
                - age: age in days
                - novelty: 0.0 to 1.0

        Returns:
            Dict mapping level_name -> weight
        """
        code_type = context.get("type", "unknown")
        age_days = context.get("age", 0)
        novelty = context.get("novelty", 0.5)

        if code_type == "platform":
            # Platform code: rely heavily on static knowledge
            return {"token": 0.05, "function": 0.05, "config": 0.15, "platform": 0.75}

        elif code_type == "config":
            # Configuration code: balanced with config emphasis
            return {"token": 0.15, "function": 0.20, "config": 0.50, "platform": 0.15}

        elif age_days < 7:
            # Recent code: rely on fast levels
            return {"token": 0.45, "function": 0.35, "config": 0.15, "platform": 0.05}

        elif novelty > 0.7:
            # Novel code: emphasize learning levels
            return {"token": 0.40, "function": 0.35, "config": 0.20, "platform": 0.05}

        else:
            # Default: balanced weights
            return {"token": 0.25, "function": 0.30, "config": 0.30, "platform": 0.15}

    def _compute_key(self, code: str) -> str:
        """
        Compute unique key for code

        Args:
            code: Code string

        Returns:
            Hash key
        """
        return hashlib.sha256(code.encode()).hexdigest()

    def get_stats(self) -> Dict:
        """
        Get service statistics

        Returns:
            Statistics dictionary
        """
        cms_stats = self.cms.get_stats()

        return {**self.stats, "cms": cms_stats.to_dict()}

    def health_check(self) -> Dict:
        """
        Health check for nested service

        Returns:
            Health status
        """
        return {
            "status": "healthy",
            "base_service": self.base_service.health_check(),
            "cms_levels": len(self.cms.levels),
            "cms_step": self.cms.global_step,
            "stats": self.stats,
        }
