"""ASGI wire boundary tests using the real durable notification receiver."""

import asyncio
import hashlib
import json
import sqlite3

import pytest

from rentgen_core.notification_receiver import NotificationReceiver


TOKEN = "test-secret-123"


def _body(event=None):
    value = {
        "id": 1,
        "event": {"status": "analyzed"} if event is None else event,
        "created_at": "2026-09-23T00:00:00+00:00",
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _scope(body, *, key=None):
    key = key or hashlib.sha256(b"rentgen-notification-v1:test:1").hexdigest()
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.5"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/notifications",
        "raw_path": b"/notifications",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"receiver.example.test"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"authorization", ("Bearer " + TOKEN).encode("ascii")),
            (b"idempotency-key", key.encode("ascii")),
            (b"content-type", b"application/json; charset=utf-8"),
        ],
    }


async def _call(app, scope, body, *, messages=None):
    sent = []
    pending = iter(
        messages
        if messages is not None
        else [{"type": "http.request", "body": body, "more_body": False}]
    )

    async def receive():
        return next(pending)

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    return sent


async def _with_startup(app, exercise):
    incoming = asyncio.Queue()
    lifespan_sent = asyncio.Queue()

    async def send_lifespan(message):
        await lifespan_sent.put(message)

    lifespan = asyncio.create_task(
        app({"type": "lifespan"}, incoming.get, send_lifespan)
    )
    await incoming.put({"type": "lifespan.startup"})
    assert await asyncio.wait_for(lifespan_sent.get(), 5) == {
        "type": "lifespan.startup.complete"
    }
    try:
        return await exercise()
    finally:
        await incoming.put({"type": "lifespan.shutdown"})
        assert await asyncio.wait_for(lifespan_sent.get(), 5) == {
            "type": "lifespan.shutdown.complete"
        }
        await lifespan


def test_asgi_startup_accepts_one_durable_notification(tmp_path):
    from rentgen_core import NotificationReceiverASGI

    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver)

    async def scenario():
        async def exercise():
            body = _body()
            response = await _call(app, _scope(body), body)
            assert response[0]["type"] == "http.response.start"
            assert response[0]["status"] == 204
            assert response[1] == {"type": "http.response.body", "body": b""}
            assert receiver.count() == 1

        await _with_startup(app, exercise)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "variant",
    [
        "duplicate_length",
        "missing_length",
        "leading_zero_length",
        "transfer_encoding",
        "non_ascii_value",
        "invalid_header_name",
        "query",
        "root_path",
        "wrong_scheme",
        "missing_raw_path",
        "length_mismatch",
    ],
)
def test_invalid_wire_request_creates_no_receipt(tmp_path, variant):
    from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI

    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver)

    async def scenario():
        async def exercise():
            body = _body()
            scope = _scope(body)
            if variant == "duplicate_length":
                scope["headers"].append((b"content-length", str(len(body)).encode()))
            elif variant == "missing_length":
                del scope["headers"][1]
            elif variant == "leading_zero_length":
                scope["headers"][1] = (
                    b"content-length",
                    ("0" + str(len(body))).encode(),
                )
            elif variant == "transfer_encoding":
                scope["headers"].append((b"transfer-encoding", b"chunked"))
            elif variant == "non_ascii_value":
                scope["headers"].append((b"x-note", b"\xff"))
            elif variant == "invalid_header_name":
                scope["headers"].append((b"bad name", b"value"))
            elif variant == "query":
                scope["query_string"] = b"x=1"
            elif variant == "root_path":
                scope["root_path"] = "/proxy"
            elif variant == "wrong_scheme":
                scope["scheme"] = "http"
            elif variant == "missing_raw_path":
                del scope["raw_path"]
            elif variant == "length_mismatch":
                scope["headers"][1] = (b"content-length", b"1")
            response = await _call(app, scope, body)
            assert response[0]["status"] == 400
            assert response[1]["body"] == b""
            assert receiver.count() == 0

        await _with_startup(app, exercise)

    asyncio.run(scenario())


def test_duplicate_wire_authorization_is_rejected_before_receipt(tmp_path):
    from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI

    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver)

    async def scenario():
        async def exercise():
            body = _body()
            scope = _scope(body)
            scope["headers"].insert(2, (b"authorization", b"Bearer attacker"))
            response = await _call(app, scope, body)
            assert response[0]["status"] == 400
            assert receiver.count() == 0

        await _with_startup(app, exercise)

    asyncio.run(scenario())


def test_retry_and_conflicting_reuse_keep_one_receipt(tmp_path):
    from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI

    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver)

    async def scenario():
        async def exercise():
            original = _body()
            assert (await _call(app, _scope(original), original))[0]["status"] == 204
            assert (await _call(app, _scope(original), original))[0]["status"] == 204
            changed = _body({"status": "error"})
            assert (await _call(app, _scope(changed), changed))[0]["status"] == 409
            assert receiver.count() == 1

        await _with_startup(app, exercise)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("too_large_length", 413),
        ("too_large_body", 413),
        ("short_body", 400),
        ("malformed_event", 400),
        ("malformed_chunk", 400),
        ("too_many_chunks", 400),
    ],
)
def test_body_boundary_creates_no_receipt(tmp_path, variant, expected):
    from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI

    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver, max_body_bytes=256)

    async def scenario():
        async def exercise():
            body = _body()
            scope = _scope(body)
            messages = None
            if variant == "too_large_length":
                scope["headers"][1] = (b"content-length", b"257")
            elif variant == "too_large_body":
                messages = [{"type": "http.request", "body": b"x" * 257}]
            elif variant == "short_body":
                messages = [{"type": "http.request", "body": body[:-1]}]
            elif variant == "malformed_event":
                messages = [{"type": "unexpected", "body": body}]
            elif variant == "malformed_chunk":
                messages = [{"type": "http.request", "body": "not bytes"}]
            elif variant == "too_many_chunks":
                messages = [
                    {"type": "http.request", "body": b"", "more_body": True}
                ] * 129
            response = await _call(app, scope, body, messages=messages)
            assert response[0]["status"] == expected
            assert receiver.count() == 0

        await _with_startup(app, exercise)

    asyncio.run(scenario())


def test_streamed_body_is_accepted_only_when_complete(tmp_path):
    from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI

    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver)

    async def scenario():
        async def exercise():
            body = _body()
            messages = [
                {"type": "http.request", "body": body[:20], "more_body": True},
                {"type": "http.request", "body": body[20:], "more_body": False},
            ]
            assert (await _call(app, _scope(body), body, messages=messages))[0][
                "status"
            ] == 204
            assert receiver.count() == 1

        await _with_startup(app, exercise)

    asyncio.run(scenario())


def test_disconnect_before_complete_body_has_no_response_or_receipt(tmp_path):
    from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI

    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver)

    async def scenario():
        async def exercise():
            body = _body()
            messages = [
                {"type": "http.request", "body": body[:20], "more_body": True},
                {"type": "http.disconnect"},
            ]
            assert await _call(app, _scope(body), body, messages=messages) == []
            assert receiver.count() == 0

        await _with_startup(app, exercise)

    asyncio.run(scenario())


def test_only_notification_post_route_is_served(tmp_path):
    from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI

    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver)

    async def scenario():
        async def exercise():
            body = _body()
            scope = _scope(body)
            scope["raw_path"] = b"/other"
            assert (await _call(app, scope, body))[0]["status"] == 404
            scope = _scope(body)
            scope["method"] = "GET"
            assert (await _call(app, scope, body))[0]["status"] == 405
            assert receiver.count() == 0

        await _with_startup(app, exercise)

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["core", "unexpected"])
def test_startup_failure_and_pre_startup_request_never_accept(
    tmp_path, monkeypatch, failure
):
    from rentgen_core.errors import CoreError
    from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI

    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver)

    def fail_initialize():
        if failure == "core":
            raise CoreError("TEST_FAILURE", "private database path and token")
        raise RuntimeError("private database path and token")

    monkeypatch.setattr(receiver, "initialize", fail_initialize)

    async def scenario():
        body = _body()
        assert (await _call(app, _scope(body), body))[0]["status"] == 503
        incoming = iter([{"type": "lifespan.startup"}])
        sent = []

        async def receive():
            return next(incoming)

        async def send(message):
            sent.append(message)

        await app({"type": "lifespan"}, receive, send)
        assert sent == [
            {
                "type": "lifespan.startup.failed",
                "message": "Notification receiver unavailable",
            }
        ]
        assert (await _call(app, _scope(body), body))[0]["status"] == 503
        assert not (tmp_path / "receiver.sqlite3").exists()

    asyncio.run(scenario())


def test_storage_failure_after_startup_returns_fixed_503(tmp_path):
    from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI

    path = tmp_path / "receiver.sqlite3"
    receiver = NotificationReceiver(path, bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver)

    async def scenario():
        async def exercise():
            moved = tmp_path / "moved.sqlite3"
            path.rename(moved)
            path.mkdir()
            body = _body()
            response = await _call(app, _scope(body), body)
            assert response[0]["status"] == 503
            assert b"private" not in repr(response).encode()
            with sqlite3.connect(moved) as connection:
                assert (
                    connection.execute(
                        "SELECT count(*) FROM notification_receipts"
                    ).fetchone()[0]
                    == 0
                )

        await _with_startup(app, exercise)

    asyncio.run(scenario())


def test_unexpected_receiver_error_does_not_escape_http_boundary(tmp_path, monkeypatch):
    from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI

    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    app = NotificationReceiverASGI(receiver)

    def fail_accept(*_):
        raise RuntimeError("private token and database path")

    async def scenario():
        async def exercise():
            monkeypatch.setattr(receiver, "accept", fail_accept)
            body = _body()
            response = await _call(app, _scope(body), body)
            assert response == [
                {
                    "type": "http.response.start",
                    "status": 503,
                    "headers": [
                        (b"content-length", b"0"),
                        (b"cache-control", b"no-store"),
                    ],
                },
                {"type": "http.response.body", "body": b""},
            ]
            assert receiver.count() == 0

        await _with_startup(app, exercise)

    asyncio.run(scenario())
