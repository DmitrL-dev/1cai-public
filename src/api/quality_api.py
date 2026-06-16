"""Quality API — BSL module quality scores + explainable risk hotspots.

Backed by the local Рентген SQLite store (data/rentgen.db), built once from the
scoring pipeline output (gabriel_runs/scores.json) and the Go call graph. No
Neo4j required.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.bsl_diagnostics import analyze_bsl
from src.services.rentgen.standards_review import (
    STANDARDS_CATALOG,
    list_standards_findings,
    review_bsl_standards,
    save_standards_review,
)

router = APIRouter(prefix="/quality", tags=["quality"])

_NO_STORE = (
    "Рентген store not built. Run: python tools/rentgen/build_store.py "
    "(needs data/rentgen_callgraph.ndjson + gabriel_runs/scores.json)."
)


class ModuleScore(BaseModel):
    module_path: str
    module_type: str = "Unknown"
    domain: str = "Прочее"
    loc: int = 0
    complexity_score: int = 0
    documentation_score: int = 0
    maintainability_score: int = 0
    has_n_plus_one: bool = False
    has_empty_catch: bool = False
    has_deep_nesting: bool = False
    code_quality: int | None = None


class QualitySummary(BaseModel):
    total_modules: int
    avg_complexity: float
    avg_documentation: float
    avg_maintainability: float
    modules_with_issues: int
    by_domain: list[dict]


class RiskReason(BaseModel):
    factor: str
    detail: str
    weight: float


class Hotspot(BaseModel):
    module_path: str
    module_type: str = "Unknown"
    domain: str = "Прочее"
    loc: int = 0
    complexity_score: int = 0
    documentation_score: int = 0
    maintainability_score: int = 0
    code_quality: int | None = None
    risk: int
    quality_risk: int
    fan_in: int = 0
    fan_out: int = 0
    reasons: list[RiskReason] = []


class ReviewDiffRequest(BaseModel):
    changed_modules: list[str] = Field(default_factory=list)
    diff: str | None = None
    max_depth: int = 4
    max_edges: int = 300
    hotspot_limit: int = 10


class StandardsFinding(BaseModel):
    module_path: str
    source: str
    severity: str
    message: str
    rule_id: str | None = None
    standard: str | None = None
    code: str | None = None
    line: int | None = None
    details: dict = Field(default_factory=dict)
    autofix: dict | None = None


class ReviewDiffItem(BaseModel):
    module_path: str
    canonical: dict
    graph_modules: list[dict]
    quality: dict | None = None
    changed_hotspot: dict | None = None
    impact_total: int
    impacted_modules: list[dict]
    impacted_hotspots: list[dict]
    standards_findings: list[StandardsFinding] = Field(default_factory=list)


class ReviewDiffResponse(BaseModel):
    changed_modules: list[str]
    modules: list[ReviewDiffItem]
    total_impact_edges: int
    total_findings: int
    caveats: list[str]


class DiagnosticsRequest(BaseModel):
    code: str = Field(..., max_length=200000)
    module_path: str | None = None
    max_nesting_threshold: int = Field(default=5, ge=2, le=20)


class StandardsReviewRequest(DiagnosticsRequest):
    save: bool = True


def _strip_diff_path(path: str) -> str | None:
    path = path.strip().split("\t", 1)[0]
    if path == "/dev/null":
        return None
    if path.startswith(("a/", "b/")):
        path = path[2:]
    if ".bsl" not in path.lower():
        return None
    marker_idx = path.lower().find(".bsl")
    return path[: marker_idx + 4].replace("\\", "/")


def _extract_diff_modules(diff: str | None) -> list[str]:
    if not diff:
        return []
    modules = []
    for line in diff.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            path = _strip_diff_path(line[4:])
            if path:
                modules.append(path)
    return list(dict.fromkeys(modules))


def _extract_added_code(diff: str | None) -> dict[str, str]:
    if not diff:
        return {}
    current: str | None = None
    added: dict[str, list[str]] = {}
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = _strip_diff_path(line[4:])
            if current:
                added.setdefault(current, [])
            continue
        if line.startswith("--- "):
            continue
        if current and line.startswith("+") and not line.startswith("+++"):
            added[current].append(line[1:])
    return {path: "\n".join(lines) for path, lines in added.items() if lines}


def _dedupe(seq: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in seq if item and item.strip()))


def _quality_findings(module_path: str, quality: dict | None) -> list[StandardsFinding]:
    if not quality:
        return [
            StandardsFinding(
                module_path=module_path,
                source="quality-store",
                severity="warning",
                message="Модуль не найден в quality store; проверьте путь или пересоберите Рентген.",
            )
        ]

    findings = []
    if int(quality.get("risk", 0)) >= 60:
        findings.append(
            StandardsFinding(
                module_path=module_path,
                source="quality-store",
                severity="high",
                message="Изменение попадает в модуль с высоким объяснимым риском.",
                details={"risk": quality.get("risk"), "reasons": quality.get("reasons", [])},
            )
        )
    if quality.get("has_n_plus_one"):
        findings.append(
            StandardsFinding(
                module_path=module_path,
                source="quality-store",
                severity="high",
                message="В модуле есть признак запроса в цикле (N+1).",
            )
        )
    if quality.get("has_empty_catch"):
        findings.append(
            StandardsFinding(
                module_path=module_path,
                source="quality-store",
                severity="medium",
                message="В модуле есть пустой блок Попытка/Исключение.",
            )
        )
    return findings


def _swarm_findings(module_path: str, code: str | None) -> list[StandardsFinding]:
    if not code or not code.strip():
        return []
    from src.micro_swarm.router import SwarmRouter

    result = SwarmRouter.default().review(code)
    if result.decision.value == "clean":
        return []
    return [
        StandardsFinding(
            module_path=module_path,
            source="micro-swarm",
            severity="high" if result.decision.value == "llm_required" else "medium",
            message=result.response or "Micro-Swarm нашёл потенциальные проблемы в изменённых строках.",
            details={
                "decision": result.decision.value,
                "confidence": result.confidence,
                "scores": result.scores,
            },
        )
    ]


def _diagnostic_findings(module_path: str, code: str | None) -> list[StandardsFinding]:
    if not code or not code.strip():
        return []

    result = review_bsl_standards(code, module_path=module_path)
    findings: list[StandardsFinding] = []
    for finding in result["findings"]:
        findings.append(
            StandardsFinding(
                module_path=module_path,
                source=finding["source"],
                severity=finding["severity"],
                code=finding["rule_id"],
                rule_id=finding["rule_id"],
                standard=finding["standard"],
                line=finding["line"],
                message=finding["message"],
                details=finding.get("details", {}),
                autofix=finding.get("autofix"),
            )
        )
    return findings


class PredictRequest(BaseModel):
    loc: int = 0
    cyclomatic_complexity: int = 1
    max_nesting: int = 0
    doc_coverage: float = 0.0
    comment_density: float = 0.0
    has_module_header: bool = False
    num_functions: int = 0
    avg_func_length: float = 0.0
    export_ratio: float = 0.0
    avg_identifier_length: float = 0.0
    has_error_handling: bool = False
    has_n_plus_one: bool = False
    has_select_star: bool = False
    has_empty_catch: bool = False
    has_magic_numbers: bool = False
    has_deep_nesting: bool = False
    num_todo_fixme: int = 0
    num_referenced_objects: int = 0


class PredictResponse(BaseModel):
    code_quality: int
    complexity_score: int
    documentation_score: int
    maintainability_score: int


@router.get("/module", response_model=ModuleScore | None)
def module(path: str = Query(..., description="Module path (relative)")):
    """Get quality scores for a single BSL module."""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    return store.get_module(path)


@router.get("/summary", response_model=QualitySummary)
def summary():
    """Aggregate quality scores across all scored modules."""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    return QualitySummary(**store.summary())


@router.get("/worst", response_model=list[ModuleScore])
def worst(limit: int = Query(20, ge=1, le=100)):
    """Get worst-scored modules by maintainability."""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    return [ModuleScore(**r) for r in store.worst(limit)]


@router.get("/search", response_model=list[ModuleScore])
def search(q: str = Query(..., min_length=2), limit: int = Query(20, ge=1, le=100)):
    """Search scored modules by path substring."""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    return [ModuleScore(**r) for r in store.search(q, limit)]


@router.get("/hotspots", response_model=list[Hotspot])
def hotspots(
    limit: int = Query(30, ge=1, le=200),
    domain: str | None = Query(None, description="Filter by quality domain"),
    min_fan_in: int = Query(0, ge=0, description="Only modules with >= this fan-in"),
):
    """Explainable risk hotspots: ranks modules by a transparent risk score that
    blends maintainability, complexity, anti-patterns and call-graph blast radius
    (fan-in). Every hotspot carries the per-factor `reasons` that produced its
    score — the number is never a black box."""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    return [Hotspot(**h) for h in store.hotspots(limit, domain, min_fan_in)]


@router.post("/review-diff", response_model=ReviewDiffResponse)
def review_diff(req: ReviewDiffRequest):
    """Whole-config review for changed BSL modules or a unified diff."""
    changed_modules = _dedupe(req.changed_modules + _extract_diff_modules(req.diff))
    if not changed_modules:
        raise HTTPException(
            400,
            "Provide changed_modules or a unified diff with .bsl file paths.",
        )

    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)

    added_code = _extract_added_code(req.diff)
    items: list[ReviewDiffItem] = []
    total_edges = 0
    total_findings = 0

    for module_path in changed_modules:
        quality = store.get_module_risk(module_path)
        impact = store.module_impact(
            module_path,
            max_depth=req.max_depth,
            max_edges=req.max_edges,
        )
        impacted_module_names = [m["module"] for m in impact["impacted_modules"]]
        impacted_hotspots = store.hotspots_for_graph_modules(
            impacted_module_names,
            limit=req.hotspot_limit,
        )

        code = added_code.get(module_path)
        findings = (
            _quality_findings(module_path, quality)
            + _diagnostic_findings(module_path, code)
            + _swarm_findings(module_path, code)
        )
        total_findings += len(findings)
        total_edges += impact["total"]

        items.append(
            ReviewDiffItem(
                module_path=module_path,
                canonical=impact["canonical"],
                graph_modules=impact["graph_modules"],
                quality=quality,
                changed_hotspot=(
                    quality if quality and int(quality.get("risk", 0)) >= 40 else None
                ),
                impact_total=impact["total"],
                impacted_modules=impact["impacted_modules"][:50],
                impacted_hotspots=impacted_hotspots,
                standards_findings=findings,
            )
        )

    return ReviewDiffResponse(
        changed_modules=changed_modules,
        modules=items,
        total_impact_edges=total_edges,
        total_findings=total_findings,
        caveats=[
            "Diff review uses added lines only for Micro-Swarm; full-file review needs source checkout access.",
            "Impact is based on the high-precision Рентген graph and may miss dynamic calls.",
        ],
    )


@router.get("/stats")
def stats():
    """Graph + quality store statistics (for dashboards)."""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    return {**store.get_stats(), "meta": store.db_meta()}


@router.post("/diagnostics")
def diagnostics(req: DiagnosticsRequest):
    """Run deterministic offline BSL diagnostics for pasted code or diff hunks."""

    if not req.code.strip():
        raise HTTPException(400, "Code cannot be empty")
    return analyze_bsl(
        req.code,
        module_path=req.module_path,
        max_nesting_threshold=req.max_nesting_threshold,
    )


@router.post("/standards-review")
def standards_review(req: StandardsReviewRequest):
    """Run catalog-aware offline BSL standards review with auto-fix hints."""

    if not req.code.strip():
        raise HTTPException(400, "Code cannot be empty")
    report = review_bsl_standards(
        req.code,
        module_path=req.module_path,
        max_nesting_threshold=req.max_nesting_threshold,
    )
    if req.save:
        report["stored"] = save_standards_review(report)
    return report


@router.get("/standards-findings")
def standards_findings(
    module_path: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """List locally persisted standards findings by module."""

    return list_standards_findings(module_path=module_path, limit=limit)


@router.get("/standards-catalog")
def standards_catalog():
    """Return the local standards catalog used by fallback review."""

    return {"items": STANDARDS_CATALOG, "total": len(STANDARDS_CATALOG)}


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    """Predict quality scores for a BSL module given its features (no DB)."""
    import sys
    from pathlib import Path as _Path

    tools = str(_Path(__file__).resolve().parents[2] / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from bsl_scoring.score import (
        predict_quality,
        score_complexity,
        score_documentation,
        score_maintainability,
    )

    features = req.model_dump()
    features["referenced_objects"] = [None] * req.num_referenced_objects

    cx = score_complexity(
        cyclomatic=req.cyclomatic_complexity,
        max_nesting=req.max_nesting,
        loc=req.loc,
        num_functions=req.num_functions,
        avg_func_length=req.avg_func_length,
        has_n_plus_one=req.has_n_plus_one,
    )
    doc = score_documentation(
        doc_coverage=req.doc_coverage,
        comment_density=req.comment_density,
        has_module_header=req.has_module_header,
        num_functions=req.num_functions,
        loc=req.loc,
    )
    mi = score_maintainability(
        complexity_score=cx,
        documentation_score=doc,
        loc=req.loc,
        has_empty_catch=req.has_empty_catch,
        has_magic_numbers=req.has_magic_numbers,
        export_ratio=req.export_ratio,
        avg_identifier_length=req.avg_identifier_length,
    )
    cq = predict_quality(features)
    return PredictResponse(
        code_quality=cq if cq is not None else 50,
        complexity_score=cx,
        documentation_score=doc,
        maintainability_score=mi,
    )


class ScoreConfigRequest(BaseModel):
    config_path: str
    load_to_neo4j: bool = False


class ScoreConfigResponse(BaseModel):
    total_modules: int
    avg_complexity: float
    avg_documentation: float
    avg_maintainability: float
    classified_count: int
    unclassified_count: int
    loaded_to_neo4j: bool


@router.post("/score-config", response_model=ScoreConfigResponse)
def score_config(req: ScoreConfigRequest):
    """Run the scoring pipeline on a config dir: extract → classify → score."""
    import sys
    import tempfile
    from pathlib import Path as _Path

    tools = str(_Path(__file__).resolve().parents[2] / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from bsl_scoring.classify import run_classification
    from bsl_scoring.extract import run_extraction
    from bsl_scoring.score import run_scoring

    config = _Path(req.config_path)
    if not config.exists():
        raise HTTPException(404, f"Config path not found: {req.config_path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = _Path(tmp)
        features_path = tmp_path / "features.ndjson"
        domains_path = tmp_path / "domains.csv"
        scores_path = tmp_path / "scores.json"

        run_extraction(config_path=config, output=features_path)
        classifications = run_classification(
            config_path=config, features_path=features_path, output=domains_path
        )
        results = run_scoring(
            features_path=features_path, domains_path=domains_path, output=scores_path
        )
        classified = sum(1 for c in classifications if c.get("method") != "none")
        unclassified = len(classifications) - classified

        import json

        scores_data = json.loads(scores_path.read_text(encoding="utf-8"))
        summary = scores_data.get("summary", {})

    return ScoreConfigResponse(
        total_modules=summary.get("total_modules", len(results)),
        avg_complexity=summary.get("avg_complexity", 0),
        avg_documentation=summary.get("avg_documentation", 0),
        avg_maintainability=summary.get("avg_maintainability", 0),
        classified_count=classified,
        unclassified_count=unclassified,
        loaded_to_neo4j=False,
    )
