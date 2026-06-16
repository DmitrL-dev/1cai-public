"""Модуль dependencies.

TODO: Добавить подробное описание модуля.

Этот docstring был автоматически сгенегирован.
Пожалуйста, обновите его с правильным описанием.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from fastapi import Depends

try:
    from src.db.neo4j_client import Neo4jClient, get_neo4j_client
except ImportError:
    Neo4jClient = None  # type: ignore
    get_neo4j_client = None  # type: ignore

if TYPE_CHECKING:
    from src.exporters.archi_exporter import ArchiExporter
    from src.modules.graph_api.services.graph_service import GraphService


from src.utils.structured_logging import StructuredLogger


logger = StructuredLogger(__name__).logger

# Global instances for dependency injection
_graph_service: Optional["GraphService"] = None


def get_graph_service(
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
) -> "GraphService":
    """Get or create GraphService instance"""
    # Lazy import to avoid circular dependency
    from src.modules.graph_api.services.graph_service import GraphService

    global _graph_service

    if _graph_service is None:
        _graph_service = GraphService(neo4j_client)

    return _graph_service


def get_archi_exporter(
    graph_service: "GraphService" = Depends(get_graph_service),
) -> "ArchiExporter":
    """Get ArchiExporter with injected GraphService"""
    # Lazy import to avoid circular dependency
    from src.exporters.archi_exporter import ArchiExporter

    return ArchiExporter(graph_service)


def get_archi_importer(
    graph_service=Depends(get_graph_service),
):
    """Get ArchiImporter instance"""
    # Lazy import to avoid circular dependency
    from src.exporters.archi_importer import ArchiImporter

    return ArchiImporter(graph_service)
