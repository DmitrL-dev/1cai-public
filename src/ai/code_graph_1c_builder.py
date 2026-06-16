"""1C Configuration Code Graph Builder (Рентген).

Parses BSL modules and metadata to build a call graph in Neo4j.
Enables: execution flow tracing, impact analysis, performance bottleneck detection.

Architecture:
    Unpacked Configuration (XML + BSL)
        → parse_metadata()     → metadata objects, subscriptions, module properties
        → parse_bsl_modules()  → functions, procedures, call sites, queries
        → build_graph()        → Neo4j nodes + edges
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from src.parser.bsl_ast_visitor import ANTLR4_AVAILABLE, parse_bsl_source

logger = logging.getLogger(__name__)


@dataclass
class BslFunction:
    """Extracted BSL function/procedure."""

    name: str
    module: str
    line: int
    is_export: bool = False
    is_function: bool = True  # False = procedure
    complexity: int = 1
    calls: list[str] = field(default_factory=list)  # names of called functions
    queries: list[dict] = field(default_factory=list)  # {text, line}


@dataclass
class EventSubscription:
    """1C Event Subscription metadata."""

    name: str
    source_type: str  # e.g. "DocumentObject.*"
    event: str  # e.g. "ПередЗаписью"
    handler_module: str
    handler_method: str


@dataclass
class ConfigMetadata:
    """Parsed 1C configuration metadata."""

    documents: list[str] = field(default_factory=list)
    catalogs: list[str] = field(default_factory=list)
    common_modules: list[dict] = field(
        default_factory=list
    )  # {name, server, client, ...}
    subscriptions: list[EventSubscription] = field(default_factory=list)
    scheduled_jobs: list[dict] = field(default_factory=list)


class OneCCodeGraphBuilder:
    """Builds call graph from unpacked 1C configuration.

    Usage:
        builder = OneCCodeGraphBuilder(config_path="./unpacked_config")
        builder.parse_all()
        builder.build_graph(graph_service)

        # Or standalone (no Neo4j):
        builder.parse_all()
        functions = builder.functions  # all extracted functions
        calls = builder.get_all_calls()  # all call edges
    """

    # Regex patterns for BSL parsing
    RE_FUNC_START = re.compile(
        r"^\s*(Функция|Function|Процедура|Procedure)\s+"
        r"([А-Яа-яA-Za-z_]\w*)\s*\(([^)]*)\)\s*(Экспорт|Export)?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    RE_FUNC_END = re.compile(
        r"^\s*(КонецФункции|EndFunction|КонецПроцедуры|EndProcedure)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    RE_CALL = re.compile(
        r"([А-Яа-яA-Za-z_]\w*)\s*\(",
    )
    RE_MODULE_CALL = re.compile(
        r"([А-Яа-яA-Za-z_]\w*)\.([А-Яа-яA-Za-z_]\w*)\s*\(",
    )
    RE_QUERY = re.compile(
        r'(?:Запрос\.Текст|Query\.Text)\s*=\s*["\'](.+?)(?:["\'];|["\']$)',
        re.IGNORECASE | re.DOTALL,
    )
    RE_QUERY_MULTILINE = re.compile(
        r'(?:Запрос\.Текст|Query\.Text)\s*=\s*"([^"]*(?:""[^"]*)*)"',
        re.IGNORECASE,
    )
    RE_QUERY_TABLES = re.compile(
        r"(?:ИЗ|FROM|СОЕДИНЕНИЕ|JOIN)\s+([А-Яа-яA-Za-z_]\w*(?:\.[А-Яа-яA-Za-z_]\w*)*)",
        re.IGNORECASE,
    )
    # BSL keywords that are NOT function calls
    BSL_KEYWORDS = {
        "если",
        "тогда",
        "иначе",
        "иначеесли",
        "конецесли",
        "для",
        "каждого",
        "из",
        "по",
        "цикл",
        "конеццикла",
        "пока",
        "попытка",
        "исключение",
        "конецпопытки",
        "возврат",
        "продолжить",
        "прервать",
        "перейти",
        "новый",
        "не",
        "и",
        "или",
        "истина",
        "ложь",
        "if",
        "then",
        "else",
        "elsif",
        "endif",
        "for",
        "each",
        "in",
        "to",
        "do",
        "enddo",
        "while",
        "try",
        "except",
        "endtry",
        "return",
        "continue",
        "break",
        "goto",
        "new",
        "not",
        "and",
        "or",
        "true",
        "false",
        "процедура",
        "функция",
        "конецпроцедуры",
        "конецфункции",
        "procedure",
        "function",
        "endprocedure",
        "endfunction",
    }

    def __init__(self, config_path: str = "."):
        self.config_path = Path(config_path)
        self.metadata = ConfigMetadata()
        self.functions: list[BslFunction] = []
        self._modules_parsed = 0

    # === METADATA PARSING ===

    def parse_metadata(self) -> ConfigMetadata:
        """Parse 1C configuration metadata from XML files."""
        # Parse documents
        docs_dir = self.config_path / "Documents"
        if docs_dir.exists():
            for doc_dir in sorted(docs_dir.iterdir()):
                if doc_dir.is_dir():
                    self.metadata.documents.append(doc_dir.name)

        # Parse catalogs
        cats_dir = self.config_path / "Catalogs"
        if cats_dir.exists():
            for cat_dir in sorted(cats_dir.iterdir()):
                if cat_dir.is_dir():
                    self.metadata.catalogs.append(cat_dir.name)

        # Parse common modules
        cm_dir = self.config_path / "CommonModules"
        if cm_dir.exists():
            for mod_dir in sorted(cm_dir.iterdir()):
                if mod_dir.is_dir():
                    self.metadata.common_modules.append({"name": mod_dir.name})

        # Parse event subscriptions
        sub_dir = self.config_path / "EventSubscriptions"
        if sub_dir.exists():
            for xml_file in sorted(sub_dir.glob("*.xml")):
                sub = self._parse_subscription_xml(xml_file)
                if sub:
                    self.metadata.subscriptions.append(sub)

        logger.info(
            "Metadata: %d documents, %d catalogs, %d common modules, %d subscriptions",
            len(self.metadata.documents),
            len(self.metadata.catalogs),
            len(self.metadata.common_modules),
            len(self.metadata.subscriptions),
        )
        return self.metadata

    def _parse_subscription_xml(self, xml_path: Path) -> Optional[EventSubscription]:
        """Parse a single event subscription XML file."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            # Handle namespace
            ns = ""
            if root.tag.startswith("{"):
                ns = root.tag.split("}")[0] + "}"

            name = self._xml_text(root, f".//{ns}Name") or xml_path.stem
            source = self._xml_text(root, f".//{ns}Source//{ns}Type") or ""
            event = self._xml_text(root, f".//{ns}Event") or ""
            handler_module = (
                self._xml_text(root, f".//{ns}Handler//{ns}CommonModule") or ""
            )
            handler_method = self._xml_text(root, f".//{ns}Handler//{ns}Method") or ""

            if handler_module and handler_method:
                return EventSubscription(
                    name=name,
                    source_type=source,
                    event=event,
                    handler_module=handler_module,
                    handler_method=handler_method,
                )
        except ET.ParseError as e:
            logger.warning("Failed to parse subscription XML %s: %s", xml_path, e)
        return None

    @staticmethod
    def _xml_text(root, path: str) -> Optional[str]:
        el = root.find(path)
        return el.text.strip() if el is not None and el.text else None

    # === BSL MODULE PARSING ===

    def parse_bsl_modules(self) -> list[BslFunction]:
        """Parse all .bsl files in configuration directory."""
        bsl_files = sorted(self.config_path.rglob("*.bsl"))
        for bsl_path in bsl_files:
            module_name = self._module_name_from_path(bsl_path)
            self._parse_bsl_file(bsl_path, module_name)
        logger.info(
            "Parsed %d modules, found %d functions/procedures",
            self._modules_parsed,
            len(self.functions),
        )
        return self.functions

    def _module_name_from_path(self, path: Path) -> str:
        """Derive module name from file path."""
        rel = path.relative_to(self.config_path)
        parts = rel.parts
        # CommonModules/МойМодуль/Ext/Module.bsl → МойМодуль
        # Documents/МойДокумент/Ext/ObjectModule.bsl → МойДокумент.ObjectModule
        if len(parts) >= 2:
            obj_name = parts[1]  # metadata object name
            module_type = path.stem  # Module, ObjectModule, ManagerModule, etc.
            if module_type == "Module":
                return obj_name
            return f"{obj_name}.{module_type}"
        return path.stem

    def _parse_bsl_file(self, path: Path, module_name: str) -> None:
        """Parse a single BSL file for functions, calls, and queries.

        Uses ANTLR4 AST for accurate function/procedure boundary detection
        with automatic fallback to regex if ANTLR4 is unavailable or fails.
        Call extraction, query extraction, and complexity remain regex-based.
        """
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError) as e:
            logger.warning("Cannot read %s: %s", path, e)
            return

        self._modules_parsed += 1

        # Try ANTLR4 first, fall back to regex
        if ANTLR4_AVAILABLE:
            subroutines = parse_bsl_source(text)
            if subroutines is not None:
                self._process_antlr4_results(subroutines, module_name)
                return

        # Fallback: regex-based parsing
        self._parse_bsl_file_regex(text, module_name)

    def _process_antlr4_results(self, subroutines, module_name: str) -> None:
        """Convert ANTLR4 parse results into BslFunction entries."""
        for sub in subroutines:
            calls = self._extract_calls(sub.body_text)
            queries = self._extract_queries(sub.body_text, sub.line)
            complexity = self._estimate_complexity(sub.body_text)

            self.functions.append(
                BslFunction(
                    name=sub.name,
                    module=module_name,
                    line=sub.line,
                    is_export=sub.is_export,
                    is_function=sub.is_function,
                    complexity=complexity,
                    calls=calls,
                    queries=queries,
                )
            )

    def _parse_bsl_file_regex(self, text: str, module_name: str) -> None:
        """Regex-based BSL parsing (fallback when ANTLR4 unavailable)."""
        lines = text.split("\n")

        # Find all function/procedure boundaries
        func_ranges: list[
            tuple[str, int, int, bool, bool]
        ] = []  # name, start, end, is_export, is_function
        starts = list(self.RE_FUNC_START.finditer(text))
        ends = list(self.RE_FUNC_END.finditer(text))

        for i, m in enumerate(starts):
            keyword = m.group(1).lower()
            name = m.group(2)
            is_export = bool(m.group(4))
            is_function = keyword in ("функция", "function")
            start_line = text[: m.start()].count("\n") + 1

            # Find matching end
            end_line = len(lines)
            for e in ends:
                e_line = text[: e.start()].count("\n") + 1
                if e_line > start_line:
                    # Check this end isn't claimed by a closer start
                    if i + 1 < len(starts):
                        next_start_line = text[: starts[i + 1].start()].count("\n") + 1
                        if e_line > next_start_line:
                            continue
                    end_line = e_line
                    break

            func_ranges.append((name, start_line, end_line, is_export, is_function))

        # Parse each function body
        for name, start, end, is_export, is_func in func_ranges:
            body = "\n".join(lines[start : end - 1])  # exclude start/end lines
            calls = self._extract_calls(body)
            queries = self._extract_queries(body, start)
            complexity = self._estimate_complexity(body)

            self.functions.append(
                BslFunction(
                    name=name,
                    module=module_name,
                    line=start,
                    is_export=is_export,
                    is_function=is_func,
                    complexity=complexity,
                    calls=calls,
                    queries=queries,
                )
            )

    def _extract_calls(self, body: str) -> list[str]:
        """Extract function/procedure calls from body text."""
        calls = set()
        # Module.Method() calls
        for m in self.RE_MODULE_CALL.finditer(body):
            module = m.group(1)
            method = m.group(2)
            calls.add(f"{module}.{method}")
        # Direct calls
        for m in self.RE_CALL.finditer(body):
            name = m.group(1)
            if name.lower() not in self.BSL_KEYWORDS:
                calls.add(name)
        return sorted(calls)

    def _extract_queries(self, body: str, base_line: int) -> list[dict]:
        """Extract SQL/SDBL queries from body."""
        queries = []
        for m in self.RE_QUERY_MULTILINE.finditer(body):
            q_text = m.group(1).replace('""', '"')
            q_line = base_line + body[: m.start()].count("\n")
            tables = self.RE_QUERY_TABLES.findall(q_text)
            queries.append({"text": q_text, "line": q_line, "tables": tables})
        return queries

    @staticmethod
    def _estimate_complexity(body: str) -> int:
        """Simple cyclomatic complexity estimate."""
        keywords = re.findall(
            r"\b(Если|If|Для|For|Пока|While|ИначеЕсли|ElsIf|И|And|Или|Or)\b",
            body,
            re.IGNORECASE,
        )
        return 1 + len(keywords)

    # === GRAPH BUILDING ===

    def parse_all(self) -> None:
        """Parse everything: metadata + BSL modules."""
        self.parse_metadata()
        self.parse_bsl_modules()

    def build_graph(self, graph_service) -> dict:
        """Build Neo4j graph from parsed data.

        Args:
            graph_service: GraphService instance

        Returns:
            Stats dict with counts
        """
        graph_service.ensure_indexes()

        # Create module nodes
        modules_set = set()
        for func in self.functions:
            if func.module not in modules_set:
                modules_set.add(func.module)
                # Determine module type and metadata object
                parts = func.module.split(".")
                meta_obj = parts[0]
                mod_type = parts[1] if len(parts) > 1 else "Module"
                graph_service.upsert_module(
                    name=func.module,
                    module_type=mod_type,
                    metadata_object=meta_obj,
                    file_path="",
                    loc=0,
                )

        # Create function/procedure nodes
        for func in self.functions:
            if func.is_function:
                graph_service.upsert_function(
                    name=func.name,
                    module=func.module,
                    line=func.line,
                    is_export=func.is_export,
                    complexity=func.complexity,
                )
            else:
                graph_service.upsert_procedure(
                    name=func.name,
                    module=func.module,
                    line=func.line,
                    is_export=func.is_export,
                    complexity=func.complexity,
                )

        # Create call edges
        call_count = 0
        for func in self.functions:
            for call in func.calls:
                if "." in call:
                    # Module.Method call
                    parts = call.split(".", 1)
                    graph_service.add_call_edge(
                        func.name,
                        func.module,
                        parts[1],
                        parts[0],
                        func.line,
                    )
                else:
                    # Direct call (same module)
                    graph_service.add_call_edge(
                        func.name,
                        func.module,
                        call,
                        func.module,
                        func.line,
                    )
                call_count += 1

        # Create subscription nodes
        for sub in self.metadata.subscriptions:
            graph_service.add_subscription(
                name=sub.name,
                source_type=sub.source_type,
                event=sub.event,
                handler_module=sub.handler_module,
                handler_method=sub.handler_method,
            )

        # Create query nodes
        query_count = 0
        for func in self.functions:
            for q in func.queries:
                graph_service.add_query(
                    query_text=q["text"],
                    module=func.module,
                    function_name=func.name,
                    line=q["line"],
                    tables=q.get("tables", []),
                )
                query_count += 1

        stats = {
            "modules": len(modules_set),
            "functions": sum(1 for f in self.functions if f.is_function),
            "procedures": sum(1 for f in self.functions if not f.is_function),
            "calls": call_count,
            "subscriptions": len(self.metadata.subscriptions),
            "queries": query_count,
        }
        logger.info("Graph built: %s", stats)
        return stats

    def get_all_calls(self) -> list[dict]:
        """Get all call edges (standalone, no Neo4j needed)."""
        edges = []
        for func in self.functions:
            for call in func.calls:
                edges.append(
                    {
                        "caller": func.name,
                        "caller_module": func.module,
                        "callee": call,
                        "line": func.line,
                    }
                )
        return edges

    def to_json(self) -> str:
        """Export parsed data as JSON (for debugging/testing)."""
        import dataclasses

        return json.dumps(
            {
                "metadata": dataclasses.asdict(self.metadata),
                "functions": [dataclasses.asdict(f) for f in self.functions],
            },
            ensure_ascii=False,
            indent=2,
        )
