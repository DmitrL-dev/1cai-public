"""Portable verifier guards; never substitutes for real editor acceptance."""
import importlib.util
import json
from pathlib import Path
import subprocess
import urllib.request

import pytest

HERE = Path(__file__).resolve().parents[2] / "scripts/verification/editor_workbench"


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(HERE))
    def load(name):
        spec = importlib.util.spec_from_file_location("test_editor_workbench_" + name, HERE / (name + ".py"))
        value = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(value)
        return value
    return load("inputs"), load("run")


def phase(which="first"):
    fields = {
        "first": ["opened_project", "metadata_search", "manual_draft_saved", "real_bsl", "problems_exact_revision",
                  "concurrent_cli", "stale_refused", "revoked_write_refused", "forged_handle_refused",
                  "crash_stage_committed", "snapshot_pinned_before_restart"],
        "restart": ["fresh_extension_host", "persisted_context_restored", "pinned_snapshot_restored",
                    "historical_draft_restored", "reconciled_unobserved_commit", "inspect_did_not_repeat_save",
                    "historical_bsl_bound", "source_unchanged"],
    }
    return {"schema": 1, "accepted": True, "runtime": "actual_windows_electron_extension_host", "phase": which,
            "process_id": 123, "model_calls": 0, "live_1c_apply": False,
            "fault_model": "durable_intent_commit_unobserved", **dict.fromkeys(fields[which], True)}


@pytest.mark.parametrize("which", ["first", "restart"])
def test_complete_receipt_reduced_without_private_body(modules, which):
    _, runner = modules
    value = phase(which) | {"private_source": "never publish", "environment": {"TOKEN": "never publish"}}
    assert runner.reduce_phase(value) == phase(which)


@pytest.mark.parametrize("changed", [
    {"accepted": False}, {"runtime": "node_service_mock"}, {"phase": "other"},
    {"process_id": True}, {"process_id": 0}, {"model_calls": 1}, {"live_1c_apply": True},
    {"fault_model": "real_tcp_loss"}, {"stale_refused": False}, {"real_bsl": "true"},
])
def test_incomplete_or_mislabelled_runtime_not_accepted(modules, changed):
    _, runner = modules
    with pytest.raises(RuntimeError):
        runner.reduce_phase(phase() | changed)


def test_child_environment_is_allowlisted(modules, monkeypatch):
    _, runner = modules
    for key in ("GITHUB_TOKEN", "AZURE_TOKEN", "CUSTOM_SECRET", "NODE_OPTIONS", "PYTHONPATH", "SSH_AUTH_SOCK"):
        monkeypatch.setenv(key, "not-in-child")
    monkeypatch.setenv("SYSTEMROOT", "C:\\Windows")
    result = runner.clean_env()
    assert result["SYSTEMROOT"] == "C:\\Windows"
    assert not any(value == "not-in-child" for value in result.values())


@pytest.mark.parametrize("url", ["http://github.com/a", "https://127.0.0.1/a", "https://user:pass@github.com/a", "https://example.org/a"])
def test_download_redirect_cannot_expand_fixed_origins(modules, url):
    inputs, _ = modules
    with pytest.raises(RuntimeError):
        inputs._HTTPSRedirect().redirect_request(urllib.request.Request("https://github.com/start"), None, 302, "", {}, url)


def test_receipt_write_does_not_overwrite_or_exceed_bound(modules, tmp_path):
    inputs, _ = modules
    path = tmp_path / "receipt.json"
    inputs.save(path, {"accepted": False})
    with pytest.raises(FileExistsError):
        inputs.save(path, {"accepted": True})
    with pytest.raises(RuntimeError):
        inputs.save(tmp_path / "large.json", {"large": "x" * (2 * 1024**2)})
    assert json.loads(path.read_text()) == {"accepted": False}


def test_binding_rejects_changed_head_before_package_execution(modules, tmp_path):
    inputs, _ = modules
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Guard", "-c", "user.email=guard@example.invalid",
                    "commit", "--allow-empty", "-qm", "Owned verifier guard fixture"], check=True)
    with pytest.raises(RuntimeError, match="Checkout source differs"):
        inputs.bind_checkout(tmp_path, "0" * 40, "1" * 40, tmp_path / "absent.vsix")


@pytest.mark.parametrize("tamper", [None, "source", "vsix"])
def test_exact_git_and_vsix_bytes_bound_before_runtime(modules, tmp_path, tamper):
    inputs, _ = modules
    root = tmp_path / "checkout"
    extension = root / "integrations/vscode-rentgen"
    extension.mkdir(parents=True)
    (extension / "build.py").write_text("def build_bytes():\n    return b'exact-vsix'\n")
    (extension / "package.json").write_text(json.dumps({"publisher": "rentgen", "name": "project-companion", "version": "0.1.20"}))
    product = root / "rentgen_core"
    product.mkdir()
    (product / "__init__.py").write_text("VALUE = 'bound source'\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Guard", "-c", "user.email=guard@example.invalid",
                    "commit", "-qm", "Owned verifier source fixture"], check=True)
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    vsix = tmp_path / "exact.vsix"
    vsix.write_bytes(b"exact-vsix")
    if tamper == "source":
        (product / "__init__.py").write_text("VALUE = 'changed after commit'\n")
    elif tamper == "vsix":
        vsix.write_bytes(b"other-vsix")
    if tamper:
        with pytest.raises(RuntimeError, match="Source bytes differ|VSIX does not reproduce"):
            inputs.bind_checkout(root, head, head, vsix)
    else:
        bound = inputs.bind_checkout(root, head, head, vsix)
        assert bound["source_commit"] == bound["trigger_head"] == head
        assert bound["companion_id"] == "rentgen.project-companion"
        assert len(bound["files"]) == 3


def test_real_runtime_never_skips_on_non_windows(modules, monkeypatch):
    _, runner = modules
    monkeypatch.setattr(runner.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="Real Windows"):
        runner.verify(None)
