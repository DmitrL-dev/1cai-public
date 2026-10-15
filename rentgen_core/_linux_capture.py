"""Linux fixed-scanner orchestration and short publication CAS, without path fallback."""
from dataclasses import asdict, dataclass, field, replace
import os
from pathlib import Path
import platform
import re
import sys
from threading import get_ident
from time import monotonic

from ._linux_scanner import LinuxScannerLimits, open_linux_scanner
from ._posix_capture_candidate import PosixCandidateLimits
from ._posix_captured_sources import PosixCapturedLimits, capture_posix_sources
from ._posix_generation import CompletePosixGeneration, PosixGenerationLimits, open_posix_generation
from ._posix_live_tree import PosixLiveLimits
from ._posix_snapshot_session import PosixSnapshotLimits, open_posix_snapshot_session
from ._verified_graph import VerifiedGraphLimits
from .context import ProjectContext
from .errors import CoreError
from .publication import _receipt, _reconcile
from .snapshots import ProjectHead, validate_operation_id
from .source_configuration import SourceConfiguration


def _boundary(name, **values):
    """Private fault-injection seam; not a request option or generic runner."""


def _limit():
    return CoreError("SOURCE_CAPTURE_LIMIT_EXCEEDED", "Linux capture resource budget exceeded")


@dataclass(frozen=True)
class LinuxCaptureLimits:
    """Configured parent byte images; child Go memory target is independently soft."""
    resident_byte_budget: int = 512 * 1024**2
    max_source_bytes: int = 64 * 1024**2
    max_file_bytes: int = 16 * 1024**2
    max_source_entries: int = 4096
    max_inventory_items: int = 20_000
    max_manifest_bytes: int = 8 * 1024**2
    max_stdout_bytes: int = 12 * 1024**2
    max_coverage_bytes: int = 4 * 1024**2
    max_graph_bytes: int = 64 * 1024**2
    max_retained_descriptors: int = 4096
    max_relative_components: int = 128
    max_transport_reads: int = 65_536
    graph_cache_kib: int = 8192
    max_vm_steps: int = 10_000_000
    go_memory_target_bytes: int = 256 * 1024**2
    phase_deadline_seconds: int = 30
    operation_deadline_seconds: int = 120

    def __post_init__(self):
        maxima = (2 * 1024**3, 1024**3, 64 * 1024**2, 20_000, 200_000,
                  64 * 1024**2, 64 * 1024**2, 64 * 1024**2, 1024**3,
                  65_536, 128, 1_000_000, 65_536, 100_000_000,
                  4 * 1024**3, 30, 120)
        if any(type(value) is not int or not 1 <= value <= maximum
               for value, maximum in zip(asdict(self).values(), maxima)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed bounded Linux capture limits required")
        if self.max_file_bytes > self.max_source_bytes or self.max_source_entries > self.max_inventory_items:
            raise CoreError("INVALID_QUERY_OPTIONS", "Inconsistent Linux source limits")

    def _scanner_reservation(self):
        return (2 * (self.max_stdout_bytes + self.max_coverage_bytes + 65_536)
                + 256 * self.max_transport_reads + 65_536 + 512)


@dataclass(frozen=True)
class LinuxCaptureBackend:
    scanner_executable: Path | None = None
    scanner_sha256: str | None = None
    limits: LinuxCaptureLimits = field(default_factory=LinuxCaptureLimits)

    def __post_init__(self):
        if type(self.limits) is not LinuxCaptureLimits:
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed Linux capture limits required")
        executable, digest = self.scanner_executable, self.scanner_sha256
        if executable is None and digest is None:
            return  # Receipt replay needs no installed scanner.
        if (not isinstance(executable, Path) or not executable.is_absolute()
                or ".." in executable.parts or len(executable.parts) > 128 or type(digest) is not str
                or re.fullmatch("[0-9a-f]{64}", digest) is None):
            raise CoreError("INVALID_QUERY_OPTIONS", "Absolute scanner and exact SHA-256 required")

    def capture(self, ctx, *, expected_head, operation_id,
                authorize_capture=lambda: None, cancelled=lambda: False):
        deadline = monotonic() + self.limits.operation_deadline_seconds
        _validate_inputs(ctx, expected_head, operation_id, authorize_capture, cancelled)
        previous = _receipt(ctx, expected_head, operation_id)
        if previous is not None:
            return previous
        # Deliberately after the authorized durable receipt lookup, before any
        # source/executable IO. A replay does not need the old head or scanner.
        if sys.platform != "linux" or platform.machine() not in {"x86_64", "amd64"}:
            raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "Linux/amd64 capture runtime is required")
        if self.scanner_executable is None:
            raise CoreError("GRAPH_ADAPTER_UNAVAILABLE", "An owned Linux scanner is required for new capture")
        gate = _CaptureGate(ctx, expected_head, self.limits, authorize_capture, cancelled, deadline=deadline)
        gate.check()
        complete, configuration = _capture_complete(self, ctx, expected_head, gate)
        # Both copied and complete-generation owners are now closed. Nothing
        # checking the old head remains around the state-changing transaction.
        return _commit_complete(ctx, complete, configuration=configuration,
            operation_id=operation_id, limits=self.limits, gate=gate)


def _validate_inputs(ctx, head, operation_id, authorize, cancelled):
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    if type(ctx) is not ProjectContext:
        raise CoreError("INVALID_QUERY_OPTIONS", "Trusted project context required")
    validate_operation_id(operation_id)
    if type(head) is not ProjectHead or head.project_id != ctx.project_id:
        raise CoreError("HEAD_CONFLICT", "Expected head must belong to selected project")
    if not callable(authorize) or not callable(cancelled):
        raise CoreError("INVALID_QUERY_OPTIONS", "Trusted capture callbacks required")


class _CaptureGate:
    def __init__(self, ctx, head, limits, authorize, cancelled, *, deadline=None):
        self.ctx, self.head = ctx, head
        self.deadline = monotonic() + limits.operation_deadline_seconds if deadline is None else deadline
        self.authorize, self.cancelled = authorize, cancelled
        self.configuration = None
        self.owner, self.busy = (os.getpid(), get_ident()), False

    def tick(self):
        self.owner_deadline()
        if self.cancelled():
            raise CoreError("GRAPH_SCANNER_CANCELLED", "Linux capture was cancelled")
        self.owner_deadline()

    def owner_deadline(self):
        """Pure check usable inside the short SQL transaction; no callbacks/IO."""
        if self.owner != (os.getpid(), get_ident()):
            raise CoreError("SOURCE_READ_SESSION_INVALID", "Linux capture operation belongs to another owner")
        if monotonic() >= self.deadline:
            raise CoreError("SOURCE_READ_DEADLINE_EXCEEDED", "Linux capture operation deadline exceeded")

    def check(self):
        if self.busy:
            raise CoreError("SOURCE_READ_SESSION_INVALID", "Linux capture authorization is nonreentrant")
        self.busy = True
        try:
            self.tick(); self.authorize(); self.tick()
            with self.ctx.state.transaction(self.ctx.principal) as tx:
                tx.require_all({"analysis:run"})
                current, configuration = tx.get_project_head(), tx.get_source_configuration()
            if current.source_revision != self.head.source_revision:
                raise CoreError("SOURCE_CONFIGURATION_CONFLICT", "Source configuration changed during Linux capture")
            if current != self.head:
                raise CoreError("HEAD_CONFLICT", "Project head changed during Linux capture")
            if self.configuration is not None and configuration != self.configuration:
                raise CoreError("SOURCE_CONFIGURATION_CONFLICT", "Source configuration changed during Linux capture")
            self.configuration = configuration
            self.tick()
        finally:
            self.busy = False


def _capture_complete(backend, ctx, head, gate):
    from rentgen_graph.posix_snapshot_adapter import PosixGraphLimits, build_posix_graph_bundle
    from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory
    limits = backend.limits
    captured = generation = scanner = scanner_output = bundle = None
    complete = configuration = None
    try:
        captured = capture_posix_sources(state=ctx.state, principal=ctx.principal,
            source_root=ctx.source_root, expected_head=head,
            candidate_limits=PosixCandidateLimits(resident_byte_budget=limits.resident_byte_budget,
                max_source_bytes=limits.max_source_bytes, max_source_entries=limits.max_source_entries,
                max_manifest_bytes=limits.max_manifest_bytes,
                max_retained_descriptors=limits.max_retained_descriptors,
                max_relative_components=limits.max_relative_components,
                max_builder_read_bytes=limits.max_source_bytes,
                deadline_seconds=limits.phase_deadline_seconds),
            live_limits=PosixLiveLimits(max_total_bytes=limits.max_source_bytes,
                max_file_bytes=limits.max_file_bytes, max_entries=min(100_000, limits.max_inventory_items),
                max_retained_descriptors=max(1, limits.max_retained_descriptors//2),
                max_relative_components=limits.max_relative_components,
                deadline_seconds=limits.phase_deadline_seconds),
            limits=PosixCapturedLimits(resident_byte_budget=limits.resident_byte_budget,
                max_source_bytes=limits.max_source_bytes, max_source_entries=limits.max_source_entries,
                max_read_bytes=2*limits.max_source_bytes, max_manifest_bytes=limits.max_manifest_bytes,
                deadline_seconds=limits.operation_deadline_seconds),
            authorize_capture=gate.check)
        with captured:
            configuration = captured._configuration
            source_total = sum(entry.size_bytes for entry in captured.entries)
            source_document_size = len(captured.source_document)
            # Captured immutable source/manifest images coexist with transport
            # chunks and joined scanner outputs. Go memory is a separate target.
            scanner_reservation = limits._scanner_reservation()
            sealed_executable_reservation = 32*1024**2 + 2*65_536
            if source_total + 9*source_document_size + scanner_reservation + sealed_executable_reservation > limits.resident_byte_budget:
                raise _limit()
            # Scanner retains the complete executable ancestor chain, sealed
            # image, root duplicate, selector and bounded Popen/pipe transport.
            scanner_descriptors = len(backend.scanner_executable.parts) + 32
            generation_descriptors = limits.max_retained_descriptors - scanner_descriptors
            if generation_descriptors < 1:
                raise _limit()
            generation = open_posix_generation(state=ctx.state, principal=ctx.principal,
                expected_head=head, captured=captured,
                limits=PosixGenerationLimits(resident_byte_budget=limits.resident_byte_budget,
                    max_generation_bytes=min(2560*1024**2, limits.max_source_bytes + limits.max_graph_bytes
                        + limits.max_stdout_bytes + limits.max_coverage_bytes + limits.max_manifest_bytes),
                    max_manifest_bytes=limits.max_manifest_bytes,
                    max_derived_bytes=max(limits.max_stdout_bytes, limits.max_coverage_bytes),
                    max_source_entries=limits.max_source_entries,
                    max_inventory_items=limits.max_inventory_items,
                    max_retained_descriptors=generation_descriptors,
                    max_relative_components=limits.max_relative_components,
                    deadline_seconds=limits.phase_deadline_seconds), authorize_capture=gate.check)
            with generation:
                scanner = open_linux_scanner(executable=backend.scanner_executable,
                    executable_sha256=backend.scanner_sha256, scan_directory=generation.scan_directory,
                    limits=LinuxScannerLimits(resident_byte_budget=scanner_reservation,
                        max_stdout_bytes=limits.max_stdout_bytes, max_coverage_bytes=limits.max_coverage_bytes,
                        max_source_bytes=limits.max_source_bytes, max_file_bytes=limits.max_file_bytes,
                        max_files=limits.max_source_entries, max_entries=limits.max_inventory_items,
                        max_depth=limits.max_relative_components,
                        max_transport_reads=limits.max_transport_reads,
                        go_memory_target_bytes=limits.go_memory_target_bytes,
                        deadline_seconds=limits.phase_deadline_seconds),
                    authorize=gate.check, cancelled=gate.cancelled)
                with scanner:
                    scanner_output = scanner.scan()
                scanner = None  # Its successful exit precedes graph processing.
                gate.check()
                graph_budget = limits.resident_byte_budget - source_document_size
                if graph_budget < 1:
                    raise _limit()
                bundle = build_posix_graph_bundle(captured, scanner_output,
                    limits=PosixGraphLimits(image_buffer_budget=graph_budget,
                        max_source_bytes=limits.max_source_bytes,
                        max_scanner_output_bytes=limits.max_stdout_bytes+limits.max_coverage_bytes,
                        max_graph_bytes=limits.max_graph_bytes, max_files=limits.max_source_entries,
                        max_vm_steps=limits.max_vm_steps, cache_kib=limits.graph_cache_kib,
                        deadline_seconds=limits.phase_deadline_seconds), authorize=gate.check)
                scanner_output = None
                generation.seal(bundle, graph_reader_factory=RentgenGraphReaderFactory(),
                    graph_limits=VerifiedGraphLimits(image_buffer_budget=2*limits.max_graph_bytes,
                        max_graph_bytes=limits.max_graph_bytes, max_vm_steps=limits.max_vm_steps,
                        cache_kib=limits.graph_cache_kib, deadline_seconds=limits.phase_deadline_seconds))
                bundle = None
            complete = generation.result
        gate.check()
        _boundary("after_generation_complete", ctx=ctx, complete=complete)
        return complete, configuration
    finally:
        captured = generation = scanner = scanner_output = bundle = None
        complete = configuration = None


def _catalog_or_none(tx, snapshot):
    try:
        return tx.get_snapshot(snapshot.snapshot_id)
    except CoreError as exc:
        if exc.code != "SNAPSHOT_NOT_FOUND":
            raise
        return None


def _commit_complete(ctx, complete, *, configuration, operation_id, limits, gate):
    """Trusted storage seam: only a successfully closed complete-generation proof."""
    if (type(complete) is not CompletePosixGeneration or complete.published is not False
            or complete.status != "complete_unpublished_generation"
            or type(configuration) is not SourceConfiguration or type(limits) is not LinuxCaptureLimits
            or type(gate) is not _CaptureGate or gate.ctx is not ctx or gate.head != complete.expected_head
            or complete.source_revision != configuration.revision):
        raise CoreError("INVALID_QUERY_OPTIONS", "Trusted closed generation proof and exact capture context required")
    from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory
    head, snapshot, catalog = complete.expected_head, complete.snapshot, complete.catalog
    _validate_inputs(ctx, head, operation_id, gate.authorize, gate.cancelled)
    gate.check()
    if gate.configuration != configuration:
        raise CoreError("SOURCE_CONFIGURATION_CONFLICT", "Captured source configuration differs")
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"analysis:run"})
        existing = _catalog_or_none(tx, snapshot)
    if existing is not None:
        # This verifier reads only the already catalogued locator, outside the
        # write UOW; it never trusts the fresh proposed locator for dedup reuse.
        with open_posix_snapshot_session(state=ctx.state, principal=ctx.principal,
                snapshot=snapshot, graph_reader_factory=RentgenGraphReaderFactory(),
                limits=PosixSnapshotLimits(copied_byte_budget=2560*1024**2,
                    resident_byte_budget=limits.resident_byte_budget,
                    max_source_entries=limits.max_source_entries,
                    max_inventory_items=limits.max_inventory_items,
                    max_retained_descriptors=limits.max_retained_descriptors,
                    max_relative_components=limits.max_relative_components,
                    max_manifest_bytes=limits.max_manifest_bytes,
                    deadline_seconds=limits.phase_deadline_seconds),
                graph_limits=VerifiedGraphLimits(image_buffer_budget=2*limits.max_graph_bytes,
                    max_graph_bytes=limits.max_graph_bytes, max_vm_steps=limits.max_vm_steps,
                    cache_kib=limits.graph_cache_kib, deadline_seconds=limits.phase_deadline_seconds),
                authorize_read=gate.check) as verified:
            if verified._catalog != existing:
                raise CoreError("STATE_CORRUPT", "Opened dedup locator differs from selected catalog row")
        catalog = replace(catalog, generation_relpath=existing.generation_relpath)
    gate.check()
    _boundary("before_state_transaction", ctx=ctx, complete=complete, catalog=catalog)
    gate.tick()  # Last cancellation callback before the bounded write UOW.
    commit_attempted = False
    try:
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            tx.require_all({"analysis:run"})
            found = tx._find_publication(operation_id)
            if found is not None:
                if found[1] != head or found[0].snapshot != snapshot:
                    raise CoreError("OPERATION_CONFLICT", "Operation is bound to different inputs")
                return found[0]
            current = tx.get_project_head()
            if current.source_revision != head.source_revision or tx.get_source_configuration() != configuration:
                raise CoreError("SOURCE_CONFIGURATION_CONFLICT", "Source configuration changed before publication")
            if current != head:
                raise CoreError("HEAD_CONFLICT", "Project head changed before publication")
            if _catalog_or_none(tx, snapshot) != existing:
                raise CoreError("STATE_CORRUPT", "Catalog changed without a head transition")
            result = tx.commit_publication(expected_head=head, catalog=catalog,
                layers=complete.layers, operation_id=operation_id)
            _boundary("before_commit", ctx=ctx, complete=complete, catalog=catalog)
            gate.owner_deadline()
            commit_attempted = True
        _boundary("after_commit", ctx=ctx, complete=complete, catalog=catalog)
        return result
    except Exception:
        if not commit_attempted:
            raise
        # No owner or write connection is open now. The durable receipt is
        # authoritative even after a later head/config/deadline transition.
        reconciled = _reconcile(ctx, head, operation_id, snapshot)
        if reconciled is not None:
            return reconciled
        raise
