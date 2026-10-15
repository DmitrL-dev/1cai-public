"""Real POSIX pair/CLI boundaries and controlled partial stdout writes.

Constructed scanner records do not qualify native capture or macOS admission.
"""
from copy import deepcopy
import hashlib
import io
import json
import sys
from uuid import UUID

import pytest

from project_access_test_support import grant_membership, revoke_membership
from test_snapshot_diff_pair import pair
from rentgen_core import capabilities, cli, snapshot_diff as diff
from rentgen_core.context import Principal
from rentgen_core.errors import CoreError
from rentgen_core.local import LocalRuntime

pytestmark = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="Real POSIX pair output contract")


class BinaryCapture:
    def __init__(self, *, maximum=None):
        self.data, self.calls = bytearray(), []
        self.maximum, self.flushed = maximum, False

    def write(self, data):
        count = len(data) if self.maximum is None else min(self.maximum, len(data))
        self.data.extend(data[:count])
        self.calls.append((len(data), count))
        return count

    def flush(self):
        self.flushed = True


class StdoutCapture:
    def __init__(self, *, maximum=None):
        self.buffer, self.errors = BinaryCapture(maximum=maximum), io.StringIO()

    def write(self, text):
        return self.errors.write(text)

    def flush(self):
        return None


def argv(pair):
    return ["snapshot-diff", "--registry", str(pair["registry"]), "--identity-profile", str(pair["profile"]),
            "--project", pair["project_id"], "--before", pair["before"]["snapshot"].snapshot_id,
            "--after", pair["after"]["snapshot"].snapshot_id]


def trusted_adapter(pair, monkeypatch):
    # Public admission is checked separately below. Only the trusted unit
    # adapter seam is opened on Mac; actual Linux uses its genuine profile.
    if sys.platform == "darwin":
        original = cli.require_operation
        monkeypatch.setattr(cli, "require_operation", lambda name: None if name == "snapshot-diff" else original(name))
        monkeypatch.setattr(cli, "current_local_principal", lambda **options: pair["principal"])


def stored_bytes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def test_real_cli_read_preserves_stored_bytes_without_eager_resolver(pair, monkeypatch):
    trusted_adapter(pair, monkeypatch)
    monkeypatch.setattr(LocalRuntime, "resolve", lambda *a, **k: pytest.fail("CLI used eager single-snapshot resolver"))
    root = pair["state"].path.parent.parent
    before = stored_bytes(root)
    output = StdoutCapture()
    monkeypatch.setattr(cli.sys, "stdout", output)
    assert cli.main(argv(pair)) == 0
    assert output.buffer.flushed and not output.errors.getvalue()
    raw = bytes(output.buffer.data)
    assert raw.endswith(b"\n") and len(raw.splitlines()) == 1
    assert json.loads(raw)["result"]["changes"]
    assert b"catalog_digest" not in raw and b"deadline" not in raw
    assert stored_bytes(root) == before


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual macOS admission refusal")
def test_actual_macos_cli_refuses_before_identity_and_state(pair, monkeypatch):
    assert capabilities._platform == "darwin"
    monkeypatch.setattr(cli, "current_local_principal", lambda **k: pytest.fail("Denied operation resolved identity"))
    monkeypatch.setattr(cli, "_runtime", lambda *a, **k: pytest.fail("Denied operation resolved state"))
    output = StdoutCapture()
    monkeypatch.setattr(cli.sys, "stdout", output)
    assert cli.main(argv(pair)) == 2 and not output.buffer.data
    assert json.loads(output.errors.getvalue())["error"]["code"] == "CAPABILITY_UNAVAILABLE"


def test_failed_pair_error_rechecks_revocation_after_error_encoding(pair, monkeypatch):
    trusted_adapter(pair, monkeypatch)
    admin = Principal("error-output-admin", "local_os")
    with pair["state"].transaction(pair["principal"], write=True) as tx:
        grant_membership(tx, admin, {"project:read", "project:admin"})
    def refused(*args, **kwargs):
        raise CoreError("PRIVATE_FIXTURE_FAILURE", "PRIVATE_ERROR_DETAIL")
    monkeypatch.setattr(diff, "compare_retained_pair", refused)
    original, revoked = cli.json.dumps, False
    def encoded(value, *args, **kwargs):
        nonlocal revoked
        raw = original(value, *args, **kwargs)
        if type(value) is dict and value.get("error", {}).get("code") == "PRIVATE_FIXTURE_FAILURE" and not revoked:
            revoked = True
            with pair["state"].transaction(admin, write=True) as tx:
                revoke_membership(tx, pair["principal"])
        return raw
    monkeypatch.setattr(cli.json, "dumps", encoded)
    output = StdoutCapture()
    monkeypatch.setattr(cli.sys, "stdout", output)
    assert cli.main(argv(pair)) == 2 and revoked and not output.buffer.data
    raw = output.errors.getvalue()
    assert "PRIVATE_ERROR_DETAIL" not in raw
    assert json.loads(raw)["error"]["code"] == "PROJECT_FORBIDDEN"


def serialization_seam(pair, monkeypatch):
    operation = diff.compare_retained_pair(pair["runtime"], pair["principal"], pair["project_id"],
        pair["before"]["snapshot"].snapshot_id, pair["after"]["snapshot"].snapshot_id)
    value = deepcopy(operation.value)
    value["wire_probe"] = ""
    controlled = diff.DiffOperationResult(value, operation.output_scope)
    # Isolate the encoder's full-envelope bound using trusted test output. This
    # does not expand the genuine coordinator's separate 1 MiB page contract.
    def execute(args, *, proposal_scope):
        proposal_scope.diff_runtime, proposal_scope.diff_principal = pair["runtime"], pair["principal"]
        proposal_scope.diff_project_id = pair["project_id"]
        return cli._DiffCommandResult(controlled, pair["runtime"], pair["principal"])
    monkeypatch.setattr(cli, "_execute", execute)
    monkeypatch.setattr(cli, "uuid4", lambda: UUID("22222222-2222-4222-8222-222222222222"))
    return value


def test_complete_cli_utf8_envelope_accepts_exact_cap_and_refuses_one_more_byte(pair, monkeypatch):
    value = serialization_seam(pair, monkeypatch)
    value["wire_probe"] = "я\n\\\""
    baseline = StdoutCapture()
    monkeypatch.setattr(cli.sys, "stdout", baseline)
    assert cli.main(argv(pair)) == 0
    measured = len(baseline.buffer.data)
    value["wire_probe"] += "x" * (diff.MAX_DIFF_OUTPUT_BYTES - measured)
    exact = StdoutCapture()
    monkeypatch.setattr(cli.sys, "stdout", exact)
    assert cli.main(argv(pair)) == 0
    assert len(exact.buffer.data) == diff.MAX_DIFF_OUTPUT_BYTES and exact.buffer.data.endswith(b"\n")
    assert json.loads(exact.buffer.data)["result"]["wire_probe"] == value["wire_probe"]
    value["wire_probe"] += "x"
    above = StdoutCapture()
    monkeypatch.setattr(cli.sys, "stdout", above)
    assert cli.main(argv(pair)) == 2 and not above.buffer.data
    assert json.loads(above.errors.getvalue())["error"]["code"] == "OUTPUT_LIMIT_EXCEEDED"


def test_short_binary_stdout_writes_finish_the_complete_cli_json_frame(pair, monkeypatch):
    trusted_adapter(pair, monkeypatch)
    output = StdoutCapture(maximum=7)
    monkeypatch.setattr(cli.sys, "stdout", output)
    assert cli.main(argv(pair)) == 0 and len(output.buffer.calls) > 1
    assert json.loads(output.buffer.data)["result"]["changes"]
    assert output.buffer.data.endswith(b"\n") and not output.errors.getvalue()


@pytest.mark.parametrize("invalid", ["zero", "none", "negative", "boolean", "oversized"])
def test_invalid_binary_stdout_progress_refuses_success(pair, monkeypatch, invalid):
    trusted_adapter(pair, monkeypatch)
    output, calls = StdoutCapture(), []
    def refused(data):
        calls.append(len(data))
        return {"zero": 0, "none": None, "negative": -1, "boolean": True, "oversized": len(data) + 1}[invalid]
    output.buffer.write = refused
    monkeypatch.setattr(cli.sys, "stdout", output)
    assert cli.main(argv(pair)) == 2 and len(calls) == 1 and not output.buffer.data
    assert json.loads(output.errors.getvalue())["error"]["code"] == "LOCAL_IO_ERROR"


def test_short_text_stdout_fallback_keeps_complete_unicode_cli_frame(pair, monkeypatch):
    value = serialization_seam(pair, monkeypatch)
    value["wire_probe"] = "Кириллица\n\\\""
    class TextCapture:
        def __init__(self): self.parts, self.calls, self.flushed = [], 0, False
        def write(self, text):
            self.calls += 1
            self.parts.append(text[:3])
            return min(3, len(text))
        def flush(self): self.flushed = True
    output = TextCapture()
    monkeypatch.setattr(cli.sys, "stdout", output)
    assert cli.main(argv(pair)) == 0 and output.flushed and output.calls > 1
    text = "".join(output.parts)
    assert text.endswith("\n") and json.loads(text)["result"]["wire_probe"] == value["wire_probe"]
