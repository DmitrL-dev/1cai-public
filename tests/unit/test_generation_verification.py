"""Real SQLite/POSIX storage contracts; platform overrides are not native admission."""
from dataclasses import replace
from uuid import uuid4
import sys

import pytest

import rentgen_core as api
from rentgen_core import capabilities
from rentgen_core import generation_verification as verification
from project_access_test_support import force_legacy_membership
from test_generation_attribution import project, catalog, commit
from test_posix_snapshot_session import make_generation, generation


@pytest.fixture(autouse=True)
def storage_admission(monkeypatch):
    monkeypatch.setattr(capabilities, "_platform", "win32" if sys.platform == "win32" else "linux")


@pytest.mark.parametrize("locator", ["../escape", "generations/" + "A" * 64, "generations/" + str(uuid4())],
                         ids=["traversal", "uppercase", "unreferenced"])
def test_refuses_before_retained_io(project, monkeypatch, locator):
    ctx = project[0]
    def forbidden(*args, **kwargs):
        pytest.fail("Refused locator reached physical session")
    from rentgen_core import sources, _posix_snapshot_session
    monkeypatch.setattr(sources.SnapshotReadSession, "__enter__", forbidden)
    monkeypatch.setattr(_posix_snapshot_session._PosixSnapshotSession, "__enter__", forbidden)
    with pytest.raises(api.CoreError) as error:
        api.verify_catalog_generation(ctx, locator)
    assert error.value.code == ("GENERATION_UNREFERENCED" if len(locator) == 48 else "INVALID_GENERATION_LOCATOR")


def test_denied_reader_does_not_learn_locator_state(project):
    ctx = project[0]
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, set())
    for locator in ("invalid", "generations/" + str(uuid4())):
        with pytest.raises(api.CoreError) as error:
            api.verify_catalog_generation(ctx, locator)
        assert error.value.code == "PROJECT_FORBIDDEN"


def test_missing_context():
    with pytest.raises(api.CoreError) as error:
        api.verify_catalog_generation(None, "generations/" + str(uuid4()))
    assert error.value.code == "CONTEXT_REQUIRED"


@pytest.mark.parametrize("platform,supported", [("win32", True), ("linux", True), ("darwin", False)])
def test_os_admission_before_state(monkeypatch, platform, supported):
    monkeypatch.setattr(capabilities, "_platform", platform)
    assert capabilities.operation_supported("generation-verify") is supported
    if not supported:
        with pytest.raises(api.CoreError) as error:
            api.verify_catalog_generation(None, "invalid")
        assert error.value.code == "CAPABILITY_UNAVAILABLE"


posix = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="POSIX storage fixture")


def context(g):
    return api.ProjectContext(g.state.project_id, g.principal, str(uuid4()), g.state, g.root / "absent-live")


def verify(g):
    return api.verify_catalog_generation(context(g), g.catalog.generation_relpath,
                                        graph_reader_factory=g.options["graph_reader_factory"])


@posix
@pytest.mark.parametrize("legacy", [False, True])
def test_verifies_exact_retained_files_without_live_source(generation, legacy):
    g = generation
    if legacy:
        locator = "generations/" + g.snapshot.snapshot_id
        g.path.rename(g.root / locator)
        with g.state.transaction(g.owner, write=True) as tx:
            tx._connection.execute("UPDATE snapshots SET generation_relpath=?", (locator,))
        g.catalog = replace(g.catalog, generation_relpath=locator)
    result = verify(g)
    assert result.catalog == g.catalog
    assert result.physical_state == "verified_at_read" and not result.removal_permitted
    assert result.validation["verified_source_files"] == 3
    assert result.validation["verified_derived_files"] == 2
    assert result.validation["verified_total_bytes"] == g.copied
    assert result.validation["expected_bytes_protected"] == "private_verified_copies"
    assert result.validation["temporal_atomicity"] == "not_proven"


@posix
@pytest.mark.parametrize("damage", ["source", "derived", "graph", "manifest", "extra", "sidecar", "missing"])
def test_corruption_never_produces_verified_result(generation, damage):
    g = generation
    name = {"source": "sources/base/data.xml", "derived": "inputs/callgraph.ndjson",
            "graph": "graph.sqlite3", "manifest": "manifest.json", "extra": "extra",
            "sidecar": "graph.sqlite3-wal", "missing": "manifest.json"}[damage]
    target = g.path / name
    if damage == "missing":
        target.unlink()
    else:
        target.write_bytes(b"corrupt")
        target.chmod(0o600)
    with pytest.raises(api.CoreError) as error:
        verify(g)
    assert error.value.code == "SNAPSHOT_CORRUPT"


@posix
def test_catalog_change_between_selection_and_session_refuses_before_io(generation, monkeypatch):
    g = generation
    original = verification.get_generation_attribution
    def change(*args):
        result = original(*args)
        with g.state.transaction(g.owner, write=True) as tx:
            tx._connection.execute("UPDATE snapshots SET generation_relpath=?", ("generations/" + str(uuid4()),))
        return result
    monkeypatch.setattr(verification, "get_generation_attribution", change)
    with pytest.raises(api.CoreError, match="catalog binding changed") as error:
        verify(g)
    assert error.value.code == "SNAPSHOT_CORRUPT"


@posix
@pytest.mark.parametrize("change", ["revoke", "catalog"])
def test_post_session_change_suppresses_success(generation, monkeypatch, change):
    from rentgen_core._posix_snapshot_session import _PosixSnapshotSession
    g = generation
    original = _PosixSnapshotSession.__exit__
    def finish(self, *args):
        result = original(self, *args)
        with g.state.transaction(g.owner, write=True) as tx:
            if change == "revoke":
                force_legacy_membership(tx, g.principal, set())
            else:
                tx._connection.execute("UPDATE snapshots SET generation_relpath=?", ("generations/" + str(uuid4()),))
        return result
    monkeypatch.setattr(_PosixSnapshotSession, "__exit__", finish)
    with pytest.raises(api.CoreError) as error:
        verify(g)
    assert error.value.code == ("PROJECT_FORBIDDEN" if change == "revoke" else "SNAPSHOT_CORRUPT")


@posix
def test_missing_graph_adapter_refuses(generation):
    with pytest.raises(api.CoreError) as error:
        api.verify_catalog_generation(context(generation), generation.catalog.generation_relpath)
    assert error.value.code == "GRAPH_ADAPTER_UNAVAILABLE"
