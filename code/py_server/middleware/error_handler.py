
"""
Глобальный обработчик исключений для FastAPI приложения

Обеспечивает:
- Перехват всех исключений с нормализацией ответов
- Интеграцию с иерархией исключений из errors/
- Структурированное логирование всех ошибок
- Поддержку всех типов MCP ошибок
- HTTPException и общие исключения
"""

import logging
import traceback
from typing import Any, Dict, Union

import httpx
# Импорты иерархии исключений
from errors.base import ErrorSeverity as McpErrorSeverity
from errors.base import McpError
from errors.mcp import (McpInternalServerError, McpInvalidRequestError,
                        McpPromptError, McpProtocolError, McpRateLimitError,
                        McpResourceError, McpToolError)
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import HTTPException, RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from .correlation import (format_correlation_context, get_correlation_id)
# Импорты модулей проекта
from .response_models import (ErrorCategory, ErrorResponse, ErrorSeverity,
                              Language)

logger = logging.getLogger(__name__)


class GlobalExceptionHandler:
    """
    Глобальный обработчик всех исключений FastAPI приложения
    
    Обеспечивает:
    - Централизованную обработку всех типов ошибок
    - Нормализацию ответов
    - Структурированное логирование
    - Корректную работу с correlation_id
    """
    
    def __init__(self, app: FastAPI, default_language: Language = Language.RU):
        """
        Инициализация обработчика
        
        Args:
            app: FastAPI приложение
            default_language: Язык по умолчанию для сообщений
        """
        self.app = app
        self.default_language = default_language
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Настройка всех обработчиков исключений"""
        
        # Глобальный обработчик всех исключений
        @self.app.exception_handler(Exception)
        async def handle_general_exception(request: Request, exc: Exception) -> Response:
            return await self._handle_general_exception(request, exc)
        
        # HTTPException
        @self.app.exception_handler(HTTPException)
        async def handle_http_exception(request: Request, exc: HTTPException) -> Response:
            return await self._handle_http_exception(request, exc)
        
        # Starlette HTTPException
        @self.app.exception_handler(StarletteHTTPException)
        async def handle_starlette_http_exception(request: Request, exc: StarletteHTTPException) -> Response:
            return await self._handle_http_exception(request, exc)
        
        # Validation Error
        @self.app.exception_handler(RequestValidationError)
        async def handle_validation_error(request: Request, exc: RequestValidationError) -> Response:
            return await self._handle_validation_error(request, exc)
        
        # McpError и подклассы
        self._register_mcp_error_handlers()
        
        # HTTP клиент ошибки
        self._register_http_client_handlers()
    
    def _register_mcp_error_handlers(self) -> None:
        """Регистрация обработчиков для MCP ошибок"""
        
        @self.app.exception_handler(McpProtocolError)
        async def handle_mcp_protocol_error(request: Request, exc: McpProtocolError) -> Response:
            return await self._handle_mcp_error(request, exc, "MCP Protocol Error")
        
        @self.app.exception_handler(McpToolError)
        async def handle_mcp_tool_error(request: Request, exc: McpToolError) -> Response:
            return await self._handle_mcp_error(request, exc, "MCP Tool Error")
        
        @self.app.exception_handler(McpResourceError)
        async def handle_mcp_resource_error(request: Request, exc: McpResourceError) -> Response:
            return await self._handle_mcp_error(request, exc, "MCP Resource Error")
        
        @self.app.exception_handler(McpPromptError)
        async def handle_mcp_prompt_error(request: Request, exc: McpPromptError) -> Response:
            return await self._handle_mcp_error(request, exc, "MCP Prompt Error")
        
        @self.app.exception_handler(McpInternalServerError)
        async def handle_mcp_internal_error(request: Request, exc: McpInternalServerError) -> Response:
            return await self._handle_mcp_error(request, exc, "MCP Internal Error", http_status=500)
        
        @self.app.exception_handler(McpInvalidRequestError)
        async def handle_mcp_invalid_request(request: Request, exc: McpInvalidRequestError) -> Response:
            return await self._handle_mcp_error(request, exc, "MCP Invalid Request", http_status=400)
        
        @self.app.exception_handler(McpRateLimitError)
        async def handle_mcp_rate_limit(request: Request, exc: McpRateLimitError) -> Response:
            return await self._handle_mcp_error(request, exc, "MCP Rate Limit", http_status=429)
    
    def _register_http_client_handlers(self) -> None:
        """Регистрация обработчиков для HTTP клиент ошибок"""
        
        @self.app.exception_handler(httpx.HTTPError)
        async def handle_httpx_error(request: Request, exc: httpx.HTTPError) -> Response:
            return await self._handle_httpx_error(request, exc)
        
        @self.app.exception_handler(httpx.HTTPStatusError)
        async def handle_httpx_status_error(request: Request, exc: httpx.HTTPStatusError) -> Response:
            return await self._handle_httpx_status_error(request, exc)
        
        @self.app.exception_handler(httpx.ConnectError)
        async def handle_connect_error(request: Request, exc: httpx.ConnectError) -> Response:
            return await self._handle_connection_error(request, exc)
        
        @self.app.exception_handler(httpx.TimeoutException)
        async def handle_timeout_error(request: Request, exc: httpx.TimeoutException) -> Response:
            return await self._handle_timeout_error(request, exc)
    
    async def _handle_general_exception(self, request: Request, exc: Exception) -> Response:
        """
        Обработчик общих исключений
        
        Args:
            request: FastAPI Request
            exc: Исключение
            
        Returns:
            Response: JSONResponse с нормализованной ошибкой
        """
        correlation_id = get_correlation_id()
        
        # Логируем с полным контекстом
        context = format_correlation_context(
            operation="handle_general_exception",
            request_method=request.method,
            request_path=str(request.url.path),
            request_headers=dict(request.headers),
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            traceback=traceback.format_exc()
        )
        
        logger.error(
            f"Необработанное исключение: {type(exc).__name__}: {str(exc)}",
            extra=context
        )
        
        # Определяем тип исключения и маппинг
        error_mapping = self._map_general_exception(exc)
        
        # Создаем нормализованный ответ
        error_response = ErrorResponse.create(
            error_code=error_mapping['code'],
            error_type=error_mapping['type'],
            message_ru=error_mapping['message_ru'],
            message_en=error_mapping['message_en'],
            http_status_code=error_mapping['http_status'],
            correlation_id=correlation_id,
            severity=ErrorSeverity(error_mapping['severity']),
            category=ErrorCategory(error_mapping['category']),
            recoverable=error_mapping['recoverable'],
            details={
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "request_id": request.headers.get('X-Request-ID', ''),
                "user_agent": request.headers.get('User-Agent', '')
            }
        )
        
        return JSONResponse(
            status_code=error_response.error['error']['http_status_code'],
            content=error_response.dict()
        )
    
    async def _handle_http_exception(self, request: Request, exc: Union[HTTPException, StarletteHTTPException]) -> Response:
        """
        Обработчик HTTPException
        
        Args:
            request: FastAPI Request
            exc: HTTPException
            
        Returns:
            Response: JSONResponse с нормализованной ошибкой
        """
        correlation_id = get_correlation_id()
        
        # Логируем HTTP исключение
        context = format_correlation_context(
            operation="handle_http_exception",
            http_status_code=exc.status_code,
            detail=str(exc.detail),
            request_path=str(request.url.path)
        )
        
        logger.warning(
            f"HTTP Exception {exc.status_code}: {str(exc.detail)}",
            extra=context
        )
        
        # Создаем нормализованный ответ
        error_response = ErrorResponse.from_http_exception(exc, correlation_id)
        
        return JSONResponse(
            status_code=error_response.error['error']['http_status_code'],
            content=error_response.dict()
        )
    
    async def _handle_validation_error(self, request: Request, exc: RequestValidationError) -> Response:
        """
        Обработчик ошибок валидации Pydantic
        
        Args:
            request: FastAPI Request
            exc: RequestValidationError
            
        Returns:
            Response: JSONResponse с нормализованной ошибкой
        """
        correlation_id = get_correlation_id()
        
        # Логируем ошибку валидации
        context = format_correlation_context(
            operation="handle_validation_error",
            validation_errors=exc.errors(),
            request_path=str(request.url.path)
        )
        
        logger.warning(
            f"Ошибка валидации: {len(exc.errors())} ошибок",
            extra=context
        )
        
        # Формируем сообщения об ошибках
        validation_messages = []
        for error in exc.errors():
            field = '.'.join(str(x) for x in error['loc'] if x != 'body')
            msg = error['msg']
            validation_messages.append(f"{field}: {msg}")
        
        error_response = ErrorResponse.create(
            error_code="E020",
            error_type="ValidationError",
            message_ru="Ошибка валидации входных данных: " + "; ".join(validation_messages),
            message_en=f"Validation error: {'; '.join(validation_messages)}",
            http_status_code=422,
            correlation_id=correlation_id,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,
            recoverable=False,
            details={
                "validation_errors": exc.errors(),
                "validation_count": len(exc.errors())
            }
        )
        
        return JSONResponse(
            status_code=422,
            content=error_response.dict()
        )
    
    async def _handle_mcp_error(
        self,
        request: Request,
        exc: McpError,
        error_type_description: str,
        http_status: int = None
    ) -> Response:
        """
        Обработчик MCP ошибок
        
        Args:
            request: FastAPI Request
            exc: McpError исключение
            error_type_description: Описание типа ошибки
            http_status: HTTP статус (опционально)
            
        Returns:
            Response: JSONResponse с нормализованной ошибкой
        """
        correlation_id = exc.correlation_id or get_correlation_id()
        
        # Логируем MCP ошибку
        context = format_correlation_context(
            operation="handle_mcp_error",
            mcp_error_code=exc.error_code,
            mcp_error_type=exc.error_type,
            mcp_context=exc.context,
            recoverable=exc.recoverable,
            severity=exc.severity.value
        )
        
        log_level = logger.warning if exc.severity == McpErrorSeverity.MEDIUM else logger.error
        log_level(
            f"MCP Error {exc.error_code}: {exc.user_message}",
            extra=context
        )
        
        # Создаем нормализованный ответ
        error_response = ErrorResponse.from_mcp_error(
            exc,
            language=self.default_language,
            http_status_code=http_status or self._map_mcp_error_to_http(exc)
        )
        
        return JSONResponse(
            status_code=error_response.error['error']['http_status_code'],
            content=error_response.dict()
        )
    
    async def _handle_httpx_error(self, request: Request, exc: httpx.HTTPError) -> Response:
        """Обработчик общих HTTP клиент ошибок"""
        correlation_id = get_correlation_id()
        
        error_response = ErrorResponse.transport_error(
            message=f"HTTP клиент ошибка: {str(exc)}",
            http_status_code=503,
            correlation_id=correlation_id,
            details={
                "request_url": str(request.url),
                "exception_type": type(exc).__name__
            }
        )
        
        logger.error(f"HTTP клиент ошибка: {str(exc)}", extra={
            'correlation_id': correlation_id,
            'exception_type': type(exc).__name__
        })
        
        return JSONResponse(status_code=503, content=error_response.dict())
    
    async def _handle_httpx_status_error(self, request: Request, exc: httpx.HTTPStatusError) -> Response:
        """Обработчик HTTP статус ошибок"""
        correlation_id = get_correlation_id()
        
        error_response = ErrorResponse.create(
            error_code="E046",
            error_type="HTTPRequestError",
            message_ru=f"HTTP ошибка {exc.response.status_code}: {exc.response.text[:200]}",
            message_en=f"HTTP error {exc.response.status_code}: {exc.response.text[:200]}",
            http_status_code=502,
            correlation_id=correlation_id,
            details={
                "response_status_code": exc.response.status_code,
                "response_headers": dict(exc.response.headers),
                "request_url": str(request.url)
            }
        )
        
        logger.warning(f"HTTP статус ошибка: {exc.response.status_code}", extra={
            'correlation_id': correlation_id,
            'status_code': exc.response.status_code
        })
        
        return JSONResponse(status_code=502, content=error_response.dict())
    
    async def _handle_connection_error(self, request: Request, exc: httpx.ConnectError) -> Response:
        """Обработчик ошибок подключения"""
        correlation_id = get_correlation_id()
        
        error_response = ErrorResponse.transport_error(
            message=f"Ошибка подключения: {str(exc)}",
            http_status_code=503,
            correlation_id=correlation_id,
            details={
                "connection_error": str(exc),
                "request_url": str(request.url)
            }
        )
        
        logger.warning(f"Ошибка подключения: {str(exc)}", extra={
            'correlation_id': correlation_id
        })
        
        return JSONResponse(status_code=503, content=error_response.dict())
    
    async def _handle_timeout_error(self, request: Request, exc: httpx.TimeoutException) -> Response:
        """Обработчик ошибок таймаута"""
        correlation_id = get_correlation_id()
        
        error_response = ErrorResponse.create(
            error_code="E041",
            error_type="TimeoutError",
            message_ru=f"Превышено время ожидания: {str(exc)}",
            message_en=f"Request timeout: {str(exc)}",
            http_status_code=408,
            correlation_id=correlation_id,
            details={
                "timeout_error": str(exc),
                "request_url": str(request.url)
            }
        )
        
        logger.warning(f"Таймаут запроса: {str(exc)}", extra={
            'correlation_id': correlation_id
        })
        
        return JSONResponse(status_code=408, content=error_response.dict())
    
    def _map_general_exception(self, exc: Exception) -> Dict[str, Any]:
        """
        Маппинг общих исключений на коды ошибок
        
        Args:
            exc: Исключение
            
        Returns:
            Dict[str, Any]: Маппинг исключения
        """
        exc_type = type(exc).__name__
        
        # Маппинг типов исключений
        mapping = {
            'ValueError': {
                'code': 'E020',
                'type': 'ValueError',
                'message_ru': 'Некорректное значение параметра',
                'message_en': 'Invalid parameter value',
                'http_status': 400,
                'severity': 'medium',
                'category': 'validation',
                'recoverable': False
            },
            'KeyError': {
                'code': 'E021',
                'type': 'KeyError',
                'message_ru': 'Отсутствует обязательный параметр',
                'message_en': 'Missing required parameter',
                'http_status': 400,
                'severity': 'medium',
                'category': 'validation',
                'recoverable': False
            },
            'TypeError': {
                'code': 'E020',
                'type': 'TypeError',
                'message_ru': 'Некорректный тип данных',
                'message_en': 'Invalid data type',
                'http_status': 400,
                'severity': 'medium',
                'category': 'validation',
                'recoverable': False
            },
            'AttributeError': {
                'code': 'E001',
                'type': 'AttributeError',
                'message_ru': 'Ошибка доступа к атрибуту',
                'message_en': 'Attribute access error',
                'http_status': 500,
                'severity': 'high',
                'category': 'system',
                'recoverable': False
            },
            'FileNotFoundError': {
                'code': 'E004',
                'type': 'FileNotFoundError',
                'message_ru': 'Файл не найден',
                'message_en': 'File not found',
                'http_status': 404,
                'severity': 'medium',
                'category': 'validation',
                'recoverable': False
            },
            'PermissionError': {
                'code': 'E003',
                'type': 'PermissionError',
                'message_ru': 'Недостаточно прав доступа',
                'message_en': 'Permission denied',
                'http_status': 403,
                'severity': 'high',
                'category': 'auth',
                'recoverable': False
            },
            'MemoryError': {
                'code': 'E010',
                'type': 'MemoryError',
                'message_ru': 'Недостаточно памяти',
                'message_en': 'Out of memory',
                'http_status': 507,
                'severity': 'critical',
                'category': 'system',
                'recoverable': False
            },
            'ConnectionError': {
                'code': 'E048',
                'type': 'ConnectionError',
                'message_ru': 'Ошибка соединения',
                'message_en': 'Connection error',
                'http_status': 503,
                'severity': 'high',
                'category': 'transport',
                'recoverable': True
            }
        }
        
        return mapping.get(exc_type, {
            'code': 'E001',
            'type': 'UnknownError',
            'message_ru': 'Неизвестная ошибка сервера',
            'message_en': 'Unknown server error',
            'http_status': 500,
            'severity': 'medium',
            'category': 'system',
            'recoverable': False
        })
    
    def _map_mcp_error_to_http(self, exc: McpError) -> int:
        """Маппинг MCP ошибок на HTTP статусы"""
        error_type = exc.error_type.lower()
        
        mapping = {
            'mcpprotocolerror': 400,
            'mcpinvalidrequesterror': 400,
            'mcptoolerror': 500,
            'mcpresourceerror': 404,
            'mcpprompterror': 500,
            'mcpinternalservererror': 500,
            'mcpconnectionerror': 503,
            'mcpratelimiterror': 429
        }
        
        return mapping.get(error_type, 500)


def setup_global_exception_handler(
    app: FastAPI,
    default_language: Language = Language.RU,
    enable_structured_logging: bool = True
) -> GlobalExceptionHandler:
    """
    Настройка глобального обработчика исключений
    
    Args:
        app: FastAPI приложение
        default_language: Язык по умолчанию для сообщений
        enable_structured_logging: Включить структурированное логирование
        
    Returns:
        GlobalExceptionHandler: Настроенный обработчик
    """
    
    if enable_structured_logging:
        # Настраиваем JSON форматтер для логгера если нужно
        from logging.handlers import RotatingFileHandler

        # Проверяем наличие JSON форматтера
        if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(handler)
    
    # Создаем и регистрируем обработчик
    handler = GlobalExceptionHandler(app, default_language)
    
    logger.info(
        "Глобальный обработчик исключений настроен",
        extra={'default_language': default_language.value}
    )
    
    return handler


# Декоратор для автоматического логирования исключений
def with_error_handling(
    operation_name: str,
    error_handler: callable = None,
    reraise: bool = True
):
    """
    Декоратор для автоматической обработки исключений в функциях
    
    Args:
        operation_name: Название операции для логирования
        error_handler: Кастомный обработчик ошибок
        reraise: Перевыбрасывать ли исключение
        
    Usage:
        @with_error_handling("save_user")
        async def save_user(user_data):
            # операция
            pass
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            correlation_id = get_correlation_id()
            
            logger.info(f"Начало операции {operation_name}", extra={
                'correlation_id': correlation_id,
                'operation': operation_name
            })
            
            try:
                result = await func(*args, **kwargs)
                logger.info(f"Операция {operation_name} завершена успешно", extra={
                    'correlation_id': correlation_id,
                    'operation': operation_name
                })
                return result
                
            except Exception as e:
                logger.error(
                    f"Ошибка в операции {operation_name}: {str(e)}",
                    extra={
                        'correlation_id': correlation_id,
                        'operation': operation_name,
                        'error_type': type(e).__name__,
                        'error_message': str(e)
                    },
                    exc_info=True
                )
                
                if error_handler:
                    return await error_handler(e, *args, **kwargs)
                
                if reraise:
                    raise
                
                return None
        
        def sync_wrapper(*args, **kwargs):
            correlation_id = get_correlation_id()
            
            logger.info(f"Начало операции {operation_name}", extra={
                'correlation_id': correlation_id,
                'operation': operation_name
            })
            
            try:
                result = func(*args, **kwargs)
                logger.info(f"Операция {operation_name} завершена успешно", extra={
                    'correlation_id': correlation_id,
                    'operation': operation_name
                })
                return result
                
            except Exception as e:
                logger.error(
                    f"Ошибка в операции {operation_name}: {str(e)}",
                    extra={
                        'correlation_id': correlation_id,
                        'operation': operation_name,
                        'error_type': type(e).__name__,
                        'error_message': str(e)
                    },
                    exc_info=True
                )
                
                if error_handler:
                    return error_handler(e, *args, **kwargs)
                
                if reraise:
                    raise
                
                return None
        
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator
