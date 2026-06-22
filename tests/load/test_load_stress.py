"""
Load & Stress Testing - Нагрузочное тестирование
================================================

Нагрузочное и стресс-тестирование для всех компонентов:
- Load testing
- Stress testing
- Spike testing
- Endurance testing
"""

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

# Both tests here target src.infrastructure.event_bus, removed in cleanup — obsolete
# test-rot (not the 1С:Рентген product). Skipped so the CI gate reflects real state.
pytestmark = pytest.mark.skip(
    reason="targets src.infrastructure.event_bus (removed in cleanup); obsolete test-rot"
)

logger = logging.getLogger(__name__)


@dataclass
class LoadTestResult:
    """Результат нагрузочного теста"""

    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time: float
    requests_per_second: float
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    max_response_time: float
    min_response_time: float
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация результата"""
        return {
            "test_name": self.test_name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_time": self.total_time,
            "requests_per_second": self.requests_per_second,
            "avg_response_time": self.avg_response_time,
            "p50_response_time": self.p50_response_time,
            "p95_response_time": self.p95_response_time,
            "p99_response_time": self.p99_response_time,
            "max_response_time": self.max_response_time,
            "min_response_time": self.min_response_time,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat(),
        }


class LoadTester:
    """Нагрузочный тестер"""

    def __init__(self):
        self.results: List[LoadTestResult] = []

    async def load_test(
        self,
        test_name: str,
        func: callable,
        num_requests: int = 1000,
        concurrent: int = 10,
        duration_seconds: Optional[float] = None,
    ) -> LoadTestResult:
        """
        Нагрузочный тест

        Args:
            test_name: Название теста
            func: Функция для тестирования
            num_requests: Количество запросов
            concurrent: Количество одновременных запросов
            duration_seconds: Максимальная длительность (опционально)
        """
        logger.info(f"Starting load test: {test_name}")

        response_times = []
        errors = []
        successful = 0
        failed = 0

        start_time = time.time()

        # Создание семафора для ограничения параллелизма
        semaphore = asyncio.Semaphore(concurrent)

        async def make_request():
            """Выполнение одного запроса"""
            async with semaphore:
                try:
                    req_start = time.time()

                    if asyncio.iscoroutinefunction(func):
                        await func()
                    else:
                        func()

                    req_time = (time.time() - req_start) * 1000  # ms
                    response_times.append(req_time)
                    nonlocal successful
                    successful += 1

                except Exception as e:
                    nonlocal failed
                    failed += 1
                    errors.append(str(e))
                    logger.error(f"Request failed: {e}")

        # Выполнение запросов
        tasks = []
        for i in range(num_requests):
            if duration_seconds and (time.time() - start_time) >= duration_seconds:
                break

            task = asyncio.create_task(make_request())
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time

        # Статистика
        if response_times:
            sorted_times = sorted(response_times)
            n = len(sorted_times)

            result = LoadTestResult(
                test_name=test_name,
                total_requests=num_requests,
                successful_requests=successful,
                failed_requests=failed,
                total_time=total_time,
                requests_per_second=successful / total_time if total_time > 0 else 0,
                avg_response_time=statistics.mean(response_times),
                p50_response_time=sorted_times[n // 2],
                p95_response_time=sorted_times[int(n * 0.95)],
                p99_response_time=sorted_times[int(n * 0.99)],
                max_response_time=max(response_times),
                min_response_time=min(response_times),
                errors=errors[:10],  # Первые 10 ошибок
            )
        else:
            result = LoadTestResult(
                test_name=test_name,
                total_requests=num_requests,
                successful_requests=0,
                failed_requests=failed,
                total_time=total_time,
                requests_per_second=0,
                avg_response_time=0,
                p50_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                max_response_time=0,
                min_response_time=0,
                errors=errors,
            )

        self.results.append(result)

        logger.info(f"Load test completed: {test_name}", extra=result.to_dict())

        return result

    async def stress_test(
        self,
        test_name: str,
        func: callable,
        initial_load: int = 100,
        max_load: int = 1000,
        step: int = 100,
    ) -> List[LoadTestResult]:
        """
        Стресс-тест - постепенное увеличение нагрузки

        Args:
            test_name: Название теста
            func: Функция для тестирования
            initial_load: Начальная нагрузка
            max_load: Максимальная нагрузка
            step: Шаг увеличения нагрузки
        """
        logger.info(f"Starting stress test: {test_name}")

        results = []

        for load in range(initial_load, max_load + 1, step):
            logger.info(f"Stress test load: {load}")

            result = await self.load_test(
                f"{test_name}_load_{load}",
                func,
                num_requests=load,
                concurrent=min(load, 50),
            )

            results.append(result)

            # Проверка деградации
            if result.failed_requests / result.total_requests > 0.1:
                logger.warning(
                    f"High failure rate at load {load}: {result.failed_requests}/{result.total_requests}"
                )
                break

        return results

    async def spike_test(
        self,
        test_name: str,
        func: callable,
        base_load: int = 100,
        spike_load: int = 500,
        spike_duration: float = 10.0,
    ) -> LoadTestResult:
        """
        Spike тест - резкое увеличение нагрузки

        Args:
            test_name: Название теста
            func: Функция для тестирования
            base_load: Базовая нагрузка
            spike_load: Пиковая нагрузка
            spike_duration: Длительность пика (секунды)
        """
        logger.info(f"Starting spike test: {test_name}")

        # Базовая нагрузка
        await self.load_test(f"{test_name}_base", func, num_requests=base_load)

        # Пиковая нагрузка
        spike_result = await self.load_test(
            f"{test_name}_spike",
            func,
            num_requests=spike_load,
            duration_seconds=spike_duration,
        )

        return spike_result

    def get_all_results(self) -> List[LoadTestResult]:
        """Получение всех результатов"""
        return self.results.copy()

    def generate_report(self) -> str:
        """Генерация отчета"""
        report = ["=" * 80]
        report.append("LOAD & STRESS TESTING REPORT")
        report.append("=" * 80)
        report.append("")

        for result in self.results:
            report.append(f"Test: {result.test_name}")
            report.append(f"  Total requests: {result.total_requests}")
            report.append(f"  Successful: {result.successful_requests}")
            report.append(f"  Failed: {result.failed_requests}")
            report.append(f"  RPS: {result.requests_per_second:.2f}")
            report.append(f"  Avg response: {result.avg_response_time:.2f}ms")
            report.append(f"  P95: {result.p95_response_time:.2f}ms")
            report.append(f"  P99: {result.p99_response_time:.2f}ms")
            report.append("")

        return "\n".join(report)


@pytest.mark.asyncio
async def test_event_bus_load():
    """Нагрузочный тест Event Bus"""
    from src.infrastructure.event_bus import Event, EventBus, EventType

    bus = EventBus()
    await bus.start()

    tester = LoadTester()

    async def publish_event():
        event = Event(type=EventType.ML_TRAINING_STARTED)
        await bus.publish(event)

    result = await tester.load_test(
        "event_bus_publish", publish_event, num_requests=1000, concurrent=50
    )

    assert result.successful_requests > 0
    assert result.requests_per_second > 0

    await bus.stop()


@pytest.mark.asyncio
async def test_event_bus_stress():
    """Стресс-тест Event Bus"""
    from src.infrastructure.event_bus import Event, EventBus, EventType

    bus = EventBus()
    await bus.start()

    tester = LoadTester()

    async def publish_event():
        event = Event(type=EventType.ML_TRAINING_STARTED)
        await bus.publish(event)

    results = await tester.stress_test(
        "event_bus_stress", publish_event, initial_load=100, max_load=1000, step=100
    )

    assert len(results) > 0

    await bus.stop()
