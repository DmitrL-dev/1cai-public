"""
Compatibility layer for structured logging.
Redirects to src.infrastructure.logging.structured_logging to avoid duplication.
"""

from src.infrastructure.logging.structured_logging import (
    LogContext,
    StructuredLogger,
    get_or_create_request_id,
    get_request_context,
    set_request_context,
)

# Re-export for compatibility
__all__ = [
    "StructuredLogger",
    "get_or_create_request_id",
    "set_request_context",
    "get_request_context",
    "LogContext",
]
