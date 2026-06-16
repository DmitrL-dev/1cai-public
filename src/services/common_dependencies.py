"""
Common dependencies for the application.
Moved here to avoid circular dependencies between API and Modules.
"""

from typing import Optional

from src.db.postgres_saver import PostgreSQLSaver

try:
    from src.db.qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None  # type: ignore
from src.services.embedding_service import EmbeddingService
from src.services.service_container import ServiceContainer


def get_qdrant_client() -> QdrantClient:
    """Get QdrantClient instance."""
    return QdrantClient()


def get_postgres_client() -> Optional[PostgreSQLSaver]:
    """Get PostgreSQLSaver instance."""
    return ServiceContainer.get_postgres()


def get_embedding_service() -> Optional[EmbeddingService]:
    """Get EmbeddingService instance."""
    return ServiceContainer.get_embedding()
