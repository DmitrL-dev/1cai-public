"""The owned workspace writer proves file CAS and undo without live 1C writes."""

import json
import os
from pathlib import Path
import subprocess
import sys

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


@pytest.mark.parametrize("operation", ["apply", "undo", "recover"])
def test_workspace_mutation_refuses_busy_operation_lock(
    captured, tmp_path, monkeypatch, operation
):
    import msvcrt

    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    if operation == "undo":
        workspace.apply_workspace(ctx, request["operation_id"], root)
    elif operation == "recover":
        original_replace = workspace.os.replace

        def interrupt(source, target):
            if "tree" in target.parts:
                raise OSError("interrupted apply")
            return original_replace(source, target)

        monkeypatch.setattr(workspace.os, "replace", interrupt)
        with pytest.raises(OSError):
            workspace.apply_workspace(ctx, request["operation_id"], root)
        monkeypatch.setattr(workspace.os, "replace", original_replace)
    lock = root / "workspace-operation.lock"
    if not lock.exists():
        lock.write_bytes(b"0")
    before = _bytes(root)
    with lock.open("r+b") as stream:
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            with pytest.raises(api.CoreError) as error:
                if operation == "recover":
                    workspace.recover_workspace(
                        ctx, request["operation_id"], root, target="original"
                    )
                else:
                    getattr(workspace, operation + "_workspace")(
                        ctx, request["operation_id"], root
                    )
            assert error.value.code == "METADATA_WORKSPACE_BUSY"
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    assert _bytes(root) == before


def test_workspace_lock_excludes_second_process_and_releases_after_error(
    captured, tmp_path, monkeypatch
):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    code = """from pathlib import Path
import sys
from rentgen_core.metadata_workspace import _workspace_lock
from rentgen_core.errors import CoreError
try:
    with _workspace_lock(Path(sys.argv[1])):
        print('acquired')
except CoreError as error:
    print(error.code)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])}

    def another_process():
        return subprocess.check_output(
            [sys.executable, "-c", code, str(root)], env=env, timeout=10
        ).strip()

    with pytest.raises(RuntimeError):
        with workspace._workspace_lock(root):
            assert another_process() == b"METADATA_WORKSPACE_BUSY"
            raise RuntimeError("operation failed")
    assert another_process() == b"acquired"
    original_write = workspace.write_record
    observed_publication = []

    def assert_lock_at_publication(path, value):
        if path.name == "workspace-result.json":
            observed_publication.append(another_process())
        return original_write(path, value)

    monkeypatch.setattr(workspace, "write_record", assert_lock_at_publication)
    assert (
        workspace.apply_workspace(ctx, request["operation_id"], root)["status"]
        == "applied"
    )
    assert observed_publication == [b"METADATA_WORKSPACE_BUSY"]
    assert another_process() == b"acquired"


@pytest.mark.parametrize(
    "unsafe", ["directory", "symlink", "junction", "hardlink", "empty"]
)
def test_workspace_operation_lock_rejects_unsafe_path(captured, tmp_path, unsafe):
    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    lock = root / "workspace-operation.lock"
    external = tmp_path / "external-lock"
    external.write_bytes(b"0")
    if unsafe == "directory":
        lock.mkdir()
    elif unsafe == "symlink":
        try:
            lock.symlink_to(external)
        except OSError as exc:
            pytest.skip("File symlinks unavailable: " + str(exc))
    elif unsafe == "hardlink":
        os.link(external, lock)
    elif unsafe == "junction":
        external_directory = tmp_path / "external-directory"
        external_directory.mkdir()
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(lock), str(external_directory)],
            check=True,
            capture_output=True,
            timeout=10,
        )
    else:
        lock.write_bytes(b"")
    original_tree = _bytes(root / "tree")
    with pytest.raises(api.CoreError) as error:
        workspace.apply_workspace(ctx, request["operation_id"], root)
    assert error.value.code == "METADATA_WORKSPACE_LOCK_INVALID"
    assert _bytes(root / "tree") == original_tree
    assert external.read_bytes() == b"0"
    assert not (root / "workspace-state.json").exists()


def test_workspace_rechecks_tree_identity_before_publishing_apply_state(
    captured, tmp_path, monkeypatch
):
    import shutil

    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    original_copy = workspace._copy_rows

    def substitute_tree(source, target, rows, **kwargs):
        original_copy(source, target, rows, **kwargs)
        if target.name == ".rentgen-stage":
            (root / "tree").rename(root / "original-tree")
            shutil.copytree(root / "original-tree", root / "tree")

    monkeypatch.setattr(workspace, "_copy_rows", substitute_tree)
    with pytest.raises(api.CoreError) as error:
        workspace.apply_workspace(ctx, request["operation_id"], root)
    assert error.value.code == "METADATA_WORKSPACE_CONFLICT"
    assert _bytes(root / "tree") == _bytes(root / "original-tree")
    assert not (root / "workspace-state.json").exists()


def test_public_contender_does_not_pin_marker_before_busy_admission(
    captured, tmp_path, monkeypatch
):
    import queue
    import threading

    ctx, request, _, root, _ = _prepared(captured, tmp_path)
    code = """from pathlib import Path
import sys
import rentgen_core as api
from rentgen_core import metadata_workspace as workspace
from rentgen_core._windows_source_tree import pinned_retained
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory
ctx = api.ContextResolver(
    api.ProjectRegistry(Path(sys.argv[1])),
    graph_reader_factory=RentgenGraphReaderFactory(),
).resolve_context(api.Principal('owner', 'local_os'), api.Explicit(sys.argv[2]), sys.argv[3])
original_read = workspace.read_retained
def observe_marker(path, maximum):
    if path.name == '.rentgen-workspace.json':
        with pinned_retained(path, maximum) as raw:
            print('marker-pinned', flush=True)
            sys.stdin.readline()
            return raw
    return original_read(path, maximum)
workspace.read_retained = observe_marker
try:
    workspace.apply_workspace(ctx, sys.argv[4], Path(sys.argv[5]))
    print('applied', flush=True)
except api.CoreError as error:
    print(error.code, flush=True)
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
    original_replace = workspace.os.replace
    observations = []

    def contend_at_publication(source, target):
        if target.name != "workspace-state.json":
            return original_replace(source, target)
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                code,
                str(ctx.source_root.parent / "registry.sqlite3"),
                ctx.project_id,
                ctx.snapshot.snapshot_id,
                request["operation_id"],
                str(root),
            ],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        events = queue.Queue()
        threading.Thread(
            target=lambda: events.put(process.stdout.readline()), daemon=True
        ).start()
        sharing_error = None
        try:
            observed = events.get(timeout=10).strip()
            observations.append(observed)
            try:
                original_replace(source, target)
            except OSError as exc:
                sharing_error = exc
        finally:
            try:
                process.communicate(input="\n", timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
                raise
        assert observed == "METADATA_WORKSPACE_BUSY", (
            "Public contender read the marker before acquiring the lock; "
            f"publication error: {sharing_error!r}"
        )
        assert sharing_error is None

    monkeypatch.setattr(workspace.os, "replace", contend_at_publication)
    assert (
        workspace.apply_workspace(ctx, request["operation_id"], root)["status"]
        == "applied"
    )
    assert observations == ["METADATA_WORKSPACE_BUSY"]


@pytest.mark.parametrize(
    "invalid",
    [
        "absent",
        "project_id",
        "operation_id",
        "source_root",
        "malformed",
        "array",
        "oversized",
        "directory",
        "hardlink",
    ],
)
def test_unowned_admission_does_not_create_lock_or_change_bytes(
    captured, tmp_path, invalid
):
    ctx, request, _, root, marker = _prepared(captured, tmp_path)
    marker_path = root / ".rentgen-workspace.json"
    if invalid == "absent":
        root = tmp_path / "foreign-workspace"
        (root / "tree").mkdir(parents=True)
        (root / "tree" / "foreign.bin").write_bytes(b"foreign tree bytes")
    elif invalid in {"project_id", "operation_id", "source_root"}:
        marker[invalid] = (
            "87654321-1234-4234-8234-123456789abc"
            if invalid != "source_root"
            else str(tmp_path / "foreign-source")
        )
        del marker["marker_id"]
        marker_path.write_bytes(
            workspace.canonical_bytes(workspace._seal(marker, "marker_id"))
        )
    elif invalid == "malformed":
        marker_path.write_bytes(b"{broken")
    elif invalid == "array":
        marker_path.write_bytes(b"[]")
    elif invalid == "oversized":
        marker_path.write_bytes(b" " * (workspace.MAX_RECORD + 1))
    elif invalid == "directory":
        marker_path.unlink()
        marker_path.mkdir()
    else:
        os.link(marker_path, tmp_path / "foreign-marker.json")
    (root / "workspace-state.json").write_bytes(b"foreign state bytes")
    before = _bytes(root)
    entries = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
    for function, kwargs in (
        (workspace.apply_workspace, {}),
        (workspace.undo_workspace, {}),
        (workspace.recover_workspace, {"target": "original"}),
    ):
        with pytest.raises(api.CoreError):
            function(ctx, request["operation_id"], root, **kwargs)
        assert _bytes(root) == before
        assert (
            sorted(str(path.relative_to(root)) for path in root.rglob("*")) == entries
        )
        assert not (root / "workspace-operation.lock").exists()
