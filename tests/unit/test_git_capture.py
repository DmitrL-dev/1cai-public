"""Actual pipe/child boundary contracts; no Git/SCM/native BSL acceptance."""
import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest


def api():
    return importlib.import_module('rentgen_core._git_capture')


@pytest.fixture
def children(monkeypatch):
    actual, spawn = [], subprocess.Popen

    def track(command, **kwargs):
        child = spawn(command, **kwargs)
        actual.append(child)
        return child

    monkeypatch.setattr(subprocess, 'Popen', track)
    yield actual
    # Only inspect the same owned Popen handle; never signal a PID by number.
    assert all(child.poll() is not None and child.stdout.closed for child in actual)


def run(code, limit, timeout=3):
    return api().capture_git([sys.executable, '-I', '-c', code], env=dict(os.environ),
        max_stdout=limit, timeout=timeout)


@pytest.mark.parametrize('size,limit', [(0, 0), (31, 32), (32, 32), (65536, 65536)])
def test_exact_output_boundary_preserves_binary_bytes_and_reaps(children, size, limit):
    result = run('import os; os.write(1, b"x" * ' + str(size) + ')', limit)
    assert result.stdout == b'x' * size and result.returncode == 0
    assert len(children) == 1


@pytest.mark.parametrize('size,limit', [(1, 0), (33, 32), (1048576, 32)])
def test_overflow_retains_only_limit_plus_one_and_reaps_same_child(children, size, limit):
    with pytest.raises(api().GitOutputLimitExceeded) as error:
        run('import os,time; os.write(1, b"x" * ' + str(size) + '); time.sleep(30)', limit)
    assert error.value.limit == limit and error.value.stdout == b'x' * (limit + 1)
    assert len(children) == 1


@pytest.mark.parametrize('prefix', [b'', b'partial'])
def test_timeout_keeps_bounded_partial_output_and_reaps_same_child(children, prefix):
    with pytest.raises(subprocess.TimeoutExpired) as error:
        run('import os,time; os.write(1, ' + repr(prefix) + '); time.sleep(30)', 32, timeout=0.5)
    assert error.value.output == prefix and len(children) == 1


def test_nonzero_exit_and_discarded_stderr_do_not_deadlock(children):
    result = run('import os,sys; os.write(2,b"e"*1048576); os.write(1,b"out"); sys.exit(7)', 32)
    assert result.returncode == 7 and result.stdout == b'out' and result.stderr is None
    assert len(children) == 1


@pytest.mark.parametrize('limit', [-1, True, 1.0, 67108865])
def test_invalid_limit_refused_before_process(children, limit):
    with pytest.raises(ValueError):
        run('raise AssertionError("must not launch")', limit)
    assert children == []


@pytest.mark.parametrize('timeout', [0, -1, True, float('inf'), float('nan')])
def test_invalid_timeout_refused_before_process(children, timeout):
    with pytest.raises(ValueError):
        run('raise AssertionError("must not launch")', 32, timeout)
    assert children == []


def test_missing_executable_does_not_leave_process_or_pipe(children, tmp_path):
    with pytest.raises(OSError):
        api().capture_git([str(tmp_path / 'missing.exe')], env=dict(os.environ), max_stdout=32)
    assert children == []


def test_exit_between_empty_peek_and_poll_cannot_drop_final_bytes(monkeypatch):
    import tempfile

    class Child:
        stdout = tempfile.TemporaryFile()
        returncode = None
        waits = 0

        def poll(self):
            return self.returncode

        def wait(self):
            self.waits += 1
            return self.returncode

        def kill(self):
            pytest.fail('already exited child was killed')

    child = Child()
    reads = []

    def available(stream, count):
        reads.append(count)
        if len(reads) == 1:
            # A child writes its last bytes and exits just after an empty peek.
            child.returncode = 0
            return None
        return b'last bytes' if len(reads) == 2 else b''

    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: child)
    monkeypatch.setattr(api(), '_read_available', available)
    result = api().capture_git(['fixed-test-child'], env={}, max_stdout=32)
    assert result.stdout == b'last bytes' and child.waits == 1 and child.stdout.closed
