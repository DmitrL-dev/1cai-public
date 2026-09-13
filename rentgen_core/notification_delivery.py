"""Explicit, bounded HTTPS delivery for the Git watcher notification outbox."""

from dataclasses import dataclass
from datetime import datetime
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


class DeliveryStatus(str, Enum):
    ACCEPTED = "accepted"
    RETRYABLE = "retryable"
    PERMANENT = "permanent"


@dataclass(frozen=True)
class DeliveryResult:
    """Safe receipt: never contains endpoint, credentials or response content."""

    status: DeliveryStatus
    notification_id: int | None
    idempotency_key: str | None
    code: str
    http_status: int | None = None


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
            or type(namespace) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", namespace) is None
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
            else hashlib.sha256(
                f"rentgen-notification-v1:{self._namespace}:{notification_id}".encode(
                    "ascii"
                )
            ).hexdigest()
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


def deliver_outbox(outbox, adapter, limit=100):
    """Attempt a bounded batch and ack only accepted events.

    The caller serializes consumers and explicitly decides when to retry pending
    events. Acceptance followed by an ack failure can cause a later duplicate;
    the receiver must deduplicate the stable idempotency key.
    """
    if (
        not isinstance(outbox, NotificationOutbox)
        or not isinstance(adapter, WebhookAdapter)
        or not _bounded_int(limit, NotificationOutbox.MAX_EVENTS)
    ):
        raise _invalid()
    notifications = outbox.peek(NotificationOutbox.MAX_EVENTS)
    # Validate the entire bounded queue before the first external side effect.
    try:
        for notification in notifications:
            _payload(notification, NotificationOutbox.MAX_BYTES)
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise CoreError(
            "NOTIFICATION_DELIVERY_INVALID", "Malformed outbox notification"
        ) from None
    results = []
    for notification in notifications[:limit]:
        receipt = adapter.deliver(notification)
        results.append(receipt)
        if receipt.status is DeliveryStatus.ACCEPTED:
            outbox.ack(notification["id"])
    return tuple(results)
