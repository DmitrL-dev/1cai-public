"""Mandatory Windows byte locks must be acquired before touching their bytes."""
import errno
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from rentgen_core import git_watcher
from rentgen_core.errors import CoreError


@pytest.mark.parametrize("mode", ["busy", "empty", "existing"])
def test_windows_lock_protocol_never_reads_or_initializes_unowned_byte(tmp_path, monkeypatch, mode):
    box = git_watcher.NotificationOutbox(tmp_path / "outbox.json")
    lock_path = box.path.with_name(box.path.name + ".lock")
    if mode != "empty":
        lock_path.write_bytes(b"0")
    owned = False
    attempts = []
    descriptor_stream = os.fdopen

    class GuardedStream:
        def __init__(self, fd, mode):
            self.stream = descriptor_stream(fd, mode)

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def read(self, count):
            if not owned:
                raise PermissionError(errno.EACCES, "Permission denied")
            return self.stream.read(count)

        def write(self, value):
            if not owned:
                raise PermissionError(errno.EACCES, "Permission denied")
            return self.stream.write(value)

    class WindowsOS:
        name = "nt"
        fdopen = GuardedStream

        def __getattr__(self, name):
            return getattr(os, name)

    def locking(fd, operation, count):
        nonlocal owned
        assert count == 1 and os.lseek(fd, 0, os.SEEK_CUR) == 0
        attempts.append(operation)
        if operation == 1:
            if mode == "busy":
                raise PermissionError(errno.EACCES, "Permission denied")
            assert not owned
            owned = True
        else:
            assert operation == 2 and owned
            owned = False

    monkeypatch.setattr(git_watcher, "os", WindowsOS())
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(locking=locking, LK_NBLCK=1, LK_UNLCK=2))
    monkeypatch.setattr(git_watcher, "time", SimpleNamespace(sleep=lambda _: None))
    if mode == "busy":
        with pytest.raises(CoreError) as error:
            box.peek()
        assert error.value.code == "GIT_WATCHER_NOTIFICATION_BUSY"
        assert attempts == [1] * 20 and lock_path.read_bytes() == b"0"
    else:
        with box._locked():
            assert owned and lock_path.stat().st_size == 1
        assert attempts == [1, 2] and lock_path.read_bytes() == b"0"
    assert not owned and not box.path.exists()


@pytest.mark.skipif(os.name != "nt", reason="Real Windows mandatory byte locks")
@pytest.mark.parametrize("empty", [False, True])
def test_other_process_lock_yields_bounded_busy_then_recovers_without_data_loss(tmp_path, empty):
    box = git_watcher.NotificationOutbox(tmp_path / "outbox.json")
    lock_path = box.path.with_name(box.path.name + ".lock")
    lock_path.write_bytes(b"" if empty else b"0")
    ready = tmp_path / "ready"
    child = subprocess.Popen([sys.executable, "-c", """
import msvcrt, sys
from pathlib import Path
with open(sys.argv[1], 'r+b', buffering=0) as stream:
    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    Path(sys.argv[2]).write_text('locked')
    sys.stdin.readline()
    stream.seek(0)
    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
""", str(lock_path), str(ready)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), "child did not acquire the byte lock"
        if not empty:
            # This is the old initialization probe: Windows refuses it before
            # the outbox can reach its bounded lock acquisition loop.
            with lock_path.open("rb") as stream, pytest.raises(PermissionError):
                stream.read(1)
        with pytest.raises(CoreError) as error:
            box.peek()
        assert error.value.code == "GIT_WATCHER_NOTIFICATION_BUSY"
        assert not box.path.exists()
    finally:
        try:
            stdout, stderr = child.communicate("release\n", timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate(timeout=10)
            raise
    assert child.returncode == 0, (stdout, stderr)
    assert box.peek() == []
    identifier = box.enqueue({"status": "analyzed", "commit": "a" * 40})
    assert box.peek()[0]["id"] == identifier == 1
    box.ack(identifier)
    assert box.peek() == []
