
"""
Менеджер graceful degradation для управления уровнями деградации сервисов
"""
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .config import DegradationLevel, GracefulDegradationConfig, get_logger


@dataclass
class ServiceMetrics:
    """Метрики сервиса для принятия решений о деградации"""
    total_requests: int = 0
    failed_requests: int = 0
    success_requests: int = 0
    last_error_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    error_rate: float = 0.0
    
    def add_request(self, success: bool):
        """Добавить информацию о запросе"""
        self.total_requests += 1
        current_time = time.time()
        
        if success:
            self.success_requests += 1
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            self.last_success_time = current_time
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            self.last_error_time = current_time
        
        # Обновляем процент ошибок
        if self.total_requests > 0:
            self.error_rate = (self.failed_requests / self.total_requests) * 100


@dataclass
class FallbackData:
    """Данные fallback для восстановления"""
    data: Any
    timestamp: float
    source: str  # Источник данных (cache, database, etc.)
    expires_at: float
    
    def is_expired(self) -> bool:
        """Проверка, истекли ли данные"""
        return time.time() > self.expires_at


class GracefulDegradationManager:
    """
    Менеджер graceful degradation для автоматического управления уровнями деградации
    
    Уровни деградации:
    - FULL_SERVICE: Полная функциональность
    - CACHED_DATA: Только кэшированные данные  
    - SIMPLIFIED_RESPONSE: Упрощенные ответы
    - MINIMAL_RESPONSE: Минимальная функциональность
    """
    
    def __init__(self, config: GracefulDegradationConfig):
        self.config = config
        self._service_metrics: Dict[str, ServiceMetrics] = defaultdict(ServiceMetrics)
        self._current_levels: Dict[str, DegradationLevel] = {}
        self._fallback_cache: Dict[str, FallbackData] = {}
        self._last_notifications: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._notification_callbacks: List[Callable] = []
        
        self.logger = get_logger()
        self.logger.info("Graceful Degradation Manager инициализирован")
    
    def register_service(self, service_name: str, initial_level: DegradationLevel = DegradationLevel.FULL_SERVICE):
        """Регистрация сервиса в менеджере деградации"""
        with self._lock:
            self._current_levels[service_name] = initial_level
            self.logger.info(f"Сервис '{service_name}' зарегистрирован с уровнем: {initial_level.value}")
    
    def evaluate_request(self, service_name: str, operation: str, success: bool) -> DegradationLevel:
        """
        Оценка запроса и принятие решения об изменении уровня деградации
        
        Args:
            service_name: Имя сервиса
            operation: Тип операции (tools_list, tools_call, resources_read, etc.)
            success: Результат выполнения операции
            
        Returns:
            Текущий уровень деградации сервиса
        """
        with self._lock:
            # Обновляем метрики
            self._service_metrics[service_name].add_request(success)
            
            # Очистка устаревших fallback данных
            self._cleanup_fallback_cache()
            
            # Получаем текущий уровень
            current_level = self._current_levels.get(service_name, DegradationLevel.FULL_SERVICE)
            
            # Анализируем необходимость изменения уровня
            new_level = self._calculate_degradation_level(service_name)
            
            if new_level != current_level:
                self._transition_level(service_name, current_level, new_level, operation)
            
            return new_level
    
    def _calculate_degradation_level(self, service_name: str) -> DegradationLevel:
        """Расчет уровня деградации на основе метрик"""
        metrics = self._service_metrics[service_name]
        
        # Если слишком много подряд идущих ошибок - усиливаем деградацию
        if metrics.consecutive_failures >= self.config.degradation_threshold:
            # Определяем уровень на основе количества ошибок
            if metrics.consecutive_failures >= self.config.degradation_threshold * 3:
                return DegradationLevel.MINIMAL_RESPONSE
            elif metrics.consecutive_failures >= self.config.degradation_threshold * 2:
                return DegradationLevel.SIMPLIFIED_RESPONSE
            else:
                return DegradationLevel.CACHED_DATA
        
        # Если много успешных запросов - уменьшаем деградацию
        if metrics.consecutive_successes >= self.config.recovery_threshold:
            if self._current_levels.get(service_name) == DegradationLevel.MINIMAL_RESPONSE:
                return DegradationLevel.SIMPLIFIED_RESPONSE
            elif self._current_levels.get(service_name) == DegradationLevel.SIMPLIFIED_RESPONSE:
                return DegradationLevel.CACHED_DATA
            elif self._current_levels.get(service_name) == DegradationLevel.CACHED_DATA:
                return DegradationLevel.FULL_SERVICE
        
        return self._current_levels.get(service_name, DegradationLevel.FULL_SERVICE)
    
    def _transition_level(self, service_name: str, old_level: DegradationLevel, 
                         new_level: DegradationLevel, operation: str):
        """Обработка перехода между уровнями деградации"""
        self._current_levels[service_name] = new_level
        
        # Уведомляем об изменении
        self._notify_degradation_change(service_name, old_level, new_level, operation)
        
        # Логируем переход
        self.logger.warning(
            f"Сервис '{service_name}' перешел с уровня {old_level.value} на {new_level.value} "
            f"(операция: {operation})"
        )
        
        # Очищаем метрики при полном восстановлении
        if new_level == DegradationLevel.FULL_SERVICE:
            self._service_metrics[service_name] = ServiceMetrics()
    
    def _notify_degradation_change(self, service_name: str, old_level: DegradationLevel, 
                                  new_level: DegradationLevel, operation: str):
        """Уведомление об изменении уровня деградации"""
        current_time = time.time()
        
        # Проверяем интервал уведомлений
        last_notification = self._last_notifications.get(service_name, 0)
        if current_time - last_notification < self.config.notification_interval:
            return
        
        self._last_notifications[service_name] = current_time
        
        notification = {
            'service': service_name,
            'old_level': old_level.value,
            'new_level': new_level.value,
            'operation': operation,
            'timestamp': current_time,
            'metrics': {
                'consecutive_failures': self._service_metrics[service_name].consecutive_failures,
                'consecutive_successes': self._service_metrics[service_name].consecutive_successes,
                'error_rate': self._service_metrics[service_name].error_rate
            }
        }
        
        # Вызываем callback'и
        for callback in self._notification_callbacks:
            try:
                callback(notification)
            except Exception as e:
                self.logger.error(f"Ошибка в callback уведомления: {e}")
    
    def get_fallback_data(self, service_name: str, operation: str) -> Optional[FallbackData]:
        """Получение fallback данных для операции"""
        cache_key = f"{service_name}:{operation}"
        fallback_data = self._fallback_cache.get(cache_key)
        
        if fallback_data and not fallback_data.is_expired():
            return fallback_data
        
        return None
    
    def store_fallback_data(self, service_name: str, operation: str, data: Any, source: str = "cache"):
        """Сохранение fallback данных"""
        cache_key = f"{service_name}:{operation}"
        expires_at = time.time() + self.config.fallback_cache_ttl
        
        fallback_data = FallbackData(
            data=data,
            timestamp=time.time(),
            source=source,
            expires_at=expires_at
        )
        
        with self._lock:
            self._fallback_cache[cache_key] = fallback_data
    
    def _cleanup_fallback_cache(self):
        """Очистка устаревших fallback данных"""
        with self._lock:
            expired_keys = [
                key for key, data in self._fallback_cache.items()
                if data.is_expired()
            ]
            for key in expired_keys:
                del self._fallback_cache[key]
    
    def get_current_level(self, service_name: str) -> DegradationLevel:
        """Получение текущего уровня деградации сервиса"""
        return self._current_levels.get(service_name, DegradationLevel.FULL_SERVICE)
    
    def get_service_metrics(self, service_name: str) -> ServiceMetrics:
        """Получение метрик сервиса"""
        return self._service_metrics[service_name]
    
    def get_all_levels(self) -> Dict[str, DegradationLevel]:
        """Получение уровней всех сервисов"""
        with self._lock:
            return self._current_levels.copy()
    
    def force_degradation(self, service_name: str, level: DegradationLevel, reason: str = ""):
        """Принудительное установление уровня деградации"""
        old_level = self.get_current_level(service_name)
        self._current_levels[service_name] = level
        
        self.logger.warning(
            f"Принудительная деградация сервиса '{service_name}' с {old_level.value} на {level.value}. "
            f"Причина: {reason}"
        )
        
        self._notify_degradation_change(service_name, old_level, level, f"force: {reason}")
    
    def force_recovery(self, service_name: str, reason: str = ""):
        """Принудительное восстановление сервиса"""
        old_level = self.get_current_level(service_name)
        self.force_degradation(service_name, DegradationLevel.FULL_SERVICE, 
                              f"forced recovery: {reason}")
        
        # Очищаем метрики
        self._service_metrics[service_name] = ServiceMetrics()
    
    def register_notification_callback(self, callback: Callable):
        """Регистрация callback для уведомлений о деградации"""
        self._notification_callbacks.append(callback)
    
    def get_degradation_report(self) -> Dict[str, Any]:
        """Получение отчета о состоянии деградации"""
        with self._lock:
            report = {
                'timestamp': time.time(),
                'total_services': len(self._current_levels),
                'services': {}
            }
            
            for service_name, level in self._current_levels.items():
                metrics = self._service_metrics[service_name]
                report['services'][service_name] = {
                    'degradation_level': level.value,
                    'metrics': {
                        'total_requests': metrics.total_requests,
                        'failed_requests': metrics.failed_requests,
                        'success_requests': metrics.success_requests,
                        'error_rate': metrics.error_rate,
                        'consecutive_failures': metrics.consecutive_failures,
                        'consecutive_successes': metrics.consecutive_successes,
                        'last_error': metrics.last_error_time,
                        'last_success': metrics.last_success_time
                    },
                    'fallback_data_count': sum(
                        1 for key, data in self._fallback_cache.items()
                        if key.startswith(f"{service_name}:") and not data.is_expired()
                    )
                }
            
            return report
    
    def reset_service(self, service_name: str):
        """Сброс сервиса в начальное состояние"""
        with self._lock:
            if service_name in self._current_levels:
                old_level = self._current_levels[service_name]
                self._current_levels[service_name] = DegradationLevel.FULL_SERVICE
                self._service_metrics[service_name] = ServiceMetrics()
                
                # Удаляем fallback данные для сервиса
                keys_to_remove = [
                    key for key in self._fallback_cache.keys()
                    if key.startswith(f"{service_name}:")
                ]
                for key in keys_to_remove:
                    del self._fallback_cache[key]
                
                self.logger.info(f"Сервис '{service_name}' сброшен (был уровень: {old_level.value})")
    
    def clear_all_data(self):
        """Очистка всех данных менеджера"""
        with self._lock:
            self._service_metrics.clear()
            self._current_levels.clear()
            self._fallback_cache.clear()
            self._last_notifications.clear()
            self._notification_callbacks.clear()
            
            self.logger.info("Graceful Degradation Manager сброшен")


class DefaultFallbackHandler:
    """Обработчик fallback по умолчанию для различных типов операций"""
    
    def __init__(self, degradation_manager: GracefulDegradationManager):
        self.degradation_manager = degradation_manager
        self.logger = get_logger()
    
    def handle_tools_list_fallback(self, service_name: str, operation: str) -> Dict[str, Any]:
        """Fallback для tools_list"""
        fallback_data = self.degradation_manager.get_fallback_data(service_name, operation)
        
        if fallback_data:
            return {
                'tools': fallback_data.data.get('tools', []),
                'fallback': True,
                'source': fallback_data.source,
                'timestamp': fallback_data.timestamp
            }
        
        # Возвращаем минимальный список инструментов
        return {
            'tools': [
                {
                    'name': 'basic_tool',
                    'description': 'Базовый инструмент',
                    'inputSchema': {'type': 'object', 'properties': {}}
                }
            ],
            'fallback': True,
            'source': 'minimal',
            'error': 'Сервис недоступен'
        }
    
    def handle_tools_call_fallback(self, service_name: str, operation: str, tool_name: str) -> Dict[str, Any]:
        """Fallback для tools_call"""
        fallback_data = self.degradation_manager.get_fallback_data(service_name, operation)
        
        if fallback_data:
            return {
                'result': fallback_data.data,
                'fallback': True,
                'source': fallback_data.source,
                'timestamp': fallback_data.timestamp
            }
        
        # Минимальный ответ при недоступности
        return {
            'result': f'Инструмент {tool_name} временно недоступен',
            'fallback': True,
            'source': 'minimal',
            'error': 'Сервис недоступен'
        }
    
    def handle_resources_read_fallback(self, service_name: str, operation: str, resource_uri: str) -> Dict[str, Any]:
        """Fallback для resources/read"""
        fallback_data = self.degradation_manager.get_fallback_data(service_name, operation)
        
        if fallback_data:
            return {
                'contents': [{
                    'uri': resource_uri,
                    'mimeType': 'text/plain',
                    'text': fallback_data.data
                }],
                'fallback': True,
                'source': fallback_data.source
            }
        
        # Минимальный ответ
        return {
            'contents': [{
                'uri': resource_uri,
                'mimeType': 'text/plain',
                'text': f'Ресурс {resource_uri} временно недоступен'
            }],
            'fallback': True,
            'source': 'minimal'
        }
    
    def handle_prompts_get_fallback(self, service_name: str, operation: str, prompt_name: str) -> Dict[str, Any]:
        """Fallback для prompts/get"""
        fallback_data = self.degradation_manager.get_fallback_data(service_name, operation)
        
        if fallback_data:
            return {
                'description': fallback_data.data.get('description', 'Сохраненный промпт'),
                'arguments': fallback_data.data.get('arguments', []),
                'fallback': True,
                'source': fallback_data.source
            }
        
        # Минимальный промпт
        return {
            'description': f'Промпт {prompt_name} временно недоступен',
            'arguments': [],
            'fallback': True,
            'source': 'minimal'
        }