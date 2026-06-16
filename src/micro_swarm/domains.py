"""1cAI Domain Configurations for Micro-Model Swarm.

Defines feature extraction specs for 1C Enterprise AI use cases:
- QueryIntent: classify user queries into routing categories
- RoleDetection: detect user role from query text
- AnomalyDetection: detect anomalies in logs/metrics

Based on SENTINEL DomainConfig pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class NormMethod(str, Enum):
    """Feature normalization methods."""

    NONE = "none"
    MIN_MAX = "min_max"
    Z_SCORE = "z_score"


@dataclass(frozen=True)
class FeatureSpec:
    """Specification for a single feature."""

    name: str
    norm_method: NormMethod = NormMethod.MIN_MAX
    min_val: float = 0.0
    max_val: float = 1.0
    mean: float = 0.0
    std: float = 1.0
    default: float = 0.0

    def normalize(self, value: float) -> float:
        """Normalize a single value according to this spec."""
        if self.norm_method == NormMethod.NONE:
            return value
        if self.norm_method == NormMethod.MIN_MAX:
            denom = self.max_val - self.min_val
            if denom == 0:
                return 0.0
            return max(0.0, min(1.0, (value - self.min_val) / denom))
        if self.norm_method == NormMethod.Z_SCORE:
            if self.std == 0:
                return 0.0
            return (value - self.mean) / self.std
        return value


@dataclass(frozen=True)
class DomainConfig:
    """Declarative domain configuration for feature extraction."""

    name: str
    features: tuple[FeatureSpec, ...]
    description: str = ""

    @property
    def n_features(self) -> int:
        return len(self.features)

    @property
    def feature_names(self) -> list[str]:
        return [f.name for f in self.features]

    def extract(self, data: dict[str, Any]) -> list[float]:
        """Extract and normalize features from data dict."""
        result: list[float] = []
        for spec in self.features:
            raw = data.get(spec.name, spec.default)
            try:
                val = float(raw)
            except (ValueError, TypeError):
                val = spec.default
            result.append(spec.normalize(val))
        return result


# ──────────────────────────────────────────
# 1cAI Domain: Query Intent Classification
# ──────────────────────────────────────────

# BSL/1C keyword patterns for feature extraction
_BSL_KEYWORDS = [
    "процедура", "функция", "перем", "конецпроцедуры", "конецфункции",
    "если", "тогда", "иначе", "конецесли", "для", "каждого", "цикл",
    "попытка", "исключение", "конецпопытки", "запрос", "выборка",
]

_GRAPH_KEYWORDS = [
    "зависимост", "граф", "связ", "модуль", "архитектур", "структур",
    "дерев", "иерарх", "подчинен",
]

_CODE_GEN_KEYWORDS = [
    "сгенерируй", "напиши", "создай", "код", "реализуй", "функци",
    "процедур", "обработк", "форм",
]

_OPTIMIZE_KEYWORDS = [
    "оптимиз", "ускор", "медлен", "производительност", "замедлен",
    "тормоз", "долго", "быстр",
]

_SEARCH_KEYWORDS = [
    "найди", "поиск", "где", "как", "покажи", "объясни", "документац",
]


def _count_keyword_hits(text: str, keywords: list[str]) -> float:
    """Count how many keywords appear in text (case-insensitive)."""
    text_lower = text.lower()
    return sum(1.0 for kw in keywords if kw in text_lower)


def extract_query_features(query: str) -> dict[str, float]:
    """Extract features from a user query for intent classification."""
    words = query.split()
    return {
        "query_length": float(len(query)),
        "word_count": float(len(words)),
        "has_question_mark": float("?" in query),
        "has_code_block": float("```" in query or "Процедура" in query),
        "bsl_keyword_hits": _count_keyword_hits(query, _BSL_KEYWORDS),
        "graph_keyword_hits": _count_keyword_hits(query, _GRAPH_KEYWORDS),
        "code_gen_hits": _count_keyword_hits(query, _CODE_GEN_KEYWORDS),
        "optimize_hits": _count_keyword_hits(query, _OPTIMIZE_KEYWORDS),
        "search_hits": _count_keyword_hits(query, _SEARCH_KEYWORDS),
        "avg_word_length": (
            sum(len(w) for w in words) / max(len(words), 1)
        ),
        "uppercase_ratio": (
            sum(1 for c in query if c.isupper()) / max(len(query), 1)
        ),
        "digit_ratio": (
            sum(1 for c in query if c.isdigit()) / max(len(query), 1)
        ),
    }


QUERY_INTENT_DOMAIN = DomainConfig(
    name="query_intent",
    description="Классификация пользовательских запросов по типу",
    features=(
        FeatureSpec("query_length", NormMethod.MIN_MAX, 0.0, 500.0),
        FeatureSpec("word_count", NormMethod.MIN_MAX, 0.0, 50.0),
        FeatureSpec("has_question_mark", NormMethod.NONE),
        FeatureSpec("has_code_block", NormMethod.NONE),
        FeatureSpec("bsl_keyword_hits", NormMethod.MIN_MAX, 0.0, 10.0),
        FeatureSpec("graph_keyword_hits", NormMethod.MIN_MAX, 0.0, 5.0),
        FeatureSpec("code_gen_hits", NormMethod.MIN_MAX, 0.0, 5.0),
        FeatureSpec("optimize_hits", NormMethod.MIN_MAX, 0.0, 5.0),
        FeatureSpec("search_hits", NormMethod.MIN_MAX, 0.0, 5.0),
        FeatureSpec("avg_word_length", NormMethod.MIN_MAX, 0.0, 20.0),
        FeatureSpec("uppercase_ratio", NormMethod.NONE),
        FeatureSpec("digit_ratio", NormMethod.NONE),
    ),
)


# ──────────────────────────────────────────
# 1cAI Domain: Role Detection
# ──────────────────────────────────────────

_ROLE_KEYWORDS = {
    "developer": [
        "сгенерируй код", "напиши функцию", "рефакторинг", "баг", "отладка",
        "компилятор", "модуль", "обработка", "форма", "макет",
    ],
    "business_analyst": [
        "бизнес-процесс", "требования", "техзадание", "анализ", "отчёт",
        "пользовательская история", "user story", "сценарий", "бп",
    ],
    "qa_engineer": [
        "тест", "проверка", "ошибка", "регресс", "тестирование",
        "покрытие", "автотест", "юнит-тест", "smoke",
    ],
    "architect": [
        "архитектура", "подсистема", "интеграция", "API", "схема",
        "паттерн", "масштабирование", "микросервис",
    ],
    "devops": [
        "деплой", "CI/CD", "контейнер", "docker", "мониторинг",
        "сервер", "нагрузка", "балансировка", "kubernetes",
    ],
    "technical_writer": [
        "документация", "инструкция", "описание", "руководство",
        "справка", "комментарий", "readme",
    ],
}


def extract_role_features(query: str) -> dict[str, float]:
    """Extract features for role detection."""
    words = query.split()
    features: dict[str, float] = {
        "query_length": float(len(query)),
        "word_count": float(len(words)),
    }

    # Keyword hits per role
    for role, keywords in _ROLE_KEYWORDS.items():
        features[f"{role}_hits"] = _count_keyword_hits(query, keywords)

    return features


ROLE_DETECTION_DOMAIN = DomainConfig(
    name="role_detection",
    description="Определение роли пользователя по запросу",
    features=(
        FeatureSpec("query_length", NormMethod.MIN_MAX, 0.0, 500.0),
        FeatureSpec("word_count", NormMethod.MIN_MAX, 0.0, 50.0),
        FeatureSpec("developer_hits", NormMethod.MIN_MAX, 0.0, 5.0),
        FeatureSpec("business_analyst_hits", NormMethod.MIN_MAX, 0.0, 5.0),
        FeatureSpec("qa_engineer_hits", NormMethod.MIN_MAX, 0.0, 5.0),
        FeatureSpec("architect_hits", NormMethod.MIN_MAX, 0.0, 5.0),
        FeatureSpec("devops_hits", NormMethod.MIN_MAX, 0.0, 5.0),
        FeatureSpec("technical_writer_hits", NormMethod.MIN_MAX, 0.0, 5.0),
    ),
)


# ──────────────────────────────────────────
# 1cAI Domain: Anomaly Detection
# ──────────────────────────────────────────


def extract_log_features(log_entry: dict[str, Any]) -> dict[str, float]:
    """Extract features from a log entry for anomaly detection."""
    message = str(log_entry.get("message", ""))
    return {
        "message_length": float(len(message)),
        "error_level": float(
            str(log_entry.get("level", "")).upper() in ("ERROR", "CRITICAL")
        ),
        "warning_level": float(
            str(log_entry.get("level", "")).upper() == "WARNING"
        ),
        "has_stack_trace": float("traceback" in message.lower() or "error" in message.lower()),
        "word_count": float(len(message.split())),
        "digit_ratio": (
            sum(1 for c in message if c.isdigit()) / max(len(message), 1)
        ),
        "special_char_ratio": (
            sum(1 for c in message if not c.isalnum() and not c.isspace())
            / max(len(message), 1)
        ),
        "response_time_ms": float(log_entry.get("response_time_ms", 0)),
    }


def extract_metric_features(metric: dict[str, Any]) -> dict[str, float]:
    """Extract features from system metrics for anomaly detection."""
    return {
        "cpu_usage": float(metric.get("cpu_usage", 0)),
        "memory_usage": float(metric.get("memory_usage", 0)),
        "disk_io": float(metric.get("disk_io", 0)),
        "network_io": float(metric.get("network_io", 0)),
        "active_connections": float(metric.get("active_connections", 0)),
        "request_rate": float(metric.get("request_rate", 0)),
        "error_rate": float(metric.get("error_rate", 0)),
        "response_time_p99": float(metric.get("response_time_p99", 0)),
    }


ANOMALY_DETECTION_DOMAIN = DomainConfig(
    name="anomaly_detection",
    description="Обнаружение аномалий в логах и метриках",
    features=(
        FeatureSpec("cpu_usage", NormMethod.NONE, 0.0, 1.0),
        FeatureSpec("memory_usage", NormMethod.NONE, 0.0, 1.0),
        FeatureSpec("disk_io", NormMethod.MIN_MAX, 0.0, 1000.0),
        FeatureSpec("network_io", NormMethod.MIN_MAX, 0.0, 10000.0),
        FeatureSpec("active_connections", NormMethod.MIN_MAX, 0.0, 10000.0),
        FeatureSpec("request_rate", NormMethod.MIN_MAX, 0.0, 10000.0),
        FeatureSpec("error_rate", NormMethod.NONE, 0.0, 1.0),
        FeatureSpec("response_time_p99", NormMethod.MIN_MAX, 0.0, 30000.0),
    ),
)
