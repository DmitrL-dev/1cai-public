
"""
Интеграционные тесты полного цикла генерации кода 1C.

Тестируют процесс от получения запроса на генерацию до получения
готового кода с валидацией и сохранением.
"""

import asyncio

import pytest

from src.prompts.context import GenerationContext


@pytest.mark.integration
@pytest.mark.asyncio
class TestFullGenerationCycle:
    """Тесты полного цикла генерации кода."""
    
    async def test_simple_processing_generation(self, integration_test_setup, sample_generation_requests, audit_logger):
        """Тест генерации простой обработки."""
        test_name = "test_simple_processing_generation"
        params = {
            "request_type": "processing",
            "complexity": "simple"
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            request = next(r for r in sample_generation_requests if r["request_type"] == "processing")
            
            # Выполняем генерацию
            result = await components["engine"].generate_code(
                object_type=request["request_type"],
                description=request["description"],
                parameters=request["parameters"]
            )
            
            # Проверяем результат
            assert result.success is True
            assert result.generated_code is not None
            assert len(result.generated_code) > 0
            assert "Процедура ВыполнитьОбработку" in result.generated_code
            
            # Проверяем метрики
            assert result.metrics.generation_time > 0
            assert result.metrics.tokens_used > 0
            assert result.metrics.confidence_score >= 0.7
            
            audit_logger.log_test_result(
                test_name, 
                "PASS", 
                0.5,  # Примерная длительность
                {
                    "code_length": len(result.generated_code),
                    "confidence": result.metrics.confidence_score
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    async def test_complex_report_generation(self, integration_test_setup, sample_generation_requests, audit_logger):
        """Тест генерации сложного отчета с СКД."""
        test_name = "test_complex_report_generation"
        params = {
            "request_type": "report",
            "complexity": "complex",
            "features": ["СКД", "группировки", "итоги"]
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            request = next(r for r in sample_generation_requests if r["request_type"] == "report")
            
            # Обогащаем запрос для сложного отчета
            enhanced_request = {
                **request,
                "parameters": {
                    **request["parameters"],
                    "use_skd": True,
                    "groupings": ["Период", "Номенклатура"],
                    "totals": ["Количество", "Сумма"],
                    "filters": ["Дата", "Организация"]
                }
            }
            
            result = await components["engine"].generate_code(
                object_type=enhanced_request["request_type"],
                description=enhanced_request["description"],
                parameters=enhanced_request["parameters"]
            )
            
            # Проверяем результат
            assert result.success is True
            assert "СхемаКомпоновкиДанных" in result.generated_code
            assert "Настройки" in result.generated_code
            assert "Группировки" in result.generated_code
            
            # Проверяем наличие основных методов отчета
            generated_code = result.generated_code
            required_methods = [
                "ПриФормированииСпискаОтчетов",
                "Сформировать",
                "ОбновитьОтчет"
            ]
            
            for method in required_methods:
                assert method in generated_code, f"Метод {method} не найден в сгенерированном коде"
            
            audit_logger.log_test_result(test_name, "PASS", 1.2, {"features_count": 8})
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    async def test_hierarchical_catalog_generation(self, integration_test_setup, sample_generation_requests, audit_logger):
        """Тест генерации иерархического справочника."""
        test_name = "test_hierarchical_catalog_generation"
        params = {
            "request_type": "catalog",
            "hierarchical": True,
            "features": ["иерархия", "коды", "наименования"]
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            request = next(r for r in sample_generation_requests if r["request_type"] == "catalog")
            
            result = await components["engine"].generate_code(
                object_type=request["request_type"],
                description=request["description"],
                parameters=request["parameters"]
            )
            
            # Проверяем результат
            assert result.success is True
            assert "СправочникМенеджер" in result.generated_code
            assert "СправочникОбъект" in result.generated_code
            assert "Иерархия" in result.generated_code
            
            # Проверяем поддержку иерархии
            generated_code = result.generated_code
            assert "Родитель" in generated_code
            assert "ЭтоГруппа" in generated_code
            
            # Проверяем CRUD операции
            crud_methods = ["ПередЗаписью", "ПриЗаписи", "ПередУдалением"]
            for method in crud_methods:
                assert method in generated_code, f"CRUD метод {method} не найден"
            
            audit_logger.log_test_result(test_name, "PASS", 0.8, {"hierarchical": True})
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    async def test_document_with_posting_generation(self, integration_test_setup, sample_generation_requests, audit_logger):
        """Тест генерации документа с механизмом проведения."""
        test_name = "test_document_with_posting_generation"
        params = {
            "request_type": "document",
            "features": ["проведение", "движения", "табличные части"]
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            request = next(r for r in sample_generation_requests if r["request_type"] == "document")
            
            result = await components["engine"].generate_code(
                object_type=request["request_type"],
                description=request["description"],
                parameters=request["parameters"]
            )
            
            # Проверяем результат
            assert result.success is True
            assert "ДокументМенеджер" in result.generated_code
            assert "ДокументОбъект" in result.generated_code
            
            # Проверяем проведение
            generated_code = result.generated_code
            assert "ОбработкаПроведения" in generated_code
            assert "ОбработкаОтменыПроведения" in generated_code
            
            # Проверяем табличные части
            assert "Товары" in generated_code
            assert "Услуги" in generated_code
            
            # Проверяем движения по регистрам
            assert "Движения" in generated_code
            assert "Продажи" in generated_code
            assert "Взаиморасчеты" in generated_code
            
            audit_logger.log_test_result(
                test_name, 
                "PASS", 
                1.5, 
                {
                    "tabular_sections": 2,
                    "registers": 2,
                    "posting_enabled": True
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    async def test_error_handling_in_generation(self, integration_test_setup, audit_logger):
        """Тест обработки ошибок в процессе генерации."""
        test_name = "test_error_handling_in_generation"
        params = {
            "error_type": "invalid_parameters",
            "expected_behavior": "graceful_failure"
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            
            # Проверяем обработку некорректных параметров
            result = await components["engine"].generate_code(
                object_type="invalid_type",
                description="Тестовый запрос",
                parameters={}
            )
            
            # Должна быть обработана ошибка
            assert result.success is False
            assert result.error_message is not None
            assert len(result.error_message) > 0
            
            # Проверяем что сгенерирован код не создается при ошибке
            assert result.generated_code is None or result.generated_code == ""
            
            audit_logger.log_test_result(
                test_name, 
                "PASS", 
                0.3, 
                {
                    "error_handled": True,
                    "error_type": "invalid_object_type"
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    async def test_template_based_generation(self, integration_test_setup, sample_generation_requests, audit_logger):
        """Тест генерации с использованием шаблонов."""
        test_name = "test_template_based_generation"
        params = {
            "generation_method": "template",
            "template_type": "basic_processing"
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            template_processor = components["template_processor"]
            
            # Используем шаблон обработки
            result = await template_processor.generate_from_template(
                template_id="basic_processing",
                variables={
                    "object_name": "ТестоваяОбработка",
                    "description": "Обработка для тестирования",
                    "author": "TestSystem",
                    "features": "тестирование,проверка"
                }
            )
            
            # Проверяем результат
            assert result.success is True
            assert result.generated_code is not None
            assert "{{object_name}}" not in result.generated_code  # Переменные должны быть заменены
            assert "ТестоваяОбработка" in result.generated_code
            
            # Проверяем качество кода
            generated_code = result.generated_code
            assert "Процедура" in generated_code
            assert "КонецПроцедуры" in generated_code
            
            # Проверяем TODO замены
            assert "TODO: Добавить основную логику" not in generated_code
            
            audit_logger.log_test_result(
                test_name, 
                "PASS", 
                0.4, 
                {
                    "template_used": "basic_processing",
                    "variables_replaced": True
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    async def test_context_aware_generation(self, integration_test_setup, sample_generation_requests, audit_logger):
        """Тест генерации с учетом контекста."""
        test_name = "test_context_aware_generation"
        params = {
            "context_type": "1c_enterprise",
            "features": ["context_injection", "adaptive_prompts"]
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            context_builder = components["context_builder"]
            
            # Создаем контекст генерации
            generation_context = GenerationContext(
                object_type="processing",
                platform_version="8.3.18",
                database_type="MS SQL Server",
                code_style="enterprise",
                security_level="high",
                performance_requirements={
                    "max_execution_time": 30,
                    "memory_limit": "256MB"
                }
            )
            
            # Строим контекстуальный промпт
            base_prompt = "Создать обработку для анализа данных"
            contextual_prompt = await context_builder.build_prompt(base_prompt, generation_context)
            
            # Проверяем что контекст добавлен в промпт
            assert "8.3.18" in contextual_prompt
            assert "MS SQL Server" in contextual_prompt
            assert "enterprise" in contextual_prompt
            assert "high" in contextual_prompt
            
            # Генерируем код с контекстом
            result = await components["engine"].generate_code_with_context(
                base_prompt=base_prompt,
                context=generation_context,
                parameters={"object_name": "КонтекстнаяОбработка"}
            )
            
            assert result.success is True
            assert result.generated_code is not None
            
            audit_logger.log_test_result(
                test_name, 
                "PASS", 
                0.6, 
                {
                    "context_applied": True,
                    "prompt_length": len(contextual_prompt)
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    async def test_concurrent_generation(self, integration_test_setup, sample_generation_requests, audit_logger):
        """Тест параллельной генерации нескольких объектов."""
        test_name = "test_concurrent_generation"
        params = {
            "concurrent_requests": 5,
            "generation_types": ["processing", "report", "catalog", "document", "processing"]
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            engine = components["engine"]
            
            # Создаем несколько запросов
            requests = []
            object_types = ["processing", "report", "catalog", "document", "processing"]
            
            for i, obj_type in enumerate(object_types):
                requests.append(
                    engine.generate_code(
                        object_type=obj_type,
                        description=f"Параллельная генерация {i+1}",
                        parameters={
                            "object_name": f"ПараллельныйОбъект{i+1}",
                            "description": f"Объект для параллельной генерации #{i+1}",
                            "author": "TestSystem"
                        }
                    )
                )
            
            # Выполняем параллельно
            results = await asyncio.gather(*requests, return_exceptions=True)
            
            # Проверяем результаты
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Логируем ошибку но не падаем
                    print(f"Ошибка в запросе {i}: {result}")
                    continue
                    
                assert result.success is True, f"Запрос {i} не был успешным"
                assert result.generated_code is not None
                assert len(result.generated_code) > 0
                successful_results.append(result)
            
            # Проверяем что хотя бы 4 из 5 запросов выполнились успешно
            assert len(successful_results) >= 4, f"Только {len(successful_results)} из 5 запросов выполнились успешно"
            
            audit_logger.log_test_result(
                test_name, 
                "PASS", 
                2.1, 
                {
                    "total_requests": len(requests),
                    "successful_requests": len(successful_results),
                    "success_rate": len(successful_results) / len(requests)
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise
    
    async def test_prompt_optimization_integration(self, integration_test_setup, sample_generation_requests, audit_logger):
        """Тест интеграции оптимизации промптов в процесс генерации."""
        test_name = "test_prompt_optimization_integration"
        params = {
            "optimization_enabled": True,
            "target_improvement": 0.15
        }
        
        audit_logger.log_test_start(test_name, params)
        
        try:
            components = integration_test_setup
            optimizer = components["optimizer"]
            prompt_manager = components["prompt_manager"]
            
            # Создаем начальный промпт
            initial_prompt = {
                "prompt_id": "test_processing_prompt",
                "content": "Создать простую обработку для анализа",
                "variables": ["object_name", "description"],
                "category": "processing"
            }
            
            await prompt_manager.save_prompt(
                prompt_id=initial_prompt["prompt_id"],
                content=initial_prompt["content"],
                variables=initial_prompt["variables"],
                category=initial_prompt["category"]
            )
            
            # Оптимизируем промпт
            optimization_result = await optimizer.optimize_prompt(
                prompt_id=initial_prompt["prompt_id"],
                target_improvement=0.15
            )
            
            # Проверяем результат оптимизации
            assert optimization_result.improvement_percentage >= 0.15
            assert optimization_result.new_prompt_id is not None
            assert optimization_result.optimization_successful is True
            
            # Генерируем код с оптимизированным промптом
            result = await components["engine"].generate_code(
                object_type="processing",
                description="Обработка с оптимизированным промптом",
                parameters={
                    "object_name": "ОптимизированнаяОбработка",
                    "description": "Тест оптимизации промптов",
                    "author": "TestSystem"
                },
                prompt_version="optimized"
            )
            
            assert result.success is True
            assert result.metrics.confidence_score >= 0.8  # Должен быть выше после оптимизации
            
            audit_logger.log_test_result(
                test_name, 
                "PASS", 
                1.8, 
                {
                    "optimization_improvement": optimization_result.improvement_percentage,
                    "confidence_score": result.metrics.confidence_score
                }
            )
            
        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise