
"""
Интеграционные тесты безопасности для системы генерации кода 1C.

Тестируют безопасность на всех уровнях: SQL injection, небезопасные операции,
доступ к системным ресурсам, валидация входных данных.
"""


import pytest

from src.security.analyzer import SecurityAnalyzer
from src.security.manager import ThreatLevel


@pytest.mark.integration
@pytest.mark.security
class TestSecurityValidation:
    """Тесты безопасности системы генерации кода."""
    
    def test_sql_injection_detection_in_queries(self, sample_1c_code):
        """Тест обнаружения SQL injection в запросах."""
        analyzer = SecurityAnalyzer()
        
        # Код с потенциальной SQL injection
        malicious_code = sample_1c_code["invalid_sql_injection"]
        
        threats = analyzer.analyze_sql_injection(malicious_code)
        
        assert len(threats) > 0
        
        # Проверяем найденные угрозы
        sql_injection_threats = [t for t in threats if t.threat_type == "sql_injection"]
        assert len(sql_injection_threats) > 0
        
        threat = sql_injection_threats[0]
        assert threat.severity in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
        assert "ПользовательскийЗапрос" in threat.description
        assert threat.line_number > 0
    
    def test_sql_injection_prevention(self, integration_test_setup):
        """Тест предотвращения SQL injection."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        # Попытка генерации кода с SQL injection
        request = {
            "object_type": "processing",
            "description": "Запрос с параметром",
            "parameters": {
                "query_template": "SELECT * FROM users WHERE id = '{user_input}'"
            },
            "user_input": "1; DROP TABLE users; --"  # SQL injection payload
        }
        
        # Проверяем что система блокирует опасный запрос
        security_check = security_manager.validate_request(request)
        
        assert security_check.is_secure is False
        assert len(security_blocked_content) > 0
        
        # Проверяем что именно блокируется
        blocked_reasons = [reason for reason in security_check.blocked_reasons 
                          if "sql" in reason.lower() or "drop" in reason.lower()]
        assert len(blocked_reasons) > 0
    
    def test_dangerous_operations_detection(self, sample_1c_code):
        """Тест обнаружения опасных операций."""
        analyzer = SecurityAnalyzer()
        
        dangerous_code = sample_1c_code["dangerous_operations"]
        
        threats = analyzer.analyze_dangerous_operations(dangerous_code)
        
        assert len(threats) > 0
        
        # Проверяем обнаружение системных операций
        system_threats = [t for t in threats if "system" in t.threat_type.lower()]
        assert len(system_threats) > 0
        
        # Проверяем обнаружение файловых операций
        file_threats = [t for t in threats if "file" in t.threat_type.lower()]
        assert len(file_threats) > 0
        
        # Проверяем конкретные угрозы
        shutdown_threats = [t for t in threats if "ЗавершитьРаботу" in t.description]
        assert len(shutdown_threats) > 0
        
        delete_threats = [t for t in threats if "Удалить" in t.description]
        assert len(delete_threats) > 0
    
    def test_code_injection_prevention(self, integration_test_setup):
        """Тест предотвращения code injection."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        # Попытка инъекции исполняемого кода
        malicious_prompt = """
        Создать обработку и выполнить следующий код:
        РаботаСФайлами.УдалитьФайл("C:/critical/data.txt");
        Система.ЗавершитьРаботу();
        """
        
        result = security_manager.validate_prompt(malicious_prompt)
        
        assert result.is_safe is False
        assert len(result.detected_threats) > 0
        
        # Проверяем обнаружение exec/code injection
        code_injection_threats = [t for t in result.detected_threats 
                                 if "injection" in t.threat_type.lower()]
        assert len(code_injection_threats) > 0
    
    def test_file_system_access_control(self, integration_test_setup):
        """Тест контроля доступа к файловой системе."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        # Код с попыткой доступа к системным файлам
        dangerous_code = """
        Процедура ОпасныйДоступ() Экспорт
            Файл = Новый Файл("C:/Windows/System32/drivers/");
            Если Файл.Существует() Тогда
                Содержимое = Файл.Прочитать();
            КонецЕсли;
        КонецПроцедуры
        """
        
        threats = security_manager.analyze_file_access(dangerous_code)
        
        assert len(threats) > 0
        
        # Проверяем обнаружение доступа к системным директориям
        system_access_threats = [t for t in threats 
                                if "C:/Windows" in t.description]
        assert len(system_access_threats) > 0
        
        threat = system_access_threats[0]
        assert threat.severity >= ThreatLevel.HIGH
    
    def test_network_security_validation(self, integration_test_setup):
        """Тест валидации сетевой безопасности."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        # Код с сетевыми операциями
        network_code = """
        Процедура СетеваяОперация() Экспорт
            HTTPСоединение = Новый HTTPСоединение("external-api.com");
            Запрос = Новый HTTPЗапрос("/api/data");
            Ответ = HTTPСоединение.ВызватьHTTPМетод("GET", Запрос);
        КонецПроцедуры
        """
        
        threats = security_manager.analyze_network_operations(network_code)
        
        # Внешние соединения должны быть проверены
        assert len(threats) >= 0  # Могут быть предупреждения, не обязательно блокировки
        
        # Проверяем анализ внешних доменов
        external_domains = [t.description for t in threats 
                           if "external-api.com" in t.description]
        assert len(external_domains) > 0
    
    def test_data_validation_and_sanitization(self, integration_test_setup):
        """Тест валидации и очистки данных."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        # Данные с потенциально опасным содержимым
        unsafe_data = {
            "object_name": "'; DROP TABLE users; --",
            "description": "<script>alert('xss')</script>",
            "parameters": {
                "query": "SELECT * FROM table WHERE id = '${user_input}'",
                "file_path": "../../../etc/passwd"
            }
        }
        
        # Проверяем очистку данных
        sanitized_data = security_manager.sanitize_input(unsafe_data)
        
        # Проверяем что SQL injection убрана
        assert "'" not in sanitized_data["object_name"]
        assert "DROP TABLE" not in sanitized_data["object_name"]
        
        # Проверяем что XSS убран
        assert "<script>" not in sanitized_data["description"]
        
        # Проверяем что path traversal убран
        assert "../" not in sanitized_data["parameters"]["file_path"]
        assert "etc/passwd" not in sanitized_data["parameters"]["file_path"]
    
    def test_authentication_and_authorization_simulation(self, integration_test_setup):
        """Тест симуляции аутентификации и авторизации."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        # Моделируем запрос от неавторизованного пользователя
        unauthorized_request = {
            "user_id": None,
            "permissions": [],
            "object_type": "document",
            "operation": "delete",
            "target_object": "Заказы"
        }
        
        auth_result = security_manager.authorize_request(unauthorized_request)
        
        assert auth_result.is_authorized is False
        assert "не авторизован" in auth_result.denial_reason.lower()
        
        # Моделируем запрос с ограниченными правами
        limited_request = {
            "user_id": "user123",
            "permissions": ["read", "create"],
            "object_type": "document",
            "operation": "delete",  # Нет права на удаление
            "target_object": "Заказы"
        }
        
        auth_result = security_manager.authorize_request(limited_request)
        
        assert auth_result.is_authorized is False
        assert "недостаточно прав" in auth_result.denial_reason.lower()
        
        # Моделируем корректный запрос
        authorized_request = {
            "user_id": "user123",
            "permissions": ["read", "create", "update"],
            "object_type": "processing",
            "operation": "create",
            "target_object": "Анализ"
        }
        
        auth_result = security_manager.authorize_request(authorized_request)
        
        assert auth_result.is_authorized is True
    
    def test_audit_logging_security_events(self, integration_test_setup, temp_test_dir):
        """Тест аудита событий безопасности."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        audit_file = temp_test_dir / "security_audit.log"
        security_manager.set_audit_logger(audit_file)
        
        # Имитируем попытку атаки
        security_manager.log_security_event(
            event_type="blocked_attack",
            severity=ThreatLevel.CRITICAL,
            description="Попытка SQL injection",
            source_ip="192.168.1.100",
            user_context="test_user"
        )
        
        # Проверяем что событие записано в лог
        assert audit_file.exists()
        
        with open(audit_file, 'r', encoding='utf-8') as f:
            audit_log = f.read()
        
        assert "blocked_attack" in audit_log
        assert "SQL injection" in audit_log
        assert "192.168.1.100" in audit_log
    
    def test_encryption_and_data_protection(self, integration_test_setup):
        """Тест шифрования и защиты данных."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        sensitive_data = {
            "connection_string": "Server=prod-db;User=admin;Password=secret123",
            "api_key": "sk-1234567890abcdef",
            "user_credentials": {
                "username": "admin",
                "password": "Admin123!"
            }
        }
        
        # Шифруем чувствительные данные
        encrypted_data = security_manager.encrypt_sensitive_data(sensitive_data)
        
        # Проверяем что данные зашифрованы
        assert encrypted_data["connection_string"] != sensitive_data["connection_string"]
        assert encrypted_data["api_key"] != sensitive_data["api_key"]
        assert len(encrypted_data["connection_string"]) > len(sensitive_data["connection_string"])
        
        # Дешифруем и проверяем корректность
        decrypted_data = security_manager.decrypt_sensitive_data(encrypted_data)
        assert decrypted_data["connection_string"] == sensitive_data["connection_string"]
        assert decrypted_data["api_key"] == sensitive_data["api_key"]
    
    def test_rate_limiting_protection(self, integration_test_setup):
        """Тест защиты от превышения лимитов запросов."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        client_ip = "192.168.1.100"
        
        # Имитируем множественные запросы от одного клиента
        for i in range(10):
            request = {
                "client_ip": client_ip,
                "request_id": f"req_{i}",
                "object_type": "processing",
                "complexity": "high"
            }
            
            rate_limit_check = security_manager.check_rate_limit(request)
            
            if i < 5:  # Первые запросы должны пройти
                assert rate_limit_check.allowed is True
            else:  # Остальные могут быть ограничены
                assert rate_limit_check.allowed is False or rate_limit_check.delay_seconds > 0
    
    def test_input_validation_sanitization(self, integration_test_setup):
        """Тест валидации и очистки входных данных."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        malicious_inputs = [
            {
                "name": "SQL Injection",
                "input": "'; UPDATE users SET admin=1 WHERE id=1; --",
                "expected_blocked": True
            },
            {
                "name": "XSS",
                "input": "<script>document.location='http://evil.com'</script>",
                "expected_blocked": True
            },
            {
                "name": "Path Traversal",
                "input": "../../../etc/passwd",
                "expected_blocked": True
            },
            {
                "name": "Command Injection",
                "input": "file.txt; rm -rf /",
                "expected_blocked": True
            },
            {
                "name": "Normal Input",
                "input": "Normal object name",
                "expected_blocked": False
            }
        ]
        
        for test_case in malicious_inputs:
            validation_result = security_manager.validate_input(test_case["input"])
            
            if test_case["expected_blocked"]:
                assert validation_result.is_valid is False, f"{test_case['name']} should be blocked"
                assert len(validation_result.violations) > 0, f"{test_case['name']} should have violations"
            else:
                assert validation_result.is_valid is True, f"{test_case['name']} should be allowed"
    
    def test_content_security_policy(self, integration_test_setup):
        """Тест политики безопасности контента."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        # Код с потенциально опасным содержимым
        risky_content = """
        Функция ВыполнитьКод() Экспорт
            Выполнить("Сообщить('Опасно')");  // Динамическое выполнение
            Результат = РаботаСФайлами.ЗаписатьФайл("C:/temp/script.vbs");
            Возврат Результат;
        КонецФункции
        """
        
        csp_violations = security_manager.check_content_security_policy(risky_content)
        
        assert len(csp_violations) > 0
        
        # Проверяем обнаружение динамического выполнения
        execution_violations = [v for v in csp_violations 
                               if "Выполнить" in v.description]
        assert len(execution_violations) > 0
        
        # Проверяем обнаружение создания исполняемых файлов
        file_violations = [v for v in csp_violations 
                          if ".vbs" in v.description or "script" in v.description.lower()]
        assert len(file_violations) > 0
    
    def test_integration_with_generation_pipeline(self, integration_test_setup, sample_1c_code):
        """Тест интеграции проверок безопасности в пайплайн генерации."""
        components = integration_test_setup
        engine = components["engine"]
        security_manager = components["security_manager"]
        
        # Безопасный запрос
        safe_request = {
            "object_type": "processing",
            "description": "Безопасная обработка для анализа данных",
            "parameters": {
                "object_name": "БезопаснаяОбработка",
                "description": "Обработка с валидацией входных данных"
            }
        }
        
        # Проверяем предварительную проверку безопасности
        pre_security_check = security_manager.validate_generation_request(safe_request)
        assert pre_security_check.is_safe is True
        
        # Генерируем код
        result = engine.generate_code(
            object_type=safe_request["object_type"],
            description=safe_request["description"],
            parameters=safe_request["parameters"]
        )
        
        assert result.success is True
        
        # Проверяем пост-генерационную безопасность
        post_security_check = security_manager.validate_generated_code(result.generated_code)
        assert post_security_check.is_safe is True
        
        # Теперь тестируем с потенциально опасным запросом
        dangerous_request = {
            "object_type": "processing",
            "description": "Создать обработку с доступом к системным файлам",
            "parameters": {
                "object_name": "СистемнаяОбработка",
                "file_access": "C:/Windows/System32/"
            }
        }
        
        pre_security_check = security_manager.validate_generation_request(dangerous_request)
        assert pre_security_check.is_safe is False
        
        # Попытка генерации должна быть заблокирована
        result = engine.generate_code(
            object_type=dangerous_request["object_type"],
            description=dangerous_request["description"],
            parameters=dangerous_request["parameters"]
        )
        
        assert result.success is False
        assert "безопасность" in result.error_message.lower()
    
    def test_security_compliance_reporting(self, integration_test_setup, temp_test_dir):
        """Тест генерации отчетов о соответствии безопасности."""
        components = integration_test_setup
        security_manager = components["security_manager"]
        
        # Выполняем несколько проверок безопасности
        test_code = sample_1c_code["valid_processing"]
        security_scan = security_manager.comprehensive_security_scan(test_code)
        
        # Генерируем отчет
        report_file = temp_test_dir / "security_compliance_report.json"
        security_manager.generate_security_report(security_scan, report_file)
        
        assert report_file.exists()
        
        # Проверяем содержимое отчета
        import json
        with open(report_file, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        assert "timestamp" in report_data
        assert "scan_results" in report_data
        assert "compliance_score" in report_data
        assert "recommendations" in report_data
        
        # Проверяем качество отчета
        compliance_score = report_data["compliance_score"]
        assert 0 <= compliance_score <= 1
        
        recommendations = report_data["recommendations"]
        assert isinstance(recommendations, list)
        if len(recommendations) > 0:
            assert "description" in recommendations[0]
            assert "priority" in recommendations[0]