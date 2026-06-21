"""Extension safety inventory and release-risk checks for 1C configurations."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rentgen.change_plan import dedupe
from src.services.rentgen.metadata_graph import DEFAULT_CONFIG_PATH
from src.services.rentgen.path_safety import collect_files, confine_path
from src.services.rentgen.test_coverage_matrix import build_test_coverage_matrix


EXTENSION_ROOTS = ("Extensions", "Расширения")
OBJECT_MARKERS = {
    "commonmodules",
    "documents",
    "catalogs",
    "reports",
    "dataprocessors",
    "informationregisters",
    "accumulationregisters",
    "accountingregisters",
    "businessprocesses",
    "tasks",
}
TEXT_SUFFIXES = {".bsl", ".xml", ".txt", ".json", ".md"}
RISK_PATTERNS = (
    ("privileged-mode", "high", ("setprivilegedmode", "установитьпривилегированныйрежим", "привилегированныйрежим")),
    ("explicit-transaction", "medium", ("begintransaction", "начатьтранзакцию", "зафиксироватьтранзакцию")),
    ("write-event", "medium", ("передзаписью", "призаписи", "обработкапроведения", "приwrite", "beforewrite")),
    ("background-job", "medium", ("регламентноезадание", "scheduledjob", "backgroundjob")),
    ("unsafe-query", "medium", ("левое соединение", "left join", "полное соединение", "full join")),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extension_roots(config_path: Path) -> list[Path]:
    roots = [config_path / name for name in EXTENSION_ROOTS]
    return [root for root in roots if root.exists()]


def _safe_text(path: Path, limit: int = 250_000) -> str:
    if path.suffix.casefold() not in TEXT_SUFFIXES:
        return ""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def _discover_extension_paths(config_path: Path, limit: int) -> tuple[list[Path], list[str]]:
    items: list[Path] = []
    caveats: list[str] = []
    for root in _extension_roots(config_path):
        try:
            children = sorted(root.iterdir(), key=lambda item: item.name.casefold())
        except OSError as exc:
            caveats.append(f"Cannot read extension root {root}: {exc}")
            continue
        for item in children:
            if len(items) >= limit:
                break
            if item.is_dir() or item.suffix.casefold() in {".cfe", ".xml"}:
                items.append(item)
    try:
        for item in sorted(config_path.glob("*.cfe"), key=lambda value: value.name.casefold()):
            if len(items) >= limit:
                break
            items.append(item)
    except OSError as exc:
        caveats.append(f"Cannot read root CFE files: {exc}")
    if len(items) >= limit:
        caveats.append(f"Extension inventory was truncated at {limit} items.")
    return items, caveats


def _iter_files(path: Path, max_files: int) -> tuple[list[Path], bool]:
    if path.is_file():
        return [path], False
    # Bounded, symlink-safe recursive walk so a hostile/huge extension tree
    # cannot DoS the analyzer. ``truncated`` is surfaced as files_truncated so a
    # capped scan is never reported as a complete count.
    try:
        return collect_files(path, max_files=max_files)
    except OSError:
        return [], True


def _relative_parts(path: Path, root: Path) -> list[str]:
    try:
        return list(path.relative_to(root).parts)
    except ValueError:
        return list(path.parts)


def _canonical_module_ref(path: Path, extension_path: Path) -> str | None:
    if path.suffix.casefold() != ".bsl":
        return None
    parts = _relative_parts(path, extension_path)
    lowered = [part.casefold() for part in parts]
    for index, value in enumerate(lowered):
        if value in OBJECT_MARKERS:
            return "/".join(parts[index:])
    return "/".join(parts[-4:]) if len(parts) >= 4 else "/".join(parts)


def _object_ref(path: Path, extension_path: Path) -> str | None:
    parts = _relative_parts(path, extension_path)
    lowered = [part.casefold() for part in parts]
    for index, value in enumerate(lowered[:-1]):
        if value in OBJECT_MARKERS:
            return "/".join(parts[index : min(index + 3, len(parts))])
    return None


def _signals_for_file(path: Path, extension_path: Path) -> list[dict[str, Any]]:
    text = _safe_text(path)
    haystack = f"{path.as_posix()}\n{text}".casefold().replace(" ", "")
    signals = []

    if "roles/" in path.as_posix().casefold() or "rights" in path.name.casefold() or "права" in path.name.casefold():
        signals.append(
            {
                "id": "rights-surface",
                "severity": "medium",
                "title": "Extension changes rights surface",
                "path": str(path),
            }
        )

    for signal_id, severity, tokens in RISK_PATTERNS:
        if any(token.casefold().replace(" ", "") in haystack for token in tokens):
            signals.append(
                {
                    "id": signal_id,
                    "severity": severity,
                    "title": signal_id.replace("-", " ").title(),
                    "path": str(path),
                }
            )

    if "borrow" in haystack or "заимств" in haystack:
        signals.append(
            {
                "id": "borrowed-object",
                "severity": "medium",
                "title": "Borrowed object or borrowed-object metadata detected",
                "path": str(path),
            }
        )
    return signals


def _extension_item(path: Path, *, max_files: int) -> dict[str, Any]:
    files, truncated = _iter_files(path, max_files=max_files)
    suffix_counts = Counter(item.suffix.casefold() or "<none>" for item in files)
    bsl_modules = dedupe([ref for item in files if (ref := _canonical_module_ref(item, path))])
    objects = dedupe([ref for item in files if (ref := _object_ref(item, path))])
    signals: list[dict[str, Any]] = []
    for item in files:
        signals.extend(_signals_for_file(item, path))

    signal_counts = Counter(signal["id"] for signal in signals)
    severity_counts = Counter(signal["severity"] for signal in signals)
    return {
        "name": path.stem if path.is_file() else path.name,
        "path": str(path),
        "kind": "folder" if path.is_dir() else path.suffix.lower().lstrip("."),
        "files": len(files),
        "files_truncated": truncated,
        "bsl_files": int(suffix_counts.get(".bsl") or 0),
        "xml_files": int(suffix_counts.get(".xml") or 0),
        "rights_files": int(signal_counts.get("rights-surface") or 0),
        "borrowed_objects": int(signal_counts.get("borrowed-object") or 0),
        "modules": bsl_modules[:40],
        "objects": objects[:60],
        "signals": signals[:80],
        "severity_counts": dict(severity_counts),
        "signal_counts": dict(signal_counts),
    }


def _module_impact(
    store: Any,
    modules: list[str],
    *,
    max_depth: int,
    max_edges: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    if store is None or not modules:
        return [], []

    rows = []
    caveats = []
    for module in modules[:30]:
        try:
            impact = store.module_impact(module, max_depth=max_depth, max_edges=max_edges)
            quality = store.get_module_risk(module)
        except Exception as exc:  # pragma: no cover - defensive integration guard
            caveats.append(f"Impact analysis failed for extension module {module}: {exc}")
            continue
        rows.append(
            {
                "module_ref": module,
                "canonical": impact.get("canonical", {}),
                "graph_modules": impact.get("graph_modules", []),
                "impact_total": int(impact.get("total") or 0),
                "impacted_modules": impact.get("impacted_modules", [])[:25],
                "quality": quality,
            }
        )
    rows.sort(
        key=lambda item: (
            int((item.get("quality") or {}).get("risk") or 0),
            int(item.get("impact_total") or 0),
        ),
        reverse=True,
    )
    return rows, caveats


def _test_matrix(
    store: Any,
    modules: list[str],
    *,
    max_depth: int,
    max_edges: int,
) -> tuple[dict[str, Any] | None, list[str]]:
    if store is None or not modules:
        return None, []
    try:
        return build_test_coverage_matrix(
            store,
            changed_modules=modules[:30],
            max_depth=max_depth,
            max_edges=max_edges,
            hotspot_limit=8,
            match_limit=8,
        ), []
    except Exception as exc:  # pragma: no cover - defensive integration guard
        return None, [f"Test coverage matrix failed for extension modules: {exc}"]


def _decision(
    *,
    source_exists: bool,
    extensions: list[dict[str, Any]],
    impact_rows: list[dict[str, Any]],
    test_matrix: dict[str, Any] | None,
) -> dict[str, Any]:
    if not source_exists:
        return {
            "status": "watch",
            "score": 0,
            "risk_score": 100,
            "headline": "Configuration source is missing; extension safety cannot be measured.",
        }
    if not extensions:
        return {
            "status": "ready",
            "score": 100,
            "risk_score": 0,
            "headline": "No local extensions were found in the supplied configuration source.",
        }

    severity = Counter()
    signal_counts = Counter()
    for item in extensions:
        severity.update(item.get("severity_counts") or {})
        signal_counts.update(item.get("signal_counts") or {})

    max_module_risk = max((int((row.get("quality") or {}).get("risk") or 0) for row in impact_rows), default=0)
    impact_total = sum(int(row.get("impact_total") or 0) for row in impact_rows)
    test_gaps = int(((test_matrix or {}).get("summary") or {}).get("gaps") or 0)
    risk_score = 0
    risk_score += min(20, len(extensions) * 5)
    risk_score += min(45, int(severity.get("high") or 0) * 18)
    risk_score += min(35, int(severity.get("medium") or 0) * 8)
    risk_score += min(18, int(signal_counts.get("rights-surface") or 0) * 6)
    risk_score += min(18, int(signal_counts.get("borrowed-object") or 0) * 5)
    risk_score += min(18, int(max_module_risk * 0.18))
    risk_score += min(15, int(impact_total / 80))
    risk_score += min(15, test_gaps * 5)
    risk_score = min(risk_score, 100)

    if risk_score >= 65 or severity.get("high"):
        status = "risk"
        headline = f"Extension safety needs owner review: {len(extensions)} extensions, risk {risk_score}."
    elif risk_score >= 25:
        status = "watch"
        headline = f"Extensions are present and need release-gate checks: risk {risk_score}."
    else:
        status = "ready"
        headline = "Extensions are inventoried with no high-risk deterministic signals."

    return {
        "status": status,
        "score": max(0, 100 - risk_score),
        "risk_score": risk_score,
        "headline": headline,
        "signals": dict(signal_counts),
        "max_module_risk": max_module_risk,
        "impact_total": impact_total,
        "test_gaps": test_gaps,
    }


def _actions(
    decision: dict[str, Any],
    extensions: list[dict[str, Any]],
    impact_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions = []
    risky = [
        item
        for item in extensions
        if int((item.get("severity_counts") or {}).get("high") or 0)
        or int((item.get("severity_counts") or {}).get("medium") or 0)
    ]
    rights = [item for item in extensions if int(item.get("rights_files") or 0)]
    borrowed = [item for item in extensions if int(item.get("borrowed_objects") or 0)]

    if risky:
        actions.append(
            {
                "owner": "architect",
                "severity": "high" if decision.get("status") == "risk" else "medium",
                "kind": "extension-review",
                "title": "Review risky extension hooks before update window",
                "target": risky[0]["name"],
                "details": {"extensions": [item["name"] for item in risky[:8]]},
            }
        )
    if rights:
        actions.append(
            {
                "owner": "security",
                "severity": "high",
                "kind": "rights",
                "title": "Validate rights changed by extensions separately from typical configuration",
                "target": rights[0]["name"],
                "details": {"extensions": [item["name"] for item in rights[:8]]},
            }
        )
    if borrowed:
        actions.append(
            {
                "owner": "architect",
                "severity": "medium",
                "kind": "borrowed-object",
                "title": "Compare borrowed objects against vendor update baseline",
                "target": borrowed[0]["name"],
                "details": {"extensions": [item["name"] for item in borrowed[:8]]},
            }
        )
    if impact_rows:
        actions.append(
            {
                "owner": "qa",
                "severity": "medium",
                "kind": "impact-tests",
                "title": "Add regression checks for extension module impact radius",
                "target": impact_rows[0]["module_ref"],
                "details": {
                    "impact_total": impact_rows[0].get("impact_total"),
                    "risk": (impact_rows[0].get("quality") or {}).get("risk"),
                },
            }
        )
    if not actions:
        actions.append(
            {
                "owner": "release",
                "severity": "low",
                "kind": "evidence",
                "title": "Attach extension inventory to update approval",
                "target": None,
                "details": {"extensions": len(extensions)},
            }
        )
    return actions


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Extension Safety",
        "",
        f"Generated: {report['generated_at']}",
        f"Status: **{report['decision']['status'].upper()}** / risk **{report['decision']['risk_score']}**",
        f"Source: `{report['source']['path']}`",
        "",
        "## Extensions",
        "",
    ]
    for item in report["extensions"]:
        lines.append(
            f"- **{item['name']}**: {item['files']} files, {len(item['modules'])} modules, "
            f"{len(item['signals'])} signals"
        )
    lines.extend(["", "## Actions", ""])
    lines.extend(f"- **{item['severity']}** {item['owner']}: {item['title']}" for item in report["recommended_actions"])
    if report["caveats"]:
        lines.extend(["", "## Caveats", ""])
        lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_extension_safety(
    store: Any = None,
    *,
    config_path: str | None = None,
    changed_modules: list[str] | None = None,
    extension_limit: int = 40,
    max_files_per_extension: int = 1200,
    max_depth: int = 5,
    max_edges: int = 300,
) -> dict[str, Any]:
    """Build a deterministic release-safety report for local 1C extensions."""

    # Confine a caller-supplied config_path to the allowed data roots before any
    # filesystem access (arbitrary-file-read / traversal guard). A path outside
    # them raises ValueError, mapped to HTTP 400 by the API. The default path is
    # already a trusted repo location and is not confined.
    if config_path:
        source = confine_path(config_path, label="config_path")
    else:
        source = DEFAULT_CONFIG_PATH.resolve()
    caveats: list[str] = []
    extension_paths: list[Path] = []
    if source.exists():
        extension_paths, caveats = _discover_extension_paths(source, extension_limit)
    else:
        caveats.append(f"Configuration source does not exist: {source}")

    extensions = [
        _extension_item(path, max_files=max_files_per_extension)
        for path in extension_paths
    ]
    extension_modules = dedupe(
        [
            module
            for item in extensions
            for module in item.get("modules", [])
        ]
    )
    modules = dedupe([*(changed_modules or []), *extension_modules])
    impact_rows, impact_caveats = _module_impact(
        store,
        modules,
        max_depth=max_depth,
        max_edges=max_edges,
    )
    test_matrix, test_caveats = _test_matrix(
        store,
        modules,
        max_depth=max_depth,
        max_edges=max_edges,
    )
    caveats.extend(impact_caveats)
    caveats.extend(test_caveats)
    if source.exists() and not extensions:
        caveats.append("No Extensions/Расширения folders or root .cfe files were found.")
    if store is None and modules:
        caveats.append("Rentgen store is unavailable; extension impact and test links are skipped.")

    severity = Counter()
    signal_counts = Counter()
    for item in extensions:
        severity.update(item.get("severity_counts") or {})
        signal_counts.update(item.get("signal_counts") or {})

    decision = _decision(
        source_exists=source.exists(),
        extensions=extensions,
        impact_rows=impact_rows,
        test_matrix=test_matrix,
    )
    report: dict[str, Any] = {
        "generated_at": _now(),
        "source": {
            "path": str(source),
            "exists": source.exists(),
        },
        "decision": decision,
        "summary": {
            "extensions": len(extensions),
            "modules": len(extension_modules),
            "objects": sum(len(item.get("objects", [])) for item in extensions),
            "signals": sum(len(item.get("signals", [])) for item in extensions),
            "high": int(severity.get("high") or 0),
            "medium": int(severity.get("medium") or 0),
            "rights_files": int(signal_counts.get("rights-surface") or 0),
            "borrowed_objects": int(signal_counts.get("borrowed-object") or 0),
            "impact_modules": len(impact_rows),
            "test_gaps": decision.get("test_gaps", 0),
        },
        "extensions": extensions,
        "modules": extension_modules,
        "impact": impact_rows,
        "test_matrix": test_matrix,
        "recommended_actions": _actions(decision, extensions, impact_rows),
        "checklist": [
            "Compare extension objects with the vendor update baseline before merge.",
            "Review privileged mode, explicit transactions and write event handlers.",
            "Validate rights/RLS changes outside the normal functional test path.",
            "Attach extension inventory to Update War Room and Evidence Bundle.",
        ],
        "caveats": dedupe(caveats),
    }
    report["markdown"] = _markdown(report)
    return report
