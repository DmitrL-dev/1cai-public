"""The owned workspace writer proves file CAS and undo without live 1C writes."""

import json

import pytest
import rentgen_core as api
import test_metadata_runs as fixtures

from rentgen_core import metadata_workspace as workspace
from rentgen_core import metadata_apply


project, scanner, captured, pytestmark = (
    fixtures.project,
    fixtures.scanner,
    fixtures.captured,
    fixtures.pytestmark,
)


def _request(captured):
    ctx, preview_operation, run, preview = fixtures._finished_run(captured)
    request = {
        "preview_operation_id": preview_operation,
        "operation_id": "",
        "expected_preview_id": preview["preview_id"],
        "expected_head": api.get_project_head(ctx),
    }
    return ctx, request, preview


def _bytes(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _prepared(captured, tmp_path):
    ctx, request, preview = _request(captured)
    request["operation_id"] = "12345678-1234-4234-8234-123456789abc"
    metadata_apply.preflight_apply(ctx, **request)
    root = tmp_path / "owned-workspace"
    marker = workspace.create_workspace(ctx, request["operation_id"], root)
    return ctx, request, preview, root, marker


def test_owned_workspace_apply_and_undo_are_cas_bound(captured, tmp_path):
    ctx, request, preview, root, marker = _prepared(captured, tmp_path)
    original_live = _bytes(ctx.source_root)
    original_workspace = _bytes(root / "tree")
    assert original_workspace == original_live
    assert marker["original_digest"] == workspace._digest(marker["original_inventory"])

    result = workspace.apply_workspace(ctx, request["operation_id"], root)
    assert result["status"] == "applied"
    assert result["workspace_source_written"] is True
    assert result["live_source_written"] is False
    assert _bytes(ctx.source_root) == original_live
    candidate, _ = workspace._candidate(ctx, marker)
    assert _bytes(root / "tree") == _bytes(candidate)
    assert result["after_digest"] == workspace._digest(
        preview["preview"]["inventories"]["candidate"]
    )
    assert workspace.apply_workspace(ctx, request["operation_id"], root) == result

    undo = workspace.undo_workspace(ctx, request["operation_id"], root)
    assert undo["status"] == "undone"
    assert undo["live_source_written"] is False
    assert _bytes(root / "tree") == original_workspace
    assert _bytes(ctx.source_root) == original_live
    assert workspace.undo_workspace(ctx, request["operation_id"], root) == undo


def test_owned_workspace_refuses_stale_tree_before_apply(captured, tmp_path):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    target = next((root / "tree").rglob("*.xml"))
    target.write_bytes(target.read_bytes() + b"\nexternal")
    with pytest.raises(api.CoreError) as error:
        workspace.apply_workspace(ctx, request["operation_id"], root)
    assert error.value.code == "METADATA_APPLY_STALE"
    assert not (root / "workspace-result.json").exists()


def test_owned_workspace_undo_refuses_foreign_change(captured, tmp_path):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    workspace.apply_workspace(ctx, request["operation_id"], root)
    target = next((root / "tree").rglob("*.xml"))
    target.write_bytes(target.read_bytes() + b"\nforeign")
    with pytest.raises(api.CoreError) as error:
        workspace.undo_workspace(ctx, request["operation_id"], root)
    assert error.value.code == "METADATA_UNDO_CONFLICT"


@pytest.mark.parametrize("target", ["original", "candidate"])
def test_interrupted_owned_workspace_apply_can_be_recovered(
    captured, tmp_path, monkeypatch, target
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original = _bytes(root / "tree")
    candidate, _ = workspace._candidate(
        ctx, workspace._read_sealed(root / ".rentgen-workspace.json", "marker_id")
    )
    expected = _bytes(candidate)
    original_replace = workspace.os.replace
    calls = {"count": 0}

    def interrupt(source, target):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated interruption")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)
    recovered = workspace.recover_workspace(
        ctx, request["operation_id"], root, target=target
    )
    assert recovered["status"] == "recovered"
    assert (
        workspace.get_workspace_status(ctx, request["operation_id"], root)["recovery"]
        == recovered
    )
    if target == "original":
        assert recovered["target"] == "original"
        assert _bytes(root / "tree") == original
        assert (
            workspace.apply_workspace(ctx, request["operation_id"], root)["status"]
            == "applied"
        )
    else:
        assert recovered["target"] == "candidate"
        assert _bytes(root / "tree") == expected
        assert (
            workspace.get_workspace_status(ctx, request["operation_id"], root)[
                "result"
            ]["status"]
            == "applied"
        )


def test_interrupted_workspace_recovery_rejects_foreign_tree_file(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original_replace = workspace.os.replace
    calls = {"count": 0}

    def interrupt(source, target):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated interruption")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)
    (root / "tree" / "foreign.txt").write_bytes(b"foreign")
    with pytest.raises(api.CoreError) as error:
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="original"
        )
    assert error.value.code == "METADATA_WORKSPACE_CONFLICT"


def test_recovery_finalizes_result_written_before_state(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original_replace = workspace._replace_record

    def interrupt(path, value):
        raise OSError("simulated finalization interruption")

    monkeypatch.setattr(workspace, "_replace_record", interrupt)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace, "_replace_record", original_replace)
    assert (root / "workspace-result.json").exists()
    assert (
        workspace.get_workspace_status(ctx, request["operation_id"], root)["state"][
            "phase"
        ]
        == "applying"
    )

    recovered = workspace.recover_workspace(
        ctx, request["operation_id"], root, target="candidate"
    )
    assert recovered["target"] == "candidate"
    status = workspace.get_workspace_status(ctx, request["operation_id"], root)
    assert status["state"]["phase"] == "complete"
    assert status["result"]["status"] == "applied"
    assert (
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="candidate"
        )
        == recovered
    )


def test_tampered_workspace_marker_is_not_replayed(captured, tmp_path):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    marker_path = root / ".rentgen-workspace.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["source_root"] = str(tmp_path / "foreign")
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(api.CoreError) as error:
        workspace.get_workspace_status(ctx, request["operation_id"], root)
    assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"


def test_original_recovery_does_not_consume_backup_of_new_apply(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original_replace = workspace.os.replace
    calls = {"count": 0}

    def interrupt(source, target):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated interruption")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)

    workspace.recover_workspace(ctx, request["operation_id"], root, target="original")
    workspace.apply_workspace(ctx, request["operation_id"], root)
    with pytest.raises(api.CoreError) as error:
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="original"
        )
    assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"
    assert (
        workspace.undo_workspace(ctx, request["operation_id"], root)["status"]
        == "undone"
    )


def test_candidate_recovery_resumes_after_recovery_receipt_is_written(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original_replace = workspace.os.replace
    calls = {"count": 0}

    def interrupt(source, target):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated apply interruption")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)

    original_write = workspace.write_record
    calls = {"count": 0}

    def interrupt_result(path, value):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated recovery interruption")
        return original_write(path, value)

    monkeypatch.setattr(workspace, "write_record", interrupt_result)
    with pytest.raises(OSError):
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="candidate"
        )
    monkeypatch.setattr(workspace, "write_record", original_write)

    recovered = workspace.recover_workspace(
        ctx, request["operation_id"], root, target="candidate"
    )
    assert recovered["status"] == "recovered"
    assert (
        workspace.get_workspace_status(ctx, request["operation_id"], root)["state"][
            "phase"
        ]
        == "complete"
    )


def test_recovery_receipt_cannot_be_replayed_for_another_target(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original_replace = workspace.os.replace
    calls = {"count": 0}

    def interrupt(source, target):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated apply interruption")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)

    recovered = workspace.recover_workspace(
        ctx, request["operation_id"], root, target="candidate"
    )
    assert recovered["target"] == "candidate"
    with pytest.raises(api.CoreError) as error:
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="original"
        )
    assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"
    assert (
        workspace._digest(workspace._inventory(root / "tree", lambda: None))
        == recovered["restored_digest"]
    )


def test_reapply_recovers_after_staging_before_new_state(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original_replace = workspace.os.replace
    calls = {"count": 0}

    def interrupt(source, target):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated apply interruption")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)
    workspace.recover_workspace(ctx, request["operation_id"], root, target="original")

    original_write_state = workspace._write_or_replace_record

    def interrupt_state(path, value):
        if path.name == "workspace-state.json" and value.get("phase") == "applying":
            raise OSError("simulated prejournal interruption")
        return original_write_state(path, value)

    monkeypatch.setattr(workspace, "_write_or_replace_record", interrupt_state)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace, "_write_or_replace_record", original_write_state)
    assert (root / ".rentgen-backup").is_dir()
    assert (root / ".rentgen-stage").is_dir()

    result = workspace.apply_workspace(ctx, request["operation_id"], root)
    assert result["status"] == "applied"


def test_reapply_recovery_accepts_candidate_after_receipt_cleanup_interrupt(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original_replace = workspace.os.replace
    calls = {"count": 0}

    def interrupt(source, target):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated apply interruption")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)
    workspace.recover_workspace(ctx, request["operation_id"], root, target="original")

    original_unlink = workspace.Path.unlink

    def interrupt_receipt(path, *args, **kwargs):
        if path.name == "workspace-recovery.json":
            raise OSError("simulated recovery cleanup interruption")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(workspace.Path, "unlink", interrupt_receipt)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.Path, "unlink", original_unlink)
    assert (
        workspace.get_workspace_status(ctx, request["operation_id"], root)["state"][
            "phase"
        ]
        == "applying"
    )

    recovered = workspace.recover_workspace(
        ctx, request["operation_id"], root, target="candidate"
    )
    assert recovered["target"] == "candidate"


@pytest.mark.parametrize("damage", ["corrupt", "missing", "foreign"])
def test_undo_rejects_invalid_backup_before_mutating_tree(captured, tmp_path, damage):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    workspace.apply_workspace(ctx, request["operation_id"], root)
    backup = root / ".rentgen-backup"
    leaf = next(backup.rglob("*.xml"))
    if damage == "corrupt":
        leaf.write_bytes(b"corrupt backup")
    elif damage == "missing":
        leaf.unlink()
    else:
        (backup / "foreign.txt").write_bytes(b"foreign backup file")
    before = _bytes(root)

    with pytest.raises(api.CoreError) as error:
        workspace.undo_workspace(ctx, request["operation_id"], root)
    assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"
    assert _bytes(root) == before, "Invalid backup must fail before any undo mutation"


@pytest.mark.parametrize(
    "boundary", ["first_file", "undo_receipt", "undoing_state", "complete_state"]
)
def test_interrupted_undo_preserves_backup_and_recovers_original(
    captured, tmp_path, monkeypatch, boundary
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original = _bytes(root / "tree")
    workspace.apply_workspace(ctx, request["operation_id"], root)
    original_replace, original_write = workspace.os.replace, workspace.write_record
    stopped = False

    def interrupt_replace(source, target):
        nonlocal stopped
        if not stopped and boundary == "first_file" and "tree" in target.parts:
            original_replace(source, target)
            stopped = True
            raise OSError("interrupted undo replacement")
        if not stopped and target.name == "workspace-state.json":
            phase = json.loads(source.read_bytes())["phase"]
            if (boundary, phase) in {
                ("undoing_state", "undoing"),
                ("complete_state", "complete"),
            }:
                stopped = True
                raise OSError("interrupted undo state publication")
        return original_replace(source, target)

    def interrupt_write(path, value):
        if boundary == "undo_receipt" and path.name == "workspace-undo.json":
            raise OSError("interrupted undo receipt")
        return original_write(path, value)

    monkeypatch.setattr(workspace.os, "replace", interrupt_replace)
    monkeypatch.setattr(workspace, "write_record", interrupt_write)
    with pytest.raises(OSError, match="interrupted undo"):
        workspace.undo_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)
    monkeypatch.setattr(workspace, "write_record", original_write)
    assert _bytes(root / ".rentgen-backup") == original
    with pytest.raises(api.CoreError):
        workspace.undo_workspace(ctx, request["operation_id"], root)
    before_recovery = _bytes(root)
    with pytest.raises(api.CoreError):
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="candidate"
        )
    assert _bytes(root) == before_recovery

    recovered = workspace.recover_workspace(
        ctx, request["operation_id"], root, target="original"
    )
    assert recovered["status"] == "recovered" and recovered["target"] == "original"
    assert _bytes(root / "tree") == original
    assert _bytes(root / ".rentgen-backup") == original
    assert not (root / ".rentgen-undo-stage").exists()
    status = workspace.get_workspace_status(ctx, request["operation_id"], root)
    assert status["undo"]["status"] == "undone"
    assert status["state"]["phase"] == "complete"
    assert (
        workspace.undo_workspace(ctx, request["operation_id"], root) == status["undo"]
    )
    assert (
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="original"
        )
        == recovered
    )


@pytest.mark.parametrize("foreign_root", ["tree", ".rentgen-undo-stage"])
def test_undo_recovery_preserves_foreign_files(
    captured, tmp_path, monkeypatch, foreign_root
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    workspace.apply_workspace(ctx, request["operation_id"], root)
    original_replace = workspace.os.replace

    def interrupt(source, target):
        if "tree" in target.parts:
            raise OSError("interrupted undo")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        workspace.undo_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)
    folder = root / foreign_root
    folder.mkdir(exist_ok=True)
    (folder / "foreign.txt").write_bytes(b"foreign")
    before = _bytes(root)
    with pytest.raises(api.CoreError):
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="original"
        )
    assert _bytes(root) == before


def test_undo_recovery_resumes_after_recovery_receipt_replace(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original = _bytes(root / "tree")
    original_replace = workspace.os.replace

    def interrupt_tree(source, target):
        if "tree" in target.parts:
            raise OSError("interrupted tree write")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt_tree)
    with pytest.raises(OSError):
        workspace.apply_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)
    workspace.recover_workspace(ctx, request["operation_id"], root, target="candidate")
    monkeypatch.setattr(workspace.os, "replace", interrupt_tree)
    with pytest.raises(OSError):
        workspace.undo_workspace(ctx, request["operation_id"], root)

    def interrupt_receipt(source, target):
        if target.name == "workspace-recovery.json":
            raise OSError("interrupted recovery receipt")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt_receipt)
    with pytest.raises(OSError, match="interrupted recovery receipt"):
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="original"
        )
    monkeypatch.setattr(workspace.os, "replace", original_replace)
    assert _bytes(root / "tree") == original
    assert _bytes(root / ".rentgen-backup") == original
    recovered = workspace.recover_workspace(
        ctx, request["operation_id"], root, target="original"
    )
    assert recovered["status"] == "recovered"
    assert not (root / "workspace-recovery.json.tmp").exists()
    assert (
        workspace.get_workspace_status(ctx, request["operation_id"], root)["recovery"]
        == recovered
    )


def test_undo_recovery_rejects_corrupt_prior_receipt_before_mutation(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    workspace.apply_workspace(ctx, request["operation_id"], root)
    original_replace = workspace.os.replace

    def interrupt(source, target):
        if "tree" in target.parts:
            raise OSError("interrupted undo")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        workspace.undo_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)
    (root / "workspace-recovery.json").write_bytes(b"corrupt receipt")
    before = _bytes(root)
    with pytest.raises(api.CoreError):
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="original"
        )
    assert _bytes(root) == before


@pytest.mark.parametrize("invalid_record", ["state", "undo"])
def test_undo_recovery_rejects_invalid_sealed_record_schema(
    captured, tmp_path, monkeypatch, invalid_record
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    workspace.apply_workspace(ctx, request["operation_id"], root)
    original_replace = workspace.os.replace

    def interrupt(source, target):
        if (
            target.name == "workspace-state.json"
            and json.loads(source.read_bytes())["phase"] == "complete"
        ):
            raise OSError("interrupted undo completion")
        return original_replace(source, target)

    monkeypatch.setattr(workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        workspace.undo_workspace(ctx, request["operation_id"], root)
    monkeypatch.setattr(workspace.os, "replace", original_replace)
    path = root / (
        "workspace-state.json" if invalid_record == "state" else "workspace-undo.json"
    )
    key = "state_id" if invalid_record == "state" else "undo_id"
    value = workspace._read_sealed(path, key)
    del value[key]
    if invalid_record == "state":
        value["foreign_field"] = True
    else:
        del value["created_at"]
    path.write_bytes(workspace.canonical_bytes(workspace._seal(value, key)))
    before = _bytes(root)
    with pytest.raises(api.CoreError) as error:
        workspace.recover_workspace(
            ctx, request["operation_id"], root, target="original"
        )
    assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"
    assert _bytes(root) == before
