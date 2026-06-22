"""
LLM Integration Module

Provides adaptive LLM selection and integration with multiple providers.
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

try:
    from .adaptive_selector import AdaptiveLLMSelector, LLMModel, TaskType
except Exception:

    class TaskType(str, Enum):
        """Minimal task taxonomy for baseline offline mode."""

        SECURITY_ANALYSIS = "security_analysis"
        CODE_GENERATION = "code_generation"
        CODE_REVIEW = "code_review"
        DOCUMENTATION = "documentation"
        GENERAL = "general"

    @dataclass
    class LLMModel:
        """Offline model descriptor used when adaptive selector is unavailable."""

        name: str = "offline-llm-fallback"
        provider: str = "local"
        available: bool = False

    class AdaptiveLLMSelector:
        """Honest offline fallback for optional adaptive LLM integration."""

        available = False

        async def generate(
            self,
            task_type: TaskType,
            prompt: str,
            context: Dict[str, Any] | None = None,
        ) -> Dict[str, Any]:
            response = {
                "status": "llm_offline_fallback",
                "task_type": task_type.value
                if hasattr(task_type, "value")
                else str(task_type),
                "is_injection": False,
                "confidence": 0.0,
                "reason": "Adaptive LLM selector is not installed in the baseline profile.",
            }
            return {
                "response": json.dumps(response, ensure_ascii=False),
                "model": LLMModel().name,
                "provider": "local",
                "mode": "offline_fallback",
                "coverage": "no_llm_provider",
                "context_keys": sorted(str(key) for key in (context or {}).keys()),
            }


__all__ = ["AdaptiveLLMSelector", "LLMModel", "TaskType"]
