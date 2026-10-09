"""Version admission fixtures; no installed runtime or native 1C is executed."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


def adapter(name):
    path = Path(__file__).resolve().parents[2] / "integrations/open-editor" / name
    spec = importlib.util.spec_from_file_location("dev16_compat_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("version", [f"0.1.0.dev{dev}" for dev in range(7, 19)])
def test_editor_probe_accepts_reviewed_versions_with_exact_mcp_python_and_project(monkeypatch, version):
    module = adapter("prepare.py")
    project = "6e461c4d-e19c-4e37-85b3-3aa0961580b7"
    identity = {
        "core": version,
        "mcp": "1.30.0",
        "platform": "win32",
        "python": [3, 11],
        "installed": True,
    }
    replies = [identity, {"result": {"project_id": project}}]
    commands = []

    def execute(argv, **options):
        commands.append(argv)
        return SimpleNamespace(returncode=0, stdout=json.dumps(replies.pop(0)))

    monkeypatch.setattr(module.subprocess, "run", execute)
    head, actual_version = module.probe(
        Path(sys.executable), Path("owned-registry.sqlite3"), project
    )
    assert (head, actual_version) == ({"project_id": project}, version)
    assert len(commands)==2 and not replies
    assert all(argv[1] == "-I" for argv in commands)
    assert commands[1][2:5] == ["-m", "rentgen_core", "project-head"]


@pytest.mark.parametrize("version", [f"0.1.0.dev{dev}" for dev in [*range(4, 19), 19, 999]])
def test_runtime_installer_admission_keeps_unknown_versions_refused(
    monkeypatch, version
):
    module = adapter("install_bsl_runtime.py")
    import rentgen_core
    actual = module.importlib.metadata.version
    monkeypatch.setattr(
        module.importlib.metadata,
        "version",
        lambda name: version if name == "rentgen-core" else actual(name),
    )
    # Model the same package/prefix relation queried by -I's installed probe.
    monkeypatch.setattr(
        rentgen_core,
        "__file__",
        str(Path(sys.prefix) / "Lib/site-packages/rentgen_core/__init__.py"),
    )
    monkeypatch.setattr(
        module,
        "sys",
        SimpleNamespace(platform="win32", version_info=(3, 11), prefix=sys.prefix),
    )
    if version in {"0.1.0.dev19", "0.1.0.dev999"}:
        with pytest.raises(ValueError, match="supported installed core"):
            module.contract()
    else:
        descriptor, expected, pins = module.contract()
        assert (
            descriptor["profile_id"]
            == "bsl-ls-1.0.5-temurin21.0.12.1-win64-bmp-default-v1"
        )
        assert len(expected) == 490 and pins.__name__ == "RuntimePins"


@pytest.mark.parametrize(
    "platform,version", [("linux", (3, 11)), ("win32", (3, 12))]
)
def test_runtime_installer_keeps_os_and_python_admission_explicit(
    monkeypatch, platform, version
):
    module = adapter("install_bsl_runtime.py")
    monkeypatch.setattr(
        module,
        "sys",
        SimpleNamespace(platform=platform, version_info=version, prefix=sys.prefix),
    )
    with pytest.raises(ValueError, match="Windows Python 3.11"):
        module.contract()
