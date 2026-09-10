"""Pinned BSL-LS diagnostics adapter and strict report decoding.

This decoder only validates bytes. It cannot attest that a process ran or that
its configuration was enabled; the concrete runtime owner supplies that proof.
"""

import json
import hashlib
import os
import threading
import time
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from rentgen_core.diagnostics import (
    BslAnalysis,
    BslDiagnostic,
    BslPosition,
    BSL_PROFILE_ID,
    BSL_CONFIG_SHA256,
    BSL_RUNTIME_MANIFEST_SHA256,
)
from ._windows_process import WindowsProcessOwner, ProcessFailure, ProcessLimits
from ._runtime_pins import RuntimePins, PinFailure
from ._owned_attempt import OwnedAttempt


class ReportFailure(Exception):
    """Bounded failure reason without untrusted report text."""

    def __init__(self, code="BSL_REPORT_INVALID"):
        self.code = code
        super().__init__(code)


def _require(condition, code="BSL_REPORT_INVALID"):
    if not condition:
        raise ReportFailure(code)


def _object(value, keys):
    _require(type(value) is dict and set(value) == set(keys))
    return value


def _integer(value, maximum):
    _require(type(value) is int and 0 <= value <= maximum)
    return value


def _string(value, maximum):
    _require(type(value) is str)
    try:
        _require(len(value.encode("utf-8", errors="strict")) <= maximum)
    except UnicodeError:
        raise ReportFailure() from None
    return value


def _json(raw):
    _require(type(raw) is bytes and len(raw) <= 2 * 1024 * 1024, "BSL_RESOURCE_LIMIT")
    # Reject deep structures before json.loads can recurse/allocate them.
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            _require(depth <= 24, "BSL_RESOURCE_LIMIT")
        elif byte in (93, 125):
            depth -= 1

    def pairs(items):
        value = {}
        for key, item in items:
            _require(key not in value)
            value[key] = item
        return value

    def invalid_number(_):
        raise ReportFailure()

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=invalid_number,
            parse_float=invalid_number,
        )
    except (ValueError, UnicodeError, RecursionError):
        raise ReportFailure() from None
    nodes = 0
    stack = [value]
    while stack:
        item = stack.pop()
        nodes += 1
        _require(nodes <= 50000, "BSL_RESOURCE_LIMIT")
        if type(item) is dict:
            stack.extend(item.keys())
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)
        elif type(item) is str:
            _string(item, 2 * 1024 * 1024)
    return value


def _candidate_lines(candidate):
    _require(
        type(candidate) is bytes and len(candidate) <= 1024 * 1024, "BSL_RESOURCE_LIMIT"
    )
    try:
        text = candidate.decode("utf-8-sig", errors="strict")
    except UnicodeError:
        raise ReportFailure("BSL_ENCODING_UNSUPPORTED") from None
    _require(all(ord(char) <= 0xFFFF for char in text), "BSL_COORDINATES_UNSUPPORTED")
    # U+2028 and similar characters are not source line delimiters. Preserve
    # final empty LF/CRLF lines, matching the pinned producer's metrics.
    return re.split(r"\r\n|\n", text)


def _uri(value, expected):
    _string(value, 32768)
    _require("?" not in value and "#" not in value)
    _require(not re.search(r"%(?![0-9a-fA-F]{2})", value))
    _require(not re.search(r"%(?:2f|5c|00)", value, re.IGNORECASE))
    _require(not any(ord(char) < 32 for char in value))
    try:
        parsed = urlsplit(value)
        decoded = unquote(parsed.path, encoding="utf-8", errors="strict")
        expected_path = unquote(
            urlsplit(expected.as_uri()).path, encoding="utf-8", errors="strict"
        )
    except (ValueError, UnicodeError):
        raise ReportFailure() from None
    _require(
        parsed.scheme == "file"
        and not parsed.netloc
        and not parsed.query
        and not parsed.fragment
        and decoded == expected_path,
        "BSL_COVERAGE_MISMATCH",
    )


def _range(value, lines):
    _object(value, ("start", "end"))
    positions = []
    for endpoint in ("start", "end"):
        point = _object(value[endpoint], ("line", "character"))
        line = _integer(point["line"], len(lines) - 1)
        character = _integer(point["character"], len(lines[line]))
        positions.append(BslPosition(line, character))
    start, end = positions
    _require((start.line, start.character) <= (end.line, end.character))
    return start, end


def _metrics(value, lines):
    scalar = (
        "procedures",
        "functions",
        "lines",
        "ncloc",
        "comments",
        "statements",
        "cognitiveComplexity",
        "cyclomaticComplexity",
    )
    _object(value, (*scalar, "nclocData", "covlocData"))
    for key in scalar:
        _integer(value[key], 1024 * 1024 + 1)
    _require(value["lines"] == len(lines))
    _require(value["covlocData"] is None)
    data = value["nclocData"]
    _require(type(data) is list and len(data) <= len(lines))
    previous = 0
    for line in data:
        _integer(line, len(lines))
        _require(line > previous)
        previous = line
    _require(value["ncloc"] == len(data))


def _diagnostic(value, lines, expected):
    _object(
        value,
        (
            "code",
            "codeDescription",
            "data",
            "message",
            "range",
            "relatedInformation",
            "severity",
            "source",
            "tags",
        ),
    )
    code = _string(value["code"], 128)
    _require(re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", code))
    _object(value["codeDescription"], ("href",))
    _require(
        value["codeDescription"]["href"]
        == "https://1c-syntax.github.io/bsl-language-server/en/diagnostics/" + code
    )
    _require(value["data"] is None)
    _require(value["source"] == "bsl-language-server")
    _require(
        type(value["severity"]) is str
        and value["severity"] in ("Error", "Warning", "Information", "Hint")
    )
    message = _string(value["message"], 1024)
    start, end = _range(value["range"], lines)
    tags = value["tags"]
    _require(type(tags) is list and len(tags) <= 2)
    _require(
        all(type(tag) is str and tag in ("Unnecessary", "Deprecated") for tag in tags)
    )
    _require(len(set(tags)) == len(tags))
    related = value["relatedInformation"]
    if related is not None:
        _require(type(related) is list and len(related) <= 32)
        for info in related:
            _object(info, ("location", "message"))
            _string(info["message"], 1024)
            location = _object(info["location"], ("uri", "range"))
            _uri(location["uri"], expected)
            _range(location["range"], lines)
    return BslDiagnostic(code, value["severity"], message, start, end)


def decode_report(
    raw: bytes, candidate: bytes, *, expected_directory: Path, suffix: str
) -> tuple[BslDiagnostic, ...]:
    """Decode a bounded, exact-one-module BMP producer report, or fail closed."""
    _require(suffix in (".bsl", ".os"), "BSL_SOURCE_TYPE_UNSUPPORTED")
    _require(isinstance(expected_directory, Path) and expected_directory.is_absolute())
    lines = _candidate_lines(candidate)
    value = _object(_json(raw), ("date", "sourceDir", "fileinfos"))
    _require(
        re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", _string(value["date"], 19))
    )
    _require(value["sourceDir"] == str(expected_directory), "BSL_COVERAGE_MISMATCH")
    files = value["fileinfos"]
    _require(type(files) is list and len(files) == 1, "BSL_COVERAGE_MISMATCH")
    info = _object(files[0], ("path", "mdoRef", "diagnostics", "metrics"))
    expected = expected_directory / ("Candidate" + suffix)
    _uri(info["path"], expected)
    _uri(info["mdoRef"], expected)
    _metrics(info["metrics"], lines)
    diagnostics = info["diagnostics"]
    _require(
        type(diagnostics) is list and len(diagnostics) <= 4096, "BSL_RESOURCE_LIMIT"
    )
    _require(len(diagnostics) <= 128, "BSL_RESOURCE_LIMIT")
    return tuple(_diagnostic(item, lines, expected) for item in diagnostics)


@dataclass(frozen=True)
class BslRuntimeProfile:
    """Trusted startup locators, never accepted from proposal/tool JSON."""

    java_home: Path
    jar_path: Path
    work_parent: Path

    def __post_init__(self):
        for path in (self.java_home, self.jar_path, self.work_parent):
            if (
                not isinstance(path, Path)
                or not path.is_absolute()
                or ".." in path.parts
            ):
                raise ValueError("Explicit absolute BSL startup paths required")


@dataclass
class _AnalysisState:
    started: float
    pins: RuntimePins | None = None
    attempt: OwnedAttempt | None = None
    runtime_verified: bool = False
    execution_possible: bool = False
    stdout_sha256: str | None = None
    stderr_sha256: str | None = None
    report_sha256: str | None = None
    exit_code: int | None = None


def _runtime_descriptor():
    package = files("rentgen_diagnostics").joinpath("profiles")
    with package.joinpath("bsl-ls-1.0.5-temurin21-win64.json").open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if hashlib.sha256(raw).hexdigest() != BSL_RUNTIME_MANIFEST_SHA256:
        raise PinFailure()
    descriptor = json.loads(raw)
    with package.joinpath("temurin21.0.12.1-win64-files.json").open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if hashlib.sha256(raw).hexdigest() != descriptor["java"]["manifest_sha256"]:
        raise PinFailure()
    manifest = json.loads(raw)
    expected = {item["path"]: (item["size_bytes"], item["sha256"]) for item in manifest}
    if len(expected) != 490 or sum(size for size, _ in expected.values()) != 343823876:
        raise PinFailure()
    return descriptor, expected


def _windows_environment(attempt):
    import ctypes as c
    from ctypes import wintypes as w

    api = attempt.native.kernel
    api.GetWindowsDirectoryW.argtypes = [w.LPWSTR, w.UINT]
    api.GetWindowsDirectoryW.restype = w.UINT
    directory = c.create_unicode_buffer(32768)
    count = api.GetWindowsDirectoryW(directory, len(directory))
    if not 0 < count < len(directory):
        raise ProcessFailure("BSL_PROCESS_FAILED")
    return {
        "SYSTEMROOT": directory.value,
        "WINDIR": directory.value,
        "USERPROFILE": str(attempt.path / "profile"),
        "TEMP": str(attempt.path / "tmp"),
        "TMP": str(attempt.path / "tmp"),
        "SENTRY_DSN": "",
        "SENTRY_ENABLED": "false",
    }


class BslLanguageServerAdapter:
    """One lifetime owner; construction has no filesystem or subprocess IO.

    No OS network sandbox is claimed. The child receives a fixed allowlisted
    environment/configuration and owned private scratch, with an inherited Job.
    A process or file-cleanup uncertainty poisons this adapter until restart.
    """

    def __init__(self, profile: BslRuntimeProfile):
        if type(profile) is not BslRuntimeProfile:
            raise ValueError("Trusted BSL runtime profile required")
        self.profile = profile
        self._owner = WindowsProcessOwner()
        self._lock = threading.Lock()
        self._retained = None

    def _check_available(self):
        if self._retained is not None:
            raise ProcessFailure("BSL_OWNER_QUARANTINED")
        self._owner.check_available()

    def analyze(self, candidate_bytes: bytes, *, suffix: str, authorize) -> BslAnalysis:
        if not callable(authorize):
            raise ValueError("Trusted authorization callback required")
        authorize()
        try:
            if type(candidate_bytes) is not bytes or len(candidate_bytes) > 1024 * 1024:
                raise ValueError("Bounded immutable candidate bytes required")
            state = _AnalysisState(time.monotonic())
            if not self._lock.acquire(blocking=False):
                return self._result(candidate_bytes, state, "failed", "BSL_OWNER_BUSY")
            try:
                return self._analyze_locked(candidate_bytes, suffix, authorize, state)
            finally:
                self._lock.release()
        finally:
            try:
                authorize()
            except BaseException as exc:
                raise exc from None

    def _result(self, candidate, state, status, reason, diagnostics=()):
        completed = status == "completed"
        return BslAnalysis(
            status=status,
            reason=reason,
            candidate_sha256=hashlib.sha256(candidate).hexdigest(),
            candidate_size_bytes=len(candidate),
            profile_id=BSL_PROFILE_ID,
            runtime_manifest_sha256=BSL_RUNTIME_MANIFEST_SHA256,
            runtime_verified=state.runtime_verified,
            config_sha256=BSL_CONFIG_SHA256,
            scope="single_module_isolated",
            coverage="exact_one"
            if completed
            else "incomplete"
            if state.execution_possible
            else "not_run",
            diagnostics=diagnostics if completed else (),
            diagnostics_complete=completed,
            total_diagnostics=len(diagnostics) if completed else None,
            report_sha256=state.report_sha256,
            stdout_sha256=state.stdout_sha256,
            stderr_sha256=state.stderr_sha256,
            exit_code=state.exit_code,
        )

    def _analyze_locked(self, candidate, suffix, authorize, state):
        status, reason, diagnostics, primary = "failed", None, (), None
        try:
            self._check_available()
            if os.name != "nt":
                raise ReportFailure("BSL_PLATFORM_UNSUPPORTED")
            if suffix not in (".bsl", ".os"):
                raise ReportFailure("BSL_SOURCE_TYPE_UNSUPPORTED")
            _candidate_lines(candidate)
            diagnostics = self._execute(candidate, suffix, authorize, state)
            status = "completed"
        except (ReportFailure, PinFailure, ProcessFailure) as exc:
            reason = (
                exc.code
                if type(exc.code) is str
                and re.fullmatch(r"BSL_[A-Z0-9_]{1,60}", exc.code)
                else "BSL_PROCESS_FAILED"
            )
            if reason in (
                "BSL_PLATFORM_UNSUPPORTED",
                "BSL_SOURCE_TYPE_UNSUPPORTED",
                "BSL_ENCODING_UNSUPPORTED",
                "BSL_COORDINATES_UNSUPPORTED",
            ):
                status = "unsupported"
        except OSError:
            reason = "BSL_PROCESS_FAILED"
        except BaseException as exc:
            primary = exc
        try:
            self._cleanup(state)
        except BaseException:
            # Public DTO preserves the primary reason and makes cleanup failure
            # visible. Runtime/input objects remain held independently of errors.
            status = "failed"
            reason = reason + "_CLEANUP_FAILED" if reason else "BSL_CLEANUP_FAILED"
            if primary is not None:
                primary.cleanup_failed = True
        if primary is not None:
            raise primary
        return self._result(candidate, state, status, reason, diagnostics)

    def _execute(self, candidate, suffix, authorize, state):
        def deadline():
            if time.monotonic() - state.started >= 60:
                raise PinFailure("BSL_TIMEOUT")

        authorize()
        self._owner.check_available()
        descriptor, expected = _runtime_descriptor()
        if not self.profile.java_home.exists() or not self.profile.jar_path.exists():
            raise PinFailure("BSL_RUNTIME_UNAVAILABLE")
        state.pins = RuntimePins(check=deadline)
        self._retained = state
        state.pins.tree(self.profile.java_home, expected)
        state.pins.file(
            self.profile.jar_path,
            expected_size=descriptor["bsl"]["jar_size_bytes"],
            expected_sha256=descriptor["bsl"]["jar_sha256"],
        )
        state.pins.verify()
        state.runtime_verified = True
        authorize()
        deadline()
        state.attempt = OwnedAttempt(self.profile.work_parent, state.pins)
        state.attempt.create()
        attempt = state.attempt.path
        source = attempt / "src" / ("Candidate" + suffix)
        configuration = attempt / "configuration.json"
        authorize()
        with source.open("xb") as stream:
            stream.write(candidate)
        config_bytes = descriptor["configuration_json"].encode("utf-8")
        with configuration.open("xb") as stream:
            stream.write(config_bytes)
        state.pins.file(source, expected_bytes=candidate)
        state.pins.file(configuration, expected_bytes=config_bytes)
        state.pins.watch_directory(attempt / "src")
        state.pins.verify()
        authorize()
        deadline()
        report_path = attempt / "report" / "bsl-json.json"

        def monitor():
            # This is a cooperative size observation, not an OS disk quota;
            # authority comes only from a retained post-exit report handle.
            try:
                size = report_path.lstat().st_size
            except FileNotFoundError:
                return
            if size > 2 * 1024 * 1024:
                raise ProcessFailure("BSL_RESOURCE_LIMIT")

        argv = [
            str(self.profile.java_home / "bin" / "java.exe"),
            "-Xmx512m",
            "-XX:ActiveProcessorCount=2",
            "-Dfile.encoding=UTF-8",
            "-Duser.home=" + str(attempt / "profile"),
            "-Djava.io.tmpdir=" + str(attempt / "tmp"),
            "-Dsentry.dsn=",
            "-Dsentry.enabled=false",
            "-Dapp.globalConfiguration.path=" + str(configuration),
            "-Dapp.configuration.path=" + str(configuration),
            "-jar",
            str(self.profile.jar_path),
            "analyze",
            "--srcDir",
            str(attempt / "src"),
            "--workspaceDir",
            str(attempt / "src"),
            "--outputDir",
            str(attempt / "report"),
            "--configuration",
            str(configuration),
            "--reporter",
            "json",
            "--silent",
        ]
        state.execution_possible = True
        remaining = 60 - (time.monotonic() - state.started)
        if remaining <= 0:
            raise ProcessFailure("BSL_TIMEOUT")
        result = self._owner.run_process(
            argv,
            cwd=attempt / "src",
            env=_windows_environment(state.attempt),
            authorize=authorize,
            limits=ProcessLimits(wall_seconds=remaining),
            monitor=monitor,
            retained_resources=(state,),
        )
        state.exit_code = result.exit_code
        state.stdout_sha256 = hashlib.sha256(result.stdout).hexdigest()
        state.stderr_sha256 = hashlib.sha256(result.stderr).hexdigest()
        authorize()
        deadline()
        if result.exit_code != 0:
            raise ProcessFailure("BSL_PROCESS_FAILED")
        raw = state.pins.file(report_path, maximum=2 * 1024 * 1024, capture=True)
        state.report_sha256 = hashlib.sha256(raw).hexdigest()
        diagnostics = decode_report(
            raw, candidate, expected_directory=attempt / "src", suffix=suffix
        )
        state.pins.verify()
        deadline()
        return diagnostics

    def _cleanup(self, state):
        if state.pins is None:
            return
        if self._owner.poisoned or (
            state.attempt is not None
            and (
                state.attempt.native.uncertain or state.attempt.native.cleanup_uncertain
            )
        ):
            raise PinFailure("BSL_CLEANUP_FAILED")
        # Process cleanup has already proved root/job/drains stopped. Filesystem
        # cleanup is separately bounded cooperatively and never a path rmtree.
        cleanup_end = min(time.monotonic() + 5, state.started + 65)

        def check_cleanup():
            if time.monotonic() >= cleanup_end:
                raise PinFailure("BSL_CLEANUP_FAILED")

        state.pins.check = check_cleanup
        if state.attempt is not None and state.attempt.created:
            state.attempt.capture_cleanup_inventory()
            state.attempt.cleanup()
        state.pins.close()
        self._retained = None
