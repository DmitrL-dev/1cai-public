
"""
Performance Analyzer - Анализ производительности 1С конфигураций
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

PERFORMANCE_CONTRACT = "offline_performance_evidence_contract"


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
                "apdex_score": 0.75 | null,
                "optimization_priorities": [...]
            }
        """
        logger.info("Analyzing performance", extra={"config_name": config_name})

        # 1. Поиск медленных запросов только по предоставленной телеметрии
        slow_queries = await self._find_slow_queries(config_name, metrics)

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
            "mode": PERFORMANCE_CONTRACT,
            "coverage": self._coverage(metrics, slow_queries, resource_usage, apdex),
            "measured": bool(metrics),
            "analysis_date": datetime.now().isoformat(),
            "bottlenecks": bottlenecks,
            "scalability_assessment": scalability,
            "apdex_score": apdex,
            "apdex_measured": apdex is not None,
            "performance_grade": self._get_performance_grade(apdex),
            "optimization_priorities": priorities,
            "recommendations": recommendations,
            "estimated_improvement": self._estimate_improvement(bottlenecks),
            "required_evidence": self._required_evidence(metrics),
            "caveats": self._caveats(metrics, apdex),
        }

    async def _find_slow_queries(
        self, config_name: str, metrics: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """Поиск медленных запросов"""
        if not metrics:
            return []

        candidates = (
            metrics.get("slow_queries")
            or metrics.get("top_slow_queries")
            or metrics.get("queries")
            or []
        )
        if not isinstance(candidates, list):
            return []

        normalized = []
        for index, query in enumerate(candidates, 1):
            if not isinstance(query, dict):
                continue
            avg_time = self._duration_seconds(query)
            threshold = self._number(
                query.get("threshold") or query.get("threshold_seconds")
            )
            if threshold is None:
                threshold = self.performance_thresholds["query_time"]
            executions = self._integer(
                query.get("executions") or query.get("count")
            )
            if avg_time is None or avg_time <= threshold:
                continue
            normalized.append(
                {
                    "location": str(
                        query.get("location")
                        or query.get("name")
                        or query.get("query_name")
                        or query.get("sql")
                        or f"query_{index}"
                    ),
                    "avg_time": avg_time,
                    "executions": executions or 0,
                    "threshold": threshold,
                    "query_type": str(query.get("query_type") or query.get("type") or "unknown"),
                    "source": query.get("source") or "provided_metrics",
                }
            )
        return normalized

    def _duration_seconds(self, query: Dict[str, Any]) -> Optional[float]:
        for key in ("avg_time", "duration", "duration_seconds", "avg_duration_seconds"):
            value = query.get(key)
            parsed = self._number(value)
            if parsed is not None:
                return parsed

        for key in ("duration_ms", "avg_duration_ms", "elapsed_ms"):
            value = query.get(key)
            parsed = self._number(value)
            if parsed is not None:
                return parsed / 1000.0

        return None

    def _number(self, value: Any) -> Optional[float]:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = value.strip().replace(",", ".")
            if not normalized:
                return None
            try:
                return float(normalized)
            except ValueError:
                return None
        return None

    def _integer(self, value: Any) -> Optional[int]:
        parsed = self._number(value)
        return int(parsed) if parsed is not None else None

    async def _analyze_resource_usage(self, metrics: Optional[Dict]) -> List[Dict]:
        """Анализ использования ресурсов"""
        if not metrics:
            return []

        issues = []

        # Memory
        memory_usage = self._number(metrics.get("memory_usage"))
        if (
            memory_usage is not None
            and memory_usage > self.performance_thresholds["memory_usage"]
        ):
            issues.append(
                {
                    "resource": "memory",
                    "usage": memory_usage,
                    "threshold": self.performance_thresholds["memory_usage"],
                }
            )

        # CPU
        cpu_usage = self._number(metrics.get("cpu_usage"))
        if (
            cpu_usage is not None
            and cpu_usage > self.performance_thresholds["cpu_usage"]
        ):
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
                "current_capacity": "measured users" | null,
                "predicted_capacity": "target users (12 months)" | null,
                "scaling_strategy": "strategy or evidence request",
                "bottlenecks": [...]
            }
        """
        if not metrics:
            return {
                "measured": False,
                "current_capacity": None,
                "predicted_capacity": None,
                "scaling_strategy": "needs_load_profile",
                "scaling_readiness": "unknown",
                "recommendations": [
                    "Подключить RAS/Prometheus/TJ метрики",
                    "Собрать текущих активных пользователей и пиковые сессии",
                    "Зафиксировать целевой рост нагрузки на 6-12 месяцев",
                ],
            }

        current_load = metrics.get("current_users") or metrics.get("active_users")
        predicted_load = (
            metrics.get("predicted_users")
            or metrics.get("target_users")
            or metrics.get("expected_users_12m")
        )
        growth_factor = self._number(metrics.get("growth_factor"))
        current_load_number = self._number(current_load)
        predicted_load_number = self._number(predicted_load)
        if (
            predicted_load_number is None
            and current_load_number is not None
            and growth_factor is not None
        ):
            predicted_load_number = int(current_load_number * growth_factor)

        if current_load_number is None:
            return {
                "measured": False,
                "current_capacity": None,
                "predicted_capacity": predicted_load_number,
                "scaling_strategy": "needs_current_load",
                "scaling_readiness": "unknown",
                "recommendations": [
                    "Перед расчетом масштабирования измерить активных пользователей, сессии и пиковые операции."
                ],
            }

        current_load = int(current_load_number)
        predicted_load = (
            int(predicted_load_number) if predicted_load_number is not None else None
        )

        return {
            "measured": predicted_load is not None,
            "current_capacity": f"{current_load} users",
            "predicted_capacity": f"{predicted_load} users (12 months)"
            if predicted_load is not None
            else None,
            "scaling_strategy": self._recommend_scaling_strategy(
                current_load, predicted_load or current_load
            ),
            "scaling_readiness": "measured" if predicted_load is not None else "partial",
            "recommendations": [
                "Валидировать стратегию на нагрузочном профиле",
                "Сверить рекомендации с топом медленных запросов и RAS/TJ метриками",
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
            return None

        response_times = metrics["response_times"]
        if not isinstance(response_times, list):
            return None
        threshold_satisfied = 2.0  # < 2s = satisfied
        threshold_tolerating = 8.0  # < 8s = tolerating

        numeric_response_times = [
            parsed
            for parsed in (self._number(value) for value in response_times)
            if parsed is not None
        ]

        satisfied = len(
            [t for t in numeric_response_times if t < threshold_satisfied]
        )
        tolerating = len(
            [
                t
                for t in numeric_response_times
                if threshold_satisfied <= t < threshold_tolerating
            ]
        )
        total = len(numeric_response_times)

        if total == 0:
            return None

        apdex = (satisfied + 0.5 * tolerating) / total
        return round(apdex, 3)

    def _get_performance_grade(self, apdex: Optional[float]) -> str:
        """Оценка производительности на основе Apdex"""
        if apdex is None:
            return "unknown"
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
                        "source": issue.get("source", "provided_metrics"),
                    }
                )
            elif issue_type == "resource":
                resource = issue.get("resource", "resource")
                usage = float(issue.get("usage", 0))
                threshold = float(issue.get("threshold", 1))
                bottlenecks.append(
                    {
                        "type": f"high_{resource}",
                        "location": str(issue.get("location") or "runtime_metrics"),
                        "metric_name": f"{resource}_usage",
                        "current_value": usage,
                        "threshold": threshold,
                        "impact": "high" if usage >= threshold * 1.15 else "medium",
                        "recommendations": self._get_resource_recommendations(resource),
                        "source": "provided_metrics",
                    }
                )

        return bottlenecks

    def _get_query_optimization_tips(self, query_info: Dict) -> List[str]:
        """Рекомендации по оптимизации запроса"""
        tips = []

        query_type = query_info.get("query_type", "unknown")
        if query_type == "report_generation":
            tips.extend(
                [
                    "Добавить индексы на часто используемые поля",
                    "Использовать временные таблицы",
                    "Оптимизировать JOIN запросы",
                    "Рассмотреть материализованные представления",
                ]
            )
        elif query_type == "document_posting":
            tips.extend(
                [
                    "Оптимизировать триггеры",
                    "Batch processing для массовых операций",
                    "Асинхронная обработка где возможно",
                ]
            )
        else:
            tips.extend(
                [
                    "Получить план выполнения и фактические чтения",
                    "Проверить фильтры, соединения и индексы по фактическим условиям",
                    "Сравнить время до/после на копии продуктивной статистики",
                ]
            )

        return tips

    def _get_resource_recommendations(self, resource: str) -> List[str]:
        if resource == "memory":
            return [
                "Проверить рост памяти по рабочим процессам 1С",
                "Сопоставить пики с регламентными заданиями и тяжелыми отчетами",
                "Собрать дампы/профили перед изменением настроек",
            ]
        if resource == "cpu":
            return [
                "Сверить пики CPU с RAS/TJ событиями и медленными запросами",
                "Проверить регламентные задания и массовые операции",
                "Запланировать нагрузочный прогон после оптимизации запросов",
            ]
        return ["Уточнить источник метрики и порог с владельцем эксплуатации"]

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
        if apdex is not None and apdex < 0.7:
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
                    "estimated_improvement": "requires_before_after_benchmark",
                }
            )

        return recommendations

    def _estimate_improvement(self, bottlenecks: List[Dict]) -> Dict[str, Any]:
        """Оценка потенциального улучшения"""
        if not bottlenecks:
            return {
                "measured": False,
                "potential_speedup": "not_estimated",
                "effort": "none",
                "caveat": "No measured bottlenecks were supplied.",
            }

        # Simplified estimation
        critical_count = len([b for b in bottlenecks if b.get("impact") == "critical"])
        high_count = len([b for b in bottlenecks if b.get("impact") == "high"])

        potential_speedup = critical_count * 30 + high_count * 15

        return {
            "measured": False,
            "potential_speedup": f"{potential_speedup}%",
            "effort": "high" if critical_count > 3 else "medium",
            "estimated_days": critical_count * 3 + high_count * 2,
            "caveat": "Heuristic estimate; validate with before/after benchmarks.",
        }

    def _coverage(
        self,
        metrics: Optional[Dict[str, Any]],
        slow_queries: List[Dict],
        resource_usage: List[Dict],
        apdex: Optional[float],
    ) -> str:
        if not metrics:
            return "no_runtime_metrics"
        covered = []
        if slow_queries:
            covered.append("slow_queries")
        if resource_usage:
            covered.append("resource_thresholds")
        if apdex is not None:
            covered.append("response_times")
        return "+".join(covered) if covered else "metrics_without_threshold_breaches"

    def _required_evidence(self, metrics: Optional[Dict[str, Any]]) -> List[str]:
        required = []
        if not metrics:
            return [
                "slow query log or TJ report",
                "response time samples",
                "CPU/memory metrics",
                "current and target load profile",
            ]
        if "response_times" not in metrics:
            required.append("response time samples for Apdex")
        if not any(key in metrics for key in ("slow_queries", "top_slow_queries", "queries")):
            required.append("slow query log or top SQL report")
        if not any(key in metrics for key in ("current_users", "active_users")):
            required.append("current active users/sessions")
        if not any(
            key in metrics
            for key in ("predicted_users", "target_users", "expected_users_12m", "growth_factor")
        ):
            required.append("target load or growth factor")
        return required

    def _caveats(
        self, metrics: Optional[Dict[str, Any]], apdex: Optional[float]
    ) -> List[str]:
        if not metrics:
            return ["No synthetic bottlenecks or capacity numbers are generated without telemetry."]

        caveats = ["Analysis is limited to metrics supplied by the caller."]
        if apdex is None:
            caveats.append("Apdex is unknown because response time samples are missing.")
        return caveats


from datetime import datetime

# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        analyzer = PerformanceAnalyzer()

        # Example metrics
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
