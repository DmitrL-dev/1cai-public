
"""
Utility script to run Code Review API tests sequentially with per-test timeout
and store structured results in JSON for further analysis.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "output" / "code_review_test_results.json"

# Node IDs for targeted tests (focus on /api/code-review/analyze)
TESTS: List[str] = [
    "tests/unit/test_code_review_api.py::test_analyze_bsl_code_empty",
    "tests/unit/test_code_review_api.py::test_analyze_bsl_code_detects_issues",
    "tests/unit/test_code_review_api.py::test_analyze_code_endpoint_without_ai",
    "tests/unit/test_code_review_api.py::test_analyze_code_endpoint_with_ai",
]

DEFAULT_TIMEOUT = int(os.getenv("CODE_REVIEW_TEST_TIMEOUT", "15"))
PYTEST_BASE_CMD = [
    sys.executable,
    "-m",
    "pytest",
    "--maxfail=1",
    "-q",
    "--disable-warnings",
    "--no-cov",
    f"--timeout={DEFAULT_TIMEOUT}",
]


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 50] + "\n...[truncated]..."


def run_test(node_id: str) -> Dict[str, Any]:
    start = time.perf_counter()
    result: Dict[str, Any] = {
        "id": node_id,
        "status": "unknown",
        "duration_seconds": None,
        "return_code": None,
        "stdout": "",
        "stderr": "",
    }

    cmd = PYTEST_BASE_CMD + [node_id]
    try:
        completed = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT * 4,  # allow pytest to manage per-test timeout first
            check=False,
        )
        duration = time.perf_counter() - start
        result["duration_seconds"] = round(duration, 4)
        result["return_code"] = completed.returncode
        result["stdout"] = truncate(completed.stdout)
        result["stderr"] = truncate(completed.stderr)

        if completed.returncode == 0:
            result["status"] = "passed"
        else:
            combined_output = (completed.stdout or "") + (completed.stderr or "")
            if "Failed: Timeout" in combined_output or "Timeout >" in combined_output:
                result["status"] = "timeout"
            else:
                result["status"] = "failed"
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - start
        result["duration_seconds"] = round(duration, 4)
        result["status"] = "runner_timeout"
        result["stdout"] = truncate(exc.stdout or "")
        result["stderr"] = truncate(exc.stderr or "")
        result["return_code"] = None

    return result


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    test_results = [run_test(node_id) for node_id in TESTS]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timeout_seconds": DEFAULT_TIMEOUT,
        "tests": test_results,
    }

    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Test results saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

