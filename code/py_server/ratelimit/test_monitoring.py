
"""
Тесты для системы мониторинга Rate Limiting

Проверка основной функциональности системы мониторинга
"""

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from ratelimit.metrics import (AlertManager, AlertRule, AlertSeverity,
                               PrometheusExporter, RateLimitDashboard,
                               RateLimitMetrics, RateLimitMonitoringSystem,
                               RealTimeMonitor, rate_limit_monitoring)


class TestRateLimitMetrics(unittest.TestCase):
    """Тесты для сборщика метрик"""
    
    def setUp(self):
        self.metrics = RateLimitMetrics(max_history_size=100)
    
    def test_record_request_basic(self):
        """Тест базовой записи запроса"""
        self.metrics.record_request(
            ip="192.168.1.100",
            user_id="user123",
            tool="test",
            response_time=0.150,
            blocked=False
        )
        
        summary = self.metrics.get_metrics_summary()
        self.assertEqual(summary['total_requests'], 1)
        self.assertEqual(summary['total_blocked'], 0)
    
    def test_record_blocked_request(self):
        """Тест записи заблокированного запроса"""
        self.metrics.record_request(
            ip="192.168.1.100",
            user_id="user123",
            tool="test",
            response_time=0.150,
            blocked=True
        )
        
        summary = self.metrics.get_metrics_summary()
        self.assertEqual(summary['total_requests'], 1)
        self.assertEqual(summary['total_blocked'], 1)
    
    def test_register_active_limit(self):
        """Тест регистрации активного ограничения"""
        self.metrics.register_active_limit("limit_123", {"type": "test"})
        
        summary = self.metrics.get_metrics_summary()
        self.assertEqual(summary['active_limits'], 1)
    
    def test_rps_metrics(self):
        """Тест RPS метрик"""
        # Записываем несколько запросов от одного IP
        for _ in range(5):
            self.metrics.record_request(ip="192.168.1.100", tool="test")
            time.sleep(0.1)
        
        # Проверяем что RPS метрика создана
        recent_metrics = self.metrics.get_recent_metrics(minutes=1)
        rps_metrics = [m for m in recent_metrics if m.metric_name == 'rate_limit_requests_per_second']
        self.assertTrue(len(rps_metrics) > 0)
    
    def test_health_status(self):
        """Тест статуса здоровья"""
        self.metrics.set_health_status("healthy")
        health = self.metrics.get_health_status()
        self.assertEqual(health['status'], "healthy")
        
        self.metrics.set_health_status("error")
        health = self.metrics.get_health_status()
        self.assertEqual(health['status'], "error")


class TestPrometheusExporter(unittest.TestCase):
    """Тесты для экспортера Prometheus"""
    
    def setUp(self):
        self.metrics = RateLimitMetrics()
        self.exporter = PrometheusExporter(self.metrics)
        
        # Добавляем тестовые данные
        self.metrics.record_request(ip="192.168.1.100", tool="test", response_time=0.150)
    
    def test_generate_prometheus_metrics(self):
        """Тест генерации метрик Prometheus"""
        prometheus_text = self.exporter.generate_prometheus_metrics()
        
        self.assertIn('rate_limit_requests_total', prometheus_text)
        self.assertIn('192.168.1.100', prometheus_text)
        self.assertIn('test', prometheus_text)
    
    def test_export_to_file(self):
        """Тест экспорта в файл"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            filepath = f.name
        
        try:
            self.exporter.export_to_file(filepath)
            
            # Проверяем что файл создан и содержит метрики
            self.assertTrue(os.path.exists(filepath))
            
            with open(filepath, 'r') as f:
                content = f.read()
            
            self.assertIn('rate_limit_requests_total', content)
            
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)


class TestAlertManager(unittest.TestCase):
    """Тесты для менеджера алертов"""
    
    def setUp(self):
        self.metrics = RateLimitMetrics()
        self.alert_manager = AlertManager(self.metrics)
    
    def test_add_alert_rule(self):
        """Тест добавления правила алерта"""
        rule = AlertRule(
            name="test_rule",
            metric_name="test_metric",
            condition=">",
            threshold=10.0,
            severity=AlertSeverity.WARNING
        )
        
        self.alert_manager.add_alert_rule(rule)
        self.assertIn("test_rule", self.alert_manager.alert_rules)
    
    def test_alert_evaluation(self):
        """Тест оценки алертов"""
        # Добавляем правило
        rule = AlertRule(
            name="high_block_rate",
            metric_name="rate_limit_summary_blocked_rate",
            condition=">",
            threshold=0.1,
            severity=AlertSeverity.WARNING
        )
        self.alert_manager.add_alert_rule(rule)
        
        # Генерируем много заблокированных запросов
        for _ in range(20):
            self.metrics.record_request(blocked=True)
        
        # Запускаем проверку алертов
        self.alert_manager._check_alerts()
        
        # Проверяем что алерт сработал
        active_alerts = self.alert_manager.get_active_alerts()
        self.assertTrue(len(active_alerts) > 0)
    
    def test_alert_callback(self):
        """Тест callback для алертов"""
        callback_called = []
        
        def test_callback(alerts):
            callback_called.append(len(alerts))
        
        # Добавляем callback
        self.alert_manager.add_alert_rule(AlertRule(
            name="test_alert",
            metric_name="rate_limit_health_status",
            condition="<",
            threshold=1.0,
            severity=AlertSeverity.CRITICAL
        ))
        
        # Запускаем мониторинг в отдельном потоке
        monitoring_thread = threading.Thread(target=self.alert_manager._monitoring_loop)
        monitoring_thread.daemon = True
        
        # Устанавливаем флаг остановки
        self.alert_manager._stop_monitoring = True
        
        # Тестируем что система не падает
        self.assertIsNotNone(self.alert_manager.alert_rules)


class TestRateLimitDashboard(unittest.TestCase):
    """Тесты для генератора дашбордов"""
    
    def setUp(self):
        self.metrics = RateLimitMetrics()
        self.dashboard = RateLimitDashboard(self.metrics)
    
    def test_generate_grafana_dashboard_config(self):
        """Тест генерации конфигурации дашборда"""
        config = self.dashboard.generate_grafana_dashboard_config()
        
        self.assertIn('dashboard', config)
        self.assertEqual(config['dashboard']['title'], 'Rate Limiting Monitoring')
        self.assertIn('panels', config['dashboard'])
        self.assertTrue(len(config['dashboard']['panels']) > 0)
    
    def test_get_prometheus_queries(self):
        """Тест получения PromQL запросов"""
        queries = self.dashboard.get_prometheus_queries()
        
        self.assertIn('total_requests_rate', queries)
        self.assertIn('blocked_requests_rate', queries)
        self.assertIn('active_limits', queries)
        
        # Проверяем что запросы выглядят как PromQL
        self.assertTrue(queries['total_requests_rate'].startswith('rate('))
    
    def test_export_dashboard_config(self):
        """Тест экспорта конфигурации дашборда"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            filepath = f.name
        
        try:
            self.dashboard.export_dashboard_config(filepath)
            
            # Проверяем что файл создан
            self.assertTrue(os.path.exists(filepath))
            
            # Проверяем что это валидный JSON
            import json
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            self.assertIn('dashboard', config)
            
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)


class TestRealTimeMonitor(unittest.TestCase):
    """Тесты для мониторинга в реальном времени"""
    
    def setUp(self):
        self.metrics = RateLimitMetrics()
        self.monitor = RealTimeMonitor(self.metrics)
    
    def test_add_callbacks(self):
        """Тест добавления callbacks"""
        def test_alert_callback(alerts):
            pass
        
        def test_metrics_callback(stats):
            pass
        
        self.monitor.add_alert_callback(test_alert_callback)
        self.monitor.add_metrics_callback(test_metrics_callback)
        
        self.assertEqual(len(self.monitor._alert_callbacks), 1)
        self.assertEqual(len(self.monitor._metrics_callbacks), 1)
    
    def test_get_current_stats(self):
        """Тест получения текущей статистики"""
        stats = self.monitor.get_current_stats()
        
        self.assertIn('total_checks', stats)
        self.assertIn('alerts_triggered', stats)
        self.assertIsInstance(stats['total_checks'], int)
    
    def test_force_health_check(self):
        """Тест принудительной проверки здоровья"""
        health = self.monitor.force_health_check()
        
        self.assertIn('overall_health', health)
        self.assertIn('checks', health)
        self.assertIn('timestamp', health)
        self.assertIsInstance(health['overall_health'], bool)
    
    def test_get_system_status(self):
        """Тест получения статуса системы"""
        status = self.monitor.get_system_status()
        
        self.assertIn('overall_status', status)
        self.assertIn('health', status)
        self.assertIn('monitoring_active', status)


class TestRateLimitMonitoringSystem(unittest.TestCase):
    """Тесты для полной системы мониторинга"""
    
    def setUp(self):
        self.monitoring = RateLimitMonitoringSystem(
            metrics_history_size=100,
            monitoring_interval=1,
            enable_prometheus_export=False,  # Отключаем для тестов
            enable_realtime_monitoring=False  # Отключаем для тестов
        )
    
    def tearDown(self):
        if self.monitoring._system_started:
            self.monitoring.stop()
    
    def test_system_lifecycle(self):
        """Тест жизненного цикла системы"""
        # Проверяем что система не запущена
        self.assertFalse(self.monitoring._system_started)
        
        # Запускаем систему
        self.monitoring.start()
        self.assertTrue(self.monitoring._system_started)
        
        # Останавливаем систему
        self.monitoring.stop()
        self.assertFalse(self.monitoring._system_started)
    
    def test_record_request(self):
        """Тест записи запроса"""
        self.monitoring.start()
        
        self.monitoring.record_request(
            ip="192.168.1.100",
            user_id="user123",
            tool="test",
            response_time=0.150,
            blocked=False
        )
        
        summary = self.monitoring.metrics_collector.get_metrics_summary()
        self.assertEqual(summary['total_requests'], 1)
    
    def test_register_limit(self):
        """Тест регистрации ограничения"""
        self.monitoring.start()
        
        self.monitoring.register_limit("test_limit", {"type": "test"})
        
        summary = self.monitoring.metrics_collector.get_metrics_summary()
        self.assertEqual(summary['active_limits'], 1)
    
    def test_get_system_status(self):
        """Тест получения статуса системы"""
        self.monitoring.start()
        
        status = self.monitoring.get_system_status()
        
        self.assertIn('system_started', status)
        self.assertIn('components', status)
        self.assertIn('metrics_collector', status['components'])
    
    def test_custom_alert_rule(self):
        """Тест добавления пользовательского алерта"""
        self.monitoring.start()
        
        rule = AlertRule(
            name="custom_test",
            metric_name="test_metric",
            condition=">",
            threshold=5.0,
            severity=AlertSeverity.INFO
        )
        
        self.monitoring.add_custom_alert_rule(rule)
        
        # Проверяем что правило добавлено
        self.assertIn("custom_test", self.monitoring.alert_manager.alert_rules)
    
    def test_prometheus_export(self):
        """Тест экспорта в Prometheus"""
        self.monitoring.start()
        
        # Временно включаем экспорт
        self.monitoring.enable_prometheus_export = True
        self.monitoring.record_request(tool="test")
        
        # Тестируем экспорт
        prometheus_text = self.monitoring.export_prometheus_metrics()
        self.assertIn('rate_limit_requests_total', prometheus_text)
    
    @patch('ratelimit.metrics.RateLimitDashboard.export_dashboard_config')
    def test_grafana_dashboard_export(self, mock_export):
        """Тест экспорта Grafana дашборда"""
        self.monitoring.start()
        
        with tempfile.NamedTemporaryFile(suffix='.json') as f:
            self.monitoring.export_grafana_dashboard(f.name)
        
        # Проверяем что функция экспорта была вызвана
        mock_export.assert_called_once()


class TestDecoratorMonitoring(unittest.TestCase):
    """Тесты для декоратора мониторинга"""
    
    def setUp(self):
        self.monitoring = RateLimitMonitoringSystem(
            enable_realtime_monitoring=False
        )
        self.monitoring.start()
    
    def tearDown(self):
        self.monitoring.stop()
    
    def test_rate_limit_monitoring_decorator(self):
        """Тест декоратора мониторинга"""
        
        @rate_limit_monitoring(self.monitoring)
        def test_function(ip: str, user_id: str, tool: str = "test"):
            return {"status": "success"}
        
        # Вызываем функцию
        result = test_function(ip="192.168.1.100", user_id="user123")
        
        # Проверяем результат
        self.assertEqual(result["status"], "success")
        
        # Проверяем что метрики записаны
        summary = self.monitoring.metrics_collector.get_metrics_summary()
        self.assertGreaterEqual(summary['total_requests'], 1)
    
    def test_decorator_with_exception(self):
        """Тест декоратора с исключением"""
        
        @rate_limit_monitoring(self.monitoring)
        def failing_function(ip: str):
            raise Exception("Test exception")
        
        # Проверяем что исключение проброшено
        with self.assertRaises(Exception):
            failing_function(ip="192.168.1.100")
        
        # Проверяем что метрика все равно записана
        summary = self.monitoring.metrics_collector.get_metrics_summary()
        self.assertGreaterEqual(summary['total_requests'], 1)


def run_tests():
    """Запуск всех тестов"""
    # Создаем test suite
    test_suite = unittest.TestSuite()
    
    # Добавляем тестовые классы
    test_classes = [
        TestRateLimitMetrics,
        TestPrometheusExporter,
        TestAlertManager,
        TestRateLimitDashboard,
        TestRealTimeMonitor,
        TestRateLimitMonitoringSystem,
        TestDecoratorMonitoring
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("🧪 Запуск тестов системы мониторинга Rate Limiting")
    print("=" * 60)
    
    success = run_tests()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Все тесты прошли успешно!")
    else:
        print("❌ Некоторые тесты не прошли!")
        exit(1)
