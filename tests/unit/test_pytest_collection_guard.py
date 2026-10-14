"""Portable isolated subprocess acceptance for the actual collection guard."""
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

import pytest

GUARD = Path(__file__).resolve().parents[1] / "conftest.py"
PREFIX = "test_sample.py::test_payload["
SUFFIX = "]"


def run_collection(tmp_path, source, *options):
    shutil.copyfile(GUARD, tmp_path / "conftest.py")
    (tmp_path / "test_sample.py").write_text(source, encoding="utf-8")
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\ntestpaths = .\ndisable_test_id_escaping_and_forfeit_all_rights_to_community_support = True\n")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PYTEST_") and key != "PYTHONPATH"}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, "-m", "pytest", "-c", str(config),
                           "--confcutdir", str(tmp_path), "-q", *options],
                          cwd=tmp_path, env=env, text=True, encoding="utf-8", errors="replace",
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)


def parametrized(identifier, value="1"):
    return ("import pytest\nfrom pathlib import Path\n"
            f"@pytest.mark.parametrize('value', [{value}], ids=[{identifier!r}])\n"
            "def test_payload(value, request):\n"
            f"    assert value == {value}\n"
            f"    assert request.node.nodeid == {(PREFIX + identifier + SUFFIX)!r}\n"
            "    Path('body-ran').write_text('ran')\n")


@pytest.mark.parametrize("text,units", [("a" * 1024, 1024), ("a" * 1025, 1025),
    ("😀" * 512, 1024), ("😀" * 513, 1026), ("\ud800", 1)],
    ids=["ascii-bound", "ascii-over", "nonbmp-bound", "nonbmp-over", "lone-surrogate"])
def test_utf16_unit_count_is_windows_accurate(text, units):
    assert runpy.run_path(str(GUARD))["_node_id_units"](text) == units


@pytest.mark.parametrize("extra,expected", [(0, 0), (1, 4)], ids=["bound", "bound-plus-one"])
@pytest.mark.parametrize("collect_only", [False, True], ids=["execute", "collect-only"])
def test_exact_node_id_boundary_before_test_execution(tmp_path, extra, expected, collect_only):
    identifier = "x" * (1024 - len(PREFIX + SUFFIX) + extra)
    result = run_collection(tmp_path, parametrized(identifier), *(["--collect-only"] if collect_only else []))
    assert result.returncode == expected, result.stdout
    assert (tmp_path / "body-ran").exists() == (expected == 0 and not collect_only)
    if expected:
        assert "1025 UTF-16 units" in result.stdout
        assert identifier not in result.stdout
        assert "short explicit ids=" in result.stdout


def test_nonbmp_identifier_uses_utf16_boundary(tmp_path):
    room = 1024 - len(PREFIX + SUFFIX)
    identifier = "😀" * (room // 2) + "a" * (room % 2)
    good = run_collection(tmp_path, parametrized(identifier), "--collect-only")
    assert good.returncode == 0, good.stdout
    assert identifier in good.stdout
    bad = run_collection(tmp_path, parametrized(identifier + "😀"), "--collect-only")
    assert bad.returncode == 4 and "1026 UTF-16 units" in bad.stdout
    assert not (tmp_path / "body-ran").exists()


@pytest.mark.parametrize("collect_only", [False, True], ids=["execute", "collect-only"])
def test_large_payload_requires_explicit_short_identity(tmp_path, collect_only):
    opts = ["--collect-only"] if collect_only else []
    short = run_collection(tmp_path, parametrized("large-synthetic", "'PAYLOAD_SENTINEL_' * 65536"), *opts)
    assert short.returncode == 0, short.stdout
    marker = tmp_path / "body-ran"
    assert marker.exists() == (not collect_only)
    marker.unlink(missing_ok=True)
    source = ("import pytest\nfrom pathlib import Path\n"
              "@pytest.mark.parametrize('value', ['PAYLOAD_SENTINEL_' * 65536])\n"
              "def test_payload(value):\n    Path('body-ran').write_text('ran')\n")
    oversized = run_collection(tmp_path, source, *opts)
    assert oversized.returncode == 4, oversized.stdout[:1000]
    assert "PAYLOAD_SENTINEL" not in oversized.stdout
    assert "test_sample.py::test_payload" in oversized.stdout
    assert "short explicit ids=" in oversized.stdout and len(oversized.stdout) < 2000
    assert not marker.exists()


def test_guard_includes_cases_deselected_by_expression(tmp_path):
    result = run_collection(tmp_path, parametrized("z" * 2000), "-k", "does_not_match")
    assert result.returncode == 4 and "short explicit ids=" in result.stdout
    assert not (tmp_path / "body-ran").exists()


def test_diagnostic_escapes_controls_and_never_contains_parameters():
    class Item:
        path = Path("private") / "test_\nfile.py"
        originalname = "test_\tfunction"
        name = "test_function[PAYLOAD_SENTINEL]"
    label = runpy.run_path(str(GUARD))["_safe_test_label"](Item())
    assert "\n" not in label and "\t" not in label
    assert "\\n" in label and "\\t" in label
    assert "PAYLOAD_SENTINEL" not in label and "private" not in label
    assert len(label) <= 120
    Item.originalname = "x" * 10000
    assert len(runpy.run_path(str(GUARD))["_safe_test_label"](Item())) == 120
