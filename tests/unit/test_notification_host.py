"""Foreground delivery with real queues/journals and an injected transport."""
from datetime import datetime, timedelta, timezone
import io
from threading import Event, Thread

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.git_watcher import NotificationOutbox
from rentgen_core.notification_delivery import WebhookAdapter
from rentgen_core.notification_journal import DeliveryJournal, RetryPolicy


@pytest.fixture
def setup_delivery(tmp_path):
    outbox = NotificationOutbox(tmp_path / "outbox.json")
    outbox.enqueue({"status": "analyzed", "private": "PRIVATE_EVENT"})
    journal = DeliveryJournal(tmp_path / "delivery.json", namespace="project-a")
    now = [datetime(2026, 10, 17, tzinfo=timezone.utc)]
    calls, responses = [], [503]

    def sender(request, *, timeout):
        calls.append(request.get_header("Idempotency-key"))
        response = io.BytesIO(b"")
        response.status = responses[0]
        return response

    adapter = WebhookAdapter(
        "https://hooks.example.test/events", allowed_hosts={"hooks.example.test"},
        namespace="project-a", bearer_token="PRIVATE_TOKEN", sender=sender,
    )
    return outbox, journal, adapter, now, calls, responses


def make_host(setup_delivery, **changes):
    from rentgen_core import NotificationDeliveryHost
    outbox, journal, adapter, now, _, _ = setup_delivery
    options = dict(authorize=lambda: None, journal=journal, interval_seconds=5,
                   clock=lambda: now[0], retry_policy=RetryPolicy(
                       max_attempts=2, base_delay_seconds=10, max_delay_seconds=10))
    options.update(changes)
    return NotificationDeliveryHost(outbox, adapter, **options)


def test_explicit_start_and_restart_preserve_due_time_and_retry_budget(setup_delivery):
    outbox, journal, _, now, calls, responses = setup_delivery
    first = make_host(setup_delivery)
    assert calls == [] and not journal.path.exists()
    assert first.last_results == () and first.run() == 1
    assert first.last_results[0].attempt == 1 and len(calls) == 1
    assert make_host(setup_delivery).run() == 1 and len(calls) == 1
    now[0] += timedelta(seconds=10)
    exhausted = make_host(setup_delivery)
    assert exhausted.run() == 1
    assert exhausted.last_results[0].code == "RETRY_EXHAUSTED"
    responses[0] = 204
    assert make_host(setup_delivery).run() == 1 and len(calls) == 2
    assert len(outbox.peek()) == 1
    journal.rearm(1, clock=lambda: now[0])
    assert make_host(setup_delivery).run() == 1
    assert calls == [calls[0]] * 3 and outbox.peek() == []
    assert all(secret not in journal.path.read_text() for secret in (
        "PRIVATE_EVENT", "PRIVATE_TOKEN", "hooks.example.test"))


def test_scheduler_waits_between_bounded_batches_and_keeps_only_last_results(setup_delivery):
    outbox, _, _, now, calls, responses = setup_delivery
    responses[0] = 204
    outbox.enqueue({"status": "second"})
    host = make_host(setup_delivery, batch_limit=1, max_cycles=2)
    waits = []
    def wait(seconds):
        waits.append(seconds)
        now[0] += timedelta(seconds=seconds)
    host._wait = wait
    assert host.run() == 2 and waits == [5]
    assert len(calls) == 2 and outbox.peek() == []
    assert len(host.last_results) == 1 and host.last_results[0].notification_id == 2
    with pytest.raises(CoreError) as error:
        host.run()
    assert error.value.code == "NOTIFICATION_HOST_ALREADY_RUN"


def test_stop_before_start_does_not_read_or_write_queue(setup_delivery):
    outbox, journal, _, _, calls, _ = setup_delivery
    host = make_host(setup_delivery)
    outbox.path.write_text("malformed")
    host.stop()
    assert host.run() == 0 and host.last_results == ()
    assert not journal.path.exists() and calls == []


def test_stop_wakes_real_interval_and_refuses_concurrent_run(setup_delivery):
    host = make_host(setup_delivery, max_cycles=2, interval_seconds=86400)
    entered, finished = Event(), Event()
    result, errors = [], []
    original = host._wait
    def wait(seconds):
        entered.set()
        return original(seconds)
    host._wait = wait
    def run():
        try:
            result.append(host.run())
        except BaseException as error:
            errors.append(error)
        finally:
            finished.set()
    thread = Thread(target=run, daemon=True)
    thread.start()
    try:
        assert entered.wait(5)
        with pytest.raises(CoreError) as error:
            host.run()
        assert error.value.code == "NOTIFICATION_HOST_ALREADY_RUN"
    finally:
        host.stop()
        thread.join(5)
    assert finished.is_set() and not thread.is_alive() and errors == []
    assert result == [1]


def test_stop_during_transport_retains_acceptance_and_restart_only_recovers_ack(setup_delivery):
    outbox, journal, adapter, _, calls, responses = setup_delivery
    responses[0] = 204
    host = make_host(setup_delivery)
    sender = adapter._sender
    def stopping_sender(request, *, timeout):
        response = sender(request, timeout=timeout)
        host.stop()
        return response
    adapter._sender = stopping_sender
    assert host.run() == 0 and len(calls) == 1
    assert len(outbox.peek()) == 1 and journal.records()[0].state == "accepted"
    adapter._sender = sender
    restarted = make_host(setup_delivery)
    assert restarted.run() == 1 and len(calls) == 1 and outbox.peek() == []
    assert restarted.last_results[0].code == "ACK_RECOVERED"


def test_revocation_between_batches_stops_without_another_send(setup_delivery):
    _, _, _, _, calls, _ = setup_delivery
    revoked = [False]
    def authorize():
        if revoked[0]:
            raise CoreError("PROJECT_FORBIDDEN", "Access revoked")
    host = make_host(setup_delivery, authorize=authorize, max_cycles=2)
    host._wait = lambda _: revoked.__setitem__(0, True)
    with pytest.raises(CoreError) as error:
        host.run()
    assert error.value.code == "PROJECT_FORBIDDEN" and len(calls) == 1


def test_revoked_idle_batch_does_not_reconcile_journal(setup_delivery):
    outbox, journal, _, _, calls, _ = setup_delivery
    outbox.ack(1)
    def deny():
        raise CoreError("PROJECT_FORBIDDEN", "Access revoked")
    host = make_host(setup_delivery, authorize=deny)
    with pytest.raises(CoreError, match="Access revoked"):
        host.run()
    assert calls == [] and not journal.path.exists()


@pytest.mark.parametrize("option,value", [
    ("max_cycles", None), ("max_cycles", True), ("max_cycles", 0),
    ("max_cycles", 10001), ("interval_seconds", 0), ("interval_seconds", True),
    ("interval_seconds", 86401), ("batch_limit", 0), ("batch_limit", 1001),
    ("batch_limit", True), ("authorize", None), ("journal", None),
    ("retry_policy", object()), ("clock", object()),
])
def test_invalid_host_configuration_has_no_side_effects(setup_delivery, option, value):
    _, journal, _, _, calls, _ = setup_delivery
    with pytest.raises(CoreError) as error:
        make_host(setup_delivery, **{option: value})
    assert error.value.code == "NOTIFICATION_HOST_INVALID"
    assert not journal.path.exists() and calls == []


def test_namespace_mismatch_refuses_before_run(setup_delivery, tmp_path):
    other = DeliveryJournal(tmp_path / "other.json", namespace="other")
    with pytest.raises(CoreError) as error:
        make_host(setup_delivery, journal=other)
    assert error.value.code == "NOTIFICATION_HOST_INVALID"
    assert not other.path.exists() and setup_delivery[4] == []


@pytest.mark.parametrize("suffix", ["", ".lock", ".tmp"])
def test_journal_cannot_overwrite_outbox_or_its_control_files(setup_delivery, suffix):
    outbox, _, _, _, calls, _ = setup_delivery
    before = outbox.path.read_bytes()
    collision = DeliveryJournal(outbox.path.with_name(outbox.path.name + suffix), namespace="project-a")
    with pytest.raises(CoreError) as error:
        make_host(setup_delivery, journal=collision)
    assert error.value.code == "NOTIFICATION_HOST_INVALID"
    assert outbox.path.read_bytes() == before and calls == []


def test_malformed_queue_stops_host_without_transport_retry(setup_delivery):
    outbox, _, _, _, calls, _ = setup_delivery
    host = make_host(setup_delivery, max_cycles=2)
    outbox.path.write_text("malformed")
    with pytest.raises(CoreError) as error:
        host.run()
    assert error.value.code == "GIT_WATCHER_NOTIFICATION_RECOVERY_REQUIRED"
    assert calls == [] and host.last_results == ()
