"""Service adapters use real profile/state/Git, stopping at the source probe.

On POSIX only the Windows lifetime lease is replaced with its authorization
check. These are wiring/failure contracts, not SCM or capture qualification.
Windows capture and unchanged-source behavior have a separate real suite.
"""
from contextlib import contextmanager
from datetime import timedelta
import json
import os
import sqlite3

import pytest

from rentgen_core import local_identity, observer as implementation, service_entry
from rentgen_core.errors import CoreError
from rentgen_core.observer import Observer
from project_access_test_support import grant_membership
from test_git_watcher import git
from test_observer_polling import observer, clock, checked, T0


@pytest.fixture
def service_profile(observer, monkeypatch, tmp_path):
    source = observer._context().source_root
    git(source, "init", "--initial-branch=main")
    git(source, "config", "user.name", "Service polling test")
    git(source, "config", "user.email", "polling@example.invalid")
    git(source, "commit", "--allow-empty", "-m", "baseline")
    scanner = tmp_path / "scanner.exe"
    scanner.touch()
    diagnostics = tmp_path / "diagnostics"
    diagnostics.mkdir()
    monkeypatch.setattr(local_identity, "current_windows_principal", lambda: observer.principal)
    if os.name != "nt":
        @contextmanager
        def authorized_lease(self):
            self._validate(self._context(write=True))
            yield
        monkeypatch.setattr(Observer, "locked", authorized_lease)

    def stop_at_probe(ctx):
        raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "Controlled stop at source probe")
    monkeypatch.setattr(implementation, "probe_sources", stop_at_probe)

    def config(schema, *, trusted=False, interval=60):
        document = {
            "schema": schema, "service_name": "Rentgen.Polling",
            "registry": str(observer.runtime.registry_path),
            "profile": str(observer.profile), "project": observer.project_id,
            "interval_seconds": interval, "max_cycles": 1,
        }
        if schema in (1, 3):
            document["scanner"] = str(scanner)
        if schema in (2, 3):
            document.update(diagnostics_root=str(diagnostics), mode="read-only",
                            trust_registered_source=trusted)
        path = tmp_path / "service.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return service_entry.load_config(path)
    return config


def tick(worker, schema):
    return worker.tick() if schema == 1 else worker.watcher.tick()


@pytest.mark.parametrize("schema,trusted", [(1, False), (3, False), (3, True)])
def test_service_records_gaps_and_clock_regression_across_restart(
    service_profile, observer, clock, schema, trusted,
):
    checked(observer, T0)
    clock[0] = T0 + timedelta(seconds=120)
    worker = service_entry.create_worker(service_profile(schema, trusted=trusted))
    try:
        # Merely constructing an authorized worker is not a completed poll.
        assert observer.status()["polling"]["interval_seconds"] is None
        with pytest.raises(CoreError, match="Controlled stop"):
            tick(worker, schema)
        first = observer.status()["polling"]
        assert first["interval_seconds"] == 60
        assert first["gap_count"] == 1 and first["clock_regressions"] == 0
        assert first["last_gap"] == {
            "after": T0.isoformat(), "before": clock[0].isoformat(), "idle_seconds": 120,
        }
    finally:
        worker.close()
    restarted = service_entry.create_worker(service_profile(schema, trusted=trusted, interval=30))
    try:
        assert observer.status()["polling"] == first
        clock[0] -= timedelta(seconds=1)
        with pytest.raises(CoreError, match="Controlled stop"):
            tick(restarted, schema)
        retained = Observer(observer.runtime, observer.principal, observer.project_id, observer.profile)
        polling = retained.status()["polling"]
        assert polling["interval_seconds"] == 30
        assert polling["gap_count"] == polling["clock_regressions"] == 1
        assert polling["last_gap"] == first["last_gap"]
    finally:
        restarted.close()


@pytest.mark.parametrize("schema,trusted", [(1, False), (3, False), (3, True)])
def test_revocation_prevents_service_poll_record(service_profile, observer, clock, schema, trusted):
    worker = service_entry.create_worker(service_profile(schema, trusted=trusted))
    try:
        ctx = observer._context(write=True)
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            grant_membership(tx, ctx.principal, {"project:read", "project:admin"})
        with pytest.raises(CoreError) as error:
            tick(worker, schema)
        assert error.value.code == "PROJECT_FORBIDDEN"
        with sqlite3.connect(observer.database) as db:
            assert db.execute("SELECT name FROM sqlite_master WHERE name='polling'").fetchone() is None
        db.close()
    finally:
        worker.close()


@pytest.mark.parametrize("trusted", [False, True])
def test_non_capture_git_service_does_not_declare_capture_polls(
    service_profile, observer, clock, trusted,
):
    checked(observer, T0)
    clock[0] = T0 + timedelta(seconds=120)
    worker = service_entry.create_worker(service_profile(2, trusted=trusted))
    try:
        with pytest.raises(CoreError, match="Controlled stop"):
            tick(worker, 2)
        polling = observer.status()["polling"]
        assert polling["interval_seconds"] is None
        assert polling["gap_count"] is None and polling["on_schedule"] is False
    finally:
        worker.close()
