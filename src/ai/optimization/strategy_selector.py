"""
Strategy Selector
-----------------

Implements Multi-Armed Bandit (Thompson Sampling) for adaptive strategy selection.
Part of Phase 2: The Brain (Meta-Optimizer).
"""

import random
import math
import logging
from typing import Dict, List, Optional
from enum import Enum

from src.ai.query_classifier import AIService
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class StrategySelector:
    """
    Selects the best AI service strategy using Thompson Sampling.
    """

    def __init__(self):
        # Beta distribution parameters for each arm (service)
        # alpha = successes + 1
        # beta = failures + 1
        self._stats: Dict[str, Dict[str, int]] = {}

        # Default priors
        self._default_alpha = 1
        self._default_beta = 1

    def select_strategy(
        self, available_services: List[AIService], query_type: str
    ) -> AIService:
        """
        Selects the best service from the available ones.

        Args:
            available_services: List of candidate services.
            query_type: The type of query (context for selection).

        Returns:
            The selected AIService.
        """
        if not available_services:
            raise ValueError("No services available for selection")

        if len(available_services) == 1:
            return available_services[0]

        best_service = None
        max_sample = -1.0

        for service in available_services:
            service_key = (
                str(service.value) if hasattr(service, "value") else str(service)
            )
            key = f"{service_key}:{query_type}"

            alpha, beta = self._get_params(key)

            # Thompson Sampling: Draw from Beta(alpha, beta)
            sample = random.betavariate(alpha, beta)

            if sample > max_sample:
                max_sample = sample
                best_service = service

        logger.debug(
            f"Selected strategy {best_service} for {query_type}",
            extra={"sample_value": max_sample},
        )
        return best_service

    def update_feedback(self, service: AIService, query_type: str, success: bool):
        """
        Updates the bandit parameters based on execution result.

        Args:
            service: The service that was executed.
            query_type: The type of query.
            success: Whether the execution was successful.
        """
        service_key = str(service.value) if hasattr(service, "value") else str(service)
        key = f"{service_key}:{query_type}"

        if key not in self._stats:
            self._stats[key] = {
                "alpha": self._default_alpha,
                "beta": self._default_beta,
            }

        if success:
            self._stats[key]["alpha"] += 1
        else:
            self._stats[key]["beta"] += 1

        logger.debug(
            f"Updated stats for {key}",
            extra={
                "alpha": self._stats[key]["alpha"],
                "beta": self._stats[key]["beta"],
            },
        )

    def _get_params(self, key: str) -> tuple[int, int]:
        """Get alpha and beta parameters for a key."""
        if key not in self._stats:
            return self._default_alpha, self._default_beta
        return self._stats[key]["alpha"], self._stats[key]["beta"]


class StrategyFeedbackHandler:
    """
    Updates StrategySelector based on performance events.
    """

    def __init__(self):
        self.selector = get_strategy_selector()

    async def handle(self, event):
        """Handle STRATEGY_PERFORMANCE_RECORDED event."""
        if event.type != "ai.evolution.strategy_performance":
            return

        payload = event.payload
        service_name = payload.get("service")
        query_type = payload.get("query_type")
        success = payload.get("success", False)

        if service_name and query_type:
            # We need to map string service name back to AIService enum if possible,
            # or StrategySelector should handle strings.
            # The current StrategySelector expects AIService object in select_strategy
            # but uses string keys internally. update_feedback takes AIService.
            # Let's adjust StrategySelector to be more flexible or map here.
            # For now, we pass the string and let StrategySelector handle it if we modify it,
            # or we just pass the string if we change type hint.
            # Let's assume we pass the string and modify StrategySelector type hint if needed,
            # but actually update_feedback takes AIService.
            # Let's try to convert string to AIService if possible, or just pass string.
            self.selector.update_feedback(service_name, query_type, success)


# Global instance
_selector_instance = None


def get_strategy_selector() -> StrategySelector:
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = StrategySelector()
    return _selector_instance


def register_strategy_feedback_handler():
    """Register handler with EventBus"""
    try:
        from src.infrastructure.event_bus import get_event_bus, EventType
    except ImportError:
        return  # event bus not available

    bus = get_event_bus()
    handler = StrategyFeedbackHandler()

    # We need to wrap the handler to match EventHandler protocol if it's strict,
    # or make StrategyFeedbackHandler inherit from EventHandler.
    # Let's do the latter in the full file content or just duck type if allowed.
    # The EventBus expects EventHandler.

    # Dynamic import to avoid circular deps if any
    try:
        from src.infrastructure.event_bus import EventHandler as BaseEventHandler
    except ImportError:
        BaseEventHandler = object  # type: ignore

    class WrappedHandler(BaseEventHandler):
        def __init__(self, inner):
            self.inner = inner

        @property
        def event_types(self):
            return {EventType.STRATEGY_PERFORMANCE_RECORDED}

        async def handle(self, event):
            await self.inner.handle(event)

    bus.subscribe(EventType.STRATEGY_PERFORMANCE_RECORDED, WrappedHandler(handler))
    logger.info("StrategyFeedbackHandler registered")
