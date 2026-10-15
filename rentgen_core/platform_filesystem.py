"""Explicit OS boundary for copied retained bytes and POSIX capabilities.

Windows retains its original no-follow, deny-write/delete handle implementation.
POSIX operations use descriptor confinement and verified immutable byte copies;
they do not promise a Windows-style filesystem lease.
"""
import sys

from .errors import CoreError


def read_retained(path, maximum):
    if sys.platform == "win32":
        from ._windows_source_tree import read_retained as reader
    elif sys.platform in {"linux", "darwin"}:
        from ._posix_source_tree import read_retained as reader
    else:
        raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "No retained filesystem adapter")
    return reader(path, maximum)


def open_directory(path, *, private=False):
    """Return a POSIX Directory context; there is no fake Windows lease facade."""
    if sys.platform not in {"linux", "darwin"}:
        raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "POSIX directory capability required")
    from ._posix_source_tree import open_directory as opener

    return opener(path, private=private)
