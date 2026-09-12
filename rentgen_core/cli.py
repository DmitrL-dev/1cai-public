"""Local Windows CLI. Console entry point: rentgen_core.cli:main.

Normal stdout is one JSON envelope; --help is human-readable. Identity is never
a command argument. This adapter is not suitable for serving remote requests.
"""
import argparse
from dataclasses import asdict, dataclass, is_dataclass, replace
import base64
import json
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

from .errors import CoreError
from .local import LocalRuntime
from .local_identity import current_windows_principal
from .registry import ProjectRegistry, ProjectSummary
from .source_configuration import SourceLayerSpec, configure_source_layers
from .context import Principal, SnapshotRef
from .publication import capture_and_publish
from .resolver import require_snapshot
from .snapshots import ProjectHead, validate_operation_id
from .sources import SourceRef

_MAX_JSON_BYTES = 1024 * 1024


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CoreError("INVALID_ARGUMENT", message)


class _Once(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        seen = getattr(namespace, "_provided_once", None)
        if seen is None:
            seen = set()
            setattr(namespace, "_provided_once", seen)
        if self.dest in seen:
            raise CoreError("INVALID_ARGUMENT", "Repeated option: " + option_string)
        seen.add(self.dest)
        setattr(namespace, self.dest, values)


def _parser():
    parser = _Parser(
        prog="rentgen", description="Explicit local project snapshots (Windows)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "registry-init",
        "project-register",
        "project-list",
        "project-head",
        "layers-get",
        "layers-set",
        "publication-receipt",
        "state-migrate",
        "state-upgrade-access",
        "state-upgrade-workflows",
        "membership-list",
        "membership-set",
        "membership-revoke",
        "membership-receipt",
        "capture",
        "source-list",
        "snapshot-diff",
        "source-read",
        "graph-resolve",
        "impact",
        "proposal-create",
        "proposal-diff",
        "proposal-check",
        "proposal-platform-check",
        "proposal-platform-result",
        "test-profile-register",
        "test-profile-list",
        "test-profile-disable",
        "edt-profile-register",
        "edt-profile-list",
        "edt-profile-disable",
        "metadata-plan",
        "metadata-preview",
        "metadata-result",
        "metadata-evidence",
        "metadata-workspace-create",
        "metadata-workspace-apply",
        "metadata-workspace-undo",
        "metadata-workspace-status",
        "proposal-test",
        "proposal-test-result",
        "draft-save",
        "draft-get",
        "draft-list",
        "draft-history",
        "draft-archive",
        "draft-restore",
        "draft-receipt",
    ):
        command = commands.add_parser(name, allow_abbrev=False)
        command.add_argument("--registry", required=True, type=Path, action=_Once)
        if name not in ("registry-init", "project-register", "project-list"):
            command.add_argument("--project", required=True, action=_Once)
        if name.startswith("metadata-"):
            command.add_argument("--snapshot", required=True, action=_Once)
            if name == "metadata-plan":
                command.add_argument(
                    "--request-json", type=Path, required=True, action=_Once
                )
            if name == "metadata-preview":
                command.add_argument(
                    "--plan-json", type=Path, required=True, action=_Once
                )
                command.add_argument("--profile-id", required=True, action=_Once)
            if name in {
                "metadata-preview",
                "metadata-result",
                "metadata-evidence",
                "metadata-workspace-create",
                "metadata-workspace-apply",
                "metadata-workspace-undo",
                "metadata-workspace-status",
            }:
                command.add_argument("--operation-id", required=True, action=_Once)
            if name == "metadata-evidence":
                command.add_argument(
                    "--evidence-json", type=Path, required=True, action=_Once
                )
            if name.startswith("metadata-workspace-"):
                command.add_argument(
                    "--workspace", type=Path, required=True, action=_Once
                )
        elif name == "project-register":
            for option in ("source-root", "state-root"):
                command.add_argument(
                    "--" + option, type=Path, required=True, action=_Once
                )
            command.add_argument("--name", required=True, action=_Once)
        elif name == "layers-set":
            command.add_argument(
                "--expected-revision", type=int, required=True, action=_Once
            )
            command.add_argument(
                "--layers-json", type=Path, required=True, action=_Once
            )
        elif name == "publication-receipt":
            command.add_argument("--operation-id", required=True, action=_Once)
        elif name in {"proposal-platform-result", "proposal-test-result"}:
            command.add_argument("--operation-id", required=True, action=_Once)
        elif name in {"test-profile-register", "edt-profile-register"}:
            command.add_argument(
                "--profile-json", type=Path, required=True, action=_Once
            )
        elif name in {"test-profile-disable", "edt-profile-disable"}:
            command.add_argument("--profile-id", required=True, action=_Once)
        elif name in {
            "state-migrate",
            "state-upgrade-access",
            "state-upgrade-workflows",
        }:
            command.add_argument(
                "--backup-directory", type=Path, required=True, action=_Once
            )
            command.add_argument(
                "--operation-id", required=name != "state-migrate", action=_Once
            )
        elif name == "membership-list":
            command.add_argument("--limit", type=int, action=_Once)
            command.add_argument("--after-principal-json", type=Path, action=_Once)
        elif name == "membership-receipt":
            command.add_argument("--operation-id", required=True, action=_Once)
        elif name in {"membership-set", "membership-revoke"}:
            command.add_argument(
                "--principal-json", type=Path, required=True, action=_Once
            )
            command.add_argument("--operation-id", required=True, action=_Once)
            command.add_argument(
                "--expected-revision", type=int, required=True, action=_Once
            )
            if name == "membership-set":
                command.add_argument(
                    "--permissions-json", type=Path, required=True, action=_Once
                )
        elif name == "capture":
            command.add_argument("--scanner", type=Path, action=_Once)
            command.add_argument("--operation-id", action=_Once)
            command.add_argument("--expected-head-json", type=Path, action=_Once)
        if name.startswith("draft-"):
            if name not in {"draft-list", "draft-receipt"}:
                command.add_argument("--draft-id", required=True, action=_Once)
            if name in {
                "draft-save",
                "draft-archive",
                "draft-restore",
                "draft-receipt",
            }:
                command.add_argument("--operation-id", required=True, action=_Once)
            if name in {"draft-save", "draft-archive", "draft-restore"}:
                command.add_argument(
                    "--expected-revision", type=int, required=True, action=_Once
                )
            if name == "draft-save":
                command.add_argument("--snapshot", required=True, action=_Once)
                command.add_argument(
                    "--proposal-json", type=Path, required=True, action=_Once
                )
                command.add_argument("--title", required=True, action=_Once)
            if name == "draft-get":
                command.add_argument("--revision", type=int, action=_Once)
            if name in {"draft-list", "draft-history"}:
                command.add_argument("--limit", type=int, default=20, action=_Once)
            if name == "draft-list":
                command.add_argument("--after-draft-id", action=_Once)
                command.add_argument(
                    "--status",
                    choices=("active", "archived"),
                    default="active",
                    action=_Once,
                )
            if name == "draft-history":
                command.add_argument("--before-revision", type=int, action=_Once)
        if name in {
            "proposal-create",
            "proposal-diff",
            "proposal-check",
            "proposal-platform-check",
            "proposal-test",
        }:
            command.add_argument("--snapshot", required=True, action=_Once)
            if name == "proposal-create":
                command.add_argument(
                    "--source-ref-json", type=Path, required=True, action=_Once
                )
                command.add_argument(
                    "--replacement-file", type=Path, required=True, action=_Once
                )
            else:
                command.add_argument(
                    "--proposal-json", type=Path, required=True, action=_Once
                )
            if name == "proposal-check":
                command.add_argument(
                    "--diagnostics-profile", required=True, action=_Once
                )
            if name == "proposal-platform-check":
                command.add_argument("--operation-id", action=_Once)
                command.add_argument(
                    "--platform", type=Path, required=True, action=_Once
                )
                command.add_argument("--platform-sha256", required=True, action=_Once)
            if name == "proposal-test":
                command.add_argument("--operation-id", required=True, action=_Once)
                command.add_argument("--test-profile", required=True, action=_Once)
        if name == "snapshot-diff":
            command.add_argument("--before", required=True, action=_Once)
            command.add_argument("--after", required=True, action=_Once)
            command.add_argument("--limit", type=int, default=100, action=_Once)
            command.add_argument("--cursor", action=_Once)
        if name in {"source-list", "source-read", "graph-resolve", "impact"}:
            command.add_argument("--snapshot", action=_Once)
            if name == "source-list":
                command.add_argument("--limit", type=int, action=_Once)
                command.add_argument("--cursor", action=_Once)
                command.add_argument("--query", action=_Once)
                command.add_argument("--kind", choices=("all", "module"), action=_Once)
                command.add_argument("--layer", action=_Once)
            else:
                command.add_argument("--source-ref-json", type=Path, action=_Once)
                command.add_argument("--layer", action=_Once)
                command.add_argument("--path", action=_Once)
                if name == "source-read":
                    output = command.add_mutually_exclusive_group(required=True)
                    output.add_argument("--base64", action="store_true")
                    output.add_argument("--output", type=Path, action=_Once)
                if name == "impact":
                    command.add_argument("--depth", type=int, action=_Once)
    return parser


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


def _json_file(path):
    with Path(path).open("rb") as source:
        raw = source.read(_MAX_JSON_BYTES + 1)
    if len(raw) > _MAX_JSON_BYTES:
        raise CoreError("INVALID_ARGUMENT", "JSON input exceeds 1 MiB")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CoreError(
            "INVALID_ARGUMENT", "Expected bounded UTF-8 JSON without duplicate keys"
        ) from exc


def _fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise CoreError(
            "INVALID_ARGUMENT", "JSON fields do not match the command schema"
        )
    return value


def _runtime(args):
    return LocalRuntime(args.registry)


def _snapshot_ref(value):
    return SnapshotRef(**_fields(value, ("project_id", "snapshot_id", "manifest_hash")))


def _expected_head(path):
    value = _json_file(path)
    # A raw ProjectHead or the exact successful project-head command envelope.
    if isinstance(value, dict) and set(value) == {"result", "request_id"}:
        value = value["result"]
    value = dict(
        _fields(value, ("project_id", "revision", "snapshot", "source_revision"))
    )
    if value["snapshot"] is not None:
        value["snapshot"] = _snapshot_ref(value["snapshot"])
    return ProjectHead(**value)


def _graph_factory():
    try:
        from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory
    except ImportError as exc:
        raise CoreError(
            "GRAPH_ADAPTER_UNAVAILABLE", "Install the supported rentgen_graph package"
        ) from exc
    return RentgenGraphReaderFactory()


class _InstalledBuilder:
    """Lazy only to allow committed receipt replay without the former scanner."""

    def __init__(self, scanner):
        self.scanner = scanner

    def build(self, captured, *, output_path, work_dir):
        if self.scanner is None:
            raise CoreError(
                "GRAPH_ADAPTER_UNAVAILABLE",
                "Capture requires an explicit --scanner executable",
            )
        try:
            from rentgen_graph.snapshot_adapter import RentgenCapturedGoBuilder
        except ImportError as exc:
            raise CoreError(
                "GRAPH_ADAPTER_UNAVAILABLE",
                "Install the supported rentgen_graph package",
            ) from exc
        return RentgenCapturedGoBuilder(self.scanner).build(
            captured, output_path=output_path, work_dir=work_dir
        )


def _capture(args, runtime, ctx):
    replay = args.operation_id is not None
    if replay != (args.expected_head_json is not None):
        raise CoreError(
            "INVALID_ARGUMENT",
            "Replay requires both --operation-id and the original --expected-head-json",
        )
    if replay:
        operation_id = validate_operation_id(args.operation_id)
        head = _expected_head(args.expected_head_json)
    else:
        if runtime.graph_builder is None and args.scanner is None:
            raise CoreError(
                "GRAPH_ADAPTER_UNAVAILABLE",
                "Initial capture requires an explicit --scanner executable",
            )
        operation_id = str(uuid4())
        with ctx.state.transaction(ctx.principal) as tx:
            head = tx.get_project_head()
    if head.project_id != ctx.project_id:
        raise CoreError("HEAD_CONFLICT", "Expected head belongs to another project")
    _emit(
        {"recovery": {"operation_id": operation_id, "expected_head": head}},
        stream=sys.stderr,
    )
    builder = runtime.graph_builder or _InstalledBuilder(args.scanner)
    return capture_and_publish(
        ctx, expected_head=head, builder=builder, operation_id=operation_id
    )


def _snapshot_command(args, runtime, principal):
    ref, snapshot_id = None, args.snapshot
    if args.command == "source-list":
        from .source_catalog import source_query

        filters = source_query(
            query=args.query or "", kind=args.kind or "all", layer=args.layer
        )
    if args.command != "source-list":
        if args.source_ref_json is not None:
            if args.layer is not None or args.path is not None:
                raise CoreError(
                    "INVALID_ARGUMENT", "Choose a SourceRef or a layer/path pair"
                )
            value = dict(
                _fields(
                    _json_file(args.source_ref_json),
                    ("snapshot", "layer_id", "relative_path", "raw_sha256"),
                )
            )
            value["snapshot"] = _snapshot_ref(value["snapshot"])
            ref = SourceRef(**value)
            if ref.snapshot.project_id != args.project or (
                snapshot_id is not None and snapshot_id != ref.snapshot.snapshot_id
            ):
                raise CoreError(
                    "SOURCE_REF_MISMATCH",
                    "SourceRef does not match the selected project/snapshot",
                )
            snapshot_id = ref.snapshot.snapshot_id
        elif args.layer is None or args.path is None:
            raise CoreError(
                "INVALID_ARGUMENT",
                "Provide --source-ref-json or both --layer and --path",
            )
    runtime = replace(
        runtime, graph_reader_factory=runtime.graph_reader_factory or _graph_factory()
    )
    ctx = runtime.resolve(principal, args.project, snapshot_id)
    require_snapshot(ctx)
    if args.command == "source-list":
        return ctx.sources.list_entries(
            limit=100 if args.limit is None else args.limit,
            cursor=args.cursor,
            **filters,
        )
    if ref is None:
        ref = ctx.sources.resolve(args.layer, args.path)
    if args.command == "graph-resolve":
        return ctx.graph.resolve_module(ref)
    if args.command == "impact":
        return ctx.graph.impact(ref, depth=1 if args.depth is None else args.depth)
    raw = ctx.sources.read_source(ref)
    result = {"ref": ref, "raw_sha256": ref.raw_sha256, "size_bytes": len(raw)}
    if args.base64:
        return {
            **result,
            "encoding": "base64",
            "data": base64.b64encode(raw).decode("ascii"),
        }
    # Explicit local output, after authorization and complete verified source read.
    # Exclusive creation never overwrites an existing file, including a symlink.
    with args.output.open("xb") as output:
        output.write(raw)
    return {**result, "output": str(args.output.absolute())}


@dataclass
class _ProposalScope:
    context: object = None
    permissions: frozenset = frozenset({"project:read", "source:edit"})


@dataclass(frozen=True)
class _ProposalCommandResult:
    value: dict
    context: object
    permissions: frozenset = frozenset({"project:read", "source:edit"})


def _proposal_permissions(ctx, permissions=frozenset({"project:read", "source:edit"})):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(permissions)


def _installed_diagnostic_provider():
    try:
        from rentgen_diagnostics.installed import InstalledDiagnostics
    except ImportError as exc:
        raise CoreError(
            "DIAGNOSTIC_RUNTIME_UNAVAILABLE",
            "Install the supported diagnostics adapter",
        ) from exc
    return InstalledDiagnostics()


def _proposal_input(
    ctx, path, limit, *, permissions=frozenset({"project:read", "source:edit"})
):
    _proposal_permissions(ctx, permissions)
    with Path(path).open("rb") as source:
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise CoreError("INVALID_ARGUMENT", "Proposal input exceeds its byte limit")
    return raw


def _proposal_command(args, runtime, state_ctx):
    # CLI paths are explicit local inputs, never accepted by an MCP tool. No
    # payload, generation or adapter is opened before current editing rights.
    permissions = frozenset({"project:read", "source:edit"})
    if args.command in {"proposal-check", "proposal-platform-check", "proposal-test"}:
        permissions = permissions | {"analysis:run"}
    try:
        _proposal_permissions(state_ctx, permissions)
        selected = SnapshotRef(args.project, args.snapshot, args.snapshot)
        ref = None
        if args.command == "proposal-create":
            _proposal_permissions(state_ctx, permissions)
            value = dict(
                _fields(
                    _json_file(args.source_ref_json),
                    ("snapshot", "layer_id", "relative_path", "raw_sha256"),
                )
            )
            value["snapshot"] = _snapshot_ref(value["snapshot"])
            ref = SourceRef(**value)
            if ref.snapshot != selected:
                raise CoreError(
                    "SOURCE_REF_MISMATCH",
                    "SourceRef does not match selected project/snapshot",
                )
        _proposal_permissions(state_ctx, permissions)
        runtime = replace(
            runtime,
            graph_reader_factory=runtime.graph_reader_factory or _graph_factory(),
        )
        ctx = runtime.resolve(state_ctx.principal, args.project, args.snapshot)
        from .proposals import (
            ProposalLimits,
            create_proposal_presentation,
            parse_proposal_presentation,
        )

        limits = ProposalLimits(1048576, 1048576, 1572864, 262144)
        if args.command == "proposal-test":
            from .test_execution import check_proposal_tests

            raw = _proposal_input(
                state_ctx,
                args.proposal_json,
                limits.max_canonical_bytes,
                permissions=permissions,
            )
            result = check_proposal_tests(
                ctx, raw, args.test_profile, args.operation_id, limits=limits
            )
            return _ProposalCommandResult(result, state_ctx, permissions)
        if args.command == "proposal-platform-check":
            from .native_platform import NativePlatform
            from .platform_check import check_proposal_platform_json

            raw = _proposal_input(
                state_ctx,
                args.proposal_json,
                limits.max_canonical_bytes,
                permissions=permissions,
            )
            _proposal_permissions(state_ctx, permissions)
            result = check_proposal_platform_json(
                ctx,
                raw,
                NativePlatform(args.platform, args.platform_sha256),
                limits=limits,
                operation_id=args.operation_id,
            )
            return _ProposalCommandResult(result, state_ctx, permissions)
        if args.command == "proposal-check":
            from .diagnostics import diagnose_proposal_json

            raw = _proposal_input(
                state_ctx,
                args.proposal_json,
                limits.max_canonical_bytes,
                permissions=permissions,
            )
            _proposal_permissions(state_ctx, permissions)
            provider = runtime.diagnostic_provider or _installed_diagnostic_provider()
            adapter = provider.for_profile(args.diagnostics_profile)
            diagnostic = diagnose_proposal_json(ctx, raw, adapter, limits=limits)
            _proposal_permissions(state_ctx, permissions)
            return _ProposalCommandResult(
                {
                    "diagnostic": asdict(diagnostic),
                    "tests": {"status": "not_run"},
                    "apply": {"status": "unavailable"},
                },
                state_ctx,
                permissions,
            )
        if ref is not None:
            raw = _proposal_input(
                state_ctx, args.replacement_file, limits.max_replacement_bytes
            )
            presentation = create_proposal_presentation(ctx, ref, raw, limits=limits)
        else:
            raw = _proposal_input(
                state_ctx, args.proposal_json, limits.max_canonical_bytes
            )
            presentation = parse_proposal_presentation(ctx, raw, limits=limits)
        result = {
            "proposal": json.loads(presentation.canonical_json.decode("utf-8")),
            "diff": asdict(presentation.diff),
            "tests": {"status": "not_run"},
            "apply": {"status": "unavailable"},
        }
        _proposal_permissions(state_ctx, permissions)
        return _ProposalCommandResult(result, state_ctx, permissions)
    except BaseException:
        # A revoked request must not release a stale source-related error/log.
        _proposal_permissions(state_ctx, permissions)
        raise


def _execute(args, *, proposal_scope=None):
    principal = current_windows_principal()
    if args.command == "registry-init":
        ProjectRegistry.create(args.registry)
        return {"created": True}
    runtime = _runtime(args)
    if args.command == "project-register":
        project = runtime.registry.register(
            principal,
            source_root=args.source_root,
            state_root=args.state_root,
            display_name=args.name,
        )
        return ProjectSummary(project.project_id, project.display_name)
    if args.command == "project-list":
        return runtime.registry.list_for(principal)
    if args.command == "project-head":
        return runtime.head(principal, args.project)
    permissions = (
        {"project:admin"}
        if args.command
        in {
            "layers-set",
            "state-migrate",
            "state-upgrade-access",
            "state-upgrade-workflows",
            "membership-list",
            "membership-set",
            "membership-revoke",
            "membership-receipt",
            "test-profile-register",
            "test-profile-disable",
            "edt-profile-register",
            "edt-profile-disable",
        }
        else {"project:read", "source:edit", "analysis:run"}
        if args.command
        in {
            "proposal-check",
            "proposal-platform-check",
            "proposal-platform-result",
            "proposal-test",
            "proposal-test-result",
            "test-profile-list",
            "edt-profile-list",
            "metadata-plan",
            "metadata-preview",
            "metadata-result",
            "metadata-evidence",
            "metadata-workspace-create",
            "metadata-workspace-apply",
            "metadata-workspace-undo",
            "metadata-workspace-status",
        }
        else {"project:read", "source:edit"}
        if args.command
        in {
            "proposal-create",
            "proposal-diff",
            "draft-save",
            "draft-archive",
            "draft-restore",
        }
        else {"project:read"}
        if args.command.startswith("draft-") or args.command == "snapshot-diff"
        else {"analysis:run"}
        if args.command == "capture"
        else set()
    )
    ctx = runtime.state_context(principal, args.project, permissions=permissions)
    if args.command.startswith("metadata-"):
        import asyncio
        from .edt_profiles import parse_json
        from .metadata_plans import create_plan
        from .metadata_runs import attach_business_evidence, create_preview, get_preview
        from . import metadata_workspace

        if proposal_scope is not None:
            proposal_scope.context = ctx
            proposal_scope.permissions = frozenset(permissions)
        runtime = replace(
            runtime,
            graph_reader_factory=runtime.graph_reader_factory or _graph_factory(),
        )
        selected = runtime.resolve(ctx.principal, ctx.project_id, args.snapshot)
        if args.command == "metadata-plan":
            raw = _proposal_input(ctx, args.request_json, 8192, permissions=permissions)
            value = create_plan(selected, parse_json(raw))
        elif args.command == "metadata-preview":
            raw = _proposal_input(ctx, args.plan_json, 32768, permissions=permissions)
            value = asyncio.run(
                create_preview(
                    selected, parse_json(raw), args.profile_id, args.operation_id
                )
            )
        elif args.command == "metadata-evidence":
            raw = _proposal_input(
                ctx, args.evidence_json, 2 * 1024**2, permissions=permissions
            )
            value = attach_business_evidence(
                selected, args.operation_id, parse_json(raw)
            )
        elif args.command == "metadata-workspace-create":
            value = metadata_workspace.create_workspace(
                selected, args.operation_id, args.workspace
            )
        elif args.command == "metadata-workspace-apply":
            value = metadata_workspace.apply_workspace(
                selected, args.operation_id, args.workspace
            )
        elif args.command == "metadata-workspace-undo":
            value = metadata_workspace.undo_workspace(
                selected, args.operation_id, args.workspace
            )
        elif args.command == "metadata-workspace-status":
            value = metadata_workspace.get_workspace_status(
                selected, args.operation_id, args.workspace
            )
        else:
            value = get_preview(selected, args.operation_id)
        return _ProposalCommandResult(value, ctx, frozenset(permissions))
    if args.command.startswith("edt-profile-"):
        from . import edt_profiles

        if proposal_scope is not None:
            proposal_scope.context = ctx
            proposal_scope.permissions = frozenset(permissions)
        if args.command == "edt-profile-register":
            from ._windows_source_tree import read_retained

            value = edt_profiles.register_profile(
                ctx,
                edt_profiles.parse_json(
                    read_retained(args.profile_json.absolute(), 131072)
                ),
            )
        elif args.command == "edt-profile-list":
            value = edt_profiles.list_profiles(ctx)
        else:
            value = edt_profiles.disable_profile(ctx, args.profile_id)
        return _ProposalCommandResult(value, ctx, frozenset(permissions))
    if (
        args.command.startswith("test-profile-")
        or args.command == "proposal-test-result"
    ):
        from . import test_profiles

        if proposal_scope is not None:
            proposal_scope.context = ctx
            proposal_scope.permissions = frozenset(permissions)
        if args.command == "test-profile-register":
            from ._windows_source_tree import read_retained

            value = test_profiles.register_profile(
                ctx,
                test_profiles._json(
                    read_retained(args.profile_json.absolute(), 131072)
                ),
            )
        elif args.command == "test-profile-list":
            value = test_profiles.list_profiles(ctx)
        elif args.command == "test-profile-disable":
            value = test_profiles.disable_profile(ctx, args.profile_id)
        else:
            from .platform_runs import get_platform_run

            value = get_platform_run(ctx, args.operation_id, namespace="test-runs")
        return _ProposalCommandResult(value, ctx, frozenset(permissions))
    if args.command == "proposal-platform-result":
        from .platform_runs import get_platform_run

        if proposal_scope is not None:
            proposal_scope.context = ctx
            proposal_scope.permissions = frozenset(permissions)
        return _ProposalCommandResult(
            get_platform_run(ctx, args.operation_id), ctx, frozenset(permissions)
        )
    if args.command.startswith("draft-"):
        if proposal_scope is not None:
            proposal_scope.context = ctx
            proposal_scope.permissions = frozenset(permissions)
        return _ProposalCommandResult(
            _draft_command(args, runtime, ctx), ctx, frozenset(permissions)
        )
    if args.command in {
        "proposal-create",
        "proposal-diff",
        "proposal-check",
        "proposal-platform-check",
        "proposal-test",
    }:
        if proposal_scope is not None:
            proposal_scope.context = ctx
            proposal_scope.permissions = frozenset(permissions)
        return _proposal_command(args, runtime, ctx)
    if args.command.startswith("membership-"):
        return _membership_command(args, ctx)
    if args.command == "state-upgrade-access":
        from .access_migration import upgrade_project_access

        operation_id = validate_operation_id(args.operation_id)
        return upgrade_project_access(
            ctx.state,
            principal,
            backup_directory=args.backup_directory,
            operation_id=operation_id,
        )
    if args.command == "state-upgrade-workflows":
        from .workflow_migration import upgrade_project_workflows

        return upgrade_project_workflows(
            ctx.state,
            principal,
            backup_directory=args.backup_directory,
            operation_id=validate_operation_id(args.operation_id),
        )
    if args.command == "capture":
        return _capture(args, runtime, ctx)
    if args.command == "snapshot-diff":
        from .snapshot_diff import compare_snapshots

        if proposal_scope is not None:
            proposal_scope.context = ctx
            proposal_scope.permissions = frozenset(permissions)
        runtime = replace(
            runtime,
            graph_reader_factory=runtime.graph_reader_factory or _graph_factory(),
        )
        before = runtime.resolve(principal, args.project, args.before)
        after = runtime.resolve(principal, args.project, args.after)
        report = compare_snapshots(before, after, limit=args.limit, cursor=args.cursor)
        document = json.loads(json.dumps(report, default=_default, allow_nan=False))
        return _ProposalCommandResult(
            document,
            ctx,
            frozenset(permissions),
        )
    if args.command in {"source-list", "source-read", "graph-resolve", "impact"}:
        return _snapshot_command(args, runtime, principal)
    if args.command == "state-migrate":
        from .state_migration import migrate_project_state

        operation_id = (
            validate_operation_id(args.operation_id)
            if args.operation_id is not None
            else str(uuid4())
        )
        _emit(
            {
                "migration_recovery": {
                    "operation_id": operation_id,
                    "project_id": ctx.project_id,
                    "backup_directory": str(args.backup_directory.absolute()),
                }
            },
            stream=sys.stderr,
        )
        return migrate_project_state(
            ctx.state,
            principal,
            backup_directory=args.backup_directory,
            operation_id=operation_id,
        )
    if args.command == "layers-set":
        document = _json_file(args.layers_json)
        if not isinstance(document, list) or not 1 <= len(document) <= 256:
            raise CoreError("INVALID_ARGUMENT", "Expected 1..256 layer specifications")
        fields = ("layer_id", "ordinal", "kind", "root_relative_path", "source_format")
        layers = tuple(SourceLayerSpec(**_fields(item, fields)) for item in document)
        return configure_source_layers(
            ctx, layers, expected_revision=args.expected_revision
        )
    with ctx.state.transaction(principal) as tx:
        if args.command == "layers-get":
            return tx.get_source_configuration()
        return tx.get_publication(args.operation_id)


def _target_principal(path):
    from .access import principal_value

    target = Principal(**_fields(_json_file(path), ("id", "authority")))
    principal_value(target)
    return target


def _draft_command(args, runtime, ctx):
    from . import drafts

    # Reject unsupported schema before reading any caller-selected local file.
    with ctx.state.transaction(ctx.principal) as tx:
        drafts._require(
            tx, write=args.command in {"draft-save", "draft-archive", "draft-restore"}
        )
    if args.command == "draft-save":
        raw = _proposal_input(ctx, args.proposal_json, 1536 * 1024)
        runtime = replace(
            runtime,
            graph_reader_factory=runtime.graph_reader_factory or _graph_factory(),
        )
        pinned = runtime.resolve(ctx.principal, args.project, args.snapshot)
        return drafts.save_draft(
            pinned,
            raw,
            draft_id=args.draft_id,
            title=args.title,
            expected_revision=args.expected_revision,
            operation_id=args.operation_id,
        )
    if args.command == "draft-get":
        result = drafts.get_draft(ctx, args.draft_id, revision=args.revision)
        return {
            "receipt": result["receipt"],
            "proposal": json.loads(result["canonical_json"]),
        }
    if args.command == "draft-list":
        return drafts.list_drafts(
            ctx,
            limit=args.limit,
            after_draft_id=args.after_draft_id,
            status=args.status,
        )
    if args.command == "draft-history":
        return drafts.draft_history(
            ctx, args.draft_id, limit=args.limit, before_revision=args.before_revision
        )
    if args.command == "draft-receipt":
        return drafts.get_draft_receipt(ctx, args.operation_id)
    action = (
        drafts.archive_draft
        if args.command == "draft-archive"
        else drafts.restore_draft
    )
    return action(
        ctx,
        args.draft_id,
        expected_revision=args.expected_revision,
        operation_id=args.operation_id,
    )


def _membership_command(args, ctx):
    from .access import change_membership

    if args.command == "membership-list":
        after = (
            None
            if args.after_principal_json is None
            else _target_principal(args.after_principal_json)
        )
        with ctx.state.transaction(ctx.principal) as tx:
            return tx.list_memberships(
                limit=100 if args.limit is None else args.limit, after=after
            )
    if args.command == "membership-receipt":
        with ctx.state.transaction(ctx.principal) as tx:
            return tx.get_membership_receipt(args.operation_id)
    target = _target_principal(args.principal_json)
    permissions = (
        _json_file(args.permissions_json) if args.command == "membership-set" else None
    )
    return change_membership(
        ctx.state,
        ctx.principal,
        target=target,
        permissions=permissions,
        action="membership.set"
        if args.command == "membership-set"
        else "membership.revoke",
        operation_id=args.operation_id,
        expected_revision=args.expected_revision,
    )


def _default(value):
    if is_dataclass(value):
        return asdict(value)
    raise TypeError("Unsupported command result")


def _emit(value, *, stream=None):
    print(
        json.dumps(value, default=_default, ensure_ascii=True, allow_nan=False),
        file=stream or sys.stdout,
        flush=True,
    )


def _emit_error(payload, scope, request_id):
    if scope.context is None:
        _emit(payload)
        return
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False)
    try:
        _proposal_permissions(scope.context, scope.permissions)
    except CoreError as exc:
        encoded = json.dumps(
            exc.to_dict(request_id), ensure_ascii=True, allow_nan=False
        )
    except (OSError, sqlite3.Error):
        encoded = json.dumps(
            CoreError(
                "PROJECT_ACCESS_UNAVAILABLE",
                "Current project permissions could not be verified",
            ).to_dict(request_id),
            ensure_ascii=True,
            allow_nan=False,
        )
    # A replacement authorization error contains no candidate/report details.
    # No original error survives this last check after serialization.
    print(encoded, flush=True)


def main(argv=None) -> int:
    """Run a trusted local command; return zero on success, two on failure."""
    request_id = str(uuid4())
    scope = _ProposalScope()
    try:
        args = _parser().parse_args(argv)
        result = _execute(args, proposal_scope=scope)
        if isinstance(result, _ProposalCommandResult):
            try:
                envelope = {"result": result.value, "request_id": request_id}
                encoded = json.dumps(
                    envelope, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                ).encode("utf-8")
                if len(encoded) > 2097152:
                    raise CoreError(
                        "OUTPUT_LIMIT_EXCEEDED", "Proposal result exceeds 2 MiB"
                    )
            except BaseException:
                _proposal_permissions(result.context, result.permissions)
                raise
            _proposal_permissions(result.context, result.permissions)
            # stdout is part of the supported UTF-8 local CLI contract.
            if hasattr(sys.stdout, "buffer"):
                sys.stdout.buffer.write(encoded + b"\n")
                sys.stdout.buffer.flush()
            else:
                print(encoded.decode("utf-8"), flush=True)
        else:
            _emit({"result": result, "request_id": request_id})
        return 0
    except CoreError as exc:
        _emit_error(exc.to_dict(request_id), scope, request_id)
    except KeyboardInterrupt:
        _emit_error(
            CoreError(
                "OPERATION_INTERRUPTED",
                "Command interrupted; publication may have committed. Reconcile using the emitted recovery identity",
            ).to_dict(request_id),
            scope,
            request_id,
        )
    except (OSError, sqlite3.Error) as exc:
        code = (
            "STATE_DATABASE_ERROR"
            if isinstance(exc, sqlite3.Error)
            else "LOCAL_IO_ERROR"
        )
        _emit_error(
            CoreError(
                code, "Local operation failed; no success receipt is asserted"
            ).to_dict(request_id),
            scope,
            request_id,
        )
    except Exception:
        _emit_error(
            CoreError(
                "LOCAL_OPERATION_FAILED",
                "Local operation failed; no success receipt is asserted",
            ).to_dict(request_id),
            scope,
            request_id,
        )
    return 2
