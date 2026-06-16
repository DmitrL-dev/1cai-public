
"""
Транспортные исключения для 1С MCP сервера

Ошибки сетевого взаимодействия (E040-E049):
- Сетевые ошибки подключения
- Таймауты соединения
- Недоступность сервиса
- DNS ошибки
- SSL сертификаты
- Ошибки HTTP запросов
- Rate limiting

Все транспортные ошибки являются восстановимыми и поддерживают
retry логику с экспоненциальным backoff.
"""

from typing import Any, Dict, Optional

try:
    from .base import ErrorSeverity, RecoverableError
except ImportError:
    from base import RecoverableError, ErrorSeverity



class TransportError(RecoverableError):
    """
    Базовый класс транспортных ошибок (E040-E059)
    
    Все транспортные ошибки по умолчанию восстановимы,
    так как могут быть решены повторной попыткой.
    """
    
    def __init__(
        self,
        error_code: str,
        url: str = "",
        method: str = "GET",
        status_code: Optional[int] = None,
        **kwargs
    ):
        kwargs.setdefault('recoverable', True)
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('context_data', {})
        
        # Добавляем информацию о HTTP запросе
        if url or method:
            kwargs['context_data']['url'] = url
            kwargs['context_data']['method'] = method
            kwargs['context_data']['status_code'] = status_code
        
        super().__init__(error_code, "TransportError", **kwargs)


class NetworkError(TransportError):
    """
    Сетевая ошибка (E040)
    
    Используется для общих сетевых ошибок подключения,
    которые не подходят под более специфичные категории.
    """
    
    def __init__(
        self,
        url: str,
        method: str = "GET",
        network_error: Optional[str] = None,
        **kwargs
    ):
        user_message = f"Сетевая ошибка при выполнении {method} {url}"
        if network_error:
            user_message += f": {network_error}"
        
        kwargs.setdefault('error_code', 'E040')
        kwargs.setdefault('context_data', {}).update({
            'network_error': network_error,
            'error_type': 'network'
        })
        
        # Извлекаем error_code из kwargs, чтобы избежать дублирования
        error_code = kwargs.pop('error_code', 'E040')
        
        super().__init__(
            error_code,
            url,
            method,
            user_message=user_message,
            **kwargs
        )


class ConnectionTimeoutError(TransportError):
    """
    Таймаут соединения (E041)
    
    Используется когда превышено время ожидания соединения
    с удаленным сервисом.
    """
    
    def __init__(
        self,
        url: str,
        timeout_seconds: float,
        method: str = "GET",
        **kwargs
    ):
        user_message = (
            f"Таймаут соединения с {url} "
            f"(таймаут: {timeout_seconds}s, метод: {method})"
        )
        
        kwargs.setdefault('error_code', 'E041')
        kwargs['context_data'].update({
            'timeout_seconds': timeout_seconds,
            'error_type': 'connection_timeout'
        })
        
        super().__init__(
            kwargs['error_code'],
            url,
            method,
            user_message=user_message,
            **kwargs
        )


class ServiceUnavailableTransportError(TransportError):
    """
    Сервис недоступен (E042)
    
    Используется когда удаленный сервис недоступен
    или отвечает кодом 503/502.
    """
    
    def __init__(
        self,
        url: str,
        method: str = "GET",
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        user_message = f"Сервис {url} недоступен"
        if status_code:
            user_message += f" (HTTP {status_code})"
        if retry_after:
            user_message += f", повторите через {retry_after} секунд"
        
        kwargs.setdefault('error_code', 'E042')
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        kwargs['context_data'].update({
            'retry_after': retry_after,
            'error_type': 'service_unavailable'
        })
        
        super().__init__(
            kwargs['error_code'],
            url,
            method,
            status_code,
            user_message=user_message,
            **kwargs
        )


class DNSResolutionError(TransportError):
    """
    Ошибка DNS (E043)
    
    Используется когда не удается разрешить доменное имя
    в IP адрес.
    """
    
    def __init__(
        self,
        hostname: str,
        dns_error: Optional[str] = None,
        **kwargs
    ):
        user_message = f"Ошибка разрешения DNS для '{hostname}'"
        if dns_error:
            user_message += f": {dns_error}"
        
        kwargs.setdefault('error_code', 'E043')
        kwargs['context_data'].update({
            'hostname': hostname,
            'dns_error': dns_error,
            'error_type': 'dns_resolution'
        })
        
        # Для DNS ошибок URL может быть недоступен
        super().__init__(
            kwargs['error_code'],
            hostname,
            "",
            user_message=user_message,
            **kwargs
        )


class SSLCertificateError(TransportError):
    """
    Ошибка SSL сертификата (E044)
    
    Используется когда есть проблемы с SSL/TLS сертификатами:
    недействительный сертификат, неподходящий CN, истек срок и т.д.
    """
    
    def __init__(
        self,
        url: str,
        certificate_error: str,
        certificate_details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        user_message = f"Ошибка SSL сертификата для {url}: {certificate_error}"
        
        kwargs.setdefault('error_code', 'E044')
        kwargs['context_data'].update({
            'certificate_error': certificate_error,
            'certificate_details': certificate_details or {},
            'error_type': 'ssl_certificate'
        })
        
        super().__init__(
            kwargs['error_code'],
            url,
            "HTTPS",
            user_message=user_message,
            **kwargs
        )


class RateLimitExceededError(TransportError):
    """
    Превышен лимит запросов (E045)
    
    Используется когда API возвращает код 429 Too Many Requests
    или аналогичный статус rate limiting.
    """
    
    def __init__(
        self,
        url: str,
        method: str = "GET",
        retry_after: Optional[int] = None,
        rate_limit_info: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        user_message = f"Превышен лимит запросов к {url}"
        if retry_after:
            user_message += f", повторите через {retry_after} секунд"
        
        kwargs.setdefault('error_code', 'E045')
        kwargs['context_data'].update({
            'retry_after': retry_after,
            'rate_limit_info': rate_limit_info or {},
            'error_type': 'rate_limit_exceeded'
        })
        
        super().__init__(
            kwargs['error_code'],
            url,
            method,
            429,
            user_message=user_message,
            **kwargs
        )


class HTTPRequestError(TransportError):
    """
    Ошибка HTTP запроса (E046)
    
    Используется для ошибок HTTP протокола,
    которые не подходят под более специфичные категории.
    """
    
    def __init__(
        self,
        url: str,
        method: str,
        status_code: int,
        response_body: Optional[str] = None,
        **kwargs
    ):
        user_message = f"Ошибка HTTP запроса {method} {url}: {status_code}"
        if response_body and len(response_body) < 200:
            user_message += f". Ответ: {response_body}"
        
        kwargs.setdefault('error_code', 'E046')
        kwargs['context_data'].update({
            'response_body': response_body[:500] if response_body else None,
            'error_type': 'http_request'
        })
        
        super().__init__(
            kwargs['error_code'],
            url,
            method,
            status_code,
            user_message=user_message,
            **kwargs
        )


class InvalidURLError(TransportError):
    """
    Неверный URL (E047)
    
    Используется когда URL имеет некорректный формат
    или содержит недопустимые символы.
    """
    
    def __init__(
        self,
        url: str,
        url_error: Optional[str] = None,
        **kwargs
    ):
        user_message = f"Некорректный формат URL: {url}"
        if url_error:
            user_message += f". Ошибка: {url_error}"
        
        kwargs.setdefault('error_code', 'E047')
        kwargs['context_data'].update({
            'url_error': url_error,
            'error_type': 'invalid_url'
        })
        
        super().__init__(
            kwargs['error_code'],
            url,
            "",
            user_message=user_message,
            **kwargs
        )


class ConnectionError(TransportError):
    """
    Ошибка подключения (E048)
    
    Используется когда не удается установить соединение
    с удаленным сервисом.
    """
    
    def __init__(
        self,
        url: str,
        connection_error: str,
        method: str = "GET",
        **kwargs
    ):
        user_message = f"Не удалось подключиться к {url}: {connection_error}"
        
        kwargs.setdefault('error_code', 'E048')
        kwargs['context_data'].update({
            'connection_error': connection_error,
            'error_type': 'connection_failed'
        })
        
        super().__init__(
            kwargs['error_code'],
            url,
            method,
            user_message=user_message,
            **kwargs
        )


class CorruptedResponseError(TransportError):
    """
    Поврежденный ответ (E049)
    
    Используется когда ответ от сервера имеет некорректный формат
    или поврежден.
    """
    
    def __init__(
        self,
        url: str,
        method: str,
        response_headers: Optional[Dict[str, str]] = None,
        content_type_error: Optional[str] = None,
        **kwargs
    ):
        user_message = f"Получен поврежденный ответ от {url}"
        if content_type_error:
            user_message += f": {content_type_error}"
        
        kwargs.setdefault('error_code', 'E049')
        kwargs['context_data'].update({
            'response_headers': response_headers,
            'content_type_error': content_type_error,
            'error_type': 'corrupted_response'
        })
        
        super().__init__(
            kwargs['error_code'],
            url,
            method,
            user_message=user_message,
            **kwargs
        )


class ConnectionPoolError(TransportError):
    """
    Ошибка пула соединений
    
    Используется когда возникают проблемы с пулом HTTP соединений:
    исчерпаны соединения, проблемы с keep-alive и т.д.
    """
    
    def __init__(
        self,
        pool_name: str,
        pool_error: str,
        **kwargs
    ):
        user_message = f"Ошибка пула соединений '{pool_name}': {pool_error}"
        
        kwargs.setdefault('context_data', {})
        kwargs['context_data'].update({
            'pool_name': pool_name,
            'pool_error': pool_error,
            'error_type': 'connection_pool'
        })
        
        super().__init__(
            'E048',
            "",
            user_message=user_message,
            **kwargs
        )


class ProxyError(TransportError):
    """
    Ошибка прокси сервера
    
    Используется когда возникают проблемы с прокси сервером.
    """
    
    def __init__(
        self,
        proxy_url: str,
        target_url: str,
        proxy_error: str,
        **kwargs
    ):
        user_message = f"Ошибка прокси сервера {proxy_url} при обращении к {target_url}: {proxy_error}"
        
        kwargs.setdefault('context_data', {})
        kwargs['context_data'].update({
            'proxy_url': proxy_url,
            'target_url': target_url,
            'proxy_error': proxy_error,
            'error_type': 'proxy_error'
        })
        
        super().__init__(
            'E048',
            target_url,
            user_message=user_message,
            **kwargs
        )


class ChunkedEncodingError(TransportError):
    """
    Ошибка chunked encoding
    
    Используется когда возникают проблемы с chunked transfer encoding.
    """
    
    def __init__(
        self,
        url: str,
        encoding_error: str,
        **kwargs
    ):
        user_message = f"Ошибка chunked encoding для {url}: {encoding_error}"
        
        kwargs.setdefault('context_data', {})
        kwargs['context_data'].update({
            'encoding_error': encoding_error,
            'error_type': 'chunked_encoding'
        })
        
        super().__init__(
            'E049',
            url,
            user_message=user_message,
            **kwargs
        )


class SSLError(TransportError):
    """
    Общая ошибка SSL/TLS
    
    Используется для ошибок SSL протокола,
    не связанных с сертификатами.
    """
    
    def __init__(
        self,
        url: str,
        ssl_error: str,
        **kwargs
    ):
        user_message = f"Ошибка SSL/TLS для {url}: {ssl_error}"
        
        kwargs.setdefault('context_data', {})
        kwargs['context_data'].update({
            'ssl_error': ssl_error,
            'error_type': 'ssl_protocol'
        })
        
        super().__init__(
            'E044',
            url,
            "HTTPS",
            user_message=user_message,
            **kwargs
        )


# Фабрика для создания стандартных транспортных ошибок
class TransportErrorFactory:
    """Фабрика для создания транспортных ошибок"""
    
    @staticmethod
    def timeout(url: str, timeout_seconds: float, method: str = "GET") -> TransportError:
        """Создает ошибку таймаута"""
        return ConnectionTimeoutError(url, timeout_seconds, method)
    
    @staticmethod
    def service_unavailable(
        url: str, 
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None
    ) -> TransportError:
        """Создает ошибку недоступности сервиса"""
        return ServiceUnavailableTransportError(url, "GET", status_code, retry_after)
    
    @staticmethod
    def rate_limit(
        url: str,
        retry_after: Optional[int] = None
    ) -> TransportError:
        """Создает ошибку превышения лимита"""
        return RateLimitExceededError(url, "GET", retry_after)
    
    @staticmethod
    def http_error(
        url: str,
        method: str,
        status_code: int,
        response_body: Optional[str] = None
    ) -> TransportError:
        """Создает ошибку HTTP запроса"""
        return HTTPRequestError(url, method, status_code, response_body)