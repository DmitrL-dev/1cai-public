"""Worker polling gaps are persisted in the profile and reported by status."""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import rentgen_core as api
from rentgen_core import observer as implementation
from rentgen_core.local import LocalRuntime
from rentgen_core.observer import Observer
from observer_kill_support import killed_inside_write

T0 = datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)
NOT_RECORDED = {
    "interval_seconds": None,
    "gap_count": None,
    "clock_regressions": None,
    "last_gap": None,
}


@pytest.fixture
def observer(tmp_path):
    principal = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    project = registry.register(
        principal, source_root=source, state_root=tmp_path / "state", display_name="A"
    )
    result = Observer(
        LocalRuntime(registry.path),
        principal,
        project.project_id,
        tmp_path / "observer",
        poll_interval=60,
    )
    result.initialize()
    return result


@pytest.fixture
def clock(monkeypatch):
    now = [T0]
    monkeypatch.setattr(implementation, "_utcnow", lambda: now[0])
    return now


def checked(observer, value):
    with sqlite3.connect(observer.database) as db:
        db.execute("UPDATE meta SET checked_at=? WHERE id=1", (value.isoformat(),))
    db.close()


def execute(observer, *statements):
    with sqlite3.connect(observer.database) as db:
        for statement in statements:
            db.execute(statement)
    db.close()


def test_missed_polls_are_counted_and_reported_by_status(observer, clock):
    assert observer.status()["polling"] == {
        **NOT_RECORDED,
        "idle_seconds": None,
        "on_schedule": False,
    }
    observer._record_poll()  # First worker cycle: no previous check.
    checked(observer, T0)
    clock[0] = T0 + timedelta(seconds=119.9)
    observer._record_poll()
    assert observer.status()["polling"] == {
        "interval_seconds": 60,
        "gap_count": 0,
        "clock_regressions": 0,
        "last_gap": None,
        "idle_seconds": 119,
        "on_schedule": True,
    }
    clock[0] = T0 + timedelta(seconds=120)
    observer._record_poll()
    gap = {
        "after": T0.isoformat(),
        "before": (T0 + timedelta(seconds=120)).isoformat(),
        "idle_seconds": 120,
    }
    status = observer.status()["polling"]
    assert status["gap_count"] == 1
    assert status["last_gap"] == gap
    assert (status["idle_seconds"], status["on_schedule"]) == (120, False)
    restarted = Observer(
        observer.runtime, observer.principal, observer.project_id, observer.profile
    )
    assert restarted.status()["polling"] == status
    checked(observer, T0 + timedelta(seconds=300))
    clock[0] = T0 + timedelta(seconds=299)
    observer._record_poll()
    status = observer.status()["polling"]
    assert (status["gap_count"], status["clock_regressions"]) == (1, 1)
    assert status["last_gap"] == gap
    assert (status["idle_seconds"], status["on_schedule"]) == (None, False)


def test_gap_counters_saturate_and_interval_is_bounded(observer, clock):
    checked(observer, T0)
    clock[0] = T0 + timedelta(days=3)
    observer._record_poll()
    execute(
        observer,
        f"UPDATE polling SET gap_count={implementation.POLL_COUNTER_MAX},"
        f"clock_regressions={implementation.POLL_COUNTER_MAX}",
    )
    observer._record_poll()
    checked(observer, T0 + timedelta(days=4))
    observer._record_poll()
    status = observer.status()["polling"]
    assert status["gap_count"] == status["clock_regressions"] == 1_000_000
    assert status["last_gap"]["idle_seconds"] == 3 * 86400
    for invalid in (4, 86401, True, "60", 60.0):
        with pytest.raises(api.CoreError) as error:
            Observer(
                observer.runtime,
                observer.principal,
                observer.project_id,
                observer.profile,
                poll_interval=invalid,
            )
        assert error.value.code == "INVALID_ARGUMENT"


@pytest.mark.parametrize(
    "damage",
    [
        "UPDATE meta SET checked_at='2026-10-16T08:00:00'",
        "UPDATE meta SET checked_at='yesterday'",
        "UPDATE polling SET last_gap_seconds=last_gap_seconds+1",
        "UPDATE polling SET last_gap_after=NULL",
        "UPDATE polling SET gap_count=0",
        "UPDATE polling SET interval_seconds=60.5",
        "ALTER TABLE polling ADD COLUMN extra TEXT",
    ],
    ids=["naive", "malformed", "duration", "partial", "count", "type", "columns"],
)
def test_invalid_polling_state_fails_closed(observer, clock, damage):
    checked(observer, T0)
    clock[0] = T0 + timedelta(seconds=600)
    observer._record_poll()
    execute(observer, damage)
    for operation in (observer.status, observer._record_poll):
        with pytest.raises(api.CoreError) as error:
            operation()
        assert error.value.code == "OBSERVER_POLLING_INVALID"


def test_status_without_worker_interval_is_not_recorded(observer, clock):
    checked(observer, T0)
    clock[0] = T0 + timedelta(seconds=30)
    assert observer.status()["polling"] == {
        **NOT_RECORDED,
        "idle_seconds": 30,
        "on_schedule": False,
    }


def test_killed_worker_inside_polling_write_rolls_back(observer, tmp_path):
    """A real child is killed inside its open polling transaction."""
    old = datetime.now(timezone.utc) - timedelta(hours=1)
    checked(observer, old)
    code = """
import sys
from pathlib import Path
import rentgen_core as api
from rentgen_core.local import LocalRuntime
from rentgen_core.observer import Observer
registry, project, profile = sys.argv[1:-2]
Observer(LocalRuntime(Path(registry)), api.Principal("owner", "local_os"),
         project, Path(profile), poll_interval=60)._tick()
"""
    with killed_inside_write(
        code,
        observer.runtime.registry_path,
        observer.project_id,
        observer.profile,
        boundary="polling_written",
        ready=tmp_path / "ready",
    ):
        # The uncommitted gap is invisible to a concurrent reader.
        assert observer.status()["polling"]["interval_seconds"] is None
    with sqlite3.connect(observer.database) as db:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert (
            db.execute("SELECT name FROM sqlite_master WHERE name='polling'").fetchone()
            is None
        )
        assert db.execute("SELECT checked_at FROM meta").fetchone() == (
            old.isoformat(),
        )
    db.close()
    observer._record_poll()
    polling = observer.status()["polling"]
    assert polling["gap_count"] == 1
    assert polling["last_gap"]["after"] == old.isoformat()
    assert polling["last_gap"]["idle_seconds"] >= 3600


def test_only_cli_run_declares_and_records_its_interval(
    observer, monkeypatch, capsys
):
    from contextlib import nullcontext
    import json

    import rentgen_core.observer_cli as cli

    def stop(ctx):
        raise api.CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "Test stop after poll")

    monkeypatch.setattr(cli, "LocalRuntime", lambda *args: observer.runtime)
    monkeypatch.setattr(cli, "current_windows_principal", lambda: observer.principal)
    monkeypatch.setattr(cli.Observer, "locked", lambda self: nullcontext())
    monkeypatch.setattr(implementation, "probe_sources", stop)
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: pytest.fail("No sleep"))
    common = [
        "--registry",
        str(observer.runtime.registry_path),
        "--project",
        observer.project_id,
        "--profile",
        str(observer.profile),
    ]

    def status():
        assert cli.main(["status", *common, "--interval", "9"]) == 0
        return json.loads(capsys.readouterr().out)["result"]["polling"]

    assert status()["interval_seconds"] is None
    code = cli.main(
        ["run", *common, "--scanner", "unused", "--interval", "7", "--cycles", "1"]
    )
    assert code == 2
    assert "CAPTURE_PLATFORM_UNSUPPORTED" in capsys.readouterr().out
    polling = status()
    assert (polling["interval_seconds"], polling["gap_count"]) == (7, 0)
    assert polling["on_schedule"] is True
