"""Architecture boundary review over the Rentgen module graph."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from src.services.rentgen.change_plan import dedupe, extract_diff_modules

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}

INTEGRATION_HINTS = (
    "обмен",
    "интеграц",
    "http",
    "web",
    "api",
    "odata",
    "xdt",
    "soap",
    "эдо",
    "edi",
    "внеш",
)
PRESENTATION_HINTS = ("клиент", "форма", "ui", "интерфейс")
INFRA_HINTS = (
    "общегоназначения",
    "строковые",
    "файлов",
    "хранилищ",
    "настройк",
    "администр",
)


LAYER_ORDER = {
    "presentation": 5,
    "application": 4,
    "domain": 3,
    "data": 2,
    "integration": 2,
    "infrastructure": 1,
    "unknown": 0,
}


def _text(*values: Any) -> str:
    return " ".join(str(value or "").casefold() for value in values)


def infer_layer(module: dict[str, Any], prefix: str) -> str:
    """Infer a coarse architectural layer from EDT path, module kind and names."""

    name = _text(
        module.get(f"{prefix}_object"), module.get(prefix), module.get(f"{prefix}_path")
    )
    path = str(module.get(f"{prefix}_path") or "").replace("\\", "/")
    root = path.split("/", 1)[0] if "/" in path else ""
    kind = str(module.get(f"{prefix}_kind") or "").casefold()

    if kind in {"form", "commandmodule"} or "/Forms/" in path or "/Commands/" in path:
        return "presentation"
    if any(hint in name for hint in INTEGRATION_HINTS) or root in {
        "ExchangePlans",
        "HTTPServices",
        "WebServices",
        "ExternalDataSources",
        "IntegrationServices",
        "WSReferences",
        "XDTOPackages",
    }:
        return "integration"
    if "клиентсервер" in name or "clientserver" in name:
        return "domain"
    if any(hint in name for hint in PRESENTATION_HINTS):
        return "presentation"
    if root in {
        "InformationRegisters",
        "AccumulationRegisters",
        "AccountingRegisters",
        "CalculationRegisters",
        "Constants",
    }:
        return "data"
    if root in {
        "Documents",
        "Catalogs",
        "Reports",
        "DataProcessors",
        "BusinessProcesses",
        "Tasks",
    }:
        return "application"
    if root == "CommonModules":
        if any(hint in name for hint in INFRA_HINTS):
            return "infrastructure"
        return "domain"
    return "domain" if kind == "module" else "unknown"


def _severity(rule: str, weight: int) -> str:
    if rule in {
        "presentation_to_data",
        "server_to_presentation",
        "data_to_presentation",
    }:
        return "high" if weight >= 10 else "medium"
    if rule == "cycle":
        return "high" if weight >= 25 else "medium"
    if rule == "dense_coupling":
        return "medium" if weight >= 250 else "low"
    return "medium"


def _finding(
    *,
    rule: str,
    edge: dict[str, Any],
    src_layer: str,
    dst_layer: str,
    message: str,
    recommendation: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    weight = int(edge.get("weight") or 0)
    return {
        "rule": rule,
        "severity": _severity(rule, weight),
        "src": edge["src"],
        "dst": edge["dst"],
        "weight": weight,
        "src_layer": src_layer,
        "dst_layer": dst_layer,
        "message": message,
        "recommendation": recommendation,
        "details": {
            "src_path": edge.get("src_path"),
            "dst_path": edge.get("dst_path"),
            "src_domain": edge.get("src_domain"),
            "dst_domain": edge.get("dst_domain"),
            **(extra or {}),
        },
    }


def _edge_findings(edge: dict[str, Any], dense_threshold: int) -> list[dict[str, Any]]:
    src_layer = infer_layer(edge, "src")
    dst_layer = infer_layer(edge, "dst")
    weight = int(edge.get("weight") or 0)
    findings: list[dict[str, Any]] = []

    if src_layer == "presentation" and dst_layer == "data":
        findings.append(
            _finding(
                rule="presentation_to_data",
                edge=edge,
                src_layer=src_layer,
                dst_layer=dst_layer,
                message="Presentation layer calls data layer directly.",
                recommendation="Route the dependency through application/domain services and keep data access off forms/client modules.",
            )
        )

    if (
        src_layer in {"domain", "application", "integration", "data", "infrastructure"}
        and dst_layer == "presentation"
    ):
        findings.append(
            _finding(
                rule="server_to_presentation",
                edge=edge,
                src_layer=src_layer,
                dst_layer=dst_layer,
                message="Non-presentation module depends on presentation/client code.",
                recommendation="Move shared logic to domain/application common modules; keep presentation modules as callers only.",
            )
        )

    if src_layer == "data" and dst_layer in {"presentation", "application"}:
        findings.append(
            _finding(
                rule="data_to_presentation",
                edge=edge,
                src_layer=src_layer,
                dst_layer=dst_layer,
                message="Data layer depends upward on business or UI layer.",
                recommendation="Invert the dependency: data modules should expose primitives and be called by application/domain modules.",
            )
        )

    if (
        src_layer != dst_layer
        and LAYER_ORDER[src_layer] < LAYER_ORDER[dst_layer]
        and weight >= 20
    ):
        findings.append(
            _finding(
                rule="upward_dependency",
                edge=edge,
                src_layer=src_layer,
                dst_layer=dst_layer,
                message="Lower-level layer depends on a higher-level layer.",
                recommendation="Introduce a stable lower-level abstraction or move the shared function below both callers.",
            )
        )

    if weight >= dense_threshold:
        findings.append(
            _finding(
                rule="dense_coupling",
                edge=edge,
                src_layer=src_layer,
                dst_layer=dst_layer,
                message="Dependency edge is very dense and should be reviewed as an architectural boundary.",
                recommendation="Split the API surface, introduce a facade, or document the dependency as an intentional ADR.",
            )
        )

    return findings


def _cycle_findings(edges: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    by_pair = {(edge["src"], edge["dst"]): edge for edge in edges}
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        src = edge["src"]
        dst = edge["dst"]
        reverse_key = (dst, src)
        if reverse_key not in by_pair:
            continue
        pair_key = tuple(sorted((src, dst)))
        if pair_key in seen:
            continue
        seen.add(pair_key)
        reverse = by_pair[reverse_key]
        weight = int(edge.get("weight") or 0) + int(reverse.get("weight") or 0)
        combined = dict(edge)
        combined["weight"] = weight
        findings.append(
            _finding(
                rule="cycle",
                edge=combined,
                src_layer=infer_layer(edge, "src"),
                dst_layer=infer_layer(edge, "dst"),
                message="Two modules depend on each other at module level.",
                recommendation="Break the cycle with a common lower-level module, event contract, or explicit facade.",
                extra={"reverse_weight": reverse.get("weight")},
            )
        )
        if len(findings) >= limit:
            break
    return findings


def _focus_module_names(store, changed_modules: list[str]) -> set[str]:
    names: set[str] = set()
    for module_ref in changed_modules:
        try:
            resolved = store.resolve_module(module_ref)
        except Exception:
            continue
        for module in resolved.get("graph_modules", []):
            if module.get("name"):
                names.add(module["name"])
    return names


def _summary(
    findings: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, Any]:
    by_severity = Counter(item["severity"] for item in findings)
    by_rule = Counter(item["rule"] for item in findings)
    layer_edges = Counter(
        f"{infer_layer(edge, 'src')}->{infer_layer(edge, 'dst')}" for edge in edges
    )
    return {
        "edges_reviewed": len(edges),
        "findings": len(findings),
        "by_severity": dict(by_severity),
        "by_rule": dict(by_rule),
        "layer_edges": dict(layer_edges.most_common(20)),
        "score": max(
            0,
            100
            - by_severity.get("high", 0) * 8
            - by_severity.get("medium", 0) * 3
            - by_severity.get("low", 0),
        ),
    }


def build_architecture_review(
    store,
    *,
    changed_modules: list[str] | None = None,
    diff: str | None = None,
    limit: int = 5000,
    min_weight: int = 1,
    dense_threshold: int = 250,
    include_cycles: bool = True,
    finding_limit: int = 200,
) -> dict[str, Any]:
    modules = dedupe(list(changed_modules or []) + extract_diff_modules(diff))
    edges = store.module_edges(limit=limit, min_weight=min_weight)
    focus_names = _focus_module_names(store, modules) if modules else set()
    if focus_names:
        edges = [
            edge
            for edge in edges
            if edge["src"] in focus_names or edge["dst"] in focus_names
        ]

    findings: list[dict[str, Any]] = []
    for edge in edges:
        findings.extend(_edge_findings(edge, dense_threshold=dense_threshold))
    if include_cycles:
        findings.extend(_cycle_findings(edges, limit=finding_limit))

    findings.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(item["severity"], 9),
            -int(item.get("weight") or 0),
            item["rule"],
            item["src"],
            item["dst"],
        )
    )
    findings = findings[:finding_limit]

    hubs = sorted(
        (
            {
                "module": module,
                "out_weight": sum(int(edge.get("weight") or 0) for edge in outgoing),
                "edges": len(outgoing),
                "layer": infer_layer(outgoing[0], "src") if outgoing else "unknown",
            }
            for module, outgoing in _group_by_src(edges).items()
        ),
        key=lambda item: (item["out_weight"], item["edges"]),
        reverse=True,
    )[:20]

    return {
        "scope": {
            "mode": "focused" if focus_names else "top_edges",
            "changed_modules": modules,
            "focus_graph_modules": sorted(focus_names),
            "limit": limit,
            "min_weight": min_weight,
            "dense_threshold": dense_threshold,
        },
        "summary": _summary(findings, edges),
        "findings": findings,
        "hubs": hubs,
        "top_edges": [
            {
                "src": edge["src"],
                "dst": edge["dst"],
                "weight": edge["weight"],
                "src_layer": infer_layer(edge, "src"),
                "dst_layer": infer_layer(edge, "dst"),
                "src_path": edge.get("src_path"),
                "dst_path": edge.get("dst_path"),
            }
            for edge in edges[:50]
        ],
        "caveats": [
            "Architecture review uses deterministic layer inference from EDT paths and module names; teams should tune rules for their local architecture.",
            "Module-level edges are aggregated from high-precision call resolution and may miss dynamic Execute() calls.",
        ],
    }


def _group_by_src(edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        grouped[edge["src"]].append(edge)
    return dict(grouped)
