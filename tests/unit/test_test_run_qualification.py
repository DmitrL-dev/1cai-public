"""Pure retained-run evaluator: constructed bytes only, never a native result."""
import copy

import pytest

import run_qualification_support as support
from rentgen_core.manifests import canonical_bytes, sha256
from rentgen_core.test_run_qualification import (
    CHECKS,
    QualificationLimits,
    evaluate,
    evidence_names,
    step_universe,
    target_path,
)
from rentgen_core.errors import CoreError


def checks(dossier):
    return {row["id"]: (row["status"], row["detail"]) for row in dossier["checks"]}


def mismatch(dossier):
    return {k: v[1] for k, v in checks(dossier).items() if v[0] == "mismatch"}


def report(value):
    return value["record"]["report"]


@pytest.mark.parametrize(
    "outcomes",
    [
        ("failed", "passed"),
        ("passed", "passed"),
        ("failed", "failed"),
        ("incomplete", "incomplete"),
        ("not_run", "passed"),
        ("passed", "not_run"),
        ("not_run", "not_run"),
    ],
)
def test_consistent_retained_runs_keep_their_own_test_outcome(outcomes):
    dossier = evaluate(support.bundle(outcomes))
    assert dossier["qualification"] == "consistent", checks(dossier)
    assert all(row["status"] == "verified" for row in dossier["checks"])
    assert [row["id"] for row in dossier["checks"]] == list(CHECKS)
    assert dossier["test_result"] == {
        "status": outcomes[1],
        "baseline": outcomes[0],
        "candidate": outcomes[1],
    }
    assert dossier["evidence"] == "local_unattested"
    assert dossier["execution"] == "not_performed"
    assert dossier["apply"] == {"status": "unavailable"}
    unsigned = {k: v for k, v in dossier.items() if k != "dossier_sha256"}
    assert dossier["dossier_sha256"] == sha256(canonical_bytes(unsigned))


def test_skip_only_remains_incomplete_and_never_passed():
    dossier = evaluate(support.bundle(("incomplete", "incomplete")))
    assert dossier["qualification"] == "consistent"
    assert dossier["test_result"]["candidate"] == "incomplete"


def test_disabled_profile_still_qualifies_the_historical_run():
    value = support.bundle()
    value["profile"]["enabled"] = False
    dossier = evaluate(value)
    assert dossier["qualification"] == "consistent"
    assert dossier["profile"]["enabled"] is False


def test_tampered_junit_bytes_are_not_accepted_from_the_report():
    value = support.bundle()
    value["files"]["baseline.junit.xml"] = value["files"]["baseline.junit.xml"].replace(
        b'<failure message="constructed"/>', b""
    )
    dossier = evaluate(value)
    assert dossier["qualification"] == "inconsistent"
    assert mismatch(dossier) == {"junit_exit": "BASELINE_JUNIT_INVALID"}


def test_client_exit_zero_cannot_turn_a_failed_junit_into_pass():
    value = support.bundle(("failed", "passed"))
    files = value["files"]
    files["candidate.junit.xml"] = files["baseline.junit.xml"]
    files["candidate.exit"] = files["baseline.exit"]
    dossier = evaluate(value)
    assert mismatch(dossier) == {"junit_exit": "CANDIDATE_JUNIT_STATUS"}
    assert dossier["test_result"]["candidate"] == "passed"  # claim shown, not confirmed


def test_bool_cannot_stand_in_for_an_integer_exit_code():
    value = support.bundle(("passed", "passed"))
    report(value)["tests"]["candidate"]["framework_exit_code"] = False
    dossier = evaluate(support.resign(value))
    assert mismatch(dossier) == {"junit_exit": "CANDIDATE_JUNIT_FRAMEWORK_EXIT_CODE"}


def test_exit_file_disagreeing_with_junit_is_rejected():
    value = support.bundle()
    value["files"]["baseline.exit"] = b"0"
    assert mismatch(evaluate(value)) == {"junit_exit": "BASELINE_JUNIT_INVALID"}


@pytest.mark.parametrize(
    "edit",
    [
        lambda raw: raw.replace(b"RentgenTests", b"OtherTests"),
        lambda raw: raw.replace(b"\\\\state\\\\", b"\\\\other\\\\"),
        lambda raw: raw.replace(b'"closeAfterTests":true', b'"closeAfterTests":1'),
    ],
)
def test_settings_must_be_the_exact_owned_runner_settings(edit):
    value = support.bundle()
    raw = value["files"]["candidate-settings.json"]
    value["files"]["candidate-settings.json"] = edited = edit(raw)
    assert edited != raw
    report(value)["tests"]["candidate"]["settings_sha256"] = sha256(edited)
    dossier = evaluate(support.resign(value))
    assert mismatch(dossier) == {"runner_settings": "CANDIDATE_SETTINGS_CONTENT"}


def test_extra_or_changed_input_file_breaks_the_inventory_digest():
    value = support.bundle()
    value["trees"]["candidate"]["files"].append(
        {"path": "Extra.xml", "size": 1, "sha256": "0" * 64}
    )
    assert mismatch(evaluate(value)) == {"input_inventories": "CANDIDATE_INPUT_DIGEST"}


def test_a_second_changed_input_is_refused_even_with_a_resigned_digest():
    value = support.bundle()
    rows = value["trees"]["candidate"]["files"]
    other = next(row for row in rows if row["path"] == "Configuration.xml")
    other["sha256"] = "1" * 64
    inventory = sorted(
        ({k: r[k] for k in ("path", "size", "sha256")} for r in rows),
        key=lambda r: r["path"],
    )
    report(value)["candidate_input_sha256"] = sha256(canonical_bytes(inventory))
    assert mismatch(evaluate(support.resign(value))) == {
        "input_inventories": "CHANGED_SET"
    }


def test_unexpected_input_directory_is_refused():
    value = support.bundle()
    value["trees"]["baseline"]["directories"].append("Empty")
    assert mismatch(evaluate(value)) == {"input_inventories": "UNEXPECTED_DIRECTORY"}


def test_native_roundtrip_must_match_the_materialized_module():
    value = support.bundle()
    raw = value["targets"]["candidate-roundtrip"] + b"// drift\r\n"
    value["targets"]["candidate-roundtrip"] = raw
    report(value)["tests"]["candidate"]["native_module_sha256"] = sha256(raw)
    assert mismatch(evaluate(support.resign(value))) == {
        "native_roundtrip": "CANDIDATE_ROUNDTRIP_TEXT"
    }


def test_crlf_and_bom_normalization_is_the_runner_normalization():
    value = support.bundle()
    raw = value["targets"]["baseline-roundtrip"].replace(b"\r\n", b"\n")[3:]
    value["targets"]["baseline-roundtrip"] = raw
    report(value)["tests"]["baseline"]["native_module_sha256"] = sha256(raw)
    assert evaluate(support.resign(value))["qualification"] == "consistent"


def test_step_log_digest_text_order_and_unexpected_steps():
    value = support.bundle()
    value["files"]["candidate-execute.log"] += b"x"
    assert mismatch(evaluate(value)) == {"step_sequence": "STEP_LOG_DIGEST"}
    value = support.bundle()
    steps = report(value)["tests"]["steps"]
    steps[0], steps[1] = steps[1], steps[0]
    assert mismatch(evaluate(support.resign(value))) == {"step_sequence": "STEP_ORDER"}
    value = support.bundle(("not_run", "passed"))
    value["files"]["baseline-execute.log"] = b"late"
    assert mismatch(evaluate(value)) == {"step_sequence": "UNEXPECTED_STEP_EVIDENCE"}
    value = support.bundle()
    step = report(value)["tests"]["steps"][3]
    assert step["name"] == "baseline-compile"
    step["exit_code"] = 101
    assert mismatch(evaluate(support.resign(value))) == {"step_sequence": "COMPILE_EXIT"}


def test_report_digest_tamper_hides_the_claimed_result():
    value = support.bundle()
    report(value)["tests"]["candidate"]["status"] = "failed"
    dossier = evaluate(value)
    assert checks(dossier)["report_identity"] == ("mismatch", "REPORT_DIGEST")
    assert dossier["test_result"] is None
    assert dossier["qualification"] == "inconsistent"


def test_missing_raw_artifacts_never_verify():
    value = support.bundle()
    del value["files"]["candidate.junit.xml"]
    dossier = evaluate(value)
    assert dossier["qualification"] == "incomplete"
    assert checks(dossier)["junit_exit"] == ("missing", "CANDIDATE_JUNIT_XML_ABSENT")
    value = support.bundle()
    value["profile"] = None
    dossier = evaluate(value)
    assert dossier["qualification"] == "incomplete"
    assert checks(dossier)["profile_definition"] == ("missing", "PROFILE_ABSENT")
    assert checks(dossier)["junit_exit"] == ("missing", "PROFILE_REQUIRED")


def test_profile_and_engine_bindings():
    value = support.bundle()
    value["profile"]["definition"]["modules"][0]["tests"].append("Three")
    assert "profile_definition" in mismatch(evaluate(value))
    value = support.bundle()
    value["engine_sha256"] = "0" * 64
    assert mismatch(evaluate(value)) == {"profile_definition": "ENGINE_DIGEST"}


def test_engine_tree_must_contain_the_profile_test_modules():
    value = support.bundle()
    rows = value["trees"]["engine-with-tests"]["files"]
    module = next(r for r in rows if r["path"].endswith("/Ext/Module.bsl"))
    module["sha256"] = "2" * 64
    inventory = sorted(
        ({k: r[k] for k in ("path", "size", "sha256")} for r in rows),
        key=lambda r: __import__("pathlib").PureWindowsPath(r["path"]),
    )
    report(value)["tests"]["engine_source_sha256"] = sha256(canonical_bytes(inventory))
    assert mismatch(evaluate(support.resign(value))) == {
        "engine_source": "ENGINE_TEST_MODULE"
    }


def test_scratch_cleanup_claim_is_checked_against_presence():
    value = support.bundle()
    value["scratch_present"] = {"candidate-extension-properties-data": True}
    assert mismatch(evaluate(value)) == {"scratch_cleanup": "SCRATCH_PRESENT"}
    value = support.bundle(
        cleanup={"status": "retained", "released_logical_bytes": 0, "reason": "X"}
    )
    value["scratch_present"] = {"candidate-extension-properties-data": True}
    assert evaluate(value)["qualification"] == "consistent"


def test_unsafe_or_oversized_retained_objects_never_verify():
    value = support.bundle()
    value["files"]["candidate.exit"] = "oversized"
    assert mismatch(evaluate(value)) == {"junit_exit": "EVIDENCE_OVERSIZED"}
    value = support.bundle()
    value["trees"]["baseline"] = "unreadable"
    assert mismatch(evaluate(value)) == {"input_inventories": "BASELINE_TREE_UNSAFE"}


def test_failed_and_unfinished_runs_are_explicit_and_unqualified():
    value = support.bundle()
    record = value["record"]
    record.update(status="failed", failure={"code": "PLATFORM_TIMEOUT"})
    del record["report"]
    dossier = evaluate(value)
    assert dossier["qualification"] == "incomplete"
    assert dossier["failure_code"] == "PLATFORM_TIMEOUT"
    assert dossier["test_result"] is None
    assert {row["status"] for row in dossier["checks"]} == {"not_applicable"}
    record.update(status="incomplete")
    del record["failure"]
    assert evaluate(value)["failure_code"] is None


def test_malformed_report_and_unsafe_target_paths():
    value = support.bundle()
    del report(value)["tests"]
    dossier = evaluate(support.resign(value))
    assert dossier["qualification"] == "inconsistent"
    assert dossier["test_result"] is None
    value = support.bundle()
    for item in (report(value), value["record"]["request"]["input"]):
        item["source_ref"] = copy.deepcopy(item["source_ref"])
        item["source_ref"]["relative_path"] = "../outside.bsl"
    assert checks(evaluate(support.resign(value)))["report_identity"] == (
        "mismatch",
        "TARGET_PATH",
    )


@pytest.mark.parametrize(
    "value",
    ["../a.bsl", "/a.bsl", "C:/a.bsl", "a\\b.bsl", "a//b.bsl", "a/./b.bsl", "a.xml", "", 1, None],
)
def test_target_path_syntax_is_closed(value):
    assert target_path(value) is None


def test_reader_file_universe_is_closed_and_flat():
    names = evidence_names()
    assert len(names) == len(set(names))
    assert all("/" not in n and "\\" not in n and ".." not in n for n in names)
    assert "engine-dump" in step_universe()
    assert {"baseline.junit.xml", "candidate.exit", "candidate-settings.json"} <= set(names)


def test_limits_are_typed_and_bounded():
    QualificationLimits(tree_entries=10)
    for bad in ({"tree_entries": 0}, {"handles": True}, {"deadline_seconds": 10**6}):
        with pytest.raises(CoreError) as error:
            QualificationLimits(**bad)
        assert error.value.code == "INVALID_QUERY_OPTIONS"


def test_cli_parser_and_non_windows_capability_refusal(monkeypatch):
    from rentgen_core import capabilities, cli

    parsed = cli._parser().parse_args(
        ["test-run-qualify", "--registry", "r.sqlite3", "--project", "p", "--operation-id", "o"]
    )
    assert parsed.operation_id == "o"
    assert capabilities.COMMAND_CAPABILITIES["test-run-qualify"] == "native.evidence.read"
    for platform in ("linux", "darwin"):
        monkeypatch.setattr(capabilities, "_platform", platform)
        assert not capabilities.operation_supported("test-run-qualify")
        with pytest.raises(CoreError) as error:
            capabilities.require_operation("test-run-qualify")
        assert error.value.code == "CAPABILITY_UNAVAILABLE"
    monkeypatch.setattr(capabilities, "_platform", "win32")
    report = capabilities.capability_report()["capabilities"]["native.evidence.read"]
    assert report == {"supported": True, "reason": None, "operations": ["test-run-qualify"]}
