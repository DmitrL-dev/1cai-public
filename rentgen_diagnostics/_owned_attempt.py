"""Private diagnostic attempt creation and exact owned handle-based cleanup.

Win32 contracts: CreateDirectoryW with an explicit protected DACL;
SetFileInformationByHandle(FileDispositionInfo). Every delete reopens no-follow
with DELETE access and compares retained identity before marking that handle.
"""

import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import re
import uuid

from rentgen_core.local_identity import current_windows_principal
from rentgen_core._windows_source_tree import _retained_stamp
from ._runtime_pins import PinFailure, _call


class _Security(c.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", c.c_void_p), ("inherit", w.BOOL)]


class _PrivateFS:
    def __init__(self, pins):
        self.pins = pins
        self.kernel = pins.ops.api
        self.security = c.WinDLL("advapi32", use_last_error=True)
        self.kernel.CreateDirectoryW.argtypes = [w.LPCWSTR, c.POINTER(_Security)]
        self.kernel.CreateDirectoryW.restype = w.BOOL
        self.kernel.LocalFree.argtypes = [c.c_void_p]
        self.kernel.LocalFree.restype = c.c_void_p
        self.kernel.SetFileInformationByHandle.argtypes = [
            w.HANDLE,
            c.c_int,
            c.c_void_p,
            w.DWORD,
        ]
        self.kernel.SetFileInformationByHandle.restype = w.BOOL
        self.security.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            w.LPCWSTR,
            w.DWORD,
            c.POINTER(c.c_void_p),
            c.c_void_p,
        ]
        self.security.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = (
            w.BOOL
        )
        principal = current_windows_principal().id
        if not re.fullmatch(r"windows-sid:S-1-[0-9-]+", principal):
            raise PinFailure("BSL_PROCESS_FAILED")
        self.sid = principal.removeprefix("windows-sid:")
        self.uncertain = []
        self.cleanup_uncertain = False
        self.created_paths = set()

    def _dacl(self, path):
        api = self.security
        api.GetSecurityInfo.argtypes = [
            w.HANDLE,
            c.c_int,
            w.DWORD,
            c.c_void_p,
            c.c_void_p,
            c.c_void_p,
            c.c_void_p,
            c.POINTER(c.c_void_p),
        ]
        api.GetSecurityInfo.restype = w.DWORD
        api.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
            c.c_void_p,
            w.DWORD,
            w.DWORD,
            c.POINTER(w.LPWSTR),
            c.c_void_p,
        ]
        api.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = w.BOOL
        handle = self.kernel.CreateFileW(
            "\\\\?\\" + str(path), 0x20080, 1, None, 3, 0x02200000, None
        )
        if handle == c.c_void_p(-1).value:
            raise PinFailure("BSL_PROCESS_FAILED")
        descriptor, rendered = c.c_void_p(), w.LPWSTR()
        try:
            stamp = _call(self.pins.ops.stamp, handle)
            if not stamp.directory or _call(self.pins.ops.final_path, handle) != path:
                raise PinFailure("BSL_PROCESS_FAILED")
            if api.GetSecurityInfo(
                handle, 1, 4, None, None, None, None, c.byref(descriptor)
            ):
                raise PinFailure("BSL_PROCESS_FAILED")
            if not api.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                descriptor, 1, 4, c.byref(rendered), None
            ):
                raise PinFailure("BSL_PROCESS_FAILED")
            return rendered.value
        finally:
            failed = False
            for value in (c.cast(rendered, c.c_void_p), descriptor):
                if value and self.kernel.LocalFree(value):
                    failed = True
            try:
                self.pins.ops.close(handle)
            except BaseException:
                self.uncertain.append(handle)
                failed = True
            if failed:
                self.cleanup_uncertain = True
                raise PinFailure("BSL_CLEANUP_FAILED") from None

    def mkdir(self, path):
        descriptor = c.c_void_p()
        sddl = f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{self.sid})"
        if not self.security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, c.byref(descriptor), None
        ):
            raise PinFailure("BSL_PROCESS_FAILED")
        try:
            security = _Security(c.sizeof(_Security), descriptor, False)
            if not self.kernel.CreateDirectoryW(
                "\\\\?\\" + str(path), c.byref(security)
            ):
                raise PinFailure("BSL_PROCESS_FAILED")
            self.created_paths.add(path)
            if self._dacl(path) != sddl:
                raise PinFailure("BSL_PROCESS_FAILED")
        finally:
            if self.kernel.LocalFree(descriptor):
                self.cleanup_uncertain = True
                raise PinFailure("BSL_CLEANUP_FAILED")

    def delete_verified(self, path, before):
        # The caller still holds the parent and has closed only this leaf's pin.
        handle = self.kernel.CreateFileW(
            "\\\\?\\" + str(path), 0x10080, 1, None, 3, 0x02200000, None
        )
        if handle == c.c_void_p(-1).value:
            raise PinFailure("BSL_CLEANUP_FAILED")
        try:
            after = _call(
                self.pins.ops.stamp if before.directory else _retained_stamp,
                *((handle,) if before.directory else (self.pins.ops, handle)),
            )
            valid = (
                (after.directory and after.identity == before.identity)
                if before.directory
                else after == before
            )
            if not valid or _call(self.pins.ops.final_path, handle) != path:
                raise PinFailure("BSL_CLEANUP_FAILED")
            deleted = c.c_ubyte(1)
            if not self.kernel.SetFileInformationByHandle(
                handle, 4, c.byref(deleted), c.sizeof(deleted)
            ):
                raise PinFailure("BSL_CLEANUP_FAILED")
        finally:
            try:
                self.pins.ops.close(handle)
            except BaseException:
                self.uncertain.append(handle)
                raise PinFailure("BSL_CLEANUP_FAILED") from None


class OwnedAttempt:
    def __init__(self, parent: Path, pins):
        if (
            not isinstance(parent, Path)
            or not parent.is_absolute()
            or ".." in parent.parts
        ):
            raise PinFailure()
        self.parent, self.pins = parent, pins
        self.path = parent / str(uuid.uuid4())
        self.native = _PrivateFS(pins)
        self.created = False
        self.inventory = None

    def create(self):
        for parent in (*reversed(self.parent.parents), self.parent):
            if not parent.exists():
                self.native.mkdir(parent)
            self.pins.directory(parent)
        try:
            self.native.mkdir(self.path)
        finally:
            self.created = self.path in self.native.created_paths
        self.pins.directory(self.path)
        for name in ("src", "report", "profile", "tmp"):
            self.native.mkdir(self.path / name)
            self.pins.directory(self.path / name)

    def capture_cleanup_inventory(self):
        if not self.created or self.inventory is not None:
            raise PinFailure("BSL_CLEANUP_FAILED")
        pending, objects, byte_count = [self.path], {}, 0
        while pending:
            directory = pending.pop()
            relative = directory.relative_to(self.path)
            if len(relative.parts) > 24:
                raise PinFailure("BSL_RESOURCE_LIMIT")
            objects[directory] = self.pins.stamps[directory]
            for name, stamp in self.pins.watch_directory(directory):
                if len(objects) >= 1024:
                    raise PinFailure("BSL_RESOURCE_LIMIT")
                path = directory / name
                if stamp.directory:
                    self.pins.directory(path)
                    pending.append(path)
                else:
                    byte_count += stamp.size
                    if byte_count > 16 * 1024 * 1024:
                        raise PinFailure("BSL_RESOURCE_LIMIT")
                    if path not in self.pins.handles:
                        self.pins.file(path, maximum=4 * 1024 * 1024)
                    if self.pins.stamps[path] != stamp:
                        raise PinFailure("BSL_INPUT_CHANGED")
                    objects[path] = stamp
        self.pins.verify()
        self.inventory = objects

    def cleanup(self):
        if self.inventory is None:
            raise PinFailure("BSL_CLEANUP_FAILED")
        self.pins.verify()
        for path in sorted(self.inventory, key=lambda p: len(p.parts), reverse=True):
            if path != self.path and not path.is_relative_to(self.path):
                raise PinFailure("BSL_CLEANUP_FAILED")
            expected = self.inventory[path]
            if expected.directory and self.pins._inventory(path):
                raise PinFailure("BSL_CLEANUP_FAILED")
            self.pins.release(path)
            self.native.delete_verified(path, expected)
            self.pins.inventories.pop(path, None)
