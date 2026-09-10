"""Bounded, no-follow inventory of explicitly selected EDT/JDK startup inputs."""
import hashlib
import os
from pathlib import Path

from ._windows_source_tree import WindowsHandleOps, _retained_stamp, pinned_directory
from .errors import CoreError
from .source_paths import validate_inventory_paths

MAX_FILES, MAX_TOTAL, MAX_FILE = 8192, 4 * 1024**3, 256 * 1024**2
BOOT = (
    "configuration/config.ini",
    "configuration/org.eclipse.equinox.simpleconfigurator/bundles.info",
)


def inventory(root, *, java=False, authorize=lambda: None, hashes=True):
    starts = ("bin", "lib", "conf", "release") if java else ("plugins", *BOOT)
    return _inventory(root, starts, authorize=authorize, hashes=hashes)


def exported_inventory(root, *, authorize):
    """Bounded complete export inventory, including unknown files."""
    return _inventory(root, (".",), authorize=authorize, hashes=True)


def _inventory(root, starts, *, authorize, hashes):
    root = Path(root)
    todo = [root / p for p in starts]
    rows, total, visited = [], 0, 0
    ops = WindowsHandleOps()
    with pinned_directory(root):
        while todo:
            authorize()
            path = todo.pop()
            visited += 1
            if visited > MAX_FILES * 2 or len(path.relative_to(root).parts) > 32:
                raise CoreError("EDT_RUNTIME_LIMIT", "Runtime tree exceeds limits")
            stamp = path.stat(follow_symlinks=False)
            if path.is_symlink() or getattr(stamp, "st_file_attributes", 0) & 0x400:
                raise CoreError(
                    "EDT_RUNTIME_INVALID", "Runtime links are not supported"
                )
            if path.is_dir():
                with pinned_directory(path), os.scandir(path) as children:
                    for child in children:
                        todo.append(Path(child.path))
                        if len(todo) + visited > MAX_FILES * 2:
                            raise CoreError(
                                "EDT_RUNTIME_LIMIT", "Too many runtime entries"
                            )
                continue
            handle = ops.open(path, directory=False)
            try:
                info = _retained_stamp(ops, handle)
                if info.directory or ops.final_path(handle) != path:
                    raise CoreError("EDT_RUNTIME_INVALID", "Invalid runtime file")
                total += info.size
                if len(rows) >= MAX_FILES or info.size > MAX_FILE or total > MAX_TOTAL:
                    raise CoreError(
                        "EDT_RUNTIME_LIMIT", "Runtime input volume exceeds limits"
                    )
                row = {"path": path.relative_to(root).as_posix(), "size": info.size}
                if hashes:
                    digest = hashlib.sha256()
                    for chunk in ops.chunks(handle):
                        digest.update(chunk)
                    row["sha256"] = digest.hexdigest()
                rows.append(row)
            finally:
                ops.close(handle)
        authorize()
    validate_inventory_paths(row["path"] for row in rows)
    return sorted(rows, key=lambda row: row["path"])
