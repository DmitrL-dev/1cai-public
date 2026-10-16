"""Durable retry and recovery contracts; no external requests."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.git_watcher import NotificationOutbox
from rentgen_core.notification_delivery import WebhookAdapter, deliver_outbox, _payload
from rentgen_core.notification_journal import DeliveryJournal, RetryPolicy, idempotency_key


class Response(io.BytesIO):
    def __init__(self, status):
        super().__init__(b"")
        self.status = status


@pytest.fixture
def delivery(tmp_path):
    outbox = NotificationOutbox(tmp_path / "outbox.json")
    outbox.enqueue({"status": "analyzed", "private": "PRIVATE_EVENT"})
    journal = DeliveryJournal(tmp_path / "journal.json", namespace="project-a")
    now = [datetime(2026, 10, 16, tzinfo=timezone.utc)]
    calls, statuses = [], [503]

    def sender(request, *, timeout):
        calls.append(request.get_header("Idempotency-key"))
        return Response(statuses[0])

    adapter = WebhookAdapter(
        "https://hooks.example.test/events", allowed_hosts={"hooks.example.test"},
        namespace="project-a", bearer_token="PRIVATE_TOKEN", sender=sender,
    )
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=10, max_delay_seconds=20)

    def run(**kwargs):
        options = dict(authorize=lambda: None, journal=journal, retry_policy=policy,
                       clock=lambda: now[0])
        options.update(kwargs)
        return deliver_outbox(outbox, adapter, **options)

    return outbox, journal, now, calls, statuses, run


def test_waiting_consumer_cannot_prune_an_attempt_from_a_stale_queue(delivery, monkeypatch):
    outbox, journal, now, calls, statuses, run = delivery
    reached, release = Event(), Event()
    original = journal._session

    @contextmanager
    def delayed(namespace):
        reached.set()
        assert release.wait(5)
        with original(namespace) as session:
            yield session

    monkeypatch.setattr(journal, "_session", delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run)
        try:
            assert reached.wait(5)
            second = outbox.enqueue({"status": "error"})
            item = outbox.peek()[-1]
            digest = hashlib.sha256(_payload(item, outbox.MAX_BYTES)).hexdigest()
            with original(journal.namespace) as session:
                session.begin(second, idempotency_key(journal.namespace, second), digest, now[0])
                session.retry(second, "TRANSPORT_ERROR", now[0] + timedelta(seconds=20), now[0])
        finally:
            release.set()
        future.result(timeout=5)
    records = {row.notification_id: row for row in journal.records()}
    assert second in records, "A waiting consumer discarded another consumer's attempt"
    assert records[second].attempts == 1
    assert records[second].next_attempt_at == (now[0] + timedelta(seconds=20)).isoformat()
    assert len(calls) == 1


def test_backoff_survives_reopen_exhausts_and_requires_explicit_rearm(delivery):
    outbox, journal, now, calls, statuses, run = delivery
    first = run()[0]
    assert first.attempt == 1 and first.next_attempt_at == (now[0] + timedelta(seconds=10)).isoformat()
    reopened = DeliveryJournal(journal.path, namespace=journal.namespace)
    assert run(journal=reopened) == ()
    now[0] += timedelta(seconds=10)
    assert run(journal=reopened)[0].attempt == 2
    now[0] += timedelta(seconds=20)
    result = run(journal=reopened)[0]
    assert (result.status.value, result.code, result.attempt) == ("permanent", "RETRY_EXHAUSTED", 3)
    assert run(journal=reopened) == () and len(calls) == 3
    assert len(outbox.peek()) == 1
    reopened.rearm(1, clock=lambda: now[0])
    statuses[0] = 204
    assert run(journal=reopened)[0].attempt == 1
    assert calls == [calls[0]] * 4 and outbox.peek() == [] and reopened.records() == ()
    raw = journal.path.read_text()
    assert all(secret not in raw for secret in ("PRIVATE_EVENT", "PRIVATE_TOKEN", "hooks.example.test"))


@pytest.mark.parametrize("refusal", ["ack", "authorization"])
def test_accepted_event_recovers_ack_without_resending(delivery, monkeypatch, refusal):
    outbox, journal, now, calls, statuses, run = delivery
    statuses[0] = 204
    original = outbox.ack

    def fail(*args):
        raise CoreError("PROJECT_FORBIDDEN", "Access revoked")

    count = 0

    def authorize():
        nonlocal count
        count += 1
        if count == 2:
            fail()

    options = {}
    if refusal == "ack":
        monkeypatch.setattr(outbox, "ack", fail)
    else:
        options["authorize"] = authorize
    with pytest.raises(CoreError):
        run(**options)
    assert journal.records()[0].state.value == "accepted" and len(outbox.peek()) == 1
    monkeypatch.setattr(outbox, "ack", original)
    result = run(journal=DeliveryJournal(journal.path, namespace=journal.namespace))[0]
    assert result.code == "ACK_RECOVERED" and result.attempt == 1
    assert len(calls) == 1 and outbox.peek() == []


def test_loss_after_begin_counts_unknown_attempt_before_retry(delivery, monkeypatch):
    outbox, journal, now, calls, statuses, run = delivery
    original = WebhookAdapter.deliver

    def interrupted(*args):
        raise SystemExit("simulated process loss")

    monkeypatch.setattr(WebhookAdapter, "deliver", interrupted)
    with pytest.raises(SystemExit):
        run()
    assert journal.records()[0].state.value == "sending"
    monkeypatch.setattr(WebhookAdapter, "deliver", original)
    assert run() == ()
    record = journal.records()[0]
    assert record.last_error == "OUTCOME_UNKNOWN" and record.attempts == 1
    now[0] += timedelta(seconds=10)
    statuses[0] = 204
    assert run()[0].attempt == 2 and len(calls) == 1


def test_hard_process_exit_preserves_attempt_and_releases_os_lock(delivery):
    outbox, journal, now, calls, statuses, run = delivery
    script = """
import os, sys
from datetime import datetime
from rentgen_core.git_watcher import NotificationOutbox
from rentgen_core.notification_delivery import WebhookAdapter, deliver_outbox
from rentgen_core.notification_journal import DeliveryJournal
def lost_response(request, *, timeout):
    os._exit(73)
adapter = WebhookAdapter('https://hooks.example.test/events',
    allowed_hosts={'hooks.example.test'}, namespace='project-a', sender=lost_response)
deliver_outbox(NotificationOutbox(sys.argv[1]), adapter, authorize=lambda: None,
    journal=DeliveryJournal(sys.argv[2], namespace='project-a'),
    clock=lambda: datetime.fromisoformat(sys.argv[3]))
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    result = subprocess.run(
        [sys.executable, "-c", script, str(outbox.path), str(journal.path), now[0].isoformat()],
        env=env, capture_output=True, timeout=20,
    )
    assert result.returncode == 73, result.stderr.decode(errors="replace")
    assert journal.records()[0].state.value == "sending"
    assert run() == ()
    assert journal.records()[0].last_error == "OUTCOME_UNKNOWN"
    now[0] += timedelta(seconds=10)
    statuses[0] = 204
    assert run()[0].attempt == 2 and len(calls) == 1
    assert outbox.peek() == []


def test_other_consumer_is_refused_while_journal_is_locked(delivery):
    outbox, journal, now, calls, statuses, run = delivery
    other = DeliveryJournal(journal.path, namespace=journal.namespace)
    with journal._session(journal.namespace):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run, journal=other)
            with pytest.raises(CoreError) as caught:
                future.result(timeout=5)
        assert caught.value.code == "NOTIFICATION_JOURNAL_BUSY"
    assert calls == [] and journal.records() == ()


def test_journal_overflow_is_detected_with_a_bounded_read(delivery, monkeypatch):
    outbox, journal, now, calls, statuses, run = delivery
    from rentgen_core import notification_journal as module
    monkeypatch.setattr(module, "MAX_BYTES", 64)
    journal.path.write_bytes(b"x" * 100)
    original = Path.open
    reads = []

    @contextmanager
    def guarded(path, *args, **kwargs):
        with original(path, *args, **kwargs) as stream:
            if path != journal.path or args != ("rb",):
                yield stream
                return
            class Bounded:
                def read(self, size):
                    reads.append(size)
                    return stream.read(size)
            yield Bounded()

    monkeypatch.setattr(Path, "open", guarded)
    with pytest.raises(CoreError) as caught:
        run()
    assert caught.value.code == "NOTIFICATION_JOURNAL_RECOVERY_REQUIRED"
    assert reads == [65] and calls == []


@pytest.mark.parametrize("corruption", ["payload", "namespace", "json", "temporary"])
def test_conflicting_or_corrupt_journal_refuses_before_send(delivery, corruption):
    outbox, journal, now, calls, statuses, run = delivery
    run()
    if corruption == "payload":
        document = json.loads(outbox.path.read_text())
        document["events"][0]["event"]["private"] = "changed"
        outbox.path.write_text(json.dumps(document))
    elif corruption == "namespace":
        document = json.loads(journal.path.read_text())
        document["namespace"] = "foreign"
        document["entries"][0]["idempotency_key"] = idempotency_key("foreign", 1)
        journal.path.write_text(json.dumps(document))
    elif corruption == "json":
        journal.path.write_text('{"schema":1,"schema":1}')
    else:
        journal.path.with_suffix(".json.tmp").write_bytes(b"interrupted")
    before = journal.path.read_bytes()
    now[0] += timedelta(seconds=30)
    with pytest.raises(CoreError) as caught:
        run()
    assert caught.value.code in {"NOTIFICATION_JOURNAL_CONFLICT", "NOTIFICATION_JOURNAL_RECOVERY_REQUIRED"}
    assert len(calls) == 1 and journal.path.read_bytes() == before


def test_recreated_queue_cannot_reuse_acknowledged_identity(delivery):
    outbox, journal, now, calls, statuses, run = delivery
    original = outbox.path.read_bytes()
    statuses[0] = 204
    run()
    outbox.path.write_bytes(original)
    with pytest.raises(CoreError) as caught:
        run()
    assert caught.value.code == "NOTIFICATION_JOURNAL_CONFLICT" and len(calls) == 1


def test_revocation_before_send_does_not_consume_attempt(delivery):
    outbox, journal, now, calls, statuses, run = delivery

    def refused():
        raise CoreError("PROJECT_FORBIDDEN", "Access revoked")

    with pytest.raises(CoreError):
        run(authorize=refused)
    assert calls == [] and journal.records() == () and len(outbox.peek()) == 1


@pytest.mark.parametrize("options", [{"max_attempts": True}, {"max_attempts": 0},
    {"max_attempts": 101}, {"base_delay_seconds": 0}, {"max_delay_seconds": 1}])
def test_retry_policy_bounds(options):
    with pytest.raises(CoreError):
        RetryPolicy(**options)
