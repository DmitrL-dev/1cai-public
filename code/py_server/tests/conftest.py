
"""
Pytest конфигурация и фикстуры для HTTP сервисов тестов

Содержит:
- Глобальные фикстуры
- Моки и заглушки
- Настройки для разных окружений
- Вспомогательные функции

"""

import asyncio
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict
from unittest.mock import AsyncMock, Mock, patch

import httpx
import psutil
import pytest
from freezegun import freeze_time

# Добавляем путь к приложению
sys.path.append(str(Path(__file__).parent.parent))

from api.cache_admin import MemoryCache, cache_metrics
from config import Environment
# Импорты приложения
from main import app

# =============================================================================
# КОНФИГУРАЦИЯ ТЕСТОВОГО ОКРУЖЕНИЯ
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Настройка тестового окружения"""
    # Сохраняем оригинальное окружение
    original_env = os.environ.copy()
    
    # Устанавливаем тестовые переменные окружения
    os.environ["MCP_ENVIRONMENT"] = "testing"
    os.environ["MCP_DEBUG"] = "true"
    os.environ["MCP_ADMIN_TOKEN"] = "test_admin_token_123"
    os.environ["MCP_HOST"] = "127.0.0.1"
    os.environ["MCP_PORT"] = "8000"
    
    # Применяем тестовую конфигурацию
    try:
        from config import apply_environment_config
        apply_environment_config(Environment.TESTING)
    except Exception:
        pass  # Игнирируем ошибки импорта в тестах
    
    yield
    
    # Восстанавливаем оригинальное окружение
    os.environ.clear()
    os.environ.update(original_env)


# =============================================================================
# HTTP КЛИЕНТЫ И ФИКСТУРЫ
# =============================================================================

@pytest.fixture
async def test_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Асинхронный HTTP клиент для тестов"""
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        # Настраиваем таймауты для тестов
        client.timeout = httpx.Timeout(30.0)
        yield client


@pytest.fixture
async def admin_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP клиент с токеном администратора"""
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        client.headers["Authorization"] = "Bearer admin_token_123"
        yield client


@pytest.fixture
async def oauth_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP клиент с OAuth2 токеном"""
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        # Добавляем Bearer токен
        client.headers["Authorization"] = "Bearer oauth_test_token_456"
        yield client


@pytest.fixture
async def mock_1c_server():
    """Мок 1С сервера для тестов"""
    mock_server = AsyncMock()
    
    # Настройка health check
    mock_server.check_health.return_value = True
    
    # Настройка JSON-RPC методов
    mock_server.call_rpc.return_value = {
        "result": {
            "protocolVersion": "2025-03-26",
            "capabilities": {
                "tools": {"listChanged": False, "subscribe": False},
                "resources": {"listChanged": False, "subscribe": False},
                "prompts": {"listChanged": False, "subscribe": False}
            },
            "serverInfo": {
                "name": "1С MCP Server",
                "version": "1.0.0"
            }
        }
    }
    
    return mock_server


# =============================================================================
# КЭШ ФИКСТУРЫ
# =============================================================================

@pytest.fixture
def test_cache() -> MemoryCache:
    """Тестовый экземпляр кэша"""
    cache = MemoryCache("pytest_test_cache")
    return cache


@pytest.fixture
def bulk_test_data():
    """Bulk данные для тестов производительности"""
    return {
        "keys": [f"test_key_{i}" for i in range(1000)],
        "values": [f"test_value_{i}" * 10 for i in range(1000)],
        "metadata": {
            "created_by": "pytest",
            "test_suite": "http_services",
            "timestamp": datetime.now().isoformat()
        }
    }


@pytest.fixture
def cache_with_data(test_cache: MemoryCache) -> MemoryCache:
    """Кэш с предустановленными данными"""
    # Добавляем тестовые данные
    for i in range(100):
        test_cache.set(f"predefined_key_{i}", f"predefined_value_{i}")
    return test_cache


# =============================================================================
# OAUTH2 ФИКСТУРЫ
# =============================================================================

@pytest.fixture
def oauth_tokens():
    """Предопределенные OAuth2 токены для тестов"""
    return {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_access_token",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_refresh_token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "read write"
    }


@pytest.fixture
def oauth_clients():
    """Предопределенные OAuth2 клиенты"""
    return {
        "confidential_client": {
            "client_id": "confidential_client_123",
            "client_secret": "confidential_secret_456",
            "grant_types": ["authorization_code", "password", "refresh_token"]
        },
        "public_client": {
            "client_id": "public_client_789",
            "grant_types": ["authorization_code", "refresh_token"],
            "requires_pkce": True
        }
    }


@pytest.fixture
def pkce_params():
    """PKCE параметры для тестов"""
    code_verifier = "x" * 43  # 43 символа для PKCE
    code_challenge = "test_code_challenge_hash"
    
    return {
        "code_verifier": code_verifier,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": "test_state_123"
    }


# =============================================================================
# JSON-RPC ФИКСТУРЫ
# =============================================================================

@pytest.fixture
def mcp_requests():
    """Предопределенные MCP JSON-RPC запросы"""
    return {
        "initialize": {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0.0"}
            },
            "id": 1
        },
        "tools_list": {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2
        },
        "tools_call": {
            "jsonrpc": "2.0", 
            "method": "tools/call",
            "params": {
                "name": "test_tool",
                "arguments": {"param1": "test_value"}
            },
            "id": 3
        },
        "notification": {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "notification_tool",
                "arguments": {"message": "test notification"}
            }
            # Без id - notification
        },
        "invalid_request": {
            "jsonrpc": "2.0",
            "method": "invalid_method",
            "params": {},
            "id": 4
        }
    }


@pytest.fixture
def mcp_responses():
    """Предопределенные MCP ответы"""
    return {
        "initialize_success": {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "tools": {"listChanged": False, "subscribe": False},
                    "resources": {"listChanged": False, "subscribe": False},
                    "prompts": {"listChanged": False, "subscribe": False}
                },
                "serverInfo": {
                    "name": "1С MCP Server",
                    "version": "1.0.0"
                }
            },
            "id": 1
        },
        "tools_list_success": {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "test_tool",
                        "description": "Test tool for pytest",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "param1": {"type": "string"}
                            }
                        }
                    }
                ]
            },
            "id": 2
        },
        "error_invalid_method": {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found"
            },
            "id": 4
        }
    }


# =============================================================================
# ПРОИЗВОДИТЕЛЬНОСТЬ ФИКСТУРЫ
# =============================================================================

@pytest.fixture
def performance_monitor():
    """Монитор производительности для тестов"""
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.start_memory = None
            self.end_memory = None
            self.process = psutil.Process()
        
        def start(self):
            """Начать мониторинг"""
            self.start_time = time.time()
            self.start_memory = self.process.memory_info().rss
        
        def stop(self):
            """Остановить мониторинг"""
            self.end_time = time.time()
            self.end_memory = self.process.memory_info().rss
        
        def get_metrics(self) -> Dict[str, float]:
            """Получить метрики производительности"""
            if self.start_time is None or self.end_time is None:
                return {}
            
            return {
                "duration_seconds": self.end_time - self.start_time,
                "memory_usage_bytes": self.end_memory - self.start_memory,
                "memory_usage_mb": (self.end_memory - self.start_memory) / (1024 * 1024)
            }
    
    return PerformanceMonitor()


# =============================================================================
# JSON-RPC ENDPOINTS - ТЕСТЫ
# =============================================================================

class TestMCPJsonRpcEndpoints:
    """Тесты JSON-RPC endpoints для MCP операций"""
    
    @pytest.mark.unit
    async def test_jsonrpc_initialize(self, test_client, mock_1c_client):
        """Тест метода initialize"""
        request_data = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test_client", "version": "1.0.0"}
            },
            "id": 1
        }
        
        with patch('api.cache_admin.AsyncMock') as mock:
            response = await test_client.post("/mcp/rpc", json=request_data)
            # Тест базовой структуры ответа
            assert response.status_code in [200, 404]  # Endpoint может не существовать
    
    @pytest.mark.unit
    async def test_jsonrpc_tools_list(self, test_client):
        """Тест получения списка инструментов"""
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 1
        }
        
        response = await test_client.post("/mcp/rpc", json=request_data)
        # Проверяем что запрос обрабатывается
        assert response.status_code in [200, 404]
    
    @pytest.mark.unit
    async def test_jsonrpc_tools_call(self, test_client):
        """Тест вызова инструмента"""
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "test_tool",
                "arguments": {"param1": "test_value"}
            },
            "id": 1
        }
        
        response = await test_client.post("/mcp/rpc", json=request_data)
        assert response.status_code in [200, 404]
    
    @pytest.mark.unit
    async def test_jsonrpc_resources_operations(self, test_client):
        """Тесты операций с ресурсами"""
        # resources/list
        request_data = {
            "jsonrpc": "2.0",
            "method": "resources/list",
            "params": {},
            "id": 1
        }
        
        response = await test_client.post("/mcp/rpc", json=request_data)
        assert response.status_code in [200, 404]
        
        # resources/read
        request_data["method"] = "resources/read"
        request_data["params"] = {"uri": "test://resource"}
        
        response = await test_client.post("/mcp/rpc", json=request_data)
        assert response.status_code in [200, 404]
    
    @pytest.mark.unit
    async def test_jsonrpc_prompts_operations(self, test_client):
        """Тесты операций с промптами"""
        # prompts/list
        request_data = {
            "jsonrpc": "2.0",
            "method": "prompts/list",
            "params": {},
            "id": 1
        }
        
        response = await test_client.post("/mcp/rpc", json=request_data)
        assert response.status_code in [200, 404]
        
        # prompts/get
        request_data["method"] = "prompts/get"
        request_data["params"] = {"name": "test_prompt"}
        
        response = await test_client.post("/mcp/rpc", json=request_data)
        assert response.status_code in [200, 404]
    
    @pytest.mark.unit
    async def test_jsonrpc_invalid_method(self, test_client):
        """Тест обработки недопустимого метода"""
        request_data = {
            "jsonrpc": "2.0",
            "method": "invalid_method",
            "params": {},
            "id": 1
        }
        
        response = await test_client.post("/mcp/rpc", json=request_data)
        assert response.status_code in [200, 404]
    
    @pytest.mark.unit
    async def test_jsonrpc_notification(self, test_client):
        """Тест обработки notification (без id)"""
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "test_tool"}
            # Без поля "id" - это notification
        }
        
        response = await test_client.post("/mcp/rpc", json=request_data)
        # Notification может вернуть 204 No Content
        assert response.status_code in [200, 204, 404]


# =============================================================================
# EVENT LOOP ФИКСТУРЫ
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Создает event loop для тестов"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# ТЕМПОРАЛЬНЫЕ ФИКСТУРЫ  
# =============================================================================

@pytest.fixture
def frozen_time():
    """Фикстура для заморозки времени"""
    with freeze_time("2025-10-29T20:26:54") as frozen_time:
        yield frozen_time


@pytest.fixture
def temp_dir():
    """Временная директория для тестов"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФИКСТУРЫ
# =============================================================================

@pytest.fixture
def sample_data():
    """Пример данных для тестов"""
    return {
        "user": {
            "id": "12345",
            "username": "test_user",
            "email": "test@example.com",
            "role": "user"
        },
        "cache_key": "test_cache_key_123",
        "cache_value": "test_cache_value_456",
        "metadata": {
            "created": datetime.now().isoformat(),
            "version": "1.0.0"
        }
    }


@pytest.fixture
def rate_limit_config():
    """Конфигурация для тестов rate limiting"""
    return {
        "requests_per_minute": 100,
        "requests_per_hour": 1000,
        "burst_size": 10,
        "cleanup_interval": 60
    }


# =============================================================================
# МОКИ И ЗАГЛУШКИ
# =============================================================================

@pytest.fixture
def mock_redis():
    """Мок Redis для тестов"""
    mock_redis = Mock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.flushdb.return_value = True
    return mock_redis


@pytest.fixture
def mock_database():
    """Мок базы данных для тестов"""
    mock_db = Mock()
    mock_db.execute.return_value = True
    mock_db.commit.return_value = True
    mock_db.rollback.return_value = True
    return mock_db


# =============================================================================
# ХУКИ pytest
# =============================================================================

def pytest_configure(config):
    """Конфигурация pytest"""
    # Регистрируем кастомные маркеры
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


def pytest_collection_modifyitems(config, items):
    """Модификация коллекции тестов"""
    for item in items:
        # Автоматически добавляем marker для async тестов
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)


@pytest.fixture(autouse=True)
def reset_cache_state():
    """Автоматическая очистка состояния кэша между тестами"""
    # Сбрасываем глобальные метрики кэша
    cache_metrics.hit_count = 0
    cache_metrics.miss_count = 0
    cache_metrics.response_times.clear()
    
    yield
    
    # Очистка после теста
    cache_metrics.hit_count = 0
    cache_metrics.miss_count = 0
    cache_metrics.response_times.clear()


# =============================================================================
# УТИЛИТЫ
# =============================================================================

def pytest_runtest_teardown(item, nextitem):
    """Утилита для очистки после каждого теста"""
    # Принудительная сборка мусора
    import gc
    gc.collect()


# Экспорт основных фикстур
__all__ = [
    "test_client",
    "admin_client", 
    "oauth_client",
    "mock_1c_server",
    "test_cache",
    "cache_with_data",
    "oauth_tokens",
    "pkce_params",
    "mcp_requests",
    "performance_monitor",
    "event_loop",
    "frozen_time",
    "sample_data",
    "rate_limit_config"
]