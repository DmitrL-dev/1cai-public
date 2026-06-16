"""Data governance review for EDT metadata.

The review turns raw metadata graph objects into an enterprise-facing data
surface: registers, documents/catalogs, exchange/integration objects, rights
exposure and migration risks.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Any

from src.services.rentgen.metadata_graph import build_metadata_graph, _enrich_object


DATA_TYPES = {
    "Catalog",
    "Document",
    "InformationRegister",
    "AccumulationRegister",
    "AccountingRegister",
    "CalculationRegister",
    "Constant",
    "ChartOfAccounts",
    "ChartOfCharacteristicTypes",
    "ChartOfCalculationTypes",
    "Sequence",
    "DocumentJournal",
}

REGISTER_TYPES = {
    "InformationRegister",
    "AccumulationRegister",
    "AccountingRegister",
    "CalculationRegister",
}

EXCHANGE_TYPES = {
    "ExchangePlan",
    "ExternalDataSource",
    "IntegrationService",
    "HTTPService",
    "WebService",
    "WSReference",
    "XDTOPackage",
}

TRANSACTION_TYPES = {"Document", "BusinessProcess", "Task"}
MASTER_DATA_TYPES = {"Catalog", "Enum", "ChartOfAccounts", "ChartOfCharacteristicTypes", "ChartOfCalculationTypes"}


def _preview(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": obj["type"],
        "name": obj["name"],
        "ref": obj["ref"],
        "path": obj["path"],
        "counts": obj["counts"],
    }


def _data_group(metadata_type: str) -> str:
    if metadata_type in REGISTER_TYPES:
        return "register"
    if metadata_type in TRANSACTION_TYPES:
        return "transaction"
    if metadata_type in MASTER_DATA_TYPES:
        return "master_data"
    if metadata_type in EXCHANGE_TYPES:
        return "exchange"
    return "support"


def _role_rights(graph: dict[str, Any], limit: int) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    by_right: Counter[str] = Counter()
    roles_reviewed = 0
    dangerous_total = 0

    for role in (obj for obj in graph["objects"] if obj["type"] == "Role"):
        if roles_reviewed >= limit:
            break
        roles_reviewed += 1
        enriched = _enrich_object(graph, role)
        rights = (enriched or {}).get("rights") or {}
        dangerous_total += int(rights.get("dangerous_total") or 0)
        by_right.update(rights.get("by_right") or {})
        for item in rights.get("dangerous") or []:
            findings.append(
                {
                    "severity": "high" if item.get("right") in {"Administration", "Delete"} else "medium",
                    "role": role["name"],
                    "right": item.get("right"),
                    "object": item.get("object"),
                    "message": "Dangerous data right requires explicit release review.",
                }
            )

    return {
        "summary": {
            "roles_reviewed": roles_reviewed,
            "dangerous_rights": dangerous_total,
            "findings": len(findings),
            "by_right": dict(by_right),
        },
        "findings": findings[:limit],
    }


def _shape_for_object(graph: dict[str, Any], obj: dict[str, Any]) -> dict[str, Any]:
    if obj["type"] not in DATA_TYPES and obj["type"] not in EXCHANGE_TYPES:
        return {
            "ref": obj["ref"],
            "type": obj["type"],
            "name": obj["name"],
            "counts": obj["counts"],
        }

    enriched = _enrich_object(graph, obj)
    counts = enriched.get("counts") or obj["counts"]
    return {
        "ref": enriched["ref"],
        "type": enriched["type"],
        "name": enriched["name"],
        "path": enriched["path"],
        "group": _data_group(enriched["type"]),
        "counts": counts,
        "attributes": (enriched.get("attributes") or [])[:20],
        "tabular_sections": (enriched.get("tabular_sections") or [])[:20],
        "dimensions": (enriched.get("dimensions") or [])[:20],
        "resources": (enriched.get("resources") or [])[:20],
        "references": (enriched.get("references") or [])[:30],
        "rights_path": enriched.get("rights_path"),
    }


def _migration_findings(shapes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for shape in shapes:
        metadata_type = shape["type"]
        counts = shape.get("counts") or {}
        ref = shape["ref"]

        if metadata_type in REGISTER_TYPES and not shape.get("dimensions") and not shape.get("resources"):
            findings.append(
                {
                    "severity": "medium",
                    "code": "register-shape-unknown",
                    "ref": ref,
                    "message": "Register has no parsed dimensions/resources; migration and query plans need manual shape review.",
                    "details": {"type": metadata_type},
                }
            )

        if metadata_type in {"Document", "Catalog"} and int(counts.get("attributes") or 0) == 0:
            findings.append(
                {
                    "severity": "low",
                    "code": "empty-data-shape",
                    "ref": ref,
                    "message": "Object has no parsed attributes; verify EDT XML coverage before structural changes.",
                    "details": {"type": metadata_type},
                }
            )

        if metadata_type in EXCHANGE_TYPES:
            findings.append(
                {
                    "severity": "high" if metadata_type in {"ExternalDataSource", "HTTPService", "WebService"} else "medium",
                    "code": "exchange-surface",
                    "ref": ref,
                    "message": "Exchange or integration object can affect external data contracts.",
                    "details": {"type": metadata_type},
                }
            )

        if int(counts.get("tabular_sections") or 0) >= 5:
            findings.append(
                {
                    "severity": "medium",
                    "code": "wide-tabular-surface",
                    "ref": ref,
                    "message": "Object has many tabular sections; migration/test data generation should be explicit.",
                    "details": {"tabular_sections": counts.get("tabular_sections")},
                }
            )
    return findings


@lru_cache(maxsize=8)
def build_data_governance(limit: int = 300, *, config_path: str | None = None) -> dict[str, Any]:
    graph = build_metadata_graph(config_path)
    if not graph["available"]:
        return {
            "available": False,
            "config_path": graph["config_path"],
            "summary": {"total_objects": 0},
            "objects": [],
            "exchanges": [],
            "rights": {"summary": {}, "findings": []},
            "migration_findings": [],
            "caveats": ["Metadata graph is unavailable."],
        }

    objects = graph["objects"]
    by_type = Counter(obj["type"] for obj in objects)
    data_candidates = [
        obj for obj in objects
        if obj["type"] in DATA_TYPES or obj["type"] in EXCHANGE_TYPES
    ][:limit]
    shapes = [_shape_for_object(graph, obj) for obj in data_candidates]
    exchanges = [shape for shape in shapes if shape["type"] in EXCHANGE_TYPES]
    rights = _role_rights(graph, limit=min(limit, 300))
    migration_findings = _migration_findings(shapes)

    by_group = Counter(shape["group"] for shape in shapes)
    summary = {
        "total_objects": len(objects),
        "data_objects": sum(1 for obj in objects if obj["type"] in DATA_TYPES),
        "registers": sum(1 for obj in objects if obj["type"] in REGISTER_TYPES),
        "exchange_objects": sum(1 for obj in objects if obj["type"] in EXCHANGE_TYPES),
        "roles": by_type.get("Role", 0),
        "dangerous_rights": rights["summary"].get("dangerous_rights", 0),
        "migration_findings": len(migration_findings),
        "by_group": dict(by_group),
        "by_type": dict(by_type),
    }

    return {
        "available": True,
        "config_path": graph["config_path"],
        "summary": summary,
        "objects": shapes,
        "exchanges": exchanges,
        "rights": rights,
        "migration_findings": migration_findings[:limit],
        "caveats": [
            "Data governance is static EDT XML analysis; runtime data volumes are not included yet.",
            "Rights review depends on local Rights.xml coverage for roles.",
        ],
    }
