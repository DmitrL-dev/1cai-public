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
    evidence = {
        "request.json": b"immutable request",
        "report.json": b"immutable result",
        "junit.xml": b"test evidence",
        "infobase/1Cv8.1CD": b"retained database",
    }
    for name, raw in evidence.items():
        path = run / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
    result = clear_ibcmd_scratch(run)
    assert result == {"status": "completed", "released_logical_bytes": 512}
    assert not (run / "baseline-extension-properties-data").exists()
    assert {name: (run / name).read_bytes() for name in evidence} == evidence


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


@pytest.mark.parametrize("namespace", ["platform-checks", "metadata-runs"])
def test_admission_reserves_whole_run_headroom_before_creating_directory(
    tmp_path, namespace
):
    from rentgen_core.native_resources import DiskLimits, reserve_run

    parent = tmp_path / namespace
    old = parent / str(uuid4())
    old.mkdir(parents=True)
    evidence = old / "request.json"
    evidence.write_bytes(b"123456")
    run = parent / str(uuid4())
    with pytest.raises(CoreError) as error:
        reserve_run(
            tmp_path,
            run,
            limits=DiskLimits(run_bytes=5, project_bytes=10, free_bytes=0),
        )
    assert error.value.code == "NATIVE_STORAGE_LIMIT"
    assert error.value.details["admitted"] is False
    assert error.value.details["reserve_bytes"] == 5
    assert not run.exists()
    assert evidence.read_bytes() == b"123456"


@pytest.mark.parametrize("namespace", ["test-runs", "metadata-runs"])
def test_admission_checks_free_headroom_and_keeps_external_working_infobase(
    tmp_path, monkeypatch, namespace
):
    from collections import namedtuple
    from rentgen_core import native_resources

    parent = tmp_path / namespace
    parent.mkdir()
    working = tmp_path / "working-infobase"
    working.mkdir()
    sentinel = working / "1Cv8.1CD"
    sentinel.write_bytes(b"user database")
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(
        native_resources.shutil, "disk_usage", lambda root: usage(100, 87, 13)
    )
    run = parent / str(uuid4())
    with pytest.raises(CoreError) as error:
        native_resources.reserve_run(
            tmp_path,
            run,
            limits=native_resources.DiskLimits(
                run_bytes=10, project_bytes=30, free_bytes=4
            ),
        )
    assert error.value.code == "NATIVE_STORAGE_LIMIT"
    assert not run.exists()
    assert sentinel.read_bytes() == b"user database"
    monkeypatch.setattr(
        native_resources.shutil, "disk_usage", lambda root: usage(100, 86, 14)
    )
    receipt = native_resources.reserve_run(
        tmp_path,
        run,
        limits=native_resources.DiskLimits(
            run_bytes=10, project_bytes=30, free_bytes=4
        ),
    )
    assert run.is_dir() and receipt["reserve_bytes"] == 10
    assert sentinel.read_bytes() == b"user database"


def test_admission_counts_metadata_and_all_retained_outcomes(tmp_path, monkeypatch):
    from rentgen_core import native_resources as resources

    monkeypatch.setattr(resources, "RETAINED_RUN_LIMIT", 5)
    limits = resources.DiskLimits(run_bytes=10, project_bytes=1000, free_bytes=0)
    retained = []
    for namespace, status in (
        ("platform-checks", "completed"),
        ("test-runs", "failed"),
        ("metadata-runs", "unknown"),
        ("metadata-runs", None),
    ):
        previous = tmp_path / namespace / str(uuid4())
        previous.mkdir(parents=True)
        if status is not None:
            (previous / "outcome.json").write_text(status)
        retained.append(previous)
    admitted = tmp_path / "metadata-runs" / str(uuid4())
    receipt = resources.reserve_run(tmp_path, admitted, limits=limits)
    assert receipt["retained_run_limit"] == 5
    assert receipt["retention"] == "retain_all_no_eviction"
    for namespace in resources.NAMESPACES:
        refused = tmp_path / namespace / str(uuid4())
        with pytest.raises(CoreError) as error:
            resources.reserve_run(tmp_path, refused, limits=limits)
        assert error.value.code == "NATIVE_RETENTION_LIMIT"
        assert error.value.details == {
            "retained_runs": 5,
            "retained_run_limit": 5,
            "run_id": refused.name,
            "admitted": False,
        }
        assert not refused.exists()
    assert [
        (run / "outcome.json").read_text() if (run / "outcome.json").exists() else None
        for run in retained
    ] == ["completed", "failed", "unknown", None]


@pytest.mark.parametrize(
    "namespaces", [("test-runs",), ("metadata-runs",), ("test-runs", "metadata-runs")]
)
def test_admission_serializes_other_processes_at_retention_boundary(
    tmp_path, namespaces
):
    parents = [tmp_path / name for name in namespaces]
    for parent in parents:
        parent.mkdir()
    code = """
import sys
from pathlib import Path
from rentgen_core import native_resources as n
from rentgen_core.errors import CoreError
n.RETAINED_RUN_LIMIT=1
try:
 n.reserve_run(Path(sys.argv[1]), Path(sys.argv[2]))
 print('admitted')
except CoreError as e: print(e.code)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
    workers = [
        subprocess.Popen(
            [
                sys._base_executable,
                "-c",
                code,
                str(tmp_path),
                str(parents[index % len(parents)] / str(uuid4())),
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for index in range(4)
    ]
    outcomes = []
    try:
        for worker in workers:
            out, err = worker.communicate(timeout=15)
            assert worker.returncode == 0, err.decode()
            outcomes.append(out.strip().decode())
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=10)
    assert outcomes.count("admitted") == 1
    assert set(outcomes) <= {
        "admitted",
        "NATIVE_RETENTION_LIMIT",
        "NATIVE_ADMISSION_BUSY",
    }
    assert sum(len(list(parent.iterdir())) for parent in parents) == 1


@pytest.mark.parametrize("namespace", ["test-runs", "metadata-runs"])
def test_controller_crash_releases_admission_lock_but_retains_unknown_run(
    tmp_path, monkeypatch, namespace
):
    from rentgen_core import native_resources
    from test_native_process import wait_file

    parent = tmp_path / namespace
    parent.mkdir()
    unknown = parent / str(uuid4())
    ready = tmp_path / "ready"
    code = """
import sys,time
from pathlib import Path
from rentgen_core.native_resources import _file_slot
root,run,ready=map(Path,sys.argv[1:])
with _file_slot(root, 'native-admission.lock', 'NATIVE_ADMISSION_BUSY'):
 run.mkdir()
 (run/'request.json').write_bytes(b'unknown outcome')
 ready.write_text('locked')
 time.sleep(120)
"""
    worker = subprocess.Popen(
        [sys._base_executable, "-c", code, str(tmp_path), str(unknown), str(ready)],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
    )
    run = parent / str(uuid4())
    try:
        wait_file(ready)
        with pytest.raises(CoreError) as error:
            native_resources.reserve_run(tmp_path, run)
        assert error.value.code == "NATIVE_ADMISSION_BUSY"
        assert not run.exists()
    finally:
        worker.kill()
        worker.wait(timeout=10)
    monkeypatch.setattr(native_resources, "RETAINED_RUN_LIMIT", 1)
    with pytest.raises(CoreError) as error:
        native_resources.reserve_run(tmp_path, run)
    assert error.value.code == "NATIVE_RETENTION_LIMIT"
    assert not run.exists()
    assert (unknown / "request.json").read_bytes() == b"unknown outcome"


@pytest.mark.parametrize("namespace", ["test-runs", "metadata-runs"])
def test_admission_rejects_reparse_run_without_touching_external_database(
    tmp_path, namespace
):
    from rentgen_core.native_resources import reserve_run

    parent = tmp_path / namespace
    parent.mkdir()
    external = tmp_path / "working-infobase"
    external.mkdir()
    database = external / "1Cv8.1CD"
    database.write_bytes(b"user database")
    junction = parent / str(uuid4())
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(external)],
        capture_output=True,
        check=True,
        timeout=10,
    )
    run = parent / str(uuid4())
    try:
        with pytest.raises(CoreError) as error:
            reserve_run(tmp_path, run)
        assert error.value.code == "NATIVE_STORAGE_INVALID"
        assert not run.exists()
        assert database.read_bytes() == b"user database"
    finally:
        junction.rmdir()


def test_cleanup_retains_hardlinked_scratch_and_external_database(tmp_path):
    from rentgen_core.native_scratch import clear_ibcmd_scratch

    run = tmp_path / "test-runs" / str(uuid4())
    scratch = run / "baseline-extension-properties-data"
    scratch.mkdir(parents=True)
    database = tmp_path / "working.1CD"
    database.write_bytes(b"user database")
    alias = scratch / "log"
    os.link(database, alias)
    assert clear_ibcmd_scratch(run)["status"] == "retained"
    assert alias.read_bytes() == b"user database"
    assert database.read_bytes() == b"user database"


@pytest.mark.parametrize("failure", ["seek", "unlock"])
def test_slot_closes_descriptor_even_when_unlock_fails(tmp_path, monkeypatch, failure):
    import msvcrt
    from rentgen_core.native_resources import _file_slot

    descriptors = []
    original = msvcrt.locking

    def locking(descriptor, mode, count):
        if mode == msvcrt.LK_UNLCK:
            raise OSError("injected unlock failure")
        original(descriptor, mode, count)
        descriptors.append(descriptor)

    def failed_seek(*args):
        raise OSError("injected seek failure")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(msvcrt, "locking", locking)
            with pytest.raises(OSError, match="injected .* failure"):
                with _file_slot(
                    tmp_path, "native-admission.lock", "NATIVE_ADMISSION_BUSY"
                ):
                    if failure == "seek":
                        patch.setattr(os, "lseek", failed_seek)
        assert len(descriptors) == 1
        with pytest.raises(OSError):
            os.fstat(descriptors[0])
    finally:
        for descriptor in descriptors:
            try:
                os.close(descriptor)
            except OSError:
                pass
    with _file_slot(tmp_path, "native-admission.lock", "NATIVE_ADMISSION_BUSY"):
        pass
