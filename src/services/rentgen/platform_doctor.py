"""Local Platform Doctor for 1C platform and operations readiness."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rentgen.metadata_graph import DEFAULT_CONFIG_PATH
from src.services.rentgen.path_safety import confine_path


VERSION_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return ""


def _parse_version(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    match = VERSION_RE.search(value)
    if not match:
        return None
    parts = [int(part or 0) for part in match.groups()]
    return tuple(parts)  # type: ignore[return-value]


def _version_gte(value: str | None, minimum: tuple[int, int, int, int]) -> bool | None:
    parsed = _parse_version(value)
    if parsed is None:
        return None
    return parsed >= minimum


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


def _path_info(raw: str) -> dict[str, Any]:
    if not raw:
        return {"configured": False, "path": "", "exists": False}
    path = Path(raw).expanduser()
    return {"configured": True, "path": str(path), "exists": path.exists()}


def _count_extensions(config_path: Path) -> int:
    if not config_path.exists():
        return 0
    candidates = ["Extensions", "Расширения", "Ext"]
    total = 0
    for name in candidates:
        folder = config_path / name
        if folder.exists():
            try:
                total += sum(1 for item in folder.iterdir() if item.is_dir() or item.suffix.lower() in {".cfe", ".xml"})
            except OSError:
                pass
    return total


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
    high = sum(1 for item in checks if item["status"] != "pass" and item["severity"] == "high")
    medium = sum(1 for item in checks if item["status"] != "pass" and item["severity"] == "medium")
    if high:
        status = "risk"
        headline = "Обновление платформы требует подготовки: есть критичные неизвестные или отсутствующие источники."
    elif score >= 86 and medium == 0:
        status = "ready"
        headline = "Платформенный контур описан достаточно для пилотного upgrade/readiness решения."
    else:
        status = "watch"
        headline = "Платформенный контур частично описан; нужны дополнительные ops-сигналы."
    return {"status": status, "score": score, "headline": headline}


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Platform Doctor",
        "",
        f"Status: **{report['decision']['status'].upper()}**",
        f"Score: **{report['decision']['score']}**",
        f"Current platform: `{report['inventory']['platform_version'] or 'unknown'}`",
        f"Target platform: `{report['inventory']['target_platform_version'] or 'unknown'}`",
        "",
        "## Checks",
        "",
    ]
    for item in report["checks"]:
        lines.append(f"- **{item['status']} / {item['severity']}** {item['title']}: {item['action']}")
    lines.extend(["", "## Upgrade checklist", ""])
    lines.extend(f"- {item}" for item in report["upgrade"]["checklist"])
    return "\n".join(lines)


def build_platform_doctor(
    *,
    config_path: str | None = None,
    target_platform_version: str | None = None,
) -> dict[str, Any]:
    """Build a local, deterministic platform readiness report.

    V1 is intentionally an inventory/readiness doctor: it does not probe network
    services and does not claim compatibility facts that were not provided by
    env/config files. Unknowns are surfaced as caveats and checklist items.
    """

    # Confine a caller-supplied config_path to the allowed data roots before any
    # filesystem access (arbitrary-file-read / traversal guard). A path outside
    # them raises ValueError, mapped to HTTP 400 by the API. The default path is
    # already a trusted repo location and is not confined.
    if config_path:
        config = confine_path(config_path, label="config_path")
    else:
        config = DEFAULT_CONFIG_PATH.resolve()
    config_xml = config / "Configuration.xml"
    root = _safe_parse(config_xml)
    configuration_version = _xml_text(root, "Version")
    configuration_name = _xml_text(root, "Name")
    compatibility_mode = _env("ONEC_COMPATIBILITY_MODE", "PLATFORM_COMPATIBILITY_MODE") or _xml_text(
        root,
        "CompatibilityMode",
        "DefaultCompatibilityMode",
    )
    platform_version = _env("ONEC_PLATFORM_VERSION", "PLATFORM_VERSION", "1C_PLATFORM_VERSION")
    target_version = target_platform_version or _env("ONEC_TARGET_PLATFORM_VERSION", "TARGET_PLATFORM_VERSION")
    dbms = _env("ONEC_DBMS", "DBMS", "DATABASE_ENGINE")
    cluster = _env("ONEC_CLUSTER", "ONEC_CLUSTER_HOST", "RAC_CLUSTER")
    infobase_mode = _env("ONEC_INFOBASE_MODE", "INFOBASE_MODE", "ONEC_SERVER_MODE")
    clients = _env("ONEC_CLIENTS", "ONEC_CLIENT_MODES")
    tech_journal = _path_info(_env("ONEC_TECH_JOURNAL_PATH", "TECH_JOURNAL_PATH", "TJ_PATH"))
    license_events = _path_info(_env("ONEC_LICENSE_EVENTS_PATH", "LICENSE_EVENTS_PATH"))
    openmetrics = _env("ONEC_OPENMETRICS_URL", "OPENMETRICS_URL", "PROMETHEUS_EXPORTER_URL")
    extensions_count = _count_extensions(config)
    checks: list[dict[str, Any]] = []

    _check(
        checks,
        id="configuration-source",
        title="EDT/XML конфигурация доступна",
        status="pass" if config_xml.exists() else "warn",
        severity="medium",
        evidence={"config_path": str(config), "configuration_xml": config_xml.exists()},
        action="Подключите EDT/XML выгрузку, чтобы связать platform readiness с метаданными.",
    )
    _check(
        checks,
        id="platform-version",
        title="Версия платформы 1С задана",
        status="pass" if platform_version else "warn",
        severity="high",
        evidence={"ONEC_PLATFORM_VERSION": platform_version},
        action="Задайте ONEC_PLATFORM_VERSION, например 8.3.25.x, из продуктивного контура.",
    )
    _check(
        checks,
        id="target-platform-version",
        title="Целевая версия платформы задана",
        status="pass" if target_version else "warn",
        severity="medium",
        evidence={"ONEC_TARGET_PLATFORM_VERSION": target_version},
        action="Задайте ONEC_TARGET_PLATFORM_VERSION для upgrade checklist и сравнения.",
    )
    _check(
        checks,
        id="compatibility-mode",
        title="Режим совместимости известен",
        status="pass" if compatibility_mode else "warn",
        severity="high",
        evidence={"compatibility_mode": compatibility_mode},
        action="Экспортируйте режим совместимости из конфигурации или задайте ONEC_COMPATIBILITY_MODE.",
    )
    _check(
        checks,
        id="dbms",
        title="СУБД контура известна",
        status="pass" if dbms else "warn",
        severity="medium",
        evidence={"dbms": dbms},
        action="Задайте ONEC_DBMS: PostgreSQL, MS SQL, Oracle, IBM DB2 или file.",
    )
    _check(
        checks,
        id="cluster",
        title="Кластер/режим инфобазы описан",
        status="pass" if cluster or infobase_mode else "warn",
        severity="medium",
        evidence={"cluster": cluster, "infobase_mode": infobase_mode},
        action="Задайте ONEC_CLUSTER/ONEC_INFOBASE_MODE для оценки серверного профиля.",
    )
    _check(
        checks,
        id="tech-journal",
        title="Технологический журнал подключен",
        status="pass" if tech_journal["exists"] else "warn",
        severity="high",
        evidence=tech_journal,
        action="Подключите TECH_JOURNAL_PATH/ONEC_TECH_JOURNAL_PATH для Lock Radar и RCA.",
    )
    _check(
        checks,
        id="openmetrics",
        title="OpenMetrics/monitoring endpoint задан",
        status="pass" if openmetrics else "warn",
        severity="medium",
        evidence={"openmetrics_url": openmetrics},
        action="Задайте ONEC_OPENMETRICS_URL или PROMETHEUS_EXPORTER_URL для runtime метрик.",
    )
    _check(
        checks,
        id="license-events",
        title="События лицензирования доступны",
        status="pass" if license_events["exists"] else "warn",
        severity="low",
        evidence=license_events,
        action="Подключите LICENSE_EVENTS_PATH, если нужно доказать лицензионные риски.",
    )

    current_supports_8325 = _version_gte(platform_version, (8, 3, 25, 0))
    target_supports_8325 = _version_gte(target_version, (8, 3, 25, 0))
    capabilities = [
        {
            "id": "openmetrics-8325",
            "title": "OpenMetrics и расширенные runtime-сигналы",
            "available": bool(current_supports_8325 or target_supports_8325),
            "evidence": {
                "current_platform_version": platform_version,
                "target_platform_version": target_version,
                "rule": ">= 8.3.25 if version is provided",
            },
        },
        {
            "id": "tech-journal-rca",
            "title": "RCA по технологическому журналу",
            "available": bool(tech_journal["exists"]),
            "evidence": tech_journal,
        },
        {
            "id": "extension-safety",
            "title": "Extension Safety inventory",
            "available": extensions_count > 0,
            "evidence": {"extensions_count": extensions_count},
        },
    ]

    checklist = [
        "Зафиксировать текущую и целевую версии платформы.",
        "Проверить режим совместимости и отключенные/устаревшие возможности.",
        "Прогнать Change Impact по критичным модулям релиза.",
        "Подключить технологический журнал и OpenMetrics до нагрузочного окна.",
        "Собрать тест-план по affected modules и релизный gate.",
        "Отдельно проверить расширения и прямые изменения типовой конфигурации.",
        "Подготовить rollback и evidence bundle для approval.",
    ]
    if not platform_version:
        checklist.insert(0, "Добавить ONEC_PLATFORM_VERSION из продуктивного контура.")
    if not target_version:
        checklist.insert(1, "Добавить ONEC_TARGET_PLATFORM_VERSION перед upgrade decision.")
    if not tech_journal["exists"]:
        checklist.append("Подключить TECH_JOURNAL_PATH, иначе блокировки и таймауты останутся без RCA.")

    score = _score(checks)
    report = {
        "generated_at": _now(),
        "config_path": str(config),
        "decision": _decision(score, checks),
        "inventory": {
            "configuration_name": configuration_name,
            "configuration_version": configuration_version,
            "platform_version": platform_version,
            "target_platform_version": target_version,
            "compatibility_mode": compatibility_mode,
            "dbms": dbms,
            "cluster": cluster,
            "infobase_mode": infobase_mode,
            "clients": clients,
            "tech_journal": tech_journal,
            "openmetrics_url": openmetrics,
            "license_events": license_events,
            "extensions_count": extensions_count,
        },
        "checks": checks,
        "capabilities": capabilities,
        "upgrade": {
            "from": platform_version,
            "to": target_version,
            "readiness": "ready" if score >= 86 else "needs-data" if score >= 60 else "blocked",
            "checklist": checklist,
        },
        "caveats": [
            "Platform Doctor v1 uses local files and environment variables only; it does not probe production services.",
            "Unknown platform facts are shown as warnings, not inferred as safe.",
            "Compatibility with a concrete 1C release must be validated against customer test base and vendor release notes.",
        ],
    }
    report["markdown"] = _markdown(report)
    return report
