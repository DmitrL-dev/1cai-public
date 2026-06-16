
"""
Unified Change Graph (experimental)
-----------------------------------

Лёгкий каркас графа изменений (Unified Change Graph), поверх которого
можно строить impact‑анализ, трассировку требований и сценариев.

Цель модуля:
- дать общий программный интерфейс (Node/Edge/GraphBackend);
- скрыть конкретную реализацию хранилища (in‑memory, Neo4j, др.);
- обеспечить минимально полезные операции (upsert, поиск, зависимости).

Спецификация типов узлов/связей описана в `docs/architecture/CODE_GRAPH_REFERENCE.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


class NodeKind(str, Enum):
    """Типы узлов графа (см. CODE_GRAPH_REFERENCE.md и BSL_CODE_GRAPH_SPEC.md)."""

    # Базовые типы (Unified Change Graph)
    SERVICE = "service"
    MODULE = "module"
    FILE = "file"
    FUNCTION = "function"
    DB_TABLE = "db_table"
    DB_VIEW = "db_view"
    QUEUE = "queue"
    TOPIC = "topic"
    API_ENDPOINT = "api_endpoint"
    K8S_DEPLOYMENT = "k8s_deployment"
    K8S_SERVICE = "k8s_service"
    INGRESS = "ingress"
    JOB = "job"
    HELM_CHART = "helm_chart"
    ARGO_APP = "argo_app"
    TF_RESOURCE = "tf_resource"
    TEST_CASE = "test_case"
    TEST_SUITE = "test_suite"
    ALERT = "alert"
    SLO = "slo"
    INCIDENT = "incident"
    BA_REQUIREMENT = "ba_requirement"
    TICKET = "ticket"

    # BSL-Specific типы для 1C метаданных (BSL Code Graph Standard)
    # Объекты метаданных
    BSL_DOCUMENT = "bsl_document"
    BSL_CATALOG = "bsl_catalog"
    BSL_COMMON_MODULE = "bsl_common_module"
    BSL_REGISTER_INFORMATION = "bsl_register_information"
    BSL_REGISTER_ACCUMULATION = "bsl_register_accumulation"
    BSL_REGISTER_ACCOUNTING = "bsl_register_accounting"
    BSL_REGISTER_CALCULATION = "bsl_register_calculation"
    BSL_REPORT = "bsl_report"
    BSL_DATA_PROCESSOR = "bsl_data_processor"
    BSL_CHART_OF_ACCOUNTS = "bsl_chart_of_accounts"
    BSL_CHART_OF_CHARACTERISTIC_TYPES = "bsl_chart_of_characteristic_types"
    BSL_CHART_OF_CALCULATION_TYPES = "bsl_chart_of_calculation_types"
    BSL_BUSINESS_PROCESS = "bsl_business_process"
    BSL_TASK = "bsl_task"
    BSL_CONSTANT = "bsl_constant"
    BSL_ENUM = "bsl_enum"
    BSL_EXTERNAL_DATA_PROCESSOR = "bsl_external_data_processor"
    BSL_EXTERNAL_REPORT = "bsl_external_report"
    BSL_HTTP_SERVICE = "bsl_http_service"
    BSL_WS_REFERENCE = "bsl_ws_reference"
    BSL_EXCHANGE_PLAN = "bsl_exchange_plan"
    # Запросы и формы
    BSL_QUERY = "bsl_query"
    BSL_FORM = "bsl_form"
    BSL_COMMAND = "bsl_command"
    # Типы модулей в объектах 1C
    BSL_OBJECT_MODULE = "bsl_object_module"
    BSL_MANAGER_MODULE = "bsl_manager_module"
    BSL_FORM_MODULE = "bsl_form_module"
    BSL_COMMAND_MODULE = "bsl_command_module"

    # Additional 1C Metadata Types (Universal Parser Support)
    BSL_SUBSYSTEM = "bsl_subsystem"
    BSL_ROLE = "bsl_role"
    BSL_COMMON_TEMPLATE = "bsl_common_template"
    BSL_COMMON_PICTURE = "bsl_common_picture"
    BSL_COMMON_COMMAND = "bsl_common_command"
    BSL_COMMON_FORM = "bsl_common_form"
    BSL_FILTER_CRITERION = "bsl_filter_criterion"
    BSL_EVENT_SUBSCRIPTION = "bsl_event_subscription"
    BSL_SCHEDULED_JOB = "bsl_scheduled_job"
    BSL_SESSION_PARAMETER = "bsl_session_parameter"
    BSL_FUNCTIONAL_OPTION = "bsl_functional_option"
    BSL_SETTINGS_STORAGE = "bsl_settings_storage"
    BSL_STYLE_ITEM = "bsl_style_item"
    BSL_LANGUAGE = "bsl_language"
    BSL_WEB_SERVICE = "bsl_web_service"
    BSL_XDTO_PACKAGE = "bsl_xdto_package"
    BSL_METADATA_OBJECT = "bsl_metadata_object"  # Fallback for unknown types


class EdgeKind(str, Enum):
    """Типы связей между узлами (см. CODE_GRAPH_REFERENCE.md и BSL_CODE_GRAPH_SPEC.md)."""

    # Базовые типы (Unified Change Graph)
    DEPENDS_ON = "DEPENDS_ON"
    DEPLOYED_AS = "DEPLOYED_AS"
    EXPOSES = "EXPOSES"
    OWNS = "OWNS"
    TESTED_BY = "TESTED_BY"
    MONITORED_BY = "MONITORED_BY"
    IMPLEMENTS = "IMPLEMENTS"
    TRIGGERS_INCIDENT = "TRIGGERS_INCIDENT"
    PART_OF_SCENARIO = "PART_OF_SCENARIO"

    # BSL-Specific типы для 1C (BSL Code Graph Standard)
    # Вызовы и зависимости
    BSL_CALLS = (
        "BSL_CALLS"  # Вызов функции/процедуры (более специфичный чем DEPENDS_ON)
    )
    BSL_USES_METADATA = "BSL_USES_METADATA"  # Использование объекта метаданных в коде
    # Работа с БД
    BSL_READS_TABLE = "BSL_READS_TABLE"  # Чтение таблицы БД (SELECT)
    BSL_WRITES_TABLE = "BSL_WRITES_TABLE"  # Запись в таблицу БД (INSERT/UPDATE/DELETE)
    BSL_EXECUTES_QUERY = "BSL_EXECUTES_QUERY"  # Выполнение SQL-запроса
    # Структура объектов 1C
    BSL_HAS_MODULE = "BSL_HAS_MODULE"  # Объект метаданных имеет модуль
    BSL_HAS_FORM = "BSL_HAS_FORM"  # Объект имеет форму
    BSL_HAS_COMMAND = "BSL_HAS_COMMAND"  # Объект имеет команду
    # Связи между объектами
    BSL_EXTENDS = "BSL_EXTENDS"  # Наследование (объект расширяет другой объект)
    BSL_REFERENCES = "BSL_REFERENCES"  # Ссылка на другой объект
    BSL_SUBTYPE = "BSL_SUBTYPE"  # Подтип объекта (для объектов с иерархией)
    BSL_HAS_REGISTER = "BSL_HAS_REGISTER"  # Документ/обработка имеет регистр


@dataclass
class Node:
    """Узел графа изменений."""

    id: str
    kind: NodeKind
    display_name: str
    labels: List[str] = field(default_factory=list)
    props: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """Направленная связь между двумя узлами."""

    source: str
    target: str
    kind: EdgeKind
    props: Dict[str, Any] = field(default_factory=dict)


class CodeGraphBackend:
    """
    Абстрактный backend графа.

    Реальные реализации (in‑memory, Neo4j и др.) должны реализовать этот интерфейс.
    """

    async def upsert_node(self, node: Node) -> None:  # pragma: no cover - интерфейс
        """TODO: Описать функцию upsert_node.
        
        Args:
            node: TODO: Описать параметр.
        """
        raise NotImplementedError

    async def upsert_edge(self, edge: Edge) -> None:  # pragma: no cover - интерфейс
        """TODO: Описать функцию upsert_edge.
        
        Args:
            edge: TODO: Описать параметр.
        """
        raise NotImplementedError

    async def get_node(self, node_id: str) -> Optional[Node]:  # pragma: no cover
        """TODO: Описать функцию get_node.
        
        Args:
            node_id: TODO: Описать параметр.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        raise NotImplementedError

    async def neighbors(
        self, node_id: str, *, kinds: Optional[Iterable[EdgeKind]] = None
    ) -> List[Node]:  # pragma: no cover
        """TODO: Описать функцию neighbors.
        
        Args:
            node_id: TODO: Описать параметр.
            kinds: TODO: Описать параметр.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        raise NotImplementedError

    async def find_nodes(
        self,
        *,
        kind: Optional[NodeKind] = None,
        label: Optional[str] = None,
        prop_equals: Optional[Dict[str, Any]] = None,
    ) -> List[Node]:  # pragma: no cover
        """TODO: Описать функцию find_nodes.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        raise NotImplementedError


class InMemoryCodeGraphBackend(CodeGraphBackend):
    """
    Простая in‑memory реализация для тестов и локальных экспериментов.

    Не предназначен для продакшена, но позволяет:
    - писать unit‑тесты без внешних зависимостей;
    - прототипировать сценарии, опирающиеся на Unified Change Graph.
    """

    def __init__(self) -> None:
        """TODO: Описать функцию __init__."""
        self._nodes: Dict[str, Node] = {}
        self._edges: List[Edge] = []

    async def upsert_node(self, node: Node) -> None:
        """TODO: Описать функцию upsert_node.
        
        Args:
            node: TODO: Описать параметр.
        """
        self._nodes[node.id] = node

    async def upsert_edge(self, edge: Edge) -> None:
        """TODO: Описать функцию upsert_edge.
        
        Args:
            edge: TODO: Описать параметр.
        """
        if edge.source not in self._nodes or edge.target not in self._nodes:
            # В простом бэкенде тихо игнорируем связи к несуществующим узлам
            return
        self._edges.append(edge)

    async def get_node(self, node_id: str) -> Optional[Node]:
        """TODO: Описать функцию get_node.
        
        Args:
            node_id: TODO: Описать параметр.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        return self._nodes.get(node_id)

    async def neighbors(
        self, node_id: str, *, kinds: Optional[Iterable[EdgeKind]] = None
    ) -> List[Node]:
        """TODO: Описать функцию neighbors.
        
        Args:
            node_id: TODO: Описать параметр.
            kinds: TODO: Описать параметр.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        if kinds is not None:
            kinds_set = set(kinds)
            relevant = [
                e for e in self._edges if e.source == node_id and e.kind in kinds_set
            ]
        else:
            relevant = [e for e in self._edges if e.source == node_id]
        return [self._nodes[e.target] for e in relevant if e.target in self._nodes]

    async def find_nodes(
        self,
        *,
        kind: Optional[NodeKind] = None,
        label: Optional[str] = None,
        prop_equals: Optional[Dict[str, Any]] = None,
    ) -> List[Node]:
        """TODO: Описать функцию find_nodes.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        result: List[Node] = []
        for node in self._nodes.values():
            if kind is not None and node.kind != kind:
                continue
            if label is not None and label not in node.labels:
                continue
            if prop_equals:
                ok = True
                for k, v in prop_equals.items():
                    if node.props.get(k) != v:
                        ok = False
                        break
                if not ok:
                    continue
            result.append(node)
        return result
