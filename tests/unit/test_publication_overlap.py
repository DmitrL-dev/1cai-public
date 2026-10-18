"""Two live native publishers and portable negative controls for the fixture."""
import importlib.util
import json
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
import venv

import pytest

from publication_kill_support import ROOT
from test_publication_process_kill import native, scanner

spec = importlib.util.spec_from_file_location("publication_overlap_probe",
    ROOT / "scripts/verification/publication_overlap_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@native
@pytest.mark.parametrize("mode,winner", probe.CASES,
    ids=[mode + "-winner-" + str(winner) for mode, winner in probe.CASES])
def test_two_live_native_publishers(tmp_path, scanner, mode, winner):
    receipt = probe.verify(sys.executable, scanner[0], scanner[1], tmp_path / "overlap",
        isolated=False, checkout=ROOT, cases=((mode, winner),))
    assert len(receipt["cases"]) == 1
    assert len(receipt["cases"][0]["outcomes"]) == 12
    assert all(receipt["cases"][0]["outcomes"].values())


@pytest.mark.parametrize("fault", ["pid", "nonce", "operation_id", "expected_head", "phase", "exited", "malformed", "missing"])
def test_marker_refuses_unbound_or_unreadable_publisher(tmp_path, fault):
    expected = dict(nonce="nonce", operation_id="operation", expected_head={"revision": 0},
        phase="before_state_transaction")
    value = dict(pid=123, parent_pid=456, **expected)
    child = SimpleNamespace(pid=123, poll=lambda: 2 if fault == "exited" else None)
    if fault in value:
        value[fault] = "wrong"
    if fault != "missing":
        (tmp_path / "ready.json").write_text("{" if fault == "malformed" else json.dumps(value), encoding="utf-8")
    with pytest.raises((ValueError, json.JSONDecodeError)):
        probe.wait_marker(child, tmp_path, expected, timeout=.05)
    assert not (tmp_path / "release").exists()


@pytest.mark.parametrize("windows,pid,parent,accepted", [
    (False, 123, 456, True), (True, 123, 456, True),
    (True, 789, 123, True), (False, 789, 123, False), (True, 789, 456, False),
])
def test_marker_process_identity_requires_owned_launcher(monkeypatch, windows, pid, parent, accepted):
    monkeypatch.setattr(probe, "_WINDOWS_LAUNCHERS", windows)
    assert probe.process_binding(dict(pid=pid, parent_pid=parent), 123) is accepted


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows venv redirector")
def test_actual_windows_venv_redirector_binds_interpreter_marker(tmp_path):
    environment = tmp_path / "environment"
    venv.EnvBuilder(with_pip=False).create(environment)
    code = """
import json, os, pathlib, sys, time
root = pathlib.Path(sys.argv[1])
temporary = root / 'ready.tmp'
temporary.write_text(json.dumps(dict(pid=os.getpid(), parent_pid=os.getppid(), nonce='owned')), encoding='utf-8')
temporary.replace(root / 'ready.json')
end = time.monotonic() + 20
while not (root / 'release').exists():
    if time.monotonic() >= end: raise RuntimeError('owned marker expired')
    time.sleep(.01)
"""
    child = subprocess.Popen([str(environment / "Scripts/python.exe"), "-I", "-c", code, str(tmp_path)],
        stdin=subprocess.DEVNULL)
    try:
        marker = probe.wait_marker(child, tmp_path, {"nonce": "owned"}, timeout=10)
        assert marker["pid"] != child.pid
        assert marker["parent_pid"] == marker["launcher_pid"] == child.pid
    finally:
        (tmp_path / "release").touch()
        child.wait(timeout=25)
    assert child.returncode == 0


def test_state_oracle_detects_same_count_mutation(tmp_path):
    path = tmp_path / "state.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE snapshots (snapshot_id TEXT, generation_relpath TEXT);
            CREATE TABLE publication_receipts (operation_id TEXT);
            CREATE TABLE snapshot_events (payload TEXT);
            CREATE TABLE snapshot_outbox (status TEXT);
            CREATE TABLE project_head (snapshot_id TEXT, revision INTEGER);
            INSERT INTO snapshots VALUES ('snapshot', 'generations/first');
            INSERT INTO publication_receipts VALUES ('operation');
            INSERT INTO snapshot_events VALUES ('published');
            INSERT INTO snapshot_outbox VALUES ('pending');
            INSERT INTO project_head VALUES ('snapshot', 1);
        """)
    before_bytes = path.read_bytes()
    before = probe.state_view(path)
    assert path.read_bytes() == before_bytes
    with sqlite3.connect(path) as db:
        db.execute("UPDATE snapshot_events SET payload='wrong'")
    after = probe.state_view(path)
    assert before["counts"] == after["counts"]
    assert before["fingerprint"] != after["fingerprint"]
