"""Safeguards of the native verifier; these tests never accept a SCM lifecycle."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/verification"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_new_workspace_rejects_existing_or_foreign_directory(tmp_path):
    api = load("verify_service_scm_delivery")
    child = tmp_path / ("rg-scm-" + "a" * 12)
    assert api.validate_output(child, tmp_path) == child
    child.mkdir()
    with pytest.raises(RuntimeError, match="new"):
        api.validate_output(child, tmp_path)
    with pytest.raises(RuntimeError, match="direct child"):
        api.validate_output(tmp_path.parent / child.name, tmp_path)


def test_provenance_requires_same_commit_and_accepted_archive(tmp_path):
    api = load("verify_service_scm_delivery")
    kit = tmp_path / "kit.zip"
    kit.write_bytes(b"owned test bytes")
    receipt = {"source_commit": "a" * 40, "builds_identical": True,
               "kit": {"archive_sha256": api.sha(kit)},
               "offline_install": {"accepted": True, "archive_sha256": api.sha(kit)}}
    assert api.validate_provenance(kit, receipt, "a" * 40) == api.sha(kit)
    with pytest.raises(RuntimeError, match="commit"):
        api.validate_provenance(kit, receipt, "b" * 40)
    receipt["offline_install"]["accepted"] = False
    with pytest.raises(RuntimeError, match="offline"):
        api.validate_provenance(kit, receipt, "a" * 40)
    receipt["offline_install"]["accepted"] = True
    kit.write_bytes(b"changed bytes")
    with pytest.raises(RuntimeError, match="hash"):
        api.validate_provenance(kit, receipt, "a" * 40)


def test_acl_restore_rejects_changed_baseline_and_new_service_grants(tmp_path):
    api = load("scm_acceptance_worker")
    before = {tmp_path: "D:AI(A;OICI;FA;;;SY)"}
    with pytest.raises(RuntimeError, match="restored exactly"):
        api.verify_acl_restoration(before, {tmp_path: "D:"})
    for sid in ("LS", "S-1-5-19"):
        with pytest.raises(RuntimeError, match="ACE remains"):
            api.verify_acl_restoration(before, {**before, tmp_path / "new": f"D:(A;;FR;;;{sid})"})
    assert api.verify_acl_restoration(before, before)["original_dacls_equal"]


def test_acl_backup_rejects_escaped_and_duplicate_paths(tmp_path):
    api = load("scm_acceptance_worker")
    root = tmp_path / "fixture"
    root.mkdir()
    path = tmp_path / "saved.acl"
    for lines in [("../foreign", "D:AI"), (root.name, "D:AI", root.name, "D:AI")]:
        path.write_text("\n".join(lines) + "\n", "utf-16")
        with pytest.raises(RuntimeError, match="escapes or duplicates"):
            api.acl_entries(path, root)


def test_exercise_deadline_does_not_consume_cleanup_reserve(monkeypatch):
    api = load("scm_acceptance_worker")
    now = [100.0]
    monkeypatch.setattr(api.time, "monotonic", lambda: now[0])
    budget = api.Budget(30, 20)
    now[0] = 131.0
    with pytest.raises(RuntimeError, match="budget"):
        budget.remaining()
    budget.begin_cleanup()
    assert budget.remaining() == 19.0
    now[0] = 151.0
    with pytest.raises(RuntimeError, match="budget"):
        budget.remaining()


def test_unknown_existing_service_is_never_controlled_or_has_acl_restored(tmp_path, monkeypatch):
    api = load("scm_acceptance_worker")
    api.ROOT, api.RUNTIME, api.NAME = tmp_path / "fixture", tmp_path / "runtime", "Rentgen.CI.test"
    config = tmp_path / "service.json"
    config.write_bytes(b"{}")
    spec = Mock()
    context = ({"config": str(config), "config_sha256": api.sha(config)}, {}, spec,
               Mock(), Mock(), {}, {})
    worker = api.Acceptance(context, tmp_path)
    worker.native.query.return_value = {"exists": True, "name": api.NAME}
    worker.installer = Mock()
    worker.icacls = Mock()
    monkeypatch.setattr(api, "owned_scanner_pids", lambda: [])
    errors = worker.cleanup()
    assert "remaining_service" in {e["stage"] for e in errors}
    assert not worker.installer.mock_calls
    assert not worker.icacls.mock_calls


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows read-only evidence")
def test_native_helper_reads_current_process_and_absent_service():
    from uuid import uuid4
    from rentgen_core.local_identity import current_windows_principal
    api = load("scm_native_evidence")
    native = api.NativeEvidence()
    process = native.process(os.getpid())
    assert process["pid"] == os.getpid()
    # Venv entry point and actual image can differ; this is a token/read-only test.
    assert Path(process["image"]).name.casefold() == "python.exe"
    assert process["token_user_sid"] == current_windows_principal().id.removeprefix("windows-sid:")
    assert native.query("Rentgen.CI.Absent." + uuid4().hex)["exists"] is False
    assert all({"name", "enabled"} == set(p) for p in native.privileges())


def test_workflow_keeps_scm_separate_and_retains_failure_evidence():
    import yaml
    document = yaml.safe_load((SCRIPTS.parents[1] / ".github/workflows/core-ci.yml").read_text("utf-8"))
    jobs = document["jobs"]
    assert jobs["native-scm"]["needs"] == "windows"
    assert jobs["windows"]["steps"][-1]["with"]["name"] == "verified-core-development"
    native = jobs["native-scm"]["steps"]
    download = next(s for s in native if "actions/download-artifact@" in s.get("uses", ""))
    assert download["with"] == {"name": "verified-core-development", "path": "output/scm-input"}
    assert "always()" in native[-1]["if"]
    assert native[-1]["with"]["name"] == "native-scm-evidence"


@pytest.mark.parametrize("name", ["verify_service_scm_delivery", "scm_acceptance_worker"])
@pytest.mark.parametrize("flag", ["-O", "-OO"])
def test_optimized_interpreter_refuses_before_loading_product(name, flag, tmp_path):
    result = subprocess.run([sys.executable, flag, "-I", str(SCRIPTS / (name + ".py")),
                             "--workdir", str(tmp_path)], capture_output=True, timeout=10)
    assert result.returncode != 0
    assert b"do not use Python -O" in result.stderr
    assert not list(tmp_path.iterdir())
