
"""
Unified Change Graph Builder for 1C Code
-----------------------------------------

Интегратор для построения Unified Change Graph из реального кода 1С (BSL модули).

Использует существующие BSL парсеры для извлечения структуры и автоматически
строит граф узлов (модули, функции, процедуры, переменные) и рёбер (зависимости,
вызовы, использование).

Это ключевая фича для "де-факто" стандарта: автоматическое построение графа
изменений из кода 1С без ручной настройки.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Set

from src.ai.code_analysis.graph import CodeGraphBackend, Edge, EdgeKind, Node, NodeKind

logger = logging.getLogger(__name__)


class OneCCodeGraphBuilder:
    """
    Построитель Unified Change Graph из кода 1С.

    Использует BSL парсеры для извлечения структуры и автоматически создаёт
    узлы и рёбра в Unified Change Graph.
    """

    def __init__(
        self,
        backend: CodeGraphBackend,
        *,
        use_ast_parser: bool = True,
    ) -> None:
        """
        Args:
            backend: Backend для хранения графа (InMemoryCodeGraphBackend, Neo4jCodeGraphBackend и др.)
            use_ast_parser: Использовать продвинутый AST парсер (если доступен)
        """
        self.backend = backend
        self.use_ast_parser = use_ast_parser
        self._parser = None
        self._module_cache: Dict[str, Dict[str, Any]] = {}

    def _get_parser(self):
        """Ленивая инициализация парсера."""
        if self._parser is None:
            if self.use_ast_parser:
                try:
                    from scripts.parsers.bsl_ast_parser import BSLASTParser

                    self._parser = BSLASTParser(use_language_server=True)
                    logger.info("Using AST parser with language server")
                except Exception as e:
                    logger.warning(
                        "AST parser unavailable, falling back to simple parser: %s", e
                    )
                    self.use_ast_parser = False

            if not self.use_ast_parser:
                from src.ai.agents.code_review.bsl_parser import BSLParser

                self._parser = BSLParser()
                logger.info("Using simple regex-based BSL parser")

        return self._parser

    async def build_from_module(
        self,
        module_path: str,
        module_code: str,
        *,
        module_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Построить граф из одного BSL модуля.

        Args:
            module_path: Путь к модулю (например, "ОбщийМодуль.УправлениеЗаказами")
            module_code: Содержимое модуля (BSL код)
            module_metadata: Дополнительные метаданные (owner, repo, environment и т.п.)

        Returns:
            Статистика построения: {nodes_created, edges_created, functions, procedures}
        """
        logger.info("Building graph from module: %s", module_path)

        parser = self._get_parser()
        parsed = parser.parse(module_code)

        # Кэшируем результат парсинга
        self._module_cache[module_path] = parsed

        # Метаданные модуля
        metadata = module_metadata or {}
        metadata.setdefault("path", module_path)
        metadata.setdefault("loc", parsed.get("loc", len(module_code.split("\n"))))
        metadata.setdefault("complexity", parsed.get("total_complexity", 0))

        # 1. Создать узел модуля
        module_node_id = f"module:{module_path}"
        module_node = Node(
            id=module_node_id,
            kind=NodeKind.MODULE,
            display_name=f"Module: {module_path}",
            labels=["bsl", "1c", "module"],
            props=metadata,
        )
        await self.backend.upsert_node(module_node)

        nodes_created = 1
        edges_created = 0

        # 2. Создать узлы функций
        functions = parsed.get("functions", [])
        function_nodes: Dict[str, Node] = {}
        for func in functions:
            func_name = func.get("name", "Unknown")
            func_node_id = f"function:{module_path}:{func_name}"
            func_node = Node(
                id=func_node_id,
                kind=NodeKind.FUNCTION,
                display_name=f"Function: {func_name}",
                labels=["bsl", "1c", "function"],
                props={
                    "module": module_path,
                    "name": func_name,
                    "exported": func.get("is_export", False)
                    or func.get("exported", False),
                    "parameters": func.get("parameters", []),
                    "complexity": func.get("complexity", 0),
                    "start_line": func.get("start_line") or func.get("line_start"),
                    "end_line": func.get("end_line") or func.get("line_end"),
                    "has_documentation": func.get("has_documentation", False),
                },
            )
            await self.backend.upsert_node(func_node)
            function_nodes[func_name] = func_node
            nodes_created += 1

            # Связь: функция принадлежит модулю (используем OWNS, но можно использовать BSL_HAS_MODULE для модулей объектов)
            edge = Edge(
                source=module_node_id,
                target=func_node_id,
                kind=EdgeKind.OWNS,
                props={"relationship": "function_in_module"},
            )
            await self.backend.upsert_edge(edge)
            edges_created += 1

        # 3. Создать узлы процедур
        procedures = parsed.get("procedures", [])
        procedure_nodes: Dict[str, Node] = {}
        for proc in procedures:
            proc_name = proc.get("name", "Unknown")
            proc_node_id = f"procedure:{module_path}:{proc_name}"
            proc_node = Node(
                id=proc_node_id,
                kind=NodeKind.FUNCTION,  # Используем FUNCTION для процедур тоже
                display_name=f"Procedure: {proc_name}",
                labels=["bsl", "1c", "procedure"],
                props={
                    "module": module_path,
                    "name": proc_name,
                    "exported": proc.get("is_export", False)
                    or proc.get("exported", False),
                    "parameters": proc.get("parameters", []),
                    "complexity": proc.get("complexity", 0),
                    "start_line": proc.get("start_line") or proc.get("line_start"),
                    "end_line": proc.get("end_line") or proc.get("line_end"),
                    "has_documentation": proc.get("has_documentation", False),
                },
            )
            await self.backend.upsert_node(proc_node)
            procedure_nodes[proc_name] = proc_node
            nodes_created += 1

            # Связь: процедура принадлежит модулю
            edge = Edge(
                source=proc_node_id,
                target=module_node_id,
                kind=EdgeKind.OWNS,
                props={"relationship": "procedure_in_module"},
            )
            await self.backend.upsert_edge(edge)
            edges_created += 1

        # 4. Извлечь зависимости (вызовы функций/процедур) из тел функций/процедур
        all_callables = {**function_nodes, **procedure_nodes}
        for callable_name, callable_node in all_callables.items():
            # Найти тело функции/процедуры
            callable_data = next(
                (f for f in functions + procedures if f.get("name") == callable_name),
                None,
            )
            if not callable_data:
                continue

            body = callable_data.get("body", "")
            if not body:
                continue

            # Извлечь вызовы функций/процедур из тела
            called_functions = self._extract_function_calls(body)
            for called_name in called_functions:
                # Ищем в текущем модуле
                if called_name in all_callables:
                    target_node = all_callables[called_name]
                    # Используем BSL_CALLS для более специфичной связи вызова функции
                    edge = Edge(
                        source=callable_node.id,
                        target=target_node.id,
                        kind=EdgeKind.BSL_CALLS,
                        props={
                            "relationship": "calls",
                            "call_type": "internal",
                            "line": callable_data.get("start_line"),
                        },
                    )
                    await self.backend.upsert_edge(edge)
                    edges_created += 1
                else:
                    # Внешний вызов - создаём узел-заглушку или ищем в других модулях
                    external_node_id = f"function:external:{called_name}"
                    # Проверяем, существует ли уже такой узел
                    existing = await self.backend.get_node(external_node_id)
                    if not existing:
                        external_node = Node(
                            id=external_node_id,
                            kind=NodeKind.FUNCTION,
                            display_name=f"External: {called_name}",
                            labels=["bsl", "1c", "function", "external"],
                            props={"name": called_name, "resolved": False},
                        )
                        await self.backend.upsert_node(external_node)
                        nodes_created += 1
                    else:
                        external_node = existing

                    # Используем BSL_CALLS для внешних вызовов
                    edge = Edge(
                        source=callable_node.id,
                        target=external_node_id,
                        kind=EdgeKind.BSL_CALLS,
                        props={
                            "relationship": "calls",
                            "call_type": "external",
                            "dynamic": True,
                            "line": callable_data.get("start_line"),
                        },
                    )
                    await self.backend.upsert_edge(edge)
                    edges_created += 1

        # 5. Извлечь использование переменных и запросов
        variables = parsed.get("variables", [])
        queries = parsed.get("queries", [])

        # Создать узлы для запросов (используем BSL_QUERY для SQL-запросов)
        for query in queries:
            query_text = query.get("text", "")
            if not query_text:
                continue

            # Создать узел запроса
            query_hash = hash(query_text) % (10**8)  # Простой hash для уникальности
            query_node_id = f"bsl_query:{module_path}:{query_hash}"
            query_type = query.get("type", "SELECT")

            query_node = Node(
                id=query_node_id,
                kind=NodeKind.BSL_QUERY,
                display_name=f"SQL-запрос: {query_type}",
                labels=["bsl", "1c", "query"],
                props={
                    "query_text": query_text,
                    "query_type": query_type,
                    "module": module_path,
                    "line": query.get("line"),
                },
            )
            await self.backend.upsert_node(query_node)
            nodes_created += 1

            # Связь: модуль выполняет запрос
            edge = Edge(
                source=module_node_id,
                target=query_node_id,
                kind=EdgeKind.BSL_EXECUTES_QUERY,
                props={"line": query.get("line")},
            )
            await self.backend.upsert_edge(edge)
            edges_created += 1

            # Извлечь имена таблиц из запроса
            tables = self._extract_table_names_from_query(query_text)
            for table_name in tables:
                table_node_id = f"db_table:1c:{table_name}"
                existing = await self.backend.get_node(table_node_id)
                if not existing:
                    table_node = Node(
                        id=table_node_id,
                        kind=NodeKind.DB_TABLE,
                        display_name=f"Table: {table_name}",
                        labels=["bsl", "1c", "database", "table"],
                        props={"name": table_name, "source": "query_analysis"},
                    )
                    await self.backend.upsert_node(table_node)
                    nodes_created += 1

                # Связь: запрос читает/пишет таблицу
                if query_type == "SELECT":
                    edge_kind = EdgeKind.BSL_READS_TABLE
                    operation = "read"
                else:
                    edge_kind = EdgeKind.BSL_WRITES_TABLE
                    operation = "write"

                edge = Edge(
                    source=query_node_id,
                    target=table_node_id,
                    kind=edge_kind,
                    props={"operation": operation, "query_type": query_type},
                )
                await self.backend.upsert_edge(edge)
                edges_created += 1

        return {
            "nodes_created": nodes_created,
            "edges_created": edges_created,
            "functions": len(functions),
            "procedures": len(procedures),
            "variables": len(variables),
            "queries": len(queries),
            "module_path": module_path,
        }

    def _extract_function_calls(self, code: str) -> Set[str]:
        """
        Извлечь имена вызываемых функций/процедур из кода.

        Упрощённый подход: ищем паттерны вызовов в BSL.
        """
        calls: Set[str] = set()

        # Паттерн: ИмяФункции( или ИмяПроцедуры(
        # Также учитываем вызовы через точку: Объект.Метод(
        pattern = r"(\w+)\s*\("
        matches = re.finditer(pattern, code)

        for match in matches:
            name = match.group(1)
            # Пропускаем ключевые слова BSL
            if name.lower() in {
                "если",
                "иначе",
                "иначеесли",
                "для",
                "пока",
                "попытка",
                "исключение",
                "вызватьисключение",
                "возврат",
                "продолжить",
                "прервать",
                "новый",
                "создатьобъект",
                "найти",
                "найтизначения",
            }:
                continue

            # Пропускаем стандартные функции 1С (можно расширить список)
            if (
                name.startswith("Строка")
                or name.startswith("Число")
                or name.startswith("Дата")
            ):
                continue

            calls.add(name)

        return calls

    def _extract_table_names_from_query(self, query_text: str) -> Set[str]:
        """
        Извлечь имена таблиц из текста запроса 1С.

        Упрощённый подход: ищем паттерны ИЗ, JOIN в запросе.
        """
        tables: Set[str] = set()

        # Паттерн: ИЗ ИмяТаблицы или JOIN ИмяТаблицы
        # Также: ИЗ Справочник.Номенклатура
        pattern = r"(?:ИЗ|FROM|JOIN)\s+([\w.]+)"
        matches = re.finditer(pattern, query_text, re.IGNORECASE)

        for match in matches:
            table_name = match.group(1).strip()
            if table_name:
                tables.add(table_name)

        return tables

    async def build_from_directory(
        self,
        directory_path: str,
        *,
        pattern: str = "*.bsl",
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """
        Построить граф из всех BSL файлов в директории.

        Args:
            directory_path: Путь к директории с BSL файлами
            pattern: Паттерн поиска файлов (по умолчанию "*.bsl")
            recursive: Рекурсивный поиск

        Returns:
            Общая статистика: {total_modules, total_nodes, total_edges, modules: [...]}
        """
        logger.info("Building graph from directory: %s", directory_path)

        path = Path(directory_path)
        if not path.exists():
            raise ValueError(f"Directory does not exist: {directory_path}")

        if recursive:
            bsl_files = list(path.rglob(pattern))
        else:
            bsl_files = list(path.glob(pattern))

        total_stats = {
            "total_modules": 0,
            "total_nodes": 0,
            "total_edges": 0,
            "modules": [],
        }

        for bsl_file in bsl_files:
            try:
                module_code = bsl_file.read_text(encoding="utf-8")
                module_path = str(bsl_file.relative_to(path))

                stats = await self.build_from_module(
                    module_path,
                    module_code,
                    module_metadata={
                        "file_path": str(bsl_file),
                        "owner": "unknown",
                    },
                )

                total_stats["total_modules"] += 1
                total_stats["total_nodes"] += stats["nodes_created"]
                total_stats["total_edges"] += stats["edges_created"]
                total_stats["modules"].append(stats)

            except Exception as e:
                logger.error(
                    "Failed to process file %s: %s", bsl_file, e, exc_info=True
                )

        logger.info(
            "Graph building completed: %d modules, %d nodes, %d edges",
            total_stats["total_modules"],
            total_stats["total_nodes"],
            total_stats["total_edges"],
        )

        return total_stats

    async def build_from_xml(
        self,
        xml_path: str,
        *,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """
        Построить граф из XML выгрузки конфигурации 1С.
        
        Args:
            xml_path: Путь к файлу или директории с XML.
            recursive: Рекурсивный поиск (для директорий).
        """
        logger.info("Building graph from XML: %s", xml_path)
        
        from src.ai.code_analysis.parsers.xml_parser import OneCXMLParser
        parser = OneCXMLParser()
        
        nodes = []
        if Path(xml_path).is_dir():
            nodes = parser.parse_directory(xml_path)
        else:
            nodes = parser.parse_file(xml_path)
            
        logger.info("Parsed %d nodes from XML", len(nodes))
        
        nodes_created = 0
        for node in nodes:
            await self.backend.upsert_node(node)
            nodes_created += 1
            
        # Create relationships (e.g., Subsystem -> Content)
        edges_created = 0
        
        # Index nodes by name for fast lookup (assuming unique names for top-level objects)
        # In reality, we might need type+name, but XML content usually has "Type.Name" format
        node_map = {}
        for node in nodes:
            # Map "Catalog.Goods" -> Node
            # Also map "Goods" -> Node (if unique)
            
            # Construct full name based on kind
            type_prefix = ""
            if node.kind == NodeKind.BSL_CATALOG: type_prefix = "Catalog"
            elif node.kind == NodeKind.BSL_DOCUMENT: type_prefix = "Document"
            elif node.kind == NodeKind.BSL_REPORT: type_prefix = "Report"
            elif node.kind == NodeKind.BSL_DATA_PROCESSOR: type_prefix = "DataProcessor"
            elif node.kind == NodeKind.BSL_REGISTER_INFORMATION: type_prefix = "InformationRegister"
            elif node.kind == NodeKind.BSL_REGISTER_ACCUMULATION: type_prefix = "AccumulationRegister"
            # ... add others as needed
            
            if type_prefix:
                full_name = f"{type_prefix}.{node.display_name}"
                node_map[full_name] = node
            
            node_map[node.display_name] = node

        for node in nodes:
            if node.kind == NodeKind.BSL_SUBSYSTEM:
                content = node.props.get("Content", [])
                for item in content:
                    # item is usually "Catalog.Goods" or "Document.Order"
                    target_node = node_map.get(item)
                    if target_node:
                        edge = Edge(
                            source=node.id,
                            target=target_node.id,
                            kind=EdgeKind.OWNS, # Subsystem owns/contains the object
                            props={"relationship": "subsystem_content"}
                        )
                        await self.backend.upsert_edge(edge)
                        edges_created += 1
        
        return {
            "nodes_created": nodes_created,
            "edges_created": edges_created,
            "xml_path": xml_path
        }

    async def export_graph(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Экспортировать граф в JSON формат (совместимый с CODE_GRAPH_SCHEMA.json).

        Args:
            output_path: Путь для сохранения JSON (опционально)

        Returns:
            Словарь с nodes и edges в формате Unified Change Graph
        """
        # Для InMemoryCodeGraphBackend можно напрямую экспортировать
        # Для других бэкендов нужна реализация через find_nodes
        if hasattr(self.backend, "_nodes") and hasattr(self.backend, "_edges"):
            # InMemoryCodeGraphBackend
            nodes = list(self.backend._nodes.values())
            edges = self.backend._edges
        else:
            # Для других бэкендов собираем все узлы и рёбра
            # Это упрощённая версия - в реальности нужен более сложный обход
            nodes = await self.backend.find_nodes()
            edges = []  # TODO: реализовать получение всех рёбер для других бэкендов

        graph_export = {
            "nodes": [
                {
                    "id": node.id,
                    "kind": node.kind.value,
                    "display_name": node.display_name,
                    "labels": node.labels,
                    "props": node.props,
                }
                for node in nodes
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "kind": edge.kind.value,
                    "props": edge.props,
                }
                for edge in edges
            ],
        }

        if output_path:
            import json

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(graph_export, f, ensure_ascii=False, indent=2)
            logger.info("Graph exported to: %s", output_path)

        return graph_export
