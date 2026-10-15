"""Extract pinned editor/runtime ZIPs into one new, owned directory."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import unicodedata
import zipfile


MAX_ENTRIES = 50_000
MAX_MEMBER_BYTES = 512 * 1024**2
MAX_TOTAL_BYTES = 2 * 1024**3
_CHUNK = 64 * 1024
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|CLOCK\$|COM[1-9¹²³]|LPT[1-9¹²³])", re.I)


def _plain_directory(path):
    value = path.lstat()
    if not stat.S_ISDIR(value.st_mode) or getattr(value, "st_file_attributes", 0) & _REPARSE:
        raise ValueError("Destination ancestor is not a plain directory")


def _new_destination(destination):
    for parent in (destination.parent, *destination.parent.parents):
        _plain_directory(parent)
    try:
        destination.lstat()
    except FileNotFoundError:
        return
    raise FileExistsError("Archive destination must be new")


def _verify_source(source, expected_hash, expected_size):
    source.seek(0)
    digest, count = hashlib.sha256(), 0
    while chunk := source.read(min(_CHUNK, expected_size - count + 1)):
        count += len(chunk)
        if count > expected_size:
            raise ValueError("Archive size differs from pin")
        digest.update(chunk)
    if count != expected_size or digest.hexdigest() != expected_hash:
        raise ValueError("Archive bytes differ from pin")
    source.seek(0)


def _parts(info):
    # ZipInfo.filename can already have lost a NUL suffix or a Windows separator.
    name = info.orig_filename
    if not name or "\\" in name or name.startswith("/"):
        raise ValueError("Unsafe archive member path")
    directory = name.endswith("/")
    parts = name[:-1].split("/") if directory else name.split("/")
    for part in parts:
        if (
            not part or part in {".", ".."} or part.endswith((".", " "))
            or any(char in ':<>"|?*' or unicodedata.category(char) in {"Cc", "Cf", "Cs"}
                   for char in part)
            or _RESERVED.fullmatch(part.split(".", 1)[0].rstrip(" "))
        ):
            raise ValueError("Unsafe archive member path")
    if info.filename != name:
        raise ValueError("Archive member spelling was normalized")
    return parts, directory


def _preflight(package):
    members = package.infolist()
    if len(members) > MAX_ENTRIES:
        raise ValueError("Archive entry limit exceeded")
    nodes, explicit, planned, total = {}, set(), [], 0
    for info in members:
        parts, directory = _parts(info)
        mode = stat.S_IFMT(info.external_attr >> 16)
        dos_attributes = info.external_attr & 0xFFFF
        if (
            info.flag_bits & (1 | 0x40)
            or mode not in (0, stat.S_IFREG, stat.S_IFDIR)
            or mode == stat.S_IFDIR and not directory
            or mode == stat.S_IFREG and directory
            or dos_attributes & (0x08 | 0x40 | _REPARSE)
            or dos_attributes & 0x10 and not directory
            or directory and info.file_size != 0
            or not 0 <= info.file_size <= MAX_MEMBER_BYTES
            or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED,
                                          zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA)
        ):
            raise ValueError("Unsupported archive member")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Archive expanded size limit exceeded")
        name = "/".join(parts)
        key = name.casefold()
        if key in explicit:
            raise ValueError("Duplicate archive member")
        explicit.add(key)
        for length in range(1, len(parts) + 1):
            spelling = "/".join(parts[:length])
            folded = spelling.casefold()
            kind = "directory" if length < len(parts) or directory else "file"
            previous = nodes.get(folded)
            if previous is not None and previous != (spelling, "directory"):
                raise ValueError("Archive path collision or file/directory shadow")
            if previous is not None and kind != "directory":
                raise ValueError("Archive path collision or file/directory shadow")
            nodes[folded] = (spelling, kind)
        planned.append((info, parts, directory))
    return planned


def _directories(root, parts):
    current = root
    _plain_directory(current)
    for part in parts:
        current = current / part
        try:
            current.mkdir(mode=0o700)
        except FileExistsError:
            pass
        _plain_directory(current)
    return current


def extract_verified(archive, dest, *, sha256, size_bytes):
    """Return {relative_file: {sha256, size_bytes}} for actual extracted bytes.

    The destination parent must exist without symlink/reparse ancestors. Pin or
    preflight refusal creates nothing. A stream/CRC failure can leave a partial
    new destination for inspection; an existing destination is never reused.
    """
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("A lowercase SHA256 archive pin is required")
    if type(size_bytes) is not int or size_bytes < 0:
        raise ValueError("An exact nonnegative archive size pin is required")
    archive, destination = Path(archive), Path(dest).absolute()
    _new_destination(destination)
    initial = archive.lstat()
    if not stat.S_ISREG(initial.st_mode) or getattr(initial, "st_file_attributes", 0) & _REPARSE:
        raise ValueError("Pinned archive must be a regular file")
    with archive.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino) != (initial.st_dev, initial.st_ino):
            raise ValueError("Pinned archive changed while opening")
        if opened.st_size != size_bytes:
            raise ValueError("Archive size differs from pin")
        _verify_source(source, sha256, size_bytes)
        with zipfile.ZipFile(source) as package:
            planned = _preflight(package)
            _new_destination(destination)
            destination.mkdir(mode=0o700)
            inventory, total = {}, 0
            for info, parts, directory in planned:
                parent = _directories(destination, parts if directory else parts[:-1])
                if directory:
                    continue
                target = parent / parts[-1]
                if not target.resolve().is_relative_to(destination):
                    raise ValueError("Archive member escapes destination")
                digest, count = hashlib.sha256(), 0
                with package.open(info) as incoming, target.open("xb") as outgoing:
                    while chunk := incoming.read(min(_CHUNK, info.file_size - count + 1)):
                        count += len(chunk)
                        total += len(chunk)
                        if count > info.file_size or count > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES:
                            raise ValueError("Archive stream exceeds declared bounds")
                        outgoing.write(chunk)
                        digest.update(chunk)
                if count != info.file_size:
                    raise ValueError("Archive stream size differs from declaration")
                inventory["/".join(parts)] = {"sha256": digest.hexdigest(), "size_bytes": count}
        # Keep the same input handle and refuse success if its bytes changed.
        _verify_source(source, sha256, size_bytes)
    return dict(sorted(inventory.items()))
