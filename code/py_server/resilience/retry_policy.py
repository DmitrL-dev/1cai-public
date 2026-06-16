
"""
Политики ретраев с экспоненциальной задержкой и джиттером
"""
import asyncio
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

from .config import RetryPolicyConfig, get_logger


class RetryResult(Enum):
    """Результат попытки ретрая"""
    SUCCESS = auto()
    RETRY = auto()
    STOP = auto()


@dataclass
class RetryAttempt:
    """Информация о попытке ретрая"""
    attempt_number: int
    start_time: float
    delay: float
    exception: Optional[Exception] = None
    success: bool = False
    elapsed_time: float = 0.0


@dataclass
class RetryStats:
    """Статистика попыток ретрая"""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_time: float = 0.0
    attempts: List[RetryAttempt] = field(default_factory=list)
    
    def add_attempt(self, attempt: RetryAttempt):
        """Добавить информацию о попытке"""
        self.attempts.append(attempt)
        self.total_attempts += 1
        
        if attempt.success:
            self.successful_attempts += 1
        else:
            self.failed_attempts += 1
        
        self.total_time = time.time() - self.attempts[0].start_time if self.attempts else 0.0
    
    def get_success_rate(self) -> float:
        """Получить процент успешных попыток"""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_attempts / self.total_attempts) * 100
    
    def get_average_delay(self) -> float:
        """Получить среднюю задержку между попытками"""
        if len(self.attempts) <= 1:
            return 0.0
        
        total_delay = sum(attempt.delay for attempt in self.attempts[1:])
        return total_delay / (len(self.attempts) - 1)


class RetryPolicy:
    """
    Политика ретраев с экспоненциальной задержкой и джиттером
    
    Поддерживает:
    - Экспоненциальная задержка: base_delay * (2 ^ attempt_number)
    - Джиттер для избежания синхронизации запросов
    - Конфигурируемые исключения для ретраев
    - Синхронные и асинхронные функции
    """
    
    def __init__(self, config: RetryPolicyConfig, name: str = "default"):
        self.config = config
        self.name = name
        self.stats = RetryStats()
        self._lock = threading.Lock()
        
        self.logger = get_logger()
        self.logger.info(f"Retry Policy '{name}' инициализирован")
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполнение функции с политикой ретраев (синхронная версия)
        
        Args:
            func: Функция для выполнения
            *args, **kwargs: Аргументы функции
            
        Returns:
            Результат выполнения функции
            
        Raises:
            Exception: Последнее исключение при превышении лимита попыток
        """
        start_time = time.time()
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            attempt_start = time.time()
            
            try:
                # Выполняем функцию
                result = func(*args, **kwargs)
                
                # Успех - записываем статистику
                attempt = RetryAttempt(
                    attempt_number=attempt,
                    start_time=start_time,
                    delay=self._calculate_delay(attempt),
                    success=True,
                    elapsed_time=time.time() - attempt_start
                )
                
                with self._lock:
                    self.stats.add_attempt(attempt)
                
                self.logger.debug(f"Попытка {attempt} в '{self.name}' успешна")
                return result
                
            except Exception as e:
                last_exception = e
                
                # Определяем, нужно ли делать ретрай
                should_retry = self._should_retry(e, attempt)
                
                if not should_retry or attempt == self.config.max_attempts:
                    # Не нужно ретраить или это последняя попытка
                    attempt = RetryAttempt(
                        attempt_number=attempt,
                        start_time=start_time,
                        delay=self._calculate_delay(attempt),
                        exception=e,
                        success=False,
                        elapsed_time=time.time() - attempt_start
                    )
                    
                    with self._lock:
                        self.stats.add_attempt(attempt)
                    
                    self.logger.warning(
                        f"Попытка {attempt} в '{self.name}' неуспешна: {type(e).__name__}: {e}"
                    )
                    break
                
                # Вычисляем задержку и ждем
                delay = self._calculate_delay(attempt)
                
                attempt = RetryAttempt(
                    attempt_number=attempt,
                    start_time=start_time,
                    delay=delay,
                    exception=e,
                    success=False,
                    elapsed_time=time.time() - attempt_start
                )
                
                with self._lock:
                    self.stats.add_attempt(attempt)
                
                self.logger.warning(
                    f"Попытка {attempt} в '{self.name}' неуспешна: {type(e).__name__}: {e}. "
                    f"Ретра через {delay:.3f}s"
                )
                
                time.sleep(delay)
        
        # Все попытки исчерпаны
        self.logger.error(
            f"Все попытки исчерпаны в '{self.name}' после {self.stats.total_attempts} попыток"
        )
        raise last_exception
    
    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполнение функции с политикой ретраев (асинхронная версия)
        
        Args:
            func: Асинхронная функция для выполнения
            *args, **kwargs: Аргументы функции
            
        Returns:
            Результат выполнения функции
            
        Raises:
            Exception: Последнее исключение при превышении лимита попыток
        """
        start_time = time.time()
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            attempt_start = time.time()
            
            try:
                # Выполняем асинхронную функцию
                result = await func(*args, **kwargs)
                
                # Успех - записываем статистику
                attempt_info = RetryAttempt(
                    attempt_number=attempt,
                    start_time=start_time,
                    delay=self._calculate_delay(attempt),
                    success=True,
                    elapsed_time=time.time() - attempt_start
                )
                
                with self._lock:
                    self.stats.add_attempt(attempt_info)
                
                self.logger.debug(f"Асинхронная попытка {attempt} в '{self.name}' успешна")
                return result
                
            except Exception as e:
                last_exception = e
                
                # Определяем, нужно ли делать ретрай
                should_retry = self._should_retry(e, attempt)
                
                if not should_retry or attempt == self.config.max_attempts:
                    # Не нужно ретраить или это последняя попытка
                    attempt_info = RetryAttempt(
                        attempt_number=attempt,
                        start_time=start_time,
                        delay=self._calculate_delay(attempt),
                        exception=e,
                        success=False,
                        elapsed_time=time.time() - attempt_start
                    )
                    
                    with self._lock:
                        self.stats.add_attempt(attempt_info)
                    
                    self.logger.warning(
                        f"Асинхронная попытка {attempt} в '{self.name}' неуспешна: {type(e).__name__}: {e}"
                    )
                    break
                
                # Вычисляем задержку и ждем
                delay = self._calculate_delay(attempt)
                
                attempt_info = RetryAttempt(
                    attempt_number=attempt,
                    start_time=start_time,
                    delay=delay,
                    exception=e,
                    success=False,
                    elapsed_time=time.time() - attempt_start
                )
                
                with self._lock:
                    self.stats.add_attempt(attempt_info)
                
                self.logger.warning(
                    f"Асинхронная попытка {attempt} в '{self.name}' неуспешна: {type(e).__name__}: {e}. "
                    f"Ретра через {delay:.3f}s"
                )
                
                await asyncio.sleep(delay)
        
        # Все попытки исчерпаны
        self.logger.error(
            f"Все асинхронные попытки исчерпаны в '{self.name}' после {self.stats.total_attempts} попыток"
        )
        raise last_exception
    
    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Определение, нужно ли делать ретрай для данного исключения
        
        Args:
            exception: Исключение для анализа
            attempt: Номер текущей попытки
            
        Returns:
            True, если ретрай необходим
        """
        # Проверяем на невозможные для ретрая исключения
        for exc_type in self.config.non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False
        
        # Проверяем на возможные для ретрая исключения
        for exc_type in self.config.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True
        
        # Если исключение не в списках, считаем что ретрай возможен
        return True
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Вычисление задержки для попытки
        
        Args:
            attempt: Номер попытки
            
        Returns:
            Время задержки в секундах
        """
        if attempt <= 1:
            return 0.0
        
        # Базовая экспоненциальная задержка
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        
        # Ограничиваем максимальной задержкой
        delay = min(delay, self.config.max_delay)
        
        # Добавляем джиттер если включен
        if self.config.jitter:
            jitter_range = delay * self.config.jitter_range
            jitter = random.uniform(-jitter_range, jitter_range)
            delay += jitter
        
        # Убеждаемся что задержка не отрицательная
        return max(0.0, delay)
    
    def get_stats(self) -> RetryStats:
        """Получение статистики ретраев"""
        with self._lock:
            return self.stats
    
    def reset_stats(self):
        """Сброс статистики ретраев"""
        with self._lock:
            self.stats = RetryStats()
            self.logger.info(f"Статистика ретраев сброшена для '{self.name}'")
    
    def get_recommended_delay(self) -> float:
        """Получение рекомендуемой задержки для следующей попытки"""
        if self.stats.total_attempts == 0:
            return self.config.base_delay
        
        return self._calculate_delay(self.stats.total_attempts + 1)


class RetryPolicyManager:
    """Менеджер множественных политик ретраев"""
    
    def __init__(self):
        self._policies: Dict[str, RetryPolicy] = {}
        self._lock = threading.Lock()
        self.logger = get_logger()
    
    def get_policy(self, name: str, config: RetryPolicyConfig = None) -> RetryPolicy:
        """
        Получение или создание политики ретраев
        
        Args:
            name: Имя политики
            config: Конфигурация политики (опциональная)
            
        Returns:
            Политика ретраев
        """
        with self._lock:
            if name not in self._policies:
                if config is None:
                    config = RetryPolicyConfig()
                self._policies[name] = RetryPolicy(config, name)
                self.logger.info(f"Создана новая политика ретраев: {name}")
            
            return self._policies[name]
    
    def get_all_stats(self) -> Dict[str, RetryStats]:
        """Получение статистики всех политик"""
        with self._lock:
            return {name: policy.get_stats() for name, policy in self._policies.items()}
    
    def reset_all_stats(self):
        """Сброс статистики всех политик"""
        with self._lock:
            for policy in self._policies.values():
                policy.reset_stats()
            self.logger.info("Статистика всех политик ретраев сброшена")
    
    def remove_policy(self, name: str):
        """Удаление политики ретраев"""
        with self._lock:
            if name in self._policies:
                del self._policies[name]
                self.logger.info(f"Политика ретраев удалена: {name}")


# Декораторы для удобного использования
def retry(config: RetryPolicyConfig = None, policy_name: str = "decorated"):
    """Декоратор для автоматического применения ретраев"""
    def decorator(func):
        policy = RetryPolicy(config or RetryPolicyConfig(), policy_name)
        
        def wrapper(*args, **kwargs):
            return policy.execute(func, *args, **kwargs)
        
        async def async_wrapper(*args, **kwargs):
            return await policy.execute_async(func, *args, **kwargs)
        
        # Копируем атрибуты функции
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__module__ = func.__module__
        
        # Добавляем асинхронную версию если функция асинхронная
        if asyncio.iscoroutinefunction(func):
            async_wrapper.__name__ = func.__name__
            async_wrapper.__doc__ = func.__doc__
            async_wrapper.__module__ = func.__module__
            return async_wrapper
        
        return wrapper
    
    return decorator


# Вспомогательные функции для различных типов ретраев
def with_exponential_backoff(max_attempts: int = 3, base_delay: float = 0.1, 
                           max_delay: float = 10.0, jitter: bool = True):
    """Упрощенный декоратор с экспоненциальной задержкой"""
    config = RetryPolicyConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        jitter=jitter
    )
    return retry(config)


def with_linear_backoff(max_attempts: int = 3, base_delay: float = 1.0):
    """Декоратор с линейной задержкой"""
    config = RetryPolicyConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        exponential_base=1.0,  # Линейная задержка
        max_delay=base_delay * max_attempts,
        jitter=False
    )
    return retry(config)


def with_fixed_delay(max_attempts: int = 3, delay: float = 1.0):
    """Декоратор с фиксированной задержкой"""
    config = RetryPolicyConfig(
        max_attempts=max_attempts,
        base_delay=delay,
        exponential_base=1.0,  # Фиксированная задержка
        max_delay=delay,
        jitter=False
    )
    return retry(config)