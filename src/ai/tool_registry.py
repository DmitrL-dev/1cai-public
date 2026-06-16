
"""
Tool / Skill Registry (experimental)
------------------------------------

Экспериментальный слой описания инструментов/skills, независимый
от конкретного протокола (HTTP, MCP, CLI).

Цели:
- Задать единый контракт для инструментов (имя, схема, риск, стоимость).
- Дать Orchestrator и Scenario Hub источник правдивых данных о том,
  что умеет платформа, какие есть ограничения и SLO.
- Подготовить базу для semantic index использования tools/skills.

На данном этапе модуль не подключён к FastAPI/MCP и используется
как reference-слой типов.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.ai.scenario_hub import ScenarioRiskLevel


class ToolProtocol(str, Enum):
    """Поддерживаемые протоколы/транспорты для инструментов."""

    HTTP = "http"
    MCP = "mcp"
    CLI = "cli"
    SCRIPT = "script"


class ToolCategory(str, Enum):
    """Категория инструмента / skill."""

    ANALYSIS = "analysis"
    BA = "ba"
    DEV = "dev"
    QA = "qa"
    DEVOPS = "devops"
    DR = "dr"
    SECURITY = "security"
    OTHER = "other"


@dataclass
class ToolEndpoint:
    """
    Описание конкретной точки вызова инструмента.

    Примеры:
    - HTTP: метод + URL, ожидаемые коды ответа.
    - MCP: имя tool и сервер.
    - CLI/script: путь до скрипта и аргументы.
    """

    protocol: ToolProtocol
    name: str
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDescriptor:
    """
    Описание инструмента/skill в реестре.

    Здесь не хранится реализация, только метаданные и контракт.
    """

    id: str
    display_name: str
    category: ToolCategory
    risk: ScenarioRiskLevel
    description: str
    # JSON Schema / pydantic-схема аргументов/результата (упрощённо: произвольный dict)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    # Привязки к конкретным протоколам/транспортам
    endpoints: List[ToolEndpoint] = field(default_factory=list)
    # SLO / SLI / cost-модель (latency, tokens, денежная стоимость)
    cost_model: Dict[str, Any] = field(default_factory=dict)
    # Связанные сценарии/плейбуки
    tags: List[str] = field(default_factory=list)
    # Документация/ссылки (README, guides, ADR)
    docs: Dict[str, str] = field(default_factory=dict)


@dataclass
class ToolUsageExample:
    """
    Пример использования инструмента, который можно индексировать семантически.
    """

    tool_id: str
    title: str
    description: str
    input_example: Dict[str, Any]
    output_example: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    Простейшая in-memory реализация реестра инструментов.

    В будущем можно заменить на хранение в БД (PostgreSQL/Neo4j)
    и поверх него построить semantic index.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDescriptor] = {}
        self._usage_examples: List[ToolUsageExample] = []

    def register_tool(self, descriptor: ToolDescriptor) -> None:
        """Зарегистрировать/обновить инструмент в реестре."""
        self._tools[descriptor.id] = descriptor

    def get_tool(self, tool_id: str) -> Optional[ToolDescriptor]:
        """Получить описание инструмента по id."""
        return self._tools.get(tool_id)

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        risk: Optional[ScenarioRiskLevel] = None,
    ) -> List[ToolDescriptor]:
        """
        Вернуть список инструментов, опционально отфильтрованных по категории/риску.
        """
        result = list(self._tools.values())
        if category is not None:
            result = [t for t in result if t.category == category]
        if risk is not None:
            result = [t for t in result if t.risk == risk]
        return result

    def add_usage_example(self, example: ToolUsageExample) -> None:
        """Добавить пример использования инструмента."""
        self._usage_examples.append(example)

    def list_usage_examples(
        self, tool_id: Optional[str] = None
    ) -> List[ToolUsageExample]:
        """Вернуть usage-примеры (опционально только для конкретного инструмента)."""
        if tool_id is None:
            return list(self._usage_examples)
        return [e for e in self._usage_examples if e.tool_id == tool_id]
