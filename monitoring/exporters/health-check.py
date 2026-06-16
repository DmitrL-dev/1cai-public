# [NEXUS IDENTITY] ID: 8933916783081907909 | DATE: 2025-11-19

"""
Health Check Middleware для Python приложений (FastAPI/Flask/Django)
Предоставляет эндпоинты для мониторинга состояния сервисов
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import psutil
from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram,
                               generate_latest)

try:
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

try:
    from flask import Flask, Response, jsonify, request
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

try:
    import aioredis
    import asyncpg
    import httpx
    ASYNC_DEPS_AVAILABLE = True
except ImportError:
    ASYNC_DEPS_AVAILABLE = False

# Prometheus метрики
http_requests_total = Counter('http_requests_total', 'Total number of HTTP requests', 
                             ['method', 'endpoint', 'status_code'])

http_request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration',
                                 ['method', 'endpoint'])

app_uptime = Gauge('app_uptime_seconds', 'Application uptime in seconds')

system_memory_usage = Gauge('system_memory_usage_bytes', 'System memory usage in bytes', 
                           ['type'])

system_cpu_usage = Gauge('system_cpu_usage_percent', 'System CPU usage percentage')

class HealthCheckMiddleware:
    """Основной класс для проверки состояния системы"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = {
            'health_check_path': '/health',
            'ready_check_path': '/ready',
            'live_check_path': '/live',
            'metrics_path': '/metrics',
            'detailed_checks': True,
            'timeout': 5,
            'external_apis': {},
            'database_url': None,
            'redis_url': None,
            'log_level': 'INFO',
            **(config or {})
        }
        
        self.start_time = time.time()
        self.logger = self._setup_logger()
        
        # Асинхронные клиенты (будут инициализированы позже)
        self.db_pool: Optional[object] = None
        self.redis_client: Optional[object] = None
        self.http_client: Optional[object] = None
        
        # Обновление системных метрик
        asyncio.create_task(self._update_system_metrics())
        
    def _setup_logger(self) -> logging.Logger:
        """Настройка логгера"""
        logger = logging.getLogger('health_check')
        logger.setLevel(getattr(logging, self.config['log_level']))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    async def initialize_async_clients(self):
        """Инициализация асинхронных клиентов"""
        if not ASYNC_DEPS_AVAILABLE:
            return
            
        # Инициализация пула соединений с БД
        if self.config['database_url']:
            try:
                self.db_pool = await asyncpg.create_pool(
                    self.config['database_url'],
                    min_size=1,
                    max_size=5,
                    command_timeout=60
                )
            except Exception as e:
                self.logger.error(f"Failed to initialize database pool: {e}")
        
        # Инициализация Redis клиента
        if self.config['redis_url']:
            try:
                self.redis_client = await aioredis.from_url(
                    self.config['redis_url'],
                    decode_responses=True
                )
            except Exception as e:
                self.logger.error(f"Failed to initialize Redis client: {e}")
        
        # Инициализация HTTP клиента
        self.http_client = httpx.AsyncClient(timeout=self.config['timeout'])
    
    async def health_check(self, request: Request = None) -> Dict[str, Any]:
        """Основной health check endpoint"""
        try:
            checks = await self.perform_health_checks()
            status = self.determine_overall_status(checks)
            
            response = {
                'status': status,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version': os.getenv('APP_VERSION', '1.0.0'),
                'uptime': int(time.time() - self.start_time),
                'checks': self.config['detailed_checks'] else checks
            }
            
            return JSONResponse(
                content=response,
                status_code=200 if status == 'healthy' else 503
            )
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return JSONResponse(
                content={
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                status_code=503
            )
    
    async def ready_check(self, request: Request = None) -> Dict[str, Any]:
        """Ready check endpoint (Kubernetes)"""
        ready = await self.check_readiness()
        
        response = {
            'ready': ready,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': {
                'database': await self.check_database_connection(),
                'redis': await self.check_redis_connection(),
                'external_apis': await self.check_external_apis()
            }
        }
        
        return JSONResponse(
            content=response,
            status_code=200 if ready else 503
        )
    
    async def live_check(self, request: Request = None) -> Dict[str, Any]:
        """Live check endpoint (Kubernetes)"""
        response = {
            'live': True,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'uptime': int(time.time() - self.start_time)
        }
        
        return JSONResponse(content=response, status_code=200)
    
    async def metrics_endpoint(self, request: Request = None) -> Response:
        """Prometheus metrics endpoint"""
        return Response(
            generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    
    async def perform_health_checks(self) -> Dict[str, Any]:
        """Выполнение всех проверок состояния"""
        checks = {}
        
        # Системные проверки
        checks['system'] = await self.check_system()
        
        # База данных
        checks['database'] = await self.check_database_connection()
        
        # Redis
        checks['redis'] = await self.check_redis_connection()
        
        # Внешние API
        checks['external_apis'] = await self.check_external_apis()
        
        # Память
        checks['memory'] = await self.check_memory_usage()
        
        # Дисковое пространство
        checks['disk_space'] = await self.check_disk_space()
        
        return checks
    
    async def check_readiness(self) -> bool:
        """Проверка готовности сервиса"""
        db_ok = await self.check_database_connection()
        redis_ok = await self.check_redis_connection()
        
        return db_ok['status'] and redis_ok['status']
    
    async def check_system(self) -> Dict[str, Any]:
        """Проверка системных ресурсов"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
        
        healthy = (
            cpu_percent < 80 and
            memory.percent < 85 and
            load_avg[0] < 2.0
        )
        
        return {
            'status': healthy,
            'data': {
                'cpu_usage_percent': cpu_percent,
                'memory_usage_percent': memory.percent,
                'load_average': list(load_avg),
                'free_memory_gb': round(memory.free / (1024**3), 2),
                'total_memory_gb': round(memory.total / (1024**3), 2)
            }
        }
    
    async def check_database_connection(self) -> Dict[str, Any]:
        """Проверка подключения к базе данных"""
        if not self.db_pool:
            return {'status': False, 'error': 'Database not configured'}
        
        try:
            start = time.time()
            async with self.db_pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            duration = (time.time() - start) * 1000
            
            healthy = duration < 1000  # Response time should be < 1 second
            
            return {
                'status': healthy,
                'duration_ms': round(duration, 2),
                'pool_info': await self.get_pool_info()
            }
        except Exception as e:
            return {
                'status': False,
                'error': str(e)
            }
    
    async def check_redis_connection(self) -> Dict[str, Any]:
        """Проверка подключения к Redis"""
        if not self.redis_client:
            return {'status': False, 'error': 'Redis not configured'}
        
        try:
            start = time.time()
            await self.redis_client.ping()
            duration = (time.time() - start) * 1000
            
            healthy = duration < 500  # Response time should be < 0.5 seconds
            
            return {
                'status': healthy,
                'duration_ms': round(duration, 2),
                'info': await self.redis_client.info()
            }
        except Exception as e:
            return {
                'status': False,
                'error': str(e)
            }
    
    async def check_external_apis(self) -> Dict[str, Any]:
        """Проверка внешних API"""
        apis = self.config['external_apis']
        results = {}
        
        for name, config in apis.items():
            try:
                start = time.time()
                response = await self.http_client.get(config['url'])
                duration = (time.time() - start) * 1000
                
                healthy = 200 <= response.status_code < 300
                
                results[name] = {
                    'status': healthy,
                    'duration_ms': round(duration, 2),
                    'status_code': response.status_code
                }
            except Exception as e:
                results[name] = {
                    'status': False,
                    'error': str(e)
                }
        
        all_healthy = not apis or all(result['status'] for result in results.values())
        
        return {
            'status': all_healthy,
            'apis': results
        }
    
    async def check_memory_usage(self) -> Dict[str, Any]:
        """Проверка использования памяти"""
        process = psutil.Process()
        memory_info = process.memory_info()
        virtual_memory = psutil.virtual_memory()
        
        heap_usage_percent = (
            memory_info.rss / virtual_memory.total
        ) * 100
        
        healthy = heap_usage_percent < 80
        
        return {
            'status': healthy,
            'data': {
                'heap_usage_percent': round(heap_usage_percent, 2),
                'heap_used_mb': round(memory_info.rss / (1024**2), 2),
                'heap_total_mb': round(memory_info.rss / (1024**2), 2),
                'virtual_memory_percent': virtual_memory.percent
            }
        }
    
    async def check_disk_space(self) -> Dict[str, Any]:
        """Проверка дискового пространства"""
        disk_usage = psutil.disk_usage('/')
        usage_percent = (disk_usage.used / disk_usage.total) * 100
        
        healthy = usage_percent < 85
        
        return {
            'status': healthy,
            'data': {
                'usage_percent': round(usage_percent, 2),
                'free_gb': round(disk_usage.free / (1024**3), 2),
                'total_gb': round(disk_usage.total / (1024**3), 2)
            }
        }
    
    async def _update_system_metrics(self):
        """Обновление системных метрик"""
        while True:
            try:
                # Обновление uptime
                app_uptime.set(time.time() - self.start_time)
                
                # Обновление памяти
                memory = psutil.virtual_memory()
                system_memory_usage.labels(type='total').set(memory.total)
                system_memory_usage.labels(type='used').set(memory.used)
                system_memory_usage.labels(type='free').set(memory.free)
                system_memory_usage.labels(type='available').set(memory.available)
                
                # Обновление CPU
                cpu_percent = psutil.cpu_percent()
                system_cpu_usage.set(cpu_percent)
                
            except Exception as e:
                self.logger.error(f"Failed to update system metrics: {e}")
            
            await asyncio.sleep(5)
    
    async def get_pool_info(self) -> Dict[str, Any]:
        """Получение информации о пуле соединений"""
        if not self.db_pool:
            return {'error': 'No database pool'}
        
        try:
            return {
                'size': self.db_pool.get_size(),
                'min_size': self.db_pool.get_min_size(),
                'max_size': self.db_pool.get_max_size(),
                'closed': self.db_pool.is_closing()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def determine_overall_status(self, checks: Dict[str, Any]) -> str:
        """Определение общего статуса системы"""
        for check in checks.values():
            if isinstance(check, dict) and check.get('status') is False:
                return 'unhealthy'
        
        for check in checks.values():
            if isinstance(check, dict) and check.get('status') == 'warning':
                return 'degraded'
        
        return 'healthy'

# FastAPI интеграция
if FASTAPI_AVAILABLE:
    def create_fastapi_health_middleware(config: Dict[str, Any] = None) -> FastAPI:
        """Создание FastAPI приложения с health check endpoints"""
        
        app = FastAPI(title="Health Check Service")
        health_check = HealthCheckMiddleware(config)
        
        @app.on_event("startup")
        async def startup_event():
            await health_check.initialize_async_clients()
        
        # Health check endpoints
        app.add_api_route(
            health_check.config['health_check_path'],
            health_check.health_check,
            methods=["GET"]
        )
        
        app.add_api_route(
            health_check.config['ready_check_path'],
            health_check.ready_check,
            methods=["GET"]
        )
        
        app.add_api_route(
            health_check.config['live_check_path'],
            health_check.live_check,
            methods=["GET"]
        )
        
        app.add_api_route(
            health_check.config['metrics_path'],
            health_check.metrics_endpoint,
            methods=["GET"]
        )
        
        return app

# Flask интеграция  
if FLASK_AVAILABLE:
    def create_flask_health_middleware(config: Dict[str, Any] = None):
        """Создание Flask приложения с health check endpoints"""
        
        app = Flask(__name__)
        health_check = HealthCheckMiddleware(config)
        
        @app.before_first_request
        async def initialize():
            await health_check.initialize_async_clients()
        
        # Health check endpoints
        @app.route(health_check.config['health_check_path'], methods=['GET'])
        async def health():
            return await health_check.health_check()
        
        @app.route(health_check.config['ready_check_path'], methods=['GET'])
        async def ready():
            return await health_check.ready_check()
        
        @app.route(health_check.config['live_check_path'], methods=['GET'])
        async def live():
            return await health_check.live_check()
        
        @app.route(health_check.config['metrics_path'], methods=['GET'])
        async def metrics():
            return await health_check.metrics_endpoint()
        
        return app

# Пример использования
if __name__ == "__main__":
    import uvicorn

    # FastAPI пример
    if FASTAPI_AVAILABLE:
        config = {
            'database_url': 'postgresql://user:pass@localhost:5432/db',
            'redis_url': 'redis://localhost:6379',
            'external_apis': {
                'payment_api': {'url': 'http://payment-service:8080/health'},
                'notification_api': {'url': 'http://notification-service:8080/health'}
            }
        }
        
        app = create_fastapi_health_middleware(config)
        uvicorn.run(app, host="0.0.0.0", port=8000)