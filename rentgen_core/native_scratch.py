"""Delete only owned ibcmd scratch through no-follow, no-delete-sharing handles."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path

from ._windows_source_tree import WindowsHandleOps, pinned_directory, _retained_stamp
from .errors import CoreError
from .snapshots import validate_operation_id

NAMES = ("baseline-extension-properties-data", "candidate-extension-properties-data")


def clear_ibcmd_scratch(run):
    run = Path(run).absolute()
    validate_operation_id(run.name)
    if run.parent.name != "test-runs":
        raise CoreError("NATIVE_CLEANUP_INVALID", "Not an owned test run")
    ops, count, released = WindowsHandleOps(), 0, 0
    dispose = ops.api.SetFileInformationByHandle
    dispose.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
    dispose.restype = w.BOOL

    def remove(path, expected=None, depth=0):
        nonlocal count, released
        count += 1
        if count > 100000 or depth > 128:
            raise CoreError("NATIVE_CLEANUP_LIMIT", "Scratch inventory limit")
        # Read/list + DELETE, open the reparse object itself. Holding every parent
        # and current object without delete sharing prevents path substitution.
        handle = ops.api.CreateFileW(
            "\\\\?\\" + str(path), 0x10081, 1, None, 3, 0x02200000, None
        )
        if handle == c.c_void_p(-1).value:
            raise c.WinError(c.get_last_error())
        try:
            stamp = _retained_stamp(ops, handle)
            if (
                ops.final_path(handle) != path
                or expected is not None
                and stamp.identity != expected
            ):
                raise CoreError(
                    "NATIVE_CLEANUP_INVALID", "Scratch object identity changed"
                )
            if stamp.directory:
                entries = []
                for name, item in ops.enumerate(handle):
                    if count + len(entries) >= 100000:
                        raise CoreError(
                            "NATIVE_CLEANUP_LIMIT", "Scratch inventory limit"
                        )
                    entries.append((name, item.identity))
                for name, identity in entries:
                    remove(path / name, identity, depth + 1)
            flag = c.c_ubyte(1)  # FILE_DISPOSITION_INFO.DeleteFile is BOOLEAN.
            if not dispose(handle, 4, c.byref(flag), c.sizeof(flag)):
                raise c.WinError(c.get_last_error())
            if not stamp.directory:
                released += stamp.size
        finally:
            ops.close(handle)

    try:
        with pinned_directory(run):
            for name in NAMES:
                target = run / name
                # Direct allowlisted child; resolved confinement is rechecked by
                # no-follow handles at every level, including the target itself.
                if not target.is_relative_to(run) or target.parent != run:
                    raise CoreError(
                        "NATIVE_CLEANUP_INVALID", "Scratch path escaped run"
                    )
                try:
                    target.lstat()
                except FileNotFoundError:
                    continue
                remove(target)
    except (OSError, CoreError) as exc:
        return {
            "status": "retained",
            "released_logical_bytes": released,
            "reason": exc.code if isinstance(exc, CoreError) else "FILESYSTEM_ERROR",
        }
    return {"status": "completed", "released_logical_bytes": released}
