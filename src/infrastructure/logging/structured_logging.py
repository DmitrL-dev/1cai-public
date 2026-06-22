"""
Structured Logging Setup with Context Propagation
Best Practices:
- JSON structured logging for ELK/Splunk
- Context propagation using contextvars (async-safe)
- Correlation IDs for request tracking
- Integration with OpenTelemetry traces
"""

import logging
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Dict, Optional

from pythonjsonlogger import jsonlogger

from src.config import settings


class StructuredLogger:
    """
    Structured logging with correlation IDs

    Logs in JSON format for easy parsing in ELK/Splunk
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.setup_json_logging()

    def setup_json_logging(self):
        """
        Setup JSON formatter with best practices

        Features:
        - JSON format for easy parsing
        - Automatic context injection
        - Configurable log level
        - File rotation support
        """
        import logging.handlers

        if self.logger.handlers:
            return

        log_level_name = settings.log_level.upper()
        handler_level = getattr(logging, log_level_name, logging.INFO)

        formatter = jsonlogger.JsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s %(request_id)s %(user_id)s %(tenant_id)s",
            timestamp=True,
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(handler_level)
        self.logger.addHandler(console_handler)

        log_dir = settings.log_dir
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, "app.json.log")
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(handler_level)
            self.logger.addHandler(file_handler)
        except (PermissionError, OSError) as e:
            # Fallback for Windows file locking issues
            sys.stderr.write(f"WARNING: Could not open log file {log_file}: {e}\n")
            sys.stderr.write("Logging to console only.\n")

        self.logger.setLevel(logging.DEBUG)

    def log(
        self,
        level: str,
        message: str,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **extra,
    ):
        """
        Log with structured context

        Best practice: Automatically injects context from contextvars if not provided
        """
        # Get context from contextvars if not provided
        ctx = get_request_context()
        if not request_id:
            request_id = ctx.get("request_id")
        if not user_id:
            user_id = ctx.get("user_id")
        if not tenant_id:
            tenant_id = ctx.get("tenant_id")

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": request_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            **extra,
        }

        # Remove None values and reserved keys (message is reserved by LogRecord)
        reserved_keys = {
            "message",
            "msg",
            "args",
            "exc_info",
            "exc_text",
            "stack_info",
            "stacklevel",
            "module",
            "filename",
            "funcName",
            "lineno",
            "pathname",
            "process",
            "processName",
            "thread",
            "threadName",
            "name",
            "levelname",
            "levelno",
            "created",
            "msecs",
            "relativeCreated",
        }
        log_data = {
            k: v
            for k, v in log_data.items()
            if v is not None and k not in reserved_keys
        }

        log_func = getattr(self.logger, level.lower())
        log_func(message, extra=log_data)

    def info(self, message: str, **kwargs):
        self.log("info", message, **kwargs)

    def warning(self, message: str, **kwargs):
        self.log("warning", message, **kwargs)

    def error(self, message: str, **kwargs):
        self.log("error", message, **kwargs)

    def debug(self, message: str, **kwargs):
        self.log("debug", message, **kwargs)


# Correlation ID middleware helper
def get_or_create_request_id(request) -> str:
    """Get or create correlation ID for request"""

    # Try to get from header (propagated from client)
    request_id = request.headers.get("X-Request-ID")

    if not request_id:
        # Generate new
        import uuid

        request_id = str(uuid.uuid4())

    return request_id


# Context variables for async-safe context propagation
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
_tenant_id: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
):
    """
    Set request context for structured logging

    Best practice: Call this at the start of each request
    """
    if request_id:
        _request_id.set(request_id)
    if user_id:
        _user_id.set(user_id)
    if tenant_id:
        _tenant_id.set(tenant_id)


def get_request_context() -> Dict[str, Optional[str]]:
    """Get current request context"""
    return {
        "request_id": _request_id.get(),
        "user_id": _user_id.get(),
        "tenant_id": _tenant_id.get(),
    }


# Context manager for correlation
class LogContext:
    """
    Context manager for adding correlation data to logs

    Best practice: Use contextvars for async-safe context propagation
    """

    def __init__(
        self,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        self.request_id = request_id or str(uuid.uuid4())
        self.user_id = user_id
        self.tenant_id = tenant_id
        self._old_request_id = None
        self._old_user_id = None
        self._old_tenant_id = None

    def __enter__(self):
        # Save old values
        self._old_request_id = _request_id.get()
        self._old_user_id = _user_id.get()
        self._old_tenant_id = _tenant_id.get()

        # Set new values
        _request_id.set(self.request_id)
        if self.user_id:
            _user_id.set(self.user_id)
        if self.tenant_id:
            _tenant_id.set(self.tenant_id)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old values
        if self._old_request_id:
            _request_id.set(self._old_request_id)
        else:
            _request_id.set(None)

        if self._old_user_id:
            _user_id.set(self._old_user_id)
        else:
            _user_id.set(None)

        if self._old_tenant_id:
            _tenant_id.set(self._old_tenant_id)
        else:
            _tenant_id.set(None)
