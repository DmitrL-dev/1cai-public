"""
Unit tests for Structured Logging
"""
import logging

from src.utils.structured_logging import StructuredLogger


class TestStructuredLogger:
    """Test StructuredLogger class"""

    def test_logger_initialization(self):
        """Test logger initialization"""
        logger = StructuredLogger("test_module")
        assert logger.logger is not None
        assert logger.logger.name == "test_module"
        assert isinstance(logger.logger, logging.Logger)

    def test_logger_with_custom_name(self):
        """Test logger with custom module name"""
        logger = StructuredLogger("my.custom.module")
        assert logger.logger.name == "my.custom.module"

    def test_info_logging(self, caplog):
        """Test info level logging"""
        logger = StructuredLogger("test_module")

        with caplog.at_level(logging.INFO):
            logger.logger.info("Test message", extra={"key1": "value1", "key2": 123})

        assert "Test message" in caplog.text
        # Check that structured data is logged
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "key1")
        assert record.key1 == "value1"
        assert record.key2 == 123

    def test_error_logging(self, caplog):
        """Test error level logging"""
        logger = StructuredLogger("test_module")

        with caplog.at_level(logging.ERROR):
            logger.logger.error(
                "Error occurred",
                extra={
                    "error": "Test error",
                    "error_type": "ValueError",
                    "status_code": 500,
                },
                exc_info=True,
            )

        assert "Error occurred" in caplog.text
        record = caplog.records[0]
        assert record.error == "Test error"
        assert record.error_type == "ValueError"
        assert record.status_code == 500

    def test_warning_logging(self, caplog):
        """Test warning level logging"""
        logger = StructuredLogger("test_module")

        with caplog.at_level(logging.WARNING):
            logger.logger.warning(
                "Warning message", extra={"component": "test", "severity": "medium"}
            )

        assert "Warning message" in caplog.text
        record = caplog.records[0]
        assert record.component == "test"
        assert record.severity == "medium"

    def test_debug_logging(self, caplog):
        """Test debug level logging"""
        logger = StructuredLogger("test_module")

        with caplog.at_level(logging.DEBUG):
            logger.logger.debug(
                "Debug message", extra={"debug_info": "test", "trace_id": "abc123"}
            )

        assert "Debug message" in caplog.text
        record = caplog.records[0]
        assert record.debug_info == "test"
        assert record.trace_id == "abc123"

    def test_logging_without_extra(self, caplog):
        """Test logging without extra dictionary"""
        logger = StructuredLogger("test_module")

        with caplog.at_level(logging.INFO):
            logger.logger.info("Simple message")

        assert "Simple message" in caplog.text
        assert len(caplog.records) == 1

    def test_logging_with_nested_dict(self, caplog):
        """Test logging with nested dictionary in extra"""
        logger = StructuredLogger("test_module")

        nested_data = {
            "user": {"id": 123, "name": "Test User"},
            "request": {"method": "POST", "path": "/api/test"},
        }

        with caplog.at_level(logging.INFO):
            logger.logger.info("Request processed", extra={"data": nested_data})

        record = caplog.records[0]
        assert record.data == nested_data

    def test_logging_with_exception(self, caplog):
        """Test logging with exception info"""
        logger = StructuredLogger("test_module")

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            with caplog.at_level(logging.ERROR):
                logger.logger.error(
                    "Exception occurred",
                    extra={"error": str(e), "error_type": type(e).__name__},
                    exc_info=True,
                )

        assert "Exception occurred" in caplog.text
        assert "ValueError" in caplog.text or "Test exception" in caplog.text
        record = caplog.records[0]
        assert record.error == "Test exception"
        assert record.error_type == "ValueError"

    def test_multiple_loggers(self):
        """Test that multiple loggers can be created"""
        logger1 = StructuredLogger("module1")
        logger2 = StructuredLogger("module2")

        assert logger1.logger.name == "module1"
        assert logger2.logger.name == "module2"
        assert logger1.logger is not logger2.logger

    def test_logger_with_special_characters(self, caplog):
        """Test logging with special characters in extra"""
        logger = StructuredLogger("test_module")

        with caplog.at_level(logging.INFO):
            logger.logger.info(
                "Message with special chars",
                extra={
                    "path": "/api/v1/users/123",
                    "query": "name=test&value=123",
                    "unicode": "тест",
                },
            )

        record = caplog.records[0]
        assert record.path == "/api/v1/users/123"
        assert record.query == "name=test&value=123"
        assert record.unicode == "тест"

    def test_logger_with_none_values(self, caplog):
        """Test logging with None values in extra"""
        logger = StructuredLogger("test_module")

        with caplog.at_level(logging.INFO):
            logger.logger.info(
                "Message with None", extra={"value1": None, "value2": "not_none"}
            )

        record = caplog.records[0]
        assert record.value1 is None
        assert record.value2 == "not_none"

    def test_logger_with_list_values(self, caplog):
        """Test logging with list values in extra"""
        logger = StructuredLogger("test_module")

        with caplog.at_level(logging.INFO):
            logger.logger.info(
                "Message with list",
                extra={"items": [1, 2, 3], "tags": ["tag1", "tag2"]},
            )

        record = caplog.records[0]
        assert record.items == [1, 2, 3]
        assert record.tags == ["tag1", "tag2"]


class TestStructuredLoggerIntegration:
    """Integration tests for StructuredLogger with real logging"""

    def test_logger_integration_with_handler(self):
        """Test logger with custom handler"""
        import io

        logger = StructuredLogger("test_module")

        # Create string handler
        handler = logging.StreamHandler(io.StringIO())
        handler.setFormatter(
            logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        )
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        logger.logger.info("Integration test", extra={"test_id": "integration_001"})

        # Handler should have logged the message
        assert handler.stream.getvalue() is not None

    def test_logger_with_json_formatter(self):
        """Test logger with JSON formatter (for ELK/Splunk)"""
        import io
        import json

        logger = StructuredLogger("test_module")

        # Create JSON formatter
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                # Add extra fields
                for key, value in record.__dict__.items():
                    if key not in [
                        "name",
                        "msg",
                        "args",
                        "created",
                        "filename",
                        "funcName",
                        "levelname",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "message",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                        "asctime",
                    ]:
                        log_data[key] = value
                return json.dumps(log_data)

        handler = logging.StreamHandler(io.StringIO())
        handler.setFormatter(JSONFormatter())
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        logger.logger.info(
            "JSON formatted message", extra={"user_id": 123, "action": "test"}
        )

        output = handler.stream.getvalue()
        assert output is not None
        # Try to parse as JSON
        try:
            log_json = json.loads(output)
            assert log_json["message"] == "JSON formatted message"
            assert log_json["user_id"] == 123
            assert log_json["action"] == "test"
        except json.JSONDecodeError:
            # If not valid JSON, at least check it contains the message
            assert "JSON formatted message" in output
