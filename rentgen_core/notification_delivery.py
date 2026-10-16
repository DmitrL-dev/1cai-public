"""Explicit, bounded HTTPS delivery for the Git watcher notification outbox."""

from dataclasses import dataclass, replace as _replace
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .errors import CoreError
from .git_watcher import NotificationOutbox
from .notification_journal import (
    DeliveryJournal,
    RetryPolicy,
    idempotency_key,
    utc_now,
    valid_namespace,
)


class DeliveryStatus(str, Enum):
    ACCEPTED = "accepted"
    RETRYABLE = "retryable"
    PERMANENT = "permanent"


@dataclass(frozen=True)
class DeliveryResult:
    """Safe receipt: never contains endpoint, credentials or response content.

    ``attempt`` and ``next_attempt_at`` are set only by a journaled run: the
    durable attempt number and, for a scheduled retry, the earliest UTC time.
    """

    status: DeliveryStatus
    notification_id: int | None
    idempotency_key: str | None
    code: str
    http_status: int | None = None
    attempt: int | None = None
    next_attempt_at: str | None = None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _send(request, *, timeout):
    # No environment proxy, redirect, cookie jar, auth retry or global opener.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    return opener.open(request, timeout=timeout)


def _invalid():
    return CoreError("NOTIFICATION_DELIVERY_INVALID", "Invalid delivery configuration")


def _bounded_int(value, upper):
    return type(value) is int and 1 <= value <= upper


def _host(value):
    return (
        type(value) is str
        and 1 <= len(value) <= 253
        and all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in value.split(".")
        )
    )


def _payload(notification, max_bytes):
    """Validate the existing queue envelope before serializing its event."""
    if (
        type(notification) is not dict
        or set(notification) != {"id", "event", "created_at"}
        or not _bounded_int(notification["id"], 2**63 - 1)
        or type(notification["event"]) is not dict
        or type(notification["created_at"]) is not str
        or not 1 <= len(notification["created_at"]) <= 64
    ):
        raise ValueError("Invalid notification")
    timestamp = datetime.fromisoformat(notification["created_at"])
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Invalid notification timestamp")
    _json_value(notification["event"])
    raw = json.dumps(
        notification,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(raw) > max_bytes:
        raise ValueError("Notification payload too large")
    return raw


def _json_value(value, depth=0):
    if depth > 64:
        raise ValueError("Notification nesting limit exceeded")
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("JSON object keys must be strings")
            _json_value(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError("JSON values required")


class WebhookAdapter:
    """Send once to an explicitly allowed HTTPS host; never retry internally.

    A custom sender must implement ``sender(request, timeout=seconds)`` and
    return a closable response with integer ``status`` and bounded ``read(n)``.
    The caller owns this trusted transport and its handling of credentials.
    """

    def __init__(
        self,
        endpoint,
        *,
        allowed_hosts,
        namespace,
        bearer_token=None,
        timeout=10,
        max_payload_bytes=65536,
        max_response_bytes=4096,
        sender=None,
    ):
        if (
            type(endpoint) is not str
            or not 1 <= len(endpoint) <= 2048
            or any(ord(char) <= 32 or ord(char) >= 127 for char in endpoint)
            or "\\" in endpoint
            or not isinstance(allowed_hosts, (set, frozenset))
            or not 1 <= len(allowed_hosts) <= 100
            or not all(_host(host) for host in allowed_hosts)
            or not valid_namespace(namespace)
            or type(timeout) not in (int, float)
            or not 0.1 <= timeout <= 30
            or not _bounded_int(max_payload_bytes, 1048576)
            or not _bounded_int(max_response_bytes, 65536)
            or (sender is not None and not callable(sender))
        ):
            raise _invalid()
        if bearer_token is not None and (
            type(bearer_token) is not str
            or re.fullmatch(r"[A-Za-z0-9._~+/-]{1,4096}=*", bearer_token) is None
            or len(bearer_token) > 4096
        ):
            raise _invalid()
        try:
            parsed = urllib.parse.urlsplit(endpoint)
            valid = (
                parsed.scheme == "https"
                and parsed.hostname in allowed_hosts
                and parsed.username is None
                and parsed.password is None
                and not parsed.query
                and not parsed.fragment
                and "?" not in endpoint
                and "#" not in endpoint
                and parsed.port != 0
                and (
                    bearer_token is None
                    or bearer_token not in urllib.parse.unquote(endpoint)
                )
            )
        except ValueError:
            raise _invalid() from None
        if not valid:
            raise _invalid()
        self._endpoint = endpoint
        self._namespace = namespace
        self._bearer_token = bearer_token
        self._timeout = float(timeout)
        self._max_payload_bytes = max_payload_bytes
        self._max_response_bytes = max_response_bytes
        self._sender = _send if sender is None else sender

    def deliver(self, notification):
        """Return a typed result for one attempt; invalid envelopes never send."""
        notification_id = notification.get("id") if type(notification) is dict else None
        if not _bounded_int(notification_id, 2**63 - 1):
            notification_id = None
        key = (
            None
            if notification_id is None
            else idempotency_key(self._namespace, notification_id)
        )
        try:
            raw = _payload(notification, self._max_payload_bytes)
        except (TypeError, ValueError, OverflowError, RecursionError):
            return DeliveryResult(
                DeliveryStatus.PERMANENT, notification_id, key, "INVALID_NOTIFICATION"
            )

        def result(status, code, http_status=None):
            return DeliveryResult(status, notification_id, key, code, http_status)

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "Idempotency-Key": key,
        }
        if self._bearer_token is not None:
            headers["Authorization"] = "Bearer " + self._bearer_token
        request = urllib.request.Request(
            self._endpoint, data=raw, headers=headers, method="POST"
        )
        response = None
        try:
            try:
                response = self._sender(request, timeout=self._timeout)
            except urllib.error.HTTPError as exc:
                response = exc
            status = response.status
            if type(status) is not int or not 100 <= status <= 599:
                return result(DeliveryStatus.PERMANENT, "INVALID_RESPONSE")
            body = response.read(self._max_response_bytes + 1)
            if type(body) is not bytes or len(body) > self._max_response_bytes:
                return result(DeliveryStatus.PERMANENT, "INVALID_RESPONSE", status)
            if 200 <= status <= 299:
                return result(DeliveryStatus.ACCEPTED, "HTTP_ACCEPTED", status)
            if 500 <= status <= 599:
                return result(DeliveryStatus.RETRYABLE, "HTTP_SERVER_ERROR", status)
            return result(DeliveryStatus.PERMANENT, "HTTP_REJECTED", status)
        except (urllib.error.URLError, OSError, http.client.HTTPException):
            return result(DeliveryStatus.RETRYABLE, "TRANSPORT_ERROR")
        except Exception:
            # Third-party senders can include headers/credentials in errors.
            return result(DeliveryStatus.PERMANENT, "INVALID_RESPONSE")
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass


def deliver_outbox(
    outbox,
    adapter,
    limit=100,
    *,
    authorize,
    journal=None,
    retry_policy=None,
    clock=None,
):
    """Attempt a bounded batch and ack only accepted events.

    ``authorize`` is the caller's current-permission check: it runs before
    every send and every ack, and its refusal stops the batch with the event
    still pending. Without ``journal`` every invocation attempts each selected
    event once and the caller decides when to run again; acceptance followed by
    an ack failure can then cause a later duplicate that the receiver must
    deduplicate by the stable idempotency key.

    With a ``DeliveryJournal`` the run is serialized by the journal lock and
    durable: each attempt is counted before sending, retryable outcomes are
    scheduled by ``retry_policy`` (default ``RetryPolicy()``), permanent or
    exhausted events become terminal, and an accepted event is acknowledged
    without being sent again. ``clock`` is a trusted test/host clock returning
    timezone-aware time.
    """
    if (
        not isinstance(outbox, NotificationOutbox)
        or not isinstance(adapter, WebhookAdapter)
        or not _bounded_int(limit, NotificationOutbox.MAX_EVENTS)
        or not callable(authorize)
        or (journal is not None and not isinstance(journal, DeliveryJournal))
        or (retry_policy is not None and not isinstance(retry_policy, RetryPolicy))
        or (clock is not None and not callable(clock))
        or (journal is None and (retry_policy is not None or clock is not None))
    ):
        raise _invalid()
    if journal is not None:
        return _deliver_journaled(
            outbox,
            adapter,
            limit,
            authorize,
            journal,
            RetryPolicy() if retry_policy is None else retry_policy,
            clock,
        )
    notifications, _ = _read_batch(outbox)
    results = []
    for notification in notifications[:limit]:
        authorize()
        receipt = adapter.deliver(notification)
        results.append(receipt)
        if receipt.status is DeliveryStatus.ACCEPTED:
            authorize()
            outbox.ack(notification["id"])
    return tuple(results)


def _read_batch(outbox):
    # Validate the entire bounded queue before the first external side effect.
    notifications = outbox.peek(NotificationOutbox.MAX_EVENTS)
    try:
        payloads = [
            _payload(notification, NotificationOutbox.MAX_BYTES)
            for notification in notifications
        ]
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise CoreError(
            "NOTIFICATION_DELIVERY_INVALID", "Malformed outbox notification"
        ) from None
    return notifications, payloads


def _deliver_journaled(
    outbox, adapter, limit, authorize, journal, policy, clock
):
    results = []
    with journal._session(adapter._namespace) as session:
        # Read after acquiring the consumer lock: an earlier queue snapshot
        # could otherwise prune attempts committed while this consumer waited.
        notifications, payloads = _read_batch(outbox)
        digests = {
            notification["id"]: hashlib.sha256(raw).hexdigest()
            for notification, raw in zip(notifications, payloads)
        }
        session.reconcile(digests, utc_now(clock), policy)
        for notification in notifications:
            if len(results) >= limit:
                break
            notification_id = notification["id"]
            key = idempotency_key(adapter._namespace, notification_id)
            entry = session.entry(notification_id)
            state = None if entry is None else entry["state"]
            if state == "terminal":
                continue
            if state == "pending" and not session.due(entry, utc_now(clock), policy):
                continue
            if state == "accepted":
                # Accepted earlier, ack interrupted: acknowledge, never resend.
                authorize()
                outbox.ack(notification_id)
                session.forget(notification_id)
                results.append(
                    DeliveryResult(
                        DeliveryStatus.ACCEPTED,
                        notification_id,
                        key,
                        "ACK_RECOVERED",
                        attempt=entry["attempts"],
                    )
                )
                continue
            authorize()
            attempt = session.begin(
                notification_id, key, digests[notification_id], utc_now(clock)
            )
            receipt = adapter.deliver(notification)
            finished = utc_now(clock)
            if receipt.status is DeliveryStatus.ACCEPTED:
                session.accepted(notification_id, finished)
                results.append(_replace(receipt, attempt=attempt))
                authorize()
                outbox.ack(notification_id)
                session.forget(notification_id)
            elif (
                receipt.status is DeliveryStatus.RETRYABLE
                and attempt < policy.max_attempts
            ):
                next_attempt = finished + timedelta(
                    seconds=policy.delay_seconds(attempt)
                )
                session.retry(notification_id, receipt.code, next_attempt, finished)
                results.append(
                    _replace(
                        receipt,
                        attempt=attempt,
                        next_attempt_at=next_attempt.isoformat(),
                    )
                )
            else:
                session.terminal(notification_id, receipt.code, finished)
                if receipt.status is DeliveryStatus.RETRYABLE:
                    receipt = DeliveryResult(
                        DeliveryStatus.PERMANENT,
                        notification_id,
                        key,
                        "RETRY_EXHAUSTED",
                        receipt.http_status,
                    )
                results.append(_replace(receipt, attempt=attempt))
    return tuple(results)
