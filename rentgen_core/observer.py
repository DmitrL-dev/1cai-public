"""Durable local source observer. No LLM, source writes, or external reporting."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from . import _sqlite
from .context import SnapshotRef
from .errors import CoreError
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


def _now():
    return datetime.now(timezone.utc).isoformat()


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
    def __init__(self, runtime, principal, project_id, profile):
        self.runtime, self.principal, self.project_id = runtime, principal, project_id
        self.profile = Path(profile).resolve()
        self.database = self.profile / "observer.sqlite3"

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

    def _tick(self):
        ctx = self._context(write=True)
        self._validate(ctx)
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
        document = {
            "last_snapshot": last,
            "checked_at": checked,
            "error": error,
            "jobs": [
                dict(zip(("operation_id", "phase", "attempts", "error"), row))
                for row in jobs
            ],
            "reports": reports,
        }
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all({"project:read"})
        return document
