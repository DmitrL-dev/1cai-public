"""The Linux offline SDK inputs fail closed without host marker resolution."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOCKS = ROOT / "requirements/locks"


@pytest.fixture
def checker():
    spec = importlib.util.spec_from_file_location("linux_mcp_dependency_lock", LOCKS / "check_linux_mcp_lock.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def entry(name, *, requires=(), extras=(), version="1.0"):
    return {"name": name, "version": version, "requires_python": ">=3.10", "requires_dist": list(requires), "provides_extra": list(extras)}


def root_entry(*, requires=()):
    return entry("mcp", version="1.30.0", requires=requires)


def write_inputs(tmp_path, checker, *, filename="mcp-1.30.0-py3-none-any.whl", members=None):
    metadata = b"Metadata-Version: 2.4\nName: mcp\nVersion: 1.30.0\nRequires-Python: >=3.10\nLicense-Expression: MIT\n\n"
    license_bytes = b"fixture license; not third-party delivery bytes\n"
    prefix = "mcp-1.30.0.dist-info/"
    if members is None:
        members = {
            prefix + "METADATA": metadata,
            prefix + "WHEEL": b"Wheel-Version: 1.0\nGenerator: test fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n",
            prefix + "licenses/LICENSE": license_bytes,
        }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, blob in members.items():
            if isinstance(name, zipfile.ZipInfo):
                archive.writestr(name, blob)
            else:
                archive.writestr(name, blob)
    blob = buffer.getvalue()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    (wheelhouse / filename).write_bytes(blob)
    original = json.loads(checker.DEFAULT_PROVENANCE.read_text())
    selected = next(copy.deepcopy(item) for item in original["wheels"] if item["name"] == "mcp")
    selected.update(
        filename=filename, size_bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(),
        url="https://files.pythonhosted.org/fixture/" + filename,
        metadata_sha256=hashlib.sha256(metadata).hexdigest(), requires_python=">=3.10",
        requires_dist=[], provides_extra=[], license_expression="MIT",
        license_files=[{"path": prefix + "licenses/LICENSE", "size_bytes": len(license_bytes), "sha256": hashlib.sha256(license_bytes).hexdigest()}],
    )
    original["wheels"] = [selected]
    provenance = tmp_path / "provenance.json"
    provenance.write_text(json.dumps(original))
    lock = tmp_path / "lock.txt"
    lock.write_text("mcp==1.30.0 --hash=sha256:" + selected["sha256"] + "\n")
    return wheelhouse, provenance, lock


def replace_fixture_bytes(wheelhouse, provenance, lock, blob):
    """Re-pin a hostile fixture, so structural guards rather than hash guards run."""
    next(wheelhouse.iterdir()).write_bytes(blob)
    data = json.loads(provenance.read_text())
    digest = hashlib.sha256(blob).hexdigest()
    data["wheels"][0].update(sha256=digest, size_bytes=len(blob))
    provenance.write_text(json.dumps(data))
    lock.write_text("mcp==1.30.0 --hash=sha256:" + digest + "\n")


def test_selected_real_metadata_closure_is_targeted_without_version_upgrades(checker):
    data = checker.load_inputs()
    assert len(data["wheels"]) == 29
    assert sum(item["size_bytes"] for item in data["wheels"]) == 9418024
    assert data["activated_extras"]["pyjwt"] == ["crypto"]
    assert "pywin32" not in data["activated_extras"]
    prior = dict(re.findall(r"^([a-z0-9.-]+)==([^\s]+)", (LOCKS / "mcp-py311-windows.txt").read_text(), re.M))
    assert all(prior[item["name"]] == item["version"] for item in data["wheels"])
    assert 'mcp = ["mcp==1.30.0"]' in (ROOT / "pyproject.toml").read_text()


def test_linux_base_and_transitive_extra_are_both_required(checker):
    wheels = [
        root_entry(requires=["auth[crypto]>=1", "windows-only; sys_platform == 'win32'"]),
        entry("auth", extras=["crypto"], requires=["base>=1", "crypto; extra == 'crypto'", "not-selected; extra == 'cli'"]),
        entry("base"), entry("crypto"),
    ]
    resolved = checker.validate_dependency_closure(wheels, checker.MARKER_ENVIRONMENT)
    assert resolved == {"auth": ["crypto"], "base": [], "crypto": [], "mcp": []}
    for missing in ("base", "crypto"):
        with pytest.raises(ValueError, match="missing or incompatible"):
            checker.validate_dependency_closure([w for w in wheels if w["name"] != missing], checker.MARKER_ENVIRONMENT)


@pytest.mark.parametrize("key,value", [("sys_platform", "darwin"), ("sys_platform", "win32"), ("python_full_version", "3.12.0"), ("platform_machine", "aarch64")])
def test_other_target_environment_is_refused(checker, key, value):
    environment = {**checker.MARKER_ENVIRONMENT, key: value}
    with pytest.raises(ValueError, match="target marker"):
        checker.validate_dependency_closure([root_entry()], environment)


@pytest.mark.parametrize("requirement", ["dep>=2", "dep[unknown]", "dep @ https://example.invalid/dep.whl", "dep; platform_release >= '5.9'"])
def test_unsatisfied_or_unqualified_dependency_is_refused(checker, requirement):
    with pytest.raises(ValueError):
        checker.validate_dependency_closure([root_entry(requires=[requirement]), entry("dep")], checker.MARKER_ENVIRONMENT)


def test_extra_unreachable_package_is_refused(checker):
    with pytest.raises(ValueError, match="unreachable"):
        checker.validate_dependency_closure([root_entry(), entry("unused")], checker.MARKER_ENVIRONMENT)


def test_minimal_selected_original_wheel_passes_without_importing_it(tmp_path, checker):
    wheelhouse, provenance, lock = write_inputs(tmp_path, checker)
    receipt = checker.verify_wheelhouse(wheelhouse, provenance_path=provenance, lock_path=lock)
    assert receipt["wheels"][0]["name"] == "mcp"
    assert "no installation" in receipt["scope"]


@pytest.mark.parametrize("change", ["missing", "extra", "changed", "truncated", "symlink"])
def test_wheel_inventory_and_digest_fail_before_zip_metadata(tmp_path, checker, monkeypatch, change):
    wheelhouse, provenance, lock = write_inputs(tmp_path, checker)
    wheel = next(wheelhouse.iterdir())
    if change == "missing":
        wheel.unlink()
    elif change == "extra":
        (wheelhouse / "unselected.whl").write_bytes(b"not selected")
    elif change == "changed":
        blob = bytearray(wheel.read_bytes())
        blob[0] ^= 1
        wheel.write_bytes(blob)
    elif change == "truncated":
        wheel.write_bytes(wheel.read_bytes()[:-1])
    else:
        outside = tmp_path / "outside.whl"
        wheel.replace(outside)
        try:
            wheel.symlink_to(outside)
        except OSError as exc:
            pytest.skip(f"OS denied a symlink test fixture: {exc}")
    monkeypatch.setattr(checker.zipfile, "ZipFile", lambda *args: pytest.fail("ZIP read preceded inventory/hash guard"))
    with pytest.raises(ValueError):
        checker.verify_wheelhouse(wheelhouse, provenance_path=provenance, lock_path=lock)


@pytest.mark.parametrize("filename", [
    "mcp-1.30.0-cp311-cp311-win_amd64.whl", "mcp-1.30.0-cp311-cp311-macosx_11_0_x86_64.whl",
    "mcp-1.30.0-cp312-cp312-manylinux_2_17_x86_64.whl", "mcp-1.30.0-cp311-cp311-manylinux_2_35_x86_64.whl",
    "mcp-1.30.0-cp311-cp311-manylinux_2_17_aarch64.whl", "mcp-1.30.0-cp311-cp311-linux_x86_64.whl",
    "mcp-1.30.0-cp311-cp311-manylinux_2_17_x86_64.win_amd64.whl",
    "mcp-1.30.0-py3-none-any.macosx_11_0_x86_64.whl",
])
def test_wrong_binary_wheel_target_is_refused(tmp_path, checker, filename):
    wheelhouse, provenance, lock = write_inputs(tmp_path, checker, filename=filename)
    with pytest.raises(ValueError, match="wrong target wheel"):
        checker.verify_wheelhouse(wheelhouse, provenance_path=provenance, lock_path=lock)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a\\b", "a:stream"])
def test_hostile_original_archive_names_are_refused(tmp_path, checker, name):
    wheelhouse, provenance, lock = write_inputs(tmp_path, checker, members={name: b"fixture"})
    with pytest.raises(ValueError, match="unsafe wheel archive"):
        checker.verify_wheelhouse(wheelhouse, provenance_path=provenance, lock_path=lock)
    assert not (tmp_path / "escape").exists()


def test_zip_directory_count_is_bounded_before_zipfile_parse(tmp_path, checker, monkeypatch):
    wheelhouse, provenance, lock = write_inputs(tmp_path, checker)
    wheel = next(wheelhouse.iterdir())
    blob = bytearray(wheel.read_bytes())
    position = blob.rfind(b"PK\x05\x06")
    struct.pack_into("<HH", blob, position + 8, 10001, 10001)
    wheel.write_bytes(blob)
    data = json.loads(provenance.read_text())
    digest = hashlib.sha256(blob).hexdigest()
    data["wheels"][0]["sha256"] = digest
    provenance.write_text(json.dumps(data))
    lock.write_text("mcp==1.30.0 --hash=sha256:" + digest + "\n")
    monkeypatch.setattr(checker.zipfile, "ZipFile", lambda *args: pytest.fail("unbounded ZIP directory parse"))
    with pytest.raises(ValueError, match="ZIP directory bound"):
        checker.verify_wheelhouse(wheelhouse, provenance_path=provenance, lock_path=lock)


@pytest.mark.parametrize("lower_budget", [False, True])
def test_underreported_zip_directory_count_is_refused_before_constructor(tmp_path, checker, monkeypatch, lower_budget):
    wheelhouse, provenance, lock = write_inputs(tmp_path, checker)
    wheel = next(wheelhouse.iterdir())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for number in range(4097):
            archive.writestr(f"fixture/{number}.txt", b"x")
    blob = bytearray(buffer.getvalue())
    position = blob.rfind(b"PK\x05\x06")
    struct.pack_into("<HH", blob, position + 8, 1, 1)
    wheel.write_bytes(blob)
    data = json.loads(provenance.read_text())
    digest = hashlib.sha256(blob).hexdigest()
    data["wheels"][0].update(sha256=digest, size_bytes=len(blob))
    provenance.write_text(json.dumps(data))
    lock.write_text("mcp==1.30.0 --hash=sha256:" + digest + "\n")
    if lower_budget:
        monkeypatch.setattr(checker, "MAX_MEMBERS", 4096)
    monkeypatch.setattr(checker.zipfile, "ZipFile", lambda *args: pytest.fail("underreported central directory reached ZipFile"))
    with pytest.raises(ValueError, match="ZIP .*directory|ZIP central"):
        checker.verify_wheelhouse(wheelhouse, provenance_path=provenance, lock_path=lock)


@pytest.mark.parametrize("change", [
    "central-name-size", "central-extra-size", "central-comment-size", "central-disk",
    "zip64-compressed-size", "zip64-expanded-size", "zip64-offset", "zip64-version",
    "local-name-size", "local-extra-size", "local-data-overlap", "local-size-mismatch",
    "local-offset-in-central", "central-record-signature", "central-end-gap", "local-record-overlap",
    "central-zip64-extra", "local-zip64-extra", "eocd-multidisk",
])
def test_structural_zip_lies_are_refused_before_constructor(tmp_path, checker, monkeypatch, change):
    if change.endswith("zip64-extra"):
        item = zipfile.ZipInfo("fixture.txt")
        item.extra = struct.pack("<HHQ", 0xCAFE, 8, 0)
        wheelhouse, provenance, lock = write_inputs(tmp_path, checker, members={item: b"x"})
    else:
        wheelhouse, provenance, lock = write_inputs(tmp_path, checker)
    blob = bytearray(next(wheelhouse.iterdir()).read_bytes())
    eocd = blob.rfind(b"PK\x05\x06")
    central = struct.unpack_from("<L", blob, eocd + 16)[0]
    local = struct.unpack_from("<L", blob, central + 42)[0]
    if change.startswith("central-") and change.endswith("-size"):
        offset = {"central-name-size": 28, "central-extra-size": 30, "central-comment-size": 32}[change]
        struct.pack_into("<H", blob, central + offset, 65535)
    elif change == "central-disk":
        struct.pack_into("<H", blob, central + 34, 1)
    elif change in {"zip64-compressed-size", "zip64-expanded-size", "zip64-offset"}:
        offset = {"zip64-compressed-size": 20, "zip64-expanded-size": 24, "zip64-offset": 42}[change]
        struct.pack_into("<L", blob, central + offset, 0xFFFFFFFF)
    elif change == "zip64-version":
        struct.pack_into("<H", blob, central + 6, 45)
    elif change in {"local-name-size", "local-extra-size"}:
        struct.pack_into("<H", blob, local + (26 if change == "local-name-size" else 28), 65535)
    elif change == "local-data-overlap":
        struct.pack_into("<L", blob, central + 20, central)
    elif change == "local-size-mismatch":
        struct.pack_into("<L", blob, local + 22, 1)
    elif change == "local-offset-in-central":
        struct.pack_into("<L", blob, central + 42, central)
    elif change == "central-record-signature":
        blob[central:central + 4] = b"FAIL"
    elif change == "central-end-gap":
        blob[eocd:eocd] = b"unused gap"
    elif change == "local-record-overlap":
        lengths = struct.unpack_from("<3H", blob, central + 28)
        record = blob[central:central + 46 + sum(lengths)]
        old_count, old_size = struct.unpack_from("<HL", blob, eocd + 10)
        blob[eocd:eocd] = record
        eocd += len(record)
        struct.pack_into("<HH", blob, eocd + 8, old_count + 1, old_count + 1)
        struct.pack_into("<L", blob, eocd + 12, old_size + len(record))
    elif change.endswith("zip64-extra"):
        if change.startswith("central"):
            name_size = struct.unpack_from("<H", blob, central + 28)[0]
            extra = central + 46 + name_size
        else:
            name_size = struct.unpack_from("<H", blob, local + 26)[0]
            extra = local + 30 + name_size
        struct.pack_into("<H", blob, extra, 1)
    else:
        struct.pack_into("<H", blob, eocd + 4, 1)
    replace_fixture_bytes(wheelhouse, provenance, lock, blob)
    monkeypatch.setattr(checker.zipfile, "ZipFile", lambda *args: pytest.fail("structurally invalid directory reached ZipFile"))
    with pytest.raises(ValueError, match="wheel ZIP"):
        checker.verify_wheelhouse(wheelhouse, provenance_path=provenance, lock_path=lock)


def test_lock_hash_cannot_be_substituted_separately(tmp_path, checker):
    wheelhouse, provenance, lock = write_inputs(tmp_path, checker)
    lock.write_text("mcp==1.30.0 --hash=sha256:" + "0" * 64 + "\n")
    with pytest.raises(ValueError, match="lock and provenance differ"):
        checker.verify_wheelhouse(wheelhouse, provenance_path=provenance, lock_path=lock)
