
"""
MCP-специфичные исключения для 1С MCP сервера

Ошибки MCP протокола и инструментов:
- Нарушения MCP протокола
- Ошибки инструментов (tools)
- Ошибки ресурсов (resources)
- Ошибки промптов (prompts)
- Ошибки сервера
- Ошибки клиента
- Внутренние ошибки MCP

Основано на спецификации Model Context Protocol (MCP).
"""

from typing import Any, Dict, List, Optional

try:
    from .base import (ErrorSeverity, McpError, NonRecoverableError)
except ImportError:
    from base import (ErrorSeverity, McpError, NonRecoverableError)


class McpProtocolError(McpError):
    """
    Базовый класс ошибок MCP протокола
    
    Используется для ошибок, связанных с нарушением
    спецификации Model Context Protocol.
    """
    
    def __init__(
        self,
        protocol_version: str,
        operation: str,
        protocol_error: str,
        **kwargs
    ):
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        kwargs.setdefault('context_data', {})
        
        kwargs['context_data']['protocol_version'] = protocol_version
        kwargs['context_data']['operation'] = operation
        kwargs['context_data']['protocol_error'] = protocol_error
        
        super().__init__(
            "MCP001",
            "McpProtocolError",
            f"Ошибка MCP протокола v{protocol_version} при операции '{operation}': {protocol_error}",
            **kwargs
        )


class McpToolError(NonRecoverableError):
    """
    Базовый класс ошибок MCP инструментов
    
    Используется для ошибок при выполнении MCP инструментов.
    """
    
    def __init__(
        self,
        tool_name: str,
        operation: str,
        tool_error: str,
        **kwargs
    ):
        kwargs.setdefault('context_data', {})
        
        kwargs['context_data']['tool_name'] = tool_name
        kwargs['context_data']['operation'] = operation
        
        super().__init__(
            "MCP002",
            "McpToolError",
            f"Ошибка инструмента '{tool_name}' при {operation}: {tool_error}",
            **kwargs
        )


class McpResourceError(McpError):
    """
    Базовый класс ошибок MCP ресурсов
    
    Используется для ошибок при работе с MCP ресурсами.
    """
    
    def __init__(
        self,
        resource_uri: str,
        resource_operation: str,
        resource_error: str,
        **kwargs
    ):
        kwargs.setdefault('context_data', {})
        
        kwargs['context_data']['resource_uri'] = resource_uri
        kwargs['context_data']['resource_operation'] = resource_operation
        
        super().__init__(
            "MCP003",
            "McpResourceError",
            f"Ошибка ресурса '{resource_uri}' при {resource_operation}: {resource_error}",
            **kwargs
        )


class McpPromptError(McpError):
    """
    Базовый класс ошибок MCP промптов
    
    Используется для ошибок при работе с MCP промптами.
    """
    
    def __init__(
        self,
        prompt_name: str,
        prompt_error: str,
        **kwargs
    ):
        kwargs.setdefault('context_data', {})
        
        kwargs['context_data']['prompt_name'] = prompt_name
        
        super().__init__(
            "MCP004",
            "McpPromptError",
            f"Ошибка промпта '{prompt_name}': {prompt_error}",
            **kwargs
        )


class McpServerError(McpError):
    """
    Базовый класс ошибок MCP сервера
    
    Используется для внутренних ошибок MCP сервера.
    """
    
    def __init__(self, server_error: str, **kwargs):
        super().__init__(
            "MCP005",
            "McpServerError",
            f"Ошибка MCP сервера: {server_error}",
            **kwargs
        )


class McpClientError(McpError):
    """
    Базовый класс ошибок MCP клиента
    
    Используется для ошибок, связанных с некорректными
    запросами от MCP клиента.
    """
    
    def __init__(self, client_error: str, **kwargs):
        super().__init__(
            "MCP006",
            "McpClientError",
            f"Ошибка MCP клиента: {client_error}",
            **kwargs
        )


# Специфичные ошибки MCP протокола

class InvalidMcpRequestError(McpProtocolError):
    """
    Некорректный запрос MCP
    
    Используется когда запрос клиента не соответствует
    спецификации MCP протокола.
    """
    
    def __init__(
        self,
        protocol_version: str,
        request_type: str,
        validation_error: str,
        **kwargs
    ):
        super().__init__(
            protocol_version,
            "request_validation",
            f"Некорректный запрос типа '{request_type}': {validation_error}",
            **kwargs
        )
        
        self.error_code = "MCP010"


class UnsupportedMcpOperationError(McpProtocolError):
    """
    Неподдерживаемая операция MCP
    
    Используется когда клиент запрашивает операцию,
    которая не поддерживается сервером.
    """
    
    def __init__(
        self,
        protocol_version: str,
        operation: str,
        supported_operations: List[str],
        **kwargs
    ):
        super().__init__(
            protocol_version,
            operation,
            f"Операция не поддерживается. Доступные операции: {', '.join(supported_operations)}",
            **kwargs
        )
        
        self.error_code = "MCP011"
        self.context_data['supported_operations'] = supported_operations


class McpVersionMismatchError(McpProtocolError):
    """
    Несовместимость версий MCP
    
    Используется когда клиент и сервер используют
    несовместимые версии MCP протокола.
    """
    
    def __init__(
        self,
        client_version: str,
        server_version: str,
        supported_versions: List[str],
        **kwargs
    ):
        super().__init__(
            server_version,
            "version_negotiation",
            f"Несовместимость версий: клиент {client_version}, сервер {server_version}",
            **kwargs
        )
        
        self.error_code = "MCP012"
        self.context_data.update({
            'client_version': client_version,
            'supported_versions': supported_versions
        })


class McpJsonRpcError(McpProtocolError):
    """
    Ошибка JSON-RPC в MCP
    
    Используется когда возникают ошибки в JSON-RPC
    протоколе, который использует MCP.
    """
    
    def __init__(
        self,
        protocol_version: str,
        rpc_code: int,
        rpc_message: str,
        rpc_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(
            protocol_version,
            "jsonrpc",
            f"JSON-RPC ошибка {rpc_code}: {rpc_message}",
            **kwargs
        )
        
        self.error_code = "MCP013"
        self.context_data.update({
            'rpc_code': rpc_code,
            'rpc_message': rpc_message,
            'rpc_data': rpc_data
        })


# Специфичные ошибки инструментов

class McpToolNotFoundError(McpToolError):
    """
    Инструмент не найден
    
    Используется когда запрашиваемый инструмент
    не существует на сервере.
    """
    
    def __init__(self, tool_name: str, available_tools: List[str]):
        super().__init__(
            tool_name,
            "execution",
            f"Инструмент не найден. Доступные инструменты: {', '.join(available_tools)}"
        )
        
        self.error_code = "MCP020"
        self.context_data['available_tools'] = available_tools


class McpToolExecutionError(McpToolError):
    """
    Ошибка выполнения инструмента
    
    Используется когда инструмент генерирует исключение
    при выполнении.
    """
    
    def __init__(
        self,
        tool_name: str,
        execution_error: str,
        execution_time: Optional[float] = None,
        **kwargs
    ):
        super().__init__(
            tool_name,
            "execution",
            execution_error
        )
        
        self.error_code = "MCP021"
        self.context_data['execution_time'] = execution_time


class McpToolTimeoutError(McpToolError):
    """
    Таймаут выполнения инструмента
    
    Используется когда инструмент не завершается
    в течение установленного времени.
    """
    
    def __init__(
        self,
        tool_name: str,
        timeout_seconds: float,
        **kwargs
    ):
        super().__init__(
            tool_name,
            "execution",
            f"Превышено время выполнения ({timeout_seconds}s)"
        )
        
        self.error_code = "MCP022"
        self.context_data['timeout_seconds'] = timeout_seconds


class McpToolValidationError(McpToolError):
    """
    Ошибка валидации параметров инструмента
    
    Используется когда параметры инструмента
    не проходят валидацию.
    """
    
    def __init__(
        self,
        tool_name: str,
        parameter_name: str,
        validation_error: str,
        **kwargs
    ):
        super().__init__(
            tool_name,
            "parameter_validation",
            f"Ошибка валидации параметра '{parameter_name}': {validation_error}"
        )
        
        self.error_code = "MCP023"
        self.context_data['parameter_name'] = parameter_name


# Специфичные ошибки ресурсов

class McpResourceNotFoundError(McpResourceError):
    """
    Ресурс не найден
    
    Используется когда запрашиваемый ресурс
    не существует.
    """
    
    def __init__(self, resource_uri: str, available_resources: List[str]):
        super().__init__(
            resource_uri,
            "read",
            f"Ресурс не найден. Доступные ресурсы: {', '.join(available_resources)}"
        )
        
        self.error_code = "MCP030"
        self.context_data['available_resources'] = available_resources


class McpResourceAccessDeniedError(McpResourceError):
    """
    Доступ к ресурсу запрещен
    
    Используется когда клиент не имеет прав
    доступа к ресурсу.
    """
    
    def __init__(
        self,
        resource_uri: str,
        resource_operation: str,
        reason: str,
        **kwargs
    ):
        super().__init__(
            resource_uri,
            resource_operation,
            f"Доступ запрещен: {reason}"
        )
        
        self.error_code = "MCP031"


class McpResourceCorruptedError(McpResourceError):
    """
    Ресурс поврежден
    
    Используется когда ресурс существует,
    но содержит некорректные данные.
    """
    
    def __init__(
        self,
        resource_uri: str,
        corruption_details: str,
        **kwargs
    ):
        super().__init__(
            resource_uri,
            "read",
            f"Ресурс поврежден: {corruption_details}"
        )
        
        self.error_code = "MCP032"
        self.context_data['corruption_details'] = corruption_details


# Специфичные ошибки промптов

class McpPromptNotFoundError(McpPromptError):
    """
    Промпт не найден
    
    Используется когда запрашиваемый промпт
    не существует.
    """
    
    def __init__(self, prompt_name: str, available_prompts: List[str]):
        super().__init__(
            prompt_name,
            f"Промпт не найден. Доступные промпты: {', '.join(available_prompts)}"
        )
        
        self.error_code = "MCP040"
        self.context_data['available_prompts'] = available_prompts


class McpPromptExecutionError(McpPromptError):
    """
    Ошибка выполнения промпта
    
    Используется когда возникают ошибки при
    обработке или выполнении промпта.
    """
    
    def __init__(
        self,
        prompt_name: str,
        execution_error: str,
        **kwargs
    ):
        super().__init__(prompt_name, execution_error)
        self.error_code = "MCP041"


# Внутренние ошибки сервера

class McpInternalServerError(McpServerError):
    """
    Внутренняя ошибка MCP сервера
    
    Используется для неожиданных ошибок сервера,
    которые не подходят под другие категории.
    """
    
    def __init__(
        self,
        server_error: str,
        internal_error_details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(server_error)
        
        self.error_code = "MCP050"
        self.recoverable = False
        self.severity = ErrorSeverity.HIGH
        
        if internal_error_details:
            self.context_data.update(internal_error_details)


class McpServerStartupError(McpServerError):
    """
    Ошибка запуска MCP сервера
    
    Используется когда сервер не может запуститься
    из-за ошибок конфигурации или инициализации.
    """
    
    def __init__(
        self,
        startup_error: str,
        startup_phase: str,
        **kwargs
    ):
        super().__init__(f"Ошибка запуска сервера на этапе '{startup_phase}': {startup_error}")
        
        self.error_code = "MCP051"
        self.recoverable = False
        self.context_data['startup_phase'] = startup_phase


class McpConnectionError(McpServerError):
    """
    Ошибка подключения MCP
    
    Используется когда возникают проблемы
    с подключением клиента к серверу.
    """
    
    def __init__(
        self,
        connection_error: str,
        client_info: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(f"Ошибка подключения: {connection_error}")
        
        self.error_code = "MCP052"
        self.recoverable = True
        
        if client_info:
            self.context_data.update(client_info)


# Ошибки клиента

class McpInvalidRequestError(McpClientError):
    """
    Некорректный запрос клиента
    
    Используется когда запрос клиента имеет
    некорректную структуру или формат.
    """
    
    def __init__(
        self,
        validation_error: str,
        request_preview: Optional[str] = None,
        **kwargs
    ):
        super().__init__(f"Некорректный запрос: {validation_error}")
        
        self.error_code = "MCP060"
        
        if request_preview:
            self.context_data['request_preview'] = request_preview


class McpRateLimitError(McpClientError):
    """
    Превышен лимит запросов клиента
    
    Используется когда клиент превышает
    установленные лимиты запросов.
    """
    
    def __init__(
        self,
        rate_limit_info: Dict[str, Any],
        **kwargs
    ):
        super().__init__(
            f"Превышен лимит запросов: {rate_limit_info.get('message', 'Rate limit exceeded')}"
        )
        
        self.error_code = "MCP061"
        self.recoverable = True
        self.context_data.update(rate_limit_info)


# Фабрика для создания стандартных MCP ошибок
class McpErrorFactory:
    """Фабрика для создания MCP ошибок"""
    
    @staticmethod
    def tool_not_found(tool_name: str, available_tools: List[str]) -> McpToolError:
        """Создает ошибку отсутствующего инструмента"""
        return McpToolNotFoundError(tool_name, available_tools)
    
    @staticmethod
    def resource_not_found(resource_uri: str, available_resources: List[str]) -> McpResourceError:
        """Создает ошибку отсутствующего ресурса"""
        return McpResourceNotFoundError(resource_uri, available_resources)
    
    @staticmethod
    def prompt_not_found(prompt_name: str, available_prompts: List[str]) -> McpPromptError:
        """Создает ошибку отсутствующего промпта"""
        return McpPromptNotFoundError(prompt_name, available_prompts)
    
    @staticmethod
    def version_mismatch(client_version: str, server_version: str) -> McpProtocolError:
        """Создает ошибку несовместимости версий"""
        return McpVersionMismatchError(client_version, server_version, [])