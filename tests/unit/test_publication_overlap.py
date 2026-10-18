"""Two live native publishers and portable negative controls for the fixture."""
import importlib.util
import json
import sqlite3
import sys
from types import SimpleNamespace

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
    value = dict(pid=123, **expected)
    child = SimpleNamespace(pid=123, poll=lambda: 2 if fault == "exited" else None)
    if fault in value:
        value[fault] = "wrong"
    if fault != "missing":
        (tmp_path / "ready.json").write_text("{" if fault == "malformed" else json.dumps(value), encoding="utf-8")
    with pytest.raises((ValueError, json.JSONDecodeError)):
        probe.wait_marker(child, tmp_path, expected, timeout=.05)
    assert not (tmp_path / "release").exists()


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
