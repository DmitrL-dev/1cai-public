"""Native compilation of a pinned proposal in an owned, separate infobase."""
from contextlib import contextmanager, ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from uuid import uuid4

from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .metadata_xml import parse_xml
from .native_platform import NativePlatform
from .platform_runs import (
    PERMISSIONS,
    _authorize,
    _authorized,
    replay_run,
    run_path,
    write_record,
)
from .proposals import parse_proposal
from .sources import SnapshotReadLimits


MAX_TOTAL = 256 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024


def _boundary(name):
    """Fault injection for local contract tests; never a transport option."""


@contextmanager
def _run_attempt(ctx, run, binding):
    from .native_resources import execution_resources

    write_record(
        ctx,
        run,
        "request",
        {
            "schema": 1,
            "run_id": run.name,
            "project_id": ctx.project_id,
            "input": binding,
            "requested_by": asdict(ctx.principal),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "execution_policy": "native-resources-v1",
        },
    )
    try:
        _boundary("request_published")
        with execution_resources(ctx, run) as resources:
            yield resources
    except (CoreError, KeyboardInterrupt) as exc:
        _authorize(ctx)
        code = exc.code if isinstance(exc, CoreError) else "PLATFORM_INTERRUPTED"
        details = {
            **(exc.details if isinstance(exc, CoreError) else {}),
            "run_id": run.name,
        }
        if not (run / "report.json").exists():
            write_record(
                ctx,
                run,
                "failure",
                {
                    "schema": 1,
                    "run_id": run.name,
                    "project_id": ctx.project_id,
                    "code": code,
                    "details": details,
                },
            )
        raise CoreError(
            code,
            str(exc)
            if isinstance(exc, CoreError)
            else "Native check interrupted; query its operation ID",
            details=details,
        ) from exc


@contextmanager
def _pin_inputs(folder, inventory):
    """Bounded known-file pins without retaining another full copy in memory."""
    from ._windows_source_tree import (
        WindowsHandleOps,
        pinned_directory,
        _retained_stamp,
        _close_all,
    )

    ops, handles, directories, stamps = WindowsHandleOps(), [], set(), []
    try:
        with pinned_directory(folder):
            for item in inventory:
                path = folder / item["path"]
                for directory in reversed(path.parent.relative_to(folder).parents):
                    # Parents of a relative path include '.', handled below.
                    actual = folder / directory
                    if actual != folder and actual not in directories:
                        handle = ops.open(actual, directory=True)
                        handles.append(handle)
                        if (
                            not ops.stamp(handle).directory
                            or ops.final_path(handle) != actual
                        ):
                            raise CoreError(
                                "PLATFORM_INPUT_CHANGED", "Invalid input directory"
                            )
                        directories.add(actual)
                if path.parent != folder and path.parent not in directories:
                    handle = ops.open(path.parent, directory=True)
                    handles.append(handle)
                    if (
                        not ops.stamp(handle).directory
                        or ops.final_path(handle) != path.parent
                    ):
                        raise CoreError(
                            "PLATFORM_INPUT_CHANGED", "Invalid input directory"
                        )
                    directories.add(path.parent)
                handle = ops.open(path, directory=False)
                handles.append(handle)
                stamp = _retained_stamp(ops, handle)
                if (
                    stamp.directory
                    or ops.final_path(handle) != path
                    or stamp.size != item["size"]
                ):
                    raise CoreError(
                        "PLATFORM_INPUT_CHANGED", "Input identity or size changed"
                    )
                digest = hashlib.sha256()
                for chunk in ops.chunks(handle):
                    digest.update(chunk)
                if digest.hexdigest() != item["sha256"]:
                    raise CoreError("PLATFORM_INPUT_CHANGED", "Input bytes changed")
                stamps.append((handle, stamp))
            yield
            if any(_retained_stamp(ops, handle) != stamp for handle, stamp in stamps):
                raise CoreError(
                    "PLATFORM_INPUT_CHANGED", "Input changed during compilation"
                )
    finally:
        _close_all(ops, handles)


def _materialize(ctx, proposal, before, after):
    inventories = ([], [])
    with ctx.sources.read_session(limits=SnapshotReadLimits()) as session:
        entries = session.entries()
        if (
            len(entries) > 20000
            or sum(e.size_bytes for e in entries) > MAX_TOTAL
            or any(e.size_bytes > MAX_FILE for e in entries)
        ):
            raise CoreError(
                "PLATFORM_SOURCE_LIMIT", "Native source materialization exceeds limits"
            )
        if not any(e.ref.relative_path == "Configuration.xml" for e in entries):
            raise CoreError(
                "PLATFORM_SOURCE_UNSUPPORTED", "Native Configuration.xml is required"
            )
        found = False
        for entry in entries:
            _authorize(ctx)
            raw = session.read_source(entry.ref)
            if entry.ref.relative_path.lower().endswith(".xml"):
                parse_xml(raw)
            changed = entry.ref == proposal.source_ref
            found = found or changed
            for folder, inventory, value in (
                (before, inventories[0], raw),
                (after, inventories[1], proposal.replacement_bytes if changed else raw),
            ):
                path = folder / entry.ref.relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(value)
                inventory.append(
                    {
                        "path": entry.ref.relative_path,
                        "size": len(value),
                        "sha256": sha256(value),
                    }
                )
        if not found:
            raise CoreError(
                "SOURCE_REF_MISMATCH", "Proposal module missing from snapshot"
            )
    return tuple(sorted(items, key=lambda i: i["path"]) for items in inventories)


def check_proposal_platform_json(ctx, raw_json, platform, *, limits, operation_id=None):
    """Trusted local entry; CLI authenticates before opening proposal/executable paths."""
    from ._windows_source_tree import pinned_directory, pinned_retained

    with _authorized(ctx):
        if type(platform) is not NativePlatform:
            raise CoreError(
                "PLATFORM_PROFILE_INVALID", "Trusted native profile required"
            )
        proposal = parse_proposal(
            ctx, raw_json, limits=limits, authorize=lambda: _authorize(ctx)
        )
        if not proposal.source_ref.relative_path.lower().endswith(".bsl"):
            raise CoreError(
                "PLATFORM_SOURCE_UNSUPPORTED", "1C compilation requires BSL"
            )
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all(PERMISSIONS)
            layers = tx.get_snapshot_layers(ctx.snapshot.snapshot_id)
        if (
            len(layers) != 1
            or layers[0].kind != "base"
            or layers[0].source_format != "designer_xml"
            or layers[0].layer_id != proposal.source_ref.layer_id
        ):
            raise CoreError(
                "PLATFORM_SOURCE_UNSUPPORTED",
                "One captured Designer XML base layer required",
            )
        executable = platform.executable.absolute()
        run_id = str(uuid4()) if operation_id is None else operation_id
        run = run_path(ctx, run_id)
        binding = {
            "source_ref": asdict(proposal.source_ref),
            "proposal_content_id": proposal.content_id,
            "platform_executable": str(executable),
            "platform_executable_sha256": platform.executable_sha256,
            "profile": "native-compile-v1",
        }
        if run.exists():
            return replay_run(ctx, run_id, binding)
        with pinned_retained(executable, MAX_FILE) as raw:
            if sha256(raw) != platform.executable_sha256:
                raise CoreError(
                    "PLATFORM_BINARY_MISMATCH", "Native executable SHA256 mismatch"
                )
            # Keep the actual pinned locator, without resolving away reparse checks.
            platform = NativePlatform(executable, platform.executable_sha256)
            parent = ctx.state.path.parent / "platform-checks"
            if any(c in str(parent) for c in (";", '"', "\r", "\n")):
                raise CoreError(
                    "PLATFORM_WORKSPACE_INVALID", "Unsupported connection path"
                )
            parent.mkdir(exist_ok=True)
            with pinned_directory(parent), ExitStack() as records:
                try:
                    run.mkdir()
                except FileExistsError:
                    return replay_run(ctx, run_id, binding)
                resources = records.enter_context(_run_attempt(ctx, run, binding))
                platform = NativePlatform(
                    executable, platform.executable_sha256, resources.job
                )
                before, after = run / "baseline", run / "candidate"
                before.mkdir()
                after.mkdir()
                inventories = _materialize(ctx, proposal, before, after)
                _authorize(ctx)
                with ExitStack() as pins:
                    pins.enter_context(_pin_inputs(before, inventories[0]))
                    pins.enter_context(_pin_inputs(after, inventories[1]))
                    analysis = platform.check(
                        before,
                        after,
                        proposal.source_ref.relative_path,
                        run,
                        resources.check,
                    )
                resources.finished()
                result = {
                    "schema": 1,
                    "run_id": run_id,
                    "source_ref": asdict(proposal.source_ref),
                    "proposal_content_id": proposal.content_id,
                    "candidate_sha256": sha256(proposal.replacement_bytes),
                    "baseline_input_sha256": sha256(canonical_bytes(inventories[0])),
                    "candidate_input_sha256": sha256(canonical_bytes(inventories[1])),
                    "platform_executable_sha256": platform.executable_sha256,
                    "analysis": analysis,
                    "evidence": "local_unattested",
                    "runtime_dependencies": "not_fully_pinned",
                    "tests": {"status": "not_run"},
                    "apply": {"status": "unavailable"},
                }
                result["report_sha256"] = sha256(canonical_bytes(result))
                write_record(ctx, run, "report", result)
                _boundary("report_published")
                return result
