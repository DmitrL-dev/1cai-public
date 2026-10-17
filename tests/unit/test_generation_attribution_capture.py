"""Real Windows capture establishes the locator; attribution remains state-only."""
from uuid import uuid4

import pytest

import rentgen_core as api
import rentgen_core.publication as publication
import test_project_core_publication as fixtures

project = fixtures.project
scanner = fixtures.scanner
pytestmark = fixtures.pytestmark


@pytest.mark.parametrize("point", ["before_complete", "after_complete", "before_commit"])
def test_failed_attempt_remains_unreferenced_and_explicit_retry_uses_new_locator(project, monkeypatch, point):
    ctx, _, _, builder = project
    before = api.get_project_head(ctx)
    operation_id = str(uuid4())
    seen = []

    def fail(name, **values):
        if name == point:
            seen.append(values["catalog"].generation_relpath)
            raise RuntimeError("stop attempt")

    monkeypatch.setattr(publication, "_boundary", fail)
    with pytest.raises(RuntimeError, match="stop attempt"):
        api.capture_and_publish(ctx, expected_head=before, builder=builder, operation_id=operation_id)
    locator = seen[0]
    assert (ctx.state.path.parent / locator).is_dir()
    result = api.get_generation_attribution(ctx, locator)
    assert result.status == "unreferenced_at_read" and result.observed_head == before
    assert result.latest_publication is None and not result.removal_permitted
    monkeypatch.setattr(publication, "_boundary", lambda *args, **kwargs: None)
    receipt = api.capture_and_publish(ctx, expected_head=before, builder=builder, operation_id=operation_id)
    with ctx.state.transaction(ctx.principal) as tx:
        entry = tx.get_snapshot(receipt.snapshot.snapshot_id)
    assert entry.generation_relpath != locator
    assert api.get_generation_attribution(ctx, locator).status == "unreferenced_at_read"
    assert api.get_generation_attribution(ctx, entry.generation_relpath).latest_publication == receipt


def test_same_content_reuses_catalog_and_does_not_attribute_redundant_attempt(project, monkeypatch):
    ctx = project[0]
    first = fixtures.publish(project)
    with ctx.state.transaction(ctx.principal) as tx:
        entry = tx.get_snapshot(first.snapshot.snapshot_id)
    attempts = []

    def observe(name, **values):
        if name == "after_capture":
            attempts.append("generations/" + values["captured"].staging_path.name)
            result = api.get_generation_attribution(ctx, attempts[-1])
            assert result.status == "unreferenced_at_read"
            assert not result.removal_permitted

    monkeypatch.setattr(publication, "_boundary", observe)
    second = fixtures.publish(project)
    assert second.snapshot == first.snapshot
    assert len(attempts) == 1 and attempts[0] != entry.generation_relpath
    assert (ctx.state.path.parent / attempts[0]).is_dir()
    assert api.get_generation_attribution(ctx, attempts[0]).status == "unreferenced_at_read"
    result = api.get_generation_attribution(ctx, entry.generation_relpath)
    assert result.catalog == entry and result.latest_publication == second


def test_lost_ack_keeps_exact_catalog_attribution(project, monkeypatch):
    def lose_ack(name, **values):
        if name == "after_commit":
            raise OSError("lost acknowledgment")

    monkeypatch.setattr(publication, "_boundary", lose_ack)
    receipt = fixtures.publish(project)
    ctx = project[0]
    with ctx.state.transaction(ctx.principal) as tx:
        entry = tx.get_snapshot(receipt.snapshot.snapshot_id)
    result = api.get_generation_attribution(ctx, entry.generation_relpath)
    assert result.status == "catalog_referenced"
    assert result.latest_publication == receipt and result.observed_head == receipt.head
