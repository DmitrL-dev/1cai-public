"""Read-only generation tools and request-bound stdio disclosure authority.

Only immutable values cross workers. Retained sessions finish before encoding;
the final output worker rechecks current permissions and verified catalog binding.
"""
from dataclasses import asdict
import hashlib
import json
import re
import sqlite3
import sys

from .context import validate_project_id
from .errors import CoreError
from .snapshots import get_generation_attribution, validate_generation_relpath, validate_operation_id

TOOLS = {
    "rentgen_generation_attribution": "generation_attribution",
    "rentgen_generation_verify": "generation_verification",
}
MAX_OUTPUT_BYTES = 131072
META = "rentgenOutputScope"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def authorize(runtime, principal, scope):
    ctx = runtime.state_context(principal, scope["project_id"], permissions={"project:read"})
    if scope["catalog_sha256"] is not None:
        with ctx.state.transaction(principal) as tx:
            tx.require_all({"project:read"})
            if digest(asdict(tx.get_snapshot(scope["snapshot_id"]))) != scope["catalog_sha256"]:
                raise CoreError("SNAPSHOT_CORRUPT", "Generation catalog binding changed")


def _reply(payload, scope, *, error=False):
    from mcp.types import CallToolResult, JSONRPCResponse, TextContent

    if error:
        payload = {"error": dict(payload["error"], details=dict(payload["error"].get("details", {}),
            operation=next(name for name, kind in TOOLS.items() if kind == scope["kind"])))}
    bound = dict(scope, payload_sha256=digest(payload))
    result = CallToolResult(content=[TextContent(type="text", text=canonical(payload))],
        structuredContent=payload, isError=error, _meta={META: bound})
    wire = JSONRPCResponse(jsonrpc="2.0", id=scope["protocol_request_id"],
        result=result.model_dump(by_alias=True, mode="json", exclude_none=True))
    if len(wire.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")) + 1 > MAX_OUTPUT_BYTES:
        raise CoreError("OUTPUT_LIMIT_EXCEEDED", "Generation SDK response exceeds its wire size limit")
    return result


def execute(runtime, principal, name, arguments, request_id, protocol_request_id):
    # Authentication precedes adapter composition and retained IO.
    ctx = runtime.state_context(principal, arguments["project_id"], permissions={"project:read"})
    scope = dict(family="generation", permissions=["project:read"], project_id=ctx.project_id,
        generation_relpath=arguments["generation_relpath"], kind=TOOLS[name], request_id=request_id,
        protocol_request_id=0 if protocol_request_id is None else protocol_request_id,
        snapshot_id=None, catalog_sha256=None)
    try:
        if name == "rentgen_generation_attribution":
            value = get_generation_attribution(ctx, scope["generation_relpath"])
        else:
            from .generation_verification import verify_catalog_generation

            factory = runtime.graph_reader_factory
            if sys.platform == "linux" and factory is None:
                from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory

                factory = RentgenGraphReaderFactory()
            value = verify_catalog_generation(ctx, scope["generation_relpath"], graph_reader_factory=factory)
            scope.update(snapshot_id=value.catalog.snapshot.snapshot_id, catalog_sha256=digest(asdict(value.catalog)))
        reply = _reply(dict(result={scope["kind"]: asdict(value)}, request_id=request_id), scope)
        authorize(runtime, principal, scope)
        return reply
    except Exception as exc:
        if isinstance(exc, CoreError):
            error = exc
        elif isinstance(exc, ImportError):
            error = CoreError("GRAPH_ADAPTER_UNAVAILABLE", "Install the supported rentgen_graph package")
        else:
            error = CoreError("LOCAL_OPERATION_FAILED", "Generation diagnostic failed; no verified result is asserted")
    # Error disclosure needs permission, but cannot require a corrupt catalog.
    scope.update(snapshot_id=None, catalog_sha256=None)
    reply = _reply(error.to_dict(request_id), scope, error=True)
    try:
        authorize(runtime, principal, scope)
    except CoreError as exc:
        reply = _reply(exc.to_dict(request_id), scope, error=True)
    except (OSError, sqlite3.Error):
        reply = _reply(CoreError("PROJECT_ACCESS_UNAVAILABLE", "Current project access could not be verified").to_dict(request_id), scope, error=True)
    return reply


def validate(result, scope, protocol_request_id):
    fields = {"family", "permissions", "project_id", "generation_relpath", "kind", "request_id",
              "protocol_request_id", "snapshot_id", "catalog_sha256", "payload_sha256"}
    if type(scope) is not dict or set(scope) != fields or scope["family"] != "generation":
        raise ValueError("Invalid generation output scope")
    if scope["permissions"] != ["project:read"] or scope["kind"] not in TOOLS.values():
        raise ValueError("Invalid generation output authority")
    validate_project_id(scope["project_id"])
    validate_generation_relpath(scope["generation_relpath"])
    validate_operation_id(scope["request_id"])
    if type(scope["protocol_request_id"]) is not type(protocol_request_id) or scope["protocol_request_id"] != protocol_request_id:
        raise ValueError("Generation response belongs to another request")
    for field in ("payload_sha256", "snapshot_id", "catalog_sha256"):
        value = scope[field]
        if value is None and field != "payload_sha256":
            continue
        if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
            raise ValueError("Invalid generation output digest")
    if (scope["snapshot_id"] is None) != (scope["catalog_sha256"] is None):
        raise ValueError("Incomplete generation catalog binding")
    if type(result) is not dict or set(result) != {"content", "structuredContent", "isError", "_meta"}:
        raise ValueError("Incomplete generation SDK result")
    if result["_meta"] != {META: scope} or type(result["isError"]) is not bool:
        raise ValueError("Invalid generation SDK metadata")
    payload = result["structuredContent"]
    if type(payload) is not dict or result["content"] != [{"type": "text", "text": canonical(payload)}]:
        raise ValueError("Generation SDK representations differ")
    if digest(payload) != scope["payload_sha256"]:
        raise ValueError("Generation output changed")
    if result["isError"]:
        if set(payload) != {"error"} or payload["error"]["request_id"] != scope["request_id"] or scope["snapshot_id"] is not None:
            raise ValueError("Invalid generation error binding")
        if TOOLS.get(payload["error"]["details"].get("operation")) != scope["kind"]:
            raise ValueError("Invalid generation error operation")
        return
    if set(payload) != {"result", "request_id"} or payload["request_id"] != scope["request_id"] or set(payload["result"]) != {scope["kind"]}:
        raise ValueError("Invalid generation result binding")
    value = payload["result"][scope["kind"]]
    catalog = value["catalog"]
    if value["removal_permitted"] is not False:
        raise ValueError("Generation result cannot grant removal")
    if scope["kind"] == "generation_attribution":
        if scope["snapshot_id"] is not None or value["generation_relpath"] != scope["generation_relpath"] or value["observed_head"]["project_id"] != scope["project_id"] or value["physical_state"] != "not_inspected":
            raise ValueError("Invalid attribution binding")
    elif catalog is None or scope["snapshot_id"] != catalog["snapshot"]["snapshot_id"] or digest(catalog) != scope["catalog_sha256"] or value["physical_state"] != "verified_at_read":
        raise ValueError("Invalid verification binding")
    if catalog is not None and (catalog["snapshot"]["project_id"] != scope["project_id"] or catalog["generation_relpath"] != scope["generation_relpath"]):
        raise ValueError("Generation catalog belongs to another request")


def protected_payload(payload):
    """Recognize both success and error if private SDK metadata was lost."""
    if type(payload) is not dict:
        return False
    result = payload.get("result")
    if type(result) is dict and set(TOOLS.values()) & result.keys():
        return True
    error = payload.get("error")
    details = error.get("details") if type(error) is dict else None
    operation = details.get("operation") if type(details) is dict else None
    return type(operation) is str and operation in TOOLS


def guarded_bytes(document, result, scope, runtime, principal, encode, error_document):
    """Encode first, reauthorize second; caller synchronously writes these bytes."""
    from uuid import uuid4

    request_id = str(uuid4())
    try:
        validate(result, scope, document["id"])
        request_id = scope["request_id"]
        del result["_meta"]
        raw = encode(document)
        if len(raw) > MAX_OUTPUT_BYTES:
            raw = encode(error_document(document, request_id, "OUTPUT_LIMIT_EXCEEDED", "Generation SDK response exceeds its wire size limit"))
    except Exception:
        return encode(error_document(document, request_id, "PROJECT_ACCESS_UNAVAILABLE", "Generation output scope could not be verified"))
    try:
        authorize(runtime, principal, scope)
    except CoreError as exc:
        return encode(error_document(document, request_id, exc.code, exc.message))
    except Exception:
        return encode(error_document(document, request_id, "PROJECT_ACCESS_UNAVAILABLE", "Current generation authority could not be verified"))
    return raw
