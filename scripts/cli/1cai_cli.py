
#!/usr/bin/env python3
"""
1C AI Stack CLI - Унифицированный CLI инструмент для работы с платформой
------------------------------------------------------------------------

Предоставляет удобный интерфейс для разработчиков для работы с:
- AI Orchestrator
- Scenario Hub
- Unified Change Graph
- Кэш и метрики
- Быстрая проверка статуса системы
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Добавить корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    print("Warning: httpx not available. Install with: pip install httpx")


class OneCAICLI:
    """Главный класс CLI инструмента."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Args:
            base_url: Базовый URL API сервера
        """
        self.base_url = base_url
        self.client = None
        if HTTPX_AVAILABLE:
            self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def query(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Отправить запрос в AI Orchestrator.

        Args:
            text: Текст запроса
            context: Опциональный контекст

        Returns:
            Ответ от Orchestrator
        """
        if not self.client:
            return {"error": "httpx not available"}

        try:
            response = await self.client.post(
                "/api/ai/query",
                params={"query": text},
                json=context or {},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def list_scenarios(self, autonomy: Optional[str] = None) -> Dict[str, Any]:
        """
        Получить список доступных сценариев.

        Args:
            autonomy: Опциональный уровень автономности

        Returns:
            Список сценариев
        """
        if not self.client:
            return {"error": "httpx not available"}

        try:
            params = {}
            if autonomy:
                params["autonomy"] = autonomy

            response = await self.client.get(
                "/api/scenarios/examples",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def recommend_scenarios(
        self, query: str, max_recommendations: int = 5
    ) -> Dict[str, Any]:
        """
        Получить рекомендации сценариев на основе запроса.

        Args:
            query: Запрос пользователя
            max_recommendations: Максимальное количество рекомендаций

        Returns:
            Рекомендации сценариев
        """
        if not self.client:
            return {"error": "httpx not available"}

        try:
            response = await self.client.post(
                "/api/scenarios/recommend",
                json={
                    "query": query,
                    "max_recommendations": max_recommendations,
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def analyze_impact(
        self, node_ids: List[str], max_depth: int = 3, include_tests: bool = True
    ) -> Dict[str, Any]:
        """
        Проанализировать влияние изменений в узлах графа.

        Args:
            node_ids: Список ID узлов графа
            max_depth: Максимальная глубина поиска зависимостей
            include_tests: Включать тесты в анализ

        Returns:
            Отчёт о влиянии изменений
        """
        if not self.client:
            return {"error": "httpx not available"}

        try:
            response = await self.client.post(
                "/api/graph/impact",
                json={
                    "node_ids": node_ids,
                    "max_depth": max_depth,
                    "include_tests": include_tests,
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def list_llm_providers(self) -> Dict[str, Any]:
        """
        Получить список всех доступных LLM провайдеров.

        Returns:
            Список провайдеров
        """
        if not self.client:
            return {"error": "httpx not available"}

        try:
            response = await self.client.get("/api/llm/providers")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def select_llm_provider(
        self,
        query_type: str,
        max_cost: Optional[float] = None,
        max_latency_ms: Optional[int] = None,
        required_compliance: Optional[List[str]] = None,
        preferred_risk_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Выбрать подходящий LLM провайдер на основе критериев.

        Args:
            query_type: Тип запроса
            max_cost: Максимальная стоимость
            max_latency_ms: Максимальная latency
            required_compliance: Требуемое соответствие
            preferred_risk_level: Предпочтительный уровень риска

        Returns:
            Выбранный провайдер
        """
        if not self.client:
            return {"error": "httpx not available"}

        try:
            payload = {"query_type": query_type}
            if max_cost is not None:
                payload["max_cost"] = max_cost
            if max_latency_ms is not None:
                payload["max_latency_ms"] = max_latency_ms
            if required_compliance:
                payload["required_compliance"] = required_compliance
            if preferred_risk_level:
                payload["preferred_risk_level"] = preferred_risk_level

            response = await self.client.post(
                "/api/llm/select-provider",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def get_cache_metrics(self) -> Dict[str, Any]:
        """
        Получить метрики кэша.

        Returns:
            Метрики кэша
        """
        if not self.client:
            return {"error": "httpx not available"}

        try:
            response = await self.client.get("/api/cache/metrics")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def invalidate_cache(
        self,
        tags: Optional[List[str]] = None,
        query_type: Optional[str] = None,
        clear_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Инвалидировать записи в кэше.

        Args:
            tags: Теги для инвалидации
            query_type: Тип запроса для инвалидации
            clear_all: Очистить весь кэш

        Returns:
            Результат инвалидации
        """
        if not self.client:
            return {"error": "httpx not available"}

        try:
            payload = {"clear_all": clear_all}
            if tags:
                payload["tags"] = tags
            if query_type:
                payload["query_type"] = query_type

            response = await self.client.post(
                "/api/cache/invalidate",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def health_check(self) -> Dict[str, Any]:
        """
        Проверить статус системы.

        Returns:
            Статус системы
        """
        if not self.client:
            return {"error": "httpx not available", "status": "unavailable"}

        try:
            # Попробовать несколько endpoints для проверки
            endpoints = {
                "orchestrator": "/api/ai/query",
                "scenarios": "/api/scenarios/examples",
                "cache": "/api/cache/metrics",
            }

            status = {"status": "healthy", "endpoints": {}}

            for name, endpoint in endpoints.items():
                try:
                    if name == "orchestrator":
                        # Для query нужен параметр, используем простой запрос
                        response = await self.client.post(
                            endpoint,
                            params={"query": "health check"},
                            json={},
                            timeout=5.0,
                        )
                    else:
                        response = await self.client.get(endpoint, timeout=5.0)

                    status["endpoints"][name] = {
                        "status": "ok" if response.status_code == 200 else "error",
                        "status_code": response.status_code,
                    }
                except Exception as e:
                    status["endpoints"][name] = {
                        "status": "error",
                        "error": str(e),
                    }

            # Определить общий статус
            all_ok = all(
                ep.get("status") == "ok" for ep in status["endpoints"].values()
            )
            if not all_ok:
                status["status"] = "degraded"

            return status
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


def format_output(data: Dict[str, Any], format: str = "json") -> str:
    """
    Форматировать вывод данных.

    Args:
        data: Данные для вывода
        format: Формат вывода (json, table, yaml)

    Returns:
        Отформатированная строка
    """
    if format == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)
    elif format == "table":
        # Простое табличное представление для некоторых типов данных
        if "scenarios" in data:
            scenarios = data["scenarios"]
            lines = ["Scenarios:", ""]
            for i, scenario in enumerate(scenarios, 1):
                lines.append(f"{i}. {scenario.get('goal', 'N/A')}")
            return "\n".join(lines)
        elif "providers" in data:
            providers = data["providers"]
            lines = ["LLM Providers:", ""]
            for provider in providers:
                lines.append(
                    f"- {provider.get('provider_id', 'N/A')}/{provider.get('model_name', 'N/A')}"
                )
            return "\n".join(lines)
        else:
            return json.dumps(data, indent=2, ensure_ascii=False)
    else:
        return json.dumps(data, indent=2, ensure_ascii=False)


async def main():
    """Главная функция CLI."""
    parser = argparse.ArgumentParser(
        description="1C AI Stack CLI - Унифицированный CLI инструмент для работы с платформой",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Базовый URL API сервера (по умолчанию: http://localhost:8000)",
    )

    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="json",
        help="Формат вывода (по умолчанию: json)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Команда query
    query_parser = subparsers.add_parser("query", help="Отправить запрос в AI Orchestrator")
    query_parser.add_argument("text", help="Текст запроса")

    # Команда scenarios
    scenarios_parser = subparsers.add_parser(
        "scenarios", help="Получить список доступных сценариев"
    )
    scenarios_parser.add_argument(
        "--autonomy",
        help="Уровень автономности (A0_propose_only, A1_safe_automation, etc.)",
    )

    # Команда recommend
    recommend_parser = subparsers.add_parser(
        "recommend", help="Получить рекомендации сценариев"
    )
    recommend_parser.add_argument("query", help="Запрос для рекомендаций")
    recommend_parser.add_argument(
        "--max", type=int, default=5, help="Максимальное количество рекомендаций"
    )

    # Команда impact
    impact_parser = subparsers.add_parser(
        "impact", help="Проанализировать влияние изменений в узлах графа"
    )
    impact_parser.add_argument("node_ids", nargs="+", help="ID узлов графа")
    impact_parser.add_argument(
        "--max-depth", type=int, default=3, help="Максимальная глубина поиска"
    )
    impact_parser.add_argument(
        "--no-tests", action="store_true", help="Не включать тесты в анализ"
    )

    # Команда llm-providers
    llm_parser = subparsers.add_parser(
        "llm-providers", help="Работа с LLM провайдерами"
    )
    llm_subparsers = llm_parser.add_subparsers(dest="llm_command", help="LLM команды")

    llm_list_parser = llm_subparsers.add_parser("list", help="Список провайдеров")
    llm_select_parser = llm_subparsers.add_parser("select", help="Выбрать провайдера")
    llm_select_parser.add_argument("query_type", help="Тип запроса")
    llm_select_parser.add_argument("--max-cost", type=float, help="Максимальная стоимость")
    llm_select_parser.add_argument(
        "--max-latency", type=int, help="Максимальная latency (мс)"
    )
    llm_select_parser.add_argument(
        "--compliance", nargs="+", help="Требуемое соответствие (152-ФЗ, GDPR, etc.)"
    )
    llm_select_parser.add_argument(
        "--risk-level", help="Предпочтительный уровень риска (low, medium, high)"
    )

    # Команда cache
    cache_parser = subparsers.add_parser("cache", help="Работа с кэшем")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache команды")

    cache_metrics_parser = cache_subparsers.add_parser("metrics", help="Метрики кэша")
    cache_invalidate_parser = cache_subparsers.add_parser(
        "invalidate", help="Инвалидировать кэш"
    )
    cache_invalidate_parser.add_argument("--tags", nargs="+", help="Теги для инвалидации")
    cache_invalidate_parser.add_argument(
        "--query-type", help="Тип запроса для инвалидации"
    )
    cache_invalidate_parser.add_argument(
        "--clear-all", action="store_true", help="Очистить весь кэш"
    )

    # Команда health
    health_parser = subparsers.add_parser("health", help="Проверить статус системы")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    async with OneCAICLI(base_url=args.base_url) as cli:
        result: Dict[str, Any] = {}

        if args.command == "query":
            result = await cli.query(args.text)
        elif args.command == "scenarios":
            result = await cli.list_scenarios(autonomy=args.autonomy)
        elif args.command == "recommend":
            result = await cli.recommend_scenarios(args.query, max_recommendations=args.max)
        elif args.command == "impact":
            result = await cli.analyze_impact(
                args.node_ids,
                max_depth=args.max_depth,
                include_tests=not args.no_tests,
            )
        elif args.command == "llm-providers":
            if args.llm_command == "list":
                result = await cli.list_llm_providers()
            elif args.llm_command == "select":
                result = await cli.select_llm_provider(
                    args.query_type,
                    max_cost=args.max_cost,
                    max_latency_ms=args.max_latency_ms,
                    required_compliance=args.compliance,
                    preferred_risk_level=args.risk_level,
                )
            else:
                llm_parser.print_help()
                return
        elif args.command == "cache":
            if args.cache_command == "metrics":
                result = await cli.get_cache_metrics()
            elif args.cache_command == "invalidate":
                result = await cli.invalidate_cache(
                    tags=args.tags,
                    query_type=args.query_type,
                    clear_all=args.clear_all,
                )
            else:
                cache_parser.print_help()
                return
        elif args.command == "health":
            result = await cli.health_check()
        else:
            parser.print_help()
            return

        print(format_output(result, format=args.format))


if __name__ == "__main__":
    asyncio.run(main())

