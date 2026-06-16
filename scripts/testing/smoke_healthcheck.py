
#!/usr/bin/env python3
"""
Lightweight smoke checks to validate core tooling without full deployment.

Steps performed:
    1. Compile critical Python modules (`src/main.py`, `src/ai/mcp_server.py`).
    2. Run spec-driven validation (`scripts/research/check_feature.py`).
    3. Ensure release automation script imports successfully.

Return codes:
    0 - success, all checks passed.
    1 - failure.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import requests
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=cwd or ROOT, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print("[smoke] Command failed:", " ".join(cmd))
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)


def check_compile() -> None:
    run([sys.executable, "-m", "compileall", "src/main.py", "src/ai/mcp_server.py"])
    print("[smoke] Python modules compiled successfully")


def check_spec_workflow() -> None:
    run([sys.executable, "scripts/research/check_feature.py"])
    print("[smoke] Spec-driven documents validated")


def check_release_script() -> None:
    run([sys.executable, "-m", "compileall", "scripts/release/create_release.py"])
    print("[smoke] Release script import check passed")


def check_fastapi_health() -> None:
    sys.path.insert(0, str(ROOT))
    try:
        os.environ.setdefault("IGNORE_PY_VERSION_CHECK", "1")
        from src.main import app  # noqa: WPS433
    finally:
        sys.path.pop(0)

    with TestClient(app) as client:
        response = client.get("/health")
        if response.status_code != 200:
            print("[smoke] Health check failed", response.status_code, response.text)
            raise SystemExit(1)
        print("[smoke] FastAPI /health reachable (in-memory)")


def check_deployed_health() -> None:
    try:
        response = requests.get("http://localhost:8080/health", timeout=3)
        if response.status_code == 200:
            print("[smoke] External /health reachable (docker-compose)")
            return
        print("[smoke] External /health returned", response.status_code)
    except requests.RequestException as exc:
        print(f"[smoke] External health check failed: {exc}")
    print("[smoke] Hint: run 'make smoke-up' before smoke-tests to verify docker service.")


def main() -> int:
    check_compile()
    check_spec_workflow()
    check_release_script()
    check_fastapi_health()
    check_deployed_health()
    print("[smoke] All smoke checks completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
