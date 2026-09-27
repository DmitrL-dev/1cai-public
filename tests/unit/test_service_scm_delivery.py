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
    config.write_bytes(b"foreign service config")
    monkeypatch.setattr(api, "owned_scanner_pids", lambda: [])
    errors = worker.cleanup()
    assert config.read_bytes() == b"foreign service config"
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



def test_acl_restore_records_only_auto_inherited_control_conversion(tmp_path):
    api = load("scm_acceptance_worker")
    acl = "(A;;FA;;;BA)(A;OICIID;FR;;;BU)"
    result = api.verify_acl_restoration({tmp_path: "D:" + acl}, {tmp_path: "D:AI" + acl})
    assert result["original_dacls_equal"]
    assert not result["original_descriptor_strings_equal"]
    assert result["auto_inherited_control_changes"] == 1


@pytest.mark.parametrize("changed", [
    "D:P(A;;FA;;;BA)(A;OICIID;FR;;;BU)",
    "D:AR(A;;FA;;;BA)(A;OICIID;FR;;;BU)",
    "D:(A;;FR;;;BA)(A;OICIID;FR;;;BU)",
    "D:(A;;FA;;;SY)(A;OICIID;FR;;;BU)",
    "D:(A;;FA;;;BA)(A;OICI;FR;;;BU)",
    "D:(A;OICIID;FR;;;BU)(A;;FA;;;BA)",
])
def test_acl_restore_preserves_protection_request_and_exact_aces(tmp_path, changed):
    api = load("scm_acceptance_worker")
    before = {tmp_path: "D:(A;;FA;;;BA)(A;OICIID;FR;;;BU)"}
    with pytest.raises(RuntimeError, match="restored exactly"):
        api.verify_acl_restoration(before, {tmp_path: changed})


@pytest.mark.parametrize("sddl", ["D:AIAI", "D:ZZ", "D:AI(A;;FA;;;BA)junk"])
def test_acl_restore_rejects_malformed_descriptor_even_if_equal(tmp_path, sddl):
    api = load("scm_acceptance_worker")
    with pytest.raises(RuntimeError, match="Invalid DACL"):
        api.verify_acl_restoration({tmp_path: sddl}, {tmp_path: sddl})


def test_new_acl_cleanup_frontiers_cover_only_new_owned_subtrees(tmp_path):
    api = load("scm_acceptance_worker")
    original = {tmp_path: "D:", tmp_path / "old": "D:"}
    after = {**original, tmp_path / "new": "D:",
             tmp_path / "new/child": "D:(A;;FA;;;LS)",
             tmp_path / "old/cache": "D:(A;;FA;;;S-1-5-19)"}
    assert set(api.new_acl_cleanup_frontiers(tmp_path, original, after)) == {
        tmp_path / "new", tmp_path / "old/cache"}
    assert api.new_acl_cleanup_frontiers(tmp_path, original, original) == []
    with pytest.raises(RuntimeError, match="original entry"):
        api.new_acl_cleanup_frontiers(tmp_path,
            {tmp_path: "D:", tmp_path / "new/child": "D:"},
            {**after, tmp_path / "new": "D:(A;;FA;;;LS)"})
    with pytest.raises(RuntimeError, match="owned root"):
        api.new_acl_cleanup_frontiers(tmp_path, original,
            {**after, tmp_path.parent / "foreign": "D:(A;;FA;;;LS)"})


def test_temporary_acl_policy_rejects_inherited_writes_and_unexpected_principals(tmp_path):
    api = load("scm_acceptance_worker")
    data = tmp_path / "data"
    data.mkdir()
    prefix = "D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)"
    read = prefix + "(A;OICI;0x1200a9;;;LS)"
    modify = prefix + "(A;OICI;0x1301bf;;;LS)"
    assert api.verify_temporary_acls(tmp_path, {tmp_path: read, data: modify}, data)["entries"] == 2
    for altered in (read.replace("D:P", "D:"), read + "(A;CI;DC;;;BU)",
                    read.replace("0x1200a9", "FA"), read + "(A;OICIIO;GA;;;CO)",
                    read.replace("OICI;0x1200a9", "OICIIO;0x1200a9")):
        with pytest.raises(RuntimeError, match="Temporary ACL"):
            api.verify_temporary_acls(tmp_path, {tmp_path: altered}, None)
    with pytest.raises(RuntimeError, match="Temporary ACL"):
        api.verify_temporary_acls(tmp_path, {tmp_path: read, data: read}, data)


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows file owner query")
def test_native_file_owner_matches_windows_acl_and_missing_file_fails(tmp_path):
    api = load("scm_native_evidence")
    native = api.NativeEvidence()
    target = tmp_path / "owned.txt"
    target.write_bytes(b"owner evidence")
    # The path is passed as an environment value, never inserted into shell code.
    env = {key: os.environ[key] for key in ("SystemRoot", "TEMP", "TMP", "PATH") if key in os.environ}
    env["RENTGEN_TEST_OWNER_PATH"] = str(target)
    result = subprocess.run(["pwsh.exe", "-NoProfile", "-NonInteractive", "-Command",
        "(Get-Acl -LiteralPath $env:RENTGEN_TEST_OWNER_PATH).GetOwner([System.Security.Principal.SecurityIdentifier]).Value"],
        env=env, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert native.owner(target) == result.stdout.decode().strip()
    with pytest.raises(api.NativeEvidenceError):
        native.owner(tmp_path / "missing")


def test_temporary_policy_materializes_file_permissions(tmp_path):
    api = load("scm_acceptance_worker")
    root = tmp_path / "owned"; root.mkdir()
    data = root / "data"; data.mkdir()
    executable = root / "python.exe"; executable.write_bytes(b"runtime")
    database = data / "state.db"; database.write_bytes(b"database")
    baseline = {p: "D:" for p in (root, data, executable, database)}
    policy = api.temporary_acl_policy(root, baseline, data)
    assert set(policy) == set(baseline)
    assert policy[executable] == "D:P(A;;FA;;;BA)(A;;FA;;;SY)(A;;0x1200a9;;;LS)"
    assert policy[database] == "D:P(A;;FA;;;BA)(A;;FA;;;SY)(A;;0x1301bf;;;LS)"
    assert policy[root] == "D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;0x1200a9;;;LS)"
    assert policy[data] == policy[root].replace("0x1200a9", "0x1301bf")
    assert api.verify_temporary_acls(root, policy, data)["entries"] == 4
    with pytest.raises(RuntimeError, match="owned root"):
        api.temporary_acl_policy(root, {**baseline, tmp_path: "D:"}, data)
    with pytest.raises(RuntimeError, match="data"):
        api.temporary_acl_policy(root, baseline, tmp_path)


def test_second_ci_empty_file_and_duplicate_directory_acls_are_rejected(tmp_path):
    api = load("scm_acceptance_worker")
    for sddl in ("D:PAI", "D:PAI(A;;FA;;;BA)(A;OICI;0x1200a9;;;LS)(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"):
        with pytest.raises(RuntimeError, match="Temporary ACL"):
            api.verify_temporary_acls(tmp_path, {tmp_path: sddl}, None)


def test_cleanup_structural_inventory_does_not_read_locked_file_bytes(tmp_path, monkeypatch):
    api = load("scm_acceptance_worker")
    api.ROOT = tmp_path
    path = tmp_path / "locked.txt"; path.write_bytes(b"locked")
    monkeypatch.setattr(api, "sha", Mock(side_effect=PermissionError("file data inaccessible")))
    result = api.inventory(tmp_path, hash_files=False)
    assert result["locked.txt"] == {"directory": False, "bytes": 6}
    api.sha.assert_not_called()


@pytest.mark.parametrize("config_denied", [False, True])
def test_cleanup_restores_acl_before_attempting_config_write(tmp_path, monkeypatch, config_denied):
    api = load("scm_acceptance_worker")
    root = tmp_path / "fixture"; root.mkdir()
    output = tmp_path / "evidence"; output.mkdir()
    api.ROOT, api.RUNTIME, api.NAME = root, tmp_path / "runtime", "Rentgen.CI.test"
    config = root / "service.json"; config.write_bytes(b"{}")
    context = ({"config": str(config), "config_sha256": api.sha(config)}, {}, Mock(), Mock(), Mock(), {}, {})
    worker = api.Acceptance(context, output)
    worker.native.query.return_value = {"exists": False}
    worker.native.owner.return_value = "S-1-5-21-123"
    worker.backup_acl = Mock()
    saved = output / "fixture.acl"
    raw = ("fixture\nD:\nfixture\\service.json\nD:\n").encode("utf-16-le")
    saved.write_bytes(raw)
    owners = output / "fixture-owners.json"
    owners.write_text(json.dumps({".": "S-1-5-21-123", "service.json": "S-1-5-21-123"}), "utf-8")
    worker.acl_backups = [(root, saved, api.sha(saved))]
    worker.owner_backups = {root: (owners, api.sha(owners))}
    calls = []
    original_write = Path.write_bytes
    def write(path, value):
        if path == config:
            calls.append("config")
            if config_denied:
                raise PermissionError("test denied config")
        return original_write(path, value)
    def icacls(args, label):
        calls.append(label)
        if "/save" in args:
            args[args.index("/save") + 1].write_bytes(raw)
    worker.icacls = icacls
    monkeypatch.setattr(api, "owned_scanner_pids", lambda: [])
    monkeypatch.setattr(Path, "write_bytes", write)
    errors = worker.cleanup()
    assert "fixture-restore" in calls
    assert calls.index("fixture-restore") < calls.index("config")
    assert calls.index("fixture-verify") < calls.index("config")
    assert errors == ([{"stage": "config", "type": "PermissionError"}] if config_denied else [])


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows DACL round trip in an owned temporary tree")
def test_native_explicit_policy_roundtrip_covers_files_and_directories(tmp_path):
    native = load("scm_native_evidence").NativeEvidence()
    if not any(p["name"] == "SeRestorePrivilege" for p in native.privileges()):
        pytest.skip("Actual icacls /restore requires SeRestorePrivilege; exercised on the elevated Windows CI runner")
    api = load("scm_acceptance_worker")
    root = tmp_path / "owned tree"; root.mkdir()
    data = root / "data"; data.mkdir()
    executable = root / "python.exe"; executable.write_bytes(b"runtime")
    database = data / "state.db"; database.write_bytes(b"database")
    baseline = tmp_path / "baseline.acl"
    policy_path = tmp_path / "policy.acl"
    observed_path = tmp_path / "observed.acl"
    restored_path = tmp_path / "restored.acl"
    def icacls(*args):
        p = subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32/icacls.exe"), *map(str, args)],
                           capture_output=True, timeout=20)
        assert p.returncode == 0, (p.returncode, p.stdout.decode(errors="replace"))
    icacls(root, "/save", baseline, "/T", "/Q")
    before = api.acl_entries(baseline, root)
    policy = api.temporary_acl_policy(root, before, data)
    api.write_acl_policy(policy_path, root, policy)
    try:
        icacls(root.parent, "/restore", policy_path, "/Q")
        icacls(root, "/save", observed_path, "/T", "/Q")
        observed = api.acl_entries(observed_path, root)
        assert set(observed) == set(before)
        assert api.verify_temporary_acls(root, observed, data)["entries"] == 4
        assert executable.read_bytes() == b"runtime" and database.read_bytes() == b"database"
        assert api.dacl_parts(observed[executable])[1] == api.dacl_parts(policy[executable])[1]
        # Reproduce the second CI failure on one disposable file. Cleanup's
        # structural guard must remain usable when file contents are denied.
        denied = tmp_path / "denied.acl"
        api.write_acl_policy(denied, root, {root: policy[root], executable: "D:P"})
        icacls(root.parent, "/restore", denied, "/Q")
        with pytest.raises(PermissionError):
            executable.read_bytes()
        api.ROOT = root
        assert api.inventory(root, hash_files=False)["python.exe"]["bytes"] == 7
    finally:
        icacls(root.parent, "/restore", baseline, "/Q")
    icacls(root, "/save", restored_path, "/T", "/Q")
    assert api.verify_acl_restoration(before, api.acl_entries(restored_path, root))["original_dacls_equal"]
