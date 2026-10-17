"""Real service binding/auth; explicit fixture events and injected transport.

POSIX replaces only the Windows Observer lease with its authorization check.
Actual capture/report events are exercised by the Windows integration suite.
"""
import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from rentgen_core import service_entry
from rentgen_core.errors import CoreError
from rentgen_core.notification_delivery import WebhookAdapter
from project_access_test_support import grant_membership
from test_service_polling import observer, service_profile


def adapter(sender):
    return WebhookAdapter(
        "https://hooks.example.test/events", allowed_hosts={"hooks.example.test"},
        namespace="service-generation-a", bearer_token="PRIVATE_TOKEN", sender=sender,
    )


def response():
    result = io.BytesIO(b"")
    result.status = 204
    return result


def revoke(observer):
    ctx = observer._context(write=True)
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        grant_membership(tx, ctx.principal, {"project:read", "project:admin"})


@pytest.mark.parametrize("schema,trusted", [(2, False), (2, True), (3, False), (3, True)])
def test_service_explicit_delivery_uses_fixed_queue_journal_and_stops_on_close(
    service_profile, observer, schema, trusted,
):
    worker = service_entry.create_worker(service_profile(schema, trusted=trusted))
    calls = []
    def sender(request, *, timeout):
        calls.append(request.get_header("Idempotency-key"))
        return response()
    try:
        worker.outbox.enqueue({"status": "fixture-event"})
        host = worker.notification_host(adapter(sender))
        journal = observer.profile / "notification-delivery.json"
        assert not journal.exists() and calls == []
        assert host.run() == 1 and len(calls) == 1 and worker.outbox.peek() == []
        assert journal.exists() and "PRIVATE_TOKEN" not in journal.read_text()
        with pytest.raises(CoreError) as error:
            worker.notification_host(adapter(sender))
        assert error.value.code == "NOTIFICATION_HOST_ALREADY_RUN"
    finally:
        worker.close()
    # A new worker owns the same profile and generation, never the old host.
    reopened = service_entry.create_worker(service_profile(schema, trusted=trusted))
    try:
        reopened.outbox.enqueue({"status": "later-event"})
        stopped = reopened.notification_host(adapter(sender), max_cycles=2)
        reopened.close()
        assert stopped.run() == 0 and len(calls) == 1
        assert len(reopened.outbox.peek()) == 1
        with pytest.raises(CoreError) as error:
            reopened.notification_host(adapter(sender))
        assert error.value.code == "SERVICE_HOST_ALREADY_RUN"
    finally:
        reopened.close()


@pytest.mark.parametrize("when", ["construction", "batch", "ack"])
def test_service_revocation_stops_delivery_at_each_boundary(service_profile, observer, when):
    worker = service_entry.create_worker(service_profile(3, trusted=True))
    calls = []
    def sender(request, *, timeout):
        calls.append(request)
        if when == "ack":
            revoke(observer)
        return response()
    try:
        worker.outbox.enqueue({"status": "fixture-event"})
        if when == "construction":
            revoke(observer)
        with pytest.raises(CoreError) as error:
            host = worker.notification_host(adapter(sender))
            if when == "batch":
                revoke(observer)
            host.run()
        assert error.value.code == "PROJECT_FORBIDDEN"
        assert len(calls) == (1 if when == "ack" else 0)
        assert len(worker.outbox.peek()) == 1
        journal = observer.profile / "notification-delivery.json"
        if when != "ack":
            assert not journal.exists()
        else:
            from rentgen_core.notification_journal import DeliveryJournal
            assert DeliveryJournal(journal, namespace="service-generation-a").records()[0].state == "accepted"
    finally:
        worker.close()


@pytest.mark.parametrize("suffix", ["", ".lock", ".tmp"])
def test_service_refuses_unsafe_delivery_placement(service_profile, observer, suffix):
    worker = service_entry.create_worker(service_profile(2))
    path = observer.profile / ("notification-delivery.json" + suffix)
    path.mkdir()
    try:
        with pytest.raises(CoreError) as error:
            worker.notification_host(adapter(lambda *args, **kwargs: pytest.fail("unexpected send")))
        assert error.value.code == "NOTIFICATION_HOST_INVALID" and path.is_dir()
    finally:
        worker.close()


def test_concurrent_factory_has_one_lifetime_owner(service_profile):
    worker = service_entry.create_worker(service_profile(2))
    ready = Barrier(2, timeout=5)
    webhook = adapter(lambda *args, **kwargs: pytest.fail("unexpected send"))
    def create():
        ready.wait()
        try:
            return worker.notification_host(webhook)
        except CoreError as error:
            return error.code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(create) for _ in range(2)]
            results = [future.result(timeout=10) for future in futures]
        assert sum(result == "NOTIFICATION_HOST_ALREADY_RUN" for result in results) == 1
        host = next(result for result in results if not isinstance(result, str))
        worker.close()
        assert host.run() == 0
    finally:
        worker.close()
