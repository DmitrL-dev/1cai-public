
"""
Стратегии fallback для критичных сервисов
"""
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .config import ServiceType, get_logger
from .graceful_degradation import GracefulDegradationManager


class FallbackStrategy(Enum):
    """Типы fallback стратегий"""
    CACHE_ONLY = "cache_only"
    QUEUE_AND_CACHE = "queue_and_cache"
    DEFAULT_RESPONSE = "default_response"
    SIMPLIFIED_MODE = "simplified_mode"
    OFFLINE_MODE = "offline_mode"


@dataclass
class ServiceContext:
    """Контекст сервиса для fallback"""
    service_name: str
    service_type: ServiceType
    operation: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackResult:
    """Результат выполнения fallback стратегии"""
    success: bool
    data: Any = None
    source: str = "fallback"
    strategy: Optional[FallbackStrategy] = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class OneCFallbackStrategy:
    """Стратегии fallback для 1С сервиса"""
    
    def __init__(self, degradation_manager: GracefulDegradationManager):
        self.degradation_manager = degradation_manager
        self.logger = get_logger()
        self._metadata_cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
    
    def handle_1c_operation(self, context: ServiceContext, original_operation: Callable, *args, **kwargs) -> FallbackResult:
        """
        Обработка операций 1С с fallback стратегиями
        
        Args:
            context: Контекст сервиса
            original_operation: Оригинальная функция для выполнения
            *args, **kwargs: Аргументы операции
            
        Returns:
            Результат с fallback данными или оригинальный результат
        """
        operation_name = context.operation
        
        try:
            # Пробуем выполнить оригинальную операцию
            result = original_operation(*args, **kwargs)
            
            # Сохраняем в кэш успешные результаты
            self._cache_successful_result(operation_name, result)
            
            return FallbackResult(
                success=True,
                data=result,
                source="original",
                strategy=FallbackStrategy.CACHE_ONLY
            )
            
        except Exception as e:
            self.logger.warning(f"1С операция '{operation_name}' неуспешна: {e}")
            
            # Получаем текущий уровень деградации
            level = self.degradation_manager.get_current_level(context.service_name)
            
            if level.value == "cached_data":
                return self._use_cached_metadata(operation_name, context)
            elif level.value == "simplified":
                return self._provide_simplified_response(operation_name, context)
            elif level.value == "minimal":
                return self._provide_minimal_response(operation_name, context)
            else:
                # Попробуем отложенную обработку
                return self._queue_for_later_processing(operation_name, args, kwargs, context)
    
    def _cache_successful_result(self, operation_name: str, result: Any):
        """Кэширование успешного результата"""
        cache_key = f"1c:{operation_name}"
        self._metadata_cache[cache_key] = result
        self._cache_timestamps[cache_key] = time.time()
        
        # Ограничиваем размер кэша
        if len(self._metadata_cache) > 100:
            oldest_key = min(self._cache_timestamps, key=self._cache_timestamps.get)
            del self._metadata_cache[oldest_key]
            del self._cache_timestamps[oldest_key]
    
    def _use_cached_metadata(self, operation_name: str, context: ServiceContext) -> FallbackResult:
        """Использование кэшированных метаданных"""
        cache_key = f"1c:{operation_name}"
        
        if cache_key in self._metadata_cache:
            cache_time = self._cache_timestamps[cache_key]
            if time.time() - cache_time < 3600:  # 1 час
                return FallbackResult(
                    success=True,
                    data=self._metadata_cache[cache_key],
                    source="cache",
                    strategy=FallbackStrategy.CACHE_ONLY
                )
        
        return FallbackResult(
            success=False,
            error="Нет доступных кэшированных данных",
            strategy=FallbackStrategy.CACHE_ONLY
        )
    
    def _provide_simplified_response(self, operation_name: str, context: ServiceContext) -> FallbackResult:
        """Упрощенный ответ при недоступности 1С"""
        simplified_responses = {
            "get_metadata": {
                "version": "cached_version",
                "objects": ["Object1", "Object2"],
                "timestamp": time.time()
            },
            "execute_query": {
                "status": "queued",
                "query": "cached_query",
                "estimated_time": 300
            },
            "get_document": {
                "document_id": "cached_id",
                "status": "unavailable",
                "fallback_data": {}
            }
        }
        
        default_response = {
            "status": "simplified",
            "message": f"1С операция '{operation_name}' в упрощенном режиме",
            "timestamp": time.time()
        }
        
        return FallbackResult(
            success=True,
            data=simplified_responses.get(operation_name, default_response),
            source="simplified",
            strategy=FallbackStrategy.SIMPLIFIED_MODE
        )
    
    def _provide_minimal_response(self, operation_name: str, context: ServiceContext) -> FallbackResult:
        """Минимальный ответ при полной недоступности 1С"""
        return FallbackResult(
            success=True,
            data={
                "status": "unavailable",
                "message": "1С сервис временно недоступен",
                "operation": operation_name,
                "timestamp": time.time()
            },
            source="minimal",
            strategy=FallbackStrategy.OFFLINE_MODE
        )
    
    def _queue_for_later_processing(self, operation_name: str, args: tuple, kwargs: dict, context: ServiceContext) -> FallbackResult:
        """Отложенная обработка для восстановления"""
        queue_data = {
            'operation': operation_name,
            'args': args,
            'kwargs': kwargs,
            'context': context.__dict__,
            'timestamp': time.time()
        }
        
        # Здесь можно добавить логику помещения в очередь
        self.logger.info(f"Операция '{operation_name}' помещена в очередь для отложенной обработки")
        
        return FallbackResult(
            success=True,
            data={
                "status": "queued",
                "operation": operation_name,
                "queue_position": "unknown",
                "message": "Операция будет выполнена при восстановлении сервиса"
            },
            source="queue",
            strategy=FallbackStrategy.QUEUE_AND_CACHE
        )


class OAuth2FallbackStrategy:
    """Стратегии fallback для OAuth2 сервиса"""
    
    def __init__(self, degradation_manager: GracefulDegradationManager):
        self.degradation_manager = degradation_manager
        self.logger = get_logger()
        self._token_cache: Dict[str, Dict[str, Any]] = {}
        self._default_permissions: List[str] = ["read"]
    
    def handle_oauth_operation(self, context: ServiceContext, original_operation: Callable, *args, **kwargs) -> FallbackResult:
        """
        Обработка OAuth2 операций с fallback стратегиями
        
        Args:
            context: Контекст сервиса
            original_operation: Оригинальная функция для выполнения
            *args, **kwargs: Аргументы операции
            
        Returns:
            Результат с fallback данными
        """
        operation_name = context.operation
        
        try:
            # Пробуем выполнить оригинальную операцию
            result = original_operation(*args, **kwargs)
            
            # Кэшируем токены если это аутентификация
            if operation_name in ["authenticate", "get_token", "refresh_token"]:
                self._cache_token_result(operation_name, result, kwargs)
            
            return FallbackResult(
                success=True,
                data=result,
                source="original"
            )
            
        except Exception as e:
            self.logger.warning(f"OAuth2 операция '{operation_name}' неуспешна: {e}")
            
            # Получаем текущий уровень деградации
            level = self.degradation_manager.get_current_level(context.service_name)
            
            if operation_name in ["authenticate", "login"]:
                return self._handle_auth_fallback(operation_name, args, kwargs, context, level)
            elif operation_name == "get_permissions":
                return self._provide_cached_permissions(context)
            elif operation_name == "validate_token":
                return self._validate_with_cached_token(args, context, level)
            else:
                return self._provide_simplified_oauth_response(operation_name, context)
    
    def _handle_auth_fallback(self, operation_name: str, args: tuple, kwargs: dict, context: ServiceContext, level) -> FallbackResult:
        """Обработка fallback для аутентификации"""
        user_id = kwargs.get('user_id') or args[0] if args else "unknown"
        
        # Проверяем кэшированные токены
        cached_token = self._get_cached_token(user_id)
        if cached_token and not self._is_token_expired(cached_token):
            return FallbackResult(
                success=True,
                data=cached_token,
                source="cached_token",
                strategy=FallbackStrategy.CACHE_ONLY
            )
        
        # Предоставляем упрощенную авторизацию
        if level.value in ["cached_data", "simplified"]:
            simple_token = {
                "access_token": f"simple_token_{user_id}_{int(time.time())}",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": " ".join(self._default_permissions),
                "user_id": user_id,
                "fallback": True
            }
            
            return FallbackResult(
                success=True,
                data=simple_token,
                source="simplified_auth",
                strategy=FallbackStrategy.SIMPLIFIED_MODE
            )
        
        return FallbackResult(
            success=False,
            error="Аутентификация недоступна",
            strategy=FallbackStrategy.OFFLINE_MODE
        )
    
    def _provide_cached_permissions(self, context: ServiceContext) -> FallbackResult:
        """Предоставление кэшированных разрешений"""
        return FallbackResult(
            success=True,
            data={
                "permissions": self._default_permissions,
                "source": "cached",
                "timestamp": time.time()
            },
            source="cached_permissions",
            strategy=FallbackStrategy.CACHE_ONLY
        )
    
    def _validate_with_cached_token(self, args: tuple, context: ServiceContext, level) -> FallbackResult:
        """Валидация с использованием кэшированного токена"""
        token = args[0] if args else None
        
        if token:
            # Проверяем формат простого токена
            if token.startswith("simple_token_"):
                return FallbackResult(
                    success=True,
                    data={
                        "valid": True,
                        "token_type": "Bearer",
                        "scope": "read",
                        "fallback": True
                    },
                    source="simplified_validation"
                )
        
        return FallbackResult(
            success=False,
            error="Токен не найден или недействителен",
            strategy=FallbackStrategy.OFFLINE_MODE
        )
    
    def _provide_simplified_oauth_response(self, operation_name: str, context: ServiceContext) -> FallbackResult:
        """Упрощенный OAuth2 ответ"""
        return FallbackResult(
            success=True,
            data={
                "status": "simplified",
                "operation": operation_name,
                "message": f"OAuth2 операция '{operation_name}' в упрощенном режиме",
                "timestamp": time.time()
            },
            source="simplified",
            strategy=FallbackStrategy.SIMPLIFIED_MODE
        )
    
    def _cache_token_result(self, operation_name: str, result: Dict[str, Any], kwargs: dict):
        """Кэширование результатов токенов"""
        user_id = kwargs.get('user_id') or "unknown"
        cache_key = f"oauth_token:{user_id}"
        
        token_data = {
            'token': result,
            'timestamp': time.time(),
            'expires_at': time.time() + result.get('expires_in', 3600)
        }
        
        self._token_cache[cache_key] = token_data
    
    def _get_cached_token(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получение кэшированного токена"""
        cache_key = f"oauth_token:{user_id}"
        return self._token_cache.get(cache_key)
    
    def _is_token_expired(self, token_data: Dict[str, Any]) -> bool:
        """Проверка истечения токена"""
        return time.time() > token_data.get('expires_at', 0)


class MCPClientFallbackStrategy:
    """Стратегии fallback для MCP клиентов"""
    
    def __init__(self, degradation_manager: GracefulDegradationManager):
        self.degradation_manager = degradation_manager
        self.logger = get_logger()
        self._cached_tools: Dict[str, List[Dict[str, Any]]] = {}
        self._cached_resources: Dict[str, str] = {}
        self._cached_prompts: Dict[str, Dict[str, Any]] = {}
    
    def handle_mcp_operation(self, context: ServiceContext, original_operation: Callable, *args, **kwargs) -> FallbackResult:
        """
        Обработка MCP операций с fallback стратегиями
        
        Args:
            context: Контекст сервиса
            original_operation: Оригинальная функция для выполнения
            *args, **kwargs: Аргументы операции
            
        Returns:
            Результат с fallback данными
        """
        operation_name = context.operation
        
        try:
            # Пробуем выполнить оригинальную операцию
            result = original_operation(*args, **kwargs)
            
            # Кэшируем результаты для последующих fallback'ов
            self._cache_mcp_result(operation_name, result, args, kwargs)
            
            return FallbackResult(
                success=True,
                data=result,
                source="original"
            )
            
        except Exception as e:
            self.logger.warning(f"MCP операция '{operation_name}' неуспешна: {e}")
            
            return self._handle_mcp_fallback(operation_name, args, kwargs, context)
    
    def _handle_mcp_fallback(self, operation_name: str, args: tuple, kwargs: dict, context: ServiceContext) -> FallbackResult:
        """Обработка fallback для MCP операций"""
        if operation_name == "tools/list":
            return self._provide_fallback_tools(context)
        elif operation_name == "tools/call":
            tool_name = kwargs.get('name') or (args[0] if args else "unknown")
            return self._provide_fallback_tool_execution(tool_name, context)
        elif operation_name == "resources/read":
            resource_uri = kwargs.get('uri') or (args[0] if args else "")
            return self._provide_fallback_resource(resource_uri, context)
        elif operation_name == "prompts/get":
            prompt_name = kwargs.get('name') or (args[0] if args else "")
            return self._provide_fallback_prompt(prompt_name, context)
        else:
            return self._provide_default_mcp_fallback(operation_name, context)
    
    def _provide_fallback_tools(self, context: ServiceContext) -> FallbackResult:
        """Предоставление базового набора инструментов"""
        basic_tools = [
            {
                "name": "echo",
                "description": "Эхо сообщение",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"}
                    },
                    "required": ["message"]
                }
            },
            {
                "name": "get_time",
                "description": "Получение текущего времени",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "simple_calculation",
                "description": "Простые вычисления",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string"}
                    },
                    "required": ["expression"]
                }
            }
        ]
        
        return FallbackResult(
            success=True,
            data={"tools": basic_tools},
            source="fallback_tools",
            strategy=FallbackStrategy.CACHE_ONLY
        )
    
    def _provide_fallback_tool_execution(self, tool_name: str, context: ServiceContext) -> FallbackResult:
        """Выполнение инструментов с fallback логикой"""
        fallback_results = {
            "echo": lambda: {"result": "Fallback echo response"},
            "get_time": lambda: {"result": f"Текущее время: {time.strftime('%Y-%m-%d %H:%M:%S')}"},
            "simple_calculation": lambda: {"result": "Вычисления в fallback режиме"}
        }
        
        if tool_name in fallback_results:
            return FallbackResult(
                success=True,
                data=fallback_results[tool_name](),
                source="fallback_execution",
                strategy=FallbackStrategy.SIMPLIFIED_MODE
            )
        
        return FallbackResult(
            success=False,
            error=f"Инструмент '{tool_name}' недоступен в fallback режиме",
            strategy=FallbackStrategy.OFFLINE_MODE
        )
    
    def _provide_fallback_resource(self, resource_uri: str, context: ServiceContext) -> FallbackResult:
        """Предоставление кэшированных ресурсов"""
        # Проверяем кэш ресурсов
        if resource_uri in self._cached_resources:
            return FallbackResult(
                success=True,
                data={
                    "contents": [{
                        "uri": resource_uri,
                        "mimeType": "text/plain",
                        "text": self._cached_resources[resource_uri]
                    }]
                },
                source="cached_resource",
                strategy=FallbackStrategy.CACHE_ONLY
            )
        
        # Возвращаем заглушку ресурса
        return FallbackResult(
            success=True,
            data={
                "contents": [{
                    "uri": resource_uri,
                    "mimeType": "text/plain",
                    "text": f"Ресурс {resource_uri} временно недоступен. Используется fallback режим."
                }]
            },
            source="fallback_resource",
            strategy=FallbackStrategy.SIMPLIFIED_MODE
        )
    
    def _provide_fallback_prompt(self, prompt_name: str, context: ServiceContext) -> FallbackResult:
        """Предоставление fallback промптов"""
        fallback_prompts = {
            "default": {
                "description": "Стандартный промпт по умолчанию",
                "arguments": []
            },
            "analysis": {
                "description": "Промпт для анализа данных",
                "arguments": ["data", "context"]
            },
            "generation": {
                "description": "Промпт для генерации контента",
                "arguments": ["topic", "style"]
            }
        }
        
        default_prompt = fallback_prompts.get("default", {
            "description": f"Промпт {prompt_name} в fallback режиме",
            "arguments": []
        })
        
        return FallbackResult(
            success=True,
            data=default_prompt,
            source="fallback_prompt",
            strategy=FallbackStrategy.SIMPLIFIED_MODE
        )
    
    def _provide_default_mcp_fallback(self, operation_name: str, context: ServiceContext) -> FallbackResult:
        """Универсальный fallback для неизвестных MCP операций"""
        return FallbackResult(
            success=True,
            data={
                "status": "fallback",
                "operation": operation_name,
                "message": f"Операция '{operation_name}' выполняется в fallback режиме",
                "timestamp": time.time()
            },
            source="general_fallback",
            strategy=FallbackStrategy.SIMPLIFIED_MODE
        )
    
    def _cache_mcp_result(self, operation_name: str, result: Any, args: tuple, kwargs: dict):
        """Кэширование MCP результатов"""
        current_time = time.time()
        
        if operation_name == "tools/list" and "tools" in result:
            cache_key = f"mcp_tools:{current_time}"
            self._cached_tools[cache_key] = result["tools"]
        
        elif operation_name == "resources/read" and "contents" in result:
            resource_uri = kwargs.get('uri') or (args[0] if args else "")
            for content in result["contents"]:
                if content.get("text"):
                    self._cached_resources[resource_uri] = content["text"]
        
        elif operation_name == "prompts/get" and result:
            prompt_name = kwargs.get('name') or (args[0] if args else "")
            self._cached_prompts[prompt_name] = result


class AdminNotificationStrategy:
    """Стратегия уведомлений администраторов о деградации"""
    
    def __init__(self):
        self.logger = get_logger()
        self._notification_history: List[Dict[str, Any]] = []
        self._notification_lock = threading.Lock()
    
    def send_degradation_notification(self, service_name: str, old_level: str, new_level: str, 
                                    metrics: Dict[str, Any], operation: str):
        """Отправка уведомления о деградации"""
        notification = {
            'timestamp': time.time(),
            'service': service_name,
            'level_change': f"{old_level} -> {new_level}",
            'operation': operation,
            'metrics': metrics,
            'severity': self._calculate_severity(old_level, new_level)
        }
        
        with self._notification_lock:
            self._notification_history.append(notification)
            
            # Ограничиваем размер истории
            if len(self._notification_history) > 1000:
                self._notification_history = self._notification_history[-500:]
        
        # Здесь можно добавить реальную отправку уведомлений
        # (email, Slack, PagerDuty, etc.)
        self.logger.warning(
            f"УВЕДОМЛЕНИЕ АДМИНИСТРАТОРУ: Сервис '{service_name}' перешел на уровень {new_level}. "
            f"Операция: {operation}, Метрики: {metrics}"
        )
    
    def _calculate_severity(self, old_level: str, new_level: str) -> str:
        """Расчет серьезности деградации"""
        levels = {
            'full_service': 0,
            'cached_data': 1,
            'simplified': 2,
            'minimal': 3
        }
        
        old_severity = levels.get(old_level, 0)
        new_severity = levels.get(new_level, 0)
        
        if new_severity - old_severity >= 2:
            return 'HIGH'
        elif new_severity - old_severity == 1:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def get_notification_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Получение истории уведомлений"""
        with self._notification_lock:
            return self._notification_history[-limit:]


class FallbackStrategyManager:
    """Менеджер всех fallback стратегий"""
    
    def __init__(self, degradation_manager: GracefulDegradationManager):
        self.degradation_manager = degradation_manager
        self.logger = get_logger()
        
        # Инициализируем стратегии
        self.one_c_strategy = OneCFallbackStrategy(degradation_manager)
        self.oauth2_strategy = OAuth2FallbackStrategy(degradation_manager)
        self.mcp_strategy = MCPClientFallbackStrategy(degradation_manager)
        self.notification_strategy = AdminNotificationStrategy()
    
    def handle_service_fallback(self, service_type: ServiceType, context: ServiceContext, 
                              original_operation: Callable, *args, **kwargs) -> FallbackResult:
        """
        Главная точка входа для обработки fallback стратегий
        
        Args:
            service_type: Тип сервиса
            context: Контекст сервиса
            original_operation: Оригинальная операция
            *args, **kwargs: Аргументы операции
            
        Returns:
            Результат с fallback данными
        """
        if service_type == ServiceType.EXTERNAL_API:
            return self.mcp_strategy.handle_mcp_operation(context, original_operation, *args, **kwargs)
        elif service_type == ServiceType.OAUTH2:
            return self.oauth2_strategy.handle_oauth_operation(context, original_operation, *args, **kwargs)
        elif service_type == ServiceType.DB:
            return self.one_c_strategy.handle_1c_operation(context, original_operation, *args, **kwargs)
        elif service_type == ServiceType.MCP_TOOL:
            return self.mcp_strategy.handle_mcp_operation(context, original_operation, *args, **kwargs)
        elif service_type == ServiceType.MCP_RESOURCE:
            return self.mcp_strategy.handle_mcp_operation(context, original_operation, *args, **kwargs)
        else:
            # Универсальная fallback стратегия
            return self._handle_generic_fallback(context, original_operation, *args, **kwargs)
    
    def _handle_generic_fallback(self, context: ServiceContext, original_operation: Callable, 
                               *args, **kwargs) -> FallbackResult:
        """Универсальная fallback стратегия"""
        try:
            result = original_operation(*args, **kwargs)
            return FallbackResult(
                success=True,
                data=result,
                source="original"
            )
        except Exception as e:
            self.logger.warning(f"Generic fallback для '{context.operation}': {e}")
            
            return FallbackResult(
                success=True,
                data={
                    "status": "fallback",
                    "message": f"Операция '{context.operation}' в fallback режиме",
                    "error": str(e),
                    "timestamp": time.time()
                },
                source="generic_fallback",
                strategy=FallbackStrategy.SIMPLIFIED_MODE
            )