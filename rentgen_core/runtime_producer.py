"""Produce immutable owner evidence from one explicitly allowed retained register.

Only trusted host code constructs the source contract and the receipt store.
Requests select its symbolic source ID; they never supply paths, commands,
credentials, context pins or freshness policy. No live runtime is executed.
"""

from dataclasses import dataclass
from pathlib import Path
import re

from .errors import CoreError
from .owner_report import build_owner_report
from .owner_report_store import OwnerReportStore
from .runtime_metrics import RuntimeFreshnessPolicy, assess_runtime_report
from .runtime_source import load_onec_register_export


_ID = re.compile(r"[a-zA-Z_][a-zA-Z0-9_.-]{0,127}\Z")


def _invalid():
    raise CoreError(
        "OWNER_RUNTIME_PRODUCER_INVALID", "Invalid trusted runtime producer contract"
    ) from None


@dataclass(frozen=True)
class RetainedRegisterSource:
    """An independent host allowlist entry, never populated from export JSON.

    The expected digest authenticates canonical source rows only against this
    trusted pin. The exact indicator inventory is independent of the export's
    completeness claim. This contract does not attest to a query against 1C.
    """

    source_id: str
    export_path: Path
    project_id: str
    snapshot_id: str
    commit: str
    source_digest: str
    register_id: str
    source_ref: str
    period_start: str
    period_end: str
    metric_ids: tuple[str, ...]
    max_age_seconds: int = 86400
    max_period_seconds: int = 366 * 86400

    def __post_init__(self):
        if (
            type(self.source_id) is not str
            or not _ID.fullmatch(self.source_id)
            or type(self.metric_ids) is not tuple
            or not 1 <= len(self.metric_ids) <= 1000
            or any(
                type(item) is not str or not _ID.fullmatch(item)
                for item in self.metric_ids
            )
            or len(set(self.metric_ids)) != len(self.metric_ids)
        ):
            _invalid()
        for name in (
            "project_id",
            "snapshot_id",
            "commit",
            "source_digest",
            "register_id",
            "source_ref",
            "period_start",
            "period_end",
        ):
            if type(getattr(self, name)) is not str:
                _invalid()
        try:
            if not isinstance(self.export_path, (str, Path)):
                _invalid()
            object.__setattr__(self, "export_path", Path(self.export_path))
            self.freshness_policy()
        except (CoreError, TypeError, ValueError, OverflowError):
            _invalid()

    def freshness_policy(self):
        """Use the pinned period; callers cannot relax it per production request."""
        return RuntimeFreshnessPolicy(
            max_age_seconds=self.max_age_seconds,
            max_period_seconds=self.max_period_seconds,
            expected_period_start=self.period_start,
            expected_period_end=self.period_end,
        )


@dataclass(frozen=True)
class RetainedRegisterProducer:
    """One allowed source and an already initialized, host-owned receipt store."""

    source: RetainedRegisterSource
    receipt_store: OwnerReportStore

    def __post_init__(self):
        if not isinstance(self.source, RetainedRegisterSource) or not isinstance(
            self.receipt_store, OwnerReportStore
        ):
            _invalid()

    def produce(self, source_id, *, authorize, as_of=None):
        """Validate read-only source evidence and persist an immutable owner receipt.

        Authorization follows the public callback contract: raise to deny.
        ``as_of`` is a trusted host clock override for reproducible fixtures,
        not request/export data. Store receipt reads remain historical evidence.
        """
        if type(source_id) is not str or source_id != self.source.source_id:
            raise CoreError(
                "OWNER_RUNTIME_PRODUCER_SOURCE", "Runtime source is not allowed"
            )
        if not callable(authorize):
            raise CoreError(
                "OWNER_RUNTIME_AUTHORIZATION", "Runtime authorization is required"
            )
        source = self.source
        policy = source.freshness_policy()
        runtime = load_onec_register_export(
            source.export_path,
            expected_project_id=source.project_id,
            expected_snapshot_id=source.snapshot_id,
            expected_commit=source.commit,
            expected_source_digest=source.source_digest,
            expected_register_id=source.register_id,
            expected_source_ref=source.source_ref,
            authorize=authorize,
            freshness_policy=policy,
            as_of=as_of,
        )
        if not runtime.complete or {
            metric.metric_id for metric in runtime.metrics
        } != set(source.metric_ids):
            raise CoreError(
                "OWNER_RUNTIME_PRODUCER_INCOMPLETE",
                "Expected register indicators are incomplete",
            )

        def authorize_current():
            # Delayed owner/store authorization must not extend source freshness.
            # Preserve the trusted callback's exception and cause unchanged.
            authorize()
            try:
                assessment = assess_runtime_report(
                    runtime, freshness_policy=policy, as_of=as_of
                )
            except CoreError as exc:
                raise CoreError(exc.code, exc.message) from None
            if assessment.status != "available":
                code = (
                    "OWNER_RUNTIME_STALE"
                    if assessment.status == "stale"
                    else "OWNER_RUNTIME_PRODUCER_INCOMPLETE"
                )
                raise CoreError(code, "Register evidence is no longer available")

        report = build_owner_report(
            source.project_id,
            source.snapshot_id,
            runtime=runtime,
            authorize=authorize_current,
        )
        return self.receipt_store.save(report, authorize=authorize_current)
