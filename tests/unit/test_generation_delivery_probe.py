"""Oracle controls and actual native source-CLI rehearsal, not installed acceptance."""
from copy import deepcopy
import importlib.util
import json
import sqlite3
import subprocess
import sys
from uuid import uuid4

import pytest

import rentgen_core as api
from project_access_test_support import grant_membership
from publication_kill_support import ROOT, backend
from test_publication_process_kill import project, scanner, native

spec = importlib.util.spec_from_file_location("generation_delivery_probe",
    ROOT / "scripts/verification/generation_delivery_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.mark.parametrize("damage", [None, "catalog", "physical_state", "removal_permitted",
    "snapshot_id", "source_digest", "graph_hash", "verified_source_files", "verified_derived_files",
    "verified_total_bytes"])
def test_oracle_refuses_misbound_or_unsafe_success(damage):
    catalog = dict(snapshot=dict(project_id="p", snapshot_id="s", manifest_hash="m"),
                   source_digest="source", graph_hash="graph")
    document = dict(source=dict(entries=[{}]), derived_inputs=[{}, {}])
    result = dict(catalog=deepcopy(catalog), physical_state="verified_at_read", removal_permitted=False,
        validation=dict(catalog["snapshot"], source_digest="source", graph_hash="graph",
                        verified_source_files=1, verified_derived_files=2, verified_total_bytes=100))
    if damage is None:
        probe.validate_verification(result, catalog, document)
        return
    if damage == "catalog": result["catalog"]["snapshot"]["snapshot_id"] = "other"
    elif damage == "physical_state": result[damage] = "not_inspected"
    elif damage == "removal_permitted": result[damage] = True
    else: result["validation"][damage] = 0
    with pytest.raises(ValueError):
        probe.validate_verification(result, catalog, document)


def test_state_fingerprint_detects_same_count_row_changes_and_does_not_write(tmp_path):
    path = tmp_path / "state.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE evidence (value TEXT)")
        connection.execute("INSERT INTO evidence VALUES ('before')")
    raw = path.read_bytes()
    before = probe.state_image(path)
    assert before == probe.state_image(path) and raw == path.read_bytes()
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE evidence SET value='after'")
    assert probe.state_image(path) != before


@native
def test_real_capture_cli_exercises_complete_delivery_oracle(project, scanner, tmp_path):
    from rentgen_core.local_identity import current_local_principal, initialize_local_identity
    ctx, registry, module = project
    extra = []
    if sys.platform == "linux":
        profile = tmp_path / "identity/profile.json"
        principal = initialize_local_identity(profile)
        extra = ["--identity-profile", str(profile)]
    else:
        principal = current_local_principal()
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        grant_membership(tx, principal, {"project:read"})
    def capture():
        from dataclasses import asdict
        return asdict(api.capture_and_publish(ctx, expected_head=api.get_project_head(ctx),
            builder=backend(*scanner), operation_id=str(uuid4())))
    first = capture()
    module.write_bytes(module.read_bytes().replace(b"Return 1", b"Return 2"))
    second = capture()
    ctx.source_root.rename(tmp_path / "removed-live-source")
    def command(name, *args, expected=0, error_code=None):
        process = subprocess.run([sys.executable, "-m", "rentgen_core", name,
            "--registry", str(registry.path), "--project", ctx.project_id, *extra, *args],
            cwd=ROOT, capture_output=True, text=True, timeout=45)
        assert process.returncode == expected, (process.stdout, process.stderr)
        value = json.loads(process.stdout)
        if error_code:
            assert value["error"]["code"] == error_code
            return None
        return value["result"]
    result = probe.verify(command, ctx.state.path.parent, ctx.source_root, first, second)
    assert all(value is True for value in result["outcomes"].values())
    assert len(result["damage_cases"]) == 7
    assert sum(row["error_code"] == "SNAPSHOT_CORRUPT" for row in result["checks"]) == 7
    assert sum(row["error_code"] == "GENERATION_UNREFERENCED" for row in result["checks"]) == 2
