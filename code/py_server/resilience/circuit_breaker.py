
"""
Реализация паттерна Circuit Breaker
"""
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

from .config import CircuitBreakerConfig, get_logger


class CircuitBreakerState(Enum):
    """Состояния circuit breaker"""
    CLOSED = auto()     # Нормальная работа
    OPEN = auto()       # Блокировка запросов
    HALF_OPEN = auto()  # Тестирование восстановления


@dataclass
class CircuitBreakerStats:
    """Статистика circuit breaker"""
    failure_count: int = 0
    success_count: int = 0
    total_requests: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_transitions: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_request(self, success: bool):
        """Добавить информацию о запросе"""
        self.total_requests += 1
        current_time = time.time()
        
        if success:
            self.success_count += 1
            self.last_success_time = current_time
        else:
            self.failure_count += 1
            self.last_failure_time = current_time
    
    def get_success_rate(self) -> float:
        """Получить процент успешных запросов"""
        if self.total_requests == 0:
            return 0.0
        return (self.success_count / self.total_requests) * 100


class CircuitBreaker:
    """
    Реализация паттерна Circuit Breaker для защиты от каскадных отказов
    
    Состояния:
    - CLOSED: Нормальная работа, все запросы проходят
    - OPEN: Слишком много ошибок, запросы блокируются
    - HALF_OPEN: Тестирование восстановления, часть запросов пропускается
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.stats = CircuitBreakerStats()
        self._lock = threading.Lock()
        self._failure_times: deque = deque()
        self._success_times: deque = deque()
        self._half_open_start: Optional[float] = None
        self._cache: Dict[str, tuple] = {}
        self._cache_times: Dict[str, float] = {}
        
        self.logger = get_logger()
        self.logger.info(f"Circuit Breaker '{self.name}' инициализирован")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Вызов функции через circuit breaker
        
        Args:
            func: Функция для выполнения
            *args, **kwargs: Аргументы функции
            
        Returns:
            Результат выполнения функции
            
        Raises:
            Exception: Если circuit breaker OPEN или ошибка функции
        """
        if self._should_block():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' в состоянии OPEN"
            )
        
        try:
            # Проверяем кэш если включен
            cache_key = self._make_cache_key(func, args, kwargs)
            if self.config.enable_caching and cache_key in self._cache:
                cached_result, cached_time = self._cache[cache_key]
                if time.time() - cached_time < self.config.cache_ttl:
                    self.logger.debug(f"Cache hit для '{self.name}'")
                    return cached_result
            
            # Выполняем функцию
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            self._on_success(execution_time)
            
            # Кэшируем результат
            if self.config.enable_caching:
                self._cache[cache_key] = (result, time.time())
                self._cleanup_cache()
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time if 'start_time' in locals() else 0
            self._on_failure(e, execution_time)
            raise
    
    def _should_block(self) -> bool:
        """Проверка, нужно ли блокировать запрос"""
        with self._lock:
            current_time = time.time()
            
            # Очищаем устаревшие записи
            self._cleanup_times()
            
            if self.state == CircuitBreakerState.CLOSED:
                return False
            
            elif self.state == CircuitBreakerState.OPEN:
                # Проверяем, прошел ли таймаут
                if (self.stats.last_failure_time and 
                    current_time - self.stats.last_failure_time >= self.config.timeout):
                    self._transition_to_half_open()
                    return False
                return True
            
            elif self.state == CircuitBreakerState.HALF_OPEN:
                # Проверяем длительность тестирования
                if (self._half_open_start and 
                    current_time - self._half_open_start >= self.config.half_open_duration):
                    # Время тестирования истекло, переходим в OPEN
                    self._transition_to_open("Время тестирования истекло")
                    return True
                return False
            
            return False
    
    def _on_success(self, execution_time: float = 0):
        """Обработка успешного выполнения"""
        with self._lock:
            self.stats.add_request(True)
            self._success_times.append(time.time())
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.stats.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
                else:
                    # Продолжаем тестирование
                    self.logger.debug(f"Тестирование продолжается: {self.stats.success_count}/{self.config.success_threshold}")
            
            # Логирование успешной операции
            self.logger.debug(f"Успех в '{self.name}' (время: {execution_time:.3f}s)")
    
    def _on_failure(self, exception: Exception, execution_time: float = 0):
        """Обработка неудачного выполнения"""
        with self._lock:
            self.stats.add_request(False)
            self._failure_times.append(time.time())
            
            # Определяем, является ли исключение критичным
            is_critical_failure = any(
                isinstance(exception, exc_type) 
                for exc_type in self.config.failure_exceptions
            )
            
            if is_critical_failure:
                # Критичные ошибки считаются для circuit breaker
                if self.state == CircuitBreakerState.HALF_OPEN:
                    self._transition_to_open("Критичная ошибка в HALF_OPEN")
                elif self.state == CircuitBreakerState.CLOSED:
                    # Проверяем пороговое значение
                    if self._get_recent_failure_count() >= self.config.failure_threshold:
                        self._transition_to_open("Превышен порог ошибок")
            
            # Логирование ошибки
            self.logger.warning(
                f"Ошибка в '{self.name}': {type(exception).__name__}: {exception} "
                f"(время: {execution_time:.3f}s, состояние: {self.state.name})"
            )
    
    def _get_recent_failure_count(self) -> int:
        """Получить количество недавних ошибок"""
        current_time = time.time()
        cutoff_time = current_time - self.config.time_window
        return sum(1 for t in self._failure_times if t >= cutoff_time)
    
    def _transition_to_open(self, reason: str):
        """Переход в состояние OPEN"""
        old_state = self.state
        self.state = CircuitBreakerState.OPEN
        self._record_transition(old_state, CircuitBreakerState.OPEN, reason)
        self.logger.warning(f"Circuit breaker '{self.name}' перешел в OPEN: {reason}")
    
    def _transition_to_half_open(self):
        """Переход в состояние HALF_OPEN"""
        old_state = self.state
        self.state = CircuitBreakerState.HALF_OPEN
        self.stats.success_count = 0
        self.stats.failure_count = 0
        self._half_open_start = time.time()
        self._record_transition(old_state, CircuitBreakerState.HALF_OPEN, "Автоматический переход")
        self.logger.info(f"Circuit breaker '{self.name}' перешел в HALF_OPEN")
    
    def _transition_to_closed(self):
        """Переход в состояние CLOSED"""
        old_state = self.state
        self.state = CircuitBreakerState.CLOSED
        self.stats.success_count = 0
        self._half_open_start = None
        self._record_transition(old_state, CircuitBreakerState.CLOSED, "Восстановление")
        self.logger.info(f"Circuit breaker '{self.name}' восстановился (CLOSED)")
    
    def _record_transition(self, from_state: CircuitBreakerState, to_state: CircuitBreakerState, reason: str):
        """Записать переход состояния"""
        transition = {
            'timestamp': time.time(),
            'from': from_state.name,
            'to': to_state.name,
            'reason': reason,
            'stats': {
                'total_requests': self.stats.total_requests,
                'failures': self.stats.failure_count,
                'successes': self.stats.success_count
            }
        }
        self.stats.state_transitions.append(transition)
    
    def _cleanup_times(self):
        """Очистка устаревших записей времени"""
        current_time = time.time()
        cutoff_time = current_time - self.config.time_window
        
        while self._failure_times and self._failure_times[0] < cutoff_time:
            self._failure_times.popleft()
        
        while self._success_times and self._success_times[0] < cutoff_time:
            self._success_times.popleft()
    
    def _cleanup_cache(self):
        """Очистка устаревшего кэша"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.config.cache_ttl
        ]
        for key in expired_keys:
            self._cache.pop(key, None)
            self._cache_times.pop(key, None)
    
    def _make_cache_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """Создание ключа кэша"""
        import hashlib
        import pickle
        
        key_data = {
            'func': func.__name__,
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_bytes = pickle.dumps(key_data)
        return hashlib.md5(key_bytes).hexdigest()[:16]
    
    def get_state(self) -> Dict[str, Any]:
        """Получение текущего состояния circuit breaker"""
        with self._lock:
            return {
                'name': self.name,
                'state': self.state.name,
                'stats': {
                    'total_requests': self.stats.total_requests,
                    'success_count': self.stats.success_count,
                    'failure_count': self.stats.failure_count,
                    'success_rate': self.stats.get_success_rate(),
                    'last_success': self.stats.last_success_time,
                    'last_failure': self.stats.last_failure_time
                },
                'recent_failures': self._get_recent_failure_count(),
                'transitions_count': len(self.stats.state_transitions)
            }
    
    def reset(self):
        """Сброс circuit breaker в начальное состояние"""
        with self._lock:
            old_state = self.state
            self.state = CircuitBreakerState.CLOSED
            self.stats = CircuitBreakerStats()
            self._failure_times.clear()
            self._success_times.clear()
            self._half_open_start = None
            self._cache.clear()
            self._cache_times.clear()
            self._record_transition(old_state, CircuitBreakerState.CLOSED, "Ручной сброс")
            self.logger.info(f"Circuit breaker '{self.name}' сброшен")


class CircuitBreakerOpenError(Exception):
    """Исключение при открытом circuit breaker"""


class CircuitBreakerManager:
    """Менеджер множественных circuit breaker'ов"""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        self.logger = get_logger()
    
    def get_breaker(self, name: str, config: CircuitBreakerConfig) -> CircuitBreaker:
        """Получение или создание circuit breaker"""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
                self.logger.info(f"Создан новый circuit breaker: {name}")
            return self._breakers[name]
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Получение состояния всех circuit breaker'ов"""
        with self._lock:
            return {name: breaker.get_state() for name, breaker in self._breakers.items()}
    
    def reset_breaker(self, name: str):
        """Сброс конкретного circuit breaker"""
        with self._lock:
            if name in self._breakers:
                self._breakers[name].reset()
    
    def reset_all(self):
        """Сброс всех circuit breaker'ов"""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()