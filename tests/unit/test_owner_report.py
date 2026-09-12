"""Owner report keeps quality and business values bound to explicit evidence."""

from dataclasses import replace

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.git_observer import Finding, FindingReport, GitObservation
from rentgen_core.git_observer import reconcile_findings
from rentgen_core.owner_report import (
    RuntimeMetric,
    RuntimeMetricReport,
    build_owner_report,
)

PROJECT = "12345678-1234-5678-1234-567812345678"
SNAPSHOT = "b" * 64
COMMIT = "a" * 40


def finding_state():
    observation = GitObservation("C:/repo", COMMIT, "refs/heads/main")
    report = FindingReport(
        observation,
        "bsl-profile-v1",
        "whole-repository-bsl",
        True,
        (
            Finding("bsl/one", "B.bsl", "B:2", "second", 2),
            Finding("bsl/one", "A.bsl", "A:1", "first", 1),
        ),
    )
    return reconcile_findings(None, report).state


def runtime(*, complete=True, **changes):
    value = RuntimeMetricReport(
        project_id=PROJECT,
        snapshot_id=SNAPSHOT,
        commit=COMMIT,
        adapter_id="erp-runtime-v1",
        source_ref="db://test/metrics",
        source_digest="c" * 64,
        period_start="2026-09-01T00:00:00+00:00",
        period_end="2026-09-07T23:59:59+00:00",
        generated_at="2026-09-08T00:00:00+00:00",
        complete=complete,
        metrics=(
            RuntimeMetric(
                "orders_count",
                42,
                "count",
                "2026-09-01T00:00:00+00:00",
                "2026-09-07T23:59:59+00:00",
                "erp-runtime-v1",
                "2026-09-08T00:00:00+00:00",
            ),
        ),
    )
    return replace(value, **changes)


def test_report_without_runtime_is_explicit_and_keeps_sorted_quality_findings():
    result = build_owner_report(PROJECT, SNAPSHOT, findings=finding_state())

    assert result["business_metrics"] == {
        "status": "not_available",
        "reason": "runtime_adapter_not_configured",
    }
    assert result["quality"]["status"] == "available"
    assert result["quality"]["open"] == 2
    assert [item["path"] for item in result["quality"]["findings"]] == [
        "A.bsl",
        "B.bsl",
    ]


def test_complete_runtime_values_are_bound_to_project_snapshot_and_commit():
    result = build_owner_report(
        PROJECT,
        SNAPSHOT,
        findings=finding_state(),
        runtime=runtime(),
        authorize=lambda: None,
    )

    assert result["business_metrics"]["status"] == "available"
    assert result["business_metrics"]["source"]["adapter_id"] == "erp-runtime-v1"
    assert result["business_metrics"]["source"]["snapshot_id"] == SNAPSHOT
    assert result["business_metrics"]["metrics"][0]["value"] == 42


def test_incomplete_runtime_never_exposes_metric_values():
    result = build_owner_report(
        PROJECT, SNAPSHOT, runtime=runtime(complete=False), authorize=lambda: None
    )

    assert result["business_metrics"]["status"] == "incomplete"
    assert result["business_metrics"]["metrics"] == []
    assert result["business_metrics"]["source"]["source_digest"] == "c" * 64


@pytest.mark.parametrize(
    "changes",
    [
        {"project_id": "87654321-4321-8765-4321-876543218765"},
        {"snapshot_id": "d" * 64},
        {"commit": "d" * 40},
    ],
)
def test_runtime_context_mismatch_is_rejected(changes):
    with pytest.raises(CoreError, match="context|match"):
        build_owner_report(
            PROJECT,
            SNAPSHOT,
            findings=finding_state(),
            runtime=runtime(**changes),
            authorize=lambda: None,
        )


def test_duplicate_metric_identity_and_invalid_period_are_rejected():
    duplicate = RuntimeMetric(
        "orders_count",
        7,
        "count",
        "2026-09-01T00:00:00+00:00",
        "2026-09-07T23:59:59+00:00",
        "erp-runtime-v1",
        "2026-09-08T00:00:00+00:00",
    )
    with pytest.raises(CoreError, match="[Dd]uplicate"):
        build_owner_report(
            PROJECT,
            SNAPSHOT,
            runtime=replace(runtime(), metrics=(runtime().metrics[0], duplicate)),
            authorize=lambda: None,
        )

    with pytest.raises(CoreError, match="period"):
        RuntimeMetric(
            "bad",
            1,
            "count",
            "2026-09-08T00:00:00+00:00",
            "2026-09-01T00:00:00+00:00",
            "adapter",
            "2026-09-08T00:00:00+00:00",
        )


def test_authorizer_is_required_to_complete_before_values_are_built():
    calls = []

    result = build_owner_report(
        PROJECT, SNAPSHOT, runtime=runtime(), authorize=lambda: calls.append("ok")
    )

    assert calls == ["ok"]
    assert result["business_metrics"]["status"] == "available"

    with pytest.raises(CoreError, match="authorization"):
        build_owner_report(PROJECT, SNAPSHOT, runtime=runtime(), authorize=None)
