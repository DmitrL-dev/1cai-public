"""CLI identity/flush contracts with injected native execution, not 1C acceptance."""
import io
import json
from pathlib import Path
from queue import Queue
import subprocess
import sys
from threading import Thread
from types import SimpleNamespace
from uuid import UUID

import pytest

from rentgen_core import capabilities, cli, platform_check
from rentgen_core.errors import CoreError
from test_stdio_native_archive import OPERATION, PROJECT, SNAPSHOT, _Runtime


def arguments(operation=None):
    args = ["proposal-platform-check", "--registry", "unused.sqlite3",
            "--project", PROJECT, "--snapshot", SNAPSHOT,
            "--proposal-json", "proposal.json", "--platform", "1cv8.exe",
            "--platform-sha256", "a" * 64]
    return args + (["--operation-id", operation] if operation is not None else [])


def configure(monkeypatch):
    runtime = _Runtime()
    monkeypatch.setattr(capabilities, "_platform", "win32")
    monkeypatch.setattr(cli, "_runtime", lambda _: runtime)
    monkeypatch.setattr(cli, "current_local_principal",
                        lambda: SimpleNamespace(id="tester", authority="local_os"))
    # Native retained payload IO is outside this transport-only fixture.
    monkeypatch.setattr(cli, "_proposal_input", lambda *a, **kw: b"proposal fixture")
    return runtime


@pytest.mark.parametrize("operation", [None, OPERATION])
@pytest.mark.parametrize("outcome", ["success", "interrupt", "failure", "revoked"])
def test_identity_is_flushed_before_execution_and_survives_failure(
    monkeypatch, capsys, operation, outcome
):
    runtime = configure(monkeypatch)
    class Stream(io.StringIO):
        flushed = False
        def flush(self):
            self.flushed = True
            super().flush()
    stream = Stream()
    monkeypatch.setattr(sys, "stderr", stream)
    calls = []

    def execute(ctx, raw, platform, *, limits, operation_id):
        assert stream.flushed
        identity = json.loads(stream.getvalue())["recovery"]
        assert identity == {"project_id": PROJECT, "operation_id": operation_id}
        assert str(UUID(operation_id)) == operation_id
        if operation is not None:
            assert operation_id == operation
        calls.append(operation_id)
        if outcome == "interrupt":
            raise KeyboardInterrupt()
        if outcome == "failure":
            raise CoreError("PLATFORM_RUN_INCOMPLETE", "Query retained status")
        if outcome == "revoked":
            runtime.revoked = True
        return {"run_id": operation_id, "marker": "withhold-after-revocation"}

    monkeypatch.setattr(platform_check, "check_proposal_platform_json", execute)
    assert cli.main(arguments(operation)) == (0 if outcome == "success" else 2)
    output = json.loads(capsys.readouterr().out)
    assert len(calls) == 1  # Failure/interruption never causes an automatic retry.
    assert len(stream.getvalue().splitlines()) == 1
    if outcome == "success":
        assert output["result"]["run_id"] == calls[0]
    else:
        assert "result" not in output
        assert output["error"]["code"] == {
            "interrupt": "OPERATION_INTERRUPTED", "failure": "PLATFORM_RUN_INCOMPLETE",
            "revoked": "PROJECT_FORBIDDEN",
        }[outcome]


@pytest.mark.parametrize("refusal", ["denied", "bad_id", "bad_profile", "unreadable", "unsupported", "revoked_during_read"])
def test_refusal_does_not_emit_identity_or_enter_executor(monkeypatch, capsys, refusal):
    runtime = configure(monkeypatch)
    args = arguments("invalid" if refusal == "bad_id" else None)
    if refusal == "denied":
        runtime.revoked = True
    if refusal == "bad_profile":
        args[args.index("--platform-sha256") + 1] = "invalid"
    if refusal == "unreadable":
        def unreadable(*a, **kw):
            raise OSError("missing payload")
        monkeypatch.setattr(cli, "_proposal_input", unreadable)
    if refusal == "unsupported":
        monkeypatch.setattr(capabilities, "_platform", "linux")
    if refusal == "revoked_during_read":
        def revoke(*a, **kw):
            runtime.revoked = True
            return b"proposal fixture"
        monkeypatch.setattr(cli, "_proposal_input", revoke)
    monkeypatch.setattr(platform_check, "check_proposal_platform_json",
                        lambda *a, **kw: pytest.fail("Refused request entered executor"))
    assert cli.main(args) == 2
    output = capsys.readouterr()
    assert output.err == ""
    assert "error" in json.loads(output.out)


def test_failed_identity_output_prevents_execution(monkeypatch, capsys):
    configure(monkeypatch)
    class BrokenStream(io.StringIO):
        def flush(self):
            raise OSError("recovery channel closed")
    monkeypatch.setattr(sys, "stderr", BrokenStream())
    calls = []
    monkeypatch.setattr(platform_check, "check_proposal_platform_json",
                        lambda *a, **kw: calls.append(1))
    assert cli.main(arguments()) == 2
    assert not calls
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "LOCAL_IO_ERROR"


def test_recovery_line_arrives_before_hard_process_exit(tmp_path):
    """A buffered pipe and killed CLI process; executor/runtime are synthetic."""
    root = Path(__file__).resolve().parents[2]
    marker = tmp_path / "entered.json"
    code = '''
import io, json, sys
from pathlib import Path
from threading import Event
sys.path.insert(0, str(Path.cwd() / "tests" / "unit"))
from test_platform_recovery_cli import arguments, configure
from rentgen_core import cli, platform_check
class Patcher:
    def setattr(self, obj, name, value): setattr(obj, name, value)
configure(Patcher())
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=False)
def execute(ctx, raw, platform, *, limits, operation_id):
    marker = Path(sys.argv[1])
    staging = marker.with_suffix(".tmp")
    staging.write_text(json.dumps({"operation_id": operation_id}))
    staging.replace(marker)
    Event().wait(60)
    raise AssertionError("Parent should terminate this process")
platform_check.check_proposal_platform_json = execute
raise SystemExit(cli.main(arguments()))
'''
    process = subprocess.Popen([sys.executable, "-c", code, str(marker)], cwd=root,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = Queue()
    reader = Thread(target=lambda: lines.put(process.stderr.readline()), daemon=True)
    reader.start()
    try:
        line = lines.get(timeout=15)
        identity = json.loads(line)["recovery"]
        assert identity["project_id"] == PROJECT
        assert str(UUID(identity["operation_id"])) == identity["operation_id"]
        # The executor marker also proves no successful result has been produced.
        import time
        until = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < until:
            time.sleep(0.01)
        assert json.loads(marker.read_text()) == {"operation_id": identity["operation_id"]}
        assert process.poll() is None
    finally:
        if process.poll() is None:
            process.kill()
        reader.join(timeout=5)
        stdout, stderr = process.communicate(timeout=5)
    assert not stdout and not stderr
