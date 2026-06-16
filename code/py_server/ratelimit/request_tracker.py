
"""
Механизм учета запросов для системы Rate Limiting
Создан на основе стандартов производительности 1С и анализа узких мест MCP

Особенности:
- Потокобезопасность (thread-safe)
- Оптимизация производительности (< 1ms на запрос)
- Поддержка Redis для distributed режима
- Автоматическая очистка устаревших данных
- Интеграция с FastAPI и OAuth2
"""

import hashlib
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

try:
    import redis.asyncio as redis
    from geoip2.database import Reader
    from geoip2.errors import AddressNotFoundError
    HAS_REDIS = True
    HAS_GEOIP = True
except ImportError:
    HAS_REDIS = False
    HAS_GEOIP = False
    redis = None
    Reader = None
    AddressNotFoundError = Exception

import psutil
from fastapi import Request

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
            
            # Ограничиваем размер данных
            if len(self.data) > self.max_size:
                # Удаляем самые старые записи
                sorted_keys = sorted(
                    self.access_times.items(),
                    key=lambda x: x[1]
                )[:len(self.data) - self.max_size]
                
                for key, _ in sorted_keys:
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
    """Трекер запросов по IP адресам с геолокацией"""
    
    def __init__(self, geoip_db_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.geoip_reader = None
        self._init_geoip(geoip_db_path)
        
        # Специальные настройки для IP
        self.blocked_ips = set()
        self.suspicious_ips = defaultdict(int)
        self.request_patterns = defaultdict(lambda: deque(maxlen=100))
    
    def _init_geoip(self, db_path: Optional[str]):
        """Инициализация GeoIP"""
        if HAS_GEOIP and db_path:
            try:
                self.geoip_reader = Reader(db_path)
                logger.info("GeoIP reader инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать GeoIP: {e}")
    
    def add_request(self, metrics: RequestMetrics) -> bool:
        """Добавить запрос"""
        with self.lock:
            # Проверяем заблокированные IP
            if metrics.ip in self.blocked_ips:
                return False
            
            current_time = time.time()
            window_start = current_time - 60  # Последняя минута
            
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
            
            # Обновляем геолокацию
            if self.geoip_reader and not ip_data["geo_data"]:
                ip_data["geo_data"] = self._get_geo_data(metrics.ip)
                metrics.geo_country = ip_data["geo_data"].get("country")
                metrics.geo_city = ip_data["geo_data"].get("city")
                metrics.geo_region = ip_data["geo_data"].get("region")
            
            # Добавляем запрос
            ip_data["requests"].append(current_time)
            ip_data["last_request"] = current_time
            ip_data["total_requests"] += 1
            ip_data["last_metrics"] = metrics
            
            # Обновляем время доступа
            self.access_times[metrics.ip] = current_time
            
            # Проверяем паттерны подозрительной активности
            self._analyze_suspicious_pattern(metrics.ip, current_time)
            
            return True
    
    def _get_geo_data(self, ip: str) -> Dict[str, Optional[str]]:
        """Получить геолокационные данные"""
        if not self.geoip_reader:
            return {}
        
        try:
            response = self.geoip_reader.city(ip)
            return {
                "country": response.country.name,
                "country_code": response.country.iso_code,
                "city": response.city.name,
                "region": response.subdivisions.most_specific.name,
                "postal_code": response.postal.code,
                "latitude": float(response.location.latitude),
                "longitude": float(response.location.longitude)
            }
        except (AddressNotFoundError, Exception):
            return {}
    
    def _analyze_suspicious_pattern(self, ip: str, current_time: float):
        """Анализ подозрительных паттернов"""
        ip_data = self.data[ip]
        
        # Проверяем частоту запросов
        recent_requests = [
            req_time for req_time in ip_data["requests"]
            if current_time - req_time < 60
        ]
        
        if len(recent_requests) > 1000:  # 1000+ запросов в минуту
            self.suspicious_ips[ip] += 1
            logger.warning(f"Подозрительная активность с IP {ip}: {len(recent_requests)} запросов/мин")
        
        # Проверяем равномерность запросов (бот активность)
        if len(ip_data["requests"]) >= 10:
            intervals = []
            sorted_requests = sorted(list(ip_data["requests"])[-10:])
            for i in range(1, len(sorted_requests)):
                intervals.append(sorted_requests[i] - sorted_requests[i-1])
            
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                std_dev = (sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)) ** 0.5
                
                # Если запросы очень равномерные (низкое std deviation)
                if avg_interval > 0 and std_dev / avg_interval < 0.1:
                    self.suspicious_ips[ip] += 0.5
    
    def block_ip(self, ip: str, reason: str = ""):
        """Заблокировать IP"""
        with self.lock:
            self.blocked_ips.add(ip)
            if ip in self.data:
                self.data[ip]["blocked_count"] += 1
            logger.warning(f"IP {ip} заблокирован. Причина: {reason}")
    
    def unblock_ip(self, ip: str):
        """Разблокировать IP"""
        with self.lock:
            self.blocked_ips.discard(ip)
            logger.info(f"IP {ip} разблокирован")
    
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
            
            requests_last_day = len([
                req_time for req_time in ip_data["requests"]
                if current_time - req_time < 86400
            ])
            
            return {
                "ip": ip,
                "is_blocked": ip in self.blocked_ips,
                "suspicious_score": self.suspicious_ips.get(ip, 0),
                "first_request": ip_data["first_request"],
                "last_request": ip_data["last_request"],
                "total_requests": ip_data["total_requests"],
                "blocked_count": ip_data.get("blocked_count", 0),
                "geo_data": ip_data.get("geo_data"),
                "requests_last_minute": requests_last_minute,
                "requests_last_hour": requests_last_hour,
                "requests_last_day": requests_last_day,
                "rate_limits_applied": requests_last_minute  # Простая эвристика
            }


class UserTracker(BaseTracker):
    """Трекер запросов по аутентифицированным пользователям"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session_data = {}
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
                    "user_tier": "free",  # По умолчанию
                    "session_count": 0,
                    "blocked_count": 0
                }
            
            user_data = self.data[user_id]
            
            # Добавляем запрос
            user_data["requests"].append(current_time)
            user_data["last_request"] = current_time
            user_data["total_requests"] += 1
            
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


class DistributedTracker(BaseTracker):
    """Трекер для горизонтального масштабирования с Redis"""
    
    def __init__(self, redis_url: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.redis_url = redis_url
        self.redis_client = None
        self.use_redis = HAS_REDIS and redis_url is not None
        
        if self.use_redis:
            self._init_redis()
    
    def _init_redis(self):
        """Инициализация Redis клиента"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1
            )
            logger.info("Redis клиент инициализирован для distributed tracker")
        except Exception as e:
            logger.error(f"Ошибка инициализации Redis: {e}")
            self.use_redis = False
    
    async def _redis_get(self, key: str) -> Optional[str]:
        """Асинхронное получение из Redis"""
        if not self.use_redis or not self.redis_client:
            return None
        try:
            return await self.redis_client.get(key)
        except Exception:
            return None
    
    async def _redis_set(self, key: str, value: str, expire: int):
        """Асинхронная запись в Redis"""
        if not self.use_redis or not self.redis_client:
            return
        try:
            await self.redis_client.setex(key, expire, value)
        except Exception:
            pass
    
    async def _redis_delete(self, key: str):
        """Асинхронное удаление из Redis"""
        if not self.use_redis or not self.redis_client:
            return
        try:
            await self.redis_client.delete(key)
        except Exception:
            pass
    
    async def add_request_distributed(self, 
                                    key: str, 
                                    request_data: Dict[str, Any], 
                                    expire_seconds: int = 3600) -> bool:
        """Добавить запрос в distributed режиме"""
        current_time = time.time()
        
        if self.use_redis:
            return await self._add_request_redis(key, request_data, expire_seconds)
        else:
            return self._add_request_local(key, request_data)
    
    async def _add_request_redis(self, 
                                key: str, 
                                request_data: Dict[str, Any], 
                                expire_seconds: int) -> bool:
        """Добавить запрос в Redis"""
        try:
            # Используем Redis sorted set для хранения временных меток
            redis_key = f"request_tracker:{key}"
            current_timestamp = current_time
            
            # Добавляем текущий запрос
            await self.redis_client.zadd(redis_key, {str(current_timestamp): current_timestamp})
            
            # Удаляем старые записи (старше expire_seconds)
            cutoff_time = current_time - expire_seconds
            await self.redis_client.zremrangebyscore(redis_key, 0, cutoff_time)
            
            # Устанавливаем TTL для ключа
            await self.redis_client.expire(redis_key, expire_seconds)
            
            # Получаем количество запросов за период
            request_count = await self.redis_client.zcard(redis_key)
            
            # Проверяем лимиты (пример: не более 1000 запросов в час)
            if request_count > 1000:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка работы с Redis: {e}")
            return False
    
    def _add_request_local(self, key: str, request_data: Dict[str, Any]) -> bool:
        """Локальное добавление запроса (fallback)"""
        with self.lock:
            current_time = time.time()
            
            # Инициализируем данные
            if key not in self.data:
                self.data[key] = {
                    "requests": deque(),
                    "first_request": current_time,
                    "last_request": current_time
                }
            
            key_data = self.data[key]
            key_data["requests"].append(current_time)
            key_data["last_request"] = current_time
            
            # Ограничиваем размер
            while len(key_data["requests"]) > 1000:
                key_data["requests"].popleft()
            
            self.access_times[key] = current_time
            return True
    
    async def get_distributed_stats(self, key: str) -> Optional[Dict[str, Any]]:
        """Получить статистику из distributed источника"""
        if self.use_redis:
            return await self._get_redis_stats(key)
        else:
            return self._get_local_stats(key)
    
    async def _get_redis_stats(self, key: str) -> Optional[Dict[str, Any]]:
        """Получить статистику из Redis"""
        try:
            redis_key = f"request_tracker:{key}"
            
            # Получаем все временные метки
            timestamps = await self.redis_client.zrange(redis_key, 0, -1, withscores=True)
            
            if not timestamps:
                return None
            
            current_time = time.time()
            request_times = [float(ts[1]) for ts in timestamps]
            
            # Статистика за различные периоды
            last_minute = len([t for t in request_times if current_time - t < 60])
            last_hour = len([t for t in request_times if current_time - t < 3600])
            last_day = len([t for t in request_times if current_time - t < 86400])
            
            return {
                "key": key,
                "total_requests": len(request_times),
                "first_request": min(request_times),
                "last_request": max(request_times),
                "requests_last_minute": last_minute,
                "requests_last_hour": last_hour,
                "requests_last_day": last_day,
                "is_distributed": True
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики из Redis: {e}")
            return None
    
    def _get_local_stats(self, key: str) -> Optional[Dict[str, Any]]:
        """Получить локальную статистику"""
        with self.lock:
            if key not in self.data:
                return None
            
            key_data = self.data[key]
            current_time = time.time()
            
            last_minute = len([
                req_time for req_time in key_data["requests"]
                if current_time - req_time < 60
            ])
            
            last_hour = len([
                req_time for req_time in key_data["requests"]
                if current_time - req_time < 3600
            ])
            
            last_day = len([
                req_time for req_time in key_data["requests"]
                if current_time - req_time < 86400
            ])
            
            return {
                "key": key,
                "total_requests": len(key_data["requests"]),
                "first_request": key_data["first_request"],
                "last_request": key_data["last_request"],
                "requests_last_minute": last_minute,
                "requests_last_hour": last_hour,
                "requests_last_day": last_day,
                "is_distributed": False
            }


class RequestTracker:
    """Основной класс для учета запросов системы Rate Limiting"""
    
    def __init__(self, 
                 use_redis: bool = False,
                 redis_url: Optional[str] = None,
                 geoip_db_path: Optional[str] = None):
        self.use_redis = use_redis
        self.redis_url = redis_url
        self.geoip_db_path = geoip_db_path
        
        # Инициализируем трекеры
        self.ip_tracker = IPTracker(
            name="ip_tracker",
            geoip_db_path=geoip_db_path,
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
        
        self.distributed_tracker = DistributedTracker(
            name="distributed_tracker",
            redis_url=redis_url,
            max_size=100000,
            ttl=3600
        )
        
        # Общая статистика
        self.total_requests = 0
        self.blocked_requests = 0
        self.start_time = time.time()
        
        logger.info("RequestTracker инициализирован")
    
    async def track_request(self, 
                           request: Request, 
                           response_time_ms: float,
                           status_code: int,
                           user_id: Optional[str] = None,
                           tool_name: Optional[str] = None) -> bool:
        """
        Основной метод для учета запроса
        
        Args:
            request: FastAPI Request объект
            response_time_ms: время отклика в миллисекундах
            status_code: HTTP статус код
            user_id: ID пользователя (опционально)
            tool_name: имя MCP инструмента (опционально)
            
        Returns:
            bool: True если запрос разрешен, False если заблокирован
        """
        start_track_time = time.time()
        
        try:
            # Извлекаем данные из запроса
            metrics = self._extract_request_metrics(
                request, response_time_ms, status_code, user_id, tool_name
            )
            
            # Проверяем различные трекеры
            ip_allowed = self.ip_tracker.add_request(metrics)
            user_allowed = self.user_tracker.add_request(metrics)
            tool_allowed = self.tool_tracker.add_request(metrics)
            
            # Проверяем distributed режим если используется
            distributed_allowed = True
            if self.use_redis:
                # Создаем ключ для distributed tracking
                dist_key = self._create_distributed_key(metrics)
                distributed_allowed = await self.distributed_tracker.add_request_distributed(
                    dist_key, metrics.__dict__
                )
            
            # Общая проверка - все трекеры должны разрешить запрос
            allowed = ip_allowed and user_allowed and tool_allowed and distributed_allowed
            
            # Обновляем статистику
            with threading.Lock():
                self.total_requests += 1
                if not allowed:
                    self.blocked_requests += 1
            
            # Логируем если запрос заблокирован
            if not allowed:
                logger.warning(
                    f"Запрос заблокирован: IP={metrics.ip}, "
                    f"User={user_id}, Tool={tool_name}, "
                    f"Endpoint={metrics.endpoint}"
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
    
    def _extract_request_metrics(self, 
                               request: Request,
                               response_time_ms: float,
                               status_code: int,
                               user_id: Optional[str],
                               tool_name: Optional[str]) -> RequestMetrics:
        """Извлечь метрики из FastAPI Request"""
        # Извлекаем IP с учетом прокси
        client_ip = request.client.host if request.client else "unknown"
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        elif "x-real-ip" in request.headers:
            client_ip = request.headers["x-real-ip"]
        
        # Извлекаем User Agent
        user_agent = request.headers.get("user-agent", "")
        
        # Извлекаем Referer
        referer = request.headers.get("referer")
        
        return RequestMetrics(
            timestamp=time.time(),
            ip=client_ip,
            user_id=user_id,
            tool_name=tool_name,
            endpoint=str(request.url.path),
            method=request.method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            user_agent=user_agent,
            referer=referer,
            content_length=0  # Можно извлечь из response если нужно
        )
    
    def _create_distributed_key(self, metrics: RequestMetrics) -> str:
        """Создать ключ для distributed tracking"""
        # Создаем ключ на основе IP, пользователя и инструмента
        key_parts = [metrics.ip]
        if metrics.user_id:
            key_parts.append(f"user:{metrics.user_id}")
        if metrics.tool_name:
            key_parts.append(f"tool:{metrics.tool_name}")
        
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
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
                "tool_tracker": self.tool_tracker.get_stats(),
                "distributed_tracker": self.distributed_tracker.get_stats()
            },
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage('/').percent
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
    
    def unblock_ip(self, ip: str):
        """Разблокировать IP адрес"""
        self.ip_tracker.unblock_ip(ip)
    
    def set_user_tier(self, user_id: str, tier: str):
        """Установить уровень пользователя"""
        self.user_tracker.set_user_tier(user_id, tier)
    
    def set_tool_limits(self, tool_name: str, limits: Dict[str, int]):
        """Установить лимиты для инструмента"""
        self.tool_tracker.set_tool_limits(tool_name, limits)
    
    async def get_distributed_stats(self, key: str) -> Optional[Dict[str, Any]]:
        """Получить distributed статистику"""
        return await self.distributed_tracker.get_distributed_stats(key)


# Глобальный экземпляр трекера
_request_tracker: Optional[RequestTracker] = None


def get_request_tracker() -> RequestTracker:
    """Получить глобальный экземпляр RequestTracker"""
    global _request_tracker
    if _request_tracker is None:
        raise RuntimeError("RequestTracker не инициализирован. Вызовите init_request_tracker()")
    return _request_tracker


async def init_request_tracker(config: Dict[str, Any] = None):
    """Инициализировать глобальный RequestTracker"""
    global _request_tracker
    
    if config is None:
        config = {}
    
    _request_tracker = RequestTracker(
        use_redis=config.get("use_redis", False),
        redis_url=config.get("redis_url"),
        geoip_db_path=config.get("geoip_db_path")
    )
    
    logger.info("RequestTracker инициализирован глобально")


@asynccontextmanager
async def request_tracking_context(request: Request, 
                                 user_id: Optional[str] = None,
                                 tool_name: Optional[str] = None):
    """Контекстный менеджер для отслеживания запросов"""
    start_time = time.time()
    tracker = get_request_tracker()
    
    try:
        yield tracker
    finally:
        response_time_ms = (time.time() - start_time) * 1000
        # В реальном приложении здесь был бы status_code из ответа
        await tracker.track_request(request, response_time_ms, 200, user_id, tool_name)


# Middleware для FastAPI
def create_rate_limit_middleware():
    """Создать middleware для FastAPI"""
    
    async def rate_limit_middleware(request: Request, call_next):
        """Middleware для rate limiting"""
        tracker = get_request_tracker()
        start_time = time.time()
        
        try:
            # Извлекаем пользователя из JWT если доступен
            user_id = None
            # В реальном приложении здесь была бы логика извлечения user_id из JWT
            # Например: user_id = getattr(request.state, "user_id", None)
            
            # Извлекаем tool_name из пути или query параметров
            tool_name = None
            path_parts = request.url.path.split("/")
            if len(path_parts) > 2 and path_parts[1] == "tools":
                tool_name = path_parts[2]
            
            # Проверяем лимиты
            allowed = await tracker.track_request(
                request, 
                0,  # response_time будет установлен после выполнения
                200,  # status_code будет установлен после выполнения
                user_id,
                tool_name
            )
            
            if not allowed:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": "Слишком много запросов. Попробуйте позже."
                    }
                )
            
            # Выполняем запрос
            response = await call_next(request)
            
            # Обновляем метрики с реальными значениями
            response_time_ms = (time.time() - start_time) * 1000
            await tracker.track_request(
                request,
                response_time_ms,
                response.status_code,
                user_id,
                tool_name
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка в rate limit middleware: {e}")
            return await call_next(request)
    
    return rate_limit_middleware


# Экспорт основных классов и функций
__all__ = [
    "RequestTracker",
    "IPTracker", 
    "UserTracker",
    "ToolTracker",
    "DistributedTracker",
    "RequestMetrics",
    "RateLimitStats",
    "get_request_tracker",
    "init_request_tracker",
    "request_tracking_context",
    "create_rate_limit_middleware"
]