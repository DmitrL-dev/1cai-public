"""The register adapter checks retained evidence before owner-report sees values."""

import hashlib
import importlib
import json
import os
import traceback

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.owner_report import RuntimeMetricReport, build_owner_report
from rentgen_core.runtime_metrics import RuntimeFreshnessPolicy


PROJECT = "12345678-1234-5678-1234-567812345678"
SNAPSHOT = "b" * 64
COMMIT = "a" * 40
AS_OF = "2026-09-08T00:00:00Z"
REGISTER = "InformationRegister.OwnerIndicators"


def digest(rows):
    return hashlib.sha256(
        json.dumps(
            sorted(rows, key=lambda row: row["row_id"]),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def payload():
    row = {
        "row_id": "orders",
        "metric_id": "orders_count",
        "value": 42,
        "unit": "count",
        "period_start": "2026-09-01T00:00:00Z",
        "period_end": "2026-09-07T23:59:59Z",
        "observed_at": AS_OF,
    }
    return {
        "schema": 1,
        "adapter_id": "onec-register-export-v1",
        "source_ref": "exports/owner-indicators.json",
        "register_id": REGISTER,
        "project_id": PROJECT,
        "snapshot_id": SNAPSHOT,
        "commit": COMMIT,
        "source_digest": digest([row]),
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "generated_at": AS_OF,
        "complete": True,
        "rows": [row],
        "metrics": [
            {**{k: v for k, v in row.items() if k != "row_id"}, "source_id": REGISTER}
        ],
    }


def load(tmp_path, data=None, *, raw=None, **kwargs):
    module = importlib.import_module("rentgen_core.runtime_source")
    data = payload() if data is None else data
    path = tmp_path / "export.json"
    path.write_bytes(json.dumps(data).encode() if raw is None else raw)
    options = {
        "expected_project_id": PROJECT,
        "expected_snapshot_id": SNAPSHOT,
        "expected_commit": COMMIT,
        "expected_source_digest": digest(payload()["rows"]),
        "expected_register_id": REGISTER,
        "expected_source_ref": "exports/owner-indicators.json",
        "authorize": lambda: None,
        "as_of": AS_OF,
    }
    options.update(kwargs)
    return module.load_onec_register_export(path, **options)


def test_valid_register_export_is_typed_and_authorized_three_times(tmp_path):
    calls = []
    report = load(tmp_path, authorize=lambda: calls.append(None))
    assert isinstance(report, RuntimeMetricReport)
    assert report.metrics[0].value == 42
    assert report.metrics[0].source_id == REGISTER
    assert len(calls) == 3
    owner = build_owner_report(
        PROJECT, SNAPSHOT, runtime=report, authorize=lambda: None
    )
    assert owner["business_metrics"]["status"] == "available"


@pytest.mark.parametrize(
    "field", ["period_start", "period_end", "observed_at", "generated_at"]
)
def test_invalid_timestamp_traceback_does_not_disclose_export_payload(tmp_path, field):
    data = payload()
    private = "private-runtime-payload"
    if field == "generated_at":
        data[field] = private
    else:
        data["rows"][0][field] = private
        data["metrics"][0][field] = private
    with pytest.raises(CoreError) as exc:
        load(tmp_path, data)
    assert exc.value.code == "OWNER_RUNTIME_SOURCE_INVALID"
    assert private not in "".join(traceback.format_exception(exc.value))
    assert private not in json.dumps(exc.value.to_dict("test"))


@pytest.mark.parametrize(
    "boundary,error_type",
    [
        ("read_retained", OSError),
        ("_report", ValueError),
        ("_report", TypeError),
        ("_report", OverflowError),
        ("_context", OverflowError),
    ],
)
def test_boundary_exception_traceback_does_not_disclose_payload(
    tmp_path, monkeypatch, boundary, error_type
):
    module = importlib.import_module("rentgen_core.runtime_source")
    private = "private-runtime-payload"

    def fail(*args):
        raise error_type(private)

    monkeypatch.setattr(module, boundary, fail)
    with pytest.raises(CoreError) as exc:
        load(tmp_path)
    assert exc.value.code == "OWNER_RUNTIME_SOURCE_INVALID"
    assert private not in "".join(traceback.format_exception(exc.value))
    assert private not in json.dumps(exc.value.to_dict("test"))


def test_parse_exception_traceback_does_not_disclose_payload(tmp_path, monkeypatch):
    module = importlib.import_module("rentgen_core.runtime_source")
    private = "private-runtime-payload"

    def fail(*args, **kwargs):
        raise json.JSONDecodeError(private, private, 0)

    monkeypatch.setattr(module.json, "loads", fail)
    with pytest.raises(CoreError) as exc:
        load(tmp_path)
    assert exc.value.code == "OWNER_RUNTIME_SOURCE_INVALID"
    assert private not in "".join(traceback.format_exception(exc.value))


@pytest.mark.parametrize(
    "code",
    [
        "OWNER_RUNTIME_SOURCE_INVALID",
        "OWNER_RUNTIME_SOURCE_DIGEST",
        "OWNER_REPORT_INVALID",
    ],
)
def test_validation_core_error_cause_is_suppressed(tmp_path, monkeypatch, code):
    module = importlib.import_module("rentgen_core.runtime_source")
    private = "private-runtime-payload"

    def fail(*args):
        raise CoreError(code, "Invalid export fields") from ValueError(private)

    monkeypatch.setattr(module, "_report", fail)
    with pytest.raises(CoreError) as exc:
        load(tmp_path)
    expected_code = (
        code
        if code.startswith("OWNER_RUNTIME_SOURCE_")
        else "OWNER_RUNTIME_SOURCE_INVALID"
    )
    assert exc.value.code == expected_code
    assert private not in "".join(traceback.format_exception(exc.value))
    assert private not in json.dumps(exc.value.to_dict("test"))


@pytest.mark.parametrize("at_call", [1, 2, 3])
def test_authorization_exception_and_cause_are_preserved(tmp_path, at_call):
    cause = ValueError("authorization-specific-cause")
    denied = CoreError("ACCESS_DENIED", "Revoked")
    calls = []

    def authorize():
        calls.append(None)
        if len(calls) == at_call:
            raise denied from cause

    with pytest.raises(CoreError) as exc:
        load(tmp_path, authorize=authorize)
    assert exc.value is denied
    assert exc.value.__cause__ is cause
    assert "authorization-specific-cause" in "".join(
        traceback.format_exception(exc.value)
    )


def test_trusted_context_overflow_is_typed_and_sanitized(tmp_path):
    with pytest.raises(CoreError) as exc:
        load(tmp_path, expected_project_id=float("inf"))
    assert exc.value.code == "OWNER_RUNTIME_SOURCE_INVALID"


def test_freshness_clock_traceback_does_not_disclose_invalid_input(tmp_path):
    private = "private-runtime-payload"
    with pytest.raises(CoreError) as exc:
        load(tmp_path, as_of=private)
    assert exc.value.code == "OWNER_RUNTIME_INVALID"
    assert private not in "".join(traceback.format_exception(exc.value))


def test_digest_is_recomputed_even_when_declared_and_expected_agree(tmp_path):
    data = payload()
    data["rows"][0]["value"] = 99
    data["metrics"][0]["value"] = 99
    with pytest.raises(CoreError) as exc:
        load(tmp_path, data)
    assert exc.value.code == "OWNER_RUNTIME_SOURCE_DIGEST"


def test_canonical_rows_ignore_export_order_and_preserve_numeric_types(tmp_path):
    data = payload()
    second = {
        **data["rows"][0],
        "row_id": "amount",
        "metric_id": "amount",
        "value": 12.5,
        "unit": "руб",
    }
    data["rows"].append(second)
    data["metrics"].append(
        {**{k: v for k, v in second.items() if k != "row_id"}, "source_id": REGISTER}
    )
    data["source_digest"] = digest(data["rows"])
    data["rows"].reverse()
    data["metrics"].reverse()
    report = load(tmp_path, data, expected_source_digest=data["source_digest"])
    assert report.metrics[0].value == 12.5
    assert report.metrics[0].unit == "руб"
    assert type(report.metrics[1].value) is int


@pytest.mark.parametrize("field", list(payload()))
def test_missing_required_field_is_rejected(tmp_path, field):
    data = payload()
    del data[field]
    with pytest.raises(CoreError):
        load(tmp_path, data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", True),
        ("schema", 2),
        ("adapter_id", "other"),
        ("complete", 1),
        ("register_id", "https://example.org/register"),
        ("source_ref", "https://example.org/export.json"),
    ],
)
def test_export_identity_and_schema_are_strict(tmp_path, field, value):
    data = payload()
    data[field] = value
    with pytest.raises(CoreError):
        load(tmp_path, data)


def test_freshness_clock_is_sampled_after_third_authorization(tmp_path, monkeypatch):
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
        if len(calls) == 3:
            clock[0] = "2026-09-10T00:00:00Z"

    with pytest.raises(CoreError) as exc:
        load(tmp_path, authorize=authorize, as_of=None)
    assert exc.value.code == "OWNER_RUNTIME_STALE"
    assert len(calls) == 3


@pytest.mark.parametrize(
    "field",
    [
        "project_id",
        "snapshot_id",
        "commit",
        "source_digest",
        "register_id",
        "source_ref",
    ],
)
def test_foreign_context_is_rejected(tmp_path, field):
    data = payload()
    replacements = {
        "project_id": "87654321-4321-8765-4321-876543218765",
        "snapshot_id": "d" * 64,
        "commit": "d" * 40,
        "source_digest": "d" * 64,
        "register_id": "InformationRegister.Other",
        "source_ref": "exports/other.json",
    }
    data[field] = replacements[field]
    with pytest.raises(CoreError):
        load(tmp_path, data)


@pytest.mark.parametrize("target", ["root", "rows", "metrics"])
def test_unknown_fields_are_rejected(tmp_path, target):
    data = payload()
    (data if target == "root" else data[target][0])["unknown"] = "x"
    with pytest.raises(CoreError):
        load(tmp_path, data)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema":1,"schema":1}',
        b'{"rows":[{"value":1,"value":2}]}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":1e999}',
        b"[" * 1500 + b"]" * 1500,
        b"\xff",
        b" " * (2 * 1024**2 + 1),
    ],
    ids=[
        "duplicate-root",
        "duplicate-row",
        "nan",
        "infinity",
        "overflow",
        "nesting",
        "encoding",
        "oversized",
    ],
)
def test_malformed_duplicate_nonfinite_and_oversized_json(tmp_path, raw):
    with pytest.raises(CoreError):
        load(tmp_path, raw=raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("metric_id", "bad/id"),
        ("metric_id", "x" * 129),
        ("value", True),
        ("value", 10**15 + 1),
        ("value", float("nan")),
        ("unit", "a\x7fb"),
        ("unit", "a\u0085b"),
        ("unit", "a\u202eb"),
        ("unit", "a\nb"),
        ("unit", "\ud800"),
        ("observed_at", "2026-09-07T00:00:00Z"),
        ("period_end", "2026-08-01T00:00:00Z"),
        ("observed_at", "2026-09-08"),
    ],
)
def test_invalid_row_fields_fail_closed(tmp_path, field, value):
    data = payload()
    data["rows"][0][field] = value
    data["metrics"][0][field] = value
    with pytest.raises(CoreError):
        load(tmp_path, data)


@pytest.mark.parametrize("target", ["rows", "metrics"])
def test_duplicate_or_excessive_rows_and_metrics(tmp_path, target):
    for count in (2, 1001):
        data = payload()
        data[target] *= count
        with pytest.raises(CoreError):
            load(tmp_path, data)


def test_metrics_must_exactly_match_source_rows(tmp_path):
    data = payload()
    data["metrics"][0]["value"] = 100
    with pytest.raises(CoreError) as exc:
        load(tmp_path, data)
    assert exc.value.code == "OWNER_RUNTIME_SOURCE_INVALID"


@pytest.mark.parametrize("kind", ["declared", "empty", "partial"])
def test_incomplete_does_not_become_available(tmp_path, kind):
    data = payload()
    if kind == "declared":
        data["complete"] = False
    elif kind == "empty":
        data["rows"] = []
        data["metrics"] = []
    else:
        data["rows"][0]["period_start"] = "2026-09-02T00:00:00Z"
        data["metrics"][0]["period_start"] = "2026-09-02T00:00:00Z"
    data["source_digest"] = digest(data["rows"])
    report = load(tmp_path, data, expected_source_digest=data["source_digest"])
    assert report.complete is False
    owner = build_owner_report(
        PROJECT, SNAPSHOT, runtime=report, authorize=lambda: None
    )
    assert owner["business_metrics"]["status"] == "incomplete"
    assert owner["business_metrics"]["metrics"] == []


def test_stale_and_period_policy_are_delegated(tmp_path):
    with pytest.raises(CoreError) as exc:
        load(tmp_path, as_of="2026-09-09T00:00:01Z")
    assert exc.value.code == "OWNER_RUNTIME_STALE"
    with pytest.raises(CoreError) as exc:
        load(tmp_path, freshness_policy=RuntimeFreshnessPolicy(max_period_seconds=60))
    assert exc.value.code == "OWNER_RUNTIME_PERIOD"


@pytest.mark.parametrize("at_call", [1, 2, 3])
def test_authorization_revocation_fails_closed(tmp_path, monkeypatch, at_call):
    module = importlib.import_module("rentgen_core.runtime_source")
    calls = []

    def authorize():
        calls.append(None)
        if len(calls) == at_call:
            raise CoreError("ACCESS_DENIED", "Revoked")

    if at_call == 1:
        monkeypatch.setattr(
            module, "read_retained", lambda *args: pytest.fail("Unauthorized read")
        )
    with pytest.raises(CoreError) as exc:
        load(tmp_path, authorize=authorize)
    assert exc.value.code == "ACCESS_DENIED"
    assert len(calls) == at_call


@pytest.mark.parametrize(
    "locator",
    [
        "export.json",
        "../export.json",
        "https://example.org/export.json",
        "\\\\server\\share\\export.json",
    ],
)
def test_relative_or_network_locator_is_rejected(tmp_path, locator):
    module = importlib.import_module("rentgen_core.runtime_source")
    with pytest.raises(CoreError):
        module.load_onec_register_export(
            locator,
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            expected_commit=COMMIT,
            expected_source_digest=digest(payload()["rows"]),
            expected_register_id=REGISTER,
            expected_source_ref="exports/owner-indicators.json",
            authorize=lambda: None,
            as_of=AS_OF,
        )


@pytest.mark.parametrize("kind", ["hardlink", "symlink", "ancestor", "junction"])
def test_links_are_rejected_without_resolving_them(tmp_path, kind):
    target = tmp_path / "target.json"
    target.write_text(json.dumps(payload()), encoding="utf-8")
    link_dir = tmp_path / "through"
    if kind in {"ancestor", "junction"}:
        actual = tmp_path / "actual"
        actual.mkdir()
        (actual / "export.json").write_bytes(target.read_bytes())
        if kind == "junction":
            import _winapi

            _winapi.CreateJunction(str(actual), str(link_dir))
        else:
            try:
                link_dir.symlink_to(actual, target_is_directory=True)
            except OSError as exc:
                pytest.skip(f"Symlink creation unavailable: {exc}")
    else:
        link_dir.mkdir()
        link = link_dir / "export.json"
        if kind == "hardlink":
            os.link(target, link)
        else:
            try:
                link.symlink_to(target)
            except OSError as exc:
                pytest.skip(f"Symlink creation unavailable: {exc}")
    module = importlib.import_module("rentgen_core.runtime_source")
    with pytest.raises(CoreError):
        module.load_onec_register_export(
            link_dir / "export.json",
            expected_project_id=PROJECT,
            expected_snapshot_id=SNAPSHOT,
            expected_commit=COMMIT,
            expected_source_digest=digest(payload()["rows"]),
            expected_register_id=REGISTER,
            expected_source_ref="exports/owner-indicators.json",
            authorize=lambda: None,
            as_of=AS_OF,
        )
