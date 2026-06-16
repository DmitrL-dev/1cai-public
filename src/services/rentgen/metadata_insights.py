"""Enterprise metadata insights: snapshots, diffs, security and form review."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import re

from src.services.bsl_diagnostics import analyze_bsl
from src.services.rentgen.metadata_graph import (
    DEFAULT_CONFIG_PATH,
    REPO_ROOT,
    _local,
    _safe_parse,
    build_metadata_graph,
    get_metadata_object,
)


SNAPSHOT_DIR = REPO_ROOT / "data" / "metadata_snapshots"
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_HIGH_RISK_RIGHTS = {
    "Delete",
    "InteractiveDelete",
    "Update",
    "Edit",
    "Administration",
    "InteractiveMarkForDeletion",
    "InteractiveClearDeletionMark",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_name(value: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("-", value.strip())[:80].strip("-")
    return cleaned or "metadata"


def _config_path(config_path: str | None = None) -> Path:
    return Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH.resolve()


def _preview_for_snapshot(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": obj["type"],
        "name": obj["name"],
        "ref": obj["ref"],
        "path": obj["path"],
        "counts": obj["counts"],
        "modules": [module["path"] for module in obj.get("modules", [])],
        "forms": [form["path"] for form in obj.get("forms", [])],
        "commands": [command["path"] for command in obj.get("commands", [])],
        "rights_path": obj.get("rights_path"),
    }


def build_snapshot_payload(config_path: str | None = None) -> dict[str, Any]:
    graph = build_metadata_graph(str(_config_path(config_path)))
    return {
        "created_at": _now(),
        "config_path": graph["config_path"],
        "configuration": graph["configuration"],
        "summary": graph["summary"],
        "objects": [_preview_for_snapshot(obj) for obj in graph["objects"]],
    }


def create_metadata_snapshot(name: str | None = None, config_path: str | None = None) -> dict[str, Any]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_snapshot_payload(config_path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_name = f"{stamp}-{_safe_name(name or payload['configuration'].get('name') or 'metadata')}.json"
    path = SNAPSHOT_DIR / file_name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "id": path.name,
        "path": str(path),
        "created_at": payload["created_at"],
        "summary": payload["summary"],
    }


def list_metadata_snapshots() -> list[dict[str, Any]]:
    if not SNAPSHOT_DIR.exists():
        return []
    result = []
    for path in sorted(SNAPSHOT_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        result.append(
            {
                "id": path.name,
                "path": str(path),
                "created_at": payload.get("created_at"),
                "summary": payload.get("summary", {}),
            }
        )
    return result


def _snapshot_path(snapshot_id: str) -> Path:
    candidate = Path(snapshot_id)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    path = SNAPSHOT_DIR / snapshot_id
    if path.exists():
        return path
    raise FileNotFoundError(f"Metadata snapshot not found: {snapshot_id}")


def load_metadata_snapshot(snapshot_id: str) -> dict[str, Any]:
    path = _snapshot_path(snapshot_id)
    return json.loads(path.read_text(encoding="utf-8"))


def _object_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {obj["ref"]: obj for obj in payload.get("objects", [])}


def diff_metadata_snapshot(
    snapshot_id: str,
    *,
    config_path: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    previous = load_metadata_snapshot(snapshot_id)
    current = build_snapshot_payload(config_path)
    before = _object_map(previous)
    after = _object_map(current)

    before_refs = set(before)
    after_refs = set(after)
    added_refs = sorted(after_refs - before_refs)
    removed_refs = sorted(before_refs - after_refs)
    common_refs = sorted(before_refs & after_refs)
    changed = []

    for ref in common_refs:
        old = before[ref]
        new = after[ref]
        changes: dict[str, Any] = {}
        for key in ("counts", "modules", "forms", "commands", "rights_path"):
            if old.get(key) != new.get(key):
                changes[key] = {"before": old.get(key), "after": new.get(key)}
        if changes:
            changed.append({"ref": ref, "type": new.get("type"), "name": new.get("name"), "changes": changes})

    return {
        "snapshot": {
            "id": snapshot_id,
            "created_at": previous.get("created_at"),
            "summary": previous.get("summary", {}),
        },
        "current": {"created_at": current["created_at"], "summary": current["summary"]},
        "summary": {
            "added": len(added_refs),
            "removed": len(removed_refs),
            "changed": len(changed),
        },
        "added": [after[ref] for ref in added_refs[:limit]],
        "removed": [before[ref] for ref in removed_refs[:limit]],
        "changed": changed[:limit],
        "caveats": [
            "Snapshot diff compares EDT metadata surface and assets; it does not prove semantic equivalence.",
            "Rights details are compared by rights XML presence in the lightweight snapshot. Use security review for rule-level rights findings.",
        ],
    }


def security_review(config_path: str | None = None, limit: int = 200) -> dict[str, Any]:
    graph = build_metadata_graph(str(_config_path(config_path)))
    roles = [obj for obj in graph["objects"] if obj["type"] == "Role"]
    findings: list[dict[str, Any]] = []
    by_right: Counter[str] = Counter()
    total_rights = 0
    dangerous_total = 0
    roles_with_rights = 0

    for role in roles:
        details = get_metadata_object(role["ref"], graph["config_path"])
        rights = details.get("rights") if details else None
        if not rights:
            findings.append(
                {
                    "role": role["ref"],
                    "severity": "low",
                    "code": "role-without-rights",
                    "message": "Role has no Rights.xml or rights could not be parsed.",
                    "details": {"path": role["path"]},
                }
            )
            continue

        roles_with_rights += 1
        total_rights += int(rights.get("rights") or 0)
        dangerous_total += int(rights.get("dangerous_total") or 0)
        by_right.update(rights.get("by_right") or {})

        if rights.get("dangerous_total"):
            findings.append(
                {
                    "role": role["ref"],
                    "severity": "high",
                    "code": "dangerous-rights",
                    "message": "Role grants write/delete/admin-class rights.",
                    "details": {
                        "dangerous_total": rights["dangerous_total"],
                        "examples": rights.get("dangerous", [])[:10],
                        "rights_path": rights.get("path"),
                    },
                }
            )
        if int(rights.get("rights") or 0) > 5000:
            findings.append(
                {
                    "role": role["ref"],
                    "severity": "medium",
                    "code": "broad-role",
                    "message": "Role grants a very broad rights surface.",
                    "details": {"rights": rights["rights"], "objects": rights.get("objects", 0)},
                }
            )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["role"], item["code"]))

    return {
        "summary": {
            "roles": len(roles),
            "roles_with_rights": roles_with_rights,
            "total_rights": total_rights,
            "dangerous_rights": dangerous_total,
            "findings": len(findings),
            "by_right": dict(by_right.most_common(20)),
        },
        "findings": findings[:limit],
        "caveats": [
            "Security review is static EDT rights analysis. It must be combined with privileged-code and integration exposure review.",
        ],
    }


def _form_ext_path(config_path: Path, form_path: str) -> Path:
    rel = Path(form_path.replace("\\", "/"))
    return config_path / rel.parent / rel.stem / "Ext" / "Form.xml"


def _form_module_path(config_path: Path, module_path: str | None) -> Path | None:
    if not module_path:
        return None
    path = config_path / module_path
    return path if path.exists() else None


def _form_metrics(ext_root) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    excluded_commands = []
    default_buttons = 0
    if ext_root is None:
        return {"parse_error": True, "counts": {}, "excluded_commands": [], "default_buttons": 0}
    for elem in ext_root.iter():
        tag = _local(elem.tag)
        if tag in {"Button", "Popup", "ButtonGroup", "Table", "Group", "InputField", "Command"}:
            counts[tag] += 1
        if tag == "ExcludedCommand" and elem.text:
            excluded_commands.append(elem.text.strip())
        if tag == "DefaultButton" and (elem.text or "").strip().lower() == "true":
            default_buttons += 1
    return {
        "parse_error": False,
        "counts": dict(counts),
        "excluded_commands": excluded_commands,
        "default_buttons": default_buttons,
    }


def review_forms(
    identifier: str,
    *,
    form_name: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    config = _config_path(config_path)
    obj = get_metadata_object(identifier, str(config))
    if obj is None:
        raise ValueError(f"Metadata object not found: {identifier}")

    reviewed = []
    total_findings = 0
    for form in obj.get("forms", []):
        if form_name and form_name.casefold() not in form["name"].casefold():
            continue

        ext_path = _form_ext_path(config, form["path"])
        ext_root = _safe_parse(ext_path)
        metrics = _form_metrics(ext_root)
        findings: list[dict[str, Any]] = []

        if metrics["parse_error"]:
            findings.append(
                {
                    "severity": "medium",
                    "code": "form-xml-missing",
                    "message": "Form layout XML is missing or could not be parsed.",
                    "details": {"path": str(ext_path)},
                }
            )

        button_count = int(metrics["counts"].get("Button", 0))
        popup_count = int(metrics["counts"].get("Popup", 0))
        table_count = int(metrics["counts"].get("Table", 0))
        excluded = set(metrics["excluded_commands"])

        if button_count > 80:
            findings.append(
                {
                    "severity": "medium",
                    "code": "large-command-surface",
                    "message": "Form has many buttons; review command grouping and role-specific UX.",
                    "details": {"buttons": button_count},
                }
            )
        if popup_count > 20:
            findings.append(
                {
                    "severity": "low",
                    "code": "many-popups",
                    "message": "Form has many popups; review discoverability and command hierarchy.",
                    "details": {"popups": popup_count},
                }
            )
        if obj["type"] == "Document" and {"Post", "PostAndClose", "Write"} & excluded:
            findings.append(
                {
                    "severity": "medium",
                    "code": "document-core-commands-excluded",
                    "message": "Document form excludes write/post commands; confirm business process and permissions.",
                    "details": {"excluded": sorted({"Post", "PostAndClose", "Write"} & excluded)},
                }
            )
        if button_count and not metrics["default_buttons"]:
            findings.append(
                {
                    "severity": "low",
                    "code": "no-default-button",
                    "message": "No default button was detected for a command-heavy form.",
                    "details": {"buttons": button_count},
                }
            )
        if table_count > 12:
            findings.append(
                {
                    "severity": "low",
                    "code": "many-tables",
                    "message": "Form has many table controls; review tab order and repeated workflows.",
                    "details": {"tables": table_count},
                }
            )

        module_path = _form_module_path(config, form.get("module_path"))
        diagnostics = None
        if module_path is not None:
            text = module_path.read_text(encoding="utf-8", errors="ignore")
            diagnostics = analyze_bsl(text, module_path=form.get("module_path"))
            for diag in diagnostics["diagnostics"][:10]:
                findings.append(
                    {
                        "severity": diag["severity"],
                        "code": f"form-module:{diag['code']}",
                        "message": diag["message"],
                        "details": {"line": diag["line"], **diag.get("details", {})},
                    }
                )
        else:
            findings.append(
                {
                    "severity": "low",
                    "code": "form-module-missing",
                    "message": "Form has no BSL module; verify that behavior is declarative by design.",
                    "details": {"module_path": form.get("module_path")},
                }
            )

        total_findings += len(findings)
        reviewed.append(
            {
                "form": form,
                "ext_path": ext_path.relative_to(config).as_posix() if ext_path.exists() else str(ext_path),
                "metrics": metrics,
                "diagnostics": diagnostics,
                "findings": findings,
            }
        )

    return {
        "object": {
            "type": obj["type"],
            "name": obj["name"],
            "ref": obj["ref"],
            "path": obj["path"],
        },
        "forms": reviewed,
        "summary": {"forms_reviewed": len(reviewed), "findings": total_findings},
        "caveats": [
            "Form review is deterministic static EDT XML and form-module analysis. It does not replace UX validation with users.",
        ],
    }
