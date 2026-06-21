import pytest

from src.ai.agents.business_analyst_agent import BusinessAnalystAgent
from src.ai.agents.qa_engineer_agent import QAEngineerAgent
from src.ai.mcp.multi_role import MultiRoleMCPServer
from src.ai.role_based_router import RoleBasedRouter


@pytest.mark.asyncio
async def test_business_analyst_extracts_only_source_backed_requirements():
    agent = BusinessAnalystAgent()
    text = """
    Система должна регистрировать пользователей.
    Производительность: отчет формируется за 5 секунд.
    Как менеджер, я хочу видеть список заявок, чтобы быстро отвечать клиентам.
    Критерий приемки: доступ к отчету проверяется по роли.
    """

    result = await agent.analyze_requirements(text)
    serialized = str(result)

    assert result["mode"] == "offline_evidence_extraction"
    assert result["coverage"] == "source_text"
    assert "регистрировать пользователей" in serialized
    assert "список заявок" in serialized
    assert "модуль продаж" not in serialized.lower()
    assert "1С:УНФ" not in serialized
    assert result["summary"]["total_requirements"] >= 3


@pytest.mark.asyncio
async def test_qa_agent_returns_false_safe_zero_coverage_contract():
    agent = QAEngineerAgent()
    code = """
Функция РассчитатьСкидку(Сумма)
    Возврат Сумма * 0.1;
КонецФункции
"""

    result = await agent.analyze_test_coverage(code)
    serialized = str(result)

    assert result["mode"] == "offline_static_coverage_triage"
    assert result["coverage_measured"] is False
    assert result["coverage"] == "unknown_no_test_evidence"
    assert result["coverage_percent"] == 0.0
    assert "РассчитатьСкидку" in result["uncovered_functions"]
    assert "65" not in serialized
    assert "РассчитатьСумму" not in serialized


@pytest.mark.asyncio
async def test_role_router_default_qa_agent_contract_does_not_crash():
    router = RoleBasedRouter()

    result = await router.route_query(
        "Сгенерируй тесты для этой функции",
        context={
            "role": "qa_engineer",
            "function_name": "РассчитатьСкидку",
            "function_code": "Функция РассчитатьСкидку() Возврат 1; КонецФункции",
        },
    )

    assert result["role"] == "qa_engineer"
    assert result["agent"] == "qa_engineer_agent"
    assert result["result"]["mode"] == "offline_test_blueprint"
    assert result["result"]["test_cases"]


@pytest.mark.asyncio
async def test_multi_role_mcp_returns_evidence_contracts_instead_of_fixtures():
    server = MultiRoleMCPServer()

    arch = await server.handle_request(
        "arch:analyze_architecture", {"config_name": "ERP", "context": {}}
    )
    logs = await server.handle_request(
        "devops:analyze_logs",
        {"logs": "INFO start\nERROR timeout\nWARN slow query", "context": {}},
    )
    docs = await server.handle_request(
        "tw:generate_api_docs", {"module_name": "Orders", "context": {}}
    )

    assert arch["status"] == "needs_evidence"
    assert arch["mode"] == "offline_mcp_contract"
    assert arch["data"]["modules_count"] == 0
    assert "Продажи" not in str(arch)
    assert logs["status"] == "success"
    assert logs["data"]["errors"] == 1
    assert logs["data"]["warnings"] == 1
    assert docs["status"] == "needs_evidence"
    assert "..." not in str(docs)
