"""
Embedding Service Facade
Redirects to the refactored implementation in src/services/embedding/
"""

from src.services.embedding.service import EmbeddingService

# Re-export for backward compatibility
__all__ = ["EmbeddingService"]
