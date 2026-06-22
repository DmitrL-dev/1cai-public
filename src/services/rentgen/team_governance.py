"""Team ownership and governance board for the Rentgen graph."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
OWNER_MAP_PATH = REPO_ROOT / "data" / "team_owners.json"
SNAPSHOT_PATH = REPO_ROOT / "data" / "team_governance_snapshots.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "unassigned"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _owner_overrides(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path, [])
    return payload if isinstance(payload, list) else []


def _owner_for_domain(domain: str, overrides: list[dict[str, Any]]) -> dict[str, Any]:
    folded = domain.casefold()
    for owner in overrides:
        domains = [str(item).casefold() for item in owner.get("domains", [])]
        patterns = [str(item).casefold() for item in owner.get("patterns", [])]
        if folded in domains or any(
            pattern and pattern in folded for pattern in patterns
        ):
            return {
                "id": str(owner.get("id") or _safe_id(domain)),
                "name": str(owner.get("name") or domain),
                "lead": str(owner.get("lead") or ""),
                "source": "team_owners.json",
            }
    return {
        "id": f"domain-{_safe_id(domain)}",
        "name": f"{domain} Team",
        "lead": "",
        "source": "inferred-domain",
    }


def _status(max_risk: int, hotspots: int, avg_maintainability: float) -> str:
    if max_risk >= 80 or hotspots >= 10 or avg_maintainability < 45:
        return "red"
    if max_risk >= 60 or hotspots or avg_maintainability < 60:
        return "yellow"
    return "green"


def _sla(status: str) -> str:
    if status == "red":
        return "next release gate"
    if status == "yellow":
        return "3 working days"
    return "next planned refactor"


def _save_snapshot(report: dict[str, Any], path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshots = _load_json(path, [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshot = {
        "created_at": report["generated_at"],
        "summary": report["summary"],
        "status_counts": report["release_board"]["status_counts"],
    }
    snapshots.insert(0, snapshot)
    snapshots = snapshots[:50]
    path.write_text(
        json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"path": str(path), "total": len(snapshots), "latest": snapshot}


def _trend(path: Path) -> dict[str, Any]:
    snapshots = _load_json(path, [])
    if not isinstance(snapshots, list):
        snapshots = []
    return {"path": str(path), "snapshots": snapshots[:12], "total": len(snapshots)}


def _domain_areas(
    summary: dict[str, Any],
    hotspots: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hotspots_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for hotspot in hotspots:
        hotspots_by_domain[str(hotspot.get("domain") or "Прочее")].append(hotspot)

    areas = []
    for item in summary.get("by_domain", []):
        domain = str(item.get("domain") or "Прочее")
        domain_hotspots = hotspots_by_domain.get(domain, [])
        max_risk = max((int(h.get("risk") or 0) for h in domain_hotspots), default=0)
        avg_maintainability = float(item.get("avg_maintainability") or 0)
        status = _status(max_risk, len(domain_hotspots), avg_maintainability)
        areas.append(
            {
                "domain": domain,
                "owner": _owner_for_domain(domain, overrides),
                "modules": int(item.get("count") or 0),
                "avg_maintainability": avg_maintainability,
                "hotspots": len(domain_hotspots),
                "max_risk": max_risk,
                "status": status,
                "risk_sla": _sla(status),
                "top_hotspots": domain_hotspots[:5],
            }
        )
    return areas


def _review_queue(areas: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    queue = []
    for area in areas:
        for hotspot in area["top_hotspots"]:
            queue.append(
                {
                    "owner": area["owner"],
                    "domain": area["domain"],
                    "module_path": hotspot.get("module_path"),
                    "risk": hotspot.get("risk"),
                    "fan_in": hotspot.get("fan_in"),
                    "reasons": hotspot.get("reasons", []),
                    "sla": area["risk_sla"],
                }
            )
    queue.sort(key=lambda item: int(item.get("risk") or 0), reverse=True)
    return queue[:limit]


def _recommendations(
    areas: list[dict[str, Any]], queue: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    recs = []
    red = [area for area in areas if area["status"] == "red"]
    if red:
        recs.append(
            {
                "owner": "lead",
                "severity": "high",
                "title": "Put red code areas into the next release gate",
                "details": {"areas": [area["domain"] for area in red[:10]]},
            }
        )
    if queue:
        recs.append(
            {
                "owner": "team",
                "severity": "medium",
                "title": "Assign high-risk module review queue",
                "details": {"items": len(queue)},
            }
        )
    if not recs:
        recs.append(
            {
                "owner": "lead",
                "severity": "low",
                "title": "Keep ownership snapshots on every release",
                "details": {},
            }
        )
    return recs


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1cAI Team Governance",
        "",
        f"Areas: **{report['summary']['areas']}**",
        f"Red areas: **{report['summary']['red_areas']}**",
        f"Review queue: **{report['summary']['review_queue']}**",
        "",
        "## Actions",
        "",
    ]
    for item in report["recommendations"]:
        lines.append(f"- **{item['severity']}** {item['owner']}: {item['title']}")
    return "\n".join(lines)


def build_team_governance(
    store: Any,
    *,
    limit: int = 40,
    save_snapshot: bool = False,
    owner_map_path: Path = OWNER_MAP_PATH,
    snapshot_path: Path = SNAPSHOT_PATH,
) -> dict[str, Any]:
    """Build a team governance board from the local Rentgen quality store."""

    if store is None:
        return {
            "available": False,
            "generated_at": _now(),
            "summary": {"areas": 0, "review_queue": 0},
            "areas": [],
            "release_board": {"review_queue": [], "status_counts": {}},
            "trend": _trend(snapshot_path),
            "recommendations": [],
            "caveats": ["Rentgen store is unavailable."],
            "markdown": "# 1cAI Team Governance\n\nRentgen store is unavailable.",
        }

    quality_summary = store.summary()
    hotspots = store.hotspots(limit=max(limit, 1), min_fan_in=0)
    overrides = _owner_overrides(owner_map_path)
    areas = _domain_areas(quality_summary, hotspots, overrides)
    status_counts = Counter(area["status"] for area in areas)
    queue = _review_queue(areas, limit)
    red_areas = status_counts.get("red", 0)
    yellow_areas = status_counts.get("yellow", 0)

    report = {
        "available": True,
        "generated_at": _now(),
        "summary": {
            "areas": len(areas),
            "red_areas": red_areas,
            "yellow_areas": yellow_areas,
            "review_queue": len(queue),
            "total_modules": quality_summary.get("total_modules", 0),
            "modules_with_issues": quality_summary.get("modules_with_issues", 0),
            "avg_maintainability": quality_summary.get("avg_maintainability", 0),
        },
        "areas": areas,
        "release_board": {
            "status_counts": dict(status_counts),
            "review_queue": queue,
            "sla_policy": {
                "red": "next release gate",
                "yellow": "3 working days",
                "green": "next planned refactor",
            },
        },
        "trend": _trend(snapshot_path),
        "recommendations": _recommendations(areas, queue),
        "caveats": [
            "Owners are inferred from quality domains unless data/team_owners.json provides overrides.",
            "SLA is a governance signal, not an automatic production incident priority.",
        ],
    }
    if save_snapshot:
        report["stored_snapshot"] = _save_snapshot(report, snapshot_path)
        report["trend"] = _trend(snapshot_path)
    report["markdown"] = _markdown(report)
    return report
