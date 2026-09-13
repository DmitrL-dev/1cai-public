"""Delivery contract tests; every transport is local and injected."""

import importlib
import importlib.util
import http.client
import io
import json
from urllib.error import HTTPError, URLError

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.git_watcher import NotificationOutbox


def api():
    assert importlib.util.find_spec("rentgen_core.notification_delivery") is not None
    return importlib.import_module("rentgen_core.notification_delivery")


class Response(io.BytesIO):
    def __init__(self, status=204, body=b""):
        super().__init__(body)
        self.status = status
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class Sender:
    def __init__(self, response=None, error=None):
        self.response = response or Response()
        self.error = error
        self.calls = []

    def __call__(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return self.response


def adapter(sender, **kwargs):
    options = dict(
        endpoint="https://hooks.example.test/events",
        allowed_hosts={"hooks.example.test"},
        namespace="project-a",
        bearer_token="test-secret-123",
        sender=sender,
    )
    options.update(kwargs)
    return api().WebhookAdapter(**options)


def notification(notification_id=1, event=None):
    return {
        "id": notification_id,
        "event": {"status": "analyzed"} if event is None else event,
        "created_at": "2026-09-13T00:00:00+00:00",
    }


def test_accepts_json_once_with_stable_scoped_idempotency_and_secret_header():
    sender = Sender()
    hook = adapter(sender)
    result = hook.deliver(notification())
    assert result.status is api().DeliveryStatus.ACCEPTED
    assert result.notification_id == 1
    assert result.http_status == 204
    assert len(sender.calls) == 1
    request, timeout = sender.calls[0]
    assert request.method == "POST"
    assert json.loads(request.data) == notification()
    assert request.get_header("Authorization") == "Bearer test-secret-123"
    assert request.get_header("Idempotency-key") == result.idempotency_key
    assert 0 < timeout <= 30
    repeated = adapter(Sender()).deliver(notification())
    other = adapter(Sender(), namespace="project-b").deliver(notification())
    assert repeated.idempotency_key == result.idempotency_key
    assert other.idempotency_key != result.idempotency_key
    assert "test-secret-123" not in repr(result) + repr(hook) + request.full_url


@pytest.mark.parametrize(
    "status,expected",
    [
        (200, "accepted"),
        (299, "accepted"),
        (301, "permanent"),
        (400, "permanent"),
        (401, "permanent"),
        (429, "permanent"),
        (500, "retryable"),
        (599, "retryable"),
    ],
)
def test_classifies_http_without_retry(status, expected):
    sender = Sender(Response(status))
    assert adapter(sender).deliver(notification()).status.value == expected
    assert len(sender.calls) == 1


@pytest.mark.parametrize(
    "error",
    [
        URLError("test-secret-123"),
        TimeoutError("test-secret-123"),
        OSError("test-secret-123"),
    ],
)
def test_transport_failure_is_retryable_without_secret_details(error):
    sender = Sender(error=error)
    result = adapter(sender).deliver(notification())
    assert result.status.value == "retryable"
    assert "test-secret-123" not in repr(result)
    assert len(sender.calls) == 1


def test_urllib_http_error_is_classified_and_closed():
    body = io.BytesIO(b"test-secret-123")
    sender = Sender(
        error=HTTPError("https://hooks.example.test/events", 503, "secret", {}, body)
    )
    result = adapter(sender).deliver(notification())
    assert result.status.value == "retryable"
    assert result.http_status == 503
    assert body.closed
    assert "secret" not in repr(result)


@pytest.mark.parametrize(
    "options",
    [
        {"endpoint": "http://hooks.example.test/events"},
        {"endpoint": "https://sub.hooks.example.test/events"},
        {"endpoint": "https://hooks.example.test.evil/events"},
        {"endpoint": "https://user:pass@hooks.example.test/events"},
        {"endpoint": "https://hooks.example.test/events?token=secret"},
        {"endpoint": "https://hooks.example.test/events#fragment"},
        {"endpoint": "https://hooks.example.test/test-secret-123"},
        {"endpoint": "https://hooks.example.test/\n"},
        {"allowed_hosts": set()},
        {"allowed_hosts": {"*.example.test"}},
        {"bearer_token": "x\r\ny"},
        {"namespace": "bad\nnamespace"},
        {"timeout": 0},
        {"timeout": 31},
        {"timeout": float("nan")},
        {"max_payload_bytes": 0},
        {"max_payload_bytes": 1048577},
        {"max_response_bytes": 0},
        {"max_response_bytes": 65537},
    ],
)
def test_bad_configuration_fails_before_transport(options):
    sender = Sender()
    with pytest.raises(CoreError) as caught:
        adapter(sender, **options)
    assert caught.value.code == "NOTIFICATION_DELIVERY_INVALID"
    assert sender.calls == []
    assert "test-secret-123" not in str(caught.value)


@pytest.mark.parametrize(
    "item",
    [
        notification(True),
        notification(0),
        notification(2**63),
        notification(event=[]),
        notification(event={"value": float("nan")}),
        {"id": 1, "event": {}, "created_at": "yesterday"},
        {**notification(), "unexpected": 1},
    ],
)
def test_malformed_notification_never_sends(item):
    sender = Sender()
    result = adapter(sender).deliver(item)
    assert result.status.value == "permanent"
    assert sender.calls == []


def test_payload_limit_checks_utf8_bytes_before_send():
    sender = Sender()
    result = adapter(sender, max_payload_bytes=128).deliver(
        notification(event={"text": "я" * 80})
    )
    assert result.status.value == "permanent"
    assert sender.calls == []


def test_response_read_is_bounded_and_oversize_is_not_accepted():
    response = Response(200, b"x" * 100)
    result = adapter(Sender(response), max_response_bytes=16).deliver(notification())
    assert result.status.value == "permanent"
    assert response.read_sizes == [17]
    assert response.closed


@pytest.mark.parametrize("status", [True, 99, 600, "200"])
def test_invalid_response_status_is_permanent(status):
    assert (
        adapter(Sender(Response(status))).deliver(notification()).status.value
        == "permanent"
    )


def test_default_transport_disables_redirects_and_environment_proxy(monkeypatch):
    module = api()
    observed = []

    class Opener:
        def open(self, request, *, timeout):
            observed.append((request, timeout))
            return Response(302)

    def build_opener(*handlers):
        redirect = next(
            h
            for h in handlers
            if isinstance(h, module.urllib.request.HTTPRedirectHandler)
        )
        assert (
            redirect.redirect_request(None, None, 302, "Found", {}, "https://evil.test")
            is None
        )
        proxy = next(
            h for h in handlers if isinstance(h, module.urllib.request.ProxyHandler)
        )
        assert proxy.proxies == {}
        return Opener()

    monkeypatch.setattr(module.urllib.request, "build_opener", build_opener)
    hook = adapter(None)
    assert hook.deliver(notification()).status.value == "permanent"
    assert len(observed) == 1


def test_deliver_outbox_acks_only_accepted_and_respects_limit(tmp_path):
    module = api()
    outbox = NotificationOutbox(tmp_path / "outbox.json")
    for status in ("analyzed", "error", "fatal"):
        outbox.enqueue({"status": status})
    calls = []

    def sender(request, *, timeout):
        calls.append(request)
        return Response(204 if len(calls) == 1 else 503)

    results = module.deliver_outbox(outbox, adapter(sender), limit=2)
    assert [r.status.value for r in results] == ["accepted", "retryable"]
    assert [i["id"] for i in outbox.peek()] == [2, 3]
    assert len(calls) == 2


def test_permanent_delivery_remains_pending(tmp_path):
    outbox = NotificationOutbox(tmp_path / "outbox.json")
    outbox.enqueue({"status": "error"})
    api().deliver_outbox(outbox, adapter(Sender(Response(403))), limit=1)
    assert len(outbox.peek()) == 1


@pytest.mark.parametrize("limit", [0, True, 1001])
def test_outbox_limit_fails_closed(tmp_path, limit):
    with pytest.raises(CoreError):
        api().deliver_outbox(
            NotificationOutbox(tmp_path / "outbox.json"), adapter(Sender()), limit=limit
        )


def test_corrupt_outbox_never_sends_or_acknowledges(tmp_path):
    path = tmp_path / "outbox.json"
    path.write_text(
        '{"schema": 1, "outbox": "git-watcher-v1", "next_id": 3, "events": ['
        + json.dumps(notification())
        + ","
        + json.dumps(notification(True))
        + "]}"
    )
    before = path.read_bytes()
    sender = Sender()
    with pytest.raises(CoreError):
        api().deliver_outbox(NotificationOutbox(path), adapter(sender), limit=1)
    assert sender.calls == []
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "error",
    [http.client.IncompleteRead(b"secret"), http.client.BadStatusLine("secret")],
)
def test_incomplete_http_transport_is_retryable(error):
    result = adapter(Sender(error=error)).deliver(notification())
    assert result.status.value == "retryable"
    assert "secret" not in repr(result)


def test_unexpected_sender_failure_cannot_expose_secret():
    result = adapter(Sender(error=RuntimeError("test-secret-123"))).deliver(
        notification()
    )
    assert result.status.value == "permanent"
    assert "test-secret-123" not in repr(result)


def test_response_close_failure_cannot_expose_secret_or_mask_acceptance():
    class BadClose(Response):
        def close(self):
            super().close()
            raise RuntimeError("test-secret-123")

    result = adapter(Sender(BadClose())).deliver(notification())
    assert result.status.value == "accepted"


@pytest.mark.parametrize("event", [{1: "invalid-key"}, {"values": (1, 2)}])
def test_notification_must_be_json_without_silent_type_coercion(event):
    sender = Sender()
    result = adapter(sender).deliver(notification(event=event))
    assert result.status.value == "permanent"
    assert sender.calls == []


def test_malformed_later_batch_event_blocks_all_delivery(tmp_path):
    path = tmp_path / "outbox.json"
    bad = notification(2, {"value": float("nan")})
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "outbox": "git-watcher-v1",
                "next_id": 3,
                "events": [notification(), bad],
            }
        )
    )
    sender = Sender()
    with pytest.raises(CoreError):
        api().deliver_outbox(NotificationOutbox(path), adapter(sender), limit=2)
    assert sender.calls == []


def test_malformed_event_beyond_batch_limit_blocks_all_delivery(tmp_path):
    path = tmp_path / "outbox.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "outbox": "git-watcher-v1",
                "next_id": 3,
                "events": [notification(), notification(2, {"value": float("nan")})],
            }
        )
    )
    sender = Sender()
    with pytest.raises(CoreError):
        api().deliver_outbox(NotificationOutbox(path), adapter(sender), limit=1)
    assert sender.calls == []


def test_extreme_timeout_is_sanitized_configuration_error():
    with pytest.raises(CoreError) as caught:
        adapter(Sender(), timeout=10**1000)
    assert caught.value.code == "NOTIFICATION_DELIVERY_INVALID"


def test_oversized_payload_receipt_preserves_validated_identity():
    hook = adapter(Sender(), max_payload_bytes=1)
    receipt = hook.deliver(notification(42))
    assert receipt.status.value == "permanent"
    assert receipt.notification_id == 42
    assert (
        receipt.idempotency_key
        == adapter(Sender()).deliver(notification(42)).idempotency_key
    )
