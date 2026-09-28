"""Injected token and process-inspection contracts; no privileges are changed."""
from contextlib import contextmanager
import ctypes
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def load(name):
    path = Path(__file__).resolve().parents[2] / "scripts/verification" / (name + ".py")
    spec = importlib.util.spec_from_file_location("debug_test_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def token_fixture(monkeypatch, attributes=0, enable_error=None, restore_error=None):
    api = load("scm_native_evidence")
    native = api.NativeEvidence.__new__(api.NativeEvidence)
    native.kernel, native.security = Mock(), Mock()
    native.kernel.GetCurrentProcess.return_value = 99
    state = {"attributes": attributes, "last_error": 0, "requested": []}
    monkeypatch.setattr(api.ctypes, "set_last_error", lambda code: state.update(last_error=code), raising=False)
    monkeypatch.setattr(api.ctypes, "get_last_error", lambda: state["last_error"], raising=False)

    def open_token(process, access, pointer):
        assert process == 99 and access == 0x28
        ctypes.cast(pointer, ctypes.POINTER(api.W.HANDLE)).contents.value = 123
        return True

    def lookup(system, name, pointer):
        assert system is None and name == "SeDebugPrivilege"
        ctypes.cast(pointer, ctypes.POINTER(api.Luid)).contents.low = 17
        return True

    def adjust(token, disable_all, requested, size, previous, needed):
        assert token.value == 123 and not disable_all
        value = ctypes.cast(requested, ctypes.POINTER(api.TokenPrivilegesOne)).contents
        assert value.count == 1 and value.items[0].luid.low == 17
        state["requested"].append(value.items[0].attributes)
        if previous is not None:
            if enable_error is not None:
                state["last_error"] = enable_error[1]
                return enable_error[0]
            original = ctypes.cast(previous, ctypes.POINTER(api.TokenPrivilegesOne)).contents
            original.count = 0 if attributes & 2 else 1
            if original.count:
                original.items[0].luid.low = 17
                original.items[0].attributes = attributes
            ctypes.cast(needed, ctypes.POINTER(api.W.DWORD)).contents.value = size
            state["attributes"] |= 2
        else:
            if restore_error is not None:
                state["last_error"] = restore_error[1]
                return restore_error[0]
            state["attributes"] = value.items[0].attributes
        state["last_error"] = 0
        return True

    native.security.OpenProcessToken.side_effect = open_token
    native.security.LookupPrivilegeValueW.side_effect = lookup
    native.security.AdjustTokenPrivileges.side_effect = adjust
    return api, native, state


@pytest.mark.parametrize("attributes", [0, 1, 2, 3])
@pytest.mark.parametrize("body_error", [False, True])
def test_debug_privilege_restores_all_previous_attributes_and_closes_token(
    monkeypatch, attributes, body_error
):
    _, native, state = token_fixture(monkeypatch, attributes)

    def body():
        with native.debug_privilege():
            assert state["attributes"] & 2
            if body_error:
                raise ValueError("inspection failed")

    if body_error:
        with pytest.raises(ValueError, match="inspection failed"):
            body()
    else:
        body()
    assert state["attributes"] == attributes
    assert state["requested"] == ([2] if attributes & 2 else [2, attributes])
    native.kernel.CloseHandle.assert_called_once()
    assert native.kernel.CloseHandle.call_args.args[0].value == 123


@pytest.mark.parametrize("outcome", [(True, 1300), (False, 5)])
def test_missing_or_denied_debug_privilege_never_enters_inspection(monkeypatch, outcome):
    api, native, state = token_fixture(monkeypatch, enable_error=outcome)
    with pytest.raises(api.NativeEvidenceError) as error:
        with native.debug_privilege():
            pytest.fail("Inspection entered without its existing privilege")
    assert error.value.code == outcome[1]
    assert state["attributes"] == 0
    native.kernel.CloseHandle.assert_called_once()


@pytest.mark.parametrize("outcome", [(True, 1300), (False, 5)])
def test_debug_restoration_failure_is_reported_and_token_handle_still_closes(monkeypatch, outcome):
    api, native, _ = token_fixture(monkeypatch, restore_error=outcome)
    with pytest.raises(api.NativeEvidenceError) as error:
        with native.debug_privilege():
            pass
    assert error.value.code == outcome[1]
    native.kernel.CloseHandle.assert_called_once()


def test_debug_lookup_failure_closes_opened_token_before_inspection(monkeypatch):
    api, native, state = token_fixture(monkeypatch)
    native.security.LookupPrivilegeValueW.side_effect = lambda *args: False
    state["last_error"] = 5
    with pytest.raises(api.NativeEvidenceError):
        with native.debug_privilege():
            pytest.fail("Unresolved privilege entered the body")
    native.security.AdjustTokenPrivileges.assert_not_called()
    native.kernel.CloseHandle.assert_called_once()


def inspection_fixture(tmp_path, monkeypatch, fault):
    api = load("scm_stock_git_lifecycle")
    state = {"enabled": False, "captures": 0, "events": []}

    def privileges():
        return [{"name": "SeDebugPrivilege", "enabled": state["enabled"]}]

    @contextmanager
    def debug():
        state["enabled"] = fault != "not_enabled"
        try:
            yield
        finally:
            state["enabled"] = fault == "restore_mismatch"

    native = SimpleNamespace(debug_privilege=debug, privileges=privileges)

    def capture(*args):
        assert state["enabled"], "CIM read executed outside privilege scope"
        script = args[0][-1]
        assert "Security_.ImpersonationLevel=3" in script
        assert "Security_.Privileges.AddAsString('SeDebugPrivilege',$true)" in script
        state["captures"] += 1
        if fault == "capture":
            raise RuntimeError("capture failed")
        return {"exit_code": 0, "child_reaped": True, "timed_out": False,
                "output_limit_exceeded": False, "process_error": None}

    rows = [{"ProcessId": 77, "ParentProcessId": 17,
             "ExecutablePath": None if fault == "incomplete" else str(tmp_path / "java.exe"),
             "CommandLine": "fixed"}]
    probe = SimpleNamespace(capture=capture, _raw=lambda *args: json.dumps(rows).encode())

    def require(ok, message):
        if not ok:
            raise RuntimeError(message)

    worker = SimpleNamespace(Acceptance=object, require=require, save=Mock(),
                             wait_until=lambda check, *args: check())
    cls = api.acceptance_type(worker, None, probe, None, None, None, None)
    test = cls.__new__(cls)
    test.native, test.output, test.query_sequence = native, tmp_path, 0
    test.event = lambda name, **fields: state["events"].append((name, fields))
    monkeypatch.setattr(api.shutil, "which", lambda name: str(tmp_path / "pwsh.exe"))
    return test, state, rows, worker, api


@pytest.mark.parametrize("fault", ["valid", "capture", "incomplete", "restore_mismatch", "not_enabled"])
def test_process_inventory_requires_scoped_debug_and_restores_on_every_read_outcome(
    tmp_path, monkeypatch, fault
):
    test, state, rows, _, _ = inspection_fixture(tmp_path, monkeypatch, fault)
    if fault == "valid":
        assert test.processes() == rows
    else:
        with pytest.raises(RuntimeError):
            test.processes()
    assert state["enabled"] is (fault == "restore_mismatch")
    assert state["captures"] == (0 if fault == "not_enabled" else 1)
    if fault != "restore_mismatch":
        assert len(state["events"]) == 1
        _, proof = state["events"][0]
        assert proof["enabled_during"] is (fault != "not_enabled")
        assert proof["privileges_before"] == proof["privileges_after"]


def test_java_native_image_token_query_stays_in_the_same_scoped_inspection(tmp_path, monkeypatch):
    test, state, rows, worker, api = inspection_fixture(tmp_path, monkeypatch, "valid")
    test.runtime, test.scratch = tmp_path / "runtime", tmp_path / "scratch"
    rows[0]["ExecutablePath"] = str(test.runtime / "jdk/bin/java.exe")
    test.java_proofs = {}
    test.held = SimpleNamespace(pid=17)
    test.f = {"project_id": "fixture"}
    test.source = tmp_path / "source"
    test.current = lambda: {"status": {"state": 4}}
    test.publication = lambda: {"outbox": [{"event": {"status": "analyzed"}}]}

    def process(pid):
        assert state["enabled"] and pid == 77
        return {"pid": pid, "image": rows[0]["ExecutablePath"], "token_user_sid": "S-1-5-19"}

    def validate(row, actual, **kwargs):
        assert state["enabled"] and row["ProcessId"] == actual["pid"] == 77
        assert kwargs["service_pid"] == row["ParentProcessId"] == 17
        return actual

    test.native.process = process
    measurement = SimpleNamespace(validate_java=validate, validate_publication=lambda *a, **kw: {"commit": "a" * 40})
    def capture(*args):
        assert "Security_.Privileges.AddAsString('SeDebugPrivilege',$true)" in args[0][-1]
        return {"exit_code": 0, "child_reaped": True, "timed_out": False,
                "output_limit_exceeded": False, "process_error": None}
    probe = SimpleNamespace(capture=capture, _raw=lambda *a: json.dumps(rows).encode())
    cls = api.acceptance_type(worker, None, probe, None, None, None, measurement)
    test.__class__ = cls
    assert test.published("first", ["a" * 40], native_bsl=True) == {"commit": "a" * 40}
    assert test.java_proofs["first"]["token_user_sid"] == "S-1-5-19"
    assert state["enabled"] is False


@pytest.mark.parametrize("initial_enabled", [False, True])
@pytest.mark.parametrize("fault", ["valid", "base", "held", "restore_mismatch"])
def test_stock_service_start_scopes_both_native_token_reads_and_restores(
    tmp_path, monkeypatch, initial_enabled, fault
):
    test, state, _, worker, api = inspection_fixture(tmp_path, monkeypatch, "valid")
    state["enabled"] = initial_enabled
    state["reads"] = []

    @contextmanager
    def debug():
        state["enabled"] = True
        try:
            yield
        finally:
            state["enabled"] = not initial_enabled if fault == "restore_mismatch" else initial_enabled

    test.native.debug_privilege = debug

    class Base:
        def start(self):
            assert state["enabled"], "Base service token read executed outside privilege scope"
            state["reads"].append("base")
            if fault == "base":
                raise RuntimeError("base token read failed")
            return {"status": {"pid": 17}}

    def held(instance, actual_worker, pid):
        assert state["enabled"], "Held service token read executed outside privilege scope"
        assert instance is test and actual_worker is worker and pid == 17
        state["reads"].append("held")
        if fault == "held":
            raise RuntimeError("held token read failed")
        return SimpleNamespace(pid=pid)

    worker.Acceptance = Base
    cls = api.acceptance_type(worker, None, None, None, None, None, None)
    test = cls.__new__(cls)
    test.native = SimpleNamespace(debug_privilege=debug, privileges=lambda: [
        {"name": "SeDebugPrivilege", "enabled": state["enabled"]}
    ])
    test.event = lambda name, **fields: state["events"].append((name, fields))
    test.held, test.service_pids = None, set()
    monkeypatch.setattr(api, "HeldProcess", held)
    if fault == "valid":
        assert test.start() == {"status": {"pid": 17}}
    else:
        message = {"base": "base token read failed", "held": "held token read failed",
                   "restore_mismatch": "changed original token privileges"}[fault]
        with pytest.raises(RuntimeError, match=message):
            test.start()
    assert state["reads"] == (["base"] if fault == "base" else ["base", "held"])
    assert state["enabled"] is (not initial_enabled if fault == "restore_mismatch" else initial_enabled)
    assert len(state["events"]) == 1
    name, proof = state["events"][0]
    assert name == "stock_debug_privilege_inspected" and proof["enabled_during"] is True
    assert proof["privileges_restored"] is (fault != "restore_mismatch")
    assert (test.held is not None) is (fault in {"valid", "restore_mismatch"})
    assert test.service_pids == ({17} if test.held is not None else set())
