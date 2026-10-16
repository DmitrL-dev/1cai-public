"""Durable local source observer. No LLM, source writes, or external reporting."""
from contextlib import contextmanager, nullcontext
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from . import _sqlite
from .context import SnapshotRef
from .errors import CoreError
from .git_observer import (
    Finding,
    FindingRecord,
    FindingReport,
    FindingState,
    GitObservation,
    reconcile_findings,
    observe_git,
)
from .git_snapshot_evidence import (
    EVIDENCE_SCHEMA,
    GitSnapshotEvidence,
    bind_git_tree,
    read_evidence,
    read_git_tree,
    save_evidence,
)
from .publication import capture_and_publish
from .snapshot_diff import compare_snapshots
from .snapshots import ProjectHead
from .source_probe import probe_sources
from .sources import SnapshotReadLimits

SCHEMA = """
CREATE TABLE meta (id INTEGER PRIMARY KEY CHECK(id=1), binding TEXT NOT NULL,
 last_snapshot TEXT, checked_at TEXT, error TEXT);
CREATE TABLE jobs (id TEXT PRIMARY KEY, phase TEXT NOT NULL CHECK(phase IN ('capture','report','done','superseded','failed')),
 expected TEXT NOT NULL, baseline TEXT, result TEXT, attempts INTEGER NOT NULL DEFAULT 0,
 error TEXT, report TEXT, created_at TEXT NOT NULL);
"""

FINDINGS_MAX_REPORTS = 10000
FINDINGS_MAX_BYTES = 64 * 1024 * 1024
FINDINGS_MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
FINDINGS_SCHEMA = """
CREATE TABLE finding_state (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL);
CREATE TABLE finding_reports (commit_id TEXT PRIMARY KEY, receipt TEXT NOT NULL);
CREATE TABLE finding_binding (
 snapshot_id TEXT NOT NULL, commit_id TEXT PRIMARY KEY
);
"""

# Created lazily by a worker that declares its poll interval; profiles without
# this table (API-only ticks, older profiles) report polling as not recorded.
POLL_INTERVAL_MIN, POLL_INTERVAL_MAX = 5, 86400
POLL_COUNTER_MAX = 1_000_000
POLLING_SCHEMA = """CREATE TABLE IF NOT EXISTS polling (
 id INTEGER PRIMARY KEY CHECK(id=1),
 interval_seconds INTEGER NOT NULL CHECK(interval_seconds BETWEEN 5 AND 86400),
 gap_count INTEGER NOT NULL CHECK(gap_count BETWEEN 0 AND 1000000),
 clock_regressions INTEGER NOT NULL CHECK(clock_regressions BETWEEN 0 AND 1000000),
 last_gap_after TEXT, last_gap_before TEXT,
 last_gap_seconds INTEGER CHECK(last_gap_seconds >= 0))"""
_POLLING_COLUMNS = [
    ("id", "INTEGER", 0, 1),
    ("interval_seconds", "INTEGER", 1, 0),
    ("gap_count", "INTEGER", 1, 0),
    ("clock_regressions", "INTEGER", 1, 0),
    ("last_gap_after", "TEXT", 0, 0),
    ("last_gap_before", "TEXT", 0, 0),
    ("last_gap_seconds", "INTEGER", 0, 0),
]


def _polling_invalid():
    return CoreError("OBSERVER_POLLING_INVALID", "Observer polling record is invalid")


def _poll_time(value):
    if type(value) is not str or len(value) > 64:
        raise _polling_invalid()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise _polling_invalid() from exc
    if parsed.utcoffset() is None:
        raise _polling_invalid()
    return parsed


def _idle_seconds(checked_at, now):
    """Whole idle seconds since ``checked_at``; None when the clock went back."""
    delta = now - _poll_time(checked_at)
    return None if delta.days < 0 else delta.days * 86400 + delta.seconds


def _polling_record(db):
    """Return the validated single polling row, or None when none is recorded."""
    if (
        db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='polling'"
        ).fetchone()
        is None
    ):
        return None
    columns = db.execute("PRAGMA table_info(polling)").fetchall()
    if [(row[1], row[2], row[3], row[5]) for row in columns] != _POLLING_COLUMNS:
        raise _polling_invalid()
    rows = db.execute(
        "SELECT id,interval_seconds,gap_count,clock_regressions,"
        "last_gap_after,last_gap_before,last_gap_seconds FROM polling LIMIT 2"
    ).fetchall()
    if not rows:
        return None
    key, interval, gaps, regressions, after, before, seconds = rows[0]
    if (
        len(rows) != 1
        or key != 1
        or type(interval) is not int
        or not POLL_INTERVAL_MIN <= interval <= POLL_INTERVAL_MAX
        or any(
            type(count) is not int or not 0 <= count <= POLL_COUNTER_MAX
            for count in (gaps, regressions)
        )
        or (gaps == 0) != ((after, before, seconds) == (None, None, None))
        or (
            gaps
            and (
                type(seconds) is not int
                or seconds < 2 * POLL_INTERVAL_MIN
                or _idle_seconds(after, _poll_time(before)) != seconds
            )
        )
    ):
        raise _polling_invalid()
    return {
        "interval_seconds": interval,
        "gap_count": gaps,
        "clock_regressions": regressions,
        "last_gap": (
            {"after": after, "before": before, "idle_seconds": seconds}
            if gaps
            else None
        ),
    }


def _findings_version(db):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, 1, 2):
        raise CoreError("OBSERVER_SCHEMA_UNSUPPORTED", "Unsupported observer schema")
    if (
        version < 2
        and db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='git_snapshot_evidence'"
        ).fetchone()
        is not None
    ):
        raise CoreError(
            "OBSERVER_SCHEMA_UNSUPPORTED", "Legacy profile has unversioned evidence"
        )
    if version == 2:
        columns = db.execute("PRAGMA table_info(git_snapshot_evidence)").fetchall()
        if [(row[1], row[2], row[3], row[5]) for row in columns] != [
            ("commit_id", "TEXT", 0, 1),
            ("evidence", "TEXT", 1, 0),
        ]:
            raise CoreError("OBSERVER_SCHEMA_UNSUPPORTED", "Invalid evidence schema")
    return version


def _finding_state(raw):
    data = json.loads(raw)
    report = data["report"]
    return FindingState(
        FindingReport(
            GitObservation(**report["observation"]),
            report["profile_id"],
            report["scope_id"],
            report["complete"],
            tuple(Finding(**item) for item in report["findings"]),
        ),
        tuple(
            FindingRecord(
                Finding(**item["finding"]),
                item["first_seen"],
                item["last_seen"],
                item["resolved_at"],
            )
            for item in data["records"]
        ),
    )


def _validate_finding_provenance(report, ctx):
    observation = report.observation
    values = (observation.repository, report.profile_id, report.scope_id)
    if (
        any(
            not isinstance(value, str)
            or not value.strip()
            or len(value) > 4096
            or "\x00" in value
            for value in values
        )
        or not isinstance(observation.commit, str)
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", observation.commit) is None
        or (
            observation.ref is not None
            and (
                not isinstance(observation.ref, str)
                or not observation.ref.startswith("refs/")
                or len(observation.ref) > 4096
                or any(char.isspace() or ord(char) < 32 for char in observation.ref)
            )
        )
    ):
        raise CoreError(
            "FINDINGS_CONTEXT_INVALID", "Explicit Git provenance is required"
        )
    if not Path(observation.repository).is_absolute() or observation.repository != str(
        ctx.source_root.resolve()
    ):
        raise CoreError(
            "FINDINGS_CONTEXT_INVALID", "Repository must match the project source root"
        )


def _utcnow():
    return datetime.now(timezone.utc)


def _now():
    return _utcnow().isoformat()


def _json(value):
    return json.dumps(value, ensure_ascii=False, default=asdict, allow_nan=False)


def _head(raw):
    data = json.loads(raw)
    if data["snapshot"] is not None:
        data["snapshot"] = SnapshotRef(**data["snapshot"])
    return ProjectHead(**data)


def _boundary(name):
    """Fault injection for tests; not a CLI option."""


class Observer:
    def __init__(
        self, runtime, principal, project_id, profile, *, git_trust=None,
        poll_interval=None,
    ):
        """``poll_interval`` is declared only by a scheduling worker.

        With it, each ``_tick`` first accounts idle time since the previous
        persisted check; without it, polling gaps are not recorded.
        """
        if poll_interval is not None and (
            type(poll_interval) is not int
            or not POLL_INTERVAL_MIN <= poll_interval <= POLL_INTERVAL_MAX
        ):
            raise CoreError("INVALID_ARGUMENT", "Poll interval must be 5..86400")
        self.runtime, self.principal, self.project_id = runtime, principal, project_id
        self.profile = Path(profile).resolve()
        self.database = self.profile / "observer.sqlite3"
        self._git_options = {} if git_trust is None else {"trust": git_trust}
        self.poll_interval = poll_interval

    def _context(self, *, write=False):
        return self.runtime.state_context(
            self.principal,
            self.project_id,
            permissions={"project:read", "analysis:run"} if write else {"project:read"},
        )

    def _binding(self, ctx):
        return {
            "schema": 1,
            "project": ctx.project_id,
            "principal": asdict(ctx.principal),
            "state": str(ctx.state.path.resolve()),
            "source": str(ctx.source_root.resolve()),
        }

    def initialize(self):
        ctx = self._context(write=True)
        source = ctx.source_root.resolve()
        if self.profile.is_relative_to(source) or source.is_relative_to(self.profile):
            raise CoreError(
                "OBSERVER_PROFILE_UNSAFE", "Profile must be outside sources"
            )
        self.profile.mkdir(exist_ok=False)
        with (self.profile / "worker.lock").open("xb") as stream:
            stream.write(b"0")
            stream.flush()
            os.fsync(stream.fileno())
        with _sqlite.create_database(self.database, SCHEMA) as db:
            db.execute(
                "INSERT INTO meta(id,binding) VALUES(1,?)", (_json(self._binding(ctx)),)
            )

    def _validate(self, ctx):
        with _sqlite.transaction(self.database) as db:
            row = db.execute("SELECT binding FROM meta WHERE id=1").fetchone()
        if row is None or json.loads(row[0]) != self._binding(ctx):
            raise CoreError(
                "OBSERVER_PROFILE_MISMATCH", "Observer belongs to another context"
            )

    @contextmanager
    def locked(self):
        self._validate(self._context(write=True))
        if os.name != "nt":
            raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "Observer requires Windows")
        import msvcrt

        with (self.profile / "worker.lock").open("r+b") as stream:
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise CoreError(
                    "OBSERVER_BUSY", "Another worker holds this profile"
                ) from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def tick(self):
        with self.locked():
            return self._tick()

    def _active(self):
        with _sqlite.transaction(self.database) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM jobs WHERE phase IN ('capture','report','failed') ORDER BY rowid LIMIT 1"
            ).fetchone()
            return dict(row) if row is not None else None

    def _record_poll(self):
        """Persist a polling gap before this cycle reads sources.

        Idle time is measured from the previous persisted ``checked_at`` to
        the start of this cycle. At least two intervals means at least one
        whole scheduled poll was missed. A clock that went back is counted
        separately and never reported as on schedule.
        """
        interval = self.poll_interval
        with _sqlite.transaction(self.database, write=True) as db:
            db.execute(POLLING_SCHEMA)
            record = _polling_record(db) or {
                "gap_count": 0,
                "clock_regressions": 0,
                "last_gap": None,
            }
            checked = db.execute("SELECT checked_at FROM meta WHERE id=1").fetchone()[0]
            now = _utcnow()
            gaps, regressions = record["gap_count"], record["clock_regressions"]
            gap = record["last_gap"]
            if checked is not None:
                idle = _idle_seconds(checked, now)
                if idle is None:
                    regressions = min(regressions + 1, POLL_COUNTER_MAX)
                elif idle >= 2 * interval:
                    gaps = min(gaps + 1, POLL_COUNTER_MAX)
                    gap = {
                        "after": checked,
                        "before": now.isoformat(),
                        "idle_seconds": idle,
                    }
            gap = gap or {"after": None, "before": None, "idle_seconds": None}
            db.execute(
                "INSERT INTO polling(id,interval_seconds,gap_count,clock_regressions,"
                "last_gap_after,last_gap_before,last_gap_seconds) VALUES(1,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET interval_seconds=excluded.interval_seconds,"
                "gap_count=excluded.gap_count,clock_regressions=excluded.clock_regressions,"
                "last_gap_after=excluded.last_gap_after,"
                "last_gap_before=excluded.last_gap_before,"
                "last_gap_seconds=excluded.last_gap_seconds",
                (
                    interval,
                    gaps,
                    regressions,
                    gap["after"],
                    gap["before"],
                    gap["idle_seconds"],
                ),
            )
            _boundary("polling_written")

    def _tick(self):
        ctx = self._context(write=True)
        self._validate(ctx)
        if self.poll_interval is not None:
            self._record_poll()
        job = self._active()
        if job is not None and job["phase"] == "failed":
            raise CoreError(
                "OBSERVER_JOB_FAILED",
                "Task needs explicit retry",
                details={"operation_id": job["id"]},
            )
        try:
            if job is None:
                head, digest = probe_sources(ctx)
                with ctx.state.transaction(ctx.principal) as tx:
                    tx.require_all({"project:read", "analysis:run"})
                    catalog = (
                        tx.get_snapshot(head.snapshot.snapshot_id)
                        if head.snapshot
                        else None
                    )
                with _sqlite.transaction(self.database, write=True) as db:
                    last = db.execute(
                        "SELECT last_snapshot FROM meta WHERE id=1"
                    ).fetchone()[0]
                    db.execute(
                        "UPDATE meta SET checked_at=?,error=NULL WHERE id=1", (_now(),)
                    )
                    current_matches = (
                        catalog is not None and catalog.source_digest == digest
                    )
                    if current_matches and last == head.snapshot.snapshot_id:
                        return {"status": "unchanged", "snapshot_id": last}
                    if db.execute("SELECT count(*) FROM jobs").fetchone()[0] >= 10000:
                        raise CoreError(
                            "OBSERVER_JOURNAL_FULL", "Journal reached 10000 tasks"
                        )
                    result = (
                        _json({"snapshot": head.snapshot, "source_digest": digest})
                        if current_matches
                        else None
                    )
                    db.execute(
                        "INSERT INTO jobs(id,phase,expected,baseline,result,created_at) VALUES(?,?,?,?,?,?)",
                        (
                            str(uuid4()),
                            "report" if current_matches else "capture",
                            _json(head),
                            last,
                            result,
                            _now(),
                        ),
                    )
                job = self._active()
            if job["phase"] == "capture":
                receipt = capture_and_publish(
                    ctx,
                    expected_head=_head(job["expected"]),
                    operation_id=job["id"],
                    builder=self.runtime.graph_builder,
                )
                _boundary("capture_committed")
                with ctx.state.transaction(ctx.principal) as tx:
                    tx.require_all({"project:read", "analysis:run"})
                    catalog = tx.get_snapshot(receipt.snapshot.snapshot_id)
                result = _json(
                    {
                        "snapshot": receipt.snapshot,
                        "source_digest": catalog.source_digest,
                    }
                )
                with _sqlite.transaction(self.database, write=True) as db:
                    db.execute(
                        "UPDATE jobs SET phase='report',result=?,attempts=0,error=NULL WHERE id=?",
                        (result, job["id"]),
                    )
                job = self._active()
            result = json.loads(job["result"])
            after_id = result["snapshot"]["snapshot_id"]
            after = self.runtime.resolve(self.principal, self.project_id, after_id)
            if job["baseline"] is None:
                with after.sources.read_session(limits=SnapshotReadLimits()) as session:
                    entries = session.entries()
                    change = {
                        "kind": "baseline",
                        "files_present": len(entries),
                        "bytes_present": sum(e.size_bytes for e in entries),
                    }
            else:
                before = self.runtime.resolve(
                    self.principal, self.project_id, job["baseline"]
                )
                change = json.loads(_json(compare_snapshots(before, after)))
            report = {
                "schema": 1,
                "operation_id": job["id"],
                "project_id": self.project_id,
                "created_at": _now(),
                "before": job["baseline"],
                "after": after_id,
                "changes": change,
                "details_truncated": change.get("next_cursor") is not None,
                "quality": {"status": "not_run"},
                "business_metrics": {"status": "not_available"},
                "model_calls": 0,
                "source_temporal_atomicity": "not_proven",
            }
            _boundary("report_ready")
            with ctx.state.transaction(ctx.principal) as tx:
                tx.require_all({"project:read", "analysis:run"})
                with _sqlite.transaction(self.database, write=True) as db:
                    db.execute(
                        "UPDATE jobs SET phase='done',report=?,error=NULL WHERE id=?",
                        (_json(report), job["id"]),
                    )
                    _boundary("report_journal_written")
                    db.execute(
                        "UPDATE meta SET last_snapshot=?,checked_at=?,error=NULL WHERE id=1",
                        (after_id, _now()),
                    )
            return {
                "status": "reported",
                "operation_id": job["id"],
                "snapshot_id": after_id,
            }
        except CoreError as exc:
            with _sqlite.transaction(self.database, write=True) as db:
                db.execute(
                    "UPDATE meta SET checked_at=?,error=? WHERE id=1",
                    (_now(), exc.code),
                )
                if job is not None:
                    if exc.code in {"HEAD_CONFLICT", "SOURCE_CONFIGURATION_CONFLICT"}:
                        db.execute(
                            "UPDATE jobs SET phase='superseded',error=? WHERE id=?",
                            (exc.code, job["id"]),
                        )
                    else:
                        db.execute(
                            "UPDATE jobs SET attempts=attempts+1,error=?,phase=CASE WHEN attempts>=2 THEN 'failed' ELSE phase END WHERE id=?",
                            (exc.code, job["id"]),
                        )
            raise

    def retry(self):
        with self.locked(), _sqlite.transaction(self.database, write=True) as db:
            db.execute(
                "UPDATE jobs SET phase=CASE WHEN result IS NULL THEN 'capture' ELSE 'report' END,attempts=0,error=NULL WHERE phase='failed'"
            )

    def verify_git_snapshot(
        self, observation: GitObservation
    ) -> GitSnapshotEvidence | None:
        """Probe stable sources between clean Git observations; None means no head.

        The confined source probe checks both content passes and project head.
        Every published snapshot file outside the repository's own ``.git`` must
        equal the blob at the same path of ``commit^{tree}``; tree entries the
        snapshot does not contain are counted, not proven.
        """
        ctx = self._context(write=True)
        self._validate(ctx)
        if not isinstance(observation, GitObservation) or observation.repository != str(
            ctx.source_root.resolve()
        ):
            raise CoreError("GIT_SNAPSHOT_CONTEXT", "Repository must match source root")
        if observe_git(ctx.source_root, **self._git_options) != observation:
            raise CoreError("GIT_HEAD_CHANGED", "Git HEAD changed before source probe")
        head, digest = probe_sources(ctx)
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all({"project:read", "analysis:run"})
            if tx.get_project_head() != head:
                raise CoreError(
                    "HEAD_CONFLICT", "Published head changed after source probe"
                )
            catalog = (
                tx.get_snapshot(head.snapshot.snapshot_id) if head.snapshot else None
            )
            if catalog is not None and catalog.source_digest != digest:
                raise CoreError(
                    "GIT_SNAPSHOT_MISMATCH",
                    "Published snapshot differs from observed sources",
                )
        tree_binding = (
            None
            if catalog is None
            else self._bind_git_tree(observation, head.snapshot.snapshot_id)
        )
        if observe_git(ctx.source_root, **self._git_options) != observation:
            raise CoreError("GIT_HEAD_CHANGED", "Git HEAD changed during source probe")
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all({"project:read", "analysis:run"})
            if tx.get_project_head() != head:
                raise CoreError(
                    "HEAD_CONFLICT", "Published head changed during verification"
                )
        return (
            None
            if catalog is None
            else GitSnapshotEvidence(
                self.project_id,
                observation,
                head.snapshot.snapshot_id,
                digest,
                tree_binding,
            )
        )

    def _bind_git_tree(self, observation, snapshot_id):
        """Compare the published snapshot's retained bytes with commit blobs."""
        tree = read_git_tree(
            observation.repository, observation.commit, **self._git_options
        )
        snapshot = self.runtime.resolve(self.principal, self.project_id, snapshot_id)
        with snapshot.sources.read_session(limits=SnapshotReadLimits()) as session:
            roots = session.layer_roots()
            pairs = [
                (
                    entry.ref.relative_path
                    if roots[entry.ref.layer_id] == "."
                    else roots[entry.ref.layer_id] + "/" + entry.ref.relative_path,
                    entry.ref,
                )
                for entry in session.entries()
            ]
            refs = dict(pairs)
            binding = bind_git_tree(
                tree,
                [path for path, _ in pairs],
                lambda path: session.read_source(refs[path]),
                roots.values(),
            )
        return binding

    def _check_git_evidence(self, evidence, observation, catalog):
        if (
            not isinstance(evidence, GitSnapshotEvidence)
            or evidence.project_id != self.project_id
            or evidence.observation != observation
            or evidence.snapshot_id != catalog.snapshot.snapshot_id
            or evidence.source_digest != catalog.source_digest
        ):
            raise CoreError(
                "GIT_SNAPSHOT_EVIDENCE_INVALID", "Evidence context or digest mismatch"
            )

    def record_findings(
        self, report: FindingReport, *, snapshot_id=None, evidence=None, _locked=False
    ):
        """Persist a caller report, rechecking any new source/Git evidence.

        One repo/ref/profile/scope context is retained per observer profile.
        Historical commit replays return their original receipt without moving
        current state. Caller ordering is authoritative; ancestry is not checked.
        ``snapshot_id`` is an explicit caller assertion that the finding commit
        was analyzed against that published snapshot. Without it, the durable
        findings remain unbound and are never presented as snapshot quality.
        Typed ``evidence`` requests verified binding; new evidence is checked
        against live sources, while a durable identical replay is historical.
        """
        with nullcontext() if _locked else self.locked():
            ctx = self._context(write=True)
            _validate_finding_provenance(report, ctx)
            if evidence is not None:
                if not isinstance(evidence, GitSnapshotEvidence):
                    raise CoreError(
                        "GIT_SNAPSHOT_EVIDENCE_INVALID", "Typed evidence required"
                    )
                if snapshot_id is not None and snapshot_id != evidence.snapshot_id:
                    raise CoreError(
                        "GIT_SNAPSHOT_EVIDENCE_INVALID", "Snapshot arguments disagree"
                    )
                snapshot_id = evidence.snapshot_id
            if snapshot_id is not None:
                SnapshotRef(self.project_id, snapshot_id, snapshot_id)
                with ctx.state.transaction(ctx.principal) as tx:
                    tx.require_all({"project:read", "analysis:run"})
                    catalog = tx.get_snapshot(snapshot_id)
                if evidence is not None:
                    self._check_git_evidence(evidence, report.observation, catalog)
                    with _sqlite.transaction(self.database) as db:
                        _findings_version(db)
                        saved_evidence = read_evidence(db, report.observation.commit)
                    if saved_evidence is not None:
                        if saved_evidence != evidence:
                            raise CoreError(
                                "FINDINGS_REPLAY_CONFLICT",
                                "Conflicting Git snapshot evidence",
                            )
                    elif self.verify_git_snapshot(report.observation) != evidence:
                        raise CoreError(
                            "GIT_SNAPSHOT_EVIDENCE_INVALID", "Evidence is not verified"
                        )
            canonical = reconcile_findings(None, report).state.report
            with _sqlite.transaction(self.database, write=True) as db:
                if _findings_version(db) == 0:
                    for statement in FINDINGS_SCHEMA.split(";"):
                        if statement.strip():
                            db.execute(statement)

                else:
                    # Profiles created before explicit snapshot bindings remain
                    # readable; their existing state is intentionally unbound.
                    db.execute(
                        "CREATE TABLE IF NOT EXISTS finding_binding ("
                        "snapshot_id TEXT NOT NULL, commit_id TEXT PRIMARY KEY)"
                    )
                if _findings_version(db) < 2:
                    db.execute(EVIDENCE_SCHEMA)
                    db.execute("PRAGMA user_version=2")
                    _findings_version(db)
                if evidence is not None:
                    save_evidence(db, evidence, _json(evidence))
                row = db.execute(
                    "SELECT state FROM finding_state WHERE id=1"
                ).fetchone()
                previous = _finding_state(row[0]) if row else None
                if (
                    previous is not None
                    and previous.report.context != canonical.context
                ):
                    raise CoreError(
                        "FINDINGS_CONTEXT_CHANGED",
                        "Different context needs a new profile",
                    )
                saved = db.execute(
                    "SELECT receipt FROM finding_reports WHERE commit_id=?",
                    (canonical.observation.commit,),
                ).fetchone()
                if saved is not None:
                    receipt = json.loads(saved[0])
                    if receipt["report"] != json.loads(_json(canonical)):
                        raise CoreError(
                            "FINDINGS_REPLAY_CONFLICT",
                            "Conflicting report for the same commit",
                        )
                    binding = db.execute(
                        "SELECT snapshot_id FROM finding_binding WHERE commit_id=?",
                        (canonical.observation.commit,),
                    ).fetchone()
                    if snapshot_id is not None:
                        if binding is not None and binding != (snapshot_id,):
                            raise CoreError(
                                "FINDINGS_REPLAY_CONFLICT",
                                "Finding commit is already bound to another snapshot",
                            )
                        if binding is None:
                            db.execute(
                                "INSERT INTO finding_binding(snapshot_id,commit_id) VALUES(?,?)",
                                (snapshot_id, canonical.observation.commit),
                            )
                else:
                    update = reconcile_findings(previous, canonical)
                    receipt = {
                        "schema": 1,
                        "operation_id": str(uuid4()),
                        "project_id": self.project_id,
                        "created_at": _now(),
                        "baseline": previous is None,
                        "report": canonical,
                        "events": update.events,
                        "model_calls": 0,
                        "analysis": "caller_supplied",
                    }
                    state_json, receipt_json = _json(update.state), _json(receipt)
                    state_size, receipt_size = (
                        len(value.encode("utf-8"))
                        for value in (state_json, receipt_json)
                    )
                    count, used = db.execute(
                        "SELECT count(*),coalesce(sum(length(CAST(receipt AS BLOB))),0) FROM finding_reports"
                    ).fetchone()
                    if (
                        count >= FINDINGS_MAX_REPORTS
                        or used + state_size + receipt_size > FINDINGS_MAX_BYTES
                        or max(state_size, receipt_size) > FINDINGS_MAX_DOCUMENT_BYTES
                    ):
                        raise CoreError(
                            "OBSERVER_JOURNAL_FULL",
                            "Finding journal limit reached; history retained",
                        )
                    db.execute(
                        "INSERT INTO finding_state(id,state) VALUES(1,?) "
                        "ON CONFLICT(id) DO UPDATE SET state=excluded.state",
                        (state_json,),
                    )
                    _boundary("findings_state_saved")
                    db.execute(
                        "INSERT INTO finding_reports(commit_id,receipt) VALUES(?,?)",
                        (canonical.observation.commit, receipt_json),
                    )
                    if snapshot_id is not None:
                        db.execute(
                            "INSERT INTO finding_binding(snapshot_id,commit_id) VALUES(?,?)",
                            (snapshot_id, canonical.observation.commit),
                        )
                    _boundary("findings_journal_saved")
                    receipt = json.loads(receipt_json)
                _boundary("findings_ready")
                with ctx.state.transaction(ctx.principal) as tx:
                    tx.require_all({"project:read", "analysis:run"})
            with ctx.state.transaction(ctx.principal) as tx:
                tx.require_all({"project:read", "analysis:run"})
            return receipt

    def findings_status(self, *, limit=10):
        """Read durable state and recent receipts, reauthorizing before return."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise CoreError("INVALID_QUERY_OPTIONS", "Report limit must be 1 to 100")
        ctx = self._context(write=True)
        self._validate(ctx)
        with _sqlite.transaction(self.database) as db:
            if _findings_version(db) == 0:
                document = {"state": None, "reports": [], "reports_truncated": False}
            else:
                row = db.execute(
                    "SELECT state FROM finding_state WHERE id=1"
                ).fetchone()
                reports = db.execute(
                    "SELECT receipt FROM finding_reports ORDER BY rowid DESC LIMIT ?",
                    (limit + 1,),
                ).fetchall()
                document = {
                    "state": json.loads(row[0]) if row else None,
                    "reports": [json.loads(item[0]) for item in reports[:limit]],
                    "reports_truncated": len(reports) > limit,
                }
        _boundary("findings_status_ready")
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all({"project:read", "analysis:run"})
        return document

    def owner_report(
        self, snapshot_id, *, runtime=None, authorize=None, max_findings=1000
    ):
        """Build a context-bound owner report from durable findings.

        Runtime evidence remains an explicit typed adapter input; this method
        never starts a process, queries 1C/SQL or invents business metrics.
        """
        SnapshotRef(self.project_id, snapshot_id, snapshot_id)
        ctx = self._context(write=True)
        try:
            self._validate(ctx)
            with ctx.state.transaction(ctx.principal) as tx:
                tx.require_all({"project:read", "analysis:run"})
                catalog = tx.get_snapshot(snapshot_id)
            evidence = None
            with _sqlite.transaction(self.database) as db:
                if _findings_version(db) == 0:
                    findings = None
                    binding = None
                else:
                    row = db.execute(
                        "SELECT state FROM finding_state WHERE id=1"
                    ).fetchone()
                    findings = None if row is None else _finding_state(row[0])
                    binding_table = db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='finding_binding'"
                    ).fetchone()
                    binding = (
                        db.execute(
                            "SELECT snapshot_id FROM finding_binding WHERE commit_id=?",
                            (findings.report.observation.commit,),
                        ).fetchone()
                        if binding_table is not None and findings is not None
                        else None
                    )
                    if findings is not None:
                        evidence = read_evidence(db, findings.report.observation.commit)
            provenance = None
            if evidence is not None and binding == (snapshot_id,):
                self._check_git_evidence(evidence, findings.report.observation, catalog)
                provenance = "git_source_verified"
            elif binding == (snapshot_id,):
                provenance = "caller_asserted"
            quality_reason = None
            if findings is not None and binding != (snapshot_id,):
                findings = None
                quality_reason = "quality_snapshot_binding_unverified"
            from .owner_report import build_owner_report

            report = build_owner_report(
                self.project_id,
                snapshot_id,
                findings=findings,
                runtime=runtime,
                authorize=authorize,
                max_findings=max_findings,
            )
            if provenance is not None:
                report["quality"]["provenance"] = provenance
            if (
                provenance == "git_source_verified"
                and evidence.tree_binding is not None
            ):
                report["quality"]["git_tree"] = asdict(evidence.tree_binding)
            if quality_reason is not None:
                report["quality"] = {
                    "status": "not_available",
                    "reason": quality_reason,
                }
            with ctx.state.transaction(ctx.principal) as tx:
                tx.require_all({"project:read", "analysis:run"})
            return report
        except BaseException:
            with ctx.state.transaction(ctx.principal) as tx:
                tx.require_all({"project:read", "analysis:run"})
            raise

    def status(self, *, limit=10):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise CoreError("INVALID_QUERY_OPTIONS", "Report limit must be 1 to 100")
        ctx = self._context()
        self._validate(ctx)
        with _sqlite.transaction(self.database) as db:
            last, checked, error = db.execute(
                "SELECT last_snapshot,checked_at,error FROM meta WHERE id=1"
            ).fetchone()
            jobs = db.execute(
                "SELECT id,phase,attempts,error FROM jobs ORDER BY rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
            reports = [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT report FROM jobs WHERE phase='done' ORDER BY rowid DESC LIMIT ?",
                    (limit,),
                )
            ]
            record = _polling_record(db)
        idle = None if checked is None else _idle_seconds(checked, _utcnow())
        polling = {
            "interval_seconds": None,
            "gap_count": None,
            "clock_regressions": None,
            "last_gap": None,
            **(record or {}),
            "idle_seconds": idle,
        }
        polling["on_schedule"] = (
            record is not None
            and idle is not None
            and idle < 2 * record["interval_seconds"]
        )
        document = {
            "last_snapshot": last,
            "checked_at": checked,
            "error": error,
            "jobs": [
                dict(zip(("operation_id", "phase", "attempts", "error"), row))
                for row in jobs
            ],
            "reports": reports,
            "polling": polling,
        }
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all({"project:read"})
        return document
