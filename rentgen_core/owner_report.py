"""Evidence-bound owner reports for quality findings and runtime metrics.

The builder is deliberately a pure report boundary. It never queries a
database, starts a runtime or invents business values. A runtime adapter must
provide a complete, context-bound report and an authorization callback before
its values can be exposed.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
import re

from .context import validate_project_id
from .errors import CoreError
from .git_observer import FindingState


_HASH_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_SNAPSHOT_RE = re.compile(r"[0-9a-f]{64}\Z")
_MAX_METRICS = 1000
_MAX_TEXT = 4096


def _text(value, name, maximum=_MAX_TEXT):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or "\x00" in value
        or any(ord(char) < 32 for char in value)
    ):
        raise CoreError("OWNER_REPORT_INVALID", f"Invalid {name}")
    return value


def _timestamp(value, name):
    _text(value, name, 64)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise CoreError("OWNER_REPORT_INVALID", f"Invalid {name}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CoreError("OWNER_REPORT_INVALID", f"Invalid {name} timezone")
    return parsed


def _hash(value, name, *, snapshot=False):
    pattern = _SNAPSHOT_RE if snapshot else _HASH_RE
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise CoreError("OWNER_REPORT_INVALID", f"Invalid {name}")
    return value


@dataclass(frozen=True)
class RuntimeMetric:
    """One value with a period, source identity and observation timestamp."""

    metric_id: str
    value: int | float
    unit: str
    period_start: str
    period_end: str
    source_id: str
    observed_at: str

    def __post_init__(self):
        _text(self.metric_id, "metric_id", 128)
        _text(self.unit, "unit", 64)
        _text(self.source_id, "source_id", 256)
        if type(self.value) not in (int, float) or (
            isinstance(self.value, float) and not math.isfinite(self.value)
        ):
            raise CoreError("OWNER_METRIC_INVALID", "Metric value must be finite")
        if abs(self.value) > 10**15:
            raise CoreError("OWNER_METRIC_INVALID", "Metric value exceeds bound")
        start, end = (
            _timestamp(self.period_start, "period_start"),
            _timestamp(self.period_end, "period_end"),
        )
        if end < start:
            raise CoreError("OWNER_METRIC_INVALID", "Metric period is inverted")
        _timestamp(self.observed_at, "observed_at")


@dataclass(frozen=True)
class RuntimeMetricReport:
    """Typed adapter evidence; values are hidden when ``complete`` is false."""

    project_id: str
    snapshot_id: str
    commit: str
    adapter_id: str
    source_ref: str
    source_digest: str
    period_start: str
    period_end: str
    generated_at: str
    complete: bool
    metrics: tuple[RuntimeMetric, ...]

    def __post_init__(self):
        validate_project_id(self.project_id)
        _hash(self.snapshot_id, "snapshot_id", snapshot=True)
        _hash(self.commit, "commit")
        _text(self.adapter_id, "adapter_id", 128)
        _text(self.source_ref, "source_ref", 1024)
        _hash(self.source_digest, "source_digest", snapshot=True)
        start, end = (
            _timestamp(self.period_start, "period_start"),
            _timestamp(self.period_end, "period_end"),
        )
        if end < start:
            raise CoreError("OWNER_REPORT_INVALID", "Report period is inverted")
        _timestamp(self.generated_at, "generated_at")
        if type(self.complete) is not bool or type(self.metrics) is not tuple:
            raise CoreError("OWNER_REPORT_INVALID", "Typed runtime report required")
        if len(self.metrics) > _MAX_METRICS or any(
            not isinstance(metric, RuntimeMetric) for metric in self.metrics
        ):
            raise CoreError("OWNER_REPORT_LIMIT", "Runtime metric limit exceeded")
        identities = {(metric.source_id, metric.metric_id) for metric in self.metrics}
        if len(identities) != len(self.metrics):
            raise CoreError("OWNER_METRIC_DUPLICATE", "Duplicate metric identity")
        for metric in self.metrics:
            metric_start = _timestamp(metric.period_start, "metric.period_start")
            metric_end = _timestamp(metric.period_end, "metric.period_end")
            if metric_start < start or metric_end > end:
                raise CoreError(
                    "OWNER_METRIC_INVALID", "Metric period is outside report period"
                )


def _quality(findings, maximum):
    if findings is None:
        return {"status": "not_available", "reason": "quality_analysis_not_configured"}
    if not isinstance(findings, FindingState):
        raise CoreError("OWNER_REPORT_INVALID", "Typed finding state required")
    if len(findings.records) > maximum:
        raise CoreError("OWNER_REPORT_LIMIT", "Finding report limit exceeded")
    records = sorted(findings.records, key=lambda item: item.finding.identity)
    report = findings.report
    observation = report.observation
    _text(observation.repository, "finding.repository")
    _hash(observation.commit, "finding.commit")
    if observation.ref is not None:
        _text(observation.ref, "finding.ref")
    _text(report.profile_id, "finding.profile_id")
    _text(report.scope_id, "finding.scope_id")
    items = []
    for record in records:
        finding = record.finding
        _hash(record.first_seen, "finding.first_seen")
        _hash(record.last_seen, "finding.last_seen")
        if record.resolved_at is not None:
            _hash(record.resolved_at, "finding.resolved_at")
        items.append(
            {
                **asdict(finding),
                "first_seen": record.first_seen,
                "last_seen": record.last_seen,
                "resolved_at": record.resolved_at,
            }
        )
    open_count = sum(record.resolved_at is None for record in records)
    return {
        "status": "available",
        "commit": observation.commit,
        "ref": observation.ref,
        "profile_id": report.profile_id,
        "scope_id": report.scope_id,
        "total": len(items),
        "open": open_count,
        "resolved": len(items) - open_count,
        "findings": items,
    }


def build_owner_report(
    project_id,
    snapshot_id,
    *,
    findings=None,
    runtime=None,
    authorize=None,
    max_findings=1000,
):
    """Build a bounded report while preserving source and context provenance."""
    validate_project_id(project_id)
    _hash(snapshot_id, "snapshot_id", snapshot=True)
    if type(max_findings) is not int or not 1 <= max_findings <= 10_000:
        raise CoreError("OWNER_REPORT_LIMIT", "Finding report limit is out of bounds")
    if findings is not None and not isinstance(findings, FindingState):
        raise CoreError("OWNER_REPORT_INVALID", "Typed finding state required")
    if runtime is not None and not callable(authorize):
        raise CoreError(
            "OWNER_REPORT_AUTHORIZATION", "Runtime report authorization is required"
        )
    if authorize is not None and not callable(authorize):
        raise CoreError("OWNER_REPORT_AUTHORIZATION", "Authorization callback required")
    if runtime is not None:
        if not isinstance(runtime, RuntimeMetricReport):
            raise CoreError("OWNER_REPORT_INVALID", "Typed runtime report required")
        authorize()
        if runtime.project_id != project_id or runtime.snapshot_id != snapshot_id:
            raise CoreError("OWNER_REPORT_CONTEXT", "Runtime context does not match")
        if (
            findings is not None
            and runtime.commit != findings.report.observation.commit
        ):
            raise CoreError(
                "OWNER_REPORT_CONTEXT", "Runtime commit does not match findings"
            )
    quality = _quality(findings, max_findings)
    if runtime is None:
        business = {
            "status": "not_available",
            "reason": "runtime_adapter_not_configured",
        }
    else:
        source = {
            "project_id": runtime.project_id,
            "snapshot_id": runtime.snapshot_id,
            "commit": runtime.commit,
            "adapter_id": runtime.adapter_id,
            "source_ref": runtime.source_ref,
            "source_digest": runtime.source_digest,
            "period_start": runtime.period_start,
            "period_end": runtime.period_end,
            "generated_at": runtime.generated_at,
        }
        business = {
            "status": "available" if runtime.complete else "incomplete",
            "reason": None if runtime.complete else "runtime_report_incomplete",
            "source": source,
            "metrics": [asdict(metric) for metric in runtime.metrics]
            if runtime.complete
            else [],
        }
    return {
        "schema": 1,
        "project_id": project_id,
        "snapshot_id": snapshot_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quality": quality,
        "business_metrics": business,
    }
