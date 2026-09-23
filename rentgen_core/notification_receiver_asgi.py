"""Bounded ASGI request boundary for durable notification receipts."""

import asyncio
import re

from .errors import CoreError
from .notification_receiver import NotificationReceiver


_HEADER_NAME = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}\Z")
_CONTENT_LENGTH = re.compile(rb"[1-9][0-9]*\Z")


def _wire_headers(raw, max_body_bytes):
    """Validate uncombined ASGI headers before creating a mapping for the core."""
    if type(raw) is not list or len(raw) > 64:
        return None, 400
    headers = {}
    for pair in raw:
        if (
            type(pair) not in (tuple, list)
            or len(pair) != 2
            or type(pair[0]) is not bytes
            or type(pair[1]) is not bytes
        ):
            return None, 400
        name, value = pair
        if (
            _HEADER_NAME.fullmatch(name) is None
            or not 1 <= len(value) <= 8192
            or any(byte < 32 or byte > 126 for byte in value)
        ):
            return None, 400
        lowered = name.lower()
        if lowered in headers or lowered == b"transfer-encoding":
            return None, 400
        headers[lowered] = value
    length = headers.get(b"content-length")
    if length is None or _CONTENT_LENGTH.fullmatch(length) is None:
        return None, 400
    if len(length) > 7 or int(length) > max_body_bytes:
        return None, 413
    return (
        {
            name.decode("ascii"): value.decode("ascii")
            for name, value in headers.items()
        },
        int(length),
    ), None


class NotificationReceiverASGI:
    """Serve one notification route after explicit ASGI lifespan startup."""

    def __init__(self, receiver: NotificationReceiver, *, max_body_bytes=65536):
        if (
            not isinstance(receiver, NotificationReceiver)
            or type(max_body_bytes) is not int
            or not 1 <= max_body_bytes <= NotificationReceiver.MAX_BODY_BYTES
        ):
            raise CoreError(
                "NOTIFICATION_RECEIVER_INVALID", "Invalid ASGI configuration"
            )
        self._receiver = receiver
        self._max_body_bytes = max_body_bytes
        self._ready = False

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
            return
        if scope["type"] == "http":
            await self._http(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})

    async def _lifespan(self, receive, send):
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    await asyncio.to_thread(self._receiver.initialize)
                except (CoreError, OSError):
                    self._ready = False
                    await send(
                        {
                            "type": "lifespan.startup.failed",
                            "message": "Notification receiver unavailable",
                        }
                    )
                    return
                self._ready = True
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                self._ready = False
                await send({"type": "lifespan.shutdown.complete"})
                return

    @staticmethod
    async def _reply(send, status):
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-length", b"0"), (b"cache-control", b"no-store")],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    async def _http(self, scope, receive, send):
        if not self._ready:
            await self._reply(send, 503)
            return
        if "raw_path" not in scope or type(scope["raw_path"]) is not bytes:
            await self._reply(send, 400)
            return
        if scope["raw_path"] != b"/notifications":
            await self._reply(send, 404)
            return
        if scope.get("method") != "POST":
            await self._reply(send, 405)
            return
        if scope.get("scheme") != "https":
            await self._reply(send, 400)
            return
        if scope.get("query_string", b"") != b"" or scope.get("root_path", "") != "":
            await self._reply(send, 400)
            return
        parsed, error = _wire_headers(scope.get("headers"), self._max_body_bytes)
        if error is not None:
            await self._reply(send, error)
            return
        headers, expected_length = parsed
        chunks = []
        received_length = 0
        for _ in range(128):
            message = await receive()
            if type(message) is not dict:
                await self._reply(send, 400)
                return
            if message.get("type") == "http.disconnect":
                return
            if message.get("type") != "http.request":
                await self._reply(send, 400)
                return
            chunk = message.get("body", b"")
            more = message.get("more_body", False)
            if type(chunk) is not bytes or type(more) is not bool:
                await self._reply(send, 400)
                return
            received_length += len(chunk)
            if received_length > self._max_body_bytes:
                await self._reply(send, 413)
                return
            if received_length > expected_length:
                await self._reply(send, 400)
                return
            chunks.append(chunk)
            if not more:
                break
        else:
            await self._reply(send, 400)
            return
        if received_length != expected_length:
            await self._reply(send, 400)
            return
        body = b"".join(chunks)
        try:
            result = await asyncio.to_thread(self._receiver.accept, headers, body)
        except CoreError:
            await self._reply(send, 503)
            return
        await self._reply(send, result.http_status)
