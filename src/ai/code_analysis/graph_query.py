
"""
Graph Query Helper для Orchestrator
-----------------------------------

Вспомогательный класс для поиска узлов в Unified Change Graph
по ключевым словам и контексту запроса.

Используется Orchestrator для:
- Построения graph_nodes_touched на основе запроса
- Подсказок по релевантным сценариям
- Impact-анализа
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

from src.ai.code_analysis.graph import CodeGraphBackend, Node, NodeKind

logger = logging.getLogger(__name__)


class GraphQueryHelper:
    """
    Помощник для поиска узлов в Unified Change Graph по запросу.

    Извлекает ключевые слова из запроса и ищет соответствующие узлы
    в графе (модули, функции, процедуры, сервисы, тесты и т.п.).
    """

    def __init__(self, backend: Optional[CodeGraphBackend] = None) -> None:
        """
        Args:
            backend: Backend графа (опционально, можно установить позже)
        """
        self.backend = backend
        # Кэш для результатов поиска (опционально, для производительности)
        self._cache: Dict[str, List[Node]] = {}

    def set_backend(self, backend: CodeGraphBackend) -> None:
        """Установить backend графа."""
        self.backend = backend

    async def find_nodes_by_query(
        self,
        query: str,
        *,
        max_results: int = 10,
        node_kinds: Optional[List[NodeKind]] = None,
    ) -> List[Node]:
        """
        Найти узлы графа по ключевым словам из запроса.

        Args:
            query: Текст запроса пользователя
            max_results: Максимальное количество результатов
            node_kinds: Фильтр по типам узлов (опционально)

        Returns:
            Список найденных узлов, отсортированных по релевантности
        """
        if not self.backend:
            logger.debug("Graph backend not available, returning empty results")
            return []

        # Извлечь ключевые слова из запроса
        keywords = self._extract_keywords(query)

        if not keywords:
            return []

        # Поиск узлов по ключевым словам
        found_nodes: List[Node] = []

        for keyword in keywords:
            # Поиск по display_name
            nodes_by_name = await self._search_by_display_name(keyword, node_kinds)
            found_nodes.extend(nodes_by_name)

            # Поиск по labels
            nodes_by_label = await self._search_by_label(keyword, node_kinds)
            found_nodes.extend(nodes_by_label)

            # Поиск по props (например, имя функции, путь модуля)
            nodes_by_props = await self._search_by_props(keyword, node_kinds)
            found_nodes.extend(nodes_by_props)

        # Удалить дубликаты и отсортировать по релевантности
        unique_nodes = self._deduplicate_and_rank(found_nodes, keywords)
        return unique_nodes[:max_results]

    async def find_related_scenarios(
        self,
        node_ids: List[str],
        *,
        max_scenarios: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Найти релевантные сценарии на основе узлов графа.

        Args:
            node_ids: Список ID узлов графа
            max_scenarios: Максимальное количество сценариев

        Returns:
            Список релевантных сценариев с метаданными
        """
        if not self.backend:
            return []

        # Простая эвристика: если запрос касается модулей/функций → BA→Dev→QA
        # Если запрос касается инфраструктуры/алертов → DR rehearsal
        # Если запрос касается кода/тестов → Code Review

        scenarios: List[Dict[str, Any]] = []

        # Проверяем типы узлов
        module_count = 0
        function_count = 0
        service_count = 0
        alert_count = 0
        test_count = 0

        for node_id in node_ids:
            node = await self.backend.get_node(node_id)
            if not node:
                continue

            if node.kind == NodeKind.MODULE:
                module_count += 1
            elif node.kind == NodeKind.FUNCTION:
                function_count += 1
            elif node.kind == NodeKind.SERVICE:
                service_count += 1
            elif node.kind == NodeKind.ALERT:
                alert_count += 1
            elif node.kind in (NodeKind.TEST_CASE, NodeKind.TEST_SUITE):
                test_count += 1

        # Рекомендации на основе типов узлов
        if module_count > 0 or function_count > 0:
            scenarios.append(
                {
                    "id": "ba-dev-qa",
                    "name": "BA→Dev→QA Flow",
                    "relevance": "high" if module_count > 0 else "medium",
                    "reason": f"Запрос касается {module_count} модулей и {function_count} функций",
                }
            )

        if test_count > 0:
            scenarios.append(
                {
                    "id": "code-review",
                    "name": "Code Review",
                    "relevance": "high",
                    "reason": f"Запрос касается {test_count} тестов",
                }
            )

        if service_count > 0 or alert_count > 0:
            scenarios.append(
                {
                    "id": "dr-rehearsal",
                    "name": "DR Rehearsal",
                    "relevance": "medium",
                    "reason": f"Запрос касается {service_count} сервисов и {alert_count} алертов",
                }
            )

        return scenarios[:max_scenarios]

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Извлечь ключевые слова из запроса.

        Удаляет стоп-слова и нормализует слова.
        """
        # Простые стоп-слова (можно расширить)
        stop_words = {
            "как",
            "что",
            "где",
            "когда",
            "кто",
            "почему",
            "зачем",
            "для",
            "из",
            "в",
            "на",
            "с",
            "по",
            "от",
            "до",
            "и",
            "или",
            "а",
            "но",
            "если",
            "то",
            "это",
            "такой",
            "такая",
            "такое",
            "такие",
            "мой",
            "моя",
            "моё",
            "мои",
            "наш",
            "наша",
            "наше",
            "наши",
        }

        # Нормализация: убрать пунктуацию, привести к нижнему регистру
        normalized = re.sub(r"[^\w\s]", " ", query.lower())
        words = normalized.split()

        # Фильтровать стоп-слова и короткие слова
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords

    async def _search_by_display_name(
        self,
        keyword: str,
        node_kinds: Optional[List[NodeKind]],
    ) -> List[Node]:
        """Поиск узлов по display_name."""
        if not self.backend:
            return []

        # Поиск всех узлов (или фильтр по kinds)
        if node_kinds:
            all_nodes: List[Node] = []
            for kind in node_kinds:
                nodes = await self.backend.find_nodes(kind=kind)
                all_nodes.extend(nodes)
        else:
            # Поиск без фильтра по kind (нужен метод find_all или итерация)
            # Для простоты используем известные kinds
            all_nodes: List[Node] = []
            for kind in [
                NodeKind.MODULE,
                NodeKind.FUNCTION,
                NodeKind.SERVICE,
                NodeKind.FILE,
                NodeKind.TEST_CASE,
                NodeKind.TEST_SUITE,
            ]:
                nodes = await self.backend.find_nodes(kind=kind)
                all_nodes.extend(nodes)

        # Фильтровать по ключевому слову в display_name
        keyword_lower = keyword.lower()
        matched = [
            node for node in all_nodes if keyword_lower in node.display_name.lower()
        ]

        return matched

    async def _search_by_label(
        self,
        keyword: str,
        node_kinds: Optional[List[NodeKind]],
    ) -> List[Node]:
        """Поиск узлов по labels."""
        if not self.backend:
            return []

        # Поиск по label
        nodes = await self.backend.find_nodes(
            label=keyword, kind=node_kinds[0] if node_kinds else None
        )
        return nodes

    async def _search_by_props(
        self,
        keyword: str,
        node_kinds: Optional[List[NodeKind]],
    ) -> List[Node]:
        """Поиск узлов по свойствам (например, имя функции, путь модуля)."""
        if not self.backend:
            return []

        # Поиск по props (например, name, path)
        keyword_lower = keyword.lower()

        # Собираем все узлы
        if node_kinds:
            all_nodes: List[Node] = []
            for kind in node_kinds:
                nodes = await self.backend.find_nodes(kind=kind)
                all_nodes.extend(nodes)
        else:
            all_nodes: List[Node] = []
            for kind in [
                NodeKind.MODULE,
                NodeKind.FUNCTION,
                NodeKind.SERVICE,
            ]:
                nodes = await self.backend.find_nodes(kind=kind)
                all_nodes.extend(nodes)

        # Фильтровать по props
        matched = []
        for node in all_nodes:
            # Проверяем props на наличие ключевого слова
            for prop_value in node.props.values():
                if isinstance(prop_value, str) and keyword_lower in prop_value.lower():
                    matched.append(node)
                    break
                elif isinstance(prop_value, list):
                    for item in prop_value:
                        if isinstance(item, str) and keyword_lower in item.lower():
                            matched.append(node)
                            break

        return matched

    def _deduplicate_and_rank(
        self,
        nodes: List[Node],
        keywords: List[str],
    ) -> List[Node]:
        """
        Удалить дубликаты и отсортировать узлы по релевантности.

        Релевантность определяется количеством совпадений ключевых слов.
        """
        # Удалить дубликаты по ID
        seen: Set[str] = set()
        unique_nodes: List[Node] = []
        for node in nodes:
            if node.id not in seen:
                seen.add(node.id)
                unique_nodes.append(node)

        # Подсчитать релевантность (количество совпадений ключевых слов)
        def score(node: Node) -> int:
            score_value = 0
            node_text = f"{node.display_name} {' '.join(node.labels)}".lower()
            for keyword in keywords:
                if keyword.lower() in node_text:
                    score_value += 1
            return score_value

        # Сортировать по релевантности (убывание)
        unique_nodes.sort(key=score, reverse=True)

        return unique_nodes
