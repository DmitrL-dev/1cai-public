"""Native SCM boundary and foreground entrypoint for an authorized Observer.

No installation, account provisioning, recovery or arbitrary plugin loading.
The Python process must itself be SCM's service process; see SERVICE-HOST.md.
"""

import ctypes
from dataclasses import dataclass
import json
from pathlib import Path, PureWindowsPath
import re
import sys
from threading import Event, Thread
import unicodedata

from .context import validate_project_id
from .errors import CoreError


_platform = sys.platform
START_PENDING, RUNNING, STOP_PENDING, STOPPED = 2, 4, 3, 1
STOP, SHUTDOWN, INTERROGATE = 1, 5, 4
MAX_CONFIG_BYTES = 16384
_CREDENTIAL = re.compile(
    r"password|passwd|secret|token|credential|api[-_]?key|bearer", re.I
)
_FIELDS = {
    "schema",
    "service_name",
    "registry",
    "profile",
    "project",
    "scanner",
    "interval_seconds",
    "max_cycles",
}
_ERROR_NUMBERS = {
    "SERVICE_CONFIG_INVALID": 1,
    "SERVICE_WORKER_FAILED": 2,
    "SERVICE_SCM_FAILED": 3,
}


def _invalid():
    return CoreError("SERVICE_CONFIG_INVALID", "Invalid service configuration")


def _text(value):
    if (
        type(value) is not str
        or not 1 <= len(value) <= 240
        or any(unicodedata.category(char).startswith("C") for char in value)
        or _CREDENTIAL.search(value)
    ):
        raise _invalid()
    return value


def _path_spelling(value):
    raw = _text(value)
    win = PureWindowsPath(raw)
    path = Path(raw)
    if (
        not path.is_absolute()
        or raw.startswith(("\\\\", "//"))
        or any(char in raw for char in '<>"|?*%')
        or ":" in raw[2:]
        or ".." in win.parts
        or win.is_reserved()
        or any(part.endswith((" ", ".")) for part in win.parts)
    ):
        raise _invalid()
    if sys.platform == "win32":
        # Reject mapped remote drives too, before opening the file.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True, winmode=0x800)
        query = kernel.GetDriveTypeW
        query.argtypes, query.restype = [ctypes.c_wchar_p], ctypes.c_uint32
        if query(path.anchor) not in {2, 3, 5, 6}:
            raise _invalid()
    return path


def _local_path(value, *, directory=False, suffix=None):
    path = _path_spelling(value)
    resolved = _path_spelling(str(path.resolve(strict=True)))
    if not (resolved.is_dir() if directory else resolved.is_file()) or (
        suffix is not None
        and (path.suffix.lower() != suffix or resolved.suffix.lower() != suffix)
    ):
        raise _invalid()
    return resolved


@dataclass(frozen=True)
class ServiceConfig:
    service_name: str
    registry: Path
    profile: Path
    project: str
    scanner: Path
    interval_seconds: int
    max_cycles: int | None = None


@dataclass(frozen=True)
class GitServiceConfig:
    service_name: str
    registry: Path
    profile: Path
    project: str
    diagnostics_root: Path
    interval_seconds: int
    max_cycles: int = 1
    mode: str = "dry-run"


def _git_config(data):
    required = (_FIELDS - {"scanner", "max_cycles"}) | {"diagnostics_root"}
    if not required <= set(data) <= required | {"max_cycles", "mode"}:
        raise _invalid()
    name = _text(data["service_name"])
    interval, cycles = data["interval_seconds"], data.get("max_cycles", 1)
    mode = data.get("mode", "dry-run")
    if (
        not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,79}", name)
        or type(interval) is not int
        or not 5 <= interval <= 86400
        or type(cycles) is not int
        or not 1 <= cycles <= 10000
        or type(mode) is not str
        or mode not in {"dry-run", "read-only"}
    ):
        raise _invalid()
    return GitServiceConfig(
        name,
        _local_path(data["registry"]),
        _local_path(data["profile"], directory=True),
        validate_project_id(data["project"]),
        _local_path(data["diagnostics_root"], directory=True),
        interval,
        cycles,
        mode,
    )


def _unique(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise _invalid()
        result[name] = value
    return result


def _constant(value):
    raise _invalid()


def load_config(path):
    """Read at most 16 KiB of strict UTF-8 JSON, returning canonical paths.

    All fields are public metadata. Filesystem identity/ACLs remain deployment
    responsibilities; canonicalization follows links and is not TOCTOU defense.
    """
    try:
        if not isinstance(path, (str, Path)):
            raise _invalid()
        path = _local_path(str(path), suffix=".json")
        with path.open("rb") as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise _invalid()
        data = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_constant
        )
        if (
            type(data) is dict
            and type(data.get("schema")) is int
            and data["schema"] == 2
        ):
            return _git_config(data)
        if (
            type(data) is not dict
            or set(data) not in (_FIELDS, _FIELDS - {"max_cycles"})
            or type(data["schema"]) is not int
            or data["schema"] != 1
        ):
            raise _invalid()
        name = _text(data["service_name"])
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,79}", name):
            raise _invalid()
        project = validate_project_id(data["project"])
        interval, cycles = data["interval_seconds"], data.get("max_cycles")
        if (
            type(interval) is not int
            or not 5 <= interval <= 86400
            or (
                cycles is not None
                and (type(cycles) is not int or not 1 <= cycles <= 10000)
            )
        ):
            raise _invalid()
        return ServiceConfig(
            name,
            _local_path(data["registry"]),
            _local_path(data["profile"], directory=True),
            project,
            _local_path(data["scanner"], suffix=".exe"),
            interval,
            cycles,
        )
    except (CoreError, OSError, ValueError, TypeError, RecursionError, RuntimeError):
        raise _invalid() from None


class ObserverWorker:
    """Minimal adapter to the same LocalRuntime/Observer used by observer_cli.

    Acquire the existing profile's lease and authenticate before returning from
    the factory. No profile initialization, principal override or retry occurs.
    """

    def __init__(self, config):
        from rentgen_graph.snapshot_adapter import (
            RentgenCapturedGoBuilder,
            RentgenGraphReaderFactory,
        )
        from .local import LocalRuntime
        from .local_identity import current_windows_principal
        from .observer import Observer

        runtime = LocalRuntime(
            config.registry,
            RentgenGraphReaderFactory(),
            RentgenCapturedGoBuilder(config.scanner),
        )
        self._observer = Observer(
            runtime, current_windows_principal(), config.project, config.profile
        )
        self._lease = self._observer.locked()
        self._lease.__enter__()

    def tick(self):
        # The public tick reacquires the same lease. This explicit adapter owns
        # it across the whole lifetime, following observer_cli's run contract.
        return self._observer._tick()

    def close(self):
        lease, self._lease = self._lease, None
        if lease is not None:
            lease.__exit__(None, None, None)


def create_worker(config):
    """Select only the two built-in compositions; JSON cannot load plugins."""
    if isinstance(config, GitServiceConfig):
        from .service_composition import GitAuditWorker

        return GitAuditWorker(config)
    return ObserverWorker(config)


@dataclass(frozen=True)
class RunResult:
    cycles: int = 0
    error_code: str | None = None

    @property
    def exit_code(self):
        return 2 if self.error_code else 0


def _execute(
    loader, factory, stop, ready=lambda: None, finishing=lambda: None, *, console=False
):
    cleanup = None
    cycles = 0
    error_code = None
    try:
        try:
            config = loader()
        except BaseException:
            error_code = "SERVICE_CONFIG_INVALID"
            return RunResult(cycles, error_code)
        if isinstance(config, GitServiceConfig) and config.mode == "dry-run":
            return RunResult()
        if not stop.is_set():
            worker = factory(config)
            try:
                # Resolve cleanup first so a failing tick accessor still releases
                # owned resources. Descriptors are caller code and may raise.
                cleanup = getattr(worker, "close", None)
                scheduled = isinstance(config, GitServiceConfig)
                tick = getattr(worker, "run" if scheduled else "tick", None)
                if not callable(cleanup) or not callable(tick):
                    raise TypeError("Invalid worker contract")
            except BaseException:
                # Even KeyboardInterrupt from a descriptor is startup failure,
                # not a foreground cancellation of a running worker.
                raise CoreError(
                    "SERVICE_WORKER_FAILED", "Worker interface unavailable"
                ) from None
            ready()
            if scheduled:
                # One scheduler owns the entire bounded lifetime and its backoff.
                cycles = tick(stop)
            while (
                not scheduled
                and not stop.is_set()
                and (config.max_cycles is None or cycles < config.max_cycles)
            ):
                tick()
                cycles += 1
                if config.max_cycles is None or cycles < config.max_cycles:
                    stop.wait(config.interval_seconds)
    except KeyboardInterrupt:
        # Foreground Ctrl+C cooperatively exits this lifetime and releases lease.
        if not console:
            error_code = "SERVICE_WORKER_FAILED"
    except BaseException:
        error_code = "SERVICE_WORKER_FAILED"
    finally:
        finishing()
        if callable(cleanup):
            try:
                cleanup()
            except BaseException:
                error_code = error_code or "SERVICE_WORKER_FAILED"
    return RunResult(cycles, error_code)


def run_console(config_path, *, worker_factory=create_worker, stop_event=None):
    """Run in this thread; injected factory owns partial-startup cleanup.

    Source workers supply tick()/close(); Git workers supply run(stop)/close().
    Cleanup is called once. Worker operations must return on their own. Git
    dry-run validates configuration without constructing a worker.
    """
    return _execute(
        lambda: load_config(config_path),
        worker_factory,
        stop_event if stop_event is not None else Event(),
        console=True,
    )


@dataclass(frozen=True)
class ServiceStatus:
    state: int
    controls: int = 0
    win32_exit_code: int = 0
    service_exit_code: int = 0
    checkpoint: int = 0
    wait_hint: int = 0


class _SERVICE_STATUS(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint32)
        for name in (
            "service_type",
            "state",
            "controls",
            "win32_exit_code",
            "service_exit_code",
            "checkpoint",
            "wait_hint",
        )
    ]


def _scm_error():
    return CoreError("SERVICE_SCM_FAILED", "Service control manager operation failed")


class Win32SCM:
    """Small ctypes seam. An injected DLL object is for isolated API tests only."""

    def __init__(self, *, library=None):
        if library is None:
            if _platform != "win32":
                raise CoreError(
                    "SERVICE_PLATFORM_UNSUPPORTED", "Windows service required"
                )
            library = ctypes.WinDLL("advapi32", use_last_error=True, winmode=0x800)
        self._library = library
        callback = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
        self._main_type = callback(
            None, ctypes.c_uint32, ctypes.POINTER(ctypes.c_wchar_p)
        )
        self._handler_type = callback(
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )

        class TableEntry(ctypes.Structure):
            _fields_ = [("name", ctypes.c_wchar_p), ("main", self._main_type)]

        self._table_type = TableEntry
        signatures = (
            (
                library.StartServiceCtrlDispatcherW,
                [ctypes.POINTER(TableEntry)],
                ctypes.c_int32,
            ),
            (
                library.RegisterServiceCtrlHandlerExW,
                [ctypes.c_wchar_p, self._handler_type, ctypes.c_void_p],
                ctypes.c_void_p,
            ),
            (
                library.SetServiceStatus,
                [ctypes.c_void_p, ctypes.POINTER(_SERVICE_STATUS)],
                ctypes.c_int32,
            ),
        )
        for function, args, result in signatures:
            function.argtypes, function.restype = args, result
        self._callbacks = []

    def dispatch(self, callback):
        failed = []

        def service_main(argc, argv):
            try:
                callback(argv[0] if argc and argv else "", argc == 1)
            except BaseException:
                failed.append(True)

        native = self._main_type(service_main)
        table = (self._table_type * 2)()
        table[0].name, table[0].main = "", native
        self._callbacks.extend((native, table))
        if not self._library.StartServiceCtrlDispatcherW(table) or failed:
            raise _scm_error()

    def register(self, name, handler):
        def control(code, event_type, event_data, context):
            try:
                return handler(code)
            except BaseException:
                return 1064  # ERROR_EXCEPTION_IN_SERVICE; no ctypes traceback.

        native = self._handler_type(control)
        self._callbacks.append(native)
        handle = self._library.RegisterServiceCtrlHandlerExW(name, native, None)
        if not handle:
            raise _scm_error()
        return handle

    def set_status(self, handle, status):
        native = _SERVICE_STATUS(
            16,
            status.state,
            status.controls,
            status.win32_exit_code,
            status.service_exit_code,
            status.checkpoint,
            status.wait_hint,
        )
        if not self._library.SetServiceStatus(handle, ctypes.byref(native)):
            raise _scm_error()


class NativeService:
    """One SCM lifetime; a ServiceMain coordinator owns all status writes.

    HandlerEx only signals events. Worker startup/lease acquisition precedes
    RUNNING; cleanup and thread termination precede the sole STOPPED report.
    """

    def __init__(self, config_path, *, worker_factory=create_worker, scm=None):
        self._path, self._factory, self._scm = config_path, worker_factory, scm
        self._stop, self._changed = Event(), Event()
        self._result = RunResult(error_code="SERVICE_SCM_FAILED")
        self._started = False

    def _control(self, code):
        if code in {STOP, SHUTDOWN}:
            self._stop.set()
            self._changed.set()
            return 0
        return 0 if code == INTERROGATE else 120

    def run(self):
        if _platform != "win32":
            return RunResult(error_code="SERVICE_PLATFORM_UNSUPPORTED")
        if self._started:
            return RunResult(error_code="SERVICE_SCM_FAILED")
        self._started = True
        try:
            if self._scm is None:
                self._scm = Win32SCM()
            self._scm.dispatch(self._service_main)
        except BaseException:
            self._result = RunResult(self._result.cycles, "SERVICE_SCM_FAILED")
        return self._result

    def _service_main(self, name, valid_arguments):
        handle = None
        thread = None
        ready, finishing, proceed, cleanup = Event(), Event(), Event(), Event()
        outcome = []
        scm_failed = False

        def acknowledge(event, release):
            event.set()
            self._changed.set()
            release.wait()

        def loader():
            config = load_config(self._path)
            if not valid_arguments or config.service_name != name:
                raise _invalid()
            return config

        def worker_main():
            outcome.append(
                _execute(
                    loader,
                    self._factory,
                    self._stop,
                    lambda: acknowledge(ready, proceed),
                    lambda: acknowledge(finishing, cleanup),
                )
            )

        def report(state, error_code=None):
            self._scm.set_status(
                handle,
                ServiceStatus(
                    state,
                    controls=5 if state == RUNNING else 0,
                    win32_exit_code=1066 if error_code else 0,
                    service_exit_code=_ERROR_NUMBERS.get(error_code, 3)
                    if error_code
                    else 0,
                    checkpoint=1 if state in {START_PENDING, STOP_PENDING} else 0,
                    wait_hint=30000 if state in {START_PENDING, STOP_PENDING} else 0,
                ),
            )

        try:
            handle = self._scm.register(name, self._control)
            report(START_PENDING)
            thread = Thread(target=worker_main, name="rentgen-observer", daemon=False)
            thread.start()
            while not (ready.is_set() or finishing.is_set() or self._stop.is_set()):
                self._changed.wait()
                self._changed.clear()
            if ready.is_set() and not finishing.is_set() and not self._stop.is_set():
                report(RUNNING)
            proceed.set()
            while not (finishing.is_set() or self._stop.is_set()):
                self._changed.wait()
                self._changed.clear()
            report(STOP_PENDING)
        except BaseException:
            scm_failed = True
        finally:
            self._stop.set()
            proceed.set()
            cleanup.set()
            if thread is not None and thread.ident is not None:
                thread.join()
            self._result = (
                outcome[0] if outcome else RunResult(error_code="SERVICE_SCM_FAILED")
            )
            if scm_failed:
                self._result = RunResult(self._result.cycles, "SERVICE_SCM_FAILED")
            if handle is not None:
                try:
                    report(STOPPED, self._result.error_code)
                except BaseException:
                    self._result = RunResult(self._result.cycles, "SERVICE_SCM_FAILED")


def main(argv=None, *, worker_factory=create_worker):
    """Only mode and a public config path may appear in argv; never echo argv."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--help"]:
        print("rentgen-service (--service|--console) --config <absolute-local.json>")
        return 0
    if (
        len(args) != 3
        or args[0] not in {"--service", "--console"}
        or args[1] != "--config"
    ):
        print('{"error":{"code":"SERVICE_ARGUMENT_INVALID"}}', file=sys.stderr)
        return 2
    if args[0] == "--service":
        # No console output in SCM mode, including startup failures.
        return NativeService(args[2], worker_factory=worker_factory).run().exit_code
    result = run_console(args[2], worker_factory=worker_factory)
    if result.error_code:
        print(json.dumps({"error": {"code": result.error_code}}), file=sys.stderr)
    else:
        print(json.dumps({"status": "stopped", "cycles": result.cycles}))
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
