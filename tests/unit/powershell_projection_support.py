"""Bound startup separately from execution; never retry the projection."""
import os
import subprocess
import time


def run_after_ready(argv, ready_path, *, startup_timeout=30, execution_timeout=10):
    if ready_path.exists():
        raise AssertionError("Refusing a stale PowerShell readiness marker")
    env = {**os.environ, "POWERSHELL_TELEMETRY_OPTOUT": "1", "POWERSHELL_UPDATECHECK": "Off"}
    phase, limit = "startup/fixture preparation", startup_timeout
    with subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env) as process:
        try:
            deadline = time.monotonic() + startup_timeout
            while not ready_path.is_file():
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    raise AssertionError(f"PowerShell exited before readiness ({process.returncode}): "
                                         f"{stderr[-4096:]!r}; stdout={stdout[-4096:]!r}")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, startup_timeout)
                time.sleep(min(0.01, remaining))
            phase, limit = "projection execution", execution_timeout
            stdout, stderr = process.communicate(input=b"RUN\n", timeout=execution_timeout)
        except subprocess.TimeoutExpired as error:
            process.kill()
            stdout, stderr = process.communicate()
            raise AssertionError(f"PowerShell {phase} timed out after {limit}s; no retry. "
                                 f"stderr={stderr[-4096:]!r}; stdout={stdout[-4096:]!r}") from error
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.communicate()
            raise
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
