
"""
Интеграционные исключения для 1С MCP сервера

Ошибки интеграции с внешними сервисами (E060-E079):
- Недоступность внешних сервисов
- Ошибки авторизации в внешних сервисах
- Некорректные ответы API
- Ошибки сопоставления данных
- Превышение времени ответа
- Ошибки трансляции протокола
- Нарушение контрактов API
- Ошибки версионирования API

Восстановимость зависит от типа ошибки.
"""

from typing import Any, Dict, List, Optional

try:
    from .base import (ErrorSeverity, McpError)
except ImportError:
    from base import (ErrorSeverity, McpError)


class IntegrationError(McpError):
    """
    Базовый класс интеграционных ошибок (E060-E079)
    
    Ошибки интеграции с внешними сервисами и API.
    Восстановимость зависит от конкретного типа ошибки.
    """
    
    def __init__(
        self,
        error_code: str,
        service_name: str,
        api_version: str = "",
        **kwargs
    ):
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('context_data', {})
        
        # Добавляем информацию о внешнем сервисе
        kwargs['context_data']['service_name'] = service_name
        kwargs['context_data']['api_version'] = api_version
        
        super().__init__(error_code, "IntegrationError", **kwargs)


class ExternalServiceUnavailableError(IntegrationError):
    """
    Внешний сервис недоступен (E060)
    
    Используется когда внешний сервис временно или
    постоянно недоступен.
    """
    
    def __init__(
        self,
        service_name: str,
        api_version: str = "",
        service_url: str = "",
        availability_check: bool = False,
        **kwargs
    ):
        user_message = f"Внешний сервис '{service_name}' недоступен"
        if availability_check:
            user_message += ". Проверка доступности не удалась"
        
        kwargs.setdefault('error_code', 'E060')
        kwargs.setdefault('recoverable', True)
        kwargs['context_data'].update({
            'service_url': service_url,
            'availability_check': availability_check
        })
        
        super().__init__(
            kwargs['error_code'],
            service_name,
            api_version,
            user_message=user_message,
            **kwargs
        )


class ExternalServiceAuthError(IntegrationError):
    """
    Ошибка авторизации в внешнем сервисе (E061)
    
    Используется когда внешний сервис отклоняет запрос
    из-за проблем с авторизацией.
    """
    
    def __init__(
        self,
        service_name: str,
        auth_method: str,
        auth_error: str,
        api_version: str = "",
        **kwargs
    ):
        user_message = (
            f"Ошибка авторизации в сервисе '{service_name}' "
            f"(метод: {auth_method}): {auth_error}"
        )
        
        kwargs.setdefault('error_code', 'E061')
        kwargs.setdefault('recoverable', False)
        kwargs['context_data'].update({
            'auth_method': auth_method,
            'auth_error': auth_error
        })
        
        super().__init__(
            kwargs['error_code'],
            service_name,
            api_version,
            user_message=user_message,
            **kwargs
        )


class InvalidExternalServiceResponseError(IntegrationError):
    """
    Некорректный ответ внешнего сервиса (E062)
    
    Используется когда ответ от внешнего сервиса
    имеет неожиданный формат или структуру.
    """
    
    def __init__(
        self,
        service_name: str,
        expected_format: str,
        actual_format: str,
        response_data: Optional[str] = None,
        api_version: str = "",
        **kwargs
    ):
        user_message = (
            f"Некорректный ответ от сервиса '{service_name}': "
            f"ожидался формат {expected_format}, получен {actual_format}"
        )
        
        kwargs.setdefault('error_code', 'E062')
        kwargs['context_data'].update({
            'expected_format': expected_format,
            'actual_format': actual_format,
            'response_preview': response_data[:200] if response_data else None
        })
        
        super().__init__(
            kwargs['error_code'],
            service_name,
            api_version,
            user_message=user_message,
            **kwargs
        )


class DataMappingError(IntegrationError):
    """
    Ошибка сопоставления данных (E063)
    
    Используется когда не удается сопоставить данные
    между системами из-за несовместимости форматов.
    """
    
    def __init__(
        self,
        service_name: str,
        source_field: str,
        target_field: str,
        mapping_error: str,
        source_value: Any = None,
        **kwargs
    ):
        user_message = (
            f"Ошибка сопоставления данных в сервисе '{service_name}': "
            f"поле '{source_field}' не может быть сопоставлено с '{target_field}'. {mapping_error}"
        )
        
        kwargs.setdefault('error_code', 'E063')
        kwargs['context_data'].update({
            'source_field': source_field,
            'target_field': target_field,
            'mapping_error': mapping_error,
            'source_value': source_value
        })
        
        super().__init__(
            kwargs['error_code'],
            service_name,
            user_message=user_message,
            **kwargs
        )


class ExternalServiceTimeoutError(IntegrationError):
    """
    Превышено время ответа внешнего сервиса (E064)
    
    Используется когда внешний сервис не отвечает
    в течение установленного времени ожидания.
    """
    
    def __init__(
        self,
        service_name: str,
        timeout_seconds: float,
        operation: str,
        api_version: str = "",
        **kwargs
    ):
        user_message = (
            f"Превышено время ожидания ответа от сервиса '{service_name}' "
            f"при выполнении операции '{operation}' ({timeout_seconds}s)"
        )
        
        kwargs.setdefault('error_code', 'E064')
        kwargs.setdefault('recoverable', True)
        kwargs['context_data'].update({
            'timeout_seconds': timeout_seconds,
            'operation': operation
        })
        
        super().__init__(
            kwargs['error_code'],
            service_name,
            api_version,
            user_message=user_message,
            **kwargs
        )


class ProtocolTranslationError(IntegrationError):
    """
    Ошибка трансляции протокола (E065)
    
    Используется когда возникают проблемы с преобразованием
    данных между различными протоколами или форматами.
    """
    
    def __init__(
        self,
        source_protocol: str,
        target_protocol: str,
        translation_error: str,
        service_name: str = "",
        **kwargs
    ):
        user_message = (
            f"Ошибка трансляции протокола из '{source_protocol}' в '{target_protocol}': {translation_error}"
        )
        if service_name:
            user_message += f" (сервис: {service_name})"
        
        kwargs.setdefault('error_code', 'E065')
        kwargs['context_data'].update({
            'source_protocol': source_protocol,
            'target_protocol': target_protocol,
            'translation_error': translation_error
        })
        
        super().__init__(
            kwargs['error_code'],
            service_name,
            user_message=user_message,
            **kwargs
        )


class APIContractViolationError(IntegrationError):
    """
    Нарушение контракта API (E066)
    
    Используется когда ответ API не соответствует
    определенному контракту или схеме.
    """
    
    def __init__(
        self,
        service_name: str,
        contract_name: str,
        violation_details: List[Dict[str, Any]],
        api_version: str = "",
        **kwargs
    ):
        violation_messages = [v.get('message', str(v)) for v in violation_details]
        user_message = (
            f"Нарушение контракта API '{contract_name}' в сервисе '{service_name}': "
            + "; ".join(violation_messages)
        )
        
        kwargs.setdefault('error_code', 'E066')
        kwargs['context_data'].update({
            'contract_name': contract_name,
            'violation_details': violation_details
        })
        
        super().__init__(
            kwargs['error_code'],
            service_name,
            api_version,
            user_message=user_message,
            **kwargs
        )


class APIVersioningError(IntegrationError):
    """
    Ошибка версионирования API (E067)
    
    Используется когда возникают проблемы с версиями API:
    несовместимые версии, устаревшие endpoint'ы и т.д.
    """
    
    def __init__(
        self,
        service_name: str,
        current_version: str,
        required_version: str,
        version_error: str,
        **kwargs
    ):
        user_message = (
            f"Ошибка версионирования API сервиса '{service_name}': "
            f"требуется версия {required_version}, доступна {current_version}. {version_error}"
        )
        
        kwargs.setdefault('error_code', 'E067')
        kwargs['context_data'].update({
            'current_version': current_version,
            'required_version': required_version,
            'version_error': version_error
        })
        
        super().__init__(
            kwargs['error_code'],
            service_name,
            current_version,
            user_message=user_message,
            **kwargs
        )


class DataMarshallingError(IntegrationError):
    """
    Ошибка маршалинга данных (E068)
    
    Используется когда не удается преобразовать данные
    для передачи через границу системы.
    """
    
    def __init__(
        self,
        service_name: str,
        data_type: str,
        marshalling_error: str,
        source_data: Any = None,
        **kwargs
    ):
        user_message = (
            f"Ошибка маршалинга данных типа '{data_type}' "
            f"для сервиса '{service_name}': {marshalling_error}"
        )
        
        kwargs.setdefault('error_code', 'E068')
        kwargs['context_data'].update({
            'data_type': data_type,
            'marshalling_error': marshalling_error,
            'source_data_preview': str(source_data)[:100] if source_data else None
        })
        
        super().__init__(
            kwargs['error_code'],
            service_name,
            user_message=user_message,
            **kwargs
        )


class APICompatibilityError(IntegrationError):
    """
    Несовместимость версий API (E069)
    
    Используется когда клиент и сервис используют
    несовместимые версии API.
    """
    
    def __init__(
        self,
        service_name: str,
        client_version: str,
        server_version: str,
        compatibility_info: Dict[str, Any],
        **kwargs
    ):
        user_message = (
            f"Несовместимость версий API сервиса '{service_name}': "
            f"клиент {client_version}, сервер {server_version}"
        )
        
        kwargs.setdefault('error_code', 'E069')
        kwargs['context_data'].update({
            'client_version': client_version,
            'server_version': server_version,
            'compatibility_info': compatibility_info
        })
        
        super().__init__(
            kwargs['error_code'],
            service_name,
            server_version,
            user_message=user_message,
            **kwargs
        )


class ServiceConfigurationError(IntegrationError):
    """
    Ошибка конфигурации сервиса
    
    Используется когда конфигурация интеграции
    с внешним сервисом некорректна.
    """
    
    def __init__(
        self,
        service_name: str,
        config_parameter: str,
        config_value: Any,
        config_error: str,
        **kwargs
    ):
        user_message = (
            f"Ошибка конфигурации сервиса '{service_name}': "
            f"параметр '{config_parameter}' = {config_value}. {config_error}"
        )
        
        kwargs.setdefault('recoverable', False)
        kwargs['context_data'].update({
            'config_parameter': config_parameter,
            'config_value': config_value,
            'config_error': config_error
        })
        
        super().__init__(
            'E066',
            service_name,
            user_message=user_message,
            **kwargs
        )


class RateLimitIntegrationError(IntegrationError):
    """
    Ошибка rate limiting интеграции
    
    Используется когда внешний сервис ограничивает
    количество запросов.
    """
    
    def __init__(
        self,
        service_name: str,
        limit_type: str,
        limit_value: int,
        window_seconds: int,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        user_message = (
            f"Превышен лимит {limit_type} для сервиса '{service_name}': "
            f"{limit_value} запросов за {window_seconds} секунд"
        )
        if retry_after:
            user_message += f", повторите через {retry_after} секунд"
        
        kwargs.setdefault('recoverable', True)
        kwargs['context_data'].update({
            'limit_type': limit_type,
            'limit_value': limit_value,
            'window_seconds': window_seconds,
            'retry_after': retry_after
        })
        
        super().__init__(
            'E045',
            service_name,
            user_message=user_message,
            **kwargs
        )


class WebhookError(IntegrationError):
    """
    Ошибка webhook интеграции
    
    Используется когда возникают проблемы с webhook'ами:
    доставка уведомлений, подтверждения и т.д.
    """
    
    def __init__(
        self,
        service_name: str,
        webhook_url: str,
        webhook_event: str,
        delivery_error: str,
        **kwargs
    ):
        user_message = (
            f"Ошибка доставки webhook '{webhook_event}' "
            f"в сервис '{service_name}': {delivery_error}"
        )
        
        kwargs['context_data'].update({
            'webhook_url': webhook_url,
            'webhook_event': webhook_event,
            'delivery_error': delivery_error
        })
        
        super().__init__(
            'E062',
            service_name,
            user_message=user_message,
            **kwargs
        )


class OAuth2Error(IntegrationError):
    """
    Ошибка OAuth2 авторизации
    
    Используется когда возникают проблемы с OAuth2
    авторизацией в внешних сервисах.
    """
    
    def __init__(
        self,
        service_name: str,
        oauth2_error: str,
        error_description: str,
        **kwargs
    ):
        user_message = (
            f"Ошибка OAuth2 авторизации в сервисе '{service_name}': "
            f"{oauth2_error} - {error_description}"
        )
        
        kwargs.setdefault('recoverable', False)
        kwargs['context_data'].update({
            'oauth2_error': oauth2_error,
            'error_description': error_description
        })
        
        super().__init__(
            'E061',
            service_name,
            user_message=user_message,
            **kwargs
        )


class SOAPError(IntegrationError):
    """
    Ошибка SOAP интеграции
    
    Используется когда возникают проблемы с SOAP веб-сервисами.
    """
    
    def __init__(
        self,
        service_name: str,
        soap_operation: str,
        soap_fault: str,
        **kwargs
    ):
        user_message = (
            f"Ошибка SOAP операции '{soap_operation}' "
            f"в сервисе '{service_name}': {soap_fault}"
        )
        
        kwargs['context_data'].update({
            'soap_operation': soap_operation,
            'soap_fault': soap_fault
        })
        
        super().__init__(
            'E062',
            service_name,
            user_message=user_message,
            **kwargs
        )


# Фабрика для создания стандартных интеграционных ошибок
class IntegrationErrorFactory:
    """Фабрика для создания интеграционных ошибок"""
    
    @staticmethod
    def service_unavailable(service_name: str, service_url: str = "") -> IntegrationError:
        """Создает ошибку недоступности сервиса"""
        return ExternalServiceUnavailableError(service_name, service_url=service_url)
    
    @staticmethod
    def auth_error(service_name: str, auth_method: str, auth_error: str) -> IntegrationError:
        """Создает ошибку авторизации"""
        return ExternalServiceAuthError(service_name, auth_method, auth_error)
    
    @staticmethod
    def timeout(service_name: str, operation: str, timeout_seconds: float) -> IntegrationError:
        """Создает ошибку таймаута"""
        return ExternalServiceTimeoutError(service_name, timeout_seconds, operation)
    
    @staticmethod
    def version_mismatch(
        service_name: str,
        client_version: str,
        server_version: str
    ) -> IntegrationError:
        """Создает ошибку несовместимости версий"""
        return APICompatibilityError(service_name, client_version, server_version, {})