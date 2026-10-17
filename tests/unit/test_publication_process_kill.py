"""Real process death, SQLite recovery and native scanner capture; no power-loss claim."""
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from uuid import uuid4

import pytest

import rentgen_core as api
from rentgen_core.local import LocalRuntime
from publication_kill_support import ROOT, backend, killed_publisher

NATIVE = sys.platform == "win32" or (
    sys.platform == "linux" and platform.machine().lower() in {"x86_64", "amd64"})
native = pytest.mark.skipif(not NATIVE, reason="Actual Windows or Linux/amd64 capture")
TABLES = ("snapshots", "publication_receipts", "snapshot_events", "snapshot_outbox")


@pytest.fixture
def project(tmp_path):
    source = tmp_path.resolve() / "source"
    source.mkdir()
    module = source / "CommonModules" / "Example" / "Ext" / "Module.bsl"
    module.parent.mkdir(parents=True)
    module.write_bytes(b"Function Value() Export\nReturn 1;\nEndFunction\n")
    principal = api.Principal("kill-test-owner", "local_os")
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    registered = registry.register(principal, source_root=source,
        state_root=tmp_path / "state", display_name="Process kill public fixture")
    ctx = LocalRuntime(registry.path).state_context(principal, registered.project_id)
    return ctx, registry, module


@pytest.fixture(scope="session")
def scanner(tmp_path_factory):
    assert NATIVE
    configured = os.environ.get("RENTGEN_TEST_LINUX_SCANNER") if sys.platform == "linux" else None
    if configured:
        executable = Path(configured)
        assert executable.is_absolute() and executable.is_file()
    else:
        executable = tmp_path_factory.mktemp("publication-kill-scanner") / (
            "bsl-scan.exe" if os.name == "nt" else "bsl-scan")
        subprocess.run([shutil.which("go") or "go", "build", "-trimpath", "-buildvcs=false",
            "-o", str(executable), "./cmd/bsl-scan"], cwd=ROOT / "go",
            env={**os.environ, "CGO_ENABLED": "0"}, check=True, timeout=120, capture_output=True)
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    expected = os.environ.get("RENTGEN_TEST_LINUX_SCANNER_SHA256") if sys.platform == "linux" else None
    if expected:
        assert digest == expected
    return executable, digest


def request(project, boundary, *, scanner=None):
    ctx, registry, _ = project
    return dict(registry=str(registry.path), project=ctx.project_id,
        head=asdict(api.get_project_head(ctx)), operation=str(uuid4()), boundary=boundary,
        mode="storage" if scanner is None else "native", locator="generations/" + str(uuid4()),
        scanner=None if scanner is None else str(scanner[0]),
        scanner_digest=None if scanner is None else scanner[1])


def counts(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        return tuple(tx._connection.execute("SELECT count(*) FROM " + table).fetchone()[0]
                     for table in TABLES)


def assert_unpublished(ctx, before, operation, locator):
    assert api.get_project_head(ctx) == before
    assert counts(ctx) == (0, 0, 0, 0)
    with pytest.raises(api.CoreError) as error:
        api.get_publication(ctx, operation)
    assert error.value.code == "PUBLICATION_NOT_FOUND"
    attribution = api.get_generation_attribution(ctx, locator)
    assert attribution.status == "unreferenced_at_read"
    assert not attribution.removal_permitted


@pytest.mark.parametrize("boundary", ["before_commit", "after_commit"])
def test_sqlite_process_kill_preserves_whole_publication(project, tmp_path, boundary):
    """Portable synthetic catalog fixture proves only the state transaction."""
    ctx = project[0]
    before = api.get_project_head(ctx)
    options = request(project, boundary)
    with killed_publisher(tmp_path / "child", options):
        if boundary == "before_commit":
            assert_unpublished(ctx, before, options["operation"], options["locator"])
        else:
            assert counts(ctx) == (1, 1, 1, 1)
            receipt = api.get_publication(ctx, options["operation"])
            assert api.get_project_head(ctx) == receipt.head
    if boundary == "before_commit":
        assert_unpublished(ctx, before, options["operation"], options["locator"])
    else:
        assert counts(ctx) == (1, 1, 1, 1)
        assert api.get_publication(ctx, options["operation"]) == receipt
    # A new writer can acquire the recovered database after actual process death.
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        assert tx.get_project_head() == api.get_project_head(ctx)


@native
@pytest.mark.parametrize("boundary", [
    pytest.param("before_complete", marks=pytest.mark.skipif(sys.platform != "win32", reason="Windows complete boundary")),
    pytest.param("after_complete", marks=pytest.mark.skipif(sys.platform != "win32", reason="Windows complete boundary")),
    pytest.param("after_generation_complete", marks=pytest.mark.skipif(sys.platform != "linux", reason="Linux complete boundary")),
    "before_commit",
])
def test_native_kill_before_commit_keeps_orphan_invisible_and_retry_allocates_new(
    project, scanner, tmp_path, boundary,
):
    ctx, registry, _ = project
    before = api.get_project_head(ctx)
    options = request(project, boundary, scanner=scanner)
    with killed_publisher(tmp_path / "child", options) as marker:
        locator = marker["physical_locator"]
        assert_unpublished(ctx, before, options["operation"], locator)
    assert_unpublished(ctx, before, options["operation"], locator)
    assert (ctx.state.path.parent / locator).is_dir()
    resolver = api.ContextResolver(registry)
    with pytest.raises(api.CoreError) as error:
        resolver.resolve_context(ctx.principal, api.Explicit(ctx.project_id),
            marker["catalog"]["snapshot"]["snapshot_id"])
    assert error.value.code == "SNAPSHOT_NOT_FOUND"
    result = api.capture_and_publish(ctx, expected_head=before,
        builder=backend(*scanner), operation_id=options["operation"])
    assert result.head.revision == before.revision + 1 and counts(ctx) == (1, 1, 1, 1)
    with ctx.state.transaction(ctx.principal) as tx:
        catalog = tx.get_snapshot(result.snapshot.snapshot_id)
    assert catalog.generation_relpath != locator
    assert api.get_generation_attribution(ctx, locator).status == "unreferenced_at_read"
    assert (ctx.state.path.parent / locator).is_dir()
    assert api.get_generation_attribution(ctx, catalog.generation_relpath).latest_publication == result


@native
@pytest.mark.parametrize("reuse", [False, True], ids=["new-content", "same-content-reuse"])
def test_native_kill_after_commit_replays_exact_receipt_after_later_head(
    project, scanner, tmp_path, reuse,
):
    ctx, registry, module = project
    builder = backend(*scanner)
    if reuse:
        first = api.capture_and_publish(ctx, expected_head=api.get_project_head(ctx),
            builder=builder, operation_id=str(uuid4()))
    before = api.get_project_head(ctx)
    options = request(project, "after_commit", scanner=scanner)
    with killed_publisher(tmp_path / "child", options) as marker:
        committed = api.get_publication(ctx, options["operation"])
        assert api.get_project_head(ctx) == committed.head
        assert committed.head.revision == before.revision + 1
        assert counts(ctx) == (1, 1 + reuse, 1 + reuse, 1 + reuse)
    assert api.get_publication(ctx, options["operation"]) == committed
    assert counts(ctx) == (1, 1 + reuse, 1 + reuse, 1 + reuse)
    physical = api.get_generation_attribution(ctx, marker["physical_locator"])
    if reuse:
        assert committed.snapshot == first.snapshot
        assert physical.status == "unreferenced_at_read"
        assert marker["physical_locator"] != marker["catalog"]["generation_relpath"]
    else:
        assert physical.latest_publication == committed
    # Resolve real retained sources/graph after kill, then move head and replay
    # the old operation with no source or builder available.
    from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory

    resolver = api.ContextResolver(registry, graph_reader_factory=RentgenGraphReaderFactory())
    selected = resolver.resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    ref = selected.sources.list_entries().entries[0].ref
    raw = module.read_bytes()
    assert selected.sources.read_source(ref) == raw
    assert selected.graph.resolve_module(ref)["result"]
    module.write_bytes(raw.replace(b"1", b"2"))
    later = api.capture_and_publish(ctx, expected_head=committed.head,
        builder=builder, operation_id=str(uuid4()))
    assert later.snapshot != committed.snapshot
    module.unlink()
    generations = set((ctx.state.path.parent / "generations").iterdir())
    assert api.capture_and_publish(ctx, expected_head=before, builder=None,
        operation_id=options["operation"]) == committed
    assert api.get_project_head(ctx) == later.head
    assert counts(ctx) == (2, 2 + reuse, 2 + reuse, 2 + reuse)
    assert set((ctx.state.path.parent / "generations").iterdir()) == generations
    assert selected.sources.read_source(ref) == raw
