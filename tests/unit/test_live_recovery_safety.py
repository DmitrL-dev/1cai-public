"""Portable recovery CAS regressions using sealed journals and synthetic trees.

Only the Windows retained-read/inventory seam and project authorization are
replaced. Journal validation, backup hashes, staging and source writes are real.
These tests do not establish Windows handle or atomic replacement guarantees.
"""

import hashlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from rentgen_core import metadata_live_apply, proposal_live_apply
from rentgen_core import _live_recovery_stage
from rentgen_core.errors import CoreError


CHANGED = "CommonModules/Example/Ext/Module.bsl"
SECOND = "CommonModules/Second/Ext/Module.bsl"
OTHER = "Configuration.xml"


def _row(name, raw):
    return {"path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _inventory(root):
    return [
        _row(path.relative_to(root).as_posix(), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _tree_bytes(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _read_fixture(path, maximum):
    raw = Path(path).read_bytes()
    assert len(raw) <= maximum
    return raw


@pytest.fixture(
    params=[metadata_live_apply, proposal_live_apply], ids=["metadata", "proposal"]
)
def interrupted_apply(tmp_path, monkeypatch, request):
    writer = request.param
    source, state = tmp_path / "source", tmp_path / "state"
    source.mkdir()
    state.mkdir()
    ctx = SimpleNamespace(
        project_id=str(uuid4()), source_root=source,
        state=SimpleNamespace(path=state / "project.sqlite3"),
    )
    operation = str(uuid4())
    original = {CHANGED: b"Return 1;\n", OTHER: b"<Configuration/>\n"}
    changed = {**original, CHANGED: b"Return 2;\n"}
    changed_paths = [CHANGED]
    if writer is metadata_live_apply:
        original[SECOND], changed[SECOND] = b"Return 3;\n", b"Return 4;\n"
        changed_paths.append(SECOND)
    before = [_row(name, original[name]) for name in sorted(original)]
    after = [_row(name, changed[name]) for name in sorted(changed)]
    for name, raw in changed.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    journal = writer.journal_path(ctx, operation)
    journal.mkdir(parents=True)
    for name in changed_paths:
        backup = journal / "backup" / name
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(original[name])
    intent = {
        "schema": 1, "project_id": ctx.project_id, "operation_id": operation,
        "source_root": str(source), "changed_paths": changed_paths,
        "before_inventory": before, "after_inventory": after,
    }
    if writer is metadata_live_apply:
        intent.update(preview_id="a" * 64, preflight_intent_id="b" * 64)
    else:
        intent.update(
            layer_id="base", proposal_content_id="a" * 64,
            before_digest=writer._digest(before), after_digest=writer._digest(after),
            source_ref={
                "snapshot": {
                    "project_id": ctx.project_id, "snapshot_id": "b" * 64,
                    "manifest_hash": "b" * 64,
                },
                "layer_id": "base", "relative_path": CHANGED,
                "raw_sha256": _row(CHANGED, original[CHANGED])["sha256"],
            },
        )
    writer.write_record(journal / "intent.json", writer._seal(intent, "intent_id"))
    writer.write_record(
        journal / "state.json",
        writer._seal(
            {"schema": 1, "operation_id": operation, "phase": "applying"}, "state_id"
        ),
    )
    monkeypatch.setattr(writer, "_check", lambda _: None)
    monkeypatch.setattr(writer, "_source_rows", lambda _: _inventory(source))
    monkeypatch.setattr(writer, "read_retained", _read_fixture)
    monkeypatch.setattr(_live_recovery_stage, "read_retained", _read_fixture)
    return SimpleNamespace(
        writer=writer, ctx=ctx, operation=operation, journal=journal,
        original=original, changed=changed,
        conflict=(
            "METADATA_LIVE_UNDO_CONFLICT" if writer is metadata_live_apply
            else "PROPOSAL_LIVE_UNDO_CONFLICT"
        ),
    )


def test_recovery_preserves_edit_during_staging(interrupted_apply, monkeypatch):
    run = interrupted_apply
    prepare = run.writer.prepare_recovery_stage

    def edit_after_staging(*args, **kwargs):
        stage = prepare(*args, **kwargs)
        (run.ctx.source_root / CHANGED).write_bytes(b"user edit during staging\n")
        return stage

    monkeypatch.setattr(run.writer, "prepare_recovery_stage", edit_after_staging)
    with pytest.raises(CoreError) as error:
        run.writer.recover_live(run.ctx, run.operation, target="original")

    assert error.value.code == run.conflict
    assert (run.ctx.source_root / CHANGED).read_bytes() == b"user edit during staging\n"
    assert not (run.journal / "result.json").exists()
    assert (
        run.writer.get_live_status(run.ctx, run.operation)["status"]
        == "OUTCOME_UNKNOWN"
    )


@pytest.mark.parametrize("change", ["modify", "add", "remove"])
def test_recovery_refuses_foreign_inventory_before_any_write(interrupted_apply, change):
    run = interrupted_apply
    other = run.ctx.source_root / OTHER
    if change == "modify":
        other.write_bytes(b"foreign configuration\n")
    elif change == "add":
        (run.ctx.source_root / "new-user-file.bsl").write_bytes(b"foreign addition\n")
    else:
        other.unlink()
    expected = _tree_bytes(run.ctx.source_root)

    with pytest.raises(CoreError) as error:
        run.writer.recover_live(run.ctx, run.operation, target="original")

    assert _tree_bytes(run.ctx.source_root) == expected
    assert error.value.code == run.conflict
    assert not (run.journal / "result.json").exists()


def test_recovery_rechecks_source_even_when_original_file_was_skipped(
    interrupted_apply, monkeypatch
):
    run = interrupted_apply
    (run.ctx.source_root / CHANGED).write_bytes(run.original[CHANGED])
    prepare = run.writer.prepare_recovery_stage

    def edit_after_staging(*args, **kwargs):
        stage = prepare(*args, **kwargs)
        (run.ctx.source_root / CHANGED).write_bytes(b"user edit after restoration\n")
        return stage

    monkeypatch.setattr(run.writer, "prepare_recovery_stage", edit_after_staging)
    with pytest.raises(CoreError) as error:
        run.writer.recover_live(run.ctx, run.operation, target="original")

    assert error.value.code == run.conflict
    assert (run.ctx.source_root / CHANGED).read_bytes() == (
        b"user edit after restoration\n"
    )


def test_recovery_rejects_corrupt_backup_without_source_write(interrupted_apply):
    run = interrupted_apply
    (run.journal / "backup" / CHANGED).write_bytes(b"corrupt backup\n")

    with pytest.raises(CoreError) as error:
        run.writer.recover_live(run.ctx, run.operation, target="original")

    assert error.value.code == run.writer.RECOVERY
    assert _tree_bytes(run.ctx.source_root) == run.changed


@pytest.mark.parametrize("interrupted_apply", [metadata_live_apply], indirect=True)
def test_recovery_preserves_edit_between_file_restores(interrupted_apply, monkeypatch):
    run = interrupted_apply
    replace = run.writer.os.replace

    def edit_after_first_restore(source, target):
        replace(source, target)
        if Path(target) == run.ctx.source_root / CHANGED:
            (run.ctx.source_root / SECOND).write_bytes(b"user edit between restores\n")

    monkeypatch.setattr(run.writer.os, "replace", edit_after_first_restore)
    with pytest.raises(CoreError) as error:
        run.writer.recover_live(run.ctx, run.operation, target="original")

    assert error.value.code == run.conflict
    assert (run.ctx.source_root / CHANGED).read_bytes() == run.original[CHANGED]
    assert (run.ctx.source_root / SECOND).read_bytes() == (
        b"user edit between restores\n"
    )
    assert not (run.journal / "result.json").exists()
    status = run.writer.get_live_status(run.ctx, run.operation)
    assert status["status"] == "OUTCOME_UNKNOWN"
    assert status["phase"] == "undoing"

    monkeypatch.setattr(run.writer.os, "replace", replace)
    (run.ctx.source_root / SECOND).write_bytes(run.changed[SECOND])
    assert (
        run.writer.recover_live(run.ctx, run.operation, target="original")["status"]
        == "recovered"
    )
    assert _tree_bytes(run.ctx.source_root) == run.original


@pytest.mark.parametrize(
    "boundary", ["before_source", "after_source", "receipt", "terminal_state"]
)
def test_interrupted_recovery_preserves_cause_and_resumes(
    interrupted_apply, monkeypatch, boundary
):
    run = interrupted_apply
    replace = run.writer.os.replace
    failure = OSError("injected recovery interruption at " + boundary)

    def interrupt(source, target):
        target = Path(target)
        if target == run.ctx.source_root / CHANGED:
            if boundary == "before_source":
                raise failure
            if boundary == "after_source":
                replace(source, target)
                raise failure
        if boundary == "receipt" and target == run.journal / "result.json":
            raise failure
        if (
            boundary == "terminal_state"
            and target == run.journal / "state.json"
            and (run.journal / "result.json").exists()
        ):
            raise failure
        return replace(source, target)

    monkeypatch.setattr(run.writer.os, "replace", interrupt)
    with pytest.raises(OSError) as error:
        run.writer.recover_live(run.ctx, run.operation, target="original")

    assert error.value is failure
    status = run.writer.get_live_status(run.ctx, run.operation)
    assert status["status"] == "OUTCOME_UNKNOWN"
    assert status["phase"] == "undoing"
    monkeypatch.setattr(run.writer.os, "replace", replace)

    result = run.writer.recover_live(run.ctx, run.operation, target="original")

    assert result["status"] == "recovered"
    assert _tree_bytes(run.ctx.source_root) == run.original
    assert run.writer.get_live_status(run.ctx, run.operation) == result


def test_recovery_restores_missing_changed_file_and_can_be_repeated(interrupted_apply):
    run = interrupted_apply
    (run.ctx.source_root / CHANGED).unlink()

    result = run.writer.recover_live(run.ctx, run.operation, target="original")

    assert result["status"] == "recovered"
    assert _tree_bytes(run.ctx.source_root) == run.original
    assert run.writer.recover_live(run.ctx, run.operation, target="original") == result
