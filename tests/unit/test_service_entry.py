"""Native service contracts with fake SCM; never install or start a service."""

import ctypes
import importlib
import json
from pathlib import Path
import threading
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from rentgen_core.errors import CoreError


def entry():
    return importlib.import_module("rentgen_core.service_entry")


@pytest.fixture
def configured(tmp_path):
    registry = tmp_path / "registry.sqlite3"
    registry.touch()
    scanner = tmp_path / "scanner.exe"
    scanner.touch()
    profile = tmp_path / "profile"
    profile.mkdir()
    document = {
        "schema": 1,
        "service_name": "Rentgen.Observer",
        "registry": str(registry),
        "profile": str(profile),
        "scanner": str(scanner),
        "project": "6e461c4d-e19c-4e37-85b3-3aa0961580b7",
        "interval_seconds": 5,
        "max_cycles": 1,
    }
    path = tmp_path / "settings.json"

    def write(**updates):
        path.write_text(json.dumps(document | updates), encoding="utf-8")
        return path

    write()
    return SimpleNamespace(path=path, document=document, write=write)


class Worker:
    def __init__(self, tick=None, close=None):
        self.calls = 0
        self.closed = 0
        self._tick = tick
        self._close = close

    def tick(self):
        self.calls += 1
        if self._tick:
            self._tick()

    def close(self):
        self.closed += 1
        if self._close:
            self._close()


class SCM:
    def __init__(self):
        self.states = []
        self.handler = None
        self.before_main = None
        self.on_status = None

    def dispatch(self, callback):
        if self.before_main:
            self.before_main()
        callback("Rentgen.Observer", True)

    def register(self, name, handler):
        assert name == "Rentgen.Observer"
        self.handler = handler
        return 123

    def set_status(self, handle, status):
        assert handle == 123
        self.states.append(status)
        if self.on_status:
            self.on_status(status)


def states(scm):
    return [status.state for status in scm.states]


def test_config_is_strict_and_canonical(configured):
    config = entry().load_config(configured.path)
    assert config.registry == Path(configured.document["registry"]).resolve()
    assert config.profile == Path(configured.document["profile"]).resolve()
    assert config.project == configured.document["project"]
    assert config.max_cycles == 1
    with pytest.raises((AttributeError, TypeError)):
        config.max_cycles = 2


@pytest.mark.parametrize(
    "updates",
    [
        {"schema": True},
        {"schema": 2},
        {"service_name": "bad name"},
        {"service_name": "password-private"},
        {"project": "not-a-uuid"},
        {"interval_seconds": True},
        {"interval_seconds": 4},
        {"interval_seconds": 86401},
        {"interval_seconds": float("nan")},
        {"max_cycles": True},
        {"max_cycles": 0},
        {"max_cycles": 10001},
        {"max_cycles": 1.0},
        {"principal": "S-1-5-18"},
        {"factory": "arbitrary.module"},
        {"password": "private-value"},
        {"registry": "relative.sqlite3"},
        {"registry": "C:relative.sqlite3"},
        {"registry": r"\\server\share\registry.sqlite3"},
        {"registry": r"\\?\C:\registry.sqlite3"},
        {"registry": r"C:\data\..\registry.sqlite3"},
        {"registry": r"C:\data\registry.sqlite3:stream"},
        {"registry": r"C:\%TEMP%\registry.sqlite3"},
        {"registry": "\ud800"},
        {"profile": "missing"},
        {"scanner": "missing.exe"},
    ],
)
def test_rejects_invalid_config_without_echo(configured, updates):
    configured.write(**updates)
    with pytest.raises(CoreError) as raised:
        entry().load_config(configured.path)
    assert raised.value.code == "SERVICE_CONFIG_INVALID"
    assert str(raised.value) == "Invalid service configuration"
    assert raised.value.details == {}


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"[]",
        b'{"schema":1,"schema":1}',
        b"\xef\xbb\xbf{}",
        b"\xff",
        b" " * 16385,
    ],
)
def test_rejects_malformed_or_oversized_json(configured, raw):
    configured.path.write_bytes(raw)
    with pytest.raises(CoreError) as raised:
        entry().load_config(configured.path)
    assert raised.value.code == "SERVICE_CONFIG_INVALID"


def test_console_runs_finite_cycles_and_closes_once(configured):
    configured.write(max_cycles=3)
    worker = Worker()

    class FastStop:
        def __init__(self):
            self.delays = []

        def is_set(self):
            return False

        def wait(self, seconds):
            self.delays.append(seconds)
            return False

    stop = FastStop()
    result = entry().run_console(
        configured.path, worker_factory=lambda _: worker, stop_event=stop
    )
    assert (result.exit_code, result.cycles, result.error_code) == (0, 3, None)
    assert (worker.calls, worker.closed) == (3, 1)
    assert stop.delays == [5, 5]


def test_console_stop_before_start_does_not_construct_worker(configured):
    stop = Event()
    stop.set()
    result = entry().run_console(
        configured.path,
        worker_factory=lambda _: pytest.fail("factory called"),
        stop_event=stop,
    )
    assert (result.exit_code, result.cycles) == (0, 0)


def test_null_budget_runs_until_cooperative_stop(configured):
    configured.write(max_cycles=None)
    stop = Event()
    worker = Worker(tick=stop.set)
    result = entry().run_console(
        configured.path, worker_factory=lambda _: worker, stop_event=stop
    )
    assert (result.exit_code, result.cycles) == (0, 1)
    assert worker.closed == 1


def test_missing_budget_defaults_to_run_until_stop(configured):
    document = dict(configured.document)
    del document["max_cycles"]
    configured.path.write_text(json.dumps(document), encoding="utf-8")
    assert entry().load_config(configured.path).max_cycles is None


@pytest.mark.parametrize("failure", ["factory", "tick", "close", "both"])
def test_worker_errors_are_sanitized_and_cleanup_is_owned(configured, failure, capsys):
    def fail():
        raise RuntimeError("private-value")

    worker = Worker(
        tick=fail if failure in {"tick", "both"} else None,
        close=fail if failure in {"close", "both"} else None,
    )

    def factory(config):
        if failure == "factory":
            fail()
        return worker

    result = entry().run_console(configured.path, worker_factory=factory)
    assert result.exit_code == 2
    assert result.error_code == "SERVICE_WORKER_FAILED"
    assert worker.closed == (0 if failure == "factory" else 1)
    assert "private-value" not in repr(result)
    assert capsys.readouterr() == ("", "")


def test_service_dispatches_before_reading_config_and_reports_lifetime(
    configured, monkeypatch
):
    module = entry()
    monkeypatch.setattr(module, "_platform", "win32")
    scm = SCM()
    worker = Worker(
        close=lambda: states(scm)[-1] == module.STOP_PENDING
        or pytest.fail("cleanup before pending")
    )
    scm.before_main = lambda: configured.path.exists() or pytest.fail("missing config")
    original = module.load_config

    def load(path):
        assert states(scm) == [module.START_PENDING]
        return original(path)

    monkeypatch.setattr(module, "load_config", load)
    result = module.NativeService(
        configured.path, worker_factory=lambda _: worker, scm=scm
    ).run()
    assert result.exit_code == 0
    assert states(scm) == [
        module.START_PENDING,
        module.RUNNING,
        module.STOP_PENDING,
        module.STOPPED,
    ]
    assert [status.controls for status in scm.states] == [0, 5, 0, 0]
    assert (worker.calls, worker.closed) == (1, 1)
    assert scm.states[-1].win32_exit_code == 0
    assert scm.states[-1].checkpoint == scm.states[-1].wait_hint == 0
    before = len(scm.states)
    assert scm.handler(module.INTERROGATE) == 0
    assert scm.handler(module.STOP) == 0
    assert len(scm.states) == before


@pytest.mark.parametrize("control", [1, 5])
def test_stop_signals_immediately_and_waits_for_tick_and_cleanup(
    configured, monkeypatch, control
):
    module = entry()
    monkeypatch.setattr(module, "_platform", "win32")
    configured.write(max_cycles=10, interval_seconds=86400)
    entered = Event()
    released = Event()
    pending = Event()
    scm = SCM()
    scm.on_status = (
        lambda status: pending.set() if status.state == module.STOP_PENDING else None
    )

    def tick():
        entered.set()
        assert released.wait(5)

    worker = Worker(tick=tick)
    service = module.NativeService(
        configured.path, worker_factory=lambda _: worker, scm=scm
    )
    results = []
    thread = Thread(target=lambda: results.append(service.run()))
    thread.start()
    try:
        assert entered.wait(5)
        assert scm.handler(999) == 120
        assert scm.handler(control) == 0
        assert scm.handler(control) == 0
        assert pending.wait(5)
        assert worker.closed == 0
        assert thread.is_alive()
    finally:
        released.set()
        thread.join(5)
    assert not thread.is_alive()
    assert results[0].exit_code == 0
    assert states(scm) == [2, 4, 3, 1]
    assert (worker.calls, worker.closed) == (1, 1)


def test_early_stop_never_reports_running(configured, monkeypatch):
    module = entry()
    monkeypatch.setattr(module, "_platform", "win32")
    scm = SCM()
    scm.on_status = (
        lambda status: scm.handler(module.STOP)
        if status.state == module.START_PENDING
        else None
    )
    result = module.NativeService(
        configured.path, scm=scm, worker_factory=lambda _: pytest.fail("factory called")
    ).run()
    assert result.exit_code == 0
    assert states(scm) == [2, 3, 1]


@pytest.mark.parametrize(
    "failure", ["config", "factory", "tick", "close", "status", "register", "dispatch"]
)
def test_service_failure_stops_with_generic_numeric_status(
    configured, monkeypatch, failure, capsys
):
    module = entry()
    monkeypatch.setattr(module, "_platform", "win32")
    scm = SCM()

    def fail(*args):
        raise RuntimeError("private-value")

    worker = Worker(
        tick=fail if failure == "tick" else None,
        close=fail if failure == "close" else None,
    )
    if failure == "config":
        configured.path.write_text("{}")
    elif failure in {"register", "dispatch"}:
        setattr(scm, failure, fail)
    elif failure == "status":
        scm.on_status = (
            lambda status: fail() if status.state == module.RUNNING else None
        )
    result = module.NativeService(
        configured.path,
        scm=scm,
        worker_factory=fail if failure == "factory" else lambda _: worker,
    ).run()
    assert result.exit_code == 2
    if failure not in {"register", "dispatch"}:
        assert states(scm)[-1] == module.STOPPED
        assert states(scm).count(module.STOPPED) == 1
        assert scm.states[-1].win32_exit_code == 1066
        assert scm.states[-1].service_exit_code in {1, 2, 3}
    assert worker.closed == (
        0 if failure in {"config", "factory", "register", "dispatch"} else 1
    )
    assert "private-value" not in repr(result)
    assert capsys.readouterr() == ("", "")


def test_service_platform_gate_precedes_config_and_factory(monkeypatch):
    module = entry()
    monkeypatch.setattr(module, "_platform", "linux")
    monkeypatch.setattr(module, "load_config", lambda _: pytest.fail("read config"))
    result = module.NativeService(
        "missing.json", scm=SCM(), worker_factory=lambda _: pytest.fail("worker")
    ).run()
    assert result.error_code == "SERVICE_PLATFORM_UNSUPPORTED"


def test_cli_console_output_and_bad_argv_are_bounded(configured, capsys):
    module = entry()
    worker = Worker()
    assert (
        module.main(
            ["--console", "--config", str(configured.path)],
            worker_factory=lambda _: worker,
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {"status": "stopped", "cycles": 1}
    assert (
        module.main(
            [
                "--console",
                "--config",
                str(configured.path),
                "--password",
                "private-value",
            ]
        )
        == 2
    )
    output = capsys.readouterr()
    assert "private-value" not in output.out + output.err
    assert "SERVICE_ARGUMENT_INVALID" in output.err


def test_native_ctypes_seam_registers_callbacks_and_fixed_width_status(monkeypatch):
    module = entry()
    callbacks = {}
    statuses = []

    class Function:
        def __init__(self, fn):
            self.fn = fn

        def __call__(self, *args):
            return self.fn(*args)

    def dispatch(table):
        assert table[0].name == ""
        assert table[1].name is None
        assert not table[1].main
        args = (ctypes.c_wchar_p * 1)("Rentgen.Observer")
        table[0].main(1, args)
        return 1

    def register(name, callback, context):
        callbacks["control"] = callback
        assert name == "Rentgen.Observer"
        assert context is None
        return 321

    def set_status(handle, pointer):
        assert handle == 321
        status = ctypes.cast(pointer, ctypes.POINTER(module._SERVICE_STATUS)).contents
        statuses.append(tuple(getattr(status, name) for name, _ in status._fields_))
        return 1

    library = SimpleNamespace(
        StartServiceCtrlDispatcherW=Function(dispatch),
        RegisterServiceCtrlHandlerExW=Function(register),
        SetServiceStatus=Function(set_status),
    )
    seam = module.Win32SCM(library=library)
    names = []
    seam.dispatch(lambda name, valid: names.append((name, valid)))
    handle = seam.register("Rentgen.Observer", lambda code: 120)
    seam.set_status(handle, module.ServiceStatus(module.RUNNING, controls=5))
    assert names == [("Rentgen.Observer", True)]
    assert callbacks["control"](99, 0, None, None) == 120
    assert ctypes.sizeof(module._SERVICE_STATUS) == 28
    assert statuses == [(16, 4, 5, 0, 0, 0, 0)]


def test_service_base_exception_is_failure_even_when_stop_arrives(
    configured, monkeypatch
):
    module = entry()
    monkeypatch.setattr(module, "_platform", "win32")
    scm = SCM()

    def fail():
        scm.handler(module.STOP)
        raise KeyboardInterrupt("private-value")

    worker = Worker(tick=fail)
    result = module.NativeService(
        configured.path, scm=scm, worker_factory=lambda _: worker
    ).run()
    assert result.error_code == "SERVICE_WORKER_FAILED"
    assert worker.closed == 1
    assert scm.states[-1].win32_exit_code == 1066


def test_default_adapter_holds_authorized_observer_lease(configured, monkeypatch):
    from contextlib import contextmanager
    from rentgen_core import local_identity, observer

    module = entry()
    config = module.load_config(configured.path)
    principal = object()
    calls = []
    monkeypatch.setattr(local_identity, "current_windows_principal", lambda: principal)

    class AuthorizedObserver:
        def __init__(self, runtime, identity, project, profile):
            assert runtime.registry_path == config.registry
            assert identity is principal
            assert (project, profile) == (config.project, config.profile)

        @contextmanager
        def locked(self):
            calls.append("authorized-and-locked")
            try:
                yield
            finally:
                calls.append("unlocked")

        def _tick(self):
            assert calls[-1] == "authorized-and-locked"
            return "unchanged"

    monkeypatch.setattr(observer, "Observer", AuthorizedObserver)
    worker = module.ObserverWorker(config)
    assert worker.tick() == "unchanged"
    assert worker.tick() == "unchanged"
    worker.close()
    worker.close()
    assert calls == ["authorized-and-locked", "unlocked"]


def test_scm_identity_mismatch_fails_before_factory(configured, monkeypatch):
    module = entry()
    monkeypatch.setattr(module, "_platform", "win32")
    configured.write(service_name="Rentgen.Other")
    scm = SCM()
    result = module.NativeService(
        configured.path, scm=scm, worker_factory=lambda _: pytest.fail("factory called")
    ).run()
    assert result.error_code == "SERVICE_CONFIG_INVALID"
    assert states(scm) == [2, 3, 1]


def test_console_interrupt_closes_worker(configured):
    def interrupt():
        raise KeyboardInterrupt()

    worker = Worker(tick=interrupt)
    result = entry().run_console(configured.path, worker_factory=lambda _: worker)
    assert result.exit_code == 0
    assert worker.closed == 1


@pytest.mark.parametrize("operation", ["dispatch", "register", "set_status"])
def test_ctypes_false_results_fail_closed(operation):
    module = entry()

    def false(*args):
        return 0

    library = SimpleNamespace(
        StartServiceCtrlDispatcherW=false,
        RegisterServiceCtrlHandlerExW=false,
        SetServiceStatus=false,
    )
    seam = module.Win32SCM(library=library)
    with pytest.raises(CoreError) as raised:
        if operation == "dispatch":
            seam.dispatch(lambda *_: None)
        elif operation == "register":
            seam.register("Rentgen.Observer", lambda _: 0)
        else:
            seam.set_status(123, module.ServiceStatus(module.STOPPED))
    assert raised.value.code == "SERVICE_SCM_FAILED"


def test_ctypes_callback_exceptions_never_escape_or_print(capsys):
    module = entry()
    callbacks = []

    def dispatch(table):
        args = (ctypes.c_wchar_p * 1)("Rentgen.Observer")
        table[0].main(1, args)
        return 1

    def register(name, handler, context):
        callbacks.append(handler)
        return 1

    def status(*args):
        return 1

    def fail(*args):
        raise SystemExit("private-value")

    seam = module.Win32SCM(
        library=SimpleNamespace(
            StartServiceCtrlDispatcherW=dispatch,
            RegisterServiceCtrlHandlerExW=register,
            SetServiceStatus=status,
        )
    )
    with pytest.raises(CoreError) as raised:
        seam.dispatch(fail)
    assert raised.value.code == "SERVICE_SCM_FAILED"
    seam.register("Rentgen.Observer", fail)
    assert callbacks[0](module.STOP, 0, None, None) == 1064
    assert capsys.readouterr() == ("", "")


def test_import_and_nonwindows_seam_do_not_load_win32(monkeypatch):
    module = entry()

    def fail(*args, **kwargs):
        pytest.fail("unexpected Windows DLL load")

    monkeypatch.setattr(ctypes, "WinDLL", fail, raising=False)
    module = importlib.reload(module)
    monkeypatch.setattr(module, "_platform", "linux")
    with pytest.raises(CoreError) as raised:
        module.Win32SCM()
    assert raised.value.code == "SERVICE_PLATFORM_UNSUPPORTED"


@pytest.mark.parametrize("mode", ["console", "native"])
@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_cleanup_accessor_failure_is_sanitized(
    configured, monkeypatch, capsys, mode, error_type
):
    module = entry()
    monkeypatch.setattr(module, "_platform", "win32")
    uncaught = []
    monkeypatch.setattr(threading, "excepthook", uncaught.append)

    class BrokenWorker:
        calls = 0

        def tick(self):
            pytest.fail("tick before worker validation")

        @property
        def close(self):
            self.calls += 1
            raise error_type("private-value")

    worker = BrokenWorker()
    scm = SCM()
    if mode == "console":
        result = module.run_console(configured.path, worker_factory=lambda _: worker)
    else:
        result = module.NativeService(
            configured.path, scm=scm, worker_factory=lambda _: worker
        ).run()
        assert states(scm) == [2, 3, 1]
        assert scm.states[-1].service_exit_code == 2
    assert result.error_code == "SERVICE_WORKER_FAILED"
    assert worker.calls == 1
    assert uncaught == []
    assert "private-value" not in repr(result)
    assert capsys.readouterr() == ("", "")


def test_tick_accessor_failure_releases_bound_cleanup(configured):
    class BrokenWorker:
        closed = 0

        @property
        def tick(self):
            raise RuntimeError("private-value")

        def close(self):
            self.closed += 1

    worker = BrokenWorker()
    result = entry().run_console(configured.path, worker_factory=lambda _: worker)
    assert result.error_code == "SERVICE_WORKER_FAILED"
    assert worker.closed == 1
