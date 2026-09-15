"""Durable, idempotent receiver core for the notification outbox."""

from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Mapping

from .errors import CoreError
from .notification_delivery import _payload


SCHEMA = 1
MAX_BODY_BYTES = 1_048_576
MAX_RECEIPTS = 100_000
MAX_STATE_BYTES = 64 * 1024**2
_KEY = re.compile(r"[0-9a-f]{64}\Z")
_HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9._~+/-]{1,4096}=*\Z")
_TABLES = {
    "receiver_meta": "CREATE TABLE receiver_meta (schema INTEGER NOT NULL)",
    "notification_receipts": "CREATE TABLE notification_receipts ("
    "idempotency_key TEXT PRIMARY KEY, "
    "payload_digest TEXT NOT NULL, "
    "received_at TEXT NOT NULL)",
}


class ReceiverStatus(str, Enum):
    """Outcome classes understood by an HTTP adapter."""

    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ReceiverResult:
    """Safe receipt; it never carries the bearer token or request body."""

    status: ReceiverStatus
    code: str
    http_status: int
    idempotency_key: str | None = None
    payload_digest: str | None = None


def _error(code, message):
    return CoreError(code, message)


def _bounded_int(value, upper):
    return type(value) is int and 1 <= value <= upper


def _headers(headers):
    if not isinstance(headers, Mapping) or len(headers) > 64:
        return None
    result = {}
    for key, value in headers.items():
        if (
            type(key) is not str
            or type(value) is not str
            or _HEADER_NAME.fullmatch(key) is None
            or not 1 <= len(value) <= 8192
            or any(ord(char) < 32 or ord(char) >= 127 for char in key + value)
        ):
            return None
        lowered = key.lower()
        if lowered in result:
            return None
        result[lowered] = value
    return result


def _content_type(value):
    if type(value) is not str:
        return False
    pieces = [piece.strip() for piece in value.split(";")]
    if not pieces or pieces[0].lower() != "application/json":
        return False
    if len(pieces) == 1:
        return True
    return len(pieces) == 2 and pieces[1].lower() == "charset=utf-8"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON member")
        result[key] = value
    return result


class NotificationReceiver:
    """Persist one bounded notification digest per idempotency key.

    The class contains the receiver's trust boundary but does not open a socket.
    A host may map ``ReceiverResult.http_status`` to its HTTP response. SQLite's
    unique key and a write transaction make concurrent retries idempotent.
    """

    MAX_BODY_BYTES = MAX_BODY_BYTES
    MAX_RECEIPTS = MAX_RECEIPTS

    def __init__(self, path, *, bearer_token, max_body_bytes=MAX_BODY_BYTES):
        self.path = Path(path) if isinstance(path, (str, Path)) else None
        if (
            self.path is None
            or not self.path.is_absolute()
            or ".." in self.path.parts
            or self.path.name in {"", ".", ".."}
            or "\x00" in str(self.path)
            or (
                os.name == "nt"
                and (
                    self.path.drive.startswith("\\\\")
                    or any(
                        ":" in part
                        or part.endswith((".", " "))
                        or Path(part).is_reserved()
                        for part in self.path.parts[1:]
                    )
                )
            )
            or type(bearer_token) is not str
            or len(bearer_token) > 4096
            or _TOKEN.fullmatch(bearer_token) is None
            or not _bounded_int(max_body_bytes, MAX_BODY_BYTES)
        ):
            raise _error(
                "NOTIFICATION_RECEIVER_INVALID", "Invalid receiver configuration"
            )
        self.path = self.path.absolute()
        self._bearer_token = bearer_token
        self._max_body_bytes = max_body_bytes
        self._initialized = False

    def _safe_path(self, *, required=False):
        try:
            for ancestor in self.path.parents:
                info = ancestor.lstat()
                if not stat.S_ISDIR(info.st_mode) or (
                    getattr(info, "st_file_attributes", 0) & 0x400
                ):
                    raise ValueError
            for suffix in ("", "-journal", "-wal", "-shm"):
                candidate = Path(str(self.path) + suffix)
                try:
                    info = candidate.lstat()
                except FileNotFoundError:
                    if required and not suffix:
                        raise
                    continue
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or getattr(info, "st_file_attributes", 0) & 0x400
                ):
                    raise ValueError
                if info.st_size > MAX_STATE_BYTES:
                    raise _error(
                        "NOTIFICATION_RECEIVER_LIMIT",
                        "Receiver state file size limit is exceeded",
                    )
        except (OSError, ValueError):
            raise _error(
                "NOTIFICATION_RECEIVER_CONFLICT", "Receiver database path is unsafe"
            ) from None

    @contextmanager
    def _connection(self):
        with closing(
            sqlite3.connect(
                self.path.as_uri() + "?mode=rw",
                uri=True,
                timeout=5,
                isolation_level=None,
            )
        ) as connection:
            # Bound malformed database values before sqlite3 materializes them.
            connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 8192)
            connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 8192)
            connection.execute("PRAGMA trusted_schema=OFF")
            if connection.execute("PRAGMA journal_mode").fetchone() != ("delete",):
                raise _error(
                    "NOTIFICATION_RECEIVER_RECOVERY_REQUIRED",
                    "Receiver database journal mode is invalid",
                )
            # EXTRA additionally syncs the directory after DELETE journal commits.
            connection.execute("PRAGMA synchronous=EXTRA")
            yield connection

    @staticmethod
    def _schema_ok(connection):
        try:
            objects = connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master LIMIT 4"
            ).fetchall()
            expected = {("table", name, name, sql) for name, sql in _TABLES.items()} | {
                (
                    "index",
                    "sqlite_autoindex_notification_receipts_1",
                    "notification_receipts",
                    None,
                )
            }
            actual = {
                (
                    kind,
                    name,
                    table,
                    None
                    if sql is None
                    else " ".join(sql.split()).replace("( ", "(").replace(" )", ")"),
                )
                for kind, name, table, sql in objects
            }
            if actual != expected:
                return False
            meta = connection.execute(
                "SELECT schema FROM receiver_meta LIMIT 2"
            ).fetchall()
        except sqlite3.Error:
            return False
        return meta == [(SCHEMA,)] and type(meta[0][0]) is int

    def _validate_state(self, connection):
        if not self._schema_ok(connection):
            raise _error(
                "NOTIFICATION_RECEIVER_RECOVERY_REQUIRED",
                "Receiver database schema is invalid",
            )
        count = connection.execute(
            "SELECT COUNT(*) FROM notification_receipts"
        ).fetchone()[0]
        if count > self.MAX_RECEIPTS:
            raise _error(
                "NOTIFICATION_RECEIVER_LIMIT", "Receiver receipt limit is exceeded"
            )
        for key, digest, timestamp in connection.execute(
            "SELECT idempotency_key, payload_digest, received_at "
            "FROM notification_receipts"
        ):
            valid = (
                type(key) is str
                and _KEY.fullmatch(key) is not None
                and type(digest) is str
                and _KEY.fullmatch(digest) is not None
                and type(timestamp) is str
                and 1 <= len(timestamp) <= 40
            )
            if valid:
                try:
                    instant = datetime.fromisoformat(timestamp)
                    valid = (
                        instant.tzinfo is not None
                        and instant.utcoffset() == timezone.utc.utcoffset(instant)
                    )
                except ValueError:
                    valid = False
            if not valid:
                raise _error(
                    "NOTIFICATION_RECEIVER_RECOVERY_REQUIRED",
                    "Receiver receipt is invalid",
                )
        return count

    def initialize(self):
        """Create or validate the owned database; malformed state fails closed."""
        self._initialized = False
        self._safe_path()
        created = False
        if not self.path.exists():
            try:
                with self.path.open("xb") as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
                created = True
            except FileExistsError:
                pass
            except OSError as exc:
                raise _error(
                    "NOTIFICATION_RECEIVER_UNAVAILABLE",
                    "Receiver database could not be created",
                ) from exc
        try:
            self._safe_path(required=True)
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if created:
                    for sql in _TABLES.values():
                        connection.execute(sql)
                    connection.execute(
                        "INSERT INTO receiver_meta(schema) VALUES (?)", (SCHEMA,)
                    )
                self._validate_state(connection)
                connection.commit()
        except CoreError:
            raise
        except (OSError, sqlite3.Error) as exc:
            busy = getattr(exc, "sqlite_errorcode", 0) & 0xFF in (
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
            )
            raise _error(
                "NOTIFICATION_RECEIVER_UNAVAILABLE"
                if busy
                else "NOTIFICATION_RECEIVER_RECOVERY_REQUIRED",
                "Receiver database cannot be validated",
            ) from exc
        self._initialized = True

    def _ready(self):
        if not self._initialized:
            raise _error(
                "NOTIFICATION_RECEIVER_NOT_INITIALIZED",
                "Receiver database is not initialized",
            )
        self._safe_path(required=True)

    @staticmethod
    def _rejected(code, http_status):
        return ReceiverResult(ReceiverStatus.REJECTED, code, http_status)

    def _request(self, headers, body):
        normalized = _headers(headers)
        if normalized is None:
            return self._rejected("INVALID_REQUEST", 400), None, None
        authorization = normalized.get("authorization")
        if type(authorization) is not str or not hmac.compare_digest(
            authorization, "Bearer " + self._bearer_token
        ):
            return self._rejected("UNAUTHORIZED", 401), None, None
        key = normalized.get("idempotency-key")
        if type(key) is not str or _KEY.fullmatch(key) is None:
            return self._rejected("INVALID_REQUEST", 400), None, None
        if not _content_type(normalized.get("content-type")):
            return self._rejected("INVALID_REQUEST", 400), None, None
        if type(body) is not bytes:
            return self._rejected("INVALID_REQUEST", 400), None, None
        if len(body) > self._max_body_bytes:
            return self._rejected("PAYLOAD_TOO_LARGE", 413), None, None
        try:
            value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
            canonical = _payload(value, self._max_body_bytes)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
            OverflowError,
            RecursionError,
        ):
            return self._rejected("INVALID_REQUEST", 400), None, None
        return None, key, hashlib.sha256(canonical).hexdigest()

    def accept(self, headers, body):
        """Validate and durably accept one request without exposing its payload."""
        self._ready()
        rejected, key, digest = self._request(headers, body)
        if rejected is not None:
            return rejected
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                count = self._validate_state(connection)
                row = connection.execute(
                    "SELECT payload_digest FROM notification_receipts WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                if row is not None:
                    connection.commit()
                    if row[0] == digest:
                        return ReceiverResult(
                            ReceiverStatus.DUPLICATE,
                            "DUPLICATE_NOTIFICATION",
                            204,
                            key,
                            digest,
                        )
                    return ReceiverResult(
                        ReceiverStatus.CONFLICT,
                        "IDEMPOTENCY_CONFLICT",
                        409,
                        key,
                        digest,
                    )
                if count >= self.MAX_RECEIPTS:
                    raise _error(
                        "NOTIFICATION_RECEIVER_LIMIT",
                        "Receiver receipt limit is exceeded",
                    )
                connection.execute(
                    "INSERT INTO notification_receipts VALUES (?, ?, ?)",
                    (key, digest, datetime.now(timezone.utc).isoformat()),
                )
                connection.commit()
                return ReceiverResult(
                    ReceiverStatus.ACCEPTED,
                    "NOTIFICATION_ACCEPTED",
                    204,
                    key,
                    digest,
                )
        except CoreError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise _error(
                "NOTIFICATION_RECEIVER_UNAVAILABLE",
                "Receiver state is unavailable",
            ) from exc

    def count(self):
        """Return the bounded number of durable receipts for local diagnostics."""
        self._ready()
        try:
            with self._connection() as connection:
                connection.execute("BEGIN")
                count = self._validate_state(connection)
        except CoreError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise _error(
                "NOTIFICATION_RECEIVER_UNAVAILABLE",
                "Receiver state is unavailable",
            ) from exc
        return count
