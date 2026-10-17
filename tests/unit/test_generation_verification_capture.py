"""Actual Windows/Linux capture and retained verification, without 1C/EDT."""
from dataclasses import asdict, replace
import json
import shutil
import subprocess
import sys
from uuid import uuid4

import pytest

import rentgen_core as api
from rentgen_core import cli, generation_verification as verification
from rentgen_core.local import LocalRuntime
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory
from project_access_test_support import force_legacy_membership, grant_membership
from publication_kill_support import ROOT, backend
from test_publication_process_kill import project, scanner, native

pytestmark = native


def publish(project, scanner):
    ctx = project[0]
    receipt = api.capture_and_publish(ctx, expected_head=api.get_project_head(ctx),
        builder=backend(*scanner), operation_id=str(uuid4()))
    with ctx.state.transaction(ctx.principal) as tx:
        return tx.get_snapshot(receipt.snapshot.snapshot_id)


def verify(ctx, entry):
    return api.verify_catalog_generation(ctx, entry.generation_relpath,
                                        graph_reader_factory=RentgenGraphReaderFactory())


@pytest.mark.parametrize("legacy", [False, True])
def test_historical_and_reused_capture_verifies_without_live_source(project, scanner, legacy):
    ctx, _, module = project
    first = publish(project, scanner)
    if legacy:
        locator = "generations/" + first.snapshot.snapshot_id
        (ctx.state.path.parent / first.generation_relpath).rename(ctx.state.path.parent / locator)
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            tx._connection.execute("UPDATE snapshots SET generation_relpath=?", (locator,))
        first = replace(first, generation_relpath=locator)
    reused = publish(project, scanner)
    assert reused == first
    module.write_bytes(module.read_bytes().replace(b"Return 1", b"Return 2"))
    later = publish(project, scanner)
    assert later.snapshot != first.snapshot
    shutil.rmtree(ctx.source_root)
    before = api.get_project_head(ctx)
    result = verify(ctx, first)
    assert result.catalog == first and result.physical_state == "verified_at_read"
    assert result.validation["verified_source_files"] == 1
    assert result.validation["verified_derived_files"] >= 1
    assert result.validation["verified_total_bytes"] > 0
    assert not result.removal_permitted
    assert api.get_project_head(ctx) == before


@pytest.mark.parametrize("damage", ["source", "derived", "graph", "manifest", "extra", "sidecar", "missing"])
def test_native_damaged_generation_refuses(project, scanner, damage):
    ctx = project[0]
    entry = publish(project, scanner)
    root = ctx.state.path.parent / entry.generation_relpath
    doc = json.loads((root / "manifest.json").read_bytes())
    names = {"source": "sources/base/" + doc["source"]["entries"][0]["relative_path"],
             "derived": doc["derived_inputs"][0]["relative_path"], "graph": "graph.sqlite3",
             "manifest": "manifest.json", "extra": "extra", "sidecar": "graph.sqlite3-wal",
             "missing": "manifest.json"}
    path = root / names[damage]
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"damaged")
        if sys.platform == "linux":
            path.chmod(0o600)
    with pytest.raises(api.CoreError) as error:
        verify(ctx, entry)
    assert error.value.code == "SNAPSHOT_CORRUPT"


def test_native_catalog_drift_refuses_before_retained_open(project, scanner, monkeypatch):
    ctx = project[0]
    entry = publish(project, scanner)
    original = verification.get_generation_attribution
    def change(*args):
        result = original(*args)
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            tx._connection.execute("UPDATE snapshots SET generation_relpath=?", ("generations/" + str(uuid4()),))
        return result
    monkeypatch.setattr(verification, "get_generation_attribution", change)
    with pytest.raises(api.CoreError, match="catalog binding changed") as error:
        verify(ctx, entry)
    assert error.value.code == "SNAPSHOT_CORRUPT"


@pytest.mark.parametrize("damaged", [False, True])
def test_cli_redacts_success_or_error_when_permission_revoked_during_encoding(project, scanner, monkeypatch, capsys, damaged):
    ctx, registry, _ = project
    entry = publish(project, scanner)
    if damaged:
        (ctx.state.path.parent / entry.generation_relpath / "manifest.json").unlink()
    monkeypatch.setattr(cli, "current_local_principal", lambda: ctx.principal)
    monkeypatch.setattr(cli, "_runtime", lambda args: LocalRuntime(registry.path))
    dumps = json.dumps
    revoked = False
    def encode(value, **kwargs):
        nonlocal revoked
        result = dumps(value, **kwargs)
        if isinstance(value, dict) and ("result" in value or "error" in value) and not revoked:
            revoked = True
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                force_legacy_membership(tx, ctx.principal, set())
        return result
    monkeypatch.setattr(json, "dumps", encode)
    code = cli.main(["generation-verify", "--registry", str(registry.path), "--project", ctx.project_id,
                     "--generation-relpath", entry.generation_relpath])
    output = capsys.readouterr().out
    assert code == 2 and revoked
    assert json.loads(output)["error"]["code"] == "PROJECT_FORBIDDEN"
    assert entry.generation_relpath not in output and entry.snapshot.snapshot_id not in output


def test_actual_cli_process_verifies_historical_generation(project, scanner, tmp_path):
    from rentgen_core.local_identity import current_local_principal, initialize_local_identity
    ctx, registry, module = project
    extra = []
    if sys.platform == "linux":
        profile = tmp_path / "identity" / "profile.json"
        principal = initialize_local_identity(profile)
        extra = ["--identity-profile", str(profile)]
    else:
        principal = current_local_principal()
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        grant_membership(tx, principal, {"project:read"})
    first = publish(project, scanner)
    module.write_bytes(module.read_bytes().replace(b"Return 1", b"Return 2"))
    publish(project, scanner)
    shutil.rmtree(ctx.source_root)
    result = subprocess.run([sys.executable, "-m", "rentgen_core", "generation-verify",
        "--registry", str(registry.path), "--project", ctx.project_id,
        "--generation-relpath", first.generation_relpath, *extra], cwd=ROOT,
        capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, (result.stdout, result.stderr)
    value = json.loads(result.stdout)["result"]
    assert value["catalog"] == asdict(first)
    assert value["physical_state"] == "verified_at_read" and not value["removal_permitted"]
