"""Bounded physical verification of one authorized catalog-referenced locator."""
from dataclasses import dataclass
import sqlite3
import sys
from typing import Literal

from .capabilities import require_operation
from .errors import CoreError
from .snapshots import SnapshotCatalogEntry, get_generation_attribution


@dataclass(frozen=True)
class GenerationVerification:
    catalog: SnapshotCatalogEntry
    validation: dict
    physical_state: Literal["verified_at_read"] = "verified_at_read"
    removal_permitted: Literal[False] = False


def verify_catalog_generation(ctx, generation_relpath, *, graph_reader_factory=None):
    """Verify retained bytes only; no discovery, live source access or cleanup lease.

    Windows holds expected files; Linux verifies private copies. Their bounded
    session summaries describe observations, not atomic filesystem/state reads.
    The graph adapter is supplied by the composition root for Linux verification.
    """
    require_operation("generation-verify")
    attribution = get_generation_attribution(ctx, generation_relpath)
    catalog = attribution.catalog
    if catalog is None:
        raise CoreError("GENERATION_UNREFERENCED", "Generation has no catalog reference")

    def authorize():
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all({"project:read"})
            if tx.get_snapshot(catalog.snapshot.snapshot_id) != catalog:
                raise CoreError("SNAPSHOT_CORRUPT", "Generation catalog binding changed")

    if sys.platform == "win32":
        from .sources import SnapshotReadLimits, SnapshotReadSession, SnapshotSources

        sources = SnapshotSources(catalog.snapshot, ctx.state, ctx.principal,
                                  ctx.state.path.parent / catalog.generation_relpath)
        session = SnapshotReadSession(sources, SnapshotReadLimits(), expected_catalog=catalog)
    else:
        from ._posix_snapshot_session import PosixSnapshotLimits, open_posix_snapshot_session
        from ._verified_graph import VerifiedGraphLimits

        session = open_posix_snapshot_session(
            state=ctx.state, principal=ctx.principal, snapshot=catalog.snapshot,
            graph_reader_factory=graph_reader_factory,
            limits=PosixSnapshotLimits(copied_byte_budget=2560 * 1024**2,
                                       resident_byte_budget=4 * 1024**3),
            graph_limits=VerifiedGraphLimits(image_buffer_budget=2 * 1024**3),
            authorize_read=authorize, expected_catalog=catalog)
    try:
        with session:
            pass
    except (OSError, sqlite3.Error) as exc:
        raise CoreError("SNAPSHOT_CORRUPT", "Retained generation is unavailable or invalid") from exc
    validation = session.validation_summary
    authorize()
    return GenerationVerification(catalog, validation)
