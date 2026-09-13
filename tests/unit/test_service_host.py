"""Foreground service lifetime contracts, independent of SCM and native 1C."""

from threading import Event, Thread

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.git_watcher import (
    GitWatcherScheduler,
    NotificationOutbox,
    SchedulerJournal,
)


class Watcher:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0

    def tick(self):
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_explicit_scheduler_retry_policy_propagates_unknown_core_error(tmp_path):
    error = CoreError("GIT_WATCHER_CONTEXT", "bad analyzer report")
    watcher = Watcher([error])
    journal = SchedulerJournal(tmp_path / "scheduler.json")
    scheduler = GitWatcherScheduler(
        watcher, max_cycles=2, journal=journal, retry_codes={"GIT_PROBE_FAILED"}
    )
    with pytest.raises(CoreError) as raised:
        scheduler.run()
    assert raised.value is error
    assert watcher.calls == 1
    assert journal.read()["event"] == {
        "status": "fatal",
        "code": "GIT_WATCHER_CONTEXT",
    }


def host_class():
    from rentgen_core.service_host import WindowsServiceHost

    return WindowsServiceHost


def test_stop_before_start_cleans_up_without_tick(tmp_path):
    watcher = Watcher([])
    cleanup = []
    journal = SchedulerJournal(tmp_path / "scheduler.json")
    host = host_class()(
        GitWatcherScheduler(watcher, journal=journal),
        max_cycles=3,
        cleanup=lambda: cleanup.append("closed"),
    )
    host.stop()
    host.cancel()
    assert host.run() == []
    assert watcher.calls == 0
    assert cleanup == ["closed"]
    assert journal.read()["phase"] == "idle"
    with pytest.raises(CoreError, match="already"):
        host.run()
    assert cleanup == ["closed"]


def test_stop_interrupts_backoff_and_keeps_scheduler_configuration(tmp_path):
    watcher = Watcher([CoreError("GIT_PROBE_FAILED", "temporary")])
    journal = SchedulerJournal(tmp_path / "scheduler.json")

    def original_sleep(seconds):
        pass

    def original_stop():
        return False

    scheduler = GitWatcherScheduler(
        watcher,
        interval=5,
        max_cycles=2,
        sleep=original_sleep,
        should_stop=original_stop,
        journal=journal,
    )
    cleanup = []
    host = host_class()(scheduler, cleanup=lambda: cleanup.append("closed"))
    entered_wait = Event()
    wait = host._stop_event.wait
    delays = []

    def observed_wait(seconds):
        delays.append(seconds)
        entered_wait.set()
        return wait(seconds)

    host._stop_event.wait = observed_wait
    results, errors = [], []

    def run():
        try:
            results.append(host.run())
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=run)
    thread.start()
    try:
        assert entered_wait.wait(2)
        with pytest.raises(CoreError) as raised:
            host.run()
        assert raised.value.code == "SERVICE_HOST_ALREADY_RUN"
        assert cleanup == []
        host.cancel()
        thread.join(2)
        assert not thread.is_alive()
    finally:
        host.stop()
        thread.join(2)
    assert errors == []
    assert results == [[{"status": "error", "code": "GIT_PROBE_FAILED", "attempt": 1}]]
    assert delays == [10]
    assert watcher.calls == 1
    assert cleanup == ["closed"]
    assert journal.read()["phase"] == "idle"
    assert scheduler.sleep is original_sleep
    assert scheduler.should_stop is original_stop
    assert scheduler.max_cycles == 2


@pytest.mark.parametrize(
    "code", ["PROJECT_FORBIDDEN", "GIT_WATCHER_CONTEXT", "NEW_ERROR"]
)
def test_fatal_error_survives_cleanup_failure(code, tmp_path):
    error = CoreError(code, "original")
    watcher = Watcher([error])
    journal = SchedulerJournal(tmp_path / "scheduler.json")
    cleanup_calls = []

    def cleanup():
        cleanup_calls.append(1)
        raise RuntimeError("cleanup failed")

    host = host_class()(GitWatcherScheduler(watcher, journal=journal), cleanup=cleanup)
    with pytest.raises(CoreError) as raised:
        host.run()
    assert raised.value is error
    assert "cleanup failed" in " ".join(error.__notes__)
    assert cleanup_calls == [1]
    assert watcher.calls == 1
    assert journal.read()["event"] == {"status": "fatal", "code": code}


def test_host_uses_smaller_cycle_budget_and_preserves_external_stop():
    watcher = Watcher([{"status": "unchanged"}] * 2)
    scheduler = GitWatcherScheduler(watcher, max_cycles=1)
    assert host_class()(scheduler, max_cycles=2).run() == [{"status": "unchanged"}]
    assert watcher.calls == 1
    scheduler.should_stop = lambda: True
    assert host_class()(scheduler).run() == []
    assert watcher.calls == 1


@pytest.mark.parametrize("limit", [None, False, 0, 10001])
def test_host_rejects_unbounded_or_invalid_budget(limit):
    with pytest.raises(CoreError) as raised:
        host_class()(GitWatcherScheduler(Watcher([])), max_cycles=limit)
    assert raised.value.code == "SERVICE_HOST_INVALID"


def test_host_caps_cycles_and_backoff_and_resets_delay_after_success():
    watcher = Watcher(
        [
            CoreError("GIT_PROBE_FAILED", "first"),
            CoreError("GIT_HEAD_CHANGED", "second"),
            {"status": "unchanged"},
            {"status": "unchanged"},
        ]
    )
    host = host_class()(
        GitWatcherScheduler(watcher, interval=5, max_backoff=15), max_cycles=4
    )
    delays = []
    host._stop_event.wait = delays.append
    assert len(host.run()) == 4
    assert watcher.calls == 4
    assert delays == [10, 15, 5]


def test_stop_during_tick_finishes_that_tick_without_another_cycle():
    host = None

    class StoppingWatcher:
        def tick(self):
            host.stop()
            return {"status": "unchanged"}

    host = host_class()(GitWatcherScheduler(StoppingWatcher()))
    assert host.run() == [{"status": "unchanged"}]


def test_explicit_empty_retry_policy_is_preserved_by_host():
    error = CoreError("GIT_PROBE_FAILED", "no retry authorized")
    watcher = Watcher([error])
    host = host_class()(GitWatcherScheduler(watcher, retry_codes=set()))
    with pytest.raises(CoreError) as raised:
        host.run()
    assert raised.value is error
    assert watcher.calls == 1


def test_host_propagates_cleanup_failure_after_success():
    failure = RuntimeError("cleanup failed")

    def cleanup():
        raise failure

    host = host_class()(
        GitWatcherScheduler(Watcher([{"status": "unchanged"}]), max_cycles=1),
        cleanup=cleanup,
    )
    with pytest.raises(RuntimeError) as raised:
        host.run()
    assert raised.value is failure


def test_cleanup_failure_is_not_suppressed_by_outer_exception():
    failure = RuntimeError("cleanup failed")
    host = host_class()(
        GitWatcherScheduler(Watcher([{"status": "unchanged"}]), max_cycles=1),
        cleanup=lambda: (_ for _ in ()).throw(failure),
    )
    try:
        raise ValueError("outer")
    except ValueError:
        with pytest.raises(RuntimeError) as raised:
            host.run()
    assert raised.value is failure


def test_known_fatal_code_cannot_be_enabled_by_retry_policy():
    error = CoreError("PROJECT_FORBIDDEN", "permission denied")
    scheduler = GitWatcherScheduler(
        Watcher([error]), retry_codes={error.code}, max_cycles=2
    )
    with pytest.raises(CoreError) as raised:
        scheduler.run()
    assert raised.value is error


@pytest.mark.parametrize(
    "codes", ["GIT_PROBE_FAILED", ["GIT_PROBE_FAILED"], {None}, {""}]
)
def test_scheduler_validates_explicit_retry_policy(codes):
    with pytest.raises(CoreError) as raised:
        GitWatcherScheduler(Watcher([]), retry_codes=codes)
    assert raised.value.code == "GIT_WATCHER_INVALID"


@pytest.mark.parametrize("method", ["record", "read"])
def test_fatal_error_survives_scheduler_journal_failure(tmp_path, monkeypatch, method):
    error = CoreError("PROJECT_FORBIDDEN", "original denial")
    journal = SchedulerJournal(tmp_path / "scheduler.json")

    def broken_journal(*args, **kwargs):
        raise OSError("journal unavailable")

    monkeypatch.setattr(journal, method, broken_journal)
    host = host_class()(GitWatcherScheduler(Watcher([error]), journal=journal))
    with pytest.raises(CoreError) as raised:
        host.run()
    assert raised.value is error
    if method == "record":
        assert "journal unavailable" in " ".join(error.__notes__)


def test_fatal_journal_failure_still_enqueues_outbox_and_requires_recovery(
    tmp_path, monkeypatch
):
    error = CoreError("PROJECT_FORBIDDEN", "original denial")
    journal = SchedulerJournal(tmp_path / "scheduler.json")
    outbox = NotificationOutbox(tmp_path / "outbox.json")

    def broken_record(*args, **kwargs):
        raise OSError("journal unavailable")

    monkeypatch.setattr(journal, "record", broken_record)
    scheduler = GitWatcherScheduler(
        Watcher([error]), journal=journal, outbox=outbox, max_cycles=1
    )
    with pytest.raises(CoreError) as raised:
        scheduler.run()
    assert raised.value is error
    assert outbox.peek()[0]["event"] == {
        "status": "fatal",
        "code": "PROJECT_FORBIDDEN",
    }
    assert journal.read()["phase"] == "running"
