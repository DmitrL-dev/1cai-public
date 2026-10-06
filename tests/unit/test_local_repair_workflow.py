"""Workflow guards bind evidence to the saved revision; fixtures are not BSL runs."""
import copy
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest
from rentgen_core.diagnostics import (
    BSL_CONFIG_SHA256,
    BSL_PROFILE_ID,
    BSL_RUNTIME_MANIFEST_SHA256,
)


MISSING = object()
DEPENDENCY_CHANGES = {
    "wrong_profile": ("profile_id", "another-profile"),
    "wrong_config": ("config_sha256", "0" * 64),
    "wrong_scope": ("scope", "whole_project"),
    "wrong_size": ("candidate_size_bytes", 3),
    **{
        f"{problem}_{field}": (field, value)
        for field in ("profile_id", "config_sha256", "scope", "candidate_size_bytes")
        for problem, value in (("missing", MISSING), ("null", None), ("boolean", True))
    },
    "float_size": ("candidate_size_bytes", 4.0),
    "string_size": ("candidate_size_bytes", "4"),
}


@pytest.fixture
def workflow():
    spec = importlib.util.spec_from_file_location(
        "repair_workflow",
        Path(__file__).resolve().parents[2]
        / "integrations/open-editor/repair_workflow.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_body(receipt, raw):
    return {
        "receipt": receipt,
        "diagnostic": {
            "source_ref": receipt["source_ref"],
            "proposal_content_id": receipt["proposal_content_id"],
            "evidence": "ephemeral_unattested",
            "diagnostics_status": "clean",
            "analysis": {
                "status": "completed",
                "exit_code": 0,
                "runtime_verified": True,
                "coverage": "exact_one",
                "diagnostics_complete": True,
                "diagnostics": [],
                "runtime_manifest_sha256": BSL_RUNTIME_MANIFEST_SHA256,
                "candidate_sha256": hashlib.sha256(raw).hexdigest(),
                "candidate_size_bytes": len(raw),
                "profile_id": BSL_PROFILE_ID,
                "config_sha256": BSL_CONFIG_SHA256,
                "scope": "single_module_isolated",
                "report_sha256": "f" * 64,
            },
        },
        "tests": {"status": "not_run"},
        "apply": {"status": "unavailable"},
    }


def test_partial_wrong_or_unverified_analysis_is_not_accepted(workflow):
    receipt = {"source_ref": {"test": "fixture"}, "proposal_content_id": "a" * 64}
    raw = b"old"
    body = check_body(receipt, raw)
    assert workflow.checked(body, receipt, raw) == body
    for field, value in [
        ("diagnostics_complete", False),
        ("runtime_verified", False),
        ("candidate_sha256", "0" * 64),
        ("runtime_manifest_sha256", "0" * 64),
        ("coverage", "partial"),
        ("exit_code", 1),
    ]:
        changed = copy.deepcopy(body)
        changed["diagnostic"]["analysis"][field] = value
        with pytest.raises(ValueError):
            workflow.checked(changed, receipt, raw)


@pytest.mark.parametrize(
    "failure", ["baseline", "conflict", "lost_ack", None, *DEPENDENCY_CHANGES]
)
def test_workflow_calls_model_once_and_never_retries_mutation(workflow, failure):
    project = "00000000-0000-4000-8000-000000000001"
    ref = {
        "snapshot": {
            "project_id": project,
            "snapshot_id": "a" * 64,
            "manifest_hash": "a" * 64,
        },
        "layer_id": "base",
        "relative_path": "Module.bsl",
        "raw_sha256": hashlib.sha256(b"Old\n").hexdigest(),
    }
    calls, records, receipts, model_calls = [], [], {}, []
    raw = b"Old\n"

    async def call(name, args):
        nonlocal raw
        calls.append(name)
        if name == "rentgen_draft_start":
            receipts[1] = {
                "project_id": project,
                "draft_id": args["draft_id"],
                "revision": 1,
                "source_ref": ref,
                "operation_id": args["operation_id"],
                "proposal_content_id": "b" * 64,
            }
            return {"draft": receipts[1]}
        if name == "rentgen_draft_read":
            digest = hashlib.sha256(raw).hexdigest()
            return {
                "draft": {
                    "receipt": receipts[args["revision"]],
                    "source_ref": ref,
                    "candidate_size_bytes": len(raw),
                    "candidate_sha256": digest,
                    "offset": 0,
                    "size_bytes": len(raw),
                    "encoding": "utf-8",
                    "text": raw.decode(),
                    "chunk_sha256": digest,
                    "next_offset": None,
                }
            }
        if name == "rentgen_draft_check":
            assert args["diagnostics_profile"] == BSL_PROFILE_ID
            body = check_body(receipts[args["revision"]], raw)
            if failure == "baseline":
                body["diagnostic"]["analysis"]["diagnostics_complete"] = False
            if args["revision"] == 2 and failure in DEPENDENCY_CHANGES:
                # The saved revision and its bytes match; only analyzer evidence
                # dependencies are invalid. This is a consumer contract fixture.
                assert any(row["phase"] == "baseline_checked" for row in records)
                assert records[-1] == {"phase": "draft_saved", "receipt": receipts[2]}
                field, value = DEPENDENCY_CHANGES[failure]
                if value is MISSING:
                    del body["diagnostic"]["analysis"][field]
                else:
                    body["diagnostic"]["analysis"][field] = value
            return {"draft": body}
        if name == "rentgen_draft_edit":
            assert records[-1]["phase"] == "edit_requested"
            assert records[-1]["operation_id"] == args["operation_id"]
            if failure == "conflict":
                raise ValueError("DRAFT_CONFLICT")
            raw = b"New\n"
            receipts[2] = {
                **receipts[1],
                "revision": 2,
                "operation_id": args["operation_id"],
                "proposal_content_id": "c" * 64,
            }
            if failure == "lost_ack":
                raise ValueError("RESPONSE_LOST_AFTER_SAVE")
            return {"draft": receipts[2]}
        raise AssertionError(name)

    async def propose(original, instruction, diagnostics):
        model_calls.append(True)
        return {
            "edits": [{"old_text": "Old", "new_text": "New"}],
            "candidate": b"New\n",
            "summary": "fixture",
            "metrics": {},
        }

    async def run():
        return await workflow.repair(
            call, ref, "Fix", SimpleNamespace(propose=propose), records.append
        )

    if failure in DEPENDENCY_CHANGES:
        with pytest.raises(ValueError, match="^ANALYSIS_NOT_VERIFIED$"):
            anyio.run(run)
        baseline = next(row["check"] for row in records if row["phase"] == "baseline_checked")
        assert baseline == check_body(receipts[1], b"Old\n")
        # A later revision does not erase valid, explicitly selected history.
        assert workflow.checked(baseline, receipts[1], b"Old\n") is baseline
        assert records[-1] == {"phase": "draft_saved", "receipt": receipts[2]}
        assert all(row["phase"] != "finished" for row in records)
        assert calls == [
            "rentgen_draft_start", "rentgen_draft_read", "rentgen_draft_check",
            "rentgen_draft_edit", "rentgen_draft_read", "rentgen_draft_check",
        ]
    elif failure:
        with pytest.raises(ValueError):
            anyio.run(run)
    else:
        report = anyio.run(run)
        assert (
            report["status"] == "analysis_clean" and report["receipt"]["revision"] == 2
        )
        assert (
            report["tests"]["status"] == "not_run"
            and report["apply"]["status"] == "unavailable"
        )
    assert len(model_calls) == (0 if failure == "baseline" else 1)
    assert calls.count("rentgen_draft_edit") == (0 if failure == "baseline" else 1)


@pytest.mark.parametrize("field", ["runtime_verified", "diagnostics_complete"])
@pytest.mark.parametrize("value", [MISSING, None, False, 1])
def test_unknown_or_false_evidence_is_not_verification(workflow, field, value):
    receipt = {"source_ref": {"test": "fixture"}, "proposal_content_id": "a" * 64}
    body = check_body(receipt, b"old")
    if value is MISSING:
        del body["diagnostic"]["analysis"][field]
    else:
        body["diagnostic"]["analysis"][field] = value
    with pytest.raises(ValueError, match="^ANALYSIS_NOT_VERIFIED$"):
        workflow.checked(body, receipt, b"old")


@pytest.mark.parametrize("field", ["diagnostic", "analysis"])
@pytest.mark.parametrize("value", [MISSING, None, [], "unknown"])
def test_malformed_analysis_container_is_not_verification(workflow, field, value):
    receipt = {"source_ref": {"test": "fixture"}, "proposal_content_id": "a" * 64}
    body = check_body(receipt, b"old")
    owner = body if field == "diagnostic" else body["diagnostic"]
    if value is MISSING:
        del owner[field]
    else:
        owner[field] = value
    with pytest.raises(ValueError, match="^ANALYSIS_NOT_VERIFIED$"):
        workflow.checked(body, receipt, b"old")


@pytest.mark.parametrize("value", [MISSING, None, False, 0.0, "0"])
def test_exit_code_requires_a_verified_integer_zero(workflow, value):
    receipt = {"source_ref": {"test": "fixture"}, "proposal_content_id": "a" * 64}
    body = check_body(receipt, b"old")
    if value is MISSING:
        del body["diagnostic"]["analysis"]["exit_code"]
    else:
        body["diagnostic"]["analysis"]["exit_code"] = value
    with pytest.raises(ValueError, match="^ANALYSIS_NOT_VERIFIED$"):
        workflow.checked(body, receipt, b"old")
