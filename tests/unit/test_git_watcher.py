"""Bounded Git watcher orchestration keeps analysis tied to one committed HEAD."""

import json
import os
import subprocess

import pytest

import rentgen_core as api
import rentgen_core.git_watcher as implementation
from rentgen_core.errors import CoreError
from rentgen_core.git_observer import Finding, FindingReport, GitObservation
from rentgen_core.local import LocalRuntime
from rentgen_core.observer import Observer

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows observer lock")


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


@pytest.fixture
def workspace(tmp_path):
    principal = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "--initial-branch=main")
    git(source, "config", "user.name", "Watcher test")
    git(source, "config", "user.email", "watcher@example.invalid")
    (source / "Module.bsl").write_text("baseline\n", encoding="utf-8")
    git(source, "add", "Module.bsl")
    git(source, "commit", "-m", "baseline")
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    project = registry.register(
        principal, source_root=source, state_root=tmp_path / "state", display_name="A"
    )
    observer = Observer(
        LocalRuntime(registry.path),
        principal,
        project.project_id,
        tmp_path / "observer",
    )
    observer.initialize()
    return source, observer


def report(observer, observation, *, profile="analyzer-v1", scope="whole-repository"):
    return FindingReport(
        observation,
        profile,
        scope,
        True,
        (Finding("rule", "Module.bsl", "module", "message", 1),),
    )


def test_tick_analyzes_new_commit_once_and_reuses_durable_state(workspace):
    source, observer = workspace
    calls = []

    def analyzer(observation):
        calls.append(observation)
        return report(observer, observation)

    watcher = implementation.GitWatcher(observer, analyzer)
    first = watcher.tick()
    assert first["status"] == "analyzed"
    assert first["observation"]["commit"] == git(source, "rev-parse", "HEAD")
    assert len(calls) == 1

    unchanged = watcher.tick()
    assert unchanged["status"] == "unchanged"
    assert unchanged["commit"] == first["commit"]
    assert len(calls) == 1

    (source / "Module.bsl").write_text("next\n", encoding="utf-8")
    git(source, "add", "Module.bsl")
    git(source, "commit", "-m", "next")
    next_result = watcher.tick()
    assert next_result["status"] == "analyzed"
    assert next_result["commit"] != first["commit"]
    assert len(calls) == 2


def test_analyzer_failure_does_not_mark_commit_processed(workspace):
    _, observer = workspace
    calls = 0

    def analyzer(observation):
        nonlocal calls
        calls += 1
        raise RuntimeError("analyzer unavailable")

    watcher = implementation.GitWatcher(observer, analyzer)
    with pytest.raises(RuntimeError):
        watcher.tick()
    with pytest.raises(RuntimeError):
        watcher.tick()
    assert calls == 2
    assert observer.findings_status()["state"] is None


def test_report_must_bind_exact_observation_and_context(workspace):
    source, observer = workspace
    observation = implementation.observe_git(source)

    def wrong_observation(_):
        return report(
            observer,
            GitObservation(observation.repository, "f" * 40, observation.ref),
        )

    with pytest.raises(CoreError) as error:
        implementation.GitWatcher(observer, wrong_observation).tick()
    assert error.value.code == "GIT_WATCHER_CONTEXT"

    def wrong_profile(_):
        return report(observer, observation, profile="other")

    with pytest.raises(CoreError) as error:
        implementation.GitWatcher(observer, wrong_profile).tick()
    assert error.value.code == "GIT_WATCHER_CONTEXT"


def test_head_change_after_analysis_is_not_recorded(workspace, monkeypatch):
    source, observer = workspace
    first = implementation.observe_git(source)
    changed = GitObservation(first.repository, "f" * 40, first.ref)
    observations = iter((first, changed))
    monkeypatch.setattr(implementation, "observe_git", lambda _: next(observations))

    with pytest.raises(CoreError) as error:
        implementation.GitWatcher(
            observer, lambda value: report(observer, value)
        ).tick()
    assert error.value.code == "GIT_HEAD_CHANGED"
    assert observer.findings_status()["state"] is None


def test_history_rewrite_is_rejected_before_analyzer(workspace):
    source, observer = workspace
    calls = []

    def analyzer(observation):
        calls.append(observation)
        return report(observer, observation)

    watcher = implementation.GitWatcher(observer, analyzer)
    first = watcher.tick()

    git(source, "checkout", "--orphan", "rewrite")
    (source / "Module.bsl").unlink()
    (source / "Rewrite.bsl").write_text("rewritten\n", encoding="utf-8")
    git(source, "add", "-A")
    git(source, "commit", "-m", "rewrite")

    with pytest.raises(CoreError) as error:
        watcher.tick()

    assert error.value.code == "GIT_HISTORY_REWRITE"
    assert len(calls) == 1
    state = observer.findings_status(limit=1)["state"]
    assert state["report"]["observation"]["commit"] == first["commit"]


def test_dirty_repository_and_foreign_repository_fail_before_analyzer(
    workspace, tmp_path
):
    source, observer = workspace
    (source / "Module.bsl").write_text("dirty\n", encoding="utf-8")
    called = False

    def analyzer(_):
        nonlocal called
        called = True
        return report(observer, implementation.observe_git(source))

    with pytest.raises(CoreError) as error:
        implementation.GitWatcher(observer, analyzer).tick()
    assert error.value.code == "GIT_TRACKED_DIRTY"
    assert called is False

    foreign = tmp_path / "foreign"
    foreign.mkdir()
    with pytest.raises(CoreError) as error:
        implementation.GitWatcher(observer, analyzer, repository=foreign).tick()
    assert error.value.code == "GIT_WATCHER_CONTEXT"


def test_invalid_constructor_options_are_rejected(workspace):
    _, observer = workspace
    with pytest.raises(CoreError) as error:
        implementation.GitWatcher(observer, None)
    assert error.value.code == "GIT_WATCHER_INVALID"

    with pytest.raises(CoreError) as error:
        implementation.GitWatcher(observer, lambda _: None, profile_id="")
    assert error.value.code == "GIT_WATCHER_INVALID"


class _ScheduledWatcher:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def tick(self):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_scheduler_runs_bounded_loop_with_controlled_backoff():
    watcher = _ScheduledWatcher(
        [
            CoreError("GIT_PROBE_FAILED", "probe"),
            CoreError("GIT_PROBE_FAILED", "probe"),
            {"status": "analyzed"},
            {"status": "unchanged"},
        ]
    )
    sleeps = []
    scheduler = implementation.GitWatcherScheduler(
        watcher, interval=5, max_cycles=4, sleep=sleeps.append
    )

    events = scheduler.run()

    assert watcher.calls == 4
    assert [event["status"] for event in events] == [
        "error",
        "error",
        "analyzed",
        "unchanged",
    ]
    assert [event.get("attempt") for event in events[:2]] == [1, 2]
    assert sleeps == [10, 20, 5]


def test_scheduler_stops_before_tick_and_does_not_swallow_fatal_errors():
    watcher = _ScheduledWatcher([{"status": "never"}])
    scheduler = implementation.GitWatcherScheduler(
        watcher, interval=5, max_cycles=2, should_stop=lambda: True
    )
    assert scheduler.run() == []
    assert watcher.calls == 0

    fatal = _ScheduledWatcher([CoreError("PROJECT_FORBIDDEN", "denied")])
    scheduler = implementation.GitWatcherScheduler(fatal, interval=5, max_cycles=1)
    with pytest.raises(CoreError) as error:
        scheduler.run()
    assert error.value.code == "PROJECT_FORBIDDEN"

    rewritten = _ScheduledWatcher([CoreError("GIT_HISTORY_REWRITE", "rewritten")])
    scheduler = implementation.GitWatcherScheduler(rewritten, interval=5, max_cycles=1)
    with pytest.raises(CoreError) as error:
        scheduler.run()
    assert error.value.code == "GIT_HISTORY_REWRITE"


def test_scheduler_rejects_unbounded_options():
    watcher = _ScheduledWatcher([])
    with pytest.raises(CoreError):
        implementation.GitWatcherScheduler(watcher, interval=4)
    with pytest.raises(CoreError):
        implementation.GitWatcherScheduler(watcher, interval=5, max_cycles=0)


def test_scheduler_backoff_stays_bounded_for_large_failure_count():
    watcher = _ScheduledWatcher([])
    scheduler = implementation.GitWatcherScheduler(
        watcher, interval=5, max_backoff=3600
    )

    assert scheduler._backoff_delay(10_000) == 3600


def test_scheduler_journal_requires_explicit_recovery_after_interruption(tmp_path):
    path = tmp_path / "scheduler.json"
    journal = implementation.SchedulerJournal(path)
    run_id = journal.begin()
    assert journal.read()["phase"] == "running"

    with pytest.raises(CoreError) as error:
        journal.begin()
    assert error.value.code == "GIT_WATCHER_RECOVERY_REQUIRED"

    journal.recover("operator-confirmed-interruption")
    assert journal.read()["phase"] == "recovered"
    next_run = journal.begin()
    journal.record(next_run, 1, 0, {"status": "unchanged"})
    journal.stop(next_run)
    state = journal.read()
    assert state["phase"] == "idle"
    assert state["event"] == {"status": "stopped"}
    assert state["run_id"] != run_id


def test_scheduler_persists_events_and_stops_cleanly(tmp_path):
    journal = implementation.SchedulerJournal(tmp_path / "scheduler.json")
    watcher = _ScheduledWatcher([{"status": "unchanged"}])
    events = implementation.GitWatcherScheduler(
        watcher, interval=5, max_cycles=1, journal=journal
    ).run()

    assert events == [{"status": "unchanged"}]
    state = journal.read()
    assert state["phase"] == "idle"
    assert state["event"] == {"status": "stopped"}
    assert state["cycle"] == 1


def test_scheduler_journal_keeps_fatal_event(tmp_path):
    journal = implementation.SchedulerJournal(tmp_path / "scheduler.json")
    watcher = _ScheduledWatcher([CoreError("PROJECT_FORBIDDEN", "denied")])

    with pytest.raises(CoreError) as error:
        implementation.GitWatcherScheduler(
            watcher, interval=5, max_cycles=1, journal=journal
        ).run()

    assert error.value.code == "PROJECT_FORBIDDEN"
    state = journal.read()
    assert state["phase"] == "idle"
    assert state["event"] == {"status": "fatal", "code": "PROJECT_FORBIDDEN"}


def test_scheduler_does_not_duplicate_controlled_fatal_notification(tmp_path):
    outbox = implementation.NotificationOutbox(tmp_path / "outbox.json")
    watcher = _ScheduledWatcher([CoreError("PROJECT_FORBIDDEN", "denied")])

    with pytest.raises(CoreError) as error:
        implementation.GitWatcherScheduler(
            watcher, interval=5, max_cycles=1, outbox=outbox
        ).run()

    assert error.value.code == "PROJECT_FORBIDDEN"
    assert [item["event"] for item in outbox.peek()] == [
        {"status": "fatal", "code": "PROJECT_FORBIDDEN"}
    ]


def test_scheduler_journal_rejects_corrupt_timestamp(tmp_path):
    journal = implementation.SchedulerJournal(tmp_path / "scheduler.json")
    run_id = journal.begin()
    data = journal.read()
    data["updated_at"] = "2026-09-13T00:00:00"
    journal.path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(CoreError) as error:
        journal.read()
    assert error.value.code == "GIT_WATCHER_RECOVERY_REQUIRED"
    assert run_id == data["run_id"]


def test_notification_outbox_enqueue_peek_and_ack(tmp_path):
    outbox = implementation.NotificationOutbox(tmp_path / "outbox.json")
    notification_id = outbox.enqueue({"status": "analyzed", "commit": "a" * 40})
    assert notification_id == 1
    assert outbox.peek() == [
        {
            "id": 1,
            "event": {"status": "analyzed", "commit": "a" * 40},
            "created_at": outbox.peek()[0]["created_at"],
        }
    ]
    outbox.ack(1)
    assert outbox.peek() == []


def test_notification_outbox_rejects_corruption_and_unknown_ack(tmp_path):
    outbox = implementation.NotificationOutbox(tmp_path / "outbox.json")
    with pytest.raises(CoreError) as error:
        outbox.ack(1)
    assert error.value.code == "GIT_WATCHER_NOTIFICATION_INVALID"
    outbox.path.write_text("{}", encoding="utf-8")
    with pytest.raises(CoreError) as error:
        outbox.peek()
    assert error.value.code == "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED"


def test_scheduler_emits_cycle_event_to_notification_outbox(tmp_path):
    outbox = implementation.NotificationOutbox(tmp_path / "outbox.json")
    watcher = _ScheduledWatcher([{"status": "unchanged"}])
    implementation.GitWatcherScheduler(
        watcher, interval=5, max_cycles=1, outbox=outbox
    ).run()

    assert [item["event"] for item in outbox.peek()] == [{"status": "unchanged"}]
