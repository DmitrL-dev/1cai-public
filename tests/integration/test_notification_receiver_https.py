"""Loopback TLS proof for the existing sender and checkout ASGI receiver."""

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import urllib.request

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest
import uvicorn

from rentgen_core.notification_delivery import DeliveryStatus, WebhookAdapter
from rentgen_core.notification_receiver import NotificationReceiver
from rentgen_core.notification_receiver_asgi import NotificationReceiverASGI


TOKEN = "test-secret-123"


def _certificate(tmp_path: Path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "loopback-cert.pem"
    key_path = tmp_path / "loopback-key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


async def _start_server(receiver, cert_path, key_path):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(10)
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        NotificationReceiverASGI(receiver),
        host="127.0.0.1",
        port=port,
        ssl_certfile=str(cert_path),
        ssl_keyfile=str(key_path),
        proxy_headers=False,
        access_log=False,
        ws="none",
        lifespan="on",
        log_level="critical",
        log_config=None,
        timeout_keep_alive=2,
        http="httptools",
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        for _ in range(500):
            if server.started:
                return server, task, sock, port
            if task.done():
                await task
                raise AssertionError("TLS test server stopped before startup")
            await asyncio.sleep(0.01)
        raise AssertionError("TLS test server did not start")
    except BaseException:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=5)
        finally:
            sock.close()
        raise


async def _stop_server(server, task, sock):
    server.should_exit = True
    try:
        await asyncio.wait_for(task, timeout=5)
    finally:
        sock.close()


def _sender(cert_path):
    context = ssl.create_default_context(
        cafile=str(cert_path) if cert_path is not None else None
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=context),
        NoRedirect(),
    )

    def send(request, *, timeout):
        return opener.open(request, timeout=timeout)

    return send


def _adapter(port, sender):
    return WebhookAdapter(
        f"https://127.0.0.1:{port}/notifications",
        allowed_hosts={"127.0.0.1"},
        namespace="test",
        bearer_token=TOKEN,
        timeout=3,
        sender=sender,
    )


def _plain_http(port, notification):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    body = json.dumps(notification, sort_keys=True, separators=(",", ":")).encode()
    key = hashlib.sha256(b"rentgen-notification-v1:test:1").hexdigest()
    try:
        connection.request(
            "POST",
            "/notifications",
            body=body,
            headers={
                "Authorization": "Bearer " + TOKEN,
                "Idempotency-Key": key,
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        response = connection.getresponse()
        return response.status
    except (OSError, http.client.HTTPException):
        return None
    finally:
        connection.close()


def _wire_header_variant(port, cert_path, notification, variant):
    body = json.dumps(notification, sort_keys=True, separators=(",", ":")).encode()
    key = hashlib.sha256(b"rentgen-notification-v1:test:1").hexdigest()
    length = str(len(body)).encode()
    if variant == "duplicate":
        length_headers = (
            b"Content-Length: "
            + length
            + b"\r\n"
            + b"Content-Length: "
            + length
            + b"\r\n"
        )
    elif variant == "comma":
        length_headers = b"Content-Length: " + length + b", " + length + b"\r\n"
    elif variant == "leading_zero":
        length_headers = b"Content-Length: 0" + length + b"\r\n"
    elif variant == "duplicate_authorization":
        length_headers = b"Content-Length: " + length + b"\r\n"
    else:
        raise AssertionError("unknown test variant")
    authorization = b"Authorization: Bearer " + TOKEN.encode() + b"\r\n"
    if variant == "duplicate_authorization":
        authorization = b"Authorization: Bearer attacker\r\n" + authorization
    request = (
        b"POST /notifications HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\n"
        + length_headers
        + authorization
        + b"Idempotency-Key: "
        + key.encode()
        + b"\r\n"
        + b"Content-Type: application/json\r\n"
        + b"Connection: close\r\n\r\n"
        + body
    )
    context = ssl.create_default_context(cafile=str(cert_path))
    with socket.create_connection(("127.0.0.1", port), timeout=3) as plain:
        with context.wrap_socket(plain, server_hostname="127.0.0.1") as tls:
            tls.sendall(request)
            return tls.recv(4096).split(b"\r\n", 1)[0]


def test_webhook_adapter_reaches_receiver_over_verified_loopback_tls(tmp_path):
    cert_path, key_path = _certificate(tmp_path)
    db_path = tmp_path / "receiver.sqlite3"
    notification = {
        "id": 1,
        "event": {"status": "analyzed"},
        "created_at": "2026-09-23T00:00:00+00:00",
    }

    async def scenario():
        receiver = NotificationReceiver(db_path, bearer_token=TOKEN)
        server, task, sock, port = await _start_server(receiver, cert_path, key_path)
        try:
            untrusted = await asyncio.to_thread(
                _adapter(port, _sender(None)).deliver, notification
            )
            assert untrusted.status is DeliveryStatus.RETRYABLE
            assert await asyncio.to_thread(_plain_http, port, notification) is None
            assert receiver.count() == 0

            accepted = await asyncio.to_thread(
                _adapter(port, _sender(cert_path)).deliver, notification
            )
            assert accepted.status is DeliveryStatus.ACCEPTED
            assert accepted.http_status == 204
            assert receiver.count() == 1
        finally:
            await _stop_server(server, task, sock)

        reopened = NotificationReceiver(db_path, bearer_token=TOKEN)
        server, task, sock, port = await _start_server(reopened, cert_path, key_path)
        try:
            duplicate = await asyncio.to_thread(
                _adapter(port, _sender(cert_path)).deliver, notification
            )
            assert duplicate.status is DeliveryStatus.ACCEPTED
            assert duplicate.http_status == 204
            assert reopened.count() == 1
        finally:
            await _stop_server(server, task, sock)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "variant", ["duplicate", "comma", "leading_zero", "duplicate_authorization"]
)
def test_ambiguous_wire_headers_are_rejected_before_receipt(tmp_path, variant):
    cert_path, key_path = _certificate(tmp_path)
    receiver = NotificationReceiver(tmp_path / "receiver.sqlite3", bearer_token=TOKEN)
    notification = {
        "id": 1,
        "event": {"status": "analyzed"},
        "created_at": "2026-09-23T00:00:00+00:00",
    }

    async def scenario():
        server, task, sock, port = await _start_server(receiver, cert_path, key_path)
        try:
            status = await asyncio.to_thread(
                _wire_header_variant, port, cert_path, notification, variant
            )
            assert b" 400 " in status
            assert receiver.count() == 0
        finally:
            await _stop_server(server, task, sock)

    asyncio.run(scenario())
