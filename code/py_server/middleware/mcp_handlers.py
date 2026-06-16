
"""
Обработчики MCP эндпоинтов с нормализацией ошибок

Обеспечивает:
- Обработку /health с proper статус-кодами
- Обработку /rpc с нормализацией JSON-RPC ошибок
- MCP tools/list, tools/call с fallback ответами
- Resources и prompts с graceful degradation
- Полную интеграцию с иерархией исключений
"""

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List

# Импорты иерархии исключений
from errors.base import McpError, ServiceUnavailableError, TimeoutError
from errors.mcp import (McpInvalidRequestError, McpJsonRpcError,
                        McpPromptError, McpPromptNotFoundError,
                        McpProtocolError, McpRateLimitError, McpResourceError,
                        McpResourceNotFoundError, McpToolError,
                        McpToolNotFoundError)
from errors.transport import ServiceUnavailableTransportError, TransportError
from errors.validation import ValidationError
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .correlation import (format_correlation_context, get_correlation_id)
# Импорты модулей проекта
from .response_models import (ErrorCategory, ErrorResponse, ErrorSeverity,
                              Language)

logger = logging.getLogger(__name__)


class McpErrorMapper:
    """Маппер MCP ошибок на HTTP статусы и типы"""
    
    ERROR_MAPPINGS = {
        # MCP Protocol ошибки
        McpProtocolError: {'http_status': 400, 'category': 'validation'},
        McpInvalidRequestError: {'http_status': 400, 'category': 'validation'},
        
        # MCP Tool ошибки
        McpToolError: {'http_status': 500, 'category': 'system'},
        McpToolNotFoundError: {'http_status': 404, 'category': 'validation'},
        
        # MCP Resource ошибки
        McpResourceError: {'http_status': 500, 'category': 'system'},
        McpResourceNotFoundError: {'http_status': 404, 'category': 'validation'},
        
        # MCP Prompt ошибки
        McpPromptError: {'http_status': 500, 'category': 'system'},
        McpPromptNotFoundError: {'http_status': 404, 'category': 'validation'},
        
        # Rate limiting
        McpRateLimitError: {'http_status': 429, 'category': 'transport'},
        
        # JSON-RPC ошибки
        McpJsonRpcError: {'http_status': 502, 'category': 'transport'},
        
        # Validation ошибки
        ValidationError: {'http_status': 422, 'category': 'validation'},
        
        # Transport ошибки
        TransportError: {'http_status': 503, 'category': 'transport'},
        ServiceUnavailableTransportError: {'http_status': 503, 'category': 'transport'},
        
        # Service ошибки
        ServiceUnavailableError: {'http_status': 503, 'category': 'service'},
        TimeoutError: {'http_status': 408, 'category': 'service'},
    }
    
    @classmethod
    def get_http_status(cls, error: Exception) -> int:
        """Получает HTTP статус для ошибки"""
        for error_type, mapping in cls.ERROR_MAPPINGS.items():
            if isinstance(error, error_type):
                return mapping['http_status']
        return 500
    
    @classmethod
    def get_category(cls, error: Exception) -> ErrorCategory:
        """Получает категорию ошибки"""
        for error_type, mapping in cls.ERROR_MAPPINGS.items():
            if isinstance(error, error_type):
                return ErrorCategory(mapping['category'])
        return ErrorCategory.SYSTEM


class McpEndpointHandler:
    """
    Базовый обработчик MCP эндпоинтов
    
    Обеспечивает:
    - Общую логику обработки запросов
    - Нормализацию ответов
    - Структурированное логирование
    - Graceful degradation
    """
    
    def __init__(self, default_language: Language = Language.RU):
        self.default_language = default_language
        self.error_mapper = McpErrorMapper()
    
    async def handle_request(
        self,
        request: Request,
        operation_name: str,
        handler_func: callable,
        fallback_response: Any = None,
        timeout_seconds: float = 30.0
    ) -> Response:
        """
        Общий обработчик MCP запросов
        
        Args:
            request: FastAPI Request
            operation_name: Название операции для логирования
            handler_func: Функция-обработчик
            fallback_response: Fallback ответ при ошибке
            timeout_seconds: Таймаут выполнения
            
        Returns:
            Response: HTTP Response
        """
        correlation_id = get_correlation_id()
        
        # Логируем начало обработки
        context = format_correlation_context(
            operation=operation_name,
            request_path=str(request.url.path),
            request_method=request.method,
            client_ip=request.client.host if request.client else 'unknown'
        )
        
        logger.info(f"Начало обработки MCP запроса: {operation_name}", extra=context)
        
        try:
            # Выполняем операцию с таймаутом
            result = await asyncio.wait_for(
                handler_func(request),
                timeout=timeout_seconds
            )
            
            # Логируем успешное завершение
            logger.info(f"MCP запрос завершен успешно: {operation_name}", extra=context)
            
            return JSONResponse(content=result)
            
        except asyncio.TimeoutError:
            # Обработка таймаута
            error_response = ErrorResponse.create(
                error_code="E041",
                error_type="TimeoutError",
                message_ru=f"Превышено время ожидания операции '{operation_name}'",
                message_en=f"Operation timeout: '{operation_name}'",
                http_status_code=408,
                correlation_id=correlation_id,
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.SERVICE,
                recoverable=True,
                details={
                    "operation": operation_name,
                    "timeout_seconds": timeout_seconds,
                    "request_path": str(request.url.path)
                }
            )
            
            logger.warning(f"Таймаут MCP операции: {operation_name}", extra={
                **context,
                'timeout_seconds': timeout_seconds
            })
            
            return JSONResponse(status_code=408, content=error_response.dict())
            
        except Exception as e:
            # Логируем ошибку
            logger.error(
                f"Ошибка в MCP операции {operation_name}: {type(e).__name__}: {str(e)}",
                extra={
                    **context,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc()
                },
                exc_info=True
            )
            
            # Нормализуем ошибку
            normalized_error = await self._normalize_error(e, correlation_id, operation_name)
            
            # Если есть fallback, возвращаем его с предупреждением
            if fallback_response is not None:
                logger.warning(
                    f"Использован fallback ответ для {operation_name}",
                    extra=context
                )
                
                # Добавляем предупреждение в fallback
                if isinstance(fallback_response, dict):
                    fallback_response['warning'] = "Fallback response due to error"
                    fallback_response['error'] = normalized_error.error['error']
                
                return JSONResponse(
                    status_code=200,  # Возвращаем 200 чтобы не ломать MCP клиентов
                    content=fallback_response
                )
            
            # Возвращаем нормализованную ошибку
            return JSONResponse(
                status_code=normalized_error.error['error']['http_status_code'],
                content=normalized_error.dict()
            )
    
    async def _normalize_error(
        self,
        error: Exception,
        correlation_id: str,
        operation: str
    ) -> ErrorResponse:
        """Нормализует ошибку в стандартный формат"""
        
        # Если это уже McpError, используем его напрямую
        if isinstance(error, McpError):
            return ErrorResponse.from_mcp_error(error, self.default_language)
        
        # Маппим на стандартные ошибки
        http_status = self.error_mapper.get_http_status(error)
        category = self.error_mapper.get_category(error)
        
        # Определяем тип и сообщение ошибки
        error_type = type(error).__name__
        error_message = str(error)
        
        # Локализация сообщений
        messages = self._get_error_messages(error_type)
        
        return ErrorResponse.create(
            error_code=self._get_error_code(error_type),
            error_type=error_type,
            message_ru=messages['ru'],
            message_en=messages['en'],
            http_status_code=http_status,
            correlation_id=correlation_id,
            severity=ErrorSeverity.HIGH if category == ErrorCategory.SYSTEM else ErrorSeverity.MEDIUM,
            category=category,
            recoverable=self._is_recoverable_error(error),
            details={
                "operation": operation,
                "original_error_type": type(error).__name__,
                "traceback": traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        )
    
    def _get_error_messages(self, error_type: str) -> Dict[str, str]:
        """Получает локализованные сообщения для типа ошибки"""
        messages_map = {
            'ValueError': {
                'ru': 'Некорректное значение параметра',
                'en': 'Invalid parameter value'
            },
            'KeyError': {
                'ru': 'Отсутствует обязательный параметр',
                'en': 'Missing required parameter'
            },
            'TypeError': {
                'ru': 'Некорректный тип данных',
                'en': 'Invalid data type'
            },
            'AttributeError': {
                'ru': 'Ошибка доступа к атрибуту',
                'en': 'Attribute access error'
            },
            'FileNotFoundError': {
                'ru': 'Ресурс не найден',
                'en': 'Resource not found'
            },
            'PermissionError': {
                'ru': 'Недостаточно прав доступа',
                'en': 'Permission denied'
            },
            'ConnectionError': {
                'ru': 'Ошибка соединения с сервисом',
                'en': 'Service connection error'
            },
            'TimeoutError': {
                'ru': 'Превышено время ожидания',
                'en': 'Request timeout'
            }
        }
        
        return messages_map.get(error_type, {
            'ru': f'Неизвестная ошибка: {error_type}',
            'en': f'Unknown error: {error_type}'
        })
    
    def _get_error_code(self, error_type: str) -> str:
        """Получает код ошибки для типа исключения"""
        codes_map = {
            'ValueError': 'E020',
            'KeyError': 'E021', 
            'TypeError': 'E020',
            'AttributeError': 'E001',
            'FileNotFoundError': 'E004',
            'PermissionError': 'E003',
            'ConnectionError': 'E048',
            'TimeoutError': 'E041',
            'json.JSONDecodeError': 'E024'
        }
        
        return codes_map.get(error_type, 'E001')
    
    def _is_recoverable_error(self, error: Exception) -> bool:
        """Определяет, является ли ошибка восстановимой"""
        recoverable_types = (
            ConnectionError, TimeoutError, TransportError, 
            ServiceUnavailableError, McpRateLimitError
        )
        
        return isinstance(error, recoverable_types)


class McpHealthHandler:
    """Специализированный обработчик для /health эндпоинта"""
    
    def __init__(self):
        self.health_checks = []
    
    def register_check(self, name: str, check_func: callable):
        """Регистрирует проверку здоровья"""
        self.health_checks.append({'name': name, 'func': check_func})
    
    async def handle_health_check(self, request: Request) -> Response:
        """Обрабатывает запрос проверки здоровья"""
        correlation_id = get_correlation_id()
        
        logger.info("Начало проверки здоровья системы", extra={
            'correlation_id': correlation_id
        })
        
        start_time = datetime.utcnow()
        health_status = {
            "status": "healthy",
            "timestamp": start_time.isoformat(),
            "correlation_id": correlation_id,
            "checks": {}
        }
        
        overall_status = "healthy"
        
        # Выполняем все проверки
        for check in self.health_checks:
            try:
                check_result = await check['func']()
                health_status["checks"][check['name']] = check_result
                
                # Определяем статус проверки
                if check_result.get('status') == 'error':
                    overall_status = "unhealthy"
                elif check_result.get('status') == 'warning' and overall_status == "healthy":
                    overall_status = "warning"
                    
            except Exception as e:
                logger.error(
                    f"Ошибка в проверке здоровья {check['name']}: {str(e)}",
                    extra={'correlation_id': correlation_id}
                )
                
                health_status["checks"][check['name']] = {
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
                overall_status = "unhealthy"
        
        health_status["status"] = overall_status
        
        # Определяем HTTP статус код
        http_status = {
            "healthy": 200,
            "warning": 200,
            "unhealthy": 503
        }.get(overall_status, 503)
        
        end_time = datetime.utcnow()
        health_status["uptime_seconds"] = (end_time - start_time).total_seconds()
        
        # Логируем результат
        logger.info(
            f"Проверка здоровья завершена: {overall_status}",
            extra={
                'correlation_id': correlation_id,
                'overall_status': overall_status,
                'checks_count': len(self.health_checks),
                'uptime_seconds': health_status["uptime_seconds"]
            }
        )
        
        return JSONResponse(status_code=http_status, content=health_status)


class McpRpcHandler:
    """Обработчик для /rpc эндпоинта с нормализацией JSON-RPC ошибок"""
    
    def __init__(self):
        self.methods = {}
    
    def register_method(self, name: str, method_func: callable):
        """Регистрирует JSON-RPC метод"""
        self.methods[name] = method_func
    
    async def handle_rpc_request(self, request: Request) -> Response:
        """Обрабатывает JSON-RPC запрос"""
        correlation_id = get_correlation_id()
        
        try:
            # Получаем JSON данные
            if request.headers.get('content-type', '').startswith('application/json'):
                rpc_request = await request.json()
            else:
                raise McpInvalidRequestError(
                    protocol_version="2.0",
                    request_type="jsonrpc",
                    protocol_error="Content-Type must be application/json"
                )
            
            logger.info(
                "Получен JSON-RPC запрос",
                extra={
                    'correlation_id': correlation_id,
                    'jsonrpc': rpc_request.get('jsonrpc'),
                    'method': rpc_request.get('method'),
                    'request_id': rpc_request.get('id')
                }
            )
            
            # Валидируем структуру JSON-RPC
            rpc_response = await self._process_jsonrpc_request(rpc_request, correlation_id)
            
            return JSONResponse(content=rpc_response)
            
        except Exception as e:
            logger.error(
                f"Ошибка в JSON-RPC обработке: {str(e)}",
                extra={
                    'correlation_id': correlation_id,
                    'error_type': type(e).__name__
                },
                exc_info=True
            )
            
            # Нормализуем ошибку
            if isinstance(e, McpError):
                error_response = ErrorResponse.from_mcp_error(e)
            else:
                error_response = ErrorResponse.create(
                    error_code="E001",
                    error_type="JsonRpcError",
                    message_ru=f"Ошибка JSON-RPC: {str(e)}",
                    message_en=f"JSON-RPC error: {str(e)}",
                    http_status_code=500,
                    correlation_id=correlation_id,
                    recoverable=True
                )
            
            return JSONResponse(status_code=500, content=error_response.dict())
    
    async def _process_jsonrpc_request(self, rpc_request: Dict, correlation_id: str) -> Dict:
        """Обрабатывает JSON-RPC запрос"""
        
        # Валидация структуры
        if 'jsonrpc' not in rpc_request or rpc_request['jsonrpc'] != '2.0':
            raise McpInvalidRequestError(
                protocol_version="2.0",
                request_type="jsonrpc",
                protocol_error="Invalid or missing 'jsonrpc' field"
            )
        
        if 'method' not in rpc_request:
            raise McpInvalidRequestError(
                protocol_version="2.0",
                request_type="jsonrpc", 
                protocol_error="Missing 'method' field"
            )
        
        method = rpc_request['method']
        request_id = rpc_request.get('id')
        
        # Проверяем существование метода
        if method not in self.methods:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                    "data": {
                        "correlation_id": correlation_id,
                        "available_methods": list(self.methods.keys())
                    }
                }
            }
        
        # Выполняем метод
        try:
            method_func = self.methods[method]
            params = rpc_request.get('params', {})
            
            result = await method_func(params, correlation_id=correlation_id)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
            
        except Exception as e:
            # Маппинг Python ошибок на JSON-RPC коды
            error_code = self._map_python_error_to_jsonrpc(e)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": error_code,
                    "message": str(e),
                    "data": {
                        "correlation_id": correlation_id,
                        "error_type": type(e).__name__
                    }
                }
            }
    
    def _map_python_error_to_jsonrpc(self, error: Exception) -> int:
        """Маппинг Python ошибок на JSON-RPC коды"""
        
        if isinstance(error, (ValueError, KeyError, TypeError)):
            return -32602  # Invalid params
        elif isinstance(error, McpInvalidRequestError):
            return -32600  # Invalid Request
        elif isinstance(error, TimeoutError):
            return -32000  # Server error (timeout)
        elif isinstance(error, PermissionError):
            return -32001  # Server error (permission)
        elif isinstance(error, FileNotFoundError):
            return -32002  # Server error (not found)
        else:
            return -32000  # Server error


class McpToolsHandler:
    """Обработчик MCP tools/list и tools/call"""
    
    def __init__(self):
        self.tools = {}
        self.fallback_tools = []
    
    def register_tool(self, name: str, tool_func: callable, description: str = ""):
        """Регистрирует MCP инструмент"""
        self.tools[name] = {
            'func': tool_func,
            'description': description
        }
    
    def set_fallback_tools(self, fallback_tools: List[Dict[str, Any]]):
        """Устанавливает fallback список инструментов"""
        self.fallback_tools = fallback_tools
    
    async def handle_tools_list(self, request: Request) -> Response:
        """Обрабатывает запрос списка инструментов"""
        
        async def get_tools_list(request: Request):
            if not self.tools:
                # Возвращаем fallback список если основные инструменты недоступны
                return {
                    "tools": self.fallback_tools,
                    "fallback": True,
                    "warning": "Using fallback tools list due to service unavailability"
                }
            
            tools_list = []
            for name, tool_info in self.tools.items():
                tools_list.append({
                    "name": name,
                    "description": tool_info['description']
                })
            
            return {"tools": tools_list, "fallback": False}
        
        # Fallback ответ при ошибке
        fallback_response = {
            "tools": self.fallback_tools,
            "fallback": True,
            "warning": "Tools list unavailable, using fallback"
        }
        
        handler = McpEndpointHandler()
        return await handler.handle_request(
            request=request,
            operation_name="tools_list",
            handler_func=get_tools_list,
            fallback_response=fallback_response
        )
    
    async def handle_tool_call(self, request: Request, tool_name: str) -> Response:
        """Обрабатывает вызов инструмента"""
        
        async def execute_tool(request: Request):
            # Получаем параметры
            try:
                params = await request.json() if request.headers.get('content-type') else {}
            except Exception:
                params = {}
            
            # Проверяем существование инструмента
            if tool_name not in self.tools:
                available_tools = list(self.tools.keys())
                raise McpToolNotFoundError(tool_name, available_tools)
            
            # Выполняем инструмент
            tool_func = self.tools[tool_name]['func']
            result = await tool_func(params)
            
            return {
                "tool": tool_name,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Fallback ответ при ошибке
        fallback_response = {
            "tool": tool_name,
            "result": None,
            "error": f"Tool {tool_name} execution failed",
            "fallback": True
        }
        
        handler = McpEndpointHandler()
        return await handler.handle_request(
            request=request,
            operation_name=f"tool_call_{tool_name}",
            handler_func=execute_tool,
            fallback_response=fallback_response
        )


class McpResourcesHandler:
    """Обработчик MCP resources/list и resources/read"""
    
    def __init__(self):
        self.resources = {}
        self.fallback_resources = []
    
    def register_resource(self, uri: str, resource_func: callable):
        """Регистрирует MCP ресурс"""
        self.resources[uri] = resource_func
    
    def set_fallback_resources(self, fallback_resources: List[Dict[str, Any]]):
        """Устанавливает fallback список ресурсов"""
        self.fallback_resources = fallback_resources
    
    async def handle_resources_list(self, request: Request) -> Response:
        """Обрабатывает запрос списка ресурсов"""
        
        async def get_resources_list(request: Request):
            if not self.resources:
                return {
                    "resources": self.fallback_resources,
                    "fallback": True,
                    "warning": "Using fallback resources list"
                }
            
            resources_list = []
            for uri in self.resources.keys():
                resources_list.append({
                    "uri": uri,
                    "name": uri.split('/')[-1]
                })
            
            return {"resources": resources_list, "fallback": False}
        
        fallback_response = {
            "resources": self.fallback_resources,
            "fallback": True
        }
        
        handler = McpEndpointHandler()
        return await handler.handle_request(
            request=request,
            operation_name="resources_list",
            handler_func=get_resources_list,
            fallback_response=fallback_response
        )
    
    async def handle_resource_read(self, request: Request, resource_uri: str) -> Response:
        """Обрабатывает чтение ресурса"""
        
        async def read_resource(request: Request):
            if resource_uri not in self.resources:
                available_resources = list(self.resources.keys())
                raise McpResourceNotFoundError(resource_uri, available_resources)
            
            resource_func = self.resources[resource_uri]
            content = await resource_func()
            
            return {
                "uri": resource_uri,
                "content": content,
                "mimeType": "text/plain"
            }
        
        fallback_response = {
            "uri": resource_uri,
            "content": f"Resource {resource_uri} unavailable",
            "mimeType": "text/plain",
            "fallback": True
        }
        
        handler = McpEndpointHandler()
        return await handler.handle_request(
            request=request,
            operation_name=f"resource_read_{resource_uri}",
            handler_func=read_resource,
            fallback_response=fallback_response
        )


class McpPromptsHandler:
    """Обработчик MCP prompts/list и prompts/get"""
    
    def __init__(self):
        self.prompts = {}
        self.fallback_prompts = []
    
    def register_prompt(self, name: str, prompt_func: callable):
        """Регистрирует MCP промпт"""
        self.prompts[name] = prompt_func
    
    def set_fallback_prompts(self, fallback_prompts: List[Dict[str, Any]]):
        """Устанавливает fallback список промптов"""
        self.fallback_prompts = fallback_prompts
    
    async def handle_prompts_list(self, request: Request) -> Response:
        """Обрабатывает запрос списка промптов"""
        
        async def get_prompts_list(request: Request):
            if not self.prompts:
                return {
                    "prompts": self.fallback_prompts,
                    "fallback": True,
                    "warning": "Using fallback prompts list"
                }
            
            prompts_list = []
            for name in self.prompts.keys():
                prompts_list.append({
                    "name": name,
                    "description": f"Prompt: {name}"
                })
            
            return {"prompts": prompts_list, "fallback": False}
        
        fallback_response = {
            "prompts": self.fallback_prompts,
            "fallback": True
        }
        
        handler = McpEndpointHandler()
        return await handler.handle_request(
            request=request,
            operation_name="prompts_list",
            handler_func=get_prompts_list,
            fallback_response=fallback_response
        )
    
    async def handle_prompt_get(self, request: Request, prompt_name: str) -> Response:
        """Обрабатывает получение промпта"""
        
        async def get_prompt(request: Request):
            if prompt_name not in self.prompts:
                available_prompts = list(self.prompts.keys())
                raise McpPromptNotFoundError(prompt_name, available_prompts)
            
            prompt_func = self.prompts[prompt_name]
            prompt_data = await prompt_func()
            
            return {
                "name": prompt_name,
                "description": prompt_data.get('description', f'Prompt: {prompt_name}'),
                "arguments": prompt_data.get('arguments', []),
                "messages": prompt_data.get('messages', [])
            }
        
        fallback_response = {
            "name": prompt_name,
            "description": f"Prompt {prompt_name} unavailable",
            "arguments": [],
            "messages": [],
            "fallback": True
        }
        
        handler = McpEndpointHandler()
        return await handler.handle_request(
            request=request,
            operation_name=f"prompt_get_{prompt_name}",
            handler_func=get_prompt,
            fallback_response=fallback_response
        )


# Фабрика для создания MCP обработчиков
class McpHandlersFactory:
    """Фабрика для создания и настройки MCP обработчиков"""
    
    def __init__(self, app: FastAPI, default_language: Language = Language.RU):
        self.app = app
        self.default_language = default_language
        self.health_handler = McpHealthHandler()
        self.rpc_handler = McpRpcHandler()
        self.tools_handler = McpToolsHandler()
        self.resources_handler = McpResourcesHandler()
        self.prompts_handler = McpPromptsHandler()
    
    def setup_all_handlers(self):
        """Настраивает все MCP обработчики на FastAPI приложении"""
        
        # Health endpoint
        @self.app.get("/health")
        async def health_check(request: Request):
            return await self.health_handler.handle_health_check(request)
        
        # RPC endpoint
        @self.app.post("/rpc")
        async def rpc_endpoint(request: Request):
            return await self.rpc_handler.handle_rpc_request(request)
        
        # MCP Tools endpoints
        @self.app.get("/mcp/tools/list")
        async def tools_list(request: Request):
            return await self.tools_handler.handle_tools_list(request)
        
        @self.app.post("/mcp/tools/call/{tool_name}")
        async def tool_call(request: Request, tool_name: str):
            return await self.tools_handler.handle_tool_call(request, tool_name)
        
        # MCP Resources endpoints
        @self.app.get("/mcp/resources/list")
        async def resources_list(request: Request):
            return await self.resources_handler.handle_resources_list(request)
        
        @self.app.get("/mcp/resources/read/{resource_uri:path}")
        async def resource_read(request: Request, resource_uri: str):
            return await self.resources_handler.handle_resource_read(request, resource_uri)
        
        # MCP Prompts endpoints
        @self.app.get("/mcp/prompts/list")
        async def prompts_list(request: Request):
            return await self.prompts_handler.handle_prompts_list(request)
        
        @self.app.get("/mcp/prompts/get/{prompt_name}")
        async def prompt_get(request: Request, prompt_name: str):
            return await self.prompts_handler.handle_prompt_get(request, prompt_name)
        
        logger.info("Все MCP обработчики настроены")
        
        return {
            'health': self.health_handler,
            'rpc': self.rpc_handler,
            'tools': self.tools_handler,
            'resources': self.resources_handler,
            'prompts': self.prompts_handler
        }
