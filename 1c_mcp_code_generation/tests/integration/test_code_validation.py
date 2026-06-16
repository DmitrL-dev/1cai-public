
"""
Интеграционные тесты валидации сгенерированного кода 1C.

Тестируют различные аспекты валидации: синтаксис, семантика, 
соответствие стандартам 1C, производительность.
"""


import pytest

from src.core.validator import CodeValidator


@pytest.mark.integration
class TestCodeValidation:
    """Тесты валидации сгенерированного кода."""
    
    def test_syntax_validation_valid_code(self, sample_1c_code):
        """Тест валидации синтаксиса корректного кода."""
        validator = CodeValidator()
        
        result = validator.validate_syntax(sample_1c_code["valid_processing"])
        
        assert result.is_valid is True
        assert len(result.issues) == 0
        assert result.confidence_score >= 0.9
    
    def test_syntax_validation_invalid_code(self, sample_1c_code):
        """Тест валидации синтаксиса некорректного кода."""
        validator = CodeValidator()
        
        invalid_code = """
        Процедура Тест() Экспорт
            // Отсутствует закрывающая скобка
            Если Истина Тогда
                Сообщить("Тест")
            // КонецЕсли отсутствует
        КонецПроцедуры
        """
        
        result = validator.validate_syntax(invalid_code)
        
        assert result.is_valid is False
        assert len(result.issues) > 0
        
        # Проверяем что найдены конкретные проблемы
        syntax_issues = [issue for issue in result.issues if issue.severity == "error"]
        assert len(syntax_issues) > 0
    
    def test_semantic_validation_procedures(self, sample_1c_code):
        """Тест семантической валидации процедур и функций."""
        validator = CodeValidator()
        
        result = validator.validate_semantics(sample_1c_code["valid_processing"])
        
        assert result.is_valid is True
        assert len(result.issues) == 0
        
        # Проверяем что найдены процедуры
        semantic_info = result.semantic_analysis
        assert "procedures" in semantic_info
        assert len(semantic_info["procedures"]) > 0
        
        # Проверяем что найдена процедура ВыполнитьАнализ
        procedures = semantic_info["procedures"]
        analyze_procedures = [p for p in procedures if "ВыполнитьАнализ" in p["name"]]
        assert len(analyze_procedures) == 1
    
    def test_semantic_validation_query_syntax(self, sample_1c_code):
        """Тест семантической валидации синтаксиса запросов."""
        validator = CodeValidator()
        
        result = validator.validate_semantics(sample_1c_code["valid_processing"])
        
        assert result.is_valid is True
        
        # Проверяем что найдены запросы
        semantic_info = result.semantic_analysis
        assert "queries" in semantic_info
        
        queries = semantic_info["queries"]
        assert len(queries) > 0
        
        # Проверяем что запрос корректный
        query = queries[0]
        assert "SELECT" in query["text"].upper()
        assert "FROM" in query["text"].upper()
    
    def test_1c_standards_compliance(self, sample_1c_code):
        """Тест соответствия стандартам разработки 1C."""
        validator = CodeValidator()
        
        result = validator.validate_1c_standards(sample_1c_code["valid_processing"])
        
        assert result.is_valid is True
        assert result.compliance_score >= 0.8
        
        # Проверяем конкретные стандарты
        standards_check = result.standards_check
        
        # Проверка кодировки
        assert "encoding" in standards_check
        assert standards_check["encoding"] == "utf-8"
        
        # Проверка комментариев
        assert "comments" in standards_check
        assert standards_check["comments"]["has_main_comment"] is True
        
        # Проверка структуры
        assert "structure" in standards_check
        assert standards_check["structure"]["has_proper_procedures"] is True
    
    def test_performance_validation(self, sample_1c_code):
        """Тест валидации производительности кода."""
        validator = CodeValidator()
        
        result = validator.validate_performance(sample_1c_code["valid_processing"])
        
        assert result.performance_score >= 0.7
        
        # Проверяем конкретные метрики
        performance_metrics = result.performance_metrics
        
        assert "query_optimization" in performance_metrics
        assert "loop_efficiency" in performance_metrics
        assert "memory_usage" in performance_metrics
        
        # В корректном коде должны быть хорошие показатели
        assert performance_metrics["query_optimization"] >= 0.8
        assert performance_metrics["loop_efficiency"] >= 0.7
    
    def test_security_validation_safe_code(self, sample_1c_code):
        """Тест валидации безопасности для безопасного кода."""
        validator = CodeValidator()
        
        result = validator.validate_security(sample_1c_code["valid_processing"])
        
        assert result.is_valid is True
        assert result.security_score >= 0.8
        
        # Проверяем отсутствие SQL injection
        security_checks = result.security_checks
        assert "sql_injection" in security_checks
        assert security_checks["sql_injection"]["detected"] is False
        
        # Проверяем безопасные операции
        assert "safe_operations" in security_checks
        assert security_checks["safe_operations"]["count"] > 0
    
    def test_security_validation_dangerous_code(self, sample_1c_code):
        """Тест валидации безопасности для опасного кода."""
        validator = CodeValidator()
        
        result = validator.validate_security(sample_1c_code["dangerous_operations"])
        
        assert result.is_valid is False
        assert result.security_score < 0.5
        
        # Проверяем обнаруженные угрозы
        security_checks = result.security_checks
        assert "sql_injection" in security_checks
        assert "dangerous_operations" in security_checks
        assert "file_system_access" in security_checks
        
        # Должны быть обнаружены опасные операции
        dangerous_ops = security_checks["dangerous_operations"]
        assert dangerous_ops["count"] > 0
        assert any("ЗавершитьРаботу" in op for op in dangerous_ops["operations"])
    
    def test_sql_injection_detection(self, sample_1c_code):
        """Тест обнаружения SQL injection."""
        validator = CodeValidator()
        
        result = validator.check_sql_injection(sample_1c_code["invalid_sql_injection"])
        
        assert result["detected"] is True
        assert len(result["vulnerabilities"]) > 0
        
        # Проверяем тип найденной уязвимости
        vulnerability = result["vulnerabilities"][0]
        assert vulnerability["type"] == "sql_injection"
        assert vulnerability["severity"] in ["high", "critical"]
        
        # Проверяем место обнаружения
        assert "line" in vulnerability
        assert "column" in vulnerability
        assert "ПользовательскийЗапрос" in vulnerability["description"]
    
    def test_code_quality_metrics(self, sample_1c_code):
        """Тест расчета метрик качества кода."""
        validator = CodeValidator()
        
        result = validator.calculate_quality_metrics(sample_1c_code["valid_processing"])
        
        assert "complexity" in result
        assert "maintainability" in result
        assert "readability" in result
        assert "testability" in result
        
        # Все метрики должны быть положительными
        assert result["complexity"] > 0
        assert result["maintainability"] > 0
        assert result["readability"] > 0
        assert result["testability"] > 0
        
        # Для качественного кода метрики должны быть высокими
        assert result["complexity"] <= 10  # Низкая сложность
        assert result["maintainability"] >= 0.7
        assert result["readability"] >= 0.8
    
    def test_validation_of_generated_processing(self, integration_test_setup):
        """Тест валидации сгенерированной обработки."""
        components = integration_test_setup
        validator = components["validator"]
        
        # Генерируем код обработки
        generated_code = """
        &НаСервере
        Процедура ВыполнитьОбработку() Экспорт
            Запрос = Новый Запрос;
            Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура";
            Результат = Запрос.Выполнить();
            
            Пока Результат.Следующий() Цикл
                Сообщить("Номенклатура: " + Результат.Наименование);
            КонецЦикла;
        КонецПроцедуры
        """
        
        # Выполняем комплексную валидацию
        syntax_result = validator.validate_syntax(generated_code)
        semantic_result = validator.validate_semantics(generated_code)
        standards_result = validator.validate_1c_standards(generated_code)
        performance_result = validator.validate_performance(generated_code)
        security_result = validator.validate_security(generated_code)
        
        # Проверяем что все проверки прошли успешно
        assert syntax_result.is_valid is True
        assert semantic_result.is_valid is True
        assert standards_result.is_valid is True
        assert performance_result.performance_score >= 0.7
        assert security_result.security_score >= 0.8
    
    def test_validation_report_generation(self, integration_test_setup, temp_test_dir):
        """Тест генерации отчета валидации."""
        components = integration_test_setup
        validator = components["validator"]
        
        # Валидируем код
        validation_result = validator.comprehensive_validation(
            sample_1c_code["valid_processing"]
        )
        
        # Генерируем отчет
        report_file = temp_test_dir / "validation_report.json"
        validator.generate_validation_report(validation_result, report_file)
        
        # Проверяем что файл создан
        assert report_file.exists()
        
        # Проверяем содержимое отчета
        import json
        with open(report_file, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        assert "timestamp" in report_data
        assert "validation_result" in report_data
        assert "summary" in report_data
        assert "details" in report_data
        
        # Проверяем качество отчета
        summary = report_data["summary"]
        assert "total_issues" in summary
        assert "critical_issues" in summary
        assert "warnings" in summary
        assert "overall_score" in summary
    
    def test_custom_validation_rules(self, integration_test_setup):
        """Тест пользовательских правил валидации."""
        components = integration_test_setup
        validator = components["validator"]
        
        # Добавляем пользовательское правило
        custom_rule = {
            "name": " обязательная процедура логирования",
            "pattern": r"ЗаписатьЛог\(",
            "severity": "warning",
            "description": "Все процедуры должны содержать логирование"
        }
        
        validator.add_custom_rule(custom_rule)
        
        # Код без логирования
        code_without_logging = """
        Процедура ВыполнитьОперацию() Экспорт
            // Основная логика без логирования
            Сообщить("Операция выполнена");
        КонецПроцедуры
        """
        
        result = validator.validate_with_custom_rules(code_without_logging)
        
        assert result.is_valid is True  # Валидация прошла, но есть предупреждение
        assert len(result.issues) > 0
        
        # Проверяем что найдено предупреждение о логировании
        logging_issues = [issue for issue in result.issues if "логирование" in issue.message.lower()]
        assert len(logging_issues) > 0
        
        logging_issue = logging_issues[0]
        assert logging_issue.severity == "warning"
        assert logging_issue.rule_name == " обязательная процедура логирования"
    
    def test_validation_performance_benchmark(self, integration_test_setup):
        """Тест производительности валидации."""
        import time
        
        components = integration_test_setup
        validator = components["validator"]
        
        # Создаем большой код для тестирования производительности
        large_code = sample_1c_code["valid_processing"] * 100  # Увеличиваем в 100 раз
        
        start_time = time.time()
        result = validator.comprehensive_validation(large_code)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Валидация должна выполняться быстро (менее 5 секунд для большого кода)
        assert execution_time < 5.0
        
        # Результат должен быть корректным
        assert result.is_valid is True
        assert len(result.issues) >= 0  # Может быть предупреждения
        
        # Проверяем что производительность отслеживается
        assert hasattr(result, "validation_time")
        assert result.validation_time > 0
        assert result.validation_time <= execution_time + 0.1  # Допускаем небольшую погрешность
    
    def test_validation_batch_processing(self, integration_test_setup, sample_1c_code):
        """Тест пакетной валидации нескольких файлов."""
        components = integration_test_setup
        validator = components["validator"]
        
        # Создаем список кодов для валидации
        code_samples = [
            sample_1c_code["valid_processing"],
            sample_1c_code["proper_validation"],
            sample_1c_code["dangerous_operations"],  # Этот должен быть невалидным
        ]
        
        # Выполняем пакетную валидацию
        results = validator.validate_batch(code_samples)
        
        assert len(results) == len(code_samples)
        
        # Первые два должны быть валидными
        assert results[0].is_valid is True
        assert results[1].is_valid is True
        
        # Третий должен быть невалидным (опасный код)
        assert results[2].is_valid is False
        
        # Проверяем статистику пакетной валидации
        batch_stats = validator.get_batch_statistics(results)
        assert "total_processed" in batch_stats
        assert "valid_count" in batch_stats
        assert "invalid_count" in batch_stats
        assert "average_time" in batch_stats
        assert batch_stats["total_processed"] == len(code_samples)
        assert batch_stats["valid_count"] == 2
        assert batch_stats["invalid_count"] == 1
    
    def test_code_formatting_validation(self, integration_test_setup):
        """Тест валидации форматирования кода."""
        components = integration_test_setup
        validator = components["validator"]
        
        # Плохо отформатированный код
        poorly_formatted_code = """
Процедура Тест()Экспорт
Если Истина Тогда
Сообщить("Тест")
КонецЕсли;
КонецПроцедуры
"""
        
        result = validator.validate_formatting(poorly_formatted_code)
        
        assert result.is_valid is False
        assert len(result.formatting_issues) > 0
        
        # Проверяем конкретные проблемы форматирования
        formatting_issues = result.formatting_issues
        
        # Должны быть проблемы с отступами
        indentation_issues = [issue for issue in formatting_issues if "отступ" in issue.message.lower()]
        assert len(indentation_issues) > 0
        
        # Должны быть проблемы с пробелами
        spacing_issues = [issue for issue in formatting_issues if "пробел" in issue.message.lower()]
        assert len(spacing_issues) > 0
        
        # Проверяем что можно получить исправленную версию
        formatted_code = validator.format_code(poorly_formatted_code)
        assert formatted_code != poorly_formatted_code
        assert formatted_code.count("\n") > poorly_formatted_code.count("\n")  # Больше переносов строк
        
        # Проверяем что отформатированный код проходит валидацию
        revalidation_result = validator.validate_formatting(formatted_code)
        assert revalidation_result.formatting_issues == []  # Нет проблем с форматированием
    
    def test_documentation_compliance(self, integration_test_setup):
        """Тест соответствия требованиям к документации."""
        components = integration_test_setup
        validator = components["validator"]
        
        # Код с документацией
        documented_code = """
// ============================================================================
// Модуль: АнализПродаж
// Назначение: Обработка для анализа продаж по периодам
// Дата: 30.10.2025
// Версия: 1.0
// ============================================================================

&НаСервере
Процедура ВыполнитьАнализ() Экспорт
    // Выполняет анализ продаж за указанный период
    // Параметры: Нет
    // Возвращаемое значение: Таблица значений с результатами анализа
    
    Попытка
        Запрос = Новый Запрос;
        Запрос.Текст = "ВЫБРАТЬ * ИЗ РегистрНакопления.Продажи.ОстаткиИОбороты";
        Результат = Запрос.Выполнить();
        Возврат Результат.Выгрузить();
    Исключение
        ЗаписатьЛог("Ошибка анализа продаж: " + ОписаниеОшибки());
        Возврат Неопределено;
    КонецПопытки;
КонецПроцедуры
"""
        
        result = validator.validate_documentation(documented_code)
        
        assert result.is_valid is True
        assert result.documentation_score >= 0.8
        
        # Проверяем конкретные элементы документации
        doc_elements = result.documentation_elements
        
        assert doc_elements["has_module_header"] is True
        assert doc_elements["has_procedure_documentation"] is True
        assert doc_elements["has_parameter_descriptions"] is True
        assert doc_elements["has_return_value_documentation"] is True
        assert doc_elements["has_error_handling_documentation"] is True
        
        # Проверяем качество документации
        quality_metrics = result.quality_metrics
        assert quality_metrics["completeness"] >= 0.8
        assert quality_metrics["clarity"] >= 0.7
        assert quality_metrics["consistency"] >= 0.8