"""Update War Room for 1C platform/configuration upgrade planning."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rentgen.change_plan import dedupe, extract_diff_modules
from src.services.rentgen.intake_wizard import build_intake_plan
from src.services.rentgen.metadata_graph import DEFAULT_CONFIG_PATH
from src.services.rentgen.platform_doctor import build_platform_doctor
from src.services.rentgen.release_readiness import build_release_readiness


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _safe_parse(path: Path) -> ET.Element | None:
    if not path.exists():
        return None
    try:
        return ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None


def _xml_text(root: ET.Element | None, *names: str) -> str:
    if root is None:
        return ""
    wanted = {name.casefold() for name in names}
    for node in root.iter():
        if _local(node.tag).casefold() in wanted and node.text:
            return node.text.strip()
    return ""


def _configuration(config_path: Path) -> dict[str, Any]:
    root = _safe_parse(config_path / "Configuration.xml")
    return {
        "path": str(config_path),
        "exists": (config_path / "Configuration.xml").exists(),
        "name": _xml_text(root, "Name") or "1C configuration",
        "version": _xml_text(root, "Version"),
        "vendor": _xml_text(root, "Vendor"),
        "compatibility_mode": _xml_text(
            root, "CompatibilityMode", "DefaultCompatibilityMode"
        ),
    }


def _extension_inventory(config_path: Path, limit: int = 40) -> dict[str, Any]:
    roots = [config_path / "Extensions", config_path / "Расширения"]
    items: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        try:
            children = sorted(root.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for item in children:
            if len(items) >= limit:
                break
            if item.is_dir() or item.suffix.casefold() in {".cfe", ".xml"}:
                items.append(
                    {
                        "name": item.stem if item.is_file() else item.name,
                        "path": str(item),
                        "kind": "folder"
                        if item.is_dir()
                        else item.suffix.lower().lstrip("."),
                    }
                )
    try:
        for item in sorted(
            config_path.glob("*.cfe"), key=lambda value: value.name.casefold()
        ):
            if len(items) >= limit:
                break
            items.append({"name": item.stem, "path": str(item), "kind": "cfe"})
    except OSError:
        pass
    return {
        "count": len(items),
        "items": items,
        "truncated": len(items) >= limit,
    }


def _check(
    checks: list[dict[str, Any]],
    *,
    id: str,
    title: str,
    status: str,
    severity: str,
    evidence: Any,
    action: str,
) -> None:
    checks.append(
        {
            "id": id,
            "title": title,
            "status": status,
            "severity": severity,
            "evidence": evidence,
            "action": action,
        }
    )


def _score(checks: list[dict[str, Any]]) -> int:
    penalty = 0
    for item in checks:
        if item["status"] == "pass":
            continue
        if item["severity"] == "high":
            penalty += 18
        elif item["severity"] == "medium":
            penalty += 10
        else:
            penalty += 5
    return max(0, 100 - penalty)


def _decision(score: int, checks: list[dict[str, Any]]) -> dict[str, Any]:
    high_fail = any(
        item["status"] == "fail" and item["severity"] == "high" for item in checks
    )
    high_attention = any(
        item["status"] != "pass" and item["severity"] == "high" for item in checks
    )
    if high_fail or score < 60:
        status = "risk"
        headline = "Обновление нельзя обещать без закрытия критичных unknowns, impact или платформенных рисков."
    elif score >= 84 and not high_attention:
        status = "ready"
        headline = "Есть достаточно evidence для пилотного update/upgrade окна с rollback и release gate."
    else:
        status = "watch"
        headline = "Update plan собран, но часть платформенных, тестовых или extension-фактов требует подтверждения."
    return {"status": status, "score": score, "headline": headline}


def _release_compact(
    *,
    store: Any,
    modules: list[str],
    diff: str | None,
    release_name: str | None,
    include_security: bool,
) -> tuple[dict[str, Any], list[str]]:
    caveats: list[str] = []
    if not modules:
        caveats.append(
            "Change set is not provided; release impact and affected tests are not measured."
        )
        return {"included": False, "reason": "no-change-set"}, caveats
    if store is None:
        caveats.append(
            "Rentgen store is not built; release impact cannot be measured for update war room."
        )
        return {
            "included": False,
            "reason": "store-not-built",
            "changed_modules": modules,
        }, caveats
    try:
        report = build_release_readiness(
            store,
            changed_modules=modules,
            diff=diff,
            release_name=release_name,
            include_security=include_security,
            include_forms=True,
            hotspot_limit=10,
            max_edges=600,
            fail_on_high=True,
        )
    except Exception as exc:  # pragma: no cover - defensive composition layer
        caveats.append(f"Release readiness failed: {exc}")
        return {
            "included": False,
            "reason": "release-readiness-error",
            "error": str(exc),
        }, caveats

    return {
        "included": True,
        "release_name": report["release_name"],
        "decision": report["decision"],
        "summary": report["summary"],
        "gate": {
            "status": report["gate"].get("status"),
            "violations": report["gate"].get("violations", [])[:20],
            "summary": report["gate"].get("summary", {}),
        },
        "tests": {
            key: value
            for key, value in report.get("tests", {}).items()
            if key != "items"
        },
        "recommended_actions": report.get("recommended_actions", [])[:20],
    }, caveats


def _checks(
    *,
    config: dict[str, Any],
    intake: dict[str, Any],
    platform: dict[str, Any],
    extensions: dict[str, Any],
    release: dict[str, Any],
    target_platform_version: str | None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    intake_status = (intake.get("decision") or {}).get("status")
    platform_status = (platform.get("decision") or {}).get("status")
    release_decision = release.get("decision") or {}
    release_status = release_decision.get("status")
    tests = release.get("tests") or {}

    _check(
        checks,
        id="configuration-source",
        title="Источник конфигурации доступен",
        status="pass"
        if config.get("exists") and intake_status in {"ready", "partial"}
        else "fail",
        severity="high",
        evidence={
            "configuration_xml": config.get("exists"),
            "intake_status": intake_status,
        },
        action="Подключите EDT/XML выгрузку до update decision.",
    )
    _check(
        checks,
        id="target-platform",
        title="Целевая платформа задана",
        status="pass" if target_platform_version else "warn",
        severity="medium",
        evidence={"target_platform_version": target_platform_version or ""},
        action="Укажите целевую версию платформы/релиза, чтобы план был проверяемым.",
    )
    _check(
        checks,
        id="platform-doctor",
        title="Platform Doctor не блокирует окно",
        status="pass"
        if platform_status == "ready"
        else "fail"
        if platform_status == "risk"
        else "warn",
        severity="high",
        evidence=platform.get("decision", {}),
        action="Закройте platform-version, compatibility, DBMS, техжурнал и OpenMetrics caveats.",
    )
    _check(
        checks,
        id="extension-safety",
        title="Расширения вынесены в отдельную проверку",
        status="warn" if extensions["count"] else "pass",
        severity="medium",
        evidence={
            "extensions_count": extensions["count"],
            "truncated": extensions["truncated"],
        },
        action="Проверить заимствованные объекты, переопределенные формы/команды и конфликт с обновлением.",
    )
    _check(
        checks,
        id="release-impact",
        title="Impact релиза измерен",
        status=(
            "pass"
            if release.get("included") and release_status == "pass"
            else "fail"
            if release.get("included") and release_status == "fail"
            else "warn"
        ),
        severity="high",
        evidence={
            "included": release.get("included", False),
            "release_status": release_status,
            "changed_modules": (release.get("summary") or {}).get(
                "changed_modules", release.get("changed_modules", 0)
            ),
        },
        action="Перед update window прогнать Release Readiness по diff/modules.",
    )
    _check(
        checks,
        id="affected-tests",
        title="Affected tests определены",
        status="pass" if int(tests.get("mapped") or 0) else "warn",
        severity="medium",
        evidence=tests or {"included": False},
        action="Собрать smoke/regression/manual checks для affected modules и missing tests.",
    )
    _check(
        checks,
        id="rollback-evidence",
        title="Rollback/evidence пакет запланирован",
        status="warn",
        severity="medium",
        evidence={"required": True},
        action="Зафиксировать backup, rollback, approval, владельцев и evidence bundle до окна.",
    )
    return checks


def _workstreams(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks = {item["id"]: item for item in report["checks"]}
    return [
        {
            "id": "merge",
            "title": "Сравнение и merge",
            "owner": "architect",
            "status": checks["configuration-source"]["status"],
            "evidence": checks["configuration-source"]["evidence"],
            "action": "Собрать baseline, vendor release, прямые изменения и конфликтующие объекты.",
            "to": "/metadata",
        },
        {
            "id": "platform",
            "title": "Платформенное окно",
            "owner": "ops",
            "status": checks["platform-doctor"]["status"],
            "evidence": checks["platform-doctor"]["evidence"],
            "action": "Закрыть Platform Doctor checklist и runtime наблюдаемость.",
            "to": "/platform-doctor",
        },
        {
            "id": "extensions",
            "title": "Extension Safety",
            "owner": "architect",
            "status": checks["extension-safety"]["status"],
            "evidence": checks["extension-safety"]["evidence"],
            "action": "Проверить расширения отдельно от типовой конфигурации.",
            "to": "/extension-safety",
        },
        {
            "id": "release-gate",
            "title": "Release gate",
            "owner": "release",
            "status": checks["release-impact"]["status"],
            "evidence": checks["release-impact"]["evidence"],
            "action": "Получить go/no-go, тесты и actions по измененным модулям.",
            "to": "/release-readiness",
        },
        {
            "id": "rollback",
            "title": "Rollback и evidence",
            "owner": "director",
            "status": checks["rollback-evidence"]["status"],
            "evidence": checks["rollback-evidence"]["evidence"],
            "action": "Утвердить окно, backup, ответственных и критерии отката.",
            "to": "/team-governance",
        },
    ]


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Update War Room",
        "",
        f"Release: **{report['release_name']}**",
        f"Configuration: **{report['configuration']['name']}** {report['configuration'].get('version') or ''}",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        "",
        "## Checks",
        "",
    ]
    for item in report["checks"]:
        lines.append(
            f"- **{item['status']} / {item['severity']}** {item['title']}: {item['action']}"
        )
    lines.extend(["", "## Workstreams", ""])
    for item in report["workstreams"]:
        lines.append(f"- **{item['owner']}** {item['title']}: {item['action']}")
    if report["caveats"]:
        lines.extend(["", "## Caveats", ""])
        lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_update_war_room(
    store: Any = None,
    *,
    config_path: str | None = None,
    target_platform_version: str | None = None,
    release_name: str | None = None,
    changed_modules: list[str] | None = None,
    diff: str | None = None,
    include_security: bool = False,
) -> dict[str, Any]:
    """Build a deterministic upgrade/update plan with evidence and caveats."""

    config_root = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
    config_root = config_root.resolve()
    modules = dedupe(list(changed_modules or []) + extract_diff_modules(diff))
    platform = build_platform_doctor(
        config_path=str(config_root),
        target_platform_version=target_platform_version,
    )
    intake = build_intake_plan(str(config_root), "auto")
    config = _configuration(config_root)
    extensions = _extension_inventory(config_root)
    release, release_caveats = _release_compact(
        store=store,
        modules=modules,
        diff=diff,
        release_name=release_name,
        include_security=include_security,
    )
    checks = _checks(
        config=config,
        intake=intake,
        platform=platform,
        extensions=extensions,
        release=release,
        target_platform_version=target_platform_version,
    )
    score = _score(checks)
    report: dict[str, Any] = {
        "generated_at": _now(),
        "release_name": release_name or "Update candidate",
        "config_path": str(config_root),
        "configuration": config,
        "decision": _decision(score, checks),
        "summary": {
            "checks": len(checks),
            "attention": sum(1 for item in checks if item["status"] != "pass"),
            "extensions": extensions["count"],
            "changed_modules": len(modules),
            "target_platform_version": target_platform_version or "",
            "release_impact_measured": bool(release.get("included")),
        },
        "checks": checks,
        "extensions": extensions,
        "platform": {
            "decision": platform.get("decision", {}),
            "upgrade": platform.get("upgrade", {}),
            "inventory": platform.get("inventory", {}),
        },
        "intake": {
            "decision": intake.get("decision", {}),
            "inventory": intake.get("inventory", {}),
        },
        "release": release,
        "caveats": [
            *release_caveats,
            *list(intake.get("caveats") or [])[:4],
            *list(platform.get("caveats") or [])[:4],
            "Update War Room v1 does not compare vendor CF/DT packages directly yet; it plans the evidence gate around local EDT/XML sources.",
        ],
    }
    report["workstreams"] = _workstreams(report)
    report["markdown"] = _markdown(report)
    return report
