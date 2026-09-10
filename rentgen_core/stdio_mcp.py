"""Explicit local-only MCP tools over the official SDK's stdio transport.

The principal and registry/scanner are trusted startup configuration. Tool JSON
never configures identity or live roots. This module is not an HTTP adapter.
"""
import argparse
import base64
import binascii
from dataclasses import asdict, dataclass, is_dataclass, replace
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
from uuid import uuid4

from .context import SnapshotRef
from .errors import CoreError
from .local import LocalRuntime
from .local_identity import current_windows_principal
from .publication import capture_and_publish
from .snapshots import ProjectHead
from .source_paths import validate_source_path
from . import mcp_drafts

MAX_FRAME_BYTES = 65536
MAX_SOURCE_BYTES = 1024 * 1024
MAX_RESULT_BYTES = 2 * 1024 * 1024
MAX_PENDING_CALLS = 8
MAX_PROPOSAL_RESULT_BYTES = 131072
MAX_PROPOSAL_ARGUMENT_BYTES = 24576
_OUTPUT_SCOPE = "rentgenOutputScope"


def _object(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties if required is None else required),
        "additionalProperties": False,
    }


_UUID = {
    "type": "string",
    "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    "maxLength": 36,
}
_HASH = {"type": "string", "pattern": r"^[0-9a-f]{64}$", "maxLength": 64}
_SNAPSHOT = _object({"project_id": _UUID, "snapshot_id": _HASH, "manifest_hash": _HASH})
_HEAD = _object(
    {
        "project_id": _UUID,
        "revision": {"type": "integer", "minimum": 0, "maximum": 2**63 - 1},
        "source_revision": {"type": "integer", "minimum": 1, "maximum": 2**63 - 1},
        "snapshot": {"anyOf": [_SNAPSHOT, {"type": "null"}]},
    }
)
_PIN = {"project_id": _UUID, "snapshot_id": _HASH}
_SOURCE = {
    **_PIN,
    "layer_id": {
        "type": "string",
        "pattern": r"^[a-z][a-z0-9_-]{0,63}$",
        "maxLength": 64,
    },
    "relative_path": {"type": "string", "minLength": 1, "maxLength": 4096},
}
_SOURCE_REF = _object(
    {
        "snapshot": _SNAPSHOT,
        "layer_id": _SOURCE["layer_id"],
        "relative_path": {"type": "string", "minLength": 1, "maxLength": 1024},
        "raw_sha256": _HASH,
    }
)
_PROPOSAL_DOCUMENT = _object(
    {
        "domain": {
            "type": "string",
            "pattern": r"^rentgen\.source-proposal$",
            "maxLength": 23,
        },
        "schema_version": {"type": "integer", "minimum": 1, "maximum": 1},
        "source_ref": _SOURCE_REF,
        "original": _object(
            {
                "size_bytes": {"type": "integer", "minimum": 0, "maximum": 1048576},
                "raw_sha256": _HASH,
            }
        ),
        "replacement": _object(
            {
                "size_bytes": {"type": "integer", "minimum": 0, "maximum": 8192},
                "raw_sha256": _HASH,
                "base64": {"type": "string", "maxLength": 10924},
            }
        ),
        "policy": _object(
            {
                "encoding": {"type": "string", "pattern": "^utf-8$", "maxLength": 5},
                "bom": {"type": "boolean"},
                "newline": {"type": "string", "pattern": "^(lf|crlf)$", "maxLength": 4},
                "original_final_newline": {"type": "boolean"},
                "replacement_final_newline": {"type": "boolean"},
            }
        ),
        "content_id": _HASH,
    }
)
_PROPOSAL_TOOLS = frozenset({"rentgen_proposal_create", "rentgen_proposal_check"})
TOOL_SCHEMAS = {
    "rentgen_proposal_check": _object(
        {
            **_PIN,
            "proposal": _PROPOSAL_DOCUMENT,
            "diagnostics_profile": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
                "pattern": r"^[a-z0-9][a-z0-9._-]*$",
            },
        }
    ),
    "rentgen_proposal_create": _object(
        {
            **_PIN,
            "source_ref": _SOURCE_REF,
            "replacement_base64": {
                "type": "string",
                "minLength": 0,
                "maxLength": 10924,
            },
        }
    ),
    "rentgen_project_list": _object({}),
    "rentgen_project_head": _object({"project_id": _UUID}),
    "rentgen_publication_receipt": _object(
        {"project_id": _UUID, "operation_id": _UUID}
    ),
    "rentgen_capture": _object(
        {"project_id": _UUID, "operation_id": _UUID, "expected_head": _HEAD}
    ),
    "rentgen_source_list": _object(
        {
            **_PIN,
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            "cursor": {"type": "string", "minLength": 1, "maxLength": 8192},
            "query": {"type": "string", "maxLength": 256},
            "kind": {"type": "string", "pattern": "^(all|module)$", "maxLength": 6},
            "layer": _SOURCE["layer_id"],
        },
        _PIN,
    ),
    "rentgen_source_read": _object(_SOURCE),
    "rentgen_graph_resolve": _object(_SOURCE),
    "rentgen_impact": _object(
        {**_SOURCE, "depth": {"type": "integer", "minimum": 1, "maximum": 5}}, _SOURCE
    ),
}
_DESCRIPTIONS = {
    "rentgen_proposal_check": "Run the installed pinned BSL analyzer on an exact ephemeral proposal. Requires editing and analysis rights. Reports single-module diagnostics; tests are not run and apply is unavailable.",
    "rentgen_proposal_create": "Build an ephemeral single-module proposal and bounded diff from an exact SourceRef. Requires editing rights; no tests or source writes. Candidate limit 8 KiB.",
    "rentgen_project_list": "List authorized project IDs and labels; no source reads.",
    "rentgen_project_head": "Read the current project head without opening a generation.",
    "rentgen_publication_receipt": "Reconcile one capture operation using its durable receipt.",
    "rentgen_capture": "Capture and publish against the original expected head. Cancellation is not rollback; reconcile the operation receipt.",
    "rentgen_source_list": "Find retained sources across an explicit snapshot by path substring, file kind and exact layer; filters apply before pagination.",
    "rentgen_source_read": "Read up to 1 MiB of exact retained bytes as base64 with SourceRef and raw hash.",
    "rentgen_graph_resolve": "Resolve a retained source module in an explicit snapshot's graph.",
    "rentgen_impact": "Return bounded static impact from an explicit snapshot's graph.",
}
TOOL_SCHEMAS.update(mcp_drafts.schemas(_object, _UUID, _HASH, _PROPOSAL_DOCUMENT))
_DESCRIPTIONS.update(mcp_drafts.DESCRIPTIONS)


@dataclass(frozen=True)
class McpScope:
    """Immutable trusted startup restrictions, additional to current memberships.

    This constrains this server connection, not other processes of the same SID.
    Tool JSON cannot construct or change this value.
    """

    project_id: str | None = None
    allowed_tools: frozenset[str] | None = None

    def __post_init__(self):
        from .context import validate_project_id

        if self.project_id is not None:
            try:
                validate_project_id(self.project_id)
            except CoreError as exc:
                raise ValueError("Scope requires one canonical project UUID") from exc
        tools = self.allowed_tools
        if tools is None:
            tools = frozenset(TOOL_SCHEMAS)
            if self.project_id is not None:
                tools -= {"rentgen_project_list"}
        elif (
            type(tools) not in {list, tuple, set, frozenset}
            or not 1 <= len(tools) <= len(TOOL_SCHEMAS)
            or any(type(name) is not str for name in tools)
            or len(set(tools)) != len(tools)
            or not set(tools) <= TOOL_SCHEMAS.keys()
            or (self.project_id is not None and "rentgen_project_list" in tools)
        ):
            raise ValueError(
                "Expected unique known tools compatible with project scope"
            )
        object.__setattr__(self, "allowed_tools", frozenset(tools))
        if self.project_id is not None and any(
            "project_id" not in TOOL_SCHEMAS[name]["required"] for name in tools
        ):
            raise ValueError("Project scope requires explicit project selectors")

    def require_tool(self, name):
        if name not in TOOL_SCHEMAS:
            raise CoreError(
                "UNKNOWN_TOOL", "Tool is not part of the local MCP allowlist"
            )
        if name not in self.allowed_tools:
            raise CoreError(
                "MCP_TOOL_FORBIDDEN", "Tool is outside this server's startup scope"
            )

    def require_project(self, arguments):
        if self.project_id is None:
            return
        # Called after schema validation. Check every structured project selector,
        # including SourceRef/proposal/expected_head; never interpret source text.
        pending = [arguments]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                if "project_id" in value and value["project_id"] != self.project_id:
                    raise CoreError(
                        "MCP_PROJECT_FORBIDDEN",
                        "Project is outside this server's startup scope",
                    )
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)


def _invalid(message="Tool arguments do not match the declared schema"):
    return CoreError("INVALID_ARGUMENT", message)


def _known_argument_fields():
    pending = list(TOOL_SCHEMAS.values())
    names = set()
    while pending:
        schema = pending.pop()
        properties = schema.get("properties", {})
        names.update(properties)
        pending.extend(properties.values())
        pending.extend(schema.get("anyOf", []))
        if "items" in schema:
            pending.append(schema["items"])
    return frozenset(names)


_KNOWN_ARGUMENT_FIELDS = _known_argument_fields()


def _schema_error(path, rule, message, **details):
    # Paths and expected fields come from our schema, never from argument values.
    return CoreError(
        "INVALID_ARGUMENT", message, details={"path": path, "rule": rule, **details}
    )


def _validate(value, schema, path=""):
    """Interpret our narrow declared schemas with exact Python integer types.

    Standard JSON Schema accepts 1.0 as an integer; command DTOs intentionally
    reject floats and booleans instead of allowing implicit numeric coercion.
    """
    if "anyOf" in schema:
        for option in schema["anyOf"]:
            try:
                _validate(value, option, path)
                return
            except CoreError:
                pass
        raise _schema_error(
            path,
            "anyOf",
            "Expected one of the declared argument types",
            expected_types=[option["type"] for option in schema["anyOf"]],
        )
    kind = schema["type"]
    if kind == "null":
        if value is not None:
            raise _schema_error(path, "type", "Expected null", expected_type=kind)
    elif kind == "object":
        if type(value) is not dict:
            raise _schema_error(path, "type", "Expected an object", expected_type=kind)
        missing = set(schema["required"]) - value.keys()
        extra = value.keys() - schema["properties"].keys()
        if missing or extra:
            # Reflect only names already present in our published schemas. Unknown
            # names could contain credentials or instructions; report their count.
            raise _schema_error(
                path,
                "object_fields",
                "Add missing fields and remove fields not allowed by this tool schema",
                missing_fields=sorted(missing),
                unexpected_fields=sorted(extra & _KNOWN_ARGUMENT_FIELDS),
                unrecognized_field_count=len(extra - _KNOWN_ARGUMENT_FIELDS),
                allowed_fields=sorted(schema["properties"]),
            )
        for key, item in value.items():
            _validate(item, schema["properties"][key], path + "/" + key)
    elif kind == "array":
        if type(value) is not list:
            raise _schema_error(path, "type", "Expected an array", expected_type=kind)
        if not schema["minItems"] <= len(value) <= schema["maxItems"]:
            raise _schema_error(
                path,
                "item_count",
                "Array length is outside the allowed range",
                minimum=schema["minItems"],
                maximum=schema["maxItems"],
            )
        for index, item in enumerate(value):
            _validate(item, schema["items"], path + "/" + str(index))
    elif kind == "boolean":
        if type(value) is not bool:
            raise _schema_error(path, "type", "Expected a boolean", expected_type=kind)
    elif kind == "integer":
        if type(value) is not int:
            raise _schema_error(
                path,
                "type",
                "Expected an integer; booleans and floats are not accepted",
                expected_type=kind,
            )
        if not schema["minimum"] <= value <= schema["maximum"]:
            raise _schema_error(
                path,
                "range",
                "Integer is outside the allowed range",
                minimum=schema["minimum"],
                maximum=schema["maximum"],
            )
    elif kind == "string":
        if type(value) is not str:
            raise _schema_error(path, "type", "Expected a string", expected_type=kind)
        if not schema.get("minLength", 0) <= len(value) <= schema["maxLength"]:
            raise _schema_error(
                path,
                "string_length",
                "String length is outside the allowed range",
                minimum=schema.get("minLength", 0),
                maximum=schema["maxLength"],
            )
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise _schema_error(
                path,
                "pattern",
                "String does not match the required format",
                expected_pattern=schema["pattern"],
            )
        try:
            value.encode("utf-8")
        except UnicodeError as exc:
            raise _schema_error(
                path, "utf8", "String must encode as valid UTF-8"
            ) from exc


def validate_arguments(name, arguments, *, scope=None):
    if name not in TOOL_SCHEMAS:
        raise CoreError("UNKNOWN_TOOL", "Tool is not part of the local MCP allowlist")
    if scope is not None:
        scope.require_tool(name)
    _validate(arguments, TOOL_SCHEMAS[name])
    if scope is not None:
        scope.require_project(arguments)
    if name in mcp_drafts.TOOLS:
        return mcp_drafts.prepare(
            name, arguments, max_argument_bytes=MAX_PROPOSAL_ARGUMENT_BYTES
        )
    if name == "rentgen_source_list":
        from .source_catalog import source_query

        source_query(
            query=arguments.get("query", ""),
            kind=arguments.get("kind", "all"),
            layer=arguments.get("layer"),
        )
    if name in _PROPOSAL_TOOLS:
        if (
            len(
                json.dumps(
                    arguments,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
            > MAX_PROPOSAL_ARGUMENT_BYTES
        ):
            raise _invalid("Proposal tool arguments exceed 24 KiB")
        source_ref = (
            arguments["source_ref"]
            if name == "rentgen_proposal_create"
            else arguments["proposal"]["source_ref"]
        )
        path = source_ref["relative_path"]
        validate_source_path(path)
        if len(path.encode("utf-8")) > 1024:
            raise _invalid("Proposal source path exceeds 1024 UTF-8 bytes")
    if "relative_path" in arguments:
        validate_source_path(arguments["relative_path"])


def validate_frame(raw):
    """Reject ambiguous/unbounded input before the SDK parses the protocol frame."""

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite")

    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite")
        return result

    if len(raw) > MAX_FRAME_BYTES:
        raise _invalid("MCP frame exceeds 64 KiB")
    try:
        text = raw.decode("utf-8", errors="strict")
        json.loads(
            text, object_pairs_hook=pairs, parse_constant=constant, parse_float=number
        )
        return text
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise _invalid(
            "MCP frame must be strict UTF-8 JSON without duplicate keys"
        ) from exc


class _WorkerCancellations:
    """Deduplicate cancellation while an admitted SDK request retains its worker.

    SDK 1.30 responds to every cancellation while a shielded responder remains
    in flight. Keep only the at-most-eight admitted calls, and release each entry
    in its handler's finally block. No session-long request-ID cache is needed.
    """

    def __init__(self):
        self.active = {}

    def duplicate(self, text):
        document = json.loads(text)
        if (
            not isinstance(document, dict)
            or document.get("jsonrpc") != "2.0"
            or document.get("method") != "notifications/cancelled"
            or "id" in document
        ):
            return False
        from mcp.types import CancelledNotification

        try:
            notification = CancelledNotification.model_validate(document)
        except ValueError:
            return False  # The SDK owns protocol-shape errors.
        request_id = notification.params.requestId
        if request_id not in self.active:
            return False
        duplicate = self.active[request_id]
        self.active[request_id] = True
        return duplicate


class _BoundedInput:
    def __init__(self, stream, cancellations=None):
        self.stream = stream
        self.cancellations = cancellations

    def __aiter__(self):
        return self

    async def __anext__(self):
        import anyio

        while True:
            raw = await anyio.to_thread.run_sync(
                self.stream.readline, MAX_FRAME_BYTES + 1
            )
            if not raw:
                raise StopAsyncIteration
            text = validate_frame(raw)
            if self.cancellations is None or not self.cancellations.duplicate(text):
                return text


class _InstalledBuilder:
    def __init__(self, scanner):
        self.scanner = scanner

    def build(self, captured, *, output_path, work_dir):
        if self.scanner is None:
            raise CoreError(
                "GRAPH_ADAPTER_UNAVAILABLE",
                "Capture requires a scanner configured at server startup",
            )
        from rentgen_graph.snapshot_adapter import RentgenCapturedGoBuilder

        return RentgenCapturedGoBuilder(self.scanner).build(
            captured, output_path=output_path, work_dir=work_dir
        )


@dataclass(frozen=True)
class _ProposalToolResult:
    value: dict
    context: object
    permissions: frozenset = frozenset({"project:read", "source:edit"})
    family: str = "proposal"


def _proposal_permissions(ctx, permissions=frozenset({"project:read", "source:edit"})):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(permissions)


def _proposal_required_permissions(name):
    permissions = frozenset({"project:read", "source:edit"})
    return (
        permissions | {"analysis:run"}
        if name == "rentgen_proposal_check"
        else permissions
    )


def _proposal_dispatch(runtime, principal, name, args, *, state_ctx=None):
    permissions = _proposal_required_permissions(name)
    state_ctx = state_ctx or runtime.state_context(
        principal, args["project_id"], permissions=permissions
    )
    try:
        from .sources import SourceRef
        from .proposals import ProposalLimits, create_proposal_presentation

        selected = SnapshotRef(
            args["project_id"], args["snapshot_id"], args["snapshot_id"]
        )
        value = (
            args["source_ref"]
            if name == "rentgen_proposal_create"
            else args["proposal"]["source_ref"]
        )
        ref = SourceRef(
            SnapshotRef(**value["snapshot"]),
            value["layer_id"],
            value["relative_path"],
            value["raw_sha256"],
        )
        if ref.snapshot != selected:
            raise CoreError(
                "SOURCE_REF_MISMATCH",
                "SourceRef does not match selected project/snapshot",
            )
        if name == "rentgen_proposal_create":
            encoded = args["replacement_base64"]
            try:
                replacement = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise _invalid("Expected canonical base64 candidate") from exc
            if base64.b64encode(replacement).decode("ascii") != encoded:
                raise _invalid("Expected canonical base64 candidate")
            if len(replacement) > 8192:
                raise CoreError(
                    "PROPOSAL_LIMIT_EXCEEDED", "MCP candidate exceeds 8 KiB"
                )
        _proposal_permissions(state_ctx, permissions)
        if runtime.graph_reader_factory is None:
            from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory

            runtime = replace(runtime, graph_reader_factory=RentgenGraphReaderFactory())
        ctx = runtime.resolve(principal, args["project_id"], args["snapshot_id"])
        if name == "rentgen_proposal_check":
            from .diagnostics import diagnose_proposal_json

            _proposal_permissions(state_ctx, permissions)
            provider = runtime.diagnostic_provider
            if provider is None:
                raise CoreError(
                    "DIAGNOSTIC_RUNTIME_UNAVAILABLE",
                    "No trusted diagnostics provider is configured",
                )
            adapter = provider.for_profile(args["diagnostics_profile"])
            raw = json.dumps(
                args["proposal"],
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
            diagnostic = diagnose_proposal_json(
                ctx, raw, adapter, limits=ProposalLimits(1048576, 8192, 16384, 24576)
            )
            _proposal_permissions(state_ctx, permissions)
            return _ProposalToolResult(
                {
                    "diagnostic": asdict(diagnostic),
                    "tests": {"status": "not_run"},
                    "apply": {"status": "unavailable"},
                },
                state_ctx,
                permissions,
            )
        presentation = create_proposal_presentation(
            ctx, ref, replacement, limits=ProposalLimits(1048576, 8192, 16384, 24576)
        )
        result = {
            "proposal": json.loads(presentation.canonical_json.decode("utf-8")),
            "diff": asdict(presentation.diff),
            "tests": {"status": "not_run"},
            "apply": {"status": "unavailable"},
        }
        _proposal_permissions(state_ctx, permissions)
        return _ProposalToolResult(result, state_ctx, permissions)
    except BaseException:
        _proposal_permissions(state_ctx, permissions)
        raise


def _family_limit(family):
    if family == "draft":
        return MAX_RESULT_BYTES
    if family == "proposal":
        return MAX_PROPOSAL_RESULT_BYTES
    raise ValueError("Unknown protected output family")


def _wire_scope(ctx, permissions, request_id, family="proposal"):
    return {
        _OUTPUT_SCOPE: {
            "project_id": ctx.project_id,
            "permissions": sorted(permissions),
            "request_id": request_id,
            **({"family": family} if family != "proposal" else {}),
        }
    }


def _proposal_reply(result, request_id, protocol_request_id):
    from mcp.types import CallToolResult, JSONRPCResponse, TextContent

    try:
        payload = {"result": result.value, "request_id": request_id}
        text = json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        reply = CallToolResult(
            content=[TextContent(type="text", text=text)],
            structuredContent=payload,
            _meta=_wire_scope(
                result.context, result.permissions, request_id, result.family
            ),
        )
        # Use the installed SDK's exact stdio serialization, including duplicate
        # text/structured content, the actual caller ID, and terminating newline.
        wire = (
            JSONRPCResponse(
                jsonrpc="2.0",
                id=0 if protocol_request_id is None else protocol_request_id,
                result=reply.model_dump(by_alias=True, mode="json", exclude_none=True),
            )
            .model_dump_json(by_alias=True, exclude_none=True)
            .encode("utf-8")
            + b"\n"
        )
        if len(wire) > _family_limit(result.family):
            raise CoreError(
                "OUTPUT_LIMIT_EXCEEDED",
                "Protected SDK response exceeds its wire size limit",
            )
    except BaseException:
        _proposal_permissions(result.context, result.permissions)
        raise
    _proposal_permissions(result.context, result.permissions)
    return reply


def _dispatch(runtime, principal, name, args):
    if name in _PROPOSAL_TOOLS:
        return _proposal_dispatch(runtime, principal, name, args)
    if name == "rentgen_project_list":
        return runtime.registry.list_for(principal)
    project = args["project_id"]
    if name == "rentgen_project_head":
        return runtime.head(principal, project)
    if name in {"rentgen_capture", "rentgen_publication_receipt"}:
        ctx = runtime.state_context(
            principal,
            project,
            permissions={"analysis:run"} if name == "rentgen_capture" else (),
        )
        if name == "rentgen_publication_receipt":
            with ctx.state.transaction(principal) as tx:
                return tx.get_publication(args["operation_id"])
        head = dict(args["expected_head"])
        if head["snapshot"] is not None:
            head["snapshot"] = SnapshotRef(**head["snapshot"])
        return capture_and_publish(
            ctx,
            expected_head=ProjectHead(**head),
            operation_id=args["operation_id"],
            builder=runtime.graph_builder,
        )
    # Authenticate before importing/opening the graph adapter or generation.
    runtime.state_context(principal, project)
    if runtime.graph_reader_factory is None:
        from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory

        runtime = replace(runtime, graph_reader_factory=RentgenGraphReaderFactory())
    ctx = runtime.resolve(principal, project, args["snapshot_id"])
    if name == "rentgen_source_list":
        return ctx.sources.list_entries(
            limit=args.get("limit", 100),
            cursor=args.get("cursor"),
            query=args.get("query", ""),
            kind=args.get("kind", "all"),
            layer=args.get("layer"),
        )
    ref = ctx.sources.resolve(args["layer_id"], args["relative_path"])
    if name == "rentgen_graph_resolve":
        return ctx.graph.resolve_module(ref)
    if name == "rentgen_impact":
        return ctx.graph.impact(ref, depth=args.get("depth", 1))
    raw = ctx.sources.read_source(ref)
    if len(raw) > MAX_SOURCE_BYTES:
        raise CoreError(
            "SOURCE_OUTPUT_LIMIT_EXCEEDED",
            "Use the local CLI to export sources larger than 1 MiB",
        )
    return {
        "ref": ref,
        "raw_sha256": ref.raw_sha256,
        "size_bytes": len(raw),
        "encoding": "base64",
        "data": base64.b64encode(raw).decode("ascii"),
    }


def _json_default(value):
    if is_dataclass(value):
        return asdict(value)
    raise TypeError("Unsupported tool result")


def _json(value):
    return json.dumps(
        value,
        default=_json_default,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )


def _execute(
    runtime, principal, name, arguments, *, protocol_request_id=None, scope=None
):
    from mcp.types import CallToolResult, TextContent

    request_id = str(uuid4())
    proposal_context = None
    permissions = frozenset()
    family = "proposal"
    try:
        prepared = validate_arguments(name, arguments, scope=scope)
        if name in mcp_drafts.TOOLS:
            family = "draft"
            permissions = mcp_drafts.permissions(name)
            proposal_context = runtime.state_context(
                principal, arguments["project_id"], permissions=permissions
            )
            value = mcp_drafts.dispatch(
                runtime, principal, name, arguments, prepared, proposal_context
            )
            result = _ProposalToolResult(
                {"draft": value}, proposal_context, permissions, family
            )
        elif name in _PROPOSAL_TOOLS:
            permissions = _proposal_required_permissions(name)
            proposal_context = runtime.state_context(
                principal,
                arguments["project_id"],
                permissions=permissions,
            )
            result = _proposal_dispatch(
                runtime, principal, name, arguments, state_ctx=proposal_context
            )
        else:
            result = _dispatch(runtime, principal, name, arguments)
        if isinstance(result, _ProposalToolResult):
            return _proposal_reply(result, request_id, protocol_request_id)
        payload = {"result": result, "request_id": request_id}
        text = _json(payload)
        if len(text.encode("utf-8")) > MAX_RESULT_BYTES:
            raise CoreError(
                "OUTPUT_LIMIT_EXCEEDED",
                "Tool result exceeds 2 MiB; use a smaller page or the local CLI",
            )
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            structuredContent=json.loads(text),
        )
    except CoreError as exc:
        payload = exc.to_dict(request_id)
    except ImportError:
        payload = CoreError(
            "GRAPH_ADAPTER_UNAVAILABLE", "Install the supported rentgen_graph package"
        ).to_dict(request_id)
    except KeyboardInterrupt:
        payload = CoreError(
            "OPERATION_INTERRUPTED",
            "Operation may have committed; reconcile the original operation receipt",
            details={"operation_id": arguments.get("operation_id")},
        ).to_dict(request_id)
    except (OSError, sqlite3.Error):
        payload = CoreError(
            "LOCAL_OPERATION_FAILED",
            "Local operation failed; no success receipt is asserted",
        ).to_dict(request_id)
    except Exception:
        payload = CoreError(
            "LOCAL_OPERATION_FAILED",
            "Local operation failed; no success receipt is asserted",
        ).to_dict(request_id)
    if proposal_context is not None:
        return _proposal_error_reply(
            payload,
            proposal_context,
            request_id,
            protocol_request_id,
            permissions,
            family,
        )
    return CallToolResult(
        content=[TextContent(type="text", text=_json(payload))],
        structuredContent=payload,
        isError=True,
    )


def _proposal_error_reply(
    payload,
    ctx,
    request_id,
    protocol_request_id,
    permissions=frozenset({"project:read", "source:edit"}),
    family="proposal",
):
    from mcp.types import CallToolResult, JSONRPCResponse, TextContent

    def encode(document):
        reply = CallToolResult(
            content=[TextContent(type="text", text=_json(document))],
            structuredContent=document,
            isError=True,
            _meta=_wire_scope(ctx, permissions, request_id, family),
        )
        wire = (
            JSONRPCResponse(
                jsonrpc="2.0",
                id=0 if protocol_request_id is None else protocol_request_id,
                result=reply.model_dump(by_alias=True, mode="json", exclude_none=True),
            )
            .model_dump_json(by_alias=True, exclude_none=True)
            .encode("utf-8")
            + b"\n"
        )
        return reply, len(wire)

    reply, size = encode(payload)
    if size > _family_limit(family):
        reply, _ = encode(
            CoreError(
                "OUTPUT_LIMIT_EXCEEDED",
                "Protected SDK response exceeds its wire size limit",
            ).to_dict(request_id)
        )
    try:
        _proposal_permissions(ctx, permissions)
    except CoreError as exc:
        reply, _ = encode(exc.to_dict(request_id))
    except (OSError, sqlite3.Error):
        reply, _ = encode(
            CoreError(
                "PROJECT_ACCESS_UNAVAILABLE",
                "Current project permissions could not be verified",
            ).to_dict(request_id)
        )
    return reply


def create_server(runtime, principal, *, cancellations=None, scope=None):
    """Trusted composition only; callers cannot select identity through protocol data."""
    import anyio
    from mcp.server.lowlevel import Server
    from mcp.types import Tool, ToolAnnotations, CallToolResult, TextContent

    scope = McpScope() if scope is None else scope
    if type(scope) is not McpScope:
        raise ValueError("Expected an immutable MCP startup scope")
    server = Server("rentgen-local", version="1")
    limiter = anyio.CapacityLimiter(1)
    cancellations = cancellations or _WorkerCancellations()
    pending = 0

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name=name,
                description=_DESCRIPTIONS[name],
                inputSchema=schema,
                annotations=ToolAnnotations(
                    readOnlyHint=name not in mcp_drafts.WRITES | {"rentgen_capture"},
                    destructiveHint=False,
                    openWorldHint=False,
                ),
            )
            for name, schema in TOOL_SCHEMAS.items()
            if name in scope.allowed_tools
        ]

    @server.call_tool(validate_input=False)
    async def call_tool(name, arguments):
        nonlocal pending
        if pending >= MAX_PENDING_CALLS:
            payload = CoreError(
                "SERVER_BUSY", "At most eight tool calls may be pending"
            ).to_dict(str(uuid4()))
            return CallToolResult(
                content=[TextContent(type="text", text=_json(payload))],
                structuredContent=payload,
                isError=True,
            )
        pending += 1
        request_id = server.request_context.request_id
        cancellations.active[request_id] = False
        try:
            result = await anyio.to_thread.run_sync(
                lambda: _execute(
                    runtime,
                    principal,
                    name,
                    arguments,
                    protocol_request_id=request_id,
                    scope=scope,
                ),
                abandon_on_cancel=False,
                limiter=limiter,
            )
            # Deliver a pending SDK cancellation only after the worker finishes.
            # The SDK already responded to cancellation; do not respond twice.
            await anyio.lowlevel.checkpoint()
            return result
        finally:
            cancellations.active.pop(request_id, None)
            pending -= 1

    return server


class _GuardedOutput:
    """Authorize protected bytes after the SDK's actual final serialization.

    Internal metadata is generated by this transport, never by tool arguments.
    It is removed before public encoding. No request-ID cache or abandoned
    response scope is retained across calls. This is the supported stdio boundary;
    custom transports around create_server need their own output authorization.
    """

    def __init__(self, stream, runtime, principal):
        self._stream = stream
        self._runtime = runtime
        self._principal = principal

    @staticmethod
    def _error(document, request_id, code, message):
        payload = CoreError(code, message).to_dict(request_id)
        return {
            "jsonrpc": "2.0",
            "id": document["id"],
            "result": {
                "content": [{"type": "text", "text": _json(payload)}],
                "structuredContent": payload,
                "isError": True,
            },
        }

    @staticmethod
    def _bytes(document):
        return (
            json.dumps(
                document, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
            + b"\n"
        )

    def _write(self, text):
        document = json.loads(text)
        result = document.get("result")
        meta = result.get("_meta") if type(result) is dict else None
        scope = meta.get(_OUTPUT_SCOPE) if type(meta) is dict else None
        structured = result.get("structuredContent") if type(result) is dict else None
        # SDK clients may consume either representation. Protect both, including
        # a text-only reply whose structured content was lost in serialization.
        payloads = [structured]
        content = result.get("content", []) if type(result) is dict else []
        for item in content if type(content) is list else []:
            if type(item) is dict and item.get("type") == "text":
                try:
                    payloads.append(json.loads(item.get("text", "")))
                except (ValueError, TypeError):
                    pass
        protected_keys = set()
        draft_diagnostic = False
        for payload in payloads:
            body = payload.get("result") if type(payload) is dict else None
            if type(body) is dict:
                protected_keys |= {"proposal", "diagnostic", "draft"} & body.keys()
                if type(body.get("draft")) is dict and "diagnostic" in body["draft"]:
                    draft_diagnostic = True
        protected = bool(protected_keys)
        marked = type(meta) is dict and _OUTPUT_SCOPE in meta
        if not marked and not protected:
            raw = text.encode("utf-8")
        else:
            request_id = str(uuid4())
            if marked:
                del meta[_OUTPUT_SCOPE]
                if not meta:
                    del result["_meta"]
            try:
                from .context import validate_project_id

                family = (
                    scope.get("family", "proposal") if type(scope) is dict else None
                )
                expected_keys = {
                    "project_id",
                    "permissions",
                    "request_id",
                } | ({"family"} if family == "draft" else set())
                if (
                    type(scope) is not dict
                    or family not in {"draft", "proposal"}
                    or set(scope) != expected_keys
                ):
                    raise ValueError("Invalid internal output scope")
                if ("draft" in protected_keys and family != "draft") or (
                    bool({"proposal", "diagnostic"} & protected_keys)
                    and family != "proposal"
                ):
                    raise ValueError("Invalid internal output family")
                validate_project_id(scope["project_id"])
                from .snapshots import validate_operation_id

                validate_operation_id(scope["request_id"])
                request_id = scope["request_id"]
                permissions = scope["permissions"]
                allowed = (
                    (
                        ["project:read"],
                        ["project:read", "source:edit"],
                        ["analysis:run", "project:read", "source:edit"],
                    )
                    if family == "draft"
                    else (
                        ["project:read", "source:edit"],
                        ["analysis:run", "project:read", "source:edit"],
                    )
                )
                if type(permissions) is not list or permissions not in allowed:
                    raise ValueError("Invalid internal output permissions")
                if (
                    "diagnostic" in protected_keys or draft_diagnostic
                ) and "analysis:run" not in permissions:
                    raise ValueError("Insufficient internal diagnostic permissions")
                raw = self._bytes(document)
                if len(raw) > _family_limit(family):
                    raw = self._bytes(
                        self._error(
                            document,
                            request_id,
                            "OUTPUT_LIMIT_EXCEEDED",
                            "Protected SDK response exceeds its wire size limit",
                        )
                    )
            except Exception:
                raw = self._bytes(
                    self._error(
                        document,
                        request_id,
                        "PROJECT_ACCESS_UNAVAILABLE",
                        "Protected output scope could not be verified",
                    )
                )
            else:
                # All transformations and size checks precede this last access
                # check. Write and flush run synchronously in this same worker.
                try:
                    self._runtime.state_context(
                        self._principal,
                        scope["project_id"],
                        permissions=frozenset(permissions),
                    )
                except Exception as exc:
                    forbidden = (
                        isinstance(exc, CoreError) and exc.code == "PROJECT_FORBIDDEN"
                    )
                    raw = self._bytes(
                        self._error(
                            document,
                            request_id,
                            "PROJECT_FORBIDDEN"
                            if forbidden
                            else "PROJECT_ACCESS_UNAVAILABLE",
                            "Current project access was denied"
                            if forbidden
                            else "Current project permissions could not be verified",
                        )
                    )
        remaining = memoryview(raw)
        while remaining:
            written = self._stream.write(remaining)
            if type(written) is not int or written <= 0 or written > len(remaining):
                raise OSError("Local MCP output write failed")
            remaining = remaining[written:]
        self._stream.flush()
        return len(text)

    async def write(self, text):
        import anyio

        return await anyio.to_thread.run_sync(
            self._write, text, abandon_on_cancel=False
        )

    async def flush(self):
        # The guarded write already flushed before releasing its worker.
        return None


async def serve(runtime, principal, scope=None):
    from mcp.server.stdio import stdio_server

    cancellations = _WorkerCancellations()
    server = create_server(runtime, principal, cancellations=cancellations, scope=scope)
    stdin = _BoundedInput(sys.stdin.buffer, cancellations)
    stdout = _GuardedOutput(sys.stdout.buffer, runtime, principal)
    async with stdio_server(stdin=stdin, stdout=stdout) as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Local Windows Rentgen MCP over stdio only", allow_abbrev=False
    )
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--scanner", type=Path)
    parser.add_argument("--project", action="append", metavar="PROJECT_UUID")
    parser.add_argument("--allow-tool", action="append", metavar="TOOL")
    args = parser.parse_args(argv)
    if args.project is not None and len(args.project) != 1:
        parser.error("--project must be supplied exactly once")
    try:
        scope = McpScope(
            project_id=args.project[0] if args.project else None,
            allowed_tools=args.allow_tool,
        )
    except ValueError as exc:
        parser.error(str(exc))
    try:
        import anyio

        principal = current_windows_principal()
        try:
            from rentgen_diagnostics.installed import InstalledDiagnostics

            diagnostics = InstalledDiagnostics()
        except ImportError:
            diagnostics = None
        runtime = LocalRuntime(
            args.registry,
            graph_builder=_InstalledBuilder(args.scanner),
            diagnostic_provider=diagnostics,
        )
        anyio.run(serve, runtime, principal, scope)
        return 0
    except KeyboardInterrupt:
        print(
            "Local MCP interrupted; reconcile any capture by its original operation receipt",
            file=sys.stderr,
        )
    except Exception:
        print(
            "Local MCP stopped; invalid transport input or local runtime failure",
            file=sys.stderr,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
