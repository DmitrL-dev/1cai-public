
"""
Performance Analyzer - Анализ производительности 1С конфигураций
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


@dataclass
class PerformanceBottleneck:
    """Узкое место производительности"""

    type: str  # slow_query, memory_leak, high_cpu, network_latency
    location: str
    metric_name: str
    current_value: float
    threshold: float
    impact: str  # critical, high, medium, low
    recommendations: List[str]


class PerformanceAnalyzer:
    """
    Анализ производительности 1С конфигураций
    """

    def __init__(self):
        self.performance_thresholds = {
            "query_time": 3.0,  # seconds
            "memory_usage": 0.8,  # 80%
            "cpu_usage": 0.7,  # 70%
            "response_time": 2.0,  # seconds
            "apdex_score": 0.75,  # minimum acceptable
        }

    async def analyze_performance(
        self, config_name: str, metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Комплексный анализ производительности

        Args:
            config_name: Название конфигурации
            metrics: Метрики из Prometheus/Grafana (optional)

        Returns:
            {
                "bottlenecks": [...],
                "scalability_assessment": {...},
                "apdex_score": 0.75,
                "optimization_priorities": [...]
            }
        """
        logger.info("Analyzing performance", extra={"config_name": config_name})

        # 1. Поиск медленных запросов
        slow_queries = await self._find_slow_queries(config_name)

        # 2. Анализ использования ресурсов
        resource_usage = await self._analyze_resource_usage(metrics)

        # 3. Оценка масштабируемости
        scalability = await self._assess_scalability(config_name, metrics)

        # 4. Расчет Apdex score
        apdex = self._calculate_apdex(metrics)

        # 5. Объединение bottlenecks
        bottlenecks = []
        bottlenecks.extend(self._convert_to_bottlenecks(slow_queries, "slow_query"))
        bottlenecks.extend(self._convert_to_bottlenecks(resource_usage, "resource"))

        # 6. Приоритизация оптимизаций
        priorities = self._prioritize_optimizations(bottlenecks)

        # 7. AI рекомендации
        recommendations = await self._generate_performance_recommendations(
            bottlenecks, scalability, apdex
        )

        return {
            "config_name": config_name,
            "analysis_date": datetime.now().isoformat(),
            "bottlenecks": bottlenecks,
            "scalability_assessment": scalability,
            "apdex_score": apdex,
            "performance_grade": self._get_performance_grade(apdex),
            "optimization_priorities": priorities,
            "recommendations": recommendations,
            "estimated_improvement": self._estimate_improvement(bottlenecks),
        }

    async def _find_slow_queries(self, config_name: str) -> List[Dict]:
        """Поиск медленных запросов"""
        # TODO: Интеграция с PostgreSQL slow query log или Neo4j

        # Placeholder - реальные данные из monitoring
        return [
            {
                "location": "Отчет.ПродажиЗаПериод",
                "avg_time": 15.3,
                "executions": 450,
                "threshold": 3.0,
                "query_type": "report_generation",
            },
            {
                "location": "Документ.Заказ.ПриПроведении",
                "avg_time": 5.7,
                "executions": 1200,
                "threshold": 2.0,
                "query_type": "document_posting",
            },
        ]

    async def _analyze_resource_usage(self, metrics: Optional[Dict]) -> List[Dict]:
        """Анализ использования ресурсов"""
        if not metrics:
            return []

        issues = []

        # Memory
        memory_usage = metrics.get("memory_usage", 0)
        if memory_usage > self.performance_thresholds["memory_usage"]:
            issues.append(
                {
                    "resource": "memory",
                    "usage": memory_usage,
                    "threshold": self.performance_thresholds["memory_usage"],
                }
            )

        # CPU
        cpu_usage = metrics.get("cpu_usage", 0)
        if cpu_usage > self.performance_thresholds["cpu_usage"]:
            issues.append(
                {
                    "resource": "cpu",
                    "usage": cpu_usage,
                    "threshold": self.performance_thresholds["cpu_usage"],
                }
            )

        return issues

    async def _assess_scalability(
        self, config_name: str, metrics: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Оценка масштабируемости

        Returns:
            {
                "current_capacity": "1000 users",
                "predicted_capacity": "5000 users (12 months)",
                "scaling_strategy": "Horizontal scaling + caching",
                "bottlenecks": [...]
            }
        """
        # Simplified assessment
        current_load = metrics.get("current_users", 1000) if metrics else 1000

        # Linear extrapolation (упрощенно)
        predicted_load = current_load * 5  # 5x growth in 12 months

        return {
            "current_capacity": f"{current_load} users",
            "predicted_capacity": f"{predicted_load} users (12 months)",
            "scaling_strategy": self._recommend_scaling_strategy(
                current_load, predicted_load
            ),
            "scaling_readiness": "medium",
            "recommendations": [
                "Внедрить кеширование для горячих данных",
                "Оптимизировать медленные запросы",
                "Рассмотреть горизонтальное масштабирование",
            ],
        }

    def _recommend_scaling_strategy(self, current: int, predicted: int) -> str:
        """Рекомендация стратегии масштабирования"""
        growth_ratio = predicted / current if current > 0 else 1

        if growth_ratio > 10:
            return "Horizontal scaling + Database sharding + CDN"
        elif growth_ratio > 5:
            return "Horizontal scaling + Caching + Load balancing"
        elif growth_ratio > 2:
            return "Vertical scaling + Caching"
        else:
            return "Current infrastructure sufficient"

    def _calculate_apdex(self, metrics: Optional[Dict]) -> float:
        """
        Расчет Apdex score (Application Performance Index)

        Apdex = (Satisfied + 0.5*Tolerating) / Total
        """
        if not metrics or "response_times" not in metrics:
            return 0.75  # Default

        response_times = metrics["response_times"]
        threshold_satisfied = 2.0  # < 2s = satisfied
        threshold_tolerating = 8.0  # < 8s = tolerating

        satisfied = len([t for t in response_times if t < threshold_satisfied])
        tolerating = len(
            [
                t
                for t in response_times
                if threshold_satisfied <= t < threshold_tolerating
            ]
        )
        total = len(response_times)

        if total == 0:
            return 0.75

        apdex = (satisfied + 0.5 * tolerating) / total
        return round(apdex, 3)

    def _get_performance_grade(self, apdex: float) -> str:
        """Оценка производительности на основе Apdex"""
        if apdex >= 0.94:
            return "Excellent"
        elif apdex >= 0.85:
            return "Good"
        elif apdex >= 0.70:
            return "Fair"
        elif apdex >= 0.50:
            return "Poor"
        else:
            return "Unacceptable"

    def _convert_to_bottlenecks(
        self, issues: List[Dict], issue_type: str
    ) -> List[Dict]:
        """Конвертация issues в bottlenecks"""
        bottlenecks = []

        for issue in issues:
            if issue_type == "slow_query":
                bottlenecks.append(
                    {
                        "type": "slow_query",
                        "location": issue["location"],
                        "metric_name": "avg_response_time",
                        "current_value": issue["avg_time"],
                        "threshold": issue["threshold"],
                        "impact": "high" if issue["avg_time"] > 10 else "medium",
                        "recommendations": self._get_query_optimization_tips(issue),
                    }
                )

        return bottlenecks

    def _get_query_optimization_tips(self, query_info: Dict) -> List[str]:
        """Рекомендации по оптимизации запроса"""
        tips = []

        if query_info["query_type"] == "report_generation":
            tips.extend(
                [
                    "Добавить индексы на часто используемые поля",
                    "Использовать временные таблицы",
                    "Оптимизировать JOIN запросы",
                    "Рассмотреть материализованные представления",
                ]
            )
        elif query_info["query_type"] == "document_posting":
            tips.extend(
                [
                    "Оптимизировать триггеры",
                    "Batch processing для массовых операций",
                    "Асинхронная обработка где возможно",
                ]
            )

        return tips

    def _prioritize_optimizations(self, bottlenecks: List[Dict]) -> List[Dict]:
        """Приоритизация оптимизаций по impact и effort"""
        impact_score = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        for bn in bottlenecks:
            # Score = impact × (current / threshold)
            impact = impact_score.get(bn.get("impact", "medium"), 2)
            ratio = bn["current_value"] / bn["threshold"] if bn["threshold"] > 0 else 1
            bn["priority_score"] = impact * ratio

        return sorted(
            bottlenecks, key=lambda x: x.get("priority_score", 0), reverse=True
        )

    async def _generate_performance_recommendations(
        self, bottlenecks: List[Dict], scalability: Dict, apdex: float
    ) -> List[Dict]:
        """AI генерация рекомендаций по производительности"""
        recommendations = []

        # По Apdex
        if apdex < 0.7:
            recommendations.append(
                {
                    "category": "user_experience",
                    "priority": "critical",
                    "issue": f"Apdex score too low: {apdex}",
                    "recommendation": "Критическая оптимизация производительности требуется",
                    "quick_wins": [
                        "Включить кеширование",
                        "Оптимизировать top-3 медленных запроса",
                        "Добавить CDN для статики",
                    ],
                }
            )

        # По bottlenecks
        if bottlenecks:
            top_bottleneck = bottlenecks[0]
            recommendations.append(
                {
                    "category": "bottleneck",
                    "priority": "high",
                    "issue": f"Критическое узкое место: {top_bottleneck['location']}",
                    "recommendation": (
                        top_bottleneck["recommendations"][0]
                        if top_bottleneck["recommendations"]
                        else "Оптимизировать"
                    ),
                    "estimated_improvement": "30-50% ускорение",
                }
            )

        return recommendations

    def _estimate_improvement(self, bottlenecks: List[Dict]) -> Dict[str, Any]:
        """Оценка потенциального улучшения"""
        if not bottlenecks:
            return {"potential_speedup": "0%", "effort": "none"}

        # Simplified estimation
        critical_count = len([b for b in bottlenecks if b.get("impact") == "critical"])
        high_count = len([b for b in bottlenecks if b.get("impact") == "high"])

        potential_speedup = critical_count * 30 + high_count * 15

        return {
            "potential_speedup": f"{potential_speedup}%",
            "effort": "high" if critical_count > 3 else "medium",
            "estimated_days": critical_count * 3 + high_count * 2,
        }


from datetime import datetime

# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        analyzer = PerformanceAnalyzer()

        # Mock metrics
        metrics = {
            "current_users": 1000,
            "memory_usage": 0.85,
            "cpu_usage": 0.65,
            "response_times": [1.5, 2.1, 1.8, 15.3, 2.3, 1.9],  # One outlier!
        }

        result = await analyzer.analyze_performance("ERP", metrics)

        print("=== Performance Analysis ===")
        print(f"Apdex Score: {result['apdex_score']}")
        print(f"Grade: {result['performance_grade']}")
        print(f"Bottlenecks found: {len(result['bottlenecks'])}")
        print(
            f"\nPotential improvement: {result['estimated_improvement']['potential_speedup']}"
        )

    asyncio.run(test())
