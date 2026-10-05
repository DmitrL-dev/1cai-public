"""Linux supplement candidates and committed acceptance have separate gates."""
import copy
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import zipfile

import pytest

SPEC = importlib.util.spec_from_file_location(
    "experimental_linux_release",
    Path(__file__).resolve().parents[2] / "scripts/release/prepare_experimental_linux.py",
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(release, "ROOT", root)

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root).decode().strip()

    git("init", "-q")
    git("config", "user.name", "Linux supplement fixture")
    git("config", "user.email", "fixture@example.invalid")
    version = "0.1.0.dev17"
    files = {p: b"Original notice fixture\n" for p in release.SOURCE_PATHS[:-1]}
    files.update({"scripts/release/prepare_experimental_linux.py": Path(SPEC.origin).read_bytes(),
                  "rust/input-core/licenses/SHA256SUMS": b"Fixture inventory only\n",
                  "rust/input-core/licenses/example/LICENSE": b"Original license fixture\n",
                  "pyproject.toml": f'[project]\nversion = "{version}"\n'.encode(),
                  "rust/input-core/Cargo.toml": b'[package]\nversion = "0.1.0"\n'})
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    git("add", ".")
    git("commit", "-qm", "Synthetic source")
    wheel = tmp_path / f"rentgen_core-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"rentgen_core-{version}.dist-info/METADATA", f"Name: rentgen-core\nVersion: {version}\n")
    binary = tmp_path / "rentgen-input-core"
    header = bytearray(64)
    header[:7] = b"\x7fELF\x02\x01\x01"
    header[16:20] = b"\x03\x00\x3e\x00"
    binary.write_bytes(header)
    inputs = {
        "schema": 1, "version": version, "rust_component_version": "0.1.0",
        "source_commit": git("rev-parse", "HEAD"), "source_tree": git("rev-parse", "HEAD^{tree}"),
        "windows_kit": {"asset": f"rentgen-core-{version}-windows-py311.zip", "sha256": "a" * 64,
                        "size_bytes": 1000, "ci_run": 101, "artifact_id": 102, "artifact_sha256": "b" * 64},
        "wheel": {"asset": wheel.name, "sha256": release.sha(wheel.read_bytes()), "size_bytes": wheel.stat().st_size},
        "linux_ci": {"ci_run": 201, "artifact_id": 202, "artifact_sha256": "c" * 64,
                     "artifact_size_bytes": 2000, "python": "3.11"},
        "binary": {"asset": binary.name, "sha256": release.sha(binary.read_bytes()), "size_bytes": binary.stat().st_size},
    }
    inputs_path = tmp_path / "inputs.json"
    inputs_path.write_bytes(release.json_bytes(inputs))
    output = tmp_path / "supplement"
    folder = root / "releases/core" / version

    def accept(manifest=None):
        folder.mkdir(parents=True, exist_ok=True)
        raw = release.json_bytes(manifest) if manifest is not None else (output / release.MANIFEST).read_bytes()
        (folder / release.MANIFEST).write_bytes(raw)
        (output / release.MANIFEST).write_bytes(raw)
        windows = {k: inputs["windows_kit"][k] for k in ("asset", "sha256", "size_bytes", "ci_run")}
        windows.update(version=version, source_commit=inputs["source_commit"],
                       wheel_sha256=inputs["wheel"]["sha256"], prerelease=True, full_product_ready=False,
                       tag="core-v0.1.0-dev17")
        (folder / "manifest.json").write_bytes(release.json_bytes(windows))
        git("add", ".")
        git("commit", "-qm", "Accept synthetic supplement", "--allow-empty")

    return {"root": root, "git": git, "version": version, "inputs": inputs, "inputs_path": inputs_path,
            "wheel": wheel, "binary": binary, "output": output, "folder": folder, "accept": accept}


def build(f):
    return release.build(f["inputs_path"], f["wheel"], f["binary"], f["output"])


def test_build_is_candidate_and_repeatable_acceptance_extracts_exact_bytes(fixture, tmp_path):
    f = fixture
    assert build(f)["accepted"] is False
    assert {p.name for p in f["output"].iterdir()} == {
        release.version_name(f["version"]) + ".tar.gz", release.MANIFEST, release.CHECKSUMS}
    with pytest.raises(FileNotFoundError):
        release.verify(f["version"], f["output"])
    repeat = tmp_path / "repeat"
    release.build(f["inputs_path"], f["wheel"], f["binary"], repeat)
    assert {p.name: p.read_bytes() for p in repeat.iterdir()} == {p.name: p.read_bytes() for p in f["output"].iterdir()}
    f["accept"]()
    target = tmp_path / "installed-inputs"
    result = release.verify(f["version"], f["output"], target)
    assert result["verified"] is True
    assert Path(result["wheel"]).read_bytes() == f["wheel"].read_bytes()
    assert Path(result["binary"]).read_bytes() == f["binary"].read_bytes()
    if os.name != "nt":
        assert Path(result["binary"]).stat().st_mode & 0o777 == 0o755
        assert Path(result["wheel"]).stat().st_mode & 0o777 == 0o644
    assert (target / "LICENSE").read_bytes() == (f["root"] / "LICENSE").read_bytes()
    assert (target / "rust/input-core/licenses/example/LICENSE").read_bytes() == b"Original license fixture\n"
    assert json.loads((target / "build-inputs.json").read_bytes()) == f["inputs"]
    guide = (target / "INSTALL.md").read_text()
    for text in ("glibc >= 2.34", "libgcc_s.so.1", "Linux >= 5.9", "memfd seals", "/proc/self/fd", "90 known failures and 2 errors", "No speedup"):
        assert text in guide
    with pytest.raises(FileExistsError):
        release.verify(f["version"], f["output"], target)
    with pytest.raises(FileExistsError):
        build(f)


@pytest.mark.parametrize("field,value", [
    ("schema", True), ("version", "../../outside"), ("version", "0.1.0.dev18"),
    ("rust_component_version", "0.2.0"), ("source_commit", "x" * 40),
    ("source_tree", "0" * 40), ("extra", True),
])
def test_input_schema_source_version_and_tree_are_closed(fixture, field, value):
    f = fixture
    f["inputs"][field] = value
    f["inputs_path"].write_bytes(release.json_bytes(f["inputs"]))
    with pytest.raises(ValueError):
        build(f)
    assert not f["output"].exists()


@pytest.mark.parametrize("section,field,value", [
    ("wheel", "sha256", "0" * 64), ("binary", "size_bytes", 0),
    ("binary", "size_bytes", release.MAX_FILE + 1), ("wheel", "size_bytes", True),
    ("wheel", "asset", "other.whl"), ("windows_kit", "artifact_id", "102"),
    ("linux_ci", "python", "3.13"), ("linux_ci", "artifact_sha256", "bad"),
    ("linux_ci", "extra", "unreviewed"),
])
def test_input_hash_size_identity_and_provenance_are_validated(fixture, section, field, value):
    f = fixture
    f["inputs"][section][field] = value
    f["inputs_path"].write_bytes(release.json_bytes(f["inputs"]))
    with pytest.raises(ValueError):
        build(f)
    assert not f["output"].exists()


@pytest.mark.parametrize("kind", ["wheel_identity", "binary_architecture"])
def test_pinned_hash_alone_does_not_establish_component_identity(fixture, kind):
    f = fixture
    key = "wheel" if kind == "wheel_identity" else "binary"
    if key == "wheel":
        with zipfile.ZipFile(f[key], "w") as archive:
            archive.writestr("other.dist-info/METADATA", "Name: another-package\nVersion: 0.1.0.dev17\n")
    else:
        f[key].write_bytes(b"not an ELF64 x86_64 executable" * 4)
    f["inputs"][key].update(sha256=release.sha(f[key].read_bytes()), size_bytes=f[key].stat().st_size)
    f["inputs_path"].write_bytes(release.json_bytes(f["inputs"]))
    with pytest.raises(ValueError):
        build(f)


def test_source_notices_use_exact_commit_not_worktree(fixture, tmp_path):
    f = fixture
    (f["root"] / "LICENSE").write_bytes(b"Uncommitted license must not ship")
    build(f)
    f["accept"]()
    target = tmp_path / "extracted"
    release.verify(f["version"], f["output"], target)
    assert (target / "LICENSE").read_bytes() == b"Original notice fixture\n"


@pytest.mark.parametrize("target", ["wheel", "binary", "inputs_path"])
@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_local_input_links_refused(fixture, tmp_path, target, kind):
    f = fixture
    original = f[target]
    alternate = tmp_path / "alternate"
    original.rename(alternate)
    try:
        if kind == "symlink":
            original.symlink_to(alternate)
        else:
            os.link(alternate, original)
    except OSError as error:
        pytest.skip(f"Link creation unavailable: {error}")
    with pytest.raises(ValueError, match="link"):
        build(f)
    assert not f["output"].exists()


def test_symlink_output_parent_refused(fixture, tmp_path):
    f = fixture
    parent = tmp_path / "linked"
    try:
        parent.symlink_to(tmp_path, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symlink unavailable: {error}")
    f["output"] = parent / "no-create"
    with pytest.raises(ValueError, match="Symlink"):
        build(f)
    assert not (tmp_path / "no-create").exists()


@pytest.mark.parametrize("kind", ["metadata", "checksum", "archive", "extra", "dirty_record", "dirty_script", "windows_wheel"])
def test_committed_gate_and_output_inventory(fixture, kind):
    f = fixture
    build(f)
    f["accept"]()
    manifest = json.loads((f["output"] / release.MANIFEST).read_bytes())
    if kind == "metadata":
        (f["output"] / release.MANIFEST).write_bytes(b"{}")
    elif kind == "checksum":
        (f["output"] / release.CHECKSUMS).write_bytes(b"wrong")
    elif kind == "archive":
        (f["output"] / manifest["asset"]).write_bytes(b"wrong")
    elif kind == "extra":
        (f["output"] / "extra.txt").write_bytes(b"wrong")
    elif kind == "dirty_script":
        (f["root"] / "scripts/release/prepare_experimental_linux.py").write_bytes(b"Uncommitted script")
    elif kind == "dirty_record":
        (f["folder"] / release.MANIFEST).write_bytes(b"{}")
    else:
        path = f["folder"] / "manifest.json"
        windows = json.loads(path.read_bytes())
        windows["wheel_sha256"] = "0" * 64
        path.write_bytes(release.json_bytes(windows))
        f["git"]("add", ".")
        f["git"]("commit", "-qm", "Wrong accepted Windows wheel")
    with pytest.raises(ValueError):
        release.verify(f["version"], f["output"])


def rewrite_tar(f, change):
    manifest = json.loads((f["output"] / release.MANIFEST).read_bytes())
    archive_path = f["output"] / manifest["asset"]
    members = []
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(archive_path.read_bytes())), mode="r:") as archive:
        for member in archive:
            members.append((member, archive.extractfile(member).read()))
    change(members, manifest)
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for member, content in members:
            archive.addfile(member, io.BytesIO(content))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=compressed, mode="wb", mtime=0) as stream:
        stream.write(data.getvalue())
    raw = compressed.getvalue()
    manifest.update(sha256=release.sha(raw), size_bytes=len(raw))
    archive_path.write_bytes(raw)
    (f["output"] / release.CHECKSUMS).write_bytes((manifest["sha256"] + "  " + manifest["asset"] + "\n").encode())
    f["accept"](manifest)


@pytest.mark.parametrize("attack", [
    "traversal", "absolute", "backslash", "duplicate", "unexpected", "missing", "symlink", "hardlink",
    "directory", "fifo", "device", "mode", "mtime", "uid", "pax", "size", "hash", "omit_license",
])
def test_malformed_tar_is_refused_even_if_outer_hash_was_accepted(fixture, tmp_path, attack):
    f = fixture
    build(f)

    def change(members, manifest):
        item, content = members[0]
        if attack == "traversal":
            item.name = "../outside"
        elif attack == "absolute":
            item.name = "/outside"
        elif attack == "backslash":
            item.name = item.name + "\\outside"
        elif attack == "duplicate":
            members.append((copy.copy(item), content))
        elif attack == "unexpected":
            item.name += ".unexpected"
        elif attack == "missing":
            members.pop()
        elif attack in ("symlink", "hardlink", "directory", "fifo", "device"):
            item.type = {"symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE, "directory": tarfile.DIRTYPE,
                         "fifo": tarfile.FIFOTYPE, "device": tarfile.CHRTYPE}[attack]
            item.linkname = "../../outside" if attack in ("symlink", "hardlink") else ""
            item.size = 0
        elif attack == "mode":
            item.mode = 0o777
        elif attack == "mtime":
            item.mtime = 1
        elif attack == "uid":
            item.uid = 1
        elif attack == "pax":
            item.pax_headers = {"comment": "Unreviewed metadata"}
        elif attack == "size":
            key = next(iter(manifest["files"]))
            manifest["files"][key]["size_bytes"] += 1
        elif attack == "hash":
            key = next(iter(manifest["files"]))
            manifest["files"][key]["sha256"] = "0" * 64
        else:
            members[:] = [(i, b) for i, b in members if not i.name.endswith("/LICENSE")]
            manifest["files"] = {k: v for k, v in manifest["files"].items() if not k.endswith("LICENSE")}
    rewrite_tar(f, change)
    target = tmp_path / "must-not-extract"
    with pytest.raises(ValueError):
        release.verify(f["version"], f["output"], target)
    assert not target.exists()
    assert not (tmp_path / "outside").exists()


def test_extra_compressed_stream_refused(fixture):
    f = fixture
    build(f)
    manifest = json.loads((f["output"] / release.MANIFEST).read_bytes())
    path = f["output"] / manifest["asset"]
    data = path.read_bytes() + gzip.compress(b"Hidden trailing payload", mtime=0)
    path.write_bytes(data)
    manifest.update(sha256=release.sha(data), size_bytes=len(data))
    (f["output"] / release.CHECKSUMS).write_bytes((manifest["sha256"] + "  " + manifest["asset"] + "\n").encode())
    f["accept"](manifest)
    with pytest.raises(ValueError, match="canonical"):
        release.verify(f["version"], f["output"])


def test_duplicate_json_fields_and_expansion_limit(fixture, monkeypatch):
    f = fixture
    with pytest.raises(ValueError, match="Duplicate"):
        release.parse_json(b'{"schema":1,"schema":1}')
    build(f)
    f["accept"]()
    manifest = json.loads((f["output"] / release.MANIFEST).read_bytes())
    data = (f["output"] / manifest["asset"]).read_bytes()
    monkeypatch.setattr(release, "MAX_TOTAL", 1024)
    with pytest.raises(ValueError, match="Expanded"):
        release.verified_payload(data, manifest)


@pytest.mark.parametrize("attack", ["extra", "wrong_scope", "scope_bool_type", "bad_mode", "oversized", "missing_binary"])
def test_manifest_inventory_is_closed(fixture, attack):
    f = fixture
    build(f)
    manifest = json.loads((f["output"] / release.MANIFEST).read_bytes())
    if attack == "extra":
        manifest["unreviewed"] = True
    elif attack == "wrong_scope":
        manifest["platform"]["full_linux_suite_green"] = True
    elif attack == "scope_bool_type":
        manifest["platform"]["full_linux_suite_green"] = 0
    elif attack == "bad_mode":
        manifest["files"]["bin/rentgen-input-core"]["mode"] = 0o644
    elif attack == "oversized":
        manifest["files"]["bin/rentgen-input-core"]["size_bytes"] = release.MAX_FILE + 1
    else:
        manifest["files"].pop("bin/rentgen-input-core")
    f["accept"](manifest)
    with pytest.raises(ValueError):
        release.verify(f["version"], f["output"])


def test_accepted_gzip_verifies_independently_of_host_compression(fixture, monkeypatch):
    f = fixture
    build(f)
    manifest = json.loads((f["output"] / release.MANIFEST).read_bytes())
    path = f["output"] / manifest["asset"]
    original = path.read_bytes()
    alternative = gzip.compress(gzip.decompress(original), compresslevel=1, mtime=0)
    assert alternative != original
    path.write_bytes(alternative)
    manifest.update(sha256=release.sha(alternative), size_bytes=len(alternative))
    (f["output"] / release.CHECKSUMS).write_bytes((manifest["sha256"] + "  " + manifest["asset"] + "\n").encode())
    f["accept"](manifest)

    def never_recompress(*args, **kwargs):
        raise AssertionError("Verification must not recompress accepted bytes")
    monkeypatch.setattr(release, "archive_bytes", never_recompress)
    assert release.verify(f["version"], f["output"])["verified"]
