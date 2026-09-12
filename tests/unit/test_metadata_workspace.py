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


def test_interrupted_owned_workspace_apply_requires_recovery(
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
    with pytest.raises(api.CoreError) as error:
        workspace.apply_workspace(ctx, request["operation_id"], root)
    assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"


def test_tampered_workspace_marker_is_not_replayed(captured, tmp_path):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    marker_path = root / ".rentgen-workspace.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["source_root"] = str(tmp_path / "foreign")
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(api.CoreError) as error:
        workspace.get_workspace_status(ctx, request["operation_id"], root)
    assert error.value.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"
