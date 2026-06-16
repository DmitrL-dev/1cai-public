
"""
Technology Selector - AI выбор технологического стека
Помогает архитектору выбрать оптимальные технологии для проекта
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class TechnologyOption:
    """Вариант технологии"""

    name: str
    category: str
    best_for: List[str]
    complexity: str  # low, medium, high
    cost: str  # low, medium, high
    maturity: str  # stable, mature, cutting-edge
    vendor_lock_in: bool
    community_support: str  # weak, moderate, strong


class TechnologySelector:
    """
    AI-помощник для выбора технологий
    """

    def __init__(self):
        self.tech_catalog = self._load_technology_catalog()

    def _load_technology_catalog(self) -> Dict[str, TechnologyOption]:
        """Загрузка каталога технологий для 1С"""
        return {
            # Message Brokers / ESB
            "apache_kafka": TechnologyOption(
                name="Apache Kafka",
                category="message_broker",
                best_for=["high-throughput", "event-driven", "streaming", "real-time"],
                complexity="high",
                cost="medium",
                maturity="mature",
                vendor_lock_in=False,
                community_support="strong",
            ),
            "rabbitmq": TechnologyOption(
                name="RabbitMQ",
                category="message_broker",
                best_for=["reliable-messaging", "microservices", "task-queues", "rpc"],
                complexity="medium",
                cost="low",
                maturity="mature",
                vendor_lock_in=False,
                community_support="strong",
            ),
            "1c_bus": TechnologyOption(
                name="1С:Шина",
                category="esb",
                best_for=[
                    "1c-native",
                    "enterprise-integration",
                    "transformation",
                    "routing",
                ],
                complexity="medium",
                cost="medium",
                maturity="stable",
                vendor_lock_in=True,
                community_support="moderate",
            ),
            # API Gateways
            "kong": TechnologyOption(
                name="Kong",
                category="api_gateway",
                best_for=["rate-limiting", "authentication", "monitoring", "plugins"],
                complexity="medium",
                cost="low",
                maturity="mature",
                vendor_lock_in=False,
                community_support="strong",
            ),
            "nginx": TechnologyOption(
                name="Nginx + Lua",
                category="api_gateway",
                best_for=["lightweight", "high-performance", "simple-routing"],
                complexity="low",
                cost="low",
                maturity="mature",
                vendor_lock_in=False,
                community_support="strong",
            ),
            # Caching
            "redis": TechnologyOption(
                name="Redis",
                category="cache",
                best_for=["session-storage", "caching", "pub-sub", "rate-limiting"],
                complexity="low",
                cost="low",
                maturity="mature",
                vendor_lock_in=False,
                community_support="strong",
            ),
            "memcached": TechnologyOption(
                name="Memcached",
                category="cache",
                best_for=["simple-caching", "high-performance"],
                complexity="low",
                cost="low",
                maturity="mature",
                vendor_lock_in=False,
                community_support="moderate",
            ),
            # Databases
            "postgresql": TechnologyOption(
                name="PostgreSQL",
                category="database",
                best_for=["relational-data", "complex-queries", "acid", "jsonb"],
                complexity="medium",
                cost="low",
                maturity="mature",
                vendor_lock_in=False,
                community_support="strong",
            ),
            "mongodb": TechnologyOption(
                name="MongoDB",
                category="database",
                best_for=["document-storage", "flexible-schema", "horizontal-scaling"],
                complexity="medium",
                cost="low",
                maturity="mature",
                vendor_lock_in=False,
                community_support="strong",
            ),
            "neo4j": TechnologyOption(
                name="Neo4j",
                category="graph_database",
                best_for=["relationships", "graph-queries", "recommendations"],
                complexity="medium",
                cost="medium",
                maturity="mature",
                vendor_lock_in=False,
                community_support="moderate",
            ),
            # Search
            "elasticsearch": TechnologyOption(
                name="Elasticsearch",
                category="search",
                best_for=["full-text-search", "analytics", "logging"],
                complexity="high",
                cost="medium",
                maturity="mature",
                vendor_lock_in=False,
                community_support="strong",
            ),
        }

    async def recommend_technology_stack(
        self, requirements: Dict[str, Any], constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Рекомендация технологического стека на основе требований

        Args:
            requirements: {
                "scale": "high",  # low/medium/high
                "availability": 0.999,  # SLA
                "performance": "< 2s response time",
                "load": "10000 requests/day",
                "integration_type": "event-driven"
            },
            constraints: {
                "budget": "medium",  # low/medium/high
                "team_skills": ["BSL", "Python", "PostgreSQL"],
                "existing_tech": ["1С:ERP", "PostgreSQL"],
                "compliance": ["GDPR", "152-ФЗ"],
                "deployment": "on-premise"  # on-premise/cloud/hybrid
            }

        Returns:
            Рекомендованный стек с обоснованием
        """
        logger.info("Analyzing requirements for tech stack recommendation")

        # Scoring каждой технологии
        recommendations = {}

        # 1. Integration Bus
        if requirements.get("integration_type") in ["event-driven", "async"]:
            integration_options = self._score_integration_options(
                requirements, constraints
            )
            recommendations["integration_bus"] = integration_options[0]  # Best score

        # 2. API Gateway
        if requirements.get("scale") in ["medium", "high"]:
            api_options = self._score_api_gateway_options(requirements, constraints)
            recommendations["api_gateway"] = api_options[0]

        # 3. Caching
        if requirements.get("performance") or requirements.get("scale") == "high":
            cache_options = self._score_cache_options(requirements, constraints)
            recommendations["caching"] = cache_options[0]

        # 4. Search
        if requirements.get("search_required"):
            search_options = self._score_search_options(requirements, constraints)
            recommendations["search"] = search_options[0]

        # AI анализ и финальная рекомендация
        architecture_pattern = self._recommend_architecture_pattern(requirements)

        return {
            "recommended_stack": recommendations,
            "architecture_pattern": architecture_pattern,
            "estimated_cost": self._estimate_total_cost(recommendations),
            "implementation_complexity": self._estimate_complexity(recommendations),
            "migration_plan": self._generate_migration_plan(recommendations),
            "risks": self._assess_technology_risks(recommendations),
            "alternatives": self._generate_alternatives(recommendations),
        }

    def _score_integration_options(
        self, requirements: Dict, constraints: Dict
    ) -> List[Dict]:
        """Scoring опций для integration bus"""
        options = []

        # Kafka
        kafka_score = 0
        if requirements.get("scale") == "high":
            kafka_score += 3
        if requirements.get("load", "").startswith("10000"):
            kafka_score += 2
        if constraints.get("budget") != "low":
            kafka_score += 2

        options.append(
            {
                "option": "Apache Kafka",
                "score": kafka_score,
                "reason": "Высокая пропускная способность, событийная архитектура",
                "pros": ["Масштабируемость", "Streaming", "Durability"],
                "cons": ["Операционная сложность", "Требует экспертизы"],
            }
        )

        # RabbitMQ
        rabbitmq_score = 0
        if requirements.get("scale") in ["low", "medium"]:
            rabbitmq_score += 3
        if constraints.get("budget") == "low":
            rabbitmq_score += 2
        if "Python" in constraints.get("team_skills", []):
            rabbitmq_score += 1

        options.append(
            {
                "option": "RabbitMQ",
                "score": rabbitmq_score,
                "reason": "Надежность, простота, зрелость",
                "pros": [
                    "Простота настройки",
                    "Гибкая маршрутизация",
                    "Низкая стоимость",
                ],
                "cons": ["Меньшая пропускная способность чем Kafka"],
            }
        )

        # 1С:Шина
        bus_score = 0
        if "1С" in str(constraints.get("existing_tech", [])):
            bus_score += 3
        if constraints.get("deployment") == "on-premise":
            bus_score += 2

        options.append(
            {
                "option": "1С:Шина",
                "score": bus_score,
                "reason": "Нативная интеграция с 1С",
                "pros": ["Интеграция с 1С", "Transformation", "Routing"],
                "cons": ["Vendor lock-in", "Ограниченное сообщество"],
            }
        )

        return sorted(options, key=lambda x: x["score"], reverse=True)

    def _score_api_gateway_options(
        self, requirements: Dict, constraints: Dict
    ) -> List[Dict]:
        """Scoring опций для API Gateway"""
        options = [
            {
                "option": "Kong",
                "score": 8.5,
                "reason": "Rate limiting, authentication, мониторинг",
                "pros": ["Богатая функциональность", "Plugins", "Масштабируемость"],
                "cons": ["Требует PostgreSQL"],
            },
            {
                "option": "Nginx + Lua",
                "score": 7.0,
                "reason": "Легковесность и производительность",
                "pros": ["Высокая производительность", "Простота"],
                "cons": ["Меньше функций"],
            },
        ]
        return sorted(options, key=lambda x: x["score"], reverse=True)

    def _score_cache_options(self, requirements: Dict, constraints: Dict) -> List[Dict]:
        """Scoring опций для кеширования"""
        return [
            {
                "option": "Redis",
                "score": 9.0,
                "reason": "Универсальность и производительность",
                "pros": ["Быстрый", "Pub/Sub", "Data structures"],
                "cons": ["In-memory (ограничен RAM)"],
            }
        ]

    def _score_search_options(
        self, requirements: Dict, constraints: Dict
    ) -> List[Dict]:
        """Scoring опций для поиска"""
        return [
            {
                "option": "Elasticsearch",
                "score": 8.5,
                "reason": "Полнотекстовый поиск и аналитика",
                "pros": ["Мощный поиск", "Аналитика", "Масштабируемость"],
                "cons": ["Ресурсоемкий", "Сложность"],
            }
        ]

    def _recommend_architecture_pattern(self, requirements: Dict) -> str:
        """Рекомендация архитектурного паттерна"""
        scale = requirements.get("scale", "medium")
        integration_type = requirements.get("integration_type", "sync")

        if scale == "high" and integration_type == "event-driven":
            return "Event-Driven Microservices"
        elif scale == "medium" and integration_type == "async":
            return "Service-Oriented Architecture (SOA)"
        elif integration_type == "sync":
            return "Layered Monolith with REST APIs"
        else:
            return "Hybrid Architecture"

    def _estimate_total_cost(self, recommendations: Dict) -> str:
        """Оценка общей стоимости"""
        # Упрощенная оценка
        cost_map = {"low": 1, "medium": 2, "high": 3}

        total = 0
        count = 0
        for tech in recommendations.values():
            # TODO: Get cost from tech catalog
            total += 2
            count += 1

        avg = total / count if count > 0 else 2

        if avg < 1.5:
            return "Low"
        elif avg < 2.5:
            return "Medium"
        else:
            return "High"

    def _estimate_complexity(self, recommendations: Dict) -> str:
        """Оценка сложности внедрения"""
        # TODO: More sophisticated calculation
        if len(recommendations) > 4:
            return "High"
        elif len(recommendations) > 2:
            return "Medium"
        else:
            return "Low"

    def _generate_migration_plan(self, recommendations: Dict) -> List[Dict]:
        """Генерация плана миграции"""
        plan = []

        for i, (category, tech) in enumerate(recommendations.items(), 1):
            plan.append(
                {
                    "phase": i,
                    "component": category,
                    "technology": tech["option"],
                    "duration": "1-2 weeks",
                    "tasks": [
                        f"Установка и настройка {tech['option']}",
                        "Интеграция с 1С",
                        "Тестирование",
                    ],
                }
            )

        return plan

    def _assess_technology_risks(self, recommendations: Dict) -> List[Dict]:
        """Оценка рисков выбранных технологий"""
        risks = []

        for category, tech in recommendations.items():
            if "сложность" in tech.get("cons", []):
                risks.append(
                    {
                        "technology": tech["option"],
                        "risk": "High operational complexity",
                        "mitigation": "Обучение команды, привлечение экспертов",
                        "probability": 0.6,
                        "impact": 0.7,
                    }
                )

        return risks

    def _generate_alternatives(self, recommendations: Dict) -> Dict[str, List[str]]:
        """Генерация альтернативных вариантов"""
        alternatives = {}

        for category, tech in recommendations.items():
            # TODO: Generate real alternatives from catalog
            alternatives[category] = [tech["option"]]

        return alternatives


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        selector = TechnologySelector()

        requirements = {
            "scale": "high",
            "availability": 0.999,
            "performance": "< 2s",
            "load": "10000 requests/day",
            "integration_type": "event-driven",
        }

        constraints = {
            "budget": "medium",
            "team_skills": ["BSL", "Python", "PostgreSQL"],
            "existing_tech": ["1С:ERP", "PostgreSQL"],
            "deployment": "on-premise",
        }

        result = await selector.recommend_technology_stack(requirements, constraints)

        print("=== Recommended Stack ===")
        for category, tech in result["recommended_stack"].items():
            print(f"{category}: {tech['option']} (score: {tech['score']})")

        print(f"\nArchitecture Pattern: {result['architecture_pattern']}")
        print(f"Estimated Cost: {result['estimated_cost']}")
        print(f"Complexity: {result['implementation_complexity']}")

    asyncio.run(test())
