"""Portable verifier guards; never substitutes for real editor acceptance."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
from zipfile import ZipFile

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


def failed_phase():
    return {"schema": 1, "accepted": False, "phase": "restart", "process_id": 456,
            "runtime": "actual_windows_electron_extension_host", "model_calls": 0, "live_1c_apply": False,
            "fault_model": "durable_intent_commit_unobserved", "checkpoint": "restart.snapshot",
            "fresh_extension_host": True, "error": {"category": "assertion", "code": "ERR_ASSERTION",
                "operator": "deepStrictEqual", "actual": {"type": "null"}, "expected": {"type": "object"}}}


def test_failed_phase_retains_only_finite_diagnostics_and_cannot_pass(modules):
    _, runner = modules
    value = failed_phase() | {"app_name": "/private/source.bsl", "bsl": {"private_source": "never publish"}}
    reduced = runner.reduce_phase_failure(value, "restart")
    assert reduced == failed_phase()
    assert "private" not in json.dumps(reduced)
    with pytest.raises(RuntimeError, match="No positive real editor receipt"):
        runner.reduce_phase(value)


@pytest.mark.parametrize("defect", ["message", "stack", "checkpoint", "phase", "operator", "category",
                                       "object-body", "boolean-value", "integer-bool", "string-digest", "flag"])
def test_failed_phase_refuses_raw_or_unknown_diagnostic_data(modules, defect):
    _, runner = modules
    value = failed_phase()
    if defect in {"message", "stack"}:
        value["error"][defect] = "/private/source.bsl: confidential"
    elif defect == "checkpoint":
        value["checkpoint"] = "/private/source.bsl"
    elif defect == "phase":
        value["checkpoint"] = "first.metadata"
    elif defect in {"operator", "category"}:
        value["error"][defect] = "private exception string"
    elif defect == "object-body":
        value["error"]["actual"] = {"type": "object", "body": "private"}
    elif defect == "boolean-value":
        value["error"]["actual"] = {"type": "boolean", "value": 1}
    elif defect == "integer-bool":
        value["error"]["actual"] = {"type": "integer", "value": True}
    elif defect == "string-digest":
        value["error"]["actual"] = {"type": "string", "size_bytes": 5, "sha256": "private"}
    else:
        value["fresh_extension_host"] = 1
    with pytest.raises(RuntimeError):
        runner.reduce_phase_failure(value, "restart")


def test_restart_failure_preserves_validated_first_phase_and_primary_exception(modules, tmp_path, monkeypatch):
    _, runner = modules
    profile, evidence = tmp_path / "profile", tmp_path / "evidence"
    profile.mkdir(); evidence.mkdir()
    (profile / "phase-first.json").write_text(json.dumps(phase()))
    (profile / "phase-restart.json").write_text(json.dumps(failed_phase()))
    (evidence / "supervisor-first.json").write_text(json.dumps({"accepted": True, "cleanup_complete": True}))
    original = RuntimeError("private wrapper failure text")
    def command(*args, **kwargs):
        if args[3] == "host-restart":
            raise original
    monkeypatch.setattr(runner, "command", command)
    receipt = {"accepted": False}
    acceptance = runner.AcceptanceReceipt(evidence / "acceptance.json")
    runner.phase_attempt([], output=tmp_path, evidence=evidence, profile=profile, phase="first", receipt=receipt,
                         acceptance=acceptance)
    saved = json.loads((evidence / "acceptance.json").read_text())
    assert saved["accepted"] is False and saved["phases"]["first"]["owned_process_cleanup"] is True
    with pytest.raises(RuntimeError) as caught:
        try:
            runner.phase_attempt([], output=tmp_path, evidence=evidence, profile=profile, phase="restart", receipt=receipt,
                                 acceptance=acceptance)
        finally:
            runner.finish_receipt(acceptance, receipt, sys.exc_info()[1])
    assert caught.value is original
    assert receipt["phases"] == saved["phases"]
    assert receipt["phase_failures"]["restart"] == failed_phase()
    assert receipt["accepted"] is False and "private" not in json.dumps(receipt)
    assert json.loads((evidence / "acceptance.json").read_text()) == receipt


def test_both_phases_and_final_acceptance_update_the_same_real_receipt(modules, tmp_path, monkeypatch):
    _, runner = modules
    for which in ("first", "restart"):
        (tmp_path / ("phase-" + which + ".json")).write_text(json.dumps(phase(which)))
        (tmp_path / ("supervisor-" + which + ".json")).write_text(json.dumps({"accepted": True, "cleanup_complete": True}))
    monkeypatch.setattr(runner, "command", lambda *args, **kwargs: None)
    receipt = {"accepted": False}
    acceptance = runner.AcceptanceReceipt(tmp_path / "acceptance.json")
    for which in ("first", "restart"):
        runner.phase_attempt([], output=tmp_path, evidence=tmp_path, profile=tmp_path, phase=which,
                             receipt=receipt, acceptance=acceptance)
        assert json.loads(acceptance.path.read_text()) == receipt and receipt["accepted"] is False
    receipt["accepted"] = True
    runner.finish_receipt(acceptance, receipt, None)
    assert json.loads(acceptance.path.read_text()) == receipt
    assert set(receipt["phases"]) == {"first", "restart"}


def test_normal_quit_exit_zero_cannot_accept_a_failed_phase_or_drop_its_diagnostics(modules, tmp_path, monkeypatch):
    _, runner = modules
    (tmp_path / "phase-restart.json").write_text(json.dumps(failed_phase()))
    (tmp_path / "supervisor-restart.json").write_text(json.dumps({"accepted": True, "cleanup_complete": True}))
    monkeypatch.setattr(runner, "command", lambda *args, **kwargs: None)
    receipt = {"accepted": False}
    acceptance = runner.AcceptanceReceipt(tmp_path / "acceptance.json")
    with pytest.raises(RuntimeError, match="No positive real editor receipt"):
        try:
            runner.phase_attempt([], output=tmp_path, evidence=tmp_path, profile=tmp_path,
                                 phase="restart", receipt=receipt, acceptance=acceptance)
        finally:
            runner.finish_receipt(acceptance, receipt, sys.exc_info()[1])
    assert json.loads(acceptance.path.read_text()) == receipt
    assert receipt["phase_failures"]["restart"] == failed_phase()
    assert receipt["phases"] == {} and receipt["accepted"] is False


@pytest.mark.parametrize("which", ["first", "restart"])
def test_editor_window_uses_persistent_workspace_mode_and_startup_harness(modules, tmp_path, which):
    inputs, _ = modules
    supervisor = inputs.load(HERE / "supervisor.py", "editor_workbench_supervisor_controls")
    launch = {"editor": str(tmp_path / "VSCodium.exe"), "harness": str(HERE), "vsix": str(tmp_path / "target.vsix")}
    command = supervisor.editor_command(launch, tmp_path, which)
    assert not any(arg.startswith("--extensionTestsPath") for arg in command)
    assert command[command.index("--user-data-dir") + 1] == str(tmp_path / "editor-user")
    assert command[-1] == str(tmp_path / "profile/workspace")
    assert "--extensionDevelopmentPath=" + str(HERE) in command
    package = json.loads((HERE / "package.json").read_text())
    assert package["main"] == "host.cjs" and package["activationEvents"] == ["onStartupFinished"]


def test_editor_install_still_uses_exact_vsix_and_unknown_launch_mode_refuses(modules, tmp_path):
    inputs, _ = modules
    supervisor = inputs.load(HERE / "supervisor.py", "editor_workbench_install_controls")
    launch = {"editor": str(tmp_path / "VSCodium.exe"), "harness": str(HERE), "vsix": str(tmp_path / "target.vsix")}
    command = supervisor.editor_command(launch, tmp_path, "install")
    assert command[1] == str(tmp_path / "resources/app/out/cli.js")
    assert command[-2:] == ["--install-extension", launch["vsix"]]
    assert not any(arg.startswith("--extensionDevelopmentPath") for arg in command)
    with pytest.raises(ValueError, match="Unknown editor mode"):
        supervisor.editor_command(launch, tmp_path, "unknown")


@pytest.mark.parametrize("primary_failure", [False, True])
def test_final_receipt_io_failure_refuses_success_and_preserves_primary_error(modules, tmp_path, monkeypatch, primary_failure):
    _, runner = modules
    acceptance = runner.AcceptanceReceipt(tmp_path / "acceptance.json")
    receipt = {"accepted": False}
    acceptance.save(receipt)
    io_error, primary = OSError("receipt IO failed"), RuntimeError("original process failure")
    monkeypatch.setattr(runner.os, "fsync", lambda fd: (_ for _ in ()).throw(io_error))
    with pytest.raises(RuntimeError if primary_failure else OSError) as caught:
        try:
            if primary_failure:
                raise primary
        finally:
            runner.finish_receipt(acceptance, receipt, sys.exc_info()[1])
    assert caught.value is (primary if primary_failure else io_error)


def test_acceptance_writer_never_overwrites_preexisting_or_replaced_file(modules, tmp_path):
    _, runner = modules
    path = tmp_path / "acceptance.json"
    path.write_bytes(b"preexisting")
    with pytest.raises(FileExistsError):
        runner.AcceptanceReceipt(path).save({"accepted": False})
    assert path.read_bytes() == b"preexisting"
    path.unlink()
    acceptance = runner.AcceptanceReceipt(path)
    acceptance.save({"accepted": False})
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"foreign replacement")
    os.replace(replacement, path)
    with pytest.raises(RuntimeError, match="identity changed"):
        acceptance.save({"accepted": True})
    assert path.read_bytes() == b"foreign replacement"


def test_acceptance_writer_refuses_hardlink_alias_and_oversized_update(modules, tmp_path):
    _, runner = modules
    acceptance = runner.AcceptanceReceipt(tmp_path / "acceptance.json")
    acceptance.save({"accepted": False})
    original = acceptance.path.read_bytes()
    with pytest.raises(RuntimeError, match="exceeds 2 MiB"):
        acceptance.save({"accepted": False, "data": "x" * (2 * 1024**2)})
    assert acceptance.path.read_bytes() == original
    os.link(acceptance.path, tmp_path / "alias")
    with pytest.raises(RuntimeError, match="Unsafe acceptance receipt"):
        acceptance.save({"accepted": True})
    assert acceptance.path.read_bytes() == original


@pytest.mark.parametrize("invalid", [False, True])
def test_missing_or_unbounded_failed_phase_still_preserves_process_failure(modules, tmp_path, monkeypatch, invalid):
    _, runner = modules
    if invalid:
        (tmp_path / "phase-restart.json").write_bytes(b"x" * (1024**2 + 1))
    original = RuntimeError("private process detail")
    monkeypatch.setattr(runner, "command", lambda *args, **kwargs: (_ for _ in ()).throw(original))
    receipt = {"accepted": False}
    with pytest.raises(RuntimeError) as caught:
        runner.phase_attempt([], output=tmp_path, evidence=tmp_path, profile=tmp_path, phase="restart", receipt=receipt,
                             acceptance=runner.AcceptanceReceipt(tmp_path / "acceptance.json"))
    assert caught.value is original and receipt["accepted"] is False
    assert receipt["phase_failures"]["restart"]["diagnostic"] == "failed-phase-receipt-unavailable-or-invalid"
    assert "private" not in json.dumps(receipt)


def test_phase_file_duplicate_json_fields_are_not_admitted(modules, tmp_path):
    _, runner = modules
    (tmp_path / "phase-restart.json").write_bytes(b'{"accepted":false,"accepted":true}')
    with pytest.raises(RuntimeError, match="Duplicate editor receipt field"):
        runner.read_phase_file(tmp_path, "restart")


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
    # Match the repository's exact-byte policy regardless of inherited Git EOL settings.
    (root / ".gitattributes").write_bytes(b"* -text\n")
    (extension / "build.py").write_bytes(b"def build_bytes():\n    return b'exact-vsix'\n")
    (extension / "package.json").write_bytes(json.dumps({"publisher": "rentgen", "name": "project-companion", "version": "0.1.20"}).encode("utf-8"))
    product = root / "rentgen_core"
    product.mkdir()
    (product / "__init__.py").write_bytes(b"VALUE = 'bound source'\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Guard", "-c", "user.email=guard@example.invalid",
                    "commit", "-qm", "Owned verifier source fixture"], check=True)
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    vsix = tmp_path / "exact.vsix"
    vsix.write_bytes(b"exact-vsix")
    if tamper == "source":
        (product / "__init__.py").write_bytes(b"VALUE = 'changed after commit'\n")
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


@pytest.fixture
def installed_companion(tmp_path):
    """Synthetic pinned-installer layout; does not launch or qualify an editor."""
    package = {"name": "project-companion", "main": "extension.cjs", "activationEvents": ["onCommand:rentgen.open"]}
    payload = {"package.json": json.dumps(package).encode("utf-8"), "extension.cjs": b"module.exports = {};\n"}
    manifest = b'<PackageManifest Version="2.0.0">bound manifest</PackageManifest>\r\n'
    vsix = tmp_path / "companion.vsix"
    with ZipFile(vsix, "w") as archive:
        archive.writestr("extension.vsixmanifest", manifest)
        archive.writestr("[Content_Types].xml", b"<Types/>")
        for name, raw in payload.items():
            archive.writestr("extension/" + name, raw)
    extension = tmp_path / "installed"
    extension.mkdir()
    for name, raw in payload.items():
        (extension / name).write_bytes(raw)
    (extension / ".vsixmanifest").write_bytes(manifest)
    package["__metadata"] = {"installedTimestamp": 1, "targetPlatform": "undefined"}
    (extension / "package.json").write_bytes(json.dumps(package, indent=2).encode("utf-8"))
    return extension, vsix, manifest


def test_installed_companion_binds_generated_manifest_and_limited_package_metadata(modules, installed_companion):
    _, runner = modules
    extension, vsix, manifest = installed_companion
    diagnostic = {}
    inventory = runner.companion_files(extension, vsix, diagnostic)
    assert set(inventory) == {"package.json", "extension.cjs", ".vsixmanifest"}
    assert inventory[".vsixmanifest"] == {"sha256": hashlib.sha256(manifest).hexdigest(), "size_bytes": len(manifest)}
    assert diagnostic["accepted"] is True
    assert diagnostic["missing"]["count"] == diagnostic["unexpected"]["count"] == 0
    assert [item["relative_path"] for item in diagnostic["content_changed"]["entries"]] == ["package.json"]
    assert diagnostic["content_changed"]["entries"][0]["allowed_package_json_rewrite"] is True
    assert "installedTimestamp" not in json.dumps(diagnostic)


@pytest.mark.parametrize("tamper,category,name,message", [
    ("payload", "content_changed", "extension.cjs", "Installed extension bytes differ"),
    ("manifest", "content_changed", ".vsixmanifest", "Installed extension bytes differ"),
    ("extra", "unexpected", "unexpected.json", "Installed Companion file inventory differs"),
    ("missing-payload", "missing", "extension.cjs", "Installed Companion file inventory differs"),
    ("missing-manifest", "missing", ".vsixmanifest", "Installed Companion file inventory differs"),
    ("package", "content_changed", "package.json", "Installed extension manifest differs"),
    ("package-extra-setting", "content_changed", "package.json", "Installed extension manifest differs"),
    ("package-invalid", "content_changed", "package.json", "Installed extension manifest differs"),
], ids=["payload-bytes", "generated-manifest-bytes", "unknown-extra", "missing-payload", "missing-generated-manifest", "package-configuration", "package-extra-setting", "package-invalid-json"])
def test_installed_companion_tamper_and_unknown_inventory_refuse_with_reduced_delta(
        modules, installed_companion, tamper, category, name, message):
    _, runner = modules
    extension, vsix, _ = installed_companion
    private_body = b"private fixture body must not appear in reduced evidence"
    if tamper.startswith("missing-"):
        (extension / name).unlink()
    elif tamper in {"package", "package-extra-setting"}:
        package = json.loads((extension / name).read_bytes())
        package["main" if tamper == "package" else "unexpectedSetting"] = "changed.cjs"
        (extension / name).write_bytes(json.dumps(package).encode("utf-8"))
    else:
        (extension / name).write_bytes(private_body)
    diagnostic = {}
    with pytest.raises(RuntimeError, match=message):
        runner.companion_files(extension, vsix, diagnostic)
    assert diagnostic["accepted"] is False
    entries = {item["relative_path"]: item for item in diagnostic[category]["entries"]}
    assert name in entries
    if category != "missing":
        assert entries[name]["actual"]["sha256"] == hashlib.sha256((extension / name).read_bytes()).hexdigest()
    if category != "unexpected":
        assert entries[name]["expected"]["sha256"]
    text = json.dumps(diagnostic)
    assert private_body.decode() not in text and str(extension) not in text


def test_vsix_payload_cannot_shadow_generated_manifest(modules, installed_companion):
    _, runner = modules
    extension, vsix, _ = installed_companion
    with ZipFile(vsix, "a") as archive:
        archive.writestr("extension/.vsixmanifest", b"shadow")
    with pytest.raises(RuntimeError, match="VSIX payload shadows installed manifest"):
        runner.companion_files(extension, vsix)


def test_companion_inventory_diagnostic_is_bounded_and_omits_unsafe_names(modules):
    _, runner = modules
    record = {"sha256": "0" * 64, "size_bytes": 1}
    actual = {f"file-{number:03}.cjs": record for number in range(100)}
    unsafe = "/private/path/" + "x" * 300
    actual[unsafe] = record
    diagnostic = runner.companion_delta(actual, {}, set(), set())
    assert diagnostic["accepted"] is False
    assert diagnostic["unexpected"]["count"] == 101
    assert diagnostic["unexpected"]["truncated"] is True
    assert len(diagnostic["unexpected"]["entries"]) == runner.MAX_COMPANION_DELTA_ENTRIES
    redacted = diagnostic["unexpected"]["entries"][0]
    assert redacted["relative_path_omitted"] is True
    assert redacted["relative_path_sha256"] == hashlib.sha256(unsafe.encode()).hexdigest()
    assert unsafe not in json.dumps(diagnostic)
    assert len(json.dumps(diagnostic).encode()) < 32 * 1024


def test_real_runtime_never_skips_on_non_windows(modules, monkeypatch):
    _, runner = modules
    monkeypatch.setattr(runner.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="Real Windows"):
        runner.verify(None)
