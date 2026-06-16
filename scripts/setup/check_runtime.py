
#!/usr/bin/env python3
"""Utility to verify that Python 3.11 runtime is available on the host."""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Iterable, List

CANDIDATE_COMMANDS: List[List[str]] = [
    ["py", "-3.11", "-c", "import sys; print(sys.version)",],
    ["python3.11", "--version"],
    ["python3", "--version"],
    ["python", "--version"],
]

REQUIRED_MAJOR = 3
REQUIRED_MINOR = 11


def _check_command(command: Iterable[str]) -> bool:
    executable = command[0]
    if shutil.which(executable) is None:
        return False
    try:
        result = subprocess.run(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return False

    version_output = result.stdout.strip()
    if not version_output:
        return False

    words = version_output.split()
    version_str = next((word for word in words if word[0].isdigit()), "")
    if not version_str:
        return False

    major_minor = version_str.split(".")[:2]
    if len(major_minor) < 2:
        return False

    major, minor = map(int, major_minor)
    return major == REQUIRED_MAJOR and minor == REQUIRED_MINOR


def ensure_python_311_available() -> None:
    for command in CANDIDATE_COMMANDS:
        if _check_command(command):
            print(
                "[runtime] Python 3.11 detected via command: "
                + " ".join(command[:-2] if command[-2:] == ["-c", "import sys; print(sys.version)"] else command)
            )
            return

    host = platform.platform()
    message = (
        "Python 3.11.x runtime not found.\n"
        "Please install CPython 3.11 (64-bit) and ensure it is available via "
        "`py -3.11`, `python3.11` or `python`.\n"
        "See docs/setup/python_311.md for installation instructions.\n"
        f"Detected platform: {host}\n"
    )
    raise SystemExit(message)


def warn_tool_availability() -> None:
    """
    Print warnings about optional tooling required for full developer experience.

    - GNU Make (Linux/macOS)
    - Docker / Docker Desktop
    """
    # Check make (not critical on Windows, поэтому только предупреждение)
    if shutil.which("make") is None:
        print("[runtime] WARNING: 'make' not found in PATH. Some helper targets (make test, make servers, …) may not be available.")
    else:
        print("[runtime] make detected in PATH")

    # Check docker client
    if shutil.which("docker") is None:
        print("[runtime] WARNING: 'docker' not found in PATH. Docker-based workflows (docker-compose, observability stack) will not work.")
    else:
        print("[runtime] docker client detected in PATH")


if __name__ == "__main__":
    ensure_python_311_available()
    warn_tool_availability()
