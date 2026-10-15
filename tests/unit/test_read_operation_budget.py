"""Actual POSIX copies/SQLite plus owner controls; no Linux release acceptance."""
from contextlib import contextmanager
from dataclasses import replace
import sqlite3
import os
import sys
from threading import Thread

import pytest

from rentgen_core import _read_operation_budget as accounting
from rentgen_core import _posix_snapshot_session as sessions
from rentgen_core import _posix_source_tree as retained
from rentgen_core.errors import CoreError
from rentgen_core.graph import open_verified_graph
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory
from test_posix_snapshot_session import make_generation, generation
from test_verified_graph_reader import graph

pytestmark = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="Actual POSIX pair budget seams")


def budget(**changes):
    return accounting.ReadOperationBudget(replace(accounting.ReadOperationLimits(), **changes))


def opened(generation, shared, **changes):
    return sessions.open_posix_snapshot_session(**(generation.options | changes), operation_budget=shared)


def test_cumulative_work_is_not_refunded_but_held_leases_are():
    shared = budget(copied_bytes=3, image_bytes=7, source_entries=2)
    shared.charge_copy(2)
    lease = shared.reserve_images(7)
    with pytest.raises(CoreError, match="budget"):
        shared.reserve_images(1)
    with pytest.raises(CoreError, match="not active"):
        shared.close()
    lease.close()
    shared.charge_copy(1)
    with pytest.raises(CoreError, match="budget"):
        shared.charge_copy(1)
    shared.close()
    summary = shared.summary()
    assert summary["cumulative"]["copied_bytes"] == 3
    assert summary["held"]["image_bytes"] == 0 and summary["peaks"]["image_bytes"] == 7
    assert summary["closed"]
    with pytest.raises(CoreError): shared.checkpoint()


def test_owner_thread_reentry_and_close_acknowledgement_are_required(monkeypatch):
    shared = budget()
    owner = object()
    shared.owner_opened(owner)
    failures = []
    def foreign():
        try: shared.owner_closed(owner)
        except CoreError as exc: failures.append(exc.code)
    thread = Thread(target=foreign); thread.start(); thread.join()
    assert failures == ["SNAPSHOT_READ_SESSION_INVALID"]
    actual_pid = os.getpid()
    with monkeypatch.context() as patch:
        patch.setattr(accounting.os, "getpid", lambda: actual_pid + 1)
        with pytest.raises(CoreError, match="not active"): shared.checkpoint()
    with pytest.raises(CoreError): shared.abort()
    shared.owner_closed(owner)
    shared.close()
    reentrant = None
    def cancelled():
        reentrant.checkpoint()
    reentrant = accounting.ReadOperationBudget(cancelled=cancelled)
    with pytest.raises(CoreError, match="not active"): reentrant.checkpoint()
    reentrant.abort()


def test_absolute_deadline_and_cancellation_do_not_prevent_cleanup(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(accounting, "monotonic", lambda: clock[0])
    shared = budget(deadline_seconds=2)
    lease = shared.reserve_images(2)
    clock[0] = 102.0
    with pytest.raises(CoreError) as error: shared.checkpoint()
    assert error.value.code == "SNAPSHOT_READ_DEADLINE_EXCEEDED"
    lease.close(); shared.abort()
    stopped = accounting.ReadOperationBudget(cancelled=lambda: True)
    with pytest.raises(CoreError) as error: stopped.checkpoint()
    assert error.value.code == "REQUEST_CANCELLED"
    stopped.abort()


def test_two_actual_default_generation_owners_share_counters_and_close(generation):
    shared = budget()
    first, second = opened(generation, shared), opened(generation, shared)
    with first, second:
        assert first.entries() == second.entries()
        assert shared.summary()["active_owners"] == 4  # two trees + two SQLite owners
        assert shared.summary()["held"]["descriptors"] > len(first._directories)
        databases = [first._reader._owner._db, second._reader._owner._db]
    shared.close()
    result = shared.summary()
    assert result["closed"] and result["owners_closed"] == 4
    summary = first.validation_summary
    probes = summary["verified_source_files"] + summary["verified_derived_files"] + 2
    assert result["cumulative"]["copied_bytes"] == 2 * (generation.copied + probes)
    assert summary["verified_total_bytes"] == generation.copied
    assert result["cumulative"]["source_entries"] == 6
    assert result["cumulative"]["row_bytes"] == 128 * 1024**2
    assert result["cumulative"]["vm_steps"] == 20_000_000
    assert not any(result["held"].values())
    for db in databases:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"): db.execute("SELECT 1")


def test_combined_copy_refuses_before_crossing_read_and_closes_both(generation, monkeypatch):
    shared = budget(copied_bytes=2 * generation.copied - 1)
    actual = []
    original = retained.Directory.file
    @contextmanager
    def observed(directory, name):
        with original(directory, name) as stream:
            class Stream:
                def fileno(self): return stream.fileno()
                def read(self, size):
                    raw = stream.read(size); actual.append(len(raw)); return raw
            yield Stream()
    monkeypatch.setattr(retained.Directory, "file", observed)
    first, second = opened(generation, shared), opened(generation, shared)
    with pytest.raises(CoreError) as error:
        with first, second: pytest.fail("Combined read cap was bypassed")
    assert error.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED"
    assert sum(actual) <= shared.limits.copied_bytes
    assert first._phase == second._phase == "closed"
    shared.abort()
    assert not any(shared.summary()["held"].values())


@pytest.mark.parametrize("case", ["exact_bound", "concurrent_grow", "zero_byte_grow"])
def test_copy_probe_byte_is_precharged_before_any_actual_read(generation, monkeypatch, case):
    target = generation.path / "manifest.json"
    if case == "zero_byte_grow":
        target.write_bytes(b"")
        shared = budget(copied_bytes=1)
        # Consume the one byte by a genuine prior control read. A zero-sized
        # retained leaf still needs its possible one-byte grow/probe allowance.
        control = generation.root / "prior-control"
        control.write_bytes(b"x")
        shared.charge_copy(1)
        with control.open("rb") as stream:
            prior_bytes = len(stream.read(1))
    else:
        shared = budget(copied_bytes=target.stat().st_size)
        prior_bytes = 0
    reads = []
    original = retained.Directory.file
    @contextmanager
    def observed(directory, name):
        with original(directory, name) as stream:
            class Stream:
                def fileno(self): return stream.fileno()
                def read(self, amount):
                    if name == "manifest.json" and case != "exact_bound":
                        with target.open("ab") as writer:
                            writer.write(b"x")
                    raw = stream.read(amount)
                    reads.append(len(raw))
                    return raw
            yield Stream()
    monkeypatch.setattr(retained.Directory, "file", observed)
    session = opened(generation, shared)
    with pytest.raises(CoreError) as error:
        session.__enter__()
    assert error.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED"
    assert reads == [], "Unreserved bounded read reached the actual retained stream"
    assert prior_bytes + sum(reads) <= shared.limits.copied_bytes
    assert session._phase == "closed"
    shared.abort()


@pytest.mark.parametrize("kind", ["image_bytes", "row_bytes", "vm_steps", "descriptors", "source_entries", "inventory_items"])
def test_joint_envelopes_refuse_second_real_owner_and_cleanup(generation, kind):
    probe = budget()
    with opened(generation, probe): pass
    one = probe.summary()
    values = {"row_bytes": one["cumulative"]["row_bytes"],
              "vm_steps": one["cumulative"]["vm_steps"],
              "source_entries": one["cumulative"]["source_entries"],
              "inventory_items": one["cumulative"]["inventory_items"],
              "image_bytes": one["peaks"]["image_bytes"],
              "descriptors": one["peaks"]["descriptors"]}
    probe.close()
    shared = budget(**{kind: values[kind]})
    first, second = opened(generation, shared), opened(generation, shared)
    with pytest.raises(CoreError) as error:
        with first, second: pytest.fail("Independent side quota bypassed shared cap")
    assert error.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED"
    assert first._phase == second._phase == "closed"
    shared.abort()


def test_manifest_parse_and_second_graph_allocation_are_precharged(generation, monkeypatch):
    shared = budget(image_bytes=len(generation.manifest) + 2)
    monkeypatch.setattr(sessions, "parse_manifest", lambda raw: pytest.fail("Unreserved manifest parse"))
    session = opened(generation, shared)
    with pytest.raises(CoreError, match="budget"): session.__enter__()
    assert session._phase == "closed"
    shared.abort()


def test_native_cursor_and_row_reservations_precede_real_query(graph):
    _, bundle = graph
    shared = budget()
    with open_verified_graph(RentgenGraphReaderFactory(), **bundle(), operation_budget=shared) as reader:
        owner = reader._owner
        shared.limits = replace(shared.limits, cursors=1)
        rows = owner._queries.execute("SELECT * FROM module")
        assert shared.summary()["held"]["cursors"] == 1
        with pytest.raises(CoreError, match="budget"):
            owner._queries.execute("SELECT * FROM module")
        old = shared.limits
        shared.limits = replace(old, image_bytes=shared.summary()["held"]["image_bytes"])
        with pytest.raises(CoreError, match="budget"): rows.fetchone()
        shared.limits = old
        assert not owner._rows and shared.summary()["held"]["cursors"] == 0
    shared.close()


def test_incompatible_graph_factory_never_retries_without_budget(graph):
    _, bundle = graph
    calls = []
    class Old:
        def open_verified(self, *, graph_bytes, manifest_bytes, snapshot, authorize_read, limits):
            calls.append("old"); pytest.fail("Unbudgeted factory was invoked")
    shared = budget()
    with pytest.raises(CoreError) as error:
        open_verified_graph(Old(), **bundle(), operation_budget=shared)
    assert error.value.code == "GRAPH_ADAPTER_UNAVAILABLE" and not calls
    shared.abort()


def test_short_sql_statements_do_not_hide_vm_tails_from_shared_allowance(graph):
    _, bundle = graph
    shared = budget()
    completed = 0
    with pytest.raises(CoreError, match="budget"):
        with open_verified_graph(RentgenGraphReaderFactory(), **bundle(), operation_budget=shared) as reader:
            owner = reader._owner
            before = owner._steps
            assert tuple(owner._queries.execute("SELECT 1").fetchone()) == (1,)
            delta = owner._steps - before
            assert 0 < delta < 1000
            owner._limits = replace(owner._limits, max_vm_steps=owner._steps + 2 * delta)
            for _ in range(2):
                owner._queries.execute("SELECT 1").fetchone()
                completed += 1
    assert completed == 1
    shared.abort()


def test_second_failure_is_preserved_when_first_cleanup_also_fails(generation, monkeypatch):
    shared = budget()
    first, second = opened(generation, shared), opened(generation, shared)
    original = first._factory
    primary = CoreError("PROJECT_FORBIDDEN", "Second owner denied")
    second._authorize_read = lambda: (_ for _ in ()).throw(primary)
    real_close = os.close
    leaked = []
    try:
        with pytest.raises(CoreError) as error:
            with first:
                selected = first._directories[""]._fd
                def close(fd):
                    if fd == selected:
                        leaked.append(fd)
                        raise OSError("injected native close refusal")
                    return real_close(fd)
                monkeypatch.setattr(os, "close", close)
                with second: pytest.fail("Denied second owner entered")
    finally:
        for fd in leaked: real_close(fd)
    assert error.value is primary
    assert first._phase == second._phase == "closed" and original is not None
    # Actual open descriptors do not forge zero-resource acknowledgements.
    assert shared.summary()["active_owners"] > 0
    with pytest.raises(CoreError): shared.close()
