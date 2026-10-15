"""Synthetic packaging controls; no installed Linux/native acceptance is implied."""
import base64
import copy
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("owned_linux_kit", ROOT / "scripts/release/prepare_owned_linux.py")
kit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kit)

GO_LICENSE = b'''Copyright 2009 The Go Authors.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

   * Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
   * Redistributions in binary form must reproduce the above
copyright notice, this list of conditions and the following disclaimer
in the documentation and/or other materials provided with the
distribution.
   * Neither the name of Google LLC nor the names of its
contributors may be used to endorse or promote products derived from
this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''


def wheel_bytes(name, version, product=None, *, requires=(), tags="py3-none-any", extra_members=None):
    prefix = f"{name.replace('-', '_')}-{version}.dist-info/"
    metadata = (f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\nRequires-Python: >=3.10\n"
                "License-Expression: MIT\nLicense-File: LICENSE\n" + "".join(f"Requires-Dist: {item}\n" for item in requires) + "\n").encode()
    files = {prefix + "METADATA": metadata,
             prefix + "WHEEL": ("Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: " + tags + "\n\n").encode(),
             prefix + "licenses/LICENSE": b"Synthetic fixture license\n"}
    files.update(product or {})
    if name == "rentgen-core":
        files[prefix + "entry_points.txt"] = b"[console_scripts]\nrentgen = rentgen_core.cli:main\nrentgen-mcp = rentgen_core.stdio_mcp:main\n"
    files.update(extra_members or {})
    rows = [[path, "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode(), str(len(raw))]
            for path, raw in sorted(files.items())]
    rows.append([prefix + "RECORD", "", ""])
    record = io.StringIO(newline="")
    csv.writer(record, lineterminator="\n").writerows(rows)
    files[prefix + "RECORD"] = record.getvalue().encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, raw in sorted(files.items()):
            archive.writestr(path, raw)
    return buffer.getvalue(), files


def elf(*, kind=2, segment=1):
    raw = bytearray(120)
    raw[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HH", raw, 16, kind, 62)
    struct.pack_into("<Q", raw, 32, 64)
    struct.pack_into("<HH", raw, 54, 56, 1)
    struct.pack_into("<IIQQQQ", raw, 64, segment, 5, 0, 0, 0, len(raw))
    return bytes(raw)


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    if os.name != "posix":
        pytest.skip("Retained no-follow exporter control requires a POSIX build host")
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(kit, "ROOT", root)

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root).decode().strip()

    git("init", "-q")
    git("config", "user.name", "Synthetic packaging control")
    git("config", "user.email", "fixture@example.invalid")
    product = {package + "/__init__.py": b'"""Synthetic packaging fixture."""\n' for package in kit.PACKAGES}
    product.update({"rentgen_core/cli.py": b"def main(): pass\n", "rentgen_core/stdio_mcp.py": b"def main(): pass\n",
                    "rentgen_graph/fixture.bin": b"\x00\xff\r\n", "rentgen_diagnostics/fixture.md": b"Source exact bytes\r\n"})
    sdk, sdk_files = wheel_bytes("mcp", "1.30.0")
    original = json.loads((ROOT / kit.PROVENANCE).read_bytes())
    selected = copy.deepcopy(next(item for item in original["wheels"] if item["name"] == "mcp"))
    prefix = "mcp-1.30.0.dist-info/"
    license_raw = sdk_files[prefix + "licenses/LICENSE"]
    selected.update(filename="mcp-1.30.0-py3-none-any.whl", size_bytes=len(sdk), sha256=kit.sha(sdk),
                    url="https://files.pythonhosted.org/fixture/mcp-1.30.0-py3-none-any.whl",
                    metadata_sha256=kit.sha(sdk_files[prefix + "METADATA"]), requires_python=">=3.10",
                    requires_dist=[], provides_extra=[], license_expression="MIT",
                    license_files=[{"path": prefix + "licenses/LICENSE", "sha256": kit.sha(license_raw), "size_bytes": len(license_raw)}])
    original["wheels"] = [selected]
    sdk_lock = ("mcp==1.30.0 --hash=sha256:" + kit.sha(sdk) + "\n").encode()
    files = dict(product)
    files.update({"pyproject.toml": b'[project]\nversion = "0.1.0.dev19"\nrequires-python = ">=3.10"\n',
                  "LICENSE": b"Synthetic fixture license\n", "go/go.mod": b"module fixture\n\ngo 1.25.5\n",
                  "go/cmd/main.go": b"package main\nfunc main() {}\n",
                  "rust/input-core/Cargo.toml": b'[package]\nversion = "0.1.0"\n',
                  "rust/input-core/Cargo.lock": b"# Synthetic fixture\n",
                  "rust/input-core/PROTOCOL.md": b"Synthetic fixture\n",
                  "rust/input-core/THIRD_PARTY_NOTICES.md": b"Synthetic fixture notice\n",
                  "rust/input-core/DEPENDENCY_PROVENANCE.json": b'{"fixture":true}\n',
                  "rust/input-core/licenses/example/LICENSE": b"Synthetic fixture license\n",
                  kit.LOCK: sdk_lock, kit.PROVENANCE: kit.json_bytes(original),
                  kit.CHECKER: (ROOT / kit.CHECKER).read_bytes()})
    rust_prefix = "rust/input-core/"
    files[rust_prefix + "licenses/SHA256SUMS"] = "".join(
        kit.sha(files[path]) + "  " + path[len(rust_prefix):] + "\n" for path in (
            rust_prefix + "THIRD_PARTY_NOTICES.md", rust_prefix + "licenses/example/LICENSE")).encode()
    for name, raw in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    git("add", ".")
    git("commit", "-qm", "Synthetic packaging source")
    commit, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    core, _ = wheel_bytes("rentgen-core", "0.1.0.dev19", product,
                          requires=["mcp==1.30.0; extra == 'mcp'"])
    scanner = elf()
    observation = {"schema": "rentgen-owned-linux-scanner-build-observation/1",
                   "protocol": "rentgen-owned-scanner-linux-v1", "source_commit": commit, "source_tree": tree,
                   "source_files_sha256": {name: kit.sha(raw) for name, raw in files.items()
                                            if name == "go/go.mod" or name.startswith("go/") and name.endswith(".go")},
                   "go_version": "go version go1.25.5 linux/amd64", "go_executable_sha256": "a" * 64,
                   "cgo_enabled": False, "build_arguments": ["build", "-trimpath", "-buildmode=exe", "./cmd/bsl-scan"],
                   "scanner": {"sha256": kit.sha(scanner), "size_bytes": len(scanner)},
                   "license": {"path": "licenses/GO-LICENSE", "sha256": kit.sha(GO_LICENSE), "size_bytes": len(GO_LICENSE)},
                   "scope": "CI build observation; installed acceptance is a separate receipt"}
    owned = {"wheel": core, "scanner": scanner, "rust_helper": elf(kind=3),
             "scanner_license": GO_LICENSE, "scanner_provenance": kit.json_bytes(observation)}
    assets = {"wheel": "rentgen_core-0.1.0.dev19-py3-none-any.whl", "scanner": "bsl-scan-owned-linux",
              "rust_helper": "rentgen-input-core", "scanner_license": "GO-LICENSE",
              "scanner_provenance": "go-scanner-build-inputs.json"}
    inputs = {"schema": 1, "profile": kit.PROFILE, "version": "0.1.0.dev19",
              "source_commit": commit, "source_tree": tree}
    paths = {}
    for name, raw in owned.items():
        inputs[name] = {"asset": assets[name], "sha256": kit.sha(raw), "size_bytes": len(raw)}
        path = tmp_path / assets[name]
        path.write_bytes(raw)
        paths[name] = path
    wheelhouse = tmp_path / "sdk"
    wheelhouse.mkdir()
    (wheelhouse / selected["filename"]).write_bytes(sdk)
    input_path = tmp_path / "inputs.json"
    input_path.write_bytes(kit.json_bytes(inputs))
    return {"root": root, "git": git, "files": files, "product": product, "owned": owned,
            "inputs": inputs, "paths": paths, "inputs_path": input_path, "wheelhouse": wheelhouse,
            "output": tmp_path / "output"}


def build(f):
    f["inputs_path"].write_bytes(kit.json_bytes(f["inputs"]))
    return kit.build(f["inputs_path"], kit.sha(f["inputs_path"].read_bytes()),
                     **f["paths"], wheelhouse=f["wheelhouse"], output=f["output"])


def test_candidate_is_deterministic_scoped_and_inventory_exact(fixture, tmp_path):
    f = fixture
    result = build(f)
    assert result["candidate"] is True and result["accepted"] is False and result["published"] is False
    first = {path.name: path.read_bytes() for path in f["output"].iterdir()}
    assert set(first) == {result["asset"], kit.MANIFEST, kit.CHECKSUMS}
    manifest = kit.parse_json(first[kit.MANIFEST])
    files = kit.verified_payload(first[result["asset"]], manifest)
    assert files["wheelhouse/" + f["inputs"]["wheel"]["asset"]] == f["owned"]["wheel"]
    assert files["GO-LICENSE"] == GO_LICENSE
    assert files["rust/input-core/licenses/example/LICENSE"] == b"Synthetic fixture license\n"
    assert files["licenses/python/mcp/mcp-1.30.0.dist-info/licenses/LICENSE"] == b"Synthetic fixture license\n"
    assert "--no-index --require-hashes" in files["INSTALL.md"].decode()
    assert "pip check" in files["INSTALL.md"].decode()
    assert "CPython 3.11.15" in files["INSTALL.md"].decode()
    assert manifest["linux_installed_cli_mcp_qualified"] is False
    assert all(str(f["root"]).encode() not in raw for raw in first.values())
    f["output"] = tmp_path / "second"
    build(f)
    assert {path.name: path.read_bytes() for path in f["output"].iterdir()} == first
    with pytest.raises(FileExistsError):
        build(f)


@pytest.mark.parametrize("package", kit.PACKAGES)
def test_source_inventory_rejects_each_package_changed_bytes(fixture, package):
    f = fixture
    altered = dict(f["product"])
    altered[package + "/__init__.py"] += b"# changed\n"
    raw, _ = wheel_bytes("rentgen-core", f["inputs"]["version"], altered,
                         requires=["mcp==1.30.0; extra == 'mcp'"])
    f["owned"]["wheel"] = raw
    f["inputs"]["wheel"].update(sha256=kit.sha(raw), size_bytes=len(raw))
    f["paths"]["wheel"].write_bytes(raw)
    with pytest.raises(ValueError, match="product sources differ"):
        build(f)
    assert not f["output"].exists()


def test_source_notices_and_packages_use_selected_git_not_dirty_worktree(fixture):
    f = fixture
    (f["root"] / "LICENSE").write_bytes(b"Dirty license\n")
    (f["root"] / "rentgen_core/__init__.py").write_bytes(b"Dirty source\n")
    result = build(f)
    files = kit.verified_payload((f["output"] / result["asset"]).read_bytes(),
                                 kit.parse_json((f["output"] / kit.MANIFEST).read_bytes()))
    assert files["LICENSE"] == b"Synthetic fixture license\n"


@pytest.mark.parametrize("field,value", [("schema", True), ("profile", "experimental-linux-supplement"),
                                         ("source_commit", "0" * 39), ("source_tree", "0" * 40),
                                         ("version", "0.1.0.dev20"), ("unknown", True)])
def test_input_contract_and_source_identity_fail_closed(fixture, field, value):
    f = fixture
    f["inputs"][field] = value
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        build(f)
    assert not f["output"].exists()


@pytest.mark.parametrize("target", ["wheel", "scanner", "scanner_license", "scanner_provenance", "rust_helper"])
def test_each_pinned_input_changed_before_parse_is_refused(fixture, monkeypatch, target):
    f = fixture
    raw = bytearray(f["paths"][target].read_bytes())
    raw[0] ^= 1
    f["paths"][target].write_bytes(raw)
    monkeypatch.setattr(kit, "candidate", lambda *a: pytest.fail("Input parser ran before hash guard"))
    with pytest.raises(ValueError, match="pinned hash/size"):
        build(f)
    assert not f["output"].exists()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "parent-symlink", "directory"])
def test_input_link_and_special_types_fail_closed(fixture, tmp_path, kind):
    f = fixture
    target = f["paths"]["wheel"]
    moved = tmp_path / "moved.whl"
    target.rename(moved)
    try:
        if kind == "symlink":
            target.symlink_to(moved)
        elif kind == "hardlink":
            os.link(moved, target)
        elif kind == "directory":
            target.mkdir()
        else:
            alternate = tmp_path / "actual"
            alternate.mkdir()
            moved.rename(alternate / target.name)
            linked = tmp_path / "linked"
            linked.symlink_to(alternate, target_is_directory=True)
            f["paths"]["wheel"] = linked / target.name
    except OSError as error:
        pytest.skip(f"Link fixture unavailable: {error}")
    with pytest.raises((ValueError, OSError)):
        build(f)
    assert not f["output"].exists()


def test_input_replacement_between_stat_and_open_is_detected(fixture, monkeypatch):
    f = fixture
    real_open = kit.os.open
    target = f["paths"]["wheel"]
    fired = False

    def raced(name, flags, *args, **kwargs):
        nonlocal fired
        if name == target.name and not fired:
            fired = True
            replacement = target.with_suffix(".replacement")
            replacement.write_bytes(target.read_bytes())
            os.replace(replacement, target)
        return real_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(kit.os, "open", raced)
    with pytest.raises(ValueError, match="changed while opening"):
        build(f)
    assert fired and not f["output"].exists()


@pytest.mark.parametrize("change", ["extra", "missing", "ambiguous-version", "wrong-hash"])
def test_sdk_exact_inventory_and_original_hashes(fixture, change):
    f = fixture
    selected = next(f["wheelhouse"].iterdir())
    if change == "extra":
        (f["wheelhouse"] / "extra.whl").write_bytes(b"fixture")
    elif change == "missing":
        selected.unlink()
    elif change == "ambiguous-version":
        (f["wheelhouse"] / "mcp-1.29.0-py3-none-any.whl").write_bytes(selected.read_bytes())
    else:
        selected.write_bytes(b"x" * selected.stat().st_size)
    with pytest.raises(ValueError):
        build(f)
    assert not f["output"].exists()


@pytest.mark.parametrize("tag", ["cp311-cp311-win_amd64", "cp311-cp311-macosx_11_0_x86_64",
                                  "cp312-cp312-manylinux_2_17_x86_64", "cp311-cp311-manylinux_2_35_x86_64",
                                  "cp311-cp311-manylinux_2_17_aarch64", "cp311-cp311-linux_x86_64",
                                  "py3-none-any.win_amd64"])
def test_wrong_linux_abi_or_platform_wheel_is_refused(tag):
    raw, _ = wheel_bytes("fixture", "1.0", tags=tag)
    with pytest.raises(ValueError, match="ABI"):
        kit.wheel_files(f"fixture-1.0-{tag}.whl", raw, "fixture", "1.0")


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a\\b", "a:stream", "module/CON.txt"])
def test_wheel_traversal_and_ambiguous_names_are_refused(name):
    raw, _ = wheel_bytes("fixture", "1.0", extra_members={name: b"fixture"})
    with pytest.raises(ValueError, match="path"):
        kit.wheel_files("fixture-1.0-py3-none-any.whl", raw, "fixture", "1.0")


def test_wheel_duplicate_and_unbounded_zip_directory_refused_before_allocation(monkeypatch):
    raw, _ = wheel_bytes("fixture", "1.0")
    buffer = io.BytesIO(raw)
    with zipfile.ZipFile(buffer, "a") as archive:
        with pytest.warns(UserWarning, match="Duplicate"):
            archive.writestr("fixture-1.0.dist-info/METADATA", b"duplicate")
    with pytest.raises(ValueError, match="duplicate"):
        kit.wheel_files("fixture-1.0-py3-none-any.whl", buffer.getvalue(), "fixture", "1.0")
    changed = bytearray(raw)
    position = changed.rfind(b"PK\x05\x06")
    struct.pack_into("<HH", changed, position + 8, kit.MAX_MEMBERS + 1, kit.MAX_MEMBERS + 1)
    monkeypatch.setattr(kit.zipfile, "ZipFile", lambda *a: pytest.fail("ZIP allocation preceded directory bound"))
    with pytest.raises(ValueError, match="directory bound"):
        kit.wheel_files("fixture-1.0-py3-none-any.whl", bytes(changed), "fixture", "1.0")


def test_forged_eocd_count_cannot_hide_actual_directory_allocations(monkeypatch):
    raw, _ = wheel_bytes("fixture", "1.0")
    changed = bytearray(raw)
    position = changed.rfind(b"PK\x05\x06")
    struct.pack_into("<HH", changed, position + 8, 1, 1)
    monkeypatch.setattr(kit.zipfile, "ZipFile", lambda *a: pytest.fail("ZIP allocation preceded actual directory walk"))
    with pytest.raises(ValueError, match="actual directory count"):
        kit.wheel_files("fixture-1.0-py3-none-any.whl", bytes(changed), "fixture", "1.0")


def test_record_missing_member_or_bad_hash_is_refused():
    raw, files = wheel_bytes("fixture", "1.0")
    files["fixture-1.0.dist-info/licenses/LICENSE"] += b"changed"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    with pytest.raises(ValueError, match="RECORD hash"):
        kit.wheel_files("fixture-1.0-py3-none-any.whl", buffer.getvalue(), "fixture", "1.0")


def test_wheel_filename_and_metadata_tag_disagreement_is_refused():
    raw, _ = wheel_bytes("fixture", "1.0", tags="cp311-abi3-manylinux_2_34_x86_64")
    with pytest.raises(ValueError, match="metadata target ABI"):
        kit.wheel_files("fixture-1.0-py3-none-any.whl", raw, "fixture", "1.0")


def test_wheel_tag_metadata_bound_precedes_parser(monkeypatch):
    raw, _ = wheel_bytes("fixture", "1.0", extra_members={
        "fixture-1.0.dist-info/WHEEL": b"Header: value\n" * 6000})
    original = kit.BytesParser
    parsed_sizes = []

    class BoundedParser:
        def parsebytes(self, data):
            parsed_sizes.append(len(data))
            assert len(data) < 65536
            return original().parsebytes(data)

    monkeypatch.setattr(kit, "BytesParser", BoundedParser)
    with pytest.raises(ValueError, match="tag metadata missing/exceeds"):
        kit.wheel_files("fixture-1.0-py3-none-any.whl", raw, "fixture", "1.0")
    assert len(parsed_sizes) == 1


@pytest.mark.parametrize("change", ["missing", "duplicate", "incompatible", "source-incompatible"])
def test_core_python_requirement_must_match_source_and_linux_target(fixture, change):
    f = fixture
    _, files = wheel_bytes("rentgen-core", f["inputs"]["version"], f["product"],
                           requires=["mcp==1.30.0; extra == 'mcp'"])
    path = "rentgen_core-0.1.0.dev19.dist-info/METADATA"
    metadata = files[path]
    source = dict(f["files"])
    if change == "missing":
        metadata = metadata.replace(b"Requires-Python: >=3.10\n", b"")
    elif change == "duplicate":
        metadata = metadata.replace(b"Requires-Python: >=3.10\n", b"Requires-Python: >=3.10\nRequires-Python: >=3.10\n")
    else:
        metadata = metadata.replace(b"Requires-Python: >=3.10\n", b"Requires-Python: >=3.12\n")
        if change == "source-incompatible":
            source["pyproject.toml"] = source["pyproject.toml"].replace(b">=3.10", b">=3.12")
    raw, _ = wheel_bytes("rentgen-core", f["inputs"]["version"], f["product"],
                         requires=["mcp==1.30.0; extra == 'mcp'"], extra_members={path: metadata})
    with pytest.raises(ValueError, match="Requires-Python"):
        kit.validate_core(f["inputs"]["wheel"]["asset"], raw, f["inputs"]["version"], source)


def test_core_wheel_license_cannot_replace_selected_source_original(fixture):
    f = fixture
    raw, _ = wheel_bytes("rentgen-core", f["inputs"]["version"], f["product"],
                         requires=["mcp==1.30.0; extra == 'mcp'"], extra_members={
                             "rentgen_core-0.1.0.dev19.dist-info/licenses/LICENSE": b"Altered original notice\n"})
    with pytest.raises(ValueError, match="original license"):
        kit.validate_core(f["inputs"]["wheel"]["asset"], raw, f["inputs"]["version"], f["files"])


def test_zip_symlink_and_file_directory_collision_are_refused():
    raw, files = wheel_bytes("fixture", "1.0")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        linked = zipfile.ZipInfo("symlink")
        linked.create_system = 3
        linked.external_attr = 0o120777 << 16
        archive.writestr(linked, b"target")
    with pytest.raises(ValueError, match="Unsafe"):
        kit.wheel_files("fixture-1.0-py3-none-any.whl", buffer.getvalue(), "fixture", "1.0")
    raw, _ = wheel_bytes("fixture", "1.0", extra_members={"file": b"x", "file/child": b"y"})
    with pytest.raises(ValueError, match="collision"):
        kit.wheel_files("fixture-1.0-py3-none-any.whl", raw, "fixture", "1.0")


@pytest.mark.parametrize("kind,segment", [(3, 1), (2, 2), (2, 3)])
def test_scanner_dynamic_or_pie_is_refused(kind, segment):
    with pytest.raises(ValueError):
        kit.validate_elf(elf(kind=kind, segment=segment), static=True)


@pytest.mark.parametrize("change", ["source", "toolchain", "cgo", "protocol", "license", "scope"])
def test_scanner_observation_source_protocol_license_and_scope_are_bound(fixture, change):
    f = fixture
    observation = kit.parse_json(f["owned"]["scanner_provenance"])
    if change == "source":
        observation["source_files_sha256"]["go/cmd/main.go"] = "0" * 64
    elif change == "toolchain":
        observation["go_version"] = "go version go1.25.6 linux/amd64"
    elif change == "cgo":
        observation["cgo_enabled"] = True
    elif change == "protocol":
        observation["protocol"] = "legacy"
    elif change == "license":
        observation["license"]["sha256"] = "0" * 64
    else:
        observation["scope"] = "Linux installed acceptance passed"
    raw = kit.json_bytes(observation)
    f["paths"]["scanner_provenance"].write_bytes(raw)
    f["inputs"]["scanner_provenance"].update(sha256=kit.sha(raw), size_bytes=len(raw))
    with pytest.raises(ValueError):
        build(f)
    assert not f["output"].exists()


@pytest.mark.parametrize("change", ["accepted", "published", "qualified", "extra-file", "member-mode", "trailing-tar"])
def test_verified_candidate_never_accepts_false_scope_or_noncanonical_inventory(fixture, change):
    f = fixture
    raw, manifest = kit.candidate(f["inputs"], f["owned"], f["wheelhouse"])
    if change in ("accepted", "published", "qualified"):
        manifest[{"qualified": "linux_installed_cli_mcp_qualified"}.get(change, change)] = True
    else:
        files = kit.verified_payload(raw, manifest)
        if change == "extra-file":
            files["unlisted.txt"] = b"extra"
            raw = kit.archive_bytes(kit.asset_name(f["inputs"]["version"]), files)
        elif change == "trailing-tar":
            raw = gzip.compress(gzip.decompress(raw) + b"extra tar bytes", mtime=0)
        else:
            manifest["files"]["bin/bsl-scan-owned-linux"]["mode"] = 0o777
        manifest.update(sha256=kit.sha(raw), size_bytes=len(raw))
    with pytest.raises(ValueError):
        kit.verified_payload(raw, manifest)


def test_no_external_input_json_hash_no_output(fixture):
    f = fixture
    with pytest.raises(ValueError, match="pinned hash/size"):
        kit.build(f["inputs_path"], "0" * 64, **f["paths"], wheelhouse=f["wheelhouse"], output=f["output"])
    assert not f["output"].exists()


def test_build_runs_only_git_never_installers_or_binaries(fixture, monkeypatch):
    f = fixture
    real = kit.subprocess.check_output
    observed = []

    def checked(command, *args, **kwargs):
        observed.append(command[0])
        assert command[0] == "git"
        return real(command, *args, **kwargs)

    monkeypatch.setattr(kit.subprocess, "check_output", checked)
    result = build(f)
    assert result["accepted"] is False
    assert observed and set(observed) == {"git"}


def test_rust_license_inventory_rejects_missing_unlisted_or_changed_original(fixture):
    source = dict(fixture["files"])
    kit.validate_rust_notices(source)
    source["rust/input-core/licenses/example/LICENSE"] += b"changed"
    with pytest.raises(ValueError, match="inventory hash"):
        kit.validate_rust_notices(source)
    source = dict(fixture["files"])
    source["rust/input-core/licenses/unlisted/LICENSE"] = b"unlisted"
    with pytest.raises(ValueError, match="inventory incomplete"):
        kit.validate_rust_notices(source)


def test_source_git_symlink_refused_before_payload(fixture):
    f = fixture
    path = f["root"] / "rentgen_core/__init__.py"
    path.unlink()
    path.symlink_to("cli.py")
    f["git"]("add", ".")
    f["git"]("commit", "-qm", "Synthetic linked source negative")
    with pytest.raises(ValueError, match="regular blobs"):
        kit.source_blobs(f["git"]("rev-parse", "HEAD"))


def test_output_symlink_parent_and_traversal_refused(fixture, tmp_path):
    f = fixture
    linked = tmp_path / "linked-output"
    linked.symlink_to(tmp_path, target_is_directory=True)
    f["output"] = linked / "must-not-exist"
    with pytest.raises(ValueError, match="Directory symlink"):
        build(f)
    assert not (tmp_path / "must-not-exist").exists()
    f["output"] = tmp_path / "unused" / ".." / "must-not-exist"
    with pytest.raises(ValueError, match="traversal"):
        build(f)
    assert not (tmp_path / "must-not-exist").exists()


def test_total_inputs_and_sdk_copy_budgets_fail_before_read(fixture, monkeypatch):
    f = fixture
    inputs = copy.deepcopy(f["inputs"])
    inputs["wheel"]["size_bytes"] = kit.MAX_FILE
    inputs["scanner"]["size_bytes"] = kit.MAX_FILE
    with pytest.raises(ValueError, match="input total"):
        kit.validate_inputs(inputs)
    monkeypatch.setattr(kit, "OwnedDirectory", lambda *a, **k: pytest.fail("Directory read preceded planned byte bound"))
    with pytest.raises(ValueError, match="remaining byte budget"):
        kit.sdk_payload(f["wheelhouse"], f["files"], byte_budget=1)


@pytest.mark.parametrize("change", ["wheel-origin", "metadata-origin", "lock-hash"])
def test_selected_checker_rejects_unqualified_origin_or_independent_lock_change(fixture, change):
    f = fixture
    source = dict(f["files"])
    provenance = kit.parse_json(source[kit.PROVENANCE])
    if change == "wheel-origin":
        provenance["wheels"][0]["url"] = "https://example.invalid/mcp-1.30.0-py3-none-any.whl"
    elif change == "metadata-origin":
        provenance["wheels"][0]["pypi_json_url"] = "https://example.invalid/metadata"
    else:
        source[kit.LOCK] = b"mcp==1.30.0 --hash=sha256:" + b"0" * 64 + b"\n"
    source[kit.PROVENANCE] = kit.json_bytes(provenance)
    with pytest.raises(ValueError):
        kit.sdk_payload(f["wheelhouse"], source)


def test_selected_checker_rejects_missing_transitive_dependency(fixture):
    f = fixture
    source = dict(f["files"])
    raw, contents = wheel_bytes("mcp", "1.30.0", requires=["unselected>=1"])
    provenance = kit.parse_json(source[kit.PROVENANCE])
    entry = provenance["wheels"][0]
    entry.update(sha256=kit.sha(raw), size_bytes=len(raw), requires_dist=["unselected>=1"],
                 metadata_sha256=kit.sha(contents["mcp-1.30.0.dist-info/METADATA"]))
    source[kit.PROVENANCE] = kit.json_bytes(provenance)
    source[kit.LOCK] = ("mcp==1.30.0 --hash=sha256:" + kit.sha(raw) + "\n").encode()
    (f["wheelhouse"] / entry["filename"]).write_bytes(raw)
    with pytest.raises(ValueError, match="missing or incompatible"):
        kit.sdk_payload(f["wheelhouse"], source)
