
"""
LLM Provider Health Monitor
Версия: 1.0.0

Мониторинг состояния LLM провайдеров с автоматическим переключением.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

import httpx

from .llm_provider_manager import LLMProviderManager, ProviderConfig

logger = logging.getLogger(__name__)


class ProviderHealthStatus(str, Enum):
    """Статус здоровья провайдера"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DEGRADED = "degraded"  # Работает, но медленно


@dataclass
class ProviderHealth:
    """Информация о здоровье провайдера"""

    provider_name: str
    status: ProviderHealthStatus
    last_check: datetime
    latency_ms: Optional[float] = None
    failure_count: int = 0
    success_count: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMHealthMonitor:
    """
    Мониторинг здоровья LLM провайдеров с автоматическим переключением.

    Особенности:
    - Периодическая проверка доступности провайдеров
    - Отслеживание latency и error rate
    - Автоматическое определение нездоровых провайдеров
    - Callback для уведомлений об изменении статуса
    """

    def __init__(
        self,
        manager: LLMProviderManager,
        check_interval_seconds: int = 60,
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
        timeout_seconds: float = 5.0,
        degraded_latency_ms: float = 5000.0,  # > 5 секунд = degraded
    ):
        """
        Args:
            manager: LLM Provider Manager
            check_interval_seconds: Интервал проверки в секундах
            failure_threshold: Количество последовательных ошибок для пометки как unhealthy
            recovery_threshold: Количество успешных проверок для восстановления
            timeout_seconds: Timeout для health check запросов
            degraded_latency_ms: Latency выше этого значения = degraded
        """
        self.manager = manager
        self.check_interval = check_interval_seconds
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.timeout = timeout_seconds
        self.degraded_latency_ms = degraded_latency_ms

        self.health_status: Dict[str, ProviderHealth] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._status_callbacks: list[
            Callable[[str, ProviderHealthStatus, ProviderHealthStatus], None]
        ] = []

        # Инициализация статусов для всех провайдеров
        for provider in self.manager.providers.values():
            if provider.enabled:
                self.health_status[provider.name] = ProviderHealth(
                    provider_name=provider.name,
                    status=ProviderHealthStatus.UNKNOWN,
                    last_check=datetime.utcnow(),
                )

    def add_status_callback(
        self,
        callback: Callable[[str, ProviderHealthStatus, ProviderHealthStatus], None],
    ) -> None:
        """Добавить callback для уведомлений об изменении статуса"""
        self._status_callbacks.append(callback)

    async def start_monitoring(self) -> None:
        """Запустить периодический мониторинг"""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Health monitoring already running")
            return

        self._stop_event.clear()
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("LLM Health Monitor started")

    async def stop_monitoring(self) -> None:
        """Остановить мониторинг"""
        self._stop_event.set()
        if self._monitoring_task:
            await self._monitoring_task
        logger.info("LLM Health Monitor stopped")

    async def _monitoring_loop(self) -> None:
        """Основной цикл мониторинга"""
        while not self._stop_event.is_set():
            try:
                await self._check_all_providers()
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}", exc_info=True)

            # Ждём до следующей проверки или остановки
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.check_interval
                )
            except asyncio.TimeoutError:
                continue

    async def _check_all_providers(self) -> None:
        """Проверить все провайдеры"""
        tasks = []
        for provider in self.manager.providers.values():
            if provider.enabled:
                tasks.append(self._check_provider(provider))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_provider(self, provider: ProviderConfig) -> None:
        """Проверить один провайдер"""
        health = self.health_status.get(provider.name)
        if not health:
            health = ProviderHealth(
                provider_name=provider.name,
                status=ProviderHealthStatus.UNKNOWN,
                last_check=datetime.utcnow(),
            )
            self.health_status[provider.name] = health

        old_status = health.status

        try:
            # Выполняем health check
            start_time = time.time()
            is_healthy = await self._perform_health_check(provider)
            latency_ms = (time.time() - start_time) * 1000

            health.last_check = datetime.utcnow()
            health.latency_ms = latency_ms

            if is_healthy:
                health.success_count += 1
                health.consecutive_successes += 1
                health.consecutive_failures = 0
                health.last_error = None

                # Определяем статус на основе latency
                if latency_ms > self.degraded_latency_ms:
                    new_status = ProviderHealthStatus.DEGRADED
                elif health.consecutive_successes >= self.recovery_threshold:
                    new_status = ProviderHealthStatus.HEALTHY
                else:
                    # В процессе восстановления
                    new_status = (
                        ProviderHealthStatus.HEALTHY
                        if old_status == ProviderHealthStatus.HEALTHY
                        else old_status
                    )
            else:
                health.failure_count += 1
                health.consecutive_failures += 1
                health.consecutive_successes = 0

                if health.consecutive_failures >= self.failure_threshold:
                    new_status = ProviderHealthStatus.UNHEALTHY
                else:
                    new_status = ProviderHealthStatus.DEGRADED

            health.status = new_status

            # Уведомляем об изменении статуса
            if old_status != new_status:
                logger.info(
                    f"Provider {provider.name} status changed: {old_status} -> {new_status} "
                    f"(latency={latency_ms:.1f}ms, failures={health.consecutive_failures})"
                )
                for callback in self._status_callbacks:
                    try:
                        callback(provider.name, old_status, new_status)
                    except Exception as e:
                        logger.warning(f"Error in status callback: {e}", exc_info=True)

        except Exception as e:
            health.failure_count += 1
            health.consecutive_failures += 1
            health.consecutive_successes = 0
            health.last_error = str(e)
            health.last_check = datetime.utcnow()

            if health.consecutive_failures >= self.failure_threshold:
                health.status = ProviderHealthStatus.UNHEALTHY
            else:
                health.status = ProviderHealthStatus.DEGRADED

            logger.warning("Health check failed for {provider.name}: %s", e)

    async def _perform_health_check(self, provider: ProviderConfig) -> bool:
        """
        Выполнить health check для провайдера.

        Для remote провайдеров проверяем доступность base_url.
        Для self-hosted провайдеров проверяем health endpoint.
        """
        try:
            # Определяем URL для health check
            health_url = provider.metadata.get("health_url")
            if not health_url:
                # Используем base_url + /health или просто base_url
                if provider.base_url.endswith("/"):
                    health_url = f"{provider.base_url}health"
                else:
                    health_url = f"{provider.base_url}/health"

            # Если base_url пустой, пробуем использовать известные endpoints
            if not health_url or health_url == "/health":
                # Fallback на base_url из конфига
                health_url = provider.base_url

            if not health_url:
                # Нет URL для проверки, считаем что провайдер недоступен
                return False

            # Выполняем HTTP запрос
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.get(health_url, follow_redirects=True)
                    return response.status_code < 400
                except httpx.TimeoutException:
                    return False
                except httpx.RequestError:
                    # Для некоторых провайдеров /health может не существовать
                    # Пробуем просто проверить доступность base_url
                    try:
                        response = await client.get(
                            provider.base_url, follow_redirects=True
                        )
                        return (
                            response.status_code < 500
                        )  # Любой ответ кроме 5xx = доступен
                    except Exception:
                        return False

        except Exception as e:
            logger.debug("Health check error for {provider.name}: %s", e)
            return False

    def get_provider_health(self, provider_name: str) -> Optional[ProviderHealth]:
        """Получить статус здоровья провайдера"""
        return self.health_status.get(provider_name)

    def is_provider_healthy(self, provider_name: str) -> bool:
        """Проверить, здоров ли провайдер"""
        health = self.get_provider_health(provider_name)
        if not health:
            return False
        return health.status in {
            ProviderHealthStatus.HEALTHY,
            ProviderHealthStatus.DEGRADED,
        }

    def get_healthy_providers(self) -> list[str]:
        """Получить список здоровых провайдеров"""
        return [
            name
            for name, health in self.health_status.items()
            if health.status
            in {ProviderHealthStatus.HEALTHY, ProviderHealthStatus.DEGRADED}
        ]

    def get_all_health_status(self) -> Dict[str, ProviderHealth]:
        """Получить статус всех провайдеров"""
        return self.health_status.copy()
