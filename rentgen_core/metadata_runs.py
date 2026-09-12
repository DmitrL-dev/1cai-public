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


def _validate_business_evidence(evidence, result, raw):
    preview = result["preview"]
    require(type(evidence) is dict, "Business evidence must be an object")
    required = {
        "schema",
        "source",
        "source_preview_id",
        "platform_sha256",
        "ibcmd_sha256",
        "engine_cfe_sha256",
        "source_inventories",
        "reports",
        "records",
        "value_cases",
        "full_record_reference_preserved",
        "schema_restore_preserves_data",
        "wrong_uuid_compiles_but_loses_data",
        "product_apply_undo",
        "unmodified_preview_execution",
    }
    require(required <= set(evidence), "Business evidence is incomplete")
    require(type(evidence["schema"]) is int and evidence["schema"] == 1)
    require(
        evidence["source"] == "real 1C/YAxUnit on a new owned file infobase",
        "Unsupported business evidence source",
    )
    require(
        evidence["source_preview_id"] == result["preview_id"],
        "Business evidence belongs to another preview",
    )
    for key in ("platform_sha256", "ibcmd_sha256", "engine_cfe_sha256"):
        require(
            type(evidence[key]) is str and re.fullmatch(r"[0-9a-f]{64}", evidence[key]),
            "Invalid business evidence tool hash",
        )
    inventories = evidence["source_inventories"]
    require(type(inventories) is dict, "Business evidence inventories are invalid")
    for source, target in (
        ("original", "original"),
        ("normalized", "baseline"),
        ("renamed", "candidate"),
    ):
        require(
            source in inventories
            and canonical_bytes(inventories[source])
            == canonical_bytes(preview["inventories"][target]),
            "Business evidence inventory does not match preview",
        )
    reports = evidence["reports"]
    require(type(reports) is dict, "Business evidence reports are invalid")
    positive = ("seed", "reopen-original", "normalized", "renamed", "restored")
    for phase in positive:
        report = reports.get(phase)
        require(
            type(report) is dict
            and report.get("status") == "passed"
            and type(report.get("counts")) is dict
            and report["counts"].get("errors") == 0
            and report["counts"].get("failures") == 0,
            "Positive business phase did not pass: " + phase,
        )
    negative = reports.get("wrong-uuid")
    require(
        type(negative) is dict
        and negative.get("status") == "failed"
        and type(negative.get("counts")) is dict
        and negative["counts"].get("errors") == 0
        and negative["counts"].get("failures") == 1,
        "Expected wrong-UUID negative phase is missing",
    )
    require(evidence["records"] == 3)
    require(evidence["value_cases"] == ["unicode", "empty", "length_32"])
    for key in (
        "full_record_reference_preserved",
        "schema_restore_preserves_data",
        "wrong_uuid_compiles_but_loses_data",
        "unmodified_preview_execution",
    ):
        require(evidence[key] is True, "Business evidence flag is false: " + key)
    require(evidence["product_apply_undo"] is False)
    return {
        "status": "passed",
        "scope": "owned_fixture",
        "source": evidence["source"],
        "records": evidence["records"],
        "value_cases": evidence["value_cases"],
        "positive_phases": list(positive),
        "negative_phase": "wrong-uuid",
        "platform_sha256": evidence["platform_sha256"],
        "ibcmd_sha256": evidence["ibcmd_sha256"],
        "engine_cfe_sha256": evidence["engine_cfe_sha256"],
        "evidence_sha256": sha256(raw),
    }


def _read_business_evidence(run, result):
    path = run / "business-evidence.json"
    if not path.exists():
        return None
    raw = read_retained(path, 2 * 1024**2)
    evidence = parse_json(raw)
    return _validate_business_evidence(evidence, result, raw)


def _with_business_evidence(result, summary):
    preview = dict(result["preview"])
    preview["business_data_test"] = {
        "status": summary["status"],
        "scope": summary["scope"],
        "records": summary["records"],
        "value_cases": summary["value_cases"],
        "evidence_sha256": summary["evidence_sha256"],
    }
    return {**result, "preview": preview, "business_evidence": summary}


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
            summary = _read_business_evidence(run, actual)
            return (
                actual if summary is None else _with_business_evidence(actual, summary)
            )


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


def attach_business_evidence(ctx, operation_id, evidence):
    """Bind the accepted own-fixture data run to an immutable metadata preview."""
    with authorized(ctx):
        run = run_path(ctx, operation_id)
        with pinned_directory(run):
            request = _request(ctx, run, operation_id)
            require(
                (run / "preview.json").exists()
                and (run / "runtime-closed.json").exists(),
                "Preview is incomplete; attach evidence only after closure",
            )
            closed = parse_json(read_retained(run / "runtime-closed.json", 8192))
            require(closed == {"status": "closed", "metadata_verified": False})
            stored = parse_json(read_retained(run / "preview.json", 2 * 1024**2))
            actual = _result(request, build_preview(ctx, request["plan"], run))
            require(
                canonical_bytes(stored) == canonical_bytes(actual),
                "Preview or retained outputs were changed",
            )
            raw = canonical_bytes(evidence)
            summary = _validate_business_evidence(evidence, actual, raw)
            path = run / "business-evidence.json"
            if path.exists():
                previous = parse_json(read_retained(path, 2 * 1024**2))
                if canonical_bytes(previous) != raw:
                    raise CoreError(
                        "METADATA_EVIDENCE_CONFLICT",
                        "Business evidence is already bound to another report",
                    )
            else:
                write_record(path, evidence)
        return _with_business_evidence(actual, summary)
