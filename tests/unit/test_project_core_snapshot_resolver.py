"""Capabilities pin a generation, enforce exact locators and reauthorize each call."""
from project_access_test_support import force_legacy_membership
from dataclasses import replace
from uuid import uuid4

import pytest
import base64
import rentgen_core as api
import test_project_core_publication as fixtures

project = fixtures.project
scanner = fixtures.scanner
publish = fixtures.publish
pytestmark = fixtures.pytestmark


def selected(project, snapshot=None):
    ctx, resolver, _, _ = project
    return resolver.resolve_context(
        ctx.principal, api.Explicit(ctx.project_id), snapshot
    )


def generation_path(ctx, snapshot):
    with ctx.state.transaction(ctx.principal) as tx:
        catalog = tx.get_snapshot(snapshot.snapshot_id)
    return ctx.state.path.parent / catalog.generation_relpath


def test_old_capabilities_remain_pinned_after_head_moves(project):
    first = publish(project)
    old = selected(project)
    ref = old.sources.list_entries().entries[0].ref
    raw, graph = old.sources.read_source(ref), old.graph.resolve_module(ref)
    project[2].write_bytes(project[2].read_bytes().replace(b"1", b"3"))
    second = publish(project)
    assert first.snapshot != second.snapshot
    assert old.sources.read_source(ref) == raw
    assert old.graph.resolve_module(ref) == graph
    fresh = selected(project)
    assert fresh.snapshot == second.snapshot
    with pytest.raises(api.CoreError) as error:
        fresh.sources.read_source(ref)
    assert error.value.code == "SOURCE_REF_MISMATCH"


def test_absent_explicit_snapshot_and_adapter_never_fall_back(project):
    ctx, resolver, _, _ = project
    publish(project)
    with pytest.raises(api.CoreError) as error:
        selected(project, "0" * 64)
    assert error.value.code == "SNAPSHOT_NOT_FOUND"
    with pytest.raises(api.CoreError) as error:
        api.ContextResolver(resolver.registry).resolve_context(
            ctx.principal, api.Explicit(ctx.project_id)
        )
    assert error.value.code == "GRAPH_ADAPTER_UNAVAILABLE"


@pytest.mark.parametrize(
    "file",
    [
        "manifest.json",
        "graph.sqlite3",
        "sources/base/CommonModules/ОбщийМодуль/Ext/Module.bsl",
        "inputs/callgraph.ndjson",
        "inputs/scanner-coverage.json",
    ],
)
def test_corrupt_artifacts_fail_resolver(project, file):
    result = publish(project)
    path = generation_path(project[0], result.snapshot) / file
    path.write_bytes(b"corrupt")
    with pytest.raises(api.CoreError) as error:
        selected(project)
    assert error.value.code == "SNAPSHOT_CORRUPT"


def test_every_pinned_public_call_rechecks_permissions(project):
    publish(project)
    pinned = selected(project)
    ref = pinned.sources.list_entries().entries[0].ref
    with pinned.state.transaction(pinned.principal, write=True) as tx:
        force_legacy_membership(tx, pinned.principal, {"project:admin"})
    for call in (
        lambda: pinned.sources.list_entries(),
        lambda: pinned.sources.list_entries(
            kind="module", query="МОДУЛЬ", layer="base"
        ),
        lambda: pinned.sources.resolve(ref.layer_id, ref.relative_path),
        lambda: pinned.sources.read_source(ref),
        lambda: pinned.graph.resolve_module(ref),
        lambda: pinned.graph.impact(ref),
    ):
        with pytest.raises(api.CoreError) as error:
            call()
        assert error.value.code == "PROJECT_FORBIDDEN"


def test_source_pages_validate_limit_cursor_snapshot_and_exact_spelling(project):
    project[2].parent.joinpath("other.xml").write_bytes(b"<data/>")
    publish(project)
    pinned = selected(project)
    page = pinned.sources.list_entries(limit=1)
    assert len(page.entries) == 1 and page.next_cursor
    last = pinned.sources.list_entries(limit=1, cursor=page.next_cursor)
    assert len(last.entries) == 1 and last.next_cursor is None
    assert page.entries != last.entries
    for limit in (0, 201, True, 1.5):
        with pytest.raises(api.CoreError) as error:
            pinned.sources.list_entries(limit=limit)
        assert error.value.code == "INVALID_QUERY_OPTIONS"
    for cursor, limit in (("!", 1), (page.next_cursor, 2)):
        with pytest.raises(api.CoreError) as error:
            pinned.sources.list_entries(limit=limit, cursor=cursor)
        assert error.value.code == "INVALID_SOURCE_CURSOR"
    ref = page.entries[0].ref
    for wrong in (
        replace(ref, raw_sha256="0" * 64),
        replace(
            ref,
            snapshot=api.SnapshotRef(
                str(uuid4()), ref.snapshot.snapshot_id, ref.snapshot.manifest_hash
            ),
        ),
    ):
        with pytest.raises(api.CoreError) as error:
            pinned.sources.read_source(wrong)
        assert error.value.code == "SOURCE_REF_MISMATCH"
    with pytest.raises(api.CoreError) as error:
        pinned.sources.resolve("base", ref.relative_path.lower())
    assert error.value.code == "SOURCE_NOT_FOUND"
    project[2].write_bytes(project[2].read_bytes().replace(b"1", b"2"))
    publish(project)
    with pytest.raises(api.CoreError) as error:
        selected(project).sources.list_entries(limit=1, cursor=page.next_cursor)
    assert error.value.code == "INVALID_SOURCE_CURSOR"


@pytest.mark.parametrize("depth", [0, 6, True, 1.5, None])
def test_impact_invalid_depth_is_rejected(project, depth):
    publish(project)
    pinned = selected(project)
    ref = pinned.sources.list_entries().entries[0].ref
    with pytest.raises(api.CoreError) as error:
        pinned.graph.impact(ref, depth=depth)
    assert error.value.code == "INVALID_QUERY_OPTIONS"


def test_context_rejects_different_capability_snapshot(project):
    first = publish(project)
    pinned = selected(project)
    with pytest.raises(api.CoreError) as error:
        replace(
            pinned,
            snapshot=api.SnapshotRef(first.snapshot.project_id, "0" * 64, "0" * 64),
        )
    assert error.value.code == "CONTEXT_PROJECT_MISMATCH"


@pytest.mark.parametrize("payload", [None, [], {"last": [0, "x"], "version": True}])
def test_malformed_cursor_shape_uses_domain_error(project, payload):
    from rentgen_core.manifests import canonical_bytes

    publish(project)
    cursor = base64.urlsafe_b64encode(canonical_bytes(payload)).decode()
    with pytest.raises(api.CoreError) as error:
        selected(project).sources.list_entries(cursor=cursor)
    assert error.value.code == "INVALID_SOURCE_CURSOR"


def test_graph_query_keeps_pins_across_factory_and_actual_sqlite_read(project):
    from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory

    result = publish(project)
    ctx, resolver, _, _ = project
    graph_path = generation_path(ctx, result.snapshot) / "graph.sqlite3"
    attempts = []

    class RacingFactory:
        def open(self, *, graph_path, snapshot):
            with pytest.raises(OSError):
                graph_path.rename(graph_path.with_name("moved.sqlite3"))
            with pytest.raises(OSError):
                graph_path.write_bytes(b"changed")
            attempts.append(True)
            return RentgenGraphReaderFactory().open(
                graph_path=graph_path, snapshot=snapshot
            )

    pinned = replace(resolver, graph_reader_factory=RacingFactory()).resolve_context(
        ctx.principal, api.Explicit(ctx.project_id)
    )
    ref = pinned.sources.list_entries().entries[0].ref
    assert pinned.graph.resolve_module(ref)["result"]
    assert attempts == [True]
    moved = graph_path.with_name("after-query.sqlite3")
    graph_path.rename(moved)
    moved.rename(graph_path)


def test_retained_source_junction_replacement_cannot_escape(project, tmp_path):
    import _winapi

    result = publish(project)
    pinned = selected(project)
    ref = pinned.sources.list_entries().entries[0].ref
    generation = generation_path(project[0], result.snapshot)
    original = generation / "sources" / "base"
    held = original.with_name("original")
    original.rename(held)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / ref.relative_path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"foreign")
    _winapi.CreateJunction(str(outside), str(original))
    try:
        with pytest.raises(api.CoreError) as error:
            pinned.sources.read_source(ref)
        assert error.value.code == "SNAPSHOT_CORRUPT"
        assert target.read_bytes() == b"foreign"
    finally:
        original.rmdir()
        held.rename(original)


def test_sidecar_added_after_resolution_fails_pinned_graph_query(project):
    result = publish(project)
    pinned = selected(project)
    ref = pinned.sources.list_entries().entries[0].ref
    (generation_path(project[0], result.snapshot) / "graph.sqlite3-wal").write_bytes(
        b"unexpected"
    )
    with pytest.raises(api.CoreError) as error:
        pinned.graph.resolve_module(ref)
    assert error.value.code == "SNAPSHOT_CORRUPT"


def test_unlisted_file_added_after_publication_fails_resolution(project):
    result = publish(project)
    (generation_path(project[0], result.snapshot) / "unlisted.lock").write_bytes(
        b"unlisted"
    )
    with pytest.raises(api.CoreError) as error:
        selected(project)
    assert error.value.code == "SNAPSHOT_CORRUPT"
