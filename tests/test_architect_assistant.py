
"""
Тесты для ArchitectAssistant
Проверяют основную функциональность AI-ассистента архитектора
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Тестовые данные
SAMPLE_REQUIREMENTS = """
Необходимо создать систему управления складскими запасами для компании ООО "Тест".

Функциональные требования:
1. Учет поступления товаров на склад
2. Отслеживание остатков в реальном времени
3. Автоматическое уведомление при низких остатках
4. Интеграция с системой бухгалтерского учета
5. Генерация отчетов по движению товаров
6. Управление поставщиками

Нефункциональные требования:
1. Система должна обрабатывать до 1000 операций в день
2. Время отклика не более 2 секунд
3. Резервное копирование каждые 6 часов
4. Доступ только для авторизованных пользователей
5. Соответствие требованиям 152-ФЗ о персональных данных
"""

SAMPLE_CONTEXT = {
    "project_name": "Складская система",
    "company": "ООО Тест",
    "timeline": "6 месяцев",
    "budget": "2 млн рублей",
    "team_size": 5,
    "integration_systems": ["1С:Бухгалтерия", "SAP", "CRM"],
}

SAMPLE_ARCHITECTURE = {
    "title": "Архитектура системы управления складом",
    "description": "Микросервисная архитектура с интеграцией с существующими системами",
    "components": [
        {
            "name": "Inventory Service",
            "type": "microservice",
            "description": "Основной сервис управления складскими запасами",
            "responsibilities": ["Учет остатков", "Уведомления", "Отчеты"],
            "technologies": ["Python", "FastAPI", "PostgreSQL"],
            "complexity_score": 8,
        },
        {
            "name": "Integration Service",
            "type": "integration",
            "description": "Сервис интеграции с внешними системами",
            "responsibilities": ["Интеграция с 1С", "API-шлюзы", "Синхронизация"],
            "technologies": ["Java Spring", "ActiveMQ", "Oracle"],
            "complexity_score": 9,
        },
    ],
    "benefits": [
        "Масштабируемость",
        "Интеграция с существующими системами",
        "Соответствие требованиям безопасности",
    ],
    "trade_offs": ["Сложность интеграции", "Необходимость в DevOps команде"],
}


class TestArchitectAssistant:
    """Класс тестов для ArchitectAssistant"""

    @pytest.fixture
    def mock_openai_client(self):
        """Мок для OpenAI клиента"""
        mock_client = AsyncMock()
        mock_client.ainvoke.return_value = Mock(
            content='{"requirements": [{"id": "REQ001", "title": "Учет товаров", "type": "functional", "priority": "high", "complexity": 7}]}'
        )
        return mock_client

    @pytest.fixture
    def mock_supabase(self):
        """Мок для Supabase клиента"""
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = (
            Mock()
        )
        return mock_client

    @pytest.fixture
    def mock_config(self):
        """Мок для конфигурации"""
        return {
            "role": "architect",
            "name": "Архитектор AI",
            "description": "Тестовый ассистент",
            "temperature": 0.3,
            "max_tokens": 1000,
            "system_prompt": "Ты архитектор систем",
            "vector_store_config": {},
        }

    @pytest.fixture
    def architect_assistant(self, mock_openai_client, mock_supabase, mock_config):
        """Фикстура для создания тестового ассистента"""
        from src.ai_assistants.architect_assistant import ArchitectAssistant

        with patch("src.ai_assistants.architect_assistant.settings") as mock_settings:
            # Настройка моков
            mock_settings.openai_api_key = "test-key"
            mock_settings.supabase_url = "test-url"
            mock_settings.supabase_key = "test-key"
            mock_settings.assistant_configs = {"architect": mock_config}

            # Создание ассистента
            assistant = ArchitectAssistant()
            return assistant

    @pytest.mark.asyncio
    async def test_analyze_requirements_success(self, architect_assistant):
        """Тест успешного анализа требований"""
        # Выполняем анализ
        result = await architect_assistant.analyze_requirements(
            requirements_text=SAMPLE_REQUIREMENTS, context=SAMPLE_CONTEXT
        )

        # Проверяем структуру ответа
        assert "requirements" in result
        assert "analysis_summary" in result
        assert "total_count" in result["analysis_summary"]
        assert "high_priority_count" in result["analysis_summary"]

        # Проверяем, что требования найдены
        assert result["analysis_summary"]["total_count"] > 0
        assert result["analysis_summary"]["high_priority_count"] >= 0

        # Проверяем структуру требований
        if result["requirements"]:
            requirement = result["requirements"][0]
            assert "id" in requirement
            assert "title" in requirement
            assert "type" in requirement
            assert "priority" in requirement

    @pytest.mark.asyncio
    async def test_analyze_requirements_empty_text(self, architect_assistant):
        """Тест анализа пустого текста требований"""
        result = await architect_assistant.analyze_requirements(
            requirements_text="", context={}
        )

        assert "error" in result or result["requirements"] == []
        assert "analysis_summary" in result
        assert result["analysis_summary"]["total_count"] == 0

    @pytest.mark.asyncio
    async def test_generate_diagram_success(self, architect_assistant):
        """Тест успешной генерации диаграммы"""
        # Мокаем LLM для возврата корректного JSON
        with patch.object(architect_assistant.llm, "ainvoke") as mock_invoke:
            mock_invoke.return_value = Mock(
                content=json.dumps(
                    {
                        "architecture": {
                            "title": "Тестовая архитектура",
                            "components": [
                                {
                                    "name": "Test Component",
                                    "type": "service",
                                    "description": "Тестовый компонент",
                                    "complexity_score": 5,
                                }
                            ],
                        },
                        "mermaid_diagram": "graph TD\nA[Start] --> B[Process]",
                    }
                )
            )

            result = await architect_assistant.generate_diagram(
                architecture_proposal=SAMPLE_ARCHITECTURE, diagram_type="flowchart"
            )

            assert "mermaid_code" in result
            assert "architecture" in result
            assert "explanation" in result
            assert "diagram_type" in result

            # Проверяем валидацию Mermaid
            mermaid_code = result["mermaid_code"]
            assert mermaid_code.startswith("flowchart") or "flowchart" in mermaid_code

    @pytest.mark.asyncio
    async def test_generate_diagram_invalid_code(self, architect_assistant):
        """Тест генерации диаграммы с некорректным кодом"""
        with patch.object(architect_assistant.llm, "ainvoke") as mock_invoke:
            mock_invoke.return_value = Mock(content="Некорректный ответ без JSON")

            result = await architect_assistant.generate_diagram(
                architecture_proposal={}, diagram_type="flowchart"
            )

            # Должен быть обработан как ошибка
            assert "error" in result or result["mermaid_code"] == ""

    @pytest.mark.asyncio
    async def test_assess_risks_success(self, architect_assistant):
        """Тест успешной оценки рисков"""
        with patch.object(architect_assistant.llm, "ainvoke") as mock_invoke:
            mock_invoke.return_value = Mock(
                content=json.dumps(
                    {
                        "risks": [
                            {
                                "risk_id": "RISK001",
                                "title": "Интеграция с 1С",
                                "severity": "high",
                                "probability": 0.7,
                                "impact": 0.8,
                                "mitigation_strategy": "Использовать готовые коннекторы",
                            }
                        ],
                        "overall_assessment": "Проект имеет средний уровень риска",
                    }
                )
            )

            result = await architect_assistant.assess_risks(
                architecture=SAMPLE_ARCHITECTURE, project_context=SAMPLE_CONTEXT
            )

            assert "risks" in result
            assert "overall_assessment" in result
            assert len(result["risks"]) > 0

            # Проверяем структуру риска
            risk = result["risks"][0]
            assert "risk_id" in risk
            assert "title" in risk
            assert "severity" in risk
            assert "probability" in risk
            assert "impact" in risk

    @pytest.mark.asyncio
    async def test_assess_risks_calculation(self, architect_assistant):
        """Тест расчета общего уровня риска"""
        with patch.object(architect_assistant.llm, "ainvoke") as mock_invoke:
            mock_invoke.return_value = Mock(
                content=json.dumps(
                    {
                        "risks": [
                            {
                                "risk_id": "RISK001",
                                "title": "Риск 1",
                                "severity": "critical",
                                "probability": 0.9,
                                "impact": 0.9,
                                "mitigation_strategy": "Стратегия 1",
                            }
                        ],
                        "overall_assessment": "Высокий риск",
                    }
                )
            )

            result = await architect_assistant.assess_risks(
                architecture=SAMPLE_ARCHITECTURE, project_context=SAMPLE_CONTEXT
            )

            assessment = result["overall_assessment"]
            assert "risk_level" in assessment
            assert "risk_percentage" in assessment
            assert "total_risks" in assessment

            # Критический риск должен давать высокий процент
            assert assessment["risk_percentage"] >= 70
            assert assessment["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_comprehensive_analysis_success(self, architect_assistant):
        """Тест комплексного анализа"""
        with patch.object(architect_assistant.llm, "ainvoke") as mock_invoke:
            # Мокаем разные ответы для разных методов
            mock_responses = [
                Mock(
                    content=json.dumps({"requirements": [{"id": "1", "title": "Test"}]})
                ),
                Mock(content=json.dumps(SAMPLE_ARCHITECTURE)),
                Mock(
                    content=json.dumps(
                        {
                            "architecture": SAMPLE_ARCHITECTURE,
                            "mermaid_diagram": "graph TD\nA-->B",
                        }
                    )
                ),
                Mock(
                    content=json.dumps(
                        {"risks": [], "overall_assessment": "Низкий риск"}
                    )
                ),
            ]

            mock_invoke.side_effect = mock_responses

            result = await architect_assistant.create_comprehensive_analysis(
                requirements_text=SAMPLE_REQUIREMENTS, context=SAMPLE_CONTEXT
            )

            assert "requirements_analysis" in result
            assert "architecture_proposal" in result
            assert "diagram" in result
            assert "risk_assessment" in result
            assert "summary" in result

            # Проверяем общую структуру
            summary = result["summary"]
            assert "total_requirements" in summary
            assert "architecture_components" in summary
            assert "identified_risks" in summary
            assert "overall_risk_level" in summary
            assert "recommendation" in summary

    @pytest.mark.asyncio
    async def test_comprehensive_analysis_error_handling(self, architect_assistant):
        """Тест обработки ошибок в комплексном анализе"""
        # Мокаем ошибку в одном из вызовов
        with patch.object(architect_assistant, "analyze_requirements") as mock_analyze:
            mock_analyze.return_value = {"error": "Test error"}

            result = await architect_assistant.create_comprehensive_analysis(
                requirements_text=SAMPLE_REQUIREMENTS, context=SAMPLE_CONTEXT
            )

            assert "error" in result

    def test_validate_mermaid_code_flowchart(self, architect_assistant):
        """Тест валидации Mermaid кода для flowchart"""
        # Тест с пустым кодом
        result = architect_assistant._validate_mermaid_code("", "flowchart")
        assert result == ""

        # Тест с корректным кодом
        valid_code = "flowchart TD\nA[Start] --> B[End]"
        result = architect_assistant._validate_mermaid_code(valid_code, "flowchart")
        assert "flowchart" in result

        # Тест с кодом без префикса
        code_without_prefix = "A[Start] --> B[End]"
        result = architect_assistant._validate_mermaid_code(
            code_without_prefix, "flowchart"
        )
        assert result.startswith("flowchart")

    def test_validate_mermaid_code_sequence(self, architect_assistant):
        """Тест валидации Mermaid кода для sequence"""
        code = "User->>Server: Request"
        result = architect_assistant._validate_mermaid_code(code, "sequence")
        assert result.startswith("sequenceDiagram")

    def test_generate_recommendation_logic(self, architect_assistant):
        """Тест логики генерации рекомендаций"""
        # Низкий риск, мало компонентов
        low_risk_data = {
            "requirements": {"total_count": 5},
            "architecture": {"components": [1, 2, 3]},
            "risks": {
                "overall_assessment": {"risk_level": "low", "risk_percentage": 20}
            },
        }

        recommendation = architect_assistant._generate_recommendation(
            low_risk_data["requirements"],
            low_risk_data["architecture"],
            low_risk_data["risks"],
        )

        assert "немедленное начало" in recommendation.lower()

        # Высокий риск
        high_risk_data = {
            "requirements": {"total_count": 20},
            "architecture": {"components": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]},
            "risks": {
                "overall_assessment": {"risk_level": "high", "risk_percentage": 80}
            },
        }

        recommendation = architect_assistant._generate_recommendation(
            high_risk_data["requirements"],
            high_risk_data["architecture"],
            high_risk_data["risks"],
        )

        assert "дополнительный анализ" in recommendation.lower()

    def test_prepare_context(self, architect_assistant):
        """Тест подготовки контекста"""
        context = {"project_id": "test-123", "user_role": "architect"}
        enhanced = architect_assistant._prepare_context(context)

        assert enhanced["project_id"] == "test-123"
        assert enhanced["user_role"] == "architect"
        assert enhanced["role"] == "architect"
        assert enhanced["assistant_name"] == "Архитектор AI"
        assert "conversation_history" in enhanced


class TestAPIIntegration:
    """Тесты интеграции с FastAPI"""

    @pytest.mark.asyncio
    async def test_analyze_requirements_endpoint(self):
        """Тест endpoint анализа требований"""
        from src.api.assistants import AnalyzeRequirementsRequest

        request = AnalyzeRequirementsRequest(
            requirements_text=SAMPLE_REQUIREMENTS, context=SAMPLE_CONTEXT
        )

        # Проверяем валидацию модели
        assert request.requirements_text == SAMPLE_REQUIREMENTS
        assert request.context == SAMPLE_CONTEXT

    def test_chat_request_model(self):
        """Тест модели запроса чата"""
        from src.api.assistants import ChatRequest

        request = ChatRequest(
            query="Тестовый вопрос",
            context={"test": "data"},
            conversation_id="conv-123",
        )

        assert request.query == "Тестовый вопрос"
        assert request.context["test"] == "data"
        assert request.conversation_id == "conv-123"


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v"])
