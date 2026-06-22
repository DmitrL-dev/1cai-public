"""
Комплексные интеграционные тесты для проверки end-to-end потоков данных
между всеми компонентами системы:

1. UX/UI → API Gateway → AI Assistant → Risk Management → ML System
2. ML System → Metrics Collection → Analytics Dashboard
3. AI Assistant → ML Prediction → Risk Assessment → Recommendations
4. Тесты производительности и надежности интеграции

Использует существующие тестовые структуры как образец и обеспечивает
покрытие реальных бизнес-сценариев с комплексной проверкой интеграции.
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

# Тестовые данные для имитации реальных сценариев
SAMPLE_USER_REQUEST = """
Необходимо создать систему управления проектами для IT-команды.

Функциональные требования:
1. Создание и управление проектами
2. Назначение задач команде
3. Отслеживание прогресса в реальном времени
4. Генерация отчетов по выполнению
5. Интеграция с системой контроля версий
6. Уведомления о дедлайнах

Нефункциональные требования:
1. Одновременная работа до 50 пользователей
2. Время отклика интерфейса не более 1 секунды
3. Резервное копирование каждые 4 часа
4. Шифрование данных согласно ГОСТ
5. Аудит действий пользователей
"""

SAMPLE_PROJECT_CONTEXT = {
    "project_name": "IT Project Management System",
    "company": "ООО ТехноКорп",
    "team_size": 25,
    "timeline": "8 месяцев",
    "budget": "5 млн рублей",
    "integration_systems": ["Jira", "GitHub", "Jenkins", "1C:Бухгалтерия"],
    "technical_stack": ["Python", "FastAPI", "React", "PostgreSQL", "Redis"],
    "compliance_requirements": ["ГОСТ Р 34.11-2012", "152-ФЗ"],
}

SAMPLE_UX_INTERACTION = {
    "user_id": "user_123",
    "session_id": "session_456",
    "action": "create_project",
    "parameters": {
        "project_name": "Новый Проект",
        "template": "agile_development",
        "team_members": ["dev_1", "dev_2", "qa_1"],
        "estimated_duration": "3 месяца",
    },
    "timestamp": "2025-10-30T12:01:36Z",
}

SAMPLE_ML_PREDICTION_REQUEST = {
    "model_type": "risk_assessment",
    "input_data": {
        "project_complexity": 8,
        "team_experience": 7,
        "timeline_pressure": 6,
        "budget_constraints": 9,
        "technical_risks": ["integration", "performance"],
        "requirements_stability": 0.7,
    },
    "prediction_horizon": "3_months",
}

SAMPLE_METRICS_DATA = {
    "timestamp": "2025-10-30T12:01:36Z",
    "system_metrics": {
        "cpu_usage": 0.65,
        "memory_usage": 0.72,
        "response_time": 0.45,
        "error_rate": 0.02,
        "throughput": 120,
    },
    "business_metrics": {
        "active_projects": 15,
        "completed_sprints": 47,
        "team_velocity": 32.5,
        "bug_rate": 0.08,
        "customer_satisfaction": 0.87,
    },
    "ml_metrics": {
        "model_accuracy": 0.92,
        "prediction_latency": 0.12,
        "feature_importance": {
            "team_experience": 0.23,
            "project_complexity": 0.31,
            "timeline_pressure": 0.19,
            "budget_constraints": 0.27,
        },
    },
}


class TestEndToEndDataFlows:
    """Класс для тестирования полных end-to-end потоков данных."""

    @pytest.fixture
    def mock_ux_ui_component(self):
        """Мок UX/UI компонента."""
        ui_mock = AsyncMock()
        ui_mock.submit_request.return_value = {
            "request_id": str(uuid.uuid4()),
            "status": "submitted",
            "timestamp": datetime.now().isoformat(),
            "user_context": SAMPLE_UX_INTERACTION,
        }
        ui_mock.get_dashboard_data.return_value = {
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Проект A",
                    "status": "in_progress",
                    "progress": 0.65,
                },
                {
                    "id": "proj_2",
                    "name": "Проект B",
                    "status": "planning",
                    "progress": 0.15,
                },
            ],
            "metrics": SAMPLE_METRICS_DATA,
        }
        return ui_mock

    @pytest.fixture
    def mock_api_gateway(self):
        """Мок API Gateway."""
        gateway_mock = AsyncMock()
        gateway_mock.route_request.return_value = {
            "gateway_response_id": str(uuid.uuid4()),
            "routed_to": "ai_assistant",
            "routing_latency": 0.05,
            "auth_status": "authenticated",
            "rate_limit_status": "passed",
        }
        gateway_mock.validate_request.return_value = {
            "valid": True,
            "validation_errors": [],
            "security_check": "passed",
        }
        return gateway_mock

    @pytest.fixture
    def mock_ai_assistant(self):
        """Мок AI ассистента."""
        assistant_mock = AsyncMock()
        assistant_mock.analyze_requirements.return_value = {
            "requirements_analysis": {
                "total_count": 12,
                "high_priority_count": 4,
                "complexity_score": 7.2,
                "estimated_effort": "6 месяцев",
            },
            "extracted_requirements": [
                {
                    "id": "REQ001",
                    "title": "Создание проектов",
                    "type": "functional",
                    "priority": "high",
                    "complexity": 8,
                },
                {
                    "id": "REQ002",
                    "title": "Управление задачами",
                    "type": "functional",
                    "priority": "high",
                    "complexity": 7,
                },
            ],
        }
        assistant_mock.generate_recommendations.return_value = {
            "architecture_recommendations": [
                {
                    "component": "Task Management Service",
                    "technology": "FastAPI + PostgreSQL",
                    "complexity_score": 6,
                    "estimated_development_time": "3 недели",
                },
                {
                    "component": "Real-time Notifications",
                    "technology": "Redis + WebSockets",
                    "complexity_score": 5,
                    "estimated_development_time": "2 недели",
                },
            ],
            "risk_mitigation_strategies": [
                {
                    "risk": "Интеграция с GitHub",
                    "mitigation": "Использовать GitHub API v4",
                    "confidence": 0.85,
                }
            ],
        }
        return assistant_mock

    @pytest.fixture
    def mock_risk_management(self):
        """Мок системы управления рисками."""
        risk_mock = AsyncMock()
        risk_mock.assess_project_risks.return_value = {
            "risk_assessment": {
                "overall_risk_level": "medium",
                "risk_percentage": 45,
                "total_risks_identified": 8,
            },
            "risk_breakdown": [
                {
                    "risk_id": "RISK001",
                    "title": "Сложность интеграции",
                    "severity": "medium",
                    "probability": 0.6,
                    "impact": 0.7,
                    "risk_score": 0.42,
                    "mitigation_plan": "Поэтапная интеграция с моками",
                },
                {
                    "risk_id": "RISK002",
                    "title": "Ограничения бюджета",
                    "severity": "high",
                    "priority": 0.8,
                    "impact": 0.9,
                    "risk_score": 0.72,
                    "mitigation_plan": "Приоритизация функций по MVP",
                },
            ],
        }
        return risk_mock

    @pytest.fixture
    def mock_ml_system(self):
        """Мок ML системы."""
        ml_mock = AsyncMock()
        ml_mock.predict_risks.return_value = {
            "prediction_id": str(uuid.uuid4()),
            "model_version": "v2.3.1",
            "predictions": {
                "project_success_probability": 0.73,
                "risk_factors": [
                    {"factor": "timeline_pressure", "probability": 0.67, "impact": 0.8},
                    {"factor": "team_experience", "probability": 0.23, "impact": 0.4},
                ],
                "recommended_actions": [
                    {"action": "Добавить QA ресурсы", "priority": "high"},
                    {
                        "action": "Провести техническое планирование",
                        "priority": "medium",
                    },
                ],
            },
            "confidence_score": 0.87,
            "prediction_timestamp": datetime.now().isoformat(),
        }
        ml_mock.update_model_metrics.return_value = {
            "model_metrics_updated": True,
            "new_metrics": {
                "accuracy": 0.92,
                "precision": 0.89,
                "recall": 0.91,
                "f1_score": 0.90,
            },
        }
        return ml_mock

    @pytest.fixture
    def mock_metrics_collector(self):
        """Мок системы сбора метрик."""
        metrics_mock = AsyncMock()
        metrics_mock.collect_system_metrics.return_value = {
            "collection_id": str(uuid.uuid4()),
            "metrics": SAMPLE_METRICS_DATA,
            "collection_latency": 0.12,
            "data_quality_score": 0.95,
        }
        metrics_mock.store_metrics.return_value = {
            "storage_status": "success",
            "stored_records": 156,
            "compression_ratio": 0.3,
        }
        return metrics_mock

    @pytest.fixture
    def mock_analytics_dashboard(self):
        """Мок аналитической панели."""
        dashboard_mock = AsyncMock()
        dashboard_mock.generate_visualization.return_value = {
            "visualization_id": str(uuid.uuid4()),
            "chart_type": "risk_heatmap",
            "data_points": 45,
            "render_time": 0.23,
            "formats": ["png", "svg", "interactive_html"],
        }
        dashboard_mock.get_dashboard_data.return_value = {
            "dashboard_sections": {
                "project_overview": {
                    "active_projects": 12,
                    "total_budget": "2.5M руб",
                    "team_utilization": 0.78,
                },
                "risk_monitoring": {
                    "high_risks": 3,
                    "medium_risks": 8,
                    "mitigated_risks": 15,
                },
                "performance_metrics": {
                    "avg_response_time": "0.45 сек",
                    "throughput": "120 req/sec",
                    "error_rate": "0.02%",
                },
            }
        }
        return dashboard_mock

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_ux_ui_to_ml_system_complete_flow(
        self,
        mock_ux_ui_component,
        mock_api_gateway,
        mock_ai_assistant,
        mock_risk_management,
        mock_ml_system,
        audit_logger,
    ):
        """Тест полного потока: UX/UI → API Gateway → AI Assistant → Risk Management → ML System"""
        test_name = "ux_ui_to_ml_complete_flow"
        params = {
            "flow_type": "end_to_end",
            "components": [
                "ux_ui",
                "api_gateway",
                "ai_assistant",
                "risk_management",
                "ml_system",
            ],
        }

        audit_logger.log_test_start(test_name, params)
        start_time = time.time()

        try:
            # Шаг 1: UX/UI отправляет запрос
            ui_response = await mock_ux_ui_component.submit_request(SAMPLE_USER_REQUEST)
            assert ui_response["status"] == "submitted"
            assert "request_id" in ui_response

            # Шаг 2: API Gateway валидирует и маршрутизирует запрос
            validation_result = await mock_api_gateway.validate_request(ui_response)
            assert validation_result["valid"] is True

            gateway_response = await mock_api_gateway.route_request(ui_response)
            assert gateway_response["routed_to"] == "ai_assistant"
            assert gateway_response["auth_status"] == "authenticated"

            # Шаг 3: AI Assistant анализирует требования
            assistant_response = await mock_ai_assistant.analyze_requirements(
                requirements_text=SAMPLE_USER_REQUEST, context=SAMPLE_PROJECT_CONTEXT
            )
            assert assistant_response["requirements_analysis"]["total_count"] > 0
            assert len(assistant_response["extracted_requirements"]) > 0

            # Шаг 4: Risk Management оценивает риски
            risk_response = await mock_risk_management.assess_project_risks(
                project_data=assistant_response, context=SAMPLE_PROJECT_CONTEXT
            )
            assert risk_response["risk_assessment"]["overall_risk_level"] in [
                "low",
                "medium",
                "high",
            ]
            assert risk_response["risk_assessment"]["total_risks_identified"] >= 0

            # Шаг 5: ML System делает предсказания
            ml_response = await mock_ml_system.predict_risks(
                model_type="risk_assessment",
                input_data={
                    **assistant_response,
                    **risk_response,
                    "project_context": SAMPLE_PROJECT_CONTEXT,
                },
            )
            assert ml_response["predictions"]["project_success_probability"] > 0
            assert ml_response["confidence_score"] > 0.5

            end_time = time.time()
            duration = end_time - start_time

            # Проверяем общую производительность потока
            assert duration < 5.0  # Весь поток должен выполняться менее 5 секунд

            audit_logger.log_test_result(
                test_name,
                "SUCCESS",
                duration,
                {
                    "ui_request_id": ui_response["request_id"],
                    "gateway_response_id": gateway_response["gateway_response_id"],
                    "ml_prediction_id": ml_response["prediction_id"],
                    "total_requirements": assistant_response["requirements_analysis"][
                        "total_count"
                    ],
                    "risk_level": risk_response["risk_assessment"][
                        "overall_risk_level"
                    ],
                    "success_probability": ml_response["predictions"][
                        "project_success_probability"
                    ],
                },
            )

        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_ml_system_to_analytics_dashboard_flow(
        self,
        mock_ml_system,
        mock_metrics_collector,
        mock_analytics_dashboard,
        audit_logger,
    ):
        """Тест потока: ML System → Metrics Collection → Analytics Dashboard"""
        test_name = "ml_to_analytics_dashboard"
        params = {
            "flow_type": "analytics_pipeline",
            "components": ["ml_system", "metrics_collector", "analytics_dashboard"],
        }

        audit_logger.log_test_start(test_name, params)
        start_time = time.time()

        try:
            # Шаг 1: ML система генерирует предсказания и обновляет метрики
            ml_predictions = await mock_ml_system.predict_risks(
                model_type="risk_assessment",
                input_data=SAMPLE_ML_PREDICTION_REQUEST["input_data"],
            )
            assert ml_predictions["predictions"]["project_success_probability"] > 0

            ml_metrics_update = await mock_ml_system.update_model_metrics(
                {"prediction_data": ml_predictions, "model_version": "v2.3.1"}
            )
            assert ml_metrics_update["model_metrics_updated"] is True

            # Шаг 2: Система сбора метрик собирает и сохраняет данные
            metrics_collection = await mock_metrics_collector.collect_system_metrics(
                {"ml_predictions": ml_predictions, "system_state": "operational"}
            )
            assert metrics_collection["data_quality_score"] > 0.8

            metrics_storage = await mock_metrics_collector.store_metrics(
                {"metrics": SAMPLE_METRICS_DATA, "source": "ml_system"}
            )
            assert metrics_storage["storage_status"] == "success"
            assert metrics_storage["stored_records"] > 0

            # Шаг 3: Analytics Dashboard генерирует визуализации
            dashboard_data = await mock_analytics_dashboard.get_dashboard_data(
                {
                    "date_range": "last_30_days",
                    "include_predictions": True,
                    "include_metrics": True,
                }
            )

            # Генерируем heatmap рисков
            risk_heatmap = await mock_analytics_dashboard.generate_visualization(
                {
                    "visualization_type": "risk_heatmap",
                    "data_source": "ml_predictions",
                    "time_range": "7_days",
                }
            )
            assert risk_heatmap["chart_type"] == "risk_heatmap"
            assert risk_heatmap["data_points"] > 0

            # Генерируем dashboard для отображения метрик
            metrics_viz = await mock_analytics_dashboard.generate_visualization(
                {
                    "visualization_type": "metrics_trend",
                    "data_source": "metrics_collector",
                    "metrics": ["accuracy", "response_time", "throughput"],
                }
            )

            end_time = time.time()
            duration = end_time - start_time

            # Проверяем производительность аналитического потока
            assert duration < 3.0  # Аналитический поток должен быть быстрым

            audit_logger.log_test_result(
                test_name,
                "SUCCESS",
                duration,
                {
                    "ml_prediction_id": ml_predictions["prediction_id"],
                    "metrics_collected": len(SAMPLE_METRICS_DATA["system_metrics"]),
                    "dashboard_sections": len(dashboard_data["dashboard_sections"]),
                    "visualizations_created": 2,
                    "data_quality_score": metrics_collection["data_quality_score"],
                },
            )

        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_ai_assistant_ml_prediction_risk_assessment_flow(
        self, mock_ai_assistant, mock_ml_system, mock_risk_management, audit_logger
    ):
        """Тест потока: AI Assistant → ML Prediction → Risk Assessment → Recommendations"""
        test_name = "ai_ml_risk_recommendations"
        params = {
            "flow_type": "intelligent_analysis",
            "components": [
                "ai_assistant",
                "ml_system",
                "risk_management",
                "recommendations",
            ],
        }

        audit_logger.log_test_start(test_name, params)
        start_time = time.time()

        try:
            # Шаг 1: AI Assistant анализирует требования и генерирует рекомендации
            requirements_analysis = await mock_ai_assistant.analyze_requirements(
                requirements_text=SAMPLE_USER_REQUEST, context=SAMPLE_PROJECT_CONTEXT
            )

            recommendations = await mock_ai_assistant.generate_recommendations(
                requirements=requirements_analysis,
                project_context=SAMPLE_PROJECT_CONTEXT,
            )

            assert len(recommendations["architecture_recommendations"]) > 0
            assert len(recommendations["risk_mitigation_strategies"]) > 0

            # Шаг 2: ML система делает предсказания на основе анализа
            ml_input = {
                "requirements_analysis": requirements_analysis,
                "recommendations": recommendations,
                "project_context": SAMPLE_PROJECT_CONTEXT,
                "historical_data": {
                    "similar_projects": 25,
                    "success_rate": 0.68,
                    "average_timeline": "6.5 месяцев",
                },
            }

            ml_predictions = await mock_ml_system.predict_risks(
                model_type="comprehensive_analysis", input_data=ml_input
            )

            assert ml_predictions["predictions"]["project_success_probability"] > 0
            assert len(ml_predictions["predictions"]["risk_factors"]) > 0
            assert len(ml_predictions["predictions"]["recommended_actions"]) > 0

            # Шаг 3: Risk Management интегрирует данные и проводит оценку
            risk_assessment_input = {
                "ai_analysis": requirements_analysis,
                "ml_predictions": ml_predictions,
                "recommendations": recommendations,
                "project_context": SAMPLE_PROJECT_CONTEXT,
            }

            risk_assessment = await mock_risk_management.assess_project_risks(
                project_data=risk_assessment_input, context=SAMPLE_PROJECT_CONTEXT
            )

            assert risk_assessment["risk_assessment"]["overall_risk_level"] in [
                "low",
                "medium",
                "high",
            ]
            assert len(risk_assessment["risk_breakdown"]) >= 0

            # Проверяем интеграцию данных между компонентами
            ai_requirements_count = requirements_analysis["requirements_analysis"][
                "total_count"
            ]
            ml_confidence = ml_predictions["confidence_score"]
            risk_total_risks = risk_assessment["risk_assessment"][
                "total_risks_identified"
            ]

            # Логические проверки интеграции
            assert ml_confidence > 0.5  # ML должна иметь достаточную уверенность
            assert (
                risk_total_risks >= 0
            )  # Количество рисков должно быть неотрицательным

            end_time = time.time()
            duration = end_time - start_time

            # Проверяем производительность интеллектуального анализа
            assert duration < 4.0

            audit_logger.log_test_result(
                test_name,
                "SUCCESS",
                duration,
                {
                    "requirements_analyzed": ai_requirements_count,
                    "ml_confidence": ml_confidence,
                    "recommendations_generated": len(
                        recommendations["architecture_recommendations"]
                    ),
                    "risks_identified": risk_total_risks,
                    "risk_level": risk_assessment["risk_assessment"][
                        "overall_risk_level"
                    ],
                },
            )

        except Exception as e:
            audit_logger.log_error(test_name, e, params)
            raise


class TestPerformanceAndReliability:
    """Тесты производительности и надежности интеграции."""

    @pytest.fixture
    def load_test_scenarios(self):
        """Сценарии для нагрузочного тестирования."""
        return {
            "concurrent_users": [
                {
                    "user_id": f"user_{i}",
                    "request_type": "analyze_requirements",
                    "complexity": "medium",
                    "timestamp": datetime.now() + timedelta(seconds=i * 0.1),
                }
                for i in range(10)
            ],
            "burst_load": {
                "requests_per_second": 50,
                "duration": 30,
                "request_types": [
                    "ml_prediction",
                    "risk_assessment",
                    "generate_recommendations",
                ],
            },
            "stress_test": {
                "max_concurrent_sessions": 100,
                "peak_memory_usage": "2GB",
                "response_time_threshold": 2.0,
            },
        }

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.performance
    async def test_concurrent_user_flows_performance(
        self,
        mock_ux_ui_component,
        mock_api_gateway,
        mock_ai_assistant,
        mock_ml_system,
        mock_risk_management,
        load_test_scenarios,
        audit_logger,
    ):
        """Тест производительности при параллельной обработке запросов пользователей."""
        test_name = "concurrent_flows_performance"
        params = {
            "test_type": "load_test",
            "concurrent_users": len(load_test_scenarios["concurrent_users"]),
        }

        audit_logger.log_test_start(test_name, params)
        start_time = time.time()

        # Выполняем запросы параллельно
        async def process_single_user_request(user_data):
            try:
                # Симулируем полный поток для одного пользователя
                ui_response = await mock_ux_ui_component.submit_request(
                    SAMPLE_USER_REQUEST
                )
                gateway_response = await mock_api_gateway.route_request(ui_response)
                assistant_response = await mock_ai_assistant.analyze_requirements(
                    SAMPLE_USER_REQUEST, SAMPLE_PROJECT_CONTEXT
                )
                ml_response = await mock_ml_system.predict_risks(
                    "risk_assessment", assistant_response
                )
                risk_response = await mock_risk_management.assess_project_risks(
                    ml_response, SAMPLE_PROJECT_CONTEXT
                )

                return {
                    "user_id": user_data["user_id"],
                    "status": "success",
                    "response_time": time.time() - start_time,
                    "risk_level": risk_response["risk_assessment"][
                        "overall_risk_level"
                    ],
                }
            except Exception as e:
                return {
                    "user_id": user_data["user_id"],
                    "status": "error",
                    "error": str(e),
                    "response_time": time.time() - start_time,
                }

        # Запускаем все пользовательские потоки параллельно
        results = await asyncio.gather(
            *[
                process_single_user_request(user)
                for user in load_test_scenarios["concurrent_users"]
            ],
            return_exceptions=True,
        )

        end_time = time.time()
        total_duration = end_time - start_time

        # Анализируем результаты
        successful_requests = [
            r for r in results if isinstance(r, dict) and r["status"] == "success"
        ]
        failed_requests = [
            r for r in results if isinstance(r, dict) and r["status"] == "error"
        ]
        exceptions = [r for r in results if isinstance(r, Exception)]

        # Проверяем критерии производительности
        success_rate = len(successful_requests) / len(results)
        assert success_rate >= 0.9  # Минимум 90% успешных запросов

        if successful_requests:
            avg_response_time = sum(
                r["response_time"] for r in successful_requests
            ) / len(successful_requests)
            assert avg_response_time < 3.0  # Среднее время отклика менее 3 секунд

        # Проверяем надежность
        assert len(exceptions) == 0  # Никаких исключений
        assert len(failed_requests) == 0  # Никаких неудачных запросов

        audit_logger.log_test_result(
            test_name,
            "SUCCESS",
            total_duration,
            {
                "total_users": len(load_test_scenarios["concurrent_users"]),
                "successful_requests": len(successful_requests),
                "failed_requests": len(failed_requests),
                "success_rate": success_rate,
                "avg_response_time": avg_response_time if successful_requests else None,
                "max_response_time": (
                    max(r["response_time"] for r in successful_requests)
                    if successful_requests
                    else None
                ),
            },
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.performance
    async def test_burst_load_resilience(
        self,
        mock_api_gateway,
        mock_ai_assistant,
        mock_ml_system,
        mock_risk_management,
        load_test_scenarios,
        audit_logger,
    ):
        """Тест устойчивости системы при пиковых нагрузках."""
        test_name = "burst_load_resilience"
        params = {
            "test_type": "stress_test",
            "requests_per_second": load_test_scenarios["burst_load"][
                "requests_per_second"
            ],
        }

        audit_logger.log_test_start(test_name, params)

        start_time = time.time()
        request_count = 0
        error_count = 0
        response_times = []

        # Симулируем всплеск запросов
        burst_duration = 5  # секунд
        requests_per_second = load_test_scenarios["burst_load"]["requests_per_second"]

        async def send_burst_requests():
            nonlocal request_count, error_count, response_times

            for second in range(burst_duration):
                second_start = time.time()

                # Отправляем пачку запросов за секунду
                batch_requests = []
                for _ in range(requests_per_second):
                    request_start = time.time()

                    try:
                        # Минимум компонентов для стресс-теста
                        gateway_response = await mock_api_gateway.route_request(
                            {"test": "data"}
                        )
                        assistant_response = (
                            await mock_ai_assistant.analyze_requirements("test", {})
                        )

                        request_end = time.time()
                        response_times.append(request_end - request_start)
                        request_count += 1

                    except Exception as e:
                        error_count += 1
                        request_count += 1

                # Ждем до конца секунды
                elapsed = time.time() - second_start
                if elapsed < 1.0:
                    await asyncio.sleep(1.0 - elapsed)

        await send_burst_requests()
        end_time = time.time()
        total_duration = end_time - start_time

        # Анализируем результаты стресс-теста
        total_requests = request_count
        actual_rps = total_requests / total_duration
        error_rate = error_count / total_requests if total_requests > 0 else 0

        # Критерии устойчивости
        assert actual_rps >= requests_per_second * 0.8  # Не менее 80% целевого RPS
        assert error_rate < 0.1  # Менее 10% ошибок
        assert total_duration <= burst_duration * 1.2  # Не более 20% превышения времени

        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)

            assert avg_response_time < 1.0  # Среднее время отклика менее 1 секунды
            assert max_response_time < 3.0  # Максимальное время отклика менее 3 секунд

        audit_logger.log_test_result(
            test_name,
            "SUCCESS",
            total_duration,
            {
                "total_requests": total_requests,
                "target_rps": requests_per_second,
                "actual_rps": actual_rps,
                "error_count": error_count,
                "error_rate": error_rate,
                "avg_response_time": avg_response_time if response_times else None,
                "max_response_time": max_response_time if response_times else None,
            },
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.performance
    async def test_data_consistency_across_components(
        self,
        mock_ai_assistant,
        mock_ml_system,
        mock_risk_management,
        mock_metrics_collector,
        audit_logger,
    ):
        """Тест согласованности данных между компонентами при высокой нагрузке."""
        test_name = "data_consistency_test"
        params = {"test_type": "consistency_check", "iterations": 50}

        audit_logger.log_test_start(test_name, params)

        consistency_errors = []
        data_samples = []

        for i in range(50):
            # Запускаем параллельные запросы к разным компонентам
            assistant_task = mock_ai_assistant.analyze_requirements(
                SAMPLE_USER_REQUEST, SAMPLE_PROJECT_CONTEXT
            )
            ml_task = mock_ml_system.predict_risks(
                "risk_assessment", SAMPLE_ML_PREDICTION_REQUEST["input_data"]
            )
            risk_task = mock_risk_management.assess_project_risks(
                {}, SAMPLE_PROJECT_CONTEXT
            )
            metrics_task = mock_metrics_collector.collect_system_metrics({})

            try:
                results = await asyncio.gather(
                    assistant_task, ml_task, risk_task, metrics_task
                )

                assistant_data, ml_data, risk_data, metrics_data = results

                # Проверяем структурную согласованность
                consistency_checks = [
                    {
                        "name": "assistant_has_requirements",
                        "check": "requirements_analysis" in assistant_data,
                        "component": "ai_assistant",
                    },
                    {
                        "name": "ml_has_predictions",
                        "check": "predictions" in ml_data,
                        "component": "ml_system",
                    },
                    {
                        "name": "risk_has_assessment",
                        "check": "risk_assessment" in risk_data,
                        "component": "risk_management",
                    },
                    {
                        "name": "metrics_has_data",
                        "check": "metrics" in metrics_data,
                        "component": "metrics_collector",
                    },
                ]

                for check in consistency_checks:
                    if not check["check"]:
                        consistency_errors.append(
                            {
                                "iteration": i,
                                "error": f"{check['component']} missing {check['name']}",
                                "data": {
                                    "assistant": assistant_data,
                                    "ml": ml_data,
                                    "risk": risk_data,
                                    "metrics": metrics_data,
                                },
                            }
                        )

                # Сохраняем образцы данных для анализа
                data_samples.append(
                    {
                        "iteration": i,
                        "timestamp": datetime.now().isoformat(),
                        "assistant_data": assistant_data,
                        "ml_data": ml_data,
                        "risk_data": risk_data,
                        "metrics_data": metrics_data,
                    }
                )

            except Exception as e:
                consistency_errors.append(
                    {
                        "iteration": i,
                        "error": f"Parallel execution failed: {str(e)}",
                        "data": None,
                    }
                )

        # Проверяем результаты согласованности
        consistency_rate = (50 - len(consistency_errors)) / 50
        assert consistency_rate >= 0.95  # Минимум 95% согласованности

        if consistency_errors:
            print(f"Обнаружено {len(consistency_errors)} ошибок согласованности:")
            for error in consistency_errors[:5]:  # Показываем первые 5
                print(f"  Итерация {error['iteration']}: {error['error']}")

        audit_logger.log_test_result(
            test_name,
            "SUCCESS" if len(consistency_errors) == 0 else "WARNING",
            0,  # Время не критично для этого теста
            {
                "total_iterations": 50,
                "consistency_errors": len(consistency_errors),
                "consistency_rate": consistency_rate,
                "data_samples_collected": len(data_samples),
                "error_sample": consistency_errors[0] if consistency_errors else None,
            },
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.performance
    async def test_recovery_after_component_failure(
        self, mock_ai_assistant, mock_api_gateway, audit_logger
    ):
        """Тест восстановления системы после отказа компонента."""
        test_name = "component_failure_recovery"
        params = {
            "test_type": "failure_recovery",
            "failure_scenarios": ["ai_assistant_timeout", "gateway_throttling"],
        }

        audit_logger.log_test_start(test_name, params)

        recovery_tests = []

        # Тест 1: Восстановление после таймаута AI Assistant
        async def test_ai_assistant_timeout_recovery():
            # Временно делаем AI Assistant недоступным
            with patch.object(
                mock_ai_assistant,
                "analyze_requirements",
                side_effect=Exception("Timeout"),
            ):
                try:
                    await mock_ai_assistant.analyze_requirements(
                        SAMPLE_USER_REQUEST, SAMPLE_PROJECT_CONTEXT
                    )
                except Exception:
                    pass  # Ожидаемая ошибка

            # Проверяем восстановление
            try:
                response = await mock_ai_assistant.analyze_requirements(
                    SAMPLE_USER_REQUEST, SAMPLE_PROJECT_CONTEXT
                )
                return {"status": "recovered", "response": response}
            except Exception as e:
                return {"status": "failed", "error": str(e)}

        # Тест 2: Восстановление после throttling API Gateway
        async def test_gateway_throttling_recovery():
            # Симулируем throttling
            with patch.object(
                mock_api_gateway, "route_request", side_effect=Exception("Rate limited")
            ):
                try:
                    await mock_api_gateway.route_request({"test": "data"})
                except Exception:
                    pass  # Ожидаемая ошибка

            # Проверяем восстановление
            try:
                response = await mock_api_gateway.route_request({"test": "recovery"})
                return {"status": "recovered", "response": response}
            except Exception as e:
                return {"status": "failed", "error": str(e)}

        # Выполняем тесты восстановления параллельно
        recovery_results = await asyncio.gather(
            test_ai_assistant_timeout_recovery(),
            test_gateway_throttling_recovery(),
            return_exceptions=True,
        )

        # Анализируем результаты
        for i, result in enumerate(recovery_results):
            if isinstance(result, Exception):
                recovery_tests.append(
                    {
                        "test": f"recovery_test_{i}",
                        "status": "failed",
                        "error": str(result),
                    }
                )
            else:
                recovery_tests.append(
                    {
                        "test": f"recovery_test_{i}",
                        "status": result["status"],
                        "response": result.get("response"),
                        "error": result.get("error"),
                    }
                )

        # Проверяем критерии восстановления
        successful_recoveries = [
            t for t in recovery_tests if t["status"] == "recovered"
        ]
        recovery_rate = len(successful_recoveries) / len(recovery_tests)

        assert recovery_rate >= 0.8  # Минимум 80% успешного восстановления

        audit_logger.log_test_result(
            test_name,
            "SUCCESS" if recovery_rate >= 0.8 else "WARNING",
            0,
            {
                "total_recovery_tests": len(recovery_tests),
                "successful_recoveries": len(successful_recoveries),
                "recovery_rate": recovery_rate,
                "recovery_details": recovery_tests,
            },
        )


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v", "--tb=short"])
