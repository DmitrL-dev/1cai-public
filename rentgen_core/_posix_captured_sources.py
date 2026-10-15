"""Internal copied source owner admitted only after successful native F2 exit."""
from dataclasses import asdict, dataclass, replace
import os
from threading import get_ident
from time import monotonic

from ._posix_capture_candidate import PosixCandidateLimits, open_posix_capture_candidate
from .context import Principal
from .errors import CoreError
from .manifests import CapturedInput, parse_source_document, sha256
from .snapshots import ProjectHead
from .state import ProjectState

_ADMITTED = object()


def _invalid():
    return CoreError("SOURCE_READ_SESSION_INVALID", "Copied source owner is not active on its owner")


def _limit():
    return CoreError("SOURCE_CAPTURE_LIMIT_EXCEEDED", "Copied source resource budget exceeded")


@dataclass(frozen=True)
class PosixCapturedLimits:
    # Source/manifest byte images, including the real F2 capture peak. Not RSS.
    resident_byte_budget: int
    max_source_bytes: int = 1024**3
    max_source_entries: int = 20_000
    max_read_bytes: int = 2 * 1024**3
    max_manifest_bytes: int = 64 * 1024**2
    deadline_seconds: int = 30

    def __post_init__(self):
        maxima = (4 * 1024**3, 1024**3, 20_000, 4 * 1024**3, 64 * 1024**2, 120)
        if any(type(value) is not int or not 1 <= value <= maximum
               for value, maximum in zip(asdict(self).values(), maxima)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed bounded copied source limits required")


def capture_posix_sources(*, state, principal, source_root, expected_head,
                          candidate_limits, live_limits, limits, authorize_capture,
                          candidate_id=None):
    """Own F2 completely. Its failed exit can never disclose an admitted owner.

    Aliases are immutable bytes, not new reads of the live or staged pathname.
    Their later lifetime is explicit; closing this owner cannot revoke aliases
    already returned to a trusted caller.
    """
    if (type(state) is not ProjectState or type(principal) is not Principal
            or type(expected_head) is not ProjectHead
            or type(candidate_limits) is not PosixCandidateLimits
            or type(limits) is not PosixCapturedLimits or not callable(authorize_capture)):
        raise CoreError("INVALID_QUERY_OPTIONS", "Typed trusted copied source inputs required")
    deadline = monotonic() + limits.deadline_seconds
    def authorize():
        if monotonic() >= deadline:
            raise CoreError("SOURCE_READ_DEADLINE_EXCEEDED", "Copied source deadline exceeded")
        authorize_capture()
        if monotonic() >= deadline:
            raise CoreError("SOURCE_READ_DEADLINE_EXCEEDED", "Copied source deadline exceeded")
    buffers, entries, document, receipt, configuration, raw = {}, (), None, None, None, None
    try:
        effective = replace(candidate_limits,
            resident_byte_budget=min(candidate_limits.resident_byte_budget, limits.resident_byte_budget),
            max_source_bytes=min(candidate_limits.max_source_bytes, limits.max_source_bytes),
            max_source_entries=min(candidate_limits.max_source_entries, limits.max_source_entries),
            max_manifest_bytes=min(candidate_limits.max_manifest_bytes, limits.max_manifest_bytes))
        candidate = open_posix_capture_candidate(state=state, principal=principal,
            source_root=source_root, expected_head=expected_head, limits=effective,
            live_limits=live_limits, authorize_capture=authorize, candidate_id=candidate_id)
        with candidate:
            entries, document = candidate.entries, candidate.source_document
            total = sum(entry.size_bytes for entry in entries)
            if (len(entries) > limits.max_source_entries or total > limits.max_source_bytes
                    or len(document) > limits.max_manifest_bytes
                    or max(candidate._resident_plan, total + len(document)) > limits.resident_byte_budget):
                raise _limit()
            parsed = parse_source_document(document)
            if (parsed["project_id"] != state.project_id
                    or tuple(CapturedInput(**entry) for entry in parsed["entries"]) != entries):
                raise CoreError("SOURCE_REF_MISMATCH", "Copied source entries differ from source manifest")
            for entry in entries:
                authorize()
                raw = candidate.read_bytes(entry)
                if type(raw) is not bytes or len(raw) != entry.size_bytes or sha256(raw) != entry.raw_sha256:
                    raise CoreError("SOURCE_REF_MISMATCH", "Copied source image differs from its entry")
                buffers[entry.layer_id, entry.relative_path] = raw
            configuration = candidate._configuration
        # A receipt exists only after full F2 inventory, durability and cleanup.
        receipt = candidate.receipt
        authorize()
        if (receipt["source_digest"] != sha256(document)
                or receipt["source_revision"] != expected_head.source_revision):
            raise CoreError("SOURCE_REF_MISMATCH", "F2 terminal source receipt differs")
        result = _CapturedSources(_ADMITTED, state, principal, expected_head, configuration,
                                  limits, authorize, deadline, entries, document, buffers, receipt)
        buffers = {}
        return result
    finally:
        buffers.clear()
        raw = None
        entries, document, receipt, configuration = (), None, None, None


class _CapturedSources:
    def __init__(self, admission, state, principal, head, configuration, limits,
                 authorize, deadline, entries, document, buffers, receipt):
        if admission is not _ADMITTED:
            raise _invalid()
        self.project_id = state.project_id
        self._state, self._principal, self._head = state, principal, head
        self._configuration, self._limits, self._authorize = configuration, limits, authorize
        self._deadline, self._entries, self._document = deadline, entries, document
        self._buffers, self._receipt = buffers, dict(receipt)
        self._index = {(entry.layer_id, entry.relative_path): entry for entry in entries}
        self._owner, self._phase, self._busy, self._read = (os.getpid(), get_ident()), "ready", False, 0

    def _checkpoint(self):
        if self._owner != (os.getpid(), get_ident()) or self._phase not in {"entering", "active"}:
            raise _invalid()
        if monotonic() >= self._deadline:
            raise CoreError("SOURCE_READ_DEADLINE_EXCEEDED", "Copied source deadline exceeded")
        self._authorize()
        with self._state.transaction(self._principal) as tx:
            tx.require_all({"analysis:run"})
            head, configuration = tx.get_project_head(), tx.get_source_configuration()
        if head != self._head:
            raise CoreError("HEAD_CONFLICT", "Project head changed during copied source operation")
        if configuration != self._configuration or configuration.revision != head.source_revision:
            raise CoreError("SOURCE_CONFIGURATION_CONFLICT", "Source configuration changed during copied source operation")
        if monotonic() >= self._deadline:
            raise CoreError("SOURCE_READ_DEADLINE_EXCEEDED", "Copied source deadline exceeded")

    def __enter__(self):
        if self._owner != (os.getpid(), get_ident()) or self._phase != "ready" or self._busy:
            raise _invalid()
        self._phase, self._busy = "entering", True
        try:
            self._checkpoint()
            self._phase = "active"
            return self
        except BaseException:
            self._close()
            raise
        finally:
            self._busy = False

    def _call(self, operation):
        if self._owner != (os.getpid(), get_ident()) or self._phase != "active" or self._busy:
            raise _invalid()
        self._busy = True
        result = None
        try:
            self._checkpoint()
            result = operation()
            self._checkpoint()
            return result
        except BaseException:
            result = None
            self._close()
            raise
        finally:
            self._busy = False

    def checkpoint(self):
        return self._call(lambda: None)

    @property
    def entries(self):
        return self._call(lambda: self._entries)

    @property
    def source_document(self):
        return self._call(lambda: self._document)

    @property
    def source_digest(self):
        return self._call(lambda: self._receipt["source_digest"])

    @property
    def source_revision(self):
        return self._call(lambda: self._configuration.revision)

    @property
    def operation_deadline(self):
        return self._call(lambda: self._deadline)

    def read_bytes(self, entry):
        def read():
            if type(entry) is not CapturedInput or self._index.get((entry.layer_id, entry.relative_path)) != entry:
                raise CoreError("SOURCE_REF_MISMATCH", "Exact copied source entry required")
            if self._read + entry.size_bytes > self._limits.max_read_bytes:
                raise _limit()
            self._read += entry.size_bytes
            return self._buffers[entry.layer_id, entry.relative_path]
        return self._call(read)

    def _close(self):
        self._phase = "closed"
        self._buffers.clear(); self._index.clear()
        self._entries, self._document, self._receipt = (), None, None
        self._state = self._principal = self._configuration = self._authorize = None

    def __exit__(self, kind, value, traceback):
        if self._owner != (os.getpid(), get_ident()) or self._busy or self._phase not in {"active", "closed"}:
            raise _invalid()
        if self._phase == "closed":
            return False
        self._busy = True
        try:
            if kind is None:
                self._checkpoint()
        finally:
            self._close()
            self._busy = False
        return False
