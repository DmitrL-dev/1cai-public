"""Snapshot-bound metadata preview and validated readback; live apply is separate."""
import re

from ._windows_source_tree import pinned_directory, read_retained
from .edt_execution import write_record
from .edt_inventory import exported_inventory
from .edt_profiles import authorized, parse_json
from .edt_runtime import edt_session
from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .metadata_plans import keys, require, validate_plan
from .metadata_preview import build_preview, _verify_identity
from .platform_check import _pin_inputs
from .snapshots import validate_operation_id


def run_path(ctx, operation_id):
    return ctx.state.path.parent / "metadata-runs" / validate_operation_id(operation_id)


def preview_hash(response, request):
    matches = []
    for block in response.content:
        if block.type != "resource":
            continue
        raw = getattr(block.resource, "text", "")
        if not raw.startswith("---\n"):
            continue
        header, separator, _ = raw[4:].partition("\n---")
        if not separator:
            continue
        fields = {}
        for line in header.splitlines():
            key, sep, value = line.partition(": ")
            require(sep and key not in fields, "Ambiguous rename preview")
            fields[key] = value
        expected = (
            "Catalog."
            + request["catalog"]["name"]
            + ".Attribute."
            + request["attribute"]["name"]
        )
        require(
            fields.get("action") == "preview"
            and fields.get("objectFqn") == expected
            and fields.get("newName") == request["new_name"]
            and fields.get("problems") == "0",
            "Rename preview differs from plan",
        )
        token = fields.get("contentHash", "")
        require(re.fullmatch(r"[0-9a-f]{16}", token), "Missing rename preview token")
        matches.append(token)
    require(len(matches) == 1, "Missing or ambiguous rename preview token")
    return matches[0]


def _request(ctx, run, operation_id):
    value = parse_json(read_retained(run / "runtime-request.json", 2 * 1024**2))
    keys(value, {"schema", "project_id", "operation_id", "profile_id", "plan"})
    require(type(value["schema"]) is int and value["schema"] == 1)
    require(
        value["project_id"] == ctx.project_id and value["operation_id"] == operation_id,
        "Metadata operation belongs to another context",
    )
    require(
        type(value["profile_id"]) is str
        and re.fullmatch(r"[0-9a-f]{64}", value["profile_id"])
    )
    value["plan"] = validate_plan(ctx, value["plan"])
    return value


def _result(request, preview):
    value = {
        "schema": 1,
        "operation_id": request["operation_id"],
        "project_id": request["project_id"],
        "profile_id": request["profile_id"],
        "plan_id": request["plan"]["plan_id"],
        "preview": preview,
    }
    return {**value, "preview_id": sha256(canonical_bytes(value))}


def get_preview(ctx, operation_id):
    with authorized(ctx):
        run = run_path(ctx, operation_id)
        with pinned_directory(run):
            request = _request(ctx, run, operation_id)
            if (
                not (run / "preview.json").exists()
                or not (run / "runtime-closed.json").exists()
            ):
                raise CoreError(
                    "METADATA_RUN_INCOMPLETE",
                    "Preview is incomplete; do not replay the operation",
                )
            closed = parse_json(read_retained(run / "runtime-closed.json", 8192))
            require(closed == {"status": "closed", "metadata_verified": False})
            stored = parse_json(read_retained(run / "preview.json", 2 * 1024**2))
            actual = _result(request, build_preview(ctx, request["plan"], run))
            require(
                canonical_bytes(stored) == canonical_bytes(actual),
                "Preview or retained outputs were changed",
            )
            return actual


async def create_preview(ctx, plan, profile_id, operation_id):
    with authorized(ctx):
        plan = validate_plan(ctx, plan)
        run = run_path(ctx, operation_id)
        if run.exists():
            with pinned_directory(run):
                previous = _request(ctx, run, operation_id)
                require(
                    previous["profile_id"] == profile_id and previous["plan"] == plan,
                    "Operation ID already has a different request",
                )
            return get_preview(ctx, operation_id)
        async with edt_session(ctx, profile_id, operation_id, plan=plan) as client:
            await client.import_configuration()
            request = plan["request"]
            await client.wait_for_model(request["catalog"]["name"])
            await client.export_configuration("baseline")
            baseline = client.run / "baseline-xml"
            inventory = exported_inventory(baseline, authorize=client.check)
            with _pin_inputs(baseline, inventory):
                _verify_identity(baseline, inventory, request, client.check)
            arguments = (
                request["catalog"]["name"],
                request["attribute"]["name"],
                request["new_name"],
            )
            response = await client.rename_attribute(*arguments)
            token = preview_hash(response, request)
            await client.rename_attribute(*arguments, expected_hash=token)
            await client.export_configuration("candidate")
        with pinned_directory(run):
            binding = _request(ctx, run, operation_id)
            result = _result(binding, build_preview(ctx, plan, run))
            write_record(run / "preview.json", result)
        return result
