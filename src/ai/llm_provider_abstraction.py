
"""
LLM Provider Abstraction Layer
------------------------------

Унифицированный уровень абстракции для работы с разными LLM провайдерами.
Обеспечивает единый интерфейс для выбора провайдера на основе типа запроса,
рисков, стоимости и latency.

Интегрируется с ToolRegistry для описания доступных моделей.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from src.config import USE_ADAPTIVE_SELECTION

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Типы запросов для выбора провайдера."""

    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    REASONING = "reasoning"
    RUSSIAN_TEXT = "russian_text"
    ENGLISH_TEXT = "english_text"
    ANALYSIS = "analysis"
    GENERAL = "general"


class RiskLevel(Enum):
    """Уровни риска провайдера."""

    LOW = "low"  # Локальные модели, полностью контролируемые
    MEDIUM = "medium"  # Российские провайдеры с compliance
    HIGH = "high"  # Зарубежные провайдеры, возможны регуляторные ограничения


@dataclass
class ModelProfile:
    """
    Профиль модели с метаданными для выбора провайдера.

    Содержит информацию о рисках, стоимости, latency и поддерживаемых типах запросов.
    """

    provider_id: str  # Идентификатор провайдера (kimi, qwen, gigachat, etc.)
    model_name: str  # Название модели
    capabilities: Set[QueryType] = field(
        default_factory=set
    )  # Поддерживаемые типы запросов
    risk_level: RiskLevel = RiskLevel.MEDIUM  # Уровень риска
    cost_per_1k_tokens: float = 0.0  # Стоимость за 1K токенов (USD)
    avg_latency_ms: int = 1000  # Средняя latency в миллисекундах
    max_tokens: int = 4096  # Максимальное количество токенов
    supports_streaming: bool = False  # Поддержка streaming
    # Соответствие требованиям (152-ФЗ, GDPR, etc.)
    compliance: List[str] = field(default_factory=list)
    description: str = ""  # Описание модели

    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь для сериализации."""
        return {
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "capabilities": [cap.value for cap in self.capabilities],
            "risk_level": self.risk_level.value,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "avg_latency_ms": self.avg_latency_ms,
            "max_tokens": self.max_tokens,
            "supports_streaming": self.supports_streaming,
            "compliance": self.compliance,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelProfile":
        """Создать из словаря."""
        return cls(
            provider_id=data["provider_id"],
            model_name=data["model_name"],
            capabilities={QueryType(cap) for cap in data.get("capabilities", [])},
            risk_level=RiskLevel(data.get("risk_level", "medium")),
            cost_per_1k_tokens=data.get("cost_per_1k_tokens", 0.0),
            avg_latency_ms=data.get("avg_latency_ms", 1000),
            max_tokens=data.get("max_tokens", 4096),
            supports_streaming=data.get("supports_streaming", False),
            compliance=data.get("compliance", []),
            description=data.get("description", ""),
        )


class LLMProviderAbstraction:
    """
    Унифицированный уровень абстракции для LLM провайдеров.

    Управляет профилями моделей и выбором провайдера на основе типа запроса,
    рисков, стоимости и latency.

    With optional Nested Learning for adaptive selection.
    """

    def __init__(self) -> None:
        """Инициализация абстракции провайдеров."""
        self.profiles: Dict[str, ModelProfile] = {}
        self._load_default_profiles()

        # Nested Learning integration — removed Phase 7 (phantom module)
        self._nested = None

    def _load_default_profiles(self) -> None:
        """Загрузить профили по умолчанию."""
        # Kimi-K2-Thinking
        self.register_profile(
            ModelProfile(
                provider_id="kimi",
                model_name="moonshot-v1-8k",
                capabilities={
                    QueryType.REASONING,
                    QueryType.CODE_GENERATION,
                    QueryType.ANALYSIS,
                    QueryType.GENERAL,
                },
                risk_level=RiskLevel.HIGH,
                cost_per_1k_tokens=0.01,
                avg_latency_ms=2000,
                max_tokens=8192,
                supports_streaming=True,
                compliance=[],
                description="Kimi-K2-Thinking: мощная модель для reasoning и анализа",
            )
        )

        # Qwen3-Coder
        self.register_profile(
            ModelProfile(
                provider_id="qwen",
                model_name="qwen2.5-coder-7b-instruct",
                capabilities={
                    QueryType.CODE_GENERATION,
                    QueryType.CODE_REVIEW,
                    QueryType.ANALYSIS,
                },
                risk_level=RiskLevel.LOW,
                cost_per_1k_tokens=0.0,  # Локальная модель
                avg_latency_ms=1500,
                max_tokens=4096,
                supports_streaming=False,
                compliance=["self-hosted"],
                description="Qwen3-Coder: локальная модель для генерации кода",
            )
        )

        # GigaChat
        self.register_profile(
            ModelProfile(
                provider_id="gigachat",
                model_name="gigachat",
                capabilities={
                    QueryType.RUSSIAN_TEXT,
                    QueryType.GENERAL,
                    QueryType.ANALYSIS,
                },
                risk_level=RiskLevel.MEDIUM,
                cost_per_1k_tokens=0.005,
                avg_latency_ms=1800,
                max_tokens=4096,
                supports_streaming=True,
                compliance=["152-ФЗ", "GDPR"],
                description="GigaChat: российская модель для работы с русским текстом",
            )
        )

        # YandexGPT
        self.register_profile(
            ModelProfile(
                provider_id="yandexgpt",
                model_name="yandexgpt-lite",
                capabilities={
                    QueryType.RUSSIAN_TEXT,
                    QueryType.GENERAL,
                    QueryType.ANALYSIS,
                },
                risk_level=RiskLevel.MEDIUM,
                cost_per_1k_tokens=0.004,
                avg_latency_ms=1500,
                max_tokens=4096,
                supports_streaming=True,
                compliance=["152-ФЗ", "GDPR"],
                description="YandexGPT: российская модель от Яндекса",
            )
        )

        # 1C:Напарник
        self.register_profile(
            ModelProfile(
                provider_id="naparnik",
                model_name="naparnik-pro",
                capabilities={
                    QueryType.RUSSIAN_TEXT,
                    QueryType.GENERAL,
                    QueryType.ANALYSIS,
                    QueryType.CODE_GENERATION,
                },
                risk_level=RiskLevel.LOW,
                cost_per_1k_tokens=0.0,  # Бесплатно для пользователей 1С
                avg_latency_ms=2000,
                max_tokens=4096,
                supports_streaming=False,
                compliance=["152-ФЗ", "GDPR"],
                description="1C:Напарник: специализированный AI-помощник для разработчиков 1С:Enterprise",
            )
        )

        # Ollama модели (локальные) - Updated 2025-12
        # Llama 4 Scout - универсальная модель с 10M контекстом
        self.register_profile(
            ModelProfile(
                provider_id="ollama",
                model_name="llama4:scout",
                capabilities={
                    QueryType.GENERAL,
                    QueryType.ENGLISH_TEXT,
                    QueryType.ANALYSIS,
                    QueryType.REASONING,
                    QueryType.CODE_GENERATION,
                },
                risk_level=RiskLevel.LOW,  # Локальная модель, полный контроль
                cost_per_1k_tokens=0.0,  # Бесплатно (локально)
                avg_latency_ms=2500,
                max_tokens=10000000,  # 10M context window
                supports_streaming=True,
                compliance=["152-ФЗ", "GDPR"],  # Локальное исполнение
                description="Llama 4 Scout: универсальная MoE модель (17B active) с 10M контекстом",
            )
        )

        # Qwen3 - универсальная модель с Thinking Mode
        self.register_profile(
            ModelProfile(
                provider_id="ollama",
                model_name="qwen3:8b",
                capabilities={
                    QueryType.GENERAL,
                    QueryType.RUSSIAN_TEXT,
                    QueryType.ENGLISH_TEXT,
                    QueryType.ANALYSIS,
                    QueryType.REASONING,
                },
                risk_level=RiskLevel.LOW,
                cost_per_1k_tokens=0.0,
                avg_latency_ms=2000,
                max_tokens=1000000,  # 1M context
                supports_streaming=True,
                compliance=["152-ФЗ", "GDPR"],
                description="Qwen3: универсальная модель с Thinking/Non-thinking режимами, 119 языков",
            )
        )

        # Qwen3-Coder - специализированная модель для кода
        self.register_profile(
            ModelProfile(
                provider_id="ollama",
                model_name="qwen3-coder",
                capabilities={
                    QueryType.CODE_GENERATION,
                    QueryType.CODE_REVIEW,
                    QueryType.REASONING,
                },
                risk_level=RiskLevel.LOW,
                cost_per_1k_tokens=0.0,
                avg_latency_ms=2500,
                max_tokens=131072,
                supports_streaming=True,
                compliance=["152-ФЗ", "GDPR"],
                description="Qwen3-Coder: продвинутая модель для программирования, сравнима с GPT-4o",
            )
        )

        # Qwen3-VL - vision-language модель
        self.register_profile(
            ModelProfile(
                provider_id="ollama",
                model_name="qwen3-vl",
                capabilities={
                    QueryType.ANALYSIS,
                    QueryType.CODE_GENERATION,
                    QueryType.GENERAL,
                },
                risk_level=RiskLevel.LOW,
                cost_per_1k_tokens=0.0,
                avg_latency_ms=3000,
                max_tokens=32768,
                supports_streaming=True,
                compliance=["152-ФЗ", "GDPR"],
                description="Qwen3-VL: vision-language модель для анализа UI и диаграмм",
            )
        )

    def register_profile(self, profile: ModelProfile) -> None:
        """Зарегистрировать профиль модели."""
        key = f"{profile.provider_id}:{profile.model_name}"
        self.profiles[key] = profile
        logger.debug(
            "Registered model profile",
            extra={
                "provider_id": profile.provider_id,
                "model_name": profile.model_name,
            },
        )

    def get_profile(self, provider_id: str, model_name: str) -> Optional[ModelProfile]:
        """Получить профиль модели."""
        key = f"{provider_id}:{model_name}"
        return self.profiles.get(key)

    def select_provider(
        self,
        query_type: QueryType,
        *,
        max_cost: Optional[float] = None,
        max_latency_ms: Optional[int] = None,
        required_compliance: Optional[List[str]] = None,
        preferred_risk_level: Optional[RiskLevel] = None,
    ) -> Optional[ModelProfile]:
        """
        Выбрать провайдера на основе критериев.

        Args:
            query_type: Тип запроса
            max_cost: Максимальная стоимость за 1K токенов
            max_latency_ms: Максимальная latency в миллисекундах
            required_compliance: Требуемое соответствие (152-ФЗ, GDPR, etc.)
            preferred_risk_level: Предпочтительный уровень риска

        Returns:
            Подходящий профиль модели или None
        """
        candidates: List[ModelProfile] = []

        # Фильтровать по типу запроса
        for profile in self.profiles.values():
            if query_type not in profile.capabilities:
                continue

            # Фильтровать по стоимости
            if max_cost is not None and profile.cost_per_1k_tokens > max_cost:
                continue

            # Фильтровать по latency
            if max_latency_ms is not None and profile.avg_latency_ms > max_latency_ms:
                continue

            # Фильтровать по compliance
            if required_compliance:
                if not all(comp in profile.compliance for comp in required_compliance):
                    continue

            # Фильтровать по уровню риска
            # Риск: LOW < MEDIUM < HIGH (по алфавиту, но нужно сравнить правильно)
            if preferred_risk_level is not None:
                risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
                profile_risk_value = risk_order.get(profile.risk_level, 1)
                preferred_risk_value = risk_order.get(preferred_risk_level, 1)
                # Принимаем только провайдеры с риском <= предпочтительного
                if profile_risk_value > preferred_risk_value:
                    continue

            candidates.append(profile)

        if not candidates:
            return None

        # Сортировать по приоритету: сначала по риску (низкий лучше), затем по стоимости, затем по latency
        candidates.sort(
            key=lambda p: (
                p.risk_level.value,
                p.cost_per_1k_tokens,
                p.avg_latency_ms,
            )
        )

        selected = candidates[0]

        # Метрики: отслеживание выбора провайдера
        try:
            from src.monitoring.prometheus_metrics import track_llm_provider_selection

            # Время выбора очень быстрое, но измеряем для консистентности
            duration = 0.0001  # Приблизительное время выбора
            reason = "default"
            if max_cost is not None:
                reason = "cost_constraint"
            elif max_latency_ms is not None:
                reason = "latency_constraint"
            elif required_compliance:
                reason = "compliance_requirement"
            elif preferred_risk_level is not None:
                reason = "risk_preference"

            track_llm_provider_selection(
                duration=duration,
                provider_id=selected.provider_id,
                query_type=query_type.value,
                reason=reason,
                cost_per_1k_tokens=selected.cost_per_1k_tokens,
            )
        except ImportError:
            pass  # Метрики опциональны

        return selected

    def get_all_profiles(self) -> List[ModelProfile]:
        """Получить все зарегистрированные профили."""
        return list(self.profiles.values())

    def get_profiles_by_capability(self, query_type: QueryType) -> List[ModelProfile]:
        """Получить профили, поддерживающие тип запроса."""
        return [
            profile
            for profile in self.profiles.values()
            if query_type in profile.capabilities
        ]

    def to_tool_registry_format(self) -> List[Dict[str, Any]]:
        """
        Конвертировать профили в формат ToolRegistry.

        Используется для интеграции с ToolRegistry.
        """
        tools: List[Dict[str, Any]] = []

        for profile in self.profiles.values():
            tool = {
                "id": f"llm:{profile.provider_id}:{profile.model_name}",
                "name": f"LLM: {profile.provider_id}/{profile.model_name}",
                "description": profile.description
                or f"LLM model {profile.model_name} from {profile.provider_id}",
                "version": "1.0.0",
                "schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Prompt для модели",
                        },
                        "max_tokens": {
                            "type": "integer",
                            "default": profile.max_tokens,
                            "description": "Максимальное количество токенов",
                        },
                    },
                    "required": ["prompt"],
                },
                "cost": {
                    "per_1k_tokens": profile.cost_per_1k_tokens,
                    "currency": "USD",
                },
                "risks": {
                    "level": profile.risk_level.value,
                    "compliance": profile.compliance,
                },
                "metadata": {
                    "avg_latency_ms": profile.avg_latency_ms,
                    "supports_streaming": profile.supports_streaming,
                    "capabilities": [cap.value for cap in profile.capabilities],
                },
            }
            tools.append(tool)

        return tools
