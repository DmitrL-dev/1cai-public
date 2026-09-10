"""Real Windows process trees, including abrupt controller termination."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows process ownership")


def wait_file(path, timeout=10):
    deadline = time.monotonic() + timeout
    while not path.exists() or not path.read_text():
        if time.monotonic() >= deadline:
            raise AssertionError("Owned fixture did not signal")
        time.sleep(0.05)
    return path.read_text()


def test_owned_parent_and_descendant_are_stopped_on_context_exit(tmp_path):
    from rentgen_core.native_process import OwnedProcess

    marker = tmp_path / "child.pid"
    child = "import time;time.sleep(120)"
    code = f"import subprocess,sys,pathlib,time;p=subprocess.Popen([sys.executable,'-c',{child!r}]);pathlib.Path({str(marker)!r}).write_text(str(p.pid));time.sleep(120)"
    with (tmp_path / "stdout").open("wb") as out, (tmp_path / "stderr").open(
        "wb"
    ) as err:
        with OwnedProcess(
            subprocess.list2cmdline([sys.executable, "-c", code]),
            sys.executable,
            out,
            err,
        ) as process:
            wait_file(marker)
            # A venv launcher and console host can add more owned processes.
            assert process.job.active() >= 2
        assert process.returncode is not None


def test_abrupt_controller_death_kills_child_without_cooperative_finally(tmp_path):
    marker = tmp_path / "running"
    pidfile = tmp_path / "owned.pid"
    script = tmp_path / "controller.py"
    script.write_text(
        """
import subprocess,sys,pathlib,time
from rentgen_core.native_process import OwnedProcess
root=pathlib.Path(sys.argv[1])
out=(root/'stdout').open('wb');err=(root/'stderr').open('wb')
child="import pathlib,time;pathlib.Path("+repr(str(root/'running'))+").write_text('yes');time.sleep(120)"
p=OwnedProcess(subprocess.list2cmdline([sys.executable,'-c',child]),sys.executable,out,err)
(root/'owned.pid').write_text(str(p.pid))
time.sleep(120)
""",
        "utf-8",
    )
    controller = subprocess.Popen(
        [sys._base_executable, str(script), str(tmp_path)],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
    )
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = None
    try:
        wait_file(marker)
        handle = kernel.OpenProcess(0x100000, False, int(wait_file(pidfile)))
        assert handle
        controller.kill()  # Intentionally no taskkill /T: the job must kill its child.
        controller.wait(timeout=10)
        assert kernel.WaitForSingleObject(handle, 10000) == 0
    finally:
        if controller.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(controller.pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
            )
            controller.wait(timeout=15)
        if handle:
            kernel.CloseHandle(handle)


def test_exit_code_and_literal_arguments_and_failed_spawn(tmp_path):
    from rentgen_core.native_process import OwnedProcess

    with (tmp_path / "stdout").open("wb") as out, (tmp_path / "stderr").open(
        "wb"
    ) as err:
        with OwnedProcess(
            subprocess.list2cmdline(
                [
                    sys.executable,
                    "-c",
                    "import sys;print(sys.argv[1]);sys.exit(7)",
                    'literal $() & " кириллица',
                ]
            ),
            sys.executable,
            out,
            err,
        ) as process:
            assert process.wait(timeout=10) == 7
        with pytest.raises(OSError):
            OwnedProcess("missing.exe", str(tmp_path / "missing.exe"), out, err)
    assert (tmp_path / "stdout").read_text().strip() == 'literal $() & " кириллица'


def test_child_is_born_in_project_and_command_jobs(tmp_path):
    from rentgen_core.native_process import OwnedProcess
    from rentgen_core.native_resources import project_slot

    with project_slot(tmp_path) as job:
        with (tmp_path / "stdout").open("wb") as out, (tmp_path / "stderr").open(
            "wb"
        ) as err:
            with OwnedProcess(
                subprocess.list2cmdline(
                    [sys._base_executable, "-c", "import time;time.sleep(120)"]
                ),
                sys._base_executable,
                out,
                err,
                parent_job=job,
            ) as process:
                assert job.active() >= 1
                assert process.poll() is None
            assert job.active() == 0
