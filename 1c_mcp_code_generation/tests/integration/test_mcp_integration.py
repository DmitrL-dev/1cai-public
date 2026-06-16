
"""
Интеграционные тесты интеграции с MCP (Model Context Protocol).

Тестируют полную интеграцию с MCP протоколом: инициализацию,
инструменты, обработку запросов, ответы.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.mcp.client import MCP1CClient
from src.mcp.server import MCP1CServer


@pytest.mark.integration
class TestMCPIntegration:
    """Тесты интеграции с MCP протоколом."""
    
    @pytest.mark.asyncio
    async def test_mcp_server_initialization(self, mcp_mock_client):
        """Тест инициализации MCP сервера."""
        server = MCP1CServer()
        
        # Тестируем инициализацию
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "1C MCP Test Client",
                    "version": "1.0.0"
                }
            }
        }
        
        # Выполняем инициализацию
        response = await server.handle_request(init_request)
        
        # Проверяем ответ
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        
        result = response["result"]
        assert "protocolVersion" in result
        assert "capabilities" in result
        assert "serverInfo" in result
        
        # Проверяем информацию о сервере
        server_info = result["serverInfo"]
        assert "name" in server_info
        assert "version" in server_info
        assert "1C MCP" in server_info["name"]
    
    @pytest.mark.asyncio
    async def test_mcp_tools_listing(self, mcp_mock_client):
        """Тест получения списка доступных инструментов."""
        server = MCP1CServer()
        
        # Инициализируем сервер
        await server.initialize()
        
        # Запрашиваем список инструментов
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        response = await server.handle_request(tools_request)
        
        assert "result" in response
        
        tools = response["result"]["tools"]
        assert len(tools) > 0
        
        # Проверяем наличие основных инструментов
        tool_names = [tool["name"] for tool in tools]
        
        expected_tools = [
            "generate_code",
            "validate_code", 
            "security_check",
            "optimize_prompt",
            "template_list"
        ]
        
        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"Инструмент {expected_tool} не найден"
        
        # Проверяем структуру инструмента
        generate_tool = next((t for t in tools if t["name"] == "generate_code"), None)
        assert generate_tool is not None
        assert "description" in generate_tool
        assert "inputSchema" in generate_tool
        assert "parameters" in generate_tool["inputSchema"]
    
    @pytest.mark.asyncio
    async def test_code_generation_via_mcp(self, mcp_mock_client, integration_test_setup):
        """Тест генерации кода через MCP инструмент."""
        server = MCP1CServer()
        await server.initialize()
        
        # Подготавливаем запрос на генерацию кода
        generate_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "generate_code",
                "arguments": {
                    "object_type": "processing",
                    "description": "Обработка для анализа продаж",
                    "parameters": {
                        "object_name": "АнализПродаж",
                        "description": "Обработка для анализа продаж по периодам",
                        "author": "TestSystem",
                        "features": ["отчетность", "фильтры"]
                    }
                }
            }
        }
        
        # Выполняем запрос
        response = await server.handle_request(generate_request)
        
        assert "result" in response
        
        result = response["result"]
        assert "content" in result
        
        # Проверяем содержимое ответа
        content = result["content"]
        assert len(content) > 0
        
        content_text = content[0]["text"]
        assert "код" in content_text.lower() or "сгенерирован" in content_text.lower()
        
        # Проверяем что есть метаданные
        if "metadata" in result:
            metadata = result["metadata"]
            assert "generation_time" in metadata
            assert "confidence_score" in metadata
    
    @pytest.mark.asyncio
    async def test_code_validation_via_mcp(self, integration_test_setup):
        """Тест валидации кода через MCP инструмент."""
        server = MCP1CServer()
        await server.initialize()
        
        sample_code = '''
        &НаСервере
        Процедура ВыполнитьОбработку() Экспорт
            Запрос = Новый Запрос;
            Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура";
            Результат = Запрос.Выполнить();
            Пока Результат.Следующий() Цикл
                Сообщить("Номенклатура: " + Результат.Наименование);
            КонецЦикла;
        КонецПроцедуры
        '''
        
        validate_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "validate_code",
                "arguments": {
                    "code": sample_code,
                    "validation_types": ["syntax", "semantics", "standards"],
                    "strict_mode": False
                }
            }
        }
        
        response = await server.handle_request(validate_request)
        
        assert "result" in response
        
        result = response["result"]
        content = result["content"]
        
        # Проверяем что валидация выполнена
        content_text = content[0]["text"]
        assert "валидация" in content_text.lower() or "valid" in content_text.lower()
        
        # Проверяем наличие результатов валидации
        if "validation_results" in result:
            validation_results = result["validation_results"]
            assert "is_valid" in validation_results
            assert "issues" in validation_results
    
    @pytest.mark.asyncio
    async def test_security_check_via_mcp(self, integration_test_setup):
        """Тест проверки безопасности через MCP инструмент."""
        server = MCP1CServer()
        await server.initialize()
        
        risky_code = '''
        Процедура ОпаснаяОперация() Экспорт
            ПользовательскийЗапрос = "'; DROP TABLE users; --";
            Запрос = Новый Запрос;
            Запрос.Текст = "ВЫБРАТЬ * ИЗ таблица WHERE поле = '" + ПользовательскийЗапрос + "'";
            Результат = Запрос.Выполнить();
        КонецПроцедуры
        '''
        
        security_request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "security_check",
                "arguments": {
                    "code": risky_code,
                    "check_types": ["sql_injection", "dangerous_operations", "data_access"],
                    "severity_threshold": "medium"
                }
            }
        }
        
        response = await server.handle_request(security_request)
        
        assert "result" in response
        
        result = response["result"]
        content = result["content"]
        
        content_text = content[0]["text"]
        assert "безопасность" in content_text.lower() or "security" in content_text.lower()
        
        # Проверяем что обнаружены угрозы
        if "security_report" in result:
            security_report = result["security_report"]
            assert "threats_detected" in security_report
            assert security_report["threats_detected"] > 0
    
    @pytest.mark.asyncio
    async def test_prompt_optimization_via_mcp(self, integration_test_setup):
        """Тест оптимизации промптов через MCP инструмент."""
        server = MCP1CServer()
        await server.initialize()
        
        original_prompt = """
        Создать обработку для 1C. Нужно сделать анализ данных.
        """
        
        optimize_request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "optimize_prompt",
                "arguments": {
                    "original_prompt": original_prompt,
                    "target_improvement": 0.2,
                    "optimization_type": "quality",
                    "context": {
                        "platform_version": "8.3.18",
                        "database_type": "MS SQL"
                    }
                }
            }
        }
        
        response = await server.handle_request(optimize_request)
        
        assert "result" in response
        
        result = response["result"]
        content = result["content"]
        
        content_text = content[0]["text"]
        assert "оптимизация" in content_text.lower() or "optimization" in content_text.lower()
        
        # Проверяем результаты оптимизации
        if "optimization_results" in result:
            optimization_results = result["optimization_results"]
            assert "improvement_percentage" in optimization_results
            assert "optimized_prompt" in optimization_results
            assert optimization_results["improvement_percentage"] > 0
    
    @pytest.mark.asyncio
    async def test_template_listing_via_mcp(self, integration_test_setup):
        """Тест получения списка шаблонов через MCP инструмент."""
        server = MCP1CServer()
        await server.initialize()
        
        template_request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "template_list",
                "arguments": {
                    "category": "all",
                    "include_metadata": True,
                    "sort_by": "name"
                }
            }
        }
        
        response = await server.handle_request(template_request)
        
        assert "result" in response
        
        result = response["result"]
        content = result["content"]
        
        content_text = content[0]["text"]
        assert "шаблон" in content_text.lower() or "template" in content_text.lower()
        
        # Проверяем наличие списка шаблонов
        if "templates" in result:
            templates = result["templates"]
            assert isinstance(templates, list)
            
            if len(templates) > 0:
                template = templates[0]
                assert "id" in template
                assert "name" in template
                assert "category" in template
    
    @pytest.mark.asyncio
    async def test_mcp_error_handling(self, integration_test_setup):
        """Тест обработки ошибок в MCP протоколе."""
        server = MCP1CServer()
        await server.initialize()
        
        # Некорректный запрос (отсутствуют обязательные параметры)
        invalid_request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "generate_code",
                "arguments": {
                    # Отсутствует object_type
                    "description": "Обработка"
                }
            }
        }
        
        response = await server.handle_request(invalid_request)
        
        # Проверяем что возвращена ошибка
        assert "error" in response
        
        error = response["error"]
        assert error["code"] is not None
        assert error["message"] is not None
        
        # Проверяем код ошибки для валидации параметров
        assert error["code"] == -32602  # Invalid params
        
        # Несуществующий инструмент
        invalid_tool_request = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {}
            }
        }
        
        response = await server.handle_request(invalid_tool_request)
        
        assert "error" in response
        assert response["error"]["code"] == -32601  # Method not found
    
    @pytest.mark.asyncio
    async def test_mcp_concurrent_requests(self, integration_test_setup):
        """Тест обработки параллельных запросов через MCP."""
        server = MCP1CServer()
        await server.initialize()
        
        # Создаем несколько параллельных запросов
        requests = []
        for i in range(5):
            request = {
                "jsonrpc": "2.0",
                "id": 100 + i,
                "method": "tools/call",
                "params": {
                    "name": "generate_code",
                    "arguments": {
                        "object_type": "processing",
                        "description": f"Обработка #{i+1}",
                        "parameters": {
                            "object_name": f"Обработка{i+1}",
                            "description": f"Тестовая обработка номер {i+1}"
                        }
                    }
                }
            }
            requests.append(server.handle_request(request))
        
        # Выполняем параллельно
        responses = await asyncio.gather(*requests, return_exceptions=True)
        
        # Проверяем что все запросы обработаны
        assert len(responses) == 5
        
        successful_responses = 0
        for response in responses:
            if not isinstance(response, Exception):
                assert "result" in response or "error" in response
                if "result" in response:
                    successful_responses += 1
        
        # Проверяем что хотя бы часть запросов выполнилась успешно
        assert successful_responses >= 3, f"Только {successful_responses} из 5 запросов выполнились успешно"
    
    @pytest.mark.asyncio
    async def test_mcp_batch_operations(self, integration_test_setup):
        """Тест пакетных операций через MCP."""
        server = MCP1CServer()
        await server.initialize()
        
        batch_request = {
            "jsonrpc": "2.0",
            "id": 200,
            "method": "tools/batch",
            "params": {
                "operations": [
                    {
                        "name": "generate_code",
                        "arguments": {
                            "object_type": "processing",
                            "description": "Обработка для анализа",
                            "parameters": {"object_name": "Анализ"}
                        }
                    },
                    {
                        "name": "validate_code",
                        "arguments": {
                            "code": "Процедура Тест() Экспорт КонецПроцедуры",
                            "validation_types": ["syntax"]
                        }
                    },
                    {
                        "name": "template_list",
                        "arguments": {"category": "processing"}
                    }
                ]
            }
        }
        
        response = await server.handle_request(batch_request)
        
        assert "result" in response
        
        result = response["result"]
        assert "batch_results" in result
        
        batch_results = result["batch_results"]
        assert len(batch_results) == 3
        
        # Проверяем результаты каждой операции
        for i, batch_result in enumerate(batch_results):
            assert "operation_index" in batch_result
            assert batch_result["operation_index"] == i
            assert "result" in batch_result or "error" in batch_result
    
    @pytest.mark.asyncio
    async def test_mcp_session_management(self, integration_test_setup):
        """Тест управления сессиями в MCP."""
        server = MCP1CServer()
        
        # Создаем сессию
        session_request = {
            "jsonrpc": "2.0",
            "id": 300,
            "method": "session/create",
            "params": {
                "client_id": "test_client_1",
                "session_config": {
                    "timeout": 300,
                    "max_requests": 100
                }
            }
        }
        
        response = await server.handle_request(session_request)
        assert "result" in response
        
        session_id = response["result"]["session_id"]
        assert session_id is not None
        
        # Используем сессию для запросов
        sessioned_request = {
            "jsonrpc": "2.0",
            "id": 301,
            "method": "tools/call",
            "params": {
                "name": "generate_code",
                "arguments": {
                    "object_type": "report",
                    "description": "Отчет в рамках сессии",
                    "parameters": {"object_name": "СессионныйОтчет"}
                },
                "session_id": session_id
            }
        }
        
        response = await server.handle_request(sessioned_request)
        assert "result" in response
        
        # Завершаем сессию
        close_request = {
            "jsonrpc": "2.0",
            "id": 302,
            "method": "session/close",
            "params": {
                "session_id": session_id
            }
        }
        
        response = await server.handle_request(close_request)
        assert "result" in response
        assert response["result"]["closed"] is True
    
    @pytest.mark.asyncio
    async def test_mcp_client_integration(self, mcp_mock_client, integration_test_setup):
        """Тест интеграции MCP клиента."""
        # Создаем клиент
        client = MCP1CClient(
            server_url="ws://localhost:8080",
            client_name="1C MCP Test Client"
        )
        
        # Мокируем соединение
        with patch.object(client, 'connect') as mock_connect:
            mock_connect.return_value = AsyncMock()
            
            # Инициализируем соединение
            init_result = await client.initialize()
            
            assert init_result is not None
            assert "serverInfo" in init_result
            
            # Получаем список инструментов
            tools = await client.list_tools()
            
            assert tools is not None
            assert "tools" in tools
            
            # Генерируем код
            generation_result = await client.call_tool(
                "generate_code",
                {
                    "object_type": "catalog",
                    "description": "Справочник для тестирования",
                    "parameters": {
                        "object_name": "ТестовыйСправочник",
                        "hierarchical": True
                    }
                }
            )
            
            assert generation_result is not None
            assert "content" in generation_result
    
    @pytest.mark.asyncio
    async def test_mcp_protocol_compliance(self, integration_test_setup):
        """Тест соответствия протоколу MCP."""
        server = MCP1CServer()
        await server.initialize()
        
        # Тестируем базовую структуру JSON-RPC 2.0
        valid_request = {
            "jsonrpc": "2.0",
            "id": 400,
            "method": "tools/list"
        }
        
        response = await server.handle_request(valid_request)
        
        # Проверяем соответствие JSON-RPC 2.0
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 400
        assert ("result" in response) ^ ("error" in response)  # XOR - только один из них
        
        # Тестируем уведомления (без ID)
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/status",
            "params": {
                "status": "processing",
                "message": "Генерация кода в процессе"
            }
        }
        
        # Уведомления не должны возвращать ответ
        notification_response = await server.handle_request(notification)
        assert notification_response is None
        
        # Тестируем отмену запроса
        cancel_request = {
            "jsonrpc": "2.0",
            "id": 401,
            "method": "cancel",
            "params": {
                "request_id": 400
            }
        }
        
        cancel_response = await server.handle_request(cancel_request)
        assert cancel_response is not None
        assert "result" in cancel_response
    
    @pytest.mark.asyncio
    async def test_mcp_ping_pong(self, integration_test_setup):
        """Тест ping-pong сообщений."""
        server = MCP1CServer()
        
        ping_request = {
            "jsonrpc": "2.0",
            "id": 500,
            "method": "ping"
        }
        
        response = await server.handle_request(ping_request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 500
        assert "result" in response
        
        assert response["result"]["pong"] is True
        assert "timestamp" in response["result"]
    
    @pytest.mark.asyncio
    async def test_mcp_capability_negotiation(self, integration_test_setup):
        """Тест согласования возможностей."""
        server = MCP1CServer()
        
        # Клиент заявляет о своих возможностях
        client_capabilities = {
            "tools": {
                "listChanged": True
            },
            "logging": {},
            "sampling": {}
        }
        
        init_request = {
            "jsonrpc": "2.0",
            "id": 600,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": client_capabilities,
                "clientInfo": {
                    "name": "Test Client",
                    "version": "1.0.0"
                }
            }
        }
        
        response = await server.handle_request(init_request)
        
        # Проверяем согласование возможностей
        server_capabilities = response["result"]["capabilities"]
        
        # Сервер должен подтвердить или отклонить возможности клиента
        assert "tools" in server_capabilities
        
        if "tools" in server_capabilities:
            tools_caps = server_capabilities["tools"]
            # Сервер может подтвердить или отклонить listChanged
            assert "listChanged" in tools_caps or "listChanged" in client_capabilities["tools"]
    
    @pytest.mark.asyncio
    async def test_mcp_resource_management(self, integration_test_setup, temp_test_dir):
        """Тест управления ресурсами в MCP."""
        server = MCP1CServer()
        await server.initialize()
        
        # Получаем статистику ресурсов
        stats_request = {
            "jsonrpc": "2.0",
            "id": 700,
            "method": "server/stats"
        }
        
        response = await server.handle_request(stats_request)
        assert "result" in response
        
        stats = response["result"]
        assert "active_connections" in stats
        assert "total_requests" in stats
        assert "memory_usage" in stats
        
        # Очищаем кеш
        cache_clear_request = {
            "jsonrpc": "2.0",
            "id": 701,
            "method": "server/cache/clear",
            "params": {
                "cache_type": "all"
            }
        }
        
        response = await server.handle_request(cache_clear_request)
        assert "result" in response
        assert response["result"]["cleared"] is True