"""Runtime metric exports are bounded, authorized and context-bound."""

import json

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.owner_report import build_owner_report
from rentgen_core.runtime_metrics import (
    RuntimeFreshnessPolicy,
    assess_runtime_report,
    load_runtime_report,
)


PROJECT = "12345678-1234-5678-1234-567812345678"
SNAPSHOT = "b" * 64
COMMIT = "a" * 40
SOURCE_DIGEST = "c" * 64
AS_OF = "2026-09-08T00:00:00+00:00"


def payload(*, complete=True):
    return {
        "schema": 1,
        "adapter_id": "erp-runtime-v1",
        "source_ref": "export/metrics.json",
        "project_id": PROJECT,
        "snapshot_id": SNAPSHOT,
        "commit": COMMIT,
        "source_digest": SOURCE_DIGEST,
        "period_start": "2026-09-01T00:00:00+00:00",
        "period_end": "2026-09-07T23:59:59+00:00",
        "generated_at": "2026-09-08T00:00:00+00:00",
        "complete": complete,
        "metrics": [
            {
                "metric_id": "orders_count",
                "value": 42,
                "unit": "count",
                "period_start": "2026-09-01T00:00:00+00:00",
                "period_end": "2026-09-07T23:59:59+00:00",
                "source_id": "erp-runtime-v1",
                "observed_at": "2026-09-08T00:00:00+00:00",
            }
        ],
    }


def write_payload(tmp_path, value):
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_load_runtime_report_binds_context_and_reauthorizes(tmp_path):
    calls = []
    report = load_runtime_report(
        write_payload(tmp_path, payload()),
        expected_project_id=PROJECT,
        expected_snapshot_id=SNAPSHOT,
        expected_commit=COMMIT,
        expected_source_digest=SOURCE_DIGEST,
        as_of=AS_OF,
        authorize=lambda: calls.append("authorized"),
    )

    assert report.project_id == PROJECT
    assert report.metrics[0].value == 42
    assert calls == ["authorized", "authorized"]


@pytest.mark.parametrize(
    "field, value",
    [
        ("project_id", "87654321-4321-8765-4321-876543218765"),
        ("snapshot_id", "d" * 64),
        ("commit", "d" * 40),
        ("source_digest", "d" * 64),
    ],
)
def test_load_runtime_report_rejects_context_mismatch(tmp_path, field, value):
    data = payload()
    data[field] = value
    with pytest.raises(CoreError, match="context"):
        load_runtime_report(
            write_payload(tmp_path, data),
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            expected_commit=COMMIT,
            expected_source_digest=SOURCE_DIGEST,
            as_of=AS_OF,
            authorize=lambda: None,
        )


def test_load_runtime_report_rejects_duplicate_or_oversized_input(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(b'{"schema":1,"schema":1}')
    with pytest.raises(CoreError, match="JSON|Runtime"):
        load_runtime_report(
            duplicate,
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            expected_commit=COMMIT,
            expected_source_digest=SOURCE_DIGEST,
            as_of=AS_OF,
            authorize=lambda: None,
        )

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + b"x" * (2 * 1024**2) + b"}")
    with pytest.raises(CoreError):
        load_runtime_report(
            oversized,
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            expected_commit=COMMIT,
            expected_source_digest=SOURCE_DIGEST,
            as_of=AS_OF,
            authorize=lambda: None,
        )


def test_load_runtime_report_keeps_incomplete_status_without_inventing_values(tmp_path):
    report = load_runtime_report(
        write_payload(tmp_path, payload(complete=False)),
        expected_project_id=PROJECT,
        expected_snapshot_id=SNAPSHOT,
        expected_commit=COMMIT,
        expected_source_digest=SOURCE_DIGEST,
        as_of=AS_OF,
        authorize=lambda: None,
    )

    assert report.complete is False
    assert report.metrics[0].value == 42


def test_loaded_report_is_accepted_by_owner_report(tmp_path):
    report = load_runtime_report(
        write_payload(tmp_path, payload()),
        expected_project_id=PROJECT,
        expected_snapshot_id=SNAPSHOT,
        expected_commit=COMMIT,
        expected_source_digest=SOURCE_DIGEST,
        as_of=AS_OF,
        authorize=lambda: None,
    )

    owner = build_owner_report(
        PROJECT, SNAPSHOT, runtime=report, authorize=lambda: None
    )
    assert owner["business_metrics"]["status"] == "available"


def load(tmp_path, data=None, *, as_of=AS_OF, **kwargs):
    return load_runtime_report(
        write_payload(tmp_path, payload() if data is None else data),
        expected_project_id=PROJECT,
        expected_snapshot_id=SNAPSHOT,
        expected_commit=COMMIT,
        expected_source_digest=SOURCE_DIGEST,
        authorize=lambda: None,
        as_of=as_of,
        **kwargs,
    )


def test_stale_loader_fails_closed_instead_of_returning_available_evidence(tmp_path):
    with pytest.raises(CoreError) as exc:
        load(tmp_path, as_of="2026-09-09T00:00:01Z")
    assert exc.value.code == "OWNER_RUNTIME_STALE"


def test_assessment_rechecks_age_and_exact_boundary_without_values(tmp_path):
    report = load(tmp_path)
    for as_of, status in [
        (AS_OF, "available"),
        ("2026-09-09T00:00:00Z", "available"),
        ("2026-09-09T00:00:01Z", "stale"),
    ]:
        assessment = assess_runtime_report(report, as_of=as_of)
        assert assessment.status == status
        assert not hasattr(assessment, "metrics")
    assert assessment.reason == "runtime_report_stale"


@pytest.mark.parametrize(
    "changes",
    [
        {"max_age_seconds": 0},
        {"max_age_seconds": True},
        {"max_age_seconds": 366 * 86400 + 1},
        {"max_period_seconds": 0},
        {"max_period_seconds": float("inf")},
        {"expected_period_start": AS_OF},
        {"expected_period_start": AS_OF, "expected_period_end": "2026-09-07T00:00:00Z"},
        {"expected_period_start": "2026-09-01", "expected_period_end": AS_OF},
    ],
)
def test_invalid_policy_is_rejected(changes):
    with pytest.raises(CoreError) as exc:
        RuntimeFreshnessPolicy(**changes)
    assert exc.value.code == "OWNER_RUNTIME_INVALID"


def test_stricter_consumer_policy_blocks_older_evidence(tmp_path):
    with pytest.raises(CoreError) as exc:
        load(
            tmp_path,
            as_of="2026-09-08T00:01:01Z",
            freshness_policy=RuntimeFreshnessPolicy(max_age_seconds=60),
        )
    assert exc.value.code == "OWNER_RUNTIME_STALE"


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-09-02T00:00:00Z", "2026-09-07T23:59:59Z"),
        ("2026-09-01T00:00:00Z", "2026-09-07T23:59:58Z"),
    ],
)
def test_expected_period_requires_exact_instants(tmp_path, start, end):
    with pytest.raises(CoreError) as exc:
        load(
            tmp_path,
            freshness_policy=RuntimeFreshnessPolicy(
                expected_period_start=start,
                expected_period_end=end,
            ),
        )
    assert exc.value.code == "OWNER_RUNTIME_PERIOD"


def test_equivalent_timezone_period_is_accepted(tmp_path):
    policy = RuntimeFreshnessPolicy(
        expected_period_start="2026-09-01T10:00:00+10:00",
        expected_period_end="2026-09-08T09:59:59+10:00",
    )
    report = load(tmp_path, freshness_policy=policy)
    assert (
        assess_runtime_report(report, as_of=AS_OF, freshness_policy=policy).status
        == "available"
    )


@pytest.mark.parametrize("kind", ["partial", "empty", "declared_incomplete"])
def test_incomplete_runtime_never_reaches_owner_report_as_available(tmp_path, kind):
    data = payload()
    if kind == "partial":
        data["metrics"][0]["period_start"] = "2026-09-02T00:00:00Z"
    elif kind == "empty":
        data["metrics"] = []
    else:
        data["complete"] = False
    report = load(tmp_path, data)
    assert report.complete is False
    assert assess_runtime_report(report, as_of=AS_OF).status == "incomplete"
    owner = build_owner_report(
        PROJECT,
        SNAPSHOT,
        runtime=report,
        authorize=lambda: None,
    )
    assert owner["business_metrics"]["status"] == "incomplete"
    assert owner["business_metrics"]["metrics"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("generated_at", "2026-09-07T23:59:58Z"),
        ("generated_at", "2026-09-08T00:00:01Z"),
        ("observed_at", "2026-09-07T23:59:58Z"),
        ("observed_at", "2026-09-08T00:00:01Z"),
    ],
)
def test_impossible_timestamp_order_is_rejected(tmp_path, field, value):
    data = payload()
    target = data["metrics"][0] if field == "observed_at" else data
    target[field] = value
    with pytest.raises(CoreError) as exc:
        load(tmp_path, data)
    assert exc.value.code == "OWNER_RUNTIME_INVALID"


def test_policy_bounds_report_duration(tmp_path):
    with pytest.raises(CoreError) as exc:
        load(
            tmp_path, freshness_policy=RuntimeFreshnessPolicy(max_period_seconds=86400)
        )
    assert exc.value.code == "OWNER_RUNTIME_PERIOD"


def test_fresh_generation_cannot_resurrect_old_observations(tmp_path):
    data = payload()
    data["generated_at"] = "2026-09-10T00:00:00Z"
    with pytest.raises(CoreError) as exc:
        load(tmp_path, data, as_of="2026-09-10T00:00:00Z")
    assert exc.value.code == "OWNER_RUNTIME_STALE"


def test_metric_count_is_bounded_before_construction(tmp_path, monkeypatch):
    def unexpected(**kwargs):
        pytest.fail("Oversized metric array must be rejected before construction")

    data = payload()
    data["metrics"] *= 1001
    monkeypatch.setattr("rentgen_core.runtime_metrics.RuntimeMetric", unexpected)
    with pytest.raises(CoreError):
        load(tmp_path, data)


def test_runtime_read_revoked_before_return_fails_closed(tmp_path):
    calls = []

    def authorize():
        calls.append(None)
        if len(calls) == 2:
            raise CoreError("ACCESS_DENIED", "Revoked")

    with pytest.raises(CoreError, match="Revoked"):
        load_runtime_report(
            write_payload(tmp_path, payload()),
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            expected_commit=COMMIT,
            expected_source_digest=SOURCE_DIGEST,
            authorize=authorize,
            as_of=AS_OF,
        )
    assert len(calls) == 2


def test_export_cannot_override_consumer_policy(tmp_path):
    data = payload()
    data["freshness_policy"] = {"max_age_seconds": 366 * 86400}
    with pytest.raises(CoreError, match="schema"):
        load(tmp_path, data)


@pytest.mark.parametrize("as_of", ["2026-09-08", "bad", True])
def test_loader_rejects_invalid_clock(tmp_path, as_of):
    with pytest.raises(CoreError) as exc:
        load(tmp_path, as_of=as_of)
    assert exc.value.code == "OWNER_RUNTIME_INVALID"


def test_freshness_clock_is_sampled_after_final_authorization(tmp_path, monkeypatch):
    from datetime import datetime

    clock = [AS_OF]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(clock[0])

    monkeypatch.setattr("rentgen_core.runtime_metrics.datetime", Clock)
    calls = []

    def authorize():
        calls.append(None)
        if len(calls) == 2:
            clock[0] = "2026-09-10T00:00:00+00:00"

    with pytest.raises(CoreError) as exc:
        load_runtime_report(
            write_payload(tmp_path, payload()),
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            expected_commit=COMMIT,
            expected_source_digest=SOURCE_DIGEST,
            authorize=authorize,
        )
    assert exc.value.code == "OWNER_RUNTIME_STALE"
    assert len(calls) == 2
