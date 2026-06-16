# -*- coding: utf-8 -*-
"""Unit tests for the Рентген engine (tools/rentgen/store.py :: RentgenStore).

These run against the prebuilt SQLite store at data/rentgen.db. If that DB has
not been built, the whole module is skipped (see ``pytestmark`` below).

The store opens short-lived read-only connections per call, so no fixtures are
needed beyond ``get_store()`` (cached singleton).
"""

import sys

import pytest

sys.path.insert(0, r"C:\1cAI\tools")
from rentgen.store import get_store, RentgenStore, DB_PATH  # noqa: E402

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="rentgen.db not built")


@pytest.fixture(scope="module")
def store() -> RentgenStore:
    return get_store()


# --------------------------------------------------------------------------- #
# 1. db_meta
# --------------------------------------------------------------------------- #
def test_db_meta_has_expected_keys(store):
    meta = store.db_meta()
    assert isinstance(meta, dict)
    for key in ("n_subroutines", "n_modules", "n_call_edges", "n_quality"):
        assert key in meta, f"db_meta() missing key {key!r}"


# --------------------------------------------------------------------------- #
# 2. get_stats
# --------------------------------------------------------------------------- #
def test_get_stats_magnitudes_and_top_fan_in(store):
    stats = store.get_stats()

    assert stats["subroutines"] > 700_000
    assert stats["modules"] > 18_000
    assert stats["call_edges"] > 1_400_000
    assert stats["quality_modules"] == 26_748

    top = stats["top_fan_in"]
    assert isinstance(top, list)
    assert len(top) > 0, "top_fan_in should be non-empty"

    names = [row["name"] for row in top]
    assert "ОбщегоНазначения" in names, (
        "expected well-known common module 'ОбщегоНазначения' in top_fan_in; "
        f"got {names}"
    )

    # #1 by fan_in must be a common (1-segment) module name — no '.' in name.
    assert "." not in top[0]["name"], (
        f"top fan-in module should be a 1-segment name, got {top[0]['name']!r}"
    )


# --------------------------------------------------------------------------- #
# 3. summary
# --------------------------------------------------------------------------- #
def test_summary(store):
    summ = store.summary()

    assert summ["total_modules"] == 26_748
    assert len(summ["by_domain"]) > 0, "by_domain should be non-empty"

    avg_mi = summ["avg_maintainability"]
    assert 0 < avg_mi < 100, f"avg_maintainability out of range: {avg_mi}"


# --------------------------------------------------------------------------- #
# 4. worst
# --------------------------------------------------------------------------- #
def test_worst_returns_sorted_dicts(store):
    rows = store.worst(5)

    assert isinstance(rows, list)
    assert len(rows) == 5
    assert all(isinstance(r, dict) for r in rows)

    for r in rows:
        for key in ("module_path", "complexity_score", "maintainability_score"):
            assert key in r, f"worst() row missing key {key!r}"

    scores = [r["maintainability_score"] for r in rows]
    assert scores == sorted(scores), (
        f"maintainability_score should be non-decreasing across worst(); got {scores}"
    )


# --------------------------------------------------------------------------- #
# 5. search
# --------------------------------------------------------------------------- #
def test_search_filters_by_substring(store):
    rows = store.search("Module", 10)

    assert isinstance(rows, list)
    assert len(rows) > 0, "search('Module') should be non-empty"
    assert all("Module" in r["module_path"] for r in rows), (
        "every search result module_path should contain the query substring"
    )


# --------------------------------------------------------------------------- #
# 6. get_module
# --------------------------------------------------------------------------- #
def test_get_module_roundtrip(store):
    path = store.worst(1)[0]["module_path"]
    mod = store.get_module(path)

    assert isinstance(mod, dict)
    assert mod["module_path"] == path


# --------------------------------------------------------------------------- #
# 6b. module risk / module path -> graph mapping
# --------------------------------------------------------------------------- #
def test_get_module_risk_and_module_impact(store):
    path = store.hotspots(1)[0]["module_path"]

    risk = store.get_module_risk(path)
    assert isinstance(risk, dict)
    assert risk["module_path"] == path
    assert risk["risk"] > 0
    assert isinstance(risk["reasons"], list)

    impact = store.module_impact(path, max_depth=1, max_edges=50)
    assert impact["canonical"]["source"] == "module_path"
    assert len(impact["graph_modules"]) >= 1
    assert impact["entry_subroutines"] > 0
    assert impact["total"] > 0
    assert len(impact["impacted_modules"]) > 0


def test_hotspots_for_graph_modules(store):
    path = store.hotspots(1)[0]["module_path"]
    impact = store.module_impact(path, max_depth=1, max_edges=50)
    graph_modules = [m["module"] for m in impact["impacted_modules"]]

    rows = store.hotspots_for_graph_modules(graph_modules, limit=5)
    assert isinstance(rows, list)
    assert len(rows) <= 5
    for row in rows:
        assert "risk" in row
        assert "module_path" in row


# --------------------------------------------------------------------------- #
# 7. hotspots
# --------------------------------------------------------------------------- #
def test_hotspots_explainable_and_sorted(store):
    rows = store.hotspots(10)

    assert isinstance(rows, list)
    assert len(rows) == 10
    assert all(isinstance(r, dict) for r in rows)

    # risk bounded to 0..100
    assert all(0 <= r["risk"] <= 100 for r in rows), (
        f"risk out of 0..100: {[r['risk'] for r in rows]}"
    )

    # risk sorted descending (non-increasing)
    risks = [r["risk"] for r in rows]
    assert risks == sorted(risks, reverse=True), f"risk not sorted descending: {risks}"

    # each row has a non-empty, structured reasons list
    for r in rows:
        reasons = r["reasons"]
        assert isinstance(reasons, list) and len(reasons) > 0, (
            f"hotspot {r['module_path']!r} has empty reasons"
        )
        for reason in reasons:
            for key in ("factor", "detail", "weight"):
                assert key in reason, f"reason missing key {key!r}: {reason}"


# --------------------------------------------------------------------------- #
# 8. get_impact_analysis (callers / blast radius)
# --------------------------------------------------------------------------- #
def test_impact_analysis_of_heavily_called_bsp_function(store):
    edges = store.get_impact_analysis("ЗначениеРеквизитаОбъекта")

    assert isinstance(edges, list)
    assert len(edges) > 0, "impact analysis of a heavily-called BSP fn should be non-empty"

    for edge in edges:
        for key in ("caller", "caller_module", "callee", "callee_module", "depth"):
            assert key in edge, f"impact edge missing key {key!r}: {edge}"


# --------------------------------------------------------------------------- #
# 9. get_execution_flow
# --------------------------------------------------------------------------- #
def test_execution_flow_non_empty(store):
    edges = store.get_execution_flow("ПроверитьВозможностьВыгрузки")

    assert isinstance(edges, list)
    assert len(edges) > 0, "execution flow should return a non-empty list of edges"


# --------------------------------------------------------------------------- #
# 10. dead_code
# --------------------------------------------------------------------------- #
def test_dead_code_common_scope(store):
    result = store.dead_code(5, scope="common")

    assert isinstance(result, dict)
    assert result["scope"] == "common"
    assert result["total"] > 0
    assert len(result["candidates"]) <= 5

    # common scope ⇒ every candidate is a 1-segment (common) module: no '.'
    for cand in result["candidates"]:
        assert "." not in cand["module"], (
            f"common-scope dead_code candidate should be a common module, "
            f"got {cand['module']!r}"
        )
