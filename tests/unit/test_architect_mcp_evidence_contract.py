import pytest

from src.ai.agents.sql_optimizer import SQLOptimizer
from src.ai.agents.technology_selector import TechnologySelector
from src.ai.mcp.architect import ARCHITECT_CONTRACT, ArchitectMCPServer


def make_server() -> ArchitectMCPServer:
    server = ArchitectMCPServer.__new__(ArchitectMCPServer)
    server.tech_selector = TechnologySelector()
    server.sql_optimizer = SQLOptimizer("postgresql")
    return server


@pytest.mark.asyncio
async def test_architect_mcp_does_not_fabricate_adrs_or_diagrams():
    server = make_server()

    adrs = await server._list_adrs({}, {})
    diagram = await server._generate_diagram({}, {})

    assert adrs["status"] == "needs_evidence"
    assert adrs["mode"] == ARCHITECT_CONTRACT
    assert adrs["adrs"] == []
    assert "ADR-001" not in str(adrs)

    assert diagram["status"] == "needs_evidence"
    assert diagram["diagram"] == ""
    assert "A --> B" not in str(diagram)


@pytest.mark.asyncio
async def test_architect_mcp_uses_only_context_adrs():
    server = make_server()

    result = await server._get_adr(
        "ADR-002",
        {
            "adrs": [
                {
                    "id": "ADR-002",
                    "title": "Use transactional outbox",
                    "status": "accepted",
                    "decision": "Outbox for 1C integration events",
                }
            ]
        },
    )

    assert result["status"] == "success"
    assert result["coverage"] == "context_adrs_only"
    assert result["adr"]["adr_id"] == "ADR-002"
    assert result["adr"]["decision"] == "Outbox for 1C integration events"


@pytest.mark.asyncio
async def test_architect_mcp_generates_mermaid_from_declared_components():
    server = make_server()

    result = await server._generate_diagram(
        {
            "components": [
                {"id": "1c_erp", "name": "1C ERP", "owner": "erp-team"},
                {"id": "data_bus", "name": "Data Bus", "owner": "platform-team"},
            ],
            "flows": [
                {
                    "source": "1c_erp",
                    "target": "data_bus",
                    "protocol": "AMQP",
                }
            ],
        },
        {},
    )

    assert result["status"] == "success"
    assert result["coverage"] == "declared_components_and_flows"
    assert '1c_erp["1C ERP"]' in result["diagram"]
    assert '1c_erp -->|"AMQP"| data_bus' in result["diagram"]


@pytest.mark.asyncio
async def test_architect_mcp_requirement_and_risk_outputs_are_evidence_marked():
    server = make_server()

    requirements = await server._analyze_requirements(
        "Требуется API обмен с WMS. SLA доступности 99.9%. "
        "Ответ документов должен быть быстрее 2 секунд.",
        {},
    )
    risks = await server._assess_risks(
        {
            "components": [{"id": "erp", "name": "1C ERP"}],
            "flows": [],
        },
        {},
    )

    assert requirements["status"] == "success"
    assert requirements["coverage"] == "source_text_extraction"
    assert {item["category"] for item in requirements["requirements"]} >= {
        "integration",
        "availability",
        "performance",
    }

    assert risks["status"] == "success"
    assert risks["coverage"] == "heuristic_from_declared_architecture"
    assert any(risk["id"] == "ARCH-RISK-002" for risk in risks["risks"])
    assert risks["caveats"]


@pytest.mark.asyncio
async def test_architect_mcp_designs_integration_without_hiding_unknown_contracts():
    server = make_server()

    result = await server._design_integration(
        [{"name": "1C ERP"}, {"name": "WMS"}],
        {},
    )

    assert result["status"] == "success"
    assert result["coverage"] == "declared_systems_with_candidate_flows"
    assert result["integration_architecture"]["flows"][0]["status"] == "candidate"
    assert result["required_evidence"]


@pytest.mark.asyncio
async def test_architect_mcp_generates_openapi_only_from_declared_endpoints():
    server = make_server()

    empty = await server._generate_api_spec({"title": "ERP API"}, {})
    assert empty["status"] == "needs_evidence"
    assert empty["openapi_spec"] == {}

    result = await server._generate_api_spec(
        {
            "title": "ERP API",
            "version": "1.0.0",
            "endpoints": [
                {
                    "method": "POST",
                    "path": "/orders",
                    "summary": "Create order",
                }
            ],
        },
        {},
    )

    assert result["status"] == "success"
    assert result["coverage"] == "declared_endpoints_only"
    assert result["openapi_spec"]["info"]["title"] == "ERP API"
    assert "post" in result["openapi_spec"]["paths"]["/orders"]


@pytest.mark.asyncio
async def test_architect_mcp_compares_known_and_unknown_technologies():
    server = make_server()

    result = await server._compare_technologies(["RabbitMQ", "UnknownBus"], {})

    assert result["status"] == "success"
    assert result["coverage"] == "local_catalog_only"
    matrix = result["comparison"]["matrix"]
    assert any(item.get("technology") == "RabbitMQ" for item in matrix)
    assert any(item.get("catalog_status") == "unknown" for item in matrix)


@pytest.mark.asyncio
async def test_architect_mcp_does_not_default_database_hardware():
    server = make_server()

    result = await server._recommend_db_config("postgresql", {})

    assert result["status"] == "needs_evidence"
    assert result["recommended_config"] == {}
    assert {"ram_gb", "cpu_cores"} == set(result["required_evidence"])
