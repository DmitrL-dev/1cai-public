"""Durable, context-bound storage for owner-report evidence."""

from datetime import datetime, timezone
from contextlib import contextmanager
import heapq
import json
import math
import os
from pathlib import Path
import stat
import time
from uuid import UUID, uuid4

from ._windows_source_tree import pinned_directory
from .platform_filesystem import open_directory, read_retained
from .edt_profiles import parse_json
from .errors import CoreError
from .manifests import sha256
from .owner_report import RuntimeMetric, RuntimeMetricReport, _hash, _timestamp
from .context import validate_project_id


SCHEMA = 1
MAX_RECORD = 2 * 1024**2
MAX_REPORTS = 1000


def _require(condition, code, message):
    if not condition:
        raise CoreError(code, message)


def _seal(value):
    return {**value, "receipt_id": sha256(_canonical(value))}


def _canonical(value):
    try:
        _json_domain(value)
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CoreError(
            "OWNER_REPORT_STORE_INVALID", "Owner-report values are not JSON"
        ) from exc


def _json_domain(value):
    if value is None or type(value) is bool or isinstance(value, str):
        if isinstance(value, str):
            value.encode("utf-8")
        return
    if type(value) is int:
        _require(
            -(2**63) <= value < 2**63,
            "OWNER_REPORT_STORE_INVALID",
            "Owner-report integer is out of bounds",
        )
        return
    if type(value) is float:
        _require(
            math.isfinite(value) and abs(value) <= 10**15,
            "OWNER_REPORT_STORE_INVALID",
            "Owner-report number is invalid",
        )
        return
    if isinstance(value, list):
        for item in value:
            _json_domain(item)
        return
    if isinstance(value, dict) and all(type(key) is str for key in value):
        for key, item in value.items():
            _json_domain(key)
            _json_domain(item)
        return
    raise CoreError(
        "OWNER_REPORT_STORE_INVALID", "Owner-report value is outside JSON domain"
    )


def _report(value):
    _require(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "project_id",
            "snapshot_id",
            "generated_at",
            "quality",
            "business_metrics",
        }
        and value["schema"] == 1
        and isinstance(value["quality"], dict)
        and isinstance(value["business_metrics"], dict),
        "OWNER_REPORT_STORE_INVALID",
        "Owner report schema is invalid",
    )
    try:
        validate_project_id(value["project_id"])
        _hash(value["snapshot_id"], "snapshot_id", snapshot=True)
        _timestamp(value["generated_at"], "generated_at")
        business = value["business_metrics"]
        _require(
            business.get("status") in {"available", "incomplete", "not_available"},
            "OWNER_REPORT_STORE_INVALID",
            "Owner-report business status is invalid",
        )
        if business["status"] in {"available", "incomplete"}:
            _require(
                set(business) == {"status", "reason", "source", "metrics"}
                and isinstance(business["source"], dict)
                and isinstance(business["metrics"], list),
                "OWNER_REPORT_STORE_INVALID",
                "Owner-report runtime evidence is invalid",
            )
            source = business["source"]
            _require(
                set(source)
                == {
                    "project_id",
                    "snapshot_id",
                    "commit",
                    "adapter_id",
                    "source_ref",
                    "source_digest",
                    "period_start",
                    "period_end",
                    "generated_at",
                }
                and source["project_id"] == value["project_id"]
                and source["snapshot_id"] == value["snapshot_id"],
                "OWNER_REPORT_STORE_CONTEXT",
                "Nested runtime context does not match owner report",
            )
            _require(
                (business["status"] == "available" and business["reason"] is None)
                or (
                    business["status"] == "incomplete"
                    and business["reason"] == "runtime_report_incomplete"
                    and business["metrics"] == []
                ),
                "OWNER_REPORT_STORE_INVALID",
                "Owner-report runtime completeness is invalid",
            )
            metrics = tuple(RuntimeMetric(**item) for item in business["metrics"])
            RuntimeMetricReport(
                project_id=source["project_id"],
                snapshot_id=source["snapshot_id"],
                commit=source["commit"],
                adapter_id=source["adapter_id"],
                source_ref=source["source_ref"],
                source_digest=source["source_digest"],
                period_start=source["period_start"],
                period_end=source["period_end"],
                generated_at=source["generated_at"],
                complete=business["status"] == "available",
                metrics=metrics,
            )
        else:
            _require(
                set(business) == {"status", "reason"}
                and isinstance(business["reason"], str),
                "OWNER_REPORT_STORE_INVALID",
                "Owner-report unavailable status is invalid",
            )
        _require(
            len(_canonical(value)) <= MAX_RECORD,
            "OWNER_REPORT_STORE_LIMIT",
            "Owner report is too large",
        )
    except (CoreError, TypeError, ValueError, RecursionError) as exc:
        if isinstance(exc, CoreError) and exc.code.startswith("OWNER_REPORT_STORE_"):
            raise
        raise CoreError(
            "OWNER_REPORT_STORE_INVALID", "Owner report values are invalid"
        ) from exc
    return value


def _report_id(value):
    _require(type(value) is str, "OWNER_REPORT_STORE_INVALID", "Report ID is required")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise CoreError("OWNER_REPORT_STORE_INVALID", "Invalid report ID") from exc
    _require(
        str(parsed) == value,
        "OWNER_REPORT_STORE_INVALID",
        "Report ID must be canonical",
    )
    return value


class OwnerReportStore:
    """Store immutable owner reports under one explicitly owned directory."""

    MAX_REPORTS = MAX_REPORTS

    def __init__(self, root):
        self.root = Path(root) if isinstance(root, (str, Path)) else None
        _require(
            self.root is not None
            and self.root.is_absolute()
            and ".." not in self.root.parts,
            "OWNER_REPORT_STORE_INVALID",
            "Absolute owner-report store path is required",
        )
        if self.root.is_symlink():
            raise CoreError(
                "OWNER_REPORT_STORE_CONFLICT", "Owner-report store path is unsafe"
            )
        self.root = self.root.absolute()
        self.reports = self.root / "reports"

    def initialize(self):
        if os.name == "posix":
            return self._initialize_posix()
        _require(
            self.root.parent.is_dir(),
            "OWNER_REPORT_STORE_NOT_FOUND",
            "Owner-report store parent is absent",
        )
        # Pin the parent before creating the root.  A lexical path check alone
        # would permit a junction to be installed between the check and mkdir.
        with pinned_directory(self.root.parent):
            if self.root.is_symlink() or (
                self.root.exists() and not self.root.is_dir()
            ):
                raise CoreError(
                    "OWNER_REPORT_STORE_CONFLICT",
                    "Owner-report store is not a directory",
                )
            if not self.root.exists():
                try:
                    self.root.mkdir()
                except FileExistsError:
                    pass
            if self.root.is_symlink() or not self._safe_directory(self.root):
                raise CoreError(
                    "OWNER_REPORT_STORE_CONFLICT",
                    "Owner-report store is not a directory",
                )
            with pinned_directory(self.root):
                if self.reports.is_symlink() or (
                    self.reports.exists() and not self.reports.is_dir()
                ):
                    raise CoreError(
                        "OWNER_REPORT_STORE_CONFLICT",
                        "Owner-report reports path is unsafe",
                    )
                if not self.reports.exists():
                    try:
                        self.reports.mkdir()
                    except FileExistsError:
                        pass
                if not self._safe_directory(self.reports):
                    raise CoreError(
                        "OWNER_REPORT_STORE_CONFLICT",
                        "Owner-report reports path is unsafe",
                    )
                self._initialize_lock()

    def _initialize_posix(self):
        """Create only owned children of verified directory capabilities."""
        try:
            with open_directory(self.root.parent) as parent:
                with parent.child(self.root.name, create=True, private=True) as root:
                    with root.child("reports", create=True, private=True):
                        pass
                    try:
                        with root.create_file("store.lock") as stream:
                            stream.write(b"0")
                    except FileExistsError:
                        pass
                    if root.read("store.lock", 1) != b"0":
                        raise CoreError(
                            "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                            "Owner-report lock file is incomplete",
                        )
        except FileNotFoundError as exc:
            raise CoreError("OWNER_REPORT_STORE_NOT_FOUND", "Owner-report store parent is absent") from exc
        except (OSError, CoreError) as exc:
            if isinstance(exc, CoreError) and exc.code.startswith("OWNER_REPORT_STORE_"):
                raise
            raise CoreError("OWNER_REPORT_STORE_CONFLICT", "Owner-report store path is unsafe") from exc

    def _initialize_lock(self):
        lock_path = self.root / "store.lock"
        if lock_path.exists() and not self._regular_leaf(lock_path):
            raise CoreError(
                "OWNER_REPORT_STORE_CONFLICT", "Owner-report lock path is unsafe"
            )
        if not lock_path.exists():
            try:
                with lock_path.open("xb") as stream:
                    stream.write(b"0")
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                pass
        if not self._regular_leaf(lock_path) or lock_path.stat().st_size < 1:
            raise CoreError(
                "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                "Owner-report lock file is incomplete",
            )

    @staticmethod
    def _regular_leaf(path):
        try:
            info = path.lstat()
        except OSError as exc:
            raise CoreError(
                "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                "Owner-report path is unreadable",
            ) from exc
        return (
            stat.S_ISREG(info.st_mode)
            and not bool(getattr(info, "st_file_attributes", 0) & 0x400)
            and getattr(info, "st_nlink", 1) == 1
        )

    @staticmethod
    def _safe_directory(path):
        try:
            info = path.lstat()
        except OSError as exc:
            raise CoreError(
                "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                "Owner-report path is unreadable",
            ) from exc
        return stat.S_ISDIR(info.st_mode) and not bool(
            getattr(info, "st_file_attributes", 0) & 0x400
        )

    @contextmanager
    def _owned_root(self):
        """Pin root and reports for the complete store operation."""
        try:
            if os.name == "posix":
                with open_directory(self.root, private=True) as root:
                    with root.child("reports", private=True) as reports:
                        yield root, reports
                return
            with pinned_directory(self.root):
                if not self._safe_directory(self.reports):
                    raise CoreError(
                        "OWNER_REPORT_STORE_CONFLICT",
                        "Owner-report reports path is a reparse point",
                    )
                # A reports-directory pin blocks replacement by a junction on
                # Windows.  Direct exclusive file creation remains compatible
                # with this read-only directory handle.
                with pinned_directory(self.reports):
                    yield None
        except CoreError as exc:
            if exc.code in {"SOURCE_PATH_UNSAFE", "SNAPSHOT_CORRUPT"}:
                raise CoreError(
                    "OWNER_REPORT_STORE_CONFLICT",
                    "Owner-report store path is unsafe",
                ) from exc
            raise
        except OSError as exc:
            raise CoreError(
                "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                "Owner-report store path is unavailable",
            ) from exc

    def _ready(self):
        if os.name == "posix":
            # The held-capability entry below performs the no-follow check.
            # Do not reopen reports by pathname before that scope.
            return
        _require(
            self.reports.is_dir() and not self.reports.is_symlink(),
            "OWNER_REPORT_STORE_NOT_FOUND",
            "Owner-report store is not initialized",
        )

    @contextmanager
    def _locked(self, directories=None):
        if directories is not None:
            with self._posix_locked(directories[0]):
                yield
            return
        lock_path = self.root / "store.lock"
        if lock_path.exists() and not self._regular_leaf(lock_path):
            raise CoreError(
                "OWNER_REPORT_STORE_CONFLICT", "Owner-report lock path is unsafe"
            )
        try:
            descriptor = os.open(
                lock_path,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0),
                0o600,
            )
            stream = os.fdopen(descriptor, "r+b")
        except OSError as exc:
            raise CoreError(
                "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                "Owner-report lock could not be opened",
            ) from exc
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt

                if os.fstat(stream.fileno()).st_size < 1:
                    raise CoreError(
                        "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                        "Owner-report lock file is incomplete",
                    )
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
                    "OWNER_REPORT_STORE_BUSY",
                    "Another owner-report store operation is active",
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

    @contextmanager
    def _posix_locked(self, root):
        """Cooperative store serialization; flock is not a hostile-writer lease."""
        import fcntl

        with root.file("store.lock") as stream:
            if stream.read(2) != b"0":
                raise CoreError("OWNER_REPORT_STORE_RECOVERY_REQUIRED", "Owner-report lock file is incomplete")
            acquired = False
            try:
                for _ in range(20):
                    try:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                        break
                    except BlockingIOError:
                        time.sleep(0.01)
                if not acquired:
                    raise CoreError("OWNER_REPORT_STORE_BUSY", "Another owner-report store operation is active")
                root.verify()
                yield
            except BaseException:
                if acquired:
                    try:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                raise
            else:
                if acquired:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _entries(self, directories=None, *, validate=False):
        self._ready()
        try:
            if directories is None:
                entries = list(self.reports.iterdir())
            else:
                entries = []
                for name in directories[1].names():
                    entries.append(self.reports / name)
                    if len(entries) > self.MAX_REPORTS:
                        break
        except OSError as exc:
            raise CoreError(
                "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                "Owner-report store is unreadable",
            ) from exc
        _require(
            len(entries) <= self.MAX_REPORTS,
            "OWNER_REPORT_STORE_LIMIT",
            "Owner-report store limit reached",
        )
        result = []
        for entry in entries:
            if entry.name.endswith(".tmp"):
                raise CoreError(
                    "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                    "Owner-report temporary file requires recovery",
                )
            valid = (
                stat.S_ISREG(directories[1].stat(entry.name).st_mode)
                if directories is not None else not entry.is_symlink() and entry.is_file()
            )
            if not valid or entry.suffix != ".json":
                raise CoreError(
                    "OWNER_REPORT_STORE_CONFLICT",
                    "Owner-report store contains foreign files",
                )
            _report_id(entry.stem)
            result.append(entry)
        result = sorted(result, key=lambda path: path.name)
        if validate:
            for entry in result:
                self._read(entry, directories)
        return result

    def _read(self, path, directories=None):
        try:
            raw = (
                read_retained(path, MAX_RECORD) if directories is None
                else directories[1].read(path.name, MAX_RECORD)
            )
            value = parse_json(raw)
            valid = (
                type(value) is dict
                and set(value)
                == {
                    "schema",
                    "report_id",
                    "project_id",
                    "snapshot_id",
                    "status",
                    "created_at",
                    "report",
                    "receipt_id",
                }
                and value["schema"] == SCHEMA
                and value["status"] == "stored"
                and value["report_id"] == path.stem
                and isinstance(value["report"], dict)
                and value["project_id"] == value["report"]["project_id"]
                and value["snapshot_id"] == value["report"]["snapshot_id"]
                and _seal(
                    {key: item for key, item in value.items() if key != "receipt_id"}
                )
                == value
                and _canonical(value) == raw
            )
            _require(
                valid,
                "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                "Owner-report receipt hash or schema differs",
            )
            _report_id(value["report_id"])
            _timestamp(value["created_at"], "created_at")
            _report(value["report"])
            return value
        except CoreError as exc:
            if exc.code.startswith("OWNER_REPORT_STORE_"):
                raise
            raise CoreError(
                "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                "Owner-report receipt is invalid",
            ) from exc
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            UnicodeError,
            RecursionError,
        ) as exc:
            raise CoreError(
                "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                "Owner-report receipt is unreadable",
            ) from exc

    def save(self, report, *, report_id=None, authorize):
        if not callable(authorize):
            raise CoreError(
                "OWNER_REPORT_STORE_AUTHORIZATION",
                "Owner-report authorization is required",
            )
        self._ready()
        authorize()
        report = _report(report)
        with self._owned_root() as directories, self._locked(directories):
            entries = self._entries(directories, validate=True)
            report_id = str(uuid4()) if report_id is None else _report_id(report_id)
            path = self.reports / f"{report_id}.json"
            if directories is None and path.is_symlink():
                raise CoreError(
                    "OWNER_REPORT_STORE_CONFLICT", "Owner-report path is unsafe"
                )
            if path in entries:
                previous = self._read(path, directories)
                _require(
                    _canonical(previous["report"]) == _canonical(report),
                    "OWNER_REPORT_STORE_CONFLICT",
                    "Report ID already contains another report",
                )
                if directories is not None:
                    directories[1].sync()
                authorize()
                return previous
            _require(
                len(entries) < self.MAX_REPORTS,
                "OWNER_REPORT_STORE_LIMIT",
                "Owner-report store limit reached",
            )
            receipt = _seal(
                {
                    "schema": SCHEMA,
                    "report_id": report_id,
                    "project_id": report["project_id"],
                    "snapshot_id": report["snapshot_id"],
                    "status": "stored",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "report": report,
                }
            )
            try:
                raw = _canonical(receipt)
                _require(
                    len(raw) <= MAX_RECORD,
                    "OWNER_REPORT_STORE_LIMIT",
                    "Owner-report receipt is too large",
                )
                if directories is not None:
                    # POSIX readers consume verified copied bytes. Publication
                    # uses a private sibling, fsync and atomic no-overwrite rename;
                    # an interrupted temporary is recovery-required, never history.
                    authorize()
                    directories[1].publish_bytes(path.name, raw)
                else:
                    # Preserve the Windows deny-write/delete directory-pin path.
                    with path.open("xb") as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(stream.fileno())
            except FileExistsError:
                try:
                    previous = self._read(path, directories)
                    _require(
                        _canonical(previous["report"]) == _canonical(report),
                        "OWNER_REPORT_STORE_CONFLICT",
                        "Report ID already contains another report",
                    )
                    if directories is not None:
                        directories[1].sync()
                    authorize()
                    return previous
                except CoreError:
                    raise
            except CoreError:
                raise
            except OSError as exc:
                raise CoreError(
                    "OWNER_REPORT_STORE_RECOVERY_REQUIRED",
                    "Owner-report receipt write failed",
                ) from exc
            authorize()
            return receipt

    def get(
        self,
        report_id,
        *,
        expected_project_id,
        expected_snapshot_id,
        authorize,
    ):
        if not callable(authorize):
            raise CoreError(
                "OWNER_REPORT_STORE_AUTHORIZATION",
                "Owner-report authorization is required",
            )
        _report_id(report_id)
        validate_project_id(expected_project_id)
        _hash(expected_snapshot_id, "snapshot_id", snapshot=True)
        self._ready()
        authorize()
        with self._owned_root() as directories, self._locked(directories):
            entries = self._entries(directories, validate=True)
            path = self.reports / f"{report_id}.json"
            _require(
                path in entries,
                "OWNER_REPORT_STORE_NOT_FOUND",
                "Owner-report receipt is absent",
            )
            receipt = self._read(path, directories)
            _require(
                receipt["project_id"] == expected_project_id
                and receipt["snapshot_id"] == expected_snapshot_id,
                "OWNER_REPORT_STORE_CONTEXT",
                "Owner-report receipt does not match expected context",
            )
            authorize()
            return receipt

    def list(self, *, expected_project_id, expected_snapshot_id, authorize, limit=100):
        if not callable(authorize):
            raise CoreError(
                "OWNER_REPORT_STORE_AUTHORIZATION",
                "Owner-report authorization is required",
            )
        validate_project_id(expected_project_id)
        _hash(expected_snapshot_id, "snapshot_id", snapshot=True)
        if type(limit) is not int or not 1 <= limit <= self.MAX_REPORTS:
            raise CoreError(
                "OWNER_REPORT_STORE_INVALID", "Report limit is out of bounds"
            )
        self._ready()
        authorize()
        with self._owned_root() as directories, self._locked(directories):
            selected = []
            for path in self._entries(directories, validate=False):
                receipt = self._read(path, directories)
                if (
                    receipt["project_id"] != expected_project_id
                    or receipt["snapshot_id"] != expected_snapshot_id
                ):
                    continue
                key = (_timestamp(receipt["created_at"], "created_at"), path.name)
                item = (key, receipt)
                if len(selected) < limit:
                    heapq.heappush(selected, item)
                elif key > selected[0][0]:
                    heapq.heapreplace(selected, item)
        selected.sort(key=lambda item: item[0], reverse=True)
        authorize()
        return [item[1] for item in selected]
