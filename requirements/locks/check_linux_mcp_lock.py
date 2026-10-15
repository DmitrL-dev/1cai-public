"""Build-time, offline checks of the explicitly selected Linux MCP wheels.

This inspects data only. It does not install/import wheel contents or qualify a
Linux runtime. ``packaging`` is a build/test tool, not a kit runtime dependency.
"""
from __future__ import annotations

import argparse
import email.parser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
from urllib.parse import urlparse
import zipfile

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

HERE = Path(__file__).resolve().parent
DEFAULT_PROVENANCE = HERE / "mcp-py311-linux-x86_64.provenance.json"
DEFAULT_LOCK = HERE / "mcp-py311-linux-x86_64.txt"
MARKER_ENVIRONMENT = {
    "implementation_name": "cpython", "implementation_version": "3.11.15",
    "os_name": "posix", "platform_machine": "x86_64",
    "platform_release": "", "platform_system": "Linux", "platform_version": "",
    "python_full_version": "3.11.15", "platform_python_implementation": "CPython",
    "python_version": "3.11", "sys_platform": "linux", "extra": "",
}
MAX_WHEEL_BYTES = 32 * 1024 * 1024
MAX_TOTAL_WHEEL_BYTES = 128 * 1024 * 1024
MAX_MEMBERS = 10000
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_METADATA_BYTES = 2 * 1024 * 1024
HASH = re.compile(r"[0-9a-f]{64}\Z")
LOCK_LINE = re.compile(r"([a-z0-9][a-z0-9.-]*)==([^\s]+) --hash=sha256:([0-9a-f]{64})\Z")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bounded_file(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"not a regular file: {path.name}")
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f"file byte bound exceeded: {path.name}")
    return data


def target_tags():
    """CPython 3.11 / glibc 2.34; no host-derived platform or ABI tags."""
    platforms = [f"manylinux_2_{n}_x86_64" for n in range(34, 4, -1)]
    platforms += ["manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"]
    return set(cpython_tags((3, 11), abis=["cp311"], platforms=platforms)) | set(
        compatible_tags((3, 11), interpreter="cp311", platforms=platforms)
    )


def _wheel_tags(filename: str):
    parsed = parse_wheel_filename(filename)
    allowed_platforms = {tag.platform for tag in target_tags()}
    if (any(character in filename for character in "/\\:\x00")
            or not parsed[3] & target_tags()
            or any(tag.platform not in allowed_platforms for tag in parsed[3])):
        raise ValueError(f"wrong target wheel: {filename}")
    return parsed


def _check_target(document: dict) -> None:
    target = document.get("target", {})
    expected = {
        "implementation": "cpython", "python_version": "3.11", "python_full_version": "3.11.15",
        "machine": "x86_64", "sys_platform": "linux", "glibc_minimum": "2.34",
        "uv_python_platform": "x86_64-manylinux_2_34",
    }
    if document.get("schema_version") != 1 or document.get("root_requirement") != "mcp==1.30.0":
        raise ValueError("unsupported schema or root requirement")
    if any(target.get(key) != value for key, value in expected.items()):
        raise ValueError("wrong dependency target")
    if target.get("marker_environment") != MARKER_ENVIRONMENT:
        raise ValueError("wrong target marker environment")
    if target.get("unevaluated_marker_fields") != ["platform_release", "platform_version"]:
        raise ValueError("unknown kernel marker policy")


def validate_dependency_closure(wheels: list[dict], marker_environment: dict) -> dict:
    """Evaluate all base/activated-extra requirements with an explicit target.

    Never let packaging fill in this process's macOS/Windows marker values.
    Kernel release/version are deliberately unqualified and forbidden in markers.
    """
    if marker_environment != MARKER_ENVIRONMENT:
        raise ValueError("wrong target marker environment")
    selected = {entry["name"]: entry for entry in wheels}
    if len(selected) != len(wheels) or "mcp" not in selected or selected["mcp"]["version"] != "1.30.0":
        raise ValueError("duplicate package or missing exact MCP root")
    for name, entry in selected.items():
        if canonicalize_name(name) != name:
            raise ValueError("noncanonical package name")
        if not SpecifierSet(entry["requires_python"]).contains("3.11.15"):
            raise ValueError(f"incompatible Requires-Python: {name}")
        for raw in entry["requires_dist"]:
            requirement = Requirement(raw)
            if requirement.url is not None:
                raise ValueError("direct dependency URL is not permitted")
            if requirement.marker and re.search(r"\bplatform_(release|version)\b", str(requirement.marker)):
                raise ValueError("unqualified kernel marker")
    extras = {"mcp": {""}}
    pending = ["mcp"]
    while pending:
        name = pending.pop()
        entry = selected[name]
        for raw in entry["requires_dist"]:
            requirement = Requirement(raw)
            active = any(
                requirement.marker is None or requirement.marker.evaluate({**marker_environment, "extra": extra})
                for extra in extras[name]
            )
            if not active:
                continue
            dependency = canonicalize_name(requirement.name)
            target = selected.get(dependency)
            if target is None or not requirement.specifier.contains(target["version"]):
                raise ValueError(f"missing or incompatible active dependency: {name} -> {requirement}")
            requested = {canonicalize_name(extra) for extra in requirement.extras}
            if not requested <= {canonicalize_name(extra) for extra in target["provides_extra"]}:
                raise ValueError(f"unknown dependency extra: {dependency}")
            active_extras = extras.setdefault(dependency, set())
            expanded = active_extras | requested | {""}
            if expanded != active_extras:
                extras[dependency] = expanded
                pending.append(dependency)
    if set(extras) != set(selected):
        raise ValueError(f"unreachable packages: {sorted(set(selected) - set(extras))}")
    return {name: sorted(value - {""}) for name, value in sorted(extras.items())}


def load_inputs(provenance_path: Path = DEFAULT_PROVENANCE, lock_path: Path = DEFAULT_LOCK) -> dict:
    """Validate selected manifest data and its exact one-wheel-per-package lock."""
    document = json.loads(_bounded_file(Path(provenance_path), 2 * 1024 * 1024))
    _check_target(document)
    wheels = document.get("wheels", [])
    if not isinstance(wheels, list) or not 1 <= len(wheels) <= 128:
        raise ValueError("package count bound")
    expected_lock, filenames, total = {}, set(), 0
    for entry in wheels:
        name, version, filename = entry["name"], entry["version"], entry["filename"]
        parsed_name, parsed_version, _, tags = _wheel_tags(filename)
        if parsed_name != name or str(parsed_version) != version:
            raise ValueError(f"wrong target wheel: {filename}")
        if name in expected_lock or filename in filenames or name == "pywin32":
            raise ValueError("duplicate or Windows-only package")
        size = entry["size_bytes"]
        if type(size) is not int or not 0 < size <= MAX_WHEEL_BYTES or not HASH.fullmatch(entry["sha256"]):
            raise ValueError("invalid wheel size/hash")
        url = urlparse(entry["url"])
        if (url.scheme != "https" or url.netloc != "files.pythonhosted.org" or url.query or url.fragment
                or PurePosixPath(url.path).name != filename):
            raise ValueError("invalid original wheel URL")
        if entry["pypi_json_url"] != f"https://pypi.org/pypi/{name}/{version}/json":
            raise ValueError("invalid PyPI metadata URL")
        if not HASH.fullmatch(entry["pypi_json_sha256"]) or not HASH.fullmatch(entry["metadata_sha256"]):
            raise ValueError("invalid metadata digest")
        if not 1 <= len(entry["license_files"]) <= 128:
            raise ValueError("missing license evidence")
        license_names = set()
        license_total = 0
        for license_file in entry["license_files"]:
            if (license_file["path"] in license_names or not HASH.fullmatch(license_file["sha256"])
                    or type(license_file["size_bytes"]) is not int or not 0 < license_file["size_bytes"] <= MAX_METADATA_BYTES):
                raise ValueError("invalid license evidence")
            license_names.add(license_file["path"])
            license_total += license_file["size_bytes"]
        if license_total > 16 * 1024 * 1024:
            raise ValueError("license byte bound")
        if (not isinstance(entry["requires_dist"], list) or len(entry["requires_dist"]) > 512
                or any(not isinstance(raw, str) or len(raw) > 4096 for raw in entry["requires_dist"])
                or not isinstance(entry["provides_extra"], list) or len(entry["provides_extra"]) > 128):
            raise ValueError("dependency metadata bound")
        total += size
        filenames.add(filename)
        expected_lock[name] = (version, entry["sha256"])
    if total > MAX_TOTAL_WHEEL_BYTES:
        raise ValueError("total wheel byte bound")
    actual_lock = {}
    for line in _bounded_file(Path(lock_path), 128 * 1024).decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        match = LOCK_LINE.fullmatch(line)
        if match is None or match[1] in actual_lock:
            raise ValueError("unpinned, duplicate or remote lock entry")
        actual_lock[match[1]] = (match[2], match[3])
    if actual_lock != expected_lock:
        raise ValueError("lock and provenance differ")
    document["activated_extras"] = validate_dependency_closure(wheels, document["target"]["marker_environment"])
    return document


def _zip_members(archive: zipfile.ZipFile) -> dict:
    members = archive.infolist()
    if not 0 < len(members) <= MAX_MEMBERS or sum(info.file_size for info in members) > MAX_EXPANDED_BYTES:
        raise ValueError("wheel archive member/expanded byte bound")
    names, result = set(), {}
    for info in members:
        name = info.filename
        parts = name.rstrip("/").split("/")
        if (info.orig_filename != name or PurePosixPath(name).is_absolute() or any(p in {"", ".", ".."} for p in parts)
                or "\\" in name or ":" in name or any(ord(c) < 32 for c in name) or len(name) > 512
                or name.rstrip("/").casefold() in names or info.flag_bits & 1
                or stat.S_IFMT(info.external_attr >> 16) not in {0, stat.S_IFREG, stat.S_IFDIR}
                or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                or info.file_size > MAX_WHEEL_BYTES):
            raise ValueError("unsafe wheel archive member")
        names.add(name.rstrip("/").casefold())
        result[name] = info
    return result


def _zip_extra_bound(blob: bytes, start: int, length: int) -> None:
    end = start + length
    while start < end:
        if start + 4 > end:
            raise ValueError("wheel ZIP extra field bound")
        kind, size = struct.unpack_from("<HH", blob, start)
        start += 4 + size
        if kind == 1 or start > end:
            raise ValueError("wheel ZIP64 or extra field bound")


def _zip_local_interval(blob: bytes, central: tuple, name: bytes, directory_offset: int) -> tuple[int, int]:
    compressed, expanded, local_offset = central[8], central[9], central[16]
    if local_offset + 30 > directory_offset or blob[local_offset:local_offset + 4] != b"PK\x03\x04":
        raise ValueError("wheel ZIP local header bound")
    local = struct.unpack_from("<4s5H3L2H", blob, local_offset)
    name_size, extra_size = local[9], local[10]
    data_start = local_offset + 30 + name_size + extra_size
    data_end = data_start + compressed
    if (not 1 <= name_size <= 2048 or extra_size > 4096 or data_end > directory_offset
            or local[1] > 20 or local[2] != central[3] or local[3] != central[4]
            or blob[local_offset + 30:local_offset + 30 + name_size] != name):
        raise ValueError("wheel ZIP local header/data bound")
    _zip_extra_bound(blob, local_offset + 30 + name_size, extra_size)
    expected_sizes = (central[7], compressed, expanded)
    if central[3] & 8:
        if any(actual not in (0, expected) for actual, expected in zip(local[6:9], expected_sizes)):
            raise ValueError("wheel ZIP local descriptor sizes differ")
        descriptor = data_end + (4 if blob[data_end:data_end + 4] == b"PK\x07\x08" else 0)
        if descriptor + 12 > directory_offset or struct.unpack_from("<3L", blob, descriptor) != expected_sizes:
            raise ValueError("wheel ZIP data descriptor bound")
        data_end = descriptor + 12
    elif local[6:9] != expected_sizes:
        raise ValueError("wheel ZIP local sizes differ")
    return local_offset, data_end


def _zip_directory_bound(blob: bytes) -> None:
    # Walk actual central records before ZipFile allocates ZipInfo objects. EOCD
    # record counts alone are untrusted: ZipFile parses the whole byte directory.
    start = max(0, len(blob) - 65557)
    position = blob.rfind(b"PK\x05\x06", start)
    if position < 0 or len(blob) < position + 22:
        raise ValueError("missing wheel ZIP directory")
    _, disk, directory_disk, on_disk, count, size, offset, comment = struct.unpack_from("<4s4H2LH", blob, position)
    if (disk or directory_disk or on_disk != count or not 0 < count <= MAX_MEMBERS
            or count == 65535 or size > 4 * 1024 * 1024 or offset + size != position
            or position + 22 + comment != len(blob) or blob[max(0, position - 20):position - 16] == b"PK\x06\x07"):
        raise ValueError("wheel ZIP directory bound")
    cursor, actual_count, expanded_bytes = offset, 0, 0
    intervals = []
    while cursor < position:
        if cursor + 46 > position or blob[cursor:cursor + 4] != b"PK\x01\x02":
            raise ValueError("wheel ZIP central directory record bound")
        central = struct.unpack_from("<4s6H3L5H2L", blob, cursor)
        name_size, extra_size, comment_size = central[10:13]
        end = cursor + 46 + name_size + extra_size + comment_size
        if (not 1 <= name_size <= 2048 or extra_size > 4096 or comment_size > 4096 or end > position
                or central[13] or central[2] > 20 or central[3] & ~0x080E or central[4] not in {0, 8}
                or 0xFFFFFFFF in (central[8], central[9], central[16]) or central[9] > MAX_WHEEL_BYTES):
            raise ValueError("wheel ZIP central directory field bound/ZIP64/multidisk")
        actual_count += 1
        expanded_bytes += central[9]
        if actual_count > MAX_MEMBERS or expanded_bytes > MAX_EXPANDED_BYTES:
            raise ValueError("wheel ZIP actual directory count/expanded bound")
        name_start = cursor + 46
        _zip_extra_bound(blob, name_start + name_size, extra_size)
        intervals.append(_zip_local_interval(blob, central, blob[name_start:name_start + name_size], offset))
        cursor = end
    if cursor != position or actual_count != count:
        raise ValueError("wheel ZIP actual directory count differs")
    previous_end = 0
    for local_start, local_end in sorted(intervals):
        if local_start < previous_end:
            raise ValueError("wheel ZIP local records overlap")
        previous_end = local_end


def verify_wheelhouse(
    wheelhouse: Path, *, provenance_path: Path = DEFAULT_PROVENANCE, lock_path: Path = DEFAULT_LOCK,
) -> dict:
    """Check every original wheel before use; missing/extra/changed inputs fail."""
    import io

    document = load_inputs(provenance_path, lock_path)
    wheelhouse = Path(wheelhouse)
    if wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise ValueError("wheelhouse must be a real directory")
    inventory = list(wheelhouse.iterdir())
    if len(inventory) > 128 or {path.name for path in inventory} != {w["filename"] for w in document["wheels"]}:
        raise ValueError("wheelhouse inventory differs")
    checked = []
    for entry in document["wheels"]:
        blob = _bounded_file(wheelhouse / entry["filename"], entry["size_bytes"])
        if len(blob) != entry["size_bytes"] or _digest(blob) != entry["sha256"]:
            raise ValueError(f"wheel size/hash differs: {entry['filename']}")
        _zip_directory_bound(blob)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            members = _zip_members(archive)
            prefix = f"{entry['name'].replace('-', '_')}-{entry['version']}.dist-info/"
            metadata_names = [name for name in members if name.endswith(".dist-info/METADATA")]
            if metadata_names != [prefix + "METADATA"] or members[metadata_names[0]].file_size > MAX_METADATA_BYTES:
                raise ValueError("wheel METADATA identity/count/bound")
            raw = archive.read(metadata_names[0])
            if _digest(raw) != entry["metadata_sha256"]:
                raise ValueError("wheel metadata digest differs")
            metadata = email.parser.BytesParser().parsebytes(raw)
            if (canonicalize_name(metadata["Name"]) != entry["name"] or metadata["Version"] != entry["version"]
                    or metadata.get("Requires-Python", "") != entry["requires_python"]
                    or metadata.get_all("Requires-Dist", []) != entry["requires_dist"]
                    or metadata.get_all("Provides-Extra", []) != entry["provides_extra"]
                    or metadata.get("License-Expression", "") != entry["license_expression"]):
                raise ValueError("wheel dependency/license metadata differs")
            wheel_name = prefix + "WHEEL"
            if wheel_name not in members or members[wheel_name].file_size > 64 * 1024:
                raise ValueError("wheel tags missing/bound")
            wheel_metadata = email.parser.BytesParser().parsebytes(archive.read(wheel_name))
            from packaging.tags import parse_tag
            declared_tags = set()
            for tag in wheel_metadata.get_all("Tag", []):
                declared_tags.update(parse_tag(tag))
            if declared_tags != parse_wheel_filename(entry["filename"])[3]:
                raise ValueError("wheel filename and WHEEL tags differ")
            for license_file in entry["license_files"]:
                name = license_file["path"]
                if name not in members or members[name].file_size != license_file["size_bytes"]:
                    raise ValueError("wheel license missing/size differs")
                if _digest(archive.read(name)) != license_file["sha256"]:
                    raise ValueError("wheel license digest differs")
        checked.append({key: entry[key] for key in ("name", "version", "filename", "sha256", "size_bytes")})
    return {
        "schema_version": 1, "target": document["target"], "wheels": checked,
        "activated_extras": document["activated_extras"],
        "scope": "offline input validation only; no installation, SDK execution or native Linux qualification",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args()
    print(json.dumps(verify_wheelhouse(args.wheelhouse, provenance_path=args.provenance, lock_path=args.lock), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
