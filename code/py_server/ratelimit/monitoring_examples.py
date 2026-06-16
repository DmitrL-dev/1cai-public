
"""
Примеры использования системы мониторинга Rate Limiting

Демонстрация основных возможностей системы мониторинга:
- Сбор и анализ метрик
- Экспорт в Prometheus формат
- Система алертов
- Grafana дашборды
- Real-time мониторинг
"""

import random
import time
from datetime import timedelta

# Импорт системы мониторинга
try:
    from ratelimit.metrics import (AlertRule, AlertSeverity,
                                   RateLimitMonitoringSystem,
                                   rate_limit_monitoring)
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь что модуль metrics.py находится в папке ratelimit")
    exit(1)


def example_basic_monitoring():
    """Базовый пример использования системы мониторинга"""
    print("=== Базовый пример мониторинга ===")
    
    # Создание системы мониторинга
    monitoring_system = RateLimitMonitoringSystem(
        metrics_history_size=5000,
        monitoring_interval=2,
        enable_prometheus_export=True,
        enable_realtime_monitoring=True
    )
    
    try:
        # Запуск системы
        monitoring_system.start()
        
        # Симуляция запросов
        for i in range(20):
            ip = f"192.168.1.{random.randint(1, 50)}"
            user_id = f"user_{random.randint(1, 10)}"
            tool = random.choice(["search", "update", "delete", "create"])
            response_time = random.uniform(0.01, 0.3)
            blocked = random.random() < 0.05
            
            monitoring_system.record_request(
                ip=ip,
                user_id=user_id,
                tool=tool,
                response_time=response_time,
                blocked=blocked
            )
            
            time.sleep(0.1)
        
        # Получение статуса системы
        status = monitoring_system.get_system_status()
        print(f"Система запущена: {status['system_started']}")
        print(f"Активных алертов: {status['components']['alert_manager']['active_alerts']}")
        
        # Получение метрик в реальном времени
        realtime_metrics = monitoring_system.realtime_monitor.get_real_time_metrics()
        summary = realtime_metrics['summary']
        print(f"Всего запросов: {summary['total_requests']}")
        print(f"Заблокировано: {summary['total_blocked']}")
        
    finally:
        monitoring_system.stop()


def example_custom_alerts():
    """Пример настройки пользовательских алертов"""
    print("\n=== Пользовательские алерты ===")
    
    monitoring_system = RateLimitMonitoringSystem(
        enable_realtime_monitoring=True
    )
    
    try:
        monitoring_system.start()
        
        # Добавление пользовательских правил алертов
        custom_rules = [
            AlertRule(
                name="high_error_rate",
                metric_name="rate_limit_summary_blocked_rate",
                condition=">",
                threshold=0.05,  # 5% ошибок
                severity=AlertSeverity.WARNING,
                duration=timedelta(minutes=1),
                description="Высокий процент заблокированных запросов"
            ),
            AlertRule(
                name="critical_slow_responses",
                metric_name="rate_limit_response_time_seconds",
                condition=">",
                threshold=0.5,  # 500ms
                severity=AlertSeverity.CRITICAL,
                duration=timedelta(seconds=30),
                description="Критически медленные ответы"
            )
        ]
        
        for rule in custom_rules:
            monitoring_system.add_custom_alert_rule(rule)
            print(f"Добавлено правило: {rule.name}")
        
        # Симуляция нагрузки для триггера алертов
        for i in range(50):
            # Имитируем медленные ответы
            response_time = random.uniform(0.1, 1.0) if i > 40 else random.uniform(0.01, 0.1)
            blocked = random.random() < 0.1 if i > 30 else random.random() < 0.01
            
            monitoring_system.record_request(
                ip=f"192.168.1.{random.randint(1, 10)}",
                user_id=f"user_{random.randint(1, 5)}",
                tool="stress_test",
                response_time=response_time,
                blocked=blocked
            )
            
            time.sleep(0.05)
        
        # Проверяем активные алерты
        alerts = monitoring_system.get_active_alerts()
        print(f"Активных алертов: {len(alerts)}")
        for alert in alerts:
            print(f"  - {alert['rule_name']}: {alert['severity']}")
            
    finally:
        monitoring_system.stop()


def example_prometheus_export():
    """Пример экспорта метрик в Prometheus формат"""
    print("\n=== Экспорт в Prometheus ===")
    
    monitoring_system = RateLimitMonitoringSystem(
        enable_prometheus_export=True
    )
    
    try:
        monitoring_system.start()
        
        # Создаем тестовые данные
        for i in range(30):
            monitoring_system.record_request(
                ip=f"10.0.0.{i % 10}",
                user_id=f"user_{i % 5}",
                tool=f"tool_{i % 3}",
                response_time=random.uniform(0.01, 0.2),
                blocked=random.random() < 0.02
            )
            
            # Регистрация активных ограничений
            if i % 5 == 0:
                monitoring_system.register_limit(
                    f"limit_{i // 5}",
                    {"type": "rate_limit", "limit": 100, "window": 60}
                )
        
        time.sleep(2)  # Даем время на сбор метрик
        
        # Экспорт в файл
        monitoring_system.export_prometheus_metrics('/tmp/rate_limit_metrics.prom')
        print("Метрики экспортированы в /tmp/rate_limit_metrics.prom")
        
        # Получение метрик как строки
        prometheus_metrics = monitoring_system.export_prometheus_metrics()
        print("Первые 500 символов метрик:")
        print(prometheus_metrics[:500])
        
        # Получение PromQL запросов
        queries = monitoring_system.get_prometheus_queries()
        print("\nPromQL запросы:")
        for name, query in queries.items():
            print(f"  {name}: {query}")
            
    finally:
        monitoring_system.stop()


def example_grafana_dashboard():
    """Пример генерации Grafana дашборда"""
    print("\n=== Grafana дашборд ===")
    
    monitoring_system = RateLimitMonitoringSystem()
    
    try:
        monitoring_system.start()
        
        # Создаем данные для дашборда
        for i in range(25):
            monitoring_system.record_request(
                ip=f"172.16.0.{i % 20}",
                user_id=f"user_{i % 8}",
                tool=random.choice(["api_call", "database_query", "file_upload"]),
                response_time=random.uniform(0.005, 0.15),
                blocked=random.random() < 0.03
            )
            
            if i % 3 == 0:
                monitoring_system.register_limit(
                    f"active_limit_{i}",
                    {"type": "tiered_limit", "tier": i % 3 + 1}
                )
        
        time.sleep(1)
        
        # Экспорт конфигурации дашборда
        monitoring_system.export_grafana_dashboard('/tmp/rate_limit_dashboard.json')
        print("Конфигурация дашборда экспортирована в /tmp/rate_limit_dashboard.json")
        
        # Получение запросов для дашборда
        dashboard_queries = monitoring_system.get_prometheus_queries()
        print("\nЗапросы для дашборда:")
        for query_name, query in dashboard_queries.items():
            print(f"  {query_name}: {query}")
            
    finally:
        monitoring_system.stop()


def example_decorator_monitoring():
    """Пример использования декоратора для автоматического мониторинга"""
    print("\n=== Декоратор мониторинга ===")
    
    # Создаем систему мониторинга
    monitoring_system = RateLimitMonitoringSystem(
        enable_realtime_monitoring=True
    )
    
    try:
        monitoring_system.start()
        
        # Применяем декоратор к функции
        @rate_limit_monitoring(monitoring_system)
        def simulated_api_call(ip: str, user_id: str, tool: str = "api_call"):
            """Симуляция API вызова с автоматическим мониторингом"""
            # Имитируем обработку
            time.sleep(random.uniform(0.01, 0.1))
            
            # Имитируем случайные ошибки
            if random.random() < 0.05:
                raise Exception("Simulated API error")
            
            return {"status": "success", "data": "some_data"}
        
        # Вызываем функцию несколько раз
        for i in range(15):
            try:
                result = simulated_api_call(
                    ip=f"203.0.113.{i % 15}",
                    user_id=f"user_{i % 7}",
                    tool="monitored_api"
                )
                print(f"Call {i+1}: {result['status']}")
            except Exception as e:
                print(f"Call {i+1}: Error - {str(e)[:30]}")
            
            time.sleep(0.2)
        
        # Проверяем метрики
        summary = monitoring_system.metrics_collector.get_metrics_summary()
        print(f"\nСтатистика вызовов:")
        print(f"  Всего запросов: {summary['total_requests']}")
        print(f"  Заблокировано: {summary['total_blocked']}")
        print(f"  Уникальных IP: {summary['unique_ips']}")
        
    finally:
        monitoring_system.stop()


def example_health_checks():
    """Пример проверок здоровья системы"""
    print("\n=== Health Checks ===")
    
    monitoring_system = RateLimitMonitoringSystem(
        enable_realtime_monitoring=True
    )
    
    try:
        monitoring_system.start()
        
        # Добавляем callback для алертов
        def alert_handler(alerts):
            print(f"🚨 Alert callback: {len(alerts)} активных алертов")
            for alert in alerts[:3]:  # Показываем только первые 3
                print(f"  - {alert['rule_name']}: {alert['description']}")
        
        monitoring_system.realtime_monitor.add_alert_callback(alert_handler)
        
        # Добавляем callback для метрик
        def metrics_handler(stats):
            if stats['total_checks'] % 10 == 0:  # Показываем каждый 10-й
                print(f"📊 RPS: {stats.get('peak_rps', 0):.1f}, "
                      f"Response time: {stats.get('avg_response_time', 0):.3f}s")
        
        monitoring_system.realtime_monitor.add_metrics_callback(metrics_handler)
        
        # Принудительная проверка здоровья
        health = monitoring_system.realtime_monitor.force_health_check()
        print(f"Проверка здоровья системы:")
        print(f"  Общий статус: {'Здоров' if health['overall_health'] else 'Не здоров'}")
        print(f"  Компоненты:")
        for check, result in health['checks'].items():
            status = "✓" if result else "✗"
            print(f"    {status} {check}")
        
        # Симуляция нагрузки для триггера проверок
        for i in range(50):
            monitoring_system.record_request(
                ip=f"198.51.100.{i % 25}",
                user_id=f"user_{i % 12}",
                tool="health_check_test",
                response_time=random.uniform(0.01, 0.3),
                blocked=random.random() < 0.08
            )
            
            if i % 10 == 0:
                monitoring_system.register_limit(
                    f"health_limit_{i // 10}",
                    {"type": "health_check", "threshold": 0.8}
                )
            
            time.sleep(0.1)
        
        # Финальная проверка здоровья
        final_health = monitoring_system.realtime_monitor.force_health_check()
        print(f"\nФинальная проверка:")
        print(f"  Статус: {'Здоров' if final_health['overall_health'] else 'Не здоров'}")
        
        # Статус системы
        system_status = monitoring_system.get_system_status()
        print(f"  Время работы: {system_status['uptime_seconds']:.1f} сек")
        print(f"  Активных алертов: {len(system_status['realtime_metrics']['active_alerts'])}")
        
    finally:
        monitoring_system.stop()


def main():
    """Запуск всех примеров"""
    print("🚀 Демонстрация системы мониторинга Rate Limiting")
    print("=" * 60)
    
    examples = [
        ("Базовый мониторинг", example_basic_monitoring),
        ("Пользовательские алерты", example_custom_alerts),
        ("Экспорт в Prometheus", example_prometheus_export),
        ("Grafana дашборд", example_grafana_dashboard),
        ("Декоратор мониторинга", example_decorator_monitoring),
        ("Health Checks", example_health_checks),
    ]
    
    for name, example_func in examples:
        try:
            print(f"\n{'='*20} {name} {'='*20}")
            example_func()
            time.sleep(1)  # Пауза между примерами
        except KeyboardInterrupt:
            print("\nПрервано пользователем")
            break
        except Exception as e:
            print(f"\nОшибка в примере {name}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ Все примеры завершены успешно!")
    print("\nСозданные файлы:")
    print("  - /tmp/rate_limit_metrics.prom (метрики Prometheus)")
    print("  - /tmp/rate_limit_dashboard.json (конфигурация Grafana)")


if __name__ == "__main__":
    main()
