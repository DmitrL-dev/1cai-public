"""Strict offline adapter for retained 1C/ERP register indicator exports."""

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

from ._windows_source_tree import read_retained
from .context import validate_project_id
from .errors import CoreError
from .owner_report import RuntimeMetric, RuntimeMetricReport
from .runtime_metrics import RuntimeFreshnessPolicy, assess_runtime_report
from .source_paths import validate_source_path


ADAPTER_ID = "onec-register-export-v1"
MAX_BYTES = 2 * 1024**2
MAX_ROWS = 1000
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_ID = re.compile(r"[a-zA-Z_][a-zA-Z0-9_.-]{0,127}\Z")
_REGISTER = re.compile(
    r"(?:InformationRegister|AccumulationRegister|AccountingRegister|CalculationRegister)"
    r"\.[^\W\d]\w*\Z"
)
_FIELDS = {
    "schema",
    "adapter_id",
    "source_ref",
    "register_id",
    "project_id",
    "snapshot_id",
    "commit",
    "source_digest",
    "period_start",
    "period_end",
    "generated_at",
    "complete",
    "rows",
    "metrics",
}
_ROW_FIELDS = {
    "row_id",
    "metric_id",
    "value",
    "unit",
    "period_start",
    "period_end",
    "observed_at",
}
_METRIC_FIELDS = (_ROW_FIELDS - {"row_id"}) | {"source_id"}


def _require(condition, message):
    if not condition:
        raise CoreError("OWNER_RUNTIME_SOURCE_INVALID", message)


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate export field")
        result[key] = value
    return result


def _constant(value):
    _require(False, "Nonfinite JSON number")


def _bounded_json(value, depth=0):
    _require(depth <= 8, "Export nesting exceeds bound")
    if isinstance(value, str):
        _require(
            len(value) <= 1024
            and not any(unicodedata.category(char).startswith("C") for char in value),
            "Invalid export text",
        )
    elif type(value) is dict:
        _require(len(value) <= 32, "Export object exceeds bound")
        for key, item in value.items():
            _bounded_json(key, depth + 1)
            _bounded_json(item, depth + 1)
    elif type(value) is list:
        _require(len(value) <= MAX_ROWS, "Export rows exceed bound")
        for item in value:
            _bounded_json(item, depth + 1)
    elif type(value) in (int, float):
        _require(
            abs(value) <= 10**15 and (type(value) is int or math.isfinite(value)),
            "Export number exceeds bound",
        )


def _context(project, snapshot, commit, digest, register, source):
    validate_project_id(project)
    for value, pattern in ((snapshot, _HASH), (commit, _COMMIT), (digest, _HASH)):
        _require(
            type(value) is str and pattern.fullmatch(value), "Invalid export context"
        )
    _require(
        type(register) is str
        and len(register) <= 128
        and _REGISTER.fullmatch(register),
        "Invalid register identifier",
    )
    _require(type(source) is str and len(source) <= 1024, "Invalid source reference")
    _bounded_json(register)
    _bounded_json(source)
    validate_source_path(source)


def _report(value):
    _require(type(value) is dict and set(value) == _FIELDS, "Invalid export schema")
    _require(
        type(value["schema"]) is int and value["schema"] == 1, "Invalid schema version"
    )
    _require(value["adapter_id"] == ADAPTER_ID, "Invalid adapter identifier")
    _require(type(value["complete"]) is bool, "Invalid completeness flag")
    _context(
        *(
            value[key]
            for key in (
                "project_id",
                "snapshot_id",
                "commit",
                "source_digest",
                "register_id",
                "source_ref",
            )
        )
    )
    rows, items = value["rows"], value["metrics"]
    _require(
        type(rows) is list and type(items) is list, "Rows and metrics are required"
    )
    _require(
        len(rows) == len(items) <= MAX_ROWS, "Rows and metrics must match within bounds"
    )
    row_ids, source_metrics = set(), {}
    for row in rows:
        _require(
            type(row) is dict and set(row) == _ROW_FIELDS, "Invalid register row schema"
        )
        for key in ("row_id", "metric_id"):
            _require(
                type(row[key]) is str and _ID.fullmatch(row[key]),
                "Invalid row or metric identifier",
            )
        _require(row["row_id"] not in row_ids, "Duplicate row identifier")
        _require(row["metric_id"] not in source_metrics, "Duplicate source metric")
        row_ids.add(row["row_id"])
        metric = {key: item for key, item in row.items() if key != "row_id"}
        metric["source_id"] = value["register_id"]
        RuntimeMetric(**metric)
        source_metrics[row["metric_id"]] = _canonical(metric)
    actual_digest = hashlib.sha256(
        _canonical(sorted(rows, key=lambda row: row["row_id"]))
    ).hexdigest()
    if actual_digest != value["source_digest"]:
        raise CoreError(
            "OWNER_RUNTIME_SOURCE_DIGEST", "Register rows do not match source digest"
        )
    metrics, seen = [], set()
    for item in items:
        _require(
            type(item) is dict and set(item) == _METRIC_FIELDS, "Invalid metric schema"
        )
        identity = item["metric_id"]
        _require(
            type(identity) is str and _ID.fullmatch(identity),
            "Invalid metric identifier",
        )
        _require(
            identity not in seen and source_metrics.get(identity) == _canonical(item),
            "Metric does not match register row",
        )
        seen.add(identity)
        metrics.append(RuntimeMetric(**item))
    return RuntimeMetricReport(
        **{
            key: item
            for key, item in value.items()
            if key not in {"schema", "register_id", "rows", "metrics"}
        },
        metrics=tuple(metrics),
    )


def load_onec_register_export(
    path,
    *,
    expected_project_id,
    expected_snapshot_id,
    expected_commit,
    expected_source_digest,
    expected_register_id,
    expected_source_ref,
    authorize,
    freshness_policy=RuntimeFreshnessPolicy(),
    as_of=None,
) -> RuntimeMetricReport:
    """Verify a local register export; raise CoreError on invalid or stale evidence.

    The caller supplies trusted context and authorization (raise to deny). No
    source locator from JSON is opened. Freshness is assessed after final auth.
    """
    if not callable(authorize):
        raise CoreError(
            "OWNER_RUNTIME_AUTHORIZATION", "Runtime authorization is required"
        )
    try:
        _context(
            expected_project_id,
            expected_snapshot_id,
            expected_commit,
            expected_source_digest,
            expected_register_id,
            expected_source_ref,
        )
        path = Path(path)
        _require(
            path.is_absolute()
            and ".." not in path.parts
            and not path.drive.startswith("\\\\"),
            "Absolute local retained path is required",
        )
        _bounded_json(str(path))
        for part in path.parts[1:]:
            validate_source_path(part)
    except (CoreError, OSError, TypeError, ValueError, OverflowError):
        raise CoreError(
            "OWNER_RUNTIME_SOURCE_INVALID", "Invalid trusted export locator or context"
        ) from None
    authorize()
    try:
        # Do not resolve: following a link would defeat the retained no-follow pins.
        raw = read_retained(path, MAX_BYTES)
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_constant
        )
    except (
        CoreError,
        OSError,
        ValueError,
        TypeError,
        UnicodeError,
        RecursionError,
        OverflowError,
    ):
        raise CoreError(
            "OWNER_RUNTIME_SOURCE_INVALID", "Register export is unreadable"
        ) from None
    authorize()
    try:
        _bounded_json(value)
        report = _report(value)
    except CoreError as exc:
        if exc.code.startswith("OWNER_RUNTIME_SOURCE_"):
            raise exc from None
        raise CoreError(
            "OWNER_RUNTIME_SOURCE_INVALID", "Invalid register export fields"
        ) from None
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise CoreError(
            "OWNER_RUNTIME_SOURCE_INVALID", "Invalid register export fields"
        ) from None
    if (
        report.project_id != expected_project_id
        or report.snapshot_id != expected_snapshot_id
        or report.commit != expected_commit
        or report.source_digest != expected_source_digest
        or value["register_id"] != expected_register_id
        or report.source_ref != expected_source_ref
    ):
        raise CoreError(
            "OWNER_RUNTIME_CONTEXT", "Register export does not match expected context"
        )
    authorize()
    try:
        assessment = assess_runtime_report(
            report, freshness_policy=freshness_policy, as_of=as_of
        )
    except CoreError as exc:
        raise CoreError(exc.code, exc.message) from None
    if assessment.status == "stale":
        raise CoreError("OWNER_RUNTIME_STALE", "Register export evidence is stale")
    return (
        replace(report, complete=False) if assessment.status == "incomplete" else report
    )
