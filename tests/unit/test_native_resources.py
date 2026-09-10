"""Native admission and scratch cleanup use real local files and Windows locks."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from rentgen_core.errors import CoreError

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows native resources")


def test_gate_refuses_another_process_and_releases_on_exit(tmp_path):
    from rentgen_core.native_resources import project_slot

    code = "from pathlib import Path;from rentgen_core.native_resources import project_slot;from rentgen_core.errors import CoreError;import sys\ntry:\n with project_slot(Path(sys.argv[1])): print('acquired')\nexcept CoreError as e: print(e.code)"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
    with project_slot(tmp_path):
        result = subprocess.check_output(
            [sys.executable, "-c", code, str(tmp_path)], env=env, timeout=10
        )
        assert result.strip() == b"NATIVE_EXECUTOR_BUSY"
    assert (
        subprocess.check_output(
            [sys.executable, "-c", code, str(tmp_path)], env=env, timeout=10
        ).strip()
        == b"acquired"
    )


@pytest.mark.parametrize("namespace", ["test-runs", "metadata-runs"])
def test_budget_refuses_new_work_and_detects_growth(tmp_path, namespace):
    from rentgen_core.native_resources import DiskLimits, DiskBudget

    root = tmp_path / "state"
    run = root / namespace / str(uuid4())
    run.mkdir(parents=True)
    data = run / "data"
    data.write_bytes(b"123")
    budget = DiskBudget(
        root, run, DiskLimits(run_bytes=10, project_bytes=20, free_bytes=0)
    )
    budget.check(force=True)
    data.write_bytes(b"x" * 11)
    with pytest.raises(CoreError) as error:
        budget.check(force=True)
    assert error.value.code == "NATIVE_STORAGE_LIMIT"
    with pytest.raises(CoreError):
        DiskBudget(
            root, run, DiskLimits(run_bytes=100, project_bytes=5, free_bytes=0)
        ).check(force=True)
    with pytest.raises(CoreError):
        DiskBudget(root, run, DiskLimits(free_bytes=2**63)).check(force=True)


def test_cleanup_removes_only_owned_service_data_and_preserves_evidence(tmp_path):
    from rentgen_core.native_scratch import clear_ibcmd_scratch

    run = tmp_path / "test-runs" / str(uuid4())
    scratch = run / "baseline-extension-properties-data/session-data/shardes/0/log"
    scratch.mkdir(parents=True)
    (scratch / "00000000.log").write_bytes(b"x" * 512)
    (run / "report.json").write_bytes(b"immutable result")
    result = clear_ibcmd_scratch(run)
    assert result == {"status": "completed", "released_logical_bytes": 512}
    assert not (run / "baseline-extension-properties-data").exists()
    assert (run / "report.json").read_bytes() == b"immutable result"


def test_cleanup_rejects_junction_without_touching_external_files(tmp_path):
    from rentgen_core.native_scratch import clear_ibcmd_scratch

    run = tmp_path / "test-runs" / str(uuid4())
    run.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    (external / "keep").write_bytes(b"outside")
    junction = run / "baseline-extension-properties-data"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(external)],
        capture_output=True,
        check=True,
        timeout=10,
    )
    try:
        assert clear_ibcmd_scratch(run)["status"] == "retained"
        assert (external / "keep").read_bytes() == b"outside"
    finally:
        junction.rmdir()  # Remove only the verified junction itself, no recursive walk.
