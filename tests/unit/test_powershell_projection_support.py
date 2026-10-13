"""Real child-process regressions; no pwsh, account, or network required."""
import os
import sys

import pytest

from powershell_projection_support import run_after_ready


def child(tmp_path, *, startup=0, execution=0, status=0, ready=True):
    marker = tmp_path / "ready"
    script = ("import pathlib,sys,time\n"
              f"time.sleep({startup!r})\n"
              + (f"pathlib.Path({str(marker)!r}).write_text('ready')\n" if ready else "")
              + "assert sys.stdin.readline() == 'RUN\\n'\n"
              + f"time.sleep({execution!r})\nprint('RESULT')\nsys.exit({status!r})\n")
    return [sys.executable, "-c", script], marker


def test_slow_startup_does_not_consume_execution_budget(tmp_path):
    argv, marker = child(tmp_path, startup=1.2)
    result = run_after_ready(argv, marker, startup_timeout=10, execution_timeout=1)
    assert result.returncode == 0
    assert result.stdout == b"RESULT" + os.linesep.encode("ascii")


def test_execution_remains_bounded_without_retry(tmp_path):
    argv, marker = child(tmp_path, execution=5)
    with pytest.raises(AssertionError, match="projection execution timed out.*no retry"):
        run_after_ready(argv, marker, startup_timeout=5, execution_timeout=0.1)


def test_startup_remains_bounded(tmp_path):
    argv, marker = child(tmp_path, ready=False)
    with pytest.raises(AssertionError, match="startup/fixture preparation timed out"):
        run_after_ready(argv, marker, startup_timeout=0.2)


def test_nonzero_exit_is_not_normalized(tmp_path):
    argv, marker = child(tmp_path, status=7)
    assert run_after_ready(argv, marker).returncode == 7


def test_exit_before_readiness_is_failure(tmp_path):
    with pytest.raises(AssertionError, match="exited before readiness.*9"):
        run_after_ready([sys.executable, "-c", "import sys;sys.exit(9)"], tmp_path / "ready")


def test_stale_readiness_is_rejected(tmp_path):
    marker = tmp_path / "ready"
    marker.write_text("stale")
    with pytest.raises(AssertionError, match="stale"):
        run_after_ready(["must-not-start"], marker)
