
"""
1C Server Optimizer
Оптимизация сервера 1С:Предприятие

Источники:
- its.1c.ru - Официальная документация
- infostart.ru - Best practices сообщества
- 1С:Производительность (efsol.ru)
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ServerOptimization:
    """Рекомендация по оптимизации сервера"""

    category: str
    parameter: str
    current_value: Any
    recommended_value: Any
    rationale: str
    expected_improvement: str
    priority: str  # critical, high, medium, low


class OneCServerOptimizer:
    """
    Оптимизация сервера 1С:Предприятие

    Оптимизирует:
    - Кластер серверов
    - Рабочие процессы
    - Connection pooling
    - Кеширование
    - Блокировки
    """

    def __init__(self):
        self.optimization_rules = self._load_optimization_rules()

    async def optimize_server_config(
        self, current_config: Dict[str, Any], workload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Оптимизация конфигурации сервера 1С

        Args:
            current_config: {
                "working_processes": 4,
                "connection_pooling": False,
                "memory_limit_mb": 2048,
                "cluster_mode": "round_robin"
            },
            workload: {
                "concurrent_users": 200,
                "peak_load": "09:00-18:00",
                "database_size_gb": 100,
                "query_intensity": "high"
            }

        Returns:
            Рекомендации по оптимизации
        """
        logger.info("Analyzing 1C Server configuration")

        recommendations = []

        # 1. Рабочие процессы
        wp_recommendation = await self._optimize_working_processes(
            current_config, workload
        )
        if wp_recommendation:
            recommendations.append(wp_recommendation)

        # 2. Connection Pooling
        pool_recommendation = await self._optimize_connection_pooling(
            current_config, workload
        )
        if pool_recommendation:
            recommendations.append(pool_recommendation)

        # 3. Memory allocation
        memory_recommendation = await self._optimize_memory(current_config, workload)
        if memory_recommendation:
            recommendations.append(memory_recommendation)

        # 4. Кластер и балансировка
        cluster_recommendation = await self._optimize_cluster(current_config, workload)
        if cluster_recommendation:
            recommendations.append(cluster_recommendation)

        # 5. Кеширование
        cache_recommendation = await self._optimize_caching(current_config, workload)
        if cache_recommendation:
            recommendations.append(cache_recommendation)

        return {
            "recommendations": recommendations,
            "priority_fixes": self._prioritize_recommendations(recommendations),
            "config_snippet": self._generate_config_file(recommendations),
            "expected_total_improvement": self._estimate_total_improvement(
                recommendations
            ),
            "sources": [
                "https://its.1c.ru/db/metod8dev/",
                "https://infostart.ru/",
                "https://efsol.ru/articles/1c-performance-monitoring/",
            ],
        }

    async def _optimize_working_processes(
        self, config: Dict, workload: Dict
    ) -> Optional[ServerOptimization]:
        """
        Оптимизация количества рабочих процессов

        Формула (из Infostart + ITS):
        - Для CPU-intensive: cores * 1-2
        - Для I/O-intensive: cores * 2-4
        - Минимум: concurrent_users / 10
        """
        current_wp = config.get("working_processes", 4)
        concurrent_users = workload.get("concurrent_users", 100)

        # Рекомендация по формуле
        min_wp_by_users = max(concurrent_users // 10, 2)

        # Если query-intensive
        if workload.get("query_intensity") == "high":
            recommended_wp = min_wp_by_users
        else:
            recommended_wp = min_wp_by_users // 2

        if recommended_wp > current_wp:
            return ServerOptimization(
                category="working_processes",
                parameter="РабочихПроцессов",
                current_value=current_wp,
                recommended_value=recommended_wp,
                rationale=f"Для {concurrent_users} пользователей рекомендуется {recommended_wp} процессов",
                expected_improvement=f"{((recommended_wp/current_wp - 1) * 100):.0f}% больше пропускная способность",
                priority="high",
            )

        return None

    async def _optimize_connection_pooling(
        self, config: Dict, workload: Dict
    ) -> Optional[ServerOptimization]:
        """Оптимизация connection pooling"""
        pooling_enabled = config.get("connection_pooling", False)

        if not pooling_enabled and workload.get("concurrent_users", 0) > 50:
            return ServerOptimization(
                category="connection_pooling",
                parameter="ИспользоватьПулСоединений",
                current_value=False,
                recommended_value=True,
                rationale="Connection pooling критичен для 50+ пользователей",
                expected_improvement="Снижение overhead на 30-40%",
                priority="critical",
            )

        return None

    async def _optimize_memory(
        self, config: Dict, workload: Dict
    ) -> Optional[ServerOptimization]:
        """Оптимизация памяти"""
        current_memory = config.get("memory_limit_mb", 2048)
        concurrent_users = workload.get("concurrent_users", 100)

        # Рекомендация: 50-100MB на пользователя
        recommended_memory = concurrent_users * 75  # 75MB per user

        if recommended_memory > current_memory * 1.5:
            return ServerOptimization(
                category="memory",
                parameter="МаксимальныйРазмерПамяти",
                current_value=f"{current_memory}MB",
                recommended_value=f"{recommended_memory}MB",
                rationale=f"Для {concurrent_users} пользователей нужно больше памяти",
                expected_improvement="Меньше swapping, быстрее работа",
                priority="high",
            )

        return None

    async def _optimize_cluster(
        self, config: Dict, workload: Dict
    ) -> Optional[ServerOptimization]:
        """Оптимизация кластера и балансировки"""
        current_mode = config.get("cluster_mode", "round_robin")

        if workload.get("query_intensity") == "high" and current_mode == "round_robin":
            return ServerOptimization(
                category="cluster",
                parameter="РежимБалансировки",
                current_value="Round Robin",
                recommended_value="По производительности",
                rationale="Для query-intensive нагрузки лучше балансировка по производительности",
                expected_improvement="Равномерное распределение нагрузки",
                priority="medium",
            )

        return None

    async def _optimize_caching(
        self, config: Dict, workload: Dict
    ) -> Optional[ServerOptimization]:
        """Оптимизация кеширования"""
        # Рекомендация включить серверное кеширование
        return ServerOptimization(
            category="caching",
            parameter="ИспользоватьСерверноеКеширование",
            current_value="Auto",
            recommended_value="Включено",
            rationale="Серверное кеширование ускоряет повторяющиеся запросы",
            expected_improvement="30-50% для read-heavy нагрузки",
            priority="high",
        )

    def _prioritize_recommendations(
        self, recommendations: List[ServerOptimization]
    ) -> List[ServerOptimization]:
        """Приоритизация рекомендаций"""
        priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        return sorted(
            recommendations,
            key=lambda x: priority_order.get(x.priority, 1),
            reverse=True,
        )

    def _generate_config_file(self, recommendations: List[ServerOptimization]) -> str:
        """Генерация конфига для 1С кластера"""
        lines = ["# 1C:Enterprise Server Configuration"]
        lines.append("# Generated by AI Architect\n")

        for rec in recommendations:
            lines.append(f"# {rec.rationale}")
            lines.append(f"{rec.parameter} = {rec.recommended_value}\n")

        return "\n".join(lines)

    def _estimate_total_improvement(
        self, recommendations: List[ServerOptimization]
    ) -> str:
        """Оценка общего улучшения"""
        critical_count = len([r for r in recommendations if r.priority == "critical"])
        high_count = len([r for r in recommendations if r.priority == "high"])

        if critical_count > 0:
            return "50-100% overall improvement expected"
        elif high_count >= 2:
            return "30-50% overall improvement expected"
        else:
            return "10-30% overall improvement expected"

    def _load_optimization_rules(self) -> Dict:
        """Загрузка правил оптимизации из ИТС + Infostart"""
        return {
            "working_processes": {
                "formula": "concurrent_users / 10",
                "min": 2,
                "max": 64,
                "source": "Infostart.ru + ITS",
            },
            "connection_pooling": {
                "recommendation": "Всегда включать для 50+ пользователей",
                "source": "ITS",
            },
        }


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        optimizer = OneCServerOptimizer()

        current_config = {
            "working_processes": 4,
            "connection_pooling": False,
            "memory_limit_mb": 2048,
            "cluster_mode": "round_robin",
        }

        workload = {
            "concurrent_users": 200,
            "peak_load": "09:00-18:00",
            "database_size_gb": 100,
            "query_intensity": "high",
        }

        result = await optimizer.optimize_server_config(current_config, workload)

        print("=== 1C Server Optimization ===")
        print(f"Recommendations: {len(result['recommendations'])}")

        for rec in result["priority_fixes"]:
            print(f"\n[{rec.priority.upper()}] {rec.parameter}")
            print(f"  Current: {rec.current_value}")
            print(f"  Recommended: {rec.recommended_value}")
            print(f"  Improvement: {rec.expected_improvement}")

    asyncio.run(test())
