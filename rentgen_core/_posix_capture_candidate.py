"""Internal owned POSIX source candidate; no scanner or publication dispatch."""
import codecs
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import os
from pathlib import Path
import sys
from threading import get_ident
from time import monotonic
from uuid import uuid4

from . import _posix_source_tree as retained
from ._posix_live_tree import PosixLiveLimits, PosixLiveTree
from .context import Principal
from .errors import CoreError
from .manifests import CapturedInput, build_source_document, sha256
from .snapshots import ProjectHead, validate_operation_id
from .state import ProjectState

_CHUNK = 65536
_SOURCE_MANIFEST = "source-manifest.json"


def _json_size(value):
    """Canonical encoded length without first allocating a complete JSON image."""
    if value is None:
        return 4
    if type(value) is int:
        return len(str(value))
    if type(value) is str:
        size = 2
        for character in value:
            code = ord(character)
            if character in '\\"' or character in "\b\f\n\r\t":
                size += 2
            elif code < 32:
                size += 6
            else:
                size += 1 if code < 128 else 2 if code < 2048 else 3 if code < 65536 else 4
        return size
    if type(value) is list:
        return 2 + sum(map(_json_size, value)) + max(0, len(value) - 1)
    if type(value) is dict:
        return 2 + sum(_json_size(key) + 1 + _json_size(item) for key, item in value.items()) + max(0, len(value) - 1)
    raise CoreError("INVALID_QUERY_OPTIONS", "Unexpected source-manifest size input")


def _invalid():
    return CoreError("SOURCE_READ_SESSION_INVALID", "POSIX candidate is not active on its owner")


def _limit():
    return CoreError("SOURCE_CAPTURE_LIMIT_EXCEEDED", "POSIX candidate resource limit exceeded")


def _changed(message="Owned candidate content or namespace changed"):
    return CoreError("SOURCE_CAPTURE_CHANGED", message)


@dataclass(frozen=True)
class PosixCandidateLimits:
    # Source byte images, one transient copy/decoder chunk, bounded manifest copies.
    resident_byte_budget: int
    max_source_bytes: int = 1024**3
    max_source_entries: int = 100_000
    max_manifest_bytes: int = 64 * 1024**2
    max_retained_descriptors: int = 4096
    max_relative_components: int = 256
    max_builder_read_bytes: int = 1024**3
    deadline_seconds: int = 30

    def __post_init__(self):
        maxima = (2 * 1024**3, 1024**3, 100_000, 64 * 1024**2,
                  65_536, 256, 2 * 1024**3, 30)
        if any(type(value) is not int or not 1 <= value <= maximum
               for value, maximum in zip(asdict(self).values(), maxima)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed bounded candidate limits required")


def open_posix_capture_candidate(*, state, principal, source_root, expected_head,
                                  limits, live_limits, authorize_capture, candidate_id=None):
    """Trusted internal factory. Every attempt gets an exclusive staging UUID."""
    return _PosixCaptureCandidate(state, principal, source_root, expected_head,
                                 limits, live_limits, authorize_capture, candidate_id)


class _PosixCaptureCandidate:
    def __init__(self, state, principal, source_root, expected_head, limits, live_limits, authorize, identifier):
        if (type(state) is not ProjectState or type(principal) is not Principal
                or type(expected_head) is not ProjectHead or expected_head.project_id != state.project_id
                or type(limits) is not PosixCandidateLimits or type(live_limits) is not PosixLiveLimits
                or not callable(authorize)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed trusted POSIX candidate inputs required")
        self.project_id = state.project_id
        self.candidate_id = validate_operation_id(str(uuid4()) if identifier is None else identifier)
        self._state, self._principal, self._expected_head = state, principal, expected_head
        self._source_root, self._limits, self._live_limits = Path(source_root).absolute(), limits, live_limits
        self._authorize = authorize
        self._phase, self._owner, self._busy = "new", None, False
        self._stack, self._live, self._root, self._staging = None, None, None, None
        self._dirs, self._files, self._buffers, self._index = {}, {}, {}, {}
        self._configuration, self._entries, self._source_document = None, (), None
        self._builder_bytes, self._resident_plan = 0, 0
        self._receipt = None

    def _owner_check(self):
        if self._owner != (os.getpid(), get_ident()):
            raise _invalid()

    def _deadline_check(self):
        if monotonic() >= self._deadline:
            raise CoreError("SOURCE_READ_DEADLINE_EXCEEDED", "POSIX candidate deadline exceeded")

    def _checkpoint(self):
        self._owner_check()
        if self._phase not in {"entering", "active"}:
            raise _invalid()
        self._deadline_check()
        self._authorize()
        self._deadline_check()
        with self._state.transaction(self._principal) as tx:
            tx.require_all({"analysis:run"})
            head, configuration = tx.get_project_head(), tx.get_source_configuration()
        if head != self._expected_head:
            raise CoreError("HEAD_CONFLICT", "Project head changed during candidate capture")
        if configuration.revision != head.source_revision or (
            self._configuration is not None and configuration != self._configuration
        ):
            raise CoreError("SOURCE_CONFIGURATION_CONFLICT", "Source configuration changed during candidate capture")
        if self._root is not None:
            self._root.verify()
        if "" in self._dirs:
            self._dirs[""].verify()
        self._deadline_check()
        return configuration

    def _descriptors(self, extra=0):
        # Reserve the entire configured live-tree cap as well as our held FDs.
        fds = set()
        for directory in (self._root, self._staging, *self._dirs.values()):
            if directory is not None:
                fds.update(entry[0] for entry in directory._chain)
        fds.update(stream.fileno() for stream, *_ in self._files.values())
        if len(fds) + self._live_limits.max_retained_descriptors + extra + 1 > self._limits.max_retained_descriptors:
            raise _limit()

    def _exclusive_child(self, parent, name):
        self._checkpoint()
        self._descriptors(extra=1)
        parent.verify()
        os.mkdir(name, mode=0o700, dir_fd=parent._fd)  # EEXIST never grants ownership.
        identity = retained._identity(parent.stat(name))
        parent.sync()
        child = self._stack.enter_context(parent.child(name, private=True))
        if retained._identity(os.fstat(child._fd)) != identity:
            raise _changed("Owned candidate directory was replaced after creation")
        return child

    def _directory(self, relative):
        if relative in self._dirs:
            self._dirs[relative].verify()
            return self._dirs[relative]
        if len(relative.split("/")) > self._limits.max_relative_components:
            raise _limit()
        parent, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
        cap = self._exclusive_child(self._directory(parent), name)
        self._dirs[relative] = cap
        return cap

    def _file_check(self, relative):
        stream, directory, name, stamp = self._files[relative]
        if retained._stamp(os.fstat(stream.fileno())) != stamp or retained._stamp(directory.stat(name)) != stamp:
            raise _changed()
        return stream

    def _write_verified(self, relative, raw):
        try:
            self._checkpoint()
            if len(relative.split("/")) > self._limits.max_relative_components:
                raise _limit()
            parent, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
            directory = self._directory(parent)
            self._descriptors(extra=1)
            with directory.create_file(name) as output:
                identity = retained._identity(os.fstat(output.fileno()))
                if output.write(raw) != len(raw):
                    raise _changed("Owned source copy was not written completely")
            self._checkpoint()
            self._descriptors(extra=1)
            stream = self._stack.enter_context(directory.file(name))
            stamp = retained._stamp(os.fstat(stream.fileno()))
            if retained._identity(os.fstat(stream.fileno())) != identity:
                raise _changed("Owned candidate file was replaced after creation")
            self._files[relative] = stream, directory, name, stamp
            copied = None
            try:
                if os.fstat(stream.fileno()).st_size != len(raw):
                    raise _changed()
                copied = os.pread(stream.fileno(), len(raw) + 1, 0)
                if copied != raw:
                    raise _changed("Owned source copy differs from verified live bytes")
                self._file_check(relative)
                self._checkpoint()
            finally:
                copied = None
        finally:
            raw = None

    def _manifest_bound(self, items, exclusions):
        # Count bounded fragments before allocating the complete canonical image.
        base = dict(format_version=1, project_id=self.project_id, layers=[], excluded_state_subtrees=[], entries=[])
        size = _json_size(base)
        groups = (
            (dict(asdict(layer), configuration_uuid=None, identity_status="unresolved") for layer in self._configuration.layers),
            (dict(layer_id=layer, relative_path=path) for layer, path in exclusions),
            (dict(layer_id=item.layer_id, relative_path=item.relative_path, raw_sha256="0"*64,
                  size_bytes=item.stamp.size, encoding="utf-8-sig") for item in items if not item.stamp.directory),
        )
        for group in groups:
            first = True
            for fragment in group:
                self._deadline_check()
                size += _json_size(fragment) + (0 if first else 1)
                first = False
                if size > self._limits.max_manifest_bytes:
                    raise _limit()
        return size

    @staticmethod
    def _encoding(raw):
        try:
            decoder = codecs.getincrementaldecoder("utf-8-sig")(errors="strict")
            try:
                for offset in range(0, len(raw), _CHUNK):
                    decoder.decode(raw[offset:offset + _CHUNK], final=False)
                decoder.decode(b"", final=True)
            except UnicodeError:
                return None
            return "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
        finally:
            raw = None

    def _live_bytes(self, item):
        raw = None
        try:
            with self._live.read(item) as chunks:
                raw = next(chunks)
                if type(raw) is not bytes or len(raw) != item.stamp.size:
                    raise _changed("Live copy contract changed")
                try:
                    next(chunks)
                except StopIteration:
                    pass
                else:
                    raise _changed("Live copy contract changed")
            return raw
        except BaseException:
            raw = None
            raise

    def _verify_inventory(self):
        expected = {"": set()}
        for relative in (*self._dirs.keys(), *self._files.keys()):
            if relative:
                parent, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
                expected.setdefault(parent, set()).add(name)
        for relative, directory in self._dirs.items():
            self._checkpoint()
            if set(directory.names()) != expected.get(relative, set()):
                raise _changed("Owned candidate contains an unlisted or missing object")
        for relative in self._files:
            self._deadline_check()
            self._file_check(relative)

    def _sync(self):
        for relative in sorted(self._dirs, key=lambda value: value.count("/") + bool(value), reverse=True):
            self._checkpoint()
            self._dirs[relative].sync()
        self._staging.sync()
        self._root.sync()
        self._checkpoint()

    def __enter__(self):
        if self._phase != "new":
            raise _invalid()
        self._owner, self._phase, self._busy = (os.getpid(), get_ident()), "entering", True
        self._deadline = monotonic() + self._limits.deadline_seconds
        raw = expected = None
        try:
            self._configuration = self._checkpoint()
            self._stack = ExitStack()
            if len(self._state.path.parent.parts) + self._live_limits.max_retained_descriptors + 4 > self._limits.max_retained_descriptors:
                raise _limit()
            self._root = self._stack.enter_context(retained.open_directory(self._state.path.parent, private=True))
            self._staging = self._stack.enter_context(self._root.child("staging", create=True, private=True))
            self._dirs[""] = self._exclusive_child(self._staging, self.candidate_id)
            self._directory("sources")
            self._live = PosixLiveTree(self._source_root, self._state.path.parent,
                                      limits=self._live_limits, authorize_read=self._checkpoint)
            self._live.__enter__()
            exclusions = self._live.configure(self._configuration)
            first = self._live.inventory(self._configuration, exclusions)
            files = [item for item in first if not item.stamp.directory]
            total = sum(item.stamp.size for item in files)
            if len(files) > self._limits.max_source_entries or total > self._limits.max_source_bytes:
                raise _limit()
            manifest_bound = self._manifest_bound(first, exclusions)
            maximum = max((item.stamp.size for item in files), default=0)
            # Decoder slice plus conservative four-byte Unicode storage per char.
            self._resident_plan = total + max(maximum + 5 * min(_CHUNK, maximum) + 1 if files else 0,
                                             9 * manifest_bound + 1)
            if self._resident_plan > self._limits.resident_byte_budget:
                raise _limit()
            for layer in self._configuration.layers:
                self._directory("sources/" + layer.layer_id)
            entries = []
            for item in files:
                self._checkpoint()
                raw = self._live_bytes(item)
                entry = CapturedInput(item.layer_id, item.relative_path, sha256(raw), len(raw), self._encoding(raw))
                self._write_verified("sources/" + item.layer_id + "/" + item.relative_path, raw)
                entries.append(entry)
                self._buffers[entry.layer_id, entry.relative_path] = raw
                raw = None
            self._entries = tuple(entries)
            second = self._live.inventory(self._configuration, exclusions)
            if second != first:
                raise _changed("Source inventory changed between content passes")
            for item in files:
                raw = self._live_bytes(item)
                expected = self._buffers[item.layer_id, item.relative_path]
                if len(raw) != len(expected) or sha256(raw) != sha256(expected):
                    raise _changed("Source bytes changed between content passes")
                raw = None
            if self._live.inventory(self._configuration, exclusions) != second:
                raise _changed("Source inventory changed after content passes")
            self._live.__exit__(None, None, None)
            self._live = None
            self._source_document = build_source_document(self.project_id, self._configuration, exclusions, self._entries)
            if len(self._source_document) > manifest_bound:
                raise _changed("Canonical source manifest exceeded its preflight bound")
            self._write_verified(_SOURCE_MANIFEST, self._source_document)
            self._source_digest = sha256(self._source_document)
            self._index = {(entry.layer_id, entry.relative_path): entry for entry in self._entries}
            self._verify_inventory()
            self._sync()
            self._phase = "active"
            self._checkpoint()
            return self
        except BaseException:
            self._cleanup(sys.exc_info())
            raise
        finally:
            raw = expected = None
            self._busy = False

    def _call(self, operation):
        self._owner_check()
        if self._phase != "active" or self._busy:
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
            self._cleanup(sys.exc_info())
            raise
        finally:
            self._busy = False

    @property
    def entries(self):
        return self._call(lambda: self._entries)

    @property
    def source_document(self):
        return self._call(lambda: self._source_document)

    @property
    def source_digest(self):
        return self._call(lambda: self._source_digest)

    @property
    def source_revision(self):
        return self._call(lambda: self._configuration.revision)

    def read_bytes(self, entry):
        def read():
            if type(entry) is not CapturedInput or self._index.get((entry.layer_id, entry.relative_path)) != entry:
                raise CoreError("SOURCE_REF_MISMATCH", "Exact candidate source entry required")
            if self._builder_bytes + entry.size_bytes > self._limits.max_builder_read_bytes:
                raise _limit()
            self._builder_bytes += entry.size_bytes
            relative = "sources/" + entry.layer_id + "/" + entry.relative_path
            self._file_check(relative)
            return self._buffers[entry.layer_id, entry.relative_path]
        return self._call(read)

    def _cleanup(self, exception):
        failure = None
        live, self._live = self._live, None
        if live is not None:
            try:
                live.__exit__(*exception)
            except BaseException:
                failure = sys.exc_info()
        stack, self._stack = self._stack, None
        if stack is not None:
            try:
                stack.__exit__(*(exception if exception[0] is not None else failure or exception))
            except BaseException:
                failure = failure or sys.exc_info()
        self._phase = "closed"
        self._dirs.clear(); self._files.clear(); self._buffers.clear(); self._index.clear()
        self._root = self._staging = self._configuration = self._source_document = self._authorize = None
        self._state = self._principal = None
        self._entries = ()
        # Files are deliberately retained on every outcome; never delete by path.
        if failure is not None and exception[0] is None:
            raise failure[1].with_traceback(failure[2])

    def __exit__(self, kind, value, traceback):
        self._owner_check()
        if self._busy or self._phase not in {"active", "closed"}:
            raise _invalid()
        if self._phase == "closed":
            return False
        self._busy = True
        try:
            if kind is None:
                try:
                    self._verify_inventory()
                    self._sync()
                    self._checkpoint()
                    receipt = dict(project_id=self.project_id, candidate_id=self.candidate_id,
                        relative_path="staging/" + self.candidate_id, source_digest=self._source_digest,
                        source_revision=self._configuration.revision, source_files=len(self._entries),
                        source_bytes=sum(entry.size_bytes for entry in self._entries),
                        source_manifest=_SOURCE_MANIFEST, resident_image_accounting=self._resident_plan,
                        temporal_atomicity="not_proven", status="source_verified_candidate", published=False)
                except BaseException:
                    self._cleanup(sys.exc_info())
                    raise
            self._cleanup((kind, value, traceback))
            if kind is None:
                self._deadline_check()
                self._receipt = receipt
            return False
        finally:
            self._busy = False

    @property
    def receipt(self):
        self._owner_check()
        if self._receipt is None or self._busy:
            raise _invalid()
        return dict(self._receipt)
