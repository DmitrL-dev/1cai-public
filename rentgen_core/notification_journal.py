"""Durable attempt journal and bounded retry policy for notification delivery.

The journal keeps one record per outbox notification that a journaled
``deliver_outbox`` run has touched: notification ID, idempotency key, payload
digest, state, attempt count, fixed last-error code and timestamps. It never
stores the endpoint, request headers, credentials, response content or the
event body. One exclusive lock is held for a whole delivery run, so consumers
that share a journal are serialized instead of sending the same event twice.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import time

from .errors import CoreError


SCHEMA = 1
JOURNAL_KIND = "notification-delivery-v1"
MAX_BYTES = 1024 * 1024
MAX_ENTRIES = 1000
MAX_NOTIFICATION_ID = 2**63 - 1
MAX_ATTEMPTS = 100
MAX_DELAY_SECONDS = 86400
ERROR_CODES = frozenset(
    {
        "INVALID_NOTIFICATION",
        "INVALID_RESPONSE",
        "HTTP_SERVER_ERROR",
        "HTTP_REJECTED",
        "TRANSPORT_ERROR",
        "OUTCOME_UNKNOWN",
    }
)
_NAMESPACE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_ENTRY_KEYS = frozenset(
    {
        "id",
        "idempotency_key",
        "payload_sha256",
        "state",
        "attempts",
        "last_error",
        "next_attempt_at",
        "updated_at",
    }
)
_INVALID = "NOTIFICATION_DELIVERY_INVALID"
_RECOVERY = "NOTIFICATION_JOURNAL_RECOVERY_REQUIRED"
_CONFLICT = "NOTIFICATION_JOURNAL_CONFLICT"
_BUSY = "NOTIFICATION_JOURNAL_BUSY"


def valid_namespace(value):
    return type(value) is str and _NAMESPACE_RE.fullmatch(value) is not None


def idempotency_key(namespace, notification_id):
    """Stable receiver deduplication key for one notification in one queue."""
    return hashlib.sha256(
        f"rentgen-notification-v1:{namespace}:{notification_id}".encode("ascii")
    ).hexdigest()


def _bounded(value, lower, upper):
    return type(value) is int and lower <= value <= upper


def utc_now(clock=None):
    """Read the trusted host clock; a custom clock must return aware time."""
    value = datetime.now(timezone.utc) if clock is None else clock()
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise CoreError(_INVALID, "Delivery clock must return timezone-aware time")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff without jitter or ``Retry-After`` inference.

    Attempt ``n`` (1-based) that ends retryable waits
    ``min(max_delay_seconds, base_delay_seconds * 2 ** (n - 1))``. The event
    becomes terminal when a retryable outcome reaches ``max_attempts``.
    """

    max_attempts: int = 8
    base_delay_seconds: int = 30
    max_delay_seconds: int = 3600

    def __post_init__(self):
        if (
            not _bounded(self.max_attempts, 1, MAX_ATTEMPTS)
            or not _bounded(self.base_delay_seconds, 1, MAX_DELAY_SECONDS)
            or not _bounded(
                self.max_delay_seconds, self.base_delay_seconds, MAX_DELAY_SECONDS
            )
        ):
            raise CoreError(_INVALID, "Invalid retry policy")

    def delay_seconds(self, attempts):
        if not _bounded(attempts, 1, MAX_ATTEMPTS):
            raise CoreError(_INVALID, "Attempt number is out of bounds")
        # 2**17 already exceeds the largest allowed delay.
        return min(
            self.max_delay_seconds,
            self.base_delay_seconds * 2 ** min(attempts - 1, 17),
        )


class AttemptState(str, Enum):
    PENDING = "pending"
    SENDING = "sending"
    ACCEPTED = "accepted"
    TERMINAL = "terminal"


@dataclass(frozen=True)
class AttemptRecord:
    """Private journal view: delivery metadata only, never content or secrets."""

    notification_id: int
    idempotency_key: str
    state: AttemptState
    attempts: int
    last_error: str | None
    next_attempt_at: str | None
    updated_at: str


def _time(value):
    if type(value) is not str or not 1 <= len(value) <= 64:
        raise ValueError("Invalid journal time")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Journal time needs timezone")
    return parsed


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate journal key")
        result[key] = value
    return result


def _fsync_directory(path):
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


class DeliveryJournal:
    """Atomic local attempt journal bound to one adapter namespace.

    Create one journal per outbox generation next to the outbox, with the same
    stable namespace as the ``WebhookAdapter``. Pass it to ``deliver_outbox``.
    """

    def __init__(self, path, *, namespace):
        if not valid_namespace(namespace):
            raise CoreError(_INVALID, "Invalid journal namespace")
        self.namespace = namespace
        self.path = Path(path).resolve()
        if self.path.exists() and not self.path.is_file():
            raise CoreError(_INVALID, "Journal file required")
        if not self.path.parent.exists() or not self.path.parent.is_dir():
            raise CoreError(_INVALID, "Journal parent required")

    def __repr__(self):
        return f"DeliveryJournal(namespace={self.namespace!r})"

    @contextmanager
    def _locked(self):
        """Hold one non-blocking OS lock; a second holder fails as busy."""
        lock_path = self.path.with_name(self.path.name + ".lock")
        if lock_path.is_symlink() or (lock_path.exists() and not lock_path.is_file()):
            raise CoreError(_RECOVERY, "Journal lock file required")
        try:
            descriptor = os.open(
                lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o600
            )
            stream = os.fdopen(descriptor, "r+b")
        except OSError as exc:
            raise CoreError(_RECOVERY, "Journal lock could not be opened") from exc
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
                raise CoreError(_BUSY, "Another delivery run holds the journal")
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

    def _temporary(self):
        return self.path.with_name(self.path.name + ".tmp")

    def _read(self):
        if self._temporary().exists():
            raise CoreError(_RECOVERY, "Interrupted journal write needs recovery")
        if not self.path.exists():
            return {
                "schema": SCHEMA,
                "journal": JOURNAL_KIND,
                "namespace": self.namespace,
                "high_water": 0,
                "entries": [],
            }
        try:
            with self.path.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise CoreError(_RECOVERY, "Journal is too large")
            document = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
            self._validate(document)
        except CoreError:
            raise
        except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
            raise CoreError(_RECOVERY, "Journal is unreadable or malformed") from exc
        if document["namespace"] != self.namespace:
            raise CoreError(_CONFLICT, "Journal belongs to another namespace")
        return document

    @staticmethod
    def _validate(document):
        if (
            type(document) is not dict
            or set(document)
            != {"schema", "journal", "namespace", "high_water", "entries"}
            or document["schema"] != SCHEMA
            or type(document["schema"]) is not int
            or document["journal"] != JOURNAL_KIND
            or not valid_namespace(document["namespace"])
            or not _bounded(document["high_water"], 0, MAX_NOTIFICATION_ID)
            or type(document["entries"]) is not list
            or len(document["entries"]) > MAX_ENTRIES
        ):
            raise ValueError("Malformed journal")
        previous = 0
        for entry in document["entries"]:
            if (
                type(entry) is not dict
                or set(entry) != _ENTRY_KEYS
                or not _bounded(entry["id"], previous + 1, MAX_NOTIFICATION_ID)
                or entry["idempotency_key"]
                != idempotency_key(document["namespace"], entry["id"])
                or type(entry["payload_sha256"]) is not str
                or _DIGEST_RE.fullmatch(entry["payload_sha256"]) is None
                or entry["state"] not in {state.value for state in AttemptState}
                or not _bounded(entry["attempts"], 0, MAX_ATTEMPTS)
                or (
                    entry["last_error"] is not None
                    and entry["last_error"] not in ERROR_CODES
                )
                or (entry["state"] == AttemptState.PENDING.value)
                != (entry["next_attempt_at"] is not None)
                or (entry["attempts"] == 0 and entry["state"] != "pending")
            ):
                raise ValueError("Malformed journal entry")
            _time(entry["updated_at"])
            if entry["next_attempt_at"] is not None:
                _time(entry["next_attempt_at"])
            previous = entry["id"]

    def _write(self, document):
        try:
            self._validate(document)
            raw = json.dumps(
                document,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("ascii")
        except (TypeError, ValueError, RecursionError) as exc:
            raise CoreError(_INVALID, "Journal state is invalid") from exc
        if len(raw) > MAX_BYTES:
            raise CoreError(_INVALID, "Journal size limit exceeded")
        temporary = self._temporary()
        if temporary.exists():
            raise CoreError(_RECOVERY, "Interrupted journal write needs recovery")
        try:
            with temporary.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            raise CoreError(_RECOVERY, "Journal write failed") from exc
        _fsync_directory(self.path.parent)

    @staticmethod
    def _record(entry):
        return AttemptRecord(
            notification_id=entry["id"],
            idempotency_key=entry["idempotency_key"],
            state=AttemptState(entry["state"]),
            attempts=entry["attempts"],
            last_error=entry["last_error"],
            next_attempt_at=entry["next_attempt_at"],
            updated_at=entry["updated_at"],
        )

    def records(self):
        """Return the current private records in notification-ID order."""
        with self._locked():
            return tuple(self._record(entry) for entry in self._read()["entries"])

    def rearm(self, notification_id, *, clock=None):
        """Operator decision: give one terminal event a fresh attempt budget.

        The idempotency key and payload binding stay unchanged; the next
        journaled run still checks authorization before sending.
        """
        if not _bounded(notification_id, 1, MAX_NOTIFICATION_ID):
            raise CoreError(_INVALID, "Invalid notification id")
        with self._locked():
            document = self._read()
            entry = next(
                (item for item in document["entries"] if item["id"] == notification_id),
                None,
            )
            if entry is None or entry["state"] != AttemptState.TERMINAL.value:
                raise CoreError(_INVALID, "Only a terminal journal entry can be rearmed")
            now = utc_now(clock).isoformat()
            entry.update(
                state=AttemptState.PENDING.value,
                attempts=0,
                next_attempt_at=now,
                updated_at=now,
            )
            self._write(document)
            return self._record(entry)

    @contextmanager
    def _session(self, namespace):
        """Lock and load the journal for one delivery run."""
        if namespace != self.namespace:
            raise CoreError(_CONFLICT, "Adapter namespace does not match journal")
        with self._locked():
            yield _Session(self, self._read())


class _Session:
    """Write-through transitions while the journal lock is held."""

    def __init__(self, journal, document):
        self._journal = journal
        self._document = document
        self._entries = {entry["id"]: entry for entry in document["entries"]}

    def _persist(self):
        self._document["entries"] = [
            self._entries[key] for key in sorted(self._entries)
        ]
        self._journal._write(self._document)

    def entry(self, notification_id):
        entry = self._entries.get(notification_id)
        return None if entry is None else dict(entry)

    def reconcile(self, digests, now, policy):
        """Fail on replayed or changed events, then prune and recover entries.

        ``digests`` maps every pending outbox ID to its canonical payload
        SHA-256. Conflicts raise before any write. Entries for events no
        longer in the outbox are dropped; an interrupted ``sending`` attempt
        is counted with ``OUTCOME_UNKNOWN`` and scheduled by the policy.
        """
        high_water = self._document["high_water"]
        for notification_id, digest in digests.items():
            entry = self._entries.get(notification_id)
            if entry is None and notification_id <= high_water:
                raise CoreError(
                    _CONFLICT,
                    "Outbox presents an already delivered notification id",
                )
            if entry is not None and entry["payload_sha256"] != digest:
                raise CoreError(
                    _CONFLICT, "Outbox notification differs from its journaled attempt"
                )
        changed = False
        for notification_id in [key for key in self._entries if key not in digests]:
            del self._entries[notification_id]
            changed = True
        stamp = now.isoformat()
        for entry in self._entries.values():
            if entry["state"] == AttemptState.SENDING.value:
                entry["last_error"] = "OUTCOME_UNKNOWN"
                changed = True
                if entry["attempts"] >= policy.max_attempts:
                    entry.update(
                        state=AttemptState.TERMINAL.value,
                        next_attempt_at=None,
                        updated_at=stamp,
                    )
                else:
                    started = _time(entry["updated_at"])
                    entry.update(
                        state=AttemptState.PENDING.value,
                        next_attempt_at=(
                            started
                            + timedelta(seconds=policy.delay_seconds(entry["attempts"]))
                        )
                        .astimezone(timezone.utc)
                        .isoformat(),
                        updated_at=stamp,
                    )
            elif (
                entry["state"] == AttemptState.PENDING.value
                and entry["attempts"] >= policy.max_attempts
            ):
                # A lowered policy never grants attempts beyond its budget.
                entry.update(
                    state=AttemptState.TERMINAL.value,
                    next_attempt_at=None,
                    updated_at=stamp,
                )
                changed = True
        if changed:
            self._persist()

    @staticmethod
    def due(entry, now, policy):
        """Pending entry is due at its time, or at once after a clock rollback."""
        next_attempt = _time(entry["next_attempt_at"])
        return now >= next_attempt or next_attempt - now > timedelta(
            seconds=policy.max_delay_seconds
        )

    def begin(self, notification_id, key, digest, now):
        """Durably count one attempt before the request leaves the process."""
        entry = self._entries.get(notification_id)
        attempts = 1 if entry is None else entry["attempts"] + 1
        if attempts > MAX_ATTEMPTS:
            raise CoreError(_RECOVERY, "Journal attempt counter exhausted")
        self._entries[notification_id] = {
            "id": notification_id,
            "idempotency_key": key,
            "payload_sha256": digest,
            "state": AttemptState.SENDING.value,
            "attempts": attempts,
            "last_error": None if entry is None else entry["last_error"],
            "next_attempt_at": None,
            "updated_at": now.isoformat(),
        }
        self._persist()
        return attempts

    def accepted(self, notification_id, now):
        entry = self._entries[notification_id]
        entry.update(
            state=AttemptState.ACCEPTED.value,
            next_attempt_at=None,
            updated_at=now.isoformat(),
        )
        self._document["high_water"] = max(
            self._document["high_water"], notification_id
        )
        self._persist()

    def retry(self, notification_id, code, next_attempt, now):
        entry = self._entries[notification_id]
        entry.update(
            state=AttemptState.PENDING.value,
            last_error=code,
            next_attempt_at=next_attempt.isoformat(),
            updated_at=now.isoformat(),
        )
        self._persist()

    def terminal(self, notification_id, code, now):
        entry = self._entries[notification_id]
        entry.update(
            state=AttemptState.TERMINAL.value,
            last_error=code,
            next_attempt_at=None,
            updated_at=now.isoformat(),
        )
        self._persist()

    def forget(self, notification_id):
        """Drop an acknowledged entry; ``high_water`` still blocks a replay."""
        del self._entries[notification_id]
        self._persist()
