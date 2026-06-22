"""Deterministic 1C EDT form blueprint generator."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from src.services.rentgen.metadata_graph import DEFAULT_CONFIG_PATH, get_metadata_object
from src.services.rentgen.metadata_insights import review_forms

REGISTER_TYPES = {
    "InformationRegister",
    "AccumulationRegister",
    "AccountingRegister",
    "CalculationRegister",
}
OBJECT_FORM_TYPES = {
    "Document",
    "Catalog",
    "DataProcessor",
    "Report",
    "BusinessProcess",
    "Task",
}
LIST_FORM_TYPES = {"Document", "Catalog", "DocumentJournal", *REGISTER_TYPES}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _config_path(config_path: str | None) -> Path:
    return Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH.resolve()


def _display_name(item: dict[str, Any]) -> str:
    return str(item.get("synonym") or item.get("name") or "")


def _field_source(obj: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for group, source in (
        ("attribute", obj.get("attributes") or []),
        ("dimension", obj.get("dimensions") or []),
        ("resource", obj.get("resources") or []),
    ):
        for item in source:
            name = str(item.get("name") or "")
            if not name:
                continue
            fields.append(
                {
                    "name": name,
                    "caption": _display_name(item) or name,
                    "type": str(item.get("type") or ""),
                    "group": group,
                    "control": "InputField",
                    "binding": f"Object.{name}",
                }
            )
    return fields


def _resolve_kind(obj: dict[str, Any], requested: str | None) -> str:
    kind = (requested or "auto").casefold()
    if kind in {"object", "list", "choice"}:
        return kind
    if obj["type"] in LIST_FORM_TYPES and obj["type"] not in OBJECT_FORM_TYPES:
        return "list"
    return "object"


def _default_commands(obj: dict[str, Any], kind: str) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    if kind == "object":
        commands.extend(
            [
                {"name": "Write", "caption": "Write", "placement": "primary"},
                {
                    "name": "WriteAndClose",
                    "caption": "Write and close",
                    "placement": "primary",
                },
            ]
        )
        if obj["type"] == "Document":
            commands.append({"name": "Post", "caption": "Post", "placement": "primary"})
    else:
        commands.extend(
            [
                {"name": "Create", "caption": "Create", "placement": "primary"},
                {"name": "Refresh", "caption": "Refresh", "placement": "secondary"},
            ]
        )

    for command in obj.get("commands") or []:
        commands.append(
            {
                "name": str(command.get("name") or ""),
                "caption": str(command.get("name") or ""),
                "placement": "secondary",
            }
        )
    return [command for command in commands if command["name"]]


def _layout(
    obj: dict[str, Any], kind: str, fields: list[dict[str, Any]]
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    if kind in {"list", "choice"}:
        sections.append(
            {
                "id": "dynamic_list",
                "title": "Dynamic list",
                "type": "DynamicList",
                "data_source": obj["ref"],
                "columns": fields[:12],
                "filters": [field for field in fields if field["group"] == "dimension"][
                    :6
                ],
            }
        )
    else:
        sections.append(
            {
                "id": "main",
                "title": "Main",
                "type": "Group",
                "fields": fields[:24],
            }
        )
        table_sections = []
        for item in obj.get("tabular_sections") or []:
            name = str(item.get("name") or "")
            if name:
                table_sections.append(
                    {
                        "name": name,
                        "caption": _display_name(item) or name,
                        "control": "Table",
                    }
                )
        if table_sections:
            sections.append(
                {
                    "id": "tables",
                    "title": "Tabular sections",
                    "type": "TabbedGroup",
                    "tables": table_sections[:10],
                }
            )

    return {
        "kind": kind,
        "root": "ManagedForm",
        "sections": sections,
        "empty_state": "Show a focused empty state when the object has no rows or tabular lines.",
    }


def _xml_draft(
    obj: dict[str, Any],
    kind: str,
    layout: dict[str, Any],
    commands: list[dict[str, str]],
) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<FormBlueprint metadata="{escape(obj["ref"])}" kind="{escape(kind)}">',
        "  <CommandBar>",
    ]
    for command in commands:
        lines.append(
            f'    <Command name="{escape(command["name"])}" caption="{escape(command["caption"])}" placement="{escape(command["placement"])}" />'
        )
    lines.extend(["  </CommandBar>", "  <Layout>"])
    for section in layout["sections"]:
        lines.append(
            f'    <Section id="{escape(section["id"])}" title="{escape(section["title"])}" type="{escape(section["type"])}">'
        )
        for field in section.get("fields", []) or section.get("columns", []):
            lines.append(
                f'      <Field name="{escape(field["name"])}" caption="{escape(field["caption"])}" binding="{escape(field["binding"])}" />'
            )
        for table in section.get("tables", []):
            lines.append(
                f'      <Table name="{escape(table["name"])}" caption="{escape(table["caption"])}" />'
            )
        lines.append("    </Section>")
    lines.extend(["  </Layout>", "</FormBlueprint>"])
    return "\n".join(lines)


def _module_draft(obj: dict[str, Any], kind: str) -> str:
    prefix = obj["name"]
    if kind in {"list", "choice"}:
        return f"""Procedure OnCreateAtServer(Cancel, StandardProcessing)
    // Prepare filters and commands for {prefix} list form.
EndProcedure

Procedure RefreshList(Command)
    Items.Refresh();
EndProcedure"""

    return f"""Procedure OnCreateAtServer(Cancel, StandardProcessing)
    // Initialize defaults for {prefix} form.
EndProcedure

Procedure BeforeWrite(Cancel, WriteParameters)
    ValidateRequiredFields(Cancel);
EndProcedure

Procedure ValidateRequiredFields(Cancel)
EndProcedure"""


def _ux_rules(
    obj: dict[str, Any],
    kind: str,
    fields: list[dict[str, Any]],
    commands: list[dict[str, str]],
) -> list[dict[str, Any]]:
    rules = [
        {
            "severity": "medium",
            "code": "role-aware-commands",
            "message": "Keep write/post/delete commands visible only for roles that have matching rights.",
        },
        {
            "severity": "medium",
            "code": "test-required-fields",
            "message": "Add Vanessa/YAxUnit checks for required fields and command availability.",
        },
    ]
    if kind in {"list", "choice"}:
        rules.append(
            {
                "severity": "low",
                "code": "dynamic-list-filters",
                "message": "Expose high-selectivity filters first and avoid expensive default filters.",
            }
        )
    if len(fields) > 24:
        rules.append(
            {
                "severity": "medium",
                "code": "wide-form",
                "message": "Split a wide form into semantic groups or tabs.",
                "details": {"fields": len(fields)},
            }
        )
    if len(commands) > 12:
        rules.append(
            {
                "severity": "low",
                "code": "large-command-surface",
                "message": "Group secondary commands and keep primary commands scarce.",
                "details": {"commands": len(commands)},
            }
        )
    if obj["type"] == "Document" and kind == "object":
        rules.append(
            {
                "severity": "medium",
                "code": "posting-path",
                "message": "Document forms must expose posting outcome, validation messages and rollback-safe behavior.",
            }
        )
    return rules


def _review(
    identifier: str, config_path: Path, include_review: bool
) -> dict[str, Any] | None:
    if not include_review:
        return None
    try:
        return review_forms(identifier, config_path=str(config_path))
    except ValueError:
        return None


def build_form_blueprint(
    identifier: str,
    *,
    form_kind: str | None = "auto",
    intent: str | None = None,
    include_review: bool = True,
    config_path: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic form design blueprint and generated draft assets."""

    config = _config_path(config_path)
    obj = get_metadata_object(identifier, str(config))
    if obj is None:
        raise ValueError(f"Metadata object not found: {identifier}")

    kind = _resolve_kind(obj, form_kind)
    fields = _field_source(obj)
    commands = _default_commands(obj, kind)
    layout = _layout(obj, kind, fields)
    review = _review(identifier, config, include_review)
    review_findings = int((review or {}).get("summary", {}).get("findings", 0))
    ux_rules = _ux_rules(obj, kind, fields, commands)
    readiness_status = (
        "warn"
        if review_findings or any(rule["severity"] == "medium" for rule in ux_rules)
        else "pass"
    )

    report = {
        "generated_at": _now(),
        "config_path": str(config),
        "identifier": identifier,
        "intent": intent or "",
        "object": {
            "type": obj["type"],
            "name": obj["name"],
            "ref": obj["ref"],
            "path": obj["path"],
            "synonym": obj.get("synonym"),
        },
        "form_kind": kind,
        "summary": {
            "fields": len(fields),
            "tabular_sections": len(obj.get("tabular_sections") or []),
            "commands": len(commands),
            "existing_forms": len(obj.get("forms") or []),
            "review_findings": review_findings,
            "ux_rules": len(ux_rules),
            "readiness": readiness_status,
        },
        "layout": layout,
        "commands": commands,
        "ux_rules": ux_rules,
        "review": review,
        "generated_assets": {
            "form_xml": _xml_draft(obj, kind, layout, commands),
            "form_module_bsl": _module_draft(obj, kind),
            "import_ready": False,
        },
        "acceptance_checks": [
            "Open form for the minimum and maximum role set.",
            "Run command availability checks for write/post/delete paths.",
            "Run form smoke with empty, typical and high-volume data.",
        ],
        "caveats": [
            "Generated XML is a deterministic blueprint draft, not a full EDT designer export.",
            "Review generated controls with a 1C developer before importing into a configuration.",
        ],
    }
    report["markdown"] = _markdown(report)
    return report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1cAI Form Blueprint",
        "",
        f"Object: **{report['object']['ref']}**",
        f"Kind: **{report['form_kind']}**",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## UX Rules", ""])
    for rule in report["ux_rules"]:
        lines.append(f"- **{rule['severity']}** `{rule['code']}`: {rule['message']}")
    lines.extend(["", "## Acceptance Checks", ""])
    for check in report["acceptance_checks"]:
        lines.append(f"- {check}")
    return "\n".join(lines)
