
"""
HTTP обработчики для FastAPI приложения

Обеспечивает:
- Обработку 401/403 с информативными сообщениями
- Логирование попыток аутентификации
- Маскирование чувствительных данных
- Rate limiting ошибки
- Структурированные HTTP ответы
- Graceful degradation для сервисов
"""

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

# Импорты иерархии исключений
from errors.transport import RateLimitExceededError
from errors.validation import ValidationError
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .correlation import format_correlation_context, get_correlation_id
# Импорты модулей проекта
from .response_models import (ErrorCategory, ErrorResponse, ErrorSeverity,
                              Language)

logger = logging.getLogger(__name__)


class OAuth2ErrorHandler:
    """Обработчик OAuth2 ошибок и аутентификации"""
    
    def __init__(self, default_language: Language = Language.RU):
        self.default_language = default_language
        self.security = HTTPBearer(auto_error=False)
    
    async def handle_auth_error(
        self,
        request: Request,
        error_type: str,
        error_description: str,
        http_status: int = 401,
        **kwargs
    ) -> Response:
        """
        Обрабатывает ошибки аутентификации
        
        Args:
            request: FastAPI Request
            error_type: Тип ошибки OAuth2
            error_description: Описание ошибки
            http_status: HTTP статус код
            **kwargs: Дополнительные параметры
            
        Returns:
            Response: JSONResponse с нормализованной ошибкой
        """
        correlation_id = get_correlation_id()
        
        # Логируем попытку аутентификации
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get('User-Agent', '')
        
        context = format_correlation_context(
            operation="auth_error",
            auth_error_type=error_type,
            client_ip=client_ip,
            user_agent=user_agent,
            request_path=str(request.url.path),
            **kwargs
        )
        
        if http_status == 401:
            logger.warning(
                f"Неудачная попытка аутентификации: {error_description}",
                extra=context
            )
        elif http_status == 403:
            logger.warning(
                f"Недостаточно прав доступа: {error_description}",
                extra=context
            )
        
        # Маппинг OAuth2 ошибок на типы
        error_mapping = self._map_oauth_error(error_type, http_status)
        
        # Локализация сообщений
        messages = self._get_auth_messages(error_type)
        
        # Создаем нормализованный ответ
        error_response = ErrorResponse.create(
            error_code=error_mapping['code'],
            error_type=error_mapping['type'],
            message_ru=messages['ru'],
            message_en=messages['en'],
            http_status_code=http_status,
            correlation_id=correlation_id,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.AUTH,
            recoverable=True,
            details={
                "auth_error_type": error_type,
                "client_ip": self._mask_ip(client_ip),
                "request_path": str(request.url.path),
                "auth_method": kwargs.get('auth_method', 'bearer'),
                **self._sanitize_context(kwargs)
            }
        )
        
        return JSONResponse(
            status_code=http_status,
            content=error_response.dict(),
            headers=self._get_auth_headers(error_type)
        )
    
    def _map_oauth_error(self, error_type: str, http_status: int) -> Dict[str, str]:
        """Маппинг OAuth2 ошибок на внутренние коды"""
        
        if http_status == 401:
            return {
                'code': 'E080',
                'type': 'UnauthorizedError'
            }
        elif http_status == 403:
            return {
                'code': 'E081', 
                'type': 'ForbiddenError'
            }
        elif 'invalid_token' in error_type.lower():
            return {
                'code': 'E082',
                'type': 'InvalidTokenError'
            }
        elif 'expired_token' in error_type.lower():
            return {
                'code': 'E083',
                'type': 'ExpiredTokenError'
            }
        elif 'insufficient_scope' in error_type.lower():
            return {
                'code': 'E084',
                'type': 'InsufficientScopeError'
            }
        else:
            return {
                'code': 'E080',
                'type': 'AuthError'
            }
    
    def _get_auth_messages(self, error_type: str) -> Dict[str, str]:
        """Получает локализованные сообщения для ошибок аутентификации"""
        
        messages_map = {
            'invalid_request': {
                'ru': 'Некорректный запрос аутентификации',
                'en': 'Invalid authentication request'
            },
            'unauthorized_client': {
                'ru': 'Неавторизованный клиент',
                'en': 'Unauthorized client'
            },
            'access_denied': {
                'ru': 'Доступ запрещен',
                'en': 'Access denied'
            },
            'unsupported_response_type': {
                'ru': 'Неподдерживаемый тип ответа',
                'en': 'Unsupported response type'
            },
            'invalid_scope': {
                'ru': 'Некорректная область доступа',
                'en': 'Invalid scope'
            },
            'server_error': {
                'ru': 'Ошибка сервера авторизации',
                'en': 'Authorization server error'
            },
            'temporarily_unavailable': {
                'ru': 'Сервис авторизации временно недоступен',
                'en': 'Authorization service temporarily unavailable'
            },
            'invalid_token': {
                'ru': 'Недействительный токен',
                'en': 'Invalid token'
            },
            'expired_token': {
                'ru': 'Токен истек',
                'en': 'Token expired'
            },
            'insufficient_scope': {
                'ru': 'Недостаточно прав доступа',
                'en': 'Insufficient scope'
            }
        }
        
        return messages_map.get(error_type, {
            'ru': 'Ошибка аутентификации',
            'en': 'Authentication error'
        })
    
    def _get_client_ip(self, request: Request) -> str:
        """Получает IP адрес клиента с учетом прокси"""
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else 'unknown'
    
    def _mask_ip(self, ip: str) -> str:
        """Маскирует IP адрес для логирования"""
        if ip == 'unknown':
            return ip
        
        parts = ip.split('.')
        if len(parts) == 4:  # IPv4
            return f"{parts[0]}.{parts[1]}.***.***"
        elif ':' in ip:  # IPv6
            return ip[:19] + ":*:*:*:*:*:*:*"
        else:
            return "***"
    
    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Санитизирует чувствительные данные из контекста"""
        sensitive_keys = ['password', 'token', 'secret', 'key', 'auth']
        sanitized = {}
        
        for key, value in context.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _get_auth_headers(self, error_type: str) -> Dict[str, str]:
        """Получает дополнительные заголовки для ошибок аутентификации"""
        headers = {}
        
        # WWW-Authenticate для 401 ошибок
        if error_type in ['invalid_token', 'expired_token', 'insufficient_scope']:
            headers['WWW-Authenticate'] = 'Bearer error="invalid_token"'
        elif error_type == 'invalid_scope':
            headers['WWW-Authenticate'] = 'Bearer error="invalid_scope"'
        else:
            headers['WWW-Authenticate'] = 'Bearer'
        
        return headers


class RateLimitErrorHandler:
    """Обработчик ошибок rate limiting"""
    
    def __init__(self):
        self.rate_limits = {}
        self.failed_attempts = {}
    
    async def handle_rate_limit_error(
        self,
        request: Request,
        limit_info: Dict[str, Any],
        http_status: int = 429
    ) -> Response:
        """
        Обрабатывает ошибки превышения лимита запросов
        
        Args:
            request: FastAPI Request
            limit_info: Информация о лимите
            http_status: HTTP статус код
            
        Returns:
            Response: JSONResponse с информацией о лимитах
        """
        correlation_id = get_correlation_id()
        
        # Извлекаем данные клиента
        client_id = self._get_client_identifier(request)
        client_ip = self._get_client_ip(request)
        
        # Логируем превышение лимита
        context = format_correlation_context(
            operation="rate_limit_exceeded",
            client_id=client_id,
            client_ip=self._mask_ip(client_ip),
            limit_info=limit_info,
            request_path=str(request.url.path)
        )
        
        logger.warning(
            f"Превышен лимит запросов для клиента {client_id}",
            extra=context
        )
        
        # Вычисляем время до сброса лимита
        reset_time = limit_info.get('reset_time')
        retry_after = limit_info.get('retry_after', 60)
        
        if reset_time and isinstance(reset_time, datetime):
            retry_after = int((reset_time - datetime.utcnow()).total_seconds())
        
        # Создаем нормализованный ответ
        error_response = ErrorResponse.create(
            error_code="E045",
            error_type="RateLimitError",
            message_ru=f"Превышен лимит запросов. Повторите через {retry_after} секунд",
            message_en=f"Rate limit exceeded. Try again in {retry_after} seconds",
            http_status_code=http_status,
            correlation_id=correlation_id,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.TRANSPORT,
            recoverable=True,
            details={
                "client_id": client_id,
                "client_ip": self._mask_ip(client_ip),
                "rate_limit_info": limit_info,
                "request_path": str(request.url.path),
                "user_agent": request.headers.get('User-Agent', '')
            }
        )
        
        # Дополнительные заголовки
        headers = {
            'Retry-After': str(retry_after),
            'X-RateLimit-Limit': str(limit_info.get('limit', 'unknown')),
            'X-RateLimit-Remaining': str(limit_info.get('remaining', 0)),
            'X-RateLimit-Reset': str(int(time.time()) + retry_after)
        }
        
        return JSONResponse(
            status_code=http_status,
            content=error_response.dict(),
            headers=headers
        )
    
    def _get_client_identifier(self, request: Request) -> str:
        """Получает идентификатор клиента для rate limiting"""
        # Проверяем заголовки в порядке приоритета
        identifiers = [
            'X-User-ID',
            'X-Client-ID', 
            'X-API-Key',
            'Authorization',  # Извлекаем из токена
        ]
        
        for identifier_header in identifiers:
            value = request.headers.get(identifier_header)
            if value:
                if identifier_header == 'Authorization':
                    # Извлекаем ID из Bearer токена (упрощенно)
                    return f"bearer_{value[:20]}"
                return value
        
        # Используем IP если нет других идентификаторов
        return f"ip_{self._get_client_ip(request)}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Получает IP адрес клиента"""
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        return request.client.host if request.client else 'unknown'
    
    def _mask_ip(self, ip: str) -> str:
        """Маскирует IP адрес"""
        if ip == 'unknown':
            return ip
        
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.***.***"
        else:
            return "***"


class HttpServiceErrorHandler:
    """Обработчик ошибок внешних HTTP сервисов"""
    
    def __init__(self):
        self.service_status = {}
        self.service_health = {}
    
    async def handle_service_error(
        self,
        request: Request,
        service_name: str,
        error: Exception,
        http_status: int = 503
    ) -> Response:
        """
        Обрабатывает ошибки внешних сервисов
        
        Args:
            request: FastAPI Request
            service_name: Название сервиса
            error: Исключение
            http_status: HTTP статус код
            
        Returns:
            Response: JSONResponse с информацией об ошибке сервиса
        """
        correlation_id = get_correlation_id()
        
        # Обновляем статус сервиса
        self._update_service_status(service_name, 'error', str(error))
        
        # Логируем ошибку сервиса
        context = format_correlation_context(
            operation="service_error",
            service_name=service_name,
            error_type=type(error).__name__,
            error_message=str(error),
            request_path=str(request.url.path)
        )
        
        logger.error(
            f"Ошибка сервиса {service_name}: {str(error)}",
            extra=context
        )
        
        # Создаем нормализованный ответ
        error_response = ErrorResponse.create(
            error_code="E042",
            error_type="ServiceUnavailableError",
            message_ru=f"Сервис '{service_name}' временно недоступен",
            message_en=f"Service '{service_name}' temporarily unavailable",
            http_status_code=http_status,
            correlation_id=correlation_id,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.SERVICE,
            recoverable=True,
            details={
                "service_name": service_name,
                "service_status": self.service_status.get(service_name, {}),
                "original_error": str(error),
                "error_type": type(error).__name__,
                "request_path": str(request.url.path)
            }
        )
        
        return JSONResponse(status_code=http_status, content=error_response.dict())
    
    async def handle_service_health_check(
        self,
        request: Request,
        service_name: str,
        health_status: Dict[str, Any]
    ) -> Response:
        """
        Обрабатывает проверку здоровья сервиса
        
        Args:
            request: FastAPI Request
            service_name: Название сервиса
            health_status: Статус здоровья
            
        Returns:
            Response: JSONResponse с информацией о здоровье
        """
        correlation_id = get_correlation_id()
        
        # Обновляем статус здоровья
        self.service_health[service_name] = {
            **health_status,
            'last_check': datetime.utcnow().isoformat(),
            'correlation_id': correlation_id
        }
        
        # Определяем общий статус
        is_healthy = health_status.get('status') == 'ok'
        
        if is_healthy:
            logger.debug(
                f"Сервис {service_name} работает нормально",
                extra={'correlation_id': correlation_id}
            )
        else:
            logger.warning(
                f"Проблемы с сервисом {service_name}: {health_status.get('message', 'Unknown error')}",
                extra={'correlation_id': correlation_id}
            )
        
        return JSONResponse(
            status_code=200 if is_healthy else 503,
            content={
                'service': service_name,
                'status': health_status.get('status', 'unknown'),
                'message': health_status.get('message', ''),
                'timestamp': datetime.utcnow().isoformat(),
                'correlation_id': correlation_id,
                'details': health_status.get('details', {})
            }
        )
    
    def _update_service_status(self, service_name: str, status: str, message: str):
        """Обновляет статус сервиса"""
        self.service_status[service_name] = {
            'status': status,
            'message': message,
            'last_update': datetime.utcnow().isoformat()
        }


class HttpGracefulDegradation:
    """Модуль graceful degradation для HTTP сервисов"""
    
    def __init__(self):
        self.fallback_data = {}
        self.degradation_rules = {}
    
    def register_fallback(
        self,
        endpoint_pattern: str,
        fallback_func: Callable,
        conditions: Optional[Dict[str, Any]] = None
    ):
        """
        Регистрирует fallback функцию для эндпоинта
        
        Args:
            endpoint_pattern: Паттерн эндпоинта (например, "/api/users/*")
            fallback_func: Функция fallback
            conditions: Условия для активации fallback
        """
        self.fallback_data[endpoint_pattern] = {
            'func': fallback_func,
            'conditions': conditions or {},
            'registered_at': datetime.utcnow().isoformat()
        }
    
    async def get_fallback_response(
        self,
        request: Request,
        endpoint: str,
        original_error: Exception
    ) -> Optional[Response]:
        """
        Получает fallback ответ для эндпоинта
        
        Args:
            request: FastAPI Request
            endpoint: Эндпоинт
            original_error: Исходная ошибка
            
        Returns:
            Response: Fallback ответ или None
        """
        # Ищем подходящий fallback
        fallback_info = self._find_matching_fallback(endpoint)
        
        if not fallback_info:
            return None
        
        # Проверяем условия
        if not self._check_conditions(fallback_info['conditions'], original_error):
            return None
        
        # Выполняем fallback
        try:
            correlation_id = get_correlation_id()
            
            fallback_result = await fallback_info['func'](
                request=request,
                endpoint=endpoint,
                error=original_error,
                correlation_id=correlation_id
            )
            
            # Логируем использование fallback
            logger.warning(
                f"Использован fallback для {endpoint}",
                extra={
                    'correlation_id': correlation_id,
                    'endpoint': endpoint,
                    'error_type': type(original_error).__name__
                }
            )
            
            return JSONResponse(
                status_code=200,  # Возвращаем 200 чтобы не ломать клиентов
                content={
                    'data': fallback_result,
                    'fallback': True,
                    'original_endpoint': endpoint,
                    'fallback_reason': str(original_error),
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
        except Exception as fallback_error:
            logger.error(
                f"Ошибка в fallback для {endpoint}: {str(fallback_error)}",
                extra={
                    'correlation_id': get_correlation_id(),
                    'endpoint': endpoint,
                    'fallback_error': str(fallback_error)
                }
            )
            return None
    
    def _find_matching_fallback(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Находит подходящий fallback для эндпоинта"""
        for pattern, fallback_info in self.fallback_data.items():
            if self._pattern_matches(pattern, endpoint):
                return fallback_info
        return None
    
    def _pattern_matches(self, pattern: str, endpoint: str) -> bool:
        """Проверяет соответствие паттерну"""
        if pattern.endswith('*'):
            return endpoint.startswith(pattern[:-1])
        return endpoint == pattern
    
    def _check_conditions(self, conditions: Dict[str, Any], error: Exception) -> bool:
        """Проверяет условия для активации fallback"""
        
        # Проверяем тип ошибки
        if 'error_types' in conditions:
            if type(error).__name__ not in conditions['error_types']:
                return False
        
        # Проверяем статус код ошибки
        if 'http_status_codes' in conditions:
            if hasattr(error, 'status_code'):
                if error.status_code not in conditions['http_status_codes']:
                    return False
        
        # Проверяем восстановимость ошибки
        if 'recoverable' in conditions:
            if hasattr(error, 'recoverable'):
                if error.recoverable != conditions['recoverable']:
                    return False
        
        return True


class HttpErrorHandler:
    """
    Главный HTTP обработчик ошибок
    
    Координирует работу всех специализированных обработчиков
    """
    
    def __init__(self, app: FastAPI, default_language: Language = Language.RU):
        self.app = app
        self.default_language = default_language
        self.oauth_handler = OAuth2ErrorHandler(default_language)
        self.rate_limit_handler = RateLimitErrorHandler()
        self.service_handler = HttpServiceErrorHandler()
        self.degradation = HttpGracefulDegradation()
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Настройка всех HTTP обработчиков ошибок"""
        
        # Глобальный обработчик HTTPException
        @self.app.exception_handler(HTTPException)
        async def handle_http_exception(request: Request, exc: HTTPException) -> Response:
            return await self._handle_http_exception(request, exc)
        
        # Обработчик ошибок валидации
        @self.app.exception_handler(ValidationError)
        async def handle_validation_error(request: Request, exc: ValidationError) -> Response:
            return await self._handle_validation_error(request, exc)
        
        # Обработчик Rate Limit ошибок
        @self.app.exception_handler(RateLimitExceededError)
        async def handle_rate_limit_error(request: Request, exc: RateLimitExceededError) -> Response:
            return await self.rate_limit_handler.handle_rate_limit_error(
                request,
                exc.context_data.get('rate_limit_info', {})
            )
        
        logger.info("HTTP обработчики ошибок настроены")
    
    async def _handle_http_exception(self, request: Request, exc: HTTPException) -> Response:
        """Главный обработчик HTTPException"""
        
        # Специальная обработка для 401 и 403
        if exc.status_code in [401, 403]:
            auth_header = request.headers.get('Authorization', '')
            auth_method = 'bearer' if auth_header.startswith('Bearer') else 'unknown'
            
            return await self.oauth_handler.handle_auth_error(
                request=request,
                error_type='server_error',
                error_description=exc.detail,
                http_status=exc.status_code,
                auth_method=auth_method,
                detail=exc.detail
            )
        
        # Стандартная обработка
        correlation_id = get_correlation_id()
        
        error_response = ErrorResponse.from_http_exception(exc, correlation_id)
        
        return JSONResponse(
            status_code=error_response.error['error']['http_status_code'],
            content=error_response.dict()
        )
    
    async def _handle_validation_error(self, request: Request, exc: ValidationError) -> Response:
        """Обработчик ошибок валидации"""
        correlation_id = get_correlation_id()
        
        # Логируем ошибку валидации
        context = format_correlation_context(
            operation="validation_error",
            field_name=exc.context_data.get('field_name', ''),
            validation_rule=exc.context_data.get('validation_rule', ''),
            request_path=str(request.url.path)
        )
        
        logger.warning(f"Ошибка валидации: {exc.user_message}", extra=context)
        
        error_response = ErrorResponse.from_mcp_error(exc, self.default_language)
        
        return JSONResponse(status_code=422, content=error_response.dict())
    
    def setup_oauth_error_handling(self):
        """Настройка обработки OAuth2 ошибок"""
        return self.oauth_handler
    
    def setup_rate_limit_handling(self):
        """Настройка обработки rate limiting"""
        return self.rate_limit_handler
    
    def setup_service_error_handling(self):
        """Настройка обработки ошибок сервисов"""
        return self.service_handler
    
    def setup_graceful_degradation(self):
        """Настройка graceful degradation"""
        return self.degradation


# Middleware для автоматического логирования HTTP запросов
class HttpLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования HTTP запросов и ответов"""
    
    def __init__(self, app: ASGIApp, log_slow_requests: bool = True, slow_threshold: float = 1.0):
        super().__init__(app)
        self.log_slow_requests = log_slow_requests
        self.slow_threshold = slow_threshold
    
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        correlation_id = get_correlation_id()
        
        # Логируем начало запроса
        context = format_correlation_context(
            operation="http_request",
            method=request.method,
            path=str(request.url.path),
            query_params=dict(request.query_params),
            client_ip=self._get_client_ip(request),
            user_agent=request.headers.get('User-Agent', '')
        )
        
        logger.info(
            f"Начало HTTP запроса: {request.method} {request.url.path}",
            extra=context
        )
        
        try:
            # Выполняем запрос
            response = await call_next(request)
            
            # Вычисляем время выполнения
            duration = time.time() - start_time
            
            # Логируем завершение
            status_context = {
                **context,
                'status_code': response.status_code,
                'duration': duration,
                'response_headers': dict(response.headers)
            }
            
            if self.log_slow_requests and duration > self.slow_threshold:
                logger.warning(
                    f"Медленный запрос: {duration:.2f}s",
                    extra=status_context
                )
            else:
                logger.info(
                    f"HTTP запрос завершен: {response.status_code}",
                    extra=status_context
                )
            
            # Добавляем correlation_id в ответ
            response.headers['X-Correlation-Id'] = correlation_id
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Логируем ошибку
            logger.error(
                f"Ошибка HTTP запроса: {type(e).__name__}: {str(e)}",
                extra={
                    **context,
                    'duration': duration,
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                },
                exc_info=True
            )
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Получает IP адрес клиента"""
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.client.host if request.client else 'unknown'


# Фабрика для создания HTTP обработчиков
def setup_http_error_handlers(
    app: FastAPI,
    default_language: Language = Language.RU,
    enable_logging: bool = True,
    enable_graceful_degradation: bool = True
) -> HttpErrorHandler:
    """
    Настройка всех HTTP обработчиков ошибок
    
    Args:
        app: FastAPI приложение
        default_language: Язык по умолчанию
        enable_logging: Включить HTTP логирование
        enable_graceful_degradation: Включить graceful degradation
        
    Returns:
        HttpErrorHandler: Настроенный обработчик
    """
    
    # Создаем главный обработчик
    http_handler = HttpErrorHandler(app, default_language)
    
    # Добавляем middleware для логирования
    if enable_logging:
        app.add_middleware(HttpLoggingMiddleware)
    
    # Добавляем middleware для graceful degradation
    if enable_graceful_degradation:
        # Можно добавить специальное middleware
        pass
    
    logger.info(
        "HTTP обработчики ошибок настроены",
        extra={
            'default_language': default_language.value,
            'logging_enabled': enable_logging,
            'graceful_degradation': enable_graceful_degradation
        }
    )
    
    return http_handler
