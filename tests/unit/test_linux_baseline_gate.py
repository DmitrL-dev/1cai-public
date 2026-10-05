"""A diagnostic allowlist must not turn collection loss or new failures green."""
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest


_path = Path(__file__).resolve().parents[2] / "scripts/verification/check_linux_baseline.py"
_spec = importlib.util.spec_from_file_location("linux_baseline_gate", _path)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def report(tmp_path, *, total=3000, skips=900, known="failure", extra=None,
           missing=False, duplicate=False, conflict=False):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    for number in range(total):
        name = "known" if number == 0 and not missing else f"case_{number}"
        if duplicate and number == 2:
            name = "case_1"
        case = ET.SubElement(suite, "testcase", classname="tests.example", name=name)
        if number == 0 and known:
            ET.SubElement(case, known)
            if conflict:
                ET.SubElement(case, "skipped")
        elif number == 1 and extra:
            ET.SubElement(case, extra)
        elif number >= total - skips:
            ET.SubElement(case, "skipped")
    junit = tmp_path / "report.xml"
    ET.ElementTree(root).write(junit)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"tests": [{"test": "tests.example::known"}]}))
    return junit, baseline


@pytest.mark.parametrize("kind", ["failure", "error"])
def test_known_failure_can_pass_only_baseline_comparison(tmp_path, kind):
    result = gate.assess(*report(tmp_path, known=kind), 1)
    assert result["baseline_comparison_passed"]
    assert not result["full_suite_green"]
    assert result["new_failures"] == []


def test_known_test_may_improve_without_hiding_a_failure(tmp_path):
    result = gate.assess(*report(tmp_path, known=None), 0)
    assert result["baseline_comparison_passed"] and result["full_suite_green"]
    assert result["known_failures_absent"] == ["tests.example::known"]


@pytest.mark.parametrize("options,status", [
    ({"extra": "failure"}, 1), ({"extra": "error"}, 1),
    ({"missing": True, "known": None}, 0),
    ({"duplicate": True}, 1), ({"conflict": True}, 1),
    ({"total": 2999}, 1), ({"skips": 1001}, 1),
    ({}, 0), ({"known": None}, 1), ({}, 2), ({}, 3), ({}, 5),
])
def test_gate_refuses_new_or_incomplete_or_inconsistent_results(tmp_path, options, status):
    result = gate.assess(*report(tmp_path, **options), status)
    assert not result["baseline_comparison_passed"]
    assert not result["full_suite_green"]


def test_malformed_report_never_returns_a_pass(tmp_path):
    junit, baseline = report(tmp_path)
    junit.write_text("<testsuites>")
    with pytest.raises(ET.ParseError):
        gate.assess(junit, baseline, 1)
