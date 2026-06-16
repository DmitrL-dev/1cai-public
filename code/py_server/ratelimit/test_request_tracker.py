
"""
Тестирование RequestTracker
Демонстрирует работу всех компонентов системы учета запросов
"""

import asyncio
import json
import time
from unittest.mock import Mock

try:
    from .request_tracker import (DistributedTracker, IPTracker,
                                  RequestMetrics, RequestTracker, ToolTracker,
                                  UserTracker)
except ImportError:
    # Для запуска как скрипта
    import os
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from request_tracker import (DistributedTracker, IPTracker, RequestMetrics,
                                 RequestTracker, ToolTracker, UserTracker)


async def create_mock_request(ip="192.168.1.100", method="GET", path="/api/test"):
    """Создать mock FastAPI Request"""
    request = Mock()
    request.client = Mock()
    request.client.host = ip
    request.method = method
    request.url = Mock()
    request.url.path = path
    request.headers = {"user-agent": "TestClient/1.0"}
    return request


async def test_ip_tracker():
    """Тестирование IPTracker"""
    print("\n=== Тестирование IPTracker ===")
    
    tracker = IPTracker(max_size=1000, ttl=3600)
    
    # Создаем метрики для тестирования
    metrics = RequestMetrics(
        timestamp=time.time(),
        ip="192.168.1.100",
        user_id=None,
        tool_name=None,
        endpoint="/api/test",
        method="GET",
        status_code=200,
        response_time_ms=45.2,
        user_agent="TestClient/1.0",
        referer=None,
        content_length=1024
    )
    
    # Добавляем несколько запросов
    for i in range(5):
        metrics.timestamp = time.time()
        result = tracker.add_request(metrics)
        print(f"Запрос {i+1}: {'Разрешен' if result else 'Заблокирован'}")
    
    # Получаем статистику
    stats = tracker.get_ip_stats("192.168.1.100")
    print(f"Статистика IP: {json.dumps(stats, indent=2, ensure_ascii=False)}")
    
    # Тестируем блокировку
    tracker.block_ip("192.168.1.100", "Test block")
    result = tracker.add_request(metrics)
    print(f"После блокировки: {'Разрешен' if result else 'Заблокирован'}")
    
    # Разблокируем
    tracker.unblock_ip("192.168.1.100")
    result = tracker.add_request(metrics)
    print(f"После разблокировки: {'Разрешен' if result else 'Заблокирован'}")


async def test_user_tracker():
    """Тестирование UserTracker"""
    print("\n=== Тестирование UserTracker ===")
    
    tracker = UserTracker(max_size=1000, ttl=3600)
    
    # Создаем метрики для разных пользователей
    users = ["user123", "user456", "admin"]
    
    for user_id in users:
        metrics = RequestMetrics(
            timestamp=time.time(),
            ip="192.168.1.100",
            user_id=user_id,
            tool_name=None,
            endpoint="/api/test",
            method="GET",
            status_code=200,
            response_time_ms=30.0,
            user_agent="TestClient/1.0",
            referer=None,
            content_length=512
        )
        
        # Добавляем несколько запросов для пользователя
        for i in range(10):
            metrics.timestamp = time.time()
            result = tracker.add_request(metrics)
            print(f"Пользователь {user_id}, запрос {i+1}: {'Разрешен' if result else 'Заблокирован'}")
        
        # Получаем статистику
        stats = tracker.get_user_stats(user_id)
        print(f"Статистика пользователя {user_id}: {json.dumps(stats, indent=2, ensure_ascii=False)}")


async def test_tool_tracker():
    """Тестирование ToolTracker"""
    print("\n=== Тестирование ToolTracker ===")
    
    tracker = ToolTracker(max_size=1000, ttl=3600)
    
    # Тестируем разные инструменты
    tools = ["database_query", "file_operation", "report_generation"]
    
    for tool_name in tools:
        metrics = RequestMetrics(
            timestamp=time.time(),
            ip="192.168.1.100",
            user_id="user123",
            tool_name=tool_name,
            endpoint=f"/tools/{tool_name}",
            method="POST",
            status_code=200,
            response_time_ms=100.0 + hash(tool_name) % 50,  # Разное время отклика
            user_agent="TestClient/1.0",
            referer=None,
            content_length=2048
        )
        
        # Добавляем несколько вызовов инструмента
        for i in range(5):
            metrics.timestamp = time.time()
            metrics.response_time_ms = 100.0 + (i * 10)  # Увеличивающееся время
            result = tracker.add_request(metrics)
            print(f"Инструмент {tool_name}, вызов {i+1}: {'Разрешен' if result else 'Заблокирован'}")
        
        # Получаем статистику
        stats = tracker.get_tool_stats(tool_name)
        print(f"Статистика инструмента {tool_name}: {json.dumps(stats, indent=2, ensure_ascii=False)}")


async def test_distributed_tracker():
    """Тестирование DistributedTracker"""
    print("\n=== Тестирование DistributedTracker ===")
    
    # Тест с local режимом (без Redis)
    tracker = DistributedTracker(max_size=1000, ttl=3600)
    
    # Добавляем запросы локально
    request_data = {
        "timestamp": time.time(),
        "ip": "192.168.1.100",
        "user_id": "user123",
        "endpoint": "/api/test"
    }
    
    # Добавляем несколько запросов
    for i in range(3):
        result = await tracker.add_request_distributed(
            key=f"test_key_{i}",
            request_data=request_data,
            expire_seconds=3600
        )
        print(f"Distributed запрос {i+1}: {'Разрешен' if result else 'Заблокирован'}")
    
    # Получаем статистику
    for i in range(3):
        stats = await tracker.get_distributed_stats(f"test_key_{i}")
        print(f"Distributed статистика ключа {i}: {json.dumps(stats, indent=2, ensure_ascii=False)}")


async def test_full_tracker():
    """Тестирование полного RequestTracker"""
    print("\n=== Тестирование RequestTracker ===")
    
    tracker = RequestTracker(use_redis=False)
    
    # Создаем mock запрос
    request = await create_mock_request(ip="10.0.0.100", path="/api/data")
    
    # Симулируем несколько запросов
    for i in range(10):
        start_time = time.time()
        
        # Отслеживаем запрос
        allowed = await tracker.track_request(
            request=request,
            response_time_ms=25.0 + i * 5,  # Увеличивающееся время
            status_code=200,
            user_id=f"user{i % 3}",  # Ротируем пользователей
            tool_name="database_query" if i % 2 == 0 else "file_operation"
        )
        
        print(f"Запрос {i+1}: {'Разрешен' if allowed else 'Заблокирован'}")
        
        # Небольшая задержка
        await asyncio.sleep(0.01)
    
    # Получаем комплексную статистику
    stats = tracker.get_comprehensive_stats()
    print(f"Общая статистика:")
    print(f"  Всего запросов: {stats['overall']['total_requests']}")
    print(f"  Заблокировано: {stats['overall']['blocked_requests']}")
    print(f"  Процент блокировки: {stats['overall']['blocked_rate_percent']:.2f}%")
    print(f"  Запросов в секунду: {stats['overall']['requests_per_second']}")
    print(f"  Системная нагрузка CPU: {stats['system']['cpu_percent']}%")
    print(f"  Использование памяти: {stats['system']['memory_percent']}%")


async def test_performance():
    """Тестирование производительности"""
    print("\n=== Тестирование производительности ===")
    
    tracker = RequestTracker(use_redis=False)
    request = await create_mock_request()
    
    # Тестируем производительность на 1000 запросах
    num_requests = 1000
    start_time = time.time()
    
    for i in range(num_requests):
        request.client.host = f"192.168.1.{i % 255}"
        request.url.path = f"/api/test/{i}"
        
        allowed = await tracker.track_request(
            request=request,
            response_time_ms=10.0,
            status_code=200,
            user_id=f"user{i % 100}",
            tool_name="test_tool"
        )
    
    total_time = time.time() - start_time
    avg_time_per_request = (total_time / num_requests) * 1000  # в миллисекундах
    
    print(f"Выполнено запросов: {num_requests}")
    print(f"Общее время: {total_time:.3f} сек")
    print(f"Среднее время на запрос: {avg_time_per_request:.3f} ms")
    print(f"Запросов в секунду: {num_requests / total_time:.0f}")
    
    # Проверяем цель < 1ms
    if avg_time_per_request < 1.0:
        print("✅ Цель производительности достигнута (< 1ms)")
    else:
        print("❌ Превышение цели производительности")


async def test_context_manager():
    """Тестирование контекстного менеджера"""
    print("\n=== Тестирование контекстного менеджера ===")
    
    from ratelimit import (get_request_tracker, init_request_tracker,
                           request_tracking_context)
    
    await init_request_tracker({"use_redis": False})
    tracker = get_request_tracker()
    request = await create_mock_request()
    
    # Используем контекстный менеджер
    async with request_tracking_context(request, user_id="test_user", tool_name="test_tool") as tr:
        # Симулируем обработку
        await asyncio.sleep(0.01)
        print("Обработка в контексте трекера завершена")
    
    print("Контекстный менеджер работает корректно")


async def main():
    """Основная функция тестирования"""
    print("Начинаем тестирование RequestTracker...")
    
    try:
        await test_ip_tracker()
        await test_user_tracker()
        await test_tool_tracker()
        await test_distributed_tracker()
        await test_full_tracker()
        await test_performance()
        await test_context_manager()
        
        print("\n🎉 Все тесты успешно завершены!")
        
    except Exception as e:
        print(f"\n❌ Ошибка во время тестирования: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
