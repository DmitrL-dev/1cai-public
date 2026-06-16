
"""
Демонстрационная версия RequestTracker без внешних зависимостей
Показывает основную функциональность модуля
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Метрики запроса"""
    timestamp: float
    ip: str
    user_id: Optional[str]
    tool_name: Optional[str]
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    user_agent: str
    referer: Optional[str]
    content_length: int
    
    # Дополнительные поля для анализа
    geo_country: Optional[str] = None
    geo_city: Optional[str] = None
    geo_region: Optional[str] = None


@dataclass
class RateLimitStats:
    """Статистика лимитов"""
    requests_per_minute: int = 0
    requests_per_hour: int = 0
    requests_per_day: int = 0
    blocked_requests: int = 0
    allowed_requests: int = 0
    
    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


class BaseTracker(ABC):
    """Базовый класс для трекеров запросов"""
    
    def __init__(self, name: str, max_size: int = 10000, ttl: int = 3600):
        self.name = name
        self.max_size = max_size
        self.ttl = ttl
        self.lock = threading.RLock()
        self.data = {}
        self.access_times = {}
        self.cleanup_interval = 300  # 5 минут
        self._start_cleanup_task()
    
    @abstractmethod
    def add_request(self, metrics: RequestMetrics) -> bool:
        """Добавить запрос и вернуть True если разрешен"""
    
    def _start_cleanup_task(self):
        """Запустить задачу очистки"""
        def cleanup():
            while True:
                try:
                    self._cleanup_old_data()
                    time.sleep(self.cleanup_interval)
                except Exception as e:
                    logger.error(f"Ошибка очистки в {self.name}: {e}")
        
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()
    
    def _cleanup_old_data(self):
        """Очистка устаревших данных"""
        current_time = time.time()
        cutoff_time = current_time - self.ttl
        
        with self.lock:
            # Удаляем устаревшие записи
            keys_to_remove = [
                key for key, access_time in self.access_times.items()
                if access_time < cutoff_time
            ]
            
            for key in keys_to_remove:
                self.data.pop(key, None)
                self.access_times.pop(key, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику трекера"""
        with self.lock:
            return {
                "name": self.name,
                "total_keys": len(self.data),
                "max_size": self.max_size,
                "ttl": self.ttl,
                "cleanup_interval": self.cleanup_interval
            }


class IPTracker(BaseTracker):
    """Трекер запросов по IP адресам"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.blocked_ips = set()
        self.suspicious_ips = defaultdict(int)
    
    def add_request(self, metrics: RequestMetrics) -> bool:
        """Добавить запрос"""
        with self.lock:
            # Проверяем заблокированные IP
            if metrics.ip in self.blocked_ips:
                return False
            
            current_time = time.time()
            
            # Инициализируем данные IP если нужно
            if metrics.ip not in self.data:
                self.data[metrics.ip] = {
                    "requests": deque(),
                    "first_request": current_time,
                    "last_request": current_time,
                    "total_requests": 0,
                    "blocked_count": 0,
                    "geo_data": None
                }
            
            ip_data = self.data[metrics.ip]
            
            # Добавляем запрос
            ip_data["requests"].append(current_time)
            ip_data["last_request"] = current_time
            ip_data["total_requests"] += 1
            
            # Ограничиваем размер
            while len(ip_data["requests"]) > 1000:
                ip_data["requests"].popleft()
            
            # Обновляем время доступа
            self.access_times[metrics.ip] = current_time
            
            # Простая проверка лимитов (100 запросов в минуту)
            recent_requests = [
                req_time for req_time in ip_data["requests"]
                if current_time - req_time < 60
            ]
            
            if len(recent_requests) > 100:
                ip_data["blocked_count"] += 1
                return False
            
            return True
    
    def block_ip(self, ip: str, reason: str = ""):
        """Заблокировать IP"""
        with self.lock:
            self.blocked_ips.add(ip)
            logger.warning(f"IP {ip} заблокирован. Причина: {reason}")
    
    def get_ip_stats(self, ip: str) -> Optional[Dict[str, Any]]:
        """Получить статистику IP"""
        with self.lock:
            if ip not in self.data:
                return None
            
            ip_data = self.data[ip]
            current_time = time.time()
            
            # Статистика за последние периоды
            requests_last_minute = len([
                req_time for req_time in ip_data["requests"]
                if current_time - req_time < 60
            ])
            
            requests_last_hour = len([
                req_time for req_time in ip_data["requests"]
                if current_time - req_time < 3600
            ])
            
            return {
                "ip": ip,
                "is_blocked": ip in self.blocked_ips,
                "suspicious_score": self.suspicious_ips.get(ip, 0),
                "first_request": ip_data["first_request"],
                "last_request": ip_data["last_request"],
                "total_requests": ip_data["total_requests"],
                "blocked_count": ip_data.get("blocked_count", 0),
                "requests_last_minute": requests_last_minute,
                "requests_last_hour": requests_last_hour,
                "rate_limits_applied": requests_last_minute
            }


class UserTracker(BaseTracker):
    """Трекер запросов по аутентифицированным пользователям"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rate_limits = {
            "free": {"requests_per_minute": 60, "requests_per_hour": 1000},
            "premium": {"requests_per_minute": 300, "requests_per_hour": 10000},
            "enterprise": {"requests_per_minute": 1000, "requests_per_hour": 50000}
        }
    
    def add_request(self, metrics: RequestMetrics) -> bool:
        """Добавить запрос"""
        if not metrics.user_id:
            return True  # Анонимные запросы всегда разрешены
        
        with self.lock:
            current_time = time.time()
            user_id = metrics.user_id
            
            # Инициализируем данные пользователя
            if user_id not in self.data:
                self.data[user_id] = {
                    "requests": deque(),
                    "first_request": current_time,
                    "last_request": current_time,
                    "total_requests": 0,
                    "user_tier": "free",
                    "session_count": 0,
                    "blocked_count": 0
                }
            
            user_data = self.data[user_id]
            
            # Добавляем запрос
            user_data["requests"].append(current_time)
            user_data["last_request"] = current_time
            user_data["total_requests"] += 1
            
            # Ограничиваем размер
            while len(user_data["requests"]) > 1000:
                user_data["requests"].popleft()
            
            # Обновляем время доступа
            self.access_times[user_id] = current_time
            
            # Проверяем лимиты
            return self._check_rate_limits(user_id, current_time)
    
    def _check_rate_limits(self, user_id: str, current_time: float) -> bool:
        """Проверка лимитов для пользователя"""
        user_data = self.data[user_id]
        user_tier = user_data["user_tier"]
        limits = self.rate_limits.get(user_tier, self.rate_limits["free"])
        
        # Проверяем запросы за последнюю минуту
        requests_last_minute = len([
            req_time for req_time in user_data["requests"]
            if current_time - req_time < 60
        ])
        
        if requests_last_minute > limits["requests_per_minute"]:
            user_data["blocked_count"] += 1
            return False
        
        # Проверяем запросы за последний час
        requests_last_hour = len([
            req_time for req_time in user_data["requests"]
            if current_time - req_time < 3600
        ])
        
        if requests_last_hour > limits["requests_per_hour"]:
            user_data["blocked_count"] += 1
            return False
        
        return True
    
    def set_user_tier(self, user_id: str, tier: str):
        """Установить уровень пользователя"""
        with self.lock:
            if user_id in self.data:
                self.data[user_id]["user_tier"] = tier
                logger.info(f"Пользователю {user_id} установлен уровень {tier}")
    
    def get_user_stats(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получить статистику пользователя"""
        with self.lock:
            if user_id not in self.data:
                return None
            
            user_data = self.data[user_id]
            current_time = time.time()
            user_tier = user_data["user_tier"]
            limits = self.rate_limits.get(user_tier, self.rate_limits["free"])
            
            # Статистика за последние периоды
            requests_last_minute = len([
                req_time for req_time in user_data["requests"]
                if current_time - req_time < 60
            ])
            
            requests_last_hour = len([
                req_time for req_time in user_data["requests"]
                if current_time - req_time < 3600
            ])
            
            return {
                "user_id": user_id,
                "user_tier": user_tier,
                "first_request": user_data["first_request"],
                "last_request": user_data["last_request"],
                "total_requests": user_data["total_requests"],
                "blocked_count": user_data.get("blocked_count", 0),
                "requests_last_minute": requests_last_minute,
                "requests_last_hour": requests_last_hour,
                "limits": limits,
                "remaining_quota": {
                    "per_minute": limits["requests_per_minute"] - requests_last_minute,
                    "per_hour": limits["requests_per_hour"] - requests_last_hour
                }
            }


class ToolTracker(BaseTracker):
    """Специализированный трекер для MCP tools"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tool_limits = {}
        self.tool_stats = defaultdict(lambda: {
            "total_calls": 0,
            "avg_response_time": 0,
            "error_count": 0,
            "last_calls": deque(maxlen=100)
        })
        
        # Стандартные лимиты для инструментов
        self.default_tool_limits = {
            "database_query": {"per_minute": 100, "per_hour": 2000},
            "file_operation": {"per_minute": 50, "per_hour": 1000},
            "report_generation": {"per_minute": 10, "per_hour": 200},
            "external_api": {"per_minute": 30, "per_hour": 500}
        }
    
    def add_request(self, metrics: RequestMetrics) -> bool:
        """Добавить запрос к инструменту"""
        if not metrics.tool_name:
            return True
        
        with self.lock:
            current_time = time.time()
            tool_name = metrics.tool_name
            
            # Инициализируем данные инструмента
            if tool_name not in self.data:
                self.data[tool_name] = {
                    "requests": deque(),
                    "first_call": current_time,
                    "last_call": current_time,
                    "total_calls": 0,
                    "blocked_calls": 0
                }
            
            tool_data = self.data[tool_name]
            tool_data["requests"].append(current_time)
            tool_data["last_call"] = current_time
            tool_data["total_calls"] += 1
            
            # Обновляем статистику
            tool_stats = self.tool_stats[tool_name]
            tool_stats["total_calls"] += 1
            tool_stats["last_calls"].append(current_time)
            
            if metrics.response_time_ms > 0:
                # Обновляем среднее время отклика
                current_avg = tool_stats["avg_response_time"]
                count = tool_stats["total_calls"]
                tool_stats["avg_response_time"] = (
                    (current_avg * (count - 1) + metrics.response_time_ms) / count
                )
            
            if metrics.status_code >= 400:
                tool_stats["error_count"] += 1
            
            # Обновляем время доступа
            self.access_times[tool_name] = current_time
            
            # Проверяем лимиты
            return self._check_tool_limits(tool_name, current_time)
    
    def _check_tool_limits(self, tool_name: str, current_time: float) -> bool:
        """Проверка лимитов для инструмента"""
        tool_data = self.data[tool_name]
        limits = self.tool_limits.get(tool_name, self.default_tool_limits.get(tool_name, {"per_minute": 60, "per_hour": 1000}))
        
        # Проверяем запросы за последнюю минуту
        calls_last_minute = len([
            call_time for call_time in tool_data["requests"]
            if current_time - call_time < 60
        ])
        
        if calls_last_minute > limits["per_minute"]:
            tool_data["blocked_calls"] += 1
            return False
        
        # Проверяем запросы за последний час
        calls_last_hour = len([
            call_time for call_time in tool_data["requests"]
            if current_time - call_time < 3600
        ])
        
        if calls_last_hour > limits["per_hour"]:
            tool_data["blocked_calls"] += 1
            return False
        
        return True
    
    def set_tool_limits(self, tool_name: str, limits: Dict[str, int]):
        """Установить лимиты для инструмента"""
        with self.lock:
            self.tool_limits[tool_name] = limits
            logger.info(f"Установлены лимиты для инструмента {tool_name}: {limits}")
    
    def get_tool_stats(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Получить статистику инструмента"""
        with self.lock:
            if tool_name not in self.data:
                return None
            
            tool_data = self.data[tool_name]
            tool_stats = self.tool_stats[tool_name]
            current_time = time.time()
            limits = self.tool_limits.get(tool_name, self.default_tool_limits.get(tool_name, {"per_minute": 60, "per_hour": 1000}))
            
            calls_last_minute = len([
                call_time for call_time in tool_data["requests"]
                if current_time - call_time < 60
            ])
            
            calls_last_hour = len([
                call_time for call_time in tool_data["requests"]
                if current_time - call_time < 3600
            ])
            
            error_rate = (tool_stats["error_count"] / max(tool_stats["total_calls"], 1)) * 100
            
            return {
                "tool_name": tool_name,
                "first_call": tool_data["first_call"],
                "last_call": tool_data["last_call"],
                "total_calls": tool_data["total_calls"],
                "blocked_calls": tool_data.get("blocked_calls", 0),
                "calls_last_minute": calls_last_minute,
                "calls_last_hour": calls_last_hour,
                "limits": limits,
                "remaining_quota": {
                    "per_minute": limits["per_minute"] - calls_last_minute,
                    "per_hour": limits["per_hour"] - calls_last_hour
                },
                "avg_response_time_ms": round(tool_stats["avg_response_time"], 2),
                "error_count": tool_stats["error_count"],
                "error_rate_percent": round(error_rate, 2)
            }


class RequestTracker:
    """Основной класс для учета запросов системы Rate Limiting"""
    
    def __init__(self, use_redis: bool = False, redis_url: Optional[str] = None):
        self.use_redis = use_redis
        self.redis_url = redis_url
        
        # Инициализируем трекеры
        self.ip_tracker = IPTracker(
            name="ip_tracker",
            max_size=50000,
            ttl=86400  # 24 часа
        )
        
        self.user_tracker = UserTracker(
            name="user_tracker",
            max_size=20000,
            ttl=86400  # 24 часа
        )
        
        self.tool_tracker = ToolTracker(
            name="tool_tracker",
            max_size=10000,
            ttl=3600  # 1 час
        )
        
        # Общая статистика
        self.total_requests = 0
        self.blocked_requests = 0
        self.start_time = time.time()
        
        logger.info("RequestTracker инициализирован")
    
    async def track_request(self, 
                           response_time_ms: float,
                           status_code: int,
                           ip: str = "127.0.0.1",
                           user_id: Optional[str] = None,
                           tool_name: Optional[str] = None,
                           endpoint: str = "/",
                           method: str = "GET") -> bool:
        """
        Основной метод для учета запроса
        """
        start_track_time = time.time()
        
        try:
            # Извлекаем данные из запроса
            metrics = RequestMetrics(
                timestamp=time.time(),
                ip=ip,
                user_id=user_id,
                tool_name=tool_name,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time_ms=response_time_ms,
                user_agent="TestClient/1.0",
                referer=None,
                content_length=1024
            )
            
            # Проверяем различные трекеры
            ip_allowed = self.ip_tracker.add_request(metrics)
            user_allowed = self.user_tracker.add_request(metrics)
            tool_allowed = self.tool_tracker.add_request(metrics)
            
            # Общая проверка - все трекеры должны разрешить запрос
            allowed = ip_allowed and user_allowed and tool_allowed
            
            # Обновляем статистику
            with threading.Lock():
                self.total_requests += 1
                if not allowed:
                    self.blocked_requests += 1
            
            # Логируем если запрос заблокирован
            if not allowed:
                logger.warning(
                    f"Запрос заблокирован: IP={ip}, "
                    f"User={user_id}, Tool={tool_name}, "
                    f"Endpoint={endpoint}"
                )
            
            # Проверяем производительность (должно быть < 1ms)
            track_time = (time.time() - start_track_time) * 1000
            if track_time > 1.0:
                logger.warning(f"Время трекинга запроса превышает 1ms: {track_time:.2f}ms")
            
            return allowed
            
        except Exception as e:
            logger.error(f"Ошибка трекинга запроса: {e}")
            # В случае ошибки разрешаем запрос
            return True
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Получить комплексную статистику всех трекеров"""
        uptime = time.time() - self.start_time
        
        with threading.Lock():
            blocked_rate = (self.blocked_requests / max(self.total_requests, 1)) * 100
        
        return {
            "overall": {
                "total_requests": self.total_requests,
                "blocked_requests": self.blocked_requests,
                "blocked_rate_percent": round(blocked_rate, 2),
                "uptime_seconds": round(uptime, 2),
                "requests_per_second": round(self.total_requests / max(uptime, 1), 2)
            },
            "trackers": {
                "ip_tracker": self.ip_tracker.get_stats(),
                "user_tracker": self.user_tracker.get_stats(),
                "tool_tracker": self.tool_tracker.get_stats()
            },
            "system": {
                "cpu_percent": 15.2,  # Демо данные
                "memory_percent": 45.8,
                "disk_usage_percent": 23.1
            }
        }
    
    def get_ip_stats(self, ip: str) -> Optional[Dict[str, Any]]:
        """Получить статистику по IP"""
        return self.ip_tracker.get_ip_stats(ip)
    
    def get_user_stats(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получить статистику по пользователю"""
        return self.user_tracker.get_user_stats(user_id)
    
    def get_tool_stats(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Получить статистику по инструменту"""
        return self.tool_tracker.get_tool_stats(tool_name)
    
    def block_ip(self, ip: str, reason: str = ""):
        """Заблокировать IP адрес"""
        self.ip_tracker.block_ip(ip, reason)
    
    def set_user_tier(self, user_id: str, tier: str):
        """Установить уровень пользователя"""
        self.user_tracker.set_user_tier(user_id, tier)
    
    def set_tool_limits(self, tool_name: str, limits: Dict[str, int]):
        """Установить лимиты для инструмента"""
        self.tool_tracker.set_tool_limits(tool_name, limits)


# Демонстрационная функция
async def demo_request_tracker():
    """Демонстрация работы RequestTracker"""
    print("🚀 Демонстрация RequestTracker")
    print("=" * 50)
    
    # Создаем трекер
    tracker = RequestTracker(use_redis=False)
    print("✅ RequestTracker создан")
    
    # Симулируем запросы
    print("\n📊 Симуляция запросов:")
    for i in range(20):
        allowed = await tracker.track_request(
            response_time_ms=25.0 + (i % 10) * 5,
            status_code=200 if i % 10 != 0 else 500,  # 10% ошибок
            ip=f"192.168.1.{i % 5 + 1}",
            user_id=f"user{i % 3}",
            tool_name=f"tool_{i % 4}",
            endpoint=f"/api/endpoint_{i}",
            method="GET"
        )
        
        status = "✅" if allowed else "❌"
        print(f"  Запрос {i+1:2d}: {status} IP=192.168.1.{i % 5 + 1} User=user{i % 3}")
    
    # Получаем статистику
    print("\n📈 Общая статистика:")
    stats = tracker.get_comprehensive_stats()
    print(f"  Всего запросов: {stats['overall']['total_requests']}")
    print(f"  Заблокировано: {stats['overall']['blocked_requests']}")
    print(f"  Процент блокировки: {stats['overall']['blocked_rate_percent']:.2f}%")
    print(f"  Запросов в секунду: {stats['overall']['requests_per_second']}")
    
    # Статистика по IP
    print("\n🌐 Статистика IP:")
    for ip_num in range(1, 6):
        ip = f"192.168.1.{ip_num}"
        ip_stats = tracker.get_ip_stats(ip)
        if ip_stats:
            print(f"  {ip}: {ip_stats['total_requests']} запросов, "
                  f"{ip_stats['requests_last_minute']}/мин")
    
    # Статистика по пользователям
    print("\n👥 Статистика пользователей:")
    for user_num in range(3):
        user_id = f"user{user_num}"
        user_stats = tracker.get_user_stats(user_id)
        if user_stats:
            print(f"  {user_id}: {user_stats['total_requests']} запросов, "
                  f"уровень {user_stats['user_tier']}, "
                  f"осталось {user_stats['remaining_quota']['per_minute']}/мин")
    
    # Статистика по инструментам
    print("\n🔧 Статистика инструментов:")
    for tool_num in range(4):
        tool_name = f"tool_{tool_num}"
        tool_stats = tracker.get_tool_stats(tool_name)
        if tool_stats:
            print(f"  {tool_name}: {tool_stats['total_calls']} вызовов, "
                  f"среднее время {tool_stats['avg_response_time_ms']}ms, "
                  f"ошибок {tool_stats['error_count']}")
    
    # Демонстрация блокировки
    print("\n🚫 Демонстрация блокировки IP:")
    tracker.block_ip("192.168.1.1", "Test block")
    allowed = await tracker.track_request(
        response_time_ms=30.0,
        status_code=200,
        ip="192.168.1.1"
    )
    print(f"  Запрос с заблокированного IP: {'✅ Разрешен' if allowed else '❌ Заблокирован'}")
    
    # Демонстрация изменения уровня пользователя
    print("\n⬆️ Демонстрация изменения уровня пользователя:")
    tracker.set_user_tier("user0", "premium")
    user_stats = tracker.get_user_stats("user0")
    if user_stats:
        print(f"  Пользователь user0: уровень {user_stats['user_tier']}, "
              f"лимит {user_stats['limits']['requests_per_minute']}/мин")
    
    print("\n🎉 Демонстрация завершена!")
    
    return tracker


if __name__ == "__main__":
    asyncio.run(demo_request_tracker())
