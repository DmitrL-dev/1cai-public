"""Native compilation of a pinned proposal in an owned, separate infobase."""
from contextlib import contextmanager, ExitStack
from dataclasses import asdict
import hashlib
import json
from uuid import uuid4

from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .metadata_xml import parse_xml
from .native_platform import NativePlatform
from .proposals import parse_proposal
from .sources import SnapshotReadLimits


PERMISSIONS = frozenset({"project:read", "source:edit", "analysis:run"})
MAX_TOTAL = 256 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024


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


def check_proposal_platform_json(ctx, raw_json, platform, *, limits):
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
            with pinned_directory(parent):
                run_id = str(uuid4())
                run = parent / run_id
                run.mkdir()
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
                        lambda: _authorize(ctx),
                    )
                _authorize(ctx)
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
                encoded = json.dumps(
                    result, ensure_ascii=False, allow_nan=False
                ).encode("utf-8")
                if len(encoded) > 1536 * 1024:
                    raise CoreError(
                        "PLATFORM_OUTPUT_LIMIT", "Native result exceeds 1.5 MiB"
                    )
                with ctx.state.transaction(ctx.principal) as tx:
                    tx.require_all(PERMISSIONS)
                    with (run / "report.json").open("xb") as stream:
                        stream.write(encoded)
                return result
