"""Windows local-volume source reader with pinned, no-follow ancestor handles.

Paths are used only while their complete ancestor chain remains open without
write/delete sharing. Enumeration and content reads use the verified handles.
This confines reads; it cannot prove a filesystem-wide simultaneous snapshot.
"""
from contextlib import contextmanager
import ctypes as c
from ctypes import wintypes as w
from dataclasses import dataclass
import os
import sys
from pathlib import Path

from .errors import CoreError
from .source_paths import validate_source_path

_MAX_INVENTORY_ITEMS = 100_000


@dataclass(frozen=True)
class FileStamp:
    identity: tuple[int, int]
    attributes: int
    creation: int
    write: int
    change: int
    size: int

    @property
    def directory(self):
        return bool(self.attributes & 0x10)


@dataclass(frozen=True)
class TreeItem:
    layer_id: str
    relative_path: str
    stamp: FileStamp


class _Basic(c.Structure):
    _fields_ = [
        ("creation", c.c_int64),
        ("access", c.c_int64),
        ("write", c.c_int64),
        ("change", c.c_int64),
        ("attributes", w.DWORD),
    ]


class _Info(c.Structure):
    _fields_ = [
        ("attributes", w.DWORD),
        ("creation", w.FILETIME),
        ("access", w.FILETIME),
        ("write", w.FILETIME),
        ("volume", w.DWORD),
        ("size_hi", w.DWORD),
        ("size_lo", w.DWORD),
        ("links", w.DWORD),
        ("id_hi", w.DWORD),
        ("id_lo", w.DWORD),
    ]


class _Tag(c.Structure):
    _fields_ = [("attributes", w.DWORD), ("tag", w.DWORD)]


class _FileId(c.Structure):
    _fields_ = [("volume", c.c_uint64), ("file_id", c.c_ubyte * 16)]


def _file_id_value(raw):
    value = int.from_bytes(bytes(raw), "little")
    if value in (0, (1 << 128) - 1):
        raise CoreError(
            "CAPTURE_PLATFORM_UNSUPPORTED",
            "Filesystem does not provide a unique file identity",
        )
    return value


class _Dir(c.Structure):
    _fields_ = [
        ("next", w.DWORD),
        ("index", w.DWORD),
        ("creation", c.c_int64),
        ("access", c.c_int64),
        ("write", c.c_int64),
        ("change", c.c_int64),
        ("size", c.c_int64),
        ("allocation", c.c_int64),
        ("attributes", w.DWORD),
        ("name_length", w.DWORD),
        ("ea", w.DWORD),
        ("reparse_tag", w.DWORD),
        ("file_id", c.c_ubyte * 16),
    ]


class WindowsHandleOps:
    """Small injectable Win32 seam, with no path-based content read fallback."""

    def __init__(self):
        if os.name != "nt":
            raise CoreError(
                "CAPTURE_PLATFORM_UNSUPPORTED",
                "Capture requires Windows local filesystem handles",
            )
        self.api = c.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateFileW": (
                [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE],
                w.HANDLE,
            ),
            "CloseHandle": ([w.HANDLE], w.BOOL),
            "FlushFileBuffers": ([w.HANDLE], w.BOOL),
            "GetFileInformationByHandle": ([w.HANDLE, c.POINTER(_Info)], w.BOOL),
            "GetFileInformationByHandleEx": (
                [w.HANDLE, c.c_int, c.c_void_p, w.DWORD],
                w.BOOL,
            ),
            "GetFinalPathNameByHandleW": (
                [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD],
                w.DWORD,
            ),
            "GetFileType": ([w.HANDLE], w.DWORD),
            "ReadFile": (
                [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p],
                w.BOOL,
            ),
            "GetDriveTypeW": ([w.LPCWSTR], w.UINT),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result

    def _checked(self, result):
        if not result:
            raise CoreError(
                "SOURCE_ROOT_UNAVAILABLE", "Source handle operation failed"
            ) from c.WinError(c.get_last_error())
        return result

    def open(self, path, *, directory):
        # Directory list/read attributes, leaf GENERIC_READ. No write/delete sharing.
        access = 0x81 if directory else 0x80000000
        handle = self.api.CreateFileW(
            "\\\\?\\" + str(path), access, 1, None, 3, 0x02200000, None
        )
        if handle == c.c_void_p(-1).value:
            self._checked(False)
        return handle

    def open_write(self, path):
        handle = self.api.CreateFileW(
            "\\\\?\\" + str(path), 0x40000080, 1, None, 3, 0x02200000, None
        )
        if handle == c.c_void_p(-1).value:
            self._checked(False)
        return handle

    def flush(self, handle):
        self._checked(self.api.FlushFileBuffers(handle))

    def close(self, handle):
        self._checked(self.api.CloseHandle(handle))

    def stamp(self, handle):
        tag, basic, info = _Tag(), _Basic(), _Info()
        self._checked(
            self.api.GetFileInformationByHandleEx(
                handle, 9, c.byref(tag), c.sizeof(tag)
            )
        )
        if tag.attributes & 0x400:
            raise CoreError("SOURCE_PATH_UNSAFE", "Source traverses a reparse point")
        if self.api.GetFileType(handle) != 1:
            raise CoreError("SOURCE_PATH_UNSAFE", "Source is not a regular disk object")
        self._checked(
            self.api.GetFileInformationByHandleEx(
                handle, 0, c.byref(basic), c.sizeof(basic)
            )
        )
        self._checked(self.api.GetFileInformationByHandle(handle, c.byref(info)))
        identity = _FileId()
        self._checked(
            self.api.GetFileInformationByHandleEx(
                handle, 18, c.byref(identity), c.sizeof(identity)
            )
        )
        return FileStamp(
            (identity.volume, _file_id_value(identity.file_id)),
            basic.attributes,
            basic.creation,
            basic.write,
            basic.change,
            info.size_hi << 32 | info.size_lo,
        )

    def final_path(self, handle):
        buffer = c.create_unicode_buffer(32768)
        length = self._checked(
            self.api.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        )
        if length >= len(buffer) or not buffer.value.startswith("\\\\?\\"):
            raise CoreError("SOURCE_PATH_UNSAFE", "Unsupported final source namespace")
        return Path(buffer.value[4:])

    def local_drive(self, anchor):
        return self.api.GetDriveTypeW(anchor) == 3

    def enumerate(self, handle):
        volume = self.stamp(handle).identity[0]
        buffer = c.create_string_buffer(65536)
        first = True
        while True:
            result = self.api.GetFileInformationByHandleEx(
                handle, 20 if first else 19, buffer, len(buffer)
            )
            first = False
            if not result:
                if (
                    c.get_last_error() == 18
                ):  # ERROR_NO_MORE_FILES, never swallow other errors
                    return
                self._checked(result)
            offset = 0
            while True:
                if offset + c.sizeof(_Dir) > len(buffer):
                    raise CoreError(
                        "SOURCE_PATH_UNSAFE", "Invalid source directory record"
                    )
                item = _Dir.from_buffer(buffer, offset)
                length = int(item.name_length)
                if length % 2 or offset + c.sizeof(_Dir) + length > len(buffer):
                    raise CoreError("SOURCE_PATH_UNSAFE", "Invalid source name record")
                try:
                    name = c.string_at(
                        c.addressof(buffer) + offset + c.sizeof(_Dir), length
                    ).decode("utf-16-le", errors="strict")
                except UnicodeError as exc:
                    raise CoreError(
                        "SOURCE_PATH_UNSAFE", "Source name is not valid Unicode"
                    ) from exc
                if name not in (".", ".."):
                    validate_source_path(name)
                    if "/" in name or item.attributes & 0x400:
                        raise CoreError(
                            "SOURCE_PATH_UNSAFE",
                            "Source inventory contains an unsafe object",
                        )
                    yield name, FileStamp(
                        (volume, _file_id_value(item.file_id)),
                        item.attributes,
                        item.creation,
                        item.write,
                        item.change,
                        item.size,
                    )
                if not item.next:
                    break
                if item.next < c.sizeof(_Dir):
                    raise CoreError(
                        "SOURCE_PATH_UNSAFE", "Invalid source directory offset"
                    )
                offset += item.next

    def chunks(self, handle):
        buffer, count = c.create_string_buffer(1024 * 1024), w.DWORD()
        while True:
            self._checked(
                self.api.ReadFile(handle, buffer, len(buffer), c.byref(count), None)
            )
            if not count.value:
                return
            yield buffer.raw[: count.value]


class WindowsSourceTree:
    def __init__(self, source_root, state_root, *, operations=None):
        self.ops = operations or WindowsHandleOps()
        self.source_root, self.state_root = (
            Path(source_root).absolute(),
            Path(state_root).absolute(),
        )
        self.handles = {}
        self.layers = {}

    def __enter__(self):
        try:
            for root in (self.source_root, self.state_root):
                if (
                    not root.drive
                    or root.drive.startswith("\\\\")
                    or not self.ops.local_drive(root.anchor)
                ):
                    raise CoreError(
                        "CAPTURE_PLATFORM_UNSUPPORTED",
                        "Capture requires a fixed local volume",
                    )
                for ancestor in (*reversed(root.parents), root):
                    self._directory(ancestor)
            self.source_root = self.ops.final_path(self.handles[self.source_root])
            self.state_root = self.ops.final_path(self.handles[self.state_root])
            if self.source_root.is_relative_to(self.state_root):
                raise CoreError(
                    "SOURCE_LAYER_INVALID", "Source root cannot be inside project state"
                )
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, *args):
        failure = None
        for handle in reversed(tuple(self.handles.values())):
            try:
                self.ops.close(handle)
            except BaseException as exc:
                failure = failure or exc
        self.handles.clear()
        if failure and (not args or args[0] is None):
            raise failure

    def _verify(self, handle, path, directory):
        stamp = self.ops.stamp(handle)
        if stamp.directory != directory or self.ops.final_path(handle) != path:
            raise CoreError(
                "SOURCE_PATH_UNSAFE", "Source handle locator or object type mismatch"
            )
        return stamp

    def _directory(self, path):
        if path not in self.handles:
            handle = self.ops.open(path, directory=True)
            try:
                self._verify(handle, path, True)
            except BaseException:
                self.ops.close(handle)
                raise
            self.handles[path] = handle
        return self.handles[path]

    def configure(self, configuration):
        exclusions = []
        for layer in configuration.layers:
            path = self.source_root
            if layer.root_relative_path != ".":
                for part in layer.root_relative_path.split("/"):
                    path = path / part
                    self._directory(path)
            if path.is_relative_to(self.state_root):
                raise CoreError(
                    "SOURCE_LAYER_INVALID",
                    "Source layer cannot be inside project state",
                )
            path = self.ops.final_path(self.handles[path])
            self.layers[layer.layer_id] = path
            if self.state_root.is_relative_to(path):
                exclusions.append(
                    (layer.layer_id, self.state_root.relative_to(path).as_posix())
                )
        return tuple(exclusions)

    def inventory(self, configuration, exclusions):
        excluded = dict(exclusions)
        result = []
        for layer in configuration.layers:
            root = self.layers[layer.layer_id]
            pending = [(root, "")]
            while pending:
                path, relative = pending.pop()
                handle = self._directory(path)
                # Root and every empty directory participate in the pass comparison.
                result.append(
                    TreeItem(layer.layer_id, relative, self.ops.stamp(handle))
                )
                children = []
                for child in self.ops.enumerate(handle):
                    if (
                        len(result) + len(pending) + len(children)
                        >= _MAX_INVENTORY_ITEMS
                    ):
                        raise CoreError(
                            "SOURCE_CAPTURE_LIMIT_EXCEEDED",
                            "Source inventory exceeds its resource limit",
                        )
                    children.append(child)
                children.sort(key=lambda item: item[0].encode("utf-8"))
                for name, stamp in children:
                    rel = relative + "/" + name if relative else name
                    if rel == excluded.get(layer.layer_id):
                        continue
                    child = path / name
                    if stamp.directory:
                        opened = self._directory(child)
                        actual = self.ops.stamp(opened)
                        if actual.identity != stamp.identity or not actual.directory:
                            raise CoreError(
                                "SOURCE_CAPTURE_CHANGED",
                                "Source directory changed during inventory",
                            )
                        pending.append((child, rel))
                    else:
                        opened = self.ops.open(child, directory=False)
                        try:
                            actual = self._verify(opened, child, False)
                            if actual.identity != stamp.identity or stamp.directory:
                                raise CoreError(
                                    "SOURCE_CAPTURE_CHANGED",
                                    "Source identity changed during inventory",
                                )
                            result.append(TreeItem(layer.layer_id, rel, actual))
                        finally:
                            self.ops.close(opened)
        return tuple(result)

    @contextmanager
    def read(self, item):
        path = self.layers[item.layer_id] / item.relative_path
        handle = self.ops.open(path, directory=False)
        try:
            if self._verify(handle, path, False) != item.stamp:
                raise CoreError(
                    "SOURCE_CAPTURE_CHANGED", "Source file changed before reading"
                )
            yield self.ops.chunks(handle)
            if self.ops.stamp(handle) != item.stamp:
                raise CoreError(
                    "SOURCE_CAPTURE_CHANGED", "Source file changed while reading"
                )
        finally:
            self.ops.close(handle)
        # Reopen only for metadata and verify pathname identity after read close.
        handle = self.ops.open(path, directory=False)
        try:
            if self._verify(handle, path, False) != item.stamp:
                raise CoreError(
                    "SOURCE_CAPTURE_CHANGED", "Source file changed after reading"
                )
        finally:
            self.ops.close(handle)


def _require_local_path(ops, path):
    if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
        raise CoreError(
            "SNAPSHOT_CORRUPT", "Retained path must be an absolute trusted locator"
        )
    if path.drive.startswith("\\\\") or not ops.local_drive(path.anchor):
        raise CoreError(
            "CAPTURE_PLATFORM_UNSUPPORTED", "Retained pins require a fixed local volume"
        )


@contextmanager
def pinned_retained(path: Path, maximum: int):
    """Yield retained bytes while the no-follow file/ancestor pins remain held.

    Trusted callers authorize before entry and keep every path-based reader open
    only inside this scope. For finalized SQLite use mode=ro&immutable=1, verify
    sidecar absence separately, and close the connection before leaving scope.
    This guards the main file, not arbitrary paths a consumer elects to open.
    """
    ops, handles = WindowsHandleOps(), []
    _require_local_path(ops, path)
    try:
        for ancestor in reversed(path.parents):
            handle = ops.open(ancestor, directory=True)
            handles.append(handle)
            if not ops.stamp(handle).directory or ops.final_path(handle) != ancestor:
                raise CoreError("SNAPSHOT_CORRUPT", "Invalid retained source ancestor")
        handle = ops.open(path, directory=False)
        handles.append(handle)
        before = _retained_stamp(ops, handle)
        if before.directory or ops.final_path(handle) != path or before.size > maximum:
            raise CoreError("SNAPSHOT_CORRUPT", "Invalid retained source file")
        raw = bytearray()
        for chunk in ops.chunks(handle):
            if len(raw) + len(chunk) > maximum:
                raise CoreError(
                    "SNAPSHOT_CORRUPT", "Retained source exceeds declared size"
                )
            raw.extend(chunk)
        if _retained_stamp(ops, handle) != before:
            raise CoreError("SNAPSHOT_CORRUPT", "Retained source changed while reading")
        yield bytes(raw)
        if _retained_stamp(ops, handle) != before:
            raise CoreError(
                "SNAPSHOT_CORRUPT", "Retained file changed during pinned operation"
            )
    finally:
        _close_all(ops, handles)


def read_retained(path: Path, maximum: int) -> bytes:
    """Read and verify retained bytes, releasing all pins before returning."""
    with pinned_retained(path, maximum) as raw:
        return raw


def _retained_stamp(ops, handle):
    stamp = ops.stamp(handle)
    info = _Info()
    ops._checked(ops.api.GetFileInformationByHandle(handle, c.byref(info)))
    if info.links != 1:
        raise CoreError(
            "SNAPSHOT_CORRUPT", "Retained files must not have hardlink aliases"
        )
    return stamp


def _close_all(ops, handles):
    active_error = sys.exc_info()[0] is not None
    close_error = None
    for handle in reversed(handles):
        try:
            ops.close(handle)
        except BaseException as exc:
            close_error = close_error or exc
    if close_error is not None and not active_error:
        raise close_error


@contextmanager
def pinned_directory(path: Path):
    """Hold a trusted directory and its no-follow ancestors against write/delete.

    Yield its verified final Path. Pins prevent renaming this directory itself;
    target directory pin also prevents normal cross-parent child renames on
    Windows. This is not a publication rename API. Existing children are not
    recursively pinned. No source authorization is inferred by this API.
    """
    ops, handles = WindowsHandleOps(), []
    _require_local_path(ops, path)
    try:
        for ancestor in (*reversed(path.parents), path):
            handle = ops.open(ancestor, directory=True)
            handles.append(handle)
            if not ops.stamp(handle).directory or ops.final_path(handle) != ancestor:
                raise CoreError(
                    "SNAPSHOT_CORRUPT", "Invalid retained directory ancestor"
                )
        yield ops.final_path(handle)
    finally:
        _close_all(ops, handles)


def flush_owned(path: Path) -> None:
    """Flush one caller-owned regular staging file without changing its bytes.

    Call after the producer has closed the file, before opening readonly pins.
    This is not a general published-file mutation capability or a directory
    durability guarantee. Ancestors and the write-capable leaf deny other writers.
    """
    with pinned_directory(path.parent):
        ops = WindowsHandleOps()
        handle = ops.open_write(path)
        try:
            before = _retained_stamp(ops, handle)
            if before.directory or ops.final_path(handle) != path:
                raise CoreError("SNAPSHOT_CORRUPT", "Invalid owned file for flush")
            ops.flush(handle)
            if _retained_stamp(ops, handle) != before:
                raise CoreError("SNAPSHOT_CORRUPT", "Owned file changed while flushing")
        finally:
            _close_all(ops, [handle])
