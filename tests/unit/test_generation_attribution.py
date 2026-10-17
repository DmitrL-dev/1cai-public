"""Catalog attribution uses real SQLite; synthetic rows prove no file validity."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread
from uuid import uuid4

import pytest

import rentgen_core as api
from rentgen_core import cli, capabilities
from rentgen_core.local import LocalRuntime
from project_access_test_support import force_legacy_membership, grant_membership, revoke_membership


@pytest.fixture
def project(tmp_path):
    owner = api.Principal("attribution-owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    registered = registry.register(owner, source_root=source,
        state_root=tmp_path / "state", display_name="Attribution fixture")
    runtime = LocalRuntime(registry.path)
    return runtime.state_context(owner, registered.project_id), runtime


def catalog(ctx, char="a", locator=None):
    return api.SnapshotCatalogEntry(
        api.SnapshotRef(ctx.project_id, char * 64, char * 64),
        "c" * 64, "d" * 64, locator or "generations/" + str(uuid4()), 1,
        datetime.now(timezone.utc).isoformat())


def commit(ctx, entry):
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        return tx.commit_publication(expected_head=tx.get_project_head(), catalog=entry,
            layers=(api.SnapshotLayer("base", 0, "base", None, "unresolved", "unknown"),),
            operation_id=str(uuid4()))


def test_unreferenced_at_read_does_not_assert_orphan_or_allow_removal(project):
    ctx, _ = project
    locator = "generations/" + str(uuid4())
    before = ctx.state.path.read_bytes()
    result = api.get_generation_attribution(ctx, locator)
    assert result.status == "unreferenced_at_read"
    assert result.generation_relpath == locator
    assert result.observed_head == api.get_project_head(ctx)
    assert result.catalog is None and result.latest_publication is None
    assert result.physical_state == "not_inspected"
    assert result.removal_permitted is False
    assert not (ctx.state.path.parent / "generations").exists()
    assert ctx.state.path.read_bytes() == before


@pytest.mark.parametrize("legacy", [False, True])
def test_catalog_reference_retains_history_and_latest_reuse_receipt(project, legacy):
    ctx, _ = project
    entry = catalog(ctx, locator="generations/" + "a" * 64 if legacy else None)
    first = commit(ctx, entry)
    second = commit(ctx, catalog(ctx, "b"))
    historical = api.get_generation_attribution(ctx, entry.generation_relpath)
    assert historical.catalog == entry
    assert historical.latest_publication == first
    assert historical.observed_head == second.head
    reused = commit(ctx, entry)
    result = api.get_generation_attribution(ctx, entry.generation_relpath)
    assert result.status == "catalog_referenced"
    assert result.latest_publication == reused
    assert result.observed_head == reused.head
    assert result.physical_state == "not_inspected" and not result.removal_permitted


@pytest.mark.parametrize("locator", [None, 1, True, [], "", "../a", "generations/../a",
    "/generations/" + "a" * 64, "generations\\" + "a" * 64,
    "generations/" + "A" * 64, "generations/" + "a" * 63,
    "generations/AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA", "generations/" + str(uuid4()) + "/",
    "generations/" + "f" * 10000], ids=["null", "integer", "bool", "list", "empty",
    "parent", "traversal", "absolute", "backslash", "uppercase-hash", "short-hash",
    "uppercase-uuid", "trailing-slash", "oversized"])
def test_locator_rejects_noncanonical_paths(project, locator):
    with pytest.raises(api.CoreError) as error:
        api.get_generation_attribution(project[0], locator)
    assert error.value.code == "INVALID_GENERATION_LOCATOR"


def test_context_required():
    with pytest.raises(api.CoreError) as error:
        api.get_generation_attribution(None, "generations/" + str(uuid4()))
    assert error.value.code == "CONTEXT_REQUIRED"


def test_read_permission_is_rechecked_and_closed_transaction_refuses(project):
    ctx, _ = project
    entry = catalog(ctx)
    commit(ctx, entry)
    reader = api.Principal("reader", "local_os")
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        grant_membership(tx, reader, {"project:read"})
    selected = replace(ctx, principal=reader)
    assert api.get_generation_attribution(selected, entry.generation_relpath).catalog == entry
    with ctx.state.transaction(reader) as closed:
        pass
    with pytest.raises(api.CoreError) as error:
        closed.get_generation_attribution(entry.generation_relpath)
    assert error.value.code == "TRANSACTION_CLOSED"
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        revoke_membership(tx, reader)
    for locator in (entry.generation_relpath, "invalid"):
        with pytest.raises(api.CoreError) as error:
            api.get_generation_attribution(selected, locator)
        assert error.value.code == "PROJECT_FORBIDDEN"


def test_foreign_project_same_locator_is_not_attributed(project, tmp_path):
    ctx, _ = project
    entry = catalog(ctx)
    commit(ctx, entry)
    state = api.ProjectState.create(tmp_path / "other.sqlite3", str(uuid4()), ctx.principal)
    other = replace(ctx, project_id=state.project_id, state=state)
    result = api.get_generation_attribution(other, entry.generation_relpath)
    assert result.status == "unreferenced_at_read"
    assert result.observed_head.project_id == other.project_id


@pytest.mark.parametrize("defect", ["missing_receipt", "future_receipt", "missing_head_receipt", "bad_manifest"])
def test_corrupt_reference_is_never_reported_as_unreferenced(project, defect):
    from rentgen_core import _sqlite
    ctx, _ = project
    entry = catalog(ctx)
    receipt = commit(ctx, entry)
    with _sqlite.transaction(ctx.state.path, write=True) as db:
        if defect == "missing_receipt":
            db.execute("DELETE FROM snapshot_outbox")
            db.execute("DELETE FROM snapshot_events")
            db.execute("DELETE FROM publication_receipts")
        elif defect == "future_receipt":
            db.execute("UPDATE publication_receipts SET committed_head_revision=9")
        elif defect == "missing_head_receipt":
            db.execute("UPDATE project_head SET revision=9")
        else:
            db.execute("PRAGMA ignore_check_constraints=ON")
            db.execute("UPDATE snapshots SET manifest_hash=?", ("f" * 64,))
    with pytest.raises(api.CoreError) as error:
        api.get_generation_attribution(ctx, entry.generation_relpath)
    assert error.value.code in {"STATE_CORRUPT", "SNAPSHOT_CORRUPT"}


def test_cli_uses_state_only_and_explicit_project(project, monkeypatch, capsys):
    ctx, runtime = project
    entry = catalog(ctx)
    receipt = commit(ctx, entry)
    ctx.source_root.rmdir()
    monkeypatch.setattr(capabilities, "_platform", "linux")
    monkeypatch.setattr(cli, "current_local_principal", lambda: ctx.principal)
    monkeypatch.setattr(cli, "_runtime", lambda args: runtime)
    result = cli.main(["generation-attribution", "--registry", str(runtime.registry_path),
        "--project", ctx.project_id, "--generation-relpath", entry.generation_relpath])
    output = capsys.readouterr()
    assert result == 0, output
    document = json.loads(output.out)["result"]
    assert document["catalog"] == asdict(entry)
    assert document["latest_publication"] == asdict(receipt)
    assert document["physical_state"] == "not_inspected"
    assert not document["removal_permitted"]


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_schema_admission(project, tmp_path, version):
    from rentgen_core import _sqlite
    from rentgen_core.state import _SCHEMA_V1, _SCHEMA_V2_ADDITIONS, _SCHEMA_V3_ADDITIONS, SCHEMA_V4_ADDITIONS, _initialize_v2
    from rentgen_core.authorization import OWNER_PERMISSIONS
    ctx, _ = project
    state = api.ProjectState(tmp_path / "schema.sqlite3", ctx.project_id)
    schema = _SCHEMA_V1
    if version >= 2:
        schema += _SCHEMA_V2_ADDITIONS
    if version >= 3:
        schema += _SCHEMA_V3_ADDITIONS
    if version >= 4:
        schema += SCHEMA_V4_ADDITIONS
    with _sqlite.create_database(state.path, schema) as db:
        db.execute("INSERT INTO project VALUES (1,?)", (ctx.project_id,))
        identity = (ctx.project_id, ctx.principal.id, ctx.principal.authority)
        db.execute("INSERT INTO memberships VALUES (?,?,?)", identity)
        db.executemany("INSERT INTO membership_permissions VALUES (?,?,?,?)",
            [(*identity, permission) for permission in OWNER_PERMISSIONS])
        if version >= 2:
            _initialize_v2(db, ctx.project_id)
        db.execute(f"PRAGMA user_version={version}")
    ctx = replace(ctx, state=state)
    if version == 1:
        with pytest.raises(api.CoreError) as error:
            api.get_generation_attribution(ctx, "generations/" + str(uuid4()))
        assert error.value.code == "PROJECT_STATE_MISMATCH"
    else:
        assert api.get_generation_attribution(ctx, "generations/" + str(uuid4())).status == "unreferenced_at_read"


def test_cli_redacts_result_if_read_permission_is_revoked_during_encoding(project, monkeypatch, capsys):
    ctx, runtime = project
    entry = catalog(ctx)
    commit(ctx, entry)
    monkeypatch.setattr(capabilities, "_platform", "linux")
    monkeypatch.setattr(cli, "current_local_principal", lambda: ctx.principal)
    monkeypatch.setattr(cli, "_runtime", lambda args: runtime)
    dumps = json.dumps
    revoked = False

    def encode(value, **kwargs):
        nonlocal revoked
        encoded = dumps(value, **kwargs)
        if isinstance(value, dict) and "result" in value and not revoked:
            revoked = True
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                force_legacy_membership(tx, ctx.principal, set())
        return encoded

    monkeypatch.setattr(json, "dumps", encode)
    code = cli.main(["generation-attribution", "--registry", str(runtime.registry_path),
        "--project", ctx.project_id, "--generation-relpath", entry.generation_relpath])
    output = capsys.readouterr()
    assert code == 2 and revoked
    assert json.loads(output.out)["error"]["code"] == "PROJECT_FORBIDDEN"
    assert entry.generation_relpath not in output.out and entry.snapshot.snapshot_id not in output.out


@pytest.mark.skipif(sys.platform != "linux", reason="Real Linux identity and CLI subprocess")
def test_linux_cli_subprocess_attributes_catalog_without_source_or_generation(tmp_path):
    from rentgen_core.local_identity import initialize_local_identity
    profile = tmp_path / "profile" / "identity.json"
    owner = initialize_local_identity(profile)
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    source = tmp_path / "source"
    source.mkdir()
    registered = registry.register(owner, source_root=source, state_root=tmp_path / "state", display_name="CLI fixture")
    ctx = LocalRuntime(registry.path).state_context(owner, registered.project_id)
    entry = catalog(ctx)
    receipt = commit(ctx, entry)
    source.rmdir()
    result = subprocess.run([sys.executable, "-m", "rentgen_core", "generation-attribution",
        "--registry", str(registry.path), "--identity-profile", str(profile), "--project", ctx.project_id,
        "--generation-relpath", entry.generation_relpath], cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, (result.stdout, result.stderr)
    value = json.loads(result.stdout)["result"]
    assert value["catalog"] == asdict(entry) and value["latest_publication"] == asdict(receipt)
    assert value["physical_state"] == "not_inspected" and not value["removal_permitted"]


@pytest.mark.parametrize("platform,supported", [("win32", True), ("linux", True), ("darwin", False)])
def test_platform_admission(monkeypatch, platform, supported):
    monkeypatch.setattr(capabilities, "_platform", platform)
    assert capabilities.operation_supported("generation-attribution") is supported


def test_concurrent_publication_cannot_mix_catalog_and_observed_head(project):
    ctx, _ = project
    entry = catalog(ctx)
    ready = Event()
    failures = []

    def publish():
        try:
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                tx.commit_publication(expected_head=tx.get_project_head(), catalog=entry,
                    layers=(api.SnapshotLayer("base", 0, "base", None, "unresolved", "unknown"),),
                    operation_id=str(uuid4()))
                ready.set()
        except BaseException as exc:
            failures.append(exc)
            ready.set()

    writer = Thread(target=publish)
    try:
        with ctx.state.transaction(ctx.principal) as tx:
            before = tx.get_generation_attribution(entry.generation_relpath)
            writer.start()
            assert ready.wait(5), "writer did not reach commit"
            assert not failures
            during = tx.get_generation_attribution(entry.generation_relpath)
            assert during == before and during.status == "unreferenced_at_read"
            assert during.observed_head.revision == 0
    finally:
        if writer.ident is not None:
            writer.join(10)
    assert not writer.is_alive() and not failures
    after = api.get_generation_attribution(ctx, entry.generation_relpath)
    assert after.status == "catalog_referenced"
    assert after.observed_head == after.latest_publication.head
    assert after.observed_head.revision == 1
