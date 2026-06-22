# -*- coding: utf-8 -*-
"""Regression tests for ENGINE finding C6 — the change-impact silent false-zero.

FORMS are ~44% of all modules (≈11,903). They USED to be absent from the call
graph (the Go scanner mislabeled form modules and merged them into the object),
so a form's module_path resolved to zero graph nodes and ``build_change_plan``
returned ``impact_total == 0`` with no caveat — a silent false-zero the UI read
as "safe to change". The scanner now emits form modules as ``<Object>.Form``, so
forms ARE measured. The no_graph_data path remains for modules genuinely absent
from the graph.

These tests pin the honest behaviour:
  * a form module -> coverage == "in_graph" with measured impact (the fix);
  * a module genuinely absent from the graph -> coverage == "no_graph_data" + a
    caveat, NEVER a bare zero presented as "safe";
  * a real common module -> coverage == "in_graph" with measured impact;
  * the CI gate surfaces an unmeasured module as a (non-fatal) warning instead
    of silently passing it as safe;
  * the markdown report prints "НЕ ИЗМЕРЕНО", not "Impact edges: 0".

Most tests run against the prebuilt store at data/rentgen.db and are skipped if
it has not been built. The gate/markdown shape tests use a tiny fake store so
they run regardless.
"""

import sys

import pytest

sys.path.insert(0, r"C:\1cAI\tools")
from rentgen.store import DB_PATH, RentgenStore, get_store  # noqa: E402

from src.services.rentgen.change_plan import (  # noqa: E402
    COVERAGE_IN_GRAPH,
    COVERAGE_NO_GRAPH_DATA,
    assess_ci_gate,
    build_change_plan,
    impact_coverage,
    render_markdown_report,
)

db_required = pytest.mark.skipif(not DB_PATH.exists(), reason="rentgen.db not built")


@pytest.fixture(scope="module")
def store() -> RentgenStore:
    return get_store()


def _a_form_path(store: RentgenStore) -> str:
    for row in store.search("/Forms/", 50):
        path = row["module_path"]
        if path.lower().endswith("form/module.bsl"):
            return path
    pytest.skip("no form module_path found in store")


def _a_common_path(store: RentgenStore) -> str:
    for hot in store.hotspots(40):
        path = hot["module_path"]
        if "CommonModules/" in path and "/Forms/" not in path:
            impact = store.module_impact(path, max_depth=1, max_edges=50)
            if impact["graph_modules"] and impact["total"] > 0:
                return path
    pytest.skip("no resolvable common module found in store")


# --------------------------------------------------------------------------- #
# impact_coverage classifier (pure, no DB)                                     #
# --------------------------------------------------------------------------- #
def test_impact_coverage_classifier():
    in_graph, caveat = impact_coverage({"graph_modules": [{"name": "X"}], "total": 12})
    assert in_graph == COVERAGE_IN_GRAPH
    assert caveat is None

    no_graph, caveat = impact_coverage({"graph_modules": [], "total": 0})
    assert no_graph == COVERAGE_NO_GRAPH_DATA
    assert caveat and "НЕ измерен" in caveat


# --------------------------------------------------------------------------- #
# Forms are now IN the graph (the C6 fix): a form must be measured, not flagged #
# --------------------------------------------------------------------------- #
@db_required
def test_form_module_now_measured_in_graph(store):
    form_path = _a_form_path(store)

    # The scanner now emits <Object>.Form, so a form resolves to a graph node.
    impact = store.module_impact(form_path)
    assert impact["graph_modules"], "form must now resolve to a graph node"

    plan = build_change_plan(store, [form_path])
    item = plan["modules"][0]

    assert item["coverage"] == COVERAGE_IN_GRAPH
    assert item["impact_measured"] is True
    assert item["coverage_caveat"] is None
    assert form_path not in plan["unmeasured_modules"]


# --------------------------------------------------------------------------- #
# THE false-zero guard: a module genuinely absent from the graph must carry    #
# no_graph_data + caveat, never a bare 0 presented as "safe".                  #
# --------------------------------------------------------------------------- #
_GHOST_PATH = "Documents/ЯНесуществующийОбъектРентгенТест999/Ext/ObjectModule.bsl"


@db_required
def test_unresolved_module_is_flagged_not_silent_zero(store):
    # Precondition: this fabricated object is not in the config / graph.
    impact = store.module_impact(_GHOST_PATH)
    assert impact["graph_modules"] == []
    assert impact["total"] == 0

    plan = build_change_plan(store, [_GHOST_PATH])
    item = plan["modules"][0]

    # impact_total is 0 — but it is explicitly UNMEASURED, not "safe".
    assert item["impact_total"] == 0
    assert item["impact_measured"] is False
    assert item["coverage"] == COVERAGE_NO_GRAPH_DATA
    assert item["coverage_caveat"], "unresolved item must carry a coverage caveat"
    assert "НЕ измерен" in item["coverage_caveat"]
    assert "это не ноль" in item["coverage_caveat"]

    assert _GHOST_PATH in plan["unmeasured_modules"]
    assert any(
        "НЕ измерен" in c for c in plan["caveats"]
    ), "top-level caveats must warn that some modules were not measured"


# --------------------------------------------------------------------------- #
# A real common module still resolves and reports measured impact             #
# --------------------------------------------------------------------------- #
@db_required
def test_common_module_still_measured(store):
    common_path = _a_common_path(store)

    plan = build_change_plan(store, [common_path], max_depth=1, max_edges=50)
    item = plan["modules"][0]

    assert item["coverage"] == COVERAGE_IN_GRAPH
    assert item["impact_measured"] is True
    assert item["coverage_caveat"] is None
    assert item["impact_total"] > 0
    assert len(item["graph_modules"]) >= 1
    assert common_path not in plan["unmeasured_modules"]


# --------------------------------------------------------------------------- #
# Mixed batch: form is flagged, common is measured, both present              #
# --------------------------------------------------------------------------- #
@db_required
def test_mixed_batch_separates_measured_from_unmeasured(store):
    common_path = _a_common_path(store)

    plan = build_change_plan(
        store, [common_path, _GHOST_PATH], max_depth=1, max_edges=50
    )
    by_path = {item["module_path"]: item for item in plan["modules"]}

    assert by_path[common_path]["coverage"] == COVERAGE_IN_GRAPH
    assert by_path[_GHOST_PATH]["coverage"] == COVERAGE_NO_GRAPH_DATA
    assert plan["unmeasured_modules"] == [_GHOST_PATH]


# --------------------------------------------------------------------------- #
# CI gate / markdown shape — deterministic fake store (no DB needed)           #
# --------------------------------------------------------------------------- #
class _UnresolvedFormStore:
    """Mimics a form: resolves to no graph node, zero impact."""

    def get_module_risk(self, module_path):
        # A plausible quality row that is BELOW the risk gate threshold, so the
        # only thing the gate can flag is the unmeasured coverage.
        return {"module_path": module_path, "risk": 20, "reasons": []}

    def module_impact(self, module_path, max_depth=5, max_edges=600):
        return {
            "canonical": {
                "object_name": "x",
                "module_kind": "form",
                "source": "module_path",
            },
            "graph_modules": [],
            "entry_subroutines": 0,
            "total": 0,
            "impacted_modules": [],
        }

    def hotspots_for_graph_modules(self, module_names, limit=10):
        return []


def test_ci_gate_warns_on_unmeasured_form_instead_of_passing():
    plan = build_change_plan(
        _UnresolvedFormStore(),
        ["Catalogs/Заказ/Forms/ФормаДокумента/Ext/Form/Module.bsl"],
    )
    item = plan["modules"][0]
    assert item["coverage"] == COVERAGE_NO_GRAPH_DATA

    gate = assess_ci_gate(plan, risk_threshold=70, impact_threshold=300)

    # Not a hard fail (we don't KNOW it's bad) — but explicitly a warning, never
    # a clean "pass" that hides the unmeasured radius.
    assert gate["status"] == "warn"
    coverage_violations = [v for v in gate["violations"] if v["kind"] == "coverage"]
    assert coverage_violations, "gate must surface an unmeasured-coverage signal"
    assert coverage_violations[0]["severity"] == "warning"

    markdown = render_markdown_report(plan, gate)
    assert "НЕ ИЗМЕРЕНО" in markdown
    assert (
        "Impact edges: 0" not in markdown
    ), "report must not present a bare 'Impact edges: 0' for an unmeasured module"
