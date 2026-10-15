"""Fresh release qualification keeps exact versions without a stale dev pin."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(
        "delivery_" + name.replace("/", "_"),
        ROOT / "scripts/verification" / (name + ".py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScenarioReached(Exception):
    """Stop before a native operation; this test covers the preceding version gate."""


@pytest.mark.parametrize("name", [
    "verify_snapshot_diff_delivery", "verify_test_profile_delivery", "prepare_test_editor_profile",
])
@pytest.mark.parametrize("explicit", [None, "0.1.0.dev8"])
@pytest.mark.parametrize("matching", [False, True])
def test_delivery_version_gate_uses_source_default_or_explicit_target(
    tmp_path, monkeypatch, name, explicit, matching
):
    module = load(name)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_text(
        '[project]\nversion = "9.12.3.dev42"\n', encoding="utf-8"
    )
    monkeypatch.setattr(module, "ROOT", checkout)
    source = tmp_path / "source"
    file = source / "CommonModules/RentgenPlatformProbe/Ext/Module.bsl"
    file.parent.mkdir(parents=True)
    file.write_bytes("    Исключение\r\n".encode())
    scanner = tmp_path / "scanner"
    scanner.write_bytes(b"unused: version gate only")
    expected = explicit or "9.12.3.dev42"
    identity = json.dumps({
        "installed": True, "version": expected if matching else "0.0.0.dev1",
    }).encode()

    def scenario(*args, **kwargs):
        raise ScenarioReached

    args = SimpleNamespace(
        output=tmp_path / "output", source=source, python=Path(sys.executable),
        scanner=scanner, expected_core_version=explicit,
    )
    if name == "verify_snapshot_diff_delivery":
        calls = 0

        def probe_then_scenario(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise ScenarioReached
            return SimpleNamespace(stdout=identity)

        monkeypatch.setattr(module.subprocess, "run", probe_then_scenario)
        invoke = lambda: module.verify(args.python, scanner, args.output, explicit)
    else:
        monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **k: identity)
        monkeypatch.setattr(module.subprocess, "Popen", scenario)
        monkeypatch.setattr(module.subprocess, "run", scenario)
        invoke = lambda: (module.prepare(args) if name.startswith("prepare") else module.verify(args))
    with pytest.raises(ScenarioReached if matching else (AssertionError, ValueError)):
        invoke()


def test_cross_client_binds_version_metadata_and_refuses_worktree_replacement(tmp_path):
    module = load("draft_companion/verify")
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=checkout, text=True).strip()

    git("init", "-q")
    git("config", "user.name", "Version contract fixture")
    git("config", "user.email", "test@example.invalid")
    git("config", "core.autocrlf", "false")
    package = checkout / "integrations/vscode-rentgen/lib/core.cjs"
    package.parent.mkdir(parents=True)
    package.write_text("// synthetic fixture\n", encoding="utf-8")
    metadata = checkout / "pyproject.toml"
    metadata.write_text('[project]\nversion = "9.12.3.dev42"\n', encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "Bind version fixture")
    commit = git("rev-parse", "HEAD")
    manifest = module.bind_checkout(checkout, commit, commit)
    assert manifest["core_version"] == "9.12.3.dev42"
    assert "pyproject.toml" in manifest["files"]
    metadata.write_text('[project]\nversion = "9.12.3.dev43"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Raw checkout bytes differ"):
        module.bind_checkout(checkout, commit, commit)
    git("rm", "-f", "pyproject.toml")
    git("commit", "-qm", "Remove bound version metadata")
    commit = git("rev-parse", "HEAD")
    with pytest.raises(ValueError, match="Missing bound Core version metadata"):
        module.bind_checkout(checkout, commit, commit)


def test_cross_client_rejects_wrong_installed_version_before_native_fixture(tmp_path, monkeypatch):
    module = load("draft_companion/verify")
    manifest = tmp_path / "binding.json"
    manifest.write_text(json.dumps({"core_version": "9.12.3.dev42"}), encoding="utf-8")
    monkeypatch.setattr(module, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(module.importlib.metadata, "version", lambda name: "0.0.0.dev1")
    with pytest.raises(RuntimeError, match="version differs from bound checkout"):
        module.prepare_fixture(manifest, tmp_path, tmp_path / "unused-scanner")
