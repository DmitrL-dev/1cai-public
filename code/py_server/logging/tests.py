
"""
Тесты для системы структурированного логирования.

Покрытие основных компонентов:
- Конфигурация
- Форматирование логов
- Маскирование данных
- HTTP middleware
- Корреляционные ID
"""

import asyncio
import json
import time
from unittest.mock import patch

import pytest

# Импорт тестируемых модулей
from .config import LoggingConfig, logging_config
from .formatter import (HTTPRequestFormatter, LogLevel, PerformanceFormatter,
                        StructuredFormatter, create_log_structure)
from .handlers import (ConsoleHandler, FileHandler, StructuredLogger)
from .middleware import (LoggingMiddleware, correlation_context,
                         correlation_context_manager, log_execution_time,
                         with_correlation_id)
from .sanitizers import (DataSanitizer, MaskingRule, sanitize_user_data)


class TestLoggingConfig:
    """Тесты конфигурации логирования"""
    
    def test_default_config_values(self):
        """Тест значений конфигурации по умолчанию"""
        assert logging_config.SERVICE_NAME == "py_server"
        assert logging_config.LOG_LEVEL == "INFO"
        assert logging_config.JSON_OUTPUT is True
        assert logging_config.CONSOLE_COLOR is True
    
    def test_environment_override(self, monkeypatch):
        """Тест переопределения через переменные окружения"""
        monkeypatch.setenv("SERVICE_NAME", "test_service")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        
        config = LoggingConfig()
        assert config.SERVICE_NAME == "test_service"
        assert config.LOG_LEVEL == "DEBUG"
    
    def test_config_to_dict(self):
        """Тест преобразования конфигурации в словарь"""
        config_dict = LoggingConfig.to_dict()
        
        assert "service_name" in config_dict
        assert "log_level" in config_dict
        assert "json_output" in config_dict
        assert isinstance(config_dict, dict)


class TestLogStructure:
    """Тесты структуры логов"""
    
    def test_create_basic_log_structure(self):
        """Тест создания базовой структуры лога"""
        log_data = create_log_structure(
            level=LogLevel.INFO,
            message="Test message",
            logger_name="test_logger"
        )
        
        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        assert log_data["logger_name"] == "test_logger"
        assert "timestamp" in log_data
        assert "correlation_id" in log_data
        assert "request_id" in log_data
    
    def test_create_log_with_optional_fields(self):
        """Тест создания лога с опциональными полями"""
        log_data = create_log_structure(
            level=LogLevel.ERROR,
            message="Error occurred",
            logger_name="error_logger",
            correlation_id="test-correlation",
            user_id="user123",
            duration_ms=150.5,
            error_code="ERR_001",
            context={"key": "value"}
        )
        
        assert log_data["level"] == "ERROR"
        assert log_data["correlation_id"] == "test-correlation"
        assert log_data["user_id"] == "user123"
        assert log_data["duration_ms"] == 150.5
        assert log_data["error_code"] == "ERR_001"
        assert log_data["context"]["key"] == "value"
    
    def test_log_validation(self):
        """Тест валидации структуры лога"""
        from .formatter import LogValidator
        
        valid_log = create_log_structure(
            level=LogLevel.INFO,
            message="Valid log",
            logger_name="test"
        )
        
        is_valid, errors = LogValidator.validate(valid_log)
        assert is_valid is True
        assert len(errors) == 0
        
        # Тест с невалидными данными
        invalid_log = {"message": "missing required fields"}
        is_valid, errors = LogValidator.validate(invalid_log)
        assert is_valid is False
        assert len(errors) > 0


class TestStructuredFormatter:
    """Тесты JSON форматирования"""
    
    def test_json_formatting(self):
        """Тест форматирования в JSON"""
        formatter = StructuredFormatter()
        
        log_data = {
            "timestamp": "2023-01-01T00:00:00Z",
            "level": "INFO",
            "message": "Test message"
        }
        
        json_output = formatter.format_json(log_data, pretty=True)
        assert json.loads(json_output) == log_data
    
    def test_json_parsing(self):
        """Тест парсинга JSON логов"""
        formatter = StructuredFormatter()
        
        log_line = '{"timestamp": "2023-01-01T00:00:00Z", "level": "INFO", "message": "Test"}'
        parsed = formatter.parse_json(log_line)
        
        assert parsed is not None
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test"


class TestDataSanitizer:
    """Тесты маскирования данных"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.sanitizer = DataSanitizer()
    
    def test_email_masking(self):
        """Тест маскирования email"""
        email = "user@example.com"
        masked = self.sanitizer.matcher.replace_with_pattern(
            email, MaskingRule.EMAIL, "***EMAIL***", True
        )
        assert "***EMAIL***" in masked
    
    def test_phone_masking(self):
        """Тест маскирования телефонных номеров"""
        phone = "+7 (900) 123-45-67"
        masked = self.sanitizer.matcher.replace_with_pattern(
            phone, MaskingRule.PHONE, "***PHONE***", True
        )
        assert "X" in masked or "***PHONE***" in masked
    
    def test_sensitive_key_masking(self):
        """Тест маскирования по ключам"""
        data = {"password": "secret123", "email": "test@example.com"}
        sanitized = self.sanitizer.sanitize_dict(data)
        
        assert sanitized["password"] == "***PASSWORD***"
        assert "***EMAIL***" in sanitized["email"]
    
    def test_nested_dict_sanitization(self):
        """Тест санитизации вложенных словарей"""
        data = {
            "user": {
                "email": "user@example.com",
                "profile": {
                    "phone": "+7 (900) 123-45-67"
                }
            }
        }
        
        sanitized = self.sanitizer.sanitize_dict(data)
        assert "***EMAIL***" in sanitized["user"]["email"]
        assert "X" in sanitized["user"]["profile"]["phone"]
    
    def test_credit_card_masking(self):
        """Тест маскирования кредитных карт"""
        card_number = "4532123456789012"
        masked = self.sanitizer.matcher.replace_with_pattern(
            card_number, MaskingRule.CREDIT_CARD, "***CARD***", True
        )
        # Должны сохраниться последние 4 цифры
        assert masked.endswith("9012")
    
    def test_user_data_sanitization(self):
        """Тест санитизации пользовательских данных"""
        user_data = {
            "user_id": "12345",
            "email": "user@example.com",
            "phone": "+7 (900) 123-45-67"
        }
        
        sanitized = sanitize_user_data(user_data)
        
        # user_id должен быть захеширован
        assert len(sanitized["user_id"]) == 64  # SHA256 длина
        assert "***EMAIL***" in sanitized["email"]


class TestCorrelationContext:
    """Тесты корреляционного контекста"""
    
    def test_correlation_id_generation(self):
        """Тест генерации correlation ID"""
        correlation_id = correlation_context.generate_correlation_id()
        assert len(correlation_id) == 36  # UUID4 длина
        assert correlation_context.get_correlation_id() == correlation_id
    
    def test_correlation_context_manager(self):
        """Тест контекстного менеджера"""
        original_id = correlation_context.get_correlation_id()
        custom_id = "custom-correlation-123"
        
        with correlation_context_manager(correlation_id=custom_id):
            assert correlation_context.get_correlation_id() == custom_id
        
        # После выхода из контекста должно восстановиться
        assert correlation_context.get_correlation_id() == original_id
    
    def test_user_id_context(self):
        """Тест контекста user ID"""
        original_user_id = correlation_context.get_user_id()
        custom_user_id = "user456"
        
        with correlation_context_manager(user_id=custom_user_id):
            assert correlation_context.get_user_id() == custom_user_id
        
        assert correlation_context.get_user_id() == original_user_id
    
    def test_duration_calculation(self):
        """Тест вычисления продолжительности"""
        start_time = time.time()
        correlation_context.set_start_time(start_time)
        
        time.sleep(0.01)  # 10ms
        duration = correlation_context.get_duration_ms()
        
        assert duration >= 10  # Минимум 10ms
        assert duration < 50   # Максимум 50ms для теста


class TestLoggingMiddleware:
    """Тесты HTTP middleware"""
    
    @pytest.fixture
    def mock_app(self):
        """Мок приложения"""
        async def app(scope, receive, send):
            response = {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
            }
            await send(response)
            response = {
                "type": "http.response.body",
                "body": b'{"status": "ok"}',
            }
            await send(response)
        return app
    
    def test_middleware_creation(self, mock_app):
        """Тест создания middleware"""
        middleware = LoggingMiddleware(mock_app)
        assert middleware.correlation_header == "X-Correlation-ID"
        assert middleware.user_id_header == "X-User-ID"
    
    @pytest.mark.asyncio
    async def test_http_request_handling(self, mock_app):
        """Тест обработки HTTP запроса"""
        middleware = LoggingMiddleware(mock_app)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [
                [b"x-correlation-id", b"test-correlation-123"],
                [b"user-agent", b"test-agent"]
            ],
            "client": ("127.0.0.1", 8000)
        }
        
        messages = []
        async def mock_send(message):
            messages.append(message)
        
        await middleware(scope, None, mock_send)
        
        # Проверяем, что запрос был обработан
        assert len(messages) > 0
    
    @pytest.mark.asyncio
    async def test_correlation_id_extraction(self, mock_app):
        """Тест извлечения correlation ID из заголовков"""
        middleware = LoggingMiddleware(mock_app)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [[b"x-correlation-id", b"extracted-id"]],
            "client": ("127.0.0.1", 8000)
        }
        
        messages = []
        async def mock_send(message):
            messages.append(message)
        
        with patch('logging_system.middleware.correlation_context') as mock_context:
            await middleware(scope, None, mock_send)
            
            # Проверяем, что correlation ID был установлен
            mock_context.set_correlation_id.assert_called()


class TestDecorators:
    """Тесты декораторов"""
    
    @pytest.mark.asyncio
    async def test_with_correlation_id_decorator(self):
        """Тест декоратора с correlation ID"""
        
        @with_correlation_id("test-correlation-456")
        async def test_function():
            return correlation_context.get_correlation_id()
        
        result = await test_function()
        assert result == "test-correlation-456"
    
    def test_log_execution_time_decorator(self):
        """Тест декоратора времени выполнения"""
        
        @log_execution_time("test_operation")
        def test_function():
            time.sleep(0.01)  # 10ms
            return "result"
        
        result = test_function()
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_async_log_execution_time_decorator(self):
        """Тест асинхронного декоратора времени выполнения"""
        
        @log_execution_time("async_test_operation")
        async def test_async_function():
            await asyncio.sleep(0.01)  # 10ms
            return "async_result"
        
        result = await test_async_function()
        assert result == "async_result"


class TestHandlers:
    """Тесты обработчиков логов"""
    
    def test_console_handler(self):
        """Тест консольного обработчика"""
        handler = ConsoleHandler(color=False, pretty_print=True)
        
        log_data = {
            "timestamp": "2023-01-01T00:00:00Z",
            "level": "INFO",
            "message": "Test console message"
        }
        
        # Тест не должен выбрасывать исключения
        handler.handle(log_data)
    
    def test_file_handler(self, tmp_path):
        """Тест файлового обработчика"""
        log_file = tmp_path / "test.log"
        handler = FileHandler(str(log_file))
        
        log_data = {
            "timestamp": "2023-01-01T00:00:00Z",
            "level": "INFO", 
            "message": "Test file message"
        }
        
        handler.handle(log_data)
        
        # Проверяем, что файл создан и содержит данные
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test file message" in content
        assert json.loads(content.split('\n')[0])["level"] == "INFO"
    
    def test_structured_logger(self):
        """Тест структурированного логгера"""
        logger = StructuredLogger("test_logger", console=False)
        
        # Тест различных уровней логирования
        logger.info("Test info message", extra_data="value")
        logger.warning("Test warning message")
        logger.error("Test error message")
        logger.critical("Test critical message")
        logger.debug("Test debug message")


class TestSpecializedFormatters:
    """Тесты специализированных форматировщиков"""
    
    def test_http_request_formatter(self):
        """Тест форматировщика HTTP запросов"""
        log_data = HTTPRequestFormatter.format_request_log(
            method="POST",
            url="/api/users",
            status_code=201,
            duration_ms=45.2,
            correlation_id="req-123"
        )
        
        assert log_data["level"] == "INFO"
        assert log_data["http_method"] == "POST"
        assert log_data["http_status_code"] == 201
        assert log_data["duration_ms"] == 45.2
    
    def test_performance_formatter(self):
        """Тест форматировщика производительности"""
        log_data = PerformanceFormatter.format_performance_log(
            operation="database_query",
            duration_ms=150.0,
            correlation_id="perf-123",
            query_complexity="high"
        )
        
        assert log_data["level"] == "INFO"
        assert log_data["duration_ms"] == 150.0
        assert log_data["context"]["operation"] == "database_query"


class TestIntegration:
    """Интеграционные тесты"""
    
    def test_full_logging_workflow(self):
        """Тест полного рабочего процесса логирования"""
        
        # Создание логгера
        logger = StructuredLogger("integration_test", console=False)
        
        # Создание структурированного лога
        log_data = create_log_structure(
            level=LogLevel.INFO,
            message="Integration test message",
            logger_name="integration_test",
            user_id="test_user",
            duration_ms=25.5
        )
        
        # Санитизация данных
        from .sanitizers import sanitize_for_logging
        sanitized_data = sanitize_for_logging(log_data)
        
        # Обработка через handler
        handler = ConsoleHandler(color=False)
        handler.handle(sanitized_data)
        
        # Проверяем, что все работает без ошибок
        assert True  # Если дошли до сюда - тест прошел
    
    @pytest.mark.asyncio
    async def test_async_logging_workflow(self):
        """Тест асинхронного рабочего процесса"""
        
        @with_correlation_id()
        @log_execution_time("async_test")
        async def async_operation():
            await asyncio.sleep(0.01)
            return {"result": "success"}
        
        result = await async_operation()
        assert result["result"] == "success"


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v"])