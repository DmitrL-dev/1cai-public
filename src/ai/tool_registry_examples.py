
"""
ToolRegistry examples (experimental)
------------------------------------

Небольшой набор примерных ToolDescriptor для демонстрации
Tool / Skill Registry. Эти данные не используются в продовом
маршруте и нужны как витрина/референс.
"""

from __future__ import annotations

from typing import List

from src.ai.scenario_hub import ScenarioRiskLevel
from src.ai.tool_registry import (
    ToolCategory,
    ToolDescriptor,
    ToolEndpoint,
    ToolProtocol,
    ToolRegistry,
)


def build_example_tool_registry() -> ToolRegistry:
    """Создать реестр с несколькими примерными инструментами."""
    registry = ToolRegistry()

    # Пример: BA Extractor / Requirements Intelligence
    ba_tool = ToolDescriptor(
        id="ba_requirements_extract",
        display_name="BA Requirements Extractor",
        category=ToolCategory.BA,
        risk=ScenarioRiskLevel.READ_ONLY,
        description="Извлечение требований из docx/pdf и формирование структурированного бэклога.",
        input_schema={
            "type": "object",
            "properties": {"document_path": {"type": "string"}},
        },
        output_schema={
            "type": "object",
            "properties": {"requirements": {"type": "array"}},
        },
        endpoints=[
            ToolEndpoint(
                protocol=ToolProtocol.HTTP,
                name="POST /api/ba/extract",
                config={"method": "POST", "path": "/api/ba/extract"},
            )
        ],
        cost_model={"latency_target_ms": 5000, "risk": "read_only"},
        tags=["ba", "requirements", "analysis"],
        docs={
            "guide": "docs/06-features/BUSINESS_ANALYST_GUIDE.md",
        },
    )
    registry.register_tool(ba_tool)

    # Пример: DR rehearsal runner (staging)
    dr_tool = ToolDescriptor(
        id="dr_rehearsal_run",
        display_name="DR Rehearsal Runner (staging)",
        category=ToolCategory.DR,
        risk=ScenarioRiskLevel.NON_PROD_CHANGE,
        description="Запуск DR rehearsal в staging для выбранного сервиса.",
        input_schema={"type": "object", "properties": {"service": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"status": {"type": "string"}}},
        endpoints=[
            ToolEndpoint(
                protocol=ToolProtocol.SCRIPT,
                name="scripts/runbooks/dr_rehearsal_runner.py",
                config={"args": ["{service}"]},
            )
        ],
        cost_model={"latency_target_ms": 600000, "risk": "non_prod_change"},
        tags=["dr", "resilience"],
        docs={
            "runbook": "docs/runbooks/dr_rehearsal_plan.md",
        },
    )
    registry.register_tool(dr_tool)

    # Пример: security-audit aggregator
    sec_tool = ToolDescriptor(
        id="security_audit",
        display_name="Security Audit (local)",
        category=ToolCategory.SECURITY,
        risk=ScenarioRiskLevel.READ_ONLY,
        description="Локальный security-audit (hidden dirs, secrets, git safety, project audit).",
        input_schema={"type": "object", "properties": {}},
        output_schema={
            "type": "object",
            "properties": {"report_path": {"type": "string"}},
        },
        endpoints=[
            ToolEndpoint(
                protocol=ToolProtocol.SCRIPT,
                name="make security-audit",
                config={"shell": True},
            ),
            ToolEndpoint(
                protocol=ToolProtocol.CLI,
                name="scripts/windows/security-audit.ps1",
                config={"shell": True},
            ),
        ],
        cost_model={"latency_target_ms": 900000, "risk": "read_only"},
        tags=["security", "audit"],
        docs={
            "audit_docs": "scripts/audit/README.md",
        },
    )
    registry.register_tool(sec_tool)

    # Пример: BA→Dev→QA Scenario Runner (связка с плейбуком)
    scenario_tool = ToolDescriptor(
        id="scenario_ba_dev_qa",
        display_name="Scenario BA→Dev→QA Runner",
        category=ToolCategory.BA,
        risk=ScenarioRiskLevel.NON_PROD_CHANGE,
        description="Запуск BA→Dev→QA сценария на основе YAML-плейбука.",
        input_schema={
            "type": "object",
            "properties": {"feature_id": {"type": "string"}},
        },
        output_schema={"type": "object", "properties": {"status": {"type": "string"}}},
        endpoints=[
            ToolEndpoint(
                protocol=ToolProtocol.SCRIPT,
                name="scripts/runbooks/run_playbook.py",
                config={
                    "args": [
                        "playbooks/ba_dev_qa_example.yaml",
                        "--autonomy",
                        "A2_non_prod_changes",
                    ]
                },
            )
        ],
        cost_model={"latency_target_ms": 600000, "risk": "non_prod_change"},
        tags=["scenario", "ba-dev-qa"],
        docs={
            "cookbook": "docs/01-getting-started/cookbook.md",
        },
    )
    registry.register_tool(scenario_tool)

    return registry


def list_example_tools() -> List[ToolDescriptor]:
    """Удобный helper для получения списка примерных инструментов."""
    return build_example_tool_registry().list_tools()
