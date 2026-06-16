from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.analytics.domain.models import AnalyticsReport, MetricType

logger = StructuredLogger(__name__).logger


class AnalyticsService:
    """Сервис аналитики.

    Отвечает за сбор метрик, анализ производительности и генерацию отчетов.
    """

    def __init__(self):
        self._metrics_data: Dict[str, List[Dict[str, Any]]] = {}
        self._reports: List[AnalyticsReport] = []
        logger.info("AnalyticsService initialized")

    def collect_metric(
        self,
        component: str,
        metric_type: MetricType,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Собирает новую метрику.

        Args:
            component: Имя компонента.
            metric_type: Тип метрики.
            value: Значение.
            metadata: Дополнительные данные.
        """
        if component not in self._metrics_data:
            self._metrics_data[component] = []

        metric_entry = {
            "type": metric_type.value,
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        self._metrics_data[component].append(metric_entry)
        logger.debug("Metric collected: %s.{metric_type.value} = {value}", component)

    def analyze_performance(self, component: str, period_days: int = 7) -> Dict[str, Any]:
        """Анализирует производительность компонента за период.

        Args:
            component: Имя компонента.
            period_days: Период анализа в днях.

        Returns:
            Dict[str, Any]: Статистика (avg, min, max, trend).
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)

        metrics = self._metrics_data.get(component, [])
        recent_metrics = [
            m
            for m in metrics
            if datetime.fromisoformat(m["timestamp"]) >= cutoff and m["type"] == MetricType.PERFORMANCE.value
        ]

        if not recent_metrics:
            return {"error": "No data available"}

        values = [m["value"] for m in recent_metrics]

        return {
            "component": component,
            "period_days": period_days,
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "trend": self._calculate_trend(values),
            "samples": len(values),
        }

    def _calculate_trend(self, values: List[float]) -> str:
        """Вычисляет направление тренда.

        Args:
            values: Список значений.

        Returns:
            str: "improving", "degrading", "stable" или "insufficient_data".
        """
        if len(values) < 2:
            return "insufficient_data"

        first_half = values[: len(values) // 2]
        second_half = values[len(values) // 2 :]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        change = (avg_second - avg_first) / avg_first if avg_first > 0 else 0

        if change > 0.1:
            return "improving"
        elif change < -0.1:
            return "degrading"
        else:
            return "stable"

    def calculate_roi(self, component: str, period_days: int = 30) -> Dict[str, Any]:
        """Рассчитывает ROI для компонента.

        Args:
            component: Имя компонента.
            period_days: Период в днях.

        Returns:
            Dict[str, Any]: Данные ROI (improvement, cost_savings, roi_percent).
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)

        # Collect metrics
        metrics = self._metrics_data.get(component, [])
        recent = [m for m in metrics if datetime.fromisoformat(
            m["timestamp"]) >= cutoff]

        # Calculate improvements
        performance_improvement = self._calculate_improvement(
            recent, MetricType.PERFORMANCE)
        quality_improvement = self._calculate_improvement(recent, MetricType.QUALITY)

        # Estimate costs (Simplified)
        cost_savings = self._estimate_cost_savings(
            performance_improvement, quality_improvement)

        # ROI = (Benefits - Costs) / Costs * 100%
        estimated_costs = period_days * 100  # Mock cost
        roi = (cost_savings - estimated_costs) / \
               estimated_costs * 100 if estimated_costs > 0 else 0

        return {
            "component": component,
            "period_days": period_days,
            "performance_improvement": performance_improvement,
            "quality_improvement": quality_improvement,
            "cost_savings": cost_savings,
            "estimated_costs": estimated_costs,
            "roi_percent": roi,
        }

    def _calculate_improvement(self, metrics: List[Dict[str, Any]], metric_type: MetricType) -> float:
        """Рассчитывает процент улучшения для типа метрики."""
        type_metrics = [m for m in metrics if m["type"] == metric_type.value]

        if len(type_metrics) < 2:
            return 0.0

        values = [m["value"] for m in type_metrics]
        first_half = values[: len(values) // 2]
        second_half = values[len(values) // 2 :]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        if avg_first > 0:
            return (avg_second - avg_first) / avg_first
        return 0.0

    def _estimate_cost_savings(self, performance_improvement: float, quality_improvement: float) -> float:
        """Оценивает экономию затрат на основе улучшений."""
        # Simplified model:
        # Performance improvement = less time = less cost
        # Quality improvement = fewer bugs = less fix cost

        time_savings = performance_improvement * 1000  # Mock: hours
        bug_reduction = quality_improvement * 50  # Mock: bug count

        cost_per_hour = 50  # Mock: hourly rate
        cost_per_bug = 200  # Mock: fix cost

        savings = (time_savings * cost_per_hour) + (bug_reduction * cost_per_bug)

        return max(0.0, savings)

    def generate_report(
        self, title: str, period_days: int = 7, components: Optional[List[str]] = None
    ) -> AnalyticsReport:
        """Генерирует комплексный аналитический отчет.

        Args:
            title: Заголовок отчета.
            period_days: Период анализа.
            components: Список компонентов (опционально).

        Returns:
            AnalyticsReport: Объект отчета.
        """
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=period_days)

        if components is None:
            components = list(self._metrics_data.keys())

        report_metrics = {}
        insights = []
        recommendations = []

        for component in components:
            # Performance Analysis
            perf_analysis = self.analyze_performance(component, period_days)
            report_metrics[f"{component}_performance"] = perf_analysis

            # ROI Analysis
            roi_analysis = self.calculate_roi(component, period_days)
            report_metrics[f"{component}_roi"] = roi_analysis

            # Generate Insights
            if perf_analysis.get("trend") == "improving":
                insights.append(
                    f"{component}: Performance is improving ({perf_analysis.get('trend', 'unknown')})")

            if roi_analysis.get("roi_percent", 0) > 0:
                recommendations.append(
                    f"{component}: Positive ROI ({roi_analysis['roi_percent']:.1f}%) - consider expanding"
                )

        report = AnalyticsReport(
            id=f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            title=title,
            period_start=period_start,
            period_end=period_end,
            metrics=report_metrics,
            insights=insights,
            recommendations=recommendations,
        )

        self._reports.append(report)
        logger.info(f"Report generated: {report.id}")
        return report

    def get_all_reports(self) -> List[AnalyticsReport]:
        """Возвращает все сгенерированные отчеты."""
        return self._reports.copy()

    def get_report(self, report_id: str) -> Optional[AnalyticsReport]:
        """Возвращает отчет по ID."""
        return next((r for r in self._reports if r.id == report_id), None)
