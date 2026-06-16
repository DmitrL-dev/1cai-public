"""Рентген MCP Tools — call graph analysis tools for IDE integration.

Exposes Рентген capabilities as MCP tools that can be called from
Cursor, Claude Desktop, or any MCP-compatible IDE.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tool definitions for MCP list_tools
RENTGEN_TOOLS = [
    {
        "name": "rentgen_build_graph",
        "description": "Parse a 1C configuration directory and build call graph in Neo4j. "
        "Input: config_path (string) - path to unpacked 1C configuration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to unpacked 1C configuration directory (XML + BSL files)",
                }
            },
            "required": ["config_path"],
        },
    },
    {
        "name": "rentgen_execution_flow",
        "description": "Trace execution flow from an entry point through the entire call chain. "
        "Shows what functions are called when a specific handler runs "
        "(e.g. ОбработкаПроведения, ПередЗаписью). "
        "Input: entry_point (string), max_depth (int, default 10).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_point": {
                    "type": "string",
                    "description": "Function/procedure name to trace (e.g. ОбработкаПроведения)",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum call chain depth (default: 10)",
                    "default": 10,
                },
            },
            "required": ["entry_point"],
        },
    },
    {
        "name": "rentgen_impact_analysis",
        "description": "Reverse call graph analysis: find all callers of a function. "
        "Answers: 'If I change this function, what will break?' "
        "Input: target (string) - function name, max_depth (int, default 5).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target function name to analyze impact for",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum reverse traversal depth (default: 5)",
                    "default": 5,
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "rentgen_subscriptions",
        "description": "Get all event subscriptions that fire for a metadata type. "
        "Shows which handlers intercept events like ПередЗаписью, ПриЗаписи. "
        "Input: metadata_type (string, e.g. 'Документ.РеализацияТоваров').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "metadata_type": {
                    "type": "string",
                    "description": "Metadata type name (e.g. Документ.РеализацияТоваров)",
                }
            },
            "required": ["metadata_type"],
        },
    },
    {
        "name": "rentgen_queries_in_flow",
        "description": "Get all database queries executed in a call chain. "
        "Combines Рентген (call graph) with Перформер (query analysis). "
        "Input: entry_point (string), max_depth (int, default 10).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_point": {
                    "type": "string",
                    "description": "Entry point function name",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum call chain depth (default: 10)",
                    "default": 10,
                },
            },
            "required": ["entry_point"],
        },
    },
    {
        "name": "performer_analyze_tj",
        "description": "Analyze 1C Technology Journal logs for performance bottlenecks. "
        "Finds slow queries, N+1 patterns, lock waits, and deadlocks. "
        "Correlates each issue with specific BSL source code location. "
        "Input: log_path (string), min_duration_ms (float, default 100).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_path": {
                    "type": "string",
                    "description": "Path to Technology Journal log directory",
                },
                "min_duration_ms": {
                    "type": "number",
                    "description": "Minimum query duration to report (ms, default: 100)",
                    "default": 100,
                },
            },
            "required": ["log_path"],
        },
    },
]


async def handle_rentgen_tool(name: str, arguments: dict[str, Any]) -> str:
    """Handle Рентген/Перформер MCP tool calls.

    Returns JSON string with results.
    """
    try:
        if name == "rentgen_build_graph":
            return await _build_graph(arguments["config_path"])
        elif name == "rentgen_execution_flow":
            return await _execution_flow(
                arguments["entry_point"],
                arguments.get("max_depth", 10),
            )
        elif name == "rentgen_impact_analysis":
            return await _impact_analysis(
                arguments["target"],
                arguments.get("max_depth", 5),
            )
        elif name == "rentgen_subscriptions":
            return await _subscriptions(arguments["metadata_type"])
        elif name == "rentgen_queries_in_flow":
            return await _queries_in_flow(
                arguments["entry_point"],
                arguments.get("max_depth", 10),
            )
        elif name == "performer_analyze_tj":
            return await _analyze_tj(
                arguments["log_path"],
                arguments.get("min_duration_ms", 100),
            )
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        logger.error("Рентген tool error: %s — %s", name, e)
        return json.dumps({"error": str(e)})


async def _build_graph(config_path: str) -> str:
    from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder
    from src.db.neo4j_client import get_neo4j_client
    from src.modules.graph_api.services.graph_service import GraphService

    builder = OneCCodeGraphBuilder(config_path=config_path)
    builder.parse_all()
    client = get_neo4j_client()
    service = GraphService(client)
    stats = builder.build_graph(service)
    return json.dumps(stats, ensure_ascii=False)


async def _execution_flow(entry_point: str, max_depth: int) -> str:
    from src.db.neo4j_client import get_neo4j_client
    from src.modules.graph_api.services.graph_service import GraphService

    client = get_neo4j_client()
    service = GraphService(client)
    edges = service.get_execution_flow(entry_point, max_depth)
    return json.dumps(
        {
            "entry_point": entry_point,
            "edges": edges,
            "total": len(edges),
        },
        ensure_ascii=False,
    )


async def _impact_analysis(target: str, max_depth: int) -> str:
    from src.db.neo4j_client import get_neo4j_client
    from src.modules.graph_api.services.graph_service import GraphService

    client = get_neo4j_client()
    service = GraphService(client)
    callers = service.get_impact_analysis(target, max_depth)
    return json.dumps(
        {
            "target": target,
            "callers": callers,
            "total": len(callers),
        },
        ensure_ascii=False,
    )


async def _subscriptions(metadata_type: str) -> str:
    from src.db.neo4j_client import get_neo4j_client
    from src.modules.graph_api.services.graph_service import GraphService

    client = get_neo4j_client()
    service = GraphService(client)
    subs = service.get_subscriptions_for(metadata_type)
    return json.dumps(subs, ensure_ascii=False)


async def _queries_in_flow(entry_point: str, max_depth: int) -> str:
    from src.db.neo4j_client import get_neo4j_client
    from src.modules.graph_api.services.graph_service import GraphService

    client = get_neo4j_client()
    service = GraphService(client)
    queries = service.get_queries_in_flow(entry_point, max_depth)
    return json.dumps(
        {
            "entry_point": entry_point,
            "queries": queries,
            "total": len(queries),
        },
        ensure_ascii=False,
    )


async def _analyze_tj(log_path: str, min_duration_ms: float) -> str:
    from src.services.tj_parser.analyzer import TJPerformanceAnalyzer

    analyzer = TJPerformanceAnalyzer(min_duration_ms=min_duration_ms)
    report = analyzer.analyze(log_path)
    return json.dumps(
        {
            "total_events": report.total_events,
            "total_duration_ms": report.total_duration_ms,
            "hotspots": [
                {
                    "module": h.module,
                    "line": h.line,
                    "code_fragment": h.code_fragment,
                    "total_calls": h.total_calls,
                    "total_duration_ms": h.total_duration_ms,
                    "is_in_loop": h.is_in_loop,
                }
                for h in report.hotspots[:10]
            ],
            "n_plus_one_count": len(report.n_plus_one),
            "lock_waits": len(report.lock_waits),
            "deadlocks": len(report.deadlocks),
        },
        ensure_ascii=False,
    )
