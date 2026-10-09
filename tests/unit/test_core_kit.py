"""Delivery guards are checked before installing any kit content."""
import hashlib
import re
import importlib.util
from pathlib import Path
import zipfile

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def modules(monkeypatch):
    folder = ROOT / "scripts/verification"
    monkeypatch.syspath_prepend(str(folder))
    result = {}
    for name in ("kit_inputs", "export_core_kit", "verify_core_kit"):
        spec = importlib.util.spec_from_file_location(name, folder / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result[name] = module
    return result


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "C:/escape",
        "kit/file:stream",
        "kit/NUL.txt",
        "kit/trailing.",
        "kit\\escape",
    ],
)
def test_unsafe_archive_names_are_refused(tmp_path, modules, name):
    archive = tmp_path / "kit.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        info = zipfile.ZipInfo("placeholder")
        info.filename = name  # Preserve a raw hostile name on Windows too.
        stream.writestr(info, b"untrusted")
    with pytest.raises(ValueError, match="Unsafe"):
        modules["kit_inputs"].extract(archive, tmp_path / "unpacked")
    assert not (tmp_path / "escape").exists()


def test_case_aliases_and_links_are_refused(tmp_path, modules):
    for number, names in enumerate([("kit/A", "kit/a"), ("kit/link",)]):
        archive = tmp_path / f"{number}.zip"
        with zipfile.ZipFile(archive, "w") as stream:
            for name in names:
                info = zipfile.ZipInfo(name)
                if name.endswith("link"):
                    info.external_attr = 0o120777 << 16
                stream.writestr(info, b"target")
        with pytest.raises(ValueError):
            modules["kit_inputs"].extract(archive, tmp_path / f"out{number}")


def test_archive_hash_is_checked_before_creating_installation(tmp_path, modules):
    archive = tmp_path / "kit.zip"
    archive.write_bytes(b"changed")
    output = tmp_path / "installation"
    with pytest.raises(ValueError, match="hash"):
        modules["verify_core_kit"].verify(archive, output, "0" * 64)
    assert not output.exists()


def test_selected_mcp_lock_is_pinned_in_public_runtime_lock(modules):
    parse = modules["kit_inputs"].lock_entries
    selected = parse(ROOT / "requirements/locks/mcp-py311-windows.txt")
    full = parse(ROOT / "requirements/locks/product-py311-windows.txt")
    assert ("mcp", "1.30.0") in selected
    assert all(key in full and hashes <= full[key] for key, hashes in selected.items())


def test_runtime_lock_source_manifest_is_published(modules):
    source = ROOT / "requirements-rentgen.txt"
    lock = ROOT / "requirements/locks/product-py311-windows.txt"
    assert source.is_file()
    first_line = lock.read_text(encoding="utf-8").splitlines()[1]
    assert "requirements-rentgen.txt" in first_line
    # Check the declared source/lock relationship without resolving or installing
    # the full profile. Core/MCP/test profiles remain separate installation paths.
    requirements = {}
    for line in source.read_text(encoding="utf-8").splitlines():
        value = line.split("#", 1)[0].strip()
        if not value:
            continue
        requirement = Requirement(value)
        assert requirement.url is None and requirement.marker is None
        name = canonicalize_name(requirement.name)
        assert name not in requirements
        requirements[name] = requirement
    locked = modules["kit_inputs"].lock_entries(lock)
    problems = []
    for name, requirement in requirements.items():
        versions = [version for package, version in locked if package == name]
        if len(versions) != 1 or not requirement.specifier.contains(versions[0]):
            problems.append(f"{requirement}: locked versions {versions}")
    direct_roots, package = set(), None
    for line in lock.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==", line)
        if match:
            package = canonicalize_name(match[1])
        if line.lstrip().startswith("#") and "-r requirements-rentgen.txt" in line:
            assert package is not None
            direct_roots.add(package)
    if direct_roots != set(requirements):
        problems.append(f"Direct-root difference: {sorted(direct_roots ^ set(requirements))}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize(
    "text", ["mcp>=1.0", "https://example.invalid/package.whl", "mcp==1.30.0"]
)
def test_unpinned_or_remote_requirements_are_refused(tmp_path, modules, text):
    lock = tmp_path / "lock.txt"
    lock.write_text(text, "utf-8")
    with pytest.raises(ValueError):
        modules["kit_inputs"].lock_entries(lock)


def test_export_requires_approved_wheels_and_identical_scanner(tmp_path, modules):
    exporter = modules["export_core_kit"]
    first, second = tmp_path / "first", tmp_path / "second"
    for root in (first, second):
        (root / "dist").mkdir(parents=True)
        with zipfile.ZipFile(root / "dist/core.whl", "w") as stream:
            stream.writestr(
                # Both wheels must be byte-identical even across ZIP's two-
                # second timestamp boundary. This fixture tests later guards.
                zipfile.ZipInfo("rentgen_core.dist-info/METADATA"),
                "Name: rentgen-core\nVersion: 0.1.0.dev8\n",
            )
        (root / "dist/core.tar.gz").write_bytes(b"fixture only")
        (root / "bsl-scan.exe").write_bytes(b"scanner")
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    wheel = wheels / "mcp.whl"
    with zipfile.ZipFile(wheel, "w") as stream:
        stream.writestr("mcp.dist-info/METADATA", "Name: mcp\nVersion: 1.30.0\n")
    locks = second / "checkout/requirements/locks"
    locks.mkdir(parents=True)
    lock = (
        "mcp==1.30.0 --hash=sha256:"
        + hashlib.sha256(wheel.read_bytes()).hexdigest()
        + "\n"
    )
    for name in ("product-py311-windows.txt", "mcp-py311-windows.txt"):
        (locks / name).write_text(lock, "utf-8")
    license_file = tmp_path / "LICENSE"
    license_file.write_text("fixture", "utf-8")
    output = tmp_path / "kit"
    original_wheel = wheel.read_bytes()
    wheel.write_bytes(original_wheel + b"modified")
    with pytest.raises(ValueError, match="not accepted"):
        exporter.export(first, second, wheels, license_file, output)
    assert not output.exists()
    wheel.write_bytes(original_wheel)
    (second / "bsl-scan.exe").write_bytes(b"different scanner")
    with pytest.raises(ValueError, match="scanner differs"):
        exporter.export(first, second, wheels, license_file, output)
    assert not output.exists()
