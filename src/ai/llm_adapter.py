"""
LLM Adapter — bridges rlm-toolkit providers to BSL pipeline.

Wraps any rlm_toolkit LLMProvider into the BSLPipeline's LLMProvider protocol.

Usage::

    from src.ai.llm_adapter import from_ollama
    from src.ai.bsl_pipeline import BSLPipeline

    llm = from_ollama(model="qwen3:4b")
    pipeline = BSLPipeline("/path/to/1c/project", llm_provider=llm)
    results = pipeline.run()
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from rlm_toolkit.providers import AnthropicProvider, OllamaProvider, OpenAIProvider
    from rlm_toolkit.providers.base import ResilientProvider
except ImportError:
    raise ImportError(
        "rlm-toolkit not found. Install it or add to PYTHONPATH: "
        "set PYTHONPATH=%PYTHONPATH%;C:\\AISecurity\\sentinel-community\\rlm-toolkit"
    )

# ── System prompt (Russian, 1C-specific) ──────────────────────────

BSL_REVIEW_SYSTEM_PROMPT = (
    "Вы — эксперт-разработчик 1С:Предприятие с глубоким знанием языка BSL.\n"
    "Проведите ревью кода на языке BSL. Обратите внимание на:\n"
    "• Проблемы качества кода и соответствие стандартам 1С\n"
    "• N+1 запросы к базе данных (запросы в цикле)\n"
    "• Пустые блоки Попытка-Исключение (проглатывание ошибок)\n"
    "• Магические числа и строковые константы без пояснений\n"
    "• Глубокая вложенность (более 3 уровней)\n"
    "• Неэффективные конструкции и потенциальные утечки ресурсов\n\n"
    "Micro-Swarm уже оценил этот код автоматически. "
    "Используйте приведённые оценки как контекст для анализа.\n\n"
    "Формат ответа:\n"
    "1. Найденные проблемы — с указанием серьёзности (критично / важно / замечание)\n"
    "2. Рекомендации по исправлению — конкретные, применимые\n"
    "Будьте кратки и по делу. Отвечайте на русском языке."
)


def _build_user_prompt(code: str, scores: dict[str, float]) -> str:
    """Build user prompt with code and swarm scores."""
    scores_text = "\n".join(
        f"  • {name}: {value:.2f}" for name, value in scores.items()
    )
    return (
        f"Оценки Micro-Swarm:\n{scores_text}\n\nКод BSL для ревью:\n```bsl\n{code}\n```"
    )


# ── Adapter class ─────────────────────────────────────────────────


class BSLReviewProvider:
    """Adapter: wraps an rlm-toolkit provider into BSLPipeline's LLMProvider protocol.

    Attributes:
        model_name: Name of the underlying model (used by bsl_pipeline for logging).
        total_cost: Accumulated cost across all review calls.
    """

    def __init__(self, provider: ResilientProvider) -> None:
        self._provider = provider
        self.total_cost: float = 0.0

    @property
    def model_name(self) -> str:
        """Model identifier string (read by BSLPipeline via getattr)."""
        return getattr(self._provider, "model", "unknown")

    def review(self, code: str, scores: dict[str, float]) -> str:
        """Review BSL code using the wrapped LLM provider.

        Args:
            code: BSL source code to review.
            scores: Micro-Swarm scores (agent_name → float).

        Returns:
            Review text in Russian with issues and recommendations.
        """
        user_prompt = _build_user_prompt(code, scores)

        logger.info("Requesting LLM review via %s", self.model_name)
        response = self._provider.generate(
            prompt=user_prompt,
            system_prompt=BSL_REVIEW_SYSTEM_PROMPT,
            temperature=0.0,
        )

        # Track cost if the provider supports it
        try:
            cost = self._provider.get_cost(response)
            self.total_cost += cost
            logger.debug("Review cost: %.6f (total: %.6f)", cost, self.total_cost)
        except (AttributeError, TypeError):
            pass

        return response.content


# ── Factory functions ─────────────────────────────────────────────


def from_ollama(
    model: str = "qwen3:4b",
    base_url: str = "http://localhost:11434",
) -> BSLReviewProvider:
    """Create a BSLReviewProvider backed by a local Ollama instance."""
    provider = OllamaProvider(model=model, base_url=base_url)
    return BSLReviewProvider(provider)


def from_openai(
    model: str = "gpt-4o-mini",
    api_key: str | None = None,
) -> BSLReviewProvider:
    """Create a BSLReviewProvider backed by OpenAI."""
    kwargs: dict[str, Any] = {"model": model}
    if api_key is not None:
        kwargs["api_key"] = api_key
    provider = OpenAIProvider(**kwargs)
    return BSLReviewProvider(provider)


def from_anthropic(
    model: str = "claude-3.5-sonnet",
    api_key: str | None = None,
) -> BSLReviewProvider:
    """Create a BSLReviewProvider backed by Anthropic."""
    kwargs: dict[str, Any] = {"model": model}
    if api_key is not None:
        kwargs["api_key"] = api_key
    provider = AnthropicProvider(**kwargs)
    return BSLReviewProvider(provider)
