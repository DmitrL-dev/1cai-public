
"""
Модели нормализованных ответов для MCP сервера

Обеспечивает:
- Стандартную структуру ErrorResponse
- Поддержку русского и английского языков
- Различение HTTP статус-кодов и error.code
- Интеграцию с иерархией исключений из errors/
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field


class ErrorSeverity(str, Enum):
    """Уровни серьезности ошибок"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Категории ошибок"""
    SYSTEM = "system"
    VALIDATION = "validation"
    TRANSPORT = "transport"
    INTEGRATION = "integration"
    AUTH = "auth"
    DATABASE = "database"
    MCP = "mcp"
    SERVICE = "service"


class Language(str, Enum):
    """Поддерживаемые языки для сообщений"""
    RU = "ru"
    EN = "en"


class ErrorDetails(BaseModel):
    """Детали ошибки для внутреннего использования"""
    original_exception: Optional[str] = None
    stack_trace: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    operation: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """
    Нормализованная структура ответа об ошибке
    
    Стандартизированный формат для всех типов ошибок:
    - HTTP ошибки (400, 401, 403, 404, 500, etc.)
    - MCP ошибки (tools, resources, prompts)
    - JSON-RPC ошибки
    - Внутренние ошибки сервера
    """
    
    error: Dict[str, Any] = Field(
        ...,
        description="Структурированная информация об ошибке"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "error": {
                    "code": "E001",
                    "type": "SystemError", 
                    "message": "Внутренняя ошибка сервера",
                    "message_en": "Internal server error",
                    "details": {
                        "original_exception": "ValueError: Invalid input data",
                        "operation": "validate_input",
                        "context": {"field": "user_id"}
                    },
                    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "timestamp": "2025-10-29T21:57:33",
                    "severity": "high",
                    "category": "system",
                    "recoverable": False,
                    "http_status_code": 500
                }
            }
        }
    
    @classmethod
    def create(
        cls,
        error_code: str,
        error_type: str,
        message_ru: str,
        message_en: Optional[str] = None,
        http_status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SERVICE,
        recoverable: bool = True,
        **kwargs
    ) -> 'ErrorResponse':
        """
        Создает ErrorResponse с заданными параметрами
        
        Args:
            error_code: Код ошибки (E001-E099, MCP001, etc.)
            error_type: Тип исключения
            message_ru: Сообщение на русском языке
            message_en: Сообщение на английском языке
            http_status_code: HTTP статус код
            details: Дополнительные детали
            correlation_id: Идентификатор корреляции
            severity: Серьезность ошибки
            category: Категория ошибки
            recoverable: Возможность восстановления
            **kwargs: Дополнительные параметры
            
        Returns:
            ErrorResponse: Нормализованный ответ об ошибке
        """
        # Создаем корреляционный ID если не передан
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        
        # Создаем timestamp
        timestamp = datetime.utcnow().isoformat()
        
        # Формируем details
        error_details = ErrorDetails(**(details or {}))
        if error_details.correlation_id is None:
            error_details.correlation_id = correlation_id
            
        # Локализуем сообщения
        localized_messages = {
            "ru": message_ru,
            "en": message_en or message_ru
        }
        
        error_data = {
            "code": error_code,
            "type": error_type,
            "message": localized_messages,
            "http_status_code": http_status_code,
            "correlation_id": correlation_id,
            "timestamp": timestamp,
            "severity": severity,
            "category": category,
            "recoverable": recoverable
        }
        
        # Добавляем details если есть
        if details:
            error_data["details"] = error_details.dict(exclude_none=True)
        
        # Добавляем дополнительные параметры
        error_data.update(kwargs)
        
        return cls(error={"error": error_data})
    
    @classmethod
    def from_mcp_error(
        cls,
        mcp_error,
        language: Language = Language.RU,
        **kwargs
    ) -> 'ErrorResponse':
        """
        Создает ErrorResponse из McpError исключения
        
        Args:
            mcp_error: Исключение из иерархии errors/
            language: Язык для сообщения
            **kwargs: Дополнительные параметры
            
        Returns:
            ErrorResponse: Нормализованный ответ
        """
        # Определяем HTTP статус код по типу ошибки
        http_status = cls._map_error_to_http_status(mcp_error)
        
        # Выбираем сообщение по языку
        message = getattr(mcp_error, 'user_message', 'Unknown error')
        
        # Дополнительные details из исключения
        details = {
            "original_exception": str(mcp_error.original_exception) if mcp_error.original_exception else None,
            "operation": getattr(mcp_error, 'context', ''),
            "context": getattr(mcp_error, 'context_data', {})
        }
        
        return cls.create(
            error_code=getattr(mcp_error, 'error_code', 'E001'),
            error_type=getattr(mcp_error, 'error_type', 'UnknownError'),
            message_ru=message,
            message_en=message,  # Можно добавить переводы
            http_status_code=http_status,
            details=details,
            correlation_id=getattr(mcp_error, 'correlation_id', None),
            severity=getattr(mcp_error, 'severity', ErrorSeverity.MEDIUM),
            category=getattr(mcp_error, 'category', ErrorCategory.SERVICE),
            recoverable=getattr(mcp_error, 'recoverable', True),
            **kwargs
        )
    
    @classmethod
    def from_http_exception(
        cls,
        http_exception,
        correlation_id: Optional[str] = None
    ) -> 'ErrorResponse':
        """
        Создает ErrorResponse из HTTPException
        
        Args:
            http_exception: FastAPI HTTPException
            correlation_id: Идентификатор корреляции
            
        Returns:
            ErrorResponse: Нормализованный ответ
        """
        # Маппинг HTTP кодов на типы ошибок
        status_code = http_exception.status_code
        error_mapping = cls._get_http_error_mapping(status_code)
        
        message_ru = cls._get_http_message_ru(status_code)
        message_en = cls._get_http_message_en(status_code)
        
        return cls.create(
            error_code=error_mapping['code'],
            error_type=error_mapping['type'],
            message_ru=message_ru,
            message_en=message_en,
            http_status_code=status_code,
            correlation_id=correlation_id,
            severity=ErrorSeverity(error_mapping['severity']),
            category=ErrorCategory(error_mapping['category']),
            recoverable=error_mapping['recoverable'],
            details={"detail": str(http_exception.detail)} if http_exception.detail else None
        )
    
    @classmethod
    def validation_error(
        cls,
        field_name: str,
        message: str,
        http_status_code: int = 422,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> 'ErrorResponse':
        """Создает ErrorResponse для ошибок валидации"""
        return cls.create(
            error_code="E020",
            error_type="ValidationError",
            message_ru=f"Ошибка валидации поля '{field_name}': {message}",
            message_en=f"Validation error for field '{field_name}': {message}",
            http_status_code=http_status_code,
            correlation_id=correlation_id,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,
            recoverable=False,
            details={"field_name": field_name, "validation_error": message},
            **kwargs
        )
    
    @classmethod
    def auth_error(
        cls,
        message: str = "Ошибка аутентификации",
        http_status_code: int = 401,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> 'ErrorResponse':
        """Создает ErrorResponse для ошибок аутентификации"""
        return cls.create(
            error_code="E080",
            error_type="AuthError",
            message_ru=message,
            message_en="Authentication error",
            http_status_code=http_status_code,
            correlation_id=correlation_id,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.AUTH,
            recoverable=True,
            **kwargs
        )
    
    @classmethod
    def transport_error(
        cls,
        message: str,
        http_status_code: int = 503,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> 'ErrorResponse':
        """Создает ErrorResponse для транспортных ошибок"""
        return cls.create(
            error_code="E040",
            error_type="TransportError",
            message_ru=message,
            message_en="Transport error",
            http_status_code=http_status_code,
            correlation_id=correlation_id,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.TRANSPORT,
            recoverable=True,
            **kwargs
        )
    
    @staticmethod
    def _map_error_to_http_status(error) -> int:
        """Маппинг типов ошибок на HTTP статусы"""
        error_type = getattr(error, 'error_type', '').lower()
        
        mapping = {
            'validationerror': 422,
            'autherror': 401,
            'permissionerror': 403,
            'notfounderror': 404,
            'timeout': 408,
            'rate limite error': 429,
            'systemerror': 500,
            'transporterror': 503,
            'serviceunavailableerror': 503,
            'internalerror': 500,
            'mcpprotocolerror': 400,
            'mcptoolerror': 500,
            'mcpresourceerror': 404,
            'mcpprompterror': 500
        }
        
        return mapping.get(error_type, 500)
    
    @staticmethod
    def _get_http_error_mapping(status_code: int) -> Dict[str, Any]:
        """Маппинг HTTP кодов на типы ошибок"""
        mapping = {
            400: {
                'code': 'E002',
                'type': 'BadRequestError',
                'severity': 'medium',
                'category': 'validation',
                'recoverable': False
            },
            401: {
                'code': 'E080',
                'type': 'UnauthorizedError',
                'severity': 'high',
                'category': 'auth',
                'recoverable': True
            },
            403: {
                'code': 'E081',
                'type': 'ForbiddenError',
                'severity': 'high',
                'category': 'auth',
                'recoverable': False
            },
            404: {
                'code': 'E004',
                'type': 'NotFoundError',
                'severity': 'medium',
                'category': 'validation',
                'recoverable': False
            },
            422: {
                'code': 'E020',
                'type': 'ValidationError',
                'severity': 'medium',
                'category': 'validation',
                'recoverable': False
            },
            429: {
                'code': 'E045',
                'type': 'RateLimitError',
                'severity': 'medium',
                'category': 'transport',
                'recoverable': True
            },
            500: {
                'code': 'E001',
                'type': 'InternalServerError',
                'severity': 'high',
                'category': 'system',
                'recoverable': False
            },
            502: {
                'code': 'E048',
                'type': 'BadGatewayError',
                'severity': 'high',
                'category': 'transport',
                'recoverable': True
            },
            503: {
                'code': 'E042',
                'type': 'ServiceUnavailableError',
                'severity': 'high',
                'category': 'transport',
                'recoverable': True
            }
        }
        
        return mapping.get(status_code, {
            'code': 'E001',
            'type': 'UnknownError',
            'severity': 'medium',
            'category': 'service',
            'recoverable': False
        })
    
    @staticmethod
    def _get_http_message_ru(status_code: int) -> str:
        """Сообщения об ошибках на русском языке"""
        messages = {
            400: "Некорректный запрос",
            401: "Требуется аутентификация",
            403: "Доступ запрещен",
            404: "Ресурс не найден",
            422: "Ошибка валидации данных",
            429: "Превышен лимит запросов",
            500: "Внутренняя ошибка сервера",
            502: "Ошибка шлюза",
            503: "Сервис недоступен"
        }
        
        return messages.get(status_code, "Неизвестная ошибка")
    
    @staticmethod
    def _get_http_message_en(status_code: int) -> str:
        """Сообщения об ошибках на английском языке"""
        messages = {
            400: "Bad Request",
            401: "Authentication Required",
            403: "Access Forbidden",
            404: "Resource Not Found",
            422: "Validation Error",
            429: "Rate Limit Exceeded",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable"
        }
        
        return messages.get(status_code, "Unknown Error")


class SuccessResponse(BaseModel):
    """Модель успешного ответа"""
    
    data: Any
    correlation_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    class Config:
        schema_extra = {
            "example": {
                "data": {"result": "success"},
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-10-29T21:57:33"
            }
        }


class HealthCheckResponse(BaseModel):
    """Модель ответа проверки здоровья"""
    
    status: str = "healthy"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: Optional[str] = None
    uptime_seconds: Optional[float] = None
    checks: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-10-29T21:57:33",
                "version": "1.0.0",
                "uptime_seconds": 3600.0,
                "checks": {
                    "database": {"status": "ok", "response_time_ms": 15.2},
                    "redis": {"status": "ok", "response_time_ms": 3.1}
                },
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class McpResponse(BaseModel):
    """Базовый класс для MCP ответов"""
    
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    
    def to_error_response(self, error_data: Dict[str, Any]) -> 'McpResponse':
        """Преобразует в MCP ошибку"""
        self.error = error_data
        if hasattr(self, 'result'):
            delattr(self, 'result')
        return self


class McpSuccessResponse(McpResponse):
    """Успешный MCP ответ"""
    
    result: Any
    
    @classmethod
    def create(
        cls,
        result: Any,
        request_id: Optional[Union[str, int]] = None
    ) -> 'McpSuccessResponse':
        return cls(result=result, id=request_id)


class McpErrorResponse(McpResponse):
    """Ошибка MCP ответа"""
    
    error: Dict[str, Any]
    
    @classmethod
    def create(
        cls,
        error_code: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        request_id: Optional[Union[str, int]] = None
    ) -> 'McpErrorResponse':
        error_data = {"code": error_code, "message": message}
        if data:
            error_data["data"] = data
            
        return cls(error=error_data, id=request_id)
