"""Рентген API — 1C configuration call-graph analysis.

Served from the in-process SQLite store (data/rentgen.db). No Neo4j.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.rentgen.change_plan import (
    assess_ci_gate,
    build_change_plan,
    extract_diff_modules,
    render_markdown_report,
)
from src.services.rentgen.test_coverage_matrix import build_test_coverage_matrix
from src.services.rentgen.test_inventory import inventory_summary, match_tests_for_module

router = APIRouter(prefix="/rentgen", tags=["rentgen"])

_NO_STORE = (
    "Рентген store not built. Run: python tools/rentgen/build_store.py "
    "(needs data/rentgen_callgraph.ndjson + gabriel_runs/scores.json)."
)


class FlowRequest(BaseModel):
    entry_point: str
    max_depth: int = 10


class FlowEdge(BaseModel):
    caller: str
    caller_module: str
    callee: str
    callee_module: str
    line: int | None = None
    depth: int | None = None


class FlowResponse(BaseModel):
    entry_point: str
    edges: list[FlowEdge]
    total: int


class ImpactResponse(BaseModel):
    target: str
    callers: list[FlowEdge]
    total: int


class ChangeImpactRequest(BaseModel):
    changed_modules: list[str] = Field(default_factory=list)
    diff: str | None = None
    max_depth: int = 5
    max_edges: int = 600
    hotspot_limit: int = 10


class PerformanceRisk(BaseModel):
    module_path: str
    factor: str
    severity: str
    detail: str


class ChangeImpactItem(BaseModel):
    module_path: str
    canonical: dict
    graph_modules: list[dict]
    entry_subroutines: int
    impact_total: int
    impacted_modules: list[dict]
    impacted_hotspots: list[dict]
    quality: dict | None = None
    changed_hotspot: dict | None = None
    performance_risks: list[PerformanceRisk] = Field(default_factory=list)
    covering_tests: list[dict] = Field(default_factory=list)
    # Honesty: forms (~44% of modules) are absent from the call graph, so their
    # impact is unmeasured, NOT zero. Surface that instead of a misleading 0.
    impact_measured: bool = True
    coverage: str = "in_graph"
    coverage_caveat: str | None = None


class ChangeImpactResponse(BaseModel):
    changed_modules: list[str]
    modules: list[ChangeImpactItem]
    total_impact_edges: int
    total_impacted_modules: int
    caveats: list[str]
    unmeasured_modules: list[str] = Field(default_factory=list)


class TestSelectorResponse(BaseModel):
    changed_modules: list[str]
    modules: list[dict]
    caveats: list[str]


class TestInventoryMatchRequest(BaseModel):
    module_path: str
    object_name: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class TestCoverageMatrixRequest(ChangeImpactRequest):
    match_limit: int = Field(default=10, ge=1, le=50)


class CIGateRequest(ChangeImpactRequest):
    risk_threshold: int = 70
    impact_threshold: int = 300
    fail_on_high: bool = True
    include_markdown: bool = True


class CIGateResponse(BaseModel):
    status: str
    violations: list[dict]
    summary: dict
    markdown: str | None = None


@router.post("/flow", response_model=FlowResponse)
def get_execution_flow(req: FlowRequest):
    """Forward call graph: what does this entry point eventually call?"""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    edges = store.get_execution_flow(req.entry_point, req.max_depth)
    return FlowResponse(
        entry_point=req.entry_point,
        edges=[FlowEdge(**e) for e in edges],
        total=len(edges),
    )


@router.post("/impact", response_model=ImpactResponse)
def get_impact_analysis(req: FlowRequest):
    """Reverse call graph (blast radius): what depends on this function?"""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    callers = store.get_impact_analysis(req.entry_point, req.max_depth)
    return ImpactResponse(
        target=req.entry_point,
        callers=[FlowEdge(**c) for c in callers],
        total=len(callers),
    )


@router.post("/change-impact", response_model=ChangeImpactResponse)
def change_impact(req: ChangeImpactRequest):
    """Change-driven review: module paths -> whole-config blast radius + risks."""
    changed_modules = list(dict.fromkeys(req.changed_modules + extract_diff_modules(req.diff)))
    if not changed_modules:
        raise HTTPException(400, "Provide changed_modules or a unified diff with .bsl paths")

    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)

    plan = build_change_plan(
        store,
        changed_modules,
        max_depth=req.max_depth,
        max_edges=req.max_edges,
        hotspot_limit=req.hotspot_limit,
    )
    return ChangeImpactResponse(**plan)


@router.post("/test-selector", response_model=TestSelectorResponse)
def test_selector(req: ChangeImpactRequest):
    """Risk-driven YAxUnit/Vanessa test run plan for a diff or module list."""
    changed_modules = list(dict.fromkeys(req.changed_modules + extract_diff_modules(req.diff)))
    if not changed_modules:
        raise HTTPException(400, "Provide changed_modules or a unified diff with .bsl paths")

    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)

    plan = build_change_plan(
        store,
        changed_modules,
        max_depth=req.max_depth,
        max_edges=req.max_edges,
        hotspot_limit=req.hotspot_limit,
    )
    return TestSelectorResponse(
        changed_modules=plan["changed_modules"],
        modules=[
            {
                "module_path": item["module_path"],
                "risk": (item["quality"] or {}).get("risk"),
                "impact_total": item["impact_total"],
                "covering_tests": item["covering_tests"],
            }
            for item in plan["modules"]
        ],
        caveats=plan["caveats"],
    )


@router.post("/test-coverage-matrix")
def test_coverage_matrix(req: TestCoverageMatrixRequest):
    """Exact/planned/gap test coverage matrix for changed modules or diff."""
    changed_modules = list(dict.fromkeys(req.changed_modules + extract_diff_modules(req.diff)))
    if not changed_modules:
        raise HTTPException(400, "Provide changed_modules or a unified diff with .bsl paths")

    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)

    return build_test_coverage_matrix(
        store,
        changed_modules=changed_modules,
        max_depth=req.max_depth,
        max_edges=req.max_edges,
        hotspot_limit=req.hotspot_limit,
        match_limit=req.match_limit,
    )


@router.get("/test-inventory")
def test_inventory():
    """Local BSL/YAxUnit test inventory summary."""
    return inventory_summary()


@router.post("/test-inventory/match")
def test_inventory_match(req: TestInventoryMatchRequest):
    """Match a changed module/object to known local BSL test cases."""
    return {
        "module_path": req.module_path,
        "object_name": req.object_name,
        "matches": match_tests_for_module(
            req.module_path,
            object_name=req.object_name,
            limit=req.limit,
        ),
    }


@router.post("/ci-gate", response_model=CIGateResponse)
def ci_gate(req: CIGateRequest):
    """PR/release gate: diff/module list -> risk decision + markdown report."""
    changed_modules = list(dict.fromkeys(req.changed_modules + extract_diff_modules(req.diff)))
    if not changed_modules:
        raise HTTPException(400, "Provide changed_modules or a unified diff with .bsl paths")

    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)

    plan = build_change_plan(
        store,
        changed_modules,
        max_depth=req.max_depth,
        max_edges=req.max_edges,
        hotspot_limit=req.hotspot_limit,
    )
    gate = assess_ci_gate(
        plan,
        risk_threshold=req.risk_threshold,
        impact_threshold=req.impact_threshold,
        fail_on_high=req.fail_on_high,
    )
    return CIGateResponse(
        **gate,
        markdown=render_markdown_report(plan, gate) if req.include_markdown else None,
    )


@router.get("/dead-code")
def dead_code(limit: int = 50, scope: str = "common"):
    """Exported subroutines never called by any internal call edge.

    scope='common' (default): common-module exports only — high precision.
    scope='all': every uncalled export (noisy; includes platform-invoked handlers).
    """
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    return store.dead_code(limit, scope)


@router.get("/stats")
def graph_stats():
    """Call-graph + quality statistics."""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    return {**store.get_stats(), "meta": store.db_meta()}


@router.get("/module-neighbors")
def module_neighbors(module: str, limit: int = 60):
    """Direct callers + callees of a module (for the force-graph slice view)."""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    return store.module_neighbors(module, limit)


@router.get("/health")
def rentgen_health():
    """Рентген service health — reports store availability + size."""
    store = store_or_none()
    if store is None:
        return {"status": "store_not_built", "store": False, "hint": _NO_STORE}
    meta = store.db_meta()
    return {
        "status": "ok",
        "store": True,
        "subroutines": int(meta.get("n_subroutines", 0)),
        "modules": int(meta.get("n_modules", 0)),
        "call_edges": int(meta.get("n_call_edges", 0)),
        "quality_modules": int(meta.get("n_quality", 0)),
    }


@router.get("/build")
def build_info():
    """The graph is prebuilt offline. Report current store state."""
    store = store_or_none()
    if store is None:
        return {"built": False, "hint": _NO_STORE}
    return {"built": True, "meta": store.db_meta()}
