"""Portable source/data contracts, never a Windows receiver execution receipt.

The terminal records below are deliberately synthetic unit-test inputs. They
are not independent review records, native observations, or runtime approval.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "scripts/verification/main_witness_receiver"
SCRIPTS = (
    "reproduce.py", "compile_data_abis.py", "admit_two_cases.py",
    "launch_two_cases.py", "verify_case.py",
)


def load_definitions(name):
    # Only these two scripts have guarded entry points; neither loads a DLL
    # or starts a child on import. Do not import the three admission helpers.
    spec = importlib.util.spec_from_file_location(
        "witness_contract_" + name, PACKAGE / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reproduce = load_definitions("reproduce")
verifier = load_definitions("verify_case")
PROVENANCE = json.loads((PACKAGE / "source_provenance.json").read_text("utf-8"))


@pytest.mark.parametrize("name", SCRIPTS)
def test_public_scripts_parse_without_execution(name):
    ast.parse((PACKAGE / name).read_bytes(), filename=name)


@pytest.mark.parametrize("name", SCRIPTS)
def test_public_scripts_expose_help_without_admission_or_native_effects(name):
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", str(PACKAGE / name), "--help"],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=False,
    )
    assert result.returncode == 0
    assert b"usage:" in result.stdout
    assert result.stderr == b""


@pytest.mark.parametrize("key", sorted(reproduce.FILES))
def test_cli_pins_match_exact_checkout_bytes(key):
    name, size, sha = reproduce.FILES[key]
    raw = (PACKAGE / name).read_bytes()
    assert (len(raw), hashlib.sha256(raw).hexdigest()) == (size, sha)


@pytest.mark.parametrize("ref", PROVENANCE["public_reproduction"]["source_files"],
                         ids=lambda ref: Path(ref["repo_path"]).name)
def test_public_source_provenance_matches_exact_checkout_bytes(ref):
    raw = (ROOT / ref["repo_path"]).read_bytes()
    assert (len(raw), hashlib.sha256(raw).hexdigest()) == (
        ref["size_bytes"], ref["sha256"],
    )


def test_all_native_fixture_pins_and_abi_contracts_agree():
    launcher = ast.parse((PACKAGE / "launch_two_cases.py").read_bytes())
    approved = next(
        ast.literal_eval(node.value) for node in launcher.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "APPROVED_SOURCE"
                for target in node.targets)
    )
    assert approved == verifier.EXPECTED
    for key, (size, sha) in approved.items():
        if key == "node":
            continue  # Its executable is intentionally absent from a source checkout.
        cli_key = {"header": "receiver_H", "base_header": "original_H"}.get(key, key)
        assert reproduce.FILES[cli_key][1:] == (size, sha)
    assert reproduce.RLD == verifier.ABI
    assert reproduce.RWR == verifier.RWR_ABI
    assert verifier.receiver_layout()["sizes"]["ReceiverStatus"] == 152


def test_recorded_experiments_do_not_grant_current_product_readiness():
    assert PROVENANCE["historical_private_controls"]["not_new_public_runtime_execution"]
    assert PROVENANCE["historical_private_controls"]["observations"]["freeze_handles_closed"] == 38
    public = PROVENANCE["public_reproduction"]
    assert public["Root_one_fresh_CLI_compile_and_two_controls_executed"] == "2026-10-03"
    assert public["actual_controls"]["actual_Root_freeze_handles_checked_closed"] == 45
    for scope in (PROVENANCE["limits"], public):
        assert scope["D8"] == "OPEN"
        for key in reproduce.FALSE_SCOPE:
            assert scope[key] is False


def test_review_byte_comparison_needs_every_pinned_input():
    expected = {"source": {"path": "old", "size_bytes": 3, "sha256": "a" * 64}}
    moved = copy.deepcopy(expected)
    moved["source"]["path"] = "new"
    assert reproduce.same_bytes(moved, expected)  # Relocation is checked separately.
    assert not reproduce.same_bytes({}, expected)
    assert not reproduce.same_bytes({**moved, "extra": moved["source"]}, expected)
    for key, wrong in (("size_bytes", 4), ("sha256", "b" * 64)):
        changed = copy.deepcopy(moved)
        changed["source"][key] = wrong
        assert not reproduce.same_bytes(changed, expected)


def test_cli_json_rejects_duplicate_review_fields():
    with pytest.raises(RuntimeError, match="duplicate JSON key"):
        reproduce.json_bytes(b'{"accepted":false,"accepted":true}')


@pytest.mark.parametrize("raw", [
    b'{"generation":1,"generation":2}', b'{"generation":1.0}',
    b'{"generation":NaN}', b'{"generation":Infinity}',
])
def test_verifier_rejects_ambiguous_or_noninteger_configuration(tmp_path, raw):
    path = tmp_path / "config.json"
    path.write_bytes(raw)
    with pytest.raises((RuntimeError, ValueError)):
        verifier.read_config(path)


def test_verifier_rejects_oversized_configuration(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b" " * 16385)
    with pytest.raises(RuntimeError, match="config cap"):
        verifier.read_config(path)


def terminal_record(*, positive):
    """Fabricated fields solely for testing the pure qualification predicate."""
    expected = 0 if positive else 1
    status = {key: 0 for key, _ in verifier.ReceiverStatus._fields_}
    status.update(
        generation=1, session_cookie=2, expected_slot=expected,
        status_index=2**32 - 1, phase=8, registered=1, revoked=1,
        io_terminal=1, retired=1, listen_created=1, connected=1,
        peer_compare_attempted=1, peer_bracket_before=1, peer_bracket_after=1,
        birth_filetime=100, birth_event_sequence=expected + 1,
        client_pid=101, expected_held_pid=101 + expected,
    )
    if positive:
        status.update(peer_match=1, peer_compare_match=1, hello_completed=1,
                      ack_issued=1, ack_completed=1, hello_wire_bytes=294,
                      ack_wire_bytes=311)
    else:
        status.update(primary_stage=105, primary_error=5)
    result = {
        "case": "expected_parent_slot0" if positive else "expected_child_slot1",
        "original_binding": {"generation": 1, "session_cookie": 2},
        "receiver_terminal_observation": {
            "accepted": 1, "submit_done": 1, "command_index": 2**64 - 1,
            "call": {"entered": 1, "done": 1, "ok": 1, "error": 0},
            "status": status,
        },
        "final_snapshot": {
            "cleanup_complete": 1, "worker_returned": 1,
            "owned_handles_remaining": 0, "system_handles_pending": 0,
            "cleanup_stage": 0, "cleanup_error": 0,
        },
        "Python_worker_producer_ended": True, "Python_worker_joined": True,
        "ledger": [{"code": 3, "sequence": 1, "pid": 101},
                   {"code": 3, "sequence": 2, "pid": 102}],
    }
    if positive:
        result["receiver_live_observation"] = {"status": copy.deepcopy(status)}
    return result, [{"birth_filetime": 100}, {"birth_filetime": 101}] if positive else []


@pytest.mark.parametrize("positive", [True, False])
def test_terminal_predicate_accepts_exact_synthetic_contract(monkeypatch, positive):
    monkeypatch.setattr(verifier, "_CALLS", [{"producer_ended": True}])
    result, snapshots = terminal_record(positive=positive)
    verifier.verify_receiver_terminal(result, snapshots)
    assert result["receiver_IO_producer_handle_retirement_observed_known"] is True


@pytest.mark.parametrize("positive", [True, False])
@pytest.mark.parametrize("field,value", [
    ("generation", 9), ("session_cookie", 9), ("expected_slot", 2),
    ("status_index", 0), ("phase", 7), ("registered", 0), ("revoked", 0),
    ("authenticated", 1), ("io_pending", 1), ("producer_pending", 1),
    ("io_terminal", 0), ("retired", 0), ("owned_handles_remaining", 1),
    ("cleanup_stage", 1), ("cleanup_error", 5), ("unknown", 1), ("grants", 1),
    ("peer_compare_attempted", 0), ("peer_bracket_before", 0),
    ("peer_bracket_after", 0), ("birth_filetime", 0),
    ("birth_event_sequence", 99), ("client_pid", 999), ("expected_held_pid", 999),
])
def test_terminal_predicate_refuses_incomplete_or_wrong_binding(
    monkeypatch, positive, field, value,
):
    monkeypatch.setattr(verifier, "_CALLS", [{"producer_ended": True}])
    result, snapshots = terminal_record(positive=positive)
    result["receiver_terminal_observation"]["status"][field] = value
    with pytest.raises(RuntimeError):
        verifier.verify_receiver_terminal(result, snapshots)
    assert not result.get("receiver_IO_producer_handle_retirement_observed_known", False)


@pytest.mark.parametrize("field,value", [
    ("primary_stage", 0), ("primary_error", 21), ("peer_match", 1),
    ("peer_compare_match", 1), ("hello_completed", 1), ("ack_issued", 1),
    ("ack_completed", 1), ("hello_wire_bytes", 1), ("ack_wire_bytes", 1),
])
def test_negative_control_requires_exact_wrong_peer_without_hello_ack(
    monkeypatch, field, value,
):
    monkeypatch.setattr(verifier, "_CALLS", [{"producer_ended": True}])
    result, snapshots = terminal_record(positive=False)
    result["receiver_terminal_observation"]["status"][field] = value
    with pytest.raises(RuntimeError):
        verifier.verify_receiver_terminal(result, snapshots)


@pytest.mark.parametrize("pending", ["native_call", "worker", "join", "handle"])
def test_terminal_predicate_never_accepts_unknown_producer_cleanup(monkeypatch, pending):
    monkeypatch.setattr(verifier, "_CALLS", [{"producer_ended": pending != "native_call"}])
    result, snapshots = terminal_record(positive=True)
    if pending == "worker":
        result["Python_worker_producer_ended"] = False
    elif pending == "join":
        result["Python_worker_joined"] = False
    elif pending == "handle":
        result["final_snapshot"]["owned_handles_remaining"] = 1
    with pytest.raises(RuntimeError):
        verifier.verify_receiver_terminal(result, snapshots)
