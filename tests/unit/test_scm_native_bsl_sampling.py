"""Bounded native-evidence sampling contracts; no WMI, SCM or token mutation.

Unavailable rows represent the three observed owned descendant pairs from the
failed fa35 push. Capture outputs, later Java rows and publication documents are
constructed. The real lifecycle and wait methods decide admission/refusal.
"""
import ast
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit.test_stock_git_scm_lifecycle import api


def unavailable_rows(parent, child):
    return [
        {"ProcessId": parent, "ParentProcessId": 3296,
         "ExecutablePath": None, "CommandLine": None},
        {"ProcessId": child, "ParentProcessId": parent,
         "ExecutablePath": None, "CommandLine": None},
    ]


UNAVAILABLE = [unavailable_rows(7312, 4484), unavailable_rows(6072, 1888),
               unavailable_rows(988, 2860)]


def sampling_fixture(tmp_path, monkeypatch, snapshots, *, sequence=0,
                     initial_enabled=False, fault=None, outcome=None,
                     fallback=None, tick=0.6, publication_complete=True):
    module = api()
    state = {"enabled": initial_enabled, "captures": [], "events": [],
             "saved": [], "native_reads": [], "java_rows": [],
             "publication_reads": 0, "publication_validations": 0,
             "acl_restores": 0, "held_reaps": 0, "clock": 0.0, "state": 4}
    remaining = iter(snapshots)
    runtime = tmp_path / "diagnostics/runtime"
    java = {"ProcessId": 9000, "ParentProcessId": 3296,
            "ExecutablePath": str(runtime / "jdk/bin/java.exe"),
            "CommandLine": "constructed complete pinned Java command"}

    def require(ok, message):
        if not ok:
            raise RuntimeError(message)

    @contextmanager
    def debug():
        before = state["enabled"]
        state["enabled"] = fault != "not_enabled"
        try:
            yield
        finally:
            state["enabled"] = not before if fault == "restoration" else before

    def bounded(seconds):
        if fault == "exercise_budget":
            raise RuntimeError("global exercise budget exhausted")
        return seconds

    def capture(command, environment, output, label, **options):
        assert state["enabled"] is True
        assert options == {"timeout": 10}
        state["captures"].append(label)
        state["clock"] += tick
        if fault == "capture":
            raise RuntimeError("constructed capture failure")
        if fault == "generic_incomplete":
            raise RuntimeError("Native process inventory is incomplete")
        rows = next(remaining, fallback)
        assert rows is not None, "Constructed observation fixture exhausted"
        if rows == "java":
            rows = [java]
        return {"exit_code": 0, "child_reaped": True, "timed_out": False,
                "output_limit_exceeded": False, "process_error": None,
                "fixture_stdout": json.dumps(rows).encode(), **(outcome or {})}

    class Base:
        def stop(self):
            state["state"] = 1
            return {"status": {"state": 1, "pid": 0, "win32_exit": 0,
                               "service_exit": 0}}

        def cleanup(self):
            state["acl_restores"] += 1
            return []

    def process(pid):
        assert state["enabled"] is True
        state["native_reads"].append(pid)
        if fault == "native":
            raise RuntimeError("constructed native image/token read failure")
        return {"pid": pid, "image": java["ExecutablePath"],
                "token_user_sid": "S-1-5-19"}

    def validate_java(row, actual, **options):
        assert state["enabled"] is True
        assert row["ProcessId"] == actual["pid"] == 9000
        assert row["ParentProcessId"] == options["service_pid"] == 3296
        state["java_rows"].append(dict(row))
        return {**actual, "parent_pid": row["ParentProcessId"]}

    def validate_publication(doc, **options):
        state["publication_validations"] += 1
        return {"commits": options["commits"], "constructed": True}

    def validate_stopped(status):
        assert status == {"state": 1, "pid": 0, "win32_exit": 0,
                          "service_exit": 0}

    measurement = SimpleNamespace(validate_java=validate_java,
        validate_publication=validate_publication, validate_stopped=validate_stopped,
        command_line_argv=lambda _: [])
    worker = SimpleNamespace(Acceptance=Base, require=require, bounded=bounded,
        save=lambda path, value: state["saved"].append(path.name),
        PYTHON=tmp_path / "runtime/python.exe", ROOT=tmp_path / "fixture")
    # Execute only the pure wait function with a deterministic clock, never the
    # worker module's native setup or process entry point.
    path = Path(__file__).resolve().parents[2] / "scripts/verification/scm_acceptance_worker.py"
    wait, = [node for node in ast.parse(path.read_bytes()).body
             if isinstance(node, ast.FunctionDef) and node.name == "wait_until"]
    clock = SimpleNamespace(monotonic=lambda: state["clock"],
        sleep=lambda seconds: state.update(clock=state["clock"] + seconds))
    namespace = {"time": clock, "bounded": bounded, "require": require}
    exec(compile(ast.Module(body=[wait], type_ignores=[]), str(path), "exec"), namespace)
    worker.wait_until = namespace["wait_until"]
    probe = SimpleNamespace(capture=capture,
                            _raw=lambda result, stream: result["fixture_stdout"])
    cls = module.acceptance_type(worker, None, probe, None, None, None, measurement)
    test = cls.__new__(cls)
    test.native = SimpleNamespace(debug_privilege=debug, process=process,
        privileges=lambda: [{"name": "SeDebugPrivilege", "enabled": state["enabled"]}])
    test.output, test.runtime, test.scratch = tmp_path, runtime, tmp_path / "scratch"
    test.query_sequence, test.java_proofs = sequence, {}
    test.held = SimpleNamespace(pid=3296,
        wait=lambda: state.update(held_reaps=state["held_reaps"] + 1))
    test.created = False
    test.f, test.source = {"project_id": "constructed"}, tmp_path / "source"
    test.current = lambda: {"status": {"state": state["state"]}}
    test.journal = SimpleNamespace(read=lambda: {"phase": "idle", "event": {"status": "stopped"}})
    test.event = lambda name, **fields: state["events"].append((name, fields))

    def publication():
        state["publication_reads"] += 1
        return {"outbox": [{"event": {"status": "analyzed"}}] if publication_complete else []}

    test.publication = publication
    monkeypatch.setattr(module.shutil, "which", lambda _: str(tmp_path / "pwsh.exe"))
    return test, state, module


def events(state, name):
    return [fields for kind, fields in state["events"] if kind == name]


@pytest.mark.parametrize("label", ["first", "next"])
@pytest.mark.parametrize("initial_enabled", [False, True])
def test_native_sampler_defers_three_unavailable_snapshots_until_complete_java(
    tmp_path, monkeypatch, label, initial_enabled
):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch,
        [*UNAVAILABLE, "java"], sequence=11, initial_enabled=initial_enabled)
    assert test.published(label, ["a" * 40], native_bsl=True)["constructed"] is True
    assert state["captures"] == ["stock-processes-12", "stock-processes-13",
                                 "stock-processes-14", "stock-processes-15"]
    assert events(state, "stock_native_bsl_inventory_deferred") == [{
        "label": label, "last_capture": "stock-processes-14", "max_attempts": 3,
        "cleanup_query_reserve": 6}]
    event_names = [name for name, _ in state["events"]]
    deferred = event_names.index("stock_native_bsl_inventory_deferred")
    assert event_names[deferred - 1] == "stock_debug_privilege_inspected"
    assert state["native_reads"] == [9000] and len(state["java_rows"]) == 1
    assert state["publication_reads"] == state["publication_validations"] == 1
    scopes = events(state, "stock_debug_privilege_inspected")
    assert len(scopes) == 4 and all(scope["privileges_restored"] is True for scope in scopes)
    assert all(scope["privileges_before"] == scope["privileges_after"] for scope in scopes)
    assert state["enabled"] is initial_enabled


@pytest.mark.parametrize("field,value", [("ExecutablePath", None), ("ExecutablePath", ""),
                                         ("CommandLine", None), ("CommandLine", "")])
def test_failed_whole_chain_never_reads_present_java_or_publication(
    tmp_path, monkeypatch, field, value
):
    incomplete = [{"ProcessId": 81, "ParentProcessId": 3296,
                   "ExecutablePath": "constructed", "CommandLine": "constructed",
                   field: value}]
    java = {"ProcessId": 9000, "ParentProcessId": 3296,
            "ExecutablePath": str(tmp_path / "diagnostics/runtime/jdk/bin/java.exe"),
            "CommandLine": "constructed complete pinned Java command"}
    # A Java row exists in each failed snapshot; one unavailable row invalidates
    # the whole snapshot, so the native read occurs only in the fourth capture.
    test, state, _ = sampling_fixture(tmp_path, monkeypatch,
        [[java, *incomplete]] * 3 + ["java"])
    original_process = test.native.process
    def read_only_complete(pid):
        assert len(state["captures"]) == 4
        return original_process(pid)
    test.native.process = read_only_complete
    assert test.published("next", ["a" * 40], native_bsl=True)["constructed"] is True
    assert len(state["native_reads"]) == state["publication_reads"] == 1
    assert len(events(state, "stock_native_bsl_inventory_deferred")) == 1


@pytest.mark.parametrize("fault,message", [
    ("capture", "constructed capture failure"),
    ("generic_incomplete", "Native process inventory is incomplete"),
    ("native", "constructed native image/token read failure"),
    ("restoration", "changed original token privileges"),
    ("not_enabled", "Existing debug privilege was not enabled"),
    ("exercise_budget", "global exercise budget exhausted"),
])
def test_sampler_keeps_non_availability_errors_fatal(tmp_path, monkeypatch, fault, message):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, ["java"], fault=fault)
    with pytest.raises(RuntimeError, match=message):
        test.published("next", ["a" * 40], native_bsl=True)
    assert not events(state, "stock_native_bsl_inventory_deferred")
    assert state["publication_reads"] == 0


@pytest.mark.parametrize("outcome", [{"exit_code": 1}, {"timed_out": True},
    {"child_reaped": False}, {"output_limit_exceeded": True}, {"process_error": "capture failed"}])
def test_sampler_capture_refusals_never_become_deferred(tmp_path, monkeypatch, outcome):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, ["java"], outcome=outcome)
    with pytest.raises(RuntimeError, match="Native process inventory failed"):
        test.published("first", ["a" * 40], native_bsl=True)
    assert len(state["captures"]) == 1 and state["publication_reads"] == 0
    assert not events(state, "stock_native_bsl_inventory_deferred")


@pytest.mark.parametrize("rows", [[{}], [{"ProcessId": True}], "not a row array"])
def test_sampler_malformed_rows_remain_fatal_without_deferral(tmp_path, monkeypatch, rows):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, [rows])
    with pytest.raises(RuntimeError, match="Native process inventory shape differs"):
        test.published("first", ["a" * 40], native_bsl=True)
    assert len(state["captures"]) == 1 and state["publication_reads"] == 0
    assert not events(state, "stock_native_bsl_inventory_deferred")


@pytest.mark.parametrize("method", ["processes", "children", "stop"])
def test_non_sampling_inventory_exhaustion_is_typed_and_hard(tmp_path, monkeypatch, method):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, UNAVAILABLE)
    with pytest.raises(RuntimeError, match="Native process inventory is incomplete") as error:
        getattr(test, method)()
    assert type(error.value).__name__ == "ProcessInventoryIncomplete"
    assert len(state["captures"]) == 3 and not state["enabled"]
    assert not events(state, "stock_native_bsl_inventory_deferred")


def test_cleanup_keeps_uncertain_lifetimes_outside_sdk_acl_restoration(tmp_path, monkeypatch):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, UNAVAILABLE)
    assert test.cleanup() == [{"stage": "stock_process_lifetime", "type": "ProcessInventoryIncomplete"}]
    assert state["acl_restores"] == 0 and len(state["captures"]) == 3
    assert not events(state, "stock_native_bsl_inventory_deferred")


@pytest.mark.parametrize("sequence", [192, 194, 195, 199, 200])
def test_active_sampling_refuses_before_consuming_six_cleanup_queries(
    tmp_path, monkeypatch, sequence
):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, ["java"], sequence=sequence)
    with pytest.raises(RuntimeError, match="reserved cleanup observations") as error:
        test.published("next", ["a" * 40], native_bsl=True)
    assert type(error.value) is RuntimeError
    assert test.query_sequence == sequence and not state["captures"]
    assert not state["events"] and state["publication_reads"] == 0


def test_last_full_sampling_chain_leaves_three_stop_and_three_cleanup_queries(tmp_path, monkeypatch):
    test, state, module = sampling_fixture(tmp_path, monkeypatch,
        [*UNAVAILABLE[:2], "java", *UNAVAILABLE[:2], [], *UNAVAILABLE[:2], []], sequence=191)
    assert test.published("next", ["a" * 40], native_bsl=True)["constructed"] is True
    assert test.query_sequence == 194
    test.stop()
    assert test.query_sequence == 197 and state["held_reaps"] == 1
    assert test.cleanup() == []
    assert test.query_sequence == 200 and state["acl_restores"] == 1
    assert len(state["captures"]) == 9
    assert getattr(module, "NATIVE_BSL_CLEANUP_QUERY_RESERVE", None) == 6


def test_repeated_deferral_refuses_next_chain_before_cleanup_reserve(tmp_path, monkeypatch):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch,
        [*UNAVAILABLE, *UNAVAILABLE, "java"], sequence=188)
    with pytest.raises(RuntimeError, match="reserved cleanup observations") as error:
        test.published("next", ["a" * 40], native_bsl=True)
    assert type(error.value) is RuntimeError and test.query_sequence == 194
    assert len(state["captures"]) == 6
    assert len(events(state, "stock_native_bsl_inventory_deferred")) == 2
    assert state["publication_reads"] == 0 and not test.java_proofs


@pytest.mark.parametrize("label", ["repeat", "unknown"])
def test_native_sampling_only_accepts_first_or_next_labels(tmp_path, monkeypatch, label):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, ["java"])
    with pytest.raises(RuntimeError, match="Native BSL sampling label differs"):
        test.published(label, ["a" * 40], native_bsl=True)
    assert not state["captures"] and not state["events"]


def test_complete_publication_without_java_window_is_not_native_acceptance(tmp_path, monkeypatch):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, [[]])
    with pytest.raises(RuntimeError, match="Native BSL process window was not proved"):
        test.published("first", ["a" * 40], native_bsl=True)
    assert state["publication_reads"] == 1 and not test.java_proofs
    assert "publication-first.json" not in state["saved"]


@pytest.mark.parametrize("unavailable", [False, True])
def test_native_window_timeout_never_accepts_missing_java(tmp_path, monkeypatch, unavailable):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, [],
        fallback=UNAVAILABLE[0] if unavailable else [], tick=9,
        publication_complete=False)
    with pytest.raises(RuntimeError, match="Timed out: stock complete publication next") as error:
        test.published("next", ["a" * 40], native_bsl=True)
    assert type(error.value) is RuntimeError and 180 <= state["clock"] < 210
    assert test.query_sequence < 194 and not test.java_proofs
    assert "publication-next.json" not in state["saved"]
    if unavailable:
        assert state["publication_reads"] == 0
        assert len(events(state, "stock_native_bsl_inventory_deferred")) >= 1


def test_default_non_native_publication_does_not_query_or_defer(tmp_path, monkeypatch):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, [], sequence=200)
    assert test.published("repeat", ["a" * 40])["constructed"] is True
    assert not state["captures"] and not events(state, "stock_native_bsl_inventory_deferred")


def test_existing_java_proof_does_not_restart_the_native_sampler(tmp_path, monkeypatch):
    test, state, _ = sampling_fixture(tmp_path, monkeypatch, [], sequence=200)
    test.java_proofs["next"] = {"constructed_prior": True}
    assert test.published("next", ["a" * 40], native_bsl=True)["constructed"] is True
    assert not state["captures"] and not events(state, "stock_native_bsl_inventory_deferred")
