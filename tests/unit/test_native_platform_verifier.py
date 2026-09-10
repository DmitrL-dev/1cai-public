"""Failure handling of the opt-in host verifier; these do not emulate 1C."""
import importlib.util
from pathlib import Path
import subprocess

import pytest


spec = importlib.util.spec_from_file_location(
    "native_verifier",
    Path(__file__).resolve().parents[2]
    / "scripts/verification/verify_native_platform.py",
)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
pytestmark = pytest.mark.skipif(native.os.name != "nt", reason="Windows process runner")


@pytest.fixture
def runner(tmp_path):
    executable = tmp_path / "1cv8.exe"
    executable.write_bytes(b"not executed by these unit tests")
    return native.PlatformRun(executable, tmp_path / "owned", 5)


def test_existing_output_is_not_reused(tmp_path):
    executable = tmp_path / "1cv8.exe"
    executable.write_bytes(b"fixture")
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "user-file"
    marker.write_bytes(b"preserve")
    with pytest.raises(FileExistsError):
        native.PlatformRun(executable, output, 5)
    assert marker.read_bytes() == b"preserve"
    assert sorted(p.name for p in output.iterdir()) == ["user-file"]


@pytest.mark.parametrize("failure", [KeyboardInterrupt, subprocess.TimeoutExpired])
def test_interrupt_and_timeout_terminate_only_owned_child(runner, monkeypatch, failure):
    class Child:
        pid = 987654
        returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            if self.returncode is None:
                if failure is KeyboardInterrupt:
                    raise KeyboardInterrupt()
                raise subprocess.TimeoutExpired("owned", timeout)
            return self.returncode

    child = Child()
    kills = []
    monkeypatch.setattr(native.subprocess, "Popen", lambda *a, **k: child)

    def kill(arguments, **kwargs):
        kills.append(arguments)
        child.returncode = 1

    monkeypatch.setattr(native.subprocess, "run", kill)
    expected = KeyboardInterrupt if failure is KeyboardInterrupt else RuntimeError
    with pytest.raises(expected):
        runner.command("timeout", ["DESIGNER"])
    assert kills == [["taskkill", "/PID", "987654", "/T", "/F"]]
    assert child.returncode == 1
    assert not (runner.output / "acceptance.json").exists()


def test_stale_runtime_result_is_rejected_before_launch(runner, monkeypatch):
    (runner.output / "execute.txt").write_text("42", "utf-8")
    monkeypatch.setattr(
        runner, "command", lambda *a, **k: pytest.fail("Must not launch")
    )
    with pytest.raises(FileExistsError):
        runner.execute("execute", 42)


@pytest.mark.parametrize(
    "exit_code,log",
    [
        (0, ""),
        (1, native.MODULE + "(2,16): startup failed"),
        (101, "AnotherModule(2,16): syntax error"),
    ],
)
def test_unrelated_failure_is_not_accepted_as_compiler_evidence(
    runner, monkeypatch, exit_code, log
):
    class Child:
        returncode = exit_code

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            return self.returncode

    def launch(*args, **kwargs):
        (runner.output / "broken.log").write_text(log, "utf-8")
        return Child()

    monkeypatch.setattr(native.subprocess, "Popen", launch)
    with pytest.raises(RuntimeError, match="expected compiler rejection"):
        runner.command("broken", ["DESIGNER"], expect_error=True)
