"""Deterministic file changes between two authorized, verified retained snapshots."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
import sys
from time import monotonic

from ._read_operation_budget import ReadOperationBudget
from .context import SnapshotRef
from .errors import CoreError
from .resolver import require_snapshot
from .sources import SnapshotReadLimits


MAX_DIFF_OUTPUT_BYTES = 2 * 1024**2


@dataclass(frozen=True)
class DiffOutputScope:
    """Immutable authority metadata, without a live session or thread owner.

    Only trusted adapters construct this value. It is not an authentication
    token and must never be accepted from request JSON.
    """
    project_id: str
    before_snapshot_id: str
    after_snapshot_id: str
    catalog_digest: str
    deadline: float

    def __post_init__(self):
        SnapshotRef(self.project_id, self.before_snapshot_id, self.before_snapshot_id)
        SnapshotRef(self.project_id, self.after_snapshot_id, self.after_snapshot_id)
        if (type(self.catalog_digest) is not str
                or re.fullmatch(r"[0-9a-f]{64}", self.catalog_digest) is None
                or type(self.deadline) is not float or not math.isfinite(self.deadline)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed snapshot comparison output scope required")


@dataclass(frozen=True)
class DiffOperationResult:
    value: dict
    output_scope: DiffOutputScope

    def __post_init__(self):
        if type(self.value) is not dict or type(self.output_scope) is not DiffOutputScope:
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed snapshot comparison result required")


def _catalog_pair_digest(before, after):
    return hashlib.sha256(json.dumps(
        [asdict(before), asdict(after)], sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")).hexdigest()


def _output_deadline(scope):
    if monotonic() >= scope.deadline:
        raise CoreError("SNAPSHOT_READ_DEADLINE_EXCEEDED", "Snapshot comparison deadline exceeded")


def authorize_diff_output(runtime, principal, scope):
    """Recheck the exact pair after serialization, including in another worker.

    The original budget/session cannot cross that worker boundary. Only its
    immutable deadline and catalog binding survive; authorization is fresh.
    """
    if type(scope) is not DiffOutputScope:
        raise CoreError("INVALID_QUERY_OPTIONS", "Typed snapshot comparison output scope required")
    _output_deadline(scope)
    ctx = runtime.state_context(principal, scope.project_id, permissions={"project:read"})
    _output_deadline(scope)
    with ctx.state.transaction(principal) as tx:
        tx.require_all({"project:read"})
        before = tx.get_snapshot(scope.before_snapshot_id)
        after = tx.get_snapshot(scope.after_snapshot_id)
    if _catalog_pair_digest(before, after) != scope.catalog_digest:
        raise CoreError("SNAPSHOT_CORRUPT", "Snapshot comparison catalog binding changed")
    _output_deadline(scope)


def _comparison_options(project_id, before, after, limit, cursor):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise CoreError("INVALID_QUERY_OPTIONS", "Comparison page size must be 1 to 100")
    binding = hashlib.sha256(json.dumps(
        [project_id, asdict(before), asdict(after), limit], sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    offset = 0
    if cursor is not None:
        match = (re.fullmatch(r"v1\.([0-9a-f]{64})\.([1-9][0-9]{0,4})", cursor)
                 if type(cursor) is str else None)
        if not match or match[1] != binding or int(match[2]) % limit:
            raise CoreError("INVALID_DIFF_CURSOR", "Cursor does not match this comparison")
        offset = int(match[2])
    return binding, offset


class _PairReadScope:
    def __init__(self, ctx, before, after, budget):
        self.ctx, self.before, self.after, self.budget = ctx, before, after, budget

    def checkpoint(self):
        # No callback into either live session: both graph owners can invoke
        # this same non-recursive authorization/catalog checkpoint.
        self.budget.checkpoint()
        with self.ctx.state.transaction(self.ctx.principal) as tx:
            tx.require_all({"project:read"})
            current = (tx.get_snapshot(self.before.snapshot.snapshot_id),
                       tx.get_snapshot(self.after.snapshot.snapshot_id))
        if current != (self.before, self.after):
            raise CoreError("SNAPSHOT_CORRUPT", "Snapshot comparison catalog binding changed")
        self.budget.checkpoint()


def _pair_page(left, right, before, after, *, limit, binding, offset, scope):
    """Count all changes and retain only this page, under a precharged envelope."""
    scope.checkpoint()
    previous_entries, current_entries = left.entries(), right.entries()
    # SourceEntry values already belong to the two manifest/session envelopes.
    # Reserve dictionaries, tuple keys, union/sort vector and bounded encodings
    # before constructing them. This is conservative accounting, not Python RSS.
    entries = len(previous_entries) + len(current_entries)
    envelope = entries * 4096 + sum(
        8 * (len(entry.ref.layer_id) + len(entry.ref.relative_path))
        for sequence in (previous_entries, current_entries) for entry in sequence
    ) + 16 * 1024**2
    old = new = keys = changes = result = encoded = None
    lease = scope.budget.reserve_images(envelope)
    try:
        old, new = {}, {}
        for sequence, index in ((previous_entries, old), (current_entries, new)):
            for position, entry in enumerate(sequence):
                if position % 128 == 0:
                    scope.checkpoint()
                index[(entry.ref.layer_id, entry.ref.relative_path)] = entry
        scope.checkpoint()
        keys = sorted(old.keys() | new.keys())
        scope.checkpoint()
        counts = dict(added=0, removed=0, modified=0, unchanged=0)
        changes, changed = [], 0
        for position, key in enumerate(keys):
            if position % 128 == 0:
                scope.checkpoint()
            previous, current = old.get(key), new.get(key)
            if previous is None:
                kind = "added"
            elif current is None:
                kind = "removed"
            elif (previous.ref.raw_sha256, previous.size_bytes) == (current.ref.raw_sha256, current.size_bytes):
                kind = "unchanged"
            else:
                kind = "modified"
            counts[kind] += 1
            if kind != "unchanged":
                if offset <= changed < offset + limit:
                    changes.append(dict(kind=kind, before=previous, after=current))
                changed += 1
        if offset and offset >= changed:
            raise CoreError("INVALID_DIFF_CURSOR", "Cursor exceeds comparison changes")
        result = dict(before_snapshot=before, after_snapshot=after,
            scope="source_bytes_by_layer_and_path", identity="source_path_only",
            counts=counts, changes=changes,
            next_cursor=f"v1.{binding}.{offset + limit}" if offset + limit < changed else None)
        scope.checkpoint()
        encoded = json.dumps(result, default=asdict, ensure_ascii=True, allow_nan=False).encode("ascii")
        if len(encoded) > 1048576:
            raise CoreError("DIFF_PAGE_LIMIT", "Comparison page exceeds 1 MiB; reduce --limit")
        scope.checkpoint()
        return result
    except BaseException:
        result = changes = None
        raise
    finally:
        old = new = keys = encoded = None
        previous_entries = current_entries = sequence = index = entry = None
        key = previous = current = counts = None
        lease.close()


def compare_retained_pair(runtime, principal, project_id, before_snapshot_id,
                          after_snapshot_id, *, limit=100, cursor=None,
                          cancelled=lambda: False, operation_limits=None):
    """One explicit pair read; Linux bypasses both eager ordinary resolvers.

    POSIX resource seams share conservative cumulative/held accounting. Windows
    retains its existing per-session resource contract, with this operation's
    original deadline and final pair authorization. Public adapters keep macOS
    admission closed; its real POSIX fixtures can exercise the internal seam.
    operation_limits is trusted composition, never a CLI/MCP request option.
    """
    from dataclasses import replace
    from ._posix_snapshot_session import PosixSnapshotLimits, open_posix_snapshot_session
    from ._verified_graph import VerifiedGraphLimits

    budget = ReadOperationBudget(operation_limits, cancelled=cancelled)
    owners, result, output_scope, pair = [], None, None, None
    try:
        budget.checkpoint()  # Before registry/state/catalog/source resolution.
        ctx = runtime.state_context(principal, project_id, permissions={"project:read"})
        budget.checkpoint()
        before_ref = SnapshotRef(project_id, before_snapshot_id, before_snapshot_id)
        after_ref = SnapshotRef(project_id, after_snapshot_id, after_snapshot_id)
        binding, offset = _comparison_options(project_id, before_ref, after_ref, limit, cursor)
        with ctx.state.transaction(principal) as tx:
            tx.require_all({"project:read"})
            before, after = tx.get_snapshot(before_snapshot_id), tx.get_snapshot(after_snapshot_id)
        pair = _PairReadScope(ctx, before, after, budget)
        pair.checkpoint()
        factory = runtime.graph_reader_factory
        if factory is None:
            try:
                from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory
            except ImportError as exc:
                raise CoreError("GRAPH_ADAPTER_UNAVAILABLE", "Install the supported rentgen_graph package") from exc
            factory = RentgenGraphReaderFactory()
        pair.checkpoint()
        if sys.platform == "win32":
            configured = replace(runtime, graph_reader_factory=factory)
            left = configured.resolve(principal, project_id, before_snapshot_id, authorize_read=pair.checkpoint)
            right = configured.resolve(principal, project_id, after_snapshot_id, authorize_read=pair.checkpoint)
            result = compare_snapshots(left, right, limit=limit, cursor=cursor)
        else:
            limits = PosixSnapshotLimits(copied_byte_budget=min(budget.limits.copied_bytes, 2560 * 1024**2),
                resident_byte_budget=min(budget.limits.image_bytes, 4 * 1024**3))
            graph_limits = VerifiedGraphLimits(image_buffer_budget=2 * 1024**3)
            def enter(snapshot):
                owner = open_posix_snapshot_session(state=ctx.state, principal=principal,
                    snapshot=snapshot, graph_reader_factory=factory, limits=limits,
                    graph_limits=graph_limits, authorize_read=pair.checkpoint, operation_budget=budget)
                session = owner.__enter__()
                owners.append(owner)
                return session
            left, right = enter(before_ref), enter(after_ref)
            result = _pair_page(left, right, before_ref, after_ref, limit=limit,
                                binding=binding, offset=offset, scope=pair)
            # Pop before exit: a refused successful exit has already attempted
            # its own cleanup and must not be entered/exited a second time.
            while owners:
                owners.pop().__exit__(None, None, None)
        pair.checkpoint()
        output_scope = DiffOutputScope(project_id, before_snapshot_id, after_snapshot_id,
            _catalog_pair_digest(before, after), float(budget.deadline))
        authorize_diff_output(runtime, principal, output_scope)
        budget.close()
        return DiffOperationResult(result, output_scope)
    except BaseException:
        primary = sys.exc_info()
        result = output_scope = None
        while owners:
            try:
                owners.pop().__exit__(*primary)
            except BaseException:
                pass  # Preserve the original entry/body/exit failure.
        try:
            budget.abort()
        except BaseException:
            pass  # Unacknowledged resources remain observable on the budget.
        raise


def compare_snapshots(before, after, *, limit=100, cursor=None):
    if before is None or after is None:
        raise CoreError(
            "CONTEXT_REQUIRED", "Two explicit project contexts are required"
        )
    if before.project_id != after.project_id or before.principal != after.principal:
        raise CoreError(
            "CONTEXT_PROJECT_MISMATCH", "Comparison requires one project and principal"
        )
    left_ref, right_ref = require_snapshot(before), require_snapshot(after)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise CoreError(
            "INVALID_QUERY_OPTIONS", "Comparison page size must be 1 to 100"
        )
    binding = hashlib.sha256(
        json.dumps(
            [before.project_id, asdict(left_ref), asdict(right_ref), limit],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    offset = 0
    if cursor is not None:
        match = (
            re.fullmatch(r"v1\.([0-9a-f]{64})\.([1-9][0-9]{0,4})", cursor)
            if isinstance(cursor, str)
            else None
        )
        if not match or match[1] != binding or int(match[2]) % limit:
            raise CoreError(
                "INVALID_DIFF_CURSOR", "Cursor does not match this comparison"
            )
        offset = int(match[2])
    limits = SnapshotReadLimits()
    with before.sources.read_session(limits=limits) as left, after.sources.read_session(
        limits=limits
    ) as right:

        def index(session):
            return {
                (entry.ref.layer_id, entry.ref.relative_path): entry
                for entry in session.entries()
            }

        old, new = index(left), index(right)
        counts = dict(added=0, removed=0, modified=0, unchanged=0)
        changes = []
        for position, key in enumerate(sorted(old.keys() | new.keys())):
            if position % 256 == 0:
                left.checkpoint()
                right.checkpoint()
            previous, current = old.get(key), new.get(key)
            if previous is None:
                kind = "added"
            elif current is None:
                kind = "removed"
            elif (previous.ref.raw_sha256, previous.size_bytes) == (
                current.ref.raw_sha256,
                current.size_bytes,
            ):
                kind = "unchanged"
            else:
                kind = "modified"
            counts[kind] += 1
            if kind != "unchanged":
                changes.append({"kind": kind, "before": previous, "after": current})
        if cursor is not None and offset >= len(changes):
            raise CoreError("INVALID_DIFF_CURSOR", "Cursor exceeds comparison changes")
        result = {
            "before_snapshot": left_ref,
            "after_snapshot": right_ref,
            "scope": "source_bytes_by_layer_and_path",
            "identity": "source_path_only",
            "counts": counts,
            "changes": changes[offset : offset + limit],
            "next_cursor": f"v1.{binding}.{offset + limit}"
            if offset + limit < len(changes)
            else None,
        }
        if (
            len(json.dumps(result, default=asdict, ensure_ascii=True).encode("ascii"))
            > 1048576
        ):
            raise CoreError(
                "DIFF_PAGE_LIMIT", "Comparison page exceeds 1 MiB; reduce --limit"
            )
        return result
