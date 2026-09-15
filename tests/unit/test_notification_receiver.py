"""Durable notification receiver contract tests; no external network."""

import json
import io
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from urllib.error import URLError

import pytest

from rentgen_core.errors import CoreError


def api():
    from rentgen_core.notification_receiver import NotificationReceiver, ReceiverStatus

    return NotificationReceiver, ReceiverStatus


def notification(notification_id=1, event=None):
    return {
        "id": notification_id,
        "event": {"status": "analyzed"} if event is None else event,
        "created_at": "2026-09-15T00:00:00+00:00",
    }


def headers(token="test-secret-123", key=None, content_type="application/json"):
    return {
        "Authorization": "Bearer " + token,
        "Idempotency-Key": key or "a" * 64,
        "Content-Type": content_type,
    }


def receiver(tmp_path):
    cls, _ = api()
    instance = cls(tmp_path / "receiver.sqlite3", bearer_token="test-secret-123")
    instance.initialize()
    return instance


def body(value, *, pretty=False):
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        sort_keys=pretty,
    ).encode("utf-8")


def test_accepts_then_deduplicates_canonical_payload(tmp_path):
    instance = receiver(tmp_path)
    _, status = api()
    first = instance.accept(headers(), body(notification()))
    duplicate = instance.accept(headers(), body(notification(), pretty=True))
    assert first.status is status.ACCEPTED
    assert first.http_status == 204
    assert duplicate.status is status.DUPLICATE
    assert duplicate.http_status == 204
    assert duplicate.idempotency_key == first.idempotency_key
    assert duplicate.payload_digest == first.payload_digest
    assert instance.count() == 1


def test_rejects_conflicting_replay_without_mutating_store(tmp_path):
    instance = receiver(tmp_path)
    _, status = api()
    first = instance.accept(headers(), body(notification()))
    conflict = instance.accept(headers(), body(notification(event={"status": "error"})))
    assert first.status is status.ACCEPTED
    assert conflict.status is status.CONFLICT
    assert conflict.http_status == 409
    assert instance.count() == 1


@pytest.mark.parametrize(
    "request_headers,request_body,code,status_code",
    [
        (headers(token="wrong"), body(notification()), "UNAUTHORIZED", 401),
        (
            {"Authorization": "Bearer test-secret-123"},
            body(notification()),
            "INVALID_REQUEST",
            400,
        ),
        (
            headers(content_type="text/plain"),
            body(notification()),
            "INVALID_REQUEST",
            400,
        ),
        (headers(), b"{}", "INVALID_REQUEST", 400),
        (headers(key="A" * 64), body(notification()), "INVALID_REQUEST", 400),
    ],
)
def test_invalid_requests_are_rejected_without_write(
    tmp_path, request_headers, request_body, code, status_code
):
    instance = receiver(tmp_path)
    _, status = api()
    result = instance.accept(request_headers, request_body)
    assert result.status is status.REJECTED
    assert result.code == code
    assert result.http_status == status_code
    assert instance.count() == 0


def test_body_limit_is_checked_before_json_parse(tmp_path):
    cls, status = api()
    instance = cls(
        tmp_path / "receiver.sqlite3",
        bearer_token="test-secret-123",
        max_body_bytes=64,
    )
    instance.initialize()
    result = instance.accept(headers(), b"x" * 65)
    assert result.status is status.REJECTED
    assert result.code == "PAYLOAD_TOO_LARGE"
    assert result.http_status == 413
    assert instance.count() == 0


def test_concurrent_same_key_has_one_commit_and_one_duplicate(tmp_path):
    instance = receiver(tmp_path)
    payload = body(notification())

    def submit(_):
        return instance.accept(headers(), payload)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))
    _, status = api()
    assert [item.status for item in results].count(status.ACCEPTED) == 1
    assert [item.status for item in results].count(status.DUPLICATE) == 7
    assert instance.count() == 1


def test_malformed_existing_database_fails_closed(tmp_path):
    path = tmp_path / "receiver.sqlite3"
    path.write_bytes(b"not sqlite")
    cls, _ = api()
    instance = cls(path, bearer_token="test-secret-123")
    with pytest.raises(CoreError) as caught:
        instance.initialize()
    assert caught.value.code == "NOTIFICATION_RECEIVER_RECOVERY_REQUIRED"
    assert "test-secret-123" not in str(caught.value)


def test_constructor_rejects_unsafe_configuration(tmp_path):
    cls, _ = api()
    with pytest.raises(CoreError) as caught:
        cls(tmp_path / "receiver.sqlite3", bearer_token="bad\nsecret")
    assert caught.value.code == "NOTIFICATION_RECEIVER_INVALID"


@pytest.mark.parametrize(
    "payload",
    [
        b'{"id":2,"id":1,"event":{},"created_at":"2026-09-15T00:00:00+00:00"}',
        body(notification()).replace(
            b'"status": "analyzed"', b'"status":"error","status":"analyzed"'
        ),
    ],
)
def test_duplicate_json_members_fail_closed(tmp_path, payload):
    instance = receiver(tmp_path)
    result = instance.accept(headers(), payload)
    assert result.http_status == 400
    assert instance.count() == 0


def test_token_padding_counts_toward_configuration_limit(tmp_path):
    cls, _ = api()
    with pytest.raises(CoreError) as caught:
        cls(tmp_path / "receiver.sqlite3", bearer_token="a" + "=" * 4096)
    assert caught.value.code == "NOTIFICATION_RECEIVER_INVALID"


@pytest.mark.parametrize(
    "mutation",
    [
        "CREATE TRIGGER discard AFTER INSERT ON notification_receipts "
        "BEGIN DELETE FROM notification_receipts; END",
        "CREATE VIEW shadow AS SELECT * FROM notification_receipts",
        "ALTER TABLE notification_receipts RENAME TO old_receipts; "
        "CREATE TABLE notification_receipts "
        "(idempotency_key TEXT, payload_digest TEXT NOT NULL, received_at TEXT NOT NULL); "
        "DROP TABLE old_receipts",
        "DROP TABLE receiver_meta; CREATE TABLE receiver_meta (schema TEXT); "
        "INSERT INTO receiver_meta VALUES ('1')",
    ],
)
@pytest.mark.parametrize("operation", ["initialize", "accept", "count"])
def test_unrecognized_schema_is_rejected(tmp_path, mutation, operation):
    instance = receiver(tmp_path)
    with closing(sqlite3.connect(instance.path)) as connection:
        connection.executescript(mutation)
    with pytest.raises(CoreError) as caught:
        if operation == "accept":
            instance.accept(headers(), body(notification()))
        else:
            getattr(instance, operation)()
    assert caught.value.code == "NOTIFICATION_RECEIVER_RECOVERY_REQUIRED"


@pytest.mark.parametrize(
    "key,digest,timestamp",
    [
        (None, "b" * 64, "2026-09-15T00:00:00+00:00"),
        ("A" * 64, "b" * 64, "2026-09-15T00:00:00+00:00"),
        ("b" * 64, "not-a-digest", "2026-09-15T00:00:00+00:00"),
        ("b" * 64, "c" * 64, "not-a-timestamp"),
    ],
)
@pytest.mark.parametrize("operation", ["initialize", "accept", "count"])
def test_malformed_receipts_block_all_store_operations(
    tmp_path, key, digest, timestamp, operation
):
    instance = receiver(tmp_path)
    with closing(sqlite3.connect(instance.path)) as connection:
        connection.execute(
            "INSERT INTO notification_receipts VALUES (?, ?, ?)",
            (key, digest, timestamp),
        )
        connection.commit()
    with pytest.raises(CoreError) as caught:
        if operation == "accept":
            instance.accept(headers(), body(notification()))
        else:
            getattr(instance, operation)()
    assert caught.value.code == "NOTIFICATION_RECEIVER_RECOVERY_REQUIRED"


@pytest.mark.parametrize("suffix", ["", "-journal", "-wal", "-shm"])
def test_hardlinked_database_and_sidecars_are_rejected(tmp_path, suffix):
    instance = receiver(tmp_path)
    alias = tmp_path / "foreign.sqlite3"
    if suffix:
        alias.write_bytes(b"foreign state")
        os.link(alias, str(instance.path) + suffix)
    else:
        os.link(instance.path, alias)
    original = alias.read_bytes()
    with pytest.raises(CoreError) as caught:
        instance.accept(headers(), body(notification()))
    assert caught.value.code == "NOTIFICATION_RECEIVER_CONFLICT"
    assert alias.read_bytes() == original


def test_missing_initialized_database_is_not_recreated(tmp_path):
    instance = receiver(tmp_path)
    instance.path.unlink()
    with pytest.raises(CoreError):
        instance.accept(headers(), body(notification()))
    assert not instance.path.exists()


def test_over_limit_state_blocks_duplicate_acknowledgement(tmp_path, monkeypatch):
    instance = receiver(tmp_path)
    payload = body(notification())
    instance.accept(headers(), payload)
    instance.accept(headers(key="b" * 64), payload)
    monkeypatch.setattr(instance, "MAX_RECEIPTS", 1)
    with pytest.raises(CoreError) as caught:
        instance.accept(headers(), payload)
    assert caught.value.code == "NOTIFICATION_RECEIVER_LIMIT"


@pytest.mark.parametrize(
    "extra",
    [{"Bad Name": "x"}, {"Bad:Name": "x"}, {f"X-{index}": "x" for index in range(65)}],
)
def test_invalid_or_unbounded_header_fields_are_rejected(tmp_path, extra):
    instance = receiver(tmp_path)
    assert (
        instance.accept({**headers(), **extra}, body(notification())).http_status == 400
    )
    assert instance.count() == 0


def test_oversized_store_fails_before_opening_sqlite(tmp_path):
    instance = receiver(tmp_path)
    with instance.path.open("r+b") as stream:
        stream.truncate(64 * 1024**2 + 1)
    with pytest.raises(CoreError) as caught:
        instance.accept(headers(), body(notification()))
    assert caught.value.code == "NOTIFICATION_RECEIVER_LIMIT"


def test_failed_reinitialization_revokes_readiness(tmp_path):
    instance = receiver(tmp_path)
    with closing(sqlite3.connect(instance.path)) as connection:
        connection.execute("UPDATE receiver_meta SET schema=2")
        connection.commit()
    with pytest.raises(CoreError):
        instance.initialize()
    with closing(sqlite3.connect(instance.path)) as connection:
        connection.execute("UPDATE receiver_meta SET schema=1")
        connection.commit()
    with pytest.raises(CoreError) as caught:
        instance.accept(headers(), body(notification()))
    assert caught.value.code == "NOTIFICATION_RECEIVER_NOT_INITIALIZED"


@pytest.mark.parametrize("operation", ["initialize", "accept"])
def test_busy_store_is_retryable_without_writing(tmp_path, operation):
    instance = receiver(tmp_path)
    with closing(sqlite3.connect(instance.path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        with pytest.raises(CoreError) as caught:
            if operation == "accept":
                instance.accept(headers(), body(notification()))
            else:
                instance.initialize()
        assert caught.value.code == "NOTIFICATION_RECEIVER_UNAVAILABLE"
        connection.rollback()
    instance.initialize()
    assert instance.count() == 0


@pytest.mark.parametrize("phase", ["before", "after"])
def test_commit_failure_never_acknowledges_and_retry_is_safe(
    tmp_path, monkeypatch, phase
):
    instance = receiver(tmp_path)
    connect = sqlite3.connect

    class FailedCommit(sqlite3.Connection):
        def commit(self):
            if phase == "after":
                super().commit()
            raise sqlite3.OperationalError("commit outcome unavailable")

    def failing_connect(*args, **kwargs):
        return connect(*args, **kwargs, factory=FailedCommit)

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", failing_connect)
        with pytest.raises(CoreError) as caught:
            instance.accept(headers(), body(notification()))
        assert caught.value.code == "NOTIFICATION_RECEIVER_UNAVAILABLE"
    assert instance.count() == (0 if phase == "before" else 1)
    retried = instance.accept(headers(), body(notification()))
    assert retried.status.value == ("accepted" if phase == "before" else "duplicate")
    assert instance.count() == 1


def test_independent_receivers_serialize_conflicting_payloads(tmp_path):
    first = receiver(tmp_path)
    second = receiver(tmp_path)
    barrier = Barrier(2)

    def submit(pair):
        instance, value = pair
        barrier.wait(timeout=5)
        return instance.accept(headers(), body(notification(event={"value": value})))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, [(first, "one"), (second, "two")]))
    assert sorted(item.status.value for item in results) == ["accepted", "conflict"]
    assert first.count() == second.count() == 1


def test_outbox_retry_after_lost_response_reopens_durable_receipt(tmp_path):
    from rentgen_core import DeliveryStatus, WebhookAdapter, deliver_outbox
    from rentgen_core.git_watcher import NotificationOutbox

    instance = receiver(tmp_path)
    queue = NotificationOutbox(tmp_path / "outbox.json")
    queue.enqueue({"private": "private-note-123"})
    received = []

    class Response(io.BytesIO):
        status = 204

    def sender(request, *, timeout):
        received.append(instance.accept(dict(request.header_items()), request.data))
        if len(received) == 1:
            raise URLError("response lost after commit")
        return Response()

    adapter = WebhookAdapter(
        "https://receiver.example.test/notifications",
        allowed_hosts={"receiver.example.test"},
        namespace="receiver-test",
        bearer_token="test-secret-123",
        sender=sender,
    )
    assert deliver_outbox(queue, adapter)[0].status is DeliveryStatus.RETRYABLE
    assert len(queue.peek()) == 1
    instance = receiver(tmp_path)
    assert deliver_outbox(queue, adapter)[0].status is DeliveryStatus.ACCEPTED
    assert queue.peek() == []
    assert [item.status.value for item in received] == ["accepted", "duplicate"]
    assert instance.count() == 1
    stored = instance.path.read_bytes()
    assert b"private-note-123" not in stored
    assert b"test-secret-123" not in stored
    assert "private-note-123" not in repr(received)
    assert "test-secret-123" not in repr(received)


def test_changed_journal_mode_requires_recovery(tmp_path):
    instance = receiver(tmp_path)
    with closing(sqlite3.connect(instance.path)) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    with pytest.raises(CoreError) as caught:
        instance.accept(headers(), body(notification()))
    assert caught.value.code == "NOTIFICATION_RECEIVER_RECOVERY_REQUIRED"


@pytest.mark.parametrize(
    "request_headers,request_body",
    [
        (
            {**headers(), "authorization": "Bearer test-secret-123"},
            body(notification()),
        ),
        (headers(key="a" * 64 + "\n"), body(notification())),
        (
            headers(content_type="application/json; charset=latin-1"),
            body(notification()),
        ),
        (
            headers(content_type="application/json; charset=utf-8; charset=utf-8"),
            body(notification()),
        ),
        ({**headers(), "X-Unsafe": "value\r\nInjected: yes"}, body(notification())),
        (headers(), b"\xff"),
        (headers(), body(notification()).decode("utf-8")),
        (
            headers(),
            b'{"id":1,"event":{"text":"\\ud800"},"created_at":"2026-09-15T00:00:00Z"}',
        ),
        (headers(), body(notification(event={"value": float("nan")}))),
        (headers(), body(notification(event={"value": float("inf")}))),
        (headers(), body({**notification(), "id": True})),
        (headers(), body({**notification(), "created_at": "2026-09-15T00:00:00"})),
        (headers(), body({**notification(), "event": []})),
        (headers(), body({**notification(), "extra": "rejected"})),
        (
            headers(),
            b'{"id":1,"event":{"nested":'
            + b"[" * 66
            + b"0"
            + b"]" * 66
            + b'},"created_at":"2026-09-15T00:00:00Z"}',
        ),
    ],
)
def test_malformed_request_never_acknowledges_existing_key(
    tmp_path, request_headers, request_body
):
    instance = receiver(tmp_path)
    instance.accept(headers(), body(notification()))
    before = instance.path.read_bytes()
    assert instance.accept(request_headers, request_body).http_status == 400
    assert instance.path.read_bytes() == before


def test_exact_body_limit_and_utf8_canonicalization(tmp_path):
    cls, status = api()
    payload = body(notification(event={"text": "Кириллица"}))
    instance = cls(
        tmp_path / "receiver.sqlite3",
        bearer_token="test-secret-123",
        max_body_bytes=len(payload),
    )
    instance.initialize()
    assert (
        instance.accept(
            headers(content_type="Application/JSON; Charset=UTF-8"), payload
        ).status
        is status.ACCEPTED
    )
    assert instance.accept(headers(), payload + b" ").http_status == 413


def test_capacity_keeps_existing_receipts_but_rejects_new_keys(tmp_path, monkeypatch):
    instance = receiver(tmp_path)
    monkeypatch.setattr(instance, "MAX_RECEIPTS", 1)
    payload = body(notification())
    instance.accept(headers(), payload)
    assert instance.accept(headers(), payload).status.value == "duplicate"
    assert (
        instance.accept(
            headers(), body(notification(event={"different": True}))
        ).http_status
        == 409
    )
    with pytest.raises(CoreError) as caught:
        instance.accept(headers(key="b" * 64), payload)
    assert caught.value.code == "NOTIFICATION_RECEIVER_LIMIT"
    assert instance.count() == 1


@pytest.mark.parametrize("suffix", [":hidden", ".", " ", "\x00"])
def test_ambiguous_windows_paths_are_invalid_configuration(tmp_path, suffix):
    if os.name != "nt" and suffix != "\x00":
        pytest.skip("Windows filesystem naming contract")
    cls, _ = api()
    with pytest.raises(CoreError) as caught:
        cls(str(tmp_path / "receiver.sqlite3") + suffix, bearer_token="test-secret-123")
    assert caught.value.code == "NOTIFICATION_RECEIVER_INVALID"


def test_junction_parent_is_rejected_without_creating_database(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows junction contract")
    import _winapi

    target = tmp_path / "owned"
    target.mkdir()
    junction = tmp_path / "redirected"
    _winapi.CreateJunction(str(target), str(junction))
    cls, _ = api()
    instance = cls(junction / "receiver.sqlite3", bearer_token="test-secret-123")
    with pytest.raises(CoreError) as caught:
        instance.initialize()
    assert caught.value.code == "NOTIFICATION_RECEIVER_CONFLICT"
    assert list(target.iterdir()) == []


def test_empty_preexisting_database_is_not_silently_initialized(tmp_path):
    path = tmp_path / "receiver.sqlite3"
    path.touch()
    cls, _ = api()
    instance = cls(path, bearer_token="test-secret-123")
    with pytest.raises(CoreError) as caught:
        instance.initialize()
    assert caught.value.code == "NOTIFICATION_RECEIVER_RECOVERY_REQUIRED"
    assert path.read_bytes() == b""
