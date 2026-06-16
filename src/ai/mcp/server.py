
"""
MCP Server for IDE Integration (Cursor, VSCode)
Версия: 2.1.0

Улучшения:
- Structured logging
- Улучшена обработка ошибок
- Input validation

Model Context Protocol implementation
"""

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.ai.orchestrator import get_orchestrator
from src.config import settings
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

app = FastAPI(title="1C MCP Server")

# Orchestrator
# orchestrator = get_orchestrator() # Access via function call


# MCP Protocol Types
class MCPTool:
    """MCP Tool definition"""

    def __init__(self, name: str, description: str, input_schema: Dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


# Define MCP Tools
BASE_TOOLS = [
    MCPTool(
        name="search_metadata",
        description="Поиск объектов метаданных 1С по структурным свойствам, связям и отношениям. Использует граф метаданных в Neo4j.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Запрос для поиска (например: 'Найди все документы связанные с регистром Продажи')",
                },
                "configuration": {
                    "type": "string",
                    "description": "Фильтр по конфигурации (DO, ERP, ZUP, BUH)",
                    "enum": ["DO", "ERP", "ZUP", "BUH"],
                },
                "object_type": {
                    "type": "string",
                    "description": "Тип объекта (Документ, Справочник, Регистр, и т.д.)",
                },
            },
            "required": ["query"],
        },
    ),
    MCPTool(
        name="search_code_semantic",
        description="Семантический поиск процедур и функций по их описаниям и содержанию. Использует векторный поиск в Qdrant.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Описание искомой функциональности",
                },
                "configuration": {
                    "type": "string",
                    "description": "Фильтр по конфигурации",
                },
                "limit": {
                    "type": "integer",
                    "description": "Количество результатов",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    ),
    MCPTool(
        name="generate_bsl_code",
        description="Генерация BSL кода на основе описания. Использует Qwen3-Coder для создания функций и процедур.",
        input_schema={
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Описание требуемой функциональности",
                },
                "function_name": {"type": "string", "description": "Имя функции"},
                "parameters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Список параметров",
                },
                "context": {
                    "type": "object",
                    "description": "Дополнительный контекст (модуль, объект)",
                },
            },
            "required": ["description"],
        },
    ),
    MCPTool(
        name="analyze_dependencies",
        description="Анализ зависимостей функции или модуля. Строит граф вызовов и показывает все связи.",
        input_schema={
            "type": "object",
            "properties": {
                "module_name": {"type": "string", "description": "Полное имя модуля"},
                "function_name": {"type": "string", "description": "Имя функции"},
            },
            "required": ["module_name", "function_name"],
        },
    ),
    MCPTool(
        name="rentgen_hotspots",
        description="Локальный Рентген: объяснимые hotspots риска по всей 1С-конфигурации.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "domain": {"type": "string"},
                "min_fan_in": {"type": "integer", "default": 0},
            },
        },
    ),
    MCPTool(
        name="rentgen_change_plan",
        description="Локальный Рентген: diff/module list -> blast radius, hotspots, performance risks, test plan and gate status.",
        input_schema={
            "type": "object",
            "properties": {
                "changed_modules": {"type": "array", "items": {"type": "string"}},
                "diff": {"type": "string"},
                "max_depth": {"type": "integer", "default": 5},
                "max_edges": {"type": "integer", "default": 600},
                "risk_threshold": {"type": "integer", "default": 70},
                "impact_threshold": {"type": "integer", "default": 300},
            },
        },
    ),
    MCPTool(
        name="rentgen_release_readiness",
        description="Enterprise release readiness: diff/module list -> release decision, gate violations, metadata/form/security context and test actions.",
        input_schema={
            "type": "object",
            "properties": {
                "release_name": {"type": "string"},
                "changed_modules": {"type": "array", "items": {"type": "string"}},
                "diff": {"type": "string"},
                "snapshot_id": {"type": "string"},
                "include_security": {"type": "boolean", "default": False},
                "include_forms": {"type": "boolean", "default": True},
                "max_depth": {"type": "integer", "default": 5},
                "max_edges": {"type": "integer", "default": 600},
                "risk_threshold": {"type": "integer", "default": 70},
                "impact_threshold": {"type": "integer", "default": 300},
            },
        },
    ),
    MCPTool(
        name="rentgen_architecture_review",
        description="Architecture boundary review over the Rentgen module graph: layers, forbidden dependencies, cycles and dense coupling.",
        input_schema={
            "type": "object",
            "properties": {
                "changed_modules": {"type": "array", "items": {"type": "string"}},
                "diff": {"type": "string"},
                "limit": {"type": "integer", "default": 5000},
                "min_weight": {"type": "integer", "default": 1},
                "dense_threshold": {"type": "integer", "default": 250},
                "include_cycles": {"type": "boolean", "default": True},
                "finding_limit": {"type": "integer", "default": 200},
            },
        },
    ),
    MCPTool(
        name="rentgen_generate_grounded",
        description="Generate deterministic graph-grounded BSL with Rentgen impact, metadata, ITS context, diagnostics and test actions.",
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "type": {"type": "string", "enum": ["function", "procedure", "test"], "default": "function"},
                "module_path": {"type": "string"},
                "metadata_identifier": {"type": "string"},
                "include_its_context": {"type": "boolean", "default": True},
                "include_requirement_impact": {"type": "boolean", "default": True},
            },
            "required": ["prompt"],
        },
    ),
    MCPTool(
        name="rentgen_requirement_impact",
        description="Локальный Рентген: business requirement text -> likely modules, impact and test plan.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "limit": {"type": "integer", "default": 6},
                "max_depth": {"type": "integer", "default": 3},
                "max_edges": {"type": "integer", "default": 200},
            },
            "required": ["text"],
        },
    ),
    MCPTool(
        name="rentgen_requirement_trace",
        description="Build and optionally persist requirement -> metadata/code/tests trace links with markdown.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "title": {"type": "string"},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 6},
                "max_depth": {"type": "integer", "default": 3},
                "max_edges": {"type": "integer", "default": 200},
                "include_its_context": {"type": "boolean", "default": True},
                "save": {"type": "boolean", "default": True},
            },
            "required": ["text"],
        },
    ),
    MCPTool(
        name="rentgen_metadata_search",
        description="Local EDT metadata graph search: objects, forms, modules, roles and rights presence.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "type": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    ),
    MCPTool(
        name="rentgen_metadata_object_impact",
        description="Local EDT metadata object -> modules -> Rentgen blast radius.",
        input_schema={
            "type": "object",
            "properties": {
                "identifier": {"type": "string"},
                "max_depth": {"type": "integer", "default": 3},
                "max_edges": {"type": "integer", "default": 150},
            },
            "required": ["identifier"],
        },
    ),
    MCPTool(
        name="rentgen_metadata_security_review",
        description="Static 1C role/Rights.xml security review with dangerous rights findings.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 100}},
        },
    ),
    MCPTool(
        name="rentgen_security_posture",
        description="1C security posture: role diff readiness, dangerous rights, privileged code and external integrations.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 100},
                "module_limit": {"type": "integer", "default": 2500},
                "snapshot_id": {"type": "string"},
            },
        },
    ),
    MCPTool(
        name="rentgen_metadata_data_governance",
        description="Static EDT data governance review: data objects, registers, exchanges, rights and migration findings.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 120}},
        },
    ),
    MCPTool(
        name="rentgen_offline_readiness",
        description="Closed-contour self-test: local stores, offline ITS, local model presence and external env surface.",
        input_schema={
            "type": "object",
            "properties": {"strict": {"type": "boolean", "default": False}},
        },
    ),
    MCPTool(
        name="rentgen_its_search",
        description="Offline-first ITS documentation search for 1C platform and standards context.",
        input_schema={
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
                "section_filter": {"type": "string"},
            },
            "required": ["question"],
        },
    ),
    MCPTool(
        name="rentgen_its_context",
        description="Formatted ITS context for LLM/IDE augmentation.",
        input_schema={
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "limit": {"type": "integer", "default": 3},
                "max_chars": {"type": "integer", "default": 6000},
            },
            "required": ["question"],
        },
    ),
    MCPTool(
        name="rentgen_performer_analyze",
        description="Analyze 1C Technology Journal logs for slow queries, N+1, locks and deadlocks.",
        input_schema={
            "type": "object",
            "properties": {
                "log_path": {"type": "string"},
                "min_duration_ms": {"type": "number", "default": 100},
                "top_n": {"type": "integer", "default": 20},
            },
            "required": ["log_path"],
        },
    ),
    MCPTool(
        name="rentgen_performer_impact",
        description="Analyze Technology Journal logs and map query hotspots to Rentgen blast radius.",
        input_schema={
            "type": "object",
            "properties": {
                "log_path": {"type": "string"},
                "min_duration_ms": {"type": "number", "default": 100},
                "top_n": {"type": "integer", "default": 20},
                "max_depth": {"type": "integer", "default": 5},
                "max_edges": {"type": "integer", "default": 300},
            },
            "required": ["log_path"],
        },
    ),
    MCPTool(
        name="rentgen_form_review",
        description="Static EDT form XML + form-module review for a metadata object.",
        input_schema={
            "type": "object",
            "properties": {
                "identifier": {"type": "string"},
                "form_name": {"type": "string"},
            },
            "required": ["identifier"],
        },
    ),
    MCPTool(
        name="rentgen_form_blueprint",
        description="Generate a deterministic 1C managed-form blueprint with layout, commands, XML draft and BSL module draft.",
        input_schema={
            "type": "object",
            "properties": {
                "identifier": {"type": "string"},
                "form_kind": {"type": "string", "enum": ["auto", "object", "list", "choice"], "default": "auto"},
                "intent": {"type": "string"},
                "include_review": {"type": "boolean", "default": True},
            },
            "required": ["identifier"],
        },
    ),
    MCPTool(
        name="bsl_diagnostics",
        description="Offline deterministic BSL diagnostics for pasted code or diff hunks.",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "module_path": {"type": "string"},
            },
            "required": ["code"],
        },
    ),
    MCPTool(
        name="bsl_standards_review",
        description="Catalog-aware offline BSL standards review with auto-fix hints and optional local storage.",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "module_path": {"type": "string"},
                "max_nesting_threshold": {"type": "integer", "default": 5},
                "save": {"type": "boolean", "default": False},
            },
            "required": ["code"],
        },
    ),
    MCPTool(
        name="rentgen_test_match",
        description="Match a changed 1C module/object to known local BSL/YAxUnit test cases.",
        input_schema={
            "type": "object",
            "properties": {
                "module_path": {"type": "string"},
                "object_name": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["module_path"],
        },
    ),
    MCPTool(
        name="rentgen_test_coverage_matrix",
        description="Build exact/planned/gap YAxUnit/Vanessa coverage matrix for changed modules or diff.",
        input_schema={
            "type": "object",
            "properties": {
                "changed_modules": {"type": "array", "items": {"type": "string"}},
                "diff": {"type": "string"},
                "max_depth": {"type": "integer", "default": 5},
                "max_edges": {"type": "integer", "default": 600},
                "hotspot_limit": {"type": "integer", "default": 10},
                "match_limit": {"type": "integer", "default": 10},
            },
        },
    ),
    MCPTool(
        name="rentgen_incident_report",
        description="Operations incident-to-code report: symptoms/TJ logs/modules -> impact, owners, tests and runbook.",
        input_schema={
            "type": "object",
            "properties": {
                "incident_title": {"type": "string"},
                "description": {"type": "string"},
                "symptoms": {"type": "array", "items": {"type": "string"}},
                "log_path": {"type": "string"},
                "changed_modules": {"type": "array", "items": {"type": "string"}},
                "min_duration_ms": {"type": "number", "default": 100},
                "top_n": {"type": "integer", "default": 20},
                "module_limit": {"type": "integer", "default": 12},
                "max_depth": {"type": "integer", "default": 5},
                "max_edges": {"type": "integer", "default": 300},
                "include_team": {"type": "boolean", "default": True},
            },
        },
    ),
    MCPTool(
        name="rentgen_team_governance",
        description="Build team ownership, risk SLA, review queue and governance trend board from Rentgen quality domains.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 40},
                "save_snapshot": {"type": "boolean", "default": False},
            },
        },
    ),
    MCPTool(
        name="artifact_create",
        description="Create an internal 1cAI ALM artifact: requirement, change_set, test_case, release, incident and related governance records.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "type": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "status": {"type": "string"},
                "owner": {"type": "string"},
                "risk": {"type": "string"},
                "priority": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "source": {"type": "string"},
                "attributes": {"type": "object"},
            },
            "required": ["type", "title"],
        },
    ),
    MCPTool(
        name="artifact_link",
        description="Create a directed traceability link between two internal 1cAI ALM artifacts.",
        input_schema={
            "type": "object",
            "properties": {
                "source_id": {"type": "string"},
                "target_id": {"type": "string"},
                "type": {"type": "string"},
                "rationale": {"type": "string"},
                "status": {"type": "string", "default": "active"},
                "suspect": {"type": "boolean", "default": False},
                "attributes": {"type": "object"},
            },
            "required": ["source_id", "target_id", "type"],
        },
    ),
    MCPTool(
        name="artifact_trace",
        description="Traverse incoming/outgoing links around one internal 1cAI ALM artifact.",
        input_schema={
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "depth": {"type": "integer", "default": 4},
                "direction": {"type": "string", "enum": ["in", "out", "both"], "default": "both"},
            },
            "required": ["artifact_id"],
        },
    ),
    MCPTool(
        name="artifact_matrix",
        description="Return requirements-oriented internal ALM coverage matrix from 1cAI artifact graph.",
        input_schema={"type": "object", "properties": {}},
    ),
    MCPTool(
        name="change_set_create",
        description="Create an internal 1cAI change set linked to requirements, changed modules and diff.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "owner": {"type": "string"},
                "source_requirement_ids": {"type": "array", "items": {"type": "string"}},
                "changed_modules": {"type": "array", "items": {"type": "string"}},
                "diff": {"type": "string"},
            },
            "required": ["title"],
        },
    ),
    MCPTool(
        name="change_set_analyze",
        description="Attach Rentgen impact analysis to an internal 1cAI change set.",
        input_schema={
            "type": "object",
            "properties": {
                "change_set_id": {"type": "string"},
                "max_depth": {"type": "integer", "default": 5},
                "max_edges": {"type": "integer", "default": 600},
                "hotspot_limit": {"type": "integer", "default": 10},
            },
            "required": ["change_set_id"],
        },
    ),
    MCPTool(
        name="change_set_select_tests",
        description="Attach risk-driven YAxUnit/Vanessa test coverage matrix to an internal 1cAI change set.",
        input_schema={
            "type": "object",
            "properties": {
                "change_set_id": {"type": "string"},
                "max_depth": {"type": "integer", "default": 5},
                "max_edges": {"type": "integer", "default": 600},
                "hotspot_limit": {"type": "integer", "default": 10},
                "match_limit": {"type": "integer", "default": 10},
            },
            "required": ["change_set_id"],
        },
    ),
    MCPTool(
        name="change_set_release_readiness",
        description="Attach release-readiness decision report to an internal 1cAI change set.",
        input_schema={
            "type": "object",
            "properties": {
                "change_set_id": {"type": "string"},
                "include_security": {"type": "boolean", "default": False},
                "include_forms": {"type": "boolean", "default": True},
            },
            "required": ["change_set_id"],
        },
    ),
    MCPTool(
        name="change_set_transition",
        description="Move an internal 1cAI change set through its lifecycle with actor/reason decision evidence.",
        input_schema={
            "type": "object",
            "properties": {
                "change_set_id": {"type": "string"},
                "status": {"type": "string"},
                "actor": {"type": "string"},
                "reason": {"type": "string"},
                "allow_policy_failure": {"type": "boolean", "default": False},
            },
            "required": ["change_set_id", "status"],
        },
    ),
    MCPTool(
        name="baseline_create",
        description="Create an immutable internal 1cAI baseline snapshot for selected artifact ids.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "owner": {"type": "string"},
                "artifact_ids": {"type": "array", "items": {"type": "string"}},
                "release_id": {"type": "string"},
                "change_set_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "artifact_ids"],
        },
    ),
    MCPTool(
        name="review_pack_create",
        description="Create an internal 1cAI review pack with a fixed set of artifacts and reviewers.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "owner": {"type": "string"},
                "artifact_ids": {"type": "array", "items": {"type": "string"}},
                "reviewers": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "artifact_ids"],
        },
    ),
    MCPTool(
        name="review_pack_decide",
        description="Approve or reject an internal 1cAI review pack with actor/reason evidence.",
        input_schema={
            "type": "object",
            "properties": {
                "review_pack_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["approved", "rejected"]},
                "actor": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["review_pack_id", "decision"],
        },
    ),
    MCPTool(
        name="policy_evaluate",
        description="Evaluate 1cAI policy-as-code rules against a workflow context and store gate evidence.",
        input_schema={
            "type": "object",
            "properties": {
                "context": {"type": "object"},
                "domain": {"type": "string"},
                "scope_id": {"type": "string"},
                "persist": {"type": "boolean", "default": True},
            },
            "required": ["context"],
        },
    ),
    MCPTool(
        name="policy_waiver_request",
        description="Request a temporary policy waiver with owner, reason, expiration and remediation plan.",
        input_schema={
            "type": "object",
            "properties": {
                "rule_id": {"type": "string"},
                "scope_id": {"type": "string"},
                "reason": {"type": "string"},
                "owner": {"type": "string"},
                "expires_in_days": {"type": "integer", "default": 30},
                "remediation": {"type": "string"},
            },
            "required": ["rule_id", "reason", "owner"],
        },
    ),
    MCPTool(
        name="policy_waiver_decide",
        description="Approve or reject a requested policy waiver.",
        input_schema={
            "type": "object",
            "properties": {
                "waiver_id": {"type": "string"},
                "status": {"type": "string", "enum": ["approved", "rejected"]},
                "actor": {"type": "string"},
                "decision_reason": {"type": "string"},
            },
            "required": ["waiver_id", "status"],
        },
    ),
    MCPTool(
        name="test_run_record",
        description="Record normalized test execution evidence and link it to a 1cAI change set when provided.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "framework": {"type": "string"},
                "results": {"type": "array", "items": {"type": "object"}},
                "change_set_id": {"type": "string"},
                "command": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["title", "framework", "results"],
        },
    ),
    MCPTool(
        name="test_run_import_junit",
        description="Import JUnit XML into the 1cAI test evidence store and project it into the artifact graph.",
        input_schema={
            "type": "object",
            "properties": {
                "xml_text": {"type": "string"},
                "title": {"type": "string", "default": "JUnit import"},
                "framework": {"type": "string", "default": "JUnit"},
                "change_set_id": {"type": "string"},
            },
            "required": ["xml_text"],
        },
    ),
    MCPTool(
        name="test_run_list",
        description="List stored 1cAI test execution evidence, optionally filtered by status or change set.",
        input_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "change_set_id": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
        },
    ),
    MCPTool(
        name="test_runner_plan",
        description="Build a dry-run command plan for YAxUnit, Vanessa, BSL manifest or 1C:Tester without executing external commands.",
        input_schema={
            "type": "object",
            "properties": {
                "adapter": {"type": "string"},
                "test_files": {"type": "array", "items": {"type": "string"}},
                "modules": {"type": "array", "items": {"type": "string"}},
                "selectors": {"type": "array", "items": {"type": "string"}},
                "manifest_path": {"type": "string"},
                "output_dir": {"type": "string"},
                "report_path": {"type": "string"},
                "cwd": {"type": "string"},
                "env": {"type": "object"},
                "timeout": {"type": "integer", "default": 1800},
                "extra_args": {"type": "array", "items": {"type": "string"}},
                "change_set_id": {"type": "string"},
            },
            "required": ["adapter"],
        },
    ),
    MCPTool(
        name="test_runner_run",
        description="Dry-run by default, or explicitly execute a local test runner adapter and store evidence.",
        input_schema={
            "type": "object",
            "properties": {
                "adapter": {"type": "string"},
                "execute": {"type": "boolean", "default": False},
                "allow_external": {"type": "boolean", "default": False},
                "import_results": {"type": "boolean", "default": True},
                "test_files": {"type": "array", "items": {"type": "string"}},
                "modules": {"type": "array", "items": {"type": "string"}},
                "selectors": {"type": "array", "items": {"type": "string"}},
                "manifest_path": {"type": "string"},
                "output_dir": {"type": "string"},
                "report_path": {"type": "string"},
                "cwd": {"type": "string"},
                "env": {"type": "object"},
                "timeout": {"type": "integer", "default": 1800},
                "extra_args": {"type": "array", "items": {"type": "string"}},
                "change_set_id": {"type": "string"},
            },
            "required": ["adapter"],
        },
    ),
    MCPTool(
        name="test_result_import_file",
        description="Import JUnit XML, generic JSON or Allure result files from disk into 1cAI test evidence.",
        input_schema={
            "type": "object",
            "properties": {
                "result_path": {"type": "string"},
                "result_format": {"type": "string", "default": "auto"},
                "title": {"type": "string"},
                "framework": {"type": "string"},
                "change_set_id": {"type": "string"},
            },
            "required": ["result_path"],
        },
    ),
    MCPTool(
        name="metadata_canonical_import",
        description="Import EDT metadata into the canonical 1cAI metadata store and synchronize Artifact Graph.",
        input_schema={
            "type": "object",
            "properties": {
                "config_path": {"type": "string"},
                "name": {"type": "string"},
                "source": {"type": "string", "default": "edt"},
                "refresh": {"type": "boolean", "default": True},
            },
        },
    ),
    MCPTool(
        name="metadata_canonical_objects",
        description="List canonical 1C metadata objects by type, group or query.",
        input_schema={
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "group": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
        },
    ),
    MCPTool(
        name="metadata_canonical_drift",
        description="Compare two canonical metadata snapshots, or a snapshot with the latest import.",
        input_schema={
            "type": "object",
            "properties": {
                "before_id": {"type": "string"},
                "after_id": {"type": "string"},
                "limit": {"type": "integer", "default": 200},
            },
            "required": ["before_id"],
        },
    ),
    MCPTool(
        name="metadata_rights_diff",
        description="Compare canonical role-rights changes between metadata snapshots.",
        input_schema={
            "type": "object",
            "properties": {
                "before_id": {"type": "string"},
                "after_id": {"type": "string"},
                "limit": {"type": "integer", "default": 200},
            },
            "required": ["before_id"],
        },
    ),
    MCPTool(
        name="agentic_plan_create",
        description="Create a deterministic 1cAI agentic work plan with source artifacts, steps and mode guardrails.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "objective": {"type": "string"},
                "mode": {"type": "string", "default": "plan"},
                "actor": {"type": "string"},
                "change_set_id": {"type": "string"},
                "source_artifact_ids": {"type": "array", "items": {"type": "string"}},
                "steps": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["title"],
        },
    ),
    MCPTool(
        name="agentic_plan_review",
        description="Review an agentic plan against mode rules, artifact traces, policy and test evidence.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
            },
            "required": ["plan_id"],
        },
    ),
    MCPTool(
        name="agentic_action_gate",
        description="Check whether an agentic action is allowed before risky write/run/release execution.",
        input_schema={
            "type": "object",
            "properties": {
                "action_type": {"type": "string"},
                "plan_id": {"type": "string"},
                "change_set_id": {"type": "string"},
                "risk": {"type": "string", "default": "low"},
                "confirm": {"type": "boolean", "default": False},
            },
            "required": ["action_type"],
        },
    ),
    MCPTool(
        name="productization_readiness",
        description="Check enterprise productization readiness: docs, governance core, tests, reviews, known production gaps and non-AI value.",
        input_schema={
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["json", "markdown"], "default": "json"},
            },
        },
    ),
    MCPTool(
        name="offline_bundle_manifest",
        description="Build a reproducible offline bundle manifest with sha256 hashes and optional env-based HMAC signature.",
        input_schema={
            "type": "object",
            "properties": {
                "profile": {"type": "string", "enum": ["pilot", "production", "airgap"], "default": "pilot"},
                "include_paths": {"type": "array", "items": {"type": "string"}},
                "include_defaults": {"type": "boolean", "default": True},
                "output_path": {"type": "string"},
                "sign": {"type": "boolean", "default": False},
                "write": {"type": "boolean", "default": True},
            },
        },
    ),
    MCPTool(
        name="offline_bundle_verify",
        description="Verify an offline bundle manifest: referenced file hashes, manifest digest and optional signature.",
        input_schema={
            "type": "object",
            "properties": {
                "manifest_path": {"type": "string"},
            },
        },
    ),
    MCPTool(
        name="offline_bundle_archive",
        description="Build a portable offline ZIP bundle containing payload files, manifest.json and VERIFY.txt.",
        input_schema={
            "type": "object",
            "properties": {
                "profile": {"type": "string", "enum": ["pilot", "production", "airgap"], "default": "pilot"},
                "include_paths": {"type": "array", "items": {"type": "string"}},
                "include_defaults": {"type": "boolean", "default": True},
                "output_path": {"type": "string"},
                "sign": {"type": "boolean", "default": False},
            },
        },
    ),
    MCPTool(
        name="offline_bundle_archive_verify",
        description="Verify a portable offline ZIP bundle without extracting it.",
        input_schema={
            "type": "object",
            "properties": {
                "archive_path": {"type": "string"},
            },
            "required": ["archive_path"],
        },
    ),
    MCPTool(
        name="sbom_generate",
        description="Generate a local offline SBOM/dependency inventory from requirements, package.json/package-lock and Dockerfiles.",
        input_schema={
            "type": "object",
            "properties": {
                "include_paths": {"type": "array", "items": {"type": "string"}},
                "include_defaults": {"type": "boolean", "default": True},
                "output_path": {"type": "string"},
                "write": {"type": "boolean", "default": True},
                "format": {"type": "string", "enum": ["json", "markdown"], "default": "json"},
            },
        },
    ),
    MCPTool(
        name="edt_mcp_toolsets",
        description="List the curated DitriXNew EDT-MCP toolsets, presets, reuse policy and high-value 1cAI integration points.",
        input_schema={"type": "object", "properties": {}},
    ),
    MCPTool(
        name="edt_mcp_plan",
        description="Plan which EDT-MCP toolsets/tools and 1cAI companion tools to use for an EDT-native task.",
        input_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "intent": {"type": "string"},
            },
            "required": ["task"],
        },
    ),
    MCPTool(
        name="edt_mcp_connection_config",
        description="Return ready-to-copy MCP client snippets for connecting to a local EDT-MCP server.",
        input_schema={
            "type": "object",
            "properties": {
                "base_url": {"type": "string", "default": "http://127.0.0.1:8765"},
            },
        },
    ),
    MCPTool(
        name="edt_mcp_status",
        description="Probe a live EDT-MCP server on /health and /mcp without mutating EDT state.",
        input_schema={
            "type": "object",
            "properties": {
                "base_url": {"type": "string", "default": "http://127.0.0.1:8765"},
                "auth_token": {"type": "string"},
                "timeout_s": {"type": "number", "default": 5},
            },
        },
    ),
    MCPTool(
        name="edt_mcp_live_tools",
        description="Read live EDT-MCP tools/list and enrich each tool with the 1cAI safety classification.",
        input_schema={
            "type": "object",
            "properties": {
                "base_url": {"type": "string", "default": "http://127.0.0.1:8765"},
                "auth_token": {"type": "string"},
                "timeout_s": {"type": "number", "default": 10},
            },
        },
    ),
    MCPTool(
        name="edt_mcp_call",
        description="Call a live EDT-MCP tool through the 1cAI safety gate. Write/execute/unknown tools require confirm=true, actor and approval_reason.",
        input_schema={
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "arguments": {"type": "object"},
                "base_url": {"type": "string", "default": "http://127.0.0.1:8765"},
                "auth_token": {"type": "string"},
                "confirm": {"type": "boolean", "default": False},
                "actor": {"type": "string"},
                "approval_reason": {"type": "string"},
                "approval_ticket": {"type": "string"},
                "approval_id": {"type": "string"},
                "timeout_s": {"type": "number", "default": 30},
            },
            "required": ["tool_name"],
        },
    ),
]

TOOLS = BASE_TOOLS.copy()

if os.getenv("ENABLE_MCP_EXTERNAL_TOOLS", "false").lower() == "true":
    TOOLS.extend(
        [
            MCPTool(
                name="bsl_platform_context",
                description="Прокси к внешнему MCP (alkoleft/mcp-bsl-platform-context) для получения платформенного контекста 1С.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Что нужно найти (например, 'Документ Продажи, реквизиты, табличные части')",
                        },
                        "scope": {
                            "type": "object",
                            "description": "Дополнительные параметры запроса (см. документацию внешнего MCP сервера)",
                        },
                    },
                    "required": ["query"],
                },
            ),
            MCPTool(
                name="bsl_test_runner",
                description="Прокси к внешнему MCP (alkoleft/mcp-onec-test-runner) для запуска BSL/Vanessa тестов.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "workspace": {
                            "type": "string",
                            "description": "Путь к проекту или workspace, который должен запускать тесты",
                        },
                        "testPlan": {
                            "type": "string",
                            "description": "Опциональный путь к testplan для запуска (см. документацию внешнего runner)",
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Дополнительные параметры запуска",
                        },
                    },
                    "required": ["workspace"],
                },
            ),
        ]
    )


# MCP Endpoints
@app.get("/mcp")
async def mcp_root():
    """MCP server info"""
    return {
        "name": "1C AI Assistant MCP Server",
        "version": "1.0.0",
        "protocol": "mcp/1.0",
        "capabilities": {"tools": True, "prompts": False, "resources": False},
    }


@app.get("/mcp/tools")
async def list_tools():
    """List available MCP tools"""
    return {"tools": [tool.to_dict() for tool in TOOLS]}


@app.post("/mcp/tools/call")
async def call_tool(request: Request):
    """Execute MCP tool"""
    try:
        body = await request.json()

        tool_name = body.get("name")
        arguments = body.get("arguments", {})

        # Input validation
        if not tool_name or not isinstance(tool_name, str):
            logger.warning(
                f"Invalid tool_name: {tool_name}",
                extra={
                    "tool_name": tool_name,
                    "tool_name_type": type(tool_name).__name__,
                },
            )
            return JSONResponse(
                status_code=400,
                content={"error": "Tool name is required and must be a string"},
            )

        logger.info(
            f"MCP tool called: {tool_name}",
            extra={
                "tool_name": tool_name,
                "arguments_keys": (
                    list(arguments.keys()) if isinstance(arguments, dict) else []
                ),
            },
        )

        # Route to appropriate handler
        if tool_name == "search_metadata":
            result = await handle_search_metadata(arguments)

        elif tool_name == "search_code_semantic":
            result = await handle_search_code(arguments)

        elif tool_name == "generate_bsl_code":
            result = await handle_generate_code(arguments)

        elif tool_name == "analyze_dependencies":
            result = await handle_analyze_dependencies(arguments)

        elif tool_name == "rentgen_hotspots":
            result = await handle_rentgen_hotspots(arguments)

        elif tool_name == "rentgen_change_plan":
            result = await handle_rentgen_change_plan(arguments)

        elif tool_name == "rentgen_release_readiness":
            result = await handle_rentgen_release_readiness(arguments)

        elif tool_name == "rentgen_architecture_review":
            result = await handle_rentgen_architecture_review(arguments)

        elif tool_name == "rentgen_generate_grounded":
            result = await handle_rentgen_generate_grounded(arguments)

        elif tool_name == "rentgen_requirement_impact":
            result = await handle_rentgen_requirement_impact(arguments)

        elif tool_name == "rentgen_requirement_trace":
            result = await handle_rentgen_requirement_trace(arguments)

        elif tool_name == "rentgen_metadata_search":
            result = await handle_rentgen_metadata_search(arguments)

        elif tool_name == "rentgen_metadata_object_impact":
            result = await handle_rentgen_metadata_object_impact(arguments)

        elif tool_name == "rentgen_metadata_security_review":
            result = await handle_rentgen_metadata_security_review(arguments)

        elif tool_name == "rentgen_security_posture":
            result = await handle_rentgen_security_posture(arguments)

        elif tool_name == "rentgen_metadata_data_governance":
            result = await handle_rentgen_metadata_data_governance(arguments)

        elif tool_name == "rentgen_offline_readiness":
            result = await handle_rentgen_offline_readiness(arguments)

        elif tool_name == "rentgen_its_search":
            result = await handle_rentgen_its_search(arguments)

        elif tool_name == "rentgen_its_context":
            result = await handle_rentgen_its_context(arguments)

        elif tool_name == "rentgen_performer_analyze":
            result = await handle_rentgen_performer_analyze(arguments)

        elif tool_name == "rentgen_performer_impact":
            result = await handle_rentgen_performer_impact(arguments)

        elif tool_name == "rentgen_form_review":
            result = await handle_rentgen_form_review(arguments)

        elif tool_name == "rentgen_form_blueprint":
            result = await handle_rentgen_form_blueprint(arguments)

        elif tool_name == "bsl_diagnostics":
            result = await handle_bsl_diagnostics(arguments)

        elif tool_name == "bsl_standards_review":
            result = await handle_bsl_standards_review(arguments)

        elif tool_name == "rentgen_test_match":
            result = await handle_rentgen_test_match(arguments)

        elif tool_name == "rentgen_test_coverage_matrix":
            result = await handle_rentgen_test_coverage_matrix(arguments)

        elif tool_name == "rentgen_incident_report":
            result = await handle_rentgen_incident_report(arguments)

        elif tool_name == "rentgen_team_governance":
            result = await handle_rentgen_team_governance(arguments)

        elif tool_name == "artifact_create":
            result = await handle_artifact_create(arguments)

        elif tool_name == "artifact_link":
            result = await handle_artifact_link(arguments)

        elif tool_name == "artifact_trace":
            result = await handle_artifact_trace(arguments)

        elif tool_name == "artifact_matrix":
            result = await handle_artifact_matrix(arguments)

        elif tool_name == "change_set_create":
            result = await handle_change_set_create(arguments)

        elif tool_name == "change_set_analyze":
            result = await handle_change_set_analyze(arguments)

        elif tool_name == "change_set_select_tests":
            result = await handle_change_set_select_tests(arguments)

        elif tool_name == "change_set_release_readiness":
            result = await handle_change_set_release_readiness(arguments)

        elif tool_name == "change_set_transition":
            result = await handle_change_set_transition(arguments)

        elif tool_name == "baseline_create":
            result = await handle_baseline_create(arguments)

        elif tool_name == "review_pack_create":
            result = await handle_review_pack_create(arguments)

        elif tool_name == "review_pack_decide":
            result = await handle_review_pack_decide(arguments)

        elif tool_name == "policy_evaluate":
            result = await handle_policy_evaluate(arguments)

        elif tool_name == "policy_waiver_request":
            result = await handle_policy_waiver_request(arguments)

        elif tool_name == "policy_waiver_decide":
            result = await handle_policy_waiver_decide(arguments)

        elif tool_name == "test_run_record":
            result = await handle_test_run_record(arguments)

        elif tool_name == "test_run_import_junit":
            result = await handle_test_run_import_junit(arguments)

        elif tool_name == "test_run_list":
            result = await handle_test_run_list(arguments)

        elif tool_name == "test_runner_plan":
            result = await handle_test_runner_plan(arguments)

        elif tool_name == "test_runner_run":
            result = await handle_test_runner_run(arguments)

        elif tool_name == "test_result_import_file":
            result = await handle_test_result_import_file(arguments)

        elif tool_name == "metadata_canonical_import":
            result = await handle_metadata_canonical_import(arguments)

        elif tool_name == "metadata_canonical_objects":
            result = await handle_metadata_canonical_objects(arguments)

        elif tool_name == "metadata_canonical_drift":
            result = await handle_metadata_canonical_drift(arguments)

        elif tool_name == "metadata_rights_diff":
            result = await handle_metadata_rights_diff(arguments)

        elif tool_name == "agentic_plan_create":
            result = await handle_agentic_plan_create(arguments)

        elif tool_name == "agentic_plan_review":
            result = await handle_agentic_plan_review(arguments)

        elif tool_name == "agentic_action_gate":
            result = await handle_agentic_action_gate(arguments)

        elif tool_name == "productization_readiness":
            result = await handle_productization_readiness(arguments)

        elif tool_name == "offline_bundle_manifest":
            result = await handle_offline_bundle_manifest(arguments)

        elif tool_name == "offline_bundle_verify":
            result = await handle_offline_bundle_verify(arguments)

        elif tool_name == "offline_bundle_archive":
            result = await handle_offline_bundle_archive(arguments)

        elif tool_name == "offline_bundle_archive_verify":
            result = await handle_offline_bundle_archive_verify(arguments)

        elif tool_name == "sbom_generate":
            result = await handle_sbom_generate(arguments)

        elif tool_name == "edt_mcp_toolsets":
            result = await handle_edt_mcp_toolsets(arguments)

        elif tool_name == "edt_mcp_plan":
            result = await handle_edt_mcp_plan(arguments)

        elif tool_name == "edt_mcp_connection_config":
            result = await handle_edt_mcp_connection_config(arguments)

        elif tool_name == "edt_mcp_status":
            result = await handle_edt_mcp_status(arguments)

        elif tool_name == "edt_mcp_live_tools":
            result = await handle_edt_mcp_live_tools(arguments)

        elif tool_name == "edt_mcp_call":
            result = await handle_edt_mcp_call(arguments)

        elif tool_name == "bsl_platform_context":
            result = await handle_bsl_platform_context(arguments)

        elif tool_name == "bsl_test_runner":
            result = await handle_bsl_test_runner(arguments)

        else:
            logger.warning(
                f"Tool not found: {tool_name}", extra={"tool_name": tool_name}
            )
            return JSONResponse(
                status_code=404, content={"error": f"Tool not found: {tool_name}"}
            )

        logger.debug(
            f"MCP tool executed successfully: {tool_name}",
            extra={"tool_name": tool_name},
        )

        return {"result": result}

    except Exception as e:
        logger.error(
            f"Tool execution error: {e}",
            extra={
                "tool_name": tool_name if "tool_name" in locals() else None,
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/")
async def mcp_root_alias():
    """MCP server info for mounted /mcp deployments."""
    return await mcp_root()


@app.get("/tools")
async def list_tools_alias():
    """List tools for mounted /mcp deployments."""
    return await list_tools()


@app.post("/tools/call")
async def call_tool_alias(request: Request):
    """Execute tools for mounted /mcp deployments."""
    return await call_tool(request)


# Tool handlers
async def handle_search_metadata(args: Dict) -> Dict:
    """Handle metadata search with input validation and error handling"""
    try:
        query = args.get("query")

        # Input validation
        if not query or not isinstance(query, str):
            logger.warning(
                "Invalid query in handle_search_metadata",
                extra={"query_type": type(query).__name__ if query else None},
            )
            return {"error": "Query is required and must be a non-empty string"}

        # Validate query length
        max_query_length = 5000
        if len(query) > max_query_length:
            logger.warning(
                "Query too long in handle_search_metadata",
                extra={"query_length": len(query), "max_length": max_query_length},
            )
            return {
                "error": f"Query too long. Maximum length: {max_query_length} characters"
            }

        logger.debug("Processing metadata search", extra={"query_length": len(query)})

        response = await get_orchestrator().process_query(
            query, context={"type": "metadata_search", **args}
        )

        return response
    except Exception as e:
        logger.error(
            f"Error in handle_search_metadata: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )
        return {"error": f"Failed to process metadata search: {str(e)}"}


async def handle_search_code(args: Dict) -> Dict:
    """Handle semantic code search with input validation and error handling"""
    try:
        query = args.get("query")

        # Input validation
        if not query or not isinstance(query, str):
            logger.warning(
                "Invalid query in handle_search_code",
                extra={"query_type": type(query).__name__ if query else None},
            )
            return {"error": "Query is required and must be a non-empty string"}

        # Validate query length
        max_query_length = 5000
        if len(query) > max_query_length:
            logger.warning(
                "Query too long in handle_search_code",
                extra={"query_length": len(query), "max_length": max_query_length},
            )
            return {
                "error": f"Query too long. Maximum length: {max_query_length} characters"
            }

        logger.debug(
            "Processing semantic code search", extra={"query_length": len(query)}
        )

        response = await get_orchestrator().process_query(
            query, context={"type": "semantic_search", **args}
        )

        return response
    except Exception as e:
        logger.error(
            f"Error in handle_search_code: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )
        return {"error": f"Failed to process semantic search: {str(e)}"}


async def handle_generate_code(args: Dict) -> Dict:
    """Handle code generation with input validation and error handling"""
    try:
        description = args.get("description")

        # Input validation
        if not description or not isinstance(description, str):
            logger.warning(
                "Invalid description in handle_generate_code",
                extra={
                    "description_type": (
                        type(description).__name__ if description else None
                    )
                },
            )
            return {"error": "Description is required and must be a non-empty string"}

        # Validate description length
        max_description_length = 5000
        if len(description) > max_description_length:
            logger.warning(
                "Description too long in handle_generate_code",
                extra={
                    "description_length": len(description),
                    "max_length": max_description_length,
                },
            )
            return {
                "error": f"Description too long. Maximum length: {max_description_length} characters"
            }

        logger.debug(
            "Processing code generation", extra={"description_length": len(description)}
        )

        response = await get_orchestrator().process_query(
            f"Создай функцию: {description}",
            context={"type": "code_generation", **args},
        )

        return response
    except Exception as e:
        logger.error(
            f"Error in handle_generate_code: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )
        return {"error": f"Failed to generate code: {str(e)}"}


async def handle_analyze_dependencies(args: Dict) -> Dict:
    """Handle dependency analysis with input validation and error handling"""
    try:
        module = args.get("module_name")
        function = args.get("function_name")

        # Input validation
        if not module or not isinstance(module, str):
            logger.warning(
                "Invalid module_name in handle_analyze_dependencies",
                extra={"module_type": type(module).__name__ if module else None},
            )
            return {"error": "module_name is required and must be a non-empty string"}

        if not function or not isinstance(function, str):
            logger.warning(
                "Invalid function_name in handle_analyze_dependencies",
                extra={"function_type": type(function).__name__ if function else None},
            )
            return {"error": "function_name is required and must be a non-empty string"}

        logger.debug(
            "Processing dependency analysis",
            extra={"module": module, "function": function},
        )

        response = await get_orchestrator().process_query(
            f"Покажи зависимости функции {function} в модуле {module}",
            context={"type": "dependency_analysis", **args},
        )

        return response
    except Exception as e:
        logger.error(
            f"Error in handle_analyze_dependencies: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )
        return {"error": f"Failed to analyze dependencies: {str(e)}"}


async def handle_rentgen_hotspots(args: Dict) -> Dict:
    """Return explainable whole-config hotspots from the local Рентген store."""
    from src.api._rentgen_store import store_or_none

    store = store_or_none()
    if store is None:
        return {"error": "Рентген store not built", "store": False}
    limit = int(args.get("limit") or 10)
    min_fan_in = int(args.get("min_fan_in") or 0)
    domain = args.get("domain")
    return {
        "store": True,
        "hotspots": store.hotspots(limit=limit, domain=domain, min_fan_in=min_fan_in),
    }


async def handle_rentgen_change_plan(args: Dict) -> Dict:
    """Return change impact + CI gate decision for IDE/MCP clients."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.change_plan import (
        assess_ci_gate,
        build_change_plan,
        extract_diff_modules,
    )

    store = store_or_none()
    if store is None:
        return {"error": "Рентген store not built", "store": False}

    changed_modules = list(args.get("changed_modules") or [])
    changed_modules.extend(extract_diff_modules(args.get("diff")))
    if not changed_modules:
        return {"error": "Provide changed_modules or unified diff with .bsl paths"}

    plan = build_change_plan(
        store,
        changed_modules,
        max_depth=int(args.get("max_depth") or 5),
        max_edges=int(args.get("max_edges") or 600),
    )
    gate = assess_ci_gate(
        plan,
        risk_threshold=int(args.get("risk_threshold") or 70),
        impact_threshold=int(args.get("impact_threshold") or 300),
    )
    return {"store": True, "gate": gate, "plan": plan}


async def handle_rentgen_release_readiness(args: Dict) -> Dict:
    """Return enterprise release-readiness report for IDE/MCP clients."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.release_readiness import build_release_readiness

    store = store_or_none()
    if store is None:
        return {"error": "Rentgen store not built", "store": False}

    try:
        return {
            "store": True,
            **build_release_readiness(
                store,
                changed_modules=list(args.get("changed_modules") or []),
                diff=args.get("diff"),
                release_name=args.get("release_name"),
                snapshot_id=args.get("snapshot_id"),
                include_security=bool(args.get("include_security") or False),
                include_forms=bool(args.get("include_forms", True)),
                max_depth=int(args.get("max_depth") or 5),
                max_edges=int(args.get("max_edges") or 600),
                risk_threshold=int(args.get("risk_threshold") or 70),
                impact_threshold=int(args.get("impact_threshold") or 300),
            ),
        }
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_rentgen_architecture_review(args: Dict) -> Dict:
    """Return architecture boundary review for IDE/MCP clients."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.architecture_review import build_architecture_review

    store = store_or_none()
    if store is None:
        return {"error": "Rentgen store not built", "store": False}

    return {
        "store": True,
        **build_architecture_review(
            store,
            changed_modules=list(args.get("changed_modules") or []),
            diff=args.get("diff"),
            limit=int(args.get("limit") or 5000),
            min_weight=int(args.get("min_weight") or 1),
            dense_threshold=int(args.get("dense_threshold") or 250),
            include_cycles=bool(args.get("include_cycles", True)),
            finding_limit=int(args.get("finding_limit") or 200),
        ),
    }


def _mcp_bool(args: Dict, key: str, default: bool = True) -> bool:
    value = args.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _mcp_metadata_preview(obj: dict[str, Any] | None) -> dict[str, Any] | None:
    if obj is None:
        return None
    return {
        "type": obj.get("type"),
        "name": obj.get("name"),
        "synonym": obj.get("synonym"),
        "ref": obj.get("ref"),
        "path": obj.get("path"),
        "counts": obj.get("counts"),
        "modules": (obj.get("modules") or [])[:8],
        "forms": (obj.get("forms") or [])[:8],
        "rights": obj.get("rights"),
    }


async def handle_rentgen_generate_grounded(args: Dict) -> Dict:
    """Generate deterministic graph-grounded BSL for IDE/MCP clients."""
    from src.api._rentgen_store import store_or_none
    from src.modules.copilot.services.copilot_service import CopilotService
    from src.services.bsl_diagnostics import analyze_bsl
    from src.services.its_rag.search import ITSSearchService
    from src.services.rentgen.change_plan import build_change_plan, build_requirement_impact
    from src.services.rentgen.grounded_codegen import generate_grounded_bsl
    from src.services.rentgen.metadata_graph import get_metadata_object

    prompt = args.get("prompt") or args.get("description")
    if not prompt or not isinstance(prompt, str):
        return {"error": "prompt is required and must be a non-empty string"}
    if len(prompt) > 5000:
        return {"error": "prompt is too long. Maximum length: 5000 characters"}

    code_type = str(args.get("type") or "function").lower()
    if code_type not in {"function", "procedure", "test"}:
        return {"error": f"Invalid type: {code_type}"}

    caveats: list[str] = []
    metadata_obj = None
    metadata_identifier = args.get("metadata_identifier")
    if metadata_identifier:
        metadata_obj = get_metadata_object(str(metadata_identifier))
        if metadata_obj is None:
            caveats.append(f"Metadata object not found: {metadata_identifier}")

    modules: list[str] = []
    module_path = args.get("module_path")
    if module_path and isinstance(module_path, str):
        modules.append(module_path)
    if metadata_obj:
        modules.extend(module["path"] for module in metadata_obj.get("modules", []))
    modules = list(dict.fromkeys(modules))[:5]

    store = store_or_none()
    change_plan = None
    requirement_impact = None
    if store is not None and modules:
        change_plan = build_change_plan(store, modules, max_depth=3, max_edges=200)
    elif store is not None and _mcp_bool(args, "include_requirement_impact", True):
        requirement_impact = build_requirement_impact(
            store,
            prompt,
            limit=4,
            max_depth=3,
            max_edges=200,
        )
        change_plan = requirement_impact["change_plan"]
    elif store is not None:
        caveats.append("No module path, metadata object or requirement-impact lookup was provided for Rentgen grounding.")
    else:
        caveats.append("Rentgen store is unavailable; generation has no blast-radius grounding.")

    its_context: list[dict[str, Any]] = []
    if _mcp_bool(args, "include_its_context", True):
        hits = await ITSSearchService(mode="offline").query(prompt, limit=3)
        its_context = [
            {
                "section_title": hit.section_title,
                "source_file": hit.source_file,
                "score": hit.score,
                "text": hit.text[:600],
            }
            for hit in hits
        ]

    copilot_service = CopilotService()
    generation = generate_grounded_bsl(
        prompt=prompt,
        code_type=code_type,
        module_path=module_path or (modules[0] if modules else None),
        metadata_obj=metadata_obj,
        change_plan=change_plan,
        requirement_impact=requirement_impact,
        its_context=its_context,
        model_available=copilot_service.model_available,
    )
    diagnostics = analyze_bsl(
        generation["code"],
        module_path=module_path or (modules[0] if modules else None),
    )
    caveats.append(
        "Generation uses a deterministic local graph-grounded provider; diagnostics and grounding are offline layers."
    )

    return {
        "code": generation["code"],
        "plan": generation["plan"],
        "risk_controls": generation["risk_controls"],
        "test_actions": generation["test_actions"],
        "artifact": generation["artifact"],
        "grounding": {
            "metadata_object": _mcp_metadata_preview(metadata_obj),
            "modules": modules,
            "change_plan": change_plan,
            "requirement_impact": requirement_impact,
            "its_context": its_context,
            "provider": generation["provider"],
        },
        "diagnostics": diagnostics,
        "caveats": caveats,
    }


async def handle_rentgen_requirement_impact(args: Dict) -> Dict:
    """Map a business requirement to likely modules and change risk."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.change_plan import build_requirement_impact

    text = args.get("text")
    if not text or not isinstance(text, str):
        return {"error": "text is required and must be a non-empty string"}

    store = store_or_none()
    if store is None:
        return {"error": "Рентген store not built", "store": False}

    return {
        "store": True,
        **build_requirement_impact(
            store,
            text,
            limit=int(args.get("limit") or 6),
            max_depth=int(args.get("max_depth") or 3),
            max_edges=int(args.get("max_edges") or 200),
        ),
    }


async def handle_rentgen_requirement_trace(args: Dict) -> Dict:
    """Build and optionally persist requirement traceability links."""
    from src.api._rentgen_store import store_or_none
    from src.services.its_rag.search import ITSSearchService
    from src.services.rentgen.change_plan import build_requirement_impact
    from src.services.rentgen.requirements_traceability import build_trace_record, save_trace

    text = args.get("text") or args.get("requirement")
    if not text or not isinstance(text, str):
        return {"error": "text is required and must be a non-empty string"}

    store = store_or_none()
    if store is None:
        return {"error": "Рентген store not built", "store": False}

    impact = build_requirement_impact(
        store,
        text,
        limit=int(args.get("limit") or 6),
        max_depth=int(args.get("max_depth") or 3),
        max_edges=int(args.get("max_edges") or 200),
    )

    its_context: list[dict[str, Any]] = []
    if _mcp_bool(args, "include_its_context", True):
        hits = await ITSSearchService(mode="offline").query(text, limit=3)
        its_context = [
            {
                "section_title": hit.section_title,
                "source_file": hit.source_file,
                "score": hit.score,
                "text": hit.text[:600],
            }
            for hit in hits
        ]

    criteria_raw = args.get("acceptance_criteria") or []
    criteria = criteria_raw if isinstance(criteria_raw, list) else [str(criteria_raw)]
    record = build_trace_record(
        requirement=impact["requirement"],
        candidate_modules=impact["candidate_modules"],
        change_plan=impact["change_plan"],
        its_context=its_context,
        acceptance_criteria=[str(item) for item in criteria],
        title=args.get("title"),
        caveats=impact["caveats"],
    )
    if _mcp_bool(args, "save", True):
        record = save_trace(record)
    return {"store": True, **record}


async def handle_rentgen_metadata_search(args: Dict) -> Dict:
    """Search local EDT metadata graph."""
    from src.services.rentgen.metadata_graph import metadata_summary, search_metadata

    limit = int(args.get("limit") or 20)
    return {
        "summary": metadata_summary(),
        "items": search_metadata(
            args.get("query"),
            metadata_type=args.get("type"),
            limit=max(1, min(limit, 100)),
        ),
    }


async def handle_rentgen_metadata_object_impact(args: Dict) -> Dict:
    """Return metadata object details and Rentgen module impact."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.metadata_graph import get_metadata_object

    identifier = args.get("identifier")
    if not identifier or not isinstance(identifier, str):
        return {"error": "identifier is required and must be a non-empty string"}

    obj = get_metadata_object(identifier)
    if obj is None:
        return {"error": f"Metadata object not found: {identifier}"}

    modules = [module["path"] for module in obj.get("modules", [])]
    store = store_or_none()
    impacts = []
    total_edges = 0
    if store is not None:
        for module_path in modules:
            impact = store.module_impact(
                module_path,
                max_depth=int(args.get("max_depth") or 3),
                max_edges=int(args.get("max_edges") or 150),
            )
            total_edges += int(impact.get("total", 0))
            impacts.append(impact)

    return {
        "object": {
            "type": obj["type"],
            "name": obj["name"],
            "ref": obj["ref"],
            "path": obj["path"],
            "counts": obj["counts"],
        },
        "modules": modules,
        "rentgen_available": store is not None,
        "total_impact_edges": total_edges,
        "impacts": impacts,
    }


async def handle_rentgen_metadata_security_review(args: Dict) -> Dict:
    """Return static 1C roles/Rights.xml security review."""
    from src.services.rentgen.metadata_insights import security_review

    return security_review(limit=int(args.get("limit") or 100))


async def handle_rentgen_security_posture(args: Dict) -> Dict:
    """Return full static 1C security posture for IDE/MCP clients."""
    from src.services.rentgen.security_posture import build_security_posture

    return build_security_posture(
        limit=max(1, min(int(args.get("limit") or 100), 1000)),
        module_limit=max(1, min(int(args.get("module_limit") or 2500), 30000)),
        snapshot_id=args.get("snapshot_id"),
    )


async def handle_rentgen_metadata_data_governance(args: Dict) -> Dict:
    """Return static data governance review for metadata objects."""
    from src.services.rentgen.metadata_data_governance import build_data_governance

    return build_data_governance(limit=int(args.get("limit") or 120))


async def handle_rentgen_offline_readiness(args: Dict) -> Dict:
    """Return a closed-contour readiness report for IDE/MCP clients."""
    from src.services.rentgen.offline_readiness import build_offline_readiness

    return build_offline_readiness(strict=_mcp_bool(args, "strict", False))


async def handle_rentgen_its_search(args: Dict) -> Dict:
    """Return offline-first ITS documentation search results."""
    from src.services.its_rag.search import ITSSearchService

    question = args.get("question") or args.get("query")
    if not question or not isinstance(question, str):
        return {"error": "question is required and must be a non-empty string"}

    limit = max(1, min(int(args.get("limit") or 5), 20))
    results = await ITSSearchService(mode="offline").query(
        question,
        limit=limit,
        section_filter=args.get("section_filter"),
    )
    return {
        "query": question,
        "total": len(results),
        "results": [
            {
                "text": item.text[:500],
                "section_title": item.section_title,
                "source_file": item.source_file,
                "its_article_id": item.its_article_id,
                "score": item.score,
            }
            for item in results
        ],
        "mode": "offline",
    }


async def handle_rentgen_its_context(args: Dict) -> Dict:
    """Return formatted ITS context for IDE/LLM clients."""
    from src.services.its_rag.search import ITSSearchService

    question = args.get("question") or args.get("query")
    if not question or not isinstance(question, str):
        return {"error": "question is required and must be a non-empty string"}

    limit = max(1, min(int(args.get("limit") or 3), 10))
    max_chars = max(500, min(int(args.get("max_chars") or 6000), 20000))
    context = await ITSSearchService(mode="offline").get_context_for_llm(
        question,
        max_chunks=limit,
        max_chars=max_chars,
    )
    return {
        "query": question,
        "context": context,
        "chars": len(context),
        "mode": "offline",
    }


def _tj_hotspot_dict(item) -> dict[str, Any]:
    return {
        "module": item.module,
        "line": item.line,
        "code_fragment": item.code_fragment,
        "sdbl": item.sdbl,
        "total_calls": item.total_calls,
        "total_duration_ms": item.total_duration_ms,
        "max_duration_us": item.max_duration_us,
        "avg_rows": item.avg_rows,
        "is_in_loop": item.is_in_loop,
    }


def _tj_report_dict(report) -> dict[str, Any]:
    return {
        "total_events": report.total_events,
        "total_duration_ms": report.total_duration_ms,
        "hotspots": [_tj_hotspot_dict(item) for item in report.hotspots],
        "n_plus_one": [_tj_hotspot_dict(item) for item in report.n_plus_one],
        "lock_waits_count": len(report.lock_waits),
        "deadlocks_count": len(report.deadlocks),
    }


async def handle_rentgen_performer_analyze(args: Dict) -> Dict:
    """Analyze Technology Journal logs for IDE/MCP clients."""
    from src.services.tj_parser.analyzer import TJPerformanceAnalyzer

    log_path = args.get("log_path")
    if not log_path or not isinstance(log_path, str):
        return {"error": "log_path is required and must be a non-empty string"}

    try:
        analyzer = TJPerformanceAnalyzer(
            min_duration_ms=float(args.get("min_duration_ms") or 100.0),
        )
        report = analyzer.analyze(log_path, top_n=int(args.get("top_n") or 20))
        return _tj_report_dict(report)
    except (OSError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_rentgen_performer_impact(args: Dict) -> Dict:
    """Analyze TJ logs and map hotspots to Rentgen blast radius."""
    from src.api._rentgen_store import store_or_none
    from src.services.tj_parser.analyzer import TJPerformanceAnalyzer

    log_path = args.get("log_path")
    if not log_path or not isinstance(log_path, str):
        return {"error": "log_path is required and must be a non-empty string"}

    store = store_or_none()
    if store is None:
        return {"error": "Rentgen store not built", "store": False}

    try:
        analyzer = TJPerformanceAnalyzer(
            min_duration_ms=float(args.get("min_duration_ms") or 100.0),
        )
        report = analyzer.analyze(log_path, top_n=int(args.get("top_n") or 20))
    except (OSError, ValueError) as exc:
        return {"error": str(exc)}

    max_depth = int(args.get("max_depth") or 5)
    max_edges = int(args.get("max_edges") or 300)
    impacts = []
    for hotspot in report.hotspots:
        impact = store.module_impact(
            hotspot.module,
            max_depth=max_depth,
            max_edges=max_edges,
        )
        impacts.append(
            {
                "hotspot": _tj_hotspot_dict(hotspot),
                "canonical": impact["canonical"],
                "graph_modules": impact["graph_modules"],
                "impact_total": impact["total"],
                "impacted_modules": impact["impacted_modules"][:30],
            }
        )

    return {
        **_tj_report_dict(report),
        "store": True,
        "hotspot_impacts": impacts,
    }


async def handle_rentgen_form_review(args: Dict) -> Dict:
    """Return static form XML and form-module review."""
    from src.services.rentgen.metadata_insights import review_forms

    identifier = args.get("identifier")
    if not identifier or not isinstance(identifier, str):
        return {"error": "identifier is required and must be a non-empty string"}
    try:
        return review_forms(identifier, form_name=args.get("form_name"))
    except ValueError as exc:
        return {"error": str(exc)}


async def handle_rentgen_form_blueprint(args: Dict) -> Dict:
    """Return a deterministic form blueprint and generated draft assets."""
    from src.services.rentgen.form_designer import build_form_blueprint

    identifier = args.get("identifier")
    if not identifier or not isinstance(identifier, str):
        return {"error": "identifier is required and must be a non-empty string"}
    try:
        return build_form_blueprint(
            identifier,
            form_kind=args.get("form_kind") or "auto",
            intent=args.get("intent"),
            include_review=_mcp_bool(args, "include_review", True),
        )
    except ValueError as exc:
        return {"error": str(exc)}


async def handle_bsl_diagnostics(args: Dict) -> Dict:
    """Return deterministic offline BSL diagnostics for code."""
    from src.services.bsl_diagnostics import analyze_bsl

    code = args.get("code")
    if not code or not isinstance(code, str):
        return {"error": "code is required and must be a non-empty string"}
    return analyze_bsl(code, module_path=args.get("module_path"))


async def handle_bsl_standards_review(args: Dict) -> Dict:
    """Return catalog-aware BSL standards review for code."""
    from src.services.rentgen.standards_review import review_bsl_standards, save_standards_review

    code = args.get("code")
    if not code or not isinstance(code, str):
        return {"error": "code is required and must be a non-empty string"}
    report = review_bsl_standards(
        code,
        module_path=args.get("module_path"),
        max_nesting_threshold=int(args.get("max_nesting_threshold") or 5),
    )
    if _mcp_bool(args, "save", False):
        report["stored"] = save_standards_review(report)
    return report


async def handle_rentgen_test_match(args: Dict) -> Dict:
    """Return local YAxUnit/Vanessa test matches for a changed module."""
    from src.services.rentgen.test_inventory import inventory_summary, match_tests_for_module

    module_path = args.get("module_path")
    if not module_path or not isinstance(module_path, str):
        return {"error": "module_path is required and must be a non-empty string"}
    return {
        "inventory": inventory_summary(),
        "matches": match_tests_for_module(
            module_path,
            object_name=args.get("object_name"),
            limit=int(args.get("limit") or 10),
        ),
    }


async def handle_rentgen_test_coverage_matrix(args: Dict) -> Dict:
    """Return exact/planned/gap test coverage matrix for changed modules."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.change_plan import extract_diff_modules
    from src.services.rentgen.test_coverage_matrix import build_test_coverage_matrix

    changed_modules = list(args.get("changed_modules") or [])
    diff = args.get("diff")
    modules = list(dict.fromkeys(changed_modules + extract_diff_modules(diff)))
    if not modules:
        return {"error": "changed_modules or diff with .bsl paths is required"}

    store = store_or_none()
    if store is None:
        return {"error": "Rentgen store not built", "store": False}

    return {
        "store": True,
        **build_test_coverage_matrix(
            store,
            changed_modules=modules,
            max_depth=int(args.get("max_depth") or 5),
            max_edges=int(args.get("max_edges") or 600),
            hotspot_limit=int(args.get("hotspot_limit") or 10),
            match_limit=int(args.get("match_limit") or 10),
        ),
    }


async def handle_rentgen_incident_report(args: Dict) -> Dict:
    """Return an operations incident-to-code report for IDE/MCP clients."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.incident_response import build_incident_report

    symptoms_raw = args.get("symptoms") or []
    changed_modules_raw = args.get("changed_modules") or []
    symptoms = symptoms_raw if isinstance(symptoms_raw, list) else [str(symptoms_raw)]
    changed_modules = (
        changed_modules_raw
        if isinstance(changed_modules_raw, list)
        else [str(changed_modules_raw)]
    )

    return build_incident_report(
        store_or_none(),
        incident_title=str(args.get("incident_title") or "Production incident"),
        description=args.get("description"),
        symptoms=[str(item) for item in symptoms],
        log_path=args.get("log_path"),
        changed_modules=[str(item) for item in changed_modules],
        min_duration_ms=float(args.get("min_duration_ms") or 100.0),
        top_n=max(1, min(int(args.get("top_n") or 20), 50)),
        module_limit=max(1, min(int(args.get("module_limit") or 12), 50)),
        max_depth=max(1, min(int(args.get("max_depth") or 5), 12)),
        max_edges=max(1, min(int(args.get("max_edges") or 300), 5000)),
        include_team=_mcp_bool(args, "include_team", True),
    )


async def handle_rentgen_team_governance(args: Dict) -> Dict:
    """Return team ownership, risk SLA and governance trend board."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.team_governance import build_team_governance

    return build_team_governance(
        store_or_none(),
        limit=max(1, min(int(args.get("limit") or 40), 200)),
        save_snapshot=_mcp_bool(args, "save_snapshot", False),
    )


async def handle_artifact_create(args: Dict) -> Dict:
    """Create an internal ALM artifact for agent/IDE workflows."""
    from src.services.rentgen.artifact_graph import create_artifact

    if not args.get("type") or not args.get("title"):
        return {"error": "type and title are required"}
    try:
        return create_artifact(dict(args))
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_artifact_link(args: Dict) -> Dict:
    """Create an internal ALM traceability link."""
    from src.services.rentgen.artifact_graph import link_artifacts

    if not args.get("source_id") or not args.get("target_id") or not args.get("type"):
        return {"error": "source_id, target_id and type are required"}
    try:
        return link_artifacts(
            source_id=str(args.get("source_id")),
            target_id=str(args.get("target_id")),
            link_type=str(args.get("type")),
            rationale=str(args.get("rationale") or "") or None,
            status=str(args.get("status") or "active"),
            suspect=_mcp_bool(args, "suspect", False),
            attributes=args.get("attributes") if isinstance(args.get("attributes"), dict) else {},
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_artifact_trace(args: Dict) -> Dict:
    """Trace internal ALM links around an artifact."""
    from src.services.rentgen.artifact_graph import trace_artifact

    artifact_id = args.get("artifact_id")
    if not artifact_id or not isinstance(artifact_id, str):
        return {"error": "artifact_id is required and must be a non-empty string"}
    try:
        return trace_artifact(
            artifact_id,
            depth=max(0, min(int(args.get("depth") or 4), 12)),
            direction=str(args.get("direction") or "both"),
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_artifact_matrix(args: Dict) -> Dict:
    """Return internal ALM coverage matrix."""
    from src.services.rentgen.artifact_graph import coverage_matrix

    return coverage_matrix()


async def handle_change_set_create(args: Dict) -> Dict:
    """Create an internal change set."""
    from src.services.rentgen.change_sets import create_change_set

    if not args.get("title"):
        return {"error": "title is required"}
    try:
        return create_change_set(dict(args))
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_change_set_analyze(args: Dict) -> Dict:
    """Attach Rentgen impact analysis to a change set."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.change_sets import analyze_change_set

    change_set_id = args.get("change_set_id")
    if not change_set_id or not isinstance(change_set_id, str):
        return {"error": "change_set_id is required and must be a non-empty string"}
    store = store_or_none()
    if store is None:
        return {"error": "Rentgen store not built", "store": False}
    try:
        return {
            "store": True,
            **analyze_change_set(
                store,
                change_set_id,
                max_depth=max(1, min(int(args.get("max_depth") or 5), 12)),
                max_edges=max(1, min(int(args.get("max_edges") or 600), 5000)),
                hotspot_limit=max(1, min(int(args.get("hotspot_limit") or 10), 100)),
            ),
        }
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_change_set_select_tests(args: Dict) -> Dict:
    """Attach risk-driven test coverage matrix to a change set."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.change_sets import select_change_set_tests

    change_set_id = args.get("change_set_id")
    if not change_set_id or not isinstance(change_set_id, str):
        return {"error": "change_set_id is required and must be a non-empty string"}
    store = store_or_none()
    if store is None:
        return {"error": "Rentgen store not built", "store": False}
    try:
        return {
            "store": True,
            **select_change_set_tests(
                store,
                change_set_id,
                max_depth=max(1, min(int(args.get("max_depth") or 5), 12)),
                max_edges=max(1, min(int(args.get("max_edges") or 600), 5000)),
                hotspot_limit=max(1, min(int(args.get("hotspot_limit") or 10), 100)),
                match_limit=max(1, min(int(args.get("match_limit") or 10), 100)),
            ),
        }
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_change_set_release_readiness(args: Dict) -> Dict:
    """Attach release-readiness report to a change set."""
    from src.api._rentgen_store import store_or_none
    from src.services.rentgen.change_sets import attach_release_readiness

    change_set_id = args.get("change_set_id")
    if not change_set_id or not isinstance(change_set_id, str):
        return {"error": "change_set_id is required and must be a non-empty string"}
    store = store_or_none()
    if store is None:
        return {"error": "Rentgen store not built", "store": False}
    try:
        return {
            "store": True,
            **attach_release_readiness(
                store,
                change_set_id,
                include_security=_mcp_bool(args, "include_security", False),
                include_forms=_mcp_bool(args, "include_forms", True),
            ),
        }
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_change_set_transition(args: Dict) -> Dict:
    """Move a change set through its lifecycle."""
    from src.services.rentgen.change_sets import transition_change_set

    change_set_id = args.get("change_set_id")
    status = args.get("status")
    if not change_set_id or not isinstance(change_set_id, str) or not status:
        return {"error": "change_set_id and status are required"}
    try:
        return transition_change_set(
            change_set_id,
            status=str(status),
            actor=str(args.get("actor") or "system"),
            reason=str(args.get("reason") or ""),
            allow_policy_failure=_mcp_bool(args, "allow_policy_failure", False),
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_baseline_create(args: Dict) -> Dict:
    """Create an immutable baseline snapshot."""
    from src.services.rentgen.baselines import create_baseline

    artifact_ids = args.get("artifact_ids")
    if not args.get("title") or not isinstance(artifact_ids, list):
        return {"error": "title and artifact_ids[] are required"}
    try:
        return create_baseline(
            baseline_id=str(args.get("id") or "") or None,
            title=str(args.get("title")),
            description=str(args.get("description") or "") or None,
            owner=str(args.get("owner") or "") or None,
            artifact_ids=[str(item) for item in artifact_ids],
            release_id=str(args.get("release_id") or "") or None,
            change_set_ids=[str(item) for item in (args.get("change_set_ids") or [])],
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_review_pack_create(args: Dict) -> Dict:
    """Create a review pack."""
    from src.services.rentgen.baselines import create_review_pack

    artifact_ids = args.get("artifact_ids")
    if not args.get("title") or not isinstance(artifact_ids, list):
        return {"error": "title and artifact_ids[] are required"}
    try:
        return create_review_pack(
            review_pack_id=str(args.get("id") or "") or None,
            title=str(args.get("title")),
            description=str(args.get("description") or "") or None,
            owner=str(args.get("owner") or "") or None,
            artifact_ids=[str(item) for item in artifact_ids],
            reviewers=[str(item) for item in (args.get("reviewers") or [])],
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_review_pack_decide(args: Dict) -> Dict:
    """Approve or reject a review pack."""
    from src.services.rentgen.baselines import decide_review_pack

    review_pack_id = args.get("review_pack_id")
    decision = args.get("decision")
    if not review_pack_id or not decision:
        return {"error": "review_pack_id and decision are required"}
    try:
        return decide_review_pack(
            str(review_pack_id),
            actor=str(args.get("actor") or "system"),
            decision=str(decision),
            reason=str(args.get("reason") or ""),
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_policy_evaluate(args: Dict) -> Dict:
    """Evaluate policy rules against a workflow context."""
    from src.services.rentgen.policy_engine import evaluate_policy

    context = args.get("context")
    if not isinstance(context, dict):
        return {"error": "context object is required"}
    try:
        return evaluate_policy(
            context,
            domain=str(args.get("domain") or "") or None,
            scope_id=str(args.get("scope_id") or "") or None,
            persist=_mcp_bool(args, "persist", True),
        )
    except ValueError as exc:
        return {"error": str(exc)}


async def handle_policy_waiver_request(args: Dict) -> Dict:
    """Request a policy waiver."""
    from src.services.rentgen.policy_engine import create_waiver

    if not args.get("rule_id") or not args.get("reason") or not args.get("owner"):
        return {"error": "rule_id, reason and owner are required"}
    try:
        return create_waiver(
            rule_id=str(args.get("rule_id")),
            scope_id=str(args.get("scope_id") or "") or None,
            reason=str(args.get("reason")),
            owner=str(args.get("owner")),
            expires_in_days=int(args.get("expires_in_days") or 30),
            remediation=str(args.get("remediation") or "") or None,
        )
    except ValueError as exc:
        return {"error": str(exc)}


async def handle_policy_waiver_decide(args: Dict) -> Dict:
    """Approve or reject a policy waiver."""
    from src.services.rentgen.policy_engine import decide_waiver

    if not args.get("waiver_id") or not args.get("status"):
        return {"error": "waiver_id and status are required"}
    try:
        return decide_waiver(
            str(args.get("waiver_id")),
            status=str(args.get("status")),
            actor=str(args.get("actor") or "system"),
            decision_reason=str(args.get("decision_reason") or "") or None,
        )
    except PermissionError as exc:
        # Separation-of-duties violation (e.g. waiver owner self-approving).
        # Surface as a structured, blocked result instead of letting the
        # exception escape as an opaque 500 — the decision is denied, never
        # "approved".
        return {"error": str(exc), "status": "blocked"}
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_test_run_record(args: Dict) -> Dict:
    """Record test execution evidence."""
    from src.services.rentgen.test_evidence import record_test_run

    results = args.get("results")
    if not args.get("title") or not args.get("framework") or not isinstance(results, list):
        return {"error": "title, framework and results[] are required"}
    try:
        return record_test_run(
            run_id=str(args.get("id") or "") or None,
            title=str(args.get("title")),
            framework=str(args.get("framework")),
            results=[item for item in results if isinstance(item, dict)],
            change_set_id=str(args.get("change_set_id") or "") or None,
            command=str(args.get("command") or "") or None,
            evidence=[item for item in (args.get("evidence") or []) if isinstance(item, dict)],
            dry_run=_mcp_bool(args, "dry_run", False),
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_test_run_import_junit(args: Dict) -> Dict:
    """Import JUnit XML test evidence."""
    import xml.etree.ElementTree as ET

    from src.services.rentgen.test_evidence import import_junit_xml

    if not args.get("xml_text"):
        return {"error": "xml_text is required"}
    try:
        return import_junit_xml(
            xml_text=str(args.get("xml_text")),
            title=str(args.get("title") or "JUnit import"),
            framework=str(args.get("framework") or "JUnit"),
            change_set_id=str(args.get("change_set_id") or "") or None,
        )
    except (KeyError, ValueError, ET.ParseError) as exc:
        return {"error": str(exc)}


async def handle_test_run_list(args: Dict) -> Dict:
    """List stored test execution evidence."""
    from src.services.rentgen.test_evidence import list_test_runs

    return list_test_runs(
        status=str(args.get("status") or "") or None,
        change_set_id=str(args.get("change_set_id") or "") or None,
        limit=max(1, min(int(args.get("limit") or 100), 500)),
    )


def _mcp_string_list(args: Dict, key: str) -> list[str]:
    raw = args.get(key)
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item or "").strip()]


def _mcp_runner_kwargs(args: Dict) -> Dict:
    return {
        "test_files": _mcp_string_list(args, "test_files"),
        "modules": _mcp_string_list(args, "modules"),
        "selectors": _mcp_string_list(args, "selectors"),
        "manifest_path": str(args.get("manifest_path") or "") or None,
        "output_dir": str(args.get("output_dir") or "") or None,
        "report_path": str(args.get("report_path") or "") or None,
        "cwd": str(args.get("cwd") or "") or None,
        "env": args.get("env") if isinstance(args.get("env"), dict) else {},
        "timeout": max(1, min(int(args.get("timeout") or 1800), 86400)),
        "extra_args": _mcp_string_list(args, "extra_args"),
        "change_set_id": str(args.get("change_set_id") or "") or None,
    }


async def handle_test_runner_plan(args: Dict) -> Dict:
    """Build a local test runner plan without executing it."""
    from src.services.rentgen.test_runners import build_runner_plan

    adapter = args.get("adapter")
    if not adapter:
        return {"error": "adapter is required"}
    try:
        return build_runner_plan(str(adapter), dry_run=True, **_mcp_runner_kwargs(args))
    except ValueError as exc:
        return {"error": str(exc)}


async def handle_test_runner_run(args: Dict) -> Dict:
    """Dry-run or execute a local test runner adapter."""
    from src.services.rentgen.test_runners import run_test_adapter

    adapter = args.get("adapter")
    if not adapter:
        return {"error": "adapter is required"}
    try:
        return run_test_adapter(
            str(adapter),
            execute=_mcp_bool(args, "execute", False),
            allow_external=_mcp_bool(args, "allow_external", False),
            import_results=_mcp_bool(args, "import_results", True),
            **_mcp_runner_kwargs(args),
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_test_result_import_file(args: Dict) -> Dict:
    """Import local test result files into evidence."""
    from src.services.rentgen.test_runners import import_result_file

    if not args.get("result_path"):
        return {"error": "result_path is required"}
    try:
        return import_result_file(
            str(args.get("result_path")),
            result_format=str(args.get("result_format") or "auto"),
            title=str(args.get("title") or "") or None,
            framework=str(args.get("framework") or "") or None,
            change_set_id=str(args.get("change_set_id") or "") or None,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_metadata_canonical_import(args: Dict) -> Dict:
    """Import EDT metadata into the canonical metadata store."""
    from src.services.rentgen.canonical_metadata import import_metadata_snapshot

    try:
        return import_metadata_snapshot(
            config_path=str(args.get("config_path") or "") or None,
            name=str(args.get("name") or "") or None,
            source=str(args.get("source") or "edt"),
            refresh=_mcp_bool(args, "refresh", True),
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_metadata_canonical_objects(args: Dict) -> Dict:
    """List canonical metadata objects."""
    from src.services.rentgen.canonical_metadata import list_metadata_objects

    return list_metadata_objects(
        metadata_type=str(args.get("type") or "") or None,
        group=str(args.get("group") or "") or None,
        query=str(args.get("query") or "") or None,
        limit=max(1, min(int(args.get("limit") or 100), 1000)),
    )


async def handle_metadata_canonical_drift(args: Dict) -> Dict:
    """Compare canonical metadata snapshots."""
    from src.services.rentgen.canonical_metadata import diff_metadata

    if not args.get("before_id"):
        return {"error": "before_id is required"}
    try:
        return diff_metadata(
            before_id=str(args.get("before_id")),
            after_id=str(args.get("after_id") or "") or None,
            limit=max(1, min(int(args.get("limit") or 200), 1000)),
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_metadata_rights_diff(args: Dict) -> Dict:
    """Compare role-rights changes between canonical metadata snapshots."""
    from src.services.rentgen.canonical_metadata import diff_rights

    if not args.get("before_id"):
        return {"error": "before_id is required"}
    try:
        return diff_rights(
            before_id=str(args.get("before_id")),
            after_id=str(args.get("after_id") or "") or None,
            limit=max(1, min(int(args.get("limit") or 200), 1000)),
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_agentic_plan_create(args: Dict) -> Dict:
    """Create an agentic workflow plan."""
    from src.services.rentgen.agentic_workflows import create_agentic_plan

    if not args.get("title"):
        return {"error": "title is required"}
    try:
        return create_agentic_plan(dict(args))
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_agentic_plan_review(args: Dict) -> Dict:
    """Review an agentic workflow plan."""
    from src.services.rentgen.agentic_workflows import review_agentic_plan

    if not args.get("plan_id"):
        return {"error": "plan_id is required"}
    try:
        return review_agentic_plan(str(args.get("plan_id")))
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_agentic_action_gate(args: Dict) -> Dict:
    """Gate an agentic action before execution."""
    from src.services.rentgen.agentic_workflows import action_gate

    if not args.get("action_type"):
        return {"error": "action_type is required"}
    try:
        return action_gate(
            action_type=str(args.get("action_type")),
            plan_id=str(args.get("plan_id") or "") or None,
            change_set_id=str(args.get("change_set_id") or "") or None,
            risk=str(args.get("risk") or "low"),
            confirm=_mcp_bool(args, "confirm", False),
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_productization_readiness(args: Dict) -> Dict:
    """Return productization readiness for release/package review."""
    from src.services.productization_readiness import (
        productization_markdown_report,
        productization_readiness,
    )

    if str(args.get("format") or "json").lower() == "markdown":
        return productization_markdown_report()
    return productization_readiness()


async def handle_offline_bundle_manifest(args: Dict) -> Dict:
    """Build an offline bundle manifest."""
    from pathlib import Path

    from src.services.offline_bundle import build_offline_bundle_manifest

    raw_paths = args.get("include_paths")
    include_paths = [str(item) for item in raw_paths] if isinstance(raw_paths, list) else []
    try:
        return build_offline_bundle_manifest(
            profile=str(args.get("profile") or "pilot"),
            include_paths=include_paths,
            include_defaults=_mcp_bool(args, "include_defaults", True),
            output_path=Path(str(args.get("output_path"))) if args.get("output_path") else None,
            sign=_mcp_bool(args, "sign", False),
            write=_mcp_bool(args, "write", True),
        )
    except (OSError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_offline_bundle_verify(args: Dict) -> Dict:
    """Verify an offline bundle manifest."""
    from pathlib import Path

    from src.services.offline_bundle import verify_offline_bundle_manifest

    try:
        return verify_offline_bundle_manifest(
            manifest_path=Path(str(args.get("manifest_path"))) if args.get("manifest_path") else None,
        )
    except (OSError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_offline_bundle_archive(args: Dict) -> Dict:
    """Build an offline ZIP bundle."""
    from pathlib import Path

    from src.services.offline_bundle import build_offline_bundle_archive

    raw_paths = args.get("include_paths")
    include_paths = [str(item) for item in raw_paths] if isinstance(raw_paths, list) else []
    try:
        return build_offline_bundle_archive(
            profile=str(args.get("profile") or "pilot"),
            include_paths=include_paths,
            include_defaults=_mcp_bool(args, "include_defaults", True),
            output_path=Path(str(args.get("output_path"))) if args.get("output_path") else None,
            sign=_mcp_bool(args, "sign", False),
        )
    except (OSError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_offline_bundle_archive_verify(args: Dict) -> Dict:
    """Verify an offline ZIP bundle."""
    from pathlib import Path

    from src.services.offline_bundle import verify_offline_bundle_archive

    if not args.get("archive_path"):
        return {"error": "archive_path is required"}
    try:
        return verify_offline_bundle_archive(archive_path=Path(str(args.get("archive_path"))))
    except (OSError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_sbom_generate(args: Dict) -> Dict:
    """Generate a local SBOM/dependency inventory."""
    from pathlib import Path

    from src.services.sbom_inventory import generate_sbom, sbom_markdown_report

    raw_paths = args.get("include_paths")
    include_paths = [str(item) for item in raw_paths] if isinstance(raw_paths, list) else []
    try:
        if str(args.get("format") or "json").lower() == "markdown":
            return sbom_markdown_report(
                include_paths=include_paths,
                include_defaults=_mcp_bool(args, "include_defaults", True),
            )
        return generate_sbom(
            include_paths=include_paths,
            include_defaults=_mcp_bool(args, "include_defaults", True),
            output_path=Path(str(args.get("output_path"))) if args.get("output_path") else None,
            write=_mcp_bool(args, "write", True),
        )
    except (OSError, ValueError) as exc:
        return {"error": str(exc)}


async def handle_edt_mcp_toolsets(args: Dict) -> Dict:
    """Return curated EDT-MCP toolsets and integration notes."""
    from src.services.edt_mcp_bridge import list_edt_mcp_toolsets

    return list_edt_mcp_toolsets()


async def handle_edt_mcp_plan(args: Dict) -> Dict:
    """Plan EDT-MCP toolsets/tools for a user task."""
    from src.services.edt_mcp_bridge import plan_edt_mcp_workflow

    return plan_edt_mcp_workflow(
        str(args.get("task") or ""),
        intent=str(args.get("intent") or "") if args.get("intent") is not None else None,
    )


async def handle_edt_mcp_connection_config(args: Dict) -> Dict:
    """Return MCP client config snippets for a local EDT-MCP endpoint."""
    from src.services.edt_mcp_bridge import DEFAULT_BASE_URL, build_connection_config

    return build_connection_config(str(args.get("base_url") or DEFAULT_BASE_URL))


async def handle_edt_mcp_status(args: Dict) -> Dict:
    """Probe a live EDT-MCP endpoint."""
    from src.services.edt_mcp_bridge import DEFAULT_BASE_URL, check_edt_mcp_status

    return await check_edt_mcp_status(
        str(args.get("base_url") or DEFAULT_BASE_URL),
        auth_token=str(args.get("auth_token") or "") or None,
        timeout_s=float(args.get("timeout_s") or 5.0),
    )


async def handle_edt_mcp_live_tools(args: Dict) -> Dict:
    """Return live EDT-MCP tools/list with safety metadata."""
    from src.services.edt_mcp_bridge import DEFAULT_BASE_URL, list_live_edt_mcp_tools

    return await list_live_edt_mcp_tools(
        str(args.get("base_url") or DEFAULT_BASE_URL),
        auth_token=str(args.get("auth_token") or "") or None,
        timeout_s=float(args.get("timeout_s") or 10.0),
    )


async def handle_edt_mcp_call(args: Dict) -> Dict:
    """Call a live EDT-MCP tool through the 1cAI safety gate."""
    from src.services.edt_mcp_bridge import DEFAULT_BASE_URL, call_live_edt_mcp_tool

    tool_args = args.get("arguments") if isinstance(args.get("arguments"), dict) else {}
    return await call_live_edt_mcp_tool(
        str(args.get("tool_name") or ""),
        tool_args,
        base_url=str(args.get("base_url") or DEFAULT_BASE_URL),
        auth_token=str(args.get("auth_token") or "") or None,
        confirm=_mcp_bool(args, "confirm", False),
        actor=str(args.get("actor") or "") or None,
        approval_reason=str(args.get("approval_reason") or "") or None,
        approval_ticket=str(args.get("approval_ticket") or "") or None,
        approval_id=str(args.get("approval_id") or "") or None,
        timeout_s=float(args.get("timeout_s") or 30.0),
    )


async def call_external_mcp(
    base_url: str, tool_name: str, args: Dict, auth_token: Optional[str] = None
) -> Dict:
    """Invoke an external MCP-compatible server with input validation and error handling."""
    # Input validation
    if not base_url or not isinstance(base_url, str):
        logger.warning(
            "Invalid base_url in call_external_mcp",
            extra={"base_url_type": type(base_url).__name__ if base_url else None},
        )
        return {"error": "base_url is required and must be a non-empty string"}

    if not tool_name or not isinstance(tool_name, str):
        logger.warning(
            "Invalid tool_name in call_external_mcp",
            extra={"tool_name_type": type(tool_name).__name__ if tool_name else None},
        )
        return {"error": "tool_name is required and must be a non-empty string"}

    try:
        endpoint = base_url.rstrip("/") + "/mcp/tools/call"
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        logger.debug(
            "Calling external MCP", extra={"base_url": base_url, "tool_name": tool_name}
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                json={"name": tool_name, "arguments": args},
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("result", payload)
    except httpx.TimeoutException as e:
        logger.error(
            f"Timeout calling external MCP: {e}",
            extra={
                "base_url": base_url,
                "tool_name": tool_name,
                "error_type": "TimeoutException",
            },
            exc_info=True,
        )
        return {"error": f"Timeout calling external MCP: {str(e)}"}
    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error calling external MCP: {e}",
            extra={
                "base_url": base_url,
                "tool_name": tool_name,
                "status_code": e.response.status_code,
                "error_type": "HTTPStatusError",
            },
            exc_info=True,
        )
        return {"error": f"HTTP error calling external MCP: {e.response.status_code}"}
    except httpx.RequestError as e:
        logger.error(
            f"Request error calling external MCP: {e}",
            extra={
                "base_url": base_url,
                "tool_name": tool_name,
                "error_type": "RequestError",
            },
            exc_info=True,
        )
        return {"error": f"Request error calling external MCP: {str(e)}"}
    except Exception as e:
        logger.error(
            f"Unexpected error calling external MCP: {e}",
            extra={
                "base_url": base_url,
                "tool_name": tool_name,
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return {"error": f"Unexpected error calling external MCP: {str(e)}"}


async def handle_bsl_platform_context(args: Dict) -> Dict:
    """Proxy to external MCP server providing platform context."""
    base_url = settings.mcp_bsl_context_base_url
    if not base_url:
        return {
            "error": "MCP_BSL_CONTEXT_BASE_URL is not configured. "
            "Install and run alkoleft/mcp-bsl-platform-context, then set the environment variable.",
            "configured": False,
        }

    try:
        return await call_external_mcp(
            base_url=base_url,
            tool_name=settings.mcp_bsl_context_tool_name,
            args=args,
            auth_token=settings.mcp_bsl_context_auth_token,
        )
    except httpx.HTTPError as exc:
        logger.error(
            f"External MCP (platform context) call failed: {exc}",
            extra={
                "error_type": type(exc).__name__,
                "service": "platform_context",
                "base_url": base_url,
            },
            exc_info=True,
        )
        return {"error": f"External MCP platform context call failed: {exc}"}


async def handle_bsl_test_runner(args: Dict) -> Dict:
    """Proxy to external MCP test runner."""
    base_url = settings.mcp_bsl_test_runner_base_url
    if not base_url:
        return {
            "error": "MCP_BSL_TEST_RUNNER_BASE_URL is not configured. "
            "Install and run alkoleft/mcp-onec-test-runner, then set the environment variable.",
            "configured": False,
        }

    try:
        return await call_external_mcp(
            base_url=base_url,
            tool_name=settings.mcp_bsl_test_runner_tool_name,
            args=args,
            auth_token=settings.mcp_bsl_test_runner_auth_token,
        )
    except httpx.HTTPError as exc:
        logger.error(
            f"External MCP (test runner) call failed: {exc}",
            extra={"error_type": type(exc).__name__, "service": "test_runner"},
            exc_info=True,
        )
        return {"error": f"External MCP test runner call failed: {exc}"}


class MCPServer:
    """
    Легковесная обертка, используемая в интеграционных тестах.
    """

    def __init__(self):
        self._orchestrator = get_orchestrator()

    async def search_metadata(
        self, query: str, metadata_type: Optional[str] = None
    ) -> Dict[str, Any]:
        return {
            "query": query,
            "type": metadata_type,
            "results": [],
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=6001)
