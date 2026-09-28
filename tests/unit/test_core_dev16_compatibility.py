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


def test_editor_probe_accepts_dev16_with_exact_mcp_python_and_project(monkeypatch):
    module = adapter("prepare.py")
    project = "6e461c4d-e19c-4e37-85b3-3aa0961580b7"
    identity = {
        "core": "0.1.0.dev16",
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
    head, version = module.probe(
        Path(sys.executable), Path("owned-registry.sqlite3"), project
    )
    assert (head, version) == ({"project_id": project}, "0.1.0.dev16")
    assert len(commands)==2 and not replies
    assert all(argv[1] == "-I" for argv in commands)
    assert commands[1][2:5] == ["-m", "rentgen_core", "project-head"]


@pytest.mark.parametrize("version", ["0.1.0.dev16", "0.1.0.dev999"])
def test_runtime_installer_dev16_admission_keeps_unknown_versions_refused(
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
    if version == "0.1.0.dev999":
        with pytest.raises(ValueError, match="supported installed core"):
            module.contract()
    else:
        descriptor, expected, pins = module.contract()
        assert (
            descriptor["profile_id"]
            == "bsl-ls-1.0.5-temurin21.0.12.1-win64-bmp-default-v1"
        )
        assert len(expected) == 490 and pins.__name__ == "RuntimePins"
