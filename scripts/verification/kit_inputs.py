"""Bounded archive extraction and explicit hash-lock parsing for delivery tools."""
import re
import shutil
import stat
import tarfile
import zipfile


def lock_entries(path):
    text = "\n".join(
        line.split("#", 1)[0] for line in path.read_text("utf-8").splitlines()
    )
    result = {}
    for line in text.replace("\\\n", " ").splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(
            r"\s*([a-zA-Z0-9][a-zA-Z0-9_.-]*)==([a-zA-Z0-9_.+!-]+)((?:\s+--hash=sha256:[a-f0-9]{64})+)\s*",
            line,
        )
        if not match:
            raise ValueError("Unsupported or unhashed lock entry")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        key = (name, match[2])
        if key in result:
            raise ValueError("Duplicate lock identity")
        result[key] = set(re.findall(r"sha256:([a-f0-9]{64})", match[3]))
    if not result:
        raise ValueError("Empty lock")
    return result


def member_path(name, destination, seen):
    parts = name.rstrip("/").split("/")
    if (
        not parts
        or "\\" in name
        or any(
            not p
            or p in {".", ".."}
            or p[-1:] in {".", " "}
            or any(ord(c) < 32 or c in ':<>"|?*' for c in p)
            or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", p)
            for p in parts
        )
    ):
        raise ValueError("Unsafe archive member")
    key = "/".join(parts).casefold()
    if key in seen:
        raise ValueError("Duplicate archive member")
    seen.add(key)
    target = destination.joinpath(*parts)
    if not target.resolve().is_relative_to(destination.resolve()):
        raise ValueError("Archive member escapes destination")
    return target


def extract(archive_path, destination):
    """Only regular files/directories, before any package code is installed."""
    destination.mkdir(parents=True, exist_ok=False)
    seen, total = set(), 0
    is_zip = zipfile.is_zipfile(archive_path)
    archive = zipfile.ZipFile(archive_path) if is_zip else tarfile.open(archive_path)
    with archive:
        members = archive.infolist() if is_zip else archive.getmembers()
        if len(members) > 10000:
            raise ValueError("Archive member limit")
        planned = []
        for member in members:
            if is_zip:
                # ZipInfo normalizes backslashes on Windows and truncates NULs.
                # Validate the original archive spelling before either conversion.
                name, size, directory = (
                    member.orig_filename,
                    member.file_size,
                    member.is_dir(),
                )
                mode = stat.S_IFMT(member.external_attr >> 16)
                regular = mode in (0, stat.S_IFREG, stat.S_IFDIR)
            else:
                name, size, directory = member.name, member.size, member.isdir()
                regular = member.isfile() or directory
            if not regular or size < 0 or size > 128 * 1024**2:
                raise ValueError("Unsupported archive member")
            total += size
            if total > 1024**3:
                raise ValueError("Archive size limit")
            planned.append((member, member_path(name, destination, seen), directory))
        for member, target, directory in planned:
            if directory:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.open(member) if is_zip else archive.extractfile(member)
                with source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=65536)
