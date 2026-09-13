"""Bounded orchestration for committed Git analysis and durable findings."""

from dataclasses import asdict
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from uuid import UUID, uuid4

from .errors import CoreError
from .git_observer import FindingReport, observe_git, require_ancestor


def _option(value, name):
    if (
        type(value) is not str
        or not 1 <= len(value) <= 4096
        or not value.strip()
        or "\x00" in value
        or any(ord(char) < 32 for char in value)
    ):
        raise CoreError("GIT_WATCHER_INVALID", f"Invalid {name}")
    return value


class SchedulerJournal:
    """Atomic local scheduler state with explicit interrupted-run recovery."""

    MAX_BYTES = 1024 * 1024

    def __init__(self, path):
        self.path = Path(path).resolve()
        if self.path.exists() and not self.path.is_file():
            raise CoreError("GIT_WATCHER_INVALID", "Scheduler journal file required")
        if not self.path.parent.exists() or not self.path.parent.is_dir():
            raise CoreError("GIT_WATCHER_INVALID", "Scheduler journal parent required")

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _run_id(value):
        if not isinstance(value, str):
            raise CoreError("GIT_WATCHER_RECOVERY_REQUIRED", "Malformed scheduler run")
        try:
            UUID(value)
        except (ValueError, AttributeError, TypeError) as exc:
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "Malformed scheduler run"
            ) from exc
        return value

    def _read(self):
        if not self.path.exists():
            return None
        try:
            raw = self.path.read_bytes()
            if len(raw) > self.MAX_BYTES:
                raise CoreError(
                    "GIT_WATCHER_RECOVERY_REQUIRED", "Scheduler journal too large"
                )
            document = json.loads(raw.decode("utf-8"))
        except CoreError:
            raise
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "Scheduler journal is unreadable"
            ) from exc
        if (
            not isinstance(document, dict)
            or document.get("schema") != 1
            or document.get("scheduler") != "git-watcher-v1"
            or document.get("phase") not in {"running", "recovered", "idle"}
            or type(document.get("cycle")) is not int
            or not 0 <= document["cycle"] <= 10_000
            or type(document.get("failures")) is not int
            or not 0 <= document["failures"] <= 10_000
            or not isinstance(document.get("updated_at"), str)
            or len(document["updated_at"]) > 64
        ):
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "Malformed scheduler journal"
            )
        try:
            timestamp = datetime.fromisoformat(document["updated_at"])
        except (TypeError, ValueError) as exc:
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "Malformed scheduler timestamp"
            ) from exc
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "Scheduler timestamp needs timezone"
            )
        self._run_id(document.get("run_id"))
        event = document.get("event")
        if event is not None and not isinstance(event, dict):
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "Malformed scheduler event"
            )
        return document

    def read(self):
        """Return a validated copy of the current state, or ``None``."""
        document = self._read()
        return None if document is None else dict(document)

    def _write(self, document):
        raw = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if len(raw) > self.MAX_BYTES:
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "Scheduler journal too large"
            )
        temporary = self.path.with_name(self.path.name + ".tmp")
        if temporary.exists():
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "Scheduler journal recovery required"
            )
        try:
            with temporary.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except CoreError:
            raise
        except OSError as exc:
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "Scheduler journal write failed"
            ) from exc

    @staticmethod
    def _document(run_id, phase, cycle, failures, event=None, *, recovered_reason=None):
        document = {
            "schema": 1,
            "scheduler": "git-watcher-v1",
            "phase": phase,
            "run_id": run_id,
            "cycle": cycle,
            "failures": failures,
            "event": event,
            "updated_at": SchedulerJournal._now(),
        }
        if recovered_reason is not None:
            document["reason"] = _option(recovered_reason, "recovery reason")
        return document

    def begin(self):
        current = self._read()
        if current is not None and current["phase"] == "running":
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED",
                "Previous scheduler run needs explicit recovery",
            )
        run_id = str(uuid4())
        self._write(self._document(run_id, "running", 0, 0))
        return run_id

    def _same_run(self, run_id):
        current = self._read()
        if (
            current is None
            or current["phase"] != "running"
            or current["run_id"] != self._run_id(run_id)
        ):
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "Scheduler run is not active"
            )
        return current

    def mark_running(self, run_id, cycle, failures):
        if type(cycle) is not int or not 0 <= cycle <= 10_000:
            raise CoreError("GIT_WATCHER_INVALID", "Scheduler cycle is out of bounds")
        if type(failures) is not int or not 0 <= failures <= 10_000:
            raise CoreError(
                "GIT_WATCHER_INVALID", "Scheduler failure count is out of bounds"
            )
        self._same_run(run_id)
        self._write(self._document(run_id, "running", cycle, failures))

    def record(self, run_id, cycle, failures, event, *, keep_running=True):
        if not isinstance(event, dict):
            raise CoreError("GIT_WATCHER_INVALID", "Scheduler event must be an object")
        self._same_run(run_id)
        self._write(
            self._document(
                run_id,
                "running" if keep_running else "idle",
                cycle,
                failures,
                dict(event),
            )
        )

    def stop(self, run_id, cycle=None, failures=None):
        current = self._same_run(run_id)
        cycle = current["cycle"] if cycle is None else cycle
        failures = current["failures"] if failures is None else failures
        self._write(
            self._document(run_id, "idle", cycle, failures, {"status": "stopped"})
        )

    def recover(self, reason):
        current = self._read()
        if current is None or current["phase"] != "running":
            raise CoreError(
                "GIT_WATCHER_RECOVERY_REQUIRED", "No interrupted scheduler run"
            )
        self._write(
            self._document(
                current["run_id"],
                "recovered",
                current["cycle"],
                current["failures"],
                {"status": "recovered"},
                recovered_reason=reason,
            )
        )


class NotificationOutbox:
    """Bounded atomic event queue for a caller-owned notification adapter."""

    MAX_BYTES = 4 * 1024 * 1024
    MAX_EVENTS = 1000

    def __init__(self, path):
        self.path = Path(path).resolve()
        if self.path.exists() and not self.path.is_file():
            raise CoreError("GIT_WATCHER_NOTIFICATION_INVALID", "Outbox file required")
        if not self.path.parent.exists() or not self.path.parent.is_dir():
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_INVALID", "Outbox parent required"
            )

    @contextmanager
    def _locked(self):
        """Serialize read-modify-write operations across producer processes."""
        lock_path = self.path.with_name(self.path.name + ".lock")
        if lock_path.is_symlink() or (lock_path.exists() and not lock_path.is_file()):
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_INVALID", "Outbox lock file required"
            )
        try:
            descriptor = os.open(
                lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o600
            )
            stream = os.fdopen(descriptor, "r+b")
        except OSError as exc:
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED",
                "Outbox lock could not be opened",
            ) from exc
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                if stream.read(1) == b"":
                    stream.seek(0)
                    stream.write(b"0")
                    stream.flush()
                for _ in range(20):
                    stream.seek(0)
                    try:
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                        acquired = True
                        break
                    except OSError:
                        time.sleep(0.01)
            else:
                import fcntl

                for _ in range(20):
                    try:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                        break
                    except OSError:
                        time.sleep(0.01)
            if not acquired:
                raise CoreError(
                    "GIT_WATCHER_NOTIFICATION_BUSY",
                    "Another outbox operation is active",
                )
            yield
        finally:
            if acquired:
                try:
                    if os.name == "nt":
                        import msvcrt

                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            stream.close()

    def _read(self):
        if not self.path.exists():
            return {"schema": 1, "outbox": "git-watcher-v1", "next_id": 1, "events": []}
        try:
            raw = self.path.read_bytes()
            if len(raw) > self.MAX_BYTES:
                raise CoreError(
                    "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED", "Outbox is too large"
                )
            document = json.loads(raw.decode("utf-8"))
        except CoreError:
            raise
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED", "Outbox is unreadable"
            ) from exc
        if (
            not isinstance(document, dict)
            or document.get("schema") != 1
            or document.get("outbox") != "git-watcher-v1"
            or type(document.get("next_id")) is not int
            or not 1 <= document["next_id"] <= 2**63
            or not isinstance(document.get("events"), list)
            or len(document["events"]) > self.MAX_EVENTS
        ):
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED", "Malformed outbox"
            )
        previous = 0
        for item in document["events"]:
            if (
                not isinstance(item, dict)
                or set(item) != {"id", "event", "created_at"}
                or type(item["id"]) is not int
                or not previous < item["id"] < document["next_id"]
                or not isinstance(item["event"], dict)
                or not isinstance(item["created_at"], str)
            ):
                raise CoreError(
                    "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED",
                    "Malformed outbox event",
                )
            try:
                timestamp = datetime.fromisoformat(item["created_at"])
            except (TypeError, ValueError) as exc:
                raise CoreError(
                    "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED",
                    "Malformed outbox timestamp",
                ) from exc
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise CoreError(
                    "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED",
                    "Outbox timestamp needs timezone",
                )
            previous = item["id"]
        return document

    def _write(self, document):
        try:
            raw = json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, RecursionError) as exc:
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_INVALID", "Outbox event is not JSON"
            ) from exc
        if len(raw) > self.MAX_BYTES:
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_INVALID", "Outbox size limit exceeded"
            )
        temporary = self.path.with_name(self.path.name + ".tmp")
        if temporary.exists():
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED",
                "Outbox recovery required",
            )
        try:
            with temporary.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED", "Outbox write failed"
            ) from exc

    def enqueue(self, event):
        if not isinstance(event, dict):
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_INVALID", "Outbox event must be an object"
            )
        with self._locked():
            document = self._read()
            if len(document["events"]) >= self.MAX_EVENTS:
                raise CoreError(
                    "GIT_WATCHER_NOTIFICATION_LIMIT", "Outbox event limit reached"
                )
            notification_id = document["next_id"]
            document["next_id"] += 1
            document["events"].append(
                {
                    "id": notification_id,
                    "event": dict(event),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            self._write(document)
            return notification_id

    def peek(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= self.MAX_EVENTS:
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_INVALID", "Outbox limit is out of bounds"
            )
        with self._locked():
            return [dict(item) for item in self._read()["events"][:limit]]

    def ack(self, notification_id):
        if type(notification_id) is not int or not 1 <= notification_id <= 2**63:
            raise CoreError(
                "GIT_WATCHER_NOTIFICATION_INVALID", "Invalid notification id"
            )
        with self._locked():
            document = self._read()
            if not any(item["id"] == notification_id for item in document["events"]):
                raise CoreError(
                    "GIT_WATCHER_NOTIFICATION_INVALID", "Unknown notification id"
                )
            document["events"] = [
                item for item in document["events"] if item["id"] != notification_id
            ]
            self._write(document)


class GitWatcher:
    """Run one explicit, race-checked analysis pass for a committed HEAD.

    The caller owns the analyzer. It receives the immutable observation returned
    by observe_git and must return a complete FindingReport for the exact same
    observation, profile and scope. The watcher never starts a process, model,
    network request or background thread.
    """

    def __init__(
        self,
        observer,
        analyzer,
        *,
        repository=None,
        profile_id="analyzer-v1",
        scope_id="whole-repository",
    ):
        if not callable(analyzer):
            raise CoreError("GIT_WATCHER_INVALID", "Analyzer callback is required")
        self.observer = observer
        self.analyzer = analyzer
        self.repository = None if repository is None else Path(repository).resolve()
        self.profile_id = _option(profile_id, "profile_id")
        self.scope_id = _option(scope_id, "scope_id")

    def _report(self, observation):
        report = self.analyzer(observation)
        if not isinstance(report, FindingReport):
            raise CoreError(
                "GIT_WATCHER_CONTEXT", "Analyzer must return a FindingReport"
            )
        if (
            report.observation != observation
            or report.profile_id != self.profile_id
            or report.scope_id != self.scope_id
            or report.complete is not True
        ):
            raise CoreError(
                "GIT_WATCHER_CONTEXT",
                "Analyzer report is not bound to the observed commit",
            )
        return report

    @staticmethod
    def _state_commit(state, profile_id, scope_id):
        if state is None:
            return None
        report = state.get("report") if isinstance(state, dict) else None
        observation = report.get("observation") if isinstance(report, dict) else None
        if not isinstance(report, dict) or not isinstance(observation, dict):
            raise CoreError(
                "GIT_WATCHER_CONTEXT", "Durable findings state is malformed"
            )
        if report.get("profile_id") != profile_id or report.get("scope_id") != scope_id:
            raise CoreError(
                "GIT_WATCHER_CONTEXT",
                "Durable findings state belongs to another analysis context",
            )
        return observation.get("commit")

    def tick(self):
        """Analyze at most one new clean commit and persist it atomically."""
        with self.observer.locked():
            ctx = self.observer._context(write=True)
            self.observer._validate(ctx)
            repository = self.repository or ctx.source_root.resolve()
            expected = str(ctx.source_root.resolve())
            if str(repository) != expected:
                raise CoreError(
                    "GIT_WATCHER_CONTEXT",
                    "Repository must match the registered project source root",
                )
            observation = observe_git(repository)
            if observation.repository != expected:
                raise CoreError(
                    "GIT_WATCHER_CONTEXT",
                    "Repository must match the registered project source root",
                )

            status = self.observer.findings_status(limit=1)
            commit = self._state_commit(status["state"], self.profile_id, self.scope_id)
            if commit == observation.commit:
                return {
                    "status": "unchanged",
                    "commit": observation.commit,
                    "observation": asdict(observation),
                }
            if commit is not None:
                require_ancestor(repository, commit, observation.commit)

            evidence = self.observer.verify_git_snapshot(observation)
            report = self._report(observation)
            latest = observe_git(repository)
            if latest != observation:
                raise CoreError(
                    "GIT_HEAD_CHANGED",
                    "Git HEAD changed while the commit was being analyzed",
                )
            receipt = self.observer.record_findings(
                report, evidence=evidence, _locked=True
            )
            return {
                "status": "analyzed",
                "snapshot_binding": "git_source_verified"
                if evidence
                else "unbound_no_snapshot",
                "commit": observation.commit,
                "observation": asdict(observation),
                "receipt": receipt,
            }


@contextmanager
def _preserve_primary_error(error):
    """Retain the run failure when diagnostic persistence also fails."""
    try:
        yield
    except BaseException as secondary:
        if error is None:
            raise
        error.add_note(
            f"Scheduler persistence failed: {type(secondary).__name__}: {secondary}"
        )


class GitWatcherScheduler:
    """Bounded foreground loop for a GitWatcher with explicit backoff.

    The observer's profile lock remains the process lease. This helper does not
    create threads or hide failures; callers choose a stop predicate and retain
    the returned events for their own service/notification layer.
    """

    MAX_RETAINED_EVENTS = 1000

    def __init__(
        self,
        watcher,
        *,
        interval=60,
        max_cycles=None,
        max_backoff=3600,
        sleep=time.sleep,
        should_stop=lambda: False,
        journal=None,
        outbox=None,
        retry_codes=None,
    ):
        if not callable(getattr(watcher, "tick", None)):
            raise CoreError("GIT_WATCHER_INVALID", "Watcher with tick() is required")
        if type(interval) is not int or not 5 <= interval <= 86400:
            raise CoreError("GIT_WATCHER_INVALID", "Interval must be 5..86400 seconds")
        if max_cycles is not None and (
            type(max_cycles) is not int or not 1 <= max_cycles <= 10000
        ):
            raise CoreError("GIT_WATCHER_INVALID", "max_cycles must be 1..10000")
        if type(max_backoff) is not int or not interval <= max_backoff <= 86400:
            raise CoreError("GIT_WATCHER_INVALID", "max_backoff is out of bounds")
        if not callable(sleep) or not callable(should_stop):
            raise CoreError("GIT_WATCHER_INVALID", "Scheduler callbacks are required")
        if journal is not None and not isinstance(journal, SchedulerJournal):
            raise CoreError("GIT_WATCHER_INVALID", "Typed scheduler journal required")
        if outbox is not None and not isinstance(outbox, NotificationOutbox):
            raise CoreError("GIT_WATCHER_INVALID", "Typed notification outbox required")
        if retry_codes is not None and (
            not isinstance(retry_codes, (set, frozenset))
            or len(retry_codes) > 100
            or any(
                type(code) is not str or not 1 <= len(code) <= 128
                for code in retry_codes
            )
        ):
            raise CoreError(
                "GIT_WATCHER_INVALID", "Bounded set of retry codes required"
            )
        self.watcher = watcher
        self.interval = interval
        self.max_cycles = max_cycles
        self.max_backoff = max_backoff
        self.sleep = sleep
        self.should_stop = should_stop
        self.journal = journal
        self.outbox = outbox
        self.retry_codes = None if retry_codes is None else frozenset(retry_codes)

    def _backoff_delay(self, failures):
        """Return exponential backoff without constructing an unbounded integer."""
        delay = self.interval
        remaining = min(failures, 32)
        while remaining and delay < self.max_backoff:
            delay = min(self.max_backoff, delay * 2)
            remaining -= 1
        return delay

    def run(self):
        """Run until stop/max_cycles, backing off only controlled CoreErrors."""
        events, failures, cycle = [], 0, 0
        run_id = self.journal.begin() if self.journal is not None else None
        fatal_handled = False
        primary_error = None
        try:
            while self.max_cycles is None or cycle < self.max_cycles:
                if self.should_stop():
                    break
                if self.journal is not None:
                    self.journal.mark_running(run_id, cycle, failures)
                try:
                    event = self.watcher.tick()
                    failures = 0
                except CoreError as exc:
                    if exc.code in {
                        "PROJECT_FORBIDDEN",
                        "PROJECT_NOT_FOUND",
                        "OBSERVER_PROFILE_MISMATCH",
                        "OBSERVER_BUSY",
                        "OBSERVER_JOB_FAILED",
                        "OBSERVER_JOURNAL_FULL",
                        "GIT_HISTORY_REWRITE",
                    } or (
                        self.retry_codes is not None
                        and exc.code not in self.retry_codes
                    ):
                        fatal_handled = True
                        if self.journal is not None:
                            with _preserve_primary_error(exc):
                                self.journal.record(
                                    run_id,
                                    cycle,
                                    failures,
                                    {"status": "fatal", "code": exc.code},
                                    keep_running=False,
                                )
                        if self.outbox is not None:
                            with _preserve_primary_error(exc):
                                self.outbox.enqueue(
                                    {"status": "fatal", "code": exc.code}
                                )
                        raise
                    failures += 1
                    event = {"status": "error", "code": exc.code, "attempt": failures}
                cycle += 1
                events.append(event)
                if len(events) > self.MAX_RETAINED_EVENTS:
                    del events[: -self.MAX_RETAINED_EVENTS]
                if self.journal is not None:
                    self.journal.record(run_id, cycle, failures, event)
                if self.outbox is not None:
                    self.outbox.enqueue(event)
                if self.max_cycles is not None and cycle >= self.max_cycles:
                    break
                if self.should_stop():
                    break
                self.sleep(self._backoff_delay(failures))
            return events
        except BaseException as exc:
            primary_error = exc
            if not fatal_handled:
                fatal_handled = True
                if self.journal is not None:
                    with _preserve_primary_error(exc):
                        current = self.journal.read()
                        if current is not None and current["phase"] == "running":
                            self.journal.record(
                                run_id,
                                cycle,
                                failures,
                                {"status": "fatal", "code": "GIT_WATCHER_UNEXPECTED"},
                                keep_running=False,
                            )
                if self.outbox is not None:
                    with _preserve_primary_error(exc):
                        self.outbox.enqueue(
                            {"status": "fatal", "code": "GIT_WATCHER_UNEXPECTED"}
                        )
            raise
        finally:
            with _preserve_primary_error(primary_error):
                if not fatal_handled and self.journal is not None:
                    current = self.journal.read()
                    if current is not None and current["phase"] == "running":
                        self.journal.stop(run_id, cycle, failures)
