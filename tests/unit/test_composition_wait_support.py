"""Deterministic portable diagnostics; no native scanner or SCM needed."""
import json
from threading import Event, Thread

import pytest

from composition_wait_support import wait_diagnostic
from rentgen_core.service_entry import RunResult


def test_timeout_reports_live_worker_without_disclosing_locals(monkeypatch):
    import linecache

    def forbidden_source_lookup(*args, **kwargs):
        raise AssertionError("Diagnostic must not read source lines")

    monkeypatch.setattr(linecache, "getline", forbidden_source_lookup)
    started, entered, finished, release = (Event() for _ in range(4))
    results = []

    def blocked():
        private_local = "PRIVATE_SOURCE_ENVIRONMENT_MESSAGE"
        started.set()
        try:
            release.wait()
        finally:
            finished.set()

    thread = Thread(target=blocked)
    thread.start()
    try:
        assert started.wait(2)
        assert not entered.wait(0)
        raw = wait_diagnostic(thread, started, entered, finished, results)
        data = json.loads(raw)
        assert data['worker_started'] and data['worker_alive']
        assert not data['adapter_entered'] and not data['worker_finished']
        assert data['results'] == []
        assert 1 <= len(data['worker_stack']) <= 8
        assert any(row['function'] == 'blocked' for row in data['worker_stack'])
        assert all(set(row) == {'file', 'function', 'line'} for row in data['worker_stack'])
        assert all('/' not in row['file'] and '\\' not in row['file'] for row in data['worker_stack'])
        assert 'PRIVATE_SOURCE_ENVIRONMENT_MESSAGE' not in raw
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive()


def test_early_failed_result_remains_visible_after_cleanup():
    started, entered, finished = (Event() for _ in range(3))
    results = []

    def failed():
        started.set()
        results.append(RunResult(0, 'SERVICE_WORKER_FAILED',
                                 {'stage': 'factory', 'kind': 'CoreError', 'reason': 'STATE_BUSY'}))
        finished.set()

    thread = Thread(target=failed)
    thread.start()
    thread.join(2)
    assert not thread.is_alive()
    data = json.loads(wait_diagnostic(thread, started, entered, finished, results))
    assert data['worker_finished'] and not data['worker_alive']
    assert not data['adapter_entered'] and data['worker_stack'] == []
    assert data['results'] == [{'cycles': 0, 'error_code': 'SERVICE_WORKER_FAILED',
                              'failure_detail': {'stage': 'factory', 'kind': 'CoreError', 'reason': 'STATE_BUSY'}}]


def test_untrusted_result_fields_are_filtered_and_counts_bounded():
    secret = '/private/PASSWORD_SOURCE_CONTENT'
    result = RunResult(-1, secret, {'stage': secret, 'kind': secret, 'reason': secret,
                                   'message': secret, 'environment': secret})
    flags = [Event() for _ in range(3)]
    raw = wait_diagnostic(Thread(), *flags, [result] * 100)
    data = json.loads(raw)
    assert secret not in raw
    assert len(data['results']) == 3
    assert data['results'][0] == {'cycles': None, 'error_code': 'UNCLASSIFIED',
        'failure_detail': {'stage': 'UNCLASSIFIED', 'kind': 'UNCLASSIFIED', 'reason': 'UNCLASSIFIED'}}
    assert len(raw) < 1500


def _exercise_idle_wait_failure(tmp_path, monkeypatch, phase):
    from contextlib import nullcontext
    from types import SimpleNamespace
    import test_service_composition as composition

    phase_ready, release = Event(), Event()
    created, adapters, threads = [], [], []
    original_thread = composition.Thread

    def start_thread(*args, **kwargs):
        thread = original_thread(*args, **kwargs)
        threads.append(thread)
        return thread

    monkeypatch.setattr(composition, "Thread", start_thread)

    class ControlledEvent(Event):
        def __init__(self):
            super().__init__()
            created.append(self)

        def wait(self, timeout=None):
            if self is created[0]:
                assert timeout == 120
                assert phase_ready.wait(2)
                return False
            return super().wait(timeout)

        def set(self):
            super().set()
            if type(self).__name__ == "ObservableStop":
                release.set()

    module = tmp_path / "Module.bsl"
    module.write_bytes(b"owned test source")
    configured = SimpleNamespace(document={}, path=tmp_path / "config.json")

    def wire(*args, **kwargs):
        adapter = kwargs.get("adapter", composition.FakeAdapter())
        adapters.append(adapter)
        return SimpleNamespace(locked=nullcontext), tmp_path, module, None, adapter

    def run_console(path, *, stop_event):
        private_local = "PRIVATE_CONFIG_SOURCE_EXCEPTION_CONTENT"
        if phase == "factory":
            phase_ready.set()
            return RunResult(0, "SERVICE_WORKER_FAILED",
                             {"stage": "factory", "kind": "CoreError", "reason": "STATE_BUSY"})
        adapters[0].analyze(b"owned", suffix=".bsl", authorize=lambda: None)
        phase_ready.set()
        assert release.wait(2)
        assert stop_event.is_set()
        return RunResult(1)

    monkeypatch.setattr(composition, "Event", ControlledEvent)
    monkeypatch.setattr(composition, "wire", wire)
    monkeypatch.setattr(composition.service_entry, "run_console", run_console)
    with pytest.raises(AssertionError) as raised:
        composition.test_continuous_git_stop_interrupts_idle_wait(
            configured, None, monkeypatch, tmp_path / "scanner.exe", True
        )
    return raised.value, threads[0], release


@pytest.mark.parametrize("phase", ["factory", "active_cycle"])
def test_idle_wait_failure_reports_phase_and_cleanup(tmp_path, monkeypatch, phase):
    error, thread, release = _exercise_idle_wait_failure(tmp_path, monkeypatch, phase)
    assert not thread.is_alive() and release.is_set()
    before = json.loads(str(error).splitlines()[0])
    notes = error.__notes__
    assert len(notes) == 1
    after = json.loads(notes[0].split(": ", 1)[1])
    assert before["worker_started"] and not before["idle_wait_entered"]
    assert after["worker_finished"] and not after["worker_alive"]
    assert not after["idle_wait_entered"] and after["worker_stack"] == []
    assert "PRIVATE_CONFIG_SOURCE_EXCEPTION_CONTENT" not in str(error) + notes[0]
    if phase == "factory":
        assert not before["adapter_entered"]
        assert after["results"] == [{"cycles": 0, "error_code": "SERVICE_WORKER_FAILED",
                                    "failure_detail": {"stage": "factory", "kind": "CoreError", "reason": "STATE_BUSY"}}]
    else:
        assert before["adapter_entered"] and before["worker_alive"]
        assert not before["worker_finished"] and before["results"] == []
        assert 1 <= len(before["worker_stack"]) <= 8
        assert after["results"] == [{"cycles": 1, "error_code": None}]


@pytest.mark.parametrize("point", ["before", "after", "add_note"])
def test_idle_wait_diagnostic_failure_preserves_assertion_and_cleanup(tmp_path, monkeypatch, point):
    from types import SimpleNamespace
    import test_service_composition as composition

    secret = "PRIVATE_DIAGNOSTIC_EXCEPTION_CONTENT"
    original = composition.wait_diagnostic
    calls = []

    def failed_diagnostic(*args, **kwargs):
        calls.append(True)
        if len(calls) == (1 if point == "before" else 2):
            raise RuntimeError(secret)
        return original(*args, **kwargs)

    if point == "add_note":
        class BrokenNote:
            def add_note(self, note):
                raise RuntimeError(secret)
        monkeypatch.setattr(composition, "sys", SimpleNamespace(exception=lambda: BrokenNote()))
    else:
        monkeypatch.setattr(composition, "wait_diagnostic", failed_diagnostic)
    error, thread, release = _exercise_idle_wait_failure(tmp_path, monkeypatch, "active_cycle")
    assert type(error) is AssertionError
    assert not thread.is_alive() and release.is_set()
    assert error.__context__ is None
    before = json.loads(str(error).splitlines()[0])
    notes = getattr(error, "__notes__", [])
    assert secret not in str(error) + " ".join(notes)
    if point == "add_note":
        assert not before["idle_wait_entered"] and notes == []
        return
    assert len(calls) == 2 and len(notes) == 1
    after = json.loads(notes[0].split(": ", 1)[1])
    if point == "before":
        assert before == {"diagnostic_available": False}
        assert after["worker_finished"] and not after["worker_alive"]
    else:
        assert not before["idle_wait_entered"] and before["worker_alive"]
        assert after == {"diagnostic_available": False}
