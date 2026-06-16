#!/usr/bin/env python3
"""
Execute BSL / 1C test suites described in a manifest file.

The manifest is a JSON array where each element describes a test runner:
[
  {
    "name": "yaxunit-smoke",
    "command": ["oscript", "tools/yaxunit/src/cli/yaxunit-runner.os", "--workspace", "path/to/project"],
    "working_directory": "tests/bsl/yaxunit-smoke",
    "env": {
      "YAXUNIT_OPTS": "--report=junit --output=reports"
    },
    "timeout": 1800
  }
]

If the manifest file is missing, the script exits successfully (skipped run) so
that CI pipelines remain green until real suites are configured.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Sequence

DEFAULT_MANIFEST = Path("tests/bsl/testplan.json")
DEFAULT_ARTIFACT_DIR = Path("output/bsl-tests")

# Kill switch + executable allow-list (RCE-by-manifest defense-in-depth).
# A manifest is caller-supplied data: every command it lists is otherwise run
# verbatim as an OS process. We refuse to run anything unless an operator has
# opted in on the host, and we only ever spawn known test-runner binaries.
TEST_EXECUTION_FLAG = "RENTGEN_ENABLE_TEST_EXECUTION"
ALLOWED_EXECUTABLE_BASENAMES = frozenset(
    {
        "python",
        "python3",
        "python.exe",
        "pythonw.exe",
        "oscript",
        "oscript.exe",
        "1cv8",
        "1cv8.exe",
        "1cv8c",
        "1cv8c.exe",
        "vanessa-runner",
        "vanessa-runner.exe",
        "1ctestc",
        "1ctestc.exe",
    }
)


def _execution_enabled() -> bool:
    return os.getenv(TEST_EXECUTION_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


def _executable_allowed(command: Sequence[str]) -> bool:
    if not command:
        return False
    basename = Path(str(command[0]).replace("\\", "/")).name.casefold()
    return basename in {item.casefold() for item in ALLOWED_EXECUTABLE_BASENAMES}


class TestCase:
    def __init__(
        self,
        name: str,
        command: Sequence[str],
        working_directory: Path | None = None,
        env: Dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> None:
        self.name = name
        self.command = list(command)
        self.working_directory = working_directory
        self.env = env or {}
        self.timeout = timeout

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "TestCase":
        try:
            name = str(payload["name"])
            command_raw = payload["command"]
        except KeyError as exc:
            raise ValueError(f"Manifest entry missing required key: {exc}") from exc

        if not isinstance(command_raw, list) or not command_raw:
            raise ValueError(f"Manifest entry '{name}' must contain non-empty 'command' array")

        command = [str(part) for part in command_raw]
        working_directory = None
        if payload.get("working_directory"):
            working_directory = Path(str(payload["working_directory"]))
        env = None
        if payload.get("env"):
            env = {str(k): str(v) for k, v in dict(payload["env"]).items()}
        timeout = None
        if payload.get("timeout"):
            timeout = int(payload["timeout"])
        return cls(name=name, command=command, working_directory=working_directory, env=env, timeout=timeout)


def load_manifest(manifest_path: Path) -> List[TestCase]:
    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("Manifest root must be a JSON array")
    return [TestCase.from_dict(item) for item in payload]


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_test_case(case: TestCase, artifact_dir: Path) -> int:
    log_path = artifact_dir / f"{case.name}.log"
    ensure_directory(log_path.parent)

    if not _executable_allowed(case.command):
        message = (
            f"Refusing to run '{case.name}': executable "
            f"'{case.command[0] if case.command else ''}' is not in the allow-list "
            f"{sorted(ALLOWED_EXECUTABLE_BASENAMES)}."
        )
        print(f"[run_bsl_tests] {message}")
        log_path.write_text(message + "\n", encoding="utf-8")
        return 126

    env = os.environ.copy()
    env.update(case.env)

    cwd = None
    if case.working_directory:
        cwd = case.working_directory
        cwd.mkdir(parents=True, exist_ok=True)

    print(f"[run_bsl_tests] Running '{case.name}': {' '.join(case.command)}")
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            process = subprocess.run(
                case.command,
                cwd=cwd,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                timeout=case.timeout,
                check=False,
            )
        exit_code = process.returncode
    except FileNotFoundError as exc:
        log_path.write_text(f"Runner not found: {exc}\n", encoding="utf-8")
        exit_code = 127
    except subprocess.TimeoutExpired as exc:
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"Timed out after {exc.timeout} seconds\n")
        exit_code = 124

    status = "PASSED" if exit_code == 0 else f"FAILED (code {exit_code})"
    print(f"[run_bsl_tests] {case.name}: {status} → {log_path}")
    return exit_code


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run BSL/YAxUnit test suites defined in a manifest.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Path to JSON manifest (default: {DEFAULT_MANIFEST})",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"Directory to store logs and reports (default: {DEFAULT_ARTIFACT_DIR})",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    manifest_path: Path = args.manifest
    artifact_dir: Path = args.artifacts_dir

    if not manifest_path.exists():
        print(f"[run_bsl_tests] Manifest '{manifest_path}' not found. Skipping BSL test execution.")
        return 0

    try:
        test_cases = load_manifest(manifest_path)
    except Exception as exc:  # noqa: BLE001
        print(f"[run_bsl_tests] Failed to parse manifest: {exc}")
        return 2

    if not test_cases:
        print("[run_bsl_tests] Manifest is empty – nothing to run.")
        return 0

    if not _execution_enabled():
        print(
            "[run_bsl_tests] Test execution is disabled. "
            f"Set {TEST_EXECUTION_FLAG}=1 on the host to allow manifest execution. Refusing to run."
        )
        return 3

    ensure_directory(artifact_dir)

    failures = 0
    for case in test_cases:
        exit_code = run_test_case(case, artifact_dir)
        if exit_code != 0:
            failures += 1

    if failures:
        print(f"[run_bsl_tests] Completed with {failures} failing test runner(s).")
        return 1

    print("[run_bsl_tests] All BSL test runners completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

