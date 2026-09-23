"""Valid receipt hashes do not authorize replay in another owned workspace."""

import shutil
from uuid import uuid4

import pytest

import test_metadata_workspace as fixtures
from rentgen_core import CoreError, metadata_apply, metadata_workspace as workspace


project, scanner, captured, pytestmark = (
    fixtures.project,
    fixtures.scanner,
    fixtures.captured,
    fixtures.pytestmark,
)


@pytest.fixture
def pair(captured, tmp_path):
    ctx, request, _, first, _ = fixtures._prepared(captured, tmp_path)
    second_request = {**request, "operation_id": str(uuid4())}
    metadata_apply.preflight_apply(ctx, **second_request)
    second = tmp_path / "second-workspace"
    workspace.create_workspace(ctx, second_request["operation_id"], second)
    workspace.apply_workspace(ctx, request["operation_id"], first)
    workspace.apply_workspace(ctx, second_request["operation_id"], second)
    return ctx, request["operation_id"], second_request["operation_id"], first, second


def invoke(action, ctx, operation_id, root):
    if action == "status":
        return workspace.get_workspace_status(ctx, operation_id, root)
    if action == "recover":
        return workspace.recover_workspace(ctx, operation_id, root, target="original")
    return getattr(workspace, action + "_workspace")(ctx, operation_id, root)


@pytest.mark.parametrize("action", ["apply", "undo", "recover", "status"])
@pytest.mark.parametrize("receipt", ["result", "state", "undo"])
def test_foreign_sealed_receipt_is_rejected_before_any_write(pair, action, receipt):
    ctx, first_id, second_id, first, second = pair
    if receipt == "undo":
        workspace.undo_workspace(ctx, first_id, first)
        workspace.undo_workspace(ctx, second_id, second)
    name = "workspace-" + receipt + ".json"
    shutil.copyfile(second / name, first / name)
    before = fixtures._bytes(first)

    with pytest.raises(CoreError) as error:
        invoke(action, ctx, first_id, first)

    assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"
    assert fixtures._bytes(first) == before, "A foreign receipt must not permit writes"


@pytest.mark.parametrize("action", ["apply", "undo", "recover", "status"])
def test_receipt_from_same_operation_other_workspace_is_rejected(
    pair, tmp_path, action
):
    ctx, first_id, _, first, _ = pair
    sibling = tmp_path / "same-operation-workspace"
    workspace.create_workspace(ctx, first_id, sibling)
    workspace.apply_workspace(ctx, first_id, sibling)
    shutil.copyfile(sibling / "workspace-result.json", first / "workspace-result.json")
    before = fixtures._bytes(first)

    with pytest.raises(CoreError) as error:
        invoke(action, ctx, first_id, first)

    assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"
    assert fixtures._bytes(first) == before


def test_foreign_recovery_receipt_cannot_authorize_any_operation(pair):
    ctx, first_id, second_id, first, second = pair
    for operation_id, root in ((first_id, first), (second_id, second)):
        workspace.undo_workspace(ctx, operation_id, root)
        workspace.recover_workspace(ctx, operation_id, root, target="original")
    shutil.copyfile(
        second / "workspace-recovery.json", first / "workspace-recovery.json"
    )
    before = fixtures._bytes(first)
    for action in ("apply", "undo", "recover", "status"):
        with pytest.raises(CoreError) as error:
            invoke(action, ctx, first_id, first)
        assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED", action
        assert fixtures._bytes(first) == before, action


def test_foreign_result_is_rejected_before_recreating_operation_lock(pair):
    ctx, first_id, _, first, second = pair
    shutil.copyfile(second / "workspace-result.json", first / "workspace-result.json")
    (first / "workspace-operation.lock").unlink()
    before = fixtures._bytes(first)
    with pytest.raises(CoreError) as error:
        workspace.apply_workspace(ctx, first_id, first)
    assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"
    assert fixtures._bytes(first) == before


def test_resealed_false_bindings_are_rejected_without_mutation(pair):
    ctx, first_id, _, first, _ = pair
    cases = {
        "result": {
            "intent_id": "0" * 64,
            "preview_id": "0" * 64,
            "project_id": str(uuid4()),
            "before_digest": "0" * 64,
            "after_digest": "0" * 64,
            "changed_paths": [],
            "schema": True,
            "workspace_source_written": 1,
            "live_source_written": 0,
        },
        "state": {
            "result_id": "0" * 64,
            "before_digest": "0" * 64,
            "after_digest": "0" * 64,
            "schema": True,
            "foreign_field": True,
            "phase": [],
        },
    }
    for name, changes in cases.items():
        path, key = first / ("workspace-" + name + ".json"), name + "_id"
        original = path.read_bytes()
        value = workspace._read_sealed(path, key)
        del value[key]
        for field, wrong in changes.items():
            path.write_bytes(
                workspace.canonical_bytes(workspace._seal({**value, field: wrong}, key))
            )
            before = fixtures._bytes(first)
            for action in ("apply", "undo", "recover", "status"):
                with pytest.raises(CoreError) as error:
                    invoke(action, ctx, first_id, first)
                assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED", field
                assert fixtures._bytes(first) == before, (name, field, action)
        path.write_bytes(original)


def test_recovered_result_before_first_state_remains_finalizable(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = fixtures._prepared(captured, tmp_path)
    original_write = workspace._write_or_replace_record

    def stop_state(path, value):
        raise OSError("interrupted state publication")

    monkeypatch.setattr(workspace, "_write_or_replace_record", stop_state)
    with pytest.raises(OSError, match="interrupted state"):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    with pytest.raises(OSError, match="interrupted state"):
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="candidate"
        )
    assert not (root / "workspace-state.json").exists()
    assert (root / "workspace-result.json").exists()
    monkeypatch.setattr(workspace, "_write_or_replace_record", original_write)

    recovered = workspace.recover_workspace(
        ctx, request["operation_id"], root, target="candidate"
    )

    assert recovered["status"] == "recovered"
    status = workspace.get_workspace_status(ctx, request["operation_id"], root)
    assert status["state"]["result_id"] == status["result"]["result_id"]
    assert (
        workspace.apply_workspace(ctx, request["operation_id"], root)
        == status["result"]
    )


@pytest.mark.parametrize(
    "kind", ["state", "recovery", "pending_state", "pending_recovery"]
)
@pytest.mark.parametrize("lock_absent", [False, True])
def test_same_operation_sibling_phase_receipts_are_workspace_bound(
    captured, tmp_path, monkeypatch, kind, lock_absent
):
    ctx, request, _, first, _ = fixtures._prepared(captured, tmp_path)
    operation_id = request["operation_id"]
    sibling = tmp_path / "sibling-workspace"
    workspace.create_workspace(ctx, operation_id, sibling)
    original_replace = workspace._publish_replace

    def interrupt(source, target):
        if "tree" in target.parts:
            raise OSError("interrupted tree publication")
        return original_replace(source, target)

    monkeypatch.setattr(workspace, "_publish_replace", interrupt)
    for root in (first, sibling):
        with pytest.raises(OSError, match="interrupted tree"):
            workspace.apply_workspace(ctx, operation_id, root)
    monkeypatch.setattr(workspace, "_publish_replace", original_replace)
    if "recovery" in kind:
        workspace.recover_workspace(ctx, operation_id, sibling, target="original")
    receipt = "recovery" if "recovery" in kind else "state"
    source = sibling / ("workspace-" + receipt + ".json")
    destination = first / (
        "workspace-"
        + receipt
        + ".json"
        + (".tmp" if kind.startswith("pending") else "")
    )
    shutil.copyfile(source, destination)
    if lock_absent:
        (first / "workspace-operation.lock").unlink()
    before = fixtures._bytes(first)
    for action in ("status", "apply", "undo", "recover"):
        with pytest.raises(CoreError) as error:
            invoke(action, ctx, operation_id, first)
        assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED", action
        assert fixtures._bytes(first) == before, (kind, action)


@pytest.mark.parametrize("undone", [False, True])
def test_result_and_undo_are_bound_to_retained_marker_identity(pair, undone):
    ctx, operation_id, _, root, _ = pair
    if undone:
        workspace.undo_workspace(ctx, operation_id, root)
    path = root / ".rentgen-workspace.json"
    marker = workspace._read_sealed(path, "marker_id")
    del marker["marker_id"]
    marker["created_at"] = "2000-01-01T00:00:00+00:00"
    path.write_bytes(workspace.canonical_bytes(workspace._seal(marker, "marker_id")))
    before = fixtures._bytes(root)
    for action in ("status", "apply", "undo", "recover"):
        with pytest.raises(CoreError) as error:
            invoke(action, ctx, operation_id, root)
        assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED", action
        assert fixtures._bytes(root) == before, action


def legacy_phase(path, key):
    value = workspace._read_sealed(path, key)
    for field in ("workspace_root", "marker_id", key):
        del value[field]
    path.write_bytes(workspace.canonical_bytes(workspace._seal(value, key)))


def test_legacy_complete_result_replay_and_undo_remain_supported(pair):
    ctx, operation_id, _, root, _ = pair
    legacy_phase(root / "workspace-state.json", "state_id")
    before = fixtures._bytes(root)
    status = workspace.get_workspace_status(ctx, operation_id, root)
    assert workspace.apply_workspace(ctx, operation_id, root) == status["result"]
    assert (
        fixtures._bytes(root) == before
    ), "Legacy readback/replay must not migrate files"
    undo = workspace.undo_workspace(ctx, operation_id, root)
    assert undo["status"] == "undone"
    assert workspace.undo_workspace(ctx, operation_id, root) == undo


@pytest.mark.parametrize("pending", [False, True])
def test_legacy_final_undo_recovery_requires_its_local_rooted_anchor(pair, pending):
    ctx, operation_id, _, root, _ = pair
    workspace.undo_workspace(ctx, operation_id, root)
    workspace.recover_workspace(ctx, operation_id, root, target="original")
    legacy_phase(root / "workspace-state.json", "state_id")
    legacy_phase(root / "workspace-recovery.json", "recovery_id")
    expected = workspace._read_sealed(root / "workspace-recovery.json", "recovery_id")
    if pending:
        (root / "workspace-recovery.json").rename(root / "workspace-recovery.json.tmp")
    before = fixtures._bytes(root)
    status = workspace.get_workspace_status(ctx, operation_id, root)
    assert workspace.undo_workspace(ctx, operation_id, root) == status["undo"]
    assert fixtures._bytes(root) == before
    assert (
        workspace.recover_workspace(ctx, operation_id, root, target="original")
        == expected
    )


def test_legacy_applying_state_requires_explicit_recovery_without_writes(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = fixtures._prepared(captured, tmp_path)
    original = workspace._publish_replace

    def interrupt(source, target):
        if "tree" in target.parts:
            raise OSError("interrupted tree publication")
        return original(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(workspace, "_publish_replace", interrupt)
        with pytest.raises(OSError):
            workspace.apply_workspace(ctx, request["operation_id"], root)
    legacy_phase(root / "workspace-state.json", "state_id")
    before = fixtures._bytes(root)
    for action in ("status", "apply", "undo", "recover"):
        with pytest.raises(CoreError) as error:
            invoke(action, ctx, request["operation_id"], root)
        assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"
        assert fixtures._bytes(root) == before
