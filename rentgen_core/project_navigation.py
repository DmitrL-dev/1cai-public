"""Versioned project navigation over an explicit, authorized retained snapshot.

These projections reuse the metadata reader. They neither consult a current
head nor turn a display label or observed UUID into an authoritative selector.
"""
from dataclasses import asdict
import re
import unicodedata

from . import metadata
from .errors import CoreError
from .resolver import require_snapshot
from .source_paths import validate_source_path

SCHEMA = 1
OUTPUT_LIMIT = 2 * 1024**2
OPERATIONS = frozenset({"metadata-summary", "metadata-search", "metadata-object"})
_LAYER = re.compile(r"[a-z][a-z0-9_-]{0,63}")


def _authorize(ctx):
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"project:read"})
    require_snapshot(ctx)


def _text(value, *, optional=False):
    if optional and value is None:
        return value
    if (
        type(value) is not str
        or len(value) > 256
        or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value)
        or len(value.encode("utf-8")) > 1024
    ):
        raise CoreError("INVALID_QUERY_OPTIONS", "Invalid navigation text filter")
    return value


def _layer(value, *, required=False):
    if value is None and not required:
        return value
    if type(value) is not str or _LAYER.fullmatch(value) is None:
        raise CoreError("INVALID_QUERY_OPTIONS", "An explicit source layer is required")
    return value


def _result(ctx, value):
    # Recheck after complete materialization; cached labels never grant access.
    _authorize(ctx)
    if not isinstance(value, dict) or value.get("snapshot") != asdict(ctx.snapshot):
        raise CoreError("METADATA_RESULT_MISMATCH", "Navigation snapshot binding differs")
    return {**value, "schema": SCHEMA}


def summary(ctx, *, layer_id=None):
    _authorize(ctx)
    return _result(ctx, metadata.metadata_summary(ctx, layer_id=_layer(layer_id)))


def search(ctx, *, query="", metadata_type=None, layer_id=None, limit=100):
    _authorize(ctx)
    query = _text(query)
    metadata_type = _text(metadata_type, optional=True)
    layer_id = _layer(layer_id)
    if type(limit) is not int or not 1 <= limit <= 200:
        raise CoreError("INVALID_QUERY_OPTIONS", "Navigation limit must be between 1 and 200")
    return _result(
        ctx,
        metadata.search_metadata(
            ctx, query, metadata_type=metadata_type, layer_id=layer_id, limit=limit
        ),
    )


def object_details(ctx, *, layer_id, relative_path):
    _authorize(ctx)
    layer_id = _layer(layer_id, required=True)
    validate_source_path(relative_path)
    return _result(
        ctx,
        metadata.get_metadata_object(ctx, layer_id=layer_id, relative_path=relative_path),
    )
