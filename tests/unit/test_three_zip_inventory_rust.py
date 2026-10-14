"""Real Rust manifests are sufficient; no ZIP reader or candidate in classifier."""
import hashlib
from itertools import product
import sys

import pytest

from rentgen_core.rust_input import RustInputSession
from rentgen_core.three_way import plan_three_way
from rentgen_core.three_zip_inventory import classify_entries, page_entries
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Rust submitted ZIPs are Linux-only")


def test_three_real_verified_manifests_match_bytes_oracle_without_reading_entries(binary, tmp_path, monkeypatch):
    # Synthetic test bytes only. Python ZIP creation is not a product fallback.
    values = (None, b"", b"\xef\xbb\xbfA\r\n", "Процедура Б()\nКонецПроцедуры\n".encode())
    files = [{}, {}, {}]
    for indices in product(range(4), repeat=3):
        path = "ОбщиеМодули/" + "".join(map(str, indices)) + "/Ext/Module.bsl"
        for side, index in zip(files, indices):
            if values[index] is not None:
                side[path] = values[index]
    manifests, original, processes = [], {}, []
    monkeypatch.setattr(RustInputSession, "read_entry", lambda *args: pytest.fail("Classifier must not read source bytes"))
    for index, tree in enumerate(files):
        archive = tmp_path / f"role-{index}.zip"
        raw = zip_bytes(tree)
        archive.write_bytes(raw)
        original[archive] = raw
        with RustInputSession(*binary, authorize=lambda: None) as session:
            manifest = session.open_import(archive, hashlib.sha256(raw).hexdigest())
            manifests.append(session.entries(manifest))
            processes.append(session.process)
        assert processes[-1].returncode == 0
    result, counts, coverage = classify_entries(*manifests, checkpoint=lambda: None)
    oracle = plan_three_way(*files)
    assert {row["path"]: row["action"] for row in result} == {
        row["path"]: row["action"] for row in oracle["changes"]}
    assert {action: counts[action] for action in oracle["counts"]} == oracle["counts"]
    assert counts["total"] == coverage["union_paths"] == 63
    assert coverage["entry_records"] == 144
    assert coverage["decoded_bytes"] == sum(sum(map(len, tree.values())) for tree in files)
    for row in result:
        for label, tree in zip(("base", "current", "upstream"), files):
            raw = tree.get(row["path"])
            assert row[label] == (None if raw is None else {
                "raw_sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)})
    assert page_entries(result, 0, "conflict", checkpoint=lambda: None)["page"]["total"] == counts["conflict"]
    assert {path: path.read_bytes() for path in original} == original
    assert all(process.poll() == 0 for process in processes)


def test_maximum_union_real_sqlite_authorization_timing_without_connection_reuse(tmp_path, monkeypatch, record_property):
    import time
    from rentgen_core import _sqlite
    from rentgen_core.gui import Config
    from rentgen_core.local_identity import initialize_local_identity
    from rentgen_core.registry import ProjectRegistry

    profile = tmp_path / "private" / "identity.json"
    principal = initialize_local_identity(profile)
    source = tmp_path / "source"
    source.mkdir()
    sentinel = source / "untouched.bsl"
    sentinel.write_bytes(b"Do not read or edit the live source.\n")
    registry = ProjectRegistry.create(tmp_path / "registry.sqlite3")
    project = registry.register(principal, source_root=source, state_root=tmp_path / "state", display_name="Inventory budget")
    config = Config(registry.path, profile, project.project_id, tmp_path / "unused-helper", "0" * 64)
    manifests = [tuple({"entry_id": n, "path": f"{side}/f{n:04}", "raw_sha256": "a" * 64, "size_bytes": 1}
                       for n in range(4096)) for side in ("base", "current", "upstream")]
    original_connect = _sqlite.sqlite3.connect
    connections = checks = 0

    def connect(*args, **kwargs):
        nonlocal connections
        connections += 1
        return original_connect(*args, **kwargs)

    def checkpoint():
        nonlocal checks
        checks += 1
        before = connections
        config.authorize()
        # Each permission decision owns fresh registry/state read transactions.
        assert connections >= before + 2

    monkeypatch.setattr(_sqlite.sqlite3, "connect", connect)
    started = time.monotonic()
    rows, counts, coverage = classify_entries(*manifests, checkpoint=checkpoint)
    classify_seconds = time.monotonic() - started
    classify_checks = checks
    started = time.monotonic()
    result = page_entries(rows, 12200, "all", checkpoint=checkpoint)
    page_seconds = time.monotonic() - started
    witness = {"rows": len(rows), "classification_seconds": round(classify_seconds, 4),
               "paging_seconds": round(page_seconds, 4), "classification_checkpoints": classify_checks,
               "paging_checkpoints": checks - classify_checks, "fresh_sqlite_connections": connections}
    for name, value in witness.items():
        record_property(name, value)
    print("Three-ZIP real-SQLite timing witness:", witness)
    assert counts["total"] == coverage["union_paths"] == 12288
    assert result["page"]["returned"] == 88
    assert 384 < classify_checks < 12288
    assert checks - classify_checks == 386  # 12,288 / 32, plus initial/final.
    assert sentinel.read_bytes() == b"Do not read or edit the live source.\n"
