"""Authorized native-check records; atomic files, no claim of OS power-loss durability."""
from contextlib import contextmanager
import json
import os
import time

from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .snapshots import validate_operation_id


PERMISSIONS = frozenset({"project:read", "source:edit", "analysis:run"})


def _authorize(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(PERMISSIONS)


@contextmanager
def _authorized(ctx):
    _authorize(ctx)
    try:
        yield
    finally:
        try:
            _authorize(ctx)
        except BaseException as exc:
            raise exc from None


def run_path(ctx, operation_id, *, namespace="platform-checks"):
    if namespace not in {"platform-checks", "test-runs"}:
        raise ValueError("Unknown native run namespace")
    return ctx.state.path.parent / namespace / validate_operation_id(operation_id)


def write_record(ctx, run, name, value):
    from ._windows_source_tree import pinned_directory

    if name not in {"request", "report", "failure"}:
        raise ValueError("Unsupported native record")
    encoded = canonical_bytes(value)
    if len(encoded) > 1536 * 1024:
        raise CoreError("PLATFORM_OUTPUT_LIMIT", "Native record exceeds 1.5 MiB")
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(PERMISSIONS)
        temporary = run / (name + ".tmp")
        with pinned_directory(run):
            with temporary.open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        # A reader's no-delete directory pins may briefly deny rename on Windows.
        # Release our own run pin, then wait only for sharing violations. Never
        # overwrite an existing record or retry other filesystem errors.
        deadline = time.monotonic() + 5
        while True:
            try:
                temporary.rename(run / (name + ".json"))
                break
            except OSError as exc:
                if getattr(exc, "winerror", None) not in {32, 33}:
                    raise
                if time.monotonic() >= deadline:
                    raise CoreError(
                        "PLATFORM_RUN_BUSY",
                        "Native record publication blocked by a reader",
                    ) from exc
                time.sleep(0.02)


def _corrupt():
    return CoreError("PLATFORM_RUN_CORRUPT", "Native run record is invalid")


def _read(path):
    from ._windows_source_tree import read_retained

    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise _corrupt()
            result[key] = value
        return result

    try:
        result = json.loads(
            read_retained(path, 1536 * 1024).decode("utf-8"), object_pairs_hook=unique
        )
        if type(result) is not dict:
            raise _corrupt()
        canonical_bytes(result)
        return result
    except (UnicodeError, ValueError, TypeError, CoreError) as exc:
        raise _corrupt() from exc


def _get(ctx, operation_id, *, namespace="platform-checks"):
    from ._windows_source_tree import pinned_directory

    run = run_path(ctx, operation_id, namespace=namespace)
    if not run.exists():
        raise CoreError("PLATFORM_RUN_NOT_FOUND", "Native run does not exist")
    with pinned_directory(run):
        request = (
            _read(run / "request.json") if (run / "request.json").exists() else None
        )
        if request is not None and (
            request.get("schema") != 1
            or request.get("run_id") != operation_id
            or request.get("project_id") != ctx.project_id
            or type(request.get("input")) is not dict
        ):
            raise _corrupt()
        result = {"run_id": operation_id, "request": request}
        if (run / "report.json").exists():
            report = _read(run / "report.json")
            claimed = report.get("report_sha256")
            unsigned = {k: v for k, v in report.items() if k != "report_sha256"}
            try:
                valid = (
                    report["schema"] == 1
                    and report["run_id"] == operation_id
                    and report["source_ref"]["snapshot"]["project_id"] == ctx.project_id
                    and claimed == sha256(canonical_bytes(unsigned))
                )
                if request is not None:
                    binding = request["input"]
                    valid = valid and all(
                        report[key] == binding[key]
                        for key in (
                            "source_ref",
                            "proposal_content_id",
                            "platform_executable_sha256",
                        )
                    )
                    if namespace == "test-runs":
                        valid = valid and report["profile_id"] == binding["profile_id"]
            except (KeyError, TypeError):
                valid = False
            if not valid:
                raise _corrupt()
            return {**result, "status": "completed", "report": report}
        if (run / "failure.json").exists():
            failure = _read(run / "failure.json")
            if (
                request is None
                or failure.get("run_id") != operation_id
                or failure.get("project_id") != ctx.project_id
                or not isinstance(failure.get("code"), str)
            ):
                raise _corrupt()
            return {**result, "status": "failed", "failure": failure}
        # This means no terminal record. It does NOT assert whether a process lives.
        return {**result, "status": "incomplete"}


def get_platform_run(ctx, operation_id, *, namespace="platform-checks"):
    """Read a run without opening its snapshot, proposal, EXE or source directory."""
    with _authorized(ctx):
        return _get(ctx, operation_id, namespace=namespace)


def replay_run(ctx, operation_id, binding, *, namespace="platform-checks"):
    saved = get_platform_run(ctx, operation_id, namespace=namespace)
    if saved["request"] is None or saved["request"]["input"] != binding:
        raise CoreError(
            "PLATFORM_RUN_CONFLICT",
            "Operation ID belongs to different inputs",
            details={"run_id": operation_id},
        )
    if saved["status"] == "completed":
        return saved["report"]
    raise CoreError(
        "PLATFORM_RUN_INCOMPLETE",
        "Read run status; use a new ID for a new check",
        details={"run_id": operation_id, "status": saved["status"]},
    )
