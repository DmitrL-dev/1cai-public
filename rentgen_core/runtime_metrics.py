"""Bounded, authorized JSON exports for owner-report runtime metrics."""

from pathlib import Path
import re

from ._windows_source_tree import read_retained
from .edt_profiles import parse_json
from .errors import CoreError
from .owner_report import RuntimeMetric, RuntimeMetricReport


MAX_BYTES = 2 * 1024**2
_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = {
    "schema",
    "adapter_id",
    "source_ref",
    "project_id",
    "snapshot_id",
    "commit",
    "source_digest",
    "period_start",
    "period_end",
    "generated_at",
    "complete",
    "metrics",
}
_METRIC_FIELDS = {
    "metric_id",
    "value",
    "unit",
    "period_start",
    "period_end",
    "source_id",
    "observed_at",
}


def _invalid(message, *, cause=None):
    error = CoreError("OWNER_RUNTIME_INVALID", message)
    if cause is not None:
        raise error from cause
    raise error


def load_runtime_report(
    path,
    *,
    expected_project_id,
    expected_snapshot_id,
    expected_commit,
    expected_source_digest,
    authorize,
):
    """Load a context-bound runtime export without starting a runtime or network."""
    if not callable(authorize):
        raise CoreError(
            "OWNER_RUNTIME_AUTHORIZATION", "Runtime report authorization is required"
        )
    if not isinstance(path, Path):
        path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        _invalid("Absolute runtime export path is required")
    if (
        not isinstance(expected_project_id, str)
        or not isinstance(expected_snapshot_id, str)
        or not isinstance(expected_commit, str)
        or not isinstance(expected_source_digest, str)
        or _COMMIT.fullmatch(expected_commit) is None
        or _HASH.fullmatch(expected_snapshot_id) is None
        or _HASH.fullmatch(expected_source_digest) is None
    ):
        _invalid("Expected runtime context is invalid")
    authorize()
    try:
        value = parse_json(read_retained(path.resolve(), MAX_BYTES))
    except CoreError as exc:
        raise CoreError(
            "OWNER_RUNTIME_INVALID", "Runtime export is unreadable"
        ) from exc
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise CoreError(
            "OWNER_RUNTIME_INVALID", "Runtime export is unreadable"
        ) from exc
    if (
        type(value) is not dict
        or set(value) != _FIELDS
        or type(value["schema"]) is not int
        or value["schema"] != 1
        or type(value["complete"]) is not bool
        or not isinstance(value["metrics"], list)
    ):
        _invalid("Runtime export schema is invalid")
    metrics = []
    for item in value["metrics"]:
        if type(item) is not dict or set(item) != _METRIC_FIELDS:
            _invalid("Runtime metric schema is invalid")
        try:
            metrics.append(RuntimeMetric(**item))
        except (CoreError, TypeError, ValueError) as exc:
            raise CoreError(
                "OWNER_RUNTIME_INVALID", "Runtime metric is invalid"
            ) from exc
    try:
        report = RuntimeMetricReport(
            project_id=value["project_id"],
            snapshot_id=value["snapshot_id"],
            commit=value["commit"],
            adapter_id=value["adapter_id"],
            source_ref=value["source_ref"],
            source_digest=value["source_digest"],
            period_start=value["period_start"],
            period_end=value["period_end"],
            generated_at=value["generated_at"],
            complete=value["complete"],
            metrics=tuple(metrics),
        )
    except (CoreError, TypeError, ValueError) as exc:
        raise CoreError(
            "OWNER_RUNTIME_INVALID", "Runtime export fields are invalid"
        ) from exc
    if (
        report.project_id != expected_project_id
        or report.snapshot_id != expected_snapshot_id
        or report.commit != expected_commit
        or report.source_digest != expected_source_digest
    ):
        raise CoreError(
            "OWNER_RUNTIME_CONTEXT", "Runtime export does not match expected context"
        )
    authorize()
    return report
