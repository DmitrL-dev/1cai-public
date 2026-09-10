"""Complete files first, then one catalog/head/receipt transaction; no automatic GC."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import os

from .context import SnapshotRef
from .errors import CoreError
from .graph import GraphBuildReceipt
from .manifests import build_manifest, sha256, parse_source_document
from .snapshots import (
    ProjectHead,
    SnapshotCatalogEntry,
    SnapshotLayer,
    validate_operation_id,
)
from .sources import _graph_metadata, _read, verify_generation, _MAX_DERIVED


def _boundary(name, **values):
    """Private fault-injection seam; never exposed as request options."""


def _receipt(ctx, expected_head, operation_id):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"analysis:run"})
        found = tx._find_publication(operation_id)
        if found is not None:
            if found[1] != expected_head:
                raise CoreError(
                    "OPERATION_CONFLICT", "Operation is bound to different inputs"
                )
            return found[0]
    return None


def _assemble(captured, receipt):
    if (
        not isinstance(receipt, GraphBuildReceipt)
        or receipt.source_digest != captured.source_digest
    ):
        raise CoreError(
            "GRAPH_INPUT_MISMATCH", "Builder receipt does not match capture"
        )
    path = captured.staging_path
    with _graph_metadata(path / "graph.sqlite3") as (raw, meta):
        graph = dict(
            asdict(receipt),
            relative_path="graph.sqlite3",
            raw_sha256=sha256(raw),
            sqlite_version=meta.get("sqlite_version"),
            quality="unavailable",
        )
    derived = []
    for name in ("inputs/callgraph.ndjson", "inputs/scanner-coverage.json"):
        raw = _read(path / name, _MAX_DERIVED)
        derived.append(
            dict(relative_path=name, raw_sha256=sha256(raw), size_bytes=len(raw))
        )
    return build_manifest(captured.source_document, graph, derived), graph


def _flush_outputs(path):
    from ._windows_source_tree import flush_owned

    # Captured sources were flushed by capture; these are newly built owned files.
    for name in (
        "graph.sqlite3",
        "inputs/callgraph.ndjson",
        "inputs/scanner-coverage.json",
        "manifest.json",
    ):
        flush_owned(path / name)


def capture_and_publish(ctx, *, expected_head, builder, operation_id):
    from .capture import _capture_generation

    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    validate_operation_id(operation_id)
    if (
        not isinstance(expected_head, ProjectHead)
        or expected_head.project_id != ctx.project_id
    ):
        raise CoreError(
            "HEAD_CONFLICT", "Expected head must belong to selected project"
        )
    previous = _receipt(ctx, expected_head, operation_id)
    if previous is not None:
        return previous
    result = None
    try:
        with _capture_generation(
            ctx, expected_head=expected_head, operation_id=operation_id
        ) as captured:
            result = _publish_captured(
                ctx, captured, expected_head, builder, operation_id
            )
        return result
    except Exception:
        if result is None:
            raise
        # A candidate handle-close error can also interrupt the final acknowledgment.
        reconciled = _reconcile(ctx, expected_head, operation_id, result.snapshot)
        if reconciled is not None:
            return reconciled
        raise CoreError(
            "PUBLICATION_OUTCOME_UNKNOWN",
            "Committed receipt is unavailable",
            details={"operation_id": operation_id},
        )


def _reconcile(ctx, expected_head, operation_id, snapshot):
    try:
        with ctx.state.transaction(ctx.principal) as tx:
            found = tx._find_publication(operation_id)
    except Exception as exc:
        raise CoreError(
            "PUBLICATION_OUTCOME_UNKNOWN",
            "Publication receipt could not be read",
            details={"operation_id": operation_id},
        ) from exc
    if found is not None:
        if found[1] != expected_head or found[0].snapshot != snapshot:
            raise CoreError(
                "OPERATION_CONFLICT", "Publication receipt binding does not match"
            )
        return found[0]
    return None


def _publish_captured(ctx, captured, expected_head, builder, operation_id):
    path = captured.staging_path
    _boundary("after_capture", ctx=ctx, captured=captured)
    (path / "build-work").mkdir()
    try:
        receipt = builder.build(
            captured, output_path=path / "graph.sqlite3", work_dir=path / "build-work"
        )
    except CoreError:
        raise
    except Exception as exc:
        raise CoreError("GRAPH_BUILD_FAILED", "Captured graph build failed") from exc
    manifest, graph = _assemble(captured, receipt)
    snapshot = SnapshotRef(ctx.project_id, sha256(manifest), sha256(manifest))
    with (path / "manifest.json").open("xb") as stream:
        stream.write(manifest)
        stream.flush()
        os.fsync(stream.fileno())
    catalog = SnapshotCatalogEntry(
        snapshot,
        captured.source_digest,
        graph["raw_sha256"],
        "generations/" + path.name,
        1,
        datetime.now(timezone.utc).isoformat(),
    )
    document = parse_source_document(captured.source_document)
    layers = tuple(
        SnapshotLayer(
            **{
                key: layer[key]
                for key in (
                    "layer_id",
                    "ordinal",
                    "kind",
                    "configuration_uuid",
                    "identity_status",
                    "source_format",
                )
            }
        )
        for layer in document["layers"]
    )
    _boundary("before_complete", ctx=ctx, catalog=catalog)
    _flush_outputs(path)
    verify_generation(path, catalog)
    _boundary("after_complete", ctx=ctx, catalog=catalog)
    # Physical attempt UUID is independent of content identity. Reuse only a
    # catalogued and verified locator; never overwrite an old generation.
    with ctx.state.transaction(ctx.principal) as tx:
        try:
            existing = tx.get_snapshot(snapshot.snapshot_id)
        except CoreError as exc:
            if exc.code != "SNAPSHOT_NOT_FOUND":
                raise
            existing = None
    if existing is not None:
        verify_generation(ctx.state.path.parent / existing.generation_relpath, existing)
        catalog = replace(catalog, generation_relpath=existing.generation_relpath)
    _boundary("before_state_transaction", ctx=ctx, catalog=catalog)
    commit_attempted = False
    try:
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            tx.require_all({"analysis:run"})
            found = tx._find_publication(operation_id)
            if found is not None:
                if found[1] != expected_head or found[0].snapshot != snapshot:
                    raise CoreError(
                        "OPERATION_CONFLICT", "Operation is bound to different inputs"
                    )
                return found[0]
            current = tx.get_project_head()
            if current.source_revision != expected_head.source_revision:
                raise CoreError(
                    "SOURCE_CONFIGURATION_CONFLICT", "Source configuration changed"
                )
            if current != expected_head:
                raise CoreError("HEAD_CONFLICT", "Project head changed")
            try:
                authoritative = tx.get_snapshot(snapshot.snapshot_id)
            except CoreError as exc:
                if exc.code != "SNAPSHOT_NOT_FOUND":
                    raise
                authoritative = None
            if authoritative != existing:
                # Every legitimate catalog insertion advances head in the same
                # transaction; disappearance is also invalid with unchanged head.
                raise CoreError(
                    "STATE_CORRUPT", "Catalog changed without a head transition"
                )
            if authoritative is not None:
                catalog = replace(
                    catalog, generation_relpath=authoritative.generation_relpath
                )
            result = tx.commit_publication(
                expected_head=expected_head,
                catalog=catalog,
                layers=layers,
                operation_id=operation_id,
            )
            _boundary("before_commit", ctx=ctx, catalog=catalog)
            commit_attempted = True
        _boundary("after_commit", ctx=ctx, catalog=catalog)
        return result
    except Exception:
        if not commit_attempted:
            raise
        # The previous context manager has closed its SQLite connection. A later
        # head cannot change what this exact operation's durable receipt proves.
        reconciled = _reconcile(ctx, expected_head, operation_id, snapshot)
        if reconciled is not None:
            return reconciled
        raise
