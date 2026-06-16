
"""
Простой тест RequestTracker без внешних зависимостей
"""

import asyncio
import os
import sys
import time

# Добавляем путь к текущей директории
sys.path.insert(0, os.path.dirname(__file__))

# Импортируем основные компоненты напрямую
try:
    from request_tracker import (DistributedTracker, IPTracker, RequestMetrics,
                                 RequestTracker, ToolTracker, UserTracker)
    print("✅ Импорт RequestTracker успешен")
except ImportError as e:
    print(f"❌ Ошибка импорта RequestTracker: {e}")
    sys.exit(1)

async def simple_test():
    """Простой тест основной функциональности"""
    print("\n=== Простой тест RequestTracker ===")
    
    # Создаем трекер без Redis
    tracker = RequestTracker(use_redis=False)
    print("✅ RequestTracker создан")
    
    # Создаем mock запрос
    class MockRequest:
        def __init__(self):
            self.client = Mock()
            self.client.host = "192.168.1.100"
            self.method = "GET"
            self.url = Mock()
            self.url.path = "/api/test"
            self.headers = {"user-agent": "TestClient/1.0"}
    
    class Mock:
        pass
    
    request = MockRequest()
    
    # Тестируем отслеживание запросов
    print("\n--- Тест tracking запросов ---")
    for i in range(5):
        allowed = await tracker.track_request(
            request=request,
            response_time_ms=25.0 + i * 5,
            status_code=200,
            user_id=f"user{i % 2}",
            tool_name="test_tool"
        )
        print(f"Запрос {i+1}: {'✅ Разрешен' if allowed else '❌ Заблокирован'}")
    
    # Получаем статистику
    print("\n--- Тест получения статистики ---")
    try:
        stats = tracker.get_comprehensive_stats()
        print(f"✅ Общая статистика получена:")
        print(f"  Всего запросов: {stats['overall']['total_requests']}")
        print(f"  Заблокировано: {stats['overall']['blocked_requests']}")
        print(f"  Процент блокировки: {stats['overall']['blocked_rate_percent']:.2f}%")
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
    
    # Тестируем отдельные трекеры
    print("\n--- Тест IPTracker ---")
    ip_tracker = IPTracker(max_size=100, ttl=3600)
    
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
    for i in range(3):
        result = ip_tracker.add_request(metrics)
        print(f"IP запрос {i+1}: {'✅ Разрешен' if result else '❌ Заблокирован'}")
    
    # Получаем статистику IP
    ip_stats = ip_tracker.get_ip_stats("192.168.1.100")
    if ip_stats:
        print(f"✅ Статистика IP получена:")
        print(f"  Всего запросов: {ip_stats['total_requests']}")
    else:
        print("❌ Статистика IP не найдена")
    
    print("\n--- Тест UserTracker ---")
    user_tracker = UserTracker(max_size=100, ttl=3600)
    
    metrics.user_id = "test_user"
    for i in range(3):
        result = user_tracker.add_request(metrics)
        print(f"Пользователь запрос {i+1}: {'✅ Разрешен' if result else '❌ Заблокирован'}")
    
    user_stats = user_tracker.get_user_stats("test_user")
    if user_stats:
        print(f"✅ Статистика пользователя получена:")
        print(f"  Всего запросов: {user_stats['total_requests']}")
        print(f"  Уровень: {user_stats['user_tier']}")
    else:
        print("❌ Статистика пользователя не найдена")
    
    print("\n--- Тест ToolTracker ---")
    tool_tracker = ToolTracker(max_size=100, ttl=3600)
    
    metrics.tool_name = "test_tool"
    for i in range(3):
        result = tool_tracker.add_request(metrics)
        print(f"Инструмент запрос {i+1}: {'✅ Разрешен' if result else '❌ Заблокирован'}")
    
    tool_stats = tool_tracker.get_tool_stats("test_tool")
    if tool_stats:
        print(f"✅ Статистика инструмента получена:")
        print(f"  Всего вызовов: {tool_stats['total_calls']}")
        print(f"  Среднее время: {tool_stats['avg_response_time_ms']}ms")
    else:
        print("❌ Статистика инструмента не найдена")
    
    print("\n--- Тест DistributedTracker ---")
    dist_tracker = DistributedTracker(max_size=100, ttl=3600)
    
    request_data = {
        "timestamp": time.time(),
        "ip": "192.168.1.100",
        "user_id": "test_user",
        "endpoint": "/api/test"
    }
    
    for i in range(3):
        result = await dist_tracker.add_request_distributed(
            key=f"test_key_{i}",
            request_data=request_data,
            expire_seconds=3600
        )
        print(f"Distributed запрос {i+1}: {'✅ Разрешен' if result else '❌ Заблокирован'}")
    
    print("\n🎉 Все тесты базовой функциональности завершены!")

if __name__ == "__main__":
    asyncio.run(simple_test())
