"""Planning layer for integrating 1cAI with an EDT-native MCP server.

The catalog is based on DitriXNew/EDT-MCP public tool documentation. Keep the
data small and product-oriented: this module helps 1cAI decide which EDT-native
toolsets to reveal and which safe workflow to run before we vendor plugin code.
"""

from __future__ import annotations

import json
import os
from hashlib import sha256
from ipaddress import ip_address
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx


EDT_MCP_REPO = "https://github.com/DitriXNew/EDT-MCP"
DEFAULT_BASE_URL = "http://127.0.0.1:8765"
MCP_PROTOCOL_VERSION = "2025-11-25"
BRIDGE_CLIENT_NAME = "1cAI EDT-MCP Bridge"
LOCAL_EDT_MCP_HOSTS = {"localhost"}
APPROVAL_REASON_MIN_LENGTH = 12

TOOLSETS: list[dict[str, Any]] = [
    {
        "id": "core",
        "title": "Core",
        "purpose": "Project/module navigation, source read, metadata discovery and progressive disclosure.",
        "tools": [
            "get_edt_version",
            "get_server_status",
            "get_tool_guide",
            "list_projects",
            "get_configuration_properties",
            "list_modules",
            "get_module_structure",
            "read_module_source",
            "search_in_code",
            "get_metadata_objects",
            "get_metadata_details",
            "list_toolsets",
            "enable_toolset",
        ],
        "risk": "read",
    },
    {
        "id": "project",
        "title": "Project",
        "purpose": "EDT validation, markers, check docs, XML exchange and workspace operations.",
        "tools": [
            "get_problem_summary",
            "get_project_errors",
            "get_markers",
            "get_check_description",
            "clean_project",
            "revalidate_objects",
            "export_configuration_to_xml",
            "import_configuration_from_xml",
            "create_project",
            "delete_project",
            "resync_to_disk",
        ],
        "risk": "mixed",
    },
    {
        "id": "metadata",
        "title": "Metadata",
        "purpose": "Metadata objects, subsystems, details and structural refactoring.",
        "tools": [
            "list_subsystems",
            "get_subsystem_content",
            "find_references",
            "create_metadata",
            "modify_metadata",
            "rename_metadata_object",
            "delete_metadata",
            "adopt_metadata_object",
        ],
        "risk": "write",
    },
    {
        "id": "code",
        "title": "BSL Code",
        "purpose": "Semantic code reading/writing, call hierarchy, content assist and query validation.",
        "tools": [
            "read_method_source",
            "write_module_source",
            "get_method_call_hierarchy",
            "go_to_definition",
            "get_symbol_info",
            "get_content_assist",
            "get_platform_documentation",
            "validate_query",
        ],
        "risk": "write",
    },
    {
        "id": "forms",
        "title": "Forms",
        "purpose": "Managed-form WYSIWYG layout snapshots and screenshots from EDT.",
        "tools": ["get_form_layout_snapshot", "get_form_screenshot"],
        "risk": "read",
        "preconditions": ["EDT JVM flag -DnativeFormBufferedLayoutRender=true"],
    },
    {
        "id": "testing",
        "title": "Testing",
        "purpose": "YAXUnit run/debug through EDT launch configurations.",
        "tools": ["run_yaxunit_tests", "debug_yaxunit_tests"],
        "risk": "execute",
    },
    {
        "id": "debug",
        "title": "Debug",
        "purpose": "Launch/attach, breakpoints, stepping, variables and expression evaluation.",
        "tools": [
            "list_configurations",
            "get_applications",
            "create_infobase",
            "delete_infobase",
            "create_launch_config",
            "delete_launch_config",
            "debug_launch",
            "debug_status",
            "set_breakpoint",
            "remove_breakpoint",
            "list_breakpoints",
            "wait_for_break",
            "get_variables",
            "step",
            "resume",
            "evaluate_expression",
            "terminate_launch",
            "update_database",
        ],
        "risk": "execute",
    },
    {
        "id": "profiling",
        "title": "Profiling",
        "purpose": "Line-level runtime profiling in active EDT debug sessions.",
        "tools": ["start_profiling", "stop_profiling", "get_profiling_results"],
        "risk": "execute",
    },
    {
        "id": "tags",
        "title": "Tags",
        "purpose": "EDT metadata tags and tag-filtered navigation.",
        "tools": ["get_tags", "get_objects_by_tags"],
        "risk": "read",
    },
    {
        "id": "translation",
        "title": "Translation",
        "purpose": "LanguageTool translation string generation and synchronization.",
        "tools": ["generate_translation_strings", "translate_configuration", "get_translation_project_info"],
        "risk": "write",
    },
]

PRESETS = [
    {
        "id": "analysis_only",
        "title": "Analysis Only",
        "enabled_toolsets": ["core", "project", "tags"],
        "disabled_risks": ["write", "execute"],
    },
    {
        "id": "code_review",
        "title": "Code Review",
        "enabled_toolsets": ["core", "project", "code", "forms", "tags"],
        "disabled_tools": ["write_module_source"],
    },
    {
        "id": "development",
        "title": "Development",
        "enabled_toolsets": ["core", "project", "metadata", "code", "forms", "testing", "tags"],
        "disabled_toolsets": ["debug", "profiling"],
    },
    {
        "id": "full",
        "title": "All Tools",
        "enabled_toolsets": [item["id"] for item in TOOLSETS],
    },
]

WORKFLOW_RULES = [
    {
        "id": "query_validation",
        "keywords": ["query", "запрос", "скд", "select", "выбрать", "validate"],
        "toolsets": ["core", "code"],
        "edt_tools": ["validate_query", "get_metadata_objects", "get_platform_documentation"],
        "one_cai_tools": ["rentgen_generate_grounded", "bsl_standards_review"],
        "safety": "Validate query text in EDT before embedding it into generated BSL.",
    },
    {
        "id": "form_review",
        "keywords": ["form", "форма", "layout", "screenshot", "визуал", "интерфейс"],
        "toolsets": ["core", "forms", "code"],
        "edt_tools": ["get_form_layout_snapshot", "get_form_screenshot", "get_module_structure"],
        "one_cai_tools": ["rentgen_form_review", "rentgen_form_blueprint"],
        "safety": "Use YAML layout first; PNG only when a visual decision is needed.",
    },
    {
        "id": "metadata_refactoring",
        "keywords": ["rename", "delete", "create metadata", "переимен", "удали", "создай объект", "реквизит"],
        "toolsets": ["core", "metadata", "project"],
        "edt_tools": ["get_metadata_details", "find_references", "rename_metadata_object", "delete_metadata", "create_metadata"],
        "one_cai_tools": ["rentgen_metadata_object_impact", "rentgen_release_readiness"],
        "safety": "Run preview/impact first; destructive metadata calls require explicit confirmation.",
    },
    {
        "id": "code_change",
        "keywords": ["change code", "write", "исправ", "доработ", "метод", "module", "модуль"],
        "toolsets": ["core", "code", "project"],
        "edt_tools": ["get_module_structure", "read_method_source", "write_module_source", "get_project_errors"],
        "one_cai_tools": ["rentgen_change_plan", "bsl_standards_review", "rentgen_test_coverage_matrix"],
        "safety": "Prefer method-level read and searchReplace with contentHash/expectedSource guards.",
    },
    {
        "id": "testing",
        "keywords": ["test", "тест", "yaxunit", "vanessa", "qa"],
        "toolsets": ["core", "testing", "project"],
        "edt_tools": ["list_configurations", "run_yaxunit_tests", "get_project_errors"],
        "one_cai_tools": ["rentgen_test_coverage_matrix", "rentgen_test_match"],
        "safety": "Use Rentgen to select affected tests, EDT-MCP to run real YAXUnit.",
    },
    {
        "id": "debugging",
        "keywords": ["debug", "отлад", "breakpoint", "переменн", "stack", "expression"],
        "toolsets": ["core", "debug", "code"],
        "edt_tools": ["debug_launch", "set_breakpoint", "wait_for_break", "get_variables", "step", "resume"],
        "one_cai_tools": ["rentgen_change_plan", "rentgen_incident_report"],
        "safety": "Treat evaluate_expression as executable code; require trusted local EDT session.",
    },
    {
        "id": "performance",
        "keywords": ["performance", "производ", "profiling", "профилир", "slow", "медлен"],
        "toolsets": ["core", "profiling", "debug"],
        "edt_tools": ["start_profiling", "stop_profiling", "get_profiling_results"],
        "one_cai_tools": ["rentgen_performer_analyze", "rentgen_performer_impact", "rentgen_incident_report"],
        "safety": "Combine live profiling with Rentgen/TJ impact before assigning fixes.",
    },
]

READ_ONLY_PREFIXES = ("get_", "list_", "read_", "search_", "find_", "validate_")
READ_ONLY_TOOL_NAMES = {
    "go_to_definition",
    "get_content_assist",
    "get_method_call_hierarchy",
    "get_symbol_info",
    "export_configuration_to_xml",
}
SESSION_ONLY_TOOL_NAMES = {"enable_toolset"}
WRITE_TOOL_NAMES = {
    "adopt_metadata_object",
    "clean_project",
    "create_metadata",
    "create_project",
    "delete_metadata",
    "delete_project",
    "generate_translation_strings",
    "import_configuration_from_xml",
    "modify_metadata",
    "rename_metadata_object",
    "resync_to_disk",
    "revalidate_objects",
    "translate_configuration",
    "write_module_source",
}
EXECUTE_TOOL_NAMES = {
    "create_infobase",
    "create_launch_config",
    "debug_launch",
    "debug_yaxunit_tests",
    "delete_infobase",
    "delete_launch_config",
    "evaluate_expression",
    "remove_breakpoint",
    "resume",
    "run_yaxunit_tests",
    "set_breakpoint",
    "start_profiling",
    "step",
    "stop_profiling",
    "terminate_launch",
    "update_database",
    "wait_for_break",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _toolset_map() -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in TOOLSETS}


def _tool_to_toolset_map() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for toolset in TOOLSETS:
        for tool in toolset["tools"]:
            result[tool] = toolset
    return result


def _total_tools() -> int:
    return len({tool for toolset in TOOLSETS for tool in toolset["tools"]})


def _allow_remote_edt_mcp() -> bool:
    return os.getenv("EDT_MCP_ALLOW_REMOTE", "").strip().lower() in {"1", "true", "yes", "on"}


def _require_approval_record() -> bool:
    return os.getenv("EDT_MCP_REQUIRE_APPROVAL_RECORD", "").strip().lower() in {"1", "true", "yes", "on"}


# Risk levels that are privileged/destructive: starting/altering/executing a live
# 1C/EDT session, or destructive configuration mutations. For these, a free-text
# reason must NOT self-authorize the call; a validated approval record is
# required by default. An operator may relax this in a trusted dev environment.
PRIVILEGED_RISK_LEVELS = frozenset({"execute"})


def _allow_inline_privileged_approval() -> bool:
    """Dev-only escape hatch: permit inline-reason approval for privileged ops."""

    return os.getenv("EDT_MCP_ALLOW_INLINE_PRIVILEGED", "").strip().lower() in {"1", "true", "yes", "on"}


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    lowered = host.casefold()
    if lowered in LOCAL_EDT_MCP_HOSTS:
        return True
    try:
        return ip_address(lowered).is_loopback
    except ValueError:
        return False


def normalize_edt_mcp_base_url(base_url: str | None = None, *, allow_remote: bool | None = None) -> str:
    """Normalize an EDT-MCP endpoint root, accepting either root or /mcp URL."""

    raw = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    if raw.endswith("/mcp"):
        raw = raw[:-4].rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("EDT-MCP base_url must be an http(s) URL")
    remote_allowed = _allow_remote_edt_mcp() if allow_remote is None else allow_remote
    if not remote_allowed and not _is_loopback_host(parsed.hostname):
        raise ValueError(
            "EDT-MCP base_url must point to localhost/loopback. "
            "Set EDT_MCP_ALLOW_REMOTE=1 only for a trusted, isolated deployment."
        )
    return raw


def _annotation_bool(annotations: dict[str, Any] | None, name: str) -> bool | None:
    if not isinstance(annotations, dict) or name not in annotations:
        return None
    value = annotations.get(name)
    return value if isinstance(value, bool) else None


def _annotation_classification(annotations: dict[str, Any] | None) -> tuple[str, bool, str] | None:
    read_only = _annotation_bool(annotations, "readOnlyHint")
    destructive = _annotation_bool(annotations, "destructiveHint")
    open_world = _annotation_bool(annotations, "openWorldHint")

    if destructive is True:
        return "write", True, "Live MCP annotations mark this tool as destructive."
    if open_world is True:
        return "execute", True, "Live MCP annotations mark this tool as touching the open world."
    if read_only is True:
        return "read", False, "Live MCP annotations mark this tool as read-only."
    if read_only is False or destructive is False:
        return "write", True, "Live MCP annotations do not mark this tool as read-only."
    return None


def classify_edt_mcp_tool(tool_name: str, *, annotations: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classify an EDT-MCP tool so the bridge can gate mutating calls."""

    name = str(tool_name or "").strip()
    toolset = _tool_to_toolset_map().get(name)
    known = toolset is not None
    annotation_verdict = _annotation_classification(annotations)

    if name in SESSION_ONLY_TOOL_NAMES:
        risk = "session"
        requires_confirmation = False
        note = "Changes only MCP tool visibility for the current EDT-MCP session."
    elif name in WRITE_TOOL_NAMES:
        risk = "write"
        requires_confirmation = True
        note = "Can change EDT project/configuration state."
    elif name in EXECUTE_TOOL_NAMES:
        risk = "execute"
        requires_confirmation = True
        note = "Can start/alter/debug/execute a live EDT or 1C session."
    elif annotation_verdict is not None:
        risk, requires_confirmation, note = annotation_verdict
    elif known and (name in READ_ONLY_TOOL_NAMES or name.startswith(READ_ONLY_PREFIXES)):
        risk = "read"
        requires_confirmation = False
        note = "Read-only EDT inspection or validation."
    elif known and str(toolset.get("risk")) == "read":
        risk = "read"
        requires_confirmation = False
        note = "Catalog marks the containing toolset as read-only."
    elif known:
        risk = str(toolset.get("risk") or "mixed")
        requires_confirmation = risk in {"write", "execute", "mixed"}
        note = "Catalog toolset is not purely read-only; require explicit confirmation."
    else:
        risk = "unknown"
        requires_confirmation = True
        note = "Unknown EDT-MCP tool; require confirmation before proxying."

    return {
        "tool_name": name,
        "known": known,
        "toolset_id": toolset.get("id") if toolset else None,
        "toolset_title": toolset.get("title") if toolset else None,
        "risk": risk,
        "requires_confirmation": requires_confirmation,
        "mutates_configuration": risk in {"write", "mixed"},
        "executes_runtime": risk == "execute",
        "safety_note": note,
        "source": "catalog" if known else "live_annotations" if annotation_verdict is not None else "unknown",
    }


def _trimmed(value: str | None, *, limit: int = 1000) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _payload_fingerprint(value: Any) -> str:
    try:
        payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    except TypeError:
        payload = str(value)
    return sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:16]


def _argument_summary(arguments: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        return {"type": type(arguments).__name__, "keys": [], "fingerprint": _payload_fingerprint(arguments)}
    return {
        "type": "object",
        "keys": sorted(str(key) for key in arguments.keys())[:50],
        "count": len(arguments),
        "fingerprint": _payload_fingerprint(arguments),
    }


def _redact_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlparse(value)
    except Exception:
        return "<invalid>"
    if not parsed.scheme or not parsed.netloc:
        return value
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}{parsed.path.rstrip('/')}"


def _audit_edt_mcp_call(
    *,
    audit_logger: Any | None,
    actor: str | None,
    status: str,
    tool_name: str,
    classification: dict[str, Any],
    base_url: str | None,
    arguments: dict[str, Any] | None,
    approval_reason: str | None = None,
    approval_ticket: str | None = None,
    approval_id: str | None = None,
    approval_source: str | None = None,
    error: Any | None = None,
) -> None:
    if not classification.get("requires_confirmation") and status == "ok" and not os.getenv("EDT_MCP_AUDIT_READS"):
        return
    logger = audit_logger
    if logger is None:
        try:
            from src.security import get_audit_logger

            logger = get_audit_logger()
        except Exception:
            logger = None
    if logger is None:
        return
    metadata = {
        "status": status,
        "risk": classification.get("risk"),
        "requires_confirmation": classification.get("requires_confirmation"),
        "base_url": _redact_url(base_url),
        "arguments": _argument_summary(arguments),
        "approval": {
            "id": approval_id,
            "source": approval_source,
            "reason_present": bool(approval_reason),
            "reason_length": len(approval_reason or ""),
            "ticket": approval_ticket,
        },
    }
    if error is not None:
        metadata["error"] = str(error)[:500]
    try:
        logger.log_action(
            actor=actor or "anonymous",
            action=f"edt_mcp.call.{status}",
            target=tool_name,
            metadata=metadata,
        )
    except Exception:
        return


def guard_edt_mcp_tool_call(
    tool_name: str,
    *,
    arguments: dict[str, Any] | None = None,
    confirm: bool = False,
    actor: str | None = None,
    approval_reason: str | None = None,
    approval_ticket: str | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """Return whether a live EDT-MCP call is allowed by the 1cAI safety gate."""

    classification = classify_edt_mcp_tool(tool_name)
    normalized_actor = _trimmed(actor, limit=160)
    normalized_reason = _trimmed(approval_reason, limit=1000)
    normalized_ticket = _trimmed(approval_ticket, limit=160)
    normalized_approval_id = _trimmed(approval_id, limit=80)
    # Privileged/destructive ops (live-session execute, plus any tool the catalog
    # or live annotations flagged destructive) require a real, validated approval
    # record by default — a free-text reason cannot self-authorize them. A plain
    # global flag can also force records for all confirm-required ops.
    risk_level = str(classification.get("risk") or "unknown")
    is_privileged = (
        risk_level in PRIVILEGED_RISK_LEVELS
        or bool(classification.get("executes_runtime"))
    ) and not _allow_inline_privileged_approval()
    approval_record_required = _require_approval_record() or is_privileged
    missing: list[str] = []
    approval_validation: dict[str, Any] | None = None
    approval_source = "none"
    if classification["requires_confirmation"]:
        if not confirm:
            missing.append("confirm")
        if not normalized_actor:
            missing.append("actor")
        if normalized_approval_id:
            try:
                from src.services.rentgen.approval_workflow import validate_approval_for_call

                approval_validation = validate_approval_for_call(
                    normalized_approval_id,
                    tool_name=classification["tool_name"],
                    actor=normalized_actor,
                    risk=str(classification.get("risk") or "unknown"),
                    arguments=arguments,
                )
            except Exception as exc:
                approval_validation = {"valid": False, "reason": f"validation_error:{exc}", "approval": None}
            if approval_validation.get("valid"):
                approval_source = "record"
            else:
                missing.append("approval_id")
                approval_source = "invalid_record"
        elif approval_record_required:
            # No approval id supplied but a record is mandatory (privileged op or
            # strict mode). A reason alone is rejected.
            missing.append("approval_id")
            approval_source = "required_record"
        elif len(normalized_reason or "") >= APPROVAL_REASON_MIN_LENGTH:
            approval_source = "inline"
        else:
            missing.append("approval_reason")
    allowed = not missing
    policy = {
        "mode": "approval_required" if classification["requires_confirmation"] else "read_only",
        "requires_confirmation": classification["requires_confirmation"],
        "requires_actor": classification["requires_confirmation"],
        "requires_reason": classification["requires_confirmation"],
        "requires_approval_record": approval_record_required and classification["requires_confirmation"],
        "privileged": is_privileged and classification["requires_confirmation"],
        "minimum_reason_length": APPROVAL_REASON_MIN_LENGTH if classification["requires_confirmation"] else 0,
        "actor": normalized_actor,
        "approval_id": normalized_approval_id,
        "approval_source": approval_source,
        "approval_validation": {
            "valid": bool((approval_validation or {}).get("valid")),
            "reason": (approval_validation or {}).get("reason"),
            "status": ((approval_validation or {}).get("approval") or {}).get("status"),
        }
        if approval_validation is not None
        else None,
        "approval_ticket": normalized_ticket,
        "approval_reason_length": len(normalized_reason or ""),
        "missing": missing,
        "audit_action": "edt_mcp.call.ok" if allowed else "edt_mcp.call.blocked",
    }
    return {
        "allowed": allowed,
        "blocked": not allowed,
        "classification": classification,
        "policy": policy,
        "required_confirmation": "confirm" in missing,
        "message": (
            "Call allowed by 1cAI EDT-MCP safety gate."
            if allowed
            else "EDT-MCP call blocked: write/execute/unknown tools require confirm=true, actor and approval_reason."
        ),
    }


def _mcp_url(base_url: str) -> str:
    return normalize_edt_mcp_base_url(base_url) + "/mcp"


def _headers(auth_token: str | None = None, session_id: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    return headers


def _extract_mcp_payload(response: httpx.Response) -> Any:
    if response.status_code == 202 or not response.content:
        return None

    text = response.text.strip()
    if "text/event-stream" in response.headers.get("content-type", "") or text.startswith("event:"):
        data_lines = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        if not data_lines:
            return None
        return json.loads(data_lines[-1])

    return response.json()


async def _post_json_rpc(
    client: httpx.AsyncClient,
    *,
    mcp_url: str,
    method: str,
    params: dict[str, Any] | None = None,
    auth_token: str | None = None,
    session_id: str | None = None,
    request_id: int | None = 1,
) -> tuple[Any, httpx.Response]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        body["id"] = request_id
    if params is not None:
        body["params"] = params

    response = await client.post(
        mcp_url,
        json=body,
        headers=_headers(auth_token, session_id),
    )
    response.raise_for_status()
    return _extract_mcp_payload(response), response


def _json_rpc_error(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        return payload["error"]
    return None


async def _initialize_session(
    client: httpx.AsyncClient,
    *,
    mcp_url: str,
    auth_token: str | None = None,
) -> dict[str, Any]:
    payload, response = await _post_json_rpc(
        client,
        mcp_url=mcp_url,
        method="initialize",
        params={
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "clientInfo": {"name": BRIDGE_CLIENT_NAME, "version": "1.0.0"},
        },
        auth_token=auth_token,
        request_id=1,
    )
    error = _json_rpc_error(payload)
    if error:
        return {"ok": False, "error": error, "payload": payload}

    session_id = response.headers.get("Mcp-Session-Id")
    try:
        await _post_json_rpc(
            client,
            mcp_url=mcp_url,
            method="notifications/initialized",
            params={},
            auth_token=auth_token,
            session_id=session_id,
            request_id=None,
        )
    except httpx.HTTPError:
        pass

    return {
        "ok": True,
        "session_id": session_id,
        "server": payload.get("result", {}) if isinstance(payload, dict) else {},
    }


def _http_error_payload(exc: httpx.HTTPStatusError) -> dict[str, Any]:
    try:
        payload = _extract_mcp_payload(exc.response)
    except Exception:
        payload = exc.response.text
    return {
        "status_code": exc.response.status_code,
        "payload": payload,
        "message": f"HTTP {exc.response.status_code} from EDT-MCP",
    }


def list_edt_mcp_toolsets() -> dict[str, Any]:
    """Return the curated EDT-MCP toolset catalog for 1cAI orchestration."""

    return {
        "generated_at": _now(),
        "source": EDT_MCP_REPO,
        "license": {
            "public": "AGPL-3.0",
            "reuse_policy": "Direct code reuse requires written permission or a dual-license note for 1cAI.",
        },
        "summary": {
            "toolsets": len(TOOLSETS),
            "tools": _total_tools(),
            "write_or_execute_toolsets": sum(1 for item in TOOLSETS if item["risk"] in {"write", "execute"}),
        },
        "toolsets": TOOLSETS,
        "presets": PRESETS,
        "high_value_for_1cai": [
            "EDT-native query validation before BSL code generation.",
            "WYSIWYG form layout snapshots for our managed-form blueprint workflow.",
            "Real YAXUnit execution/debugging to close the current selector-only testing gap.",
            "Cascading metadata refactoring instead of hand-written EDT XML edits.",
            "Progressive disclosure to keep MCP context small and safer.",
        ],
    }


def plan_edt_mcp_workflow(task: str | None, *, intent: str | None = None) -> dict[str, Any]:
    """Map a user task to EDT-MCP toolsets, EDT tools and 1cAI companion tools."""

    text = f"{task or ''} {intent or ''}".casefold()
    matches = [
        rule for rule in WORKFLOW_RULES
        if any(keyword.casefold() in text for keyword in rule["keywords"])
    ]
    if not matches:
        matches = [
            {
                "id": "workspace_onboarding",
                "toolsets": ["core", "project", "tags"],
                "edt_tools": ["list_projects", "get_configuration_properties", "get_problem_summary"],
                "one_cai_tools": ["rentgen_hotspots", "rentgen_metadata_search", "rentgen_team_governance"],
                "safety": "Start read-only; reveal write/debug toolsets only after a concrete task is known.",
            }
        ]

    toolsets = _unique([item for match in matches for item in match["toolsets"]])
    edt_tools = _unique([item for match in matches for item in match["edt_tools"]])
    one_cai_tools = _unique([item for match in matches for item in match["one_cai_tools"]])
    toolset_data = _toolset_map()
    risk_levels = _unique([str(toolset_data[item]["risk"]) for item in toolsets if item in toolset_data])
    has_write = any(level in {"write", "execute", "mixed"} for level in risk_levels)

    return {
        "generated_at": _now(),
        "task": task or "",
        "matched_workflows": [match["id"] for match in matches],
        "toolsets_to_enable": toolsets,
        "edt_tools": edt_tools,
        "one_cai_tools": one_cai_tools,
        "risk_levels": risk_levels,
        "requires_confirmation": has_write,
        "recommended_preset": "code_review" if not has_write else "development",
        "progressive_disclosure_calls": [
            {"tool": "list_toolsets", "arguments": {}},
            {"tool": "enable_toolset", "arguments": {"toolsets": [item for item in toolsets if item != "core"]}},
        ],
        "safety": _unique([match["safety"] for match in matches]),
        "bridge_notes": [
            "Use EDT-MCP for live EDT-only semantics; use 1cAI/Rentgen for whole-config risk, governance and release decisions.",
            "Keep destructive EDT-MCP calls behind preview/confirm even if the local endpoint is trusted.",
        ],
    }


def build_connection_config(base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    """Return ready-to-copy MCP client snippets for an EDT-MCP server."""

    normalized_base_url = normalize_edt_mcp_base_url(base_url)
    url = normalized_base_url + "/mcp"
    return {
        "generated_at": _now(),
        "base_url": normalized_base_url,
        "mcp_url": url,
        "edt_preconditions": [
            "EDT 2025.2+.",
            "EDT-MCP plugin installed and server running.",
            "For form screenshots/layout snapshots: -DnativeFormBufferedLayoutRender=true in 1cedt.ini.",
            "Keep endpoint loopback-only unless an auth token is configured.",
        ],
        "clients": {
            "vscode": {"servers": {"EDT MCP Server": {"type": "sse", "url": url}}},
            "cursor": {"mcpServers": {"EDT MCP Server": {"url": url}}},
            "claude_desktop": {"mcpServers": {"EDT MCP Server": {"url": url}}},
            "cline": {"mcpServers": {"EDTMCPServer": {"type": "streamableHttp", "url": url}}},
        },
    }


async def check_edt_mcp_status(
    base_url: str | None = None,
    *,
    auth_token: str | None = None,
    timeout_s: float = 5.0,
) -> dict[str, Any]:
    """Probe a live EDT-MCP server without mutating EDT state."""

    checked_at = _now()
    try:
        base = normalize_edt_mcp_base_url(base_url)
    except ValueError as exc:
        return {
            "checked_at": checked_at,
            "available": False,
            "status": "invalid_url",
            "error": str(exc),
            "base_url": base_url or "",
            "mcp_url": "",
        }

    result: dict[str, Any] = {
        "checked_at": checked_at,
        "available": False,
        "status": "offline",
        "base_url": base,
        "mcp_url": base + "/mcp",
        "auth_required": False,
        "authenticated": True,
        "health": None,
        "server_info": None,
        "errors": [],
    }

    timeout = max(1.0, min(float(timeout_s), 30.0))
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            health_response = await client.get(base + "/health")
            result["health_status_code"] = health_response.status_code
            result["health"] = _extract_mcp_payload(health_response)
        except httpx.HTTPError as exc:
            result["errors"].append(f"health: {exc}")

        try:
            info_response = await client.get(result["mcp_url"], headers=_headers(auth_token))
            result["mcp_status_code"] = info_response.status_code
            if info_response.status_code == 401:
                result["auth_required"] = True
                result["authenticated"] = False
            else:
                result["server_info"] = _extract_mcp_payload(info_response)
        except httpx.HTTPError as exc:
            result["errors"].append(f"mcp: {exc}")

    health_status = ""
    if isinstance(result["health"], dict):
        health_status = str(result["health"].get("status") or "").lower()
    has_health = health_status in {"ok", "starting", "degraded"} or result.get("health_status_code") == 200
    has_info = isinstance(result["server_info"], dict)
    result["available"] = bool(has_health or has_info)
    if result["auth_required"]:
        result["status"] = "auth_required"
    elif health_status:
        result["status"] = health_status
    elif has_info:
        result["status"] = "ok"
    return result


async def list_live_edt_mcp_tools(
    base_url: str | None = None,
    *,
    auth_token: str | None = None,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    """Initialize EDT-MCP and return the live tools/list with 1cAI classifications."""

    try:
        mcp_endpoint = _mcp_url(base_url or DEFAULT_BASE_URL)
    except ValueError as exc:
        return {"available": False, "status": "invalid_url", "error": str(exc), "tools": []}

    timeout = max(1.0, min(float(timeout_s), 60.0))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            session = await _initialize_session(client, mcp_url=mcp_endpoint, auth_token=auth_token)
            if not session["ok"]:
                return {
                    "available": False,
                    "status": "initialize_error",
                    "mcp_url": mcp_endpoint,
                    "error": session.get("error"),
                    "tools": [],
                }

            payload, _ = await _post_json_rpc(
                client,
                mcp_url=mcp_endpoint,
                method="tools/list",
                params={},
                auth_token=auth_token,
                session_id=session.get("session_id"),
                request_id=2,
            )
    except httpx.HTTPStatusError as exc:
        return {
            "available": False,
            "status": "http_error",
            "mcp_url": mcp_endpoint,
            "error": _http_error_payload(exc),
            "tools": [],
        }
    except httpx.HTTPError as exc:
        return {
            "available": False,
            "status": "request_error",
            "mcp_url": mcp_endpoint,
            "error": str(exc),
            "tools": [],
        }

    error = _json_rpc_error(payload)
    if error:
        return {
            "available": False,
            "status": "json_rpc_error",
            "mcp_url": mcp_endpoint,
            "error": error,
            "tools": [],
        }

    rpc_result = payload.get("result", {}) if isinstance(payload, dict) else {}
    raw_tools = rpc_result.get("tools", []) if isinstance(rpc_result, dict) else []
    tools: list[dict[str, Any]] = []
    risk_counts: dict[str, int] = {}
    for item in raw_tools if isinstance(raw_tools, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        annotations = item.get("annotations") if isinstance(item.get("annotations"), dict) else None
        classification = classify_edt_mcp_tool(name, annotations=annotations)
        risk_counts[classification["risk"]] = risk_counts.get(classification["risk"], 0) + 1
        tools.append({**item, "classification": classification})

    return {
        "available": True,
        "status": "ok",
        "generated_at": _now(),
        "mcp_url": mcp_endpoint,
        "session_id": session.get("session_id"),
        "server": session.get("server"),
        "summary": {
            "tools": len(tools),
            "by_risk": risk_counts,
            "requires_confirmation": sum(
                1 for item in tools if item["classification"]["requires_confirmation"]
            ),
        },
        "tools": tools,
        "raw_result": rpc_result,
    }


async def call_live_edt_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
    auth_token: str | None = None,
    confirm: bool = False,
    actor: str | None = None,
    approval_reason: str | None = None,
    approval_ticket: str | None = None,
    approval_id: str | None = None,
    timeout_s: float = 30.0,
    audit_logger: Any | None = None,
) -> dict[str, Any]:
    """Call a live EDT-MCP tool through the 1cAI confirmation gate."""

    guard = guard_edt_mcp_tool_call(
        tool_name,
        arguments=arguments,
        confirm=confirm,
        actor=actor,
        approval_reason=approval_reason,
        approval_ticket=approval_ticket,
        approval_id=approval_id,
    )
    if not guard["allowed"]:
        _audit_edt_mcp_call(
            audit_logger=audit_logger,
            actor=guard["policy"].get("actor") or actor,
            status="blocked",
            tool_name=tool_name,
            classification=guard["classification"],
            base_url=base_url or DEFAULT_BASE_URL,
            arguments=arguments,
            approval_reason=approval_reason,
            approval_ticket=approval_ticket,
            approval_id=guard["policy"].get("approval_id"),
            approval_source=guard["policy"].get("approval_source"),
        )
        return {
            "available": True,
            "status": "blocked",
            "blocked": True,
            **guard,
            "tool_name": tool_name,
        }

    try:
        mcp_endpoint = _mcp_url(base_url or DEFAULT_BASE_URL)
    except ValueError as exc:
        _audit_edt_mcp_call(
            audit_logger=audit_logger,
            actor=guard["policy"].get("actor") or actor,
            status="invalid_url",
            tool_name=tool_name,
            classification=guard["classification"],
            base_url=base_url or DEFAULT_BASE_URL,
            arguments=arguments,
            approval_reason=approval_reason,
            approval_ticket=approval_ticket,
            approval_id=guard["policy"].get("approval_id"),
            approval_source=guard["policy"].get("approval_source"),
            error=str(exc),
        )
        return {
            "available": False,
            "status": "invalid_url",
            "blocked": False,
            "error": str(exc),
            "tool_name": tool_name,
            "classification": guard["classification"],
            "policy": guard["policy"],
        }

    timeout = max(1.0, min(float(timeout_s), 300.0))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            session = await _initialize_session(client, mcp_url=mcp_endpoint, auth_token=auth_token)
            if not session["ok"]:
                _audit_edt_mcp_call(
                    audit_logger=audit_logger,
                    actor=guard["policy"].get("actor") or actor,
                    status="initialize_error",
                    tool_name=tool_name,
                    classification=guard["classification"],
                    base_url=base_url or DEFAULT_BASE_URL,
                    arguments=arguments,
                    approval_reason=approval_reason,
                    approval_ticket=approval_ticket,
                    approval_id=guard["policy"].get("approval_id"),
                    approval_source=guard["policy"].get("approval_source"),
                    error=session.get("error"),
                )
                return {
                    "available": False,
                    "status": "initialize_error",
                    "blocked": False,
                    "error": session.get("error"),
                    "mcp_url": mcp_endpoint,
                    "tool_name": tool_name,
                    "classification": guard["classification"],
                    "policy": guard["policy"],
                }

            payload, _ = await _post_json_rpc(
                client,
                mcp_url=mcp_endpoint,
                method="tools/call",
                params={"name": tool_name, "arguments": arguments or {}},
                auth_token=auth_token,
                session_id=session.get("session_id"),
                request_id=3,
            )
    except httpx.HTTPStatusError as exc:
        _audit_edt_mcp_call(
            audit_logger=audit_logger,
            actor=guard["policy"].get("actor") or actor,
            status="http_error",
            tool_name=tool_name,
            classification=guard["classification"],
            base_url=base_url or DEFAULT_BASE_URL,
            arguments=arguments,
            approval_reason=approval_reason,
            approval_ticket=approval_ticket,
            approval_id=guard["policy"].get("approval_id"),
            approval_source=guard["policy"].get("approval_source"),
            error=exc,
        )
        return {
            "available": False,
            "status": "http_error",
            "blocked": False,
            "error": _http_error_payload(exc),
            "mcp_url": mcp_endpoint,
            "tool_name": tool_name,
            "classification": guard["classification"],
            "policy": guard["policy"],
        }
    except httpx.HTTPError as exc:
        _audit_edt_mcp_call(
            audit_logger=audit_logger,
            actor=guard["policy"].get("actor") or actor,
            status="request_error",
            tool_name=tool_name,
            classification=guard["classification"],
            base_url=base_url or DEFAULT_BASE_URL,
            arguments=arguments,
            approval_reason=approval_reason,
            approval_ticket=approval_ticket,
            approval_id=guard["policy"].get("approval_id"),
            approval_source=guard["policy"].get("approval_source"),
            error=exc,
        )
        return {
            "available": False,
            "status": "request_error",
            "blocked": False,
            "error": str(exc),
            "mcp_url": mcp_endpoint,
            "tool_name": tool_name,
            "classification": guard["classification"],
            "policy": guard["policy"],
        }

    error = _json_rpc_error(payload)
    if error:
        _audit_edt_mcp_call(
            audit_logger=audit_logger,
            actor=guard["policy"].get("actor") or actor,
            status="json_rpc_error",
            tool_name=tool_name,
            classification=guard["classification"],
            base_url=base_url or DEFAULT_BASE_URL,
            arguments=arguments,
            approval_reason=approval_reason,
            approval_ticket=approval_ticket,
            approval_id=guard["policy"].get("approval_id"),
            approval_source=guard["policy"].get("approval_source"),
            error=error,
        )
        return {
            "available": True,
            "status": "json_rpc_error",
            "blocked": False,
            "error": error,
            "mcp_url": mcp_endpoint,
            "tool_name": tool_name,
            "classification": guard["classification"],
            "policy": guard["policy"],
        }

    _audit_edt_mcp_call(
        audit_logger=audit_logger,
        actor=guard["policy"].get("actor") or actor,
        status="ok",
        tool_name=tool_name,
        classification=guard["classification"],
        base_url=base_url or DEFAULT_BASE_URL,
        arguments=arguments,
        approval_reason=approval_reason,
        approval_ticket=approval_ticket,
        approval_id=guard["policy"].get("approval_id"),
        approval_source=guard["policy"].get("approval_source"),
    )
    if guard["policy"].get("approval_source") == "record" and guard["policy"].get("approval_id"):
        try:
            from src.services.rentgen.approval_workflow import update_approval_status

            update_approval_status(
                str(guard["policy"]["approval_id"]),
                status="used",
                actor=str(guard["policy"].get("actor") or actor or "system"),
                decision_reason="Consumed by successful EDT-MCP call.",
            )
        except Exception:
            pass
    return {
        "available": True,
        "status": "ok",
        "blocked": False,
        "mcp_url": mcp_endpoint,
        "tool_name": tool_name,
        "classification": guard["classification"],
        "policy": guard["policy"],
        "session_id": session.get("session_id"),
        "server": session.get("server"),
        "result": payload.get("result", payload) if isinstance(payload, dict) else payload,
    }
