"""A preflight journal never grants a capability to mutate live metadata."""
from dataclasses import replace
import json
from uuid import uuid4

import pytest
import rentgen_core as api
import test_metadata_runs as fixtures
import test_project_core_publication as publication
from project_access_test_support import force_legacy_membership
from rentgen_core import metadata_apply as apply

project, scanner, captured, pytestmark = (
    fixtures.project,
    fixtures.scanner,
    fixtures.captured,
    fixtures.pytestmark,
)


def _request(captured):
    ctx, preview_operation, run, preview = fixtures._finished_run(captured)
    return (
        ctx,
        {
            "preview_operation_id": preview_operation,
            "operation_id": str(uuid4()),
            "expected_preview_id": preview["preview_id"],
            "expected_head": api.get_project_head(ctx),
        },
        run,
    )


def _bytes(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_preflight_is_durable_and_does_not_claim_or_perform_apply(captured):
    ctx, request, _ = _request(captured)
    original, head = _bytes(ctx.source_root), api.get_project_head(ctx)
    result = apply.preflight_apply(ctx, **request)
    assert result["status"] == "unavailable"
    assert result["live_source_written"] is False
    assert result["preview_id"] == request["expected_preview_id"]
    assert "live_apply_not_implemented" in result["reasons"]
    assert apply.get_apply_result(ctx, request["operation_id"]) == result
    assert apply.preflight_apply(ctx, **request) == result
    assert _bytes(ctx.source_root) == original
    assert api.get_project_head(ctx) == head


@pytest.mark.parametrize(
    "change", ["edit", "add", "delete", "head", "source_configuration"]
)
def test_preflight_records_stale_without_changing_live_sources(
    captured, project, change
):
    ctx, request, _ = _request(captured)
    if change == "head":
        request["expected_head"] = replace(request["expected_head"], revision=0)
    elif change == "source_configuration":
        current = api.get_source_configuration(ctx)
        api.configure_source_layers(
            ctx, current.layers, expected_revision=current.revision
        )
    elif change == "edit":
        (ctx.source_root / "Catalogs/Products.xml").write_bytes(b"external edit")
    elif change == "delete":
        (ctx.source_root / "Catalogs/Products.xml").unlink()
    else:
        (ctx.source_root / "unknown.bin").write_bytes(b"unknown data")
    original = _bytes(ctx.source_root)
    result = apply.preflight_apply(ctx, **request)
    assert result["status"] == "stale"
    assert result["live_source_written"] is False
    assert apply.get_apply_result(ctx, request["operation_id"]) == result
    assert _bytes(ctx.source_root) == original


def test_operation_id_cannot_be_rebound(captured):
    ctx, request, _ = _request(captured)
    apply.preflight_apply(ctx, **request)
    request["expected_preview_id"] = "f" * 64
    with pytest.raises(api.CoreError) as error:
        apply.preflight_apply(ctx, **request)
    assert error.value.code == "METADATA_APPLY_CONFLICT"


def test_interrupted_journal_is_not_replayed(captured, monkeypatch):
    ctx, request, _ = _request(captured)
    original = apply.write_record

    def interrupt(path, value):
        if path.name == "result.json":
            raise RuntimeError("crash before receipt")
        original(path, value)

    monkeypatch.setattr(apply, "write_record", interrupt)
    with pytest.raises(RuntimeError, match="crash before receipt"):
        apply.preflight_apply(ctx, **request)
    monkeypatch.setattr(apply, "write_record", original)
    with pytest.raises(api.CoreError) as error:
        apply.preflight_apply(ctx, **request)
    assert error.value.code == "METADATA_APPLY_RECOVERY_REQUIRED"
    assert not (
        apply.journal_path(ctx, request["operation_id"]) / "result.json"
    ).exists()


def test_denied_access_precedes_parsing_and_journal_io(captured):
    ctx, request, _ = _request(captured)
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:read"})
    with pytest.raises(api.CoreError) as error:
        apply.preflight_apply(
            ctx, None, None, expected_preview_id=None, expected_head=None
        )
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert not apply.journal_path(ctx, request["operation_id"]).exists()


def test_revocation_during_inventory_is_recorded_and_stops_preflight(
    captured, monkeypatch
):
    ctx, request, _ = _request(captured)
    original = apply.exported_inventory

    def revoke(root, *, authorize):
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:read"})
        return original(root, authorize=authorize)

    monkeypatch.setattr(apply, "exported_inventory", revoke)
    with pytest.raises(api.CoreError) as error:
        apply.preflight_apply(ctx, **request)
    assert error.value.code == "PROJECT_FORBIDDEN"
    record = json.loads(
        (apply.journal_path(ctx, request["operation_id"]) / "result.json").read_bytes()
    )
    assert record["status"] == "revoked"
    assert record["live_source_written"] is False


def test_apply_and_undo_refuse_to_turn_preflight_into_write_authority(captured):
    ctx, request, _ = _request(captured)
    apply.preflight_apply(ctx, **request)
    original = _bytes(ctx.source_root)
    for operation, code in (
        (apply.apply_metadata, "METADATA_LIVE_APPLY_UNAVAILABLE"),
        (apply.undo_metadata, "METADATA_UNDO_UNAVAILABLE"),
    ):
        with pytest.raises(api.CoreError) as error:
            operation(ctx, request["operation_id"])
        assert error.value.code == code
    assert _bytes(ctx.source_root) == original


def test_apply_rechecks_live_bytes_after_preflight(captured):
    ctx, request, _ = _request(captured)
    apply.preflight_apply(ctx, **request)
    (ctx.source_root / "Catalogs/Products.xml").write_bytes(b"external edit")
    with pytest.raises(api.CoreError) as error:
        apply.apply_metadata(ctx, request["operation_id"])
    assert error.value.code == "METADATA_APPLY_STALE"
    assert (ctx.source_root / "Catalogs/Products.xml").read_bytes() == b"external edit"


@pytest.mark.parametrize(
    "damage",
    ["truncated_intent", "missing_result", "tampered_result", "malformed_intent"],
)
def test_damaged_journal_requires_recovery_without_replay(captured, damage):
    ctx, request, _ = _request(captured)
    apply.preflight_apply(ctx, **request)
    journal = apply.journal_path(ctx, request["operation_id"])
    if damage == "truncated_intent":
        (journal / "intent.json").write_bytes(b'{"schema":')
    elif damage == "missing_result":
        (journal / "result.json").unlink()
    elif damage == "tampered_result":
        result = json.loads((journal / "result.json").read_bytes())
        result["status"] = "applied"
        (journal / "result.json").write_text(json.dumps(result), "utf-8")
    else:
        intent = json.loads((journal / "intent.json").read_bytes())
        intent["request"]["expected_head"] = None
        intent = apply._seal(
            {k: v for k, v in intent.items() if k != "intent_id"}, "intent_id"
        )
        result = json.loads((journal / "result.json").read_bytes())
        result["intent_id"] = intent["intent_id"]
        result = apply._seal(
            {k: v for k, v in result.items() if k != "result_id"}, "result_id"
        )
        (journal / "intent.json").write_text(json.dumps(intent), "utf-8")
        (journal / "result.json").write_text(json.dumps(result), "utf-8")
    with pytest.raises(api.CoreError) as error:
        apply.get_apply_result(ctx, request["operation_id"])
    assert error.value.code == "METADATA_APPLY_RECOVERY_REQUIRED"


def test_journal_with_no_intent_is_not_reused(captured):
    ctx, request, _ = _request(captured)
    journal = apply.journal_path(ctx, request["operation_id"])
    journal.mkdir(parents=True)
    with pytest.raises(api.CoreError) as error:
        apply.preflight_apply(ctx, **request)
    assert error.value.code == "METADATA_APPLY_RECOVERY_REQUIRED"
    assert list(journal.iterdir()) == []


def test_apply_rechecks_retained_preview(captured):
    ctx, request, run = _request(captured)
    apply.preflight_apply(ctx, **request)
    (run / "candidate-xml/Catalogs/Products.xml").write_bytes(b"tampered candidate")
    with pytest.raises(api.CoreError):
        apply.apply_metadata(ctx, request["operation_id"])


def test_historical_result_survives_new_head_but_does_not_authorize_apply(
    captured, project
):
    ctx, request, _ = _request(captured)
    result = apply.preflight_apply(ctx, **request)
    module = ctx.source_root / "CommonModules/ОбщийМодуль/Ext/Module.bsl"
    module.write_bytes(module.read_bytes().replace(b"1", b"2"))
    publication.publish(project)
    current = project[1].resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    assert apply.get_apply_result(current, request["operation_id"]) == result
    with pytest.raises(api.CoreError) as error:
        apply.apply_metadata(current, request["operation_id"])
    assert error.value.code == "METADATA_APPLY_STALE"


def test_state_nested_in_source_is_refused_before_journal_creation(captured):
    ctx, request, _ = _request(captured)
    ctx = replace(ctx, source_root=ctx.state.path.parent.parent)
    with pytest.raises(api.CoreError) as error:
        apply.preflight_apply(ctx, **request)
    assert error.value.code == "METADATA_APPLY_UNSUPPORTED"
    assert not apply.journal_path(ctx, request["operation_id"]).exists()
