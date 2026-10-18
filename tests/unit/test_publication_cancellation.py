"""Portable admission and actual Windows cancellation at publication boundaries."""
from contextlib import contextmanager
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

import rentgen_core as api
from rentgen_core import publication, capture
from rentgen_core.errors import CoreError
from test_generation_attribution import project, catalog, commit
from test_publication_process_kill import project as captured_project, scanner
from publication_kill_support import backend

windows = pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows publication cancellation")
TABLES = ("snapshots", "publication_receipts", "snapshot_events", "snapshot_outbox")


def counts(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        return [tx._connection.execute("SELECT count(*) FROM " + name).fetchone()[0] for name in TABLES]


@pytest.mark.parametrize("mode", ["cancel", "invalid", "exception"])
def test_cancel_refuses_before_candidate_or_builder(project, monkeypatch, mode):
    ctx, _ = project
    monkeypatch.setattr(publication, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(capture, "_capture_generation", lambda *a, **k: pytest.fail("Capture began before cancellation"))
    head = api.get_project_head(ctx)
    def broken(): raise RuntimeError("trusted callback failed")
    callback = {"cancel": lambda: True, "invalid": None, "exception": broken}[mode]
    with pytest.raises(RuntimeError if mode == "exception" else CoreError) as error:
        api.capture_and_publish(ctx, expected_head=head, operation_id=str(uuid4()), builder=None, cancelled=callback)
    if mode != "exception":
        assert error.value.code == ("GRAPH_SCANNER_CANCELLED" if mode == "cancel" else "INVALID_QUERY_OPTIONS")
    assert counts(ctx) == [0] * 4 and api.get_project_head(ctx) == head
    assert not (ctx.state.path.parent / "generations").exists()


def test_receipt_replay_does_not_poll_cancel_or_open_sources(project, monkeypatch):
    ctx, _ = project
    monkeypatch.setattr(publication, "sys", SimpleNamespace(platform="win32"))
    head = api.get_project_head(ctx)
    published = commit(ctx, catalog(ctx))
    commit(ctx, catalog(ctx, "e"))
    def forbidden(): pytest.fail("Durable replay polled cancellation")
    monkeypatch.setattr(capture, "_capture_generation", lambda *a, **k: pytest.fail("Replay captured sources"))
    assert api.capture_and_publish(ctx, expected_head=head, operation_id=published.operation_id,
                                   builder=None, cancelled=forbidden) == published


@windows
@pytest.mark.parametrize("phase", ["after_capture", "after_build", "before_complete", "after_complete", "before_state_transaction"])
def test_native_windows_cancel_keeps_attempt_unpublished_and_retry_allocates_new(captured_project, scanner, monkeypatch, phase):
    ctx, _, _ = captured_project
    head, operation = api.get_project_head(ctx), str(uuid4())
    cancelled = False
    def boundary(name, **values):
        nonlocal cancelled
        if name == phase: cancelled = True
    monkeypatch.setattr(publication, "_boundary", boundary)
    with pytest.raises(CoreError) as error:
        api.capture_and_publish(ctx, expected_head=head, operation_id=operation,
                               builder=backend(*scanner), cancelled=lambda: cancelled)
    assert error.value.code == "GRAPH_SCANNER_CANCELLED"
    assert api.get_project_head(ctx) == head and counts(ctx) == [0] * 4
    generations = ctx.state.path.parent / "generations"
    attempts = set(generations.iterdir())
    assert len(attempts) == 1
    orphan = next(iter(attempts))
    inventory = {p.relative_to(orphan).as_posix(): p.read_bytes() for p in orphan.rglob("*") if p.is_file()}
    attribution = api.get_generation_attribution(ctx, "generations/" + orphan.name)
    assert attribution.status == "unreferenced_at_read" and not attribution.removal_permitted
    if phase == "after_capture": assert not (orphan / "build-work").exists()
    if phase == "after_build": assert not (orphan / "manifest.json").exists()
    # The cancelled worker has closed its candidate pins without deleting files.
    moved = generations / str(uuid4())
    orphan.rename(moved); moved.rename(orphan)
    monkeypatch.setattr(publication, "_boundary", lambda *a, **k: None)
    result = api.capture_and_publish(ctx, expected_head=head, operation_id=operation, builder=backend(*scanner))
    assert counts(ctx) == [1] * 4 and api.get_publication(ctx, operation) == result
    assert len(set(generations.iterdir()) - attempts) == 1
    assert {p.relative_to(orphan).as_posix(): p.read_bytes() for p in orphan.rglob("*") if p.is_file()} == inventory
    assert api.get_generation_attribution(ctx, "generations/" + orphan.name).status == "unreferenced_at_read"


@windows
@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_native_windows_late_cancel_preserves_receipt_and_never_polls_inside_write(captured_project, scanner, monkeypatch, phase):
    ctx, _, module = captured_project
    head, operation = api.get_project_head(ctx), str(uuid4())
    cancelled = False
    sampled = []
    original = type(ctx.state).transaction
    @contextmanager
    def transaction(state, principal, *, write=False):
        with original(state, principal, write=write) as tx:
            flags[0] = write
            try: yield tx
            finally: flags[0] = False
    flags = [False]
    monkeypatch.setattr(type(ctx.state), "transaction", transaction)
    def callback():
        assert not flags[0], "Cancellation callback ran inside write UOW"
        sampled.append(cancelled)
        return cancelled
    def boundary(name, **values):
        nonlocal cancelled
        if name == phase: cancelled = True
    monkeypatch.setattr(publication, "_boundary", boundary)
    first = api.capture_and_publish(ctx, expected_head=head, operation_id=operation,
                                   builder=backend(*scanner), cancelled=callback)
    assert cancelled and sampled and not any(sampled)
    assert api.get_publication(ctx, operation) == first and counts(ctx) == [1] * 4
    monkeypatch.setattr(publication, "_boundary", lambda *a, **k: None)
    module.write_bytes(module.read_bytes().replace(b"Return 1", b"Return 2"))
    later = api.capture_and_publish(ctx, expected_head=first.head, operation_id=str(uuid4()), builder=backend(*scanner))
    ctx.source_root.rename(ctx.source_root.with_name("removed-live-source"))
    before = counts(ctx)
    replay = api.capture_and_publish(ctx, expected_head=head, operation_id=operation, builder=None,
                                    cancelled=lambda: pytest.fail("Replay polled cancellation"))
    assert replay == first and api.get_project_head(ctx) == later.head and counts(ctx) == before
