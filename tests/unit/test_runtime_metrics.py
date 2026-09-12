"""Runtime metric exports are bounded, authorized and context-bound."""

import json

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.owner_report import build_owner_report
from rentgen_core.runtime_metrics import load_runtime_report


PROJECT = "12345678-1234-5678-1234-567812345678"
SNAPSHOT = "b" * 64
COMMIT = "a" * 40
SOURCE_DIGEST = "c" * 64


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
            authorize=lambda: None,
        )


def test_load_runtime_report_keeps_incomplete_status_without_inventing_values(tmp_path):
    report = load_runtime_report(
        write_payload(tmp_path, payload(complete=False)),
        expected_project_id=PROJECT,
        expected_snapshot_id=SNAPSHOT,
        expected_commit=COMMIT,
        expected_source_digest=SOURCE_DIGEST,
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
        authorize=lambda: None,
    )

    owner = build_owner_report(
        PROJECT, SNAPSHOT, runtime=report, authorize=lambda: None
    )
    assert owner["business_metrics"]["status"] == "available"
