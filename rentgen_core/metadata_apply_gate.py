"""Read-only candidate qualification; a compiler receipt never authorizes apply."""
from contextlib import contextmanager, ExitStack
from datetime import datetime
from pathlib import Path
import re

from ._windows_source_tree import pinned_directory, read_retained
from .context import SnapshotRef
from .edt_inventory import exported_inventory
from .edt_profiles import authorized, parse_json
from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .metadata_runs import get_preview, run_path as preview_run_path
from .native_platform import CONTEXTS, MAX_LOG
from .platform_check import MAX_FILE, MAX_TOTAL, _pin_inputs
from .platform_runs import get_platform_run, run_path
from .snapshots import validate_operation_id
from .source_paths import validate_file_paths
from .sources import SourceRef

HASH = re.compile(r"[0-9a-f]{64}")
STEPS = (
    "create",
    "baseline-load",
    "baseline-dump",
    "baseline-check",
    "candidate-load",
    "candidate-dump",
    "candidate-check",
)


def _require(condition, message="Invalid metadata qualification evidence"):
    if not condition:
        raise CoreError("METADATA_GATE_INVALID", message)


def _match(condition):
    if not condition:
        raise CoreError(
            "METADATA_GATE_CONFLICT", "Evidence differs from the requested candidate"
        )


def _keys(value, names):
    _require(type(value) is dict and set(value) == set(names))


def _hash(value):
    _require(type(value) is str and HASH.fullmatch(value))


def _schema(value):
    _require(type(value["schema"]) is int and value["schema"] == 1)


def _text(value, maximum):
    _require(type(value) is str and 1 <= len(value) <= maximum)
    _require(not any(ord(c) < 32 for c in value))


@contextmanager
def _guarded(ctx):
    with authorized(ctx) as check:
        try:
            yield check
        except (UnicodeError, RecursionError, OSError) as exc:
            raise CoreError(
                "METADATA_GATE_INVALID", "Retained evidence is unreadable or malformed"
            ) from exc


def _preview(ctx, operation):
    with pinned_directory(preview_run_path(ctx, operation)):
        result = get_preview(ctx, operation)
        closed = parse_json(
            read_retained(
                preview_run_path(ctx, operation) / "runtime-closed.json", 8192
            )
        )
        _keys(closed, {"status", "metadata_verified"})
        _require(closed["status"] == "closed" and closed["metadata_verified"] is False)
        return result


def _inventory(rows):
    _require(type(rows) is list and 1 <= len(rows) <= 8192)
    for row in rows:
        _keys(row, {"path", "size", "sha256"})
        _text(row["path"], 4096)
        _require(type(row["size"]) is int and 0 <= row["size"] <= MAX_FILE)
        _hash(row["sha256"])
    _require(sum(row["size"] for row in rows) <= MAX_TOTAL)
    validate_file_paths(row["path"] for row in rows)
    _require(rows == sorted(rows, key=lambda row: row["path"]))
    return sha256(canonical_bytes(rows))


def _request(saved, preview, operation, expected_exe):
    request = saved["request"]
    _keys(
        request,
        {
            "schema",
            "run_id",
            "project_id",
            "input",
            "requested_by",
            "created_at",
            "execution_policy",
        },
    )
    _schema(request)
    _match(
        request["run_id"] == operation
        and request["project_id"] == preview["project_id"]
    )
    _require(request["execution_policy"] == "native-resources-v1")
    principal = request["requested_by"]
    _keys(principal, {"id", "authority"})
    _text(principal["id"], 512)
    _require(principal["authority"] in ("local_os", "verified_token", "local_service"))
    _text(request["created_at"], 64)
    try:
        _require(datetime.fromisoformat(request["created_at"]).utcoffset() is not None)
    except ValueError as exc:
        raise CoreError("METADATA_GATE_INVALID", "Invalid receipt timestamp") from exc
    binding = request["input"]
    _keys(
        binding,
        {
            "source_ref",
            "proposal_content_id",
            "platform_executable",
            "platform_executable_sha256",
            "profile",
        },
    )
    _require(binding["profile"] == "native-compile-v1")
    for name in ("proposal_content_id", "platform_executable_sha256"):
        _hash(binding[name])
    _match(binding["platform_executable_sha256"] == expected_exe)
    _text(binding["platform_executable"], 4096)
    executable = Path(binding["platform_executable"])
    _require(executable.is_absolute() and executable.name.lower() == "1cv8.exe")
    ref = binding["source_ref"]
    _keys(ref, {"snapshot", "layer_id", "relative_path", "raw_sha256"})
    _keys(ref["snapshot"], {"project_id", "snapshot_id", "manifest_hash"})
    _text(ref["relative_path"], 4096)
    _text(ref["layer_id"], 64)
    _hash(ref["raw_sha256"])
    SourceRef(
        SnapshotRef(**ref["snapshot"]),
        ref["layer_id"],
        ref["relative_path"],
        ref["raw_sha256"],
    )
    _require(ref["relative_path"].lower().endswith(".bsl"))
    _match(
        ref["snapshot"] == preview["preview"]["snapshot"]
        and ref["layer_id"] == preview["preview"]["layer_id"]
    )
    return binding


def _analysis(report, run, inventories, check):
    analysis = report["analysis"]
    _keys(analysis, {"baseline", "candidate", "contexts", "steps"})
    _require(analysis["contexts"] == list(CONTEXTS))
    steps = analysis["steps"]
    _require(type(steps) is list and len(steps) == len(STEPS))
    for step, name in zip(steps, STEPS):
        check()
        _keys(
            step,
            {
                "name",
                "exit_code",
                "log",
                "log_sha256",
                "stdout_sha256",
                "stderr_sha256",
                "elapsed_ms",
            },
        )
        _require(step["name"] == name)
        _require(
            type(step["exit_code"]) is int
            and step["exit_code"] in ({0, 101} if name.endswith("-check") else {0})
        )
        _require(type(step["elapsed_ms"]) is int and 0 <= step["elapsed_ms"] < 2**63)
        _require(
            type(step["log"]) is str and len(step["log"].encode("utf-8")) <= MAX_LOG
        )
        for suffix in ("log", "stdout", "stderr"):
            _hash(step[suffix + "_sha256"])
            raw = read_retained(run / (name + "." + suffix), MAX_LOG)
            _match(sha256(raw) == step[suffix + "_sha256"])
            if suffix == "log":
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = raw.decode("cp1251")
                _match(text == step["log"])
    target = report["source_ref"]["relative_path"]
    for phase, index in (("baseline", 3), ("candidate", 6)):
        result = analysis[phase]
        _keys(result, {"status", "native_module_sha256", "module_text_verified"})
        _require(result["module_text_verified"] is True)
        _hash(result["native_module_sha256"])
        expected_status = (
            "passed" if steps[index]["exit_code"] == 0 else "diagnostics_present"
        )
        _require(result["status"] == expected_status)
        rows = {row["path"]: row for row in inventories[phase]}
        _match(target in rows)
        expected_hash = (
            report["source_ref"]["raw_sha256"]
            if phase == "baseline"
            else report["candidate_sha256"]
        )
        _match(rows[target]["sha256"] == expected_hash)
        expected = read_retained(run / phase / target, 2 * 1024**2)
        native = read_retained(run / (phase + "-roundtrip") / target, 2 * 1024**2)
        _match(sha256(native) == result["native_module_sha256"])
        _match(
            native.decode("utf-8-sig").replace("\r\n", "\n")
            == expected.decode("utf-8-sig").replace("\r\n", "\n")
        )
    return (
        "passed"
        if all(analysis[p]["status"] == "passed" for p in ("baseline", "candidate"))
        else "diagnostics"
    )


def _completed(saved, run, inventories, digests, check):
    report = saved["report"]
    _keys(
        report,
        {
            "schema",
            "run_id",
            "source_ref",
            "proposal_content_id",
            "candidate_sha256",
            "baseline_input_sha256",
            "candidate_input_sha256",
            "platform_executable_sha256",
            "analysis",
            "evidence",
            "runtime_dependencies",
            "tests",
            "apply",
            "report_sha256",
        },
    )
    _schema(report)
    for name in (
        "proposal_content_id",
        "candidate_sha256",
        "baseline_input_sha256",
        "candidate_input_sha256",
        "platform_executable_sha256",
        "report_sha256",
    ):
        _hash(report[name])
    _require(
        report["evidence"] == "local_unattested"
        and report["runtime_dependencies"] == "not_fully_pinned"
    )
    _require(
        report["tests"] == {"status": "not_run"}
        and report["apply"] == {"status": "unavailable"}
    )
    for phase in ("baseline", "candidate"):
        _match(report[phase + "_input_sha256"] == digests[phase])
    with ExitStack() as pins:
        for phase in ("baseline", "candidate"):
            folder = run / phase
            _match(exported_inventory(folder, authorize=check) == inventories[phase])
            pins.enter_context(_pin_inputs(folder, inventories[phase]))
        status = _analysis(report, run, inventories, check)
        for phase in ("baseline", "candidate"):
            _match(
                exported_inventory(run / phase, authorize=check) == inventories[phase]
            )
    return status


def _failure(saved, ctx, operation):
    failure = saved["failure"]
    _keys(failure, {"schema", "run_id", "project_id", "code", "details"})
    _schema(failure)
    _match(failure["run_id"] == operation and failure["project_id"] == ctx.project_id)
    code = failure["code"]
    _require(type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", code))
    details = failure["details"]
    _require(type(details) is dict and "run_id" in details)
    _match(details["run_id"] == operation)
    # Error details are opaque diagnostic data: bounded by the retained reader,
    # hashed for provenance, never copied into a decision or executed.
    return "timeout" if code == "PLATFORM_TIMEOUT" else "failed"


def qualify_candidate(
    ctx,
    preview_operation_id,
    platform_operation_id,
    *,
    expected_preview_id,
    expected_platform_executable_sha256,
):
    """Inspect retained evidence without running a tool or writing live sources."""
    with _guarded(ctx) as check:
        for operation in (preview_operation_id, platform_operation_id):
            _require(type(operation) is str)
            validate_operation_id(operation)
        _hash(expected_preview_id)
        _hash(expected_platform_executable_sha256)
        preview = _preview(ctx, preview_operation_id)
        _match(preview["preview_id"] == expected_preview_id)
        inventories = preview["preview"]["inventories"]
        _keys(inventories, {"original", "baseline", "candidate"})
        digests = {name: _inventory(rows) for name, rows in inventories.items()}
        run = run_path(ctx, platform_operation_id)
        with pinned_directory(run):
            saved = get_platform_run(ctx, platform_operation_id)
            _require(
                not ((run / "report.json").exists() and (run / "failure.json").exists())
            )
            _request(
                saved,
                preview,
                platform_operation_id,
                expected_platform_executable_sha256,
            )
            check()
            if saved["status"] == "completed":
                status = _completed(saved, run, inventories, digests, check)
            elif saved["status"] == "failed":
                status = _failure(saved, ctx, platform_operation_id)
            else:
                _require(saved["status"] == "incomplete")
                status = "incomplete"
            _match(get_platform_run(ctx, platform_operation_id) == saved)
        _match(_preview(ctx, preview_operation_id) == preview)
        check()
        result = {
            "schema": 1,
            "status": status,
            "binding": {
                "project_id": ctx.project_id,
                "preview_operation_id": preview_operation_id,
                "preview_id": preview["preview_id"],
                "plan_id": preview["plan_id"],
                "profile_id": preview["profile_id"],
                "platform_operation_id": platform_operation_id,
                "platform_executable_sha256": expected_platform_executable_sha256,
                "snapshot": preview["preview"]["snapshot"],
                "layer_id": preview["preview"]["layer_id"],
                "original_input_sha256": digests["original"],
                "baseline_input_sha256": digests["baseline"],
                "candidate_input_sha256": digests["candidate"],
            },
            "provenance": {
                "request_sha256": sha256(canonical_bytes(saved["request"])),
                "report_sha256": saved.get("report", {}).get("report_sha256"),
                "failure_sha256": sha256(canonical_bytes(saved["failure"]))
                if "failure" in saved
                else None,
                "evidence": "local_unattested",
                "scope": "native-compile-v1",
                "runtime_dependencies": "not_fully_pinned",
            },
            "live_apply_allowed": False,
            "live_source_written": False,
            "reasons": ["live_apply_not_implemented", "normalization_not_qualified"],
        }
        return {**result, "qualification_id": sha256(canonical_bytes(result))}


def require_live_apply(ctx, *args, **kwargs):
    """Reauthorize and requalify evidence, then unconditionally deny live write."""
    qualify_candidate(ctx, *args, **kwargs)
    raise CoreError(
        "METADATA_LIVE_APPLY_UNAVAILABLE",
        "Candidate qualification has no live write or recovery capability",
    )
