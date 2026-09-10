"""Ephemeral single-module diagnostics; typed ports carry no execution authority.

The concrete adapter owns process/runtime confinement. This module owns proposal
and permission validation. DTO construction or imported JSON is never evidence
that an analyzer ran. Only the use case invokes the trusted startup adapter.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import re
from typing import Callable, Literal, Protocol

from .sources import SourceRef
from .errors import CoreError
from .proposals import Proposal, ProposalLimits, parse_proposal, validate_proposal

BSL_PROFILE_ID = "bsl-ls-1.0.5-temurin21.0.12.1-win64-bmp-default-v1"
BSL_CONFIG_SHA256 = "e56b86d4187a301a6e17e7e46906d4e7fcf6e84166d648684b6d5f1bd540af72"
BSL_RUNTIME_MANIFEST_SHA256 = (
    "2835e1a268e67be020e99ecd8d2a64c7b390e3752ed99c89d71a5340eb792ca5"
)
_PERMISSIONS = frozenset({"project:read", "source:edit", "analysis:run"})
_HASH = re.compile(r"[a-f0-9]{64}")
_REASON = re.compile(r"BSL_[A-Z0-9_]{1,76}")
_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,127}")
_UNSUPPORTED = frozenset(
    {
        "BSL_PLATFORM_UNSUPPORTED",
        "BSL_SOURCE_TYPE_UNSUPPORTED",
        "BSL_ENCODING_UNSUPPORTED",
        "BSL_COORDINATES_UNSUPPORTED",
    }
)


@dataclass(frozen=True)
class BslPosition:
    line: int
    character: int


@dataclass(frozen=True)
class BslDiagnostic:
    code: str
    severity: Literal["Error", "Warning", "Information", "Hint"]
    message: str
    start: BslPosition
    end: BslPosition


@dataclass(frozen=True)
class BslAnalysis:
    status: Literal["completed", "unsupported", "failed"]
    reason: str | None
    candidate_sha256: str
    candidate_size_bytes: int
    profile_id: str
    runtime_manifest_sha256: str | None
    runtime_verified: bool
    config_sha256: str | None
    scope: Literal["single_module_isolated"]
    coverage: Literal["exact_one", "not_run", "incomplete"]
    diagnostics: tuple[BslDiagnostic, ...]
    diagnostics_complete: bool
    total_diagnostics: int | None
    report_sha256: str | None
    stdout_sha256: str | None
    stderr_sha256: str | None
    exit_code: int | None


class DiagnosticAdapter(Protocol):
    def analyze(
        self, candidate_bytes: bytes, *, suffix: str, authorize: Callable[[], None]
    ) -> BslAnalysis:
        """Trusted startup port for the fixed profile, never selected from JSON.

        Own bounded work through cleanup; call authorize before materialization,
        runtime IO, spawn/resume and every final success/error release. Runtime
        verification is observed by the adapter, not inferred from copied hashes.
        """
        ...


@dataclass(frozen=True)
class DiagnosticRun:
    source_ref: SourceRef
    proposal_content_id: str
    analysis: BslAnalysis
    diagnostics_status: Literal["clean", "diagnostics_present", "unsupported", "failed"]
    tests_status: Literal["not_run"] = "not_run"
    apply_status: Literal["unavailable"] = "unavailable"
    evidence: Literal["ephemeral_unattested"] = "ephemeral_unattested"


def _authorize(ctx):
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(_PERMISSIONS)


@contextmanager
def _authorized(ctx):
    _authorize(ctx)
    try:
        yield
    finally:
        try:
            _authorize(ctx)
        except BaseException as exc:
            raise exc from None


def _matches(pattern, value):
    return type(value) is str and pattern.fullmatch(value) is not None


def _enum(value, allowed):
    return type(value) is str and value in allowed


def _diagnostic_valid(value, lines):
    if (
        type(value) is not BslDiagnostic
        or not _matches(_CODE, value.code)
        or not _enum(value.severity, {"Error", "Warning", "Information", "Hint"})
        or type(value.message) is not str
    ):
        return False
    try:
        if len(value.message.encode("utf-8", errors="strict")) > 1024:
            return False
    except UnicodeError:
        return False
    for position in (value.start, value.end):
        if (
            type(position) is not BslPosition
            or type(position.line) is not int
            or type(position.character) is not int
            or not 0 <= position.line < len(lines)
            or not 0 <= position.character <= len(lines[position.line])
        ):
            return False
    return (value.start.line, value.start.character) <= (
        value.end.line,
        value.end.character,
    )


def _analysis_valid(analysis, raw):
    if type(analysis) is not BslAnalysis:
        return False
    if (
        not _enum(analysis.status, {"completed", "unsupported", "failed"})
        or type(analysis.candidate_sha256) is not str
        or analysis.candidate_sha256 != hashlib.sha256(raw).hexdigest()
        or type(analysis.candidate_size_bytes) is not int
        or analysis.candidate_size_bytes != len(raw)
        or type(analysis.profile_id) is not str
        or analysis.profile_id != BSL_PROFILE_ID
        or type(analysis.runtime_manifest_sha256) is not str
        or analysis.runtime_manifest_sha256 != BSL_RUNTIME_MANIFEST_SHA256
        or type(analysis.config_sha256) is not str
        or analysis.config_sha256 != BSL_CONFIG_SHA256
        or type(analysis.runtime_verified) is not bool
        or not _enum(analysis.scope, {"single_module_isolated"})
        or type(analysis.diagnostics) is not tuple
        or len(analysis.diagnostics) > 128
        or type(analysis.diagnostics_complete) is not bool
    ):
        return False
    hashes = (analysis.report_sha256, analysis.stdout_sha256, analysis.stderr_sha256)
    if any(value is not None and not _matches(_HASH, value) for value in hashes):
        return False
    if analysis.exit_code is not None and (
        type(analysis.exit_code) is not int or not 0 <= analysis.exit_code < 2**32
    ):
        return False
    if analysis.status != "completed":
        if (
            not _matches(_REASON, analysis.reason)
            or analysis.diagnostics
            or analysis.diagnostics_complete
            or analysis.total_diagnostics is not None
            or not _enum(analysis.coverage, {"not_run", "incomplete"})
        ):
            return False
        if analysis.status == "unsupported" and (
            analysis.coverage != "not_run"
            or analysis.runtime_verified
            or analysis.reason not in _UNSUPPORTED
        ):
            return False
        return analysis.coverage != "not_run" or (
            all(value is None for value in hashes) and analysis.exit_code is None
        )
    if (
        analysis.reason is not None
        or not analysis.runtime_verified
        or not _enum(analysis.coverage, {"exact_one"})
        or analysis.exit_code != 0
        or any(value is None for value in hashes)
        or not analysis.diagnostics_complete
        or type(analysis.total_diagnostics) is not int
        or analysis.total_diagnostics != len(analysis.diagnostics)
    ):
        return False
    # This fixed release has mixed non-BMP coordinate conventions. The adapter
    # must refuse such candidates; do not guess or clamp coordinates in core.
    text = raw.decode("utf-8-sig", errors="strict")
    if any(ord(character) > 0xFFFF for character in text):
        return False
    lines = [line.removesuffix("\r") for line in text.split("\n")]
    return all(_diagnostic_valid(value, lines) for value in analysis.diagnostics)


def _invalid_analysis(raw):
    # Execution may have happened, but none of the unvalidated provenance or
    # diagnostics can be claimed. Expected profile identity is not verification.
    return BslAnalysis(
        status="failed",
        reason="BSL_ADAPTER_RESULT_INVALID",
        candidate_sha256=hashlib.sha256(raw).hexdigest(),
        candidate_size_bytes=len(raw),
        profile_id=BSL_PROFILE_ID,
        runtime_manifest_sha256=BSL_RUNTIME_MANIFEST_SHA256,
        runtime_verified=False,
        config_sha256=BSL_CONFIG_SHA256,
        scope="single_module_isolated",
        coverage="incomplete",
        diagnostics=(),
        diagnostics_complete=False,
        total_diagnostics=None,
        report_sha256=None,
        stdout_sha256=None,
        stderr_sha256=None,
        exit_code=None,
    )


def _diagnose_validated(ctx, proposal, adapter):
    _authorize(ctx)
    analysis = adapter.analyze(
        proposal.replacement_bytes,
        suffix=".os"
        if proposal.source_ref.relative_path.lower().endswith(".os")
        else ".bsl",
        authorize=lambda: _authorize(ctx),
    )
    _authorize(ctx)
    if not _analysis_valid(analysis, proposal.replacement_bytes):
        analysis = _invalid_analysis(proposal.replacement_bytes)
    status = (
        ("diagnostics_present" if analysis.diagnostics else "clean")
        if analysis.status == "completed"
        else analysis.status
    )
    return DiagnosticRun(proposal.source_ref, proposal.content_id, analysis, status)


def diagnose_proposal(
    ctx, proposal: Proposal, adapter: DiagnosticAdapter, *, limits: ProposalLimits
) -> DiagnosticRun:
    """Revalidate exact candidate bytes, then invoke one trusted startup adapter."""
    with _authorized(ctx):
        proposal = validate_proposal(
            ctx, proposal, limits=limits, authorize=lambda: _authorize(ctx)
        )
        return _diagnose_validated(ctx, proposal, adapter)


def diagnose_proposal_json(
    ctx, raw_json: bytes, adapter: DiagnosticAdapter, *, limits: ProposalLimits
) -> DiagnosticRun:
    """Parse and diagnose using one closed retained source validation session."""
    with _authorized(ctx):
        proposal = parse_proposal(
            ctx, raw_json, limits=limits, authorize=lambda: _authorize(ctx)
        )
        return _diagnose_validated(ctx, proposal, adapter)
