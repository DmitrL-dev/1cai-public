"""Deterministic draft workflow; the model cannot select tools or service IDs."""
import hashlib
import re
from uuid import uuid4

from rentgen_core import draft_editing, proposals
from rentgen_core.diagnostics import BSL_PROFILE_ID, BSL_RUNTIME_MANIFEST_SHA256
from rentgen_core.stdio_mcp import validate_arguments


def require(condition, code):
    if not condition:
        raise ValueError(code)


def checked(body, receipt, raw):
    require(body.get("receipt") == receipt, "CHECK_RECEIPT_MISMATCH")
    diagnostic = body["diagnostic"]
    analysis = diagnostic["analysis"]
    require(
        diagnostic["source_ref"] == receipt["source_ref"]
        and diagnostic["proposal_content_id"] == receipt["proposal_content_id"]
        and diagnostic["evidence"] == "ephemeral_unattested"
        and analysis["status"] == "completed"
        and analysis["exit_code"] == 0
        and analysis["runtime_verified"] is True
        and analysis["coverage"] == "exact_one"
        and analysis["diagnostics_complete"] is True
        and analysis["runtime_manifest_sha256"] == BSL_RUNTIME_MANIFEST_SHA256
        and analysis["candidate_sha256"] == hashlib.sha256(raw).hexdigest()
        and type(analysis["report_sha256"]) is str
        and re.fullmatch(r"[0-9a-f]{64}", analysis["report_sha256"])
        and type(analysis["diagnostics"]) is list
        and diagnostic["diagnostics_status"]
        == ("diagnostics_present" if analysis["diagnostics"] else "clean")
        and body["tests"] == {"status": "not_run"}
        and body["apply"] == {"status": "unavailable"},
        "ANALYSIS_NOT_VERIFIED",
    )
    return body


async def read_candidate(call, selected, receipt):
    part = (
        await call(
            "rentgen_draft_read",
            {
                **selected,
                "revision": receipt["revision"],
                "encoding": "utf-8",
                "offset": 0,
                "limit": 32768,
            },
        )
    )["draft"]
    require(
        part["receipt"] == receipt and part["source_ref"] == receipt["source_ref"],
        "READ_RECEIPT_MISMATCH",
    )
    require(
        part["offset"] == 0
        and part["next_offset"] is None
        and part["encoding"] == "utf-8",
        "MODEL_SOURCE_LIMIT",
    )
    raw = part["text"].encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    require(
        len(raw) == part["size_bytes"] == part["candidate_size_bytes"] <= 32768
        and digest == part["chunk_sha256"] == part["candidate_sha256"],
        "CANDIDATE_HASH_MISMATCH",
    )
    return raw


async def repair(call, source_ref, instruction, model, record):
    """`record` must persist before returning; failures never retry a mutation."""
    require(
        type(instruction) is str and 1 <= len(instruction.encode("utf-8")) <= 4096,
        "INVALID_INSTRUCTION",
    )
    snapshot = source_ref["snapshot"]
    project = snapshot["project_id"]
    selected = {"project_id": project, "draft_id": str(uuid4())}
    pin = {**selected, "snapshot_id": snapshot["snapshot_id"]}
    start = {
        **pin,
        "source_ref": source_ref,
        "operation_id": str(uuid4()),
        "title": "AI: " + instruction.splitlines()[0][:230],
    }
    validate_arguments("rentgen_draft_start", start)
    record(
        {
            "phase": "start_requested",
            **selected,
            "operation_id": start["operation_id"],
            "source_ref": source_ref,
        }
    )
    first = (await call("rentgen_draft_start", start))["draft"]
    require(
        first["project_id"] == project
        and first["draft_id"] == selected["draft_id"]
        and first["revision"] == 1
        and first["source_ref"] == source_ref
        and first["operation_id"] == start["operation_id"],
        "START_RECEIPT_MISMATCH",
    )
    record({"phase": "draft_created", "receipt": first})
    original = await read_candidate(call, selected, first)
    require(
        hashlib.sha256(original).hexdigest() == source_ref["raw_sha256"],
        "START_CONTENT_MISMATCH",
    )
    check_args = {**pin, "diagnostics_profile": BSL_PROFILE_ID, "revision": 1}
    before = checked(
        (await call("rentgen_draft_check", check_args))["draft"], first, original
    )
    record({"phase": "baseline_checked", "check": before})
    record(
        {
            "phase": "model_requested",
            "candidate_sha256": hashlib.sha256(original).hexdigest(),
        }
    )
    try:
        proposed = await model.propose(
            original, instruction, before["diagnostic"]["analysis"]["diagnostics"]
        )
    except Exception as exc:
        record(
            {
                "phase": "model_failed",
                "metrics": getattr(model, "last_metrics", {}),
                "error_type": type(exc).__name__,
            }
        )
        raise
    expected = draft_editing.replace_text(original, proposed["edits"])
    proposals._policy(original, expected)
    require(
        expected == proposed["candidate"] and expected != original,
        "MODEL_CANDIDATE_MISMATCH",
    )
    require(len(expected) <= 32768, "MODEL_SOURCE_LIMIT")
    edit = {
        **pin,
        "operation_id": str(uuid4()),
        "expected_revision": 1,
        "edits": proposed["edits"],
    }
    validate_arguments("rentgen_draft_edit", edit)
    record(
        {
            "phase": "model_responded",
            "metrics": proposed["metrics"],
            "summary": proposed["summary"],
        }
    )
    record(
        {
            "phase": "edit_requested",
            **selected,
            "operation_id": edit["operation_id"],
            "expected_revision": 1,
            "candidate_sha256": hashlib.sha256(expected).hexdigest(),
        }
    )
    second = (await call("rentgen_draft_edit", edit))["draft"]
    require(
        second["project_id"] == project
        and second["draft_id"] == selected["draft_id"]
        and second["revision"] == 2
        and second["source_ref"] == source_ref
        and second["operation_id"] == edit["operation_id"],
        "EDIT_RECEIPT_MISMATCH",
    )
    record({"phase": "draft_saved", "receipt": second})
    actual = await read_candidate(call, selected, second)
    require(actual == expected, "SAVED_CANDIDATE_MISMATCH")
    after = checked(
        (await call("rentgen_draft_check", {**check_args, "revision": 2}))["draft"],
        second,
        actual,
    )
    report = {
        "status": "analysis_clean"
        if not after["diagnostic"]["analysis"]["diagnostics"]
        else "diagnostics_present",
        "receipt": second,
        "before": before,
        "after": after,
        "model": proposed["metrics"],
        "model_summary": proposed["summary"],
        "candidate_sha256": hashlib.sha256(actual).hexdigest(),
        "tests": {"status": "not_run"},
        "apply": {"status": "unavailable"},
    }
    record({"phase": "finished", "status": report["status"], "receipt": second})
    return report
