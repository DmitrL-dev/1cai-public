"""Real loopback HTTP and Rust ZIP GUI boundary tests; synthetic inputs only."""
import hashlib
import http.client
import json
from pathlib import Path
import socket
import sys
import threading
import time
from urllib.parse import quote

import pytest

from rentgen_core import gui
from rentgen_core.errors import CoreError
from rentgen_core.local_identity import initialize_local_identity
from rentgen_core.registry import ProjectRegistry
from test_rust_input_workflow import binary, zip_bytes
from test_metadata_three_way_materialize import PATH, xml

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Experimental GUI ZIP backend is Linux-only")


@pytest.fixture
def running(tmp_path, binary):
    identity = tmp_path / "private" / "identity.json"
    principal = initialize_local_identity(identity)
    source = tmp_path / "source"; source.mkdir()
    (source / "untouched.txt").write_text("untouched")
    registry = ProjectRegistry.create(tmp_path / "registry.sqlite3")
    project = registry.register(principal, source_root=source, state_root=tmp_path / "state", display_name="Synthetic GUI")
    config = gui.Config(registry.path, identity, project.project_id, *binary)
    app = gui.Workspace(config)
    server = gui.Server(app)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
    thread.start()
    yield app, server, tmp_path
    app.begin_close(); server.shutdown(); server.server_close(); app.close(); thread.join(timeout=2)
    assert not thread.is_alive()
    assert not Path(app.temp.name).exists()


def request(server, path, method="GET", body=None, headers=None, token=True):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=15)
    h = {"Origin": server.origin}
    if token:
        h["X-Rentgen-Session"] = server.workspace.token
    h.update(headers or {})
    connection.request(method, path, body, h)
    response = connection.getresponse()
    raw = response.read()
    result = (response.status, raw, dict(response.getheaders()))
    connection.close()
    return result


def post(server, path, data):
    status, raw, _ = request(server, path, "POST", json.dumps(data).encode(), {"Content-Type": "application/json"})
    return status, json.loads(raw)


def prepare(server, name="synthetic.zip"):
    status, result = post(server, "/api/import-start", {"filename": name})
    assert status == 201, result
    return result["job"]


def wait(server, job):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        status, raw, _ = request(server, "/api/job?job=" + job)
        assert status == 200, raw
        result = json.loads(raw)
        if result["status"] not in {"awaiting_upload", "uploading", "analyzing"}:
            return result
        time.sleep(.01)
    pytest.fail("GUI analysis did not finish")


def upload(server, raw):
    job = prepare(server)
    status, data, _ = request(server, "/api/import?job=" + job, "PUT", raw, {"Content-Type": "application/zip"})
    assert status == 202, data
    return job, wait(server, job)


def fixture_zip():
    return zip_bytes({PATH: xml("<Code>ARTICLE</Code>"), "CommonModules/Shared/Ext/Module.bsl": "Процедура Тест()\nКонецПроцедуры\n".encode()})


def test_real_upload_inventory_source_and_unchanged_project(running):
    app, server, root = running
    before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    raw = fixture_zip()
    job, outcome = upload(server, raw)
    assert outcome["status"] == "ready", outcome
    result = outcome["result"]
    assert result["counts"]["metadata_objects"] == 1
    assert result["counts"]["modules"] == 1
    assert result["coverage"]["bsl"] == "inventory_only"
    assert result["input"]["input_sha256"] == hashlib.sha256(raw).hexdigest()
    module = result["modules"][0]
    status, body, _ = request(server, "/api/source?job=" + job + "&path=" + quote(module["input_ref"]["relative_path"]))
    source = json.loads(body)
    assert status == 200 and "Процедура Тест" in source["text"]
    assert hashlib.sha256(source["text"].encode()).hexdigest() == source["input_ref"]["raw_sha256"]
    assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert app.current.path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("path", ["../../etc/passwd", "/etc/passwd", "Catalogs/Unknown.xml", "private/identity.json"])
def test_source_is_returned_inventory_only(running, path):
    _, server, _ = running
    job, outcome = upload(server, fixture_zip())
    assert outcome["status"] == "ready"
    status, raw, _ = request(server, "/api/source?job=" + job + "&path=" + quote(path))
    assert status == 400 and json.loads(raw)["error"] == "SOURCE_NOT_AVAILABLE"


@pytest.mark.parametrize("headers,token", [({}, False), ({"X-Rentgen-Session": "wrong"}, True), ({"Host": "evil.test"}, True), ({"Origin": "https://evil.test"}, True), ({"Origin": "null"}, True), ({"Sec-Fetch-Site": "cross-site"}, True), ({"Sec-Fetch-Site": "same-site"}, True)])
def test_transport_gate_denies_foreign_requests(running, headers, token):
    _, server, _ = running
    status, raw, _ = request(server, "/api/session", headers=headers, token=token)
    assert status == 401 and json.loads(raw) == {"error": "UNAUTHORIZED"}


def test_post_without_origin_rejected_and_static_csp(running):
    _, server, _ = running
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
    connection.request("POST", "/api/import-start", b'{}', {"X-Rentgen-Session": server.workspace.token, "Content-Type": "application/json"})
    response = connection.getresponse(); assert response.status == 401
    response.read(); connection.close()
    status, raw, headers = request(server, "/", token=False)
    assert status == 200 and b'lang="ru"' in raw
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in headers
    assert server.workspace.token.encode() not in raw


@pytest.mark.parametrize("name", ["../export.zip", "x\\evil.zip", "secret.txt", "bad\n.zip", "a" * 241 + ".zip"])
def test_client_filename_never_selects_filesystem(running, name):
    app, server, _ = running
    status, result = post(server, "/api/import-start", {"filename": name})
    assert status == 400 and result["error"] == "INVALID_UPLOAD"
    assert app.pending is None


def test_corrupt_archive_preserves_previous_result(running):
    app, server, _ = running
    first, outcome = upload(server, fixture_zip())
    assert outcome["status"] == "ready"
    path = app.current.path
    _, failed = upload(server, b"not a zip")
    assert failed["status"] == "error"
    assert app.current.id == first and path.exists()
    assert wait(server, first)["status"] == "ready"


def test_cancel_before_upload_and_busy(running):
    app, server, _ = running
    job = prepare(server)
    assert post(server, "/api/import-start", {"filename": "other.zip"})[0] == 409
    assert post(server, "/api/cancel", {"job": job})[0] == 200
    assert wait(server, job)["status"] == "cancelled"
    status, _, _ = request(server, "/api/import?job=" + job, "PUT", fixture_zip(), {"Content-Type": "application/zip"})
    assert status == 400
    assert not app.pending.path.exists()
    prepare(server)


def test_cancel_real_rust_process_is_reaped(running, monkeypatch):
    app, server, _ = running
    from rentgen_core import submitted_export
    entered = threading.Event(); proceed = threading.Event(); children = []
    original = submitted_export.RustInputSession.open_import
    def opened(session, *args):
        result = original(session, *args)
        children.append(session.process)
        entered.set()
        assert proceed.wait(5)
        return result
    monkeypatch.setattr(submitted_export.RustInputSession, "open_import", opened)
    job = prepare(server)
    assert request(server, "/api/import?job=" + job, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 202
    assert entered.wait(5)
    post(server, "/api/cancel", {"job": job}); proceed.set()
    result = wait(server, job)
    assert result["status"] == "cancelled" and result["error"] == "CANCELLED"
    assert children and all(child.poll() is not None for child in children)
    assert not app.pending.path.exists() and app.current is None


def test_upload_disconnect_cleans_partial_bytes(running):
    app, server, _ = running
    job = prepare(server)
    sock = socket.create_connection(("127.0.0.1", server.server_port))
    request_head = f"PUT /api/import?job={job} HTTP/1.0\r\nHost: {server.host}\r\nOrigin: {server.origin}\r\nX-Rentgen-Session: {app.token}\r\nContent-Type: application/zip\r\nContent-Length: 1000\r\n\r\n"
    sock.sendall(request_head.encode() + b"partial"); sock.close()
    result = wait(server, job)
    assert result["status"] == "error" and not app.pending.path.exists()


def test_result_release_rechecks_after_serialization(running, monkeypatch):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    assert outcome["status"] == "ready"
    original = gui.json.dumps
    revoked = threading.Event()
    original_auth = gui.Config.authorize
    def authorize(config):
        if revoked.is_set():
            raise CoreError("ACCESS_DENIED", "denied")
        return original_auth(config)
    def dumps(value, *args, **kwargs):
        result = original(value, *args, **kwargs)
        if isinstance(value, dict) and "result" in value:
            revoked.set()
        return result
    monkeypatch.setattr(gui.Config, "authorize", authorize)
    monkeypatch.setattr(gui.json, "dumps", dumps)
    status, raw, _ = request(server, "/api/job?job=" + job)
    assert status == 403 and json.loads(raw) == {"error": "FORBIDDEN"}
    assert b"input_ref" not in raw


def test_oversized_upload_rejected_before_body(running):
    app, server, _ = running
    job = prepare(server)
    status, raw, _ = request(server, "/api/import?job=" + job, "PUT", b"", {"Content-Type": "application/zip", "Content-Length": str(gui.MAX_UPLOAD + 1)})
    assert status == 400 and json.loads(raw)["error"] == "INVALID_UPLOAD"
    assert not app.pending.path.exists()


def test_reservation_expires_after_lost_browser(running):
    app, server, _ = running
    first = prepare(server)
    app.pending.created_at -= 31
    second = prepare(server)
    assert second != first and not app.pending.path.exists()


def test_completion_wins_late_cancel(running):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    assert outcome["status"] == "ready"
    status, cancelled = post(server, "/api/cancel", {"job": job})
    assert status == 200 and cancelled == {"status": "ready", "cancel_requested": False}
    assert wait(server, job)["status"] == "ready" and app.current.path.exists()


def test_error_release_rechecks_after_serialization(running, monkeypatch):
    _, server, _ = running
    original = gui.json.dumps
    original_auth = gui.Config.authorize
    revoked = threading.Event()
    def authorize(config):
        if revoked.is_set():
            raise CoreError("ACCESS_DENIED", "denied")
        return original_auth(config)
    def dumps(value, *args, **kwargs):
        result = original(value, *args, **kwargs)
        if isinstance(value, dict) and value.get("error") == "SOURCE_NOT_AVAILABLE":
            revoked.set()
        return result
    monkeypatch.setattr(gui.Config, "authorize", authorize)
    monkeypatch.setattr(gui.json, "dumps", dumps)
    status, raw, _ = request(server, "/api/job?job=unknown")
    assert status == 403 and json.loads(raw) == {"error": "FORBIDDEN"}


def test_real_upload_cancel_partial_stream_and_cleanup(running):
    app, server, _ = running
    job = prepare(server)
    sock = socket.create_connection(("127.0.0.1", server.server_port))
    head = f"PUT /api/import?job={job} HTTP/1.0\r\nHost: {server.host}\r\nOrigin: {server.origin}\r\nX-Rentgen-Session: {app.token}\r\nContent-Type: application/zip\r\nContent-Length: 1000\r\n\r\n"
    sock.sendall(head.encode() + b"partial")
    deadline = time.monotonic() + 3
    while app.pending.status == "awaiting_upload" and time.monotonic() < deadline:
        time.sleep(.01)
    assert post(server, "/api/cancel", {"job": job})[1]["cancel_requested"]
    sock.sendall(b"one more chunk"); sock.shutdown(socket.SHUT_WR)
    result = wait(server, job)
    sock.close()
    assert result["status"] == "cancelled" and not app.pending.path.exists()


def test_second_success_releases_previous_archive(running):
    app, server, _ = running
    first, _ = upload(server, fixture_zip())
    old = app.current.path
    second, result = upload(server, fixture_zip())
    assert result["status"] == "ready" and second != first and not old.exists()
    assert request(server, "/api/job?job=" + first)[0] == 400


def test_source_preview_size_and_encoding_bounds(running):
    _, server, _ = running
    for content, expected in [(b"a" * (gui.MAX_SOURCE + 1), "SOURCE_TOO_LARGE"), (b"\xffnot utf8", "SOURCE_ENCODING_UNSUPPORTED"), (b"has\x00control", "SOURCE_ENCODING_UNSUPPORTED")]:
        path = "CommonModules/Shared/Ext/Module.bsl"
        job, outcome = upload(server, zip_bytes({PATH: xml("<Code>ARTICLE</Code>"), path: content}))
        assert outcome["status"] == "ready", outcome
        status, raw, _ = request(server, "/api/source?job=" + job + "&path=" + quote(path))
        assert status == 400 and json.loads(raw)["error"] == expected


def test_stale_reservation_cannot_accept_bytes(running):
    app, server, _ = running
    job = prepare(server)
    app.pending.created_at -= 31
    status, raw, _ = request(server, "/api/import?job=" + job, "PUT", fixture_zip(), {"Content-Type": "application/zip"})
    assert status == 400 and json.loads(raw)["error"] == "UPLOAD_TIMEOUT"
    assert not app.pending.path.exists()


def test_non_ascii_token_is_unauthorized(running):
    _, server, _ = running
    status, raw, _ = request(server, "/api/session", headers={"X-Rentgen-Session": "é" * 43})
    assert status == 401 and json.loads(raw)["error"] == "UNAUTHORIZED"
