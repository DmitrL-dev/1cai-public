"""
Intelligent Cache Manager for AI Orchestrator
---------------------------------------------

Интеллектуальное кэширование с TTL, инвалидацией на основе контекста
и метриками производительности.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Запись в кэше с метаданными."""

    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    tags: Set[str] = field(default_factory=set)  # Теги для инвалидации
    query_type: Optional[str] = None  # Тип запроса для группировки

    def is_expired(self) -> bool:
        """Проверить, истёк ли срок действия."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def touch(self) -> None:
        """Обновить время последнего доступа."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


class IntelligentCache:
    """
    Интеллектуальный кэш-менеджер для AI Orchestrator.

    Особенности:
    - TTL на основе типа запроса
    - Инвалидация по тегам
    - LRU eviction при переполнении
    - Метрики производительности
    - Контекстно-зависимое кэширование
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_seconds: int = 300,  # 5 минут по умолчанию
    ) -> None:
        """
        Args:
            max_size: Максимальное количество записей в кэше
            default_ttl_seconds: TTL по умолчанию в секундах
        """
        self.max_size = max_size
        self.default_ttl_seconds = default_ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._metrics: Dict[str, Any] = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "invalidations": 0,
        }

        # TTL для разных типов запросов (в секундах)
        self.ttl_by_query_type: Dict[str, int] = {
            "code_generation": 600,  # 10 минут
            "reasoning": 300,  # 5 минут
            "russian_text": 1800,  # 30 минут (более стабильные ответы)
            "general": 300,  # 5 минут
            "graph_query": 60,  # 1 минута (граф может меняться)
        }

    def _generate_key(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Сгенерировать ключ кэша на основе запроса и контекста.

        Args:
            query: Запрос пользователя
            context: Контекст запроса

        Returns:
            Хэш-ключ для кэша
        """
        # Нормализовать запрос (убрать лишние пробелы, привести к нижнему регистру)
        normalized_query = " ".join(query.lower().split())

        # Включить релевантные части контекста
        context_str = ""
        if context:
            # Включить только стабильные части контекста
            relevant_keys = ["type", "query_type", "user_id"]
            context_parts = [
                f"{k}:{v}" for k, v in context.items() if k in relevant_keys
            ]
            context_str = "|".join(sorted(context_parts))

        # Создать хэш
        key_data = f"{normalized_query}|{context_str}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """
        Получить значение из кэша.

        Args:
            query: Запрос пользователя
            context: Контекст запроса

        Returns:
            Кэшированное значение или None
        """
        key = self._generate_key(query, context)

        start_time = time.time()

        # Проверить наличие в кэше
        if key not in self._cache:
            self._metrics["misses"] += 1
            duration = time.time() - start_time
            try:
                from src.monitoring.prometheus_metrics import (
                    track_intelligent_cache_miss,
                    track_intelligent_cache_operation,
                )

                query_type = context.get("query_type") if context else None
                track_intelligent_cache_miss(query_type=query_type)
                track_intelligent_cache_operation("get", duration, "miss")
            except ImportError:
                pass
            return None

        entry = self._cache[key]

        # Проверить срок действия
        if entry.is_expired():
            del self._cache[key]
            self._metrics["misses"] += 1
            duration = time.time() - start_time
            try:
                from src.monitoring.prometheus_metrics import (
                    track_intelligent_cache_eviction,
                    track_intelligent_cache_miss,
                    track_intelligent_cache_operation,
                )

                query_type = entry.query_type
                track_intelligent_cache_miss(query_type=query_type)
                track_intelligent_cache_operation("get", duration, "miss")
                track_intelligent_cache_eviction(eviction_reason="ttl_expired")
            except ImportError:
                pass
            return None

        # Обновить время доступа и переместить в конец (LRU)
        entry.touch()
        self._cache.move_to_end(key)

        self._metrics["hits"] += 1
        duration = time.time() - start_time
        try:
            from src.monitoring.prometheus_metrics import (
                track_intelligent_cache_hit,
                track_intelligent_cache_operation,
            )

            query_type = entry.query_type
            track_intelligent_cache_hit(query_type=query_type)
            track_intelligent_cache_operation("get", duration, "success")
        except ImportError:
            pass

        return entry.value

    def set(
        self,
        query: str,
        value: Any,
        context: Optional[Dict[str, Any]] = None,
        *,
        ttl_seconds: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        query_type: Optional[str] = None,
    ) -> None:
        """
        Сохранить значение в кэш.

        Args:
            query: Запрос пользователя
            value: Значение для кэширования
            context: Контекст запроса
            ttl_seconds: TTL в секундах (опционально)
            tags: Теги для инвалидации (опционально)
            query_type: Тип запроса для определения TTL (опционально)
        """
        key = self._generate_key(query, context)

        # Определить TTL
        if ttl_seconds is None:
            if query_type and query_type in self.ttl_by_query_type:
                ttl_seconds = self.ttl_by_query_type[query_type]
            else:
                ttl_seconds = self.default_ttl_seconds

        # Создать запись
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        entry = CacheEntry(
            value=value,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            tags=tags or set(),
            query_type=query_type,
        )

        start_time = time.time()

        # Проверить размер кэша
        if len(self._cache) >= self.max_size and key not in self._cache:
            # Удалить самую старую запись (LRU)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self._metrics["evictions"] += 1
            try:
                from src.monitoring.prometheus_metrics import (
                    track_intelligent_cache_eviction,
                )

                track_intelligent_cache_eviction(eviction_reason="lru")
            except ImportError:
                pass

        # Сохранить запись
        self._cache[key] = entry
        self._cache.move_to_end(key)

        duration = time.time() - start_time
        try:
            from src.monitoring.prometheus_metrics import (
                track_intelligent_cache_operation,
                update_intelligent_cache_size,
            )

            track_intelligent_cache_operation("set", duration, "success")
            update_intelligent_cache_size(
                current_size=len(self._cache), max_size=self.max_size
            )
        except ImportError:
            pass

    def invalidate_by_tags(self, tags: Set[str]) -> int:
        """
        Инвалидировать записи по тегам.

        Args:
            tags: Теги для инвалидации

        Returns:
            Количество удалённых записей
        """
        start_time = time.time()
        keys_to_remove = [
            key
            for key, entry in self._cache.items()
            if entry.tags & tags  # Пересечение множеств
        ]

        for key in keys_to_remove:
            del self._cache[key]

        count = len(keys_to_remove)
        self._metrics["invalidations"] += count

        duration = time.time() - start_time
        try:
            from src.monitoring.prometheus_metrics import (
                track_intelligent_cache_invalidation,
                track_intelligent_cache_operation,
                update_intelligent_cache_size,
            )

            track_intelligent_cache_invalidation(invalidation_type="tags")
            track_intelligent_cache_operation("invalidate_by_tags", duration, "success")
            update_intelligent_cache_size(
                current_size=len(self._cache), max_size=self.max_size
            )
        except ImportError:
            pass

        return count

    def invalidate_by_query_type(self, query_type: str) -> int:
        """
        Инвалидировать записи по типу запроса.

        Args:
            query_type: Тип запроса

        Returns:
            Количество удалённых записей
        """
        start_time = time.time()
        keys_to_remove = [
            key for key, entry in self._cache.items() if entry.query_type == query_type
        ]

        for key in keys_to_remove:
            del self._cache[key]

        count = len(keys_to_remove)
        self._metrics["invalidations"] += count

        duration = time.time() - start_time
        try:
            from src.monitoring.prometheus_metrics import (
                track_intelligent_cache_invalidation,
                track_intelligent_cache_operation,
                update_intelligent_cache_size,
            )

            track_intelligent_cache_invalidation(invalidation_type="query_type")
            track_intelligent_cache_operation(
                "invalidate_by_query_type", duration, "success"
            )
            update_intelligent_cache_size(
                current_size=len(self._cache), max_size=self.max_size
            )
        except ImportError:
            pass

        return count

    def clear(self) -> None:
        """Очистить весь кэш."""
        start_time = time.time()
        size_before = len(self._cache)
        self._cache.clear()
        self._metrics["invalidations"] += size_before

        duration = time.time() - start_time
        try:
            from src.monitoring.prometheus_metrics import (
                track_intelligent_cache_invalidation,
                track_intelligent_cache_operation,
                update_intelligent_cache_size,
            )

            track_intelligent_cache_invalidation(invalidation_type="manual")
            track_intelligent_cache_operation("clear", duration, "success")
            update_intelligent_cache_size(current_size=0, max_size=self.max_size)
        except ImportError:
            pass

    def cleanup_expired(self) -> int:
        """
        Удалить истёкшие записи.

        Returns:
            Количество удалённых записей
        """
        keys_to_remove = [
            key for key, entry in self._cache.items() if entry.is_expired()
        ]

        for key in keys_to_remove:
            del self._cache[key]

        return len(keys_to_remove)

    def get_metrics(self) -> Dict[str, Any]:
        """
        Получить метрики кэша.

        Returns:
            Словарь с метриками
        """
        total_requests = self._metrics["hits"] + self._metrics["misses"]
        hit_rate = self._metrics["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            **self._metrics,
            "size": len(self._cache),
            "max_size": self.max_size,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику кэша.

        Returns:
            Словарь со статистикой
        """
        if not self._cache:
            return {
                "size": 0,
                "oldest_entry_age_seconds": 0,
                "newest_entry_age_seconds": 0,
                "avg_access_count": 0,
            }

        now = datetime.utcnow()
        ages = [
            (now - entry.created_at).total_seconds() for entry in self._cache.values()
        ]
        access_counts = [entry.access_count for entry in self._cache.values()]

        return {
            "size": len(self._cache),
            "oldest_entry_age_seconds": max(ages) if ages else 0,
            "newest_entry_age_seconds": min(ages) if ages else 0,
            "avg_access_count": (
                sum(access_counts) / len(access_counts) if access_counts else 0
            ),
        }
