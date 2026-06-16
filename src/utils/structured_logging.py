
"""
Compatibility layer for structured logging.
Redirects to src.infrastructure.logging.structured_logging to avoid duplication.
"""

from src.infrastructure.logging.structured_logging import (
    StructuredLogger,
    get_or_create_request_id,
    set_request_context,
    get_request_context,
    LogContext,
)

# Re-export for compatibility
__all__ = [
    "StructuredLogger",
    "get_or_create_request_id",
    "set_request_context",
    "get_request_context",
    "LogContext",
]
