"""Durable owner-report receipts preserve bounded evidence and context."""

import json

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
    assert calls == ["auth"] * 6


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
