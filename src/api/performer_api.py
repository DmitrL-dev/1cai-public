"""Перформер API — 1C Technology Journal performance analysis."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api._rentgen_store import store_or_none

router = APIRouter(prefix="/api/v1/performer", tags=["performer"])

_NO_STORE = (
    "Рентген store not built. Run: python tools/rentgen/build_store.py "
    "(needs data/rentgen_callgraph.ndjson + gabriel_runs/scores.json)."
)


class TJAnalyzeRequest(BaseModel):
    log_path: str
    min_duration_ms: float = 100.0
    top_n: int = 20


class QueryHotspotItem(BaseModel):
    module: str
    line: int
    code_fragment: str
    sdbl: str
    total_calls: int
    total_duration_ms: float
    max_duration_us: int
    avg_rows: float
    is_in_loop: bool


class PerformanceReportResponse(BaseModel):
    total_events: int
    total_duration_ms: float
    hotspots: list[QueryHotspotItem]
    n_plus_one: list[QueryHotspotItem]
    lock_waits_count: int
    deadlocks_count: int


class TJImpactRequest(TJAnalyzeRequest):
    max_depth: int = 5
    max_edges: int = 300


class QueryHotspotImpactItem(BaseModel):
    hotspot: QueryHotspotItem
    canonical: dict
    graph_modules: list[dict]
    impact_total: int
    impacted_modules: list[dict]


class PerformanceImpactResponse(PerformanceReportResponse):
    hotspot_impacts: list[QueryHotspotImpactItem]


def _hotspot_item(h) -> QueryHotspotItem:
    return QueryHotspotItem(
        module=h.module,
        line=h.line,
        code_fragment=h.code_fragment,
        sdbl=h.sdbl,
        total_calls=h.total_calls,
        total_duration_ms=h.total_duration_ms,
        max_duration_us=h.max_duration_us,
        avg_rows=h.avg_rows,
        is_in_loop=h.is_in_loop,
    )


def _report_response(report) -> PerformanceReportResponse:
    return PerformanceReportResponse(
        total_events=report.total_events,
        total_duration_ms=report.total_duration_ms,
        hotspots=[_hotspot_item(h) for h in report.hotspots],
        n_plus_one=[_hotspot_item(h) for h in report.n_plus_one],
        lock_waits_count=len(report.lock_waits),
        deadlocks_count=len(report.deadlocks),
    )


@router.post("/analyze", response_model=PerformanceReportResponse)
async def analyze_tj(req: TJAnalyzeRequest):
    """Analyze Technology Journal logs for performance bottlenecks."""
    from src.services.tj_parser.analyzer import TJPerformanceAnalyzer

    analyzer = TJPerformanceAnalyzer(
        min_duration_ms=req.min_duration_ms,
    )
    report = analyzer.analyze(req.log_path, top_n=req.top_n)
    return _report_response(report)


@router.post("/impact", response_model=PerformanceImpactResponse)
async def analyze_tj_impact(req: TJImpactRequest):
    """Analyze TJ logs and map query hotspots to Рентген blast radius."""
    from src.services.tj_parser.analyzer import TJPerformanceAnalyzer

    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)

    analyzer = TJPerformanceAnalyzer(
        min_duration_ms=req.min_duration_ms,
    )
    report = analyzer.analyze(req.log_path, top_n=req.top_n)
    base = _report_response(report)

    impacts = []
    for hotspot in report.hotspots:
        impact = store.module_impact(
            hotspot.module,
            max_depth=req.max_depth,
            max_edges=req.max_edges,
        )
        impacts.append(
            QueryHotspotImpactItem(
                hotspot=_hotspot_item(hotspot),
                canonical=impact["canonical"],
                graph_modules=impact["graph_modules"],
                impact_total=impact["total"],
                impacted_modules=impact["impacted_modules"][:30],
            )
        )

    return PerformanceImpactResponse(
        **base.model_dump(),
        hotspot_impacts=impacts,
    )


@router.get("/health")
async def performer_health():
    """Check Перформер service health."""
    return {"status": "ok"}
