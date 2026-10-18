"""Portable client-oracle and finite failure diagnostics, not Windows acceptance."""
import importlib.util
from pathlib import Path
import traceback

import anyio
import pytest

from rentgen_core.stdio_mcp import TOOL_SCHEMAS

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location("kit_contract_" + name,
        ROOT / "scripts/verification" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installed_client_accepts_current_complete_catalog_in_either_order():
    client = load("core_kit_client")
    names = list(TOOL_SCHEMAS)
    assert "rentgen_snapshot_diff" in names
    client.require_tool_inventory(names)
    client.require_tool_inventory(list(reversed(names)))


@pytest.mark.parametrize("change", ["missing", "duplicate", "extra", "replacement"])
def test_installed_client_refuses_incomplete_duplicate_or_changed_catalog(change):
    client = load("core_kit_client")
    names = list(TOOL_SCHEMAS)
    if change == "missing": names.remove("rentgen_snapshot_diff")
    elif change == "duplicate": names.append(names[0])
    elif change == "extra": names.append("unreviewed_tool")
    else: names[-1] = "unreviewed_tool"
    with pytest.raises(AssertionError):
        client.require_tool_inventory(names)


def verifier(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/verification"))
    return load("verify_core_kit")


def test_actual_python_traceback_reports_only_client_line_numbers(tmp_path, monkeypatch):
    module = verifier(monkeypatch)
    child = tmp_path / "client.py"
    code = compile('raise AssertionError("PRIVATE_FIXTURE_OUTPUT")\n', str(child), "exec")
    try:
        exec(code, {})
    except AssertionError:
        stderr = traceback.format_exc()
    else:
        pytest.fail("fixture did not raise its real Python exception")
    assert "PRIVATE_FIXTURE_OUTPUT" in stderr
    value = module.client_failure_locations(stderr)
    assert value == "client.py:1"
    assert str(tmp_path) not in value and "PRIVATE_FIXTURE_OUTPUT" not in value


def test_windows_client_frames_are_bounded_and_other_filenames_ignored(monkeypatch):
    module = verifier(monkeypatch)
    frames = ''.join(f'  File "C:\\private\\client.py", line {i}, in main\n' for i in range(1, 8))
    frames += '  File "/private/other.py", line 99, in main\nPRIVATE_FIXTURE_OUTPUT\n'
    assert module.client_failure_locations(frames) == "client.py:4, client.py:5, client.py:6, client.py:7"


def test_old_or_missing_client_frame_returns_fixed_diagnostic(monkeypatch):
    module = verifier(monkeypatch)
    value = '  File "/private/client.py", line 10, in main\n' + "x" * 65536
    assert module.client_failure_locations(value) == "unavailable"
    assert module.client_failure_locations(None) == "unavailable"
    assert module.client_failure_locations("PRIVATE_FIXTURE_OUTPUT") == "unavailable"
    assert module.client_failure_locations("\n" * 65536) == "unavailable"


@pytest.mark.parametrize("filename", ["publication_overlap_probe.py", "overlap.py"])
def test_overlap_traceback_reports_only_allowlisted_filename_and_line(tmp_path, monkeypatch, filename):
    module = verifier(monkeypatch)
    code = compile('raise ValueError("PRIVATE_OVERLAP_OUTPUT")\n', str(tmp_path / filename), "exec")
    try:
        exec(code, {})
    except ValueError:
        stderr = traceback.format_exc()
    else:
        pytest.fail("fixture did not raise")
    assert module.client_failure_locations(stderr) == filename + ":1"
    assert module.client_failure_locations(stderr.replace(filename, "other_probe.py")) == "unavailable"


def test_real_anyio_exception_group_preserves_client_frame_numbers(tmp_path, monkeypatch):
    module = verifier(monkeypatch)
    filename = str(tmp_path / "client.py")
    namespace = {"anyio": anyio}
    source = (
        "async def exercise():\n"
        "    async with anyio.create_task_group():\n"
        "        raise AssertionError('PRIVATE_GROUP_OUTPUT')\n"
    )
    exec(compile(source, filename, "exec"), namespace)
    try:
        anyio.run(namespace["exercise"])
    except ExceptionGroup:
        stderr = traceback.format_exc()
    else:
        pytest.fail("fixture did not raise its real AnyIO exception group")
    assert "|" in stderr and "PRIVATE_GROUP_OUTPUT" in stderr
    value = module.client_failure_locations(stderr)
    assert "client.py:3" in value.split(", ")
    assert len(value.split(", ")) <= 4
    assert str(tmp_path) not in value and "PRIVATE_GROUP_OUTPUT" not in value
