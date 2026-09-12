"""Local committed-Git probe and pure finding reconciliation; no worker or IO store.

Reports are trusted caller inputs, not proof an analyzer ran. A future integration
must analyze the exact commit, authorize access and persist state atomically.
"""

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import subprocess
from typing import Literal

from .errors import CoreError


@dataclass(frozen=True)
class GitObservation:
    repository: str
    commit: str
    ref: str | None


def observe_git(repository: Path | str) -> GitObservation:
    """Read local HEAD twice, rejecting dirty tracked files or visible ref races.

    Untracked/ignored files are outside this committed-only scope. This is not
    an atomic snapshot or permission boundary. Never fetches or changes refs.
    """
    root = Path(repository).resolve()
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1")

    def run(*args, allow_one=False):
        try:
            result = subprocess.run(
                [
                    "git",
                    "--no-pager",
                    "-c",
                    "core.fsmonitor=false",
                    "-C",
                    str(root),
                    *args,
                ],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CoreError("GIT_PROBE_FAILED", "Local Git probe failed") from exc
        if result.returncode not in ({0, 1} if allow_one else {0}):
            raise CoreError("GIT_PROBE_FAILED", "Local Git command failed")
        try:
            output = result.stdout.decode("utf-8", errors="strict").strip()
        except UnicodeError as exc:
            raise CoreError(
                "GIT_PROBE_FAILED", "Local Git output is not UTF-8"
            ) from exc
        return result.returncode, output

    _, top = run("rev-parse", "--show-toplevel")
    if Path(top).resolve() != root:
        raise CoreError("GIT_ROOT_REQUIRED", "Repository root is required")

    def read_head():
        _, commit = run("rev-parse", "--verify", "HEAD^{commit}")
        code, ref = run("symbolic-ref", "--quiet", "HEAD", allow_one=True)
        return GitObservation(str(root), commit, ref if code == 0 else None)

    before = read_head()
    dirty, _ = run(
        "diff",
        "--quiet",
        "--no-ext-diff",
        "--no-textconv",
        "--ignore-submodules=none",
        "HEAD",
        "--",
        allow_one=True,
    )
    if dirty:
        raise CoreError("GIT_TRACKED_DIRTY", "Modified tracked files are unsupported")
    after = read_head()
    if before != after:
        raise CoreError("GIT_HEAD_CHANGED", "Git HEAD changed during observation")
    return after


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    anchor: str
    message: str
    line: int

    @property
    def identity(self) -> tuple[str, str, str]:
        """Producer-supplied stable anchor; line/message never define identity."""
        return self.rule, self.path, self.anchor


@dataclass(frozen=True)
class FindingReport:
    observation: GitObservation
    profile_id: str
    scope_id: str
    complete: bool
    findings: tuple[Finding, ...]

    @property
    def context(self) -> tuple[str, str | None, str, str]:
        return (
            self.observation.repository,
            self.observation.ref,
            self.profile_id,
            self.scope_id,
        )


@dataclass(frozen=True)
class FindingRecord:
    finding: Finding
    first_seen: str
    last_seen: str
    resolved_at: str | None = None


@dataclass(frozen=True)
class FindingState:
    report: FindingReport
    records: tuple[FindingRecord, ...]


@dataclass(frozen=True)
class FindingEvent:
    kind: Literal["new", "resolved", "reopened"]
    identity: tuple[str, str, str]
    commit: str


@dataclass(frozen=True)
class FindingUpdate:
    state: FindingState
    events: tuple[FindingEvent, ...]


def reconcile_findings(
    previous: FindingState | None,
    report: FindingReport,
    *,
    max_records: int = 10000,
) -> FindingUpdate:
    """Reconcile a complete analysis, retaining resolved records for reopening.

    Same commit/context replays are idempotent; conflicting replays fail closed.
    Commits identify observations in caller order, not ancestry or wall time.
    """
    if report.complete is not True:
        raise CoreError("FINDINGS_INCOMPLETE", "A complete analysis report is required")
    if not report.profile_id or not report.scope_id:
        raise CoreError(
            "FINDINGS_CONTEXT_INVALID", "Explicit analysis context is required"
        )
    if max_records < 1 or len(report.findings) > max_records:
        raise CoreError("FINDINGS_LIMIT", "Finding history limit exceeded")
    current = {}
    for item in report.findings:
        if (
            any(
                not isinstance(value, str) or not value or len(value) > 4096
                for value in (item.rule, item.path, item.anchor, item.message)
            )
            or type(item.line) is not int
            or item.line < 1
        ):
            raise CoreError("FINDING_INVALID", "Invalid finding fields")
        path = PurePosixPath(item.path)
        if (
            not item.path
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in item.path
            or ":" in item.path
            or str(path) != item.path
            or item.path == "."
        ):
            raise CoreError("FINDING_PATH_INVALID", "Invalid repository-relative path")
        if item.identity in current:
            raise CoreError("FINDINGS_DUPLICATE", "Duplicate finding identity")
        current[item.identity] = item
    canonical = FindingReport(
        report.observation,
        report.profile_id,
        report.scope_id,
        True,
        tuple(current[key] for key in sorted(current)),
    )
    if previous is not None and previous.report.context != report.context:
        raise CoreError(
            "FINDINGS_CONTEXT_CHANGED", "Different context needs a new baseline"
        )
    old = (
        {record.finding.identity: record for record in previous.records}
        if previous
        else {}
    )
    if len(old.keys() | current.keys()) > max_records:
        raise CoreError("FINDINGS_LIMIT", "Finding history limit exceeded")
    if (
        previous is not None
        and previous.report.observation.commit == report.observation.commit
    ):
        if previous.report != canonical:
            raise CoreError(
                "FINDINGS_REPLAY_CONFLICT", "Conflicting report for the same commit"
            )
        return FindingUpdate(previous, ())
    commit = report.observation.commit
    records, events = [], []
    for key in sorted(old.keys() | current.keys()):
        prior, item = old.get(key), current.get(key)
        if item is not None:
            if prior is None or prior.resolved_at is not None:
                events.append(
                    FindingEvent("new" if prior is None else "reopened", key, commit)
                )
            records.append(
                FindingRecord(item, prior.first_seen if prior else commit, commit)
            )
        elif prior.resolved_at is None:
            events.append(FindingEvent("resolved", key, commit))
            records.append(
                FindingRecord(prior.finding, prior.first_seen, prior.last_seen, commit)
            )
        else:
            records.append(prior)
    return FindingUpdate(FindingState(canonical, tuple(records)), tuple(events))
