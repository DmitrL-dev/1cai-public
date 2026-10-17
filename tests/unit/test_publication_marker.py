"""Boundary marker transport, including real Windows sharing-denial recovery."""
import ctypes
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import publication_kill_support as support
from test_publication_process_kill import project, request, counts


@pytest.fixture
def marker(tmp_path):
    value = {"boundary": "before_commit", "pid": 123}
    (tmp_path / "ready.json").write_text(json.dumps(value), encoding="utf-8")
    (tmp_path / "child.log").write_text("child diagnostic", encoding="utf-8")
    child = SimpleNamespace(pid=123, poll=lambda: None)
    return child, tmp_path, value


def test_windows_marker_denial_retries_without_restarting_publisher(marker, monkeypatch):
    child, directory, value = marker
    original = Path.read_text
    calls = []
    def read(path, *args, **kwargs):
        if path.name == "ready.json":
            calls.append(path)
            if len(calls) == 1:
                raise PermissionError(13, "injected marker open denial", str(path))
        return original(path, *args, **kwargs)
    monkeypatch.setattr(support, "_WINDOWS_MARKERS", True)
    monkeypatch.setattr(Path, "read_text", read)
    assert support._wait_for_marker(child, directory, timeout=1) == value
    assert len(calls) == 2


@pytest.mark.parametrize("fault", ["missing", "denied"])
def test_unreadable_marker_times_out(marker, monkeypatch, fault):
    child, directory, _ = marker
    reads = []
    def read(*args, **kwargs):
        reads.append(1)
        raise (FileNotFoundError if fault == "missing" else PermissionError)(13, fault)
    monkeypatch.setattr(support, "_WINDOWS_MARKERS", True)
    monkeypatch.setattr(Path, "read_text", read)
    clock = iter([0, 0, 1])
    monkeypatch.setattr(support.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(support.time, "sleep", lambda seconds: None)
    with pytest.raises(AssertionError, match="readable boundary marker"):
        support._wait_for_marker(child, directory, timeout=1)
    assert len(reads) == 1


def test_posix_permission_error_is_not_retried(marker, monkeypatch):
    child, directory, _ = marker
    monkeypatch.setattr(support, "_WINDOWS_MARKERS", False)
    def read(*args, **kwargs):
        raise PermissionError(13, "denied")
    monkeypatch.setattr(Path, "read_text", read)
    with pytest.raises(PermissionError):
        support._wait_for_marker(child, directory, timeout=1)


def test_malformed_marker_is_not_retried(marker, monkeypatch):
    child, directory, _ = marker
    (directory / "ready.json").write_text("{", encoding="utf-8")
    monkeypatch.setattr(support, "_WINDOWS_MARKERS", True)
    with pytest.raises(json.JSONDecodeError):
        support._wait_for_marker(child, directory, timeout=1)


def test_exited_publisher_cannot_supply_successful_marker(marker):
    child, directory, _ = marker
    child.poll = lambda: 1
    with pytest.raises(AssertionError, match="child diagnostic"):
        support._wait_for_marker(child, directory, timeout=1)


def test_injected_denial_with_actual_publisher(project, tmp_path, monkeypatch):
    """Real storage child; modeled first marker-open denial, not native IO proof."""
    original = Path.read_text
    denied = []
    def read(path, *args, **kwargs):
        if path.name == "ready.json" and path.exists() and not denied:
            denied.append(path)
            raise PermissionError(13, "injected marker open denial", str(path))
        return original(path, *args, **kwargs)
    monkeypatch.setattr(support, "_WINDOWS_MARKERS", True)
    monkeypatch.setattr(Path, "read_text", read)
    directory = tmp_path / "child"
    with support.killed_publisher(directory, request(project, "before_commit")) as value:
        assert value["boundary"] == "before_commit"
        assert counts(project[0]) == (0, 0, 0, 0)
    assert denied == [directory / "ready.json"]
    assert counts(project[0]) == (0, 0, 0, 0)
    assert not (directory / "ack.json").exists()
    assert not (directory / "unwound").exists()


@pytest.mark.skipif(os.name != "nt", reason="Actual Win32 exclusive file handle")
def test_real_windows_sharing_denial_then_readable_marker(marker, monkeypatch):
    from ctypes import wintypes
    child, directory, value = marker
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes, close.restype = [wintypes.HANDLE], wintypes.BOOL
    handle = create(str(directory / "ready.json"), 0x80000000, 0, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    original = Path.read_text
    denials = []
    def read(path, *args, **kwargs):
        nonlocal handle
        try:
            return original(path, *args, **kwargs)
        except PermissionError:
            denials.append(path)
            assert close(handle), ctypes.get_last_error()
            handle = None
            raise
    monkeypatch.setattr(Path, "read_text", read)
    try:
        assert support._wait_for_marker(child, directory, timeout=5) == value
        assert denials == [directory / "ready.json"]
    finally:
        if handle is not None:
            assert close(handle), ctypes.get_last_error()
