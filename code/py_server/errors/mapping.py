
"""
Маппинг исключений между 1С и Python для 1С MCP сервера

Обеспечивает трансляцию исключений через границу API:
- Соответствие кодов ошибок между системами
- Сохранение контекста и трассировки
- Поддержка correlation_id для отслеживания
- Нормализация сообщений для跨системного использования

Основан на стандартах из проекта 1c_mcp и RFC 7807 (Problem Details).
"""

from typing import Any, Dict, Optional, Type

try:
    from .base import ErrorCategory, McpError
    from .integration import *
    from .mcp import *
    from .transport import *
    from .validation import *
except ImportError:
    from base import McpError, ErrorCategory
    from validation import *
    from transport import *
    from integration import *
    from mcp import *

import uuid

# Условный импорт логирования
try:
    import logging
    _has_logging = True
except ImportError:
    _has_logging = False
    class MockLogger:
        def debug(self, msg, *args, **kwargs): pass
        def info(self, msg, *args, **kwargs): pass
        def warning(self, msg, *args, **kwargs): pass
        def error(self, msg, *args, **kwargs): pass
        def critical(self, msg, *args, **kwargs): pass
    
    class MockLogging:
        @staticmethod
        def getLogger(name):
            return MockLogger()
    
    logging = MockLogging()


logger = logging.getLogger(__name__)


class ErrorMappingConfig:
    """Конфигурация маппинга ошибок между системами"""
    
    # Базовые соответствия кодов ошибок 1С ↔ Python
    ERROR_CODE_MAPPING = {
        # Системные ошибки (E001-E019)
        "E001": ("SYSTEM001", ErrorCategory.SYSTEM),
        "E002": ("SYSTEM002", ErrorCategory.SYSTEM),
        "E003": ("SYSTEM003", ErrorCategory.SYSTEM),
        "E004": ("SYSTEM004", ErrorCategory.SYSTEM),
        "E005": ("SYSTEM005", ErrorCategory.SYSTEM),
        "E006": ("SYSTEM006", ErrorCategory.SYSTEM),
        "E007": ("SYSTEM007", ErrorCategory.SYSTEM),
        "E008": ("SYSTEM008", ErrorCategory.SYSTEM),
        "E009": ("SYSTEM009", ErrorCategory.SYSTEM),
        "E010": ("SYSTEM010", ErrorCategory.SYSTEM),
        
        # Ошибки валидации (E020-E039)
        "E020": ("VALIDATION001", ErrorCategory.VALIDATION),
        "E021": ("VALIDATION002", ErrorCategory.VALIDATION),
        "E022": ("VALIDATION003", ErrorCategory.VALIDATION),
        "E023": ("VALIDATION004", ErrorCategory.VALIDATION),
        "E024": ("VALIDATION005", ErrorCategory.VALIDATION),
        "E025": ("VALIDATION006", ErrorCategory.VALIDATION),
        "E026": ("VALIDATION007", ErrorCategory.VALIDATION),
        "E027": ("VALIDATION008", ErrorCategory.VALIDATION),
        "E028": ("VALIDATION009", ErrorCategory.VALIDATION),
        "E029": ("VALIDATION010", ErrorCategory.VALIDATION),
        
        # Транспортные ошибки (E040-E059)
        "E040": ("TRANSPORT001", ErrorCategory.TRANSPORT),
        "E041": ("TRANSPORT002", ErrorCategory.TRANSPORT),
        "E042": ("TRANSPORT003", ErrorCategory.TRANSPORT),
        "E043": ("TRANSPORT004", ErrorCategory.TRANSPORT),
        "E044": ("TRANSPORT005", ErrorCategory.TRANSPORT),
        "E045": ("TRANSPORT006", ErrorCategory.TRANSPORT),
        "E046": ("TRANSPORT007", ErrorCategory.TRANSPORT),
        "E047": ("TRANSPORT008", ErrorCategory.TRANSPORT),
        "E048": ("TRANSPORT009", ErrorCategory.TRANSPORT),
        "E049": ("TRANSPORT010", ErrorCategory.TRANSPORT),
        
        # Интеграционные ошибки (E060-E079)
        "E060": ("INTEGRATION001", ErrorCategory.INTEGRATION),
        "E061": ("INTEGRATION002", ErrorCategory.INTEGRATION),
        "E062": ("INTEGRATION003", ErrorCategory.INTEGRATION),
        "E063": ("INTEGRATION004", ErrorCategory.INTEGRATION),
        "E064": ("INTEGRATION005", ErrorCategory.INTEGRATION),
        "E065": ("INTEGRATION006", ErrorCategory.INTEGRATION),
        "E066": ("INTEGRATION007", ErrorCategory.INTEGRATION),
        "E067": ("INTEGRATION008", ErrorCategory.INTEGRATION),
        "E068": ("INTEGRATION009", ErrorCategory.INTEGRATION),
        "E069": ("INTEGRATION010", ErrorCategory.INTEGRATION),
        
        # Аутентификационные ошибки (E080-E089)
        "E080": ("AUTH001", ErrorCategory.AUTH),
        "E081": ("AUTH002", ErrorCategory.AUTH),
        "E082": ("AUTH003", ErrorCategory.AUTH),
        "E083": ("AUTH004", ErrorCategory.AUTH),
        "E084": ("AUTH005", ErrorCategory.AUTH),
        "E085": ("AUTH006", ErrorCategory.AUTH),
        "E086": ("AUTH007", ErrorCategory.AUTH),
        "E087": ("AUTH008", ErrorCategory.AUTH),
        "E088": ("AUTH009", ErrorCategory.AUTH),
        "E089": ("AUTH010", ErrorCategory.AUTH),
        
        # Транзакционные ошибки (E090-E099)
        "E090": ("DATABASE001", ErrorCategory.DATABASE),
        "E091": ("DATABASE002", ErrorCategory.DATABASE),
        "E092": ("DATABASE003", ErrorCategory.DATABASE),
        "E093": ("DATABASE004", ErrorCategory.DATABASE),
        "E094": ("DATABASE005", ErrorCategory.DATABASE),
        "E095": ("DATABASE006", ErrorCategory.DATABASE),
        "E096": ("DATABASE007", ErrorCategory.DATABASE),
        "E097": ("DATABASE008", ErrorCategory.DATABASE),
        "E098": ("DATABASE009", ErrorCategory.DATABASE),
        "E099": ("DATABASE010", ErrorCategory.DATABASE),
    }
    
    # Соответствие классов исключений Python → 1С
    PYTHON_TO_1C_MAPPING = {
        ValidationError: "E020",
        InvalidInputDataError: "E020",
        MissingRequiredFieldError: "E021",
        InvalidFieldValueError: "E022",
        DataSizeExceededError: "E023",
        InvalidDataFormatError: "E024",
        DataDuplicationError: "E025",
        UniquenessViolationError: "E026",
        SerializationError: "E027",
        DeserializationError: "E028",
        DatabaseConstraintViolationError: "E029",
        
        TransportError: "E040",
        NetworkError: "E040",
        ConnectionTimeoutError: "E041",
        ServiceUnavailableTransportError: "E042",
        DNSResolutionError: "E043",
        SSLCertificateError: "E044",
        RateLimitExceededError: "E045",
        HTTPRequestError: "E046",
        InvalidURLError: "E047",
        ConnectionError: "E048",
        CorruptedResponseError: "E049",
        
        IntegrationError: "E060",
        ExternalServiceUnavailableError: "E060",
        ExternalServiceAuthError: "E061",
        InvalidExternalServiceResponseError: "E062",
        DataMappingError: "E063",
        ExternalServiceTimeoutError: "E064",
        ProtocolTranslationError: "E065",
        APIContractViolationError: "E066",
        APIVersioningError: "E067",
        DataMarshallingError: "E068",
        APICompatibilityError: "E069",
    }


class ErrorMapping:
    """
    Класс для маппинга исключений между 1С и Python системами
    
    Обеспечивает:
    - Трансляцию кодов ошибок
    - Сохранение контекста и метаданных
    - Нормализацию сообщений
    - Поддержку correlation_id
    """
    
    def __init__(self, config: Optional[ErrorMappingConfig] = None):
        self.config = config or ErrorMappingConfig()
    
    def python_to_1c(self, error: Exception, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Транслирует Python исключение в формат 1С
        
        Args:
            error: Python исключение
            correlation_id: Идентификатор корреляции
            
        Returns:
            Dict[str, Any]: Данные исключения в формате 1С
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        # Определяем код ошибки
        error_code = self._get_error_code(error)
        
        # Определяем категорию
        category = self._get_category(error)
        
        # Формируем базовую структуру
        result = {
            "КодОшибки": error_code,
            "Категория": category.value,
            "Контекст": "",
            "ПользовательскоеСообщение": str(error),
            "ТехническоеСообщение": str(error),
            "Восстановимое": getattr(error, 'recoverable', True),
            "TraceId": correlation_id,
            "ВремяСоздания": getattr(error, 'timestamp', None),
            "Пользователь": "",
            "Соединение": "",
            "ДополнительныеПараметры": {}
        }
        
        # Добавляем контекстные данные
        if isinstance(error, McpError):
            result["Контекст"] = error.context
            result["ТехническоеСообщение"] = error.technical_message
            result["ДополнительныеПараметры"] = error.context_data.copy()
        
        # Добавляем дополнительную информацию
        if hasattr(error, '__cause__') and error.__cause__:
            result["ДополнительныеПараметры"]["Причина"] = str(error.__cause__)
        
        if hasattr(error, '__traceback__') and error.__traceback__:
            result["ДополнительныеПараметры"]["Трассировка"] = self._format_traceback(error.__traceback__)
        
        return result
    
    def _1c_to_python(self, error_data: Dict[str, Any]) -> McpError:
        """
        Транслирует данные исключения из 1С в Python исключение
        
        Args:
            error_data: Данные исключения из 1С
            
        Returns:
            McpError: Соответствующее Python исключение
        """
        error_code = error_data.get("КодОшибки", "")
        category = error_data.get("Категория", "")
        user_message = error_data.get("ПользовательскоеСообщение", "")
        context = error_data.get("Контекст", "")
        additional_params = error_data.get("ДополнительныеПараметры", {})
        recoverable = error_data.get("Восстановимое", True)
        
        # Определяем тип исключения на основе кода ошибки
        error_class = self._get_error_class(error_code, category)
        
        # Создаем соответствующее исключение
        if error_class in [ValidationError, InvalidInputDataError, MissingRequiredFieldError]:
            field_name = additional_params.get("field_name", "")
            field_value = additional_params.get("field_value", None)
            return error_class(
                error_code=error_code,
                field_name=field_name,
                field_value=field_value,
                user_message=user_message,
                recoverable=recoverable,
                context_data=additional_params
            )
        
        elif error_class in [TransportError, NetworkError, ConnectionTimeoutError]:
            url = additional_params.get("url", "")
            method = additional_params.get("method", "GET")
            return error_class(
                error_code=error_code,
                url=url,
                method=method,
                user_message=user_message,
                recoverable=recoverable,
                context_data=additional_params
            )
        
        elif error_class in [IntegrationError, ExternalServiceUnavailableError]:
            service_name = additional_params.get("service_name", "")
            api_version = additional_params.get("api_version", "")
            return error_class(
                error_code=error_code,
                service_name=service_name,
                api_version=api_version,
                user_message=user_message,
                recoverable=recoverable,
                context_data=additional_params
            )
        
        else:
            # Базовое исключение
            return McpError(
                error_code=error_code,
                error_type=error_class.__name__,
                user_message=user_message,
                context=context,
                recoverable=recoverable,
                context_data=additional_params
            )
    
    def _get_error_code(self, error: Exception) -> str:
        """Определяет код ошибки для Python исключения"""
        if isinstance(error, McpError):
            return error.error_code
        
        # Поиск в маппинге
        for python_class, one_c_code in self.config.PYTHON_TO_1C_MAPPING.items():
            if isinstance(error, python_class):
                return one_c_code
        
        # По умолчанию системная ошибка
        return "E001"
    
    def _get_category(self, error: Exception) -> ErrorCategory:
        """Определяет категорию ошибки"""
        if isinstance(error, McpError):
            return error.category
        
        # Поиск в маппинге
        for python_class, (error_code, category) in self.config.ERROR_CODE_MAPPING.items():
            if isinstance(error, python_class):
                return category
        
        return ErrorCategory.SYSTEM
    
    def _get_error_class(self, error_code: str, category: str) -> Type[McpError]:
        """Определяет класс исключения на основе кода ошибки и категории"""
        
        # Точные соответствия
        mapping = {
            # Валидация
            "E020": InvalidInputDataError,
            "E021": MissingRequiredFieldError,
            "E022": InvalidFieldValueError,
            "E023": DataSizeExceededError,
            "E024": InvalidDataFormatError,
            "E025": DataDuplicationError,
            "E026": UniquenessViolationError,
            "E027": SerializationError,
            "E028": DeserializationError,
            "E029": DatabaseConstraintViolationError,
            
            # Транспорт
            "E040": NetworkError,
            "E041": ConnectionTimeoutError,
            "E042": ServiceUnavailableTransportError,
            "E043": DNSResolutionError,
            "E044": SSLCertificateError,
            "E045": RateLimitExceededError,
            "E046": HTTPRequestError,
            "E047": InvalidURLError,
            "E048": ConnectionError,
            "E049": CorruptedResponseError,
            
            # Интеграция
            "E060": ExternalServiceUnavailableError,
            "E061": ExternalServiceAuthError,
            "E062": InvalidExternalServiceResponseError,
            "E063": DataMappingError,
            "E064": ExternalServiceTimeoutError,
            "E065": ProtocolTranslationError,
            "E066": APIContractViolationError,
            "E067": APIVersioningError,
            "E068": DataMarshallingError,
            "E069": APICompatibilityError,
        }
        
        return mapping.get(error_code, McpError)
    
    def _format_traceback(self, tb) -> str:
        """Форматирует traceback для передачи между системами"""
        import traceback
        return ''.join(traceback.format_tb(tb))
    
    def normalize_error_message(self, error: Exception, source_system: str) -> str:
        """
        Нормализует сообщение об ошибке для跨системного использования
        
        Args:
            error: Исключение
            source_system: Источник системы ("1c" или "python")
            
        Returns:
            str: Нормализованное сообщение
        """
        if source_system == "1c":
            # Нормализация сообщения из 1С
            message = str(error)
            # Удаляем служебную информацию 1С
            message = message.replace("Ошибка:", "").strip()
            return message
        
        elif source_system == "python":
            # Нормализация сообщения Python
            if isinstance(error, McpError):
                return error.user_message
            else:
                return str(error)
        
        return str(error)
    
    def enrich_error_context(self, error: Exception, additional_context: Dict[str, Any]) -> McpError:
        """
        Обогащает контекст ошибки дополнительными данными
        
        Args:
            error: Исходное исключение
            additional_context: Дополнительный контекст
            
        Returns:
            McpError: Обогащенное исключение
        """
        if isinstance(error, McpError):
            # Обновляем контекстные данные
            error.context_data.update(additional_context)
            return error
        else:
            # Оборачиваем в McpError
            return McpError(
                error_code=self._get_error_code(error),
                error_type=type(error).__name__,
                user_message=str(error),
                context_data=additional_context.copy()
            )


class CrossSystemErrorHandler:
    """
    Обработчик ошибок для межсистемного взаимодействия
    
    Обеспечивает:
    - Логирование ошибок с корреляцией
    - Трансляцию между системами
    - Сохранение контекста операций
    """
    
    def __init__(self, mapping: Optional[ErrorMapping] = None):
        self.mapping = mapping or ErrorMapping()
        self.logger = logging.getLogger(__name__)
    
    def handle_error(
        self,
        error: Exception,
        operation: str,
        system_boundary: str = "api",
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает ошибку для межсистемного взаимодействия
        
        Args:
            error: Исключение
            operation: Выполняемая операция
            system_boundary: Граница системы ("api", "database", "external")
            correlation_id: Идентификатор корреляции
            
        Returns:
            Dict[str, Any]: Нормализованные данные ошибки
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        # Добавляем контекст операции
        additional_context = {
            "operation": operation,
            "system_boundary": system_boundary,
            "handled_at": str(uuid.uuid4())  # Для отслеживания обработки
        }
        
        # Обогащаем исключение контекстом
        enriched_error = self.mapping.enrich_error_context(error, additional_context)
        
        # Логируем ошибку
        if isinstance(enriched_error, McpError):
            enriched_error.with_correlation_id(correlation_id).log(self.logger)
        else:
            self.logger.error(
                f"Error in {operation} [{correlation_id}]: {enriched_error}",
                extra={
                    "correlation_id": correlation_id,
                    "operation": operation,
                    "system_boundary": system_boundary
                }
            )
        
        # Транслируем в формат 1С для хранения/логирования
        error_data = self.mapping.python_to_1c(enriched_error, correlation_id)
        
        return error_data
    
    def translate_for_api_response(
        self,
        error: Exception,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Подготавливает ошибку для ответа API
        
        Args:
            error: Исключение
            correlation_id: Идентификатор корреляции
            
        Returns:
            Dict[str, Any]: Ответ в формате RFC 7807
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        
        # Транслируем исключение
        if isinstance(error, McpError):
            # Уже подготовлено для MCP
            response_data = error.to_mcp_response()
        else:
            # Создаем базовое исключение
            base_error = McpError(
                error_code="E001",
                error_type=type(error).__name__,
                user_message=str(error),
                correlation_id=correlation_id
            )
            response_data = base_error.to_mcp_response()
        
        # Добавляем метаданные для отладки
        if hasattr(error, '__traceback__'):
            response_data["error"]["data"]["debug_info"] = {
                "traceback_available": True,
                "requires_debug_mode": True
            }
        
        return response_data


# Экспортируемые экземпляры
default_error_mapping = ErrorMapping()
default_error_handler = CrossSystemErrorHandler(default_error_mapping)


# Утилитарные функции
def translate_1c_error_to_python(error_data: Dict[str, Any]) -> McpError:
    """Утилита для быстрой трансляции ошибки 1С в Python"""
    return default_error_mapping._1c_to_python(error_data)


def translate_python_error_to_1c(error: Exception, correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """Утилита для быстрой трансляции ошибки Python в 1С"""
    return default_error_mapping.python_to_1c(error, correlation_id)


def handle_api_error(
    error: Exception,
    operation: str,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Утилита для обработки ошибок API"""
    return default_error_handler.handle_error(error, operation, "api", correlation_id)


def prepare_api_error_response(
    error: Exception,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Утилита для подготовки ответа API с ошибкой"""
    return default_error_handler.translate_for_api_response(error, correlation_id)