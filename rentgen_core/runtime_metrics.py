"""Bounded, authorized JSON exports for owner-report runtime metrics."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
import re

from ._windows_source_tree import read_retained
from .edt_profiles import parse_json
from .errors import CoreError
from .owner_report import (
    RuntimeMetric,
    RuntimeMetricReport,
    _MAX_METRICS,
    _timestamp,
)


MAX_BYTES = 2 * 1024**2
_MAX_POLICY_SECONDS = 366 * 86400
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


@dataclass(frozen=True)
class RuntimeFreshnessPolicy:
    """Bounded consumer policy; never accepted from the export itself."""

    max_age_seconds: int = 86400
    max_period_seconds: int = _MAX_POLICY_SECONDS
    expected_period_start: str | None = None
    expected_period_end: str | None = None

    def __post_init__(self):
        for value in (self.max_age_seconds, self.max_period_seconds):
            if type(value) is not int or not 1 <= value <= _MAX_POLICY_SECONDS:
                _invalid("Invalid runtime policy bound")
        if (self.expected_period_start is None) != (self.expected_period_end is None):
            _invalid("Expected period requires both ends")
        if self.expected_period_start is not None:
            start = _time(self.expected_period_start, "expected_period_start")
            end = _time(self.expected_period_end, "expected_period_end")
            if not 0 <= (end - start).total_seconds() <= self.max_period_seconds:
                _invalid("Invalid expected period")


@dataclass(frozen=True)
class RuntimeMetricAssessment:
    """An explicit availability decision containing no business values."""

    status: str
    reason: str | None


def _time(value, name):
    try:
        return _timestamp(value, name)
    except CoreError as exc:
        _invalid(f"Invalid runtime {name}", cause=exc)


def assess_runtime_report(
    report, *, freshness_policy=RuntimeFreshnessPolicy(), as_of=None
):
    """Evaluate evidence at the trusted consumer clock, without exposing values."""
    if not isinstance(report, RuntimeMetricReport):
        _invalid("Typed runtime report required")
    if not isinstance(freshness_policy, RuntimeFreshnessPolicy):
        _invalid("Typed runtime policy required")
    now = datetime.now(timezone.utc) if as_of is None else _time(as_of, "as_of")
    start = _time(report.period_start, "period_start")
    end = _time(report.period_end, "period_end")
    generated = _time(report.generated_at, "generated_at")
    if generated < end or generated > now:
        _invalid("Runtime generation must follow period end and not be in the future")
    if (end - start).total_seconds() > freshness_policy.max_period_seconds:
        raise CoreError("OWNER_RUNTIME_PERIOD", "Runtime period exceeds policy bound")
    if freshness_policy.expected_period_start is not None and (
        start != _time(freshness_policy.expected_period_start, "expected_period_start")
        or end != _time(freshness_policy.expected_period_end, "expected_period_end")
    ):
        raise CoreError("OWNER_RUNTIME_PERIOD", "Runtime period does not match policy")
    incomplete = not report.complete or not report.metrics
    stale = (now - generated).total_seconds() > freshness_policy.max_age_seconds
    for metric in report.metrics:
        metric_start = _time(metric.period_start, "metric.period_start")
        metric_end = _time(metric.period_end, "metric.period_end")
        observed = _time(metric.observed_at, "metric.observed_at")
        if observed < metric_end or observed > generated:
            _invalid(
                "Runtime observation must follow metric period and precede generation"
            )
        incomplete = incomplete or metric_start != start or metric_end != end
        stale = (
            stale or (now - observed).total_seconds() > freshness_policy.max_age_seconds
        )
    if stale:
        return RuntimeMetricAssessment("stale", "runtime_report_stale")
    if incomplete:
        return RuntimeMetricAssessment("incomplete", "runtime_report_incomplete")
    return RuntimeMetricAssessment("available", None)


def load_runtime_report(
    path,
    *,
    expected_project_id,
    expected_snapshot_id,
    expected_commit,
    expected_source_digest,
    authorize,
    freshness_policy=RuntimeFreshnessPolicy(),
    as_of=None,
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
    if len(value["metrics"]) > _MAX_METRICS:
        _invalid("Runtime metric limit exceeded")
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
    assessment = assess_runtime_report(
        report, freshness_policy=freshness_policy, as_of=as_of
    )
    if assessment.status == "stale":
        raise CoreError("OWNER_RUNTIME_STALE", "Runtime export evidence is stale")
    return (
        replace(report, complete=False) if assessment.status == "incomplete" else report
    )
