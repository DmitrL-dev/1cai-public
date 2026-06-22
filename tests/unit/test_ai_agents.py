"""
Unit Tests для AI Agents
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Test Architect Agent
@pytest.mark.asyncio
async def test_architect_agent_analyze_system():
    """Test системного анализа"""
    from src.ai.agents.architect_agent import ArchitectAgent

    agent = ArchitectAgent()

    system_description = """
    Система для управления складом с 1000+ пользователей,
    обработка 10000 документов в день
    """

    result = await agent.analyze_system(system_description)

    assert result is not None
    assert "architecture" in result or "analysis" in result


@pytest.mark.asyncio
async def test_devops_agent_pipeline_optimization():
    """Test оптимизации CI/CD"""
    from src.ai.agents.devops_agent_extended import DevOpsAgentExtended

    agent = DevOpsAgentExtended()

    pipeline_config = {"steps": ["build", "test", "deploy"], "duration_minutes": 45}

    metrics = {"avg_duration": 45, "success_rate": 0.85}

    result = await agent.optimize_pipeline(pipeline_config, metrics)

    assert "recommendations" in result
    assert len(result["recommendations"]) > 0


@pytest.mark.asyncio
async def test_qa_agent_test_generation():
    """Test генерации тестов"""
    from src.ai.agents.qa_engineer_agent_extended import QAEngineerAgentExtended

    agent = QAEngineerAgentExtended()

    function_code = """
Функция РассчитатьСумму(Цена, Количество)
    Возврат Цена * Количество;
КонецФункции
"""

    result = await agent.generate_tests(function_code, "РассчитатьСумму")

    assert "tests" in result
    assert "test_cases" in result


@pytest.mark.asyncio
async def test_ba_agent_requirements_extraction():
    """Test извлечения требований"""
    from src.ai.agents.business_analyst_agent_extended import (
        BusinessAnalystAgentExtended,
    )

    agent = BusinessAnalystAgentExtended()

    document = """
    Система должна:
    1. Регистрировать пользователей
    2. Хранить данные о заказах
    3. Формировать отчеты
    Как менеджер по продажам, я хочу видеть список заказов, чтобы обслуживать клиентов.
    Критерий приемки: отчёт должен генерироваться за 5 секунд.
    """

    result = await agent.extract_requirements(document, "tz")

    assert "functional_requirements" in result
    assert len(result["functional_requirements"]) >= 2
    assert "summary" in result
    assert result["summary"]["total_requirements"] >= 2
    assert "user_stories" in result


@pytest.mark.asyncio
async def test_tw_agent_api_docs_generation():
    """Test генерации API документации"""
    from src.ai.agents.technical_writer_agent_extended import (
        TechnicalWriterAgentExtended,
    )

    agent = TechnicalWriterAgentExtended()

    code = """
Функция ПолучитьДанные(ID) Экспорт
    // Returns user data
    Возврат Данные[ID];
КонецФункции
"""

    result = await agent.generate_api_docs(code, "http_service")

    assert "openapi" in result or "documentation" in result


# Test Code Review Components
@pytest.mark.asyncio
async def test_bsl_parser():
    """Test BSL парсера"""
    from src.ai.agents.code_review.bsl_parser import BSLParser

    parser = BSLParser()

    code = """
Функция Тест()
    Переменная = 123;
    Возврат Переменная;
КонецФункции
"""

    ast = parser.parse(code)

    assert ast is not None
    assert "functions" in ast
    assert len(ast["functions"]) > 0


def test_security_scanner_sql_injection():
    """Test обнаружения SQL injection"""
    from src.ai.agents.code_review.security_scanner import SecurityScanner

    scanner = SecurityScanner()

    vulnerable_code = """
Запрос.Текст = "SELECT * WHERE ID = '" + UserInput + "'";
"""

    issues = scanner.scan_sql_injection(vulnerable_code, {})

    assert len(issues) > 0
    assert issues[0]["severity"] == "CRITICAL"


def test_security_scanner_hardcoded_credentials():
    """Test обнаружения credentials"""
    from src.ai.agents.code_review.security_scanner import SecurityScanner

    scanner = SecurityScanner()

    code_with_creds = """
Password = "admin123";
APIKey = "sk_test_12345";
"""

    issues = scanner.scan_hardcoded_credentials(code_with_creds, {})

    assert len(issues) > 0
    assert issues[0]["type"] == "HARDCODED_CREDENTIALS"


def test_security_scanner_detects_cyrillic_bsl_security_patterns():
    from src.ai.agents.code_review.security_scanner import SecurityScanner

    scanner = SecurityScanner()
    code = (
        "\u0417\u0430\u043f\u0440\u043e\u0441.\u0422\u0435\u043a\u0441\u0442 = "
        '"\u0412\u042b\u0411\u0420\u0410\u0422\u042c * \u0413\u0414\u0415 ID = " + '
        "\u041a\u043e\u0434;\n"
        '\u041f\u0430\u0440\u043e\u043b\u044c = "admin123";\n'
        '\u0412\u044b\u043f\u043e\u043b\u043d\u0438\u0442\u044c("cmd");\n'
        "\u0417\u0430\u043f\u0440\u043e\u0441."
        "\u0412\u044b\u043f\u043e\u043b\u043d\u0438\u0442\u044c();"
    )

    issues = scanner.scan(code, {})

    issue_types = {issue["type"] for issue in issues}
    assert "SQL_INJECTION" in issue_types
    assert "HARDCODED_CREDENTIALS" in issue_types
    assert "DYNAMIC_EXECUTION" in issue_types
    assert [issue["type"] for issue in issues].count("DYNAMIC_EXECUTION") == 1


def test_performance_analyzer_n_plus_one():
    """Test обнаружения N+1"""
    from src.ai.agents.code_review.performance_analyzer import PerformanceAnalyzer

    analyzer = PerformanceAnalyzer()

    code = """
Для Каждого Товар Из Товары Цикл
    Запрос = Новый Запрос;
    Запрос.Выполнить();
КонецЦикла;
"""

    ast = {"functions": [{"name": "Test", "body": code, "start_line": 1}]}

    issues = analyzer.detect_n_plus_one_queries(code, ast)

    assert len(issues) > 0
    assert issues[0]["severity"] == "HIGH"


def test_performance_analyzer_detects_real_cyrillic_bsl_patterns():
    from src.ai.agents.code_review.performance_analyzer import PerformanceAnalyzer

    analyzer = PerformanceAnalyzer()
    code = (
        "\u0414\u043b\u044f \u041a\u0430\u0436\u0434\u043e\u0433\u043e "
        "\u0422\u043e\u0432\u0430\u0440 \u0418\u0437 "
        "\u0422\u043e\u0432\u0430\u0440\u044b \u0426\u0438\u043a\u043b\n"
        "    \u0417\u0430\u043f\u0440\u043e\u0441 = "
        "\u041d\u043e\u0432\u044b\u0439 \u0417\u0430\u043f\u0440\u043e\u0441;\n"
        "    \u0417\u0430\u043f\u0440\u043e\u0441."
        '\u0422\u0435\u043a\u0441\u0442 = "\u0412\u042b\u0411\u0420\u0410\u0422\u042c * '
        '\u0418\u0417 \u0421\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a";\n'
        "    \u0417\u0430\u043f\u0440\u043e\u0441."
        "\u0412\u044b\u043f\u043e\u043b\u043d\u0438\u0442\u044c();\n"
        "\u041a\u043e\u043d\u0435\u0446\u0426\u0438\u043a\u043b\u0430;"
    )

    issues = analyzer.analyze(code, {})

    issue_types = {issue["type"] for issue in issues}
    assert "N_PLUS_ONE_QUERY" in issue_types
    assert "SELECT_STAR_QUERY" in issue_types


def test_auto_fixer_sql_injection():
    """Test автоисправления SQL injection"""
    from src.ai.agents.code_review.auto_fixer import AutoFixer

    fixer = AutoFixer()

    vulnerable = 'Запрос.Текст = "SELECT * WHERE ID = " + UserID'

    fixed = fixer.fix_sql_injection(vulnerable, {})

    assert "УстановитьПараметр" in fixed
    assert fixed != vulnerable


# Test SaaS Components
@pytest.mark.asyncio
async def test_tenant_context_extraction():
    """Test извлечения tenant context"""
    from fastapi import Request

    from src.api.middleware.tenant_context import extract_tenant_id

    # Mock request with tenant header
    request = Mock(spec=Request)
    request.headers = {"X-Tenant-ID": "tenant-123"}

    tenant_id = extract_tenant_id(request)

    assert tenant_id == "tenant-123"


def test_cache_key_generation():
    """Test генерации cache keys"""
    from src.cache.multi_layer_cache import generate_cache_key

    key = generate_cache_key("products", tenant_id=123, category="dairy")

    assert "products" in key
    assert "tenant" in key or "123" in key


@pytest.mark.asyncio
async def test_multi_layer_cache():
    """Test multi-layer кеша"""
    from src.cache.multi_layer_cache import MultiLayerCache

    cache = MultiLayerCache()

    # Set value
    await cache.set("test_key", {"data": "value"}, ttl_seconds=60)

    # Get value (should hit L1)
    value = await cache.get("test_key")

    assert value == {"data": "value"}
    assert cache.hits["l1"] == 1


@pytest.mark.asyncio
async def test_multi_layer_cache_accepts_legacy_redis_client_arg():
    from src.cache.multi_layer_cache import MultiLayerCache

    redis_client = object()
    cache = MultiLayerCache(redis_client)

    await cache.set("legacy_key", "value", ttl_seconds=60)

    assert cache.redis_client is redis_client
    assert await cache.get("legacy_key") == "value"


def test_performance_monitor():
    """Test performance monitor"""
    from src.monitoring.performance_monitor import PerformanceMonitor

    monitor = PerformanceMonitor()

    # Track request
    monitor.track_request(latency_ms=150, success=True)
    monitor.track_request(latency_ms=50, success=True)

    metrics = monitor.get_metrics()

    assert metrics["requests"]["total"] == 2
    assert metrics["requests"]["success"] == 2
    assert metrics["latency"]["avg_ms"] == 100


# Test Copilot Components
def test_bsl_dataset_preparation():
    """Test подготовки BSL датасета"""
    from src.ai.copilot.bsl_dataset_preparer import BSLDatasetPreparer

    preparer = BSLDatasetPreparer()

    sample_code = """
// Рассчитывает сумму
Функция РассчитатьСумму(А, Б)
    Возврат А + Б;
КонецФункции
"""

    dataset_entry = preparer.prepare_single_sample(
        sample_code, "Функция для сложения двух чисел"
    )

    assert "instruction" in dataset_entry
    assert "input" in dataset_entry
    assert "output" in dataset_entry


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
