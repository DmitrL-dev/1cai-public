"""Native EDT verification followed by publication to an owned copy only."""

from dataclasses import asdict
import time

from . import metadata_apply as preflight
from . import metadata_runs as runs
from . import metadata_workspace as workspace
from ._windows_source_tree import pinned_directory
from .edt_execution import guarded_wait, write_record
from .edt_inventory import exported_inventory
from .edt_profiles import authorized
from .edt_runtime import edt_admission, edt_session
from .errors import CoreError
from .metadata_plans import validate_plan
from .metadata_preview import _verify_identity, build_preview
from .platform_check import _pin_inputs
from .snapshots import validate_operation_id

RECOVERY = "METADATA_NATIVE_RECOVERY_REQUIRED"
STATUSES = {"applied", "failed", "stale", "revoked", "OUTCOME_UNKNOWN"}


def _require(condition, code, message):
    if not condition:
        raise CoreError(code, message)


def journal_path(ctx, operation_id):
    return (
        ctx.state.path.parent
        / "metadata-native-apply"
        / validate_operation_id(operation_id)
    )


def _read_intent(ctx, operation_id):
    intent = preflight._read(
        journal_path(ctx, operation_id) / "intent.json", "intent_id"
    )
    try:
        request = intent["request"]
        _require(
            set(intent) == {"schema", "request", "binding", "intent_id"}
            and type(intent["schema"]) is int
            and intent["schema"] == 1
            and set(request)
            == {
                "schema",
                "project_id",
                "operation_id",
                "preview_operation_id",
                "expected_preview_id",
                "expected_plan_id",
                "expected_head",
                "source_root",
                "workspace_root",
                "timeout",
            }
            and request["project_id"] == ctx.project_id
            and request["operation_id"] == operation_id
            and request["source_root"] == str(ctx.source_root)
            and request["expected_head"]["snapshot"] == asdict(ctx.snapshot)
            and request["expected_plan_id"] == intent["binding"]["plan_id"],
            RECOVERY,
            "Native intent has an invalid context or schema",
        )
        # Reuse the strict preflight schema reader for the common binding.
        common = {
            key: value
            for key, value in request.items()
            if key not in {"expected_plan_id", "workspace_root", "timeout"}
        }
        preflight._validate_intent(
            ctx,
            operation_id,
            {
                "schema": 1,
                "request": common,
                "binding": intent["binding"],
                "intent_id": intent["intent_id"],
            },
        )
        root = workspace._workspace_root(request["workspace_root"])
        workspace._owned_paths(ctx, root)
        _require(
            str(root) == request["workspace_root"],
            RECOVERY,
            "Native workspace locator differs",
        )
        _require(
            type(request["timeout"]) is int and 0 < request["timeout"] <= 600,
            RECOVERY,
            "Invalid native deadline",
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CoreError(RECOVERY, "Native intent is malformed") from exc
    return intent


def _result(
    intent, status, *, reason=None, native_preview_id=None, workspace_result_id=None
):
    return preflight._seal(
        {
            "schema": 1,
            "project_id": intent["request"]["project_id"],
            "operation_id": intent["request"]["operation_id"],
            "intent_id": intent["intent_id"],
            "status": status,
            "reason": reason,
            "native_preview_id": native_preview_id,
            "workspace_result_id": workspace_result_id,
            "live_source_written": False,
            "live_apply_allowed": False,
        },
        "result_id",
    )


def _read_native_result(ctx, operation_id):
    """Read and validate the immutable native terminal receipt only."""
    with pinned_directory(journal_path(ctx, operation_id)):
        intent = _read_intent(ctx, operation_id)
        path = journal_path(ctx, operation_id) / "result.json"
        if not path.exists():
            return intent, _result(
                intent, "OUTCOME_UNKNOWN", reason="incomplete_operation"
            )
        result = preflight._read(path, "result_id")
        _require(
            set(result) == set(_result(intent, "failed"))
            and type(result["schema"]) is int
            and result["live_source_written"] is False
            and result["live_apply_allowed"] is False
            and type(result["status"]) is str
            and result["status"] in STATUSES
            and (
                result["reason"] is None
                or (type(result["reason"]) is str and 1 <= len(result["reason"]) <= 128)
            )
            and all(
                result[key] is None
                or (type(result[key]) is str and preflight.HASH.fullmatch(result[key]))
                for key in ("native_preview_id", "workspace_result_id")
            )
            and result
            == _result(
                intent,
                result["status"],
                reason=result["reason"],
                native_preview_id=result["native_preview_id"],
                workspace_result_id=result["workspace_result_id"],
            )
            and (
                result["status"] != "applied"
                or (
                    result["reason"] is None
                    and type(result["native_preview_id"]) is str
                    and preflight.HASH.fullmatch(result["native_preview_id"])
                    and type(result["workspace_result_id"]) is str
                    and preflight.HASH.fullmatch(result["workspace_result_id"])
                )
            ),
            RECOVERY,
            "Native receipt has an invalid binding or schema",
        )
        return intent, result


@workspace._workspace_operation
def _verify_applied_workspace(
    ctx,
    operation_id,
    workspace_root,
    *,
    intent,
    result,
    preview,
    allow_unresolved=False,
):
    root, marker = workspace._load_root(ctx, operation_id, workspace_root)
    saved = workspace._read_sealed(root / "workspace-result.json", "result_id")
    original = preview["preview"]["inventories"]["original"]
    candidate = preview["preview"]["inventories"]["candidate"]
    original_intent, original_result = preflight._load(ctx, operation_id)
    expected_request = {
        key: value
        for key, value in intent["request"].items()
        if key not in {"expected_plan_id", "workspace_root", "timeout"}
    }
    _require(
        original_intent["binding"] == intent["binding"]
        and original_intent["request"] == expected_request
        and original_result["status"] == "unavailable"
        and marker["preview_id"] == intent["request"]["expected_preview_id"]
        and marker["original_inventory"] == original,
        RECOVERY,
        "Applied workspace differs from its original intent",
    )
    expected = {
        "schema": 1,
        "project_id": ctx.project_id,
        "operation_id": operation_id,
        "preview_id": marker["preview_id"],
        "intent_id": original_intent["intent_id"],
        "status": "applied",
        "workspace_root": str(root),
        "before_digest": workspace._digest(original),
        "after_digest": workspace._digest(candidate),
        "changed_paths": workspace._changed_paths(original, candidate),
        "workspace_source_written": True,
        "live_source_written": False,
        "created_at": saved.get("created_at"),
    }
    _require(
        type(saved.get("created_at")) is str
        and 1 <= len(saved["created_at"]) <= 64
        and saved == workspace._seal(expected, "result_id")
        and saved["result_id"] == result["workspace_result_id"],
        RECOVERY,
        "Applied workspace receipt is absent or belongs to another result",
    )
    if allow_unresolved:
        return
    workspace._ensure_clean_phase(root)
    state = workspace._read_sealed(root / "workspace-state.json", "state_id")
    if (root / "workspace-undo.json").exists():
        undo = workspace._undo_receipt(ctx, operation_id, root, marker, saved)
        _require(
            state.get("undo_id") == undo["undo_id"],
            RECOVERY,
            "Undo state differs from its receipt",
        )
        expected_rows = original
    else:
        _require(
            state.get("result_id") == saved["result_id"],
            RECOVERY,
            "Apply state differs from its receipt",
        )
        expected_rows = candidate

    def check():
        workspace._check(ctx)

    actual = workspace._inventory(root / "tree", check)
    with _pin_inputs(root / "tree", actual):
        _require(
            actual == expected_rows
            and workspace._inventory(root / "tree", check) == actual,
            "METADATA_UNDO_CONFLICT",
            "Workspace changed after its apply or undo receipt",
        )


def _verify_applied(ctx, operation_id, intent, result, *, allow_unresolved=False):
    with pinned_directory(journal_path(ctx, operation_id)):
        preview = runs.get_preview(ctx, operation_id)
        binding = preflight._binding(preview)
        _require(
            preview["preview_id"] == result["native_preview_id"]
            and all(
                binding[key] == intent["binding"][key]
                for key in ("plan_id", "profile_id", "inventory_digests")
            ),
            RECOVERY,
            "Native preview is absent or differs from the applied result",
        )
        _verify_applied_workspace(
            ctx,
            operation_id,
            intent["request"]["workspace_root"],
            intent=intent,
            result=result,
            preview=preview,
            allow_unresolved=allow_unresolved,
        )


def get_native_apply_result(ctx, operation_id):
    """Read historical outcome; an unfinished intent never permits execution."""
    with authorized(ctx):
        intent, result = _read_native_result(ctx, operation_id)
        if result["status"] == "applied":
            _verify_applied(ctx, operation_id, intent, result)
        return result


def _fresh(ctx, intent, preview, check):
    check()
    status, _ = preflight._evaluate(ctx, intent, preview)
    _require(
        status == "unavailable",
        "METADATA_APPLY_STALE",
        "Native operation baseline is stale",
    )


async def _execute_native(ctx, plan, preview, operation_id, admission):
    # Admission belongs to edt_session's exclusive directory creation. The
    # preview convenience API can return an old run and must not be used here.
    async with edt_session(
        ctx, preview["profile_id"], operation_id, plan=plan, admission=admission
    ) as client:
        await client.import_configuration()
        request = plan["request"]
        await client.wait_for_model(request["catalog"]["name"])
        await client.export_configuration("baseline")
        baseline = client.run / "baseline-xml"
        inventory = exported_inventory(baseline, authorize=client.check)
        with _pin_inputs(baseline, inventory):
            _verify_identity(baseline, inventory, request, client.check)
            _require(
                inventory == preview["preview"]["inventories"]["baseline"],
                "METADATA_NATIVE_FOREIGN_OUTPUT",
                "Native baseline differs before rename",
            )
        arguments = (
            request["catalog"]["name"],
            request["attribute"]["name"],
            request["new_name"],
        )
        response = await client.rename_attribute(*arguments)
        token = runs.preview_hash(response, request)
        await client.rename_attribute(*arguments, expected_hash=token)
        await client.export_configuration("candidate")
    run = runs.run_path(ctx, operation_id)
    with pinned_directory(run):
        result = runs._result(
            runs._request(ctx, run, operation_id), build_preview(ctx, plan, run)
        )
        write_record(run / "preview.json", result)
    return result


async def apply_native_workspace(
    ctx,
    preview_operation_id,
    operation_id,
    workspace_root,
    *,
    expected_preview_id,
    expected_plan_id,
    expected_head,
    timeout=600,
):
    """Reproduce an exact preview in EDT and publish only to a new owned copy.

    No live executor, arbitrary EDT client, runtime locator or write tool can be
    passed here. The profile and typed plan come from the retained preview.
    """
    with authorized(ctx) as check:
        _require(
            not ctx.state.path.parent.resolve().is_relative_to(
                ctx.source_root.resolve()
            ),
            "METADATA_APPLY_UNSUPPORTED",
            "Native journal requires project state outside the live source tree",
        )
        request = preflight._request(
            ctx, preview_operation_id, operation_id, expected_preview_id, expected_head
        )
        _require(
            type(expected_plan_id) is str
            and preflight.HASH.fullmatch(expected_plan_id),
            "METADATA_NATIVE_INVALID",
            "Exact plan token is required",
        )
        _require(
            type(timeout) is int and 0 < timeout <= 600,
            "METADATA_NATIVE_INVALID",
            "Native deadline must be within 600 seconds",
        )
        root = workspace._workspace_root(workspace_root)
        workspace._owned_paths(ctx, root)
        request.update(
            expected_plan_id=expected_plan_id, workspace_root=str(root), timeout=timeout
        )
        journal = journal_path(ctx, operation_id)
        if journal.exists():
            intent = _read_intent(ctx, operation_id)
            _require(
                intent["request"] == request,
                "METADATA_NATIVE_CONFLICT",
                "Operation ID has a different request",
            )
            return get_native_apply_result(ctx, operation_id)
        _require(
            not runs.run_path(ctx, operation_id).exists(),
            "METADATA_NATIVE_CONFLICT",
            "Native runtime operation already exists; it must not be reused",
        )
        preview = runs.get_preview(ctx, preview_operation_id)
        _require(
            preview["preview_id"] == expected_preview_id
            and preview["plan_id"] == expected_plan_id,
            "METADATA_NATIVE_CONFLICT",
            "Preview or plan token differs",
        )
        with pinned_directory(runs.run_path(ctx, preview_operation_id)):
            plan = validate_plan(
                ctx,
                runs._request(
                    ctx, runs.run_path(ctx, preview_operation_id), preview_operation_id
                )["plan"],
            )
        intent = preflight._seal(
            {"schema": 1, "request": request, "binding": preflight._binding(preview)},
            "intent_id",
        )
        with edt_admission(
            ctx, preview["profile_id"], operation_id, plan=plan
        ) as admission, pinned_directory(ctx.state.path.parent):
            journal.parent.mkdir(exist_ok=True)
            with pinned_directory(journal.parent):
                check()
                try:
                    journal.mkdir()
                except FileExistsError as exc:
                    raise CoreError(
                        "METADATA_NATIVE_BUSY", "Another caller admitted this operation"
                    ) from exc
                with pinned_directory(journal):
                    write_record(journal / "intent.json", intent)
                    native_started = False
                    publication_started = False
                    try:
                        _fresh(ctx, intent, preview, check)
                        preflight.preflight_apply(
                            ctx,
                            preview_operation_id,
                            operation_id,
                            expected_preview_id=expected_preview_id,
                            expected_head=expected_head,
                        )
                        workspace.create_workspace(ctx, operation_id, root)
                        # Retain the workspace lock during EDT, then use the public
                        # writer which reacquires it and checks head/tree/preview.
                        with workspace._workspace_lock(root):
                            _fresh(ctx, intent, preview, check)
                            native_started = True
                            deadline = time.monotonic() + timeout
                            reproduced = await guarded_wait(
                                _execute_native(
                                    ctx, plan, preview, operation_id, admission
                                ),
                                check,
                                timeout,
                            )
                            if time.monotonic() >= deadline:
                                raise TimeoutError(
                                    "Native completion arrived after its deadline"
                                )
                            native_started = False
                            reproduced = runs.get_preview(ctx, operation_id)
                            expected = preview["preview"]
                            actual = reproduced["preview"]
                            fields = (
                                "schema",
                                "plan_id",
                                "snapshot",
                                "layer_id",
                                "inventories",
                                "normalization",
                                "edit",
                                "identity",
                            )
                            _require(
                                all(
                                    actual[field] == expected[field] for field in fields
                                ),
                                "METADATA_NATIVE_FOREIGN_OUTPUT",
                                "Native export differs from the exact retained preview",
                            )
                            _fresh(ctx, intent, preview, check)
                        check()
                        publication_started = True
                        applied = workspace.apply_workspace(ctx, operation_id, root)
                        result = _result(
                            intent,
                            "applied",
                            native_preview_id=reproduced["preview_id"],
                            workspace_result_id=applied["result_id"],
                        )
                        check()
                        write_record(journal / "result.json", result)
                        return result
                    except BaseException as exc:
                        uncertain = native_started or publication_started
                        reason = (
                            exc.code
                            if isinstance(exc, CoreError)
                            else type(exc).__name__
                        )
                        status = (
                            "OUTCOME_UNKNOWN"
                            if uncertain
                            else (
                                "revoked"
                                if reason == "PROJECT_FORBIDDEN"
                                else "stale"
                                if reason == "METADATA_APPLY_STALE"
                                else "failed"
                            )
                        )
                        # Terminal diagnostics contain no exception text or secrets.
                        # A lost result is observed as unknown by the reader.
                        if not (journal / "result.json").exists():
                            write_record(
                                journal / "result.json",
                                _result(intent, status, reason=reason),
                            )
                        if isinstance(exc, TimeoutError):
                            raise CoreError(
                                "EDT_OUTCOME_UNKNOWN",
                                "Native deadline expired; do not replay",
                            ) from exc
                        raise


def undo_native_workspace(ctx, operation_id, workspace_root):
    """Explicit CAS undo restores the owned copy; never calls EDT or live 1C."""
    with authorized(ctx):
        intent = _read_intent(ctx, operation_id)
        root = workspace._workspace_root(workspace_root)
        _require(
            str(root) == intent["request"]["workspace_root"],
            "METADATA_NATIVE_CONFLICT",
            "Undo targets a different workspace",
        )
        result = get_native_apply_result(ctx, operation_id)
        _require(
            result["status"] == "applied",
            RECOVERY,
            "Only confirmed publication can be undone",
        )
        return workspace.undo_workspace(ctx, operation_id, root)


def restore_native_workspace(ctx, operation_id, workspace_root):
    """Explicitly recover an interrupted local publication to its backup only."""
    with authorized(ctx):
        intent, native_result = _read_native_result(ctx, operation_id)
        root = workspace._workspace_root(workspace_root)
        _require(
            str(root) == intent["request"]["workspace_root"],
            "METADATA_NATIVE_CONFLICT",
            "Restore targets a different workspace",
        )
        try:
            interrupted_undo = workspace._has_interrupted_undo(ctx, operation_id, root)
        except CoreError as exc:
            if exc.code == "METADATA_WORKSPACE_NOT_FOUND":
                interrupted_undo = False
            else:
                raise
        if interrupted_undo:
            _require(
                native_result["status"] in {"OUTCOME_UNKNOWN", "applied"},
                RECOVERY,
                "Restore requires an interrupted publication; completed apply uses undo",
            )
            if native_result["status"] == "applied":
                _verify_applied(
                    ctx,
                    operation_id,
                    intent,
                    native_result,
                    allow_unresolved=True,
                )
            # Core recovery completes the already-started undo from its sealed
            # backup/stage. It never replays the native EDT operation.
            return workspace.recover_workspace(
                ctx, operation_id, root, target="original"
            )
        _require(
            native_result["status"] == "OUTCOME_UNKNOWN",
            RECOVERY,
            "Restore requires an interrupted publication; completed apply uses undo",
        )
        current = workspace.get_workspace_status(ctx, operation_id, root)
        if (
            current["state"] is not None
            and current["state"].get("phase") == "applying"
            and current["result"] is not None
        ):
            # Finalize only an already receipted, exact candidate before undo.
            # This recovery branch changes receipts, never republishes its tree.
            workspace.recover_workspace(ctx, operation_id, root, target="candidate")
            return workspace.undo_workspace(ctx, operation_id, root)
        if (
            current["state"] is not None
            and current["state"].get("phase") == "complete"
            and current["result"] is not None
            and current["result"].get("result_id") == current["state"].get("result_id")
        ):
            # A completed local receipt may survive loss of our terminal result.
            # Explicit restore can CAS-undo it without claiming EDT was retried.
            return workspace.undo_workspace(ctx, operation_id, root)
        return workspace.recover_workspace(ctx, operation_id, root, target="original")
