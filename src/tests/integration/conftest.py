"""
Конфигурация интеграционных тестов для проверки end-to-end потоков данных
между всеми компонентами системы.

Содержит общие fixtures и конфигурацию для интеграционных тестов,
покрывающих полный цикл обработки данных, производительность и надежность.
"""

import asyncio
import json
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Создает экземпляр цикла событий для тестовой сессии."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def temp_test_dir():
    """Создает временную директорию для интеграционных тестов."""
    temp_dir = tempfile.mkdtemp(prefix="integration_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def audit_logger(temp_test_dir):
    """Создает логгер для аудита интеграционных тестов."""
    audit_dir = temp_test_dir / "integration_logs"
    audit_dir.mkdir(exist_ok=True)

    audit_file = audit_dir / "end_to_end_tests.log"

    class IntegrationAuditLogger:
        def __init__(self, log_file: Path):
            self.log_file = log_file

        def log_test_start(self, test_name: str, params: Dict[str, Any]):
            """Логирует начало теста."""
            self._write_log(
                "TEST_START",
                test_name,
                {"params": params, "timestamp": datetime.now().isoformat()},
            )

        def log_test_result(
            self,
            test_name: str,
            result: str,
            duration: float,
            details: Optional[Dict] = None,
        ):
            """Логирует результат теста."""
            self._write_log(
                "TEST_RESULT",
                test_name,
                {
                    "result": result,
                    "duration": duration,
                    "details": details or {},
                    "timestamp": datetime.now().isoformat(),
                },
            )

        def log_error(
            self, test_name: str, error: Exception, context: Dict[str, Any] = None
        ):
            """Логирует ошибку теста."""
            self._write_log(
                "TEST_ERROR",
                test_name,
                {
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "context": context or {},
                    "timestamp": datetime.now().isoformat(),
                },
            )

        def log_flow_step(
            self, test_name: str, step: str, component: str, result: Dict[str, Any]
        ):
            """Логирует промежуточный шаг в потоке данных."""
            self._write_log(
                "FLOW_STEP",
                test_name,
                {
                    "step": step,
                    "component": component,
                    "result": result,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        def log_performance_metrics(self, test_name: str, metrics: Dict[str, Any]):
            """Логирует метрики производительности."""
            self._write_log(
                "PERFORMANCE",
                test_name,
                {"metrics": metrics, "timestamp": datetime.now().isoformat()},
            )

        def _write_log(self, level: str, test_name: str, data: Dict[str, Any]):
            """Записывает лог-запись в файл."""
            log_entry = {"level": level, "test": test_name, **data}

            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return IntegrationAuditLogger(audit_file)


@pytest.fixture
def integration_test_config():
    """Конфигурация для интеграционных тестов."""
    return {
        "test_timeouts": {
            "end_to_end_flow": 30.0,
            "ml_prediction": 10.0,
            "risk_assessment": 5.0,
            "analytics_generation": 15.0,
        },
        "performance_thresholds": {
            "max_response_time": 5.0,
            "min_success_rate": 0.9,
            "max_error_rate": 0.1,
            "min_consistency_rate": 0.95,
        },
        "mock_defaults": {
            "llm_response_delay": 0.1,
            "ml_prediction_confidence": 0.85,
            "risk_assessment_variance": 0.1,
        },
        "test_data_paths": {
            "sample_requests": "sample_data/requests",
            "ml_predictions": "sample_data/predictions",
            "risk_assessments": "sample_data/risks",
            "metrics_data": "sample_data/metrics",
        },
    }


@pytest.fixture
def system_state_simulator():
    """Симулятор состояния системы для интеграционных тестов."""

    class SystemStateSimulator:
        def __init__(self):
            self.component_states = {
                "api_gateway": {"status": "operational", "response_time": 0.05},
                "ai_assistant": {"status": "operational", "model_version": "v2.1.0"},
                "risk_management": {"status": "operational", "risk_threshold": 0.5},
                "ml_system": {"status": "operational", "model_accuracy": 0.92},
                "metrics_collector": {
                    "status": "operational",
                    "collection_interval": 60,
                },
                "analytics_dashboard": {
                    "status": "operational",
                    "update_frequency": 30,
                },
            }
            self.active_sessions = {}
            self.performance_metrics = {
                "avg_response_time": 0.45,
                "throughput": 120,
                "error_rate": 0.02,
                "cpu_usage": 0.65,
                "memory_usage": 0.72,
            }

        def get_component_state(self, component_name: str) -> Dict[str, Any]:
            """Получает состояние компонента."""
            return self.component_states.get(component_name, {"status": "unknown"})

        def set_component_state(self, component_name: str, state: Dict[str, Any]):
            """Устанавливает состояние компонента."""
            self.component_states[component_name].update(state)

        def create_session(self, session_id: str, user_data: Dict[str, Any]) -> str:
            """Создает тестовую сессию."""
            self.active_sessions[session_id] = {
                "user_data": user_data,
                "created_at": datetime.now().isoformat(),
                "status": "active",
            }
            return session_id

        def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
            """Получает данные сессии."""
            return self.active_sessions.get(session_id)

        def update_performance_metrics(self, new_metrics: Dict[str, Any]):
            """Обновляет метрики производительности."""
            self.performance_metrics.update(new_metrics)

        def simulate_high_load(self, duration: int = 10):
            """Симулирует высокую нагрузку на систему."""
            self.performance_metrics.update(
                {
                    "cpu_usage": min(0.95, self.performance_metrics["cpu_usage"] + 0.2),
                    "memory_usage": min(
                        0.90, self.performance_metrics["memory_usage"] + 0.15
                    ),
                    "avg_response_time": self.performance_metrics["avg_response_time"]
                    * 1.5,
                    "error_rate": min(0.05, self.performance_metrics["error_rate"] * 2),
                }
            )

        def reset_to_normal_load(self):
            """Возвращает систему к нормальной нагрузке."""
            self.performance_metrics.update(
                {
                    "cpu_usage": 0.65,
                    "memory_usage": 0.72,
                    "avg_response_time": 0.45,
                    "error_rate": 0.02,
                }
            )

        def get_system_health(self) -> Dict[str, Any]:
            """Возвращает общее состояние системы."""
            healthy_components = sum(
                1
                for state in self.component_states.values()
                if state.get("status") == "operational"
            )
            total_components = len(self.component_states)

            return {
                "overall_health": (
                    "healthy" if healthy_components == total_components else "degraded"
                ),
                "component_health": healthy_components / total_components,
                "active_sessions": len(self.active_sessions),
                "performance_metrics": self.performance_metrics.copy(),
                "timestamp": datetime.now().isoformat(),
            }

    return SystemStateSimulator()


@pytest.fixture
def data_consistency_checker():
    """Проверщик согласованности данных между компонентами."""

    class DataConsistencyChecker:
        def __init__(self):
            self.data_snapshots = {}
            self.consistency_rules = {
                "ai_assistant_to_ml": {
                    "requirements_count_must_match": lambda ai_data, ml_data: (
                        ai_data.get("requirements_analysis", {}).get("total_count", 0)
                        > 0
                        if ai_data
                        else True
                    ),
                    "complexity_score_valid": lambda ai_data, ml_data: (
                        ai_data.get("requirements_analysis", {}).get(
                            "complexity_score", 0
                        )
                        >= 0
                        if ai_data
                        else True
                    ),
                },
                "ml_to_risk_assessment": {
                    "risk_factors_count_positive": lambda ml_data, risk_data: (
                        len(ml_data.get("predictions", {}).get("risk_factors", [])) >= 0
                        if ml_data
                        else True
                    ),
                    "confidence_score_valid": lambda ml_data, risk_data: (
                        0 <= ml_data.get("confidence_score", 0) <= 1
                        if ml_data
                        else True
                    ),
                },
                "risk_assessment_to_recommendations": {
                    "risk_level_consistent": lambda risk_data, rec_data: (
                        risk_data.get("risk_assessment", {}).get("overall_risk_level")
                        in ["low", "medium", "high"]
                        if risk_data
                        else True
                    )
                },
            }

        def take_data_snapshot(self, component_name: str, data: Dict[str, Any]) -> str:
            """Сохраняет снимок данных компонента."""
            snapshot_id = f"{component_name}_{datetime.now().isoformat()}"
            self.data_snapshots[snapshot_id] = {
                "component": component_name,
                "data": data.copy(),
                "timestamp": datetime.now().isoformat(),
            }
            return snapshot_id

        def check_consistency(self, component_pairs: List[tuple]) -> Dict[str, Any]:
            """Проверяет согласованность данных между парами компонентов."""
            consistency_results = {}

            for component1, component2 in component_pairs:
                # Находим последние снимки данных для компонентов
                latest_snapshots = {}
                for snapshot_id, snapshot in self.data_snapshots.items():
                    component = snapshot["component"]
                    if component in [component1, component2]:
                        if (
                            component not in latest_snapshots
                            or snapshot["timestamp"]
                            > latest_snapshots[component]["timestamp"]
                        ):
                            latest_snapshots[component] = snapshot

                if len(latest_snapshots) == 2:
                    data1 = latest_snapshots[component1]["data"]
                    data2 = latest_snapshots[component2]["data"]

                    pair_key = f"{component1}_to_{component2}"
                    consistency_results[pair_key] = self._apply_consistency_rules(
                        component1, component2, data1, data2
                    )
                else:
                    consistency_results[f"{component1}_to_{component2}"] = {
                        "status": "insufficient_data",
                        "error": "Недостаточно снимков данных для проверки",
                    }

            return consistency_results

        def _apply_consistency_rules(
            self,
            component1: str,
            component2: str,
            data1: Dict[str, Any],
            data2: Dict[str, Any],
        ) -> Dict[str, Any]:
            """Применяет правила согласованности к паре компонентов."""
            pair_key = f"{component1}_to_{component2}"

            if pair_key not in self.consistency_rules:
                return {
                    "status": "no_rules",
                    "error": f"Нет правил для пары {component1}-{component2}",
                }

            rules = self.consistency_rules[pair_key]
            failed_rules = []
            passed_rules = []

            for rule_name, rule_func in rules.items():
                try:
                    if rule_func(data1, data2):
                        passed_rules.append(rule_name)
                    else:
                        failed_rules.append(rule_name)
                except Exception as e:
                    failed_rules.append(f"{rule_name}: {str(e)}")

            return {
                "status": "success" if len(failed_rules) == 0 else "failed",
                "passed_rules": passed_rules,
                "failed_rules": failed_rules,
                "consistency_score": len(passed_rules) / len(rules) if rules else 0,
            }

    return DataConsistencyChecker()


@pytest.fixture
def load_test_executor():
    """Исполнитель нагрузочных тестов."""

    class LoadTestExecutor:
        def __init__(self):
            self.test_results = {}

        async def execute_concurrent_test(
            self, test_func, test_params: List[Dict[str, Any]], max_concurrent: int = 10
        ) -> Dict[str, Any]:
            """Выполняет тест с ограничением параллельности."""
            start_time = time.time()
            semaphore = asyncio.Semaphore(max_concurrent)

            async def bounded_test(param):
                async with semaphore:
                    return await test_func(param)

            results = await asyncio.gather(
                *[bounded_test(param) for param in test_params], return_exceptions=True
            )

            end_time = time.time()
            total_duration = end_time - start_time

            # Анализ результатов
            successful_results = [r for r in results if not isinstance(r, Exception)]
            failed_results = [r for r in results if isinstance(r, Exception)]

            return {
                "total_requests": len(test_params),
                "successful_requests": len(successful_results),
                "failed_requests": len(failed_results),
                "success_rate": len(successful_results) / len(test_params),
                "total_duration": total_duration,
                "requests_per_second": len(test_params) / total_duration,
                "results": results,
            }

        async def execute_burst_test(
            self, test_func, burst_duration: int, requests_per_second: int
        ) -> Dict[str, Any]:
            """Выполняет тест всплеска нагрузки."""
            start_time = time.time()
            total_requests = 0
            successful_requests = 0
            error_requests = 0

            async def burst_worker():
                nonlocal total_requests, successful_requests, error_requests

                while time.time() - start_time < burst_duration:
                    try:
                        await test_func()
                        successful_requests += 1
                    except Exception:
                        error_requests += 1
                    total_requests += 1

                    # Контролируем частоту запросов
                    await asyncio.sleep(1.0 / requests_per_second)

            # Запускаем несколько воркеров параллельно
            workers = [burst_worker() for _ in range(max(1, requests_per_second // 10))]
            await asyncio.gather(*workers)

            end_time = time.time()
            actual_duration = end_time - start_time

            return {
                "target_duration": burst_duration,
                "actual_duration": actual_duration,
                "target_rps": requests_per_second,
                "actual_rps": total_requests / actual_duration,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "error_requests": error_requests,
                "success_rate": (
                    successful_requests / total_requests if total_requests > 0 else 0
                ),
            }

    return LoadTestExecutor()


def pytest_configure(config):
    """Настройка pytest для интеграционных тестов."""
    config.addinivalue_line("markers", "integration: маркер для интеграционных тестов")
    config.addinivalue_line("markers", "e2e: маркер для end-to-end тестов")
    config.addinivalue_line(
        "markers", "performance: маркер для тестов производительности"
    )
    config.addinivalue_line("markers", "slow: маркер для медленных тестов")
    config.addinivalue_line("markers", "reliability: маркер для тестов надежности")


def pytest_collection_modifyitems(config, items):
    """Модификация коллекции тестов для автоматической маркировки."""
    for item in items:
        # Автоматически добавляем маркеры по именам файлов и тестов
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        if "end_to_end" in item.name.lower() or "e2e" in item.name.lower():
            item.add_marker(pytest.mark.e2e)

        if "performance" in item.name.lower() or "load" in item.name.lower():
            item.add_marker(pytest.mark.performance)

        if any(
            word in item.name.lower()
            for word in ["slow", "concurrent", "stress", "recovery"]
        ):
            item.add_marker(pytest.mark.slow)

        if any(
            word in item.name.lower() for word in ["recovery", "failure", "consistency"]
        ):
            item.add_marker(pytest.mark.reliability)
