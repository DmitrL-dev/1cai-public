"""
Система метрик качества тестов YAxUnit.

Предоставляет:
- Code coverage tracking
- Test effectiveness metrics
- Performance benchmarks
- Quality reports
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


@dataclass
class TestMetrics:
    """Метрики качества тестов"""

    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    execution_time: float = 0.0
    code_coverage: float = 0.0
    branch_coverage: float = 0.0
    test_effectiveness: float = 0.0
    false_positive_rate: float = 0.0
    tests_per_bug: float = 0.0
    timestamp: Optional[str] = None


class TestMetricsCollector:
    """
    Сборщик метрик качества тестов.
    """

    def __init__(self, metrics_dir: Path = Path("output/bsl-tests/metrics")):
        """
        Инициализация сборщика метрик.

        Args:
            metrics_dir: Директория для сохранения метрик
        """
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "TestMetricsCollector initialized",
            extra={"metrics_dir": str(self.metrics_dir)},
        )

    def collect_from_junit_report(
        self,
        report_path: Path,
        execution_time: Optional[float] = None,
    ) -> TestMetrics:
        """
        Собирает метрики из JUnit XML отчета.

        Args:
            report_path: Путь к JUnit XML отчету
            execution_time: Время выполнения тестов (опционально)

        Returns:
            TestMetrics с собранными метриками
        """
        if not report_path.exists():
            logger.warning(
                "JUnit report not found", extra={"report_path": str(report_path)}
            )
            return TestMetrics()

        try:
            tree = ET.parse(report_path)
            root = tree.getroot()

            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            skipped_tests = 0
            total_time = 0.0

            # Парсим JUnit формат
            for testsuite in root.findall(".//testsuite"):
                total_tests += int(testsuite.get("tests", 0))
                passed_tests += (
                    int(testsuite.get("tests", 0))
                    - int(testsuite.get("failures", 0))
                    - int(testsuite.get("errors", 0))
                )
                failed_tests += int(testsuite.get("failures", 0)) + int(
                    testsuite.get("errors", 0)
                )
                skipped_tests += int(testsuite.get("skipped", 0))
                total_time += float(testsuite.get("time", 0.0))

            # Используем переданное время или время из отчета
            exec_time = execution_time if execution_time is not None else total_time

            metrics = TestMetrics(
                total_tests=total_tests,
                passed_tests=passed_tests,
                failed_tests=failed_tests,
                skipped_tests=skipped_tests,
                execution_time=exec_time,
                timestamp=datetime.now().isoformat(),
            )

            logger.info(
                "Metrics collected from JUnit report",
                extra={
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
                    "execution_time": exec_time,
                },
            )

            return metrics

        except Exception as e:
            logger.error(
                "Failed to parse JUnit report",
                extra={"report_path": str(report_path), "error": str(e)},
                exc_info=True,
            )
            return TestMetrics()

    def calculate_effectiveness(
        self,
        metrics: TestMetrics,
        bugs_found: int = 0,
        false_positives: int = 0,
    ) -> TestMetrics:
        """
        Рассчитывает эффективность тестов.

        Args:
            metrics: Базовые метрики
            bugs_found: Количество найденных багов
            false_positives: Количество ложных срабатываний

        Returns:
            TestMetrics с рассчитанной эффективностью
        """
        # Test effectiveness = (bugs_found / total_tests) * 100
        if metrics.total_tests > 0:
            metrics.test_effectiveness = (bugs_found / metrics.total_tests) * 100
        else:
            metrics.test_effectiveness = 0.0

        # False positive rate = (false_positives / total_tests) * 100
        if metrics.total_tests > 0:
            metrics.false_positive_rate = (false_positives / metrics.total_tests) * 100
        else:
            metrics.false_positive_rate = 0.0

        # Tests per bug = total_tests / bugs_found (если есть баги)
        if bugs_found > 0:
            metrics.tests_per_bug = metrics.total_tests / bugs_found
        else:
            metrics.tests_per_bug = 0.0

        logger.info(
            "Test effectiveness calculated",
            extra={
                "test_effectiveness": metrics.test_effectiveness,
                "false_positive_rate": metrics.false_positive_rate,
                "tests_per_bug": metrics.tests_per_bug,
            },
        )

        return metrics

    def save_metrics(
        self,
        metrics: TestMetrics,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Сохраняет метрики в JSON файл.

        Args:
            metrics: Метрики для сохранения
            filename: Имя файла (опционально, по умолчанию timestamp)

        Returns:
            Путь к сохраненному файлу
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_metrics_{timestamp}.json"

        metrics_file = self.metrics_dir / filename

        # Конвертируем в словарь
        metrics_dict = asdict(metrics)

        # Сохраняем в JSON
        with metrics_file.open("w", encoding="utf-8") as f:
            json.dump(metrics_dict, f, indent=2, ensure_ascii=False)

        logger.info("Metrics saved", extra={"metrics_file": str(metrics_file)})

        return metrics_file

    def load_metrics(self, filename: str) -> Optional[TestMetrics]:
        """
        Загружает метрики из JSON файла.

        Args:
            filename: Имя файла с метриками

        Returns:
            TestMetrics или None если файл не найден
        """
        metrics_file = self.metrics_dir / filename

        if not metrics_file.exists():
            logger.warning(
                "Metrics file not found", extra={"metrics_file": str(metrics_file)}
            )
            return None

        try:
            with metrics_file.open("r", encoding="utf-8") as f:
                metrics_dict = json.load(f)

            return TestMetrics(**metrics_dict)

        except Exception as e:
            logger.error(
                "Failed to load metrics",
                extra={"metrics_file": str(metrics_file), "error": str(e)},
                exc_info=True,
            )
            return None

    def generate_report(
        self,
        metrics: TestMetrics,
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Генерирует текстовый отчет по метрикам.

        Args:
            metrics: Метрики для отчета
            output_path: Путь для сохранения отчета (опционально)

        Returns:
            Текст отчета
        """
        report_lines = [
            "=" * 80,
            "YAxUnit Test Metrics Report",
            "=" * 80,
            "",
            f"Timestamp: {metrics.timestamp or 'N/A'}",
            "",
            "Test Execution:",
            f"  Total tests:     {metrics.total_tests}",
            f"  Passed:          {metrics.passed_tests}",
            f"  Failed:          {metrics.failed_tests}",
            f"  Skipped:         {metrics.skipped_tests}",
            f"  Execution time:  {metrics.execution_time:.2f}s",
            "",
            "Coverage:",
            f"  Code coverage:   {metrics.code_coverage:.1f}%",
            f"  Branch coverage: {metrics.branch_coverage:.1f}%",
            "",
            "Effectiveness:",
            f"  Test effectiveness: {metrics.test_effectiveness:.1f}%",
            f"  False positive rate: {metrics.false_positive_rate:.1f}%",
            f"  Tests per bug: {metrics.tests_per_bug:.1f}",
            "",
            "=" * 80,
        ]

        report_text = "\n".join(report_lines)

        if output_path:
            output_path.write_text(report_text, encoding="utf-8")
            logger.info("Report saved", extra={"output_path": str(output_path)})

        return report_text

    def compare_metrics(
        self,
        current: TestMetrics,
        previous: TestMetrics,
    ) -> Dict[str, Any]:
        """
        Сравнивает текущие метрики с предыдущими.

        Args:
            current: Текущие метрики
            previous: Предыдущие метрики

        Returns:
            Словарь с результатами сравнения
        """
        comparison = {
            "total_tests": {
                "current": current.total_tests,
                "previous": previous.total_tests,
                "change": current.total_tests - previous.total_tests,
                "change_percent": (
                    (
                        (current.total_tests - previous.total_tests)
                        / previous.total_tests
                        * 100
                    )
                    if previous.total_tests > 0
                    else 0.0
                ),
            },
            "pass_rate": {
                "current": (
                    (current.passed_tests / current.total_tests * 100)
                    if current.total_tests > 0
                    else 0.0
                ),
                "previous": (
                    (previous.passed_tests / previous.total_tests * 100)
                    if previous.total_tests > 0
                    else 0.0
                ),
                "change": (
                    (current.passed_tests / current.total_tests * 100)
                    - (previous.passed_tests / previous.total_tests * 100)
                    if current.total_tests > 0 and previous.total_tests > 0
                    else 0.0
                ),
            },
            "execution_time": {
                "current": current.execution_time,
                "previous": previous.execution_time,
                "change": current.execution_time - previous.execution_time,
                "change_percent": (
                    (
                        (current.execution_time - previous.execution_time)
                        / previous.execution_time
                        * 100
                    )
                    if previous.execution_time > 0
                    else 0.0
                ),
            },
        }

        logger.info(
            "Metrics compared",
            extra={
                "total_tests_change": comparison["total_tests"]["change"],
                "pass_rate_change": comparison["pass_rate"]["change"],
            },
        )

        return comparison
