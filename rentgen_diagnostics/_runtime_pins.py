"""Retained no-follow runtime filesystem ownership, with deduplicated ancestors.

The internal core _retained_stamp coupling is deliberate: it supplies the same
hardlink/reparse checks as core reads. This module does not change those primitives
or use project/source authorization; its caller supplies the trusted IO boundary.
"""

import hashlib
from pathlib import Path, PurePosixPath

from rentgen_core._windows_source_tree import WindowsHandleOps, _retained_stamp
from rentgen_core.errors import CoreError


class PinFailure(Exception):
    def __init__(self, code="BSL_RUNTIME_MISMATCH"):
        self.code = code
        super().__init__(code)


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except (CoreError, OSError):
        raise PinFailure() from None


class RuntimePins:
    """Explicitly owned pins; failed closure remains poisoned, never retried."""

    def __init__(self, *, check=lambda: None, operations=None):
        self.ops = operations or WindowsHandleOps()
        self.check = check
        self.handles = {}
        self.stamps = {}
        self.inventories = {}
        self.uncertain = []
        self.total_bytes = 0

    def _open(self, path, directory):
        self.check()
        if len(self.handles) + len(self.uncertain) >= 1080:
            # Reserve 20 of the profile's 1100 handles for process/ACL/delete IO.
            raise PinFailure("BSL_RESOURCE_LIMIT")
        handle = _call(self.ops.open, path, directory=directory)
        self.handles[path] = handle
        stamp = _call(
            self.ops.stamp if directory else _retained_stamp,
            *((handle,) if directory else (self.ops, handle)),
        )
        if stamp.directory != directory or _call(self.ops.final_path, handle) != path:
            raise PinFailure()
        self.stamps[path] = stamp
        return handle

    def directory(self, path):
        if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
            raise PinFailure()
        if path.drive.startswith("\\\\") or not _call(
            self.ops.local_drive, path.anchor
        ):
            raise PinFailure("BSL_PLATFORM_UNSUPPORTED")
        for ancestor in (*reversed(path.parents), path):
            if ancestor not in self.handles:
                self._open(ancestor, True)
        return self.handles[path]

    def file(
        self,
        path,
        *,
        expected_bytes=None,
        expected_size=None,
        expected_sha256=None,
        maximum=512 * 1024 * 1024,
        capture=False,
    ):
        self.directory(path.parent)
        if path in self.handles:
            raise PinFailure()
        if expected_bytes is not None:
            expected_size = len(expected_bytes)
            expected_sha256 = hashlib.sha256(expected_bytes).hexdigest()
        handle = self._open(path, False)
        before = self.stamps[path]
        if before.size > maximum or (
            expected_size is not None and before.size != expected_size
        ):
            raise PinFailure()
        if self.total_bytes + before.size > 512 * 1024 * 1024:
            raise PinFailure("BSL_RESOURCE_LIMIT")
        self.total_bytes += before.size
        raw, digest, size = bytearray(), hashlib.sha256(), 0
        try:
            for chunk in self.ops.chunks(handle):
                self.check()
                size += len(chunk)
                if size > maximum or size > before.size:
                    raise PinFailure("BSL_RESOURCE_LIMIT")
                digest.update(chunk)
                if capture:
                    raw.extend(chunk)
        except CoreError:
            raise PinFailure() from None
        after = _call(_retained_stamp, self.ops, handle)
        if (
            before != after
            or size != before.size
            or (expected_sha256 is not None and digest.hexdigest() != expected_sha256)
        ):
            raise PinFailure()
        return bytes(raw) if capture else digest.hexdigest()

    def _inventory(self, path):
        handle = self.directory(path)
        result = []
        try:
            for name, stamp in self.ops.enumerate(handle):
                self.check()
                if len(result) >= 1024:
                    raise PinFailure("BSL_RESOURCE_LIMIT")
                result.append((name, stamp))
        except CoreError:
            raise PinFailure() from None
        return tuple(sorted(result, key=lambda pair: pair[0]))

    def watch_directory(self, path):
        inventory = self._inventory(path)
        if path in self.inventories and self.inventories[path] != inventory:
            raise PinFailure("BSL_INPUT_CHANGED")
        self.inventories[path] = inventory
        return inventory

    def tree(self, root, expected):
        if not 0 < len(expected) <= 1024:
            raise PinFailure("BSL_RESOURCE_LIMIT")
        directories = {""}
        for name in expected:
            parts = PurePosixPath(name).parts
            if (
                not parts
                or name.startswith("/")
                or any(p in ("", ".", "..") or ":" in p or "\\" in p for p in parts)
            ):
                raise PinFailure()
            directories.update(
                str(p) for p in PurePosixPath(name).parents if str(p) != "."
            )
        found = set()
        pending = [root]
        while pending:
            path = pending.pop()
            for name, stamp in self.watch_directory(path):
                child = path / name
                relative = child.relative_to(root).as_posix()
                if stamp.directory:
                    if relative not in directories:
                        raise PinFailure()
                    self.directory(child)
                    pending.append(child)
                else:
                    if relative not in expected or relative in found:
                        raise PinFailure()
                    size, digest = expected[relative]
                    self.file(child, expected_size=size, expected_sha256=digest)
                    if self.stamps[child] != stamp:
                        raise PinFailure()
                    found.add(relative)
        if found != set(expected):
            raise PinFailure()
        self.verify()

    def verify(self):
        for path, handle in self.handles.items():
            self.check()
            before = self.stamps.get(path)
            if before is None:
                raise PinFailure()
            after = _call(
                self.ops.stamp if before.directory else _retained_stamp,
                *((handle,) if before.directory else (self.ops, handle)),
            )
            if before.directory:
                valid = after.directory and after.identity == before.identity
            else:
                valid = after == before
            if not valid or _call(self.ops.final_path, handle) != path:
                raise PinFailure("BSL_INPUT_CHANGED")
        for path, expected in self.inventories.items():
            if self._inventory(path) != expected:
                raise PinFailure("BSL_INPUT_CHANGED")

    def release(self, path):
        handle = self.handles.pop(path)
        try:
            self.ops.close(handle)
        except BaseException:
            self.uncertain.append(handle)
            raise PinFailure("BSL_CLEANUP_FAILED") from None

    def close(self):
        for path in reversed(tuple(self.handles)):
            try:
                self.release(path)
            except PinFailure:
                pass
        if self.uncertain:
            raise PinFailure("BSL_CLEANUP_FAILED")
