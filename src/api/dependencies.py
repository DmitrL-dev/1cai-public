"""Dependency providers for legacy GraphService-backed integrations.

The current Rentgen core is SQLite/local-file based, but the optional ArchiMate
bridge still uses the older Neo4j GraphService. These providers keep that
bridge injectable without making it part of the core application health.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from fastapi import Depends

from src.utils.structured_logging import StructuredLogger

try:
    from src.db.neo4j_client import Neo4jClient, get_neo4j_client
except ImportError:
    Neo4jClient = None  # type: ignore
    get_neo4j_client = None  # type: ignore

if TYPE_CHECKING:
    from src.exporters.archi_exporter import ArchiExporter
    from src.exporters.archi_importer import ArchiImporter
    from src.modules.graph_api.services.graph_service import GraphService


logger = StructuredLogger(__name__).logger

_graph_service: Optional["GraphService"] = None


def get_graph_service(
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
) -> "GraphService":
    """Get or create the optional Neo4j GraphService."""

    from src.modules.graph_api.services.graph_service import GraphService

    global _graph_service

    if _graph_service is None:
        _graph_service = GraphService(neo4j_client)

    return _graph_service


def get_archi_exporter(
    graph_service: "GraphService" = Depends(get_graph_service),
) -> "ArchiExporter":
    """Get an ArchiMate exporter with the legacy GraphService injected."""

    from src.exporters.archi_exporter import ArchiExporter

    return ArchiExporter(graph_service)


def get_archi_importer(
    graph_service: "GraphService" = Depends(get_graph_service),
) -> "ArchiImporter":
    """Get an ArchiMate importer with the legacy GraphService injected."""

    from src.exporters.archi_importer import ArchiImporter

    return ArchiImporter(graph_service)
