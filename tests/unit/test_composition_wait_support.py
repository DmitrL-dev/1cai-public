"""Deterministic portable diagnostics; no native scanner or SCM needed."""
import json
from threading import Event, Thread

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
