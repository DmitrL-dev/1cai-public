"""Reject ambiguous modes before filesystem preparation or process launch."""
from types import SimpleNamespace
import json
import pytest
from scripts.verification import run_daily_semantic_editor_host as host
from scripts.verification.daily_frozen_inputs import file_record
from scripts.verification.run_daily_semantic_editor_host import run


def test_attempt_refuses_prior_before_any_input_read(tmp_path):
    output = tmp_path / "never-created"
    with pytest.raises(ValueError, match="Recovery requires"):
        run(SimpleNamespace(mode="attempt", prior=tmp_path / "prior.json", output=output))
    assert not output.exists()


def test_recovery_requires_prior_before_any_input_read(tmp_path):
    output = tmp_path / "never-created"
    with pytest.raises(ValueError, match="Recovery requires"):
        run(SimpleNamespace(mode="recovery", prior=None, output=output))
    assert not output.exists()


@pytest.fixture
def constructed_host(tmp_path, monkeypatch):
    """Only tiny constructed files; editor/process/kit operations are intercepted."""
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    files = {}
    for role in ("python", "scanner", "platform", "ibcmd", "engine", "test_module", "profile_spec", "vsix", "editor", "core_metadata"):
        item = inputs / role
        item.write_bytes(b"constructed, never executable")
        files[role] = file_record(item)
    metadata = inputs / "core_metadata"
    metadata.write_bytes(b"Name: rentgen-core\nVersion: 0.1.0.dev16\n")
    files["core_metadata"] = file_record(metadata)
    manifest = inputs / "frozen.json"
    manifest.write_text("{}", "utf-8")
    directories = {}
    for role in ("fixture", "diagnostics", "core", "editor_runtime"):
        folder = inputs / (role + "-directory")
        folder.mkdir()
        directories[role] = {"path": str(folder), "files": 0, "manifest_sha256": "a" * 64}
    before = {"manifest": file_record(manifest), "files": files, "directories": directories,
              "producer_claim": {"origin": "constructed"}, "source_ci_qualified_by_this_check": False}
    binding = {"core_version": "0.1.0.dev16", "companion_version": "0.1.16"}
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "profile.json").write_text(json.dumps({"python": files["python"]["path"], "core_version": binding["core_version"]}), "utf-8")
    (profile / "daily-scenario.json").write_text(json.dumps({"schema": 1, "frozen_inputs": before["manifest"], "companion_version": binding["companion_version"]}), "utf-8")
    ctx = {"checks": 0, "process_calls": 0, "before": before, "binding": binding, "recheck_error": None, "wait_error": None}

    def verify(_):
        ctx["checks"] += 1
        if ctx["checks"] > 1 and ctx["recheck_error"]:
            raise ctx["recheck_error"]
        return binding, json.loads(json.dumps(before))

    def extract(_, target):
        extension = target / "extension"
        (extension / "lib").mkdir(parents=True)
        (extension / "package.json").write_text(json.dumps({"version": "0.1.16", "publisher": "rentgen", "name": "project-companion"}), "utf-8")
        for name in ("tests-result.cjs", "core.cjs"):
            (extension / "lib" / name).write_bytes(b"constructed payload, never loaded")

    def popen(*_, **__):
        ctx["process_calls"] += 1
        return object()

    def wait(*_, **__):
        if ctx["recheck_error"]:
            (inputs / "platform").write_bytes(b"constructed changed bytes")
        if ctx["wait_error"]:
            raise ctx["wait_error"]
        return 0

    monkeypatch.setattr(host, "verify_frozen", verify)
    monkeypatch.setattr(host, "extract", extract)
    monkeypatch.setattr(host, "wait_owned", wait)
    monkeypatch.setattr(host.os, "environ", {})
    monkeypatch.setattr(host.subprocess, "Popen", popen)
    monkeypatch.setattr(host.subprocess, "STARTUPINFO", lambda: SimpleNamespace(dwFlags=0, wShowWindow=0), raising=False)
    monkeypatch.setattr(host.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    ctx["args"] = SimpleNamespace(mode="attempt", prior=None, frozen_inputs=manifest, profile=profile,
                                  output=tmp_path / "output", vsix=inputs / "vsix", editor=inputs / "editor")
    return ctx


def test_postverification_drift_retains_refusal_and_observed_bytes(constructed_host):
    ctx = constructed_host
    ctx["recheck_error"] = ValueError("INPUT_BINDING_MISMATCH: constructed drift")
    with pytest.raises(ValueError, match="constructed drift"):
        run(ctx["args"])
    receipt = json.loads((ctx["args"].output / "input-preservation.json").read_text("utf-8"))
    assert receipt["input_bytes_preserved"] is False
    assert receipt["after"] is None
    assert receipt["input_recheck_error"]["type"] == "ValueError"
    assert receipt["observed_inputs"]["files"]["platform"]["sha256"] != receipt["before"]["files"]["platform"]["sha256"]
    assert receipt["source_ci_qualified_by_this_check"] is False
    assert ctx["process_calls"] == 1


def test_host_wait_failure_is_retained_before_reraising(constructed_host):
    ctx = constructed_host
    ctx["wait_error"] = RuntimeError("constructed owned-wait refusal")
    with pytest.raises(RuntimeError, match="owned-wait"):
        run(ctx["args"])
    receipt = json.loads((ctx["args"].output / "input-preservation.json").read_text("utf-8"))
    assert receipt["execution_error"]["type"] == "RuntimeError"
    assert receipt["editor_exit_code"] is None
    assert receipt["input_bytes_preserved"] is True
    assert receipt["source_ci_qualified_by_this_check"] is False
    assert ctx["checks"] == 2


def test_separate_constructed_output_retains_byte_preservation_only(constructed_host):
    ctx = constructed_host
    assert run(ctx["args"]) == 0
    receipt = json.loads((ctx["args"].output / "input-preservation.json").read_text("utf-8"))
    assert receipt["input_bytes_preserved"] is True
    assert receipt["source_ci_qualified_by_this_check"] is False
    assert ctx["process_calls"] == 1


@pytest.mark.parametrize("root", ("profile", "diagnostics"))
def test_output_inside_protected_root_refuses_before_extract_or_process(constructed_host, root):
    ctx = constructed_host
    parent = ctx["args"].profile if root == "profile" else host.Path(ctx["before"]["directories"][root]["path"])
    ctx["args"].output = parent / "never-created"
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        run(ctx["args"])
    assert not ctx["args"].output.exists()
    assert ctx["process_calls"] == 0
