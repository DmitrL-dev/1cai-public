"""Rebuild only sealed live-writer recovery files after an interrupted attempt."""

import hashlib
import os
from pathlib import Path
import stat

from ._windows_source_tree import read_retained
from .errors import CoreError


def prepare_recovery_stage(
    journal, changed_paths, before, *, copy_row, max_bytes, code
):
    """Reuse validated staged files and recreate files consumed by an earlier try."""
    stage = Path(journal) / "recovery-stage"
    expected_files = set(changed_paths)
    expected_dirs = {
        Path(*Path(name).parts[:depth])
        for name in changed_paths
        for depth in range(1, len(Path(name).parts))
    }

    def invalid():
        raise CoreError(code, "Recovery staging is unsafe or inconsistent")

    if stage.exists() or stage.is_symlink():
        info = stage.lstat()
        if not stat.S_ISDIR(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & 0x400
        ):
            invalid()
    else:
        stage.mkdir()

    pending = [stage]
    visited = 0
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as children:
            for child in children:
                visited += 1
                if visited > len(expected_files) * 33:
                    invalid()
                relative = Path(child.path).relative_to(stage)
                # On Windows DirEntry.stat may report st_nlink=0; Path.lstat
                # provides the link count required for the hardlink guard.
                info = Path(child.path).lstat()
                if getattr(info, "st_file_attributes", 0) & 0x400:
                    invalid()
                if stat.S_ISDIR(info.st_mode):
                    if relative not in expected_dirs:
                        invalid()
                    pending.append(Path(child.path))
                elif not (
                    stat.S_ISREG(info.st_mode)
                    and info.st_nlink == 1
                    and relative.as_posix() in expected_files
                ):
                    invalid()

    for name in changed_paths:
        row = before[name]
        staged = stage / name
        if staged.exists():
            raw = read_retained(staged, max_bytes)
            if (
                len(raw) == row["size"]
                and hashlib.sha256(raw).hexdigest() == row["sha256"]
            ):
                continue
            # A shorter file can be left by an interrupted exclusive write.
            # Rebuild it only from the sealed backup; same-size corruption fails closed.
            if len(raw) >= row["size"]:
                invalid()
            staged.unlink()
        copy_row(Path(journal) / "backup", stage, row)
    return stage
