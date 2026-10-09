"""Pure journal and static budget contracts; no native or tracing execution."""
import ast
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
JOURNAL = "tests/fixtures/source_facts/qualification_journal.py"
SUPERVISOR = "tests/fixtures/source_facts/boundary_supervisor.py"


@pytest.fixture
def journal():
    spec = importlib.util.spec_from_file_location("tested_qualification_journal", ROOT / JOURNAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def test_phase_start_is_flushed_before_phase_body(journal, phase):
    class Stream(io.BytesIO):
        flushes = 0
        def flush(self):
            self.flushes += 1
            super().flush()
    stream = Stream(); plugin = journal.QualificationJournal(stream)
    item = SimpleNamespace(nodeid="synthetic.py::test_owned[control]")
    hook = getattr(plugin, "pytest_runtest_" + phase)
    assert hook.pytest_impl == {"wrapper": False, "hookwrapper": True, "optionalhook": False,
                                "tryfirst": True, "trylast": False, "specname": None}
    pending = hook(item, None) if phase == "teardown" else hook(item)
    next(pending)
    assert stream.flushes == 1
    event, = records(stream)
    assert event["event"] == "phase_start" and event["phase"] == phase
    assert event["nodeid"] == item.nodeid
    with pytest.raises(StopIteration):
        next(pending)


def test_journal_records_only_diagnostic_fields_in_order(journal, monkeypatch):
    ticks = iter(range(100, 110))
    monkeypatch.setattr(journal, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    stream = io.BytesIO(); plugin = journal.QualificationJournal(stream)
    nodeid = "synthetic.py::test_owned[control]"
    plugin.pytest_sessionstart(None)
    plugin.pytest_collection_finish(SimpleNamespace(items=[object()] * 176))
    plugin.pytest_runtest_logstart(nodeid, ("unused", 1, "PRIVATE_LOCATION"))
    plugin.pytest_runtest_logreport(SimpleNamespace(
        nodeid=nodeid, when="call", outcome="failed", duration=.25,
        longrepr="PRIVATE_ASSERTION", capstdout="PRIVATE_SOURCE", capstderr="PRIVATE_ERROR"))
    plugin.pytest_runtest_logfinish(nodeid, None)
    plugin.pytest_sessionfinish(None, 1)
    events = records(stream)
    assert [e["sequence"] for e in events] == list(range(6))
    assert [e["event"] for e in events] == ["session_start", "collection_finish", "item_start",
                                          "phase_finish", "item_finish", "session_finish"]
    assert [e["elapsed_seconds"] for e in events] == list(range(1, 7))
    assert events[1]["collected"] == 176
    assert events[3] == {"sequence": 3, "event": "phase_finish", "monotonic_seconds": 104,
                         "elapsed_seconds": 4, "nodeid": nodeid, "phase": "call",
                         "outcome": "failed", "duration_seconds": .25}
    assert b"PRIVATE" not in stream.getvalue()
    assert not plugin.failed


def test_exact_journal_bound_is_inclusive_and_never_truncates(journal, monkeypatch):
    monkeypatch.setattr(journal, "time", SimpleNamespace(monotonic=lambda: 1.0))
    control = io.BytesIO(); journal.QualificationJournal(control).record("control")
    monkeypatch.setattr(journal, "MAX_JOURNAL_BYTES", len(control.getvalue()))
    stream = io.BytesIO(); plugin = journal.QualificationJournal(stream)
    plugin.record("control")
    assert stream.getvalue() == control.getvalue()
    with pytest.raises(RuntimeError, match="bound exceeded"):
        plugin.record("overflow")
    assert plugin.failed and plugin.sequence == 1
    assert stream.getvalue() == control.getvalue()


@pytest.mark.parametrize("fault", ["write", "short_write", "flush"])
def test_journal_io_failure_is_fatal_and_latched(journal, fault):
    class Broken(io.BytesIO):
        def write(self, raw):
            if fault == "write": raise OSError("injected write failure")
            if fault == "short_write": return super().write(raw[:-1])
            return super().write(raw)
        def flush(self):
            if fault == "flush": raise OSError("injected flush failure")
            super().flush()
    plugin = journal.QualificationJournal(Broken())
    with pytest.raises(OSError):
        plugin.record("control")
    assert plugin.failed and plugin.sequence == 0
    preserved = plugin.stream.getvalue()
    for _ in range(3):
        with pytest.raises(RuntimeError, match="already failed"):
            plugin.record("later hook")
    assert plugin.stream.getvalue() == preserved


@pytest.mark.parametrize("fault", ["short_write", "flush"])
def test_failed_journal_refuses_all_later_writes_within_byte_bound(journal, monkeypatch, fault):
    monkeypatch.setattr(journal, "time", SimpleNamespace(monotonic=lambda: 1.0))
    control = io.BytesIO(); journal.QualificationJournal(control).record("control")
    cap = len(control.getvalue()); monkeypatch.setattr(journal, "MAX_JOURNAL_BYTES", cap)
    class Broken(io.BytesIO):
        def write(self, raw):
            return super().write(raw[:-1] if fault == "short_write" else raw)
        def flush(self):
            if fault == "flush": raise OSError("injected flush failure")
            super().flush()
    stream = Broken(); plugin = journal.QualificationJournal(stream)
    with pytest.raises(OSError): plugin.record("control")
    first = stream.getvalue()
    for _ in range(3):
        with pytest.raises(RuntimeError, match="already failed"):
            plugin.record("control")
    assert stream.getvalue() == first
    assert len(first) <= cap and plugin.failed


@pytest.mark.parametrize("exitstatus", [0, 1, 2, 3, 4, 5])
def test_runner_preserves_pytest_exit_status(journal, tmp_path, monkeypatch, exitstatus):
    path = tmp_path / "progress.jsonl"
    def main(args, plugins):
        assert args == ["-q", "fixed.py"] and len(plugins) == 1
        plugins[0].record("control")
        assert len(path.read_text().splitlines()) == 1  # Visible before runner exit.
        return exitstatus
    monkeypatch.setattr(journal.pytest, "main", main)
    assert journal.run_pytest(path, ["-q", "fixed.py"]) == exitstatus


def test_runner_never_overwrites_previous_evidence(journal, tmp_path, monkeypatch):
    path = tmp_path / "progress.jsonl"; path.write_bytes(b"earlier evidence\n")
    monkeypatch.setattr(journal.pytest, "main", lambda *a, **k: pytest.fail("Must not launch"))
    with pytest.raises(FileExistsError): journal.run_pytest(path, [])
    assert path.read_bytes() == b"earlier evidence\n"


def test_even_caught_journal_error_cannot_return_success(journal, tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "MAX_JOURNAL_BYTES", 0)
    def main(args, plugins):
        with pytest.raises(RuntimeError, match="bound exceeded"):
            plugins[0].record("control")
        return 0
    monkeypatch.setattr(journal.pytest, "main", main)
    with pytest.raises(RuntimeError, match="journal failed"):
        journal.run_pytest(tmp_path / "progress.jsonl", [])


@pytest.mark.parametrize("fault", ["open", "close"])
def test_runner_open_and_close_errors_cannot_return_success(journal, monkeypatch, fault):
    launched = []
    class Context:
        def __enter__(self):
            if fault == "open": raise PermissionError("injected open failure")
            return io.BytesIO()
        def __exit__(self, *args):
            raise OSError("injected close failure")
    def open_file(mode, buffering):
        assert mode == "xb" and buffering == 0
        return Context()
    monkeypatch.setattr(journal, "Path", lambda path: SimpleNamespace(open=open_file))
    monkeypatch.setattr(journal.pytest, "main", lambda *a, **k: launched.append(True) or 0)
    with pytest.raises(OSError, match="injected " + fault + " failure"):
        journal.run_pytest("owned-diagnostic-path", [])
    assert launched == ([] if fault == "open" else [True])


def test_real_inprocess_pytest_reports_setup_call_and_teardown_failures(journal, tmp_path, monkeypatch):
    # These synthetic tests exercise pluggy/pytest itself, never a subprocess,
    # production operation, native image, ptrace request or strace command.
    sample = tmp_path / "test_journal_sample.py"
    sample.write_text('''import pytest
@pytest.fixture
def bad_setup():
    raise RuntimeError("PRIVATE_SETUP")
@pytest.fixture
def bad_teardown():
    yield
    raise RuntimeError("PRIVATE_TEARDOWN")
def test_pass():
    pass
def test_setup(bad_setup):
    raise AssertionError("Must never run")
def test_call():
    raise RuntimeError("PRIVATE_CALL")
def test_teardown(bad_teardown):
    pass
''')
    config = tmp_path / "pytest.ini"; config.write_text("[pytest]\n")
    path = tmp_path / "progress.jsonl"
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    status = journal.run_pytest(path, ["-q", "-p", "no:cacheprovider", "-c", str(config),
                                     "--confcutdir=" + str(tmp_path), str(sample)])
    assert status == 1
    raw = path.read_bytes(); events = [json.loads(line) for line in raw.splitlines()]
    assert b"PRIVATE" not in raw
    assert events[0]["event"] == "session_start"
    assert events[1]["event"] == "collection_finish" and events[1]["collected"] == 4
    assert events[-1]["event"] == "session_finish" and events[-1]["exitstatus"] == 1
    expected = {"test_pass": [("setup", "passed"), ("call", "passed"), ("teardown", "passed")],
                "test_setup": [("setup", "failed"), ("teardown", "passed")],
                "test_call": [("setup", "passed"), ("call", "failed"), ("teardown", "passed")],
                "test_teardown": [("setup", "passed"), ("call", "passed"), ("teardown", "failed")]}
    for name, phases in expected.items():
        own = [e for e in events if e.get("nodeid", "").endswith("::" + name)]
        assert [e["event"] for e in own] == ["item_start", *[
            event for _ in phases for event in ("phase_start", "phase_finish")], "item_finish"]
        assert [(e["phase"], e["outcome"]) for e in own if e["event"] == "phase_finish"] == phases
        assert all(e["duration_seconds"] >= 0 for e in own if e["event"] == "phase_finish")
    assert [e["sequence"] for e in events] == list(range(len(events)))


def supervisor_tree():
    return ast.parse((ROOT / SUPERVISOR).read_text())


def test_supervisor_bootstrap_passes_exact_args_and_exclusive_journal(journal, monkeypatch):
    qualify = next(n for n in supervisor_tree().body if isinstance(n, ast.FunctionDef) and n.name == "qualify")
    bootstrap = next(n.value for n in ast.walk(qualify) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "bootstrap" for t in n.targets))
    seen = []
    def run_pytest(path, args):
        seen.append((path, args)); return 3
    monkeypatch.setitem(sys.modules, "qualification_journal", SimpleNamespace(run_pytest=run_pytest))
    monkeypatch.setattr(sys, "argv", ["-c", "/reviewed/root", "/evidence/progress.jsonl", "-q", "fixed.py"])
    monkeypatch.setattr(sys, "path", list(sys.path))
    with pytest.raises(SystemExit) as exit:
        exec(ast.literal_eval(bootstrap), {})
    assert exit.value.code == 3
    assert seen == [("/evidence/progress.jsonl", ["-q", "fixed.py"])]
    assert sys.path[:2] == ["/reviewed/root", "/reviewed/root/tests/fixtures/source_facts"]


def test_journal_is_pinned_and_only_scoped_artifact_is_retained():
    harness = next(n.value for n in supervisor_tree().body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "HARNESS" for t in n.targets))
    assert JOURNAL in ast.literal_eval(harness) and len(ast.literal_eval(harness)) == 6
    job = yaml.safe_load((ROOT / ".github/workflows/source-facts-ci.yml").read_text())["jobs"]["linux-source-facts"]
    pin = next(s for s in job["steps"] if s.get("name") == "Pin exact same-job source, images, probe and trace tool")
    assert repr(JOURNAL) in pin["run"]
    upload = next(s for s in job["steps"] if s.get("name") == "Retain scoped qualification evidence and candidate distributions")
    assert "${{ env.EVIDENCE }}/full176/progress.jsonl" in upload["with"]["path"].splitlines()
    pure = next(s for s in job["steps"] if s.get("name") == "Pure host and delivery-verifier regressions")
    assert "tests/unit/test_source_fact_journal_contract.py" in pure["run"]
    assert "tests/unit/test_source_fact_ci_contract.py" in pure["run"]


def test_versioned_wall_allowance_and_predeclared_costs():
    tree = supervisor_tree()
    constants = {t.id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name) and t.id in {
                     "FULL_BUDGET_VERSION", "FULL_WALL_SECONDS", "POLLING_BUDGET_VERSION",
                     "POLLING_WALL_SECONDS", "FULL_COST_INVENTORY"}}
    assert constants["FULL_BUDGET_VERSION"] == "source-facts-176-v2"
    assert constants["FULL_WALL_SECONDS"] == 600
    assert constants["POLLING_BUDGET_VERSION"] == "source-facts-polling-v1"
    assert constants["POLLING_WALL_SECONDS"] == 240
    inventory = constants["FULL_COST_INVENTORY"]
    assert inventory["deliberate_wait_seconds"] == {
        "transport_timeouts": 70, "whole_operation": 60, "cleanup_confirmation": 9}
    assert inventory["fresh_cli_bootstrap_processes"] == 171
    assert inventory["syscall_audit_controls"] == {"count": 2, "outer_seconds_each": 34}


def test_bootstrap_inventory_matches_fixed_suite_fixture_use():
    instances = 0
    for suffix in ("runtime_boundaries", "lifecycle_completion", "wire_receipt_gaps"):
        tree = ast.parse((ROOT / ("tests/unit/test_source_fact_" + suffix + ".py")).read_text())
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try: values[node.targets[0].id] = ast.literal_eval(node.value)
                except (ValueError, TypeError): pass
            if (not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_")
                    or "portable_project" not in {a.arg for a in node.args.args}):
                continue
            variants = 1
            for decorator in node.decorator_list:
                if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == "parametrize"):
                    argument = decorator.args[1]
                    variants *= len(values[argument.id] if isinstance(argument, ast.Name) else ast.literal_eval(argument))
            instances += variants
    fixture_tree = ast.parse((ROOT / "tests/unit/test_portable_local_workflow.py").read_text())
    fixture = next(n for n in fixture_tree.body if isinstance(n, ast.FunctionDef) and n.name == "portable_project")
    launches = [n for n in ast.walk(fixture) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "command"]
    assert instances == 57 and len(launches) == 3 and instances * len(launches) == 171


def test_journal_never_supplies_qualification_counts():
    tree = supervisor_tree()
    qualify = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "qualify")
    source = ast.unparse(qualify)
    assert "ET.parse(report)" in source and "required_run_variants" in source
    assert "not timed_out" in source and "not errors" in source and "not leftover" in source
    assert source.count("progress.jsonl") == 1  # Only an output argument, never parsed as proof.
    assignments = {target.id: node.value for node in ast.walk(qualify) if isinstance(node, ast.Assign)
                   for target in node.targets if isinstance(target, ast.Name)}
    assert ast.unparse(assignments["wall_budget"]) == (
        "POLLING_WALL_SECONDS if polling_correction_only else FULL_WALL_SECONDS")
    assert ast.unparse(assignments["end"]) == "began + wall_budget"
    summary = {ast.literal_eval(key): value for key, value in zip(assignments["summary"].keys, assignments["summary"].values)}
    assert ast.unparse(summary["harness_wall_seconds"]) == "wall_budget"
    assert ast.unparse(summary["harness_budget_version"]) == "budget_version"
    assert ast.unparse(summary["predeclared_cost_inventory"]) == (
        "None if polling_correction_only else FULL_COST_INVENTORY")
