"""Bounded draft DTOs and core dispatch; identity comes from trusted transport."""
from dataclasses import replace
import json

from . import draft_editing, drafts, proposals
from .context import SnapshotRef
from .errors import CoreError
from .sources import SourceRef

WRITES = frozenset(
    {
        "rentgen_draft_save",
        "rentgen_draft_archive",
        "rentgen_draft_restore",
        "rentgen_draft_start",
        "rentgen_draft_edit",
    }
)
DESCRIPTIONS = {
    "rentgen_draft_start": "Create revision 1 of a shared draft from exact retained SourceRef bytes, up to 1 MiB, without sending the whole module. Returns a receipt. No source apply; reconcile original operation ID after interruption.",
    "rentgen_draft_edit": "Save a new revision using 1-16 exact, unique, non-overlapping text replacements against expected_revision. All matches refer to that original revision. Full candidate up to 1 MiB; each match/replacement up to 8 KiB UTF-8. No fuzzy matching or source apply.",
    "rentgen_draft_read": "Read a bounded chunk from an explicit immutable draft revision. For code review use encoding=utf-8 to receive readable text, preserved BOM/newlines and hashes; chunks end on character boundaries. Offsets/limits remain bytes, follow next_offset. Default base64 preserves legacy arbitrary-byte chunks. No source writes.",
    "rentgen_draft_check": "Run the installed trusted BSL profile on a complete explicit saved draft revision, up to 1 MiB, without resending its text. Requires editing and analysis rights. Tests not run; apply unavailable.",
    "rentgen_draft_save": "Save an exact retained-source proposal to shared draft history, with explicit operation ID and expected revision. Inline candidate limit 8 KiB. No source apply; after cancellation reconcile the original operation receipt.",
    "rentgen_draft_get": "Reopen a shared draft or exact historical revision. Returns result.draft with receipt and complete proposal; oversized reads fail explicitly. No source or graph access.",
    "rentgen_draft_list": "Page shared draft metadata by active or archived status. No source or graph access.",
    "rentgen_draft_history": "Page immutable shared draft history from newest revision. No source or graph access.",
    "rentgen_draft_archive": "Archive shared draft state using expected revision and operation ID. Preserves history and source files; reconcile receipt after cancellation.",
    "rentgen_draft_restore": "Restore archived shared draft state using expected revision and operation ID. Preserves history and source files; reconcile receipt after cancellation.",
    "rentgen_draft_receipt": "Reconcile the original draft operation without repeating a mutation. result.draft is its durable receipt or null if absent.",
}
TOOLS = frozenset(DESCRIPTIONS)
INLINE_LIMITS = proposals.ProposalLimits(1048576, 8192, 16384, 24576)


def schemas(object_schema, uuid, hash_schema, proposal):
    project = {"project_id": uuid}
    draft = {**project, "draft_id": uuid}
    revision = {"type": "integer", "minimum": 1, "maximum": 2**63 - 2}
    page = {"type": "integer", "minimum": 1, "maximum": 25}
    mutation = {
        **draft,
        "operation_id": uuid,
        "expected_revision": {**revision, "minimum": 0},
    }
    return {
        "rentgen_draft_start": object_schema(
            {
                **draft,
                "snapshot_id": hash_schema,
                "source_ref": proposal["properties"]["source_ref"],
                "operation_id": uuid,
                "title": {"type": "string", "minLength": 1, "maxLength": 240},
            }
        ),
        "rentgen_draft_edit": object_schema(
            {
                **mutation,
                "expected_revision": revision,
                "snapshot_id": hash_schema,
                "edits": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 16,
                    "items": object_schema(
                        {
                            "old_text": {
                                "type": "string",
                                "maxLength": 8192,
                            },
                            "new_text": {"type": "string", "maxLength": 8192},
                        }
                    ),
                },
            }
        ),
        "rentgen_draft_read": object_schema(
            {
                **draft,
                "revision": revision,
                "offset": {"type": "integer", "minimum": 0, "maximum": 1048576},
                "limit": {"type": "integer", "minimum": 1, "maximum": 65536},
                "encoding": {
                    "type": "string",
                    "pattern": "^(base64|utf-8)$",
                    "maxLength": 6,
                },
            },
            [*draft, "revision"],
        ),
        "rentgen_draft_check": object_schema(
            {
                **draft,
                "revision": revision,
                "snapshot_id": hash_schema,
                "diagnostics_profile": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 128,
                    "pattern": r"^[a-z0-9][a-z0-9._-]*$",
                },
            }
        ),
        "rentgen_draft_save": object_schema(
            {
                **mutation,
                "snapshot_id": hash_schema,
                "proposal": proposal,
                "title": {"type": "string", "minLength": 1, "maxLength": 240},
            }
        ),
        "rentgen_draft_get": object_schema({**draft, "revision": revision}, draft),
        "rentgen_draft_list": object_schema(
            {
                **project,
                "limit": page,
                "after_draft_id": uuid,
                "status": {
                    "type": "string",
                    "pattern": "^(active|archived)$",
                    "maxLength": 8,
                },
            },
            project,
        ),
        "rentgen_draft_history": object_schema(
            {**draft, "limit": page, "before_revision": revision}, draft
        ),
        "rentgen_draft_archive": object_schema(mutation),
        "rentgen_draft_restore": object_schema(mutation),
        "rentgen_draft_receipt": object_schema({**project, "operation_id": uuid}),
    }


def permissions(name):
    if name == "rentgen_draft_check":
        return frozenset({"project:read", "source:edit", "analysis:run"})
    return frozenset(
        {"project:read", "source:edit"} if name in WRITES else {"project:read"}
    )


def prepare(name, arguments, *, max_argument_bytes):
    """After strict schema validation, reject invalid saves before snapshot I/O."""
    values = {
        key: value
        for key, value in arguments.items()
        if key not in {"project_id", "snapshot_id"}
    }
    if (
        len(
            json.dumps(
                arguments,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        > max_argument_bytes
    ):
        raise CoreError("INVALID_ARGUMENT", "Draft tool arguments exceed 24 KiB")
    if name == "rentgen_draft_edit":
        draft_editing.validate_edits(values["edits"])
    if name == "rentgen_draft_start":
        drafts._title(values["title"])
        value = values["source_ref"]
        if len(value["relative_path"].encode("utf-8")) > 1024:
            raise CoreError(
                "INVALID_ARGUMENT", "Proposal source path exceeds 1024 UTF-8 bytes"
            )
        ref = SourceRef(
            SnapshotRef(**value["snapshot"]),
            value["layer_id"],
            value["relative_path"],
            value["raw_sha256"],
        )
        if ref.snapshot != SnapshotRef(
            arguments["project_id"], arguments["snapshot_id"], arguments["snapshot_id"]
        ):
            raise CoreError(
                "SOURCE_REF_MISMATCH",
                "SourceRef belongs to a different project or snapshot",
            )
        values["source_ref"] = ref
    if name == "rentgen_draft_save":
        drafts._title(values["title"])
        if (
            len(values["proposal"]["source_ref"]["relative_path"].encode("utf-8"))
            > 1024
        ):
            raise CoreError(
                "INVALID_ARGUMENT", "Proposal source path exceeds 1024 UTF-8 bytes"
            )
        raw = json.dumps(
            values.pop("proposal"),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        decoded = proposals._decode_proposal(raw, INLINE_LIMITS)
        selected = SnapshotRef(
            arguments["project_id"], arguments["snapshot_id"], arguments["snapshot_id"]
        )
        if decoded.source_ref.snapshot != selected:
            raise CoreError(
                "SOURCE_REF_MISMATCH",
                "Proposal belongs to a different project or snapshot",
            )
        values["raw_proposal"] = raw
    return values


def dispatch(runtime, principal, name, arguments, prepared, state_ctx):
    with state_ctx.state.transaction(principal) as tx:
        drafts._require(tx, write=name in WRITES)
        tx.require_all(permissions(name))
    if name in {
        "rentgen_draft_save",
        "rentgen_draft_start",
        "rentgen_draft_edit",
        "rentgen_draft_check",
    }:
        if name in {"rentgen_draft_edit", "rentgen_draft_check"}:
            selected = SnapshotRef(
                arguments["project_id"],
                arguments["snapshot_id"],
                arguments["snapshot_id"],
            )
            _, saved = draft_editing._stored(
                state_ctx,
                prepared["draft_id"],
                prepared.get("expected_revision", prepared.get("revision")),
            )
            if saved.source_ref.snapshot != selected:
                raise CoreError(
                    "SOURCE_REF_MISMATCH",
                    "Saved draft belongs to a different selected snapshot",
                )
        if runtime.graph_reader_factory is None:
            from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory

            runtime = replace(runtime, graph_reader_factory=RentgenGraphReaderFactory())
        ctx = runtime.resolve(
            principal, arguments["project_id"], arguments["snapshot_id"]
        )
        if name == "rentgen_draft_start":
            return draft_editing.start_draft(ctx, **prepared)
        if name == "rentgen_draft_edit":
            return draft_editing.edit_draft(ctx, **prepared)
        if name == "rentgen_draft_check":
            provider = runtime.diagnostic_provider
            if provider is None:
                raise CoreError(
                    "DIAGNOSTIC_RUNTIME_UNAVAILABLE",
                    "No trusted diagnostics provider is configured",
                )
            options = dict(prepared)
            adapter = provider.for_profile(options.pop("diagnostics_profile"))
            return draft_editing.check_draft(ctx, adapter=adapter, **options)
        return drafts.save_draft(ctx, **prepared)
    if name == "rentgen_draft_read":
        return draft_editing.read_draft(state_ctx, **prepared)
    if name == "rentgen_draft_get":
        value = drafts.get_draft(state_ctx, **prepared)
        return {
            "receipt": value["receipt"],
            "proposal": json.loads(value["canonical_json"]),
        }
    methods = {
        "rentgen_draft_list": drafts.list_drafts,
        "rentgen_draft_history": drafts.draft_history,
        "rentgen_draft_receipt": drafts.get_draft_receipt,
        "rentgen_draft_archive": drafts.archive_draft,
        "rentgen_draft_restore": drafts.restore_draft,
    }
    return methods[name](state_ctx, **prepared)
