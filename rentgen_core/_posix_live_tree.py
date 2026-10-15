"""Internal POSIX live inventory and copied reads; no capture dispatch or leases."""
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import os
from pathlib import Path
import stat
import sys
from threading import get_ident
from time import monotonic

from . import _posix_source_tree as retained
from .errors import CoreError
from .source_configuration import SourceConfiguration
from .source_paths import validate_inventory_paths, validate_source_path


def _invalid():
    return CoreError("SOURCE_READ_SESSION_INVALID", "POSIX live reader is not active on its owner")


def _changed(message="Live source changed during observation"):
    return CoreError("SOURCE_CAPTURE_CHANGED", message)


def _limit():
    return CoreError("SOURCE_CAPTURE_LIMIT_EXCEEDED", "POSIX live reader resource limit exceeded")


def _layer_invalid():
    return CoreError("SOURCE_LAYER_INVALID", "Source/state/layer descriptor namespaces overlap or alias")


@dataclass(frozen=True)
class PosixLiveLimits:
    max_file_bytes: int = 64 * 1024**2
    max_total_bytes: int = 1024**3
    max_entries: int = 100_000
    max_relative_components: int = 128
    max_retained_descriptors: int = 1024
    max_read_bytes: int = 2 * 1024**3
    max_inventory_passes: int = 3
    max_reads_per_file: int = 2
    deadline_seconds: int = 30

    def __post_init__(self):
        maxima = (64 * 1024**2, 1024**3, 100_000, 256, 65_536,
                  2 * 1024**3, 3, 2, 30)
        if any(type(value) is not int or not 1 <= value <= maximum
               for value, maximum in zip(asdict(self).values(), maxima)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed bounded POSIX live limits required")


@dataclass(frozen=True)
class PosixStamp:
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    nlink: int
    size: int
    mtime_ns: int
    ctime_ns: int
    flags: int

    @classmethod
    def of(cls, info):
        return cls(info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                   info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
                   getattr(info, "st_flags", 0))

    @property
    def directory(self):
        return stat.S_ISDIR(self.mode)


@dataclass(frozen=True)
class PosixTreeItem:
    layer_id: str
    relative_path: str
    stamp: PosixStamp


class PosixLiveTree:
    """One owner holds live descriptors; caller owns two passes/final comparison."""
    def __init__(self, source_root, state_root, *, limits, authorize_read):
        if type(limits) is not PosixLiveLimits or not callable(authorize_read):
            raise CoreError("INVALID_QUERY_OPTIONS", "POSIX live limits and authorization are required")
        self.source_root, self.state_root = Path(source_root).absolute(), Path(state_root).absolute()
        self._limits, self._authorize = limits, authorize_read
        self._phase, self._owner, self._busy = "new", None, False
        self._closing = False
        self._stack, self._active_read = None, None
        self._directories, self._leaves, self._items = {}, {}, {}
        self._configuration, self._exclusions = None, None
        self._layers, self._names = {}, {}
        self._baseline = None
        self._inventory_calls, self._read_bytes = 0, 0
        self._read_counts = {}

    def _owner_check(self):
        if self._owner != (os.getpid(), get_ident()):
            raise _invalid()

    def _deadline_check(self):
        if monotonic() >= self._deadline:
            raise CoreError("SOURCE_READ_DEADLINE_EXCEEDED", "POSIX live reader deadline exceeded")

    def _checkpoint(self):
        self._owner_check()
        if self._phase not in {"entering", "active"}:
            raise _invalid()
        self._deadline_check()
        self._authorize()
        self._deadline_check()
        if self._directories:
            self._directories[""].verify()
            self._state.verify()

    def _descriptors(self, extra=0):
        # Two independent absolute ancestor chains, children, leaves, scandir dup.
        used = self._base_fds + max(0, len(self._directories) - 1) + len(self._leaves)
        if used + extra + 1 > self._limits.max_retained_descriptors:
            raise _limit()

    def _hold(self, context):
        try:
            return self._stack.enter_context(context)
        except (OSError, CoreError) as exc:
            if isinstance(exc, CoreError) and exc.code == "CAPTURE_PLATFORM_UNSUPPORTED":
                raise
            raise CoreError("SOURCE_PATH_UNSAFE", "Live source descriptor is unavailable or unsafe") from exc

    def _directory(self, relative, *, enumerated=False):
        if relative in self._directories:
            self._directories[relative].verify()
            return self._directories[relative]
        parts = relative.split("/")
        if len(parts) > self._limits.max_relative_components:
            raise _limit()
        parent, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
        cap = self._directory(parent)
        # Configured locator aliases must not silently become different spellings.
        if not enumerated and name not in cap.names(maximum=self._limits.max_entries):
            raise _layer_invalid()
        self._descriptors(extra=1)
        opened = self._hold(cap.child(name, private=False))
        identity = self._id(opened)
        if (self._id(self._state) in self._ids(opened)
                or (identity in self._ids(self._state)
                    and not self.state_root.is_relative_to(self.source_root / relative))
                or any(self._id(old) == identity for old in self._directories.values())):
            raise _layer_invalid()
        self._directories[relative] = opened
        return opened

    @staticmethod
    def _ids(cap):
        return [(entry[3][0], entry[3][1]) for entry in cap._chain]

    @staticmethod
    def _id(cap):
        info = os.fstat(cap._fd)
        return info.st_dev, info.st_ino

    def __enter__(self):
        if self._phase != "new":
            raise _invalid()
        self._phase, self._owner, self._busy = "entering", (os.getpid(), get_ident()), True
        self._deadline = monotonic() + self._limits.deadline_seconds
        try:
            if sys.platform not in {"darwin", "linux"}:
                raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "No POSIX live tree adapter")
            if not hasattr(os, "pread"):
                raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "POSIX held-descriptor pread is required")
            self._checkpoint()
            self._base_fds = len(self.source_root.parts) + len(self.state_root.parts)
            self._descriptors()
            self._stack = ExitStack()
            source = self._hold(retained.open_directory(self.source_root, private=False))
            self._state = self._hold(retained.open_directory(self.state_root, private=False))
            self._directories[""] = source
            if self._id(self._state) in self._ids(source):
                raise _layer_invalid()
            if self._id(source) in self._ids(self._state) and not self.state_root.is_relative_to(self.source_root):
                raise _layer_invalid()
            self._checkpoint()
            self._phase = "active"
            return self
        except BaseException:
            self._cleanup(sys.exc_info())
            raise
        finally:
            self._busy = False

    def _call(self, operation):
        self._owner_check()
        if self._phase != "active" or self._busy or self._closing:
            raise _invalid()
        self._busy = True
        try:
            self._checkpoint()
            result = operation()
            self._checkpoint()
            return result
        except BaseException:
            self._cleanup(sys.exc_info())
            raise
        finally:
            self._busy = False

    def configure(self, configuration):
        def configure():
            if self._configuration is not None or type(configuration) is not SourceConfiguration:
                raise CoreError("SOURCE_CONFIGURATION_CONFLICT", "One exact source configuration is required")
            if len(configuration.layers) > self._limits.max_entries:
                raise _limit()
            exclusions = []
            for layer in configuration.layers:
                self._checkpoint()
                relative = "" if layer.root_relative_path == "." else layer.root_relative_path
                cap = self._directory(relative)
                if self._id(self._state) in self._ids(cap):
                    raise _layer_invalid()
                for old in self._layers.values():
                    other = self._directories[old]
                    if self._id(other) in self._ids(cap) or self._id(cap) in self._ids(other):
                        raise _layer_invalid()
                self._layers[layer.layer_id] = relative
                if self._id(cap) in self._ids(self._state):
                    path = self.source_root / relative
                    if not self.state_root.is_relative_to(path):
                        raise _layer_invalid()
                    excluded = self.state_root.relative_to(path).as_posix()
                    validate_source_path(excluded)
                    # Check each spelling from held parents before skipping state.
                    parent = relative
                    for index, name in enumerate(excluded.split("/")):
                        directory = self._directory(parent)
                        if name not in directory.names(maximum=self._limits.max_entries):
                            raise _layer_invalid()
                        if index + 1 < len(excluded.split("/")):
                            parent = parent + "/" + name if parent else name
                        elif (directory.stat(name).st_dev, directory.stat(name).st_ino) != self._id(self._state):
                            raise _layer_invalid()
                    exclusions.append((layer.layer_id, excluded))
            self._configuration, self._exclusions = configuration, tuple(exclusions)
            return self._exclusions
        return self._call(configure)

    def _leaf_check(self, key):
        stream, parent, name, item = self._leaves[key]
        actual = PosixStamp.of(os.fstat(stream.fileno()))
        named = PosixStamp.of(parent.stat(name))
        if actual != item.stamp or named != actual:
            raise _changed("Live source stamp or name changed")
        return stream

    def _post_inventory(self):
        for relative, names in self._names.items():
            self._checkpoint()
            cap = self._directories[relative]
            if cap.names(maximum=self._limits.max_entries) != list(names):
                raise _changed("Live directory names changed")
        for item in self._items.values():
            self._deadline_check()
            if item.stamp.directory:
                relative = self._full(item)
                if PosixStamp.of(os.fstat(self._directories[relative]._fd)) != item.stamp:
                    raise _changed("Live directory stamp changed")
            else:
                self._leaf_check((item.layer_id, item.relative_path))

    def _full(self, item):
        root = self._layers[item.layer_id]
        return root + "/" + item.relative_path if root and item.relative_path else root or item.relative_path

    def inventory(self, configuration, exclusions):
        def inventory():
            if self._configuration is None or configuration != self._configuration or exclusions != self._exclusions:
                raise CoreError("SOURCE_CONFIGURATION_CONFLICT", "Inventory configuration/exclusions changed")
            if self._inventory_calls >= self._limits.max_inventory_passes:
                raise _limit()
            self._inventory_calls += 1
            result, total = [], 0
            excluded = dict(self._exclusions)
            def add(layer, relative, stamp):
                if len(result) >= self._limits.max_entries:
                    raise _limit()
                key = layer, relative
                item = PosixTreeItem(layer, relative, stamp)
                if self._baseline is not None:
                    old = self._items.get(key)
                    if old != item:
                        raise _changed("Live inventory membership or stamp changed")
                    item = old
                result.append(item)
                return item
            for layer in configuration.layers:
                root = self._layers[layer.layer_id]
                cap = self._directories[root]
                add(layer.layer_id, "", PosixStamp.of(os.fstat(cap._fd)))
                pending = [(root, "")]
                while pending:
                    self._checkpoint()
                    full, relative = pending.pop()
                    directory = self._directories[full]
                    names = directory.names(maximum=min(retained.MAX_ENTRIES, self._limits.max_entries - len(result) + 1))
                    validate_inventory_paths(names)  # Also before skipping state.
                    names.sort(key=lambda name: name.encode("utf-8"))
                    if full in self._names and tuple(names) != self._names[full]:
                        raise _changed("Live directory names changed")
                    self._names[full] = tuple(names)
                    for name in names:
                        self._deadline_check()
                        rel = relative + "/" + name if relative else name
                        validate_source_path(rel)
                        source_relative = full + "/" + name if full else name
                        if len(source_relative.split("/")) > self._limits.max_relative_components:
                            raise _limit()
                        if rel == excluded.get(layer.layer_id):
                            self._state.verify()
                            continue
                        info = directory.stat(name)
                        stamp = PosixStamp.of(info)
                        if stat.S_ISDIR(info.st_mode):
                            item = add(layer.layer_id, rel, stamp)
                            child = self._directory(source_relative, enumerated=True)
                            if PosixStamp.of(os.fstat(child._fd)) != stamp:
                                raise _changed("Live directory changed during inventory")
                            pending.append((source_relative, rel))
                        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                            if stamp.size > self._limits.max_file_bytes or total + stamp.size > self._limits.max_total_bytes:
                                raise _limit()
                            total += stamp.size
                            item = add(layer.layer_id, rel, stamp)
                            key = layer.layer_id, rel
                            if key not in self._leaves:
                                self._descriptors(extra=1)
                                stream = self._hold(directory.file(name))
                                self._leaves[key] = stream, directory, name, item
                            self._leaf_check(key)
                        else:
                            raise CoreError("SOURCE_PATH_UNSAFE", "Live tree contains a link or special/multiple-link object")
                        self._items[layer.layer_id, rel] = item
                self._items[layer.layer_id, ""] = next(item for item in result if item.layer_id == layer.layer_id and not item.relative_path)
            order = {layer.layer_id: layer.ordinal for layer in configuration.layers}
            result.sort(key=lambda item: (order[item.layer_id], item.relative_path.encode("utf-8")))
            if self._baseline is not None and tuple(result) != self._baseline:
                raise _changed("Live inventory membership changed")
            self._post_inventory()
            self._baseline = tuple(result)
            return self._baseline
        return self._call(inventory)

    def read(self, item):
        return _CopiedRead(self, item)

    def _cleanup(self, exception):
        self._phase = "closed"
        if self._active_read is not None:
            self._active_read._raw = None
            self._active_read._phase = "closed"
            self._active_read = None
        stack, self._stack = self._stack, None
        failure = None
        if stack is not None:
            try:
                stack.__exit__(*exception)
            except BaseException as exc:
                failure = exc
        self._directories.clear(); self._leaves.clear(); self._items.clear()
        self._layers.clear(); self._names.clear(); self._read_counts.clear()
        self._configuration = self._exclusions = self._baseline = self._authorize = None
        self._state = None
        if failure is not None and exception[0] is None:
            if not isinstance(failure, Exception):
                raise failure
            raise _changed("Live source cleanup or namespace verification failed") from failure

    def __exit__(self, kind, value, traceback):
        self._owner_check()
        idle_read = self._active_read is not None and self._active_read._phase == "active" and not self._active_read._in_call
        if self._closing or (self._busy and not idle_read) or self._phase not in {"active", "closed"}:
            raise _invalid()
        if self._phase == "closed":
            return False
        self._busy = self._closing = True
        try:
            if kind is None:
                try:
                    self._checkpoint()
                    if self._baseline is not None:
                        self._post_inventory()
                    self._checkpoint()
                except BaseException:
                    self._cleanup(sys.exc_info())
                    raise
            self._cleanup((kind, value, traceback))
            if kind is None:
                self._deadline_check()
            return False
        finally:
            self._busy = self._closing = False


class _CopiedRead:
    """Explicit context/iterator: a refused exit never consumes native ownership."""
    def __init__(self, tree, item):
        self._tree, self._item = tree, item
        self._phase, self._raw, self._in_call = "new", None, False

    def __enter__(self):
        tree, item = self._tree, self._item
        tree._owner_check()
        if self._phase != "new" or tree._phase != "active" or tree._busy:
            raise _invalid()
        self._phase, tree._busy, tree._active_read = "entering", True, self
        try:
            tree._checkpoint()
            if type(item) is not PosixTreeItem:
                raise CoreError("SOURCE_REF_MISMATCH", "An exact held live-tree item is required")
            key = item.layer_id, item.relative_path
            if tree._items.get(key) is not item or item.stamp.directory:
                raise CoreError("SOURCE_REF_MISMATCH", "An exact held live-tree item is required")
            count = tree._read_counts.get(key, 0)
            if count >= tree._limits.max_reads_per_file or tree._read_bytes + item.stamp.size > tree._limits.max_read_bytes:
                raise _limit()
            tree._read_counts[key] = count + 1
            tree._read_bytes += item.stamp.size
            stream = tree._leaf_check(key)
            self._raw = os.pread(stream.fileno(), item.stamp.size + 1, 0)
            if len(self._raw) != item.stamp.size:
                raise _changed("Live source length changed while copying")
            tree._leaf_check(key)
            tree._checkpoint()
            self._phase = "active"
            return self
        except BaseException:
            tree._cleanup(sys.exc_info())
            tree._busy = False
            raise

    def __iter__(self):
        return self

    def _guard(self):
        self._tree._owner_check()
        if (self._phase != "active" or self._tree._active_read is not self
                or self._in_call or self._tree._closing):
            raise _invalid()

    def __next__(self):
        self._guard()
        if self._raw is None:
            raise StopIteration
        self._in_call = True
        result = None
        try:
            self._tree._checkpoint()
            self._tree._leaf_check((self._item.layer_id, self._item.relative_path))
            result, self._raw = self._raw, None
            self._tree._checkpoint()
            return result
        except BaseException:
            result = None
            self._tree._cleanup(sys.exc_info())
            self._tree._busy = False
            raise
        finally:
            self._in_call = False

    def __exit__(self, kind, value, traceback):
        tree = self._tree
        tree._owner_check()
        if self._phase == "closed" and tree._phase == "closed":
            return False
        self._guard()
        self._in_call = True
        try:
            if kind is None:
                tree._checkpoint()
                tree._leaf_check((self._item.layer_id, self._item.relative_path))
                tree._checkpoint()
            else:
                tree._cleanup((kind, value, traceback))
        except BaseException:
            tree._cleanup(sys.exc_info())
            raise
        finally:
            self._raw, self._phase = None, "closed"
            tree._active_read, tree._busy = None, False
            self._in_call = False
        return False
