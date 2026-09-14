"""Native execution is isolated; verified bytes alone reach an owned tree."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
import json
import shutil
from types import SimpleNamespace
from uuid import uuid4

import pytest
import rentgen_core as api
import test_metadata_workspace as fixtures
from rentgen_core import metadata_native_apply as native
from rentgen_core import metadata_runs as runs, metadata_plans as plans
from rentgen_core import native_resources as resources
from rentgen_core.edt_execution import EDTClient, write_record
from rentgen_core.edt_profiles import authorized

project, scanner, captured, pytestmark = (
    fixtures.project,
    fixtures.scanner,
    fixtures.captured,
    fixtures.pytestmark,
)


class Response(SimpleNamespace):
    def model_dump(self, mode):
        return {"isError": self.isError, "structuredContent": self.structuredContent}


@pytest.fixture
def execution(captured, tmp_path, monkeypatch):
    ctx, request, preview = fixtures._request(captured)
    request.update(
        operation_id=str(uuid4()),
        workspace_root=tmp_path / "native-owned",
        expected_plan_id=preview["plan_id"],
    )
    calls, hooks = [], {}

    @contextmanager
    def admit(context, profile_id, operation_id, *, plan):
        assert not native.journal_path(context, operation_id).exists()
        assert not native.preflight.journal_path(context, operation_id).exists()
        assert not request["workspace_root"].exists()
        run = runs.run_path(context, operation_id)
        receipt = resources.reserve_run(context.state.path.parent, run)
        yield SimpleNamespace(run=run, receipt=receipt)

    @asynccontextmanager
    async def session(context, profile_id, operation_id, *, plan, admission):
        journal = native.journal_path(context, operation_id)
        assert (
            json.loads((journal / "intent.json").read_bytes())["request"][
                "expected_plan_id"
            ]
            == plan["plan_id"]
        )
        run = runs.run_path(context, operation_id)
        assert admission.run == run and run.is_dir()
        write_record(
            run / "runtime-request.json",
            {
                "schema": 1,
                "project_id": ctx.project_id,
                "operation_id": operation_id,
                "profile_id": profile_id,
                "plan": plan,
            },
        )
        plans.materialize(context, plan, run / "input")

        class Transport:
            async def call_tool(self, name, arguments):
                calls.append((name, arguments))
                assert (run / f"{len(calls):03d}-request.json").exists()
                if hook := hooks.get(name):
                    await hook(run, arguments)
                if name == "export_configuration_to_xml":
                    phase = (
                        "created"
                        if arguments["outputPath"].endswith("baseline-xml")
                        else "renamed"
                    )
                    source = fixtures.fixtures.fixtures.FIXTURE.parent / phase
                    shutil.copytree(source, arguments["outputPath"])
                    if hook := hooks.get("exported"):
                        await hook(run, arguments)
                content = []
                if name == "rename_metadata_object" and not arguments["confirm"]:
                    content = [
                        SimpleNamespace(
                            type="resource",
                            resource=SimpleNamespace(
                                text=(
                                    "---\naction: preview\nobjectFqn: Catalog.Products.Attribute.Article\n"
                                    "newName: SKU\nproblems: 0\ncontentHash: 0123456789abcdef\n---\n"
                                )
                            ),
                        )
                    ]
                return Response(
                    isError=False, structuredContent={"success": True}, content=content
                )

        with authorized(context) as check:
            yield EDTClient(Transport(), run, check, timeout=2)
        write_record(
            run / "runtime-closed.json",
            {"status": "closed", "metadata_verified": False},
        )

    monkeypatch.setattr(native, "edt_session", session)
    monkeypatch.setattr(native, "edt_admission", admit)
    return ctx, request, preview, calls, hooks


def execute(execution, **changes):
    ctx, request, *_ = execution
    return asyncio.run(native.apply_native_workspace(ctx, **{**request, **changes}))


def test_native_happy_path_is_journaled_and_undo_preserves_live_source(execution):
    ctx, request, preview, calls, _ = execution
    before = fixtures._bytes(ctx.source_root)
    result = execute(execution)
    assert result["status"] == "applied"
    assert result["live_source_written"] is False
    assert result["live_apply_allowed"] is False
    assert result["workspace_result_id"]
    assert (
        result["native_preview_id"]
        == runs.get_preview(ctx, request["operation_id"])["preview_id"]
    )
    assert [name for name, _ in calls] == [
        "import_configuration_from_xml",
        "get_metadata_details",
        "export_configuration_to_xml",
        "rename_metadata_object",
        "rename_metadata_object",
        "export_configuration_to_xml",
    ]
    assert calls[4][1]["expectedHash"] == "0123456789abcdef"
    assert execute(execution) == result
    assert len(calls) == 6
    root = request["workspace_root"]
    assert fixtures._bytes(root / "tree") == fixtures._bytes(
        runs.run_path(ctx, request["operation_id"]) / "candidate-xml"
    )
    undo = native.undo_native_workspace(ctx, request["operation_id"], root)
    assert undo["status"] == "undone"
    assert fixtures._bytes(root / "tree") == before
    assert fixtures._bytes(ctx.source_root) == before


@pytest.mark.parametrize("changed", ["head", "preview", "plan"])
def test_stale_binding_never_starts_edt(execution, changed):
    ctx, request, _, calls, _ = execution
    if changed == "head":
        from dataclasses import replace

        request["expected_head"] = replace(
            request["expected_head"], source_revision=999
        )
    else:
        request[f"expected_{changed}_id"] = "f" * 64
    with pytest.raises(api.CoreError):
        execute(execution)
    assert calls == []
    assert not (request["workspace_root"] / "workspace-result.json").exists()


@pytest.mark.parametrize(
    "failure", ["disconnect", "timeout", "cancel", "response_loss"]
)
def test_uncertain_execution_never_retries_or_publishes(
    execution, monkeypatch, failure
):
    ctx, request, _, calls, hooks = execution

    async def fail(run, arguments):
        if failure == "timeout":
            await asyncio.sleep(10)
        if failure == "cancel":
            raise asyncio.CancelledError()
        raise ConnectionError("lost transport")

    if failure == "response_loss":
        from rentgen_core import edt_execution

        original = edt_execution.write_record

        def lose_response(path, value):
            if path.name.endswith("-response.json"):
                raise OSError("response could not be retained")
            return original(path, value)

        monkeypatch.setattr(edt_execution, "write_record", lose_response)
    else:
        hooks["import_configuration_from_xml"] = fail
    with pytest.raises((api.CoreError, asyncio.CancelledError)):
        execute(execution, timeout=1)
    result = native.get_native_apply_result(ctx, request["operation_id"])
    assert result["status"] == "OUTCOME_UNKNOWN"
    assert execute(execution, timeout=1) == result
    assert len(calls) == 1
    assert not (request["workspace_root"] / "workspace-result.json").exists()
    assert fixtures._bytes(request["workspace_root"] / "tree") == fixtures._bytes(
        ctx.source_root
    )


def test_existing_runtime_operation_is_not_silently_reused(execution):
    _, request, _, calls, _ = execution
    request["operation_id"] = request["preview_operation_id"]
    with pytest.raises(api.CoreError) as error:
        execute(execution)
    assert error.value.code == "METADATA_NATIVE_CONFLICT"
    assert calls == []
    assert not request["workspace_root"].exists()


def test_foreign_baseline_blocks_rename_confirmation(execution):
    ctx, request, _, calls, hooks = execution

    async def change_baseline(run, arguments):
        if arguments["outputPath"].endswith("baseline-xml"):
            (run / "baseline-xml" / "foreign.bin").write_bytes(
                b"unexpected normalization"
            )

    hooks["exported"] = change_baseline
    with pytest.raises(api.CoreError):
        execute(execution)
    assert all(name != "rename_metadata_object" for name, _ in calls)
    assert not (request["workspace_root"] / "workspace-result.json").exists()


def test_state_inside_live_source_is_rejected_before_journal(execution):
    from dataclasses import replace

    ctx, request, _, calls, _ = execution
    state = SimpleNamespace(
        project_id=ctx.project_id,
        path=ctx.source_root / "state" / "state.sqlite3",
        transaction=ctx.state.transaction,
    )
    selected = replace(ctx, state=state)
    before = fixtures._bytes(ctx.source_root)
    with pytest.raises(api.CoreError) as error:
        asyncio.run(native.apply_native_workspace(selected, **request))
    assert error.value.code == "METADATA_APPLY_UNSUPPORTED"
    assert fixtures._bytes(ctx.source_root) == before
    assert calls == []


def test_late_native_completion_still_has_unknown_outcome(execution, monkeypatch):
    import time

    ctx, request, *_ = execution

    async def late(*args):
        time.sleep(1.1)

    monkeypatch.setattr(native, "_execute_native", late)
    with pytest.raises(api.CoreError):
        execute(execution, timeout=1)
    result = native.get_native_apply_result(ctx, request["operation_id"])
    assert result["status"] == "OUTCOME_UNKNOWN"
    assert result["reason"] == "TimeoutError"


def test_lost_terminal_receipt_is_unknown_and_never_reexecutes(execution, monkeypatch):
    ctx, request, _, calls, _ = execution
    original = native.write_record

    def interrupt(path, value):
        if path.name == "result.json":
            raise OSError("disk write failed")
        return original(path, value)

    monkeypatch.setattr(native, "write_record", interrupt)
    with pytest.raises(OSError):
        execute(execution)
    assert (request["workspace_root"] / "workspace-result.json").exists()
    result = native.get_native_apply_result(ctx, request["operation_id"])
    assert result["status"] == "OUTCOME_UNKNOWN"
    assert execute(execution) == result
    assert len(calls) == 6
    restored = native.restore_native_workspace(
        ctx, request["operation_id"], request["workspace_root"]
    )
    assert restored["status"] == "undone"
    assert fixtures._bytes(request["workspace_root"] / "tree") == fixtures._bytes(
        ctx.source_root
    )
    assert native.get_native_apply_result(ctx, request["operation_id"]) == result


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", True),
        ("live_apply_allowed", 0),
        ("reason", []),
        ("native_preview_id", "invalid"),
    ],
)
def test_readback_rejects_resealed_invalid_result_schema(execution, field, value):
    from dataclasses import replace

    ctx, request, _, calls, _ = execution
    request["expected_head"] = replace(request["expected_head"], source_revision=999)
    with pytest.raises(api.CoreError):
        execute(execution)
    path = native.journal_path(ctx, request["operation_id"]) / "result.json"
    result = json.loads(path.read_bytes())
    result[field] = value
    del result["result_id"]
    path.write_bytes(
        fixtures.workspace.canonical_bytes(
            fixtures.workspace._seal(result, "result_id")
        )
    )
    with pytest.raises(api.CoreError) as error:
        native.get_native_apply_result(ctx, request["operation_id"])
    assert error.value.code == "METADATA_NATIVE_RECOVERY_REQUIRED"
    assert calls == []


def test_cooperating_workspace_writer_and_duplicate_native_are_excluded(execution):
    ctx, request, _, calls, hooks = execution
    observed = []

    async def contend(run, arguments):
        with pytest.raises(api.CoreError) as error:
            fixtures.workspace.apply_workspace(
                ctx, request["operation_id"], request["workspace_root"]
            )
        assert error.value.code == "METADATA_WORKSPACE_BUSY"
        observed.append(await native.apply_native_workspace(ctx, **request))

    hooks["import_configuration_from_xml"] = contend
    assert execute(execution)["status"] == "applied"
    assert observed[0]["status"] == "OUTCOME_UNKNOWN"
    assert len(calls) == 6


@pytest.mark.parametrize(
    "change", ["extra_file", "uuid", "owner", "head", "live_source", "owned_tree"]
)
def test_changes_during_native_execution_block_publication(execution, change):
    ctx, request, _, _, hooks = execution

    async def change_output(run, arguments):
        if not arguments["outputPath"].endswith("candidate-xml"):
            return
        candidate = run / "candidate-xml"
        if change == "extra_file":
            (candidate / "foreign.bin").write_bytes(b"unrecognized native output")
        elif change in {"uuid", "owner"}:
            target = candidate / "Catalogs/Products.xml"
            identity = (
                "eb298009-8fc5-4a2f-8812-902daeed99df"
                if change == "uuid"
                else "fb28b18e-d2a3-4f48-8390-c0d609c9e7c0"
            )
            target.write_bytes(
                target.read_bytes().replace(identity.encode(), str(uuid4()).encode())
            )
        elif change == "head":
            from rentgen_core.source_configuration import SourceLayerSpec

            api.configure_source_layers(
                ctx,
                (SourceLayerSpec("base", 0, "base", ".", "designer_xml"),),
                expected_revision=2,
            )
        else:
            root = (
                ctx.source_root
                if change == "live_source"
                else request["workspace_root"] / "tree"
            )
            (root / "foreign.bin").write_bytes(b"later foreign write")

    hooks["exported"] = change_output
    with pytest.raises(api.CoreError):
        execute(execution)
    assert not (request["workspace_root"] / "workspace-result.json").exists()
    assert (
        native.get_native_apply_result(ctx, request["operation_id"])["status"]
        != "applied"
    )


def test_revocation_during_edt_is_journaled_and_stops_following_calls(execution):
    from project_access_test_support import force_legacy_membership

    ctx, request, _, calls, hooks = execution

    async def revoke(run, arguments):
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:read"})

    hooks["import_configuration_from_xml"] = revoke
    with pytest.raises(api.CoreError) as error:
        execute(execution)
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert len(calls) == 1
    result = json.loads(
        (native.journal_path(ctx, request["operation_id"]) / "result.json").read_bytes()
    )
    assert result["status"] == "OUTCOME_UNKNOWN"
    with pytest.raises(api.CoreError) as error:
        native.get_native_apply_result(ctx, request["operation_id"])
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_interrupted_publication_can_only_restore_owned_original(
    execution, monkeypatch
):
    ctx, request, _, calls, _ = execution
    original = fixtures.workspace.os.replace
    writes = []

    def interrupt(source, target):
        if "tree" in target.parts:
            writes.append(target)
            if len(writes) == 2:
                raise OSError("interrupted after a file write")
        return original(source, target)

    monkeypatch.setattr(fixtures.workspace.os, "replace", interrupt)
    with pytest.raises(OSError):
        execute(execution)
    monkeypatch.setattr(fixtures.workspace.os, "replace", original)
    result = native.get_native_apply_result(ctx, request["operation_id"])
    assert result["status"] == "OUTCOME_UNKNOWN"
    with pytest.raises(api.CoreError):
        native.restore_native_workspace(ctx, request["operation_id"], ctx.source_root)
    recovered = native.restore_native_workspace(
        ctx, request["operation_id"], request["workspace_root"]
    )
    assert recovered["target"] == "original"
    assert fixtures._bytes(request["workspace_root"] / "tree") == fixtures._bytes(
        ctx.source_root
    )
    assert execute(execution) == result
    assert len(calls) == 6


@pytest.mark.parametrize("damage", [None, "corrupt", "foreign"])
def test_native_restore_finalizes_pending_apply_state_without_reexecution(
    execution, monkeypatch, damage
):
    ctx, request, _, calls, _ = execution
    root = request["workspace_root"]
    original_replace = fixtures.workspace._publish_replace

    def interrupt(source, target):
        if target.name == "workspace-state.json":
            raise OSError("interrupted complete state replacement")
        return original_replace(source, target)

    with monkeypatch.context() as crash:
        crash.setattr(fixtures.workspace, "_publish_replace", interrupt)
        with pytest.raises(OSError, match="complete state"):
            execute(execution)
    temporary = root / "workspace-state.json.tmp"
    assert temporary.exists()
    result = native.get_native_apply_result(ctx, request["operation_id"])
    assert result["status"] == "OUTCOME_UNKNOWN"
    if damage == "corrupt":
        temporary.write_bytes(b'{"incomplete":')
    elif damage == "foreign":
        pending = json.loads(temporary.read_bytes())
        pending["marker_id"] = "f" * 64
        del pending["state_id"]
        temporary.write_bytes(
            fixtures.workspace.canonical_bytes(
                fixtures.workspace._seal(pending, "state_id")
            )
        )
    if damage is not None:
        (root / "workspace-operation.lock").unlink()
        before = fixtures._bytes(root)
        with pytest.raises(api.CoreError):
            native.restore_native_workspace(ctx, request["operation_id"], root)
        assert fixtures._bytes(root) == before
        assert native.get_native_apply_result(ctx, request["operation_id"]) == result
        assert len(calls) == 6
        return
    restored = native.restore_native_workspace(ctx, request["operation_id"], root)
    assert restored["status"] == "undone"
    assert not temporary.exists()
    assert not (root / ".rentgen-undo-stage").exists()
    assert fixtures._bytes(root / "tree") == fixtures._bytes(ctx.source_root)
    repeated = native.restore_native_workspace(ctx, request["operation_id"], root)
    assert repeated["status"] == "recovered" and repeated["target"] == "original"
    assert fixtures._bytes(root / "tree") == fixtures._bytes(ctx.source_root)
    assert not temporary.exists()
    assert native.get_native_apply_result(ctx, request["operation_id"]) == result
    assert execute(execution) == result
    assert len(calls) == 6, "Restore and replay must not execute EDT again"


def test_undo_conflicts_with_later_foreign_bytes(execution):
    ctx, request, *_ = execution
    execute(execution)
    target = request["workspace_root"] / "tree" / "foreign.bin"
    target.write_bytes(b"unrelated later change")
    before = fixtures._bytes(request["workspace_root"] / "tree")
    with pytest.raises(api.CoreError) as error:
        native.undo_native_workspace(
            ctx, request["operation_id"], request["workspace_root"]
        )
    assert error.value.code == "METADATA_UNDO_CONFLICT"
    assert fixtures._bytes(request["workspace_root"] / "tree") == before


@pytest.mark.parametrize("refusal", ["retention", "storage"])
def test_retention_refusal_leaves_no_native_journal_preflight_or_workspace(
    execution, monkeypatch, refusal
):
    ctx, request, _, calls, _ = execution
    if refusal == "retention":
        monkeypatch.setattr(resources, "RETAINED_RUN_LIMIT", 1)
    else:
        monkeypatch.setattr(
            resources.shutil, "disk_usage", lambda root: SimpleNamespace(free=0)
        )
    with pytest.raises(api.CoreError) as error:
        execute(execution)
    assert error.value.code == (
        "NATIVE_RETENTION_LIMIT" if refusal == "retention" else "NATIVE_STORAGE_LIMIT"
    )
    assert not native.journal_path(ctx, request["operation_id"]).exists()
    assert not native.preflight.journal_path(ctx, request["operation_id"]).exists()
    assert not request["workspace_root"].exists()
    assert not runs.run_path(ctx, request["operation_id"]).exists()
    assert calls == []


@pytest.mark.parametrize(
    "damage",
    [
        "native_id",
        "workspace_id",
        "native_missing",
        "workspace_missing",
        "workspace_binding",
        "tree",
    ],
)
def test_applied_readback_requires_both_bound_receipts(execution, damage):
    ctx, request, *_ = execution
    execute(execution)
    result_path = native.journal_path(ctx, request["operation_id"]) / "result.json"
    result = json.loads(result_path.read_bytes())
    root = request["workspace_root"]
    if damage in {"native_id", "workspace_id"}:
        result[
            "native_preview_id" if damage == "native_id" else "workspace_result_id"
        ] = ("f" * 64)
    elif damage == "native_missing":
        (runs.run_path(ctx, request["operation_id"]) / "preview.json").unlink()
    elif damage == "workspace_missing":
        (root / "workspace-result.json").unlink()
    elif damage == "workspace_binding":
        path = root / "workspace-result.json"
        changed = json.loads(path.read_bytes())
        changed["after_digest"] = "f" * 64
        del changed["result_id"]
        changed = fixtures.workspace._seal(changed, "result_id")
        path.write_bytes(fixtures.workspace.canonical_bytes(changed))
        result["workspace_result_id"] = changed["result_id"]
    else:
        (root / "tree" / "foreign.bin").write_bytes(b"foreign bytes")
    del result["result_id"]
    result_path.write_bytes(
        fixtures.workspace.canonical_bytes(
            fixtures.workspace._seal(result, "result_id")
        )
    )
    with pytest.raises(api.CoreError):
        native.get_native_apply_result(ctx, request["operation_id"])
