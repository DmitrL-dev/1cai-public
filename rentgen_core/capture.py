"""Authorized, bounded two-pass raw capture. This module never publishes a head."""
import codecs
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
from uuid import uuid4

from ._windows_source_tree import WindowsSourceTree, pinned_directory, read_retained
from .errors import CoreError
from .manifests import CapturedInput, build_source_document, sha256
from .snapshots import ProjectHead, validate_operation_id
from .source_paths import validate_inventory_paths

_reader_factory = WindowsSourceTree
_MAX_FILE_BYTES = 64 * 1024 * 1024
_MAX_TOTAL_BYTES = 1024 * 1024 * 1024
_MAX_ENTRIES = 100_000


def _limit():
    return CoreError(
        "SOURCE_CAPTURE_LIMIT_EXCEEDED", "Source capture exceeds its resource limit"
    )


@dataclass(frozen=True)
class CapturedSources:
    """Sealed source evidence for trusted adapters, independent of all live roots.

    The owner must not mutate staging. Hash verification detects corruption;
    this object is not a capability for untrusted request deserialization.
    """

    project_id: str
    source_digest: str
    entries: tuple[CapturedInput, ...]
    source_document: bytes
    staging_path: Path
    source_revision: int
    temporal_atomicity: str = "not_proven"

    def read_bytes(self, entry: CapturedInput) -> bytes:
        if entry not in self.entries:
            raise CoreError(
                "SOURCE_REF_MISMATCH", "Entry does not belong to captured sources"
            )
        path = self.staging_path / "sources" / entry.layer_id / entry.relative_path
        try:
            raw = read_retained(path, entry.size_bytes)
        except (CoreError, OSError) as exc:
            raise CoreError(
                "SNAPSHOT_CORRUPT", "Retained source is unavailable"
            ) from exc
        if len(raw) != entry.size_bytes or sha256(raw) != entry.raw_sha256:
            raise CoreError("SNAPSHOT_CORRUPT", "Retained source digest mismatch")
        return raw

    def decode_bsl(self, entry: CapturedInput) -> str:
        raw = self.read_bytes(entry)
        if entry.encoding not in ("utf-8", "utf-8-sig"):
            raise CoreError(
                "SOURCE_ENCODING_UNSUPPORTED", "BSL requires verified UTF-8 encoding"
            )
        try:
            return raw.decode(entry.encoding, errors="strict")
        except UnicodeError as exc:
            raise CoreError(
                "SOURCE_ENCODING_UNSUPPORTED", "BSL requires verified UTF-8 encoding"
            ) from exc


def _inventory(reader, configuration, exclusions):
    items = reader.inventory(configuration, exclusions)
    if len(items) > _MAX_ENTRIES:
        raise _limit()
    for layer in configuration.layers:
        validate_inventory_paths(
            item.relative_path
            for item in items
            if item.layer_id == layer.layer_id and item.relative_path
        )
    order = {layer.layer_id: layer.ordinal for layer in configuration.layers}
    return tuple(
        sorted(
            items, key=lambda i: (order[i.layer_id], i.relative_path.encode("utf-8"))
        )
    )


def _pass(reader, items, destination=None):
    entries, total = [], 0
    for item in items:
        if item.stamp.directory:
            continue
        if (
            item.stamp.size > _MAX_FILE_BYTES
            or total + item.stamp.size > _MAX_TOTAL_BYTES
        ):
            raise _limit()
        digest, size, prefix = hashlib.sha256(), 0, bytearray()
        decoder = codecs.getincrementaldecoder("utf-8-sig")(errors="strict")
        with ExitStack() as stack:
            output = None
            if destination is not None:
                path = destination / "sources" / item.layer_id / item.relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                output = stack.enter_context(path.open("xb"))
            chunks = stack.enter_context(reader.read(item))
            for chunk in chunks:
                size += len(chunk)
                if size > _MAX_FILE_BYTES or total + size > _MAX_TOTAL_BYTES:
                    raise _limit()
                prefix.extend(chunk[: max(0, 3 - len(prefix))])
                digest.update(chunk)
                if output is not None:
                    output.write(chunk)
                if decoder is not None:
                    try:
                        decoder.decode(chunk, final=False)
                    except UnicodeError:
                        decoder = None
            if decoder is not None:
                try:
                    decoder.decode(b"", final=True)
                except UnicodeError:
                    decoder = None
            if output is not None:
                output.flush()
                os.fsync(output.fileno())
        if size != item.stamp.size:
            raise CoreError(
                "SOURCE_CAPTURE_CHANGED", "Source size changed during reading"
            )
        total += size
        encoding = (
            ("utf-8-sig" if prefix == b"\xef\xbb\xbf" else "utf-8")
            if decoder is not None
            else None
        )
        entries.append(
            CapturedInput(
                item.layer_id, item.relative_path, digest.hexdigest(), size, encoding
            )
        )
    return tuple(entries)


def capture_sources(
    ctx, *, expected_head: ProjectHead, operation_id: str
) -> CapturedSources:
    """Capture standalone raw staging bytes; this public API never publishes."""
    with _capture_attempt(
        ctx, expected_head=expected_head, operation_id=operation_id, generation=False
    ) as captured:
        return captured


@contextmanager
def _capture_generation(ctx, *, expected_head: ProjectHead, operation_id: str):
    """Trusted publication attempt: keep candidate pins through the caller body.

    The physical UUID locator is independent of content identity. Once created,
    a failed candidate is retained as an orphan; this helper never removes a
    candidate that a caller might already have cataloged. Live roots close before
    yield. The caller owns graph build, full verification and catalog publication.
    """
    with _capture_attempt(
        ctx, expected_head=expected_head, operation_id=operation_id, generation=True
    ) as captured:
        yield captured


@contextmanager
def _capture_attempt(ctx, *, expected_head, operation_id, generation):
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    validate_operation_id(operation_id)
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"analysis:run"})
        head, configuration = tx.get_project_head(), tx.get_source_configuration()
        if (
            not isinstance(expected_head, ProjectHead)
            or expected_head.project_id != ctx.project_id
        ):
            raise CoreError("HEAD_CONFLICT", "Expected head does not match project")
        if expected_head.source_revision != configuration.revision:
            raise CoreError(
                "SOURCE_CONFIGURATION_CONFLICT",
                "Source configuration changed before capture",
            )
        if head != expected_head:
            raise CoreError("HEAD_CONFLICT", "Project head changed before capture")
    state_root = ctx.state.path.parent
    parent = state_root / ("generations" if generation else "staging")
    staging = parent / (str(uuid4()) if generation else operation_id)
    owned, sealed = False, False
    try:
        with ExitStack() as pins:
            with _reader_factory(ctx.source_root, state_root) as reader:
                exclusions = reader.configure(configuration)
                staging.parent.mkdir(exist_ok=True)
                reader._directory(staging.parent)
                try:
                    staging.mkdir()
                except FileExistsError as exc:
                    raise CoreError(
                        "OPERATION_CONFLICT", "Capture staging already exists"
                    ) from exc
                owned = True
                reader._directory(staging)
                if generation:
                    pins.enter_context(pinned_directory(staging))
                (staging / "sources").mkdir()
                (staging / "inputs").mkdir()
                first = _inventory(reader, configuration, exclusions)
                entries = _pass(reader, first, staging)
                second = _inventory(reader, configuration, exclusions)
                if second != first:
                    raise CoreError(
                        "SOURCE_CAPTURE_CHANGED",
                        "Source inventory changed between passes",
                    )
                if _pass(reader, second) != entries:
                    raise CoreError(
                        "SOURCE_CAPTURE_CHANGED",
                        "Source content changed between passes",
                    )
                if _inventory(reader, configuration, exclusions) != second:
                    raise CoreError(
                        "SOURCE_CAPTURE_CHANGED",
                        "Source inventory changed during verification",
                    )
            raw = build_source_document(
                ctx.project_id, configuration, exclusions, entries
            )
            sealed = True
            yield CapturedSources(
                ctx.project_id,
                sha256(raw),
                entries,
                raw,
                staging,
                configuration.revision,
            )
    except BaseException as failure:
        if owned and not generation:
            try:
                resolved = staging.resolve(strict=True)
                if resolved == staging.absolute() and resolved.parent == (
                    state_root / "staging"
                ).resolve(strict=True):
                    shutil.rmtree(resolved)
            except OSError:
                pass
        if isinstance(failure, OSError) and not sealed:
            raise CoreError(
                "SOURCE_ROOT_UNAVAILABLE", "Capture filesystem operation failed"
            ) from failure
        raise
