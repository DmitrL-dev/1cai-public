"""Build a candidate Linux supplement; verify only against committed acceptance.

Independent of prepare_core.py's closed four-file Windows release contract.
No builds, downloads, binary execution, publication or tag changes are performed.
"""
import argparse
from email.parser import BytesParser
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[2]
MAX_FILE = 64 * 1024**2
MAX_TOTAL = 128 * 1024**2
MAX_JSON = 1024**2
MAX_MEMBERS = 256
MANIFEST = "experimental-linux-manifest.json"
CHECKSUMS = "experimental-linux-SHA256SUMS"
PLATFORM = {
    "status": "experimental",
    "os": "GNU/Linux",
    "architecture": "x86_64",
    "glibc_minimum": "2.34",
    "kernel_minimum": "5.9",
    "requires": ["libgcc_s.so.1", "memfd seals", "/proc/self/fd"],
    "full_linux_suite_green": False,
    "known_full_linux_failures": 90,
    "known_full_linux_errors": 2,
}
SOURCE_PATHS = (
    "LICENSE", "rust/input-core/Cargo.lock", "rust/input-core/PROTOCOL.md",
    "rust/input-core/THIRD_PARTY_NOTICES.md",
    "rust/input-core/DEPENDENCY_PROVENANCE.json", "rust/input-core/licenses",
)


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
        raise ValueError("Unexpected manifest/input schema")


def hex_value(value, length=64):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{%d}" % length, value):
        raise ValueError("Invalid digest or source identity")


def positive(value, maximum=MAX_FILE):
    if type(value) is not int or not 0 < value <= maximum:
        raise ValueError("Invalid or oversized file/count")


def version_name(version):
    if not isinstance(version, str) or len(version) > 64 or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.dev[0-9]+", version):
        raise ValueError("Explicit development core version required")
    return "rentgen-core-" + version + "-experimental-linux-x86_64"


def safe_name(name):
    if (not isinstance(name, str) or not name or len(name) > 240
            or not re.fullmatch(r"[A-Za-z0-9_./+-]+", name)
            or any(p in ("", ".", "..") for p in name.split("/"))
            or PurePosixPath(name).is_absolute()):
        raise ValueError("Unsafe archive path")


def no_links(path):
    # Local staging is trusted against concurrent mutation, never symlink traversal.
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("Symlink paths are not accepted")
    return path


def read_regular(path, limit=MAX_FILE):
    path = no_links(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Single-link regular file required")
    positive(info.st_size, limit)
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) != info.st_size or len(data) > limit:
        raise ValueError("Input changed or exceeds size limit")
    return data


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def validate_inputs(value):
    keys(value, "schema version rust_component_version source_commit source_tree windows_kit wheel linux_ci binary")
    if type(value["schema"]) is not int or value["schema"] != 1:
        raise ValueError("Unsupported input schema")
    version_name(value["version"])
    if value["rust_component_version"] != "0.1.0":
        raise ValueError("Unexpected Rust component version")
    hex_value(value["source_commit"], 40)
    hex_value(value["source_tree"], 40)
    for name in ("wheel", "binary", "windows_kit"):
        item = value[name]
        keys(item, "asset sha256 size_bytes" + (" ci_run artifact_id artifact_sha256" if name == "windows_kit" else ""))
        hex_value(item["sha256"])
        positive(item["size_bytes"], MAX_TOTAL if name == "windows_kit" else MAX_FILE)
    version = value["version"]
    if (value["wheel"]["asset"] != f"rentgen_core-{version}-py3-none-any.whl"
            or value["binary"]["asset"] != "rentgen-input-core"
            or value["windows_kit"]["asset"] != f"rentgen-core-{version}-windows-py311.zip"):
        raise ValueError("Unexpected input asset identity")
    linux = value["linux_ci"]
    keys(linux, "ci_run artifact_id artifact_sha256 artifact_size_bytes python")
    positive(linux["artifact_size_bytes"], MAX_TOTAL)
    if linux["python"] not in ("3.11", "3.12"):
        raise ValueError("Unexpected Linux CI Python version")
    for item in (value["windows_kit"], linux):
        for key in ("ci_run", "artifact_id"):
            positive(item[key], 2**63 - 1)
        hex_value(item["artifact_sha256"])


def source_files(inputs):
    commit = inputs["source_commit"]
    if git("rev-parse", commit + "^{tree}").decode().strip() != inputs["source_tree"]:
        raise ValueError("Source tree differs from pinned commit")
    if subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, capture_output=True).returncode:
        raise ValueError("Source commit must be in checkout history")
    paths = (*SOURCE_PATHS, "pyproject.toml", "rust/input-core/Cargo.toml")
    entries = git("ls-tree", "-rlz", commit, "--", *paths).split(b"\0")
    result = {}
    total = 0
    for entry in filter(None, entries):
        header, path = entry.split(b"\t", 1)
        mode, kind, oid, size = header.split()
        path = path.decode("utf-8")
        safe_name(path)
        if mode != b"100644" or kind != b"blob" or path in result:
            raise ValueError("Source license inputs must be unique regular files")
        positive(int(size), MAX_FILE)
        total += int(size)
        if total > 16 * 1024**2 or len(result) >= MAX_MEMBERS - 4:
            raise ValueError("Source notice inventory exceeds limits")
        data = git("cat-file", "blob", oid.decode("ascii"))
        if len(data) != int(size):
            raise ValueError("Source blob size differs")
        result[path] = data
    required = (*SOURCE_PATHS[:-1], "rust/input-core/licenses/SHA256SUMS", "pyproject.toml", "rust/input-core/Cargo.toml")
    if not set(required) <= result.keys():
        raise ValueError("Missing required source license/provenance files")
    project = tomllib.loads(result.pop("pyproject.toml").decode())
    cargo = tomllib.loads(result.pop("rust/input-core/Cargo.toml").decode())
    if project["project"]["version"] != inputs["version"] or cargo["package"]["version"] != inputs["rust_component_version"]:
        raise ValueError("Source component versions differ")
    return result


def installation(inputs):
    version = inputs["version"]
    return f"""# Rentgen Core {version}: experimental GNU/Linux x86_64 supplement

Prerelease only. Requires CPython 3.11 or 3.12 with venv/pip, glibc >= 2.34,
libgcc_s.so.1, Linux >= 5.9, usable memfd seals and /proc/self/fd. Sandboxed
hosts may deny these facilities. CI input provenance selects Python {inputs['linux_ci']['python']}.
The binary is rentgen-input-core {inputs['rust_component_version']}; this is independent of the Core version.

This archive preserves the canonical accepted Windows-kit pure Python wheel
and the exact separately qualified main Linux CI Rust binary. It includes MIT,
Rust dependency notices, original license files and input provenance. Review
rust/input-core/THIRD_PARTY_NOTICES.md for remaining attribution limitations.
No Python dependencies, Python interpreter, 1C platform or models are bundled.

Verify the archive with experimental-linux-SHA256SUMS against a trusted release
record before extraction. From the directory containing the verified archive:

    tar -xzf rentgen-core-{version}-experimental-linux-x86_64.tar.gz
    cd rentgen-core-{version}-experimental-linux-x86_64
    python3.11 -m venv .venv
    .venv/bin/python -m pip install --no-index --no-deps ./rentgen_core-{version}-py3-none-any.whl
    .venv/bin/python -I -m rentgen_core --help

Use the extracted bin/rentgen-input-core as the explicit --input-core argument
of export-analyze, with --input-core-sha256 {inputs['binary']['sha256']}.
The SHA256 must come from the trusted manifest, not an untrusted replacement.
The sidecar implements a framed protocol; do not treat it as a standalone CLI.
See rust/input-core/PROTOCOL.md. Use new, synthetic projects for evaluation.
Exact-source command guides (identity-init, registry-init, project-register and
export-analyze with explicit registry, profile, project and archive hash):
https://github.com/DmitrL-dev/1cai-public/blob/{inputs['source_commit']}/docs/product/PORTABLE-CORE.md
https://github.com/DmitrL-dev/1cai-public/blob/{inputs['source_commit']}/docs/product/RUST-INPUT-CORE.md

Accepted scope must be read together with the release's installed-smoke receipt:
basic local identity/registry/project creation and read-only ZIP export analysis.
Native capture is unavailable on Linux. Installation does not migrate state.
MCP dependencies and MCP installation are not qualified by this supplement.
The complete Linux suite is NOT green: 90 known failures and 2 errors remain.
This does not qualify native 1C, Editor, Observer, live apply, macOS, model quality,
full product readiness or acceleration. No speedup is claimed.

build-inputs.json binds source commit/tree, exact input hashes and CI artifact
identities. CI artifact hashes are provenance; local wheel and binary bytes are
independently checked. Candidate packaging itself is not release acceptance.
""".encode()


def payload(inputs, wheel, binary):
    validate_inputs(inputs)
    for key, data in (("wheel", wheel), ("binary", binary)):
        if len(data) != inputs[key]["size_bytes"] or sha(data) != inputs[key]["sha256"]:
            raise ValueError("Input bytes differ from pinned " + key)
    with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
        names = [item for item in archive.infolist() if item.filename.endswith(".dist-info/METADATA")]
        if len(names) != 1 or names[0].file_size > MAX_JSON:
            raise ValueError("Unexpected wheel metadata")
        metadata = BytesParser().parsebytes(archive.read(names[0]))
        if metadata.get_all("Name") != ["rentgen-core"] or metadata.get_all("Version") != [inputs["version"]]:
            raise ValueError("Wheel component identity differs")
    if (len(binary) < 64 or binary[:7] != b"\x7fELF\x02\x01\x01"
            or binary[16:18] not in (b"\x02\x00", b"\x03\x00")
            or binary[18:20] != b"\x3e\x00"):
        raise ValueError("Expected little-endian ELF64 x86_64 executable")
    result = source_files(inputs)
    result.update({inputs["wheel"]["asset"]: wheel, "bin/rentgen-input-core": binary,
                   "INSTALL.md": installation(inputs), "build-inputs.json": json_bytes(inputs)})
    if len(result) > MAX_MEMBERS or sum(map(len, result.values())) > MAX_TOTAL - 1024**2:
        raise ValueError("Archive payload exceeds limits")
    return result


def file_mode(name):
    return 0o755 if name == "bin/rentgen-input-core" else 0o644


def tar_bytes(prefix, files):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(files.items()):
            safe_name(name)
            item = tarfile.TarInfo(prefix + "/" + name)
            item.size = len(data)
            item.mode = file_mode(name)
            archive.addfile(item, io.BytesIO(data))
    return raw.getvalue()


def archive_bytes(prefix, files):
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=compressed, mode="wb", mtime=0, compresslevel=9) as stream:
        stream.write(tar_bytes(prefix, files))
    return compressed.getvalue()


def candidate(inputs, wheel, binary):
    files = payload(inputs, wheel, binary)
    prefix = version_name(inputs["version"])
    data = archive_bytes(prefix, files)
    manifest = {"schema": 1, "kind": "experimental-linux-supplement", "prerelease": True,
                "full_product_ready": False, "platform": PLATFORM, "inputs": inputs,
                "asset": prefix + ".tar.gz", "sha256": sha(data), "size_bytes": len(data),
                "files": {name: {"sha256": sha(content), "size_bytes": len(content), "mode": file_mode(name)}
                          for name, content in sorted(files.items())}}
    return data, manifest


def fresh_directory(path):
    path = no_links(path)
    path.mkdir(parents=True, exist_ok=False)
    return path


def build(inputs_path, wheel, binary, output):
    inputs = parse_json(read_regular(inputs_path, MAX_JSON))
    data, manifest = candidate(inputs, read_regular(wheel), read_regular(binary))
    output = fresh_directory(output)
    for name, raw in ((manifest["asset"], data), (MANIFEST, json_bytes(manifest)),
                      (CHECKSUMS, (manifest["sha256"] + "  " + manifest["asset"] + "\n").encode())):
        with (output / name).open("xb") as stream:
            stream.write(raw)
        (output / name).chmod(0o644)
    return {"candidate": True, "accepted": False, "asset": manifest["asset"], "sha256": manifest["sha256"]}


def committed(path):
    relative = path.relative_to(ROOT).as_posix()
    raw = read_regular(path, MAX_JSON)
    if git("status", "--porcelain=v1", "--", relative) or git("show", "HEAD:" + relative) != raw:
        raise ValueError("Acceptance record must be committed and unchanged")
    return raw


def accepted_manifest(version):
    version_name(version)
    committed(ROOT / "scripts/release/prepare_experimental_linux.py")
    folder = ROOT / "releases/core" / version
    raw = committed(folder / MANIFEST)
    value = parse_json(raw)
    keys(value, "schema kind prerelease full_product_ready platform inputs asset sha256 size_bytes files")
    if (type(value["schema"]) is not int or value["schema"] != 1
            or value["kind"] != "experimental-linux-supplement" or value["prerelease"] is not True
            or value["full_product_ready"] is not False or json_bytes(value["platform"]) != json_bytes(PLATFORM)):
        raise ValueError("Invalid experimental platform/acceptance scope")
    validate_inputs(value["inputs"])
    inputs = value["inputs"]
    if inputs["version"] != version or value["asset"] != version_name(version) + ".tar.gz":
        raise ValueError("Accepted version/asset differs")
    hex_value(value["sha256"])
    positive(value["size_bytes"], MAX_TOTAL)
    if not isinstance(value["files"], dict) or not 1 <= len(value["files"]) <= MAX_MEMBERS:
        raise ValueError("Invalid accepted file inventory")
    for name, item in value["files"].items():
        safe_name(name)
        keys(item, "sha256 size_bytes mode")
        hex_value(item["sha256"])
        positive(item["size_bytes"])
        if type(item["mode"]) is not int or item["mode"] != file_mode(name):
            raise ValueError("Invalid accepted file mode")
    windows = parse_json(committed(folder / "manifest.json"))
    expected = {"version": version, "source_commit": inputs["source_commit"],
                "wheel_sha256": inputs["wheel"]["sha256"], "prerelease": True,
                "full_product_ready": False, "tag": "core-v" + version.replace(".dev", "-dev")}
    expected.update({key: inputs["windows_kit"][key] for key in ("asset", "sha256", "size_bytes", "ci_run")})
    if any(type(windows.get(key)) is not type(item) or windows.get(key) != item for key, item in expected.items()):
        raise ValueError("Canonical accepted Windows wheel/kit provenance differs")
    return value, raw


def verified_payload(data, manifest):
    if len(data) != manifest["size_bytes"] or sha(data) != manifest["sha256"]:
        raise ValueError("Archive differs from accepted bytes")
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        raw = stream.read(MAX_TOTAL + 1)
    if len(raw) > MAX_TOTAL:
        raise ValueError("Expanded archive exceeds limit")
    prefix = version_name(manifest["inputs"]["version"]) + "/"
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive:
            if len(files) >= MAX_MEMBERS or not member.name.startswith(prefix):
                raise ValueError("Unexpected archive member")
            name = member.name[len(prefix):]
            safe_name(name)
            if name in files or name not in manifest["files"]:
                raise ValueError("Duplicate or unexpected archive member")
            if (member.type != tarfile.REGTYPE or member.linkname or member.pax_headers
                    or member.mode != file_mode(name) or member.uid != 0 or member.gid != 0
                    or member.uname or member.gname or member.mtime != 0):
                raise ValueError("Noncanonical archive member type/mode/header")
            positive(member.size)
            expected = manifest["files"][name]
            if member.size != expected["size_bytes"]:
                raise ValueError("Archive member size differs")
            files[name] = archive.extractfile(member).read(MAX_FILE + 1)
            if len(files[name]) != member.size or sha(files[name]) != expected["sha256"]:
                raise ValueError("Archive member hash differs")
    if set(files) != set(manifest["files"]):
        raise ValueError("Missing archive members")
    inputs = manifest["inputs"]
    if inputs["wheel"]["asset"] not in files or "bin/rentgen-input-core" not in files:
        raise ValueError("Missing delivered wheel/binary")
    canonical = payload(inputs, files[inputs["wheel"]["asset"]], files["bin/rentgen-input-core"])
    expected_files = {name: {"sha256": sha(content), "size_bytes": len(content), "mode": file_mode(name)}
                      for name, content in canonical.items()}
    # Accepted gzip bytes are hash-pinned above. Comparing the uncompressed tar
    # avoids imposing this host's zlib implementation on release verification.
    if raw != tar_bytes(prefix[:-1], canonical) or expected_files != manifest["files"]:
        raise ValueError("Archive or inventory differs from canonical source payload")
    return files


def verify(version, output, extract=None):
    manifest, raw = accepted_manifest(version)
    output = no_links(output)
    if not output.is_dir() or {p.name for p in output.iterdir()} != {manifest["asset"], MANIFEST, CHECKSUMS}:
        raise ValueError("Unexpected supplement output inventory")
    if read_regular(output / MANIFEST, MAX_JSON) != raw:
        raise ValueError("Output manifest differs from committed acceptance")
    if read_regular(output / CHECKSUMS, MAX_JSON) != (manifest["sha256"] + "  " + manifest["asset"] + "\n").encode():
        raise ValueError("Output checksum differs from acceptance")
    files = verified_payload(read_regular(output / manifest["asset"], MAX_TOTAL), manifest)
    result = {"verified": True, "source_commit": manifest["inputs"]["source_commit"], "sha256": manifest["sha256"]}
    if extract is not None:
        extract = fresh_directory(extract)
        for name, data in sorted(files.items()):
            target = extract / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
            target.chmod(file_mode(name))
        result.update(wheel=str(extract / manifest["inputs"]["wheel"]["asset"]), binary=str(extract / "bin/rentgen-input-core"))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    build_parser = commands.add_parser("build", help="Create candidate bytes; does not accept a release")
    for arg in ("inputs", "wheel", "binary", "output"):
        build_parser.add_argument("--" + arg, required=True, type=Path)
    verify_parser = commands.add_parser("verify", help="Verify the committed accepted supplement")
    verify_parser.add_argument("--version", required=True)
    verify_parser.add_argument("--output", required=True, type=Path)
    verify_parser.add_argument("--extract", type=Path)
    args = parser.parse_args()
    if args.mode == "build":
        result = build(args.inputs, args.wheel, args.binary, args.output)
    else:
        result = verify(args.version, args.output, args.extract)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
