"""Filesystem admission only; constructed inputs are never executed."""
import json
from pathlib import Path
import pytest
from scripts.verification.daily_frozen_inputs import DIRECTORIES, ROLES, directory_inventory, file_record, verify_frozen


def fixture(tmp_path):
    files = {}
    for role in ROLES:
        p = tmp_path / role
        p.write_bytes(("constructed nonexecutable input " + role).encode())
        files[role] = file_record(p)
    directories = {}
    for role in DIRECTORIES:
        p = tmp_path / (role + "-directory")
        p.mkdir()
        (p / "owned.txt").write_bytes(b"constructed directory input")
        directories[role] = {"path": str(p), "exact": role != "core", "files": directory_inventory(p)}
    value = {"schema": 1, "core_version": "0.1.0.dev16", "companion_version": "0.1.16", "profile_id": "a" * 64, "files": files, "directories": directories, "producer": {"fixture_origin": "constructed; no installed Core/native/model claim"}}
    return value


def save(tmp_path, value):
    p = tmp_path / "frozen.json"
    p.write_text(json.dumps(value), encoding="utf-8")
    return p


def test_actual_constructed_bytes_are_admitted_without_qualifying_producer(tmp_path):
    value = fixture(tmp_path)
    binding, receipt = verify_frozen(save(tmp_path, value))
    assert binding == value
    assert receipt["source_ci_qualified_by_this_check"] is False
    assert receipt["files"]["test_module"] == value["files"]["test_module"]


def test_changed_module_bytes_refuse_before_any_process(tmp_path):
    value = fixture(tmp_path)
    Path(value["files"]["test_module"]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        verify_frozen(save(tmp_path, value))


def test_wrong_named_binary_size_refuses(tmp_path):
    value = fixture(tmp_path)
    value["files"]["platform"]["size"] += 1
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        verify_frozen(save(tmp_path, value))


def test_unlisted_fixture_file_refuses(tmp_path):
    value = fixture(tmp_path)
    (Path(value["directories"]["fixture"]["path"]) / "unlisted.txt").write_bytes(b"changed input")
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        verify_frozen(save(tmp_path, value))


def test_unrelated_core_cache_does_not_replace_owned_source_pins(tmp_path):
    value = fixture(tmp_path)
    root = Path(value["directories"]["core"]["path"])
    (root / "cache.pyc").write_bytes(b"nonowned cache")
    assert verify_frozen(save(tmp_path, value))[1]["directories"]["core"]["files"] == 1
    (root / "owned.txt").write_bytes(b"changed owned source")
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        verify_frozen(save(tmp_path, value))


def test_parent_relative_inventory_is_refused(tmp_path):
    value = fixture(tmp_path)
    pin = next(iter(value["directories"]["fixture"]["files"].values()))
    value["directories"]["fixture"]["files"] = {"../owned.txt": pin}
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        verify_frozen(save(tmp_path, value))


def test_missing_required_role_is_refused(tmp_path):
    value = fixture(tmp_path)
    del value["files"]["vsix"]
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        verify_frozen(save(tmp_path, value))


def test_unknown_role_is_refused(tmp_path):
    value = fixture(tmp_path)
    value["files"]["fallback"] = value["files"]["editor"]
    with pytest.raises(ValueError, match="INPUT_BINDING_MISMATCH"):
        verify_frozen(save(tmp_path, value))
