"""Combined literal-search/comparison transitions over real Rust and HTTP."""
from collections import Counter
from pathlib import Path
import sys
import threading

import pytest

from rentgen_core import gui, rust_input
from test_local_gui import post, prepare, request, running, upload, wait
from test_local_gui_comparison import (
    binding, current, finish as comparison_finish, page,
    poll as comparison_poll, source as comparison_source,
    start as comparison_start, submit,
)
from test_local_gui_search import poll as search_poll, search_wait, source, start
from test_local_gui_source_search import args, files
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Experimental GUI ZIP backend is Linux-only"
)

LATE = "Catalogs/Owner/Ext/M200.bsl"
THREADS = {"search": "rentgen-gui-search", "comparison": "rentgen-gui-comparison",
           "import": "rentgen-gui-analysis"}


class ObservedGate:
    """Observe attempts without replacing the real mutual-exclusion behavior."""

    def __init__(self, lock):
        self.lock = lock
        self.attempted = {name: threading.Event() for name in THREADS.values()}

    def acquire(self, *args, **kwargs):
        event = self.attempted.get(threading.current_thread().name)
        if event is not None:
            event.set()
        return self.lock.acquire(*args, **kwargs)

    def release(self):
        self.lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


class RustProbe:
    """Pause one real import and count live children at each actual launch."""

    def __init__(self, monkeypatch, app, first):
        self.entered, self.proceed = threading.Event(), threading.Event()
        self.children, self.owners = [], []
        self.maximum = 0
        self.guard = threading.Lock()
        self.gate = ObservedGate(app.io_lock)
        monkeypatch.setattr(app, "io_lock", self.gate)
        original_spawn = rust_input.subprocess.Popen
        original_open = rust_input.RustInputSession.open_import

        def spawn(*args, **kwargs):
            with self.guard:
                child = original_spawn(*args, **kwargs)
                self.children.append(child)
                self.owners.append(threading.current_thread().name)
                self.maximum = max(self.maximum, sum(p.poll() is None for p in self.children))
                return child

        def opened(session, *args):
            result = original_open(session, *args)
            if threading.current_thread().name == THREADS[first] and not self.entered.is_set():
                self.entered.set()
                assert self.proceed.wait(10), "Real Rust reader was not released"
            return result

        monkeypatch.setattr(rust_input.subprocess, "Popen", spawn)
        monkeypatch.setattr(rust_input.RustInputSession, "open_import", opened)

    def assert_reaped(self):
        assert self.children and self.maximum == 1
        assert all(child.poll() is not None for child in self.children)


def launch(app, server, kind, job, before, after):
    if kind == "search":
        return start(server, args(job, before))
    comparison = comparison_start(server, job, before)
    code, body, _ = request(server, "/api/comparison-upload?comparison=" + comparison,
                            "PUT", after, {"Content-Type": "application/zip"})
    assert code == 202, body
    return comparison


def worker(app, kind):
    return app.search_worker if kind == "search" else app.comparison_worker


def finish(app, server, kind, selector):
    outcome = search_wait(server, selector) if kind == "search" else comparison_finish(app, server, selector)
    thread = worker(app, kind)
    thread.join(timeout=5)
    assert not thread.is_alive()
    return outcome


def cancel(server, kind, selector):
    payload = selector if kind == "search" else {"comparison": selector}
    code, response = post(server, "/api/" + kind + "-cancel", payload)
    assert code == 200 and response["cancel_requested"] is True


def ready_both(app, server):
    """The 201st module can be disclosed only through the current search hit."""
    before_files = files()
    after_files = {**before_files, LATE: b"after needle\n"}
    job, before = upload(server, zip_bytes(before_files))
    app.worker.join(timeout=5)
    assert before["status"] == "ready"
    assert source(server, job, LATE) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    selector = start(server, args(job, before, offset=200))
    found = finish(app, server, "search", selector)
    assert found["status"] == "ready" and found["result"]["matching_modules"] == 201
    comparison, compared = submit(app, server, job, before, zip_bytes(after_files))
    assert compared["status"] == "ready"
    result = compared["result"]
    selected = page(server, result, offset=200)
    assert source(server, job, LATE)[1]["text"].encode() == before_files[LATE]
    assert comparison_source(server, result, selected, "after", LATE)[1]["text"].encode() == after_files[LATE]
    return job, before, selector, comparison, result, selected


@pytest.mark.parametrize("first", ["search", "comparison"], ids=["search-first", "compare-first"])
@pytest.mark.parametrize("cancelled", [None, "first", "queued"], ids=["complete", "cancel-active", "cancel-queued"])
def test_both_queue_directions_share_one_real_child_and_reap(running, monkeypatch, first, cancelled):
    app, server, _ = running
    raw = zip_bytes(files(1))
    job, before = upload(server, raw)
    app.worker.join(timeout=5)
    second = "comparison" if first == "search" else "search"
    probe = RustProbe(monkeypatch, app, first)
    selectors = {first: launch(app, server, first, job, before, raw)}
    try:
        assert probe.entered.wait(5)
        selectors[second] = launch(app, server, second, job, before, raw)
        assert probe.gate.attempted[THREADS[second]].wait(5)
        threads = {kind: worker(app, kind) for kind in (first, second)}
        assert all(thread.is_alive() and not thread.daemon for thread in threads.values())
        assert probe.owners == [THREADS[first]] and probe.children[0].poll() is None
        assert source(server, job, "Catalogs/Owner/Ext/M000.bsl") == (409, {"error": "BUSY"})
        if cancelled:
            kind = first if cancelled == "first" else second
            cancel(server, kind, selectors[kind])
            assert worker(app, kind) is threads[kind] and threads[kind].is_alive()
            assert probe.owners == [THREADS[first]]
    finally:
        probe.proceed.set()
    outcomes = {kind: finish(app, server, kind, selectors[kind]) for kind in (first, second)}
    for kind, outcome in outcomes.items():
        expected = "cancelled" if cancelled and kind == (first if cancelled == "first" else second) else "ready"
        assert outcome["status"] == expected, outcome
        if expected == "cancelled":
            assert outcome["error"] == "CANCELLED" and "result" not in outcome
        elif kind == "search":
            assert outcome["result"]["matching_modules"] == 1
        else:
            assert outcome["result"]["counts"]["changes"] == 0
    counts = Counter(probe.owners)
    for kind in (first, second):
        expected = 1 if kind == "search" else 3
        if cancelled == "queued" and kind == second:
            expected = 0
        elif cancelled == "first" and kind == first:
            expected = 1
        assert counts[THREADS[kind]] == expected
    probe.assert_reaped()
    if outcomes["comparison"]["status"] == "cancelled":
        assert app.comparison_pending.rows == () and not app.comparison_pending.path.exists()
    if cancelled:
        kind = first if cancelled == "first" else second
        retried = launch(app, server, kind, job, before, raw)
        assert finish(app, server, kind, retried)["status"] == "ready"
        probe.assert_reaped()


def test_new_import_invalidates_both_search_and_comparison_identities(running):
    app, server, _ = running
    job, before, selector, comparison, result, selected = ready_both(app, server)
    old_before, old_after = app.current.path, app.comparison_current.path
    next_job = prepare(server)
    # Reservation immediately withdraws old per-page/source authority.
    assert search_poll(server, selector) == (400, {"error": "SEARCH_NOT_AVAILABLE"})
    assert source(server, job, LATE) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    assert comparison_source(server, result, selected, "after", LATE) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    raw = zip_bytes(files(1))
    assert request(server, "/api/import?job=" + next_job, "PUT", raw,
                   {"Content-Type": "application/zip"})[0] == 202
    accepted = wait(server, next_job)
    app.worker.join(timeout=5)
    assert accepted["status"] == "ready" and not app.worker.is_alive()
    assert not old_before.exists() and not old_after.exists()
    assert len(list(Path(app.temp.name).glob("*.zip"))) == 1
    assert search_poll(server, selector)[0] == 400
    assert source(server, job, LATE) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    assert comparison_poll(server, comparison) == (400, {"error": "COMPARISON_NOT_AVAILABLE"})
    assert current(server, job, before) == (400, {"error": "COMPARISON_NOT_AVAILABLE"})
    assert post(server, "/api/comparison-page", {**binding(result), "offset": 200, "status": "all"}) == (400, {"error": "COMPARISON_NOT_AVAILABLE"})
    for side in ("before", "after"):
        assert comparison_source(server, result, selected, side, LATE) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    assert current(server, next_job, accepted)[1]["current"] is None
    fresh = start(server, args(next_job, accepted))
    assert finish(app, server, "search", fresh)["result"]["matching_modules"] == 1


def test_import_waits_for_cancelled_source_child_before_replacing_both_archives(running, monkeypatch):
    app, server, _ = running
    job, before, _, comparison, result, selected = ready_both(app, server)
    old_before, old_after = app.current.path, app.comparison_current.path
    probe = RustProbe(monkeypatch, app, "search")
    selector = start(server, args(job, before, offset=200))
    search_worker = app.search_worker
    try:
        assert probe.entered.wait(5)
        next_job = prepare(server)
        assert search_poll(server, selector) == (400, {"error": "SEARCH_NOT_AVAILABLE"})
        assert request(server, "/api/import?job=" + next_job, "PUT", zip_bytes(files(1)),
                       {"Content-Type": "application/zip"})[0] == 202
        assert probe.gate.attempted[THREADS["import"]].wait(5)
        assert app.search_worker is search_worker and search_worker.is_alive()
        assert app.worker.is_alive() and old_before.exists() and old_after.exists()
        assert probe.owners == [THREADS["search"]] and probe.children[0].poll() is None
    finally:
        probe.proceed.set()
    assert wait(server, next_job)["status"] == "ready"
    app.worker.join(timeout=5)
    search_worker.join(timeout=5)
    assert not app.worker.is_alive() and not search_worker.is_alive()
    assert app.search.status == "cancelled" and app.search.result is None
    assert probe.owners == [THREADS["search"], THREADS["import"]]
    probe.assert_reaped()
    assert not old_before.exists() and not old_after.exists()
    assert app.comparison_current is app.comparison_pending is None
    assert source(server, job, LATE) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    assert comparison_poll(server, comparison) == (400, {"error": "COMPARISON_NOT_AVAILABLE"})
    assert comparison_source(server, result, selected, "after", LATE) == (400, {"error": "SOURCE_NOT_AVAILABLE"})


@pytest.mark.parametrize("first", ["search", "comparison"], ids=["search-first", "compare-first"])
@pytest.mark.parametrize("permission", ["project:read", "analysis:run"], ids=["read", "run"])
def test_revocation_reaps_active_child_and_prevents_queued_child(running, monkeypatch, first, permission):
    app, server, _ = running
    raw = zip_bytes(files(1))
    job, before = upload(server, raw)
    app.worker.join(timeout=5)
    second = "comparison" if first == "search" else "search"
    probe = RustProbe(monkeypatch, app, first)
    selectors = {first: launch(app, server, first, job, before, raw)}
    try:
        assert probe.entered.wait(5)
        selectors[second] = launch(app, server, second, job, before, raw)
        assert probe.gate.attempted[THREADS[second]].wait(5)
        context = app.config.context()
        with context.state.transaction(context.principal, write=True) as tx:
            tx._connection.execute("DELETE FROM membership_permissions WHERE permission=?", (permission,))
    finally:
        probe.proceed.set()
    for kind in (first, second):
        worker(app, kind).join(timeout=5)
        assert not worker(app, kind).is_alive()
    assert probe.owners == [THREADS[first]]
    probe.assert_reaped()
    assert app.search.result is None and app.search.status == "error"
    assert app.comparison_current is None and app.comparison_pending.rows == ()
    assert not app.comparison_pending.path.exists()
    assert search_poll(server, selectors["search"]) == (403, {"error": "FORBIDDEN"})
    assert comparison_poll(server, selectors["comparison"]) == (403, {"error": "FORBIDDEN"})
    assert source(server, job, "Catalogs/Owner/Ext/M000.bsl") == (403, {"error": "FORBIDDEN"})


@pytest.mark.parametrize("endpoint", ["search", "source", "compare", "current", "page", "before", "after"],
                         ids=["search", "source", "compare", "current", "page", "before", "after"])
@pytest.mark.parametrize("permission", ["project:read", "analysis:run"], ids=["read", "run"])
def test_combined_ready_results_reauthorize_at_disclosure(running, monkeypatch, endpoint, permission):
    app, server, _ = running
    job, before, selector, comparison, result, selected = ready_both(app, server)
    context = app.config.context()
    original = gui.json.dumps
    revoked = threading.Event()

    def dumps(value, *args, **kwargs):
        raw = original(value, *args, **kwargs)
        if (isinstance(value, dict) and not revoked.is_set()
                and any(key in value for key in ("result", "current", "rows", "text"))):
            with context.state.transaction(context.principal, write=True) as tx:
                tx._connection.execute("DELETE FROM membership_permissions WHERE permission=?", (permission,))
            revoked.set()
        return raw

    monkeypatch.setattr(gui.json, "dumps", dumps)
    if endpoint == "search":
        response = search_poll(server, selector)
    elif endpoint == "source":
        response = source(server, job, LATE)
    elif endpoint == "compare":
        response = comparison_poll(server, comparison)
    elif endpoint == "current":
        response = current(server, job, before)
    elif endpoint == "page":
        response = post(server, "/api/comparison-page", {**binding(result), "offset": 200, "status": "all"})
    else:
        response = comparison_source(server, result, selected, endpoint, LATE)
    assert revoked.is_set() and response == (403, {"error": "FORBIDDEN"})
    # Both completed features remain inaccessible after the same real revocation.
    assert search_poll(server, selector) == (403, {"error": "FORBIDDEN"})
    assert comparison_poll(server, comparison) == (403, {"error": "FORBIDDEN"})
