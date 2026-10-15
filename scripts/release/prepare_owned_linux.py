"""Export an unaccepted, versioned Linux/CPython 3.11 CLI + official MCP kit.

This new profile never reads or changes accepted experimental supplement records.
It executes neither delivered binaries nor package installers. Qualification of
the final extracted bytes belongs to a separate actual GNU/Linux acceptance.
"""
import argparse
import base64
import csv
from email.parser import BytesParser
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import types
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PROFILE = "owned-linux-cli-mcp-py311-x86_64-v1"
MANIFEST = "owned-linux-manifest-v1.json"
CHECKSUMS = "owned-linux-SHA256SUMS"
MAX_FILE = 64 * 1024**2
MAX_TOTAL = 128 * 1024**2
MAX_JSON = 1024**2
MAX_MEMBERS = 4096
PACKAGES = ("rentgen_core", "rentgen_graph", "rentgen_diagnostics")
LOCK = "requirements/locks/mcp-py311-linux-x86_64.txt"
PROVENANCE = "requirements/locks/mcp-py311-linux-x86_64.provenance.json"
CHECKER = "requirements/locks/check_linux_mcp_lock.py"
SOURCE_NOTICES = (
    "LICENSE", "go/go.mod", "rust/input-core/Cargo.toml",
    "rust/input-core/Cargo.lock", "rust/input-core/PROTOCOL.md",
    "rust/input-core/THIRD_PARTY_NOTICES.md",
    "rust/input-core/DEPENDENCY_PROVENANCE.json", "rust/input-core/licenses",
)
GO_LICENSE_SHA256 = "911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad"
PLATFORM = {
    "os": "GNU/Linux", "architecture": "x86_64", "implementation": "CPython",
    "python": "3.11.15", "glibc_minimum": "2.34", "kernel_minimum": "5.9",
    "requires": ["libgcc_s.so.1", "memfd seals", "/proc/self/fd"],
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def parse_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected.split()):
        raise ValueError("Unexpected input schema")


def digest(value, length=64):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{%d}" % length, value):
        raise ValueError("Invalid pinned digest/source identity")


def positive(value, limit=MAX_FILE):
    if type(value) is not int or not 0 < value <= limit:
        raise ValueError("Invalid or oversized file/count")


def safe_name(name):
    if (not isinstance(name, str) or not name or len(name.encode("utf-8")) > 240
            or name.startswith("/") or "\\" in name
            or any(not part or part in (".", "..") or part[-1:] in (".", " ")
                   or any(ord(c) < 32 or c in ':<>"|?*' for c in part)
                   or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
                   for part in name.split("/"))):
        raise ValueError("Unsafe or ambiguous path")


def asset_name(version):
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.dev[0-9]+", version):
        raise ValueError("Explicit Core development version required")
    return f"rentgen-core-{version}-{PROFILE}"


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def absolute(path):
    path = Path(path)
    if ".." in path.parts:
        raise ValueError("Input/output path traversal refused")
    return Path(os.path.abspath(path))


class OwnedDirectory:
    """Retain every no-follow ancestor through the operation (POSIX build hosts).

    This protects pathname component replacement and detects mutation; it is not
    an isolation boundary against hostile processes with the builder's UID.
    """
    def __init__(self, path, *, create=False):
        self.path = absolute(path)
        self.fds = []
        self.links = []
        flags = getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        if os.name != "posix" or not flags or not hasattr(os, "O_NOFOLLOW"):
            raise ValueError("A POSIX no-follow build host is required")
        try:
            fd = os.open("/", os.O_RDONLY | flags)
            self.fds.append(fd)
            for index, name in enumerate(self.path.parts[1:]):
                parent = self.fds[-1]
                if create and index == len(self.path.parts[1:]) - 1:
                    os.mkdir(name, mode=0o700, dir_fd=parent)
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode):
                    raise ValueError("Directory symlink/non-directory refused")
                child = os.open(name, os.O_RDONLY | flags, dir_fd=parent)
                opened = os.fstat(child)
                self.fds.append(child)
                if (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
                    raise ValueError("Directory changed while opening")
                self.links.append((parent, name, opened.st_dev, opened.st_ino))
            self.fd = self.fds[-1]
            self.verify()
        except BaseException:
            self.close()
            raise

    def verify(self):
        for parent, name, device, inode in self.links:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (device, inode):
                raise ValueError("Retained directory identity changed")

    def close(self):
        for fd in reversed(self.fds):
            os.close(fd)
        self.fds.clear()

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        try:
            if kind is None:
                self.verify()
        finally:
            self.close()

    def read(self, name, expected, *, limit=MAX_FILE):
        safe_name(name)
        if "/" in name:
            raise ValueError("Input must be an immediate directory member")
        keys(expected, "sha256 size_bytes")
        digest(expected["sha256"])
        positive(expected["size_bytes"], limit)
        self.verify()
        info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != expected["size_bytes"]:
            raise ValueError("Pinned single-link regular input required")
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=self.fd)
        try:
            if _stamp(os.fstat(fd)) != _stamp(info):
                raise ValueError("Input changed while opening")
            parts, count = [], 0
            while True:
                block = os.read(fd, min(65536, limit + 1 - count))
                if not block:
                    break
                count += len(block)
                parts.append(block)
                if count > limit:
                    raise ValueError("Input exceeds size budget")
            data = b"".join(parts)
            if (_stamp(os.fstat(fd)) != _stamp(info)
                    or _stamp(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) != _stamp(info)):
                raise ValueError("Input changed while reading")
            if len(data) != expected["size_bytes"] or sha(data) != expected["sha256"]:
                raise ValueError("Input differs from pinned hash/size")
            self.verify()
            return data
        finally:
            os.close(fd)

    def write(self, name, data):
        safe_name(name)
        if "/" in name:
            raise ValueError("Output must be an immediate directory member")
        self.verify()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.fd)
        try:
            view = memoryview(data)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise OSError("Short output write")
                view = view[count:]
            os.fsync(fd)
            os.fchmod(fd, 0o644)
        finally:
            os.close(fd)
        self.verify()


def read_pinned(path, expected, *, limit=MAX_FILE):
    path = absolute(path)
    with OwnedDirectory(path.parent) as parent:
        return parent.read(path.name, expected, limit=limit)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def source_blobs(commit):
    digest(commit, 40)
    tree = git("rev-parse", "--verify", commit + "^{tree}").decode().strip()
    digest(tree, 40)
    entries = git("ls-tree", "-rlz", commit, "--", *PACKAGES, "pyproject.toml", "go",
                  *SOURCE_NOTICES, LOCK, PROVENANCE, CHECKER).split(b"\0")
    files, total = {}, 0
    folded = set()
    for entry in filter(None, entries):
        header, raw_name = entry.split(b"\t", 1)
        mode, kind, oid, size = header.split()
        name = raw_name.decode("utf-8")
        safe_name(name)
        if mode != b"100644" or kind != b"blob" or name.casefold() in folded:
            raise ValueError("Source inventory must contain unique regular blobs")
        if not 0 <= int(size) <= MAX_FILE:
            raise ValueError("Source blob exceeds file budget")
        total += int(size)
        if total > MAX_TOTAL or len(files) >= MAX_MEMBERS:
            raise ValueError("Source inventory exceeds budget")
        data = git("cat-file", "blob", oid.decode("ascii"))
        if len(data) != int(size):
            raise ValueError("Source blob size differs")
        folded.add(name.casefold())
        files[name] = data
    required = {"pyproject.toml", LOCK, PROVENANCE, CHECKER, *SOURCE_NOTICES[:-1],
                "rust/input-core/licenses/SHA256SUMS"}
    required.update(package + "/__init__.py" for package in PACKAGES)
    if not required <= files.keys():
        raise ValueError("Missing exact-source packages/notices/SDK lock")
    return tree, files


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def target_tag(tag):
    try:
        python, abi, platform = tag.split("-")
    except ValueError:
        return False
    compatible_tags = []
    for py in python.split("."):
        for ab in abi.split("."):
            for plat in platform.split("."):
                pure = py in ("py3", "py311") and ab == "none" and plat == "any"
                cp = py == "cp311" and ab in ("cp311", "none")
                stable = (ab == "abi3" and bool(re.fullmatch(r"cp3[0-9]+", py))
                          and 2 <= int(py[3:]) <= 11)
                linux = re.fullmatch(r"manylinux_2_([0-9]+)_x86_64", plat)
                compatible = (linux is not None and int(linux[1]) <= 34) or plat in (
                    "manylinux1_x86_64", "manylinux2010_x86_64", "manylinux2014_x86_64")
                compatible_tags.append(pure or ((cp or stable) and compatible))
    return bool(compatible_tags) and all(compatible_tags)


def expanded_tags(tag):
    python, abi, platform = tag.split("-")
    return {"-".join((py, ab, plat)) for py in python.split(".")
            for ab in abi.split(".") for plat in platform.split(".")}


def zip_directory_guard(data):
    # Reject huge central-directory inventories before ZipFile allocates them.
    position = data.rfind(b"PK\x05\x06", max(0, len(data) - 65557))
    if position < 0 or position + 22 > len(data):
        raise ValueError("Wheel ZIP directory bound invalid")
    disk, central_disk, count_disk, count, directory_size, directory_offset, comment = struct.unpack_from(
        "<HHHHIIH", data, position + 4)
    if (disk or central_disk or count_disk != count or not 1 <= count <= MAX_MEMBERS
            or directory_size > 8 * 1024**2 or directory_offset + directory_size != position
            or position + 22 + comment != len(data)):
        raise ValueError("Wheel ZIP directory bound invalid")
    cursor, actual_count = directory_offset, 0
    while cursor < position:
        if cursor + 46 > position or data[cursor:cursor + 4] != b"PK\x01\x02":
            raise ValueError("Wheel ZIP central record invalid")
        name_size, extra_size, comment_size, disk_start = struct.unpack_from("<HHHH", data, cursor + 28)
        if not 1 <= name_size <= 240 or extra_size > 4096 or comment_size > 4096 or disk_start:
            raise ValueError("Wheel ZIP central record field bound")
        cursor += 46 + name_size + extra_size + comment_size
        actual_count += 1
        if cursor > position or actual_count > MAX_MEMBERS:
            raise ValueError("Wheel ZIP actual directory bound")
    if cursor != position or actual_count != count:
        raise ValueError("Wheel ZIP actual directory count differs")


def wheel_files(filename, data, name, version):
    safe_name(filename)
    if "/" in filename or not filename.endswith(".whl"):
        raise ValueError("Binary wheel required")
    parts = filename[:-4].split("-")
    if (len(parts) not in (5, 6) or normalized(parts[0]) != name or parts[1] != version
            or not target_tag("-".join(parts[-3:]))):
        raise ValueError("Wheel filename identity/target ABI differs")
    zip_directory_guard(data)
    files, total, folded = {}, 0, set()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if not 1 <= len(members) <= MAX_MEMBERS:
            raise ValueError("Wheel member count exceeds budget")
        for item in members:
            member = item.orig_filename
            directory = item.is_dir()
            spelling = member[:-1] if directory else member
            safe_name(spelling)
            mode = stat.S_IFMT(item.external_attr >> 16)
            if (member != item.filename or item.flag_bits & 1
                    or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or mode not in ((0, stat.S_IFDIR) if directory else (0, stat.S_IFREG))
                    or spelling.casefold() in folded
                    or item.file_size < 0 or item.file_size > MAX_FILE):
                raise ValueError("Unsafe/duplicate wheel member")
            folded.add(spelling.casefold())
            if directory:
                if item.file_size:
                    raise ValueError("Wheel directory has file bytes")
                continue
            total += item.file_size
            if total > MAX_TOTAL:
                raise ValueError("Expanded wheel exceeds budget")
            raw = archive.read(item)
            if len(raw) != item.file_size:
                raise ValueError("Wheel member size differs")
            files[member] = raw
    if any("/".join(name.split("/")[:index]) in files
           for name in files for index in range(1, len(name.split("/")))):
        raise ValueError("Wheel file/directory collision")
    metadata_paths = [path for path in files if path.endswith(".dist-info/METADATA")]
    if len(metadata_paths) != 1:
        raise ValueError("One wheel distribution metadata required")
    metadata_path = metadata_paths[0]
    if len(files[metadata_path]) > MAX_JSON:
        raise ValueError("Wheel metadata exceeds budget")
    dist = metadata_path.rsplit("/", 1)[0]
    if normalized(dist[:-10].rsplit("-", 1)[0]) != name or dist[:-10].rsplit("-", 1)[-1] != version:
        raise ValueError("Wheel dist-info identity differs")
    metadata = BytesParser().parsebytes(files[metadata_path])
    identities = metadata.get_all("Name", [])
    if len(identities) != 1 or normalized(identities[0]) != name or metadata.get_all("Version") != [version]:
        raise ValueError("Wheel metadata identity differs")
    if any(".dist-info/" in path and not path.startswith(dist + "/") for path in files):
        raise ValueError("Ambiguous wheel distribution")
    wheel_raw = files.get(dist + "/WHEEL", b"")
    if not wheel_raw or len(wheel_raw) > 65536:
        raise ValueError("Wheel tag metadata missing/exceeds budget")
    wheel = BytesParser().parsebytes(wheel_raw)
    tags = wheel.get_all("Tag", [])
    if (not tags or not all(target_tag(tag) for tag in tags)
            or set().union(*(expanded_tags(tag) for tag in tags)) != expanded_tags("-".join(parts[-3:]))):
        raise ValueError("Wheel metadata target ABI differs")
    record_path = dist + "/RECORD"
    if record_path not in files or len(files[record_path]) > 2 * MAX_JSON:
        raise ValueError("Wheel RECORD required")
    seen = set()
    for row in csv.reader(io.StringIO(files[record_path].decode("utf-8"))):
        if len(row) != 3 or row[0] not in files or row[0] in seen:
            raise ValueError("Wheel RECORD inventory differs")
        seen.add(row[0])
        if row[0] == record_path:
            if row[1:] != ["", ""]:
                raise ValueError("Wheel RECORD self-entry differs")
        else:
            expected = base64.urlsafe_b64encode(hashlib.sha256(files[row[0]]).digest()).rstrip(b"=").decode()
            if row[1] != "sha256=" + expected or row[2] != str(len(files[row[0]])):
                raise ValueError("Wheel RECORD hash/size differs")
    if seen != set(files):
        raise ValueError("Wheel RECORD incomplete")
    return files, metadata


def validate_core(filename, data, version, source):
    files, metadata = wheel_files(filename, data, "rentgen-core", version)
    from packaging.specifiers import SpecifierSet
    requirement = tomllib.loads(source["pyproject.toml"].decode())["project"].get("requires-python")
    if (not isinstance(requirement, str) or metadata.get_all("Requires-Python") != [requirement]
            or not SpecifierSet(requirement).contains("3.11.15")):
        raise ValueError("Core wheel Requires-Python differs from selected source/target")
    expected = {name: raw for name, raw in source.items()
                if name.split("/", 1)[0] in PACKAGES
                and "__pycache__" not in name.split("/") and not name.endswith((".pyc", ".pyo"))}
    actual = {name: raw for name, raw in files.items() if name.split("/", 1)[0] in PACKAGES}
    if actual != expected:
        raise ValueError("Core wheel product sources differ from selected Git commit")
    dist = next(name.rsplit("/", 1)[0] for name in files if name.endswith(".dist-info/METADATA"))
    if (metadata.get_all("License-Expression") != ["MIT"] or metadata.get_all("License-File") != ["LICENSE"]
            or files.get(dist + "/licenses/LICENSE") != source["LICENSE"]):
        raise ValueError("Core wheel original license differs from selected source")
    if any(not name.startswith(dist + "/") and name not in expected for name in files):
        raise ValueError("Unexpected Core wheel payload")
    entries = files.get(dist + "/entry_points.txt", b"")
    for entry in (b"rentgen = rentgen_core.cli:main", b"rentgen-mcp = rentgen_core.stdio_mcp:main"):
        if entry not in entries.splitlines():
            raise ValueError("Core CLI/MCP entry points required")
    if metadata.get_all("Requires-Dist", []) not in (["mcp==1.30.0; extra == 'mcp'"],
                                                     ['mcp==1.30.0; extra == "mcp"']):
        raise ValueError("Unexpected Core runtime dependency contract")
    return {name: {"sha256": sha(raw), "size_bytes": len(raw)} for name, raw in sorted(expected.items())}


def validate_elf(data, *, static):
    if (len(data) < 64 or data[:7] != b"\x7fELF\x02\x01\x01"
            or data[16:18] not in ((b"\x02\x00",) if static else (b"\x02\x00", b"\x03\x00"))
            or data[18:20] != b"\x3e\x00"):
        raise ValueError("Expected Linux ELF64 x86_64 executable")
    offset = struct.unpack_from("<Q", data, 32)[0]
    size, count = struct.unpack_from("<HH", data, 54)
    if size != 56 or not 1 <= count <= 128 or offset < 64 or offset + size * count > len(data):
        raise ValueError("Invalid ELF program header inventory")
    load = False
    for index in range(count):
        kind, _, start, _, _, file_size = struct.unpack_from("<IIQQQQ", data, offset + index * size)
        if start + file_size > len(data):
            raise ValueError("ELF segment escapes input")
        load |= kind == 1
        if static and kind in (2, 3):
            raise ValueError("Owned Go scanner must be static ET_EXEC")
    if not load:
        raise ValueError("ELF load segment required")


def validate_inputs(value):
    keys(value, "schema profile version source_commit source_tree wheel scanner scanner_license scanner_provenance rust_helper")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["profile"] != PROFILE:
        raise ValueError("Unsupported owned Linux profile")
    asset_name(value["version"])
    digest(value["source_commit"], 40)
    digest(value["source_tree"], 40)
    for name in ("wheel", "scanner", "scanner_license", "scanner_provenance", "rust_helper"):
        keys(value[name], "asset sha256 size_bytes")
        safe_name(value[name]["asset"])
        if "/" in value[name]["asset"]:
            raise ValueError("Input asset must be a basename")
        digest(value[name]["sha256"])
        positive(value[name]["size_bytes"], MAX_JSON if name == "scanner_provenance" else MAX_FILE)
    expected = {"wheel": f"rentgen_core-{value['version']}-py3-none-any.whl",
                "scanner": "bsl-scan-owned-linux", "scanner_license": "GO-LICENSE",
                "scanner_provenance": "go-scanner-build-inputs.json", "rust_helper": "rentgen-input-core"}
    if any(value[name]["asset"] != asset for name, asset in expected.items()):
        raise ValueError("Unexpected input asset identity")
    if sum(value[name]["size_bytes"] for name in expected) > MAX_TOTAL - MAX_JSON:
        raise ValueError("Pinned input total exceeds budget")


def validate_scanner_provenance(raw, inputs, source):
    value = parse_json(raw)
    keys(value, "schema protocol source_commit source_tree source_files_sha256 go_version go_executable_sha256 cgo_enabled build_arguments scanner license scope")
    expected = {"schema": "rentgen-owned-linux-scanner-build-observation/1",
                "protocol": "rentgen-owned-scanner-linux-v1",
                "source_commit": inputs["source_commit"], "source_tree": inputs["source_tree"],
                "cgo_enabled": False,
                "build_arguments": ["build", "-trimpath", "-buildmode=exe", "./cmd/bsl-scan"],
                "scope": "CI build observation; installed acceptance is a separate receipt"}
    if any(type(value[key]) is not type(item) or value[key] != item for key, item in expected.items()):
        raise ValueError("Scanner build provenance differs")
    go_version = re.search(rb"(?m)^go ([0-9]+\.[0-9]+\.[0-9]+)\s*$", source["go/go.mod"])
    if go_version is None or value["go_version"] != "go version go" + go_version[1].decode() + " linux/amd64":
        raise ValueError("Scanner Go version differs from selected source")
    digest(value["go_executable_sha256"])
    expected_sources = {name: sha(data) for name, data in source.items()
                        if name == "go/go.mod" or name.startswith("go/") and name.endswith(".go")}
    if value["source_files_sha256"] != expected_sources:
        raise ValueError("Scanner source inventory differs from selected commit")
    keys(value["scanner"], "sha256 size_bytes")
    keys(value["license"], "path sha256 size_bytes")
    if value["scanner"] != {key: inputs["scanner"][key] for key in ("sha256", "size_bytes")}:
        raise ValueError("Scanner binary provenance differs")
    if value["license"] != {"path": "licenses/GO-LICENSE", **{
            key: inputs["scanner_license"][key] for key in ("sha256", "size_bytes")}}:
        raise ValueError("Scanner license provenance differs")
    return value


def validate_rust_notices(source):
    prefix = "rust/input-core/"
    inventory = source[prefix + "licenses/SHA256SUMS"].decode("utf-8")
    actual = {}
    for line in inventory.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ValueError("Invalid Rust license inventory")
        name = prefix + match[2]
        safe_name(name)
        if name in actual or name not in source or sha(source[name]) != match[1]:
            raise ValueError("Rust license inventory hash/entry differs")
        actual[name] = match[1]
    expected = {name for name in source if name.startswith(prefix + "licenses/")}
    expected.remove(prefix + "licenses/SHA256SUMS")
    expected.add(prefix + "THIRD_PARTY_NOTICES.md")
    if set(actual) != expected:
        raise ValueError("Rust license inventory incomplete")


def sdk_payload(wheelhouse, source, *, byte_budget=MAX_TOTAL):
    provenance = parse_json(source[PROVENANCE])
    if provenance.get("schema_version") != 1 or provenance.get("root_requirement") != "mcp==1.30.0":
        raise ValueError("Official SDK closure profile differs")
    target = provenance.get("target", {})
    if any(target.get(key) != value for key, value in {
        "python_version": "3.11", "implementation": "cpython", "machine": "x86_64", "glibc_minimum": "2.34",
    }.items()):
        raise ValueError("SDK target differs")
    wheels = provenance.get("wheels")
    if not isinstance(wheels, list) or not 1 <= len(wheels) <= 64:
        raise ValueError("Bounded SDK wheel inventory required")
    planned = 0
    for item in wheels:
        positive(item["size_bytes"])
        planned += item["size_bytes"]
        if not isinstance(item["license_files"], list) or not 1 <= len(item["license_files"]) <= 128:
            raise ValueError("SDK original license inventory required")
        for license_file in item["license_files"]:
            positive(license_file["size_bytes"], MAX_JSON)
            planned += license_file["size_bytes"]
    if planned > byte_budget:
        raise ValueError("Planned SDK payload exceeds remaining byte budget")
    files, names, total = {}, set(), 0
    with OwnedDirectory(wheelhouse) as directory:
        expected = {item["filename"] for item in wheels}
        if len(expected) != len(wheels) or set(os.listdir(directory.fd)) != expected:
            raise ValueError("Wheelhouse must exactly match locked closure")
        for item in wheels:
            name = item["name"]
            if name != normalized(name) or name in names or name == "rentgen-core":
                raise ValueError("Ambiguous SDK distribution/version")
            names.add(name)
            raw = directory.read(item["filename"], {key: item[key] for key in ("sha256", "size_bytes")})
            total += len(raw)
            if total > MAX_TOTAL:
                raise ValueError("SDK wheelhouse exceeds budget")
            contents, metadata = wheel_files(item["filename"], raw, name, item["version"])
            metadata_raw = next(data for path, data in contents.items() if path.endswith(".dist-info/METADATA"))
            if (sha(metadata_raw) != item["metadata_sha256"]
                    or metadata.get_all("Requires-Dist", []) != item["requires_dist"]):
                raise ValueError("SDK metadata differs from provenance")
            licenses = item["license_files"]
            if not isinstance(licenses, list) or not licenses:
                raise ValueError("SDK original license inventory required")
            for license_file in licenses:
                path = license_file["path"]
                if (path not in contents or sha(contents[path]) != license_file["sha256"]
                        or len(contents[path]) != license_file["size_bytes"]):
                    raise ValueError("SDK original license differs")
                files["licenses/python/" + name + "/" + path] = contents[path]
            files["wheelhouse/" + item["filename"]] = raw
        directory.verify()
    # The dedicated reviewed lock checker validates target-marker dependency
    # closure and requirement hashes. Give it only our already owned copies.
    # Run only the selected repository's bounded checker source, not code from
    # the wheelhouse or a second mutable path read. The repository is the trust
    # boundary for the exporter itself, not an arbitrary downloaded installer.
    checker = types.ModuleType("owned_linux_mcp_lock")
    checker.__file__ = str(ROOT / CHECKER)
    sys.modules[checker.__name__] = checker
    try:
        exec(compile(source[CHECKER], checker.__file__, "exec"), checker.__dict__)
    finally:
        sys.modules.pop(checker.__name__, None)
    with tempfile.TemporaryDirectory(prefix="rentgen-owned-lock-") as temporary:
        temporary = Path(temporary)
        (temporary / "wheelhouse").mkdir(mode=0o700)
        for name, raw in files.items():
            if name.startswith("wheelhouse/"):
                (temporary / name).write_bytes(raw)
        (temporary / "requirements.txt").write_bytes(source[LOCK])
        (temporary / "provenance.json").write_bytes(source[PROVENANCE])
        checker.verify_wheelhouse(temporary / "wheelhouse", provenance_path=temporary / "provenance.json",
                                 lock_path=temporary / "requirements.txt")
    files["requirements-mcp-py311-linux.txt"] = source[LOCK]
    files["python-dependency-provenance.json"] = source[PROVENANCE]
    return files


def installation(inputs):
    version = inputs["version"]
    return f"""# Owned Linux CLI / official MCP SDK candidate

Profile: {PROFILE}. Core {version}; official Python MCP SDK 1.30.0.
Candidate only: accepted=false, published=false, full_product_ready=false.
Requires GNU/Linux x86_64, CPython 3.11.15 with venv/pip, glibc >= 2.34,
kernel >= 5.9, libgcc_s.so.1, memfd seals and /proc/self/fd. The interpreter
and operating-system libraries are not bundled. This is a separate profile;
it does not alter the accepted dev19 experimental supplement.

Check the externally trusted archive SHA256 before extraction. The manifest
records every final archive member; verify those hashes before installation.
From the extracted kit directory, create a new environment and install offline:

    python3.11 -I -m venv .venv
    .venv/bin/python -I -c 'import sys; assert sys.version_info[:3] == (3, 11, 15)'
    PIP_CONFIG_FILE=/dev/null .venv/bin/python -I -m pip --isolated --disable-pip-version-check --no-cache-dir install --no-index --require-hashes --only-binary=:all: --find-links=./wheelhouse -r requirements-mcp-py311-linux.txt
    PIP_CONFIG_FILE=/dev/null .venv/bin/python -I -m pip --isolated --disable-pip-version-check --no-cache-dir install --no-index --require-hashes --no-deps -r requirements-core.txt
    PIP_CONFIG_FILE=/dev/null .venv/bin/python -I -m pip --isolated --disable-pip-version-check check
    .venv/bin/python -I -m rentgen_core --help
    .venv/bin/python -I -m rentgen_core.stdio_mcp --help

These POSIX-shell prefixes disable pip configuration files. Python `-I` and
pip `--isolated` separate installation from ambient Python paths and pip
environment/user settings. `--no-index` alone does not disable configured
`find-links` URLs. The commands select local hash-pinned files; they do not
establish an OS-level network airgap.

Use absolute kit paths for the explicitly trusted native executables:
scanner bin/bsl-scan-owned-linux with --scanner-sha256 {inputs['scanner']['sha256']};
Rust input helper bin/rentgen-input-core with --input-core-sha256 {inputs['rust_helper']['sha256']}.
Do not derive a trusted hash from an untrusted replacement. The executables
are protocol helpers, not interactive tools. No installer executes while
preparing this candidate. Do not install as root; use private new test state.

Exact-source setup, CLI/MCP and scope instructions:
https://github.com/DmitrL-dev/1cai-public/blob/{inputs['source_commit']}/docs/product/PORTABLE-CORE.md
https://github.com/DmitrL-dev/1cai-public/blob/{inputs['source_commit']}/docs/product/CORE-MCP.md
https://github.com/DmitrL-dev/1cai-public/blob/{inputs['source_commit']}/rentgen_core/LINUX-CAPTURE-BACKEND.md

Intended qualification: private default-base owned-source capture, source and
graph reads, historical reads and durable operation replay through fresh
installed CLI / official-SDK MCP processes. Final extracted bytes still need
actual Linux --no-index --require-hashes installation, pip check and these
scenarios. Building this archive is not that evidence. It is not GitHub CI.
Capture is bounded: source total 64 MiB, individual file 16 MiB and 4096 source
entries by default. These are not the full product's larger budget promises.
No Companion, native 1C/EDT, metadata/drafts/diff, live apply, macOS, model
quality, complete Linux suite or full product readiness is qualified here.
The Rust helper and its existing license/provenance materials remain separate
from the owned Go scanner. Review licenses/python originals, GO-LICENSE,
LICENSE and rust/input-core notices; provenance is attribution/input evidence,
not a reproducible-build or dynamic-system-library closure claim.
""".encode()


def file_mode(name):
    return 0o755 if name in ("bin/bsl-scan-owned-linux", "bin/rentgen-input-core") else 0o644


def tar_bytes(prefix, files):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, data in sorted(files.items()):
            safe_name(name)
            item = tarfile.TarInfo(prefix + "/" + name)
            item.size, item.mode = len(data), file_mode(name)
            archive.addfile(item, io.BytesIO(data))
    return raw.getvalue()


def archive_bytes(prefix, files):
    output = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0, compresslevel=9) as compressed:
        compressed.write(tar_bytes(prefix, files))
    return output.getvalue()


def payload(inputs, owned, wheelhouse):
    validate_inputs(inputs)
    keys(owned, "wheel scanner scanner_license scanner_provenance rust_helper")
    tree, source = source_blobs(inputs["source_commit"])
    if tree != inputs["source_tree"]:
        raise ValueError("Selected source tree differs")
    project = tomllib.loads(source["pyproject.toml"].decode())
    if project["project"]["version"] != inputs["version"]:
        raise ValueError("Selected source Core version differs")
    for name, raw in owned.items():
        if len(raw) != inputs[name]["size_bytes"] or sha(raw) != inputs[name]["sha256"]:
            raise ValueError("Owned input differs from pinned hash/size")
    source_inventory = validate_core(inputs["wheel"]["asset"], owned["wheel"], inputs["version"], source)
    validate_elf(owned["scanner"], static=True)
    validate_elf(owned["rust_helper"], static=False)
    validate_scanner_provenance(owned["scanner_provenance"], inputs, source)
    validate_rust_notices(source)
    if (sha(owned["scanner_license"]) != GO_LICENSE_SHA256 or len(owned["scanner_license"]) != 1453):
        raise ValueError("Original Go license text required")
    files = {name: raw for name, raw in source.items()
             if name == "LICENSE" or name.startswith("rust/input-core/") or name == "go/go.mod"}
    files.update({"wheelhouse/" + inputs["wheel"]["asset"]: owned["wheel"],
                  "bin/bsl-scan-owned-linux": owned["scanner"], "bin/rentgen-input-core": owned["rust_helper"],
                  "GO-LICENSE": owned["scanner_license"], "go-scanner-build-inputs.json": owned["scanner_provenance"],
                  "build-inputs.json": json_bytes(inputs), "core-source-inventory.json": json_bytes(source_inventory),
                  "INSTALL.md": installation(inputs),
                  "requirements-core.txt": ("./wheelhouse/" + inputs["wheel"]["asset"] + " --hash=sha256:"
                                             + inputs["wheel"]["sha256"] + "\n").encode()})
    remaining = MAX_TOTAL - MAX_JSON - sum(map(len, files.values())) - len(source[LOCK]) - len(source[PROVENANCE])
    if remaining <= 0:
        raise ValueError("No remaining SDK payload budget")
    files.update(sdk_payload(wheelhouse, source, byte_budget=remaining))
    if len(files) > 512 or sum(map(len, files.values())) > MAX_TOTAL - MAX_JSON:
        raise ValueError("Final kit payload exceeds budget")
    if len({name.casefold() for name in files}) != len(files):
        raise ValueError("Ambiguous final kit inventory")
    return files


def candidate(inputs, owned, wheelhouse):
    files = payload(inputs, owned, wheelhouse)
    prefix = asset_name(inputs["version"])
    raw = archive_bytes(prefix, files)
    positive(len(raw), MAX_TOTAL)
    manifest = {"schema": 1, "kind": PROFILE, "candidate": True, "accepted": False,
                "published": False, "full_product_ready": False,
                "linux_installed_cli_mcp_qualified": False, "platform": PLATFORM,
                "inputs": inputs, "asset": prefix + ".tar.gz", "sha256": sha(raw), "size_bytes": len(raw),
                "files": {name: {"sha256": sha(data), "size_bytes": len(data), "mode": file_mode(name)}
                          for name, data in sorted(files.items())}}
    return raw, manifest


def verified_payload(data, manifest):
    """Pure bounded inventory verification, never extraction or acceptance.

    The caller must pin BOTH manifest and archive hashes independently before
    trusting any selected source/input identities. A manifest from the same
    untrusted archive is not an external trust anchor.
    """
    keys(manifest, "schema kind candidate accepted published full_product_ready linux_installed_cli_mcp_qualified platform inputs asset sha256 size_bytes files")
    if (type(manifest["schema"]) is not int or manifest["schema"] != 1
            or manifest["kind"] != PROFILE or manifest["candidate"] is not True
            or any(manifest[key] is not False for key in (
                "accepted", "published", "full_product_ready", "linux_installed_cli_mcp_qualified"))
            or manifest["platform"] != PLATFORM):
        raise ValueError("Unsupported candidate scope/schema")
    validate_inputs(manifest["inputs"])
    prefix = asset_name(manifest["inputs"]["version"])
    if manifest["asset"] != prefix + ".tar.gz":
        raise ValueError("Candidate archive identity differs")
    digest(manifest["sha256"])
    positive(manifest["size_bytes"], MAX_TOTAL)
    if len(data) != manifest["size_bytes"] or sha(data) != manifest["sha256"]:
        raise ValueError("Candidate archive hash/size differs")
    inventory = manifest["files"]
    if not isinstance(inventory, dict) or not 1 <= len(inventory) <= 512:
        raise ValueError("Candidate member inventory bound")
    folded, total = set(), 0
    for name, expected in inventory.items():
        safe_name(name)
        keys(expected, "sha256 size_bytes mode")
        digest(expected["sha256"])
        if type(expected["size_bytes"]) is not int or not 0 <= expected["size_bytes"] <= MAX_FILE:
            raise ValueError("Candidate file size bound")
        if type(expected["mode"]) is not int or expected["mode"] != file_mode(name) or name.casefold() in folded:
            raise ValueError("Candidate mode/name differs")
        folded.add(name.casefold())
        total += expected["size_bytes"]
    if total > MAX_TOTAL - MAX_JSON:
        raise ValueError("Candidate payload total bound")
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
        raw = compressed.read(MAX_TOTAL + 1)
    if len(raw) > MAX_TOTAL:
        raise ValueError("Expanded candidate archive exceeds budget")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for item in archive:
            if len(files) >= 512 or not item.name.startswith(prefix + "/"):
                raise ValueError("Unexpected candidate archive member")
            name = item.name[len(prefix) + 1:]
            safe_name(name)
            if (name in files or name not in inventory or item.type != tarfile.REGTYPE
                    or item.linkname or item.mode != file_mode(name) or item.uid or item.gid
                    or item.uname or item.gname or item.mtime != 0
                    or item.size != inventory[name]["size_bytes"]):
                raise ValueError("Candidate archive member/header differs")
            content = archive.extractfile(item).read(MAX_FILE + 1)
            if len(content) != item.size or sha(content) != inventory[name]["sha256"]:
                raise ValueError("Candidate archive member hash differs")
            files[name] = content
    if set(files) != set(inventory) or raw != tar_bytes(prefix, files):
        raise ValueError("Candidate archive inventory/canonical layout differs")
    inputs = manifest["inputs"]
    if files.get("build-inputs.json") != json_bytes(inputs):
        raise ValueError("Candidate embedded input identity differs")
    required = {"INSTALL.md", "requirements-core.txt", "requirements-mcp-py311-linux.txt",
                "python-dependency-provenance.json", "core-source-inventory.json", "GO-LICENSE",
                "go-scanner-build-inputs.json", "LICENSE", "bin/bsl-scan-owned-linux", "bin/rentgen-input-core",
                "wheelhouse/" + inputs["wheel"]["asset"]}
    if not required <= files.keys():
        raise ValueError("Candidate required payload missing")
    for key, path in (("wheel", "wheelhouse/" + inputs["wheel"]["asset"]),
                      ("scanner", "bin/bsl-scan-owned-linux"), ("scanner_license", "GO-LICENSE"),
                      ("scanner_provenance", "go-scanner-build-inputs.json"), ("rust_helper", "bin/rentgen-input-core")):
        if len(files[path]) != inputs[key]["size_bytes"] or sha(files[path]) != inputs[key]["sha256"]:
            raise ValueError("Candidate embedded component differs")
    return files


def build(inputs_path, inputs_sha256, wheel, scanner, scanner_license, scanner_provenance,
          rust_helper, wheelhouse, output):
    digest(inputs_sha256)
    # Size is checked before the descriptor read; JSON hash is externally pinned.
    inputs_path = absolute(inputs_path)
    with OwnedDirectory(inputs_path.parent) as directory:
        info = os.stat(inputs_path.name, dir_fd=directory.fd, follow_symlinks=False)
        raw = directory.read(inputs_path.name, {"sha256": inputs_sha256, "size_bytes": info.st_size}, limit=MAX_JSON)
    inputs = parse_json(raw)
    validate_inputs(inputs)
    paths = dict(wheel=wheel, scanner=scanner, scanner_license=scanner_license,
                 scanner_provenance=scanner_provenance, rust_helper=rust_helper)
    owned = {name: read_pinned(path, {key: inputs[name][key] for key in ("sha256", "size_bytes")},
                              limit=MAX_JSON if name == "scanner_provenance" else MAX_FILE)
             for name, path in paths.items()}
    data, manifest = candidate(inputs, owned, wheelhouse)
    manifest_bytes = json_bytes(manifest)
    positive(len(manifest_bytes), MAX_JSON)
    checksum = (sha(data) + "  " + manifest["asset"] + "\n" + sha(manifest_bytes) + "  " + MANIFEST + "\n").encode()
    with OwnedDirectory(output, create=True) as directory:
        output_files = ((manifest["asset"], data), (MANIFEST, manifest_bytes), (CHECKSUMS, checksum))
        for name, content in output_files:
            directory.write(name, content)
        if set(os.listdir(directory.fd)) != {manifest["asset"], MANIFEST, CHECKSUMS}:
            raise ValueError("Unexpected output inventory")
        for name, content in output_files:
            directory.read(name, {"sha256": sha(content), "size_bytes": len(content)}, limit=MAX_TOTAL)
        os.fsync(directory.fd)
    return {"candidate": True, "accepted": False, "published": False, "profile": PROFILE,
            "source_commit": inputs["source_commit"], "source_tree": inputs["source_tree"],
            "asset": manifest["asset"], "sha256": manifest["sha256"], "size_bytes": manifest["size_bytes"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build",))
    parser.add_argument("--inputs-sha256", required=True)
    for name in ("inputs", "wheel", "scanner", "scanner-license", "scanner-provenance", "rust-helper", "wheelhouse", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = build(args.inputs, args.inputs_sha256, args.wheel, args.scanner, args.scanner_license,
                   args.scanner_provenance, args.rust_helper, args.wheelhouse, args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
