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


def set_daily_context(ctx, profile_value, scenario_value):
    for name, value in (("profile.json", profile_value), ("daily-scenario.json", scenario_value)):
        path = ctx["args"].profile / name
        payload = json.loads(path.read_text("utf-8"))
        payload["context_tokens"] = value
        path.write_text(json.dumps(payload), "utf-8")


@pytest.mark.parametrize("context_tokens", (None, 8192, 16384, 32768))
def test_daily_context_is_bound_with_profile_bytes(constructed_host, context_tokens):
    ctx = constructed_host
    if context_tokens is not None:
        set_daily_context(ctx, context_tokens, context_tokens)
    expected = 32768 if context_tokens is None else context_tokens
    assert run(ctx["args"]) == 0
    inputs = json.loads((ctx["args"].output / "inputs.json").read_text("utf-8"))
    receipt = json.loads((ctx["args"].output / "input-preservation.json").read_text("utf-8"))
    assert inputs["context_tokens"] == receipt["context_tokens"] == expected
    assert inputs["daily_profile_files"] == receipt["daily_profile_before"] == receipt["daily_profile_after"]
    assert inputs["daily_profile_files"] == {
        "profile": file_record(ctx["args"].profile / "profile.json"),
        "scenario": file_record(ctx["args"].profile / "daily-scenario.json"),
    }


@pytest.mark.parametrize("field", ("profile", "scenario"))
@pytest.mark.parametrize("bad_value", (None, True, "8192", 8192.0, 4096))
def test_daily_context_invalid_refuses_before_output_or_editor(constructed_host, field, bad_value):
    ctx = constructed_host
    set_daily_context(ctx, bad_value if field == "profile" else 8192,
                      bad_value if field == "scenario" else 8192)
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        run(ctx["args"])
    assert not ctx["args"].output.exists()
    assert ctx["process_calls"] == 0


def test_daily_context_mismatch_refuses_before_output_or_editor(constructed_host):
    ctx = constructed_host
    set_daily_context(ctx, 8192, 16384)
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        run(ctx["args"])
    assert not ctx["args"].output.exists()
    assert ctx["process_calls"] == 0


@pytest.mark.parametrize("name,limit", (("profile.json", 65536), ("daily-scenario.json", 2097152)))
def test_daily_profile_size_limit_refuses_before_unbounded_read(
    constructed_host, monkeypatch, name, limit
):
    ctx = constructed_host
    target = ctx["args"].profile / name
    record, read_bytes = host.file_record, host.Path.read_bytes

    def pinned(path):
        pin = record(path)
        return {**pin, "size": limit + 1} if path == target else pin

    def read(path):
        if path == target:
            raise AssertionError("Oversized profile must not reach read_bytes")
        return read_bytes(path)

    monkeypatch.setattr(host, "file_record", pinned)
    monkeypatch.setattr(host.Path, "read_bytes", read)
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        run(ctx["args"])
    assert not ctx["args"].output.exists()
    assert ctx["process_calls"] == 0


@pytest.mark.parametrize("field", ("profile.json", "daily-scenario.json"))
@pytest.mark.parametrize("wait_failed", (False, True))
def test_daily_profile_drift_retained_even_when_editor_wait_fails(
    constructed_host, monkeypatch, field, wait_failed
):
    ctx = constructed_host
    set_daily_context(ctx, 16384, 16384)
    target = ctx["args"].profile / field
    original = file_record(target)

    def wait(*_, **__):
        # Same context, changed bytes: all generated profile/scenario bytes are bound.
        with target.open("a", encoding="utf-8") as stream:
            stream.write("\n")
        if wait_failed:
            raise RuntimeError("constructed owned-wait refusal")
        return 0

    monkeypatch.setattr(host, "wait_owned", wait)
    with pytest.raises((ValueError, RuntimeError)):
        run(ctx["args"])
    receipt = json.loads((ctx["args"].output / "input-preservation.json").read_text("utf-8"))
    role = "profile" if field == "profile.json" else "scenario"
    assert receipt["input_bytes_preserved"] is False
    assert receipt["daily_profile_before"][role] == original
    assert receipt["daily_profile_after"][role] == file_record(target)
    if wait_failed:
        assert receipt["execution_error"]["type"] == "RuntimeError"
    assert ctx["process_calls"] == 1
