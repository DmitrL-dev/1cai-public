"""Durable owner-report receipts preserve bounded evidence and context."""

import json
import os

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.owner_report import (
    RuntimeMetric,
    RuntimeMetricReport,
    build_owner_report,
)
from rentgen_core.owner_report_store import OwnerReportStore


PROJECT = "12345678-1234-5678-1234-567812345678"
SNAPSHOT = "b" * 64


def _report():
    return build_owner_report(PROJECT, SNAPSHOT)


def _store(tmp_path):
    store = OwnerReportStore(tmp_path / "owner-reports")
    store.initialize()
    return store


def test_owner_report_store_saves_reads_and_lists_context_bound_receipt(tmp_path):
    store = _store(tmp_path)
    calls = []

    receipt = store.save(_report(), authorize=lambda: calls.append("auth"))

    assert receipt["status"] == "stored"
    assert receipt["project_id"] == PROJECT
    assert receipt["snapshot_id"] == SNAPSHOT
    report_id = receipt["report_id"]
    loaded = store.get(
        report_id,
        expected_project_id=PROJECT,
        expected_snapshot_id=SNAPSHOT,
        authorize=lambda: calls.append("auth"),
    )
    assert loaded == receipt
    listed = store.list(
        expected_project_id=PROJECT,
        expected_snapshot_id=SNAPSHOT,
        authorize=lambda: calls.append("auth"),
    )
    assert listed == [receipt]
    # POSIX additionally authorizes immediately before atomic publication.
    assert calls == ["auth"] * (7 if os.name == "posix" else 6)


def test_owner_report_store_is_idempotent_for_same_id_and_rejects_conflict(tmp_path):
    store = _store(tmp_path)
    report_id = "12345678-1234-4234-8234-123456789abc"
    report = _report()
    first = store.save(report, report_id=report_id, authorize=lambda: None)

    assert store.save(report, report_id=report_id, authorize=lambda: None) == first
    changed = dict(_report())
    changed["generated_at"] = "2026-09-13T00:00:00+00:00"
    with pytest.raises(CoreError) as error:
        store.save(changed, report_id=report_id, authorize=lambda: None)
    assert error.value.code == "OWNER_REPORT_STORE_CONFLICT"


def test_owner_report_store_rejects_foreign_files_and_tampering(tmp_path):
    store = _store(tmp_path)
    receipt = store.save(_report(), authorize=lambda: None)
    path = store.reports / f"{receipt['report_id']}.json"
    path.write_text(json.dumps({"foreign": True}), encoding="utf-8")
    with pytest.raises(CoreError) as error:
        store.get(
            receipt["report_id"],
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            authorize=lambda: None,
        )
    assert error.value.code == "OWNER_REPORT_STORE_RECOVERY_REQUIRED"

    path.unlink()
    (store.reports / "foreign.txt").write_text("foreign", encoding="utf-8")
    with pytest.raises(CoreError) as error:
        store.list(
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            authorize=lambda: None,
        )
    assert error.value.code == "OWNER_REPORT_STORE_CONFLICT"


def test_owner_report_store_get_fails_closed_on_corrupt_sibling(tmp_path):
    store = _store(tmp_path)
    first = store.save(_report(), authorize=lambda: None)
    second = store.save(_report(), authorize=lambda: None)
    (store.reports / f"{second['report_id']}.json").write_text(
        json.dumps({"broken": True}), encoding="utf-8"
    )
    with pytest.raises(CoreError) as error:
        store.get(
            first["report_id"],
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            authorize=lambda: None,
        )
    assert error.value.code == "OWNER_REPORT_STORE_RECOVERY_REQUIRED"


def test_owner_report_store_rejects_context_and_requires_authorization(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(CoreError) as error:
        store.save(_report(), authorize=None)
    assert error.value.code == "OWNER_REPORT_STORE_AUTHORIZATION"
    receipt = store.save(_report(), authorize=lambda: None)
    with pytest.raises(CoreError) as error:
        store.get(
            receipt["report_id"],
            expected_project_id="87654321-4321-8765-4321-876543218765",
            expected_snapshot_id=SNAPSHOT,
            authorize=lambda: None,
        )
    assert error.value.code == "OWNER_REPORT_STORE_CONTEXT"


def test_owner_report_store_enforces_report_limit(tmp_path, monkeypatch):
    store = _store(tmp_path)
    monkeypatch.setattr(store, "MAX_REPORTS", 1)
    store.save(_report(), authorize=lambda: None)
    with pytest.raises(CoreError) as error:
        store.save(_report(), authorize=lambda: None)
    assert error.value.code == "OWNER_REPORT_STORE_LIMIT"


def test_owner_report_store_preserves_complete_numeric_runtime_evidence(tmp_path):
    runtime = RuntimeMetricReport(
        project_id=PROJECT,
        snapshot_id=SNAPSHOT,
        commit="a" * 40,
        adapter_id="erp-runtime-v1",
        source_ref="export/metrics.json",
        source_digest="c" * 64,
        period_start="2026-09-01T00:00:00+00:00",
        period_end="2026-09-07T23:59:59+00:00",
        generated_at="2026-09-08T00:00:00+00:00",
        complete=True,
        metrics=(
            RuntimeMetric(
                metric_id="margin",
                value=-1.5,
                unit="percent",
                period_start="2026-09-01T00:00:00+00:00",
                period_end="2026-09-07T23:59:59+00:00",
                source_id="erp-runtime-v1",
                observed_at="2026-09-08T00:00:00+00:00",
            ),
        ),
    )
    report = build_owner_report(
        PROJECT, SNAPSHOT, runtime=runtime, authorize=lambda: None
    )
    receipt = _store(tmp_path).save(report, authorize=lambda: None)
    assert receipt["report"]["business_metrics"]["metrics"][0]["value"] == -1.5


def test_owner_report_store_rejects_inconsistent_incomplete_or_nested_context(
    tmp_path,
):
    runtime = RuntimeMetricReport(
        project_id=PROJECT,
        snapshot_id=SNAPSHOT,
        commit="a" * 40,
        adapter_id="erp-runtime-v1",
        source_ref="export/metrics.json",
        source_digest="c" * 64,
        period_start="2026-09-01T00:00:00+00:00",
        period_end="2026-09-07T23:59:59+00:00",
        generated_at="2026-09-08T00:00:00+00:00",
        complete=False,
        metrics=(),
    )
    report = build_owner_report(
        PROJECT, SNAPSHOT, runtime=runtime, authorize=lambda: None
    )
    assert (
        _store(tmp_path).save(report, authorize=lambda: None)["report"][
            "business_metrics"
        ]["status"]
        == "incomplete"
    )
    changed = dict(report)
    business = dict(report["business_metrics"])
    source = dict(business["source"])
    source["project_id"] = "87654321-4321-8765-4321-876543218765"
    business["source"] = source
    changed["business_metrics"] = business
    changed_root = tmp_path / "changed"
    changed_root.mkdir()
    with pytest.raises(CoreError) as error:
        _store(changed_root).save(changed, authorize=lambda: None)
    assert error.value.code == "OWNER_REPORT_STORE_CONTEXT"


GENERATED = "2026-09-01T00:00:00+00:00"


def _dated_report():
    report = dict(_report())
    report["generated_at"] = GENERATED
    return report


def _read_kwargs(**changes):
    return {
        "expected_project_id": PROJECT,
        "expected_snapshot_id": SNAPSHOT,
        "authorize": lambda: None,
        **changes,
    }


def test_owner_report_store_marks_historical_reads_without_changing_receipt(
    tmp_path,
):
    store = _store(tmp_path)
    receipt = store.save(_dated_report(), authorize=lambda: None)
    path = store.reports / f"{receipt['report_id']}.json"
    stored = path.read_bytes()

    def get(as_of, max_age_seconds=3600):
        return store.get(
            receipt["report_id"],
            **_read_kwargs(max_age_seconds=max_age_seconds, as_of=as_of),
        )

    bound = get("2026-09-01T01:00:00Z")
    older = get("2026-09-01T01:00:00.000001+00:00")
    future = get("2026-08-31T23:59:59+00:00")
    assert bound["freshness"] == {
        "as_of": "2026-09-01T01:00:00+00:00",
        "age_seconds": 3600,
        "max_age_seconds": 3600,
        "historical": False,
        "reason": None,
    }
    assert older["freshness"] == {
        "as_of": "2026-09-01T01:00:00.000001+00:00",
        "age_seconds": 3601,
        "max_age_seconds": 3600,
        "historical": True,
        "reason": "older_than_policy",
    }
    assert future["freshness"]["age_seconds"] is None
    assert future["freshness"]["historical"] is True
    assert future["freshness"]["reason"] == "generated_after_as_of"
    for view in (bound, older, future):
        assert {key: view[key] for key in view if key != "freshness"} == receipt
    assert store.get(receipt["report_id"], **_read_kwargs()) == receipt
    assert path.read_bytes() == stored
    # Editing the sealed generation time cannot make old evidence look fresh.
    path.write_bytes(stored.replace(GENERATED.encode(), b"2026-09-01T00:59:00+00:00"))
    with pytest.raises(CoreError) as error:
        get("2026-09-01T01:00:00+00:00")
    assert error.value.code == "OWNER_REPORT_STORE_RECOVERY_REQUIRED"


def test_owner_report_store_lists_with_one_freshness_clock(tmp_path):
    store = _store(tmp_path)
    first = store.save(_dated_report(), authorize=lambda: None)
    recent = dict(_dated_report(), generated_at="2026-09-02T00:00:00+00:00")
    second = store.save(recent, authorize=lambda: None)
    listed = store.list(
        **_read_kwargs(max_age_seconds=86400, as_of="2026-09-02T12:00:00+00:00")
    )
    by_id = {item["report_id"]: item for item in listed}
    assert set(by_id) == {first["report_id"], second["report_id"]}
    assert {item["freshness"]["as_of"] for item in listed} == {
        "2026-09-02T12:00:00+00:00"
    }
    assert by_id[first["report_id"]]["freshness"]["historical"] is True
    assert by_id[first["report_id"]]["freshness"]["age_seconds"] == 129600
    assert by_id[second["report_id"]]["freshness"]["historical"] is False
    assert by_id[second["report_id"]]["freshness"]["age_seconds"] == 43200
    assert by_id[second["report_id"]]["receipt_id"] == second["receipt_id"]
    plain = store.list(**_read_kwargs())
    assert all("freshness" not in item for item in plain)
    assert sorted(plain, key=lambda item: item["report_id"]) == sorted(
        [first, second], key=lambda item: item["report_id"]
    )


def test_owner_report_store_default_freshness_clock_is_after_generation(tmp_path):
    store = _store(tmp_path)
    receipt = store.save(_report(), authorize=lambda: None)
    view = store.get(receipt["report_id"], **_read_kwargs(max_age_seconds=86400))
    freshness = view["freshness"]
    assert freshness["as_of"] >= receipt["report"]["generated_at"]
    assert type(freshness["age_seconds"]) is int
    assert 0 <= freshness["age_seconds"] <= 86400
    assert freshness["historical"] is False


@pytest.mark.parametrize(
    "policy",
    [
        {"max_age_seconds": 0},
        {"max_age_seconds": True},
        {"max_age_seconds": "60"},
        {"max_age_seconds": 366 * 86400 + 1},
        {"as_of": "2026-09-01T00:00:00+00:00"},
        {"max_age_seconds": 60, "as_of": "2026-09-01T00:00:00"},
        {"max_age_seconds": 60, "as_of": "yesterday"},
    ],
    ids=["zero", "bool", "text", "too-long", "clock-only", "naive", "malformed"],
)
def test_owner_report_store_rejects_freshness_policy_before_authorization(
    tmp_path, policy
):
    store = _store(tmp_path)
    receipt = store.save(_dated_report(), authorize=lambda: None)
    calls = []

    def authorize():
        calls.append("auth")

    for read in (
        lambda: store.get(
            receipt["report_id"], **_read_kwargs(authorize=authorize, **policy)
        ),
        lambda: store.list(**_read_kwargs(authorize=authorize, **policy)),
    ):
        with pytest.raises(CoreError) as error:
            read()
        assert error.value.code == "OWNER_REPORT_STORE_INVALID"
    assert calls == []
