"""Shared service-reachability helpers for integration probes.

These integration tests probe locally-hosted services (NocoBase, Portainer,
VS Code, Gitea, RabbitMQ, OPA, Wazuh, the collab WebSocket, ...). In a
serviceless CI environment those ports are closed, and the probes used to
hard-FAIL (``self.fail(...)`` / ``ConnectionRefusedError``). That made the gate
dishonest: an unreachable optional service looked like a broken build.

The helpers below turn "service not reachable" into a *skip* (via
``pytest.skip`` / ``unittest.SkipTest``) while leaving genuine assertion
failures (service reachable but misbehaving) intact.
"""

from __future__ import annotations

import socket
from contextlib import closing
from urllib.parse import urlparse

import pytest


def is_port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    """Return True iff a TCP connect to (host, port) succeeds quickly."""
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, port)) == 0
    except OSError:
        return False


def _host_port_from_url(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    if parsed.port:
        port = parsed.port
    else:
        port = 443 if parsed.scheme == "https" else 80
    return host, port


def skip_if_unreachable(url: str, name: str | None = None, timeout: float = 1.5) -> None:
    """``pytest.skip`` if the service behind ``url`` is not accepting connections.

    Works for both pytest-style and ``unittest.TestCase`` tests because
    ``pytest.skip`` raises ``Skipped``, which unittest also treats as a skip
    when running under pytest.
    """
    host, port = _host_port_from_url(url)
    if not is_port_open(host, port, timeout=timeout):
        label = name or url
        pytest.skip(f"{label} not reachable at {url} (port {port} closed); serviceless skip")
