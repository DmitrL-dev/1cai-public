"""A successful client exit must never turn absent or failed tests into pass."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "yaxunit_report",
    Path(__file__).resolve().parents[2] / "scripts/verification/yaxunit_report.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
EXPECTED = [("Probe.ErrorPropagates", "ErrorPropagates", "Сервер")]


def report(status="", **counts):
    counters = {
        "tests": 1,
        "failures": int(status == "failure"),
        "errors": int(status == "error"),
        "skipped": int(status == "skipped"),
        **counts,
    }
    attrs = " ".join(f'{name}="{value}"' for name, value in counters.items())
    child = f'<{status} message="observed"/>' if status else ""
    return (
        f'<testsuites><testsuite {attrs}><testcase classname="Probe.ErrorPropagates" name="ErrorPropagates" context="Сервер">{child}</testcase></testsuite></testsuites>'
    ).encode()


def test_failed_skipped_and_broken_cases_are_never_passed():
    assert module.parse_report(report(), b"0", EXPECTED)["status"] == "passed"
    for child, status in [
        ("failure", "failed"),
        ("error", "failed"),
        ("skipped", "incomplete"),
    ]:
        assert (
            module.parse_report(
                report(child), b"1" if child != "skipped" else b"0", EXPECTED
            )["status"]
            == status
        )


@pytest.mark.parametrize(
    "raw,exit_code",
    [
        (b"<testsuites/>", b"0"),
        (report("failure"), b"0"),
        (report(), b"1"),
        (report(tests=0), b"0"),
        (report(failures=1), b"0"),
        (report().replace(b"ErrorPropagates", b"Different"), b"0"),
        (report().replace(b"</testcase>", b"</testcase><unknown/>"), b"0"),
        (b'<!DOCTYPE testsuites [<!ENTITY x "test">]><testsuites/>', b"0"),
    ],
)
def test_missing_mismatched_or_unsafe_evidence_is_rejected(raw, exit_code):
    with pytest.raises(ValueError):
        module.parse_report(raw, exit_code, EXPECTED)


def test_duplicate_expected_or_reported_test_is_rejected():
    with pytest.raises(ValueError):
        module.parse_report(report(), b"0", EXPECTED * 2)
    raw = report().decode()
    case = raw[raw.index("<testcase") : raw.index("</testcase>") + 11]
    with pytest.raises(ValueError):
        module.parse_report(
            raw.replace("</testsuite>", case + "</testsuite>")
            .replace('tests="1"', 'tests="2"')
            .encode(),
            b"0",
            EXPECTED,
        )


def test_contradictory_root_totals_and_hidden_cases_are_refused():
    for raw in [
        report().replace(b"<testsuites>", b'<testsuites tests="0">'),
        report().replace(
            b"</testsuites>",
            b'<properties><testcase name="hidden"/></properties></testsuites>',
        ),
    ]:
        with pytest.raises(ValueError):
            module.parse_report(raw, b"0", EXPECTED)
