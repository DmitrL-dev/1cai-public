"""Continuous persistence contracts; no SCM or native analyzer."""

import json

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.git_watcher import GitWatcherScheduler, NotificationOutbox, SchedulerJournal

MAX_COUNTER = 2**53 - 1


def write_state(journal, run_id, operation, cycle, failures):
    if operation == "record":
        return journal.record(run_id, cycle, failures, {"status": "unchanged"})
    return getattr(journal, operation)(run_id, cycle, failures)


@pytest.mark.parametrize("operation", ["mark_running", "record", "stop"])
@pytest.mark.parametrize("cycle,failures,schema", [(10000, 0, 1), (10001, 0, 2), (10000, 10001, 2), (MAX_COUNTER, MAX_COUNTER, 2)])
def test_journal_counter_boundary_survives_reopen(tmp_path, operation, cycle, failures, schema):
    path = tmp_path / "journal.json"
    journal = SchedulerJournal(path)
    run_id = journal.begin()
    write_state(journal, run_id, operation, cycle, failures)
    state = SchedulerJournal(path).read()
    assert (state["cycle"], state["failures"], state["schema"]) == (cycle, failures, schema)
    assert state["run_id"] == run_id
    assert state["phase"] == ("idle" if operation == "stop" else "running")
    assert not path.with_name(path.name + ".tmp").exists()


@pytest.mark.parametrize("operation", ["mark_running", "record", "stop"])
@pytest.mark.parametrize("field", ["cycle", "failures"])
@pytest.mark.parametrize("value", [-1, True, 1.0, MAX_COUNTER + 1])
def test_invalid_counter_never_replaces_valid_journal(tmp_path, operation, field, value):
    path = tmp_path / "journal.json"
    journal = SchedulerJournal(path)
    run_id = journal.begin()
    before = path.read_bytes()
    counters = {"cycle": 1, "failures": 0, field: value}
    with pytest.raises(CoreError) as error:
        write_state(journal, run_id, operation, **counters)
    assert error.value.code == "GIT_WATCHER_INVALID"
    assert path.read_bytes() == before
    assert SchedulerJournal(path).read()["run_id"] == run_id


@pytest.mark.parametrize("schema,cycle,failures", [(True, 0, 0), (3, 0, 0), (1, 10001, 0), (2, MAX_COUNTER + 1, 0), (2, 0, MAX_COUNTER + 1), (2, False, 0)])
def test_reader_rejects_invalid_schema_or_counters(tmp_path, schema, cycle, failures):
    path = tmp_path / "journal.json"
    journal = SchedulerJournal(path)
    journal.begin()
    state = journal.read() | {"schema": schema, "cycle": cycle, "failures": failures}
    path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(CoreError) as error:
        SchedulerJournal(path).read()
    assert error.value.code == "GIT_WATCHER_RECOVERY_REQUIRED"


def test_extended_journal_requires_recovery_before_new_run(tmp_path):
    journal = SchedulerJournal(tmp_path / "journal.json")
    run_id = journal.begin()
    journal.record(run_id, 10001, 0, {"status": "unchanged"})
    with pytest.raises(CoreError) as error:
        journal.begin()
    assert error.value.code == "GIT_WATCHER_RECOVERY_REQUIRED"
    journal = SchedulerJournal(journal.path)
    journal.recover("controlled interrupted run")
    recovered = journal.read()
    assert (recovered["schema"], recovered["phase"], recovered["cycle"]) == (2, "recovered", 10001)
    next_id = journal.begin()
    assert next_id != run_id
    assert (journal.read()["schema"], journal.read()["cycle"]) == (1, 0)
    journal.stop(next_id)


def test_continuous_scheduler_passes_ten_thousand_durable_cycles(tmp_path):
    class Watcher:
        calls = 0

        def tick(self):
            self.calls += 1
            return {"status": "unchanged", "number": self.calls}

    watcher = Watcher()
    journal = SchedulerJournal(tmp_path / "journal.json")
    outbox = NotificationOutbox(tmp_path / "outbox.json")
    events = GitWatcherScheduler(
        watcher, interval=5, max_cycles=None,
        should_stop=lambda: watcher.calls == 10002, sleep=lambda _: None,
        journal=journal, outbox=outbox, notify_unchanged=False,
    ).run()
    assert watcher.calls == 10002
    assert len(events) == 1000
    assert (events[0]["number"], events[-1]["number"]) == (9003, 10002)
    state = SchedulerJournal(journal.path).read()
    assert (state["schema"], state["phase"], state["cycle"], state["failures"]) == (2, "idle", 10002, 0)
    assert state["event"] == {"status": "stopped"}
    assert outbox.peek() == []
    assert journal.path.stat().st_size < 1024 * 1024
