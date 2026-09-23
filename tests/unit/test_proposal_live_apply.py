"""Direct BSL proposal writer keeps the source tree recoverable and bound."""

import json
from uuid import uuid4

import pytest
from pathlib import Path

import rentgen_core as api
from rentgen_core.proposals import (
    ProposalLimits,
    create_proposal_presentation,
    parse_proposal,
)
from rentgen_core.source_configuration import SourceLayerSpec, configure_source_layers
import test_project_core_publication as fixtures


pytestmark = fixtures.pytestmark
project, scanner = fixtures.project, fixtures.scanner
LIMITS = ProposalLimits(1024 * 1024, 1024 * 1024, 1536 * 1024, 256 * 1024)
PATH = "CommonModules/ОбщийМодуль/Ext/Module.bsl"


@pytest.fixture
def proposal_project(project):
    ctx, resolver, module, builder = project
    (ctx.source_root / "Configuration.xml").write_text(
        "<MetaDataObject><Configuration><Properties><Name>Test</Name></Properties></Configuration></MetaDataObject>",
        "utf-8",
    )
    configure_source_layers(
        ctx,
        (SourceLayerSpec("base", 0, "base", ".", "designer_xml"),),
        expected_revision=1,
    )
    fixtures.publish(project)
    selected = resolver.resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    ref = selected.sources.resolve("base", PATH)
    original = selected.sources.read_source(ref)
    replacement = original.replace(b"1", b"2")
    raw = create_proposal_presentation(
        selected, ref, replacement, limits=LIMITS
    ).canonical_json
    return selected, module, parse_proposal(selected, raw, limits=LIMITS), original


def test_apply_and_cas_undo_restore_bsl_source(proposal_project):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    operation = str(uuid4())
    head = api.get_project_head(ctx)

    applied = proposal_live_apply.apply_live(
        ctx, operation, proposal, expected_head=head
    )

    assert applied["status"] == "applied"
    assert applied["live_source_written"] is True
    assert applied["changed_paths"] == [PATH]
    assert module.read_bytes() == proposal.replacement_bytes

    undone = proposal_live_apply.undo_live(ctx, operation)

    assert undone["status"] == "undone"
    assert module.read_bytes() == original
    assert proposal_live_apply.undo_live(ctx, operation) == undone


def test_stale_source_refuses_before_write(proposal_project):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    module.write_bytes(b"foreign")

    with pytest.raises(api.CoreError) as error:
        proposal_live_apply.apply_live(
            ctx, str(uuid4()), proposal, expected_head=api.get_project_head(ctx)
        )

    assert error.value.code == "PROPOSAL_LIVE_STALE"
    assert module.read_bytes() == b"foreign"


def test_cross_volume_source_refuses_before_live_journal(proposal_project, monkeypatch):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    operation = str(uuid4())
    monkeypatch.setattr(
        proposal_live_apply, "_same_volume", lambda _: False, raising=False
    )

    with pytest.raises(api.CoreError) as error:
        proposal_live_apply.apply_live(
            ctx, operation, proposal, expected_head=api.get_project_head(ctx)
        )

    assert error.value.code == "PROPOSAL_LIVE_UNSUPPORTED"
    assert not proposal_live_apply.journal_path(ctx, operation).exists()
    assert module.read_bytes() == original


def test_interrupted_apply_is_unknown_until_explicit_recovery(
    proposal_project, monkeypatch
):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    operation = str(uuid4())
    original_replace = proposal_live_apply.os.replace

    def interrupt(source, target):
        if Path(target).resolve() == module.resolve():
            raise OSError("simulated interruption")
        return original_replace(source, target)

    monkeypatch.setattr(proposal_live_apply.os, "replace", interrupt)
    with pytest.raises(OSError):
        proposal_live_apply.apply_live(
            ctx, operation, proposal, expected_head=api.get_project_head(ctx)
        )
    monkeypatch.setattr(proposal_live_apply.os, "replace", original_replace)

    assert (
        proposal_live_apply.get_live_status(ctx, operation)["status"]
        == "OUTCOME_UNKNOWN"
    )
    recovered = proposal_live_apply.recover_live(ctx, operation, target="original")
    assert recovered["status"] == "recovered"
    assert module.read_bytes() == original


def test_interrupted_undo_is_unknown_until_explicit_recovery(
    proposal_project, monkeypatch
):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    operation = str(uuid4())
    proposal_live_apply.apply_live(
        ctx, operation, proposal, expected_head=api.get_project_head(ctx)
    )
    original_replace = proposal_live_apply.os.replace

    def interrupt(source, target):
        if Path(target).resolve() == module.resolve():
            original_replace(source, target)
            raise OSError("simulated interruption after undo replace")
        return original_replace(source, target)

    monkeypatch.setattr(proposal_live_apply.os, "replace", interrupt)
    with pytest.raises(OSError):
        proposal_live_apply.undo_live(ctx, operation)
    monkeypatch.setattr(proposal_live_apply.os, "replace", original_replace)

    assert module.read_bytes() == original
    status = proposal_live_apply.get_live_status(ctx, operation)
    assert status["status"] == "OUTCOME_UNKNOWN"
    assert status["phase"] == "undoing"
    assert (
        proposal_live_apply.recover_live(ctx, operation, target="original")["status"]
        == "recovered"
    )


def test_recover_can_resume_after_its_own_interruption(proposal_project, monkeypatch):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    operation = str(uuid4())
    proposal_live_apply.apply_live(
        ctx, operation, proposal, expected_head=api.get_project_head(ctx)
    )
    original_replace = proposal_live_apply.os.replace

    def interrupt(source, target):
        if Path(target).resolve() == module.resolve():
            original_replace(source, target)
            raise OSError("simulated recovery interruption")
        return original_replace(source, target)

    monkeypatch.setattr(proposal_live_apply.os, "replace", interrupt)
    with pytest.raises(OSError):
        proposal_live_apply.recover_live(ctx, operation, target="original")
    monkeypatch.setattr(proposal_live_apply.os, "replace", original_replace)

    assert (
        proposal_live_apply.get_live_status(ctx, operation)["status"]
        == "OUTCOME_UNKNOWN"
    )
    assert (
        proposal_live_apply.recover_live(ctx, operation, target="original")["status"]
        == "recovered"
    )
    assert module.read_bytes() == original


@pytest.mark.parametrize("origin", ["missing", "prepared", "undoing"])
def test_recover_reconciles_pending_undoing_from_each_reachable_origin(
    proposal_project, monkeypatch, origin
):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    operation = str(uuid4())
    journal = proposal_live_apply.journal_path(ctx, operation)
    original_replace = proposal_live_apply.os.replace

    if origin == "missing":
        original_write = proposal_live_apply.write_record

        def interrupt_write(path, value):
            if Path(path) == journal / "state.json":
                raise OSError("before initial state")
            return original_write(path, value)

        monkeypatch.setattr(proposal_live_apply, "write_record", interrupt_write)
    elif origin == "prepared":
        original_record_replace = proposal_live_apply._replace_record

        def interrupt_record_replace(path, value):
            if Path(path) == journal / "state.json" and value["phase"] == "applying":
                raise OSError("before applying state")
            return original_record_replace(path, value)

        monkeypatch.setattr(
            proposal_live_apply, "_replace_record", interrupt_record_replace
        )

    if origin != "undoing":
        with pytest.raises(OSError):
            proposal_live_apply.apply_live(
                ctx, operation, proposal, expected_head=api.get_project_head(ctx)
            )
        monkeypatch.undo()
    else:
        proposal_live_apply.apply_live(
            ctx, operation, proposal, expected_head=api.get_project_head(ctx)
        )

        def interrupt_source(source, target):
            if Path(target).resolve() == module.resolve():
                original_replace(source, target)
                raise OSError("after source restore")
            return original_replace(source, target)

        monkeypatch.setattr(proposal_live_apply.os, "replace", interrupt_source)
        with pytest.raises(OSError):
            proposal_live_apply.recover_live(ctx, operation, target="original")
        monkeypatch.setattr(proposal_live_apply.os, "replace", original_replace)

    def interrupt_state(source, target):
        if (
            Path(target) == journal / "state.json"
            and json.loads(Path(source).read_text("utf-8"))["phase"] == "undoing"
        ):
            raise OSError("before undoing state")
        return original_replace(source, target)

    monkeypatch.setattr(proposal_live_apply.os, "replace", interrupt_state)
    with pytest.raises(OSError):
        proposal_live_apply.recover_live(ctx, operation, target="original")
    monkeypatch.setattr(proposal_live_apply.os, "replace", original_replace)
    assert (journal / "state.json.tmp").exists()
    assert (
        proposal_live_apply.recover_live(ctx, operation, target="original")["status"]
        == "recovered"
    )
    assert module.read_bytes() == original


def test_undo_finalizes_written_result_after_terminal_state_interruption(
    proposal_project, monkeypatch
):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    operation = str(uuid4())
    proposal_live_apply.apply_live(
        ctx, operation, proposal, expected_head=api.get_project_head(ctx)
    )
    journal = proposal_live_apply.journal_path(ctx, operation)
    original_replace = proposal_live_apply.os.replace

    def interrupt(source, target):
        if (
            Path(target) == journal / "state.json"
            and json.loads((journal / "result.json").read_text("utf-8"))["status"]
            == "undone"
        ):
            raise OSError("simulated terminal state interruption")
        return original_replace(source, target)

    monkeypatch.setattr(proposal_live_apply.os, "replace", interrupt)
    with pytest.raises(OSError):
        proposal_live_apply.undo_live(ctx, operation)
    monkeypatch.setattr(proposal_live_apply.os, "replace", original_replace)

    assert module.read_bytes() == original
    assert (
        proposal_live_apply.get_live_status(ctx, operation)["status"]
        == "OUTCOME_UNKNOWN"
    )
    assert proposal_live_apply.undo_live(ctx, operation)["status"] == "undone"
    assert proposal_live_apply.get_live_status(ctx, operation)["status"] == "undone"


def test_recover_promotes_sealed_undo_result_left_in_temporary_file(
    proposal_project, monkeypatch
):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    operation = str(uuid4())
    proposal_live_apply.apply_live(
        ctx, operation, proposal, expected_head=api.get_project_head(ctx)
    )
    journal = proposal_live_apply.journal_path(ctx, operation)
    original_replace = proposal_live_apply.os.replace

    def interrupt(source, target):
        if Path(target) == journal / "result.json":
            raise OSError("simulated receipt publication interruption")
        return original_replace(source, target)

    monkeypatch.setattr(proposal_live_apply.os, "replace", interrupt)
    with pytest.raises(OSError):
        proposal_live_apply.undo_live(ctx, operation)
    monkeypatch.setattr(proposal_live_apply.os, "replace", original_replace)

    assert module.read_bytes() == original
    assert (journal / "result.json.tmp").exists()
    assert (
        proposal_live_apply.get_live_status(ctx, operation)["status"]
        == "OUTCOME_UNKNOWN"
    )
    assert (
        proposal_live_apply.recover_live(ctx, operation, target="original")["status"]
        == "undone"
    )
    assert proposal_live_apply.get_live_status(ctx, operation)["status"] == "undone"


@pytest.mark.parametrize("phase", ["applying", "complete"])
def test_recover_promotes_sealed_apply_state_left_in_temporary_file(
    proposal_project, monkeypatch, phase
):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    operation = str(uuid4())
    journal = proposal_live_apply.journal_path(ctx, operation)
    original_replace = proposal_live_apply.os.replace

    def interrupt(source, target):
        if (
            Path(target) == journal / "state.json"
            and json.loads(Path(source).read_text("utf-8"))["phase"] == phase
        ):
            raise OSError("simulated state publication interruption")
        return original_replace(source, target)

    monkeypatch.setattr(proposal_live_apply.os, "replace", interrupt)
    with pytest.raises(OSError):
        proposal_live_apply.apply_live(
            ctx, operation, proposal, expected_head=api.get_project_head(ctx)
        )
    monkeypatch.setattr(proposal_live_apply.os, "replace", original_replace)

    assert (journal / "state.json.tmp").exists()
    assert (
        proposal_live_apply.get_live_status(ctx, operation)["status"]
        == "OUTCOME_UNKNOWN"
    )
    assert (
        proposal_live_apply.recover_live(ctx, operation, target="original")["status"]
        == "recovered"
    )
    assert module.read_bytes() == original


def test_foreign_undo_never_overwrites_source(proposal_project):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, _ = proposal_project
    operation = str(uuid4())
    proposal_live_apply.apply_live(
        ctx, operation, proposal, expected_head=api.get_project_head(ctx)
    )
    module.write_bytes(b"foreign after apply")

    with pytest.raises(api.CoreError) as error:
        proposal_live_apply.undo_live(ctx, operation)

    assert error.value.code == "PROPOSAL_LIVE_UNDO_CONFLICT"
    assert module.read_bytes() == b"foreign after apply"


def test_noop_proposal_is_refused_before_write(proposal_project):
    from rentgen_core import proposal_live_apply

    ctx, module, proposal, original = proposal_project
    ref = proposal.source_ref
    raw = create_proposal_presentation(ctx, ref, original, limits=LIMITS).canonical_json
    noop = parse_proposal(ctx, raw, limits=LIMITS)
    with pytest.raises(api.CoreError) as error:
        proposal_live_apply.apply_live(
            ctx, str(uuid4()), noop, expected_head=api.get_project_head(ctx)
        )
    assert error.value.code == "PROPOSAL_LIVE_UNSUPPORTED"
    assert module.read_bytes() == original
